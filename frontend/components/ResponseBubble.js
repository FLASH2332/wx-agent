import React, { useEffect, useState } from 'react';

export default function ResponseBubble({ text, lang, isLoading }) {
  const [displayedText, setDisplayedText] = useState("");

  useEffect(() => {
    if (isLoading) {
      setDisplayedText("");
      return;
    }

    if (text) {
      // Simple typewriter effect
      let i = 0;
      setDisplayedText("");
      const interval = setInterval(() => {
        setDisplayedText(text.substring(0, i));
        i++;
        if (i > text.length) clearInterval(interval);
      }, 15);
      return () => clearInterval(interval);
    }
  }, [text, isLoading]);

  if (!text && !isLoading) return null;

  return (
    <div className="mt-4 w-full">
      <div 
        className="glass-panel bg-white/5 border-l-4 border-l-blue-500 border-white/10 rounded-2xl p-4 shadow-lg min-h-[60px]"
        aria-live="polite"
        lang={lang}
      >
        {isLoading ? (
          <div className="flex flex-col gap-2">
            <div className="h-4 w-3/4 bg-white/10 rounded animate-pulse"></div>
            <div className="h-4 w-1/2 bg-white/10 rounded animate-pulse"></div>
          </div>
        ) : (
          <p className="text-white/90 text-sm leading-relaxed">
            {displayedText}
            {displayedText.length < (text || "").length && (
              <span className="inline-block w-1.5 h-4 ml-1 bg-blue-400 animate-pulse align-middle"></span>
            )}
          </p>
        )}
      </div>
    </div>
  );
}
