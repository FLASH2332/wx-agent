"""Live tts-handler test: real Amazon Polly. Skipped by default.

Requires AWS creds with polly:SynthesizeSpeech. Run with:
    RUN_LIVE_POLLY=1 pytest -m live
"""

import base64
import importlib
import os

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("RUN_LIVE_POLLY"),
        reason="set RUN_LIVE_POLLY=1 to run tests that call the real Polly API",
    ),
]


@pytest.fixture(scope="module")
def handler_mod():
    os.environ.setdefault("AWS_REGION", "us-east-1")
    import handler

    return importlib.reload(handler)


def test_english_audio_is_valid_mp3(handler_mod):
    result = handler_mod.handler({"text": "Hello, it is sunny today.", "lang": "en"})
    assert "error" not in result, result
    audio = base64.b64decode(result["audio_b64"])
    # MP3 frames start with an ID3 tag or a 0xFF sync byte.
    assert audio[:3] == b"ID3" or audio[0] == 0xFF
    assert result["voice"] == "Joanna"
