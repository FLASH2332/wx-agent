"""Live agent tests: real Bedrock + real OWM. Skipped by default.

Requires an active OWM key, AWS creds, and Bedrock Haiku model access.
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
