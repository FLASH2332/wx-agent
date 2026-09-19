"""Offline tests for agent wiring (no Bedrock calls)."""

import agent


def test_all_four_tools_registered():
    names = {t.__name__ for t in agent.TOOLS}
    assert names == {
        "get_current_weather",
        "get_forecast",
        "get_alerts",
        "activity_advisor",
    }


def test_extract_text_joins_text_blocks():
    message = {
        "role": "assistant",
        "content": [{"text": "It is 29 degrees"}, {"text": "and sunny."}],
    }
    assert agent._extract_text(message) == "It is 29 degrees and sunny."


def test_extract_text_ignores_non_text_blocks():
    message = {
        "role": "assistant",
        "content": [
            {"toolUse": {"name": "get_current_weather"}},
            {"text": "Sunny in Delhi."},
        ],
    }
    assert agent._extract_text(message) == "Sunny in Delhi."


def test_extract_text_empty_message():
    assert agent._extract_text(None) == ""
    assert agent._extract_text({"role": "assistant", "content": []}) == ""
