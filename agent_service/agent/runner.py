"""One conversational turn: analyst agent (tools) -> router (UI payload)."""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache

from strands import Agent
from strands.types.exceptions import ContextWindowOverflowException, MaxTokensReachedException

from .. import llm
from ..config import Settings
from ..errors import ServiceError
from ..i18n import t
from ..providers.translate import Translator
from . import messages as msg
from . import router
from .model import get_model
from .prompts import analyst_prompt
from .tools import ToolDataCollector, WeatherClient, build_tools

logger = logging.getLogger(__name__)


@dataclass
class TurnRequest:
    text: str
    lang: str = "en"
    history: list = field(default_factory=list)          # cleaned text-only turns (messages.clean_history)
    context_location: str | None = None
    user_lat: float | None = None
    user_lon: float | None = None
    local_time: str | None = None


@dataclass
class TurnResult:
    payload: router.UiPayload
    weather_data: dict
    forecast_data: dict
    tools_used: list
    router_fallback: bool
    pivoted: bool


@lru_cache(maxsize=4)
def weather_client(api_key: str, ttl: int) -> WeatherClient:
    """Process-wide client so the TTL cache survives across requests."""
    return WeatherClient(api_key, ttl)


def _translate_payload(payload: router.UiPayload, translator: Translator, lang: str) -> None:
    payload.short_answer = translator.translate(payload.short_answer, "en", lang)
    data = payload.comparison_data
    if data:
        data.winner_reasoning = translator.translate(data.winner_reasoning, "en", lang)
        for loc in data.locations:
            loc.condition = translator.translate(loc.condition, "en", lang)
            loc.score_reasoning = translator.translate(loc.score_reasoning, "en", lang)


def run_turn(settings: Settings, req: TurnRequest, translator: Translator | None = None) -> TurnResult:
    settings.require("OWM_API_KEY", "LLM_MODEL_ID")

    question, agent_lang, pivoted = req.text, req.lang, False
    if settings.lang_strategy == "translate-pivot" and translator is not None and translator.enabled and req.lang != "en":
        try:
            question, agent_lang, pivoted = translator.translate(req.text, req.lang, "en"), "en", True
        except Exception as exc:  # noqa: BLE001 - degrade to llm-native for this turn
            logger.warning("pivot translation failed (%s); answering natively", type(exc).__name__)

    client = weather_client(settings.owm_api_key, settings.weather_cache_ttl)
    collector = ToolDataCollector()
    agent = Agent(
        model=get_model(settings),
        tools=build_tools(client, req.user_lat, req.user_lon, req.local_time, collector),
        system_prompt=analyst_prompt(lang=agent_lang, local_time=req.local_time, user_lat=req.user_lat,
                                     user_lon=req.user_lon, context_location=req.context_location),
        messages=copy.deepcopy(msg.llm_history(req.history, settings.history_messages)),
        callback_handler=None,
    )
    try:
        last = agent(question).message
    except MaxTokensReachedException:
        last = agent.messages[-1] if agent.messages else None
    except ContextWindowOverflowException as exc:
        raise ServiceError(400, "context_too_long", "The conversation is too long. Please clear the chat and retry.") from exc
    except Exception as exc:  # noqa: BLE001
        if llm.is_rate_limit(exc):
            raise ServiceError(429, "rate_limited", t("rate_limited", req.lang)) from exc
        logger.exception("agent run failed")
        raise ServiceError(502, "agent_failed", t("agent_unavailable", req.lang)) from exc

    analyst_text = msg.extract_text(last)
    if analyst_text:
        payload, fallback = router.route(settings, user_text=question, analyst_text=analyst_text, lang=agent_lang,
                                        tool_data=json.dumps(collector.compare, ensure_ascii=False) if collector.compare else "")
        if pivoted:
            try:
                _translate_payload(payload, translator, req.lang)
            except Exception as exc:  # noqa: BLE001
                logger.warning("translating the answer back failed (%s); returning English", type(exc).__name__)
    else:
        payload, fallback = router.UiPayload(ui_mode="chat", short_answer=t("no_answer", req.lang)), True

    weather, forecast = collector.weather, collector.forecast
    if payload.ui_mode == "comparison":
        weather, forecast = {}, {}  # the comparison view replaces the dashboard; avoid showing only the last city
    return TurnResult(payload, weather, forecast, msg.tools_used(agent.messages), fallback, pivoted)
