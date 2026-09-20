import React from 'react';

export default function ForecastList({ days = [] }) {
  if (!days || days.length === 0) return null;

  return (
    <div className="mt-4 glass-panel bg-white/5 border-white/10 rounded-3xl p-5 shadow-xl">
      <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider mb-4">5-Day Forecast</h3>
      
      <div className="flex flex-col gap-4">
        {days.map((day, i) => {
          const iconUrl = day.icon ? `https://openweathermap.org/img/wn/${day.icon}.png` : null;
          const dateObj = new Date(day.date);
          const dayName = dateObj.toLocaleDateString('en-US', { weekday: 'short' });
          
          return (
            <div key={i} className="flex items-center justify-between text-sm">
              <span className="w-12 font-medium text-white/80">{dayName}</span>
              
              <div className="flex items-center gap-2 flex-1 justify-center">
                {iconUrl && <img src={iconUrl} alt={day.description} className="w-8 h-8" />}
                {day.pop > 0 && (
                  <span className="text-xs text-blue-300 font-medium">
                    {Math.round(day.pop * 100)}%
                  </span>
                )}
              </div>
              
              <div className="flex items-center gap-3 w-20 justify-end">
                <span className="text-white font-semibold">{Math.round(day.temp_max)}°</span>
                <span className="text-white/40">{Math.round(day.temp_min)}°</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
