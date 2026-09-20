import React, { useState, useEffect } from 'react';
import { Search, Globe } from 'lucide-react';

const GREETINGS = {
  en: "Good Day",
  hi: "शुभ दिन",
  fr: "Bonjour",
  de: "Guten Tag",
  es: "Buenos Días",
  ta: "நல்ல நாள்"
};

const LANG_OPTIONS = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'हिन्दी' },
  { code: 'fr', label: 'Français' },
  { code: 'de', label: 'Deutsch' },
  { code: 'es', label: 'Español' },
  { code: 'ta', label: 'தமிழ்' }
];

export default function TopBar({ currentLang, onLangChange, onLocationSearch }) {
  const [searchInput, setSearchInput] = useState('');
  const greeting = GREETINGS[currentLang] || GREETINGS['en'];

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (searchInput.trim()) {
      onLocationSearch(searchInput.trim());
      setSearchInput('');
    }
  };

  return (
    <header className="flex flex-col md:flex-row justify-between items-center gap-4 mb-8 w-full glass-panel bg-white/5 px-6 py-4 rounded-3xl border-white/10 shadow-lg">
      <div className="flex items-center gap-2">
        <h1 className="text-2xl font-bold tracking-tight text-white/90">
          {greeting}! <span className="text-xl font-normal text-white/60 ml-2">Weather Buddy</span>
        </h1>
      </div>

      <div className="flex items-center gap-4 w-full md:w-auto">
        {/* Manual Location Search */}
        <form onSubmit={handleSearchSubmit} className="relative flex-1 md:w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/50" />
          <input 
            type="text"
            placeholder="Search location..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-full bg-black/20 border border-white/10 rounded-full py-2 pl-9 pr-4 text-sm text-white placeholder:text-white/40 focus:outline-none focus:border-white/30 transition-colors"
          />
        </form>

        {/* Language Selector */}
        <div className="relative flex items-center bg-black/20 border border-white/10 rounded-full px-3 py-2 cursor-pointer hover:bg-black/30 transition-colors">
          <Globe className="w-4 h-4 text-white/50 mr-2" />
          <select 
            value={currentLang}
            onChange={(e) => onLangChange(e.target.value)}
            className="appearance-none bg-transparent text-sm font-medium text-white/90 outline-none cursor-pointer pr-4"
          >
            {LANG_OPTIONS.map(opt => (
              <option key={opt.code} value={opt.code} className="bg-slate-900 text-white">
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </header>
  );
}
