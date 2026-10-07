# Weather Buddy — Audio Engineering, Codecs & Visualizer Mathematics

This specification documents the audio processing pipeline in Weather Buddy, detailing microphone stream ingestion, container negotiation, Fast Fourier Transform (FFT) visualizer mathematics, and neural voice synthesis decoding.

---

## 1. Browser Audio Capture Pipeline

Browser audio recording utilizes the HTML5 **MediaStream Recording API** (`MediaRecorder`). To support cross-platform browser variations, Weather Buddy negotiates audio container formats at runtime:

```
┌─────────────────────────────────┐
│     User Microphone Input       │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│     MIME Type Negotiation       │
│     1. audio/webm;codecs=opus   │ (Chrome, Edge, Firefox - Preferred)
│     2. audio/webm               │ (Generic WebM container)
│     3. audio/mp4                │ (Safari iOS / macOS fallback)
│     4. audio/ogg                │ (Legacy browser fallback)
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│   MediaStream Audio Track       │
│   • Sample Rate: 48,000 Hz      │
│   • Channel Count: 1 (Mono)     │
│   • Echo Cancellation: True     │
│   • Noise Suppression: True     │
│   • Auto Gain Control: True     │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│      Blob Chunk Buffer          │  ◄── ondataavailable Event
│      (Uint8Array Stream)        │      Aggregates binary audio slices
└─────────────────────────────────┘
```

---

## 2. Real-Time Audio Visualizer Mathematics

When speech is recorded or played back, `AudioPlayer.js` and `VoiceInput.js` render a 60 FPS frequency visualizer using the browser's Web Audio API **`AnalyserNode`**.

### 2.1 Fast Fourier Transform (FFT) Analysis
The `AnalyserNode` computes the discrete Fourier transform of the time-domain audio signal:

$$X(k) = \sum_{n=0}^{N-1} x(n) \cdot e^{-i 2\pi k n / N}, \quad k = 0, \dots, N-1$$

Where:
- $N = 64$: FFT size (`analyser.fftSize = 64`), yielding 32 discrete frequency bins (`frequencyBinCount`).
- $x(n)$: Discrete time-domain audio sample amplitudes.
- $X(k)$: Complex frequency-domain representation.

### 2.2 Decibel Normalization & Smoothing
Raw frequency data is converted into normalized bar heights ($h \in [0, 1]$):

$$h_k = \frac{\text{dataArray}[k] - \text{minDecibels}}{\text{maxDecibels} - \text{minDecibels}}$$

With a temporal smoothing time constant of $\alpha = 0.8$ (`analyser.smoothingTimeConstant = 0.8`) to prevent visual jitter.

---

## 3. Audio Decoding & Amazon Polly Synthesis Stream

When the agent responds, audio arrives as a Base64-encoded MP3 string. The client decodes and mounts the stream into hardware speakers:

```javascript
export async function playBase64Audio(base64String, audioContext) {
  // 1. Decode Base64 string to raw binary string
  const binaryString = atob(base64String);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }

  // 2. Decode MP3 binary buffer into PCM AudioBuffer
  const audioBuffer = await audioContext.decodeAudioData(bytes.buffer);

  // 3. Mount buffer to AudioBufferSourceNode
  const sourceNode = audioContext.createBufferSource();
  sourceNode.buffer = audioBuffer;

  // 4. Route through AnalyserNode to Speakers
  const analyser = audioContext.createAnalyser();
  sourceNode.connect(analyser);
  analyser.connect(audioContext.destination);

  // 5. Trigger hardware playback
  sourceNode.start(0);
}
```

---

## 4. Bandwidth & Payload Optimization

| Component | Raw Uncompressed PCM | Transmitted Stream | Compression Ratio | Average Turn Payload |
|-----------|:--------------------:|:------------------:|:-----------------:|:--------------------:|
| **Voice Input (WebM Opus)** | 48 kHz / 16-bit Mono (768 kbps) | 32 kbps VBR Opus | **24 : 1** | ~12 KB (3s speech) |
| **TTS Output (Polly MP3)** | 22.05 kHz / 16-bit Mono (352 kbps) | 48 kbps CBR MP3 | **7.3 : 1** | ~28 KB (5s speech) |
