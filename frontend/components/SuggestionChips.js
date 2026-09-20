import React from 'react';

export default function SuggestionChips({ onSelect }) {
  const SUGGESTIONS = [
    "Weather in my city",
    "5-day forecast for Tokyo",
    "Can I go hiking tomorrow?",
    "Any storm alerts in Florida?"
  ];

  return (
    <div className="flex flex-wrap items-center justify-center gap-2 mt-4">
      {SUGGESTIONS.map((text, idx) => (
        <button
          key={idx}
          onClick={() => onSelect(text)}
          className="text-xs lg:text-sm font-medium text-white/60 
            bg-white/[0.03] hover:bg-white/[0.07] 
            border border-white/[0.06] hover:border-white/[0.12]
            rounded-full px-4 py-2 
            transition-[background-color,border-color,transform] duration-150 
            press-scale"
        >
          {text}
        </button>
      ))}
    </div>
  );
}
