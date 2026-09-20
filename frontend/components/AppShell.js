import React from 'react';

export default function AppShell({ children, appState }) {
  return (
    <div className="min-h-screen w-full bg-slate-950 text-slate-50 font-sans selection:bg-blue-500/30 relative">
      {/* Formal subtle grid background instead of glowing AI blobs */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#4f4f4f15_1px,transparent_1px),linear-gradient(to_bottom,#4f4f4f15_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_80%_50%_at_50%_0%,#000_70%,transparent_100%)] pointer-events-none z-0"></div>
      
      <main className="w-full max-w-7xl mx-auto p-4 md:p-8 flex flex-col min-h-screen relative z-10">
        <div className="relative z-10 flex flex-col flex-grow">
          {children}
        </div>
      </main>
    </div>
  );
}
