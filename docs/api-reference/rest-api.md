# Weather Buddy — Complete REST API & Integration Specification

This reference specification provides the definitive interface contract for Weather Buddy's public and internal endpoints, covering request headers, JSON schemas, client SDK code snippets, and error payloads conforming to RFC 7807 (Problem Details for HTTP APIs).

---

## 1. Global Specifications & Server Targets

Weather Buddy exposes endpoints across two primary hosting environments:

| Environment | Base URL | Auth Mechanism | Intended Consumer |
|-------------|----------|----------------|-------------------|
| **Local Development** | `http://127.0.0.1:3001` | None | Local React frontend / curl / Postman |
| **AWS Serverless Production** | `https://<id>.lambda-url.<region>.on.aws` | None (Lambda Function URL) | Production Next.js dashboard / mobile apps |
| **Next.js Internal API** | `https://<your-domain>/api` | None (Same-Origin) | Next.js client-side components |

### Standard HTTP Headers
```http
Content-Type: application/json
Accept: application/json
User-Agent: WeatherBuddy/1.0
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization, X-Requested-With
```

---

## 2. API Endpoints

### 2.1 Natural Language Meteorological Query: `POST /query`

The primary conversational interface. Coordinates Strands Agent reasoning, meteorological tool execution, and Polly neural speech synthesis.

#### Endpoint Signature
- **Method:** `POST`
- **Path:** `/query`
- **Content-Type:** `application/json`

#### Request Parameters
| Field | Type | Required | Description |
|-------|------|:--------:|-------------|
| `text` | `string` | **Yes** | The user's typed or spoken natural language question. |
| `lang` | `string` | No | ISO-639-1 code (e.g. `en`, `fr`, `es`, `hi`). Defaults to `en`. |
| `contextLocation` | `string` | No | City currently displayed on the dashboard for resolving context. Defaults to `London, GB`. |
| `messages` | `Array<Message>` | No | Conversational history array containing prior dialogue turns. |

#### Request Example
```json
{
  "text": "Will it rain in Tokyo tomorrow afternoon?",
  "lang": "en",
  "contextLocation": "Tokyo, JP",
  "messages": [
    {
      "role": "user",
      "content": "What is the temperature in Tokyo right now?"
    },
    {
      "role": "assistant",
      "content": "Currently in Tokyo it is 22°C and sunny."
    }
  ]
}
```

#### Successful Response (`200 OK`)
```json
{
  "response_text": "No rain is expected in Tokyo tomorrow afternoon. Skies will remain clear to partly cloudy with a high around 23°C and light southerly winds.",
  "audio_b64": "SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//uQZAAAAAAAAAAAAAAAA...",
  "weather_data": {
    "city": "Tokyo",
    "country": "JP",
    "temp": 22.4,
    "feels_like": 22.0,
    "condition": "Clear",
    "description": "clear sky",
    "humidity": 52,
    "wind_speed": 3.1,
    "icon": "01d"
  },
  "forecast_data": {
    "city": "Tokyo",
    "daily": [
      {
        "date": "2026-10-08",
        "temp_min": 16.0,
        "temp_max": 23.5,
        "condition": "Clear",
        "pop": 0.10
      }
    ]
  },
  "lang": "en"
}
```

#### Client Integration Snippets

##### TypeScript / JavaScript (`fetch`):
```typescript
interface QueryPayload {
  text: string;
  lang?: string;
  contextLocation?: string;
}

interface QueryResponse {
  response_text: string;
  audio_b64: string;
  weather_data: Record<string, any>;
  lang: string;
}

export async function askWeatherBuddy(payload: QueryPayload): Promise<QueryResponse> {
  const endpoint = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:3001/query';
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorBody = await response.json();
    throw new Error(`Weather Buddy error: ${errorBody.error || response.statusText}`);
  }

  return response.json();
}
```

##### Python (`httpx`):
```python
import httpx

def query_weather_buddy(text: str, lang: str = "en", context_city: str = "Seattle, US") -> dict:
    url = "https://your-lambda-url.on.aws/query"
    payload = {
        "text": text,
        "lang": lang,
        "contextLocation": context_city,
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return response.json()
```

---

### 2.2 Voice Audio Transcription: `POST /transcribe`

Accepts raw multipart audio streams and transcribes speech using Groq Cloud's hosted Whisper Large v3 model.

#### Endpoint Signature
- **Method:** `POST`
- **Path:** `/transcribe`
- **Content-Type:** `multipart/form-data`

#### Multipart Parameters
| Form Key | Type | Required | Description |
|----------|------|:--------:|-------------|
| `file` | `Binary Blob` | **Yes** | Recorded audio file (`audio/webm`, `audio/wav`, `audio/mp4`). |
| `prompt` | `string` | No | Optional vocabulary biasing hint (e.g. meteorological names). |

#### Successful Response (`200 OK`)
```json
{
  "text": "¿Cuál es la probabilidad de lluvia en Barcelona hoy?",
  "language": "es",
  "confidence": 0.988,
  "duration_seconds": 3.42
}
```

---

### 2.3 GDACS Disaster Proxy: `GET /api/alerts`

Proxies active emergency warnings from the Global Disaster Alert and Coordination System (GDACS).

#### Endpoint Signature
- **Method:** `GET`
- **Path:** `/api/alerts`
- **Cache Header:** `Cache-Control: s-maxage=300, stale-while-revalidate=60`

#### Query Parameters
| Parameter | Type | Required | Description |
|-----------|------|:--------:|-------------|
| `country` | `string` | No | ISO country code filter (`US`, `IN`, `FR`, `JP`). |
| `limit` | `integer` | No | Max alert items to return (default: `10`, max: `50`). |

#### Response Example
```json
{
  "status": "success",
  "total": 1,
  "alerts": [
    {
      "id": "GDACS-EQ-1002341",
      "title": "Earthquake Alert: Magnitude 5.8",
      "severity": "Orange",
      "country": "JP",
      "timestamp": "2026-10-07T06:12:00Z",
      "source": "GDACS Joint Research Centre"
    }
  ]
}
```

---

## 3. Standardized Error Handling (RFC 7807)

When an error occurs, Weather Buddy returns structured Problem Details:

```json
{
  "type": "https://weatherbuddy.app/errors/location-not-found",
  "title": "Geographic Location Not Found",
  "status": 404,
  "detail": "Could not geocode the requested locality 'Atlantis City'. Please specify a valid city and country.",
  "instance": "/query",
  "request_id": "req-9876543210"
}
```

### Error Code Catalog
| HTTP Status | Error Type Slug | Description |
|:-----------:|-----------------|-------------|
| `400` | `invalid-payload` | Request JSON body missing required fields or malformed. |
| `404` | `location-not-found` | City geocoding lookup returned 0 coordinate matches. |
| `413` | `payload-too-large` | Audio recording upload exceeded maximum size threshold (10 MB). |
| `429` | `rate-limit-exceeded` | Upstream meteorological or LLM inference quota exceeded. |
| `502` | `upstream-timeout` | OpenWeatherMap or Groq API took longer than timeout threshold. |
| `500` | `internal-agent-error` | Unhandled exception occurred within the Strands Agent loop. |
