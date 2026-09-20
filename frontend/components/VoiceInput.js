import React, { useState, useEffect, useRef } from 'react';
import { Mic, Send, Square } from 'lucide-react';

export default function VoiceInput({ onTranscript, appState }) {
  const [isSupported, setIsSupported] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const [textInput, setTextInput] = useState("");
  const [isTranscribing, setIsTranscribing] = useState(false);
  
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

  const handleTranscription = async (audioBlob) => {
    setIsTranscribing(true);
    try {
      const reader = new FileReader();
      reader.readAsDataURL(audioBlob);
      reader.onloadend = async () => {
        const base64Audio = reader.result.split(',')[1];
        
        const API_URL = process.env.NEXT_PUBLIC_API_URL;
        const baseUrl = API_URL.replace('/query', '');
        const res = await fetch(`${baseUrl}/transcribe`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ audio_b64: base64Audio })
        });
        
        if (res.ok) {
          const data = await res.json();
          if (data.text) {
             onTranscript(data.text.trim(), data.language);
          }
        } else {
          console.error("Transcription failed", await res.text());
        }
        setIsTranscribing(false);
      };
    } catch (err) {
      console.error("Transcription error:", err);
      setIsTranscribing(false);
    }
  };

  const handleTextSubmit = (e) => {
    e.preventDefault();
    if (textInput.trim()) {
      onTranscript(textInput.trim());
      setTextInput("");
    }
  };

  const isProcessing = appState === 'processing';

  return (
    <div className="w-full flex flex-col items-center mt-4 mb-2 pb-4">
      {/* Transcribing indicator */}
      <div className="h-5 mb-2 text-center">
        {isTranscribing && (
          <span className="text-white/50 italic text-xs font-medium tracking-wide animate-pulse">
            Transcribing…
          </span>
        )}
      </div>

      <div className="relative flex justify-center items-center w-full max-w-2xl">
        
        {/* Chat bar — outer radius 20px */}
        <form 
          onSubmit={handleTextSubmit} 
          className={`flex w-full items-center bg-slate-900/90 
            transition-[border-color,box-shadow] duration-200
            rounded-[20px] pl-5 pr-2 py-2
            shadow-[0_2px_6px_rgba(0,0,0,0.2),0_8px_24px_rgba(0,0,0,0.15)]
            ${isListening 
              ? 'border border-red-500/40 shadow-[0_0_0_3px_rgba(239,68,68,0.12),0_2px_6px_rgba(0,0,0,0.2)]' 
              : 'border border-slate-700/60 hover:border-slate-600/80 focus-within:border-blue-500/40 focus-within:shadow-[0_0_0_3px_rgba(59,130,246,0.12),0_2px_6px_rgba(0,0,0,0.2)]'}
          `}
        >
          <input 
            type="text" 
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            disabled={isProcessing || isListening}
            placeholder={isSupported ? "Ask Weather Buddy…" : "Type your query…"}
            className="w-full bg-transparent text-white text-base outline-none 
              placeholder:text-slate-500/80 disabled:opacity-40
              transition-opacity duration-150"
          />
          
          <div className="flex items-center gap-1 pl-2">
            {/* Send — hit area ≥44px */}
            <button 
              type="submit" 
              disabled={!textInput.trim() || isProcessing || isListening}
              className="p-2.5 min-w-[44px] min-h-[44px] flex items-center justify-center
                text-slate-400 hover:text-white disabled:opacity-20 
                transition-[color,opacity] duration-150 press-scale"
              aria-label="Send message"
            >
              <Send className="w-[18px] h-[18px]" strokeWidth={1.5} />
            </button>
            
            {/* Mic — inner radius 12px (outer 20px - padding 8px) */}
            {isSupported && (
              <button
                type="button"
                onClick={toggleListen}
                disabled={isProcessing}
                className={`relative z-10 w-11 h-11 rounded-[12px] flex items-center justify-center
                  transition-[background-color,transform,box-shadow] duration-200 press-scale
                  ${isProcessing 
                    ? 'bg-slate-800 text-slate-500 cursor-not-allowed' 
                    : isListening 
                      ? 'bg-red-500 text-white shadow-[0_0_12px_rgba(239,68,68,0.4)]' 
                      : 'bg-blue-600 hover:bg-blue-500 text-white'}
                `}
                aria-label={isListening ? "Stop listening" : "Start voice input"}
              >
                {isProcessing || isTranscribing ? (
                  <div className="w-[18px] h-[18px] border-2 border-white/25 border-t-white rounded-full animate-spin"></div>
                ) : isListening ? (
                  <Square className="w-[18px] h-[18px] fill-current" strokeWidth={1.5} />
                ) : (
                  <Mic className="w-[18px] h-[18px]" strokeWidth={1.5} />
                )}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
