"""Offline tests for the /query handler. All AWS seams are stubbed."""

import io
import json

import handler
from tools import LocationNotFoundError


class _FakeComprehend:
    def __init__(self, lang):
        self.lang = lang

    def detect_dominant_language(self, Text):  # noqa: N803 - boto3 kwarg name
        return {"Languages": [{"LanguageCode": self.lang}]}


class _RecordingTranslate:
    def __init__(self):
        self.calls = []

    def translate_text(self, Text, SourceLanguageCode, TargetLanguageCode):  # noqa: N803
        self.calls.append((Text, SourceLanguageCode, TargetLanguageCode))
        return {"TranslatedText": f"[{TargetLanguageCode}]{Text}"}


class _FakeLambda:
    def __init__(self, audio_b64="QUJD"):
        self.audio_b64 = audio_b64
        self.last_payload = None

    def invoke(self, FunctionName, InvocationType, Payload):  # noqa: N803
        self.last_payload = json.loads(Payload.decode("utf-8"))
        body = json.dumps({"audio_b64": self.audio_b64}).encode("utf-8")
        return {"Payload": io.BytesIO(body)}


def _event(text, lang="en", messages=None):
    return {"body": json.dumps({"text": text, "lang": lang, "messages": messages or []})}


def test_english_flow_skips_translation(monkeypatch):
    translate = _RecordingTranslate()
    fake_lambda = _FakeLambda()
    monkeypatch.setattr(handler, "comprehend", _FakeComprehend("en"))
    monkeypatch.setattr(handler, "translate", translate)
    monkeypatch.setattr(handler, "lambda_client", fake_lambda)
    monkeypatch.setattr(handler, "run_agent", lambda t, m: ("Sunny in Delhi.", m))

    result = handler.handler(_event("What's the weather in Delhi?"))
    body = json.loads(result["body"])

    assert result["statusCode"] == 200
    assert result["headers"]["Access-Control-Allow-Origin"] == "*"
    assert body["response_text"] == "Sunny in Delhi."
    assert body["lang"] == "en"
    assert translate.calls == []  # no translation for English
    assert fake_lambda.last_payload == {"text": "Sunny in Delhi.", "lang": "en"}
    assert body["audio_b64"] == "QUJD"


def test_hindi_flow_translates_both_ways(monkeypatch):
    translate = _RecordingTranslate()
    fake_lambda = _FakeLambda()
    monkeypatch.setattr(handler, "comprehend", _FakeComprehend("hi"))
    monkeypatch.setattr(handler, "translate", translate)
    monkeypatch.setattr(handler, "lambda_client", fake_lambda)

    captured = {}

    def fake_run_agent(text, messages):
        captured["english_in"] = text
        return "It is sunny.", messages

    monkeypatch.setattr(handler, "run_agent", fake_run_agent)

    result = handler.handler(_event("mausam", lang="hi"))
    body = json.loads(result["body"])

    assert result["statusCode"] == 200
    assert body["lang"] == "hi"
    # transcript translated to English before the agent
    assert captured["english_in"] == "[en]mausam"
    # response translated back to Hindi before TTS
    assert body["response_text"] == "[hi]It is sunny."
    assert fake_lambda.last_payload["lang"] == "hi"
    assert [c[1:] for c in translate.calls] == [("hi", "en"), ("en", "hi")]


def test_missing_text_returns_400(monkeypatch):
    monkeypatch.setattr(handler, "comprehend", _FakeComprehend("en"))
    result = handler.handler(_event(""))
    assert result["statusCode"] == 400
    assert "error" in json.loads(result["body"])


def test_invalid_json_returns_400():
    result = handler.handler({"body": "{not json"})
    assert result["statusCode"] == 400


def test_location_not_found_returns_400(monkeypatch):
    monkeypatch.setattr(handler, "comprehend", _FakeComprehend("en"))

    def boom(text, messages):
        raise LocationNotFoundError("Nowhere")

    monkeypatch.setattr(handler, "run_agent", boom)
    result = handler.handler(_event("weather in Nowhere"))
    assert result["statusCode"] == 400
    assert json.loads(result["body"])["error"] == "Location not found"


def test_weather_data_extracted_from_tool_results(monkeypatch):
    monkeypatch.setattr(handler, "comprehend", _FakeComprehend("en"))
    monkeypatch.setattr(handler, "translate", _RecordingTranslate())
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
        handler, "run_agent", lambda t, m: ("Clear in Delhi.", messages_with_tool)
    )

    body = json.loads(handler.handler(_event("weather in Delhi"))["body"])
    assert body["weather_data"]["temp"] == 29
    assert body["weather_data"]["description"] == "clear sky"
