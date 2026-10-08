"""Conversation-history and tool-result handling.

The client owns the chat. The server only ever accepts plain text turns (never tool
or reasoning blocks) and returns text-only display messages, so provider-specific
message shapes can never leak across turns.
"""

from __future__ import annotations

from typing import Any

from ..textutil import strip_think

MAX_TURN_CHARS = 1000
MAX_DISPLAY_MESSAGES = 40


def _turn_text(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    content = item.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and isinstance(b.get("text"), str)]
        return " ".join(p.strip() for p in parts if p.strip()).strip()
    text = item.get("text")
    return text.strip() if isinstance(text, str) else ""


def clean_history(raw: Any) -> list[dict]:
    """Client history -> alternating text-only user/assistant turns that start with
    'user' and end with 'assistant', ready to precede a new user message."""
    if not isinstance(raw, list):
        return []
    turns: list[dict] = []
    for item in raw:
        if not isinstance(item, dict) or item.get("role") not in ("user", "assistant"):
            continue
        text = _turn_text(item)[:MAX_TURN_CHARS]
        if not text:
            continue
        if turns and turns[-1]["role"] == item["role"]:
            turns[-1] = {"role": item["role"], "content": [{"text": text}]}  # keep the latest of a repeat
        else:
            turns.append({"role": item["role"], "content": [{"text": text}]})
    while turns and turns[0]["role"] != "user":
        turns.pop(0)
    while turns and turns[-1]["role"] != "assistant":
        turns.pop()
    return turns


def llm_history(turns: list[dict], max_messages: int) -> list[dict]:
    """Last `max_messages` turns for the model, still starting on a user turn."""
    if max_messages <= 0:
        return []
    window = turns[-max_messages:]
    while window and window[0]["role"] != "user":
        window = window[1:]
    return window


def display_messages(turns: list[dict], user_text: str, answer: str) -> list[dict]:
    kept = turns[-(MAX_DISPLAY_MESSAGES - 2):]
    return kept + [
        {"role": "user", "content": [{"text": user_text}]},
        {"role": "assistant", "content": [{"text": answer}]},
    ]


def extract_text(message: Any) -> str:
    """Concatenated text blocks of a Converse-format assistant message, <think> removed."""
    if not isinstance(message, dict):
        return ""
    parts = [
        b["text"] for b in message.get("content", [])
        if isinstance(b, dict) and isinstance(b.get("text"), str)
    ]
    return strip_think(" ".join(p.strip() for p in parts if p.strip()))


def tools_used(messages: list[dict]) -> list[str]:
    names: list[str] = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        for block in message.get("content", []):
            tool_use = block.get("toolUse") if isinstance(block, dict) else None
            if tool_use and tool_use.get("name"):
                names.append(tool_use["name"])
    return names
