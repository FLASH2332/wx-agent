"""Provider registry: STT / translate / TTS chains built once per Settings object."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ..config import Settings
from .base import ProviderChain
from .stt import build_stt_providers
from .translate import Translator, build_translate_providers
from .tts import build_tts_providers


@dataclass
class Providers:
    stt: ProviderChain
    translate: Translator
    tts: ProviderChain


@lru_cache(maxsize=4)
def get_providers(settings: Settings) -> Providers:
    cooldown = settings.provider_cooldown_seconds
    return Providers(
        stt=ProviderChain("stt", build_stt_providers(settings), cooldown),
        translate=Translator(ProviderChain("translate", build_translate_providers(settings), cooldown)),
        tts=ProviderChain("tts", build_tts_providers(settings), cooldown),
    )
