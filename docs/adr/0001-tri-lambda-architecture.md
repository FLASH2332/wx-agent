# ADR-0001: Separation into Tri-Lambda Serverless Microservices Topology

* **Status:** Accepted
* **Date:** 2026-10-06
* **Deciders:** Weather Buddy Core Architecture Team

---

## 1. Context & Problem Statement

Initial prototypes of Weather Buddy coupled speech synthesis (Polly), natural language agent reasoning (Strands Agent + LiteLLM), and scheduled event polling into a single monolithic AWS Lambda function.

This monolithic approach created severe architectural bottlenecks:
1. **Excessive Memory Overhead:** Speech synthesis requires negligible memory (~128MB), while Strands Agent cold starts require at least 512MB for speedy module importation. Running Polly within the agent container forced over-provisioning memory for lightweight audio operations.
2. **Cold Start Penalty:** Bundling all dependencies (`boto3`, `litellm`, `strands_agents`, `requests`, `python-dotenv`) increased container size, leading to cold starts of 2.5+ seconds.
3. **Execution Coupling:** Daily scheduled weather monitoring runs on an EventBridge cron and requires no conversational reasoning, yet loaded the full LLM framework unnecessarily.

---

## 2. Decision

We decided to decouple the backend into **three discrete, specialized AWS Lambda functions**:

1. **`AgentFunction` (`lambdas/agent-handler`):**
   - **Role:** Coordinates user requests, drives Strands Agent reasoning turns, evaluates meteorological tools, and orchestrates the user conversation.
   - **Memory:** 512 MB.
   - **Timeout:** 300 seconds.
2. **`TtsFunction` (`lambdas/tts-handler`):**
   - **Role:** Pure internal compute microservice invoking Amazon Polly neural voices and returning Base64-encoded MP3 streams.
   - **Memory:** 256 MB.
   - **Timeout:** 30 seconds.
   - **Access:** Invoked exclusively via internal AWS SDK (`boto3.client('lambda').invoke()`).
3. **`AlertFunction` (`lambdas/alert-handler`):**
   - **Role:** Triggered daily by Amazon EventBridge cron (`cron(30 1 * * ? *)`) to check OpenWeatherMap alerts and publish bulletins to AWS SNS.
   - **Memory:** 256 MB.
   - **Timeout:** 30 seconds.

---

## 3. Consequences

### Positive
- **Reduced Cold Starts:** `TtsFunction` and `AlertFunction` cold start in under 220ms due to minimal package dependencies.
- **Cost Isolation:** Scheduled daily checks consume fraction-of-a-cent compute without loading LLM modules.
- **Independent Scalability:** Speech synthesis scales independently from LLM reasoning.

### Negative
- **Local Development Orchestration:** Running multiple Lambdas locally requires a unified development server ([`run_local.py`](file:///Users/mithresh/wx-agent/run_local.py)) to simulate multi-lambda interactions.
