import React from 'react';

export default function SkeletonCard() {
  return (
    <div 
      className="rounded-[28px] p-6 lg:p-8 bg-white/[0.03] border border-white/[0.05]
        shadow-[0_2px_4px_rgba(0,0,0,0.12),0_8px_24px_rgba(0,0,0,0.08)]
        animate-pulse flex flex-col items-center w-full min-h-[260px]" 
      aria-busy="true" 
      aria-hidden="true"
    >
      <div className="h-5 w-28 bg-white/[0.06] rounded-full mb-8"></div>
      
      <div className="flex items-center justify-center gap-5 mb-8">
        <div className="w-20 h-20 bg-white/[0.06] rounded-full"></div>
        <div className="h-20 w-24 bg-white/[0.06] rounded-[16px]"></div>
      </div>
      
      {/* Inner panel — concentric: outer 28px, inner 20px */}
      <div className="w-full h-20 bg-black/[0.08] rounded-[20px] border border-white/[0.03] mt-auto"></div>
    </div>
  );
}
