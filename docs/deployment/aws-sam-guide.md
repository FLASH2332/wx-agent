# Weather Buddy — Production AWS SAM Operations & Deployment Manual

This operations manual details the end-to-end lifecycle for deploying, securing, monitoring, and maintaining Weather Buddy on Amazon Web Services using **AWS SAM (Serverless Application Model)**.

---

## 1. Architectural Topology & Deployment Tenets

Weather Buddy's cloud infrastructure is codifying in [`template.yaml`](file:///Users/mithresh/wx-agent/template.yaml) following strict serverless tenets:

1. **Least Privilege Microservices:** Compute workloads are partitioned into dedicated single-responsibility Lambdas:
   - `AgentFunction`: Reasoning, tool loops, and orchestration.
   - `TtsFunction`: Internal speech synthesis.
   - `AlertFunction`: Scheduled event-driven weather alerts.
2. **Timeout Decoupling via Function URLs:** Public endpoints use direct AWS Lambda Function URLs with CORS enabled, bypassing API Gateway's 29-second hard execution ceiling.
3. **Event-Driven Push Notifications:** Automated morning alert evaluations driven by Amazon EventBridge rules and AWS SNS topic distribution.
4. **Zero-File Persistence:** Audio streams are synthesized in-memory as Base64-encoded buffers, eliminating S3 storage overhead and lifecycle cleanup policies.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            AWS REGION: us-east-1                            │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      Public Ingress Boundary                        │   │
│   │                                                                     │   │
│   │   [Lambda Function URL: AgentFunctionUrl] (AuthType: NONE, CORS: *) │   │
│   │   • Uncapped 300s Execution Ceiling                                 │   │
│   │   • Directly routes POST /query and POST /transcribe                │   │
│   └──────────────────────────────────┬──────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │               AgentFunction (AWS Lambda, Python 3.12)               │   │
│   │               Memory: 512MB | Timeout: 300s                         │   │
│   │               • Strands Agent Autonomous Tool Loop                  │   │
│   │               • LiteLLM Router (Groq API / EC2 Ollama)              │   │
│   └───────────────┬─────────────────────────────────────┬───────────────┘   │
│                   │                                     │                   │
│         Synchronous boto3 Invoke              Outbound HTTPS (443)          │
│                   │                                     │                   │
│                   ▼                                     ▼                   │
│   ┌───────────────────────────────┐     ┌───────────────────────────────┐   │
│   │  TtsFunction (AWS Lambda)     │     │      External Data Feeds      │   │
│   │  Memory: 256MB | Timeout: 30s │     │      • OpenWeatherMap v2.5    │   │
│   │  • Amazon Polly Integration   │     │      • US NWS Weather API     │   │
│   │  • Base64 Audio Serialization │     │      • GDACS Emergency Alerts │   │
│   └───────────────────────────────┘     └───────────────────────────────┘   │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      Scheduled Ingress Boundary                     │   │
│   │                                                                     │   │
│   │   [Amazon EventBridge Rule] cron(30 1 * * ? *) (01:30 UTC / 7:00 IST│   │
│   └──────────────────────────────────┬──────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │               AlertFunction (AWS Lambda, Python 3.12)               │   │
│   │               Memory: 256MB | Timeout: 30s                          │   │
│   │               • Scans OWM for Severe Weather Warnings               │   │
│   │               • Evaluates Alert Significance Criteria               │   │
│   └──────────────────────────────────┬──────────────────────────────────┘   │
│                                      │                                      │
│                            Publish to SNS Topic                             │
│                                      │                                      │
│                                      ▼                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │            Amazon SNS Topic (weather-buddy-alerts)                  │   │
│   │            • Instant Email Notifications to Confirmed Subscribers   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Infrastructure Parameter Reference

When deploying via `sam deploy --guided` or automating through CI/CD, the CloudFormation stack accepts the following parameters:

| Parameter Key | Data Type | Default Value | Mandatory? | Architectural Description |
|---------------|:---------:|:-------------:|:----------:|---------------------------|
| `OwmApiKey` | String | *(None)* | **Yes** | OpenWeatherMap v2.5 API Key for meteorological data queries. Marked `NoEcho: true`. |
| `LlmModelId` | String | `groq/llama-3.1-8b-instant` | No | Model string formatted with LiteLLM provider prefix (`groq/` or `openai/`). |
| `LlmApiKey` | String | *(None)* | **Yes** | Authentication secret for the LLM inference provider (`ollama` for self-hosted instances). Marked `NoEcho: true`. |
| `LlmBaseUrl` | String | `""` | No | OpenAI-compatible endpoint URL for self-hosted models (e.g., `http://<ec2-ip>:11434/v1`). |
| `AlertLocation` | String | `Chennai, IN` | No | Geographic target city scanned daily for extreme weather warnings. |
| `AlertEmail` | String | `""` | No | Recipient email address subscribed to the SNS warning topic. |

---

## 3. Deployment Procedures

### 3.1 Validation & Linting
Verify CloudFormation compliance before building:
```bash
make validate
# Runs: sam validate --lint
```

### 3.2 Building with Makefile Method
Each Lambda directory contains a `Makefile` triggering `uv` dependency installation:
```bash
make build
# Runs: sam build
```

### 3.3 Guided First-Time Deployment
```bash
make deploy-guided
# Runs: sam deploy --guided
```

### 3.4 Headless Deployment via CI/CD
```bash
sam deploy --no-confirm-changeset --no-fail-on-empty-changeset \
  --stack-name weather-buddy-prod \
  --parameter-overrides \
    OwmApiKey="$OWM_API_KEY" \
    LlmModelId="groq/llama-3.1-8b-instant" \
    LlmApiKey="$GROQ_API_KEY" \
    AlertLocation="Seattle, US" \
    AlertEmail="alerts@example.com"
```

---

## 4. Disaster Recovery & Rollback Runbooks

### 4.1 CloudFormation Rollback Recovery
If a deployment fails during parameter validation or resource provisioning:
1. Identify the failing resource in CloudFormation events:
   ```bash
   aws cloudformation describe-stack-events --stack-name weather-buddy-prod \
     --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
     --output table
   ```
2. If the stack is locked in `ROLLBACK_COMPLETE`:
   ```bash
   sam delete --stack-name weather-buddy-prod --no-prompts
   make deploy-guided
   ```

### 4.2 Upstream Rate-Limit Failover Runbook
If Groq Cloud experiences an outage:
1. Update `LlmModelId` and `LlmBaseUrl` in `samconfig.toml` to point to a backup self-hosted EC2 instance or alternative LiteLLM provider.
2. Trigger instant redeployment:
   ```bash
   make deploy
   ```
3. Verify endpoint health with smoke tests:
   ```bash
   curl -X POST https://<function-url>/query \
     -H "Content-Type: application/json" \
     -d '{"text": "Ping"}'
   ```

---

## 5. Cost Optimization & Free Tier Budget Limits

Weather Buddy's architecture is engineered to run at **$0.00/month** on personal accounts:

| Component | AWS Resource | Free Tier Quota | Typical Monthly Consumption | Billable Cost |
|-----------|--------------|-----------------|-----------------------------|:-------------:|
| Ingress | Lambda Function URL | Unlimited (Free) | 15,000 requests | $0.00 |
| Reasoning | Agent Lambda (512MB) | 400,000 GB-seconds / mo | 3,800 GB-seconds | $0.00 |
| Audio | TTS Lambda (256MB) | 400,000 GB-seconds / mo | 900 GB-seconds | $0.00 |
| Speech Engine | Amazon Polly | 5M characters / mo (12 mos) | 120,000 characters | $0.00 |
| Scheduling | Amazon EventBridge | Unlimited standard rules | 31 executions | $0.00 |
| Notifications | Amazon SNS | 1,000 email dispatches / mo | 30 email dispatches | $0.00 |
