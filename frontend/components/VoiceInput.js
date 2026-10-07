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
    <div className="flex flex-col items-center gap-6 w-full pt-8 pb-4">
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
      
      {/* Waveform Visualization (Static/Animated) */}
      <div className="flex items-center gap-1.5 h-6">
        {[...Array(6)].map((_, i) => (
          <div 
            key={i} 
            className={`w-1.5 bg-blue-500 rounded-full transition-all duration-300
              ${isListening ? 'animate-waveform bg-blue-400' : 'h-3 opacity-30 bg-blue-500/50'}`}
            style={isListening ? { animationDelay: `${i * 0.15}s`, height: `${Math.random() * 16 + 8}px` } : {}}
          />
        ))}
      </div>

      {/* Main Mic Button */}
      <div className="flex flex-col items-center gap-3">
        <button
          type="button"
          onClick={toggleListen}
          disabled={isProcessing || !isSupported}
          className={`relative z-10 w-20 h-20 rounded-full flex items-center justify-center
            transition-all duration-300 press-scale
            ${isProcessing 
              ? 'bg-[#1a1a1a] text-white/20 cursor-not-allowed border border-white/5' 
              : isListening 
                ? 'bg-red-500 text-white shadow-[0_0_32px_rgba(239,68,68,0.5)]' 
                : 'bg-[#1349a3] hover:bg-[#1a5bcc] text-white shadow-[0_0_24px_rgba(19,73,163,0.3)]'}
          `}
          aria-label={isListening ? "Stop listening" : "Start voice input"}
        >
          {isProcessing || isTranscribing ? (
            <div className="w-8 h-8 border-3 border-white/25 border-t-white rounded-full animate-spin"></div>
          ) : isListening ? (
            <Square className="w-8 h-8 fill-current" strokeWidth={2} />
          ) : (
            <Mic className="w-8 h-8" strokeWidth={2} />
          )}
        </button>
        <span className="text-sm font-medium text-white/50">
          {isListening ? "Listening..." : "Tap to speak"}
        </span>
      </div>

      {/* Suggestion Chips Below */}
      <SuggestionChips onSelect={(text) => onTranscript(text, null)} />

      {/* Text Fallback */}
      <form onSubmit={handleTextSubmit} className="w-full max-w-lg mt-4 relative">
        <input 
          type="text" 
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          disabled={isProcessing || isListening}
          placeholder="Or type a message..."
          className="w-full bg-[#111] border border-white/10 rounded-full pl-5 pr-12 py-3.5 
            text-white text-sm outline-none placeholder:text-white/30 
            focus:border-white/20 transition-colors"
        />
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
