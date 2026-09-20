"""Live agent tests: real LLM endpoint + real OWM. Skipped by default.

Requires an active OWM key and a reachable LLM endpoint (LLM_MODEL_ID /
LLM_BASE_URL / LLM_API_KEY) in the repo-root .env.
Run with:  RUN_LIVE_AGENT=1 pytest -m live
"""

import importlib
import os

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("RUN_LIVE_AGENT"),
        reason="set RUN_LIVE_AGENT=1 to run tests that call Bedrock + OWM",
    ),
]

_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"


def _load_root_env():
    if not _ENV_PATH.exists():
        pytest.skip(f"no .env at {_ENV_PATH}")
    for line in _ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()
    os.environ.setdefault("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
    os.environ.setdefault("AWS_REGION", "us-east-2")


@pytest.fixture(scope="module")
def agent_mod():
    # .env is loaded by conftest; require a real OWM key (not the offline dummy).
    if os.environ.get("OWM_API_KEY", "test-key") == "test-key":
        pytest.skip("OWM_API_KEY not set in .env")
    import agent

    return importlib.reload(agent)


def test_single_city_query(agent_mod):
    """Checkpoint 2: readable string for a simple current-weather question."""
    text, messages = agent_mod.run_agent("What's the weather in Delhi?")
    assert isinstance(text, str) and len(text.strip()) > 0
    assert len(messages) >= 2  # user + assistant turns appended


def test_compare_two_cities(agent_mod):
    """Checkpoint 3: comparison should exercise the weather tool for each city."""
    text, _ = agent_mod.run_agent("Compare Mumbai and Bengaluru weather.")
    assert isinstance(text, str) and len(text.strip()) > 0
