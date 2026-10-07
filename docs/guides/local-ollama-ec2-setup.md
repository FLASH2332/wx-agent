# Weather Buddy — Self-Hosting Ollama on AWS EC2

This guide details how to deploy a self-hosted, private large language model (LLM) backend on Amazon EC2 running **Ollama** (e.g., `qwen2.5:3b-instruct` or `qwen2.5:7b-instruct`), and connect it directly to Weather Buddy's serverless agent via **LiteLLM**.

---

## 1. Architecture & Operational Rationale

Weather Buddy is designed with model portability at its core. By routing LLM calls through LiteLLM's unified client abstraction, switching from cloud-hosted Groq inference to a self-hosted Ollama server requires modifying only three environment variables:

```
┌─────────────────────────────────┐                 ┌─────────────────────────────────┐
│     Weather Buddy Backend       │                 │       Amazon EC2 Instance       │
│     (AWS Lambda / run_local.py) │                 │                                 │
│                                 │                 │  ┌───────────────────────────┐  │
│  ┌───────────────────────────┐  │   HTTP POST     │  │   Ollama Server (v0.3.14) │  │
│  │ LiteLLM Provider Client   ├──┼────────────────►│  │   Listening on 0.0.0.0:11434│  │
│  │ BaseUrl: http://<ip>:11434│  │   /v1/chat/...  │  └─────────────┬─────────────┘  │
│  │ ModelId: openai/qwen2.5   │  │                 │                │                │
│  └───────────────────────────┘  │                 │                ▼                │
│                                 │                 │  ┌───────────────────────────┐  │
│                                 │                 │  │ Qwen 2.5 3B / 7B Instruct │  │
│                                 │                 │  │ 4-bit Quantized GGUF Model│  │
│                                 │                 │  └───────────────────────────┘  │
└─────────────────────────────────┘                 └─────────────────────────────────┘
```

### Why Self-Host?
1. **Zero Third-Party Data Transmission:** User weather queries stay entirely inside your private AWS VPC.
2. **Predictable Flat Pricing:** Fixed hourly EC2 rate without token-metered billing.
3. **No Rate Limiting:** Eliminate third-party API rate quotas (RPM/TPM caps).

---

## 2. Recommended EC2 Instance Types

| Instance Type | vCPU | RAM | GPU / Accelerator | Best Model Fit | Avg Tokens/Sec | Est. Cost / Mo |
|---------------|:----:|:---:|:-----------------:|:---------------|:--------------:|:--------------:|
| `t3.xlarge` | 4 | 16 GiB | None (CPU Only) | `qwen2.5:3b-instruct` (Q4_K_M) | 12 - 18 t/s | ~$120 |
| `c6i.2xlarge` | 8 | 16 GiB | None (High CPU) | `qwen2.5:7b-instruct` (Q4_K_M) | 22 - 30 t/s | ~$245 |
| `g5.xlarge` | 4 | 16 GiB | NVIDIA A10G (24GB VRAM) | `qwen2.5:7b-instruct` (FP16) | 90 - 130 t/s | ~$735 |

*Recommendation for Hackathons & Demos:* The **`t3.xlarge`** or **`c6i.2xlarge`** using the 3B/7B quantized model provides an ideal balance of cost and conversational speed.

---

## 3. Automated EC2 Provisioning Script

Launch an Ubuntu 24.04 LTS instance and run the provisioning script below:

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "==> Step 1: Updating System Packages..."
sudo apt-get update -y && sudo apt-get upgrade -y
sudo apt-get install -y curl htop ufw jq

echo "==> Step 2: Installing Ollama Engine..."
curl -fsSL https://ollama.com/install.sh | sh

echo "==> Step 3: Configuring Systemd Service for External VPC Access..."
sudo mkdir -p /etc/systemd/system/ollama.service.d
cat << 'EOF' | sudo tee /etc/systemd/system/ollama.service.d/override.conf
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_ORIGINS=*"
Environment="OLLAMA_KEEP_ALIVE=24h"
EOF

sudo systemctl daemon-reload
sudo systemctl restart ollama
sudo systemctl enable ollama

echo "==> Step 4: Downloading High-Speed Weather Assistant Model..."
ollama pull qwen2.5:3b-instruct
ollama pull qwen2.5:7b-instruct

echo "==> Step 5: Verifying Ollama Health Status..."
curl http://localhost:11434/api/tags | jq .
echo "==> Setup Complete! Ollama is ready."
```

---

## 4. Security Group & Firewall Hardening

1. **Inbound Rule Configuration:**
   - Allow port `11434` **only** from your AWS Lambda Security Group or authorized developer IP addresses.
   - Never expose port `11434` open to `0.0.0.0/0` without an authentication reverse proxy (Nginx or Caddy with Bearer token authentication).
2. **Reverse Proxy with Authentication (Optional Production Setup):**
   ```nginx
   server {
       listen 80;
       server_name llm.your-domain.internal;

       location / {
           proxy_pass http://127.0.0.1:11434;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_read_timeout 300s;
           proxy_connect_timeout 300s;
       }
   }
   ```

---

## 5. Integrating with Weather Buddy

### 5.1 Local Development Configuration
Edit your root `.env` file:

```env
# OpenWeatherMap
OWM_API_KEY=your_openweathermap_api_key

# Self-Hosted Ollama
LLM_MODEL_ID=openai/qwen2.5:3b-instruct
LLM_BASE_URL=http://<YOUR_EC2_PUBLIC_OR_PRIVATE_IP>:11434/v1
LLM_API_KEY=ollama
```

### 5.2 AWS SAM Deployment Configuration
When deploying with `sam deploy --guided`, supply your EC2 endpoint:

```text
Parameter LlmModelId: openai/qwen2.5:3b-instruct
Parameter LlmBaseUrl: http://<YOUR_EC2_IP>:11434/v1
Parameter LlmApiKey: ollama
```

### 5.3 Function URL Timeout Requirement
Self-hosted models on CPU instances may take 4 to 12 seconds to generate tool-call evaluations and responses. **Always connect your frontend to `AgentFunctionUrl`** rather than the API Gateway REST URL, as API Gateway will abort requests after 29 seconds.

---

## 6. Benchmarking & Performance Diagnostics

Test inference latency directly from your terminal:

```bash
time curl -X POST http://<YOUR_EC2_IP>:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5:3b-instruct",
    "messages": [
      {"role": "system", "content": "You are a helpful weather assistant."},
      {"role": "user", "content": "What causes thunderstorms?"}
    ],
    "temperature": 0.2
  }' | jq .choices[0].message.content
```
