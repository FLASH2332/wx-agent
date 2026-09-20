import React from 'react';

// Mirrors the real hero's left-aligned layout so nothing shifts when data lands.
export default function SkeletonCard() {
  return (
    <section className="animate-pulse" aria-busy="true" aria-hidden="true">
      {/* location */}
      <div className="h-4 w-40 bg-white/10 rounded-full" />

      {/* hero temperature + icon */}
      <div className="flex items-center gap-4 mt-3">
        <div className="h-24 lg:h-32 w-44 lg:w-60 bg-white/10 rounded-3xl" />
        <div className="w-20 h-20 lg:w-28 lg:h-28 bg-white/10 rounded-full" />
      </div>

      {/* condition + feels-like */}
      <div className="h-7 w-52 bg-white/10 rounded-full mt-4" />
      <div className="h-4 w-28 bg-white/[0.07] rounded-full mt-2" />

      {/* stat strip */}
      <div className="h-11 w-80 max-w-full bg-white/[0.06] rounded-full mt-6" />
    </section>
  );
}
