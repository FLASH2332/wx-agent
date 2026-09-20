import React from 'react';
import { DEFAULT_SKY } from '../lib/skyTheme';

export default function AppShell({ children, footer, banner, sky = DEFAULT_SKY }) {
  return (
    <div
      className="h-screen w-full text-slate-50 font-sans selection:bg-white/20 relative overflow-hidden flex flex-col"
      style={{ background: sky.gradient, transition: 'background 900ms cubic-bezier(0.2,0,0,1)' }}
    >
      {/* Celestial glow — the sun or moon, tinted by the current sky */}
      <div
        className="absolute -top-32 right-[8%] w-[46vw] max-w-[560px] h-[46vw] max-h-[560px] rounded-full pointer-events-none z-0"
        style={{ background: `radial-gradient(circle, ${sky.glow} 0%, transparent 70%)`, transition: 'background 900ms ease' }}
      />
      {/* Horizon haze — a soft brightening toward the bottom, like distant light */}
      <div className="absolute inset-x-0 bottom-0 h-1/3 pointer-events-none z-0"
        style={{ background: 'linear-gradient(0deg, rgba(255,255,255,0.05), transparent)' }}
      />

      {banner && <div className="relative z-20 shrink-0">{banner}</div>}

      {/* Scrollable content — always above the footer, never behind it */}
      <main className="flex-1 min-h-0 overflow-y-auto hide-scrollbar relative z-10">
        <div className="w-full max-w-6xl mx-auto px-5 pt-6 pb-10 md:px-8 md:pt-8 flex flex-col">
          {children}
        </div>
      </main>

      {/* Docked input — flex-none, structurally below the content */}
      {footer && (
        <div className="relative z-30 shrink-0 border-t border-white/10 bg-black/25 backdrop-blur-2xl">
          {footer}
        </div>
      )}
    </div>
  );
}
