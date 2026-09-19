"""agent-handler Lambda: the POST /query entrypoint.

Flow per request:
  1. Detect the dominant language with Amazon Comprehend.
  2. If non-English, translate the transcript to English with Amazon Translate.
  3. Run the Strands agent on English text; it returns an English answer.
  4. If non-English, translate the answer back to the user's language.
  5. Synthesize speech by invoking tts-handler via boto3 (never HTTP).
  6. Return response_text, audio_b64, weather_data, lang, and updated messages.
"""

import json
import os

import boto3

from agent import latest_weather_data, run_agent
from tools import LocationNotFoundError

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
TTS_LAMBDA_NAME = os.environ["TTS_LAMBDA_NAME"]

# AWS clients initialised at module level (avoids re-init on warm invocations).
comprehend = boto3.client("comprehend", region_name=AWS_REGION)
translate = boto3.client("translate", region_name=AWS_REGION)
lambda_client = boto3.client("lambda", region_name=AWS_REGION)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json",
}


def _response(status, body):
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps(body)}


def _parse_body(event):
    body = event.get("body") if isinstance(event, dict) else None
    if body is None:
        # Direct invoke / already-parsed payload.
        return event if isinstance(event, dict) else {}
    if isinstance(body, (dict, list)):
        return body
    return json.loads(body)


def _detect_language(text, fallback="en"):
    """Return the dominant 2-letter language code (Comprehend), or a fallback."""
    try:
        result = comprehend.detect_dominant_language(Text=text)
        languages = result.get("Languages") or []
        if languages:
            return languages[0]["LanguageCode"]
    except Exception:  # noqa: BLE001 - detection is best-effort
        pass
    return fallback


def _translate(text, source, target):
    result = translate.translate_text(
        Text=text, SourceLanguageCode=source, TargetLanguageCode=target
    )
    return result["TranslatedText"]


def _synthesize(text, lang):
    """Invoke tts-handler and return its audio_b64 (empty string on failure)."""
    invoke = lambda_client.invoke(
        FunctionName=TTS_LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps({"text": text, "lang": lang}).encode("utf-8"),
    )
    payload = json.loads(invoke["Payload"].read().decode("utf-8"))
    return payload.get("audio_b64", "")


def handler(event, context=None):
    try:
        body = _parse_body(event)
    except (ValueError, TypeError):
        return _response(400, {"error": "Invalid JSON body"})

    text = (body.get("text") or "").strip()
    if not text:
        return _response(400, {"error": "Missing 'text' in request"})
    messages = body.get("messages") or []
    fallback_lang = body.get("lang") or "en"

    try:
        user_lang = _detect_language(text, fallback=fallback_lang)

        english_text = text if user_lang == "en" else _translate(text, user_lang, "en")
        response_en, updated_messages = run_agent(english_text, messages)
        final_text = (
            response_en
            if user_lang == "en"
            else _translate(response_en, "en", user_lang)
        )

        audio_b64 = _synthesize(final_text, user_lang)
        weather_data = latest_weather_data(updated_messages)

        return _response(
            200,
            {
                "response_text": final_text,
                "audio_b64": audio_b64,
                "weather_data": weather_data,
                "lang": user_lang,
                "messages": updated_messages,
            },
        )
    except LocationNotFoundError:
        return _response(400, {"error": "Location not found"})
    except Exception as exc:  # noqa: BLE001 - never leak an uncaught exception
        return _response(500, {"error": str(exc)})
