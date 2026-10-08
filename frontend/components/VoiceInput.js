import React, { useState, useEffect, useRef } from 'react';
import { Mic, Square, Send } from 'lucide-react';
import SuggestionChips from './SuggestionChips';
import { transcribeAudio } from '@/lib/api';

export default function VoiceInput({ onTranscript, onError, appState }) {
  const [isSupported, setIsSupported] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [textInput, setTextInput] = useState("");
  
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  useEffect(() => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setIsSupported(false);
    }
  }, []);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        stream.getTracks().forEach(track => track.stop());
        await handleTranscription(audioBlob);
      };

      mediaRecorder.start();
      setIsListening(true);
    } catch (err) {
      console.error("Error accessing mic:", err);
      setIsSupported(false);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
      setIsListening(false);
    }
  };

  const toggleListen = () => {
    if (isListening) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const blobToBase64 = (blob) =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(String(reader.result).split(',')[1]);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });

  const handleTranscription = async (audioBlob) => {
    setIsTranscribing(true);
    try {
      const base64Audio = await blobToBase64(audioBlob);
      const data = await transcribeAudio(base64Audio, audioBlob.type || 'audio/webm');
      if (data.text) {
        onTranscript(data.text, data.language || "en");
      }
    } catch (err) {
      console.error("Transcription failed:", err);
      if (onError) onError(err.message || "Transcription failed.");
    } finally {
      setIsTranscribing(false);
    }
  };

  const handleTextSubmit = (e) => {
    e.preventDefault();
    if (textInput.trim()) {
      onTranscript(textInput.trim(), null);
      setTextInput("");
    }
  };

  const isProcessing = appState === 'processing';

  return (
    <div className="flex flex-col items-center gap-3 w-full pb-4">
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes waveform {
          0%, 100% { transform: scaleY(1); }
          50% { transform: scaleY(0.4); }
        }
        .animate-waveform {
          animation: waveform 0.8s ease-in-out infinite;
          transform-origin: center;
        }
      `}} />

      {/* Suggestion Chips */}
      <SuggestionChips onSelect={(text) => onTranscript(text, null)} />

      {/* Unified input bar: text + mic + send */}
      <form onSubmit={handleTextSubmit} className="w-full max-w-lg relative flex items-center">
        <input
          type="text"
          value={isListening ? "Listening…" : isTranscribing ? "Transcribing…" : textInput}
          onChange={(e) => setTextInput(e.target.value)}
          disabled={isProcessing || isListening || isTranscribing}
          placeholder="Type a message or tap the mic…"
          className="w-full bg-[#111] border border-white/10 rounded-full pl-5 pr-24 py-3.5
            text-white text-sm outline-none placeholder:text-white/30
            focus:border-white/20 transition-colors"
        />

        {/* Waveform inside bar — visible only while listening */}
        {isListening && (
          <div className="absolute right-16 flex items-center gap-0.5 h-4">
            {[...Array(5)].map((_, i) => (
              <div
                key={i}
                className="w-0.5 bg-blue-400 rounded-full animate-waveform"
                style={{ animationDelay: `${i * 0.12}s`, height: `${[6,10,14,10,6][i]}px` }}
              />
            ))}
          </div>
        )}

        {/* Mic button */}
        {isSupported && (
          <button
            type="button"
            onClick={toggleListen}
            disabled={isProcessing}
            className={`absolute right-11 top-1/2 -translate-y-1/2 p-1.5 rounded-full transition-all
              ${isListening
                ? 'text-red-400 hover:text-red-300'
                : isTranscribing
                  ? 'text-white/20 cursor-not-allowed'
                  : 'text-white/40 hover:text-white'}`}
            aria-label={isListening ? "Stop recording" : "Start voice input"}
          >
            {isTranscribing ? (
              <div className="w-4 h-4 border-2 border-white/20 border-t-white/60 rounded-full animate-spin" />
            ) : isListening ? (
              <Square size={16} className="fill-current" />
            ) : (
              <Mic size={16} />
            )}
          </button>
        )}

        {/* Send button */}
        <button
          type="submit"
          disabled={!textInput.trim() || isProcessing || isListening}
          className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-white/40 hover:text-white disabled:opacity-30 transition-colors"
        >
          <Send size={18} />
        </button>
      </form>
    </div>
  );
}
