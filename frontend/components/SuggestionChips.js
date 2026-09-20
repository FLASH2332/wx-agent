import React from 'react';

const SUGGESTIONS = [
  "Weather in my city",
  "5-day forecast for Tokyo",
  "Can I go hiking tomorrow?",
  "Any storm alerts in Florida?"
];

export default function SuggestionChips({ onSelect }) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2 mt-4">
      {SUGGESTIONS.map((text, idx) => (
        <button
          key={idx}
          onClick={() => onSelect(text)}
          className="text-xs lg:text-sm font-medium text-white/70 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 rounded-full px-4 py-2 transition-all duration-200 backdrop-blur-sm shadow-sm"
        >
          {text}
        </button>
      ))}
    </div>
  );
}
