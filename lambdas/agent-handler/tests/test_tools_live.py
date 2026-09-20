"""Live tests that hit the real OpenWeatherMap API.

Skipped by default so the normal test run makes no network calls / burns no quota.
Run explicitly with:  RUN_LIVE_OWM=1 pytest -m live
"""

import importlib
import os

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("RUN_LIVE_OWM"),
        reason="set RUN_LIVE_OWM=1 to run tests that call the real OWM API",
    ),
]


@pytest.fixture(scope="module")
def tools_live():
    # .env is loaded by conftest; require a real key (not the offline dummy).
    if os.environ.get("OWM_API_KEY", "test-key") == "test-key":
        pytest.skip("OWM_API_KEY not set in .env")
    import tools

    return importlib.reload(tools)


def test_current_weather_chennai_live(tools_live):
    result = tools_live.get_current_weather("Chennai")
    assert isinstance(result["temp"], (int, float))
    assert isinstance(result["humidity"], (int, float))
    assert result["description"]
    assert result["location"].startswith("Chennai")
