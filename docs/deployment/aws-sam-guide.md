# Weather Buddy — AWS SAM Production Deployment Guide

This operations guide provides end-to-end instructions for deploying, configuring, monitoring, and maintaining Weather Buddy's multi-lambda serverless infrastructure on Amazon Web Services (AWS) using **AWS SAM (Serverless Application Model)**.

---

## 1. Prerequisites & Environment Preparation

Before deploying the serverless stack, ensure your local development workstation or CI/CD runner satisfies the following prerequisites:

### 1.1 Tooling & Versions
| Tool | Minimum Version | Verification Command | Purpose |
|------|-----------------|----------------------|---------|
| **AWS CLI** | `v2.15.0+` | `aws --version` | AWS API credentials and account interaction |
| **AWS SAM CLI** | `v1.110.0+` | `sam --version` | Serverless build, lint, and packaging engine |
| **Python** | `3.12.x` | `python --version` | Lambda execution runtime |
| **uv** | `v0.4.0+` | `uv --version` | Ultra-fast dependency resolution and virtual environments |
| **Node.js** | `v18.x+` | `node --version` | Frontend dashboard runtime & Vercel CLI |

### 1.2 AWS Account Configuration & Authentication
Ensure you have active AWS credentials configured in your environment or `~/.aws/credentials`:

```bash
# Verify caller identity and account permissions
aws sts get-caller-identity
```

Output should confirm your active Account ID, User ARN, and configured default region (e.g., `us-east-1`).

---

## 2. Infrastructure Architecture & SAM Template Breakdown

Weather Buddy's infrastructure is codified in [`template.yaml`](file:///Users/mithresh/wx-agent/template.yaml). It orchestrates three Lambda functions, one SNS topic, an EventBridge scheduler rule, and dual endpoint exposures.

### 2.1 Resource Mapping

| Logical Resource ID | AWS Resource Type | Description |
|---------------------|-------------------|-------------|
| `AgentFunction` | `AWS::Serverless::Function` | Python 3.12 Lambda running Strands Agent behind `/query` |
| `AgentFunctionUrl` | `AWS::Lambda::Url` | Direct HTTPS URL with no 29s timeout cap |
| `TtsFunction` | `AWS::Serverless::Function` | Speech synthesis Lambda invoking Amazon Polly |
| `AlertFunction` | `AWS::Serverless::Function` | Daily scheduled Lambda checking weather warnings |
| `AlertTopic` | `AWS::SNS::Topic` | Simple Notification Service topic broadcasting email alerts |
| `AlertFunctionDailySchedule` | `AWS::Events::Rule` | EventBridge cron rule (`cron(30 1 * * ? *)`) |

### 2.2 IAM Permissions & Role Definitions
In AWS Academy or enterprise environments, functions attach to a pre-provisioned role:
```yaml
Role: !Sub "arn:aws:iam::${AWS::AccountId}:role/LabRole"
```

If deploying in a standard personal AWS account without a pre-existing `LabRole`, create an IAM role with the following policies attached:
1. `AWSLambdaBasicExecutionRole` (writes logs to Amazon CloudWatch).
2. `AmazonPollyReadOnlyAccess` (allows `TtsFunction` to synthesize speech).
3. `AmazonSNSFullAccess` (allows `AlertFunction` to publish alert topics).
4. `AWSLambdaRole` (allows `AgentFunction` to invoke `TtsFunction` via `lambda:InvokeFunction`).

---

## 3. Step-by-Step Deployment Walkthrough

### Step 1: Validate SAM Template
Run template linting against CloudFormation schema rules:
```bash
make validate
# or: sam validate --lint
```

### Step 2: Build Lambdas with the Makefile Method
Weather Buddy uses custom `Makefile` targets inside each lambda subdirectory to resolve dependencies with `uv`:
```bash
make build
# or: sam build
```
This generates build artifacts in the local `.aws-sam/build/` workspace directory.

### Step 3: Interactive Guided Deployment
For the initial deployment, execute:
```bash
make deploy-guided
# or: sam deploy --guided
```

You will be prompted for parameter values:
```text
Configuring SAM deploy
======================

    Stack Name [wx-agent]: weather-buddy-prod
    AWS Region [us-east-1]: us-east-1
    Parameter OwmApiKey []: <YOUR_OPENWEATHERMAP_API_KEY>
    Parameter AlertLocation [Chennai, IN]: Seattle, US
    Parameter AlertEmail []: your-alerts@example.com
    Parameter LlmModelId [groq/llama-3.1-8b-instant]: groq/llama-3.1-8b-instant
    Parameter LlmBaseUrl []: 
    Parameter LlmApiKey []: <YOUR_GROQ_API_KEY>
    Confirm changes before deploy [y/N]: y
    Allow SAM CLI IAM role creation [Y/n]: Y
    Disable rollback [y/N]: N
    AgentFunction may not have authorization defined, Is this okay? [y/N]: y
    Save arguments to configuration file [Y/n]: Y
    SAM configuration file [samconfig.toml]: samconfig.toml
    SAM configuration environment [default]: default
```

### Step 4: Extract Stack Outputs
Upon deployment completion, CloudFormation outputs the generated endpoints:
```text
CloudFormation outputs from deployed stack
-------------------------------------------------------------------------------------------------
Outputs
-------------------------------------------------------------------------------------------------
Key                 AgentFunctionUrl
Description         Lambda Function URL for POST /query and POST /transcribe (no 29s cap)
Value               https://k7abc89xyz.lambda-url.us-east-1.on.aws/

Key                 ApiUrl
Description         API Gateway invoke URL for POST /query (29s hard cap)
Value               https://abc123def456.execute-api.us-east-1.amazonaws.com/Prod/query
-------------------------------------------------------------------------------------------------
```

---

## 4. Configuring the Frontend & Custom Domains

### 4.1 Connecting Next.js Frontend
Copy the `AgentFunctionUrl` value and store it in `frontend/.env.local`:
```env
NEXT_PUBLIC_API_URL=https://k7abc89xyz.lambda-url.us-east-1.on.aws
```

### 4.2 Deploying Frontend to Vercel
```bash
cd frontend
npx vercel
```
1. Follow interactive CLI prompts to link to your Vercel organization.
2. In the Vercel Project Dashboard, navigate to **Settings > Environment Variables**.
3. Add `NEXT_PUBLIC_API_URL` set to your `AgentFunctionUrl`.
4. Trigger a production redeploy: `npx vercel --prod`.

---

## 5. Monitoring, Observability & CloudWatch Logging

### 5.1 Real-Time Log Tailing
Tail live log output from all three Lambdas during testing:

```bash
# Stream logs from the conversational agent
sam logs -n AgentFunction --stack-name weather-buddy-prod --tail

# Stream logs from the TTS speech synthesis Lambda
sam logs -n TtsFunction --stack-name weather-buddy-prod --tail

# Stream logs from the daily alert cron Lambda
sam logs -n AlertFunction --stack-name weather-buddy-prod --tail
```

### 5.2 Key CloudWatch Metrics to Monitor
- **`Duration`**: Tracks agent execution latency (typically 1.2s - 4.5s depending on LLM tool turns).
- **`Errors`**: Monitors uncaught exceptions or external API timeouts.
- **`Throttles`**: Monitors concurrent execution limits (default standard AWS limit: 1000).
- **`ColdStarts`**: Monitored via CloudWatch Insights queries on initialization events (`@type = "REPORT"`).

---

## 6. Cost Estimation & Free Tier Utilization

Weather Buddy is designed to operate completely within the AWS Free Tier for personal and demonstration workloads:

| Service | Monthly Usage Estimate | AWS Free Tier Allowance | Estimated Cost |
|---------|------------------------|-------------------------|----------------|
| **AWS Lambda** | 10,000 requests (~20,000s compute) | 1,000,000 requests + 3.2M seconds | **$0.00** |
| **Amazon Polly** | 50,000 characters synthesized | 5,000,000 characters / month (12 months free) | **$0.00** |
| **Amazon SNS** | 30 daily email notifications | 1,000 email notifications / month | **$0.00** |
| **Amazon EventBridge** | 31 scheduled invocations | Standard rules free indefinitely | **$0.00** |
| **Groq Cloud API** | ~500 requests / day | Free developer tier with rate limits | **$0.00** |
| **OpenWeatherMap** | ~1,000 calls / day | Free tier: 60 calls/minute, 1M calls/month | **$0.00** |
