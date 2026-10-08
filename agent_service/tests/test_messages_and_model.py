from strands.models.litellm import LiteLLMModel

from agent_service.agent import messages as msg
from agent_service.agent.model import get_model
from agent_service.textutil import base_lang, strip_think, truncate_at_sentence


def turn(role, text):
    return {"role": role, "content": [{"text": text}]}


# ---------------------------------------------------------------- history
def test_clean_history_keeps_only_text_and_alternation():
    raw = [
        turn("assistant", "stray leading assistant"),
        turn("user", "weather in Paris?"),
        {"role": "assistant", "content": [{"toolUse": {"name": "x"}}, {"text": "Sunny."}]},
        {"role": "system", "content": [{"text": "ignored"}]},
        "garbage",
        turn("user", "and tomorrow?"),  # trailing user (failed turn) must be dropped
    ]
    assert msg.clean_history(raw) == [turn("user", "weather in Paris?"), turn("assistant", "Sunny.")]


def test_clean_history_accepts_string_content_and_caps_length():
    out = msg.clean_history([{"role": "user", "content": "hi"}, {"role": "assistant", "content": "x" * 5000}])
    assert out[0]["content"][0]["text"] == "hi"
    assert len(out[1]["content"][0]["text"]) == msg.MAX_TURN_CHARS


def test_clean_history_rejects_non_list():
    assert msg.clean_history(None) == []
    assert msg.clean_history({"a": 1}) == []


def test_llm_history_window_starts_on_user_turn():
    turns = [turn("user", "1"), turn("assistant", "2"), turn("user", "3"), turn("assistant", "4")]
    assert [t["content"][0]["text"] for t in msg.llm_history(turns, 3)] == ["3", "4"]
    assert msg.llm_history(turns, 0) == []
    assert len(msg.llm_history(turns, 6)) == 4


def test_display_messages_appends_user_and_short_answer():
    out = msg.display_messages([turn("user", "a"), turn("assistant", "b")], "q", "short")
    assert out[-2:] == [turn("user", "q"), turn("assistant", "short")]


# ---------------------------------------------------------------- text + tool usage
def test_extract_text_strips_think_blocks():
    message = {"role": "assistant", "content": [{"text": "<think>hmm</think>Sunny today."}, {"toolUse": {}}]}
    assert msg.extract_text(message) == "Sunny today."
    assert msg.extract_text(None) == ""


def test_tools_used_lists_tool_names_in_order():
    messages = [{"role": "assistant", "content": [{"toolUse": {"name": "get_forecast"}}, {"toolUse": {"name": "get_alerts"}}]}]
    assert msg.tools_used(messages) == ["get_forecast", "get_alerts"]


# ---------------------------------------------------------------- model wiring
REASONING = {"reasoningContent": {"reasoningText": {"text": "thinking...", "signature": "sig"}}}
CONVERSATION = [
    turn("user", "hi"),
    {"role": "assistant", "content": [REASONING, {"toolUse": {"toolUseId": "1", "name": "get_forecast", "input": {}}}]},
    {"role": "user", "content": [{"toolResult": {"toolUseId": "1", "status": "success", "content": [{"json": {"a": 1}}]}}]},
    {"role": "assistant", "content": [REASONING, {"text": "Final"}]},
    turn("user", "and tomorrow?"),
]


def test_stock_model_never_sends_reasoning_blocks():
    """Guards the assumption that made the old _ModelProxy unnecessary (strands 1.56)."""
    request = LiteLLMModel(model_id="groq/x").format_request(CONVERSATION, None, "sys")
    sent = str(request["messages"])
    assert "thinking" not in sent and "reasoning" not in sent
    assert "tool_calls" in sent  # tool loop structure is preserved


def test_get_model_is_provider_agnostic_and_cached(make_settings):
    settings = make_settings(LLM_MODEL_ID="openai/qwen2.5", LLM_BASE_URL="http://localhost:11434/v1", LLM_API_KEY="ollama")
    model = get_model(settings)
    assert model is get_model(settings)
    config = model.get_config()
    assert config["model_id"] == "openai/qwen2.5"
    assert config["params"]["max_tokens"] == settings.llm_max_tokens == 800
    assert config["params"]["reasoning_effort"] == "low"  # reasoning models otherwise burn the token budget
    assert model.client_args == {"api_key": "ollama", "api_base": "http://localhost:11434/v1"}


# ---------------------------------------------------------------- text utils
def test_strip_think_variants():
    assert strip_think("<think>a</think>hello") == "hello"
    assert strip_think("hello<think>unfinished") == "hello"
    assert strip_think("reasoning</think>answer") == "answer"
    assert strip_think(None) == ""


def test_base_lang_normalises_codes_and_names():
    assert base_lang("hi-IN") == "hi"
    assert base_lang("Tamil") == "ta"
    assert base_lang("english") == "en"
    assert base_lang("???") == "en"
    assert base_lang(None) == "en"


def test_truncate_at_sentence():
    assert truncate_at_sentence("One. Two. Three.", 12) == "One. Two."
    assert truncate_at_sentence("short", 50) == "short"
    assert truncate_at_sentence("word " * 30, 20).endswith("…")
