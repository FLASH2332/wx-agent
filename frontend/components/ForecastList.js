import React from 'react';
import { getTranslation } from '../lib/i18n';

export default function ForecastList({ days = [], currentLang = 'en' }) {
  if (!days || days.length === 0) return null;

  return (
    <div className="bg-white/[0.06] border border-white/10 rounded-[24px] p-5 backdrop-blur-md
      animate-fade-in-up" style={{ animationDelay: '200ms' }}>
      <h3 className="text-sm font-medium text-white/60 mb-4">
        Next 5 days
      </h3>
      
      <div className="flex flex-col gap-3">
        {days.map((day, i) => {
          const iconUrl = day.icon ? `https://openweathermap.org/img/wn/${day.icon}.png` : null;
          const dateObj = new Date(day.date);
          const dayName = dateObj.toLocaleDateString(currentLang, { weekday: 'short' });
          const isToday = i === 0;
          
          return (
            <div 
              key={i} 
              className={`flex items-center justify-between text-sm py-1.5 
                ${i < days.length - 1 ? 'border-b border-white/[0.04]' : ''}
                ${isToday ? 'text-white' : 'text-white/80'}`}
            >
              <span className="w-12 font-medium text-white/70 text-[13px]">
                {isToday ? getTranslation(currentLang, 'today') : dayName}
              </span>
              
              <div className="flex items-center gap-2 flex-1 justify-center">
                {iconUrl && <img src={iconUrl} alt={day.description} className="w-7 h-7" loading="lazy" />}
                {day.pop > 0 && (
                  <span className="text-[11px] text-blue-300/80 font-medium tabular-nums">
                    {Math.round(day.pop * 100)}%
                  </span>
                )}
              </div>
              
              <div className="flex items-center gap-3 w-20 justify-end tabular-nums">
                <span className="text-white font-semibold text-[13px]">{Math.round(day.temp_max)}°</span>
                <span className="text-white/35 text-[13px]">{Math.round(day.temp_min)}°</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
