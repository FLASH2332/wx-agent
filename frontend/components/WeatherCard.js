import React from 'react';
import { Droplets, Wind, ThermometerSun } from 'lucide-react';
import { getTranslation } from '../lib/i18n';

export default function WeatherCard({ weatherData, currentLang = 'en' }) {
  if (!weatherData || !weatherData.temp) return null;

  const { location, temp, feels_like, humidity, wind_speed, description, icon } = weatherData;
  const iconUrl = icon ? `https://openweathermap.org/img/wn/${icon}@4x.png` : null;

  const isWarm = temp > 20;

  return (
    <div className={`
      rounded-[28px] p-6 lg:p-8 relative overflow-hidden
      transition-interactive animate-fade-in-up
      ${isWarm 
        ? 'bg-gradient-to-br from-amber-500/8 to-orange-600/8 border border-orange-500/15' 
        : 'bg-gradient-to-br from-blue-500/8 to-cyan-600/8 border border-blue-500/15'}
      shadow-[0_2px_4px_rgba(0,0,0,0.15),0_8px_24px_rgba(0,0,0,0.12),0_16px_56px_rgba(0,0,0,0.08)]
    `}>
      {/* Ambient glow — purely decorative */}
      <div className={`absolute -top-16 -right-16 w-40 h-40 rounded-full blur-[80px] opacity-20 pointer-events-none
        ${isWarm ? 'bg-orange-500' : 'bg-blue-500'}`} 
      />
      
      <div className="relative z-10 flex flex-col items-center">
        <h2 className="text-lg lg:text-xl font-medium text-white/85 text-center tracking-wide">{location}</h2>
        
        <div className="flex items-center justify-center mt-3 gap-4">
          {iconUrl && (
            <img 
              src={iconUrl} 
              alt={description || "Weather icon"} 
              className="w-24 h-24 lg:w-28 lg:h-28 object-contain drop-shadow-[0_4px_12px_rgba(0,0,0,0.3)]"
              loading="lazy"
            />
          )}
          <div className="flex flex-col">
            <span className="text-7xl lg:text-8xl font-bold tracking-tighter text-white tabular-nums">
              {Math.round(temp)}°
            </span>
            <span className="text-white/60 text-sm lg:text-base font-medium capitalize -mt-1 text-center">
              {description}
            </span>
          </div>
        </div>

        {/* Stats row — concentric radius: outer 20px, inner 16px with 4px padding */}
        <div className="grid grid-cols-3 gap-3 w-full mt-6 lg:mt-8 bg-black/15 rounded-[20px] p-4 lg:p-5
          shadow-[inset_0_1px_2px_rgba(0,0,0,0.2),0_1px_0_rgba(255,255,255,0.03)]
          border border-white/[0.04]">
          <div className="flex flex-col items-center gap-1.5">
            <ThermometerSun className="w-5 h-5 lg:w-[22px] lg:h-[22px] text-white/45" strokeWidth={1.5} />
            <span className="text-sm lg:text-base font-semibold tabular-nums">{Math.round(feels_like)}°</span>
            <span className="text-[10px] lg:text-xs text-white/40 font-medium tracking-wider">
              {getTranslation(currentLang, 'feelsLike')}
            </span>
          </div>
          <div className="flex flex-col items-center gap-1.5 border-l border-white/[0.06]">
            <Droplets className="w-5 h-5 lg:w-[22px] lg:h-[22px] text-white/45" strokeWidth={1.5} />
            <span className="text-sm lg:text-base font-semibold tabular-nums">{humidity}%</span>
            <span className="text-[10px] lg:text-xs text-white/40 font-medium tracking-wider">
              {getTranslation(currentLang, 'humidity')}
            </span>
          </div>
          <div className="flex flex-col items-center gap-1.5 border-l border-white/[0.06]">
            <Wind className="w-5 h-5 lg:w-[22px] lg:h-[22px] text-white/45" strokeWidth={1.5} />
            <span className="text-sm lg:text-base font-semibold tabular-nums">
              {wind_speed} <span className="text-[10px] font-normal">m/s</span>
            </span>
            <span className="text-[10px] lg:text-xs text-white/40 font-medium tracking-wider">
              {getTranslation(currentLang, 'wind')}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
