# Weather Buddy — Technical Troubleshooting, Diagnostics & FAQ Handbook

This handbook provides an exhaustive catalog of diagnostic techniques, error signatures, recovery procedures, and operational FAQs for Weather Buddy across local development and AWS serverless production environments.

---

## 1. Quick Diagnostic Flowchart

```
                 Symptom Observed
                        │
       ┌────────────────┼────────────────┐
       ▼                ▼                ▼
Audio Capture /    Agent / Tool     CloudFormation /
Transcription       Execution           Deployment
   Issue              Issue               Issue
       │                │                │
   Section 2        Section 3        Section 4
```

---

## 2. Voice Ingestion & Audio Transcription Diagnostics

### Recipe 2.1: Browser Denies Microphone Access
- **Signature:** `DOMException: Permission denied` or `NotAllowedError`.
- **Root Cause:** Origin not served over secure transport (`https://`) or explicit user block.
- **Remediation:**
  1. Access frontend exclusively via `http://localhost:3000` or an HTTPS domain.
  2. In Chrome: Navigate to `chrome://settings/content/microphone` and clear block rules for the domain.
  3. In Safari: Open **Settings > Websites > Microphone** and change permission from "Deny" to "Allow".

### Recipe 2.2: Whisper Ingestion Rejection (HTTP 415 / 400)
- **Signature:** `POST /transcribe` returns `{"error": "Unsupported audio container or format"}`.
- **Root Cause:** Incomplete recording headers caused by stopping MediaRecorder too quickly (< 400ms).
- **Remediation:**
  1. Implement minimum duration debounce (500ms) before allowing the user to finalize the recording buffer.
  2. Ensure MIME type fallback hierarchy in `VoiceInput.js`:
     ```javascript
     const mimeType = [
       'audio/webm;codecs=opus',
       'audio/webm',
       'audio/mp4',
       'audio/ogg'
     ].find(type => MediaRecorder.isTypeSupported(type));
     ```

### Recipe 2.3: Audio Playback Silent / Autoplay Block
- **Signature:** `DOMException: play() failed because the user didn't interact with the document first`.
- **Root Cause:** Web Audio autoplay policies prohibit programmatic audio playback without a preceding user touch or click gesture.
- **Remediation:**
  1. Ensure the audio play trigger is tied directly to the user's click event on the send button or microphone toggle.
  2. Display a manual play/pause button in `AudioPlayer.js` allowing the user to trigger playback explicitly if autoplay fails.

---

## 3. Agent Reasoning & Meteorological Tool Failures

### Recipe 3.1: OpenWeatherMap 401 Unauthorized
- **Signature:** Tool execution returns `HTTP 401: Invalid API key`.
- **Root Cause:** `OWM_API_KEY` is missing or newly created.
- **Remediation:**
  1. New OpenWeatherMap free-tier API keys require 10 to 30 minutes to propagate across global edge caches.
  2. Verify that the key is activated on the OpenWeatherMap dashboard under API keys.

### Recipe 3.2: Upstream Rate Limit Exceeded (HTTP 429)
- **Signature:** LLM inference or OWM queries abruptly fail with HTTP 429.
- **Root Cause:** Quota exhaustion on free-tier developer accounts.
- **Remediation:**
  1. For Groq: Switch `LLM_MODEL_ID` to `groq/llama-3.1-8b-instant`, which provides higher request-per-minute ceilings.
  2. For OpenWeatherMap: Leverage client-side caching in `frontend/lib/api.js` (5-minute TTL on city forecasts).

### Recipe 3.3: Language Disconnect / Agent English Defaulting
- **Signature:** User speaks in French or Japanese, but the agent replies in English.
- **Root Cause:** `lang` parameter omitted from request payload or prompt instructions bypassed.
- **Remediation:**
  1. Check browser network tab: Verify `POST /query` body contains `{"lang": "fr"}`.
  2. Inspect `lambdas/agent-handler/prompts.py`: Ensure system prompt contains the mandatory directive:
     ```text
     CRITICAL: You must ALWAYS articulate your response in '{lang}'.
     Do not translate back to English.
     ```

---

## 4. AWS Serverless Infrastructure & CloudFormation Issues

### Recipe 4.1: CloudFormation Stack Deployment Rollback
- **Signature:** `sam deploy` outputs `UPDATE_ROLLBACK_IN_PROGRESS`.
- **Diagnostic Command:**
  ```bash
  aws cloudformation describe-stack-events --stack-name weather-buddy-prod \
    --query 'StackEvents[?ResourceStatus==`CREATE_FAILED` || ResourceStatus==`UPDATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
    --output table
  ```
- **Remediation:**
  1. If failing on IAM role creation in sandbox environments, bind directly to `LabRole` in `template.yaml`.
  2. If failing on parameter validation, run `make validate` to lint CloudFormation YAML syntax.

### Recipe 4.2: API Gateway 504 Gateway Timeout
- **Signature:** Requests to `/query` fail with `504 Gateway Timeout` after exactly 29 seconds.
- **Root Cause:** AWS API Gateway enforces an immutable 29-second hard ceiling. Slow self-hosted LLMs or multi-step tool calls exceed this window.
- **Remediation:**
  Connect the frontend directly to the **Lambda Function URL** (`AgentFunctionUrl`), which allows requests to run up to the full Lambda function timeout (configured at 300 seconds).

---

## 5. Frequently Asked Questions (FAQ)

### Q: Can I run Weather Buddy completely offline without cloud API keys?
**A:** Yes. You can run Ollama locally (`LLM_MODEL_ID=openai/qwen2.5:3b-instruct` on `http://localhost:11434/v1`) and mock OpenWeatherMap via local JSON fixtures.

### Q: How are government weather alerts aggregated?
**A:** Alerts are sourced from the US National Weather Service (NWS) API for North America and GDACS (Global Disaster Alert and Coordination System) for international emergencies.

### Q: How do I change the temperature units between Metric and Imperial?
**A:** The agent naturally interprets queries like *"What is the temperature in Fahrenheit?"* and formats responses accordingly. The frontend dashboard also includes a toggle in the settings menu.

### Q: How does the proactive daily email alert work?
**A:** Amazon EventBridge triggers `AlertFunction` every morning at 01:30 UTC (7:00 AM IST). It evaluates weather alerts for the configured `AlertLocation` and publishes bulletins to the `weather-buddy-alerts` SNS topic.
