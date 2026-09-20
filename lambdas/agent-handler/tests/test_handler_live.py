"""Live end-to-end integration test for the /query handler.

Exercises the real backend chain together: Amazon Comprehend (language detect),
Amazon Translate (both ways for non-English), the Strands agent (Groq provider),
and Amazon Polly (via the real tts-handler code). Skipped by default.

Requires: AWS creds (Comprehend/Translate/Polly), an active OWM key, and Groq set
in the repo-root .env (MODEL_PROVIDER=groq, GROQ_API_KEY). Run with:
    RUN_LIVE_HANDLER=1 pytest -m live -s
"""

import base64
import importlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("RUN_LIVE_HANDLER"),
        reason="set RUN_LIVE_HANDLER=1 to run the live handler integration test",
    ),
]

_HANDLER_DIR = Path(__file__).resolve().parents[1]
_ENV_PATH = _HANDLER_DIR.parents[1] / ".env"
_TTS_HANDLER_PATH = _HANDLER_DIR.parent / "tts-handler" / "handler.py"


def _load_root_env():
    if not _ENV_PATH.exists():
        pytest.skip(f"no .env at {_ENV_PATH}")
    for line in _ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()
    os.environ.setdefault("AWS_REGION", "us-east-1")
    # handler reads this at import; no Lambda is deployed locally, so use a
    # placeholder and route TTS through the real tts-handler code below.
    os.environ.setdefault("TTS_LAMBDA_NAME", "local-tts")


def _load_tts_module():
    spec = importlib.util.spec_from_file_location("tts_handler_live", _TTS_HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def handler_mod():
    _load_root_env()
    if os.environ.get("MODEL_PROVIDER", "").lower() != "groq":
        pytest.skip("set MODEL_PROVIDER=groq in .env to run the live handler test")

    import agent

    importlib.reload(agent)
    import handler

    handler = importlib.reload(handler)

    # Run TTS locally via the real tts-handler code instead of invoking a Lambda.
    tts = _load_tts_module()
    handler._synthesize = lambda text, lang: tts.handler(
        {"text": text, "lang": lang}
    ).get("audio_b64", "")
    return handler


def _event(text, lang):
    return {"body": json.dumps({"text": text, "lang": lang, "messages": []})}


def test_full_english_flow(handler_mod):
    """Checkpoint 6 (backend): English query -> real weather + audio, no translation."""
    result = handler_mod.handler(_event("What's the weather in Delhi?", "en"))
    assert result["statusCode"] == 200, result["body"]
    body = json.loads(result["body"])

    assert body["lang"] == "en"
    assert body["response_text"].strip()
    # real weather surfaced for the card
    assert isinstance(body["weather_data"].get("temp"), (int, float))
    # valid MP3 audio from Polly
    audio = base64.b64decode(body["audio_b64"])
    assert audio[:3] == b"ID3" or audio[0] == 0xFF


def test_full_hindi_flow(handler_mod):
    """Checkpoint 7 (backend): Hindi query -> detected, translated both ways, Hindi audio."""
    result = handler_mod.handler(
        _event("कल मुंबई में "
               "मौसम कैसा होगा?", "hi")
    )
    assert result["statusCode"] == 200, result["body"]
    body = json.loads(result["body"])

    assert body["lang"] == "hi"
    assert body["response_text"].strip()
    audio = base64.b64decode(body["audio_b64"])
    assert audio[:3] == b"ID3" or audio[0] == 0xFF
