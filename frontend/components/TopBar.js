import React, { useState, useEffect } from 'react';
import { Search, Globe } from 'lucide-react';
import { getTranslation } from '../lib/i18n';

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
  
  const hasCurrentLang = LANG_OPTIONS.some(opt => opt.code === currentLang);
  const optionsToRender = hasCurrentLang 
    ? LANG_OPTIONS 
    : [...LANG_OPTIONS, { code: currentLang, label: `Detected (${currentLang})` }];

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (searchInput.trim()) {
      onLocationSearch(searchInput.trim());
      setSearchInput('');
    }
  };

  return (
    <header className="flex flex-col md:flex-row justify-between items-center gap-4 mb-6 w-full
      bg-white/[0.03] border border-white/[0.06] px-5 py-3.5 rounded-[22px]
      shadow-[0_1px_3px_rgba(0,0,0,0.12),0_4px_16px_rgba(0,0,0,0.08)]
      transition-interactive">
      <div className="flex items-center gap-2">
        <h1 className="text-xl lg:text-2xl font-semibold tracking-tight text-white/90">
          {greeting}!
          <span className="text-base lg:text-lg font-normal text-white/45 ml-2">
            {getTranslation(currentLang, 'weatherBuddy')}
          </span>
        </h1>
      </div>

      <div className="flex items-center gap-3 w-full md:w-auto">
        {/* Search — concentric radius: outer 22px, input 14px, padding ~8px */}
        <form onSubmit={handleSearchSubmit} className="relative flex-1 md:w-60">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/35" strokeWidth={1.5} />
          <input 
            type="text"
            placeholder={getTranslation(currentLang, 'searchPlaceholder')}
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-full bg-black/20 border border-white/[0.06] rounded-[14px] py-2 pl-9 pr-4 
              text-sm text-white placeholder:text-white/30 
              outline-none transition-[border-color,box-shadow] duration-200
              focus:border-white/20 focus:shadow-[0_0_0_3px_rgba(59,130,246,0.15)]"
          />
        </form>

        {/* Language selector */}
        <div className="relative flex items-center bg-black/20 border border-white/[0.06] rounded-[14px] px-3 py-2 
          cursor-pointer transition-[background-color,border-color] duration-150 hover:bg-black/30 hover:border-white/10">
          <Globe className="w-4 h-4 text-white/40 mr-2" strokeWidth={1.5} />
          <select 
            value={currentLang}
            onChange={(e) => onLangChange(e.target.value)}
            className="appearance-none bg-transparent text-sm font-medium text-white/85 outline-none cursor-pointer pr-4"
          >
            {optionsToRender.map(opt => (
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
