<p align="center">
  <img src="https://openweathermap.org/img/wn/02d@4x.png" width="120" alt="Weather Buddy Logo" />
</p>

<h1 align="center">🌦️ Weather Buddy</h1>

<p align="center">
  <strong>An enterprise-grade, voice-first, multilingual AI meteorological assistant powered by AWS Strands Agents, Groq Whisper, Amazon Polly, and Next.js 14.</strong>
</p>

<p align="center">
  <em>Speak in any language. Receive answers spoken natively in that same tongue — backed by real-time meteorological sensor feeds.</em>
</p>

<p align="center">
  <a href="https://aws.amazon.com/serverless/sam/"><img src="https://img.shields.io/badge/AWS%20SAM-Serverless-orange?style=flat-square&logo=amazon-aws" alt="AWS SAM" /></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python" alt="Python 3.12" /></a>
  <a href="https://nextjs.org"><img src="https://img.shields.io/badge/Next.js-14.2-black?style=flat-square&logo=next.js" alt="Next.js" /></a>
  <a href="https://groq.com"><img src="https://img.shields.io/badge/Inference-Groq%20Cloud-f55036?style=flat-square" alt="Groq" /></a>
  <a href="https://aws.amazon.com/polly/"><img src="https://img.shields.io/badge/Speech-Amazon%20Polly-purple?style=flat-square" alt="Amazon Polly" /></a>
  <a href="https://litellm.ai"><img src="https://img.shields.io/badge/LLM%20Router-LiteLLM-green?style=flat-square" alt="LiteLLM" /></a>
</p>

<p align="center">
  <a href="#-key-features">Key Features</a> •
  <a href="#-system-architecture">Architecture</a> •
  <a href="#-documentation-hub">Documentation Hub</a> •
  <a href="#-project-structure">Project Structure</a> •
  <a href="#-getting-started">Getting Started</a> •
  <a href="#-deployment-guide">Deployment</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

## 🎯 What Is Weather Buddy?

Weather Buddy is an open-source, voice-first **meteorological intelligence dashboard and conversational agent**. It allows users to ask complex weather and outdoor activity questions naturally—by speaking or typing—in **over 100 languages**.

Rather than acting as a generic conversational chatbot, Weather Buddy combines a strictly scoped **AWS Strands Agent reasoning loop** with real-time sensor observations from **OpenWeatherMap**, disaster hazard feeds from **GDACS**, and government meteorological alerts from the **US National Weather Service (NWS)**.

### Why It Stands Out
- **Zero Translation Bottlenecks:** Unlike traditional voice bots that convert speech to English, query an LLM in English, and translate the text back, Weather Buddy identifies user language at the speech ingestion layer. The AI agent evaluates tools and articulates answers **natively in the target tongue**.
- **Voice In, Voice Out:** Voice recordings captured via the browser's `MediaRecorder` API are transcribed in milliseconds via Groq Whisper Large v3, with responses synthesized into natural spoken audio via Amazon Polly neural voices.
- **Strict Scope Isolation:** The conversational agent is protected by behavioral prompt sandboxing. It cannot be coerced into generating off-topic content, writing code, or acting as a general-purpose assistant.
- **Dual Runtime Target:** Run 100% locally with zero cloud dependencies using Python and Ollama, or deploy to production as a high-scale serverless AWS SAM application.

---

## ✨ Key Features

### 🎙️ Low-Latency Voice Ingestion
- Integrated speech recognition powered by [Groq Whisper Cloud](https://console.groq.com/) (`whisper-large-v3`).
- Automatic language identification directly from audio waveforms (supports 100+ languages and dialects).
- Unified microphone toggle with real-time 60 FPS Fast Fourier Transform (FFT) visualizer bars.
- Seamless fallback to keyboard text input with instant suggestion chips.

### 🌍 Adaptive Multilingual Localization
- When you speak in French, Spanish, Hindi, German, Tamil, Japanese, or any supported language, the entire application adapts dynamically:
  - The **Strands Agent reasons and replies natively** in that language without translation intermediaries.
  - The **UI terminology updates instantly** ("Humidity" → "Humidité", "Wind" → "हवा") via reactive dictionaries.
  - Meteorological conditions translate directly from OpenWeatherMap weather stations (`&lang=fr`).
  - Forecast day names and hourly formats localize to target regional calendars.

### 🤖 Autonomous Strands Agent Reasoning
- Built on [AWS Strands Agents](https://github.com/strands-agents/strands-agents) with LiteLLM provider routing.
- The agent orchestrates **4 specialized meteorological tools**:
  | Tool Name | Scope & Function | Data Provider |
  |-----------|------------------|---------------|
  | `get_current_weather` | Real-time temperature, humidity, wind velocity, barometric pressure | OpenWeatherMap v2.5 |
  | `get_forecast` | 5-day daily forecast summaries, min/max temps, 3-hour precipitation probability | OpenWeatherMap v2.5 |
  | `get_alerts` | Active government hazard bulletins (thunderstorms, floods, cyclones) | US NWS & GDACS Global |
  | `activity_advisor` | Outdoor pursuit suitability scoring (running, cycling, hiking, water sports) | Custom Heuristic Engine |
- **Context-Aware Geolocation:** Automatically infers the active city if the user asks contextual questions like *"Will it rain tomorrow?"* without specifying the location.

### 🔊 Neural Speech Synthesis & Audio Visualizer
- Agent responses are converted to speech via **Amazon Polly** neural speaker voices.
- Dynamic language-to-voice mapping matching the exact dialect of the user.
- Base64 audio stream transport eliminating persistent file storage overhead.
- Interactive audio playback player with scrubber and animated waveform frequencies.

### 📊 Modern Glassmorphism Dashboard
- Glassmorphic translucent cards with layered ambient lighting effects.
- 24-hour horizontal hourly forecast strip with condition icons.
- 5-day daily forecast sidebar with tabular numeral alignment.
- Dismissable severe weather warning pill banner.
- Responsive design tailored for mobile touch targets ($\ge 44\text{px}$) and desktop viewports.

---

## 🏗️ System Architecture

Weather Buddy utilizes a decoupled microservices architecture partitioned across client, inference, and serverless execution boundaries:

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

### Tri-Lambda Execution Topology
1. **`agent-handler` (Core Brain):** Orchestrates `/query`, injects context, drives the Strands tool loop, and coordinates with TTS. Exposed via **Lambda Function URLs** to bypass API Gateway's 29-second hard execution limit.
2. **`tts-handler` (Voice Synthesis):** Dedicated Lambda invoked synchronously via `boto3` to synthesize speech using Amazon Polly neural voices.
3. **`alert-handler` (Proactive Notifications):** Triggered daily by an Amazon EventBridge cron rule (`cron(30 1 * * ? *)` = 7:00 AM IST) to scan for hazardous conditions and broadcast email bulletins via AWS SNS.

---

## 📚 Documentation Hub

We maintain an exhaustive engineering documentation suite in the [`docs/`](file:///docs/) directory:

| Document | Primary Focus | Key Topics |
|----------|---------------|------------|
| 📖 **[Documentation Portal](file:///docs/index.md)** | Master Sitemap | Quick start paths, reading guide, and directory index |
| 🏗️ **[System Architecture](file:///docs/architecture/system-design.md)** | Engineering Design | Microservice topology, reactive state machine, and SLA targets |
| 🔄 **[Sequence Flows](file:///docs/architecture/sequence-diagrams.md)** | Interaction Diagrams | Audio lifecycle, tool reasoning turns, and retry backoffs |
| ⚛️ **[Component Lifecycle](file:///docs/architecture/component-lifecycle.md)** | Frontend Engineering | Next.js hydration, Web Audio API context, and typewriter engine |
| 📡 **[REST API Reference](file:///docs/api-reference/rest-api.md)** | Integration Contracts | Endpoints, JSON schemas, TypeScript & Python SDKs, RFC 7807 |
| 📋 **[Data Models & Schemas](file:///docs/api-reference/data-models.md)** | Entity Dictionary | Schemas for observations, forecasts, alerts, and advisor |
| ⚡ **[Streaming & WebSockets](file:///docs/api-reference/websocket-and-streaming.md)** | Real-Time Protocol | Server-Sent Events (SSE) and token-by-token streaming |
| ☁️ **[AWS SAM Operations Guide](file:///docs/deployment/aws-sam-guide.md)** | Cloud Operations | Guided deployment, CloudFormation parameters, failover runbooks |
| 🚀 **[GitHub Actions CI/CD](file:///docs/deployment/cicd-github-actions.md)** | Automation Pipeline | Keyless AWS OIDC authentication, testing, and continuous deploy |
| 🦙 **[Self-Hosting Ollama on EC2](file:///docs/guides/local-ollama-ec2-setup.md)** | Private LLM Hosting | Provisioning script, systemd daemon, instance sizing, LiteLLM |
| 🏃 **[Activity Advisor Math](file:///docs/guides/activity-advisor-algorithms.md)** | Meteorological Models | Heat Index, Wind Chill, and sport suitability scoring equations |
| 🧪 **[Testing Handbook](file:///docs/guides/testing-handbook.md)** | Quality Assurance | Offline test methodology, Boto3/Polly mocks, and test execution |
| 📊 **[Performance Benchmarks](file:///docs/guides/performance-benchmarks.md)** | Latency & Sizing | Latency profiles, cold-start analysis, and Lambda memory tuning |
| 🩺 **[Troubleshooting & FAQ](file:///docs/guides/troubleshooting-and-faq.md)** | Diagnostic Manual | 20+ error recovery recipes, CloudWatch queries, and common FAQs |
| 🌍 **[Multilingual Matrix](file:///docs/i18n/multilingual-matrix.md)** | Internationalization | 100-language routing table, Polly voices, and SSML rules |
| 🔒 **[Threat Model & Security](file:///docs/security/threat-model-and-hardening.md)** | Security Hardening | STRIDE model, OWASP Top 10 for LLMs, and prompt sandboxing |
| 🏛️ **[ADR-0001: Tri-Lambda](file:///docs/adr/0001-tri-lambda-architecture.md)** | Architecture Decision | Decoupling monolithic Lambda into specialized microservices |
| 🏛️ **[ADR-0002: Function URLs](file:///docs/adr/0002-lambda-function-urls-vs-api-gateway.md)** | Architecture Decision | Adopting Lambda Function URLs to bypass 29s timeout cap |
| 🏛️ **[ADR-0003: LiteLLM Router](file:///docs/adr/0003-litellm-multi-provider-abstraction.md)** | Architecture Decision | Multi-provider portability across Groq and self-hosted Ollama |

---

## 📁 Project Structure

```
wx-agent/
├── Makefile                        # Master shortcuts for build, validate, deploy & test
├── run_local.py                    # Standalone local dev server (Groq/Ollama-powered)
├── template.yaml                   # AWS SAM multi-lambda CloudFormation definition
├── .env.example                    # Environment variable reference
├── CONTRIBUTING.md                 # Contributor guide, code standards & ADR process
│
├── docs/                           # Comprehensive technical documentation suite
│   ├── index.md                    # Master documentation portal
│   ├── architecture/               # Architecture, sequence flows & component lifecycle
│   ├── api-reference/              # REST specs, data models & streaming protocols
│   ├── deployment/                 # AWS SAM operations manual & GitHub Actions CI/CD
│   ├── guides/                     # Ollama EC2 setup, testing handbook & benchmarks
│   ├── i18n/                       # 100-language routing matrix & translation dictionaries
│   ├── security/                   # STRIDE threat model & OWASP Top 10 for LLMs
│   └── adr/                        # Architecture Decision Records
│
├── lambdas/
│   ├── agent-handler/              # Main conversational agent Lambda (POST /query)
│   │   ├── agent.py                # Strands Agent setup + model caching (LiteLLM)
│   │   ├── handler.py              # AWS Lambda entry point (invokes TTS & tools)
│   │   ├── prompts.py              # System prompt (scoped strictly to weather)
│   │   ├── tools.py                # Weather tools (OWM, NWS, GDACS, Activity Advisor)
│   │   ├── cli.py                  # CLI interface for offline terminal testing
│   │   └── requirements.txt
│   │
│   ├── tts-handler/                # Text-to-speech Lambda (internal invocation)
│   │   ├── handler.py              # Amazon Polly speech synthesis into base64 audio
│   │   ├── conftest.py             # Pytest fixtures and mock environments
│   │   └── tests/                  # Offline unit tests
│   │
│   └── alert-handler/              # Scheduled proactive weather monitoring
│       ├── handler.py              # Checks weather alerts & publishes to SNS topic
│       └── requirements.txt
│
└── frontend/
    ├── pages/
    │   ├── index.js                # Main weather dashboard page
    │   └── api/
    │       └── alerts.js           # GDACS proxy with 5-minute cache
    ├── components/
    │   ├── AppShell.js             # Root layout with ambient lighting effects
    │   ├── TopBar.js               # Search bar, geolocation trigger & language selector
    │   ├── WeatherCard.js          # Current conditions & temperature display
    │   ├── HourlyTimeline.js       # 24-hour horizontal forecast strip
    │   ├── ForecastList.js         # 5-day daily forecast sidebar
    │   ├── AlertBanner.js          # Weather alert pill banner (NWS / GDACS)
    │   ├── VoiceInput.js           # Mic recording & natural language chat bar
    │   ├── ChatHistory.js          # Interactive conversation history
    │   ├── ResponseBubble.js       # Typewriter reveal effect for assistant responses
    │   ├── AudioPlayer.js          # Polly TTS playback with animated visualizer
    │   ├── LanguageBadge.js        # Active detected language indicator
    │   ├── SuggestionChips.js      # Quick-start conversation prompt chips
    │   ├── SkeletonCard.js         # Glassmorphic loading placeholders
    │   └── ErrorToast.js           # Ephemeral error toast notifications
    ├── lib/
    │   ├── api.js                  # Backend + Open-Meteo API communication layer
    │   └── i18n.js                 # Multi-language dictionary and localized labels
    └── styles/
        └── globals.css             # Glassmorphism design system & animation tokens
```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.12+** with `pip`
- **Node.js 18+** with `npm`
- Free developer API credentials:
  - [OpenWeatherMap API Key](https://openweathermap.org/api) (v2.5 endpoints)
  - [Groq API Key](https://console.groq.com/) (for Llama 3 & Whisper inference)

### 1. Clone the Repository
```bash
git clone https://github.com/FLASH2332/wx-agent.git
cd wx-agent
```

### 2. Configure Environment Variables
Copy the template into a root `.env` file (refer to [`.env.example`](file:///.env.example)):
```bash
cp .env.example .env
```

Populate the configuration:
```env
# OpenWeatherMap API key (free tier - v2.5 endpoints)
OWM_API_KEY=your_openweathermap_key

# LiteLLM Configuration (select provider via model-id prefix)
# Hosted Groq:
LLM_MODEL_ID=groq/llama-3.1-8b-instant
LLM_BASE_URL=
LLM_API_KEY=your_groq_api_key

# AWS Region (defaults to us-east-1)
AWS_REGION=us-east-1
```

Configure `frontend/.env.local`:
```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:3001/query
```

### 3. Install Backend Runtime
```bash
python -m venv .venv
source .venv/bin/activate  # macOS / Linux
# or: .venv\Scripts\activate on Windows

pip install strands-agents strands-agents-tools python-dotenv litellm requests
```

### 4. Install Frontend Dependencies
```bash
cd frontend
npm install
cd ..
```

### 5. Launch the Local Development Server
```bash
python run_local.py
```
The server will start listening on `http://127.0.0.1:3001`.

### 6. Start the Frontend Dashboard
In a separate terminal:
```bash
cd frontend
npm run dev
```
Open **http://localhost:3000** in your browser.

---

## ☁️ Deployment Guide

### AWS SAM Multi-Lambda Production Stack

Use the top-level `Makefile` for standardized SAM operations:

```bash
# 1. Validate template syntax and lint
make validate        # runs: sam validate --lint

# 2. Build all three Lambdas using uv / makefile builders
make build           # runs: sam build

# 3. Interactive first-time deployment
make deploy-guided   # runs: sam deploy --guided

# 4. Subsequent deployments using saved samconfig.toml
make deploy          # runs: sam deploy
```

#### Deployment Parameter Reference
During `sam deploy --guided`, configure stack parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `OwmApiKey` | *(required)* | OpenWeatherMap v2.5 API key |
| `LlmModelId` | `groq/llama-3.1-8b-instant` | LiteLLM model identifier |
| `LlmApiKey` | *(required)* | Inference provider API key |
| `LlmBaseUrl` | `""` | Base URL for self-hosted LLMs (e.g. EC2 Ollama) |
| `AlertLocation` | `Chennai, IN` | City monitored by morning alert schedule |
| `AlertEmail` | `""` | Recipient email for SNS weather alerts |

#### Connecting Frontend: Function URLs vs API Gateway
SAM outputs two entry points:
- **`AgentFunctionUrl` (Recommended):** Direct Lambda Function URL with **no 29-second timeout ceiling**, preventing connection drops during complex reasoning.
- **`ApiUrl`:** Traditional API Gateway endpoint (enforces AWS 29-second hard cap).

Set `NEXT_PUBLIC_API_URL` in your frontend deployment:
```env
NEXT_PUBLIC_API_URL=https://<id>.lambda-url.us-east-1.on.aws
```

---

## 🧪 Testing & Validation

Weather Buddy enforces offline testability with mocked cloud dependencies:

```bash
# Run unit tests across all Lambda microservices
make test

# Or run pytest individually per lambda
cd lambdas/agent-handler && pytest -v
cd lambdas/tts-handler && pytest -v
cd lambdas/alert-handler && pytest -v
```

See the **[Testing Handbook](file:///docs/guides/testing-handbook.md)** for fixture patterns and mocking strategies.

---

## 🔒 Security & Guardrails

- **Strict Prompt Sandboxing:** The conversational agent is strictly scoped to weather and outdoor activity topics. Prompt injection attempts are politely declined in the user's native language.
- **Zero Secrets in Source:** All keys are injected via environment variables. `.env` and `.env.local` are gitignored.
- **Ephemeral Audio Processing:** Voice recordings and synthesized speech are handled in volatile container memory as Base64 strings. No audio files are persisted to disk or cloud storage.
- **Least Privilege IAM:** Execution roles restrict functions strictly to their required targets (`TtsFunction`, `AlertTopic`).

See the **[Threat Model & Security Specification](file:///docs/security/threat-model-and-hardening.md)** for STRIDE analysis and OWASP Top 10 defenses.

---

## 🤝 Contributing

Contributions are warmly welcomed! Please review our **[Contributor Guide (CONTRIBUTING.md)](file:///CONTRIBUTING.md)** for:
- Development workflows and local setup.
- Coding style standards (PEP 8 for Python, ESLint for JavaScript).
- Conventional Commit message formats.
- Architecture Decision Record (ADR) review procedures.

---

## 📜 License

This project was built for the **FirstCommit Hackathon**. Please check with the repository owners for licensing and usage terms.

<p align="center">
  Built with ❤️ using AWS Strands Agents, Groq, Amazon Polly, and Next.js
</p>