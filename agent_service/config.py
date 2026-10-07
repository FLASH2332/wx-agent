"""Environment-driven settings, read lazily (never at import time).

Every knob that affects cost has a conservative default; see docs/04-phase0-local.md.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping

from .errors import ConfigError

STT_PROVIDERS = {"aws-transcribe", "openai"}
TRANSLATE_PROVIDERS = {"aws-translate", "llm"}
TTS_PROVIDERS = {"polly", "browser"}
LANG_STRATEGIES = {"llm-native", "translate-pivot"}

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
OPENAI_BASE_URL = "https://api.openai.com/v1"


AWS_SECRET_ENV_KEYS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")


def load_dotenv_file() -> None:
    """Load the nearest .env into os.environ (does not override real env vars).

    AWS credentials have exactly one source: AWS CLI profiles (scripts/set_lab_credentials.py), selected with
    AWS_PROFILE. .env may contain the profile NAME but never AWS secrets: those lines are ignored with a warning,
    because keys in .env would silently shadow the chosen profile (and there is only room for one account there)."""
    try:
        from dotenv import dotenv_values, find_dotenv, load_dotenv
    except ImportError:
        return
    log = logging.getLogger(__name__)
    path = find_dotenv(usecwd=True)
    values = dotenv_values(path) if path else {}
    if path:
        # Real environment variables win over .env (so containers/CI can override it). On a dev machine that
        # silently hides edits to .env (e.g. a system-wide AWS_REGION), so say so, by name only.
        shadowed = sorted(k for k, v in values.items() if v and k in os.environ and os.environ[k] != v)
        if shadowed:
            log.warning("These variables are set in your shell/system environment and OVERRIDE the values in %s: %s",
                        path, ", ".join(shadowed))
    load_dotenv(path, override=False)
    # An empty `AWS_PROFILE=` (copied from a template) makes boto3 raise ProfileNotFound for every client.
    for name in [n for n, v in os.environ.items() if n.startswith("AWS_") and not v.strip()]:
        del os.environ[name]
    ignored = [k for k in AWS_SECRET_ENV_KEYS if values.get(k) and os.environ.get(k) == values[k]]
    for name in ignored:
        del os.environ[name]
    if ignored:
        log.warning("Ignored AWS credentials found in %s (%s). Use an AWS CLI profile instead: "
                    "python scripts/set_lab_credentials.py <profile>, then AWS_PROFILE=<profile>. Remove those lines.",
                    path, ", ".join(ignored))


def _text(env: Mapping[str, str], name: str, default: str = "") -> str:
    value = env.get(name)
    return default if value is None else value.strip()


def _int(env, name: str, default: int) -> int:
    raw = _text(env, name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def _bool(env, name: str, default: bool) -> bool:
    raw = _text(env, name).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _csv(env, name: str, default: str, allowed: set[str]) -> tuple[str, ...]:
    raw = env.get(name)
    raw = default if raw is None else raw
    items = tuple(p.strip().lower() for p in raw.split(",") if p.strip())
    unknown = [p for p in items if p not in allowed]
    if unknown:
        raise ConfigError(f"{name} has unknown provider(s) {unknown}; allowed: {sorted(allowed)}")
    return items


@dataclass(frozen=True)
class Settings:
    # --- LLM (any LiteLLM provider) ---
    llm_model_id: str
    llm_base_url: str
    llm_api_key: str
    llm_max_tokens: int
    router_max_tokens: int
    llm_num_retries: int
    llm_reasoning_effort: str
    router_model_id: str
    router_json_mode: bool
    # --- weather ---
    owm_api_key: str
    weather_cache_ttl: int
    # --- request limits ---
    history_messages: int
    max_text_chars: int
    # --- AWS ---
    aws_region: str
    # --- speech to text ---
    stt_providers: tuple[str, ...]
    stt_s3_bucket: str
    stt_language_options: tuple[str, ...]
    stt_aws_timeout: int
    stt_max_audio_bytes: int
    stt_api_base_url: str
    stt_api_key: str
    stt_model: str
    # --- translation ---
    lang_strategy: str
    translate_providers: tuple[str, ...]
    # --- text to speech ---
    tts_providers: tuple[str, ...]
    polly_engine: str
    tts_max_chars: int
    tts_cache_dir: str
    # --- resilience / server ---
    provider_cooldown_seconds: int
    cors_allow_origins: tuple[str, ...]
    debug_errors: bool
    diagnostics_enabled: bool

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env

        model_id = _text(env, "LLM_MODEL_ID")
        api_key = _text(env, "LLM_API_KEY")
        # Legacy compatibility: older .env files only had GROQ_* variables.
        if not model_id and _text(env, "GROQ_MODEL_ID"):
            legacy = _text(env, "GROQ_MODEL_ID")
            # Groq's own ids can contain a namespace ("openai/gpt-oss-120b"), so only add the provider prefix.
            model_id = legacy if legacy.startswith("groq/") else f"groq/{legacy}"
        if not api_key:
            api_key = _text(env, "GROQ_API_KEY")
        base_url = _text(env, "LLM_BASE_URL")

        is_groq = model_id.startswith("groq/")
        stt_base = _text(env, "STT_API_BASE_URL") or (
            GROQ_BASE_URL if is_groq and not base_url else (base_url or OPENAI_BASE_URL)
        )
        stt_model_default = "whisper-large-v3-turbo" if "groq.com" in stt_base else "whisper-1"

        strategy = _text(env, "LANG_STRATEGY", "llm-native").lower()
        if strategy not in LANG_STRATEGIES:
            raise ConfigError(f"LANG_STRATEGY must be one of {sorted(LANG_STRATEGIES)}, got {strategy!r}")
        effort = _text(env, "LLM_REASONING_EFFORT", "low").lower()
        if effort not in {"", "none", "low", "medium", "high"}:
            raise ConfigError(f"LLM_REASONING_EFFORT must be low/medium/high or empty, got {effort!r}")
        engine = _text(env, "POLLY_ENGINE", "standard").lower()
        if engine not in {"standard", "neural"}:
            raise ConfigError(f"POLLY_ENGINE must be 'standard' or 'neural', got {engine!r}")

        return cls(
            llm_model_id=model_id,
            llm_base_url=base_url,
            llm_api_key=api_key,
            llm_max_tokens=_int(env, "LLM_MAX_TOKENS", 800),
            router_max_tokens=_int(env, "ROUTER_MAX_TOKENS", 900),
            llm_num_retries=_int(env, "LLM_NUM_RETRIES", 1),
            llm_reasoning_effort="" if effort == "none" else effort,
            router_model_id=_text(env, "ROUTER_MODEL_ID"),
            router_json_mode=_bool(env, "ROUTER_JSON_MODE", True),
            owm_api_key=_text(env, "OWM_API_KEY"),
            weather_cache_ttl=_int(env, "WEATHER_CACHE_TTL_SECONDS", 600),
            history_messages=_int(env, "HISTORY_MESSAGES", 6),
            max_text_chars=_int(env, "MAX_TEXT_CHARS", 400),
            aws_region=_text(env, "AWS_REGION") or _text(env, "AWS_DEFAULT_REGION") or "us-east-1",
            stt_providers=_csv(env, "STT_PROVIDERS", "aws-transcribe,openai", STT_PROVIDERS),
            stt_s3_bucket=_text(env, "STT_S3_BUCKET"),
            stt_language_options=tuple(
                p.strip() for p in _text(env, "STT_LANGUAGE_OPTIONS", "en-US,hi-IN,fr-FR,de-DE,es-ES,ta-IN").split(",") if p.strip()
            ),
            stt_aws_timeout=_int(env, "STT_AWS_TIMEOUT_SECONDS", 25),
            stt_max_audio_bytes=_int(env, "STT_MAX_AUDIO_BYTES", 3_000_000),
            stt_api_base_url=stt_base.rstrip("/"),
            stt_api_key=_text(env, "STT_API_KEY") or api_key,
            stt_model=_text(env, "STT_MODEL") or stt_model_default,
            lang_strategy=strategy,
            translate_providers=_csv(env, "TRANSLATE_PROVIDERS", "aws-translate,llm", TRANSLATE_PROVIDERS),
            tts_providers=_csv(env, "TTS_PROVIDERS", "polly,browser", TTS_PROVIDERS),
            polly_engine=engine,
            tts_max_chars=_int(env, "TTS_MAX_CHARS", 400),
            tts_cache_dir=_text(env, "TTS_CACHE_DIR", ".cache/tts"),
            provider_cooldown_seconds=_int(env, "PROVIDER_COOLDOWN_SECONDS", 60),
            cors_allow_origins=tuple(
                o.strip() for o in _text(env, "CORS_ALLOW_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()
            ),
            debug_errors=_bool(env, "DEBUG_ERRORS", False),
            diagnostics_enabled=_bool(env, "DIAG_ENABLED", False),
        )

    def require(self, *names: str) -> None:
        """Raise ConfigError listing every missing setting (env var names)."""
        mapping = {
            "OWM_API_KEY": self.owm_api_key,
            "LLM_MODEL_ID": self.llm_model_id,
        }
        missing = [n for n in names if not mapping.get(n)]
        if missing:
            raise ConfigError(f"Missing required environment variable(s): {', '.join(missing)}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()

