"""Small pure text helpers."""

from __future__ import annotations

import re

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)

_LANG_NAMES = {
    "english": "en", "hindi": "hi", "french": "fr", "german": "de", "spanish": "es",
    "tamil": "ta", "telugu": "te", "kannada": "kn", "malayalam": "ml", "marathi": "mr",
    "bengali": "bn", "gujarati": "gu", "punjabi": "pa", "urdu": "ur", "italian": "it",
    "portuguese": "pt", "dutch": "nl", "russian": "ru", "japanese": "ja", "korean": "ko",
    "chinese": "zh", "arabic": "ar", "turkish": "tr",
}
_CODE = re.compile(r"^[a-z]{2,3}([-_][a-z0-9]{2,8})?$")


def strip_think(text) -> str:
    """Remove reasoning-model <think> blocks (closed, unclosed, or close-only)."""
    if not isinstance(text, str):
        return ""
    text = _THINK_BLOCK.sub("", text)
    if "<think>" in text:
        text = text[: text.find("<think>")]
    if "</think>" in text:
        text = text.split("</think>")[-1]
    return text.strip()


def base_lang(code, default: str = "en") -> str:
    """'hi-IN' -> 'hi'; full names ('Hindi') -> 'hi'; anything unrecognised -> default."""
    if not isinstance(code, str):
        return default
    value = code.strip().lower()
    if value in _LANG_NAMES:
        return _LANG_NAMES[value]
    if _CODE.match(value):
        return re.split(r"[-_]", value)[0]
    return default


def truncate_at_sentence(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    best = max(cut.rfind(ch) for ch in ".!?।。")
    if best >= limit * 0.5:
        return cut[: best + 1].strip()
    space = cut.rfind(" ")
    return (cut[:space] if space > 0 else cut).strip() + "…"
