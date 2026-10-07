# Weather Buddy — Real-Time Streaming & WebSocket Architecture Specification

This design document specifies the proposed real-time streaming protocol for Weather Buddy, supporting Server-Sent Events (SSE) and WebSocket bidirectional communication for token-by-token response streaming and chunked audio synthesis.

---

## 1. Streaming Protocol Overview

While Weather Buddy's baseline implementation operates over synchronous REST endpoints (`POST /query`), high-performance conversational agents benefit from progressive text reveals and chunked audio streaming:

```
Client (Next.js)                                  AWS Lambda / Streaming Gateway
       │                                                         │
       ├─ WebSocket Connect (wss://api.weatherbuddy.app/stream)─►│
       │                                                         ├─ Connection Established
       │◄─ 101 Switching Protocols ──────────────────────────────┘
       │
       ├─ Send Audio Chunk (Opus / WebM) ───────────────────────►│
       │                                                         ├─ Stream to Whisper API
       │◄─ Frame: {"type": "transcript_delta", "text": "Will"}───┤
       │◄─ Frame: {"type": "transcript_delta", "text": " it"}────┤
       │◄─ Frame: {"type": "transcript_delta", "text": " rain"}──┤
       │                                                         │
       │                                                         ├─ Tool Execution Triggered
       │◄─ Frame: {"type": "tool_start", "tool": "get_forecast"}─┤
       │◄─ Frame: {"type": "tool_end", "status": "success"}──────┤
       │                                                         │
       │                                                         ├─ LLM Token Stream Initiated
       │◄─ Frame: {"type": "text_delta", "text": "No"}───────────┤
       │◄─ Frame: {"type": "text_delta", "text": " rain"}────────┤
       │◄─ Frame: {"type": "text_delta", "text": " expected"}────┤
       │                                                         │
       │                                                         ├─ Polly Audio Chunk Streamed
       │◄─ Binary Frame: [Audio Chunk 1: MP3 Bytes]──────────────┤
       │◄─ Binary Frame: [Audio Chunk 2: MP3 Bytes]──────────────┤
       │◄─ Frame: {"type": "stream_end"}─────────────────────────┘
```

---

## 2. Server-Sent Events (SSE) Interface Specification

For environments where full duplex WebSockets are unnecessary, Server-Sent Events provide a lightweight unidirectional streaming path:

### Endpoint: `GET /stream/query`
- **Headers:**
  - `Accept: text/event-stream`
  - `Cache-Control: no-cache`
  - `Connection: keep-alive`

### Event Schema Definitions

#### 1. `event: transcript`
Fired when user speech transcription tokens become available.
```json
data: {"token": "¿Va a", "is_final": false}
data: {"token": " llover mañana?", "is_final": true, "lang": "es"}
```

#### 2. `event: tool_status`
Notifies client that a background weather query is executing.
```json
data: {"tool": "get_current_weather", "location": "Madrid, ES", "status": "executing"}
```

#### 3. `event: token`
Delivers progressive response text from LiteLLM.
```json
data: {"delta": "No se esperan", "turn_id": 1}
data: {"delta": " precipitaciones.", "turn_id": 1}
```

#### 4. `event: audio_chunk`
Streams sequential base64 audio packets.
```json
data: {"chunk_index": 0, "b64": "SUQzBAAAAAAA...", "is_last": false}
data: {"chunk_index": 1, "b64": "V0JbAAQAAAG...", "is_last": true}
```

---

## 3. Backpressure & Congestion Control

1. **Client Audio Buffer:** The Next.js frontend buffers up to 2 chunks of MP3 audio before initiating playback to prevent audio stuttering during transient network jitter.
2. **Heartbeats & Keepalive:** The streaming gateway emits ping frames every 15 seconds to prevent NAT gateway connection termination.
