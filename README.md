<p align="center">
  <img src="https://openweathermap.org/img/wn/02d@4x.png" width="120" alt="Weather Buddy" />
</p>

<h1 align="center">🌦️ Weather Buddy</h1>

<p align="center">
  <strong>A voice-first, multilingual AI weather assistant powered by AWS Strands Agents and Groq.</strong>
</p>

<p align="center">
  <em>Ask about the weather in any language. Get answers in that same language — spoken aloud.</em>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#tech-stack">Tech Stack</a> •
  <a href="#getting-started">Getting Started</a> •
  <a href="#project-structure">Project Structure</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#deployment">Deployment</a>
</p>

---

## 🎯 What Is Weather Buddy?

Weather Buddy is a **voice-first, AI-powered weather dashboard** that lets you ask about the weather using natural language — by speaking or typing — in **any language**. It combines a conversational AI agent with a rich, real-time weather dashboard that adapts its entire interface to the language you speak.

Built for the **FirstCommit Hackathon**, Weather Buddy demonstrates how modern AI agent frameworks (AWS Strands Agents), speech-to-text (Groq Whisper), and large language models can come together to create a seamless, multilingual user experience that goes far beyond a simple chatbot.

---

## ✨ Features

### 🎙️ Voice-First Interaction
- **Native speech recognition** powered by [Groq Whisper](https://console.groq.com/docs/speech-text) (`whisper-large-v3`).
- Speak in **any language** — Whisper automatically detects the language from your audio.
- The microphone button is integrated directly into the chat bar for a unified, modern UX.
- Text input is also fully supported for users who prefer typing.

### 🌍 Full Multilingual Support
- **Adaptive language detection:** When you speak in French, Hindi, Tamil, German, Spanish, or any other language, the entire application adapts:
  - The **AI agent responds in your language** natively (no translation layer — the LLM speaks it directly).
  - The **UI labels translate** ("Humidity" → "Humidité", "Wind" → "हवा") via an i18n system.
  - The **weather descriptions translate** natively via OpenWeatherMap's `lang` parameter ("scattered clouds" → "nuages épars").
  - The **forecast day names localize** ("Mon" → "lun." in French).
  - The **language dropdown updates** automatically, even adding new languages dynamically if you speak one that isn't in the default list.

### 🤖 AI-Powered Conversational Agent
- Built on [AWS Strands Agents](https://github.com/strands-agents/strands-agents) — a production-grade agentic AI framework.
- The agent has access to **4 specialized tools**:
  | Tool | Purpose |
  |------|---------|
  | `get_current_weather` | Current temperature, humidity, wind, conditions |
  | `get_forecast` | Multi-day daily forecast with highs, lows, and hourly timeline |
  | `get_alerts` | Government-issued weather alerts (NWS for US, GDACS globally) |
  | `activity_advisor` | Outdoor activity recommendations based on live weather data |
- **Context-aware:** The agent knows which city dashboard you're currently viewing. If you ask "Will it rain tomorrow?" without specifying a location, it infers from your dashboard context.
- **Strictly scoped:** The agent only answers weather-related questions. Off-topic requests are politely declined.

### 📊 Rich Weather Dashboard
- **Current conditions** with temperature, feels-like, humidity, wind speed, and weather icon.
- **Hourly timeline** showing the next 24 hours of forecast data in a horizontally scrollable strip.
- **5-day forecast** sidebar with daily highs/lows, precipitation probability, and conditions.
- **Real-time weather alerts** from the National Weather Service (US) and GDACS (global), displayed as dismissable banners.
- **Auto-geolocation:** On first load, the dashboard detects your browser's location and populates weather data automatically.
- **Manual city search** via a search bar in the top navigation.

### 🔊 Text-to-Speech
- Agent responses are synthesized to speech via **Amazon Polly** (in production) and played back through a built-in audio player with visualizer bars.
- The TTS language matches the detected user language for a seamless voice conversation.

### 🎨 Polished UI
- Glassmorphism design system with layered transparent shadows for depth.
- Concentric border radii across all nested components (outer = inner + padding).
- Staggered entrance animations with `cubic-bezier(0.2, 0, 0, 1)` easing.
- `scale(0.96)` press feedback on all interactive buttons.
- Tabular number formatting on all weather data so digits don't shift.
- Icon stroke weights matched to adjacent text weight (1.5px regular, 2px semibold).
- 44px minimum touch targets on all interactive elements.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                               FRONTEND                                  │
│                 Next.js 14 + Tailwind CSS + Lucide React                │
│                                                                         │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌─────────┐  │
│  │  TopBar   │  │ Weather  │  │  Forecast  │  │  Alert   │  │Language │  │
│  │ (Search)  │  │  Card    │  │   List     │  │  Pill    │  │  Badge  │  │
│  └──────────┘  └──────────┘  └────────────┘  └──────────┘  └─────────┘  │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │          VoiceInput (MediaRecorder Audio + Chat Input Bar)        │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                     │                                   │               │
│             POST /transcribe                    POST /query             │
└─────────────────────┼───────────────────────────────────┼───────────────┘
                      │                                   │
                      ▼                                   ▼
┌───────────────────────────────────┐   ┌─────────────────────────────────┐
│     TRANSCRIPTION & INFERENCE     │   │      AWS SERVERLESS BACKEND     │
│                                   │   │                                 │
│      Groq Whisper API             │   │   AgentFunction (Lambda)        │
│      (whisper-large-v3)           │   │   • Strands Agent tool loop     │
│      • Returns text + ISO lang    │   │   • LiteLLM (Groq / Ollama EC2) │
└───────────────────────────────────┘   │   • Lambda Function URL (no 29s)│
                                        └───┬─────────────┬───────────┬───┘
                                            │             │           │
                     ┌──────────────────────┘             │           └──────────┐
                     ▼                                    ▼                      ▼
        ┌─────────────────────────┐          ┌───────────────────────┐  ┌──────────────────┐
        │       AGENT TOOLS       │          │  TTS LAMBDA (Polly)   │  │ PROACTIVE ALERTS │
        │  • OWM API (Current/FC) │          │  • Amazon Polly       │  │ • EventBridge    │
        │  • NWS / GDACS (Alerts) │          │  • Multilingual voice │  │   cron (1:30 UTC)│
        │  • Activity Advisor     │          │  • Base64 audio b64   │  │ • AlertFunction  │
        │  • Strict weather scope │          │  • Internal invoke    │  │ • SNS Email topic│
        └─────────────────────────┘          └───────────────────────┘  └──────────────────┘
```

### Backend Modes & Execution Models

Weather Buddy provides two distinct operational environments:

| Mode | Entrypoint / Infrastructure | LLM Engine | Audio & Alerts |
|------|-----------------------------|------------|----------------|
| **Local Development** | `run_local.py` (HTTP on `http://127.0.0.1:3001`) | Groq API / local Ollama via LiteLLM | Local browser audio / console output |
| **AWS Serverless Production** | `template.yaml` (SAM Tri-Lambda Architecture) | LiteLLM routing to Groq or self-hosted Ollama on EC2 | Amazon Polly (`tts-handler`) + EventBridge/SNS (`alert-handler`) |

#### Tri-Lambda Architecture Overview
1. **`agent-handler` (Core Brain)**: Receives `/query`, retrieves weather context, drives Strands Agent tool executions, and coordinates with `tts-handler`. Exposed via both API Gateway and a direct Lambda Function URL (which avoids API Gateway's 29-second hard timeout for long LLM inference chains).
2. **`tts-handler` (Voice Synthesis)**: Dedicated Lambda invoked synchronously via boto3 from `agent-handler` to synthesize audio using Amazon Polly neural voices with automatic language detection matching.
3. **`alert-handler` (Proactive Notifications)**: Triggered daily by an Amazon EventBridge schedule rule (`cron(30 1 * * ? *)` = 7:00 AM IST) to evaluate current alerts for the configured alert location and broadcast warning bulletins through AWS SNS to subscribed emails.

---

## 🛠️ Tech Stack

### Frontend
| Technology | Purpose |
|------------|---------|
| **Next.js 14** | React framework with file-based routing |
| **Tailwind CSS 3** | Utility-first styling with custom design tokens |
| **Lucide React** | Consistent, stroke-matched icon library |
| **Open-Meteo API** | Client-side instant weather data (no key required) |

### Backend
| Technology | Purpose |
|------------|---------|
| **Python 3.12** | Backend runtime |
| **AWS Strands Agents** | Agentic AI framework with tool-use loop |
| **Groq API** | LLM inference (Llama 3.3 70B Versatile) and speech-to-text (Whisper Large v3) |
| **OpenWeatherMap API** | Server-side weather data with multilingual support |
| **Amazon Polly** | Text-to-speech synthesis (production) |

### Infrastructure
| Technology | Purpose |
|------------|---------|
| **AWS SAM** | Infrastructure-as-Code for serverless deployment |
| **AWS Lambda** | Serverless compute for agent and TTS |
| **AWS API Gateway** | HTTPS routing for `/query` and `/transcribe` |

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.12+** with `pip`
- **Node.js 18+** with `npm`
- A free **[OpenWeatherMap API key](https://openweathermap.org/api)** (v2.5 free tier)
- A free **[Groq API key](https://console.groq.com/)** (for Llama 3.3 + Whisper)

### 1. Clone the Repository

```bash
git clone https://github.com/FLASH2332/wx-agent.git
cd wx-agent
```

### 2. Configure Environment Variables

Create a `.env` file in the project root (refer to [`.env.example`](file:///.env.example)):

```env
# OpenWeatherMap API key (free tier — v2.5 current + forecast endpoints)
OWM_API_KEY=your_openweathermap_key

# LLM provider configuration via LiteLLM (select provider using prefix)
# Option A: Groq hosted inference (fastest)
LLM_MODEL_ID=groq/llama-3.1-8b-instant
LLM_BASE_URL=
LLM_API_KEY=your_groq_api_key

# Option B: Self-hosted Ollama on EC2 (OpenAI-compatible)
# LLM_MODEL_ID=openai/qwen2.5:3b-instruct
# LLM_BASE_URL=http://<ec2-ip>:11434/v1
# LLM_API_KEY=ollama

# AWS Region (defaults to us-east-1)
AWS_REGION=us-east-1
```

Create `frontend/.env.local`:

```env
# Local development:
NEXT_PUBLIC_API_URL=http://127.0.0.1:3001/query

# Production (Lambda Function URL output from SAM deploy):
# NEXT_PUBLIC_API_URL=https://<function-id>.lambda-url.us-east-1.on.aws
```

### 3. Install Backend Dependencies

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install strands-agents strands-agents-tools python-dotenv
```

### 4. Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### 5. Start the Backend

```bash
python run_local.py
```

You should see:
```
Starting direct Groq Python server on http://127.0.0.1:3001...
```

### 6. Start the Frontend

In a separate terminal:

```bash
cd frontend
npm run dev
```

Open **http://localhost:3000** in your browser.

### 7. Try It Out!

- 🎤 Click the microphone and say: *"What's the weather in Paris?"*
- ⌨️ Or type: *"Can I go hiking in Tokyo tomorrow?"*
- 🌍 Try speaking in another language — say *"Quel temps fait-il à Lyon?"* in French!

---

## 📁 Project Structure

```
wx-agent/
├── Makefile                        # Build, validate, deploy, and test shortcuts
├── run_local.py                    # Local dev server (Groq/Ollama-powered)
├── template.yaml                   # AWS SAM multi-lambda infrastructure definition
├── .env.example                    # Environment variable reference
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
│   │   ├── conftest.py             # Pytest fixtures and test environment
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

## 🔄 How It Works

### Voice Flow

```
User speaks → MediaRecorder captures audio
    → POST /transcribe (Groq Whisper)
    → Returns { text, language }
    → Frontend updates language dropdown
    → POST /query with { text, lang, contextLocation }
    → Strands Agent calls weather tools (with lang param)
    → Agent responds in detected language
    → Response displayed + spoken via TTS
```

### Language Propagation

The detected language flows through every layer:

| Layer | How Language Is Used |
|-------|---------------------|
| **Whisper** | Detects language from audio, returns ISO-639-1 code |
| **Frontend** | Updates `selectedLang` state → propagates to all components |
| **i18n.js** | Translates static UI labels (Humidity, Wind, etc.) |
| **Agent Prompt** | `IMPORTANT INSTRUCTION: You must ALWAYS respond in '{lang}'` |
| **OWM API** | `&lang=fr` returns localized weather descriptions |
| **Forecast dates** | `toLocaleDateString(lang)` renders localized day names |

### Context Awareness

When you view the dashboard for "Seattle", the agent automatically knows:

> *"Context: The user is currently viewing the dashboard for Seattle, US. If they ask a question without specifying a location, assume they mean Seattle, US."*

This is injected into the system prompt dynamically, so you can ask *"Will it rain tomorrow?"* without repeating the city name.

---

## ☁️ Deployment

### AWS SAM Multi-Lambda Architecture

The repository includes a top-level `Makefile` providing standardized shortcuts for building, linting, and deploying the AWS SAM stack:

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

#### Key Deployment Parameters
During `sam deploy --guided`, configure the following stack parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `OwmApiKey` | *(required)* | OpenWeatherMap v2.5 API key |
| `LlmModelId` | `groq/llama-3.1-8b-instant` | LiteLLM model identifier (e.g., `openai/qwen2.5:7b-instruct` or `groq/llama-3.1-8b-instant`) |
| `LlmApiKey` | *(required)* | API key for LLM provider (`ollama` for self-hosted instances) |
| `LlmBaseUrl` | `""` | Base URL for self-hosted OpenAI-compatible LLMs (e.g., `http://<ec2-ip>:11434/v1`) |
| `AlertLocation` | `Chennai, IN` | Geographic location monitored by the daily morning alert schedule |
| `AlertEmail` | `""` | Email address to receive proactive SNS weather warning alerts |

#### Connecting the Frontend: Lambda Function URL vs. API Gateway
SAM provisions two endpoints for the agent backend:
- **`AgentFunctionUrl` (Recommended)**: Direct Lambda Function URL with **no 29-second timeout limit**, ensuring slow self-hosted model generation or multi-step tool calls complete reliably without connection drops.
- **`ApiUrl`**: Standard API Gateway REST endpoint (enforces an AWS hard limit of 29 seconds).

Copy the output `AgentFunctionUrl` and configure your frontend:

```env
NEXT_PUBLIC_API_URL=https://<id>.lambda-url.us-east-1.on.aws
```

### Frontend Deployment (Vercel)

```bash
cd frontend
npx vercel
```

In the Vercel project dashboard, set `NEXT_PUBLIC_API_URL` to your deployed Lambda Function URL.

---

## 🧪 Testing & Validation

Run unit tests offline across both Lambda services:

```bash
# Run pytest test suites across agent-handler and tts-handler
make test
```

Or execute directly inside each lambda directory:
```bash
cd lambdas/agent-handler && pytest -q
cd lambdas/tts-handler && pytest -q
```

---

## 🔒 Security

- **Scoped agent:** The system prompt strictly limits the agent to weather-only conversations. Prompt injection attempts are treated as out-of-scope requests and declined.
- **No secrets in code:** All API keys are loaded from environment variables. `.env` and `.env.local` are gitignored.
- **CORS configured:** Both local and production backends set appropriate CORS headers.
- **Custom User-Agent:** All outbound HTTP requests use `WeatherBuddy/1.0` to avoid bot-blocking by external APIs.

---

## 📜 License

This project was built for the **FirstCommit Hackathon**. Please check with the repository owner for licensing details.

---

<p align="center">
  Built with ❤️ using AWS Strands Agents, Groq, and Next.js
</p>