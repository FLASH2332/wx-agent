# Weather Buddy — Troubleshooting Guide & FAQ

This document catalogs known issues, edge cases, recovery procedures, and frequently asked questions encountered across local development and production deployments of Weather Buddy.

---

## 1. Voice Ingestion & Audio Transcription Issues

### 1.1 "Microphone access denied" or MediaRecorder Not Starting
* **Symptom:** Clicking the microphone button does not trigger audio recording; console logs `NotAllowedError: Permission denied`.
* **Root Cause:** Modern browsers restrict audio device capture to secure origins (`https://` or `http://localhost`). Additionally, browser permissions may have been denied by the user.
* **Resolution:**
  1. Ensure the application is accessed over `http://localhost:3000` or an HTTPS domain.
  2. In Google Chrome, navigate to `chrome://settings/content/microphone` and grant permission for the host domain.
  3. In Safari, enable microphone access under **Settings > Websites > Microphone**.

### 1.2 Whisper Transcription Fails with HTTP 400/415
* **Symptom:** `POST /transcribe` returns `{"error": "Unsupported audio format"}`.
* **Root Cause:** The browser captured audio in an unsupported container format or empty payload (0-byte blob).
* **Resolution:**
  1. Inspect the recorded MIME type in `VoiceInput.js`. The default preferred recording type is `audio/webm;codecs=opus` on Chrome/Firefox and `audio/mp4` on Safari.
  2. Ensure recording duration exceeds 500 milliseconds before stopping the recorder to avoid empty headers.

### 1.3 Audio Autoplay Blocked on Browser
* **Symptom:** Agent responds, but synthesized Polly audio does not play aloud; console logs `DOMException: play() failed because the user didn't interact with the document first`.
* **Root Cause:** Web Audio autoplay security policies require an explicit user gesture prior to playing unmuted sound streams.
* **Resolution:**
  1. The audio player triggers playback only in response to a direct click on either the send button or the microphone toggle.
  2. If typing via keyboard, press Enter or click the dedicated Play icon in the assistant response bubble.

---

## 2. Conversational Agent & Tool Execution Failures

### 2.1 "City not found" or `LocationNotFoundError`
* **Symptom:** The assistant responds: *"I could not find weather information for that location."*
* **Root Cause:** OpenWeatherMap's geocoding endpoint failed to resolve the city name due to misspelling or ambiguous locality.
* **Resolution:**
  1. Add a country code to clarify ambiguous cities (e.g., query `"Paris, TX"` instead of `"Paris"`, or `"Portland, OR"` vs `"Portland, ME"`).
  2. Verify your `OWM_API_KEY` is activated. New OpenWeatherMap API keys can take between 10 to 30 minutes to activate globally across their edge network.

### 2.2 Rate Limit Exceeded (HTTP 429) from OpenWeatherMap or Groq
* **Symptom:** The agent loop terminates abruptly with an error toast indicating service exhaustion.
* **Root Cause:** Free tier API quota limits were exceeded:
  - OpenWeatherMap Free Tier: 60 calls per minute.
  - Groq Free Tier: Rate limits depend on requests-per-minute (RPM) and tokens-per-minute (TPM).
* **Resolution:**
  1. For OpenWeatherMap, enable client-side caching in `frontend/lib/api.js` or avoid rapid successive searches.
  2. For Groq, switch `LLM_MODEL_ID` to `groq/llama-3.1-8b-instant`, which has higher throughput and lower latency than larger 70B variants.

### 2.3 Agent Responds in English Despite Speaking Another Language
* **Symptom:** User speaks in French or Spanish, but the agent replies in English.
* **Root Cause:** The transcription payload failed to pass the detected `lang` parameter, or the system prompt did not enforce language mirroring.
* **Resolution:**
  1. Verify the `POST /query` payload contains the expected ISO-639-1 code: `{"text": "...", "lang": "fr"}`.
  2. Inspect [`lambdas/agent-handler/prompts.py`](file:///Users/mithresh/wx-agent/lambdas/agent-handler/prompts.py). Ensure the mandatory clause is present:
     ```text
     IMPORTANT INSTRUCTION: You must ALWAYS respond in '{lang}' ({lang_name}).
     Never respond in English unless the detected language is English.
     ```

---

## 3. Speech Synthesis (Polly & TTS Lambda) Issues

### 3.1 Base64 Audio String is Empty (`audio_b64: ""`)
* **Symptom:** Agent response text appears normally, but no audio is synthesized.
* **Root Cause:** The `TtsFunction` failed to execute or encountered an IAM permission error when invoking Amazon Polly.
* **Resolution:**
  1. Check CloudWatch logs for `TtsFunction`:
     ```bash
     sam logs -n TtsFunction --stack-name weather-buddy-prod --tail
     ```
  2. Verify the IAM execution role has `polly:SynthesizeSpeech` permission.
  3. Check the `TTS_LAMBDA_NAME` environment variable in `AgentFunction`. It must match the deployed physical resource name of `TtsFunction`.

### 3.2 Unsupported Language Voice in Polly
* **Symptom:** Speech synthesis fails for rare regional dialects.
* **Root Cause:** Amazon Polly does not offer Neural voices for every single world language.
* **Resolution:**
  [`lambdas/tts-handler/handler.py`](file:///Users/mithresh/wx-agent/lambdas/tts-handler/handler.py) includes a fallback mechanism: if an unmapped language code is supplied, it gracefully defaults to standard multilingual Polly voices or falls back to silent text responses.

---

## 4. AWS SAM Deployment & CloudFormation Issues

### 4.1 `ROLLBACK_IN_PROGRESS`: LabRole Permission Denied
* **Symptom:** `sam deploy` fails with `CREATE_FAILED: API: iam:CreateRole User is not authorized`.
* **Root Cause:** In restricted environments (e.g., AWS Academy, corporate sandboxes), users cannot create new IAM roles.
* **Resolution:**
  [`template.yaml`](file:///Users/mithresh/wx-agent/template.yaml) is configured to bind directly to the pre-existing role:
  ```yaml
  Role: !Sub "arn:aws:iam::${AWS::AccountId}:role/LabRole"
  ```
  Ensure the stack is deployed in an account where `LabRole` exists, or replace the ARN with your own admin role.

### 4.2 API Gateway 504 Gateway Timeout (29-Second Limit)
* **Symptom:** Frontend displays a timeout error when querying the backend via API Gateway.
* **Root Cause:** When using slow self-hosted LLMs (e.g., Ollama running on an EC2 t3 instance) with multiple tool calls, total execution time exceeds API Gateway's fixed 29-second timeout.
* **Resolution:**
  Use the **Lambda Function URL** (`AgentFunctionUrl`) instead of the API Gateway URL. Lambda Function URLs allow requests to continue up to the full Lambda function timeout (configured at 300 seconds in `template.yaml`).

---

## 5. Frequently Asked Questions (FAQ)

### Q: Can I run Weather Buddy without any AWS account?
**A:** Yes! Run the local development server:
```bash
python run_local.py
```
This runs entirely on your local machine using Groq API keys with zero AWS dependencies.

### Q: How do I change the temperature from Celsius to Fahrenheit?
**A:** The frontend and agent dynamically respect user preferences. You can ask: *"What's the weather in Fahrenheit?"* or toggle units in the settings drawer.

### Q: How do I subscribe to daily weather email alerts?
**A:** Set the `AlertEmail` parameter during deployment (`sam deploy --guided`). AWS SNS will send a confirmation email. Click **Confirm subscription** in your inbox to begin receiving daily 7:00 AM weather alerts.

### Q: Can I host the LLM locally with Ollama?
**A:** Yes. Set the following environment variables in `.env`:
```env
LLM_MODEL_ID=openai/qwen2.5:7b-instruct
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
```
Weather Buddy's LiteLLM backend handles all formatting transparently.
