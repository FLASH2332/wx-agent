# Contributing to Weather Buddy 🌦️

Thank you for your interest in contributing to **Weather Buddy**! Whether you are fixing an edge-case bug, adding new multilingual features, improving test coverage, or expanding architectural documentation, we welcome your contributions.

This handbook outlines our engineering standards, development lifecycle, review criteria, and submission workflows.

---

## 📋 Table of Contents

- [Code of Conduct](#-code-of-conduct)
- [How to Contribute](#-how-to-contribute)
- [Development Environments](#-development-environments)
  - [Prerequisites](#prerequisites)
  - [Local Backend Setup (Zero-Cloud)](#local-backend-setup-zero-cloud)
  - [Local Frontend Setup](#local-frontend-setup)
- [Testing Guidelines](#-testing-guidelines)
  - [Offline Unit Tests](#offline-unit-tests)
  - [SAM CloudFormation Validation](#sam-cloudformation-validation)
- [Engineering Standards](#-engineering-standards)
  - [Python Code Style](#python-code-style)
  - [JavaScript & React Style](#javascript--react-style)
  - [Prompt Sandboxing & Tool Safety](#prompt-sandboxing--tool-safety)
- [Git Workflow & Commit Guidelines](#-git-workflow--commit-guidelines)
  - [Conventional Commits](#conventional-commits)
  - [Submitting a Pull Request](#submitting-a-pull-request)
- [Architecture Decision Records (ADRs)](#-architecture-decision-records-adrs)

---

## 🤝 Code of Conduct

We are committed to fostering an inclusive, welcoming, and harassment-free community. Please treat all contributors with respect, kindness, and constructive collaboration.

---

## 🛠️ How to Contribute

1. **Fork the Repository:** Create your personal fork on GitHub.
2. **Create a Topic Branch:** Branch out from `main` using descriptive naming:
   ```bash
   git checkout -b feat/your-feature-name
   # or: git checkout -b fix/your-bug-fix
   ```
3. **Make Atomic Changes:** Keep commits focused on a single logical change.
4. **Run Test Suites:** Verify that all offline unit tests pass cleanly (`make test`).
5. **Format & Lint:** Adhere to PEP 8 for Python and ESLint rules for JavaScript.
6. **Submit a Pull Request:** Detail your motivation, implementation approach, and test evidence.

---

## 💻 Development Environments

### Prerequisites
- **Python 3.12+**
- **Node.js 18+** & **npm**
- **AWS SAM CLI** (for serverless CloudFormation validation)
- Free developer API credentials:
  - [OpenWeatherMap API Key](https://openweathermap.org/api) (v2.5 free tier endpoints)
  - [Groq API Key](https://console.groq.com/) (for Llama 3 & Whisper inference)

### Local Backend Setup (Zero-Cloud)
Weather Buddy can run entirely locally without requiring active AWS accounts:

```bash
# 1. Create and activate a Python virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS / Linux
# or: .venv\Scripts\activate on Windows

# 2. Install backend runtime dependencies
pip install strands-agents strands-agents-tools python-dotenv litellm requests

# 3. Configure local environment variables
cp .env.example .env
# Set OWM_API_KEY and LLM_API_KEY (Groq or Ollama)

# 4. Launch the local HTTP development server
python run_local.py
```
The local server listens on `http://127.0.0.1:3001` serving `/query` and `/transcribe`.

### Local Frontend Setup
In a separate terminal:

```bash
cd frontend
npm install

# Configure local client environment
cp .env.local.example .env.local # or ensure NEXT_PUBLIC_API_URL=http://127.0.0.1:3001/query

# Start the Next.js development server
npm run dev
```
Open **http://localhost:3000** in your browser.

---

## 🧪 Testing Guidelines

### Offline Unit Tests
All tests are engineered to execute completely offline without incurring network costs or requiring live AWS credentials:

```bash
# Execute master test target across all microservices
make test

# Or run pytest individually per lambda
cd lambdas/agent-handler && pytest -v
cd lambdas/tts-handler && pytest -v
cd lambdas/alert-handler && pytest -v
```

### SAM CloudFormation Validation
Validate the serverless application template against CloudFormation specifications:

```bash
make validate
# Runs: sam validate --lint
```

---

## 📐 Engineering Standards

### Python Code Style
- Adhere to **PEP 8** standards.
- Maintain type hints where feasible (`def run_agent(query: str, lang: str) -> dict:`).
- Document modules and functions with structured docstrings explaining parameters, returns, and exceptions.
- Never write credentials, tokens, or private endpoints into code files.

### JavaScript & React Style
- Follow modern functional React patterns with hooks (`useState`, `useEffect`, `useCallback`).
- Adhere to Tailwind CSS design tokens established in `frontend/styles/globals.css`.
- Ensure all interactive touch targets satisfy accessibility minimums ($\ge 44\text{px}$).
- Use tabular number formatting on meteorological numeric values (`font-variant-numeric: tabular-nums`).

### Prompt Sandboxing & Tool Safety
- **Strict Meteorological Scope:** Under no circumstances should `prompts.py` be modified to permit general-purpose conversation, coding help, or arbitrary question answering.
- **Tool Determinism:** All meteorological tools must catch network errors gracefully and raise typed domain exceptions (`LocationNotFoundError`) rather than allowing unhandled stack traces.

---

## 📝 Git Workflow & Commit Guidelines

### Conventional Commits
We adhere to the [Conventional Commits](https://www.conventionalcommits.org/) standard:

```
<type>(<scope>): <concise description in imperative mood>
```

**Permitted Types:**
- `feat`: A new user-facing feature or tool capability
- `fix`: A bug fix in client components or backend logic
- `docs`: Documentation additions, guides, or updates
- `refactor`: Code improvements that do not alter functional behavior
- `test`: Adding or enhancing test suites and mocks
- `chore`: Tooling, build pipeline, or dependency maintenance

**Examples:**
- `feat(tools): add UV index metric to activity advisor`
- `fix(audio): handle Safari MP4 audio container headers`
- `docs(deploy): document Function URL CORS configuration`

### Submitting a Pull Request
1. Keep PRs focused on a single feature or bug fix.
2. Provide a descriptive title following Conventional Commits.
3. In the PR body, summarize:
   - What was changed and why.
   - Any manual testing performed (include screenshots for UI changes).
   - Any new environment variables introduced.
4. Verify all tests pass before requesting review.

---

## 🏛️ Architecture Decision Records (ADRs)

Substantial architectural changes (e.g., introducing a new cloud service, changing LLM providers, or altering API schemas) require submitting an ADR under `docs/adr/` using the following template:

```markdown
# ADR-000X: [Short Title]

## Context & Problem Statement
[Describe the motivation, technical constraints, and trade-offs.]

## Decision
[Detail the selected approach and implementation strategy.]

## Consequences
- **Positive:** [Anticipated architectural benefits]
- **Negative:** [Associated overhead or trade-offs]
```
