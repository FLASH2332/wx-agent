# ADR-0002: Adoption of Lambda Function URLs over API Gateway for Agent Ingress

* **Status:** Accepted
* **Date:** 2026-10-06
* **Deciders:** Weather Buddy Core Architecture Team

---

## 1. Context & Problem Statement

AWS API Gateway enforces an immutable, hard **29-second execution timeout** on all HTTP requests. 

When Weather Buddy operates in self-hosted or complex reasoning modes:
1. Multi-turn agent loops requiring multiple meteorological tool calls (`get_forecast`, `get_alerts`, `activity_advisor`) can consume 15 to 25 seconds.
2. Self-hosted quantized models running on EC2 CPU instances (e.g. `qwen2.5:7b-instruct` on `c6i.2xlarge`) can require up to 35 seconds under heavy load.
3. API Gateway terminates connections at 29.001 seconds, returning `504 Gateway Timeout` to the client even when the Lambda is seconds away from completing successfully.

---

## 2. Decision

We decided to provision and expose **AWS Lambda Function URLs** (`AgentFunctionUrl`) directly on `AgentFunction`:

1. **Uncapped Timeout:** Lambda Function URLs respect the Lambda function's configured timeout ceiling (300 seconds), entirely bypassing the 29-second API Gateway restriction.
2. **Built-In CORS:** Configured directly in CloudFormation with `AllowOrigins: ['*']` and `AllowMethods: ['POST']`.
3. **Reduced Latency:** Bypassing API Gateway reduces network hop latency by 40-70ms per request.
4. **Dual Ingress:** API Gateway endpoints remain provisioned as fallback entry points for clients that do not experience long inference times.

---

## 3. Consequences

### Positive
- Zero 504 timeout failures when running self-hosted models or extensive multi-tool reasoning chains.
- Lower cloud hosting costs (Lambda Function URLs carry zero per-million request charge beyond base Lambda compute).

### Negative
- Lacks advanced API Gateway capabilities (WAF inspection, request throttling, usage tiers), which must be handled at the application or CloudFront layer if needed.
