# Weather Buddy — React Component Lifecycle & Hydration Specification

This document details the frontend component architecture, client-side rendering strategies, hydration mechanics, and Web Audio context lifecycles for Weather Buddy's **Next.js 14** application.

---

## 1. Client-Side Rendering Strategy

Because Weather Buddy relies heavily on browser hardware interfaces (the `MediaRecorder` API, Web Audio API `AudioContext`, and Geolocation API), all interactive dashboard views operate as Client Components (`"use client"`).

```
                            Server Shell (Root Layout)
                                       │
                                       ▼
                       Client Component Boundary (AppShell)
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
   [TopBar & Search]           [Dashboard Visuals]           [Voice & Chat Bar]
   • Geolocation Sensor        • WeatherCard (Temp/Wind)     • MediaRecorder Audio
   • i18n Dropdown             • HourlyTimeline (Horizontal) • Polly AudioContext
   • Search Input              • ForecastList (5-Day)        • Typewriter Bubble
```

---

## 2. Audio Subsystem Lifecycle & Web Audio Context

Browser security standards require explicit user activation before sound can play. The audio subsystem in `frontend/components/AudioPlayer.js` follows a strict initialization state machine:

```
[DOM Mount]
    │
    ▼
[AudioContext Created (Suspended State)]
    │
    ├─ User Interacts (Click Mic / Send) ──► AudioContext.resume() (State: Running)
    │
    ▼
[Audio Payload Ingested (Base64 MP3)]
    │
    ├─ atob() String Decoded to Uint8Array Buffer
    │
    ▼
[AudioContext.decodeAudioData()]
    │
    ├─ PCM Audio Buffer Generated
    │
    ▼
[AudioBufferSourceNode Created]
    │
    ├─ Connect to AnalyserNode (60 FPS Fast Fourier Transform Visualizer)
    ├─ Connect to GainNode (Volume Control)
    ├─ Connect to AudioDestination (Speakers)
    │
    ▼
[SourceNode.start(0) -> Playback Commences]
    │
    ▼
[onended Event -> Reset Playback State to IDLE]
```

---

## 3. Real-Time Typewriter Reveal Engine

To provide visual responsiveness while synthesized audio plays, `ResponseBubble.js` implements a variable-speed typewriter animation algorithm:

```typescript
interface TypewriterOptions {
  text: string;
  speedMs?: number;
  onComplete?: () => void;
}

export function useTypewriter({ text, speedMs = 18, onComplete }: TypewriterOptions) {
  const [displayedText, setDisplayedText] = useState("");
  const [isFinished, setIsFinished] = useState(false);

  useEffect(() => {
    let index = 0;
    setDisplayedText("");
    setIsFinished(false);

    const interval = setInterval(() => {
      if (index < text.length) {
        setDisplayedText((prev) => prev + text.charAt(index));
        index++;
      } else {
        clearInterval(interval);
        setIsFinished(true);
        if (onComplete) onComplete();
      }
    }, speedMs);

    return () => clearInterval(interval);
  }, [text, speedMs]);

  return { displayedText, isFinished };
}
```

---

## 4. Component Tree & Property Binding

| Component | File Path | Ingested Props | Emitted Events |
|-----------|-----------|----------------|----------------|
| `AppShell` | `frontend/components/AppShell.js` | `children` | None |
| `TopBar` | `frontend/components/TopBar.js` | `selectedLang`, `onSearch`, `onLocate` | `onLanguageChange`, `onCitySearch` |
| `WeatherCard` | `frontend/components/WeatherCard.js` | `data: WeatherData`, `lang: string` | None |
| `HourlyTimeline`| `frontend/components/HourlyTimeline.js`| `hourly: Array<Slice>` | `onHourSelect` |
| `ForecastList` | `frontend/components/ForecastList.js` | `forecast: Array<Day>` | None |
| `AlertBanner` | `frontend/components/AlertBanner.js` | `alert: WeatherAlert` | `onDismiss` |
| `VoiceInput` | `frontend/components/VoiceInput.js` | `onSend`, `isProcessing` | `onRecordStart`, `onRecordEnd` |
| `ChatHistory` | `frontend/components/ChatHistory.js` | `messages: Array<Msg>` | `onPlayAudio` |
| `ResponseBubble`| `frontend/components/ResponseBubble.js`| `message: Msg`, `isLatest` | `onTypewriterEnd` |
| `AudioPlayer` | `frontend/components/AudioPlayer.js` | `audioB64: string` | `onEnded`, `onPlay` |
| `LanguageBadge`| `frontend/components/LanguageBadge.js`| `langCode: string` | None |
