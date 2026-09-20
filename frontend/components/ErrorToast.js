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
      className="fixed bottom-24 left-1/2 transform -translate-x-1/2 z-50 w-11/12 max-w-sm animate-in slide-in-from-bottom-5 fade-in duration-300"
    >
      <div className="glass-panel bg-red-950/40 border-red-500/30 text-red-100 px-4 py-3 rounded-lg flex items-start gap-3 shadow-lg shadow-red-900/20">
        <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 shrink-0" />
        <div className="flex-1 text-sm">{message}</div>
        <button 
          onClick={onDismiss}
          className="text-red-300 hover:text-white transition-colors p-1 -mr-2 -mt-1"
          aria-label="Dismiss error"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
