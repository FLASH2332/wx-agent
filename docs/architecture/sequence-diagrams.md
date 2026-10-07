# Weather Buddy — Technical Sequence Flows & Interaction Diagrams

This document details the exact runtime communication patterns, lifecycle events, and inter-service sequences within Weather Buddy.

---

## 1. End-to-End Voice Query Execution Sequence

The diagram below traces the end-to-end journey from a user pressing the microphone button in the browser to synthesized audio playback.

```
User          Frontend (React)         Groq Whisper          Agent Lambda           OWM API          TTS Lambda (Polly)
 │                   │                       │                    │                    │                 │
 ├─ Click Mic ──────►│                       │                    │                    │                 │
 │  (Speak query)    ├─ MediaRecorder.start()│                    │                    │                 │
 ├─ Stop Mic ───────►├─ MediaRecorder.stop() │                    │                    │                 │
 │                   │  (creates audio blob) │                    │                    │                 │
 │                   │                       │                    │                    │                 │
 │                   ├─ POST /transcribe ───►│                    │                    │                 │
 │                   │  (multipart webm)     │                    │                    │                 │
 │                   │                       ├─ Transcribe audio  │                    │                 │
 │                   │                       ├─ Detect ISO code   │                    │                 │
 │                   │◄─ {text, lang: "fr"} ─┴─ Return text+lang  │                    │                 │
 │                   │                                            │                    │                 │
 │                   ├─ Update Language Dropdown (fr)             │                    │                 │
 │                   ├─ Translate UI Labels (i18n.js)             │                    │                 │
 │                   │                                            │                    │                 │
 │                   ├─ POST /query {text, lang, contextLocation}►│                    │                 │
 │                   │                                            ├─ Assemble Prompt   │                 │
 │                   │                                            ├─ Inject Context    │                 │
 │                   │                                            │                    │                 │
 │                   │                                            ├─ Evaluate Tool ───►│                 │
 │                   │                                            │  (get_forecast)    │                 │
 │                   │                                            │                    ├─ Query OWM      │
 │                   │                                            │◄─ Forecast JSON ───┴─ Return Weather │
 │                   │                                            │                    │                 │
 │                   │                                            ├─ Format Answer     │                 │
 │                   │                                            ├─ Boto3 Invoke ──────────────────────►│
 │                   │                                            │  (Sync Request)    │                 ├─ Synthesize
 │                   │                                            │                    │                 ├─ Neural Voice
 │                   │                                            │◄─ {audio_b64} ───────────────────────┴─ Return MP3
 │                   │◄─ {response_text, audio_b64, weather_data}─┘                    │                 │
 │                   │                                                                 │                 │
 │                   ├─ Typewriter Reveal Response Text                                │                 │
 │                   ├─ Update Weather Cards & Timeline                                │                 │
 │                   ├─ Decode Base64 to AudioContext                                  │                 │
 │◄─ Spoken Audio ───┴─ AudioPlayer.play()                                             │                 │
```

---

## 2. Autonomous Agent Tool-Execution Loop

The Strands Agent manages an autonomous evaluation loop to retrieve accurate context without hallucination.

```
                     ┌──────────────────────────────┐
                     │   User Query + Dashboard City│
                     └──────────────┬───────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │    Context Assembler         │
                     │  (Prompt + System Rules)     │
                     └──────────────┬───────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │   LiteLLM Reasoning Turn     │
                     └──────────────┬───────────────┘
                                    │
                         Is Tool Call Required?
                                    │
                   ┌────────────────┴────────────────┐
                   ▼ YES                             ▼ NO
    ┌──────────────────────────────┐   ┌──────────────────────────────┐
    │  Execute Identified Tool     │   │   Final Answer Formatted     │
    │  • get_current_weather       │   │   in User's Language         │
    │  • get_forecast              │   └──────────────┬───────────────┘
    │  • get_alerts                │                  │
    │  • activity_advisor          │                  ▼
    └──────────────┬───────────────┘   ┌──────────────────────────────┐
                   │                   │   Trigger Speech Synthesis   │
                   ▼                   └──────────────────────────────┘
    ┌──────────────────────────────┐
    │ Observation Returned to LLM  │
    └──────────────┬───────────────┘
                   │
                   ▼
         Loop to LiteLLM Turn
```

---

## 3. Proactive EventBridge & SNS Notification Flow

Weather Buddy monitors hazardous weather conditions every morning via an automated serverless cron schedule.

```
Amazon EventBridge         Alert Lambda (Python 3.12)           OpenWeatherMap API           Amazon SNS Topic         User Email Inbox
        │                              │                                │                           │                        │
        ├─ Daily Schedule Trigger ────►│                                │                           │                        │
        │  cron(30 1 * * ? *)          ├─ Read ALERT_LOCATION env       │                           │                        │
        │  (01:30 UTC / 7:00 AM IST)   ├─ Query Weather Alerts ────────►│                           │                        │
        │                              │                                ├─ Check Severe Weather     │                        │
        │                              │◄─ Active Warnings / Alerts ────┴─ Return Alert Data        │                        │
        │                              │                                                            │                        │
        │                              ├─ Alerts Found?                                             │                        │
        │                              ├─── YES:                                                    │                        │
        │                              │    ├─ Format Warning Bulletin                              │                        │
        │                              │    ├─ sns.publish() ──────────────────────────────────────►│                        │
        │                              │    │                                                       ├─ Broadcast Message ───►│
        │                              │    │                                                       │  (HTML/Plain Email)    │
        │                              │    │                                                       │                        ├─ Alert Received!
        │                              │    │                                                       │                        │
        │                              └─── NO:                                                     │                        │
        │                                   └─ Log "Zero Active Alerts"                             │                        │
        │                                      (Skip SNS execution)                                 │                        │
```

---

## 4. Cold-Start Mitigation & Container Lifecycle

To keep serverless execution under 1.5 seconds, Weather Buddy leverages container warm-start caching:

```
[Cold Start Invocation]
  1. Lambda Runtime Initialization
  2. Module Imports (boto3, strands_agents, litellm)
  3. Pre-instantiate boto3 Lambda Client
  4. Cache LiteLLM Model Registry
  5. Execute handler.handler()
  6. Response returned to client
         │
         ▼
[Container Kept Warm]
         │
         ▼
[Warm Invocations (Subsequent Calls)]
  1. Skip Module Imports (0 ms)
  2. Reuse pre-instantiated boto3 client (0 ms)
  3. Reuse memory model registry (0 ms)
  4. Execute handler.handler() immediately (~200ms latency reduction)
```
