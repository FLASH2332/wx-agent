"""Transport-agnostic service API: every function takes a parsed body dict and returns
(http_status, response_dict). Adapters (Lambda handler, Starlette app, CLI) only
translate their own request/response format to and from this.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import re
import socket
import time
import uuid
from datetime import datetime
from typing import Callable

from .agent import messages as msg
from .agent.runner import TurnRequest, run_turn, weather_client
from .config import Settings, get_settings
from .diagnostics import run_aws_probes
from .errors import (AllProvidersFailed, ConfigError, LocationNotFoundError, ServiceError, UpstreamError)
from .i18n import t
from .providers import Providers, get_providers
from .providers.tts import synthesize
from .textutil import base_lang

logger = logging.getLogger("agent_service")

_LOCATION_RE = re.compile(r"^[\w\s,.'()\-/]{1,100}$", re.UNICODE)


# ---------------------------------------------------------------- helpers
def _lang(body: dict) -> str:
    raw = body.get("lang")
    return base_lang(raw) if isinstance(raw, str) and raw.strip() else "en"


def _clean_location(value, field: str = "contextLocation", required: bool = False) -> str | None:
    if value is None or value == "":
        if required:
            raise ServiceError(400, "missing_location", "Missing location")
        return None
    if not isinstance(value, str) or not _LOCATION_RE.match(value.strip()):
        if required:
            raise ServiceError(400, "invalid_location", f"Invalid {field}")
        return None  # optional context that fails validation is ignored, not trusted
    return value.strip()


def _clean_time(value) -> str | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value


def _clean_coord(value, limit: float) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if -limit <= number <= limit else None


def _require_dict(body) -> dict:
    if not isinstance(body, dict):
        raise ServiceError(400, "invalid_json", "Request body must be a JSON object")
    return body


def _respond(route: str, fn: Callable[[], tuple[int, dict]], settings: Settings, lang: str = "en") -> tuple[int, dict]:
    request_id = uuid.uuid4().hex[:12]
    started = time.perf_counter()
    extra: dict = {}
    try:
        status, body = fn()
        extra = body.pop("_log", {})
    except ServiceError as exc:
        status, body = exc.status, {"error": exc.message, "code": exc.code}
    except ConfigError as exc:
        status, body = 500, {"error": str(exc), "code": "config"}
    except LocationNotFoundError:
        status, body = 404, {"error": t("location_not_found", lang), "code": "location_not_found"}
    except AllProvidersFailed as exc:
        status = 502
        body = {"error": f"All {exc.kind} providers failed", "code": "providers_failed",
                "providers": [{"provider": n, "error": e} for n, e in exc.errors]}
    except UpstreamError as exc:
        status, body = 502, {"error": str(exc), "code": "upstream"}
    except Exception as exc:  # noqa: BLE001 - never leak internals
        logger.exception("unhandled error in %s", route)
        status, body = 500, {"error": "Internal error", "code": "internal"}
        if settings.debug_errors:
            body["detail"] = f"{type(exc).__name__}: {exc}"
    body["request_id"] = request_id
    logger.info(json.dumps({"request_id": request_id, "route": route, "status": status, "lang": lang,
                            "ms": int((time.perf_counter() - started) * 1000), **extra}))
    return status, body


# ---------------------------------------------------------------- routes
def handle_query(body, settings: Settings | None = None, *, turn=run_turn,
                 providers: Providers | None = None) -> tuple[int, dict]:
    settings = settings or get_settings()
    lang = _lang(body) if isinstance(body, dict) else "en"

    def work():
        data = _require_dict(body)
        text = data.get("text")
        text = text.strip() if isinstance(text, str) else ""
        if not text:
            raise ServiceError(400, "missing_text", "Missing 'text' in request")
        if len(text) > settings.max_text_chars:
            raise ServiceError(400, "text_too_long", f"Message is too long (max {settings.max_text_chars} characters)")

        history = msg.clean_history(data.get("messages"))
        request = TurnRequest(
            text=text, lang=lang, history=history,
            context_location=_clean_location(data.get("contextLocation")),
            user_lat=_clean_coord(data.get("userLat"), 90), user_lon=_clean_coord(data.get("userLon"), 180),
            local_time=_clean_time(data.get("localTime")),
        )
        translator = (providers or get_providers(settings)).translate
        result = turn(settings, request, translator)
        payload = result.payload
        return 200, {
            "response_text": payload.short_answer,
            "ui_mode": payload.ui_mode,
            "comparison_data": payload.comparison_data.model_dump() if payload.comparison_data else None,
            "weather_data": result.weather_data,
            "forecast_data": result.forecast_data,
            "lang": lang,
            "messages": msg.display_messages(history, text, payload.short_answer),
            "meta": {"tools": result.tools_used, "router_fallback": result.router_fallback,
                     "lang_strategy": "translate-pivot" if result.pivoted else "llm-native"},
            "_log": {"tools": result.tools_used, "router_fallback": result.router_fallback,
                     "history_turns": len(history)},
        }

    return _respond("/query", work, settings, lang)


def handle_transcribe(body, settings: Settings | None = None, *, providers: Providers | None = None) -> tuple[int, dict]:
    settings = settings or get_settings()
    providers = providers or get_providers(settings)

    def work():
        data = _require_dict(body)
        audio_b64 = data.get("audio_b64")
        if not isinstance(audio_b64, str) or not audio_b64:
            raise ServiceError(400, "missing_audio", "Missing audio_b64")
        try:
            audio = base64.b64decode(audio_b64, validate=True)
        except (binascii.Error, ValueError):
            raise ServiceError(400, "invalid_audio", "audio_b64 is not valid base64") from None
        if not audio:
            raise ServiceError(400, "missing_audio", "Empty audio")
        if len(audio) > settings.stt_max_audio_bytes:
            raise ServiceError(413, "audio_too_large", f"Audio too large (max {settings.stt_max_audio_bytes} bytes)")
        mime = data.get("mime") if isinstance(data.get("mime"), str) else "audio/webm"
        result, provider = providers.stt.run(lambda p: p.transcribe(audio, mime))
        if not result.text:
            raise ServiceError(422, "no_speech", "No speech detected. Please try again.")
        return 200, {"text": result.text, "language": result.language, "provider": provider,
                     "_log": {"stt_provider": provider, "audio_bytes": len(audio)}}

    return _respond("/transcribe", work, settings)


def handle_sync(body, settings: Settings | None = None) -> tuple[int, dict]:
    settings = settings or get_settings()
    lang = _lang(body) if isinstance(body, dict) else "en"

    def work():
        data = _require_dict(body)
        location = _clean_location(data.get("location"), "location", required=True)
        settings.require("OWM_API_KEY")
        client = weather_client(settings.owm_api_key, settings.weather_cache_ttl)
        return 200, {"weather_data": client.current(location, "metric", lang),
                     "forecast_data": client.forecast(location, 5, "metric", lang)}

    return _respond("/sync", work, settings, lang)


def handle_tts(body, settings: Settings | None = None, *, providers: Providers | None = None) -> tuple[int, dict]:
    settings = settings or get_settings()
    providers = providers or get_providers(settings)
    lang = _lang(body) if isinstance(body, dict) else "en"

    def work():
        data = _require_dict(body)
        text = data.get("text")
        text = text.strip() if isinstance(text, str) else ""
        if not text:
            raise ServiceError(400, "missing_text", "Missing 'text' in request")
        if len(text) > 1000:
            raise ServiceError(400, "text_too_long", "Text is too long for speech (max 1000 characters)")
        if not providers.tts.names:
            return 200, {"mode": "none", "_log": {"tts_provider": "none"}}
        result = synthesize(providers.tts, text, lang)
        body_out = {"mode": result.mode, "text": result.text, "lang": result.lang,
                    "_log": {"tts_provider": result.mode, "cached": result.cached}}
        if result.mode == "polly":
            body_out.update(audio_b64=result.audio_b64, mime=result.mime, voice=result.voice)
        return 200, body_out

    return _respond("/tts", work, settings, lang)


def handle_health(settings: Settings | None = None, *, providers: Providers | None = None) -> tuple[int, dict]:
    settings = settings or get_settings()
    providers = providers or get_providers(settings)
    return 200, {
        "status": "ok",
        # Container hostname is unique per ECS task: lets scripts/load_test.py prove the ALB spreads requests.
        "instance": socket.gethostname(),
        "llm_model": settings.llm_model_id or None,
        "llm_configured": bool(settings.llm_model_id and (settings.llm_api_key or settings.llm_base_url)),
        "owm_configured": bool(settings.owm_api_key),
        "lang_strategy": settings.lang_strategy,
        "stt": providers.stt.names,
        "translate": providers.translate.chain.names,
        "tts": providers.tts.names,
        "aws_region": settings.aws_region,
        "stt_s3_bucket_set": bool(settings.stt_s3_bucket),
    }


def handle_diag(settings: Settings | None = None, *, probe=run_aws_probes) -> tuple[int, dict]:
    """Which AWS services can this process's role call? Off unless DIAG_ENABLED=true."""
    settings = settings or get_settings()
    if not settings.diagnostics_enabled:
        return 404, {"error": "Not found", "code": "not_found"}
    return 200, probe(settings)
