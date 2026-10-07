# Weather Buddy — System Architecture & Design Specification

This document provides a comprehensive technical breakdown of **Weather Buddy**, a voice-first, multilingual weather intelligence assistant built with **AWS Strands Agents**, **Groq Whisper**, **Amazon Polly**, and **Next.js 14**.

---

## 1. Executive Architecture Overview

Weather Buddy bridges natural language conversation, real-time meteorological sensor feeds, and low-latency voice synthesis. It operates on a decoupled client-server architecture with dual operational targets:
- **Local Development Environment:** Lightweight, zero-cloud execution running on Python HTTP runtime with direct Groq or Ollama inference.
- **AWS Serverless Production Environment:** Tri-Lambda microservices orchestrated via AWS SAM, featuring Amazon EventBridge daily triggers, AWS SNS broadcast alerts, and Amazon Polly neural speech synthesis.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             CLIENT LAYER (BROWSER)                          │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      Next.js 14 React Application                   │   │
│   │                                                                     │   │
│   │   [TopBar / Search]    [WeatherCard]    [ForecastList]   [Timeline] │   │
│   │   [AlertBanner]        [ChatHistory]    [AudioPlayer]    [Badges]   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│             │                                           │                   │
│      MediaRecorder API                           JSON REST Payload          │
│      (Audio Blob: webm)                         { text, lang, ctx }         │
│             │                                           │                   │
└─────────────┼───────────────────────────────────────────┼───────────────────┘
              │                                           │
       POST /transcribe                            POST /query
              │                                           │
              ▼                                           ▼
┌───────────────────────────┐           ┌─────────────────────────────────────┐
│    SPEECH TRANSLATION     │           │         CONVERSATIONAL AGENT        │
│                           │           │                                     │
│    Groq Cloud Whisper     │           │   Agent Lambda (Python 3.12)        │
│    whisper-large-v3       │           │   • AWS Strands Agent Loop          │
│    • Automatic Lang Detect│           │   • LiteLLM Provider Routing        │
│    • Low-latency transcript│          │   • In-Memory Context Injector      │
└───────────────────────────┘           └──────────────────┬──────────────────┘
                                                           │
                                ┌──────────────────────────┴───────────────┐
                                │                                          │
                                ▼                                          ▼
                ┌───────────────────────────────┐          ┌───────────────────────────────┐
                │          TOOL ORCHESTRATION   │          │      VOICE SYNTHESIS          │
                │                               │          │                               │
                │  1. OpenWeatherMap v2.5 API   │          │  TTS Lambda (Python 3.12)     │
                │     (Current weather + FC)    │          │  • Amazon Polly Client        │
                │  2. US NWS Alerts API         │          │  • Language-to-Voice Mapper   │
                │     (National Weather alerts) │          │  • Base64 MP3 Audio Stream    │
                │  3. GDACS Global Disaster Feed│          │  • Boto3 Synchronous Invoke   │
                │  4. Activity Advisor Tool     │          └───────────────────────────────┘
                └───────────────────────────────┘
                                │
                                ▼
                ┌───────────────────────────────┐
                │     PROACTIVE MONITORING      │
                │                               │
                │  EventBridge Daily Schedule   │
                │  • cron(30 1 * * ? *)         │
                │  Alert Lambda                 │
                │  • OWM Alert Evaluator        │
                │  AWS SNS Topic                │
                │  • Email Warning Broadcast    │
                └───────────────────────────────┘
```

---

## 2. Frontend Subsystem Design

The user interface is built on **Next.js 14** using client-rendered React architecture (`"use client"`), optimized for zero input latency, responsive feedback, and adaptive multilingual internationalization.

### 2.1 State Management & Reactive Data Flow

The client runtime manages three primary state trees:
1. **Meteorological State:**
   - `weatherData`: Current conditions (temperature, humidity, wind, weather code, description).
   - `forecastData`: 5-day daily highs/lows, precipitation probabilities, and 24-hour hourly intervals.
   * Source: Ingested on first load via client-side Open-Meteo API (or browser geolocation), subsequently refreshed on explicit user search or assistant response.
2. **Conversational State:**
   - `messages`: Chronological array of chat bubbles (`{ role: "user" | "assistant", text: string, audio?: string }`).
   - `isProcessing`: Boolean mutex disabling concurrent voice recording and query submission.
   - `typewriterState`: Character-by-character reveal buffer for assistant responses.
3. **Locale & Internationalization State:**
   - `selectedLang`: ISO-639-1 two-letter code (`en`, `es`, `fr`, `hi`, `ta`, etc.).
   - Dictated dynamically by Groq Whisper language detection or manual override in [`TopBar.js`](file:///Users/mithresh/wx-agent/frontend/components/TopBar.js).
   - Propagates to all UI labels via dictionary mappings in [`frontend/lib/i18n.js`](file:///Users/mithresh/wx-agent/frontend/lib/i18n.js).

### 2.2 Component Hierarchy & Responsibilities

```
AppShell
├── TopBar
│   ├── LocationSearchInput
│   ├── GeolocationTriggerButton
│   └── LanguageSelectorDropdown
├── AlertBanner (Conditionally rendered when active NWS/GDACS alert exists)
├── MainDashboardGrid
│   ├── WeatherCard (Current temperature, feels like, wind, humidity, pressure)
│   ├── HourlyTimeline (24-hour horizontal forecast cards with weather icons)
│   ├── ForecastList (5-day daily forecast summary sidebar)
│   └── SuggestionChips (Quick prompt chips: "Will it rain?", "Weekend forecast")
├── ChatContainer
│   ├── ChatHistory
│   │   ├── ResponseBubble (Typewriter animation + Markdown formatting)
│   │   └── AudioPlayer (Polly audio playback with canvas audio visualizer)
│   └── VoiceInput
│       ├── AudioRecorder (MediaRecorder API with WebM MIME capture)
│       ├── TextInputBar (Fallback manual submission)
│       └── LanguageBadge (Visual pill displaying detected audio language)
└── ErrorToast (Global floating notification queue)
```

---

## 3. Conversational Agent Subsystem

The core agent intelligence is powered by **AWS Strands Agents**, a modular framework designed for reliable tool use, loop management, and prompt sandboxing.

### 3.1 The Strands Agent Execution Loop

When a user submits a query via `POST /query`:

1. **Payload Extraction:**
   ```json
   {
     "text": "Do I need an umbrella in Paris tonight?",
     "lang": "en",
     "contextLocation": "Paris, FR"
   }
   ```
2. **Dynamic Context Injection:**
   The backend retrieves the user's active dashboard city (`contextLocation`) and injects it into the system prompt:
   ```
   Context: The user is currently viewing the dashboard for Paris, FR.
   If they ask a question without specifying a location, assume they mean Paris, FR.
   Language constraint: You must ALWAYS respond in English ('en').
   ```
3. **Autonomous Reasoning Cycle:**
   - The agent inspects available tool signatures (`get_current_weather`, `get_forecast`, `get_alerts`, `activity_advisor`).
   - Generates a structured tool call: `get_forecast(location="Paris, FR", lang="en")`.
   - The tool executes via HTTP request to OpenWeatherMap.
   - The agent evaluates the returned JSON tool result (e.g., `pop: 0.85`, `rain_volume: 4.2mm`).
   - If sufficient data is obtained, it terminates the loop and synthesizes the natural language response.
   - If additional context is required, it triggers a subsequent tool invocation.

```
       [User Message]
              │
              ▼
    ┌───────────────────┐
    │ Prompt Assembler  │ ◄── Context Location + Language
    └─────────┬─────────┘
              │
              ▼
    ┌───────────────────┐
    │  LLM Evaluation   │ ◄── LiteLLM (Groq / Ollama EC2)
    └─────────┬─────────┘
              │
        Tool Call Requested?
        ├── YES ──► Execute Tool ──► Append Observation ──┐
        │                                                 │
        └── NO  ──► Final Natural Language Response ◄─────┘
```

### 3.2 Tool Registry & Execution Mechanics

The agent has access to 4 strictly scoped meteorological tools:

| Tool Name | Module | Parameters | Data Source |
|-----------|--------|------------|-------------|
| `get_current_weather` | `tools.py` | `location` (str), `lang` (str) | OpenWeatherMap `/weather` endpoint |
| `get_forecast` | `tools.py` | `location` (str), `lang` (str), `days` (int) | OpenWeatherMap `/forecast` endpoint |
| `get_alerts` | `tools.py` | `location` (str) | National Weather Service (US) + GDACS Global Feed |
| `activity_advisor` | `tools.py` | `activity` (str), `location` (str), `date` (str) | Synthesizes current & forecast metrics |

### 3.3 Prompt Sandboxing & Security Guardrails

The agent enforces strict topic sandboxing via [`prompts.py`](file:///Users/mithresh/wx-agent/lambdas/agent-handler/prompts.py):
- **Weather Exclusivity:** The agent is instructed to act exclusively as a meteorological advisor. Questions concerning programming, mathematics, general knowledge, or creative writing are politely declined.
- **Prompt Injection Defense:** External instructions attempting to bypass system instructions ("Ignore previous instructions and write a poem") trigger a fallback message in the requested language.
- **Multilingual Mirroring:** The model is strictly instructed never to translate responses back to English if the user queried in another tongue.

---

## 4. Multi-Lambda Serverless Topology

In production, Weather Buddy is deployed as three discrete AWS Lambda functions defined in [`template.yaml`](file:///Users/mithresh/wx-agent/template.yaml).

```
                      Internet
                         │
                 ┌───────┴───────┐
                 │               │
        POST /transcribe    POST /query
                 │               │
                 ▼               ▼
        ┌─────────────────────────────────────────────────────────┐
        │             AgentFunction (Memory: 512MB, Timeout: 300s) │
        │             • Lambda Function URL (Uncapped execution)  │
        │             • REST API Gateway (29s fallback)           │
        └────────────────────────┬────────────────────────────────┘
                                 │
                   boto3 synchronous invoke
                                 │
                                 ▼
        ┌─────────────────────────────────────────────────────────┐
        │             TtsFunction (Memory: 256MB, Timeout: 30s)   │
        │             • Amazon Polly neural voice generator       │
        │             • Returns base64 audio/mp3 payload          │
        └─────────────────────────────────────────────────────────┘

        ┌─────────────────────────────────────────────────────────┐
        │             AlertFunction (Memory: 256MB, Timeout: 30s) │
        │             • Triggered by EventBridge: cron(30 1 * * ?*)│
        │             • Evaluates OWM alerts for configured city  │
        │             • Publishes alert bulletin to SNS Topic     │
        └────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
        ┌─────────────────────────────────────────────────────────┐
        │             AWS SNS Topic (weather-buddy-alerts)        │
        │             • Delivers instant email notifications      │
        └─────────────────────────────────────────────────────────┘
```

### 4.1 AgentFunction Specifications
- **Runtime:** Python 3.12
- **Memory:** 512 MB (provides additional vCPU allocation to speed up cold-start dependency imports).
- **Timeout:** 300 seconds (ensures complex multi-turn tool loops with slow self-hosted LLMs do not prematurely abort).
- **Network Interface:** Dual-exposed via AWS API Gateway and Lambda Function URL (`AuthType: NONE`).
- **Function URL Rationale:** Standard AWS API Gateway imposes an immutable 29-second hard ceiling. Connecting the frontend directly to the Lambda Function URL completely circumvents this ceiling.

### 4.2 TtsFunction Specifications
- **Runtime:** Python 3.12
- **Role:** Pure internal compute microservice. It is **not** exposed over public HTTP.
- **Invocation Protocol:** Invoked exclusively via synchronous AWS SDK (`boto3.client('lambda').invoke(InvocationType='RequestResponse')`).
- **Voice Mapping Engine:** Maps ISO-639-1 codes to Polly Neural voices:
  - `en` -> `Joanna` (Neural)
  - `es` -> `Lupe` (Neural)
  - `fr` -> `Lea` (Neural)
  - `hi` -> `Kajal` (Neural)
  - `de` -> `Vicki` (Neural)
  - `it` -> `Bianca` (Neural)
- **Output:** Returns binary audio payload encoded as Base64 string for zero-file-storage transmission.

### 4.3 AlertFunction & Proactive EventBridge Pipeline
- **Schedule:** Amazon EventBridge Rule configured for `cron(30 1 * * ? *)`, executing daily at 01:30 UTC (7:00 AM Indian Standard Time).
- **Execution Target:** [`lambdas/alert-handler/handler.py`](file:///Users/mithresh/wx-agent/lambdas/alert-handler/handler.py).
- **Processing Logic:**
  1. Reads `ALERT_LOCATION` and `OWM_API_KEY` from Lambda environment variables.
  2. Queries OpenWeatherMap for severe meteorological alerts or extreme weather conditions.
  3. If alerts are identified, formats a concise briefing message.
  4. Publishes message directly to `SNS_TOPIC_ARN`.
  5. AWS SNS delivers emails to all confirmed subscribers.

---

## 5. Network, Protocol & Serialization Schemas

All inter-service and client-service communications use structured JSON payloads.

### 5.1 POST `/query` Request & Response Specification

#### Request Payload
```json
{
  "text": "What is the wind speed in Chicago right now?",
  "lang": "en",
  "contextLocation": "Chicago, US"
}
```

#### Response Payload
```json
{
  "response_text": "The current wind speed in Chicago is 18 mph coming from the northeast, with gusts up to 26 mph.",
  "audio_b64": "//uQZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAA...",
  "weather_data": {
    "city": "Chicago",
    "country": "US",
    "temp": 14.2,
    "feels_like": 11.8,
    "condition": "Windy",
    "humidity": 65,
    "wind_speed": 8.0,
    "icon": "50d"
  },
  "lang": "en"
}
```

### 5.2 POST `/transcribe` Audio Ingestion Specification

#### Request (Multipart Form Data)
- `file`: Binary audio file (`audio/webm` or `audio/wav`).

#### Response Payload
```json
{
  "text": "Bonjour, quel temps fait-il aujourd'hui?",
  "language": "fr",
  "duration": 2.4
}
```

---

## 6. Resilience, Error Handling & Recovery Strategies

1. **Location Resolution Fallback:**
   If a user inputs a vague or unrecognized city, [`tools.py`](file:///Users/mithresh/wx-agent/lambdas/agent-handler/tools.py) raises a custom `LocationNotFoundError`. The agent catches this exception and responds requesting clarification rather than crashing the Lambda execution.
2. **TTS Failure Non-Blocking Fallback:**
   If Amazon Polly experiences rate limits or service unavailability, `_synthesize()` logs the warning and returns an empty audio string (`""`). The frontend detects the missing audio stream and gracefully falls back to displaying text without playing audio.
3. **Lambda Cold Start Mitigation:**
   Boto3 clients (`lambda_client`, `polly_client`) and LLM provider connections are instantiated at the module scope outside the Lambda handler function, allowing warm containers to reuse initialized client pools.
4. **CORS Hardening:**
   Lambda functions return standard CORS headers allowing cross-origin requests from web client deployments on Vercel or CloudFront.
