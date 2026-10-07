import pytest

from agent_service.config import Settings

BASE_ENV = {
    "OWM_API_KEY": "owm-test-key",
    "LLM_MODEL_ID": "groq/test-model",
    "LLM_API_KEY": "llm-test-key",
    "TTS_CACHE_DIR": "",
}


@pytest.fixture
def make_settings():
    """Build Settings from an explicit dict, never from the real environment or .env."""
    def _make(**overrides):
        env = {**BASE_ENV, **{k: str(v) for k, v in overrides.items()}}
        return Settings.from_env(env)
    return _make


@pytest.fixture
def settings(make_settings):
    return make_settings()
