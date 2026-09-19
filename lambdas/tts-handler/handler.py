"""tts-handler Lambda: synthesize speech with Amazon Polly.

Invoked directly by agent-handler via boto3 (AGENTS.md rule 8), never over HTTP,
so the event is a plain payload: {"text": "...", "lang": "en"}. Returns a plain
JSON dict {"audio_b64": "..."} (or {"error": "..."} on failure) — no API Gateway
envelope / CORS, since this Lambda is not exposed through API Gateway.
"""

import base64
import os

import boto3

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Voice map is fixed by AGENTS.md rule 23 — do not deviate.
VOICE_MAP = {
    "en": "Joanna",
    "hi": "Aditi",
    "fr": "Celine",
    "de": "Marlene",
    "es": "Conchita",
    "ta": "Aditi",
}
DEFAULT_VOICE = "Joanna"

# Non-English voices need an explicit Polly LanguageCode; English omits it
# (pitfall: Polly language code mismatch). Tamil has no Polly voice, so the
# rule-23 map routes it through the Hindi voice.
LANGUAGE_CODE = {
    "hi": "hi-IN",
    "fr": "fr-FR",
    "de": "de-DE",
    "es": "es-ES",
    "ta": "hi-IN",
}

# AWS client initialised at module level (rule 4).
polly = boto3.client("polly", region_name=AWS_REGION)


def synthesize(text, lang):
    """Return base64-encoded MP3 audio for `text` in language `lang`."""
    voice = VOICE_MAP.get(lang, DEFAULT_VOICE)
    kwargs = {
        "Text": text,
        "OutputFormat": "mp3",
        "VoiceId": voice,
    }
    if lang != "en" and lang in LANGUAGE_CODE:
        kwargs["LanguageCode"] = LANGUAGE_CODE[lang]

    response = polly.synthesize_speech(**kwargs)
    audio = response["AudioStream"].read()
    return base64.b64encode(audio).decode("utf-8"), voice


def handler(event, context=None):
    text = (event or {}).get("text")
    lang = (event or {}).get("lang", "en")
    if not text:
        return {"error": "Missing 'text' in TTS request"}
    try:
        audio_b64, voice = synthesize(text, lang)
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the caller
        return {"error": f"TTS synthesis failed: {exc}"}
    return {"audio_b64": audio_b64, "voice": voice, "lang": lang}
