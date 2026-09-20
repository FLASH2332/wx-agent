import React from 'react';

const LANG_MAP = {
  en: "English",
  hi: "हिन्दी",
  fr: "Français",
  de: "Deutsch",
  es: "Español",
  ta: "தமிழ்",
};

export default function LanguageBadge({ langCode }) {
  if (!langCode) return null;
  
  const displayName = LANG_MAP[langCode] || langCode.toUpperCase();

  return (
    <div 
      className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-white/10 text-white/90 border border-white/20 backdrop-blur-md shadow-sm transition-opacity duration-300"
      aria-label={`Detected language: ${displayName}`}
    >
      {displayName}
    </div>
  );
}
