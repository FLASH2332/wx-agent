import React from 'react';
import { getTranslation } from '../lib/i18n';

export default function HourlyTimeline({ hours = [], currentLang = 'en' }) {
  if (!hours || hours.length === 0) return null;

  const formatTime = (dt_txt) => {
    if (!dt_txt) return "Now";
    const date = new Date(dt_txt.replace(' ', 'T') + 'Z');
    let h = date.getHours();
    const ampm = h >= 12 ? 'PM' : 'AM';
    h = h % 12;
    h = h ? h : 12; 
    return `${h} ${ampm}`;
  };

  return (
    <div className="w-full mt-6 animate-fade-in-up" style={{ animationDelay: '100ms' }}>
      <h3 className="text-white/70 font-semibold text-sm mb-3 px-1 tracking-wide">
        {getTranslation(currentLang, 'today')}
      </h3>
      <div className="flex overflow-x-auto hide-scrollbar gap-2.5 pb-2 w-full">
        {hours.map((hour, idx) => (
          <div 
            key={idx} 
            className="flex flex-col items-center justify-between
              bg-white/[0.03] border border-white/[0.05]
              rounded-[18px] min-w-[72px] py-3 px-2.5 flex-shrink-0
              shadow-[0_1px_3px_rgba(0,0,0,0.12),0_4px_12px_rgba(0,0,0,0.06)]
              transition-interactive hover:bg-white/[0.06] hover:border-white/[0.08]"
          >
            <span className="text-[11px] text-white/55 font-medium tabular-nums">
              {formatTime(hour.dt_txt)}
            </span>
            
            <div className="my-2 h-8 flex items-center justify-center">
              {hour.icon ? (
                <img 
                  src={`https://openweathermap.org/img/wn/${hour.icon}.png`}
                  alt={hour.description || "weather"}
                  className="w-8 h-8 object-contain"
                  loading="lazy"
                />
              ) : (
                <div className="w-6 h-6 bg-white/15 rounded-full animate-pulse"></div>
              )}
            </div>
            
            <span className="text-sm font-bold text-white tabular-nums">
              {hour.temp !== undefined ? Math.round(hour.temp) + '°' : '--'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
