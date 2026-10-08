# ADR-0003: Adoption of LiteLLM Unified Model Abstraction for Multi-Provider Portability

* **Status:** Accepted
* **Date:** 2026-10-06
* **Deciders:** Weather Buddy Core Architecture Team

---

## 1. Context & Problem Statement

Initial implementations of Weather Buddy hardcoded direct SDK bindings to the Groq Cloud Python library.

This created vendor lock-in and operational limitations:
1. Developers could not run or evaluate open-weights models (such as Qwen 2.5 or Mistral) locally without substantial codebase rewrites.
2. In enterprise or sensitive compliance environments where cloud inference is forbidden, running self-hosted models on private EC2 instances was impossible.
3. Swapping model versions required modifying Python application code across multiple lambda files.

---

## 2. Decision

We integrated **LiteLLM** as the unified inference routing abstraction layer:

1. **Provider Agnostic Router:** Switching LLM engines requires altering only three environment variables (`LLM_MODEL_ID`, `LLM_BASE_URL`, `LLM_API_KEY`).
2. **Standardized Tool Calling:** LiteLLM translates OpenAI-compatible tool call payloads uniformly across hosted providers (Groq, Bedrock, Anthropic) and self-hosted instances (Ollama, vLLM).
3. **Seamless Local-to-Cloud Transition:** Local development can run against Ollama at `http://localhost:11434/v1`, while cloud production seamlessly targets hosted Groq Llama 3.1 8B.

---

## 3. Consequences

### Positive
- Single unified agent codebase across all execution targets.
- Zero code modifications required when testing new LLM releases.
- Native support for private on-premises or EC2 Ollama deployments.

### Negative
- LiteLLM introduces an additional package dependency (~15MB compressed) in the Lambda deployment package.
