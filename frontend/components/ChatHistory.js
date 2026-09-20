import React from 'react';

export default function ChatHistory({ messages = [], currentLang = "en" }) {
  if (!messages || messages.length === 0) return null;

  return (
    <div className="flex flex-col gap-3 mt-4 mb-3 overflow-y-auto max-h-64 pr-2 hide-scrollbar" role="log" aria-live="polite">
      {messages.map((msg, idx) => {
        const isUser = msg.role === 'user';
        
        const textBlocks = (msg.content || []).filter(c => c.text);
        if (textBlocks.length === 0) return null;
        
        const textContent = textBlocks.map(c => c.text).join(" ");
        if (!textContent) return null;

        return (
          <div key={idx} className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}>
            <div 
              className={`max-w-[85%] px-4 py-2.5 text-sm leading-relaxed
                shadow-[0_1px_3px_rgba(0,0,0,0.12)]
                ${isUser 
                  ? 'bg-blue-600/80 text-white rounded-[16px] rounded-tr-[4px]' 
                  : 'bg-white/[0.06] text-white/85 rounded-[16px] rounded-tl-[4px] border border-white/[0.06]'}
              `}
              lang={!isUser ? currentLang : undefined}
            >
              {textContent}
            </div>
          </div>
        );
      })}
    </div>
  );
}
