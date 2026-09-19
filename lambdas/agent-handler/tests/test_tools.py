"""Offline unit tests for weather tools. HTTP is stubbed; these run every time."""

import pytest

import tools


def test_get_current_weather_normalizes_shape(monkeypatch):
    calls = []

    def fake_http(url, params):
        calls.append((url, params))
        if url == tools.GEO_URL:
            return [{"name": "Chennai", "country": "IN", "lat": 13.08, "lon": 80.27}]
        if url == tools.ONECALL_URL:
            return {
                "current": {
                    "temp": 31.2,
                    "feels_like": 37.0,
                    "humidity": 74,
                    "wind_speed": 3.6,
                    "weather": [{"description": "haze", "icon": "50d"}],
                }
            }
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(tools, "_http_get_json", fake_http)

    result = tools.get_current_weather("Chennai")

    assert result["location"] == "Chennai, IN"
    assert result["temp"] == 31.2
    assert result["humidity"] == 74
    assert result["description"] == "haze"
    assert result["icon"] == "50d"


def test_geocode_runs_before_weather(monkeypatch):
    """Rule 14: geo endpoint resolves lat/lon first, then One Call receives them."""
    calls = []

    def fake_http(url, params):
        calls.append((url, params))
        if url == tools.GEO_URL:
            return [{"name": "Chennai", "country": "IN", "lat": 13.08, "lon": 80.27}]
        return {"current": {"weather": [{}]}}

    monkeypatch.setattr(tools, "_http_get_json", fake_http)

    tools.get_current_weather("Chennai")

    assert calls[0][0] == tools.GEO_URL
    assert calls[1][0] == tools.ONECALL_URL
    assert calls[1][1]["lat"] == 13.08
    assert calls[1][1]["lon"] == 80.27


def test_unknown_location_raises(monkeypatch):
    monkeypatch.setattr(tools, "_http_get_json", lambda url, params: [])
    with pytest.raises(tools.LocationNotFoundError):
        tools.get_current_weather("Nowhereville")


def _geo_then(payload):
    """Build a stub that geocodes, then returns `payload` from One Call."""

    def fake_http(url, params):
        if url == tools.GEO_URL:
            return [{"name": "Delhi", "country": "IN", "lat": 28.6, "lon": 77.2}]
        return payload

    return fake_http


def test_get_forecast_clamps_and_shapes(monkeypatch):
    payload = {
        "daily": [
            {"dt": 1, "temp": {"min": 20, "max": 33}, "humidity": 40,
             "weather": [{"description": "clear sky", "icon": "01d"}], "pop": 0.1},
            {"dt": 2, "temp": {"min": 22, "max": 35},
             "weather": [{"description": "haze", "icon": "50d"}]},
        ]
    }
    monkeypatch.setattr(tools, "_http_get_json", _geo_then(payload))

    # request more days than available -> clamped to what's returned
    result = tools.get_forecast("Delhi", days=7)
    assert len(result["days"]) == 2
    assert result["days"][0]["temp_max"] == 33
    assert result["days"][0]["description"] == "clear sky"
    assert result["location"] == "Delhi, IN"


def test_get_alerts_empty_when_none(monkeypatch):
    monkeypatch.setattr(tools, "_http_get_json", _geo_then({}))
    assert tools.get_alerts("Delhi")["alerts"] == []


def test_get_alerts_normalizes(monkeypatch):
    payload = {"alerts": [{"event": "Heat wave", "sender_name": "IMD",
                           "start": 1, "end": 2, "description": "stay hydrated"}]}
    monkeypatch.setattr(tools, "_http_get_json", _geo_then(payload))
    alerts = tools.get_alerts("Delhi")["alerts"]
    assert alerts[0]["event"] == "Heat wave"
    assert alerts[0]["sender"] == "IMD"


def test_activity_advisor_flags_rain(monkeypatch):
    payload = {"current": {"temp": 24, "wind_speed": 3,
                           "weather": [{"description": "light rain", "icon": "10d"}]}}
    monkeypatch.setattr(tools, "_http_get_json", _geo_then(payload))
    result = tools.activity_advisor("Delhi", "cycling")
    assert "Not ideal" in result["advice"]
    assert result["activity"] == "cycling"


def test_activity_advisor_approves_clear(monkeypatch):
    payload = {"current": {"temp": 24, "wind_speed": 3,
                           "weather": [{"description": "clear sky", "icon": "01d"}]}}
    monkeypatch.setattr(tools, "_http_get_json", _geo_then(payload))
    assert "Good conditions" in tools.activity_advisor("Delhi", "cycling")["advice"]
