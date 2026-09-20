"""Weather tools for the Strands agent.

All tools resolve a location to lat/lon via the OWM geocoding endpoint, then read
weather from the free-tier v2.5 endpoints (/weather for current, /forecast for the
5-day/3-hour forecast). Tools only call OWM or do pure computation — never Bedrock.

Note: the free tier has no weather-alerts endpoint, so get_alerts reports that none
are available rather than calling a paid API.
"""

import json
import logging
import os
import urllib.parse
import urllib.request
from collections import defaultdict
from functools import lru_cache

from strands import tool

logger = logging.getLogger(__name__)

OWM_API_KEY = os.environ["OWM_API_KEY"]

GEO_URL = "https://api.openweathermap.org/geo/1.0/direct"
CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

_HTTP_TIMEOUT = 8


class LocationNotFoundError(Exception):
    """Raised when the OWM geocoding endpoint returns no match for a location."""


@lru_cache(maxsize=128)
def _http_get_json_cached(url: str, qs: str):
    """Cached internal helper for HTTP requests."""
    full_url = f"{url}?{qs}"
    try:
        req = urllib.request.Request(full_url, headers={"User-Agent": "WeatherBuddy/1.0"})
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"HTTP GET failed for {full_url}: {e}")
        return {}


def _http_get_json(url, params):
    """Log the call (without the API key), then serialize params for the lru_cache."""
    # Log each OWM call so multi-city queries are visible.
    location = params.get("q") or f"{params.get('lat')},{params.get('lon')}"
    logger.info("OWM request: %s (%s)", url.rsplit("/", 1)[-1], location)
    qs = urllib.parse.urlencode(params)
    return _http_get_json_cached(url, qs)


def _geocode(location):
    """Resolve a location name to (lat, lon, resolved_name, country) via the OWM geo endpoint."""
    results = _http_get_json(
        GEO_URL, {"q": location, "limit": 1, "appid": OWM_API_KEY}
    )
    if not results:
        raise LocationNotFoundError(location)
    top = results[0]
    name = top.get("name", location)
    country = top.get("country")
    display = f"{name}, {country}" if country else name
    return top["lat"], top["lon"], display, country


def _current_weather_data(location, units="metric", lang="en"):
    """Return normalized current-weather data for a location (shared internal helper).

    Used by the get_current_weather tool and by activity_advisor, so the latter
    never has to invoke another tool through the agent.
    """
    lat, lon, display, _ = _geocode(location)
    payload = _http_get_json(
        CURRENT_URL, {"lat": lat, "lon": lon, "units": units, "lang": lang, "appid": OWM_API_KEY}
    )
    main = payload.get("main", {})
    wind = payload.get("wind", {})
    weather = (payload.get("weather") or [{}])[0]
    return {
        "location": display,
        "units": units,
        "temp": main.get("temp"),
        "feels_like": main.get("feels_like"),
        "humidity": main.get("humidity"),
        "wind_speed": wind.get("speed"),
        "description": weather.get("description"),
        "icon": weather.get("icon"),
    }


@tool
def get_current_weather(location: str, units: str = "metric", lang: str = "en") -> dict:
    """Get the current temperature, humidity, wind, and sky conditions for a location."""
    return _current_weather_data(location, units, lang)


def _summarize_forecast_days(entries, max_days):
    """Aggregate 3-hour forecast entries into per-day summaries (high/low/conditions)."""
    by_date = defaultdict(list)
    for entry in entries:
        date = (entry.get("dt_txt") or "")[:10]
        if date:
            by_date[date].append(entry)

    days = []
    for date in sorted(by_date)[:max_days]:
        items = by_date[date]
        temps_min = [i["main"]["temp_min"] for i in items if "main" in i]
        temps_max = [i["main"]["temp_max"] for i in items if "main" in i]
        # Representative conditions: the entry nearest midday, else the first.
        midday = min(
            items, key=lambda i: abs(int((i.get("dt_txt") or "0 12")[11:13] or 12) - 12)
        )
        weather = (midday.get("weather") or [{}])[0]
        days.append(
            {
                "date": date,
                "temp_min": min(temps_min) if temps_min else None,
                "temp_max": max(temps_max) if temps_max else None,
                "description": weather.get("description"),
                "icon": weather.get("icon"),
                "pop": max((i.get("pop", 0) for i in items), default=0),
            }
        )
    return days


def _extract_hourly(entries, count=8):
    """Extract the next 24 hours (8 3-hour slots) of raw forecast data."""
    hourly = []
    for entry in entries[:count]:
        weather = (entry.get("weather") or [{}])[0]
        hourly.append({
            "dt_txt": entry.get("dt_txt"),
            "temp": entry.get("main", {}).get("temp"),
            "description": weather.get("description"),
            "icon": weather.get("icon")
        })
    return hourly


def _forecast_data(location, days=5, units="metric", lang="en"):
    lat, lon, display, _ = _geocode(location)
    payload = _http_get_json(
        FORECAST_URL, {"lat": lat, "lon": lon, "units": units, "lang": lang, "appid": OWM_API_KEY}
    )
    max_days = max(1, int(days))
    return {
        "location": display,
        "units": units,
        "hourly": _extract_hourly(payload.get("list") or []),
        "days": _summarize_forecast_days(payload.get("list") or [], max_days),
    }


@tool
def get_forecast(location: str, days: int = 3, units: str = "metric", lang: str = "en") -> dict:
    """Get a multi-day daily weather forecast (high/low, conditions) for a location."""
    return _forecast_data(location, days, units, lang)


def _fetch_nws_alerts(lat, lon):
    try:
        req = urllib.request.Request(
            f"https://api.weather.gov/alerts/active?point={lat},{lon}",
            headers={"User-Agent": "WeatherBuddy/1.0"}
        )
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
        
        alerts = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            alerts.append({
                "event": props.get("event"),
                "headline": props.get("headline"),
                "description": props.get("description"),
                "severity": props.get("severity")
            })
        return alerts
    except Exception as e:
        print(f"NWS Error: {e}")
        return []


def _fetch_gdacs_alerts(lat, lon):
    try:
        req = urllib.request.Request("https://www.gdacs.org/xml/rss.xml")
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as response:
            xml_data = response.read()
        
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_data)
        alerts = []
        for item in root.findall(".//item"):
            geo_lat = item.find(".//{http://www.w3.org/2003/01/geo/wgs84_pos#}lat")
            geo_lon = item.find(".//{http://www.w3.org/2003/01/geo/wgs84_pos#}long")
            
            if geo_lat is not None and geo_lon is not None:
                item_lat = float(geo_lat.text)
                item_lon = float(geo_lon.text)
                
                # Check rough distance (within ~5 degrees lat/lon)
                if abs(lat - item_lat) < 5 and abs(lon - item_lon) < 5:
                    title = item.find("title")
                    desc = item.find("description")
                    alerts.append({
                        "event": title.text if title is not None else "Global Alert",
                        "description": desc.text if desc is not None else "",
                        "source": "GDACS"
                    })
        return alerts
    except Exception as e:
        print(f"GDACS Error: {e}")
        return []


@tool
def get_alerts(location: str) -> dict:
    """Get any active government-issued weather alerts or warnings for a location."""
    lat, lon, display, country = _geocode(location)
    
    if country == "US":
        alerts = _fetch_nws_alerts(lat, lon)
        source = "National Weather Service (US)"
    else:
        alerts = _fetch_gdacs_alerts(lat, lon)
        source = "Global Disaster Alert and Coordination System (GDACS)"
        
    return {
        "location": display,
        "alerts": alerts,
        "note": f"Alerts fetched from {source}" if alerts else f"No active alerts from {source}."
    }


def _advise(activity, weather):
    """Pure-computation activity recommendation from current-weather data."""
    temp = weather.get("temp")
    description = (weather.get("description") or "").lower()
    wind = weather.get("wind_speed") or 0
    wet = any(w in description for w in ("rain", "storm", "snow", "drizzle", "thunder"))

    reasons = []
    suitable = True
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


@tool
def activity_advisor(location: str, activity: str, lang: str = "en") -> dict:
    """Advise whether current weather at a location suits a given outdoor activity."""
    weather = _current_weather_data(location, lang=lang)
    return {
        "location": weather["location"],
        "activity": activity,
        "advice": _advise(activity, weather),
        "weather": weather,
    }
