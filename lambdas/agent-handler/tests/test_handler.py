"""Offline tests for the /query handler (Groq-native: no Comprehend/Translate)."""

import io
import json

import handler
from tools import LocationNotFoundError


class _FakeLambda:
    """Stubs the tts-handler invoke, returning a fixed audio_b64."""

    def __init__(self, audio_b64="QUJD"):
        self.audio_b64 = audio_b64
        self.last_payload = None

    def invoke(self, FunctionName, InvocationType, Payload):  # noqa: N803
        self.last_payload = json.loads(Payload.decode("utf-8"))
        body = json.dumps({"audio_b64": self.audio_b64}).encode("utf-8")
        return {"Payload": io.BytesIO(body)}


def _event(text, lang="en", messages=None):
    return {"body": json.dumps({"text": text, "lang": lang, "messages": messages or []})}


def test_query_success(monkeypatch):
    fake_lambda = _FakeLambda()
    monkeypatch.setattr(handler, "lambda_client", fake_lambda)
    monkeypatch.setattr(
        handler, "run_agent",
        lambda text, messages, user_lang="en", context_location=None: (
            "Sunny in Delhi.", messages
        ),
    )

    result = handler.handler(_event("What's the weather in Delhi?", lang="en"))
    body = json.loads(result["body"])

    assert result["statusCode"] == 200
    assert result["headers"]["Access-Control-Allow-Origin"] == "*"
    assert body["response_text"] == "Sunny in Delhi."
    assert body["lang"] == "en"
    assert body["audio_b64"] == "QUJD"
    assert "weather_data" in body and "forecast_data" in body
    assert fake_lambda.last_payload == {"text": "Sunny in Delhi.", "lang": "en"}


def test_lang_passed_through_to_agent(monkeypatch):
    monkeypatch.setattr(handler, "lambda_client", _FakeLambda())
    captured = {}

    def fake_run_agent(text, messages, user_lang="en", context_location=None):
        captured["user_lang"] = user_lang
        return "namaste", messages

    monkeypatch.setattr(handler, "run_agent", fake_run_agent)

    body = json.loads(handler.handler(_event("mausam", lang="hi"))["body"])
    assert captured["user_lang"] == "hi"
    assert body["lang"] == "hi"


def test_missing_text_returns_400():
    result = handler.handler(_event(""))
    assert result["statusCode"] == 400
    assert "error" in json.loads(result["body"])


def test_invalid_json_returns_400():
    result = handler.handler({"body": "{not json"})
    assert result["statusCode"] == 400


def test_location_not_found_returns_400(monkeypatch):
    def boom(text, messages, user_lang="en", context_location=None):
        raise LocationNotFoundError("Nowhere")

    monkeypatch.setattr(handler, "run_agent", boom)
    result = handler.handler(_event("weather in Nowhere"))
    assert result["statusCode"] == 400
    assert json.loads(result["body"])["error"] == "Location not found"


def test_weather_data_extracted_from_tool_results(monkeypatch):
    monkeypatch.setattr(handler, "lambda_client", _FakeLambda())
    messages_with_tool = [
        {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "toolUseId": "t1",
                        "content": [
                            {"json": {"location": "Delhi, IN", "temp": 29,
                                       "humidity": 40, "description": "clear sky"}}
                        ],
                    }
                }
            ],
        }
    ]
    monkeypatch.setattr(
        handler, "run_agent",
        lambda text, messages, user_lang="en", context_location=None: (
            "Clear in Delhi.", messages_with_tool
        ),
    )

    body = json.loads(handler.handler(_event("weather in Delhi"))["body"])
    assert body["weather_data"]["temp"] == 29
    assert body["weather_data"]["description"] == "clear sky"


def test_transcribe_missing_audio_returns_400():
    result = handler.handler({"path": "/transcribe", "body": json.dumps({})})
    assert result["statusCode"] == 400
    assert "audio" in json.loads(result["body"])["error"].lower()
