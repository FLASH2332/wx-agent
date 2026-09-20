import React from 'react';

export default function AppShell({ children, appState }) {
  return (
    <div className="min-h-screen w-full bg-slate-950 text-slate-50 font-sans selection:bg-blue-500/30 relative overflow-x-hidden">
      {/* Formal subtle grid background */}
      <div 
        className="absolute inset-0 pointer-events-none z-0 opacity-40" 
        style={{ 
          backgroundImage: 'radial-gradient(rgba(255, 255, 255, 0.1) 1px, transparent 1px)', 
          backgroundSize: '24px 24px' 
        }} 
      />
      
      <main className="w-full max-w-7xl mx-auto p-4 md:p-8 flex flex-col min-h-screen relative z-10">
        <div className="relative z-10 flex flex-col flex-grow">
          {children}
        </div>
      </main>
    </div>
  );
}
