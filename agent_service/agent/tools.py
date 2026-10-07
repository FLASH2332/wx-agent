"""Weather data access and the Strands tools built on top of it.

`WeatherClient` owns HTTP, the TTL cache and error mapping:
  - failures are never cached (the old lru_cache memoised `{}` forever);
  - successes expire after WEATHER_CACHE_TTL_SECONDS (cost decision: stays inside the
    OpenWeatherMap free tier and avoids repeat calls during multi-tool turns);
  - error messages never contain the API key.
"""

from __future__ import annotations

import datetime as _dt
import functools
import json
import logging
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable

from strands import tool

from ..errors import LocationNotFoundError, UpstreamError

logger = logging.getLogger(__name__)

GEO_URL = "https://api.openweathermap.org/geo/1.0/direct"
CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
NWS_URL = "https://api.weather.gov/alerts/active"
GDACS_URL = "https://www.gdacs.org/xml/rss.xml"
_UA = {"User-Agent": "WeatherBuddy/1.0"}
_MAX_CACHE_ENTRIES = 256


# Regions and nicknames that neither OpenWeatherMap nor Open-Meteo resolve (checked 2026-10), mapped to a
# town they do know. Matched on the first comma-separated part, case-insensitive. Extend as needed.
LOCATION_ALIASES = {
    "coorg": "Madikeri",
    "kodagu": "Madikeri",
}


def resolve_alias(location: str) -> str:
    key = (location or "").split(",")[0].strip().lower()
    return LOCATION_ALIASES.get(key, location)


NOT_FOUND_HINT = ("Retry ONCE with the nearest well-known town or the district headquarters; "
                  "if that also fails, tell the user the place could not be found.")


def _haversine(lat1, lon1, lat2, lon2):
    r = 6371
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class WeatherClient:
    def __init__(self, api_key: str, ttl_seconds: int = 600, timeout: float = 8,
                 opener: Callable | None = None, clock: Callable[[], float] = time.monotonic):
        self._api_key = api_key
        self._ttl = ttl_seconds
        self._timeout = timeout
        self._open = opener or urllib.request.urlopen
        self._clock = clock
        self._cache: dict[tuple, tuple[float, object]] = {}
        self._lock = threading.Lock()

    # -- cache ---------------------------------------------------------------
    def _cache_get(self, key):
        with self._lock:
            item = self._cache.get(key)
            if item and item[0] > self._clock():
                return item[1]
            self._cache.pop(key, None)
        return None

    def _cache_put(self, key, value):
        if self._ttl <= 0:
            return
        with self._lock:
            if len(self._cache) >= _MAX_CACHE_ENTRIES:
                self._cache.pop(min(self._cache, key=lambda k: self._cache[k][0]), None)
            self._cache[key] = (self._clock() + self._ttl, value)

    # -- HTTP ----------------------------------------------------------------
    def _get(self, url: str, params: dict | None, *, service: str, headers: dict | None = None, signed: bool = False):
        params = dict(params or {})
        key = (url, tuple(sorted((k, str(v)) for k, v in params.items())))
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        if signed:
            if not self._api_key:
                raise UpstreamError("OWM_API_KEY is not configured")
            params["appid"] = self._api_key
        full_url = f"{url}?{urllib.parse.urlencode(params)}" if params else url
        try:
            request = urllib.request.Request(full_url, headers=headers or _UA)
            with self._open(request, timeout=self._timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise UpstreamError(f"{service} rejected the API key (HTTP 401)") from None
            if exc.code == 429:
                raise UpstreamError(f"{service} rate limit reached (HTTP 429)") from None
            raise UpstreamError(f"{service} returned HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise UpstreamError(f"{service} is unreachable ({type(exc).__name__})") from None
        self._cache_put(key, body)
        return body

    def _json(self, url, params, *, service="OpenWeatherMap", signed=True):
        body = self._get(url, params, service=service, signed=signed)
        try:
            return json.loads(body)
        except ValueError:
            raise UpstreamError(f"{service} returned invalid JSON") from None

    # -- geocoding and weather ----------------------------------------------
    def geocode(self, location, user_lat=None, user_lon=None):
        results = self._json(GEO_URL, {"q": resolve_alias(location), "limit": 5})
        if not results:
            raise LocationNotFoundError(location)
        note = None
        if user_lat is not None and user_lon is not None and len(results) > 1:
            results = sorted(results, key=lambda r: _haversine(user_lat, user_lon, r.get("lat"), r.get("lon")))
            top = results[0]
            dist = _haversine(user_lat, user_lon, top.get("lat"), top.get("lon"))
            state = f"{top.get('state')}, " if top.get("state") else ""
            note = f"Resolved '{location}' to {top.get('name')}, {state}{top.get('country')} because it is {dist:.1f}km from your location."
        else:
            top = results[0]
        name, country, state = top.get("name", location), top.get("country"), top.get("state")
        display = f"{name}, {state}, {country}" if state else f"{name}, {country}" if country else name
        return top["lat"], top["lon"], display, country, note

    def current(self, location, units="metric", lang="en", user_lat=None, user_lon=None):
        lat, lon, display, _, note = self.geocode(location, user_lat, user_lon)
        payload = self._json(CURRENT_URL, {"lat": lat, "lon": lon, "units": units, "lang": lang})
        main, wind = payload.get("main", {}), payload.get("wind", {})
        weather = (payload.get("weather") or [{}])[0]
        data = {
            "location": display, "units": units,
            "temp": main.get("temp"), "feels_like": main.get("feels_like"), "humidity": main.get("humidity"),
            "wind_speed": wind.get("speed"), "description": weather.get("description"), "icon": weather.get("icon"),
        }
        if note:
            data["disambiguation_note"] = note
        return data

    def forecast(self, location, days=5, units="metric", lang="en", user_lat=None, user_lon=None):
        lat, lon, display, _, note = self.geocode(location, user_lat, user_lon)
        payload = self._json(FORECAST_URL, {"lat": lat, "lon": lon, "units": units, "lang": lang})
        entries = payload.get("list") or []
        data = {
            "location": display, "units": units,
            "hourly": extract_hourly(entries),
            "days": summarize_forecast_days(entries, max(1, int(days))),
        }
        if note:
            data["disambiguation_note"] = note
        return data

    def hourly_window(self, location, start_ts, end_ts, units="metric", lang="en", user_lat=None, user_lon=None):
        lat, lon, display, _, note = self.geocode(location, user_lat, user_lon)
        payload = self._json(FORECAST_URL, {"lat": lat, "lon": lon, "units": units, "lang": lang})
        rows = []
        for entry in payload.get("list") or []:
            if start_ts <= entry.get("dt", 0) <= end_ts:
                weather = (entry.get("weather") or [{}])[0]
                rows.append({
                    "dt_txt": entry.get("dt_txt"), "temp": entry.get("main", {}).get("temp"),
                    "description": weather.get("description"), "pop": entry.get("pop", 0),
                    "wind_speed": entry.get("wind", {}).get("speed", 0),
                })
        data = {"location": display, "units": units, "window_data": rows}
        if note:
            data["disambiguation_note"] = note
        return data

    def alerts(self, location, user_lat=None, user_lon=None):
        lat, lon, display, country, note = self.geocode(location, user_lat, user_lon)
        if country == "US":
            found, source = self._nws(lat, lon), "National Weather Service (US)"
        else:
            found, source = self._gdacs(lat, lon), "Global Disaster Alert and Coordination System (GDACS)"
        data = {
            "location": display, "alerts": found,
            "note": f"Alerts fetched from {source}" if found else f"No active alerts from {source}.",
        }
        if note:
            data["disambiguation_note"] = note
        return data

    def _nws(self, lat, lon):
        try:
            data = json.loads(self._get(NWS_URL, {"point": f"{lat},{lon}"}, service="NWS"))
        except (UpstreamError, ValueError) as exc:
            logger.warning("NWS alerts unavailable: %s", exc)
            return []
        out = []
        for feature in data.get("features", []):
            p = feature.get("properties", {})
            out.append({"event": p.get("event"), "headline": p.get("headline"),
                        "description": p.get("description"), "severity": p.get("severity")})
        return out

    def _gdacs(self, lat, lon):
        try:
            root = ET.fromstring(self._get(GDACS_URL, None, service="GDACS"))
        except (UpstreamError, ET.ParseError) as exc:
            logger.warning("GDACS alerts unavailable: %s", exc)
            return []
        ns = "{http://www.w3.org/2003/01/geo/wgs84_pos#}"
        out = []
        for item in root.findall(".//item"):
            glat, glon = item.find(f".//{ns}lat"), item.find(f".//{ns}long")
            if glat is None or glon is None:
                continue
            try:
                if abs(lat - float(glat.text)) < 5 and abs(lon - float(glon.text)) < 5:
                    title, desc = item.find("title"), item.find("description")
                    out.append({"event": title.text if title is not None else "Global Alert",
                                "description": desc.text if desc is not None else "", "source": "GDACS"})
            except (TypeError, ValueError):
                continue
        return out


def summarize_forecast_days(entries, max_days):
    by_date = defaultdict(list)
    for entry in entries:
        date = (entry.get("dt_txt") or "")[:10]
        if date:
            by_date[date].append(entry)
    days = []
    for date in sorted(by_date)[:max_days]:
        items = by_date[date]
        mins = [i["main"]["temp_min"] for i in items if "main" in i]
        maxs = [i["main"]["temp_max"] for i in items if "main" in i]
        midday = min(items, key=lambda i: abs(int((i.get("dt_txt") or "0 12")[11:13] or 12) - 12))
        weather = (midday.get("weather") or [{}])[0]
        days.append({
            "date": date, "temp_min": min(mins) if mins else None, "temp_max": max(maxs) if maxs else None,
            "description": weather.get("description"), "icon": weather.get("icon"),
            "pop": max((i.get("pop", 0) for i in items), default=0),
        })
    return days


def extract_hourly(entries, count=8):
    out = []
    for entry in entries[:count]:
        weather = (entry.get("weather") or [{}])[0]
        out.append({"dt_txt": entry.get("dt_txt"), "temp": entry.get("main", {}).get("temp"),
                    "description": weather.get("description"), "icon": weather.get("icon")})
    return out


def advise(activity, weather):
    temp = weather.get("temp")
    description = (weather.get("description") or "").lower()
    wind = weather.get("wind_speed") or 0
    wet = any(w in description for w in ("rain", "storm", "snow", "drizzle", "thunder"))
    reasons, suitable = [], True
    if wet:
        suitable = False
        reasons.append(f"there is {description}")
    if temp is not None and temp >= 35:
        suitable = False
        reasons.append(f"it is very hot ({temp}°)")
    if temp is not None and temp <= 5:
        suitable = False
        reasons.append(f"it is very cold ({temp}°)")
    if wind >= 12:
        suitable = False
        reasons.append(f"it is windy ({wind} m/s)")
    if suitable:
        verdict = f"Good conditions for {activity}."
        reasons.append(f"{description or 'clear skies'} at {temp}°")
    else:
        verdict = f"Not ideal for {activity}."
    return verdict + " " + "; ".join(reasons) + "."


@dataclass
class ToolDataCollector:
    """Full-fidelity weather payloads for the UI, captured as tools run. The model only ever sees the
    compact versions below, which is what keeps token usage (and rate-limit pressure) down."""
    weather: dict = field(default_factory=dict)
    forecast: dict = field(default_factory=dict)
    compare: dict = field(default_factory=dict)   # compact side-by-side data, also handed to the UI router


def _round(value, digits=1):
    return round(value, digits) if isinstance(value, (int, float)) else value


def _weekday(date_text) -> str:
    try:
        return _dt.date.fromisoformat(date_text).strftime("%A")
    except (TypeError, ValueError):
        return ""


def compact_current(data: dict) -> dict:
    keys = ("location", "temp", "feels_like", "humidity", "wind_speed", "description", "disambiguation_note")
    out = {k: _round(data.get(k)) for k in keys if data.get(k) is not None}
    out["units"] = data.get("units", "metric")
    return out


def compact_days(days: list) -> list:
    return [{"date": d.get("date"), "weekday": _weekday(d.get("date")), "min": _round(d.get("temp_min")),
             "max": _round(d.get("temp_max")), "rain_chance_pct": round((d.get("pop") or 0) * 100),
             "summary": d.get("description")} for d in days]


def compact_forecast(data: dict) -> dict:
    out = {"location": data.get("location"), "units": data.get("units", "metric"),
           "days": compact_days(data.get("days") or []),
           "next_hours": [{"time": (h.get("dt_txt") or "")[5:16], "temp": _round(h.get("temp")),
                           "summary": h.get("description")} for h in data.get("hourly") or []]}
    if data.get("disambiguation_note"):
        out["disambiguation_note"] = data["disambiguation_note"]
    return out


def _safe(fn):
    """Tools return an error object instead of raising, so the model can explain it
    (and so the response builders simply find no weather payload)."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except LocationNotFoundError as exc:
            return {"error": "location_not_found", "location": str(exc), "hint": NOT_FOUND_HINT}
        except UpstreamError as exc:
            return {"error": "weather_service_unavailable", "detail": str(exc)}
    return wrapper


def build_tools(client: WeatherClient, user_lat=None, user_lon=None, local_time=None,
                collector: ToolDataCollector | None = None):
    """Tools bound to this request's user context (location proximity, local time)."""
    collector = collector if collector is not None else ToolDataCollector()

    @tool
    @_safe
    def get_current_weather(location: str, units: str = "metric", lang: str = "en") -> dict:
        """Get the current temperature, humidity, wind, and sky conditions for ONE location."""
        data = client.current(location, units, lang, user_lat, user_lon)
        collector.weather = data
        return compact_current(data)

    @tool
    @_safe
    def get_forecast(location: str, days: int = 3, units: str = "metric", lang: str = "en") -> dict:
        """Get a daily forecast (with weekday names) plus the next 24 hours for ONE location."""
        data = client.forecast(location, days, units, lang, user_lat, user_lon)
        collector.forecast = data
        return compact_forecast(data)

    @tool
    @_safe
    def compare_locations(locations: list[str], days: int = 3, units: str = "metric", lang: str = "en") -> dict:
        """Compare 2-3 places in ONE call: current conditions and a compact daily forecast (with weekday
        names) for each. Use this instead of calling get_forecast once per place."""
        names = [n.strip() for n in locations if isinstance(n, str) and n.strip()][:3]
        if len(names) < 2:
            return {"error": "provide_at_least_two_locations"}

        def one(name):
            try:
                now = client.current(name, units, lang, user_lat, user_lon)
                forecast = client.forecast(name, days, units, lang, user_lat, user_lon)
            except LocationNotFoundError:
                return {"location": name, "error": "location_not_found", "hint": NOT_FOUND_HINT}
            except UpstreamError:
                return {"location": name, "error": "weather_service_unavailable"}
            current = compact_current(now)
            return {"location": now["location"],
                    "now": {k: v for k, v in current.items() if k not in ("location", "units")},
                    "days": compact_days(forecast.get("days") or [])}

        with ThreadPoolExecutor(max_workers=len(names)) as pool:
            result = {"units": units, "locations": list(pool.map(one, names))}
        collector.compare = result
        return result

    @tool
    @_safe
    def get_alerts(location: str) -> dict:
        """Get any active government-issued weather alerts or warnings for a location."""
        return client.alerts(location, user_lat, user_lon)

    @tool
    @_safe
    def activity_advisor(location: str, activity: str, lang: str = "en") -> dict:
        """Advise whether current weather at a location suits a given outdoor activity."""
        weather = client.current(location, lang=lang, user_lat=user_lat, user_lon=user_lon)
        collector.weather = weather
        return {"location": weather["location"], "activity": activity, "advice": advise(activity, weather),
                "weather": compact_current(weather)}

    @tool
    @_safe
    def get_hourly_window(location: str, start_ts: int, end_ts: int, units: str = "metric", lang: str = "en") -> dict:
        """Get precise hourly weather data for a Unix timestamp window (e.g. 'tonight' or 'tomorrow at 9am')."""
        return client.hourly_window(location, start_ts, end_ts, units, lang, user_lat, user_lon)

    @tool
    def parse_time_expression(phrase: str) -> dict:
        """Parse natural language time (like 'tonight', 'tomorrow 8am') into Unix timestamps."""
        try:
            from datetime import datetime, timezone

            import dateparser
        except ImportError:
            return {"error": "dateparser module not installed."}
        now = dateparser.parse(local_time) if local_time else datetime.now(timezone.utc)
        if now is None:
            now = datetime.now(timezone.utc)
        settings = {"RELATIVE_BASE": now, "TIMEZONE": now.tzname() or "UTC", "RETURN_AS_TIMEZONE_AWARE": True}
        parsed = dateparser.parse(phrase, settings=settings)
        if parsed:
            return {"parsed_time_iso": parsed.isoformat(), "parsed_time_unix": int(parsed.timestamp())}
        return {"error": f"Could not parse '{phrase}'"}

    return [get_current_weather, get_forecast, compare_locations, get_alerts, activity_advisor,
            get_hourly_window, parse_time_expression]
