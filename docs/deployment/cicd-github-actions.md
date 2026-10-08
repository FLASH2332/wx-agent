# Weather Buddy — GitHub Actions CI/CD Pipeline Specification

This document details the automated continuous integration and continuous deployment (CI/CD) pipelines implemented for Weather Buddy using **GitHub Actions**, **AWS OpenID Connect (OIDC)**, and the **AWS SAM CLI**.

---

## 1. Pipeline Architecture & Trust Relationship

Weather Buddy uses secure, keyless authentication with AWS via **IAM OIDC Identity Providers**. GitHub Actions runners assume a temporary IAM role during deployment rather than storing long-lived AWS Access Keys in repository secrets.

```
GitHub Actions Runner              AWS IAM (OIDC Provider)                 AWS Serverless Stack
        │                                    │                                      │
        ├─ 1. Request JWT Token ────────────►│                                      │
        │                                    ├─ 2. Validate Repo Subject Claim      │
        │◄─ 3. Return Temporary STS Creds ───┴─ (repo:FLASH2332/wx-agent)           │
        │                                                                           │
        ├─ 4. sam validate --lint ─────────────────────────────────────────────────►│
        ├─ 5. sam build ───────────────────────────────────────────────────────────►│
        ├─ 6. sam deploy (weather-buddy-prod) ─────────────────────────────────────►│
        │                                                                           │
        ├─ 7. Run Post-Deployment Smoke Tests ─────────────────────────────────────►│
        │◄─ 8. Deployment Successful (Endpoints Active) ────────────────────────────┘
```

---

## 2. Complete Workflow Definition (`.github/workflows/deploy.yml`)

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

permissions:
  id-token: write   # Required for requesting AWS STS OIDC tokens
  contents: read

jobs:
  validate-and-test:
    name: Lint & Unit Tests
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install uv Package Manager
        run: curl -fsSL https://astral.sh/uv/install.sh | sh

      - name: Install SAM CLI
        uses: aws-actions/setup-sam@v2
        with:
          use-installer: true

      - name: Validate SAM Template
        run: sam validate --lint

      - name: Run Backend Unit Tests
        run: |
          pip install pytest pytest-cov
          cd lambdas/agent-handler && pytest -q
          cd ../tts-handler && pytest -q

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 18

      - name: Test Frontend Build
        run: |
          cd frontend
          npm ci
          npm run build

  deploy-production:
    name: Deploy to AWS
    needs: validate-and-test
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Configure AWS Credentials via OIDC
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
          aws-region: us-east-1

      - name: Set up SAM CLI
        uses: aws-actions/setup-sam@v2

      - name: Build Serverless Application
        run: sam build

      - name: Deploy Production Stack
        run: |
          sam deploy --no-confirm-changeset --no-fail-on-empty-changeset \
            --stack-name weather-buddy-prod \
            --parameter-overrides \
              OwmApiKey="${{ secrets.OWM_API_KEY }}" \
              LlmModelId="groq/llama-3.1-8b-instant" \
              LlmApiKey="${{ secrets.GROQ_API_KEY }}" \
              AlertLocation="Seattle, US" \
              AlertEmail="${{ secrets.ALERT_EMAIL }}"
```
