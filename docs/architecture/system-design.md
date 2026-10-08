# Weather Buddy — Technical System Design & Architectural Specification

This technical specification details the architectural tenets, runtime execution topology, state machines, and microservice interfaces of **Weather Buddy**, an enterprise-grade, multilingual, voice-first meteorological intelligence platform built with **AWS Strands Agents**, **Groq Whisper**, **Amazon Polly**, and **Next.js 14**.

---

## 1. Architectural Tenets & Design Principles

Weather Buddy is built upon four non-negotiable architectural tenets:

1. **Sub-Second Perceived Latency:** Voice queries must deliver sensory feedback within 300ms (audio visualizer reaction and optimistic transcription updates), with complete natural language and speech responses streaming back under 1.8 seconds.
2. **Native Multilingual Fidelity:** The system avoids error-prone two-step machine translation (User Language → English → LLM → English → User Language). Instead, language detection occurs at the speech ingestion layer, and the LLM reasons, calls tools, and articulates responses natively in the target tongue.
3. **Strict Meteorological Scope Isolation:** The conversational agent is strictly sandboxed. It cannot be coerced into generating off-topic text, executing unauthorized system routines, or acting as an arbitrary chatbot.
4. **Resilient Dual-Target Deployment:** The application maintains 100% feature parity between a zero-cloud local developer runtime (`run_local.py` + Groq/Ollama) and a serverless AWS production topology (`template.yaml` + SAM).

---

## 2. End-to-End System Topology

Weather Buddy employs a decoupled microservices topology partitioned across client, transcription, reasoning, and speech synthesis boundaries:

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

## 3. Client-Side Reactive State Machine

The client application runs a deterministic finite state machine (FSM) governing user interaction and media capture states:

```
                  ┌──────────────┐
                  │     IDLE     │◄─────────────────────────────┐
                  └──────┬───────┘                              │
                         │                                      │
            User Clicks Microphone Button                       │
                         │                                      │
                         ▼                                      │
                  ┌──────────────┐                              │
                  │  RECORDING   │                              │
                  │ (MediaStream)│                              │
                  └──────┬───────┘                              │
                         │                                      │
             User Releases / Stops Recording                    │
                         │                                      │
                         ▼                                      │
                  ┌──────────────┐                              │
                  │ TRANSCRIBING │                              │
                  │(/transcribe) │                              │
                  └──────┬───────┘                              │
                         │                                      │
            Transcription Received with ISO Code                │
                         │                                      │
                         ▼                                      │
                  ┌──────────────┐                              │
                  │   QUERYING   │                              │
                  │   (/query)   │                              │
                  └──────┬───────┘                              │
                         │                                      │
           Response Received with Text & Audio Payload          │
                         │                                      │
                         ▼                                      │
                  ┌──────────────┐                              │
                  │  PLAYBACK &  │                              │
                  │  TYPEWRITER  │──────────────────────────────┘
                  └──────────────┘
```

### State Definitions
- **`IDLE`**: Default resting state. UI listens for text input, quick prompt chip clicks, or microphone triggers.
- **`RECORDING`**: Audio input stream bound to Web Audio context. Canvas visualizer updates at 60 FPS reflecting microphone decibel amplitude.
- **`TRANSCRIBING`**: MediaRecorder blob dispatched to Groq Whisper Large v3. UI renders pulsing transcription indicator.
- **`QUERYING`**: Strands agent reasoning turn active. Meteorological tool invocations executing concurrently.
- **`PLAYBACK & TYPEWRITER`**: Synthesized Polly MP3 decoded into browser audio context; typewriter animation reveals text token-by-token.

---

## 4. Strands Agent Autonomous Reasoning Loop

Weather Buddy utilizes **AWS Strands Agents**, a lightweight, production-hardened agentic framework that formalizes tool invocation loops with deterministic termination conditions.

### 4.1 Turn Lifecycle & Context Mechanics

1. **System Prompt Injection:**
   ```python
   def build_system_prompt(context_location: str, target_lang: str) -> str:
       return f"""
       You are Weather Buddy, an expert meteorological AI assistant.
       Current user context: Viewing weather dashboard for {context_location}.
       Language constraint: You must ALWAYS articulate responses in '{target_lang}'.
       Scope restriction: Answer ONLY meteorological and outdoor activity inquiries.
       """
   ```

2. **Autonomous Tool Routing:**
   LiteLLM converts model reasoning into typed tool signatures:
   - `get_current_weather(location: str, lang: str)`
   - `get_forecast(location: str, lang: str, days: int)`
   - `get_alerts(location: str)`
   - `activity_advisor(activity: str, location: str, date: str)`

3. **Tool Execution & Observation Incorporation:**
   Tools execute synchronously within the Lambda execution container. Returned JSON payloads are injected into the conversation memory as `tool` role turns before triggering the subsequent model evaluation turn.

4. **Loop Termination:**
   When the agent produces a final natural language utterance without requesting additional tool executions, the loop terminates and hands off the text buffer to speech synthesis.

---

## 5. Multi-Lambda Serverless Topology

The production architecture is deployed across three specialized AWS Lambda functions defined in [`template.yaml`](file:///Users/mithresh/wx-agent/template.yaml).

### 5.1 Service Matrix

| Function Logical Name | Memory | Max Timeout | Primary Entrypoint | Invocation Source | Scaling Behavior |
|-----------------------|:------:|:-----------:|-------------------|-------------------|------------------|
| `AgentFunction` | 512 MB | 300 s | `lambdas/agent-handler/handler.py` | Function URL / API GW | Concurrent on-demand |
| `TtsFunction` | 256 MB | 30 s | `lambdas/tts-handler/handler.py` | AWS SDK (`boto3`) | Internal synchronous |
| `AlertFunction` | 256 MB | 30 s | `lambdas/alert-handler/handler.py` | Amazon EventBridge | Scheduled cron rule |

### 5.2 Lambda Function URL vs. API Gateway Analysis

API Gateway enforces a strict, unconfigurable **29-second execution ceiling**. While sufficient for standard database lookups, multi-turn LLM reasoning chains on complex weather queries (or when using self-hosted CPU-based models on EC2) can occasionally require 30 to 45 seconds.

To eliminate premature connection aborts:
- Weather Buddy implements **AWS Lambda Function URLs** configured with `AuthType: NONE` and CORS support.
- This gives the frontend an uncapped 300-second execution headroom while reducing per-request latency by bypassing API Gateway layer translation.

---

## 6. Proactive EventBridge & SNS Pipeline

Weather Buddy does not rely solely on user-initiated pull queries; it implements an autonomous proactive push pipeline:

```
[EventBridge Rule: cron(30 1 * * ? *)] (01:30 UTC / 7:00 AM IST)
                 │
                 ▼
         [AlertFunction] 
                 │ (Fetches OpenWeatherMap alerts for ALERT_LOCATION)
                 ▼
          Active Alerts?
          ├── NO  ──► Exit silently (0 SNS publishes)
          └── YES ──► Format severe weather bulletin
                             │
                             ▼
                    [AWS SNS Topic: weather-buddy-alerts]
                             │
                             ▼
                   [Email Subscribers] (Instant Delivery)
```

### Pipeline Guarantees
- **Idempotency:** The schedule fires once daily at morning briefing time.
- **Cost Isolation:** If no active meteorological alerts or warnings exist for the target location, zero outbound messages are dispatched, maintaining zero SNS operational cost.

---

## 7. Observability, Telemetry & CloudWatch Alarms

Weather Buddy configures structured JSON logging across all three microservices.

### 7.1 Key Metric Definitions
- **`AgentExecutionLatency`:** P50, P90, and P99 response duration. Target: P90 < 2500ms.
- **`ToolExecutionDuration`:** Latency of outbound HTTP calls to OpenWeatherMap and NWS. Target: < 400ms.
- **`PollySynthesisLatency`:** Duration of speech synthesis round trip. Target: < 600ms.
- **`ColdStartLatency`:** Container initialization duration. Mitigated by module-level client caching.

### 7.2 Structured Audit Log Format
```json
{
  "timestamp": "2026-10-07T13:00:15.120Z",
  "request_id": "9a1b2c3d-4e5f-6789-0abc-def123456789",
  "level": "INFO",
  "service": "agent-handler",
  "language": "es",
  "location": "Madrid, ES",
  "tools_invoked": ["get_current_weather"],
  "llm_model": "groq/llama-3.1-8b-instant",
  "duration_ms": 1420,
  "tts_synthesized": true
}
```
