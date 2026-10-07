// Plays the result of POST /tts: server audio (Polly) or the browser's own voices.
const LOCALES = { en: "en-US", hi: "hi-IN", fr: "fr-FR", de: "de-DE", es: "es-ES", ta: "ta-IN" };

let currentAudio = null;

export function stopSpeech() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
}

export function playSpeech(result) {
  stopSpeech();
  if (!result || result.mode === "none") return;

  if (result.mode === "polly" && result.audio_b64) {
    currentAudio = new Audio(`data:${result.mime || "audio/mpeg"};base64,${result.audio_b64}`);
    currentAudio.play().catch((e) => console.warn("Audio playback blocked", e));
  } else if (result.mode === "browser" && typeof window !== "undefined" && "speechSynthesis" in window) {
    const utterance = new SpeechSynthesisUtterance(result.text);
    utterance.lang = LOCALES[result.lang] || result.lang || "en-US";
    window.speechSynthesis.speak(utterance);
  }
}
