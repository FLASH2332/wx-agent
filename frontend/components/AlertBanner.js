import React, { useState } from 'react';
import { TriangleAlert, X } from 'lucide-react';

export default function AlertBanner({ alerts = [] }) {
  const [dismissed, setDismissed] = useState(false);

  if (!alerts || alerts.length === 0 || dismissed) return null;

  const primaryAlert = alerts[0];

  return (
    <div 
      role="alert" 
      aria-live="assertive" 
      className="mb-4 bg-gradient-to-r from-red-900/60 to-amber-900/60 
        border border-red-500/20 rounded-[18px] p-3.5 
        flex items-start gap-3 
        shadow-[0_2px_8px_rgba(127,29,29,0.2),0_8px_24px_rgba(0,0,0,0.12)]
        animate-fade-in-up"
    >
      {/* Optical alignment: icon nudged down 2px to sit with first line of text */}
      <TriangleAlert className="w-5 h-5 text-amber-400/90 shrink-0 mt-0.5" strokeWidth={1.5} />
      <div className="flex-1 flex flex-col gap-1">
        <span className="text-sm font-semibold text-red-100/90">{primaryAlert.event || "Weather Alert"}</span>
        <span className="text-xs text-red-200/70 line-clamp-2 leading-relaxed">
          {primaryAlert.description || primaryAlert.note}
        </span>
      </div>
      {/* Dismiss — min 44px hit area */}
      <button 
        onClick={() => setDismissed(true)}
        className="text-red-300/70 hover:text-white min-w-[36px] min-h-[36px] 
          flex items-center justify-center -mr-1 -mt-0.5
          transition-[color] duration-150 press-scale"
        aria-label="Dismiss alert"
      >
        <X className="w-4 h-4" strokeWidth={1.5} />
      </button>
    </div>
  );
}
