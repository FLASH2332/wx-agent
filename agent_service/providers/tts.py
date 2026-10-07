"""Text-to-speech providers.

Chain default: polly -> browser. `browser` returns no audio: the frontend speaks the text
with the Web Speech API (free, runs on the user's device, covers languages Polly lacks).

Cost decisions: standard Polly engine by default, text capped at TTS_MAX_CHARS, results
cached on local disk by hash so repeated phrases never hit Polly twice.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from ..config import Settings
from ..errors import ProviderUnavailable
from ..textutil import base_lang, truncate_at_sentence
from .base import ProviderChain

logger = logging.getLogger(__name__)

# (voice id, Polly LanguageCode or None). Tamil has no Polly voice: it falls through to the
# browser provider instead of being read by a Hindi voice (the old behaviour).
STANDARD_VOICES = {
    "en": ("Joanna", None), "hi": ("Aditi", "hi-IN"), "fr": ("Celine", "fr-FR"),
    "de": ("Marlene", "de-DE"), "es": ("Conchita", "es-ES"),
}
NEURAL_VOICES = {  # verify availability per region before enabling POLLY_ENGINE=neural
    "en": ("Joanna", None), "hi": ("Kajal", "hi-IN"), "fr": ("Lea", "fr-FR"),
    "de": ("Vicki", "de-DE"), "es": ("Lucia", "es-ES"),
}


@dataclass
class TtsResult:
    mode: str                      # "polly" | "browser"
    text: str
    lang: str
    audio_b64: str = ""
    mime: str = ""
    voice: str = ""
    cached: bool = False


class PollyTts:
    name = "polly"

    def __init__(self, settings: Settings, *, client=None):
        self._s = settings
        self._client = client

    def synthesize(self, text: str, lang: str) -> TtsResult:
        voices = NEURAL_VOICES if self._s.polly_engine == "neural" else STANDARD_VOICES
        code = base_lang(lang)
        if code not in voices:
            raise ProviderUnavailable(f"no Polly voice for language '{code}'")
        voice, language_code = voices[code]
        text = truncate_at_sentence(text, self._s.tts_max_chars)

        cache_file = self._cache_path(self._s.polly_engine, voice, text)
        if cache_file and cache_file.exists():
            return TtsResult("polly", text, code, base64.b64encode(cache_file.read_bytes()).decode(),
                             "audio/mpeg", voice, cached=True)

        if self._client is None:
            import boto3

            self._client = boto3.client("polly", region_name=self._s.aws_region)
        kwargs = {"Text": text, "OutputFormat": "mp3", "VoiceId": voice, "Engine": self._s.polly_engine}
        if language_code:
            kwargs["LanguageCode"] = language_code
        audio = self._client.synthesize_speech(**kwargs)["AudioStream"].read()
        if cache_file:
            try:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_bytes(audio)
            except OSError:
                logger.debug("tts cache write failed", exc_info=True)
        return TtsResult("polly", text, code, base64.b64encode(audio).decode(), "audio/mpeg", voice)

    def _cache_path(self, engine: str, voice: str, text: str) -> Path | None:
        if not self._s.tts_cache_dir:
            return None
        digest = hashlib.sha256(f"{engine}|{voice}|{text}".encode()).hexdigest()
        return Path(self._s.tts_cache_dir) / f"{digest}.mp3"


class BrowserTts:
    name = "browser"

    def __init__(self, settings: Settings):
        self._s = settings

    def synthesize(self, text: str, lang: str) -> TtsResult:
        return TtsResult("browser", truncate_at_sentence(text, self._s.tts_max_chars), base_lang(lang))


def build_tts_providers(settings: Settings) -> list:
    factories = {"polly": PollyTts, "browser": BrowserTts}
    return [factories[name](settings) for name in settings.tts_providers]


def synthesize(chain: ProviderChain, text: str, lang: str) -> TtsResult:
    result, _ = chain.run(lambda p: p.synthesize(text, lang))
    return result
