"""Live tests that hit the real OpenWeatherMap API.

Skipped by default so the normal test run makes no network calls / burns no quota.
Run explicitly with:  RUN_LIVE_OWM=1 pytest -m live
"""

import importlib
import os
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("RUN_LIVE_OWM"),
        reason="set RUN_LIVE_OWM=1 to run tests that call the real OWM API",
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
    if not os.environ.get("OWM_API_KEY"):
        pytest.skip("OWM_API_KEY not set in .env")


@pytest.fixture(scope="module")
def tools_live():
    _load_root_env()
    import tools

    return importlib.reload(tools)


def test_current_weather_chennai_live(tools_live):
    result = tools_live.get_current_weather("Chennai")
    assert isinstance(result["temp"], (int, float))
    assert isinstance(result["humidity"], (int, float))
    assert result["description"]
    assert result["location"].startswith("Chennai")
