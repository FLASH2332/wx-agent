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
      className="max-w-xl w-full bg-gradient-to-r from-red-900/60 to-amber-900/60
        border border-red-500/20 rounded-2xl px-4 py-2.5
        flex items-center gap-2.5
        shadow-[0_2px_12px_rgba(127,29,29,0.25)]
        animate-fade-in-up"
    >
      <TriangleAlert className="w-4 h-4 text-amber-400/90 shrink-0" strokeWidth={1.5} />
      <div className="flex-1 min-w-0">
        <span className="text-xs font-semibold text-red-100/90">{primaryAlert.event || "Weather Alert"}</span>
        <span className="text-xs text-red-200/60 ml-2 line-clamp-1">
          {primaryAlert.description || primaryAlert.note}
        </span>
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="text-red-300/50 hover:text-white/80 p-1 rounded transition-colors shrink-0"
        aria-label="Dismiss alert"
      >
        <X className="w-3.5 h-3.5" strokeWidth={1.5} />
      </button>
    </div>
  );
}
