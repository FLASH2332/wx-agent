import React from 'react';

export default function SkeletonCard() {
  return (
    <div className="glass-panel rounded-3xl p-6 bg-white/5 border-white/10 shadow-2xl animate-pulse flex flex-col items-center w-full min-h-[250px]" aria-busy="true" aria-hidden="true">
      <div className="h-6 w-32 bg-white/10 rounded-full mb-8"></div>
      
      <div className="flex items-center justify-center gap-4 mb-8">
        <div className="w-20 h-20 bg-white/10 rounded-full"></div>
        <div className="h-20 w-24 bg-white/10 rounded-2xl"></div>
      </div>
      
      <div className="w-full h-20 bg-black/10 rounded-2xl border border-white/5 mt-auto"></div>
    </div>
  );
}
