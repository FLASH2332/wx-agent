import React from 'react';

export default function ActivityChips({ onSelect }) {
  const activities = [
    { label: "Hiking" },
    { label: "Beach" },
    { label: "Cycling" },
    { label: "Photography" }
  ];

  return (
    <div className="flex items-center gap-2 mb-4 overflow-x-auto hide-scrollbar">
      {activities.map((activity, idx) => (
        <button
          key={idx}
          onClick={() => onSelect(activity.label)}
          className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-colors whitespace-nowrap
            ${idx === 0 
              ? 'bg-blue-600/20 text-blue-400 border-blue-500/30' 
              : 'bg-transparent text-white/70 border-white/10 hover:bg-white/5 hover:text-white'}
          `}
        >
          {activity.label}
        </button>
      ))}
    </div>
  );
}
