import React, { useEffect } from 'react';
import { AlertCircle, X } from 'lucide-react';

export default function ErrorToast({ message, onDismiss }) {
  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => {
        onDismiss();
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [message, onDismiss]);

  if (!message) return null;

  return (
    <div
      role="alert"
      className="fixed top-5 left-1/2 -translate-x-1/2 z-[60] w-11/12 max-w-md
        animate-fade-in-up"
    >
      <div className="bg-red-950/50 border border-red-500/20 text-red-100 
        px-4 py-3 rounded-[16px] flex items-start gap-3 
        shadow-[0_4px_12px_rgba(127,29,29,0.25),0_12px_32px_rgba(0,0,0,0.2)]
        backdrop-blur-xl">
        <AlertCircle className="w-5 h-5 text-red-400/90 mt-0.5 shrink-0" strokeWidth={1.5} />
        <div className="flex-1 text-sm leading-relaxed">{message}</div>
        <button 
          onClick={onDismiss}
          className="text-red-300/60 hover:text-white min-w-[36px] min-h-[36px]
            flex items-center justify-center -mr-2 -mt-1
            transition-[color] duration-150 press-scale"
          aria-label="Dismiss error"
        >
          <X className="w-4 h-4" strokeWidth={1.5} />
        </button>
      </div>
    </div>
  );
}
