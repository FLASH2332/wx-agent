import React from 'react';

export default function ChatHistory({ messages = [], currentLang = "en" }) {
  if (!messages || messages.length === 0) return null;

  return (
    <div className="flex flex-col gap-4 mt-4 mb-3" role="log" aria-live="polite">
      {messages.map((msg, idx) => {
        const isUser = msg.role === 'user';
        
        const textBlocks = (msg.content || []).filter(c => c.text);
        if (textBlocks.length === 0) return null;
        
        const textContent = textBlocks.map(c => c.text).join(" ");
        if (!textContent) return null;

        return (
          <div key={idx} className="flex w-full justify-start">
            <div 
              className={`w-full px-5 py-4 text-sm leading-relaxed border border-white/5 shadow-sm
                ${isUser ? 'bg-[#181818] rounded-[24px]' : 'bg-[#1a1a1a] rounded-[24px]'}
              `}
              lang={!isUser ? currentLang : undefined}
            >
              <div className="text-xs font-medium text-white/40 mb-2">
                {isUser ? "You said" : "Weather Buddy"}
              </div>
              <div className="text-white/90 text-[15px]">
                {textContent.split(/(\*\*.*?\*\*)/g).map((part, i) => {
                  if (part.startsWith('**') && part.endsWith('**')) {
                    return <strong key={i} className="font-semibold text-white">{part.slice(2, -2)}</strong>;
                  }
                  return part;
                })}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
