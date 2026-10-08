import json

import pytest
from pydantic import ValidationError

from agent_service import llm
from agent_service.agent import router
from agent_service.agent.router import UiPayload, extract_json_object

LOC = {"name": "Paris", "temp": 21, "condition": "Sunny", "score": 9}


# ---------------------------------------------------------------- JSON extraction
def test_extract_plain_fenced_and_prose_wrapped():
    obj = {"ui_mode": "chat", "short_answer": "hi"}
    assert extract_json_object(json.dumps(obj)) == obj
    assert extract_json_object("```json\n" + json.dumps(obj) + "\n```") == obj
    assert extract_json_object("Sure! Here you go: " + json.dumps(obj) + " Hope that helps {not json}") == obj


def test_extract_handles_braces_inside_strings_and_nesting():
    obj = {"short_answer": "uses } and { chars", "comparison_data": {"locations": [{"name": "a"}]}}
    assert extract_json_object("prefix " + json.dumps(obj) + " suffix }") == obj


def test_extract_skips_invalid_candidate_and_finds_next():
    assert extract_json_object('{bad json} then {"short_answer": "ok"}') == {"short_answer": "ok"}


def test_extract_strips_think_and_raises_when_missing():
    assert extract_json_object('<think>{"x": 1}</think>{"short_answer": "ok"}') == {"short_answer": "ok"}
    with pytest.raises(ValueError):
        extract_json_object("no json at all")


# ---------------------------------------------------------------- validation
def test_unknown_ui_mode_is_rejected():
    with pytest.raises(ValidationError):
        UiPayload.model_validate({"ui_mode": "fullscreen", "short_answer": "x"})


def test_empty_short_answer_is_rejected():
    with pytest.raises(ValidationError):
        UiPayload.model_validate({"ui_mode": "chat", "short_answer": "   "})


def test_comparison_needs_two_locations_else_downgrades_to_dashboard():
    one = UiPayload.model_validate({"ui_mode": "comparison", "short_answer": "x",
                                    "comparison_data": {"winner": "Paris", "locations": [LOC]}})
    assert one.ui_mode == "dashboard" and one.comparison_data is None
    none = UiPayload.model_validate({"ui_mode": "comparison", "short_answer": "x"})
    assert none.ui_mode == "dashboard"


def test_comparison_coerces_numbers_to_strings_and_clamps_score():
    payload = UiPayload.model_validate({
        "ui_mode": "comparison", "short_answer": "x",
        "comparison_data": {"winner": "Paris", "locations": [{**LOC, "score": 14}, {**LOC, "name": "Rome", "score": "7"}]},
    })
    first, second = payload.comparison_data.locations
    assert first.temp == "21" and first.score == 10 and second.score == 7


def test_non_comparison_mode_drops_comparison_data():
    payload = UiPayload.model_validate({"ui_mode": "chat", "short_answer": "x",
                                        "comparison_data": {"winner": "A", "locations": [LOC, LOC]}})
    assert payload.comparison_data is None


# ---------------------------------------------------------------- route()
def _stub_llm(monkeypatch, outputs):
    calls = []

    def fake(settings, system, user, *, max_tokens, json_mode=False, model_id=None):
        calls.append({"system": system, "user": user, "json_mode": json_mode, "model_id": model_id, "max_tokens": max_tokens})
        out = outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return out

    monkeypatch.setattr(llm, "complete", fake)
    return calls


def test_route_success(monkeypatch, settings):
    calls = _stub_llm(monkeypatch, [json.dumps({"ui_mode": "dashboard", "short_answer": "Sunny."})])
    payload, fallback = router.route(settings, user_text="weather?", analyst_text="Long analysis", lang="fr")
    assert (payload.ui_mode, payload.short_answer, fallback) == ("dashboard", "Sunny.", False)
    assert "'fr'" in calls[0]["system"] and "Long analysis" in calls[0]["user"] and calls[0]["json_mode"] is True


def test_route_garbage_falls_back_to_analyst_text(monkeypatch, settings):
    _stub_llm(monkeypatch, ["I cannot do that"])
    payload, fallback = router.route(settings, user_text="q", analyst_text="Rain expected tomorrow. Bring an umbrella.", lang="en")
    assert fallback is True
    assert payload.ui_mode == "dashboard" and payload.short_answer.startswith("Rain expected")


def test_route_retries_without_json_mode_when_provider_rejects_it(monkeypatch, settings):
    calls = _stub_llm(monkeypatch, [RuntimeError("response_format unsupported"),
                                    json.dumps({"ui_mode": "chat", "short_answer": "ok"})])
    payload, fallback = router.route(settings, user_text="q", analyst_text="a", lang="en")
    assert fallback is False and payload.ui_mode == "chat"
    assert [c["json_mode"] for c in calls] == [True, False]


def test_route_rate_limit_does_not_retry_and_falls_back(monkeypatch, settings):
    class RateLimitError(Exception):
        pass

    calls = _stub_llm(monkeypatch, [RateLimitError("slow down")])
    payload, fallback = router.route(settings, user_text="q", analyst_text="Analyst says sunny.", lang="en")
    assert fallback is True and len(calls) == 1 and payload.short_answer == "Analyst says sunny."


def test_route_can_use_a_separate_router_model(monkeypatch, make_settings):
    calls = _stub_llm(monkeypatch, [json.dumps({"ui_mode": "chat", "short_answer": "ok"})])
    settings = make_settings(ROUTER_MODEL_ID="groq/llama-3.1-8b-instant")
    router.route(settings, user_text="q", analyst_text="a", lang="en")
    assert calls[0]["model_id"] == "groq/llama-3.1-8b-instant" and calls[0]["max_tokens"] == 900


def test_route_defaults_to_the_main_model(monkeypatch, settings):
    calls = _stub_llm(monkeypatch, [json.dumps({"ui_mode": "chat", "short_answer": "ok"})])
    router.route(settings, user_text="q", analyst_text="a", lang="en")
    assert calls[0]["model_id"] is None


def test_all_zero_scores_mean_unscored_and_become_none():
    payload = UiPayload.model_validate({"ui_mode": "comparison", "short_answer": "x", "comparison_data": {
        "winner": "", "locations": [{**LOC, "score": 0}, {**LOC, "name": "Rome", "score": 0}]}})
    assert [loc.score for loc in payload.comparison_data.locations] == [None, None]


def test_non_numeric_score_is_none_but_real_scores_are_kept():
    payload = UiPayload.model_validate({"ui_mode": "comparison", "short_answer": "x", "comparison_data": {
        "winner": "Paris", "locations": [{**LOC, "score": 8}, {**LOC, "name": "Rome", "score": "n/a"}]}})
    assert [loc.score for loc in payload.comparison_data.locations] == [8.0, None]


def test_route_passes_tool_data_to_the_router_prompt(monkeypatch, settings):
    calls = _stub_llm(monkeypatch, [json.dumps({"ui_mode": "chat", "short_answer": "ok"})])
    router.route(settings, user_text="q", analyst_text="a", lang="en", tool_data='{"locations": [{"wind_speed": 3.2}]}')
    assert "Tool data" in calls[0]["user"] and "3.2" in calls[0]["user"]
    calls2 = _stub_llm(monkeypatch, [json.dumps({"ui_mode": "chat", "short_answer": "ok"})])
    router.route(settings, user_text="q", analyst_text="a", lang="en")
    assert "Tool data" not in calls2[0]["user"]


def test_null_like_text_is_blanked_so_the_card_never_shows_the_word_null():
    payload = UiPayload.model_validate({"ui_mode": "comparison", "short_answer": "x", "comparison_data": {
        "winner": "null", "winner_reasoning": None,
        "locations": [{**LOC, "score": 8, "score_reasoning": "null", "uv_index": "None"}, {**LOC, "name": "Rome", "score": 6}]}})
    data = payload.comparison_data
    assert data.winner == "" and data.winner_reasoning == ""
    assert data.locations[0].score_reasoning == "" and data.locations[0].uv_index == ""
    assert data.locations[0].temp == "21"          # real values untouched
