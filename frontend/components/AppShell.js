import React from 'react';

export default function AppShell({ children, appState }) {
  return (
    <div className="min-h-screen w-full bg-slate-950 text-slate-50 font-sans selection:bg-blue-500/30 relative overflow-x-hidden">
      {/* Subtle dot-grid — opacity lowered for depth without noise */}
      <div 
        className="absolute inset-0 pointer-events-none z-0 opacity-[0.25]" 
        style={{ 
          backgroundImage: 'radial-gradient(rgba(255, 255, 255, 0.08) 1px, transparent 1px)', 
          backgroundSize: '28px 28px' 
        }} 
      />
      
      {/* Top-left ambient glow — grounds the eye on page load */}
      <div className="absolute -top-40 -left-40 w-[500px] h-[500px] rounded-full bg-blue-600/[0.06] blur-[120px] pointer-events-none z-0" />
      
      <main className="w-full max-w-7xl mx-auto px-4 py-6 md:px-8 md:py-8 flex flex-col min-h-screen relative z-10">
        <div className="relative z-10 flex flex-col flex-grow stagger-children">
          {children}
        </div>
      </main>
    </div>
  );
}
