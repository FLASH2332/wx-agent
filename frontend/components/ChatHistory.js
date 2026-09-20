import React from 'react';

export default function ChatHistory({ messages = [], currentLang = "en" }) {
  if (!messages || messages.length === 0) return null;

  return (
    <div className="flex flex-col gap-4 mt-6 mb-4 overflow-y-auto max-h-64 pr-2 hide-scrollbar" role="log" aria-live="polite">
      {messages.map((msg, idx) => {
        const isUser = msg.role === 'user';
        
        // Extract text from Bedrock Converse format
        const textBlocks = (msg.content || []).filter(c => c.text);
        if (textBlocks.length === 0) return null; // hide pure tool-call turns visually if we want
        
        const textContent = textBlocks.map(c => c.text).join(" ");
        
        if (!textContent) return null;

        return (
          <div key={idx} className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}>
            <div 
              className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-sm shadow-sm
                ${isUser 
                  ? 'bg-blue-600/90 text-white rounded-tr-sm' 
                  : 'glass-panel bg-white/10 text-white/90 rounded-tl-sm border border-white/10'}
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
