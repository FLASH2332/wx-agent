# Weather Buddy — Testing & Quality Assurance Handbook

This handbook establishes the testing methodology, fixture patterns, mock abstractions, and quality standards for Weather Buddy across Python backend services and JavaScript/React frontend components.

---

## 1. Testing Philosophy & Isolation Principles

Weather Buddy enforces **zero-credential offline testability**:
- No test should ever depend on active AWS credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`).
- No test should perform live billable HTTP requests against Groq, OpenWeatherMap, or Amazon Polly.
- Tests must execute deterministically in CI/CD pipelines without network flakiness.

```
       Unit Tests (Fast, Isolated, Mocked)
               │
               ▼
┌──────────────────────────────────────────────┐
│  lambdas/agent-handler/tests                 │
│  • Mock LiteLLM responses                    │
│  • Mock OpenWeatherMap & NWS JSON responses  │
│  • Validate tool routing & exception catches │
└──────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  lambdas/tts-handler/tests                   │
│  • Mock Boto3 Polly client                   │
│  • Validate voice ID mappings                │
│  • Test base64 encoding integrity            │
└──────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  lambdas/alert-handler/tests                 │
│  • Mock EventBridge cron trigger events      │
│  • Mock SNS publish calls                    │
│  • Verify active vs silent alert conditions  │
└──────────────────────────────────────────────┘
```

---

## 2. Running Test Suites

### 2.1 The Master Makefile Target
The root `Makefile` provides an aggregated target to run unit tests across all Lambda microservices:

```bash
make test
```

### 2.2 Running Python Tests Manually
```bash
# Agent Handler Tests
cd lambdas/agent-handler
python -m pytest -v --cov=.

# TTS Handler Tests
cd lambdas/tts-handler
python -m pytest -v --cov=.

# Alert Handler Tests
cd lambdas/alert-handler
python -m pytest -v --cov=.
```

---

## 3. Mocking Patterns & Fixtures

### 3.1 Mocking OpenWeatherMap Responses

Weather responses are mocked using Python's `unittest.mock` to simulate real API schemas without network activity:

```python
import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_owm_weather():
    return {
        "coord": {"lon": -122.3321, "lat": 47.6062},
        "weather": [{"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"}],
        "main": {
            "temp": 18.2,
            "feels_like": 17.5,
            "temp_min": 15.0,
            "temp_max": 20.5,
            "pressure": 1018,
            "humidity": 55,
        },
        "wind": {"speed": 3.6, "deg": 320},
        "name": "Seattle",
        "sys": {"country": "US"},
    }

def test_get_current_weather(mock_owm_weather):
    with patch("urllib.request.urlopen") as mock_url:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_owm_weather).encode("utf-8")
        mock_url.return_value = mock_response
        
        result = get_current_weather("Seattle, US")
        assert result["temp"] == 18.2
        assert result["condition"] == "Clear"
```

### 3.2 Mocking Boto3 Polly Client in `tts-handler`

```python
from unittest.mock import MagicMock
import io

def test_tts_handler_synthesize_speech():
    mock_polly = MagicMock()
    # Simulate AudioStream byte buffer
    mock_polly.synthesize_speech.return_value = {
        "AudioStream": io.BytesIO(b"MOCK_MP3_BINARY_DATA"),
        "ContentType": "audio/mpeg"
    }

    with patch("boto3.client", return_value=mock_polly):
        event = {"text": "Hello world", "lang": "en"}
        response = handler(event, None)
        assert "audio_b64" in response
        assert response["audio_b64"] != ""
```

---

## 4. Frontend Component Testing

Frontend tests verify React rendering, user event handlers, and design token adherence:

```bash
cd frontend
npm test
```

### Key UI Invariants Tested:
1. **Touch Target Size:** Interactive buttons must render with `min-height: 44px` and `min-width: 44px`.
2. **Audio Autoplay Safety:** Audio players must not initiate sound without preceding user interaction.
3. **Number Formatting:** Meteorological values must render using tabular numeral fonts to prevent UI layout jitter when values increment.
