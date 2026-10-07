import json
import urllib.error

import pytest

from agent_service.agent.tools import (ToolDataCollector, WeatherClient, advise, build_tools, compact_current,
                                        compact_forecast, summarize_forecast_days)
from agent_service.errors import LocationNotFoundError, UpstreamError

GEO = [{"name": "Paris", "lat": 48.85, "lon": 2.35, "country": "FR"}]
CURRENT = {"main": {"temp": 20, "feels_like": 19, "humidity": 50}, "wind": {"speed": 3},
           "weather": [{"description": "clear sky", "icon": "01d"}]}


class FakeResponse:
    def __init__(self, payload):
        self._body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Seq:
    """Marks a sequence of responses/exceptions to hand out in order (last one repeats)."""

    def __init__(self, *items):
        self.items = list(items)


class FakeOpener:
    """Routes by URL substring; a value is one payload (or exception), or a Seq of them."""

    def __init__(self, routes):
        self.routes = {k: list(v.items) if isinstance(v, Seq) else [v] for k, v in routes.items()}
        self.calls = []

    def __call__(self, request, timeout=None):
        url = request.full_url
        self.calls.append(url)
        for fragment, queue in self.routes.items():
            if fragment in url:
                item = queue.pop(0) if len(queue) > 1 else queue[0]
                if isinstance(item, Exception):
                    raise item
                return FakeResponse(item)
        raise AssertionError(f"unexpected URL {url}")


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_successful_calls_are_cached_within_ttl_and_expire_after():
    opener, clock = FakeOpener({"geo/1.0": GEO, "data/2.5/weather": CURRENT}), Clock()
    client = WeatherClient("k", ttl_seconds=60, opener=opener, clock=clock)
    client.current("Paris")
    client.current("Paris")
    assert len(opener.calls) == 2  # geocode + weather once each
    clock.now = 61
    client.current("Paris")
    assert len(opener.calls) == 4


def test_failures_are_never_cached():
    """Regression: lru_cache used to memoise {} and report 'Location not found' forever."""
    opener = FakeOpener({"geo/1.0": Seq(urllib.error.URLError("timeout"), GEO), "data/2.5/weather": CURRENT})
    client = WeatherClient("k", opener=opener)
    with pytest.raises(UpstreamError):
        client.current("Paris")
    assert client.current("Paris")["location"] == "Paris, FR"


def test_unknown_location_raises_location_not_found():
    client = WeatherClient("k", opener=FakeOpener({"geo/1.0": []}))
    with pytest.raises(LocationNotFoundError):
        client.current("Nowhereville")


def test_errors_never_contain_the_api_key():
    err = urllib.error.HTTPError("https://x?appid=SECRET", 401, "unauthorized", {}, None)
    client = WeatherClient("SECRET", opener=FakeOpener({"geo/1.0": err}))
    with pytest.raises(UpstreamError) as info:
        client.current("Paris")
    assert "SECRET" not in str(info.value) and "401" in str(info.value)


def test_missing_api_key_is_reported_not_sent():
    with pytest.raises(UpstreamError, match="OWM_API_KEY"):
        WeatherClient("", opener=FakeOpener({})).geocode("Paris")


def test_disambiguation_prefers_closest_match_and_adds_note():
    results = [{"name": "Springfield", "state": "Missouri", "country": "US", "lat": 37.2, "lon": -93.3},
               {"name": "Springfield", "state": "Illinois", "country": "US", "lat": 39.8, "lon": -89.6}]
    client = WeatherClient("k", opener=FakeOpener({"geo/1.0": results}))
    lat, lon, display, country, note = client.geocode("Springfield", user_lat=40.0, user_lon=-89.0)
    assert display == "Springfield, Illinois, US" and "km from your location" in note


def test_forecast_summary_and_hourly():
    entries = [{"dt_txt": "2026-01-01 12:00:00", "main": {"temp_min": 1, "temp_max": 5}, "pop": 0.4,
                "weather": [{"description": "rain", "icon": "10d"}]},
               {"dt_txt": "2026-01-02 12:00:00", "main": {"temp_min": 2, "temp_max": 6}, "weather": [{}]}]
    days = summarize_forecast_days(entries, 1)
    assert len(days) == 1 and days[0]["temp_max"] == 5 and days[0]["pop"] == 0.4


def test_hourly_window_filters_by_timestamp():
    payload = {"list": [{"dt": 100, "dt_txt": "a", "main": {"temp": 1}, "weather": [{}]},
                        {"dt": 200, "dt_txt": "b", "main": {"temp": 2}, "weather": [{}]}]}
    client = WeatherClient("k", opener=FakeOpener({"geo/1.0": GEO, "data/2.5/forecast": payload}))
    rows = client.hourly_window("Paris", 150, 250)["window_data"]
    assert [r["dt_txt"] for r in rows] == ["b"]


def test_alerts_failure_returns_empty_instead_of_raising():
    opener = FakeOpener({"geo/1.0": GEO, "gdacs": urllib.error.URLError("down")})
    data = WeatherClient("k", opener=opener).alerts("Paris")
    assert data["alerts"] == [] and "No active alerts" in data["note"]


def test_advise():
    assert advise("hiking", {"temp": 20, "description": "clear", "wind_speed": 2}).startswith("Good conditions")
    assert "rain" in advise("hiking", {"temp": 20, "description": "light rain", "wind_speed": 2})


def test_tools_return_error_objects_instead_of_raising():
    client = WeatherClient("k", opener=FakeOpener({"geo/1.0": []}))
    tools = {t.tool_name: t for t in build_tools(client)}
    assert set(tools) == {"get_current_weather", "get_forecast", "compare_locations", "get_alerts", "activity_advisor",
                          "get_hourly_window", "parse_time_expression"}
    assert tools["get_current_weather"]("Nowhere")["error"] == "location_not_found"
    down = WeatherClient("k", opener=FakeOpener({"geo/1.0": urllib.error.URLError("x")}))
    assert {t.tool_name: t for t in build_tools(down)}["get_forecast"]("Paris")["error"] == "weather_service_unavailable"


FORECAST = {"list": [
    {"dt": 1, "dt_txt": "2026-10-10 12:00:00", "main": {"temp": 21.37, "temp_min": 15.04, "temp_max": 22.96}, "pop": 0.62,
     "weather": [{"description": "light rain", "icon": "10d"}]},
    {"dt": 2, "dt_txt": "2026-10-11 12:00:00", "main": {"temp": 19, "temp_min": 14, "temp_max": 20}, "pop": 0,
     "weather": [{"description": "clear sky", "icon": "01d"}]},
]}


def _client(opener_routes=None):
    routes = {"geo/1.0": GEO, "data/2.5/weather": CURRENT, "data/2.5/forecast": FORECAST}
    routes.update(opener_routes or {})
    return WeatherClient("k", opener=FakeOpener(routes))


def test_compact_outputs_drop_icons_round_numbers_and_add_weekdays():
    full = _client().forecast("Paris", 2)
    compact = compact_forecast(full)
    assert compact["days"][0] == {"date": "2026-10-10", "weekday": "Saturday", "min": 15.0, "max": 23.0,
                                  "rain_chance_pct": 62, "summary": "light rain"}
    assert "icon" not in json.dumps(compact)
    assert len(json.dumps(compact)) < len(json.dumps(full))  # fewer tokens for the model
    assert "icon" not in compact_current(_client().current("Paris"))


def test_single_location_tools_return_compact_data_but_keep_full_data_for_the_ui():
    collector = ToolDataCollector()
    tools = {t.tool_name: t for t in build_tools(_client(), collector=collector)}
    seen_by_model = tools["get_forecast"]("Paris", 2)
    assert "icon" not in json.dumps(seen_by_model) and seen_by_model["days"][0]["weekday"] == "Saturday"
    assert collector.forecast["days"][0]["icon"] == "10d"        # the UI still gets icons
    tools["get_current_weather"]("Paris")
    assert collector.weather["icon"] == "01d" and collector.weather["location"] == "Paris, FR"


def test_compare_locations_is_one_call_for_all_places_with_per_place_errors():
    opener = FakeOpener({"geo/1.0": GEO, "data/2.5/weather": CURRENT, "data/2.5/forecast": FORECAST})
    tools = {t.tool_name: t for t in build_tools(WeatherClient("k", opener=opener))}
    result = tools["compare_locations"](["Paris", "Rome"], 2)
    assert [loc["location"] for loc in result["locations"]] == ["Paris, FR", "Paris, FR"]  # fake geocoder returns Paris
    first = result["locations"][0]
    assert first["now"]["temp"] == 20 and first["days"][0]["weekday"] == "Saturday" and "icon" not in json.dumps(result)
    assert tools["compare_locations"](["Paris"])["error"] == "provide_at_least_two_locations"
    assert len(tools["compare_locations"](["A", "B", "C", "D", "E"])["locations"]) == 3  # capped


def test_compare_locations_reports_a_failing_place_without_failing_the_call():
    class Router:
        calls = 0

        def __call__(self, request, timeout=None):
            url = request.full_url
            if "geo/1.0" in url:
                return FakeResponse([] if "Atlantis" in url else GEO)
            return FakeResponse(CURRENT if "weather" in url else FORECAST)

    tools = {t.tool_name: t for t in build_tools(WeatherClient("k", opener=Router()))}
    result = tools["compare_locations"](["Paris", "Atlantis"], 2)
    by_name = {loc["location"]: loc for loc in result["locations"]}
    assert by_name["Atlantis"]["error"] == "location_not_found" and "now" in by_name["Paris, FR"]


def test_unknown_regions_are_resolved_through_aliases_and_report_a_retry_hint():
    """'Coorg' (a default suggestion chip) is unknown to OpenWeatherMap and Open-Meteo."""
    from agent_service.agent.tools import resolve_alias

    assert resolve_alias("Coorg") == "Madikeri" and resolve_alias("coorg, Karnataka") == "Madikeri"
    assert resolve_alias("Goa") == "Goa"
    seen = []

    def opener(request, timeout=None):
        seen.append(request.full_url)
        return FakeResponse(GEO if "Madikeri" in request.full_url else [])

    client = WeatherClient("k", opener=FakeOpener({}))
    client._open = opener
    assert client.geocode("Coorg")[2] == "Paris, FR" and "q=Madikeri" in seen[0]   # the fake geocoder answers any alias

    tools = {t.tool_name: t for t in build_tools(WeatherClient("k", opener=FakeOpener({"geo/1.0": []})))}
    result = tools["get_current_weather"]("Nowhereville")
    assert result["error"] == "location_not_found" and "Retry ONCE" in result["hint"]


def test_compare_locations_keeps_its_compact_result_for_the_router():
    collector = ToolDataCollector()
    opener = FakeOpener({"geo/1.0": GEO, "data/2.5/weather": CURRENT, "data/2.5/forecast": FORECAST})
    tools = {t.tool_name: t for t in build_tools(WeatherClient("k", opener=opener), collector=collector)}
    result = tools["compare_locations"](["Paris", "Rome"], 2)
    assert collector.compare == result and collector.compare["locations"][0]["now"]["humidity"] == 50
