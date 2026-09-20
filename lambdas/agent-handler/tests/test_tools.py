"""Offline unit tests for weather tools. HTTP is stubbed; these run every time."""

import pytest

import tools


def test_get_current_weather_normalizes_shape(monkeypatch):
    def fake_http(url, params):
        if url == tools.GEO_URL:
            return [{"name": "Chennai", "country": "IN", "lat": 13.08, "lon": 80.27}]
        if url == tools.CURRENT_URL:
            return {
                "main": {"temp": 31.2, "feels_like": 37.0, "humidity": 74},
                "wind": {"speed": 3.6},
                "weather": [{"description": "haze", "icon": "50d"}],
            }
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(tools, "_http_get_json", fake_http)

    result = tools.get_current_weather("Chennai")

    assert result["location"] == "Chennai, IN"
    assert result["temp"] == 31.2
    assert result["humidity"] == 74
    assert result["wind_speed"] == 3.6
    assert result["description"] == "haze"
    assert result["icon"] == "50d"


def test_geocode_runs_before_weather(monkeypatch):
    """Geo endpoint resolves lat/lon first, then the weather endpoint receives them."""
    calls = []

    def fake_http(url, params):
        calls.append((url, params))
        if url == tools.GEO_URL:
            return [{"name": "Chennai", "country": "IN", "lat": 13.08, "lon": 80.27}]
        return {"main": {}, "weather": [{}]}

    monkeypatch.setattr(tools, "_http_get_json", fake_http)

    tools.get_current_weather("Chennai")

    assert calls[0][0] == tools.GEO_URL
    assert calls[1][0] == tools.CURRENT_URL
    assert calls[1][1]["lat"] == 13.08
    assert calls[1][1]["lon"] == 80.27


def test_unknown_location_raises(monkeypatch):
    monkeypatch.setattr(tools, "_http_get_json", lambda url, params: [])
    with pytest.raises(tools.LocationNotFoundError):
        tools.get_current_weather("Nowhereville")


def _geo_then(payload):
    """Build a stub that geocodes, then returns `payload` from the weather endpoint."""

    def fake_http(url, params):
        if url == tools.GEO_URL:
            return [{"name": "Delhi", "country": "IN", "lat": 28.6, "lon": 77.2}]
        return payload

    return fake_http


def test_get_forecast_aggregates_3hour_into_days(monkeypatch):
    payload = {
        "list": [
            {"dt_txt": "2024-01-01 12:00:00",
             "main": {"temp_min": 20, "temp_max": 33},
             "weather": [{"description": "clear sky", "icon": "01d"}], "pop": 0.1},
            {"dt_txt": "2024-01-01 15:00:00",
             "main": {"temp_min": 22, "temp_max": 34},
             "weather": [{"description": "haze", "icon": "50d"}], "pop": 0.2},
            {"dt_txt": "2024-01-02 12:00:00",
             "main": {"temp_min": 21, "temp_max": 32},
             "weather": [{"description": "rain", "icon": "10d"}], "pop": 0.6},
        ]
    }
    monkeypatch.setattr(tools, "_http_get_json", _geo_then(payload))

    result = tools.get_forecast("Delhi", days=7)  # more than available -> clamps

    assert result["location"] == "Delhi, IN"
    assert len(result["days"]) == 2  # two distinct dates present
    day0 = result["days"][0]
    assert day0["date"] == "2024-01-01"
    assert day0["temp_max"] == 34  # max across the day's entries
    assert day0["temp_min"] == 20  # min across the day's entries
    assert day0["description"] == "clear sky"  # midday (12:00) entry
    assert day0["pop"] == 0.2  # max pop across the day


def test_get_forecast_respects_days_limit(monkeypatch):
    payload = {
        "list": [
            {"dt_txt": "2024-01-01 12:00:00", "main": {"temp_min": 1, "temp_max": 2},
             "weather": [{"description": "a", "icon": "01d"}], "pop": 0},
            {"dt_txt": "2024-01-02 12:00:00", "main": {"temp_min": 3, "temp_max": 4},
             "weather": [{"description": "b", "icon": "02d"}], "pop": 0},
        ]
    }
    monkeypatch.setattr(tools, "_http_get_json", _geo_then(payload))
    assert len(tools.get_forecast("Delhi", days=1)["days"]) == 1


def _geo_country(country, name="Delhi"):
    """Stub _http_get_json so geocoding resolves to a given country."""

    def fake_http(url, params):
        if url == tools.GEO_URL:
            return [{"name": name, "country": country, "lat": 28.6, "lon": 77.2}]
        raise AssertionError("get_alerts should not call other OWM endpoints")

    return fake_http


def test_get_alerts_us_uses_nws(monkeypatch):
    monkeypatch.setattr(tools, "_http_get_json", _geo_country("US", name="Miami"))
    monkeypatch.setattr(
        tools, "_fetch_gdacs_alerts",
        lambda lat, lon: (_ for _ in ()).throw(AssertionError("US must not use GDACS")),
    )
    monkeypatch.setattr(
        tools, "_fetch_nws_alerts",
        lambda lat, lon: [{"event": "Hurricane Warning", "severity": "Extreme"}],
    )

    result = tools.get_alerts("Miami")

    assert result["alerts"][0]["event"] == "Hurricane Warning"
    assert "National Weather Service" in result["note"]


def test_get_alerts_non_us_uses_gdacs_and_reports_none(monkeypatch):
    monkeypatch.setattr(tools, "_http_get_json", _geo_country("IN"))
    monkeypatch.setattr(
        tools, "_fetch_nws_alerts",
        lambda lat, lon: (_ for _ in ()).throw(AssertionError("non-US must not use NWS")),
    )
    monkeypatch.setattr(tools, "_fetch_gdacs_alerts", lambda lat, lon: [])

    result = tools.get_alerts("Delhi")

    assert result["location"] == "Delhi, IN"
    assert result["alerts"] == []
    assert "No active alerts" in result["note"]
    assert "GDACS" in result["note"]


def test_get_alerts_unknown_location_raises(monkeypatch):
    monkeypatch.setattr(tools, "_http_get_json", lambda url, params: [])
    with pytest.raises(tools.LocationNotFoundError):
        tools.get_alerts("Nowhereville")


def test_activity_advisor_flags_rain(monkeypatch):
    payload = {"main": {"temp": 24, "humidity": 80}, "wind": {"speed": 3},
               "weather": [{"description": "light rain", "icon": "10d"}]}
    monkeypatch.setattr(tools, "_http_get_json", _geo_then(payload))
    result = tools.activity_advisor("Delhi", "cycling")
    assert "Not ideal" in result["advice"]
    assert result["activity"] == "cycling"


def test_activity_advisor_approves_clear(monkeypatch):
    payload = {"main": {"temp": 24, "humidity": 40}, "wind": {"speed": 3},
               "weather": [{"description": "clear sky", "icon": "01d"}]}
    monkeypatch.setattr(tools, "_http_get_json", _geo_then(payload))
    assert "Good conditions" in tools.activity_advisor("Delhi", "cycling")["advice"]
