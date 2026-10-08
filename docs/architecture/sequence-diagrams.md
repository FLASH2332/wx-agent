# Weather Buddy — Complete Sequence & State Interaction Flows

This specification documents the runtime execution flows, inter-service protocol exchanges, asynchronous message transitions, and failure recovery sequences for Weather Buddy.

---

## 1. End-to-End Voice Ingestion & Speech Synthesis Flow

The diagram below details the entire request-response cycle from physical microphone button actuation in the browser to synthesized audio playback.

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

## 2. Autonomous Agent Tool Decision Loop

Weather Buddy's agent uses autonomous tool loops to retrieve sensor data before synthesizing output:

```
                          [User Meteorological Query]
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │   Prompt & Context Assembly   │
                       └───────────────┬───────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │   LiteLLM Inference Turn      │
                       └───────────────┬───────────────┘
                                       │
                            Tool Execution Required?
                                       │
                     ┌─────────────────┴─────────────────┐
                     ▼ YES                               ▼ NO
      ┌───────────────────────────────┐   ┌───────────────────────────────┐
      │   Execute Meteorological Tool │   │  Final Multilingual Response  │
      │   • get_current_weather       │   │  Formatted in User's Language │
      │   • get_forecast              │   └───────────────┬───────────────┘
      │   • get_alerts                │                   │
      │   • activity_advisor          │                   ▼
      └───────────────┬───────────────┘   ┌───────────────────────────────┐
                      │                   │  Boto3 Invoke TtsFunction     │
                      ▼                   └───────────────────────────────┘
      ┌───────────────────────────────┐
      │  Incorporate Tool Observation │
      └───────────────┬───────────────┘
                      │
                      ▼
            Loop to Next LLM Turn
```

---

## 3. Scheduled Daily Alert & SNS Notification Pipeline

The proactive notification pipeline executes without user interaction:

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

## 4. Upstream Rate-Limit & Network Resilience Sequences

```
Agent Lambda                           OpenWeatherMap API                   Exponential Backoff Queue
     │                                         │                                      │
     ├─ Query /weather?q=Seattle ─────────────►│                                      │
     │                                         │                                      │
     │◄─ HTTP 429 Too Many Requests ───────────┤                                      │
     │                                         │                                      │
     ├─ Trigger Jittered Retry ──────────────────────────────────────────────────────►│
     │                                                                                ├─ Wait 400ms + random(0, 150ms)
     │◄─ Wakeup Signal ───────────────────────────────────────────────────────────────┘
     │                                         │
     ├─ Retry Query /weather ─────────────────►│
     │                                         ├─ Evaluate Request
     │◄─ HTTP 200 OK (WeatherData JSON) ───────┴─ Return Sensor Metrics
```

---

## 5. Amazon Polly Multilingual Fallback Sequence

```
Agent Lambda                           TtsFunction (Polly Handler)                 Amazon Polly Service
     │                                              │                                       │
     ├─ Invoke {text: "...", lang: "ta"} ──────────►│                                       │
     │                                              ├─ Lookup Voice ID (Tamil)              │
     │                                              ├─ Is Neural Voice Available?           │
     │                                              ├─── NO: Fallback to Standard Voice     │
     │                                              │    (Valluvar / Standard Engine)       │
     │                                              │                                       │
     │                                              ├─ polly.synthesize_speech() ──────────►│
     │                                              │  (Engine: standard, VoiceId: Valluvar)│
     │                                              │◄─ AudioStream (MP3 Bytes) ────────────┘
     │                                              │
     │                                              ├─ Encode Bytes to Base64 String
     │◄─ Return {audio_b64: "SUQzBA..."} ───────────┘
```
