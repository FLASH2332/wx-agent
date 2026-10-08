from types import SimpleNamespace

import pytest

from agent_service.agent import router, runner
from agent_service.agent.runner import TurnRequest, run_turn
from agent_service.errors import ServiceError
from agent_service.providers.base import ProviderChain
from agent_service.providers.translate import Translator

CURRENT = {"location": "Paris, FR", "temp": 20, "humidity": 50, "description": "clear"}


def _user(text):
    return {"role": "user", "content": [{"text": text}]}


class FakeAgent:
    """Stands in for strands.Agent: records constructor kwargs, returns scripted output."""
    instances = []
    answer = "Analyst: sunny in Paris."
    raises = None
    tool_payload = CURRENT
    collector = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.messages = list(kwargs["messages"])
        FakeAgent.instances.append(self)

    def __call__(self, text):
        self.asked = text
        if FakeAgent.raises:
            raise FakeAgent.raises
        self.messages.append(_user(text))
        self.messages.append({"role": "assistant", "content": [{"toolUse": {"name": "get_current_weather"}}]})
        self.messages.append({"role": "user", "content": [{"toolResult": {"content": [{"json": FakeAgent.tool_payload}]}}]})
        if FakeAgent.tool_payload and FakeAgent.collector is not None:
            FakeAgent.collector.weather = FakeAgent.tool_payload  # what the real tools do
        reply = {"role": "assistant", "content": [{"text": FakeAgent.answer}]}
        self.messages.append(reply)
        return SimpleNamespace(message=reply)


@pytest.fixture(autouse=True)
def fake_agent(monkeypatch):
    FakeAgent.instances, FakeAgent.answer, FakeAgent.raises, FakeAgent.tool_payload = [], "Analyst: sunny in Paris.", None, CURRENT
    monkeypatch.setattr(runner, "Agent", FakeAgent)

    def fake_build_tools(client, lat, lon, local_time, collector):
        FakeAgent.collector = collector
        return []

    monkeypatch.setattr(runner, "build_tools", fake_build_tools)
    monkeypatch.setattr(runner, "get_model", lambda settings: object())


@pytest.fixture
def routed(monkeypatch):
    seen = {}

    def fake_route(settings, *, user_text, analyst_text, lang, tool_data=""):
        seen.update(user_text=user_text, analyst_text=analyst_text, lang=lang, tool_data=tool_data)
        return router.UiPayload(ui_mode="dashboard", short_answer="Sunny."), False

    monkeypatch.setattr(router, "route", fake_route)
    return seen


def test_turn_returns_router_payload_and_tool_data(settings, routed):
    result = run_turn(settings, TurnRequest(text="weather in Paris?", lang="en"))
    assert result.payload.short_answer == "Sunny." and result.payload.ui_mode == "dashboard"
    assert result.weather_data == CURRENT and result.tools_used == ["get_current_weather"]
    assert routed["analyst_text"] == "Analyst: sunny in Paris." and routed["lang"] == "en"


def test_history_is_limited_text_only_and_starts_with_user(make_settings, routed):
    history = [_user("a"), {"role": "assistant", "content": [{"text": "b"}]},
               _user("c"), {"role": "assistant", "content": [{"text": "d"}]},
               _user("e"), {"role": "assistant", "content": [{"text": "f"}]}]
    run_turn(make_settings(HISTORY_MESSAGES=3), TurnRequest(text="new", history=history))
    sent = FakeAgent.instances[0].kwargs["messages"]
    assert [m["content"][0]["text"] for m in sent] == ["e", "f"]  # 3-window trimmed to start on a user turn
    assert FakeAgent.instances[0].asked == "new"


def test_system_prompt_carries_language_time_and_context(settings, routed):
    run_turn(settings, TurnRequest(text="q", lang="fr", context_location="Lyon, FR",
                                   local_time="2026-10-06T20:00:00Z", user_lat=1.5, user_lon=2.5))
    prompt = FakeAgent.instances[0].kwargs["system_prompt"]
    assert "'fr'" in prompt and "Lyon, FR" in prompt and "2026-10-06T20:00:00Z" in prompt and "(1.5, 2.5)" in prompt
    assert "resolve_location" not in prompt  # phantom tool removed


def test_comparison_mode_clears_single_city_dashboard_data(settings, monkeypatch):
    comparison = router.UiPayload.model_validate({
        "ui_mode": "comparison", "short_answer": "Paris wins.",
        "comparison_data": {"winner": "Paris", "locations": [{"name": "Paris"}, {"name": "Rome"}]}})
    monkeypatch.setattr(router, "route", lambda *a, **k: (comparison, False))
    result = run_turn(settings, TurnRequest(text="compare"))
    assert result.weather_data == {} and result.forecast_data == {}


def test_rate_limit_becomes_localized_429(settings, routed):
    class RateLimitError(Exception):
        pass

    FakeAgent.raises = RateLimitError("429 too many requests")
    with pytest.raises(ServiceError) as info:
        run_turn(settings, TurnRequest(text="q", lang="fr"))
    assert info.value.status == 429 and "demandes" in info.value.message


def test_other_agent_failures_become_502_without_leaking_details(settings, routed):
    FakeAgent.raises = RuntimeError("secret internal detail: key=abc")
    with pytest.raises(ServiceError) as info:
        run_turn(settings, TurnRequest(text="q"))
    assert info.value.status == 502 and "secret" not in info.value.message


def test_empty_analyst_answer_skips_router_and_asks_to_rephrase(settings, monkeypatch):
    monkeypatch.setattr(router, "route", lambda *a, **k: pytest.fail("router must not run (cost)"))
    FakeAgent.answer = "   "
    result = run_turn(settings, TurnRequest(text="q", lang="de"))
    assert result.payload.ui_mode == "chat" and "umformulieren" in result.payload.short_answer


class FakeTranslateProvider:
    name = "fake"

    def translate(self, text, source, target):
        return f"<{source}->{target}> {text}"


def test_translate_pivot_translates_question_in_and_answer_out(make_settings, routed):
    translator = Translator(ProviderChain("translate", [FakeTranslateProvider()]))
    run_turn(make_settings(LANG_STRATEGY="translate-pivot"), TurnRequest(text="pluie ?", lang="fr"), translator)
    assert FakeAgent.instances[0].asked == "<fr->en> pluie ?"
    assert "'en'" in FakeAgent.instances[0].kwargs["system_prompt"]


def test_translate_pivot_output_is_translated_back(make_settings, routed):
    translator = Translator(ProviderChain("translate", [FakeTranslateProvider()]))
    result = run_turn(make_settings(LANG_STRATEGY="translate-pivot"), TurnRequest(text="pluie ?", lang="fr"), translator)
    assert result.pivoted and result.payload.short_answer == "<en->fr> Sunny."


def test_llm_native_strategy_never_calls_translation(settings, routed):
    class Boom:
        enabled = True

        def translate(self, *a):
            raise AssertionError("translation must not run in llm-native mode")

    run_turn(settings, TurnRequest(text="pluie ?", lang="fr"), Boom())


def test_compare_data_from_the_tool_is_handed_to_the_router(settings, routed, monkeypatch):
    def fake_build_tools(client, lat, lon, local_time, collector):
        FakeAgent.collector = collector
        collector.compare = {"locations": [{"location": "Paris", "now": {"humidity": 50}}]}
        return []

    monkeypatch.setattr(runner, "build_tools", fake_build_tools)
    run_turn(settings, TurnRequest(text="compare"))
    assert '"humidity": 50' in routed["tool_data"]
