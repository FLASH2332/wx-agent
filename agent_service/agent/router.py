"""UI routing step: one small, tool-less LLM call that returns validated JSON.

Parsing is deliberately defensive: balanced-brace extraction (not a greedy regex),
pydantic validation with an enum for ui_mode, and a fallback that reuses the
analyst's own text (already in the user's language) so a bad router response costs
nothing extra and never produces an English-only canned message.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .. import llm
from ..config import Settings
from ..textutil import strip_think, truncate_at_sentence
from .prompts import router_prompt

logger = logging.getLogger(__name__)

_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
MAX_ANALYST_CHARS = 3000
MAX_TOOL_DATA_CHARS = 2500
FALLBACK_ANSWER_CHARS = 300


class ComparisonLocation(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True, extra="ignore")
    name: str
    temp: str = ""
    condition: str = ""
    rain_chance: str = ""
    uv_index: str = ""
    wind: str = ""
    humidity: str = ""
    score: Optional[float] = None
    score_reasoning: str = ""

    @field_validator("temp", "condition", "rain_chance", "uv_index", "wind", "humidity", "score_reasoning", mode="before")
    @classmethod
    def _blank_if_null_like(cls, value):
        # Models write null/None as text; the card must not display that.
        if value is None or (isinstance(value, str) and value.strip().lower() in {"null", "none", "undefined"}):
            return ""
        return value

    @field_validator("score", mode="before")
    @classmethod
    def _score(cls, value):
        try:
            return max(0.0, min(10.0, float(value)))
        except (TypeError, ValueError):
            return None  # "n/a", null, or text: no score


class ComparisonData(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True, extra="ignore")
    winner: str = ""
    winner_reasoning: str = ""

    @field_validator("winner", "winner_reasoning", mode="before")
    @classmethod
    def _blank_if_null_like(cls, value):
        if value is None or (isinstance(value, str) and value.strip().lower() in {"null", "none", "undefined"}):
            return ""
        return value

    locations: list[ComparisonLocation] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unscored_means_no_scores(self):
        # Models fill 0 when asked for a score they have no basis for; an all-zero card is noise.
        if all(not loc.score for loc in self.locations):
            for loc in self.locations:
                loc.score = None
        return self


class UiPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    ui_mode: Literal["chat", "dashboard", "comparison"] = "dashboard"
    short_answer: str
    comparison_data: Optional[ComparisonData] = None

    @field_validator("short_answer")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("short_answer is empty")
        return value

    @model_validator(mode="after")
    def _consistent(self):
        # The frontend needs two locations for the comparison view; otherwise downgrade.
        if self.ui_mode == "comparison" and (self.comparison_data is None or len(self.comparison_data.locations) < 2):
            self.ui_mode = "dashboard"
        if self.ui_mode != "comparison":
            self.comparison_data = None
        return self


def extract_json_object(text: str) -> dict:
    """First balanced top-level JSON object in `text` (handles fences, prose, nested braces)."""
    text = _FENCE.sub("", strip_think(text).strip()).strip()
    start = text.find("{")
    while start != -1:
        depth, in_string, escape = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            elif ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[start:i + 1])
                    except ValueError:
                        break
                    if isinstance(parsed, dict):
                        return parsed
                    break
        start = text.find("{", start + 1)
    raise ValueError("no JSON object found")


def fallback_payload(analyst_text: str) -> UiPayload:
    return UiPayload(ui_mode="dashboard", short_answer=truncate_at_sentence(analyst_text, FALLBACK_ANSWER_CHARS))


def route(settings: Settings, *, user_text: str, analyst_text: str, lang: str, tool_data: str = "") -> tuple[UiPayload, bool]:
    """Returns (payload, used_fallback)."""
    user = f"User query: {user_text}\n\nAnalyst answer:\n{analyst_text[:MAX_ANALYST_CHARS]}"
    if tool_data:
        user += f"\n\nTool data (exact numbers for the comparison stats):\n{tool_data[:MAX_TOOL_DATA_CHARS]}"
    system = router_prompt(lang)
    router_model = settings.router_model_id or None  # a separate model has its own rate-limit bucket
    raw = None
    try:
        try:
            raw = llm.complete(settings, system, user, max_tokens=settings.router_max_tokens,
                               json_mode=settings.router_json_mode, model_id=router_model)
        except Exception as exc:  # noqa: BLE001
            if llm.is_rate_limit(exc) or not settings.router_json_mode:
                raise
            logger.info("router json_mode rejected (%s); retrying without it", type(exc).__name__)
            raw = llm.complete(settings, system, user, max_tokens=settings.router_max_tokens, json_mode=False,
                               model_id=router_model)
        return UiPayload.model_validate(extract_json_object(raw)), False
    except (ValueError, ValidationError) as exc:
        logger.warning("router output rejected: %s", type(exc).__name__)
    except Exception as exc:  # noqa: BLE001 - router failure must not fail the turn
        logger.warning("router call failed: %s", type(exc).__name__)
    return fallback_payload(analyst_text), True
