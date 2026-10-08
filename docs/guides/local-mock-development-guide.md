# Weather Buddy — Local Mock Development & Offline Simulation Guide

This guide details how to develop, test, and run Weather Buddy completely offline without live internet access or third-party cloud API keys using simulated meteorological data and synthetic audio mocks.

---

## 1. Zero-Cloud Mocking Architecture

For offline development (on flights, hackathons with restricted Wi-Fi, or zero-cost local iteration), Weather Buddy provides an integrated mocking mode:

```
┌─────────────────────────────────┐
│     Next.js Web Client          │
│     (http://localhost:3000)     │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│     Local Python Server         │  ◄── run_local.py with MOCK_MODE=true
│     (http://127.0.0.1:3001)     │
└────────┬───────────────┬────────┘
         │               │
         ▼               ▼
┌─────────────────┐  ┌──────────────────┐
│ Synthetic Audio │  │ Simulated Sensor │
│ Mock Generator  │  │ JSON Fixtures    │
│ (Static MP3 b64)│  │ (Seattle / Tokyo)│
└─────────────────┘  └──────────────────┘
```

---

## 2. Enabling Offline Mock Mode

Set the environment variable in your root `.env`:

```env
# Enable offline mock data simulation
MOCK_MODE=true

# Local dev server port
PORT=3001
```

When `MOCK_MODE=true` is enabled:
1. `POST /transcribe`: Returns a deterministic synthetic transcription without querying Groq Whisper:
   ```json
   {
     "text": "What is the weather in Seattle today?",
     "language": "en",
     "confidence": 1.0,
     "duration_seconds": 2.5
   }
   ```
2. `tools.py`: Bypasses external HTTP queries to OpenWeatherMap, returning realistic local weather metrics from bundled test fixtures.
3. `_synthesize()`: Returns a pre-encoded 2-second synthesized speech MP3 buffer without calling Amazon Polly.

---

## 3. Mock Data Fixture Structure

Simulated city profiles are located in `fixtures/cities.json`:

```json
{
  "seattle": {
    "city": "Seattle",
    "country": "US",
    "temp": 16.5,
    "feels_like": 15.8,
    "condition": "Rain",
    "description": "light rain",
    "humidity": 78,
    "wind_speed": 4.1,
    "icon": "10d"
  },
  "tokyo": {
    "city": "Tokyo",
    "country": "JP",
    "temp": 22.0,
    "feels_like": 21.5,
    "condition": "Clear",
    "description": "clear sky",
    "humidity": 50,
    "wind_speed": 2.8,
    "icon": "01d"
  },
  "paris": {
    "city": "Paris",
    "country": "FR",
    "temp": 18.2,
    "feels_like": 17.9,
    "condition": "Clouds",
    "description": "broken clouds",
    "humidity": 65,
    "wind_speed": 3.2,
    "icon": "04d"
  }
}
```

---

## 4. Testing Offline Query Flows via cURL

```bash
# 1. Query current weather offline
curl -X POST http://127.0.0.1:3001/query \
  -H "Content-Type: application/json" \
  -d '{"text": "What is the weather in Seattle?", "lang": "en"}'

# 2. Query multi-lingual response offline
curl -X POST http://127.0.0.1:3001/query \
  -H "Content-Type: application/json" \
  -d '{"text": "Quel temps fait-il à Paris?", "lang": "fr"}'
```
