import React, { useState, useEffect, useRef } from 'react';
import { Mic, Send, Square } from 'lucide-react';

export default function VoiceInput({ onTranscript, appState }) {
  const [isSupported, setIsSupported] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const [interimText, setInterimText] = useState("");
  const [textInput, setTextInput] = useState("");
  
  const recognitionRef = useRef(null);

  useEffect(() => {
    // Feature check
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setIsSupported(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US'; // We could dynamically set this based on previous turns

    recognition.onstart = () => setIsListening(true);
    
    recognition.onresult = (event) => {
      let finalStr = '';
      let interimStr = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalStr += event.results[i][0].transcript;
        } else {
          interimStr += event.results[i][0].transcript;
        }
      }
      setInterimText(interimStr);
      if (finalStr) {
        onTranscript(finalStr);
        setInterimText("");
      }
    };

    recognition.onerror = (event) => {
      console.error("Speech recognition error", event.error);
      setIsListening(false);
      setInterimText("");
    };

    recognition.onend = () => {
      setIsListening(false);
      setInterimText("");
    };

    recognitionRef.current = recognition;
  }, [onTranscript]);

  const toggleListen = () => {
    if (isListening) {
      recognitionRef.current?.stop();
    } else {
      recognitionRef.current?.start();
    }
  };

  const handleTextSubmit = (e) => {
    e.preventDefault();
    if (textInput.trim()) {
      onTranscript(textInput.trim());
      setTextInput("");
    }
  };

  // Determine mic button styles based on state
  const isProcessing = appState === 'processing';
  const showRings = isListening;

  return (
    <div className="w-full flex flex-col items-center mt-4 mb-2 pb-4">
      {/* Interim text display */}
      <div className="h-6 mb-2 text-center">
        {interimText && <span className="text-white/70 italic text-sm">{interimText}</span>}
      </div>

      <div className="relative flex justify-center items-center w-full max-w-2xl group">
        
        {/* Unified Chat Bar */}
        <form 
          onSubmit={handleTextSubmit} 
          className={`flex w-full items-center bg-slate-900 border transition-all duration-300 rounded-2xl shadow-lg pl-6 pr-2 py-2
            ${isListening ? 'border-red-500/50 shadow-[0_0_20px_rgba(239,68,68,0.2)]' : 'border-slate-700/80 hover:border-slate-600 focus-within:border-blue-500/60'}
          `}
        >
          <input 
            type="text" 
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            disabled={isProcessing || isListening}
            placeholder={isSupported ? "Ask Weather Buddy..." : "Type your query..."}
            className="w-full bg-transparent text-white text-lg outline-none placeholder:text-slate-500 disabled:opacity-50"
          />
          
          <div className="flex items-center space-x-1 pl-2">
            <button 
              type="submit" 
              disabled={!textInput.trim() || isProcessing || isListening}
              className="p-3 text-slate-400 hover:text-white disabled:opacity-30 transition-colors"
              aria-label="Send message"
            >
              <Send className="w-5 h-5" />
            </button>
            
            {/* The main mic button integrated inside the bar */}
            {isSupported && (
              <button
                type="button"
                onClick={toggleListen}
                disabled={isProcessing}
                className={`relative z-10 w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-300
                  ${isProcessing ? 'bg-slate-800 text-slate-400 cursor-not-allowed' : 
                    isListening ? 'bg-red-500 text-white shadow-[0_0_15px_rgba(239,68,68,0.5)] scale-105' : 
                    'bg-blue-600 hover:bg-blue-500 text-white hover:scale-105'}
                `}
                aria-label={isListening ? "Stop listening" : "Start voice input"}
              >
                {isProcessing ? (
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                ) : isListening ? (
                  <Square className="w-5 h-5 fill-current" />
                ) : (
                  <Mic className="w-5 h-5" />
                )}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
