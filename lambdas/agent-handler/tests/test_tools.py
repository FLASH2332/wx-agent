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
