# Weather Buddy — Technical Documentation Portal & Knowledge Base 📚

Welcome to the **Weather Buddy** engineering documentation portal. This repository serves as the definitive technical reference for developers, DevOps engineers, and contributors building upon our voice-first, multilingual meteorological intelligence platform.

---

## 🗺️ Documentation Sitemap & Quick Directory

```
docs/
├── index.md                         # Master documentation portal (You are here)
│
├── architecture/
│   ├── system-design.md             # End-to-end system topology & state machines
│   ├── sequence-diagrams.md         # Runtime interaction flows & retry loops
│   └── component-lifecycle.md       # React client lifecycle & Web Audio FFT
│
├── api-reference/
│   ├── rest-api.md                  # Comprehensive HTTP REST endpoints & SDKs
│   ├── data-models.md               # JSON schemas for observations & alerts
│   └── websocket-and-streaming.md   # SSE & WebSocket real-time specifications
│
├── deployment/
│   ├── aws-sam-guide.md             # AWS SAM multi-lambda operations manual
│   └── cicd-github-actions.md       # OIDC-authenticated GitHub Actions pipeline
│
├── guides/
│   ├── local-ollama-ec2-setup.md    # Self-hosting Ollama models on AWS EC2
│   ├── activity-advisor-algorithms.md # Meteorological comfort index equations
│   ├── testing-handbook.md          # Offline testing fixtures & mock strategies
│   ├── performance-benchmarks.md    # Latency profiles & memory sizing analysis
│   ├── troubleshooting-and-faq.md   # 20+ diagnostic recipes & recovery runbooks
│   ├── disaster-alert-system-gdacs.md # GDACS hazard parsing & Haversine proximity
│   ├── audio-engineering-deepdive.md # Audio codecs, Web Audio FFT, and Polly streams
│   ├── developer-runbook.md         # Day-to-day recipes (adding tools, languages)
│   ├── glossary-and-meteorology.md  # Meteorological formulas & Beaufort scale
│   └── local-mock-development-guide.md # Zero-cloud offline development & simulation
│
├── i18n/
│   └── multilingual-matrix.md       # 100-language routing table & SSML rules
│
├── security/
│   └── threat-model-and-hardening.md # STRIDE analysis & OWASP Top 10 for LLMs
│
└── adr/
    ├── 0001-tri-lambda-architecture.md # Decoupling into 3 specialized Lambdas
    ├── 0002-lambda-function-urls-vs-api-gateway.md # Function URLs vs 29s timeout cap
    └── 0003-litellm-multi-provider-abstraction.md # Multi-provider LiteLLM router
```

---

## 1. System Architecture & Topology

Explore our underlying multi-lambda architecture and state management:

* 🏗️ **[System Architecture & Design Specification](file:///docs/architecture/system-design.md)**
  * Core design principles & sub-second latency targets.
  * In-depth breakdown of `AgentFunction`, `TtsFunction`, and `AlertFunction`.
  * Lambda Function URL vs API Gateway trade-offs.
  * Reactive finite state machine governing user microphone capture.
* 🔄 **[Technical Sequence Flows](file:///docs/architecture/sequence-diagrams.md)**
  * Complete lifecycle from microphone click to synthesized audio playback.
  * Strands Agent tool invocation loops and prompt sandboxing.
  * Amazon EventBridge daily 7:00 AM weather alert pipeline.
  * Rate-limit backoff and Amazon Polly fallback sequences.
* ⚛️ **[Component Lifecycle & Web Audio Context](file:///docs/architecture/component-lifecycle.md)**
  * Client Component architecture in Next.js 14.
  * Browser Web Audio API context resume mechanics and autoplay security.
  * Real-time 60 FPS audio visualizer and typewriter reveal engine.

---

## 2. API Reference & Data Contracts

Integrate programmatically with Weather Buddy endpoints:

* 📡 **[REST API Specification & Client SDKs](file:///docs/api-reference/rest-api.md)**
  * `POST /query`: Conversational meteorological querying endpoint.
  * `POST /transcribe`: Groq Whisper Large v3 audio transcription.
  * `GET /api/alerts`: 5-minute cached proxy for global GDACS hazards.
  * Typed integration examples in TypeScript and Python (`httpx`).
  * RFC 7807 problem detail error schemas.
* 📋 **[Data Models & JSON Schemas](file:///docs/api-reference/data-models.md)**
  * `WeatherData`: Normalized current meteorological observation entity.
  * `ForecastSlice`: 3-hour and daily forecast interval representations.
  * `WeatherAlert`: Official severe weather warning payload schema.
  * `ActivityRecommendation`: Suitability score and factors payload.
* ⚡ **[Streaming & WebSocket Protocol](file:///docs/api-reference/websocket-and-streaming.md)**
  * Proposed Server-Sent Events (SSE) and full-duplex WebSocket architecture.
  * Token-by-token LLM output delivery and chunked Polly audio streaming.

---

## 3. Deployment, Operations & CI/CD

Deploy Weather Buddy locally or to AWS Serverless production:

* ☁️ **[AWS SAM Operations Manual](file:///docs/deployment/aws-sam-guide.md)**
  * End-to-end guided deployment walkthrough (`sam deploy --guided`).
  * Complete CloudFormation parameter dictionary.
  * CloudWatch live log streaming and telemetry configuration.
  * Disaster recovery runbooks and failover procedures.
  * Free tier cost breakdown and resource limits analysis.
* 🚀 **[GitHub Actions CI/CD Pipeline](file:///docs/deployment/cicd-github-actions.md)**
  * Keyless AWS authentication using IAM OIDC Identity Providers.
  * Automated linting, template validation, and pytest test execution.
  * Production continuous deployment workflow.
* 🦙 **[Self-Hosting Ollama on AWS EC2](file:///docs/guides/local-ollama-ec2-setup.md)**
  * Running private quantized LLMs (`qwen2.5:3b-instruct` / `7b-instruct`) on EC2.
  * Automated bash user-data provisioning script.
  * Systemd service configuration and security group isolation.

---

## 4. Engineering Guides & Deep Dives

* 🏃 **[Activity Advisor Scoring Algorithms](file:///docs/guides/activity-advisor-algorithms.md)**
  * Mathematical equations for Heat Index ($HI$) and Wind Chill ($WCI$).
  * Threshold profiles for running, cycling, hiking, golfing, and water sports.
* 🚨 **[GDACS Disaster Hazard Architecture](file:///docs/guides/disaster-alert-system-gdacs.md)**
  * CAP XML schema parsing for tropical storms, floods, and earthquakes.
  * Geospatial proximity matching via the spherical Haversine formula.
* 🎵 **[Audio Engineering & Visualizer Mathematics](file:///docs/guides/audio-engineering-deepdive.md)**
  * MediaRecorder container negotiation (`audio/webm;codecs=opus` vs `audio/mp4`).
  * Fast Fourier Transform (FFT) 60 FPS visualizer mathematics.
  * Base64 MP3 stream decoding into PCM hardware buffers.
* 🛠️ **[Day-to-Day Developer Runbook](file:///docs/guides/developer-runbook.md)**
  * Adding new meteorological tools in 5 steps with offline mocks.
  * Adding new languages to UI translation dictionaries.
  * Emulated container testing with SAM Local and Docker.
* 🔬 **[Meteorological Science Handbook & Glossary](file:///docs/guides/glossary-and-meteorology.md)**
  * Thermodynamics equations (Tetens vapor pressure, Dew Point calculation).
  * International Beaufort Wind Scale reference (Forces 0 to 12).
  * 30/30 convective lightning safety guidelines and metric unit conversions.
* 🧪 **[Quality Assurance & Testing Handbook](file:///docs/guides/testing-handbook.md)**
  * Zero-credential offline test methodology.
  * Unit test mocking fixtures for Boto3, Polly, and OpenWeatherMap.
* 📊 **[Performance Benchmarks & Memory Sizing](file:///docs/guides/performance-benchmarks.md)**
  * End-to-end latency benchmarks across Groq, EC2 Ollama, and Bedrock.
  * Lambda cold-start vs warm-start timing measurements.
  * Optimal memory allocation analysis (512 MB sweet spot).
* 🩺 **[Troubleshooting & Diagnostic Handbook](file:///docs/guides/troubleshooting-and-faq.md)**
  * 20+ categorized diagnostic recipes with symptoms, causes, and solutions.
  * CloudWatch CLI log query recipes.
* ✈️ **[Local Mock Development Guide](file:///docs/guides/local-mock-development-guide.md)**
  * Developing completely offline with `MOCK_MODE=true`.
  * Simulated city fixtures and synthetic audio generation.

---

## 5. Architecture Decision Records (ADRs)

* 🏛️ **[ADR-0001: Separation into Tri-Lambda Serverless Topology](file:///docs/adr/0001-tri-lambda-architecture.md)**
* 🏛️ **[ADR-0002: Adoption of Lambda Function URLs over API Gateway](file:///docs/adr/0002-lambda-function-urls-vs-api-gateway.md)**
* 🏛️ **[ADR-0003: Adoption of LiteLLM Multi-Provider Inference Abstraction](file:///docs/adr/0003-litellm-multi-provider-abstraction.md)**

---

## 6. Internationalization & Security

* 🌍 **[Multilingual Internationalization Matrix](file:///docs/i18n/multilingual-matrix.md)**
  * Complete operational matrix covering 100 world languages.
  * ISO-639-1 language tags and native scripts.
  * Groq Whisper transcription confidence ratings.
  * Amazon Polly Neural voice ID mappings and SSML phonetic rules.
* 🔒 **[Threat Modeling & Security Hardening](file:///docs/security/threat-model-and-hardening.md)**
  * Microsoft STRIDE threat classification matrix.
  * OWASP Top 10 for LLMs defense (Prompt Injection, Insecure Output Handling).
  * Server-Side Request Forgery (SSRF) prevention on weather tool clients.
  * IAM Principle of Least Privilege and secrets lifecycle.
  * Ephemeral in-memory audio processing without persistent storage.
