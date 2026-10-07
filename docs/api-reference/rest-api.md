# Weather Buddy — REST API & Integration Reference

This reference manual documents the HTTP and Serverless REST endpoints provided by the Weather Buddy backend services, including request payloads, response schemas, error codes, and external meteorological service integration contracts.

---

## 1. Global Specifications & Endpoints

Weather Buddy provides two deployment operational targets:
- **Local Dev Server:** `http://127.0.0.1:3001`
- **AWS Serverless Production (Function URL):** `https://<unique-id>.lambda-url.<region>.on.aws`
- **Frontend Internal API Routes:** Hosted on Next.js server runtime (e.g., `http://localhost:3000/api` or `https://your-domain.vercel.app/api`)

### Global HTTP Headers
| Header Name | Value / Format | Description |
|-------------|----------------|-------------|
| `Content-Type` | `application/json` | Required for JSON RPC requests |
| `User-Agent` | `WeatherBuddy/1.0` | Configured on all outbound requests |
| `Access-Control-Allow-Origin` | `*` | Permits cross-origin browser fetch queries |
| `Access-Control-Allow-Methods` | `POST, OPTIONS, GET` | Supported HTTP verb registry |

---

## 2. Core Backend API Endpoints

### 2.1 Natural Language Weather Query: `POST /query`

The primary conversational interface. Takes a user prompt in any language, coordinates meteorological tool evaluations via the Strands Agent loop, requests speech synthesis from the TTS microservice, and returns formatted response text, latest structured weather attributes, and base64 audio.

#### Endpoint Signature
- **URL Path:** `/query`
- **HTTP Method:** `POST`
- **Authentication:** None (Public Endpoint via Lambda Function URL)
- **Content-Type:** `application/json`

#### Request Schema & Parameters
```json
{
  "type": "object",
  "properties": {
    "text": {
      "type": "string",
      "description": "The user's spoken or typed natural language query.",
      "example": "Will it rain in London this afternoon?"
    },
    "lang": {
      "type": "string",
      "description": "Two-letter ISO-639-1 language code detected from Whisper or UI selection.",
      "example": "en",
      "default": "en"
    },
    "contextLocation": {
      "type": "string",
      "description": "Active city currently viewed on the dashboard to resolve ambiguous location queries.",
      "example": "London, GB",
      "default": "London, GB"
    },
    "messages": {
      "type": "array",
      "description": "Optional conversational history array containing prior turn messages.",
      "items": {
        "type": "object",
        "properties": {
          "role": { "type": "string", "enum": ["user", "assistant"] },
          "content": { "type": "string" }
        }
      }
    }
  },
  "required": ["text"]
}
```

#### Successful Response (`200 OK`)
```json
{
  "response_text": "No rain is forecast for London this afternoon. Conditions will be mostly cloudy with temperatures around 16°C and a light westerly breeze of 8 km/h.",
  "audio_b64": "SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//uQZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAAbAAAGsA...",
  "weather_data": {
    "city": "London",
    "country": "GB",
    "temp": 16.2,
    "feels_like": 15.8,
    "condition": "Clouds",
    "description": "broken clouds",
    "humidity": 68,
    "wind_speed": 2.2,
    "icon": "04d"
  },
  "forecast_data": {
    "city": "London",
    "daily": [
      {
        "date": "2026-10-07",
        "temp_min": 11.4,
        "temp_max": 17.1,
        "condition": "Clouds",
        "pop": 0.15
      },
      {
        "date": "2026-10-08",
        "temp_min": 10.2,
        "temp_max": 18.0,
        "condition": "Clear",
        "pop": 0.05
      }
    ]
  },
  "lang": "en",
  "messages": [
    {
      "role": "user",
      "content": "Will it rain in London this afternoon?"
    },
    {
      "role": "assistant",
      "content": "No rain is forecast for London this afternoon. Conditions will be mostly cloudy with temperatures around 16°C and a light westerly breeze of 8 km/h."
    }
  ]
}
```

#### Error Responses
| HTTP Code | Error Reason | Example Body |
|-----------|--------------|--------------|
| `400 Bad Request` | Missing `text` or malformed JSON payload | `{"error": "Missing 'text' field in request payload"}` |
| `404 Not Found` | Unknown location that could not be resolved | `{"error": "Could not locate the requested city: 'Atlantis'"}` |
| `500 Server Error` | Uncaught exception in agent or tool loop | `{"error": "Internal agent execution error: connection timed out"}` |

#### cURL Invocation Example
```bash
curl -X POST https://abcdef12345.lambda-url.us-east-1.on.aws/query \
  -H "Content-Type: application/json" \
  -d '{
    "text": "¿Cómo está el clima en Madrid hoy?",
    "lang": "es",
    "contextLocation": "Madrid, ES"
  }'
```

---

### 2.2 Speech-to-Text Audio Transcription: `POST /transcribe`

Accepts raw audio streams captured from browser microphone recordings, sends the payload to Groq's high-throughput Whisper Large v3 model, and returns the transcribed text along with the automatically detected ISO-639-1 language code.

#### Endpoint Signature
- **URL Path:** `/transcribe`
- **HTTP Method:** `POST`
- **Content-Type:** `multipart/form-data`

#### Multipart Form Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | `Binary Blob` | Yes | Audio recording (`audio/webm`, `audio/wav`, `audio/mp3`, or `audio/ogg`). |
| `prompt` | `string` | No | Optional contextual prompt to bias Whisper vocabulary toward weather terms. |

#### Successful Response (`200 OK`)
```json
{
  "text": "What is the 3-day forecast for Berlin?",
  "language": "en",
  "confidence": 0.985,
  "duration_seconds": 3.12
}
```

#### Multilingual Example
If the speaker speaks in Japanese:
```json
{
  "text": "明日の東京の天気はどうですか？",
  "language": "ja",
  "confidence": 0.991,
  "duration_seconds": 2.85
}
```

#### cURL Invocation Example
```bash
curl -X POST https://abcdef12345.lambda-url.us-east-1.on.aws/transcribe \
  -F "file=@sample_recording.webm;type=audio/webm"
```

---

### 2.3 GDACS Global Disaster Alert Proxy: `GET /api/alerts`

Next.js server-side API route that proxies the Global Disaster Alert and Coordination System (GDACS) RSS/JSON feed. It caches alert data for 5 minutes (300 seconds) in memory to avoid redundant external network round trips and rate-limit penalties.

#### Endpoint Signature
- **URL Path:** `/api/alerts`
- **HTTP Method:** `GET`
- **Caching Header:** `Cache-Control: s-maxage=300, stale-while-revalidate`

#### Query Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `country` | `string` | No | Filters alerts by ISO-3166-1 alpha-2 or alpha-3 country code (e.g. `US`, `IND`, `JPN`). |
| `event_type` | `string` | No | Filters alerts by hazard type: `TC` (Tropical Cyclone), `FL` (Flood), `DR` (Drought). |

#### Successful Response (`200 OK`)
```json
{
  "status": "success",
  "count": 1,
  "alerts": [
    {
      "id": "GDACS-TC-1000921",
      "title": "Tropical Cyclone Warning: Category 2",
      "severity": "Orange",
      "country": "PH",
      "area_description": "Northern Luzon coastal regions",
      "event_type": "TC",
      "published_at": "2026-10-07T04:15:00Z",
      "source_url": "https://www.gdacs.org/report.aspx?eventtype=TC&eventid=1000921"
    }
  ]
}
```

---

## 3. Internal Microservice Contracts

### 3.1 Speech Synthesis Service (`tts-handler`)

Invoked internally within AWS via AWS SDK Lambda Client.

#### Payload Contract
```json
{
  "text": "Weather in Tokyo is currently sunny, 21 degrees.",
  "lang": "en"
}
```

#### Response Contract
```json
{
  "status": "success",
  "voice_id": "Joanna",
  "audio_b64": "SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//uQZAAAAAAAAAAAAAAAA...",
  "format": "mp3"
}
```

### 3.2 Scheduled Alert Evaluator Service (`alert-handler`)

Triggered automatically by AWS EventBridge rule `cron(30 1 * * ? *)`.

#### Event Input Contract
```json
{
  "version": "0",
  "id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "detail-type": "Scheduled Event",
  "source": "aws.events",
  "time": "2026-10-07T01:30:00Z",
  "region": "us-east-1",
  "resources": [
    "arn:aws:events:us-east-1:123456789012:rule/WeatherBuddyAlertSchedule"
  ],
  "detail": {}
}
```

#### Execution Outcome
1. Queries OpenWeatherMap OneCall or Weather alerts for configured `ALERT_LOCATION`.
2. Formats email subject: `[Weather Buddy Alert] Severe Weather Notice for <Location>`
3. Publishes to SNS Topic: `weather-buddy-alerts`
4. Returns execution metric log:
   ```json
   {
     "status": "completed",
     "alerts_found": 0,
     "sns_published": false
   }
   ```

---

## 4. Meteorological Provider Contracts

### 4.1 OpenWeatherMap v2.5 Specification

Weather Buddy interfaces with OpenWeatherMap using the free tier endpoint suite:

#### Current Weather Endpoint
- **URL:** `https://api.openweathermap.org/data/2.5/weather`
- **Method:** `GET`
- **Parameters:**
  - `q`: `<City, CountryCode>` (e.g., `Seattle,US`)
  - `appid`: OpenWeatherMap API Key
  - `units`: `metric` (Celsius, m/s) or `imperial` (Fahrenheit, mph)
  - `lang`: ISO-639-1 language code (e.g. `fr`, `es`, `hi`)

#### 5-Day / 3-Hour Forecast Endpoint
- **URL:** `https://api.openweathermap.org/data/2.5/forecast`
- **Method:** `GET`
- **Parameters:** Same as `/weather` endpoint.
- **Aggregation:** [`tools.py`](file:///Users/mithresh/wx-agent/lambdas/agent-handler/tools.py) aggregates the 40 three-hour forecast entries into 5 daily summaries with calculated daily minimums, maximums, and cumulative precipitation likelihoods.

### 4.2 US National Weather Service (NWS) Alerts API

- **Base URL:** `https://api.weather.gov/alerts/active`
- **Method:** `GET`
- **User-Agent Requirement:** Must specify a custom User-Agent header (`WeatherBuddy/1.0, contact@weatherbuddy.app`) to adhere to NWS API terms of service.
- **Geographic Filtering:** `point={latitude},{longitude}` or `area={stateCode}`.
