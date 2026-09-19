"""Weather tools for the Strands agent.

All tools resolve a location to lat/lon via the OWM geocoding endpoint
(AGENTS.md rule 14), then read weather from the One Call 3.0 endpoint.
Tools only call OWM or do pure computation — never Bedrock (rule 11).
"""

import json
import os
import urllib.parse
import urllib.request

from strands import tool

OWM_API_KEY = os.environ["OWM_API_KEY"]

GEO_URL = "https://api.openweathermap.org/geo/1.0/direct"
ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"

_HTTP_TIMEOUT = 8


class LocationNotFoundError(Exception):
    """Raised when the OWM geocoding endpoint returns no match for a location."""


def _http_get_json(url, params):
    """Perform a GET request and parse the JSON body."""
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"{url}?{query}", method="GET")
    with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def _geocode(location):
    """Resolve a location name to (lat, lon, resolved_name) via the OWM geo endpoint."""
    results = _http_get_json(
        GEO_URL, {"q": location, "limit": 1, "appid": OWM_API_KEY}
    )
    if not results:
        raise LocationNotFoundError(location)
    top = results[0]
    name = top.get("name", location)
    country = top.get("country")
    display = f"{name}, {country}" if country else name
    return top["lat"], top["lon"], display


def _onecall(lat, lon, units, exclude):
    """Fetch the One Call 3.0 payload for a coordinate."""
    return _http_get_json(
        ONECALL_URL,
        {
            "lat": lat,
            "lon": lon,
            "units": units,
            "exclude": ",".join(exclude),
            "appid": OWM_API_KEY,
        },
    )


def _current_weather_data(location, units="metric"):
    """Return normalized current-weather data for a location (shared internal helper).

    Used by the get_current_weather tool and by activity_advisor (rule 12), so the
    latter never has to invoke another tool through the agent.
    """
    lat, lon, display = _geocode(location)
    payload = _onecall(lat, lon, units, exclude=["minutely", "hourly", "daily"])
    current = payload.get("current", {})
    weather = (current.get("weather") or [{}])[0]
    return {
        "location": display,
        "units": units,
        "temp": current.get("temp"),
        "feels_like": current.get("feels_like"),
        "humidity": current.get("humidity"),
        "wind_speed": current.get("wind_speed"),
        "description": weather.get("description"),
        "icon": weather.get("icon"),
    }


@tool
def get_current_weather(location: str, units: str = "metric") -> dict:
    """Get the current temperature, humidity, wind, and sky conditions for a location."""
    return _current_weather_data(location, units)


@tool
def get_forecast(location: str, days: int = 3, units: str = "metric") -> dict:
    """Get a multi-day daily weather forecast (high/low, conditions) for a location."""
    lat, lon, display = _geocode(location)
    payload = _onecall(
        lat, lon, units, exclude=["current", "minutely", "hourly", "alerts"]
    )
    daily = payload.get("daily") or []
    days = max(1, min(int(days), len(daily))) if daily else 0
    forecast = []
    for entry in daily[:days]:
        temp = entry.get("temp") or {}
        weather = (entry.get("weather") or [{}])[0]
        forecast.append(
            {
                "dt": entry.get("dt"),
                "temp_min": temp.get("min"),
                "temp_max": temp.get("max"),
                "humidity": entry.get("humidity"),
                "description": weather.get("description"),
                "icon": weather.get("icon"),
                "pop": entry.get("pop"),
            }
        )
    return {"location": display, "units": units, "days": forecast}


@tool
def get_alerts(location: str) -> dict:
    """Get any active government-issued weather alerts or warnings for a location."""
    lat, lon, display = _geocode(location)
    payload = _onecall(
        lat, lon, "metric", exclude=["current", "minutely", "hourly", "daily"]
    )
    alerts = []
    for alert in payload.get("alerts") or []:
        alerts.append(
            {
                "event": alert.get("event"),
                "sender": alert.get("sender_name"),
                "start": alert.get("start"),
                "end": alert.get("end"),
                "description": alert.get("description"),
            }
        )
    return {"location": display, "alerts": alerts}


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
def activity_advisor(location: str, activity: str) -> dict:
    """Advise whether current weather at a location suits a given outdoor activity."""
    weather = _current_weather_data(location)
    return {
        "location": weather["location"],
        "activity": activity,
        "advice": _advise(activity, weather),
        "weather": weather,
    }
