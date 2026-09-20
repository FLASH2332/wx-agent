import React from 'react';
import { getTranslation } from '../lib/i18n';

export default function HourlyTimeline({ hours = [], currentLang = 'en' }) {
  if (!hours || hours.length === 0) return null;

  const formatTime = (dt_txt) => {
    if (!dt_txt) return "Now";
    // dt_txt is typically "YYYY-MM-DD HH:mm:ss"
    const date = new Date(dt_txt.replace(' ', 'T') + 'Z');
    let h = date.getHours();
    const ampm = h >= 12 ? 'PM' : 'AM';
    h = h % 12;
    h = h ? h : 12; 
    return `${h} ${ampm}`;
  };

  return (
    <div className="w-full mt-6">
      <h3 className="text-white/80 font-semibold mb-3 px-1">{getTranslation(currentLang, 'today')}</h3>
      <div className="flex overflow-x-auto hide-scrollbar gap-3 pb-2 w-full">
        {hours.map((hour, idx) => (
          <div 
            key={idx} 
            className="flex flex-col items-center justify-between glass-panel bg-white/5 border border-white/5 rounded-2xl min-w-[70px] py-3 px-2 flex-shrink-0"
          >
            <span className="text-xs text-white/70 font-medium">
              {formatTime(hour.dt_txt)}
            </span>
            
            <div className="my-2 h-8 flex items-center justify-center">
              {hour.icon ? (
                <img 
                  src={`https://openweathermap.org/img/wn/${hour.icon}.png`}
                  alt={hour.description || "weather"}
                  className="w-8 h-8 object-contain"
                />
              ) : (
                <div className="w-6 h-6 bg-white/20 rounded-full animate-pulse"></div>
              )}
            </div>
            
            <span className="text-sm font-bold text-white">
              {hour.temp !== undefined ? Math.round(hour.temp) + '°' : '--'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
