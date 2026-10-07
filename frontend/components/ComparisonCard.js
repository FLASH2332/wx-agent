import React from 'react';
import { Check } from 'lucide-react';

export default function ComparisonCard({ data }) {
  if (!data || !data.locations || data.locations.length < 2) return null;

  const [loc1, loc2] = data.locations;
  const winner = (data.winner || '').trim();
  const hasScore = (loc) => typeof loc.score === 'number';

  // Determine progress bar colors based on score
  const getScoreColor = (score) => {
    if (score >= 8) return 'bg-emerald-500';
    if (score >= 5) return 'bg-amber-500';
    return 'bg-red-500';
  };

  const getScoreBg = (score) => {
    if (score >= 8) return 'bg-emerald-950/30 text-emerald-400 border-emerald-900/50';
    if (score >= 5) return 'bg-amber-950/30 text-amber-400 border-amber-900/50';
    return 'bg-red-950/30 text-red-400 border-red-900/50';
  };

  return (
    <div className="w-full flex flex-col gap-6 animate-fade-in-up" style={{ animationDelay: '100ms' }}>
      
      {/* Side-by-side comparison */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 relative">
        
        {/* VS Badge (visible on desktop) */}
        <div className="hidden md:flex absolute left-1/2 top-8 -translate-x-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-[#1A1A1A] border border-white/10 items-center justify-center text-xs text-white/50 z-10">
          vs
        </div>

        {[loc1, loc2].map((loc, idx) => {
          const isWinner = winner !== '' && (loc.name || '').toLowerCase().includes(winner.toLowerCase());
          
          return (
            <div 
              key={idx}
              className={`p-6 rounded-[28px] border transition-all duration-300 flex flex-col gap-6 ${
                isWinner 
                  ? 'bg-[#141414] border-white/20 shadow-lg shadow-white/5' 
                  : 'bg-[#111] border-white/5 opacity-80 hover:opacity-100'
              }`}
            >
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="text-xl font-medium text-white/90">{loc.name}</h3>
                  {isWinner && (
                    <span className="inline-flex items-center gap-1 mt-1 text-xs font-medium text-emerald-400 bg-emerald-950/50 px-2 py-0.5 rounded-full border border-emerald-900/50">
                      <Check size={12} /> Winner
                    </span>
                  )}
                </div>
              </div>

              <div>
                <div className="text-5xl font-light text-white tracking-tight tabular-nums">
                  {loc.temp}
                </div>
                <div className="text-white/60 text-sm mt-2 font-medium">
                  {loc.condition}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-y-6 gap-x-4">
                {[
                  ['Rain chance', loc.rain_chance],
                  ['UV index', loc.uv_index],
                  ['Wind', loc.wind],
                  ['Humidity', loc.humidity],
                ].filter(([, value]) => value && String(value).trim().toLowerCase() !== 'n/a').map(([label, value]) => (
                  <div key={label}>
                    <div className="text-xs text-white/40 mb-1">{label}</div>
                    <div className="text-sm font-medium text-white/80">{value}</div>
                  </div>
                ))}
              </div>

              <div className="mt-auto pt-4 border-t border-white/5 flex flex-col gap-3">
                {hasScore(loc) && (<>
                <div className="flex justify-between text-sm">
                  <span className="text-white/60">Score</span>
                  <span className="text-white/90 font-medium">{loc.score}/10</span>
                </div>
                <div className="h-1.5 w-full bg-white/10 rounded-full overflow-hidden">
                  <div 
                    className={`h-full rounded-full ${getScoreColor(loc.score)}`} 
                    style={{ width: `${(loc.score / 10) * 100}%` }}
                  />
                </div>
                </>)}
                {loc.score_reasoning && loc.score_reasoning.trim().toLowerCase() !== 'n/a' && (
                  <div className={`p-4 mt-2 rounded-[20px] text-sm leading-relaxed border ${hasScore(loc) ? getScoreBg(loc.score) : 'bg-white/[0.04] text-white/70 border-white/10'}`}>
                    {loc.score_reasoning}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Full width winner reasoning */}
      {(winner || data.winner_reasoning) && (
        <div className="p-6 rounded-[28px] bg-[#141414] border border-white/10 shadow-xl">
          <h4 className="text-sm font-medium text-white/90 mb-2">{winner ? `Why ${winner} wins:` : 'Summary'}</h4>
          <p className="text-sm text-white/70 leading-relaxed">
            {data.winner_reasoning}
          </p>
        </div>
      )}
    </div>
  );
}
