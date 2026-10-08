# 🌤️ WeatherBuddy: The Agentic Weather Dashboard

**WeatherBuddy** is a next-generation, multi-modal weather assistant built for our hackathon. It moves beyond standard rule-based weather apps by employing a multi-agent LLM architecture that deeply understands user context, parses ambiguous natural language, and dynamically routes responses to the most optimal UI layout.

---

## 🚀 Hackathon Summary & Vision

Traditional weather apps force users to manually search for locations, scroll through hourly timelines, and decipher meteorological data to answer simple questions like, *"Will I need an umbrella for my run tonight?"* 

WeatherBuddy flips this paradigm. By using a sophisticated **Agentic Workflow**, the application understands conversational queries, resolves ambiguous locations, automatically translates time references (like "tonight" or "this weekend") into precise unix timestamps, and generates hyper-personalized weather analysis. It then dynamically decides whether to respond with a rich, widget-based dashboard or a simple conversational chat.

## ✨ Key Features

- **Multi-Agent Architecture**: 
  - **The Analyst Agent**: Deeply analyzes the user's query, calls real-time weather APIs, and performs complex reasoning (e.g., location disambiguation and timezone-aware calculations).
  - **The UI Router Agent**: Inspects the Analyst's output and determines the optimal way to present the data to the user (rich dashboard vs. conversational text).
- **Dynamic UI Generation**: The frontend automatically morphs between conversational chat and a full analytical dashboard with 5-day forecasts and hourly timelines based on the Router's JSON payload.
- **Voice-First Interaction (STT & TTS)**: Full support for real-time voice queries using Groq's `whisper-large-v3` model for lightning-fast speech-to-text transcription.
- **Native Multilingual Support**: Automatically detects the user's language and instructs the LLM to translate meteorological tool data natively before presenting the response.
- **Provider-Agnostic LLM Routing**: Powered by `LiteLLM`, allowing the backend to swap between Groq (the current default), OpenAI-compatible APIs and Amazon Bedrock without changing agent code.
- **Robust Error Handling**: Built-in exponential backoff for rate limits, intelligent fallback UI modes for parsing errors, and aggressive in-place memory scrubbing to ensure compatibility with strict APIs.

---

## 🛠️ Technology Stack & Architecture

### Backend (Agent service)
- **Python 3.12**
- **Strands Framework**: For orchestrating the multi-agent workflow and tool calling.
- **LiteLLM**: For universal LLM API routing.
- **OpenWeatherMap API**: For real-time meteorological data.

### Frontend
- **React / Next.js**: For a dynamic, responsive, and glassmorphic user interface.
- **Web Audio API**: For capturing microphone input and streaming it to the backend.

### ☁️ AWS (two accounts, two separately deployed stacks)

| Stack | Account | Template | Contains |
|---|---|---|---|
| **agent** | `lab-new` | `infra/container.yaml` | Docker agent on ECS Fargate, API Gateway -> VPC Link -> internal ALB, CloudWatch logs/alarms, autoscaling, Secrets Manager, ECR, log-export Lambda |
| **platform** | `lab-existing` | `infra/platform.yaml` | S3 (agent logs, Transcribe input), SNS (alarms, weather alerts), EventBridge-scheduled alert Lambda |

The old all-Lambda stack (`template.yaml`, `lambdas/`) is kept and still deployable with `make deploy`.
Full design, commands and tests: [docs/09-two-account-setup.md](docs/09-two-account-setup.md); command reference: [docs/06-deploy-script-reference.md](docs/06-deploy-script-reference.md).

## Run it locally

```bash
cp .env.example .env            # set OWM_API_KEY and LLM_API_KEY (Groq)
pip install -r agent_service/requirements-dev.txt
python -m agent_service         # backend on http://127.0.0.1:3001
cd frontend && npm install && npm run dev
```
Or with Docker: `make docker-run`. Tests (offline, no AWS): `make test`.

## AWS credentials (one mechanism)

AWS access comes only from AWS CLI profiles. `.env` holds just the profile *name* (`AWS_PROFILE`) and region, never keys.

```bash
python scripts/set_lab_credentials.py wb-new         # Learner Lab, agent account
python scripts/set_lab_credentials.py wb-existing    # Learner Lab, platform account
python scripts/deploy.py accounts                    # who is who, and which keys expired
```

## Deploy (each stack on its own)

```bash
python scripts/deploy.py deploy lab-existing   # platform: S3, SNS, EventBridge
python scripts/deploy.py deploy lab-new        # agent: Docker, ALB, API Gateway, CloudWatch
python scripts/smoke_test.py platform lab-existing
python scripts/smoke_test.py agent lab-new
python scripts/notify_test.py link lab-new     # cross-account wiring
python scripts/load_test.py lab-new --yes      # load balancing and scale up/down
```
Add `--dry-run` to `deploy` to preview commands. `--standalone` deploys the agent without the platform.
