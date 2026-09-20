import React from 'react';
import { getTranslation } from '../lib/i18n';

export default function HourlyTimeline({ hours = [], currentLang = 'en' }) {
  if (!hours || hours.length === 0) return null;

  const formatTime = (dt_txt) => {
    if (!dt_txt) return 'Now';
    const date = new Date(dt_txt.replace(' ', 'T') + 'Z');
    let h = date.getHours();
    const ampm = h >= 12 ? 'PM' : 'AM';
    h = h % 12;
    h = h ? h : 12;
    return `${h} ${ampm}`;
  };

  return (
    <div className="w-full mt-8 animate-fade-in-up" style={{ animationDelay: '100ms' }}>
      <h3 className="text-white/60 font-medium text-sm mb-3 px-1">
        {getTranslation(currentLang, 'today')}
      </h3>

      {/* One continuous rail — the panel is the container; hours are borderless
          columns separated by hairline dividers, not repeated identical cards. */}
      <div className="flex overflow-x-auto hide-scrollbar rounded-2xl
        bg-white/[0.06] border border-white/10 backdrop-blur-md
        divide-x divide-white/10">
        {hours.map((hour, idx) => (
          <div
            key={idx}
            className="flex flex-col items-center gap-2 min-w-[74px] flex-shrink-0 py-4 px-2
              transition-colors duration-150 hover:bg-white/[0.05]"
          >
            <span className="text-[11px] text-white/55 font-medium tabular-nums">
              {formatTime(hour.dt_txt)}
            </span>
            {hour.icon ? (
              <img
                src={`https://openweathermap.org/img/wn/${hour.icon}@2x.png`}
                alt={hour.description || 'weather'}
                className="w-9 h-9 object-contain"
                loading="lazy"
              />
            ) : (
              <div className="w-7 h-7 bg-white/15 rounded-full animate-pulse" />
            )}
            <span className="text-[15px] font-semibold text-white tabular-nums">
              {hour.temp !== undefined ? Math.round(hour.temp) + '°' : '--'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
