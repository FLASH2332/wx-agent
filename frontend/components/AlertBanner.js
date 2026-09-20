import React, { useState } from 'react';
import { TriangleAlert, X } from 'lucide-react';

export default function AlertBanner({ alerts = [] }) {
  const [dismissed, setDismissed] = useState(false);

  if (!alerts || alerts.length === 0 || dismissed) return null;

  // Assuming first alert is the most important
  const primaryAlert = alerts[0];

  return (
    <div role="alert" aria-live="assertive" className="mb-4 bg-gradient-to-r from-red-900/80 to-amber-900/80 border border-red-500/30 rounded-2xl p-3 flex items-start gap-3 shadow-lg shadow-red-900/20 animate-in fade-in slide-in-from-top-4">
      <TriangleAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
      <div className="flex-1 flex flex-col">
        <span className="text-sm font-bold text-red-100">{primaryAlert.title || "Weather Alert"}</span>
        <span className="text-xs text-red-200 mt-1 line-clamp-2">{primaryAlert.description || primaryAlert.note}</span>
      </div>
      <button 
        onClick={() => setDismissed(true)}
        className="text-red-300 hover:text-white p-1 -mr-1 -mt-1"
        aria-label="Dismiss alert"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
