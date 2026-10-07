# Contributing to Weather Buddy 🌦️

Thank you for your interest in contributing to **Weather Buddy**! Whether you are fixing a bug, adding new multilingual features, improving test coverage, or expanding documentation, we welcome your contributions.

Please review this guide before submitting your pull request.

---

## 📋 Table of Contents

- [Code of Conduct](#-code-of-conduct)
- [How to Contribute](#-how-to-contribute)
- [Development Workflow](#-development-workflow)
  - [Prerequisites](#prerequisites)
  - [Local Backend Setup](#local-backend-setup)
  - [Local Frontend Setup](#local-frontend-setup)
- [Testing Guidelines](#-testing-guidelines)
  - [Running Unit Tests](#running-unit-tests)
  - [Linting and Template Validation](#linting-and-template-validation)
- [Architecture & Safety Constraints](#-architecture--safety-constraints)
  - [Strict Scope Principle](#strict-scope-principle)
  - [Offline Test Isolation](#offline-test-isolation)
- [Commit & Pull Request Guidelines](#-commit--pull-request-guidelines)
  - [Commit Message Format](#commit-message-format)
  - [Submitting a PR](#submitting-a-pr)

---

## 🤝 Code of Conduct

We are committed to providing a welcoming, inclusive, and harassment-free environment for everyone. Please be respectful, constructive, and collaborative in all communications.

---

## 🛠️ How to Contribute

1. **Fork the Repository:** Create your own fork on GitHub.
2. **Create a Feature Branch:** Branch out from `main` with a descriptive name:
   ```bash
   git checkout -b feat/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```
3. **Make Your Changes:** Follow the project structure and conventions described below.
4. **Run Tests & Linters:** Verify all test suites pass cleanly.
5. **Commit Your Changes:** Write descriptive, conventional commit messages.
6. **Open a Pull Request:** Describe your motivation, changes made, and test evidence.

---

## 💻 Development Workflow

### Prerequisites

- **Python 3.12+**
- **Node.js 18+** & **npm**
- **AWS SAM CLI** (for Lambda & CloudFormation development)
- **uv** (recommended for ultra-fast Python package management)
- Free API keys:
  - [OpenWeatherMap API](https://openweathermap.org/api) (v2.5 endpoints)
  - [Groq API](https://console.groq.com/) (for Llama 3 & Whisper inference)

### Local Backend Setup

Weather Buddy supports local execution without AWS credentials:

```bash
# 1. Create and activate a Python virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS / Linux
# or .venv\Scripts\activate on Windows

# 2. Install dependencies
pip install strands-agents strands-agents-tools python-dotenv litellm requests

# 3. Configure environment variables
cp .env.example .env
# Fill in OWM_API_KEY and LLM_API_KEY (Groq or Ollama)

# 4. Start the local dev server
python run_local.py
```
The local server listens on `http://127.0.0.1:3001` with endpoints for `/query` and `/transcribe`.

### Local Frontend Setup

In a separate terminal:

```bash
cd frontend
npm install

# Configure frontend environment variables
cp .env.local.example .env.local # or ensure NEXT_PUBLIC_API_URL=http://127.0.0.1:3001/query

npm run dev
```
Access the dashboard at `http://localhost:3000`.

---

## 🧪 Testing Guidelines

### Running Unit Tests

We maintain offline unit tests that mock AWS services (`boto3`, Polly, Lambda) so contributors do not incur costs or need live cloud credentials.

Use the root `Makefile` target:

```bash
make test
```

Or run pytest directly for individual lambdas:

```bash
# Test Agent Handler
cd lambdas/agent-handler
pytest -v

# Test TTS Handler
cd lambdas/tts-handler
pytest -v
```

### Linting and Template Validation

Validate the AWS SAM template and lint against CloudFormation specifications:

```bash
make validate
# Equivalent to: sam validate --lint
```

---

## 🔒 Architecture & Safety Constraints

When modifying backend logic or agent behaviour, please adhere to these core design principles:

### Strict Scope Principle
Weather Buddy's conversational agent is **strictly scoped to weather and outdoor activity recommendations**.
- Never alter `prompts.py` in a way that allows non-weather, off-topic prompts or general assistant behavior.
- Out-of-scope questions must be politely declined in the user's detected language.

### Offline Test Isolation
- All Lambda tests under `tests/` must mock network and external cloud APIs (OWM, Groq, Polly, SNS).
- Never add tests that perform live HTTP calls against billable or rate-limited endpoints.

### UI Consistency & Design System
- The frontend uses a custom glassmorphism aesthetic built with Tailwind CSS tokens in `frontend/styles/globals.css`.
- Ensure touch targets remain $\ge 44\text{px}$, number displays use tabular formatting (`font-feature-settings: "tnum"`), and icons match text stroke weights.

---

## 📝 Commit & Pull Request Guidelines

### Commit Message Format

We follow the [Conventional Commits](https://www.conventionalcommits.org/) convention:

```
<type>(<scope>): <short description>
```

**Common types:**
- `feat`: A new feature or capability
- `fix`: A bug fix
- `docs`: Documentation updates or additions
- `refactor`: Code restructuring without functional changes
- `test`: Adding or updating test suites
- `chore`: Tooling, dependency, or configuration updates

**Examples:**
- `docs(readme): update deployment parameters and function URL guide`
- `fix(agent): handle missing forecast data gracefully`
- `feat(ui): add keyboard shortcut for microphone toggle`

### Submitting a PR

1. Ensure your branch is rebased on latest `main`.
2. Verify all tests pass with `make test`.
3. Provide a clear summary of your changes in the PR description, including:
   - What changed and why.
   - Any manual testing performed (screenshots or logs appreciated).
   - Any breaking changes or new environment variables needed.
