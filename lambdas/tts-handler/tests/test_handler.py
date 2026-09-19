"""Offline tests for tts-handler. Polly is stubbed; these run every time."""

import base64
import io

import handler


class _FakePolly:
    def __init__(self):
        self.last_kwargs = None

    def synthesize_speech(self, **kwargs):
        self.last_kwargs = kwargs
        return {"AudioStream": io.BytesIO(b"fake-mp3-bytes")}


def test_english_returns_base64_audio(monkeypatch):
    fake = _FakePolly()
    monkeypatch.setattr(handler, "polly", fake)

    result = handler.handler({"text": "Sunny in Delhi.", "lang": "en"})

    assert result["voice"] == "Joanna"
    assert base64.b64decode(result["audio_b64"]) == b"fake-mp3-bytes"
    # English must NOT send a LanguageCode (pitfall)
    assert "LanguageCode" not in fake.last_kwargs
    assert fake.last_kwargs["OutputFormat"] == "mp3"


def test_hindi_uses_aditi_and_language_code(monkeypatch):
    fake = _FakePolly()
    monkeypatch.setattr(handler, "polly", fake)

    result = handler.handler({"text": "namaste", "lang": "hi"})

    assert result["voice"] == "Aditi"
    assert fake.last_kwargs["LanguageCode"] == "hi-IN"


def test_unknown_lang_falls_back_to_default_voice(monkeypatch):
    fake = _FakePolly()
    monkeypatch.setattr(handler, "polly", fake)

    result = handler.handler({"text": "hello", "lang": "zz"})

    assert result["voice"] == handler.DEFAULT_VOICE


def test_missing_text_returns_error(monkeypatch):
    monkeypatch.setattr(handler, "polly", _FakePolly())
    assert "error" in handler.handler({"lang": "en"})


def test_polly_failure_returns_error(monkeypatch):
    class Boom:
        def synthesize_speech(self, **kwargs):
            raise RuntimeError("polly down")

    monkeypatch.setattr(handler, "polly", Boom())
    result = handler.handler({"text": "hi", "lang": "en"})
    assert "error" in result
