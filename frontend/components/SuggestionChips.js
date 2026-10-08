import React from 'react';

export default function SuggestionChips({ onSelect }) {
  const SUGGESTIONS = [
    "Will it rain today?",
    "Compare Goa and Coorg",
    "Is it good for cycling?"
  ];

  return (
    <div className="flex flex-wrap items-center justify-center gap-2 mt-4">
      {SUGGESTIONS.map((text, idx) => (
        <button
          key={idx}
          onClick={() => onSelect(text)}
          className="text-sm font-medium text-white/60 
            bg-[#1a1a1a] hover:bg-[#252525] 
            border border-white/5 hover:border-white/10
            rounded-full px-5 py-2.5
            transition-[background-color,border-color,transform] duration-150 
            press-scale"
        >
          {text}
        </button>
      ))}
    </div>
  );
}
