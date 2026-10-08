"""Text translation providers (only used when LANG_STRATEGY=translate-pivot).

Default strategy is `llm-native` (the agent answers in the user's language directly),
which spends no translation calls at all - that is the cost-saving default.
"""

from __future__ import annotations

from .. import llm
from ..config import Settings
from ..errors import ProviderUnavailable
from ..textutil import base_lang
from .base import ProviderChain

_AWS_MAX_BYTES = 9000  # TranslateText limit is 10,000 bytes


class AwsTranslate:
    name = "aws-translate"

    def __init__(self, settings: Settings, *, client=None):
        self._s = settings
        self._client = client

    def translate(self, text: str, source: str, target: str) -> str:
        if len(text.encode("utf-8")) > _AWS_MAX_BYTES:
            raise ProviderUnavailable("text exceeds the TranslateText size limit")
        if self._client is None:
            import boto3

            self._client = boto3.client("translate", region_name=self._s.aws_region)
        try:
            response = self._client.translate_text(
                Text=text, SourceLanguageCode=source or "auto", TargetLanguageCode=target)
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if code in {"UnsupportedLanguagePairException", "InvalidRequestException"}:
                raise ProviderUnavailable(code) from None
            raise
        return response["TranslatedText"]


class LlmTranslate:
    name = "llm"

    def __init__(self, settings: Settings):
        self._s = settings

    def translate(self, text: str, source: str, target: str) -> str:
        system = (f"Translate the user's text into the language with ISO-639-1 code '{target}'. "
                  "Output only the translation, nothing else. Keep numbers, units and place names.")
        out = llm.complete(self._s, system, text, max_tokens=max(64, len(text) * 3))
        if not out:
            raise RuntimeError("empty translation")
        return out


class Translator:
    def __init__(self, chain: ProviderChain):
        self.chain = chain

    @property
    def enabled(self) -> bool:
        return bool(self.chain.names)

    def translate(self, text: str, source: str | None, target: str) -> str:
        source_code, target_code = base_lang(source, "auto") if source else "auto", base_lang(target)
        if not text or not text.strip() or source_code == target_code:
            return text
        result, _ = self.chain.run(lambda p: p.translate(text, source_code, target_code))
        return result


def build_translate_providers(settings: Settings) -> list:
    factories = {"aws-translate": AwsTranslate, "llm": LlmTranslate}
    return [factories[name](settings) for name in settings.translate_providers]
