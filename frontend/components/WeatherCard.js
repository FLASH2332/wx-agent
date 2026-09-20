import React from 'react';
import { Droplets, Wind, ThermometerSun } from 'lucide-react';

export default function WeatherCard({ weatherData }) {
  if (!weatherData || !weatherData.temp) return null;

  const { location, temp, feels_like, humidity, wind_speed, description, icon } = weatherData;
  const iconUrl = icon ? `https://openweathermap.org/img/wn/${icon}@2x.png` : null;

  // Determine a subtle gradient based on temp or description (simplified)
  const isWarm = temp > 20;
  const bgClass = isWarm 
    ? "bg-gradient-to-br from-amber-500/10 to-orange-600/10 border-orange-500/20"
    : "bg-gradient-to-br from-blue-500/10 to-cyan-600/10 border-blue-500/20";

  return (
    <div className={`glass-panel rounded-3xl p-6 ${bgClass} transition-all duration-500 relative overflow-hidden shadow-2xl`}>
      {/* Decorative glow */}
      <div className={`absolute -top-12 -right-12 w-32 h-32 rounded-full blur-3xl opacity-30 ${isWarm ? 'bg-orange-500' : 'bg-blue-500'}`} />
      
      <div className="relative z-10 flex flex-col items-center">
        <h2 className="text-xl font-medium text-white/90 text-center tracking-wide">{location}</h2>
        
        <div className="flex items-center justify-center mt-2 -mb-2">
          {iconUrl && (
            <img 
              src={iconUrl} 
              alt={description || "Weather icon"} 
              className="w-24 h-24 lg:w-32 lg:h-32 object-contain drop-shadow-lg"
            />
          )}
          <div className="flex flex-col ml-4">
            <span className="text-7xl lg:text-8xl font-bold tracking-tighter text-white">
              {Math.round(temp)}°
            </span>
            <span className="text-white/70 text-sm lg:text-lg font-medium capitalize -mt-1 lg:-mt-2 text-center">
              {description}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 w-full mt-6 lg:mt-10 bg-black/20 rounded-2xl p-4 lg:p-6 border border-white/5 backdrop-blur-sm">
          <div className="flex flex-col items-center">
            <ThermometerSun className="w-5 h-5 lg:w-6 lg:h-6 text-white/50 mb-1 lg:mb-2" />
            <span className="text-sm lg:text-base font-semibold">{Math.round(feels_like)}°</span>
            <span className="text-[10px] lg:text-xs text-white/50 uppercase tracking-wider">Feels</span>
          </div>
          <div className="flex flex-col items-center border-l border-white/10">
            <Droplets className="w-5 h-5 lg:w-6 lg:h-6 text-white/50 mb-1 lg:mb-2" />
            <span className="text-sm lg:text-base font-semibold">{humidity}%</span>
            <span className="text-[10px] lg:text-xs text-white/50 uppercase tracking-wider">Humidity</span>
          </div>
          <div className="flex flex-col items-center border-l border-white/10">
            <Wind className="w-5 h-5 lg:w-6 lg:h-6 text-white/50 mb-1 lg:mb-2" />
            <span className="text-sm lg:text-base font-semibold">{wind_speed} <span className="text-[10px]">m/s</span></span>
            <span className="text-[10px] lg:text-xs text-white/50 uppercase tracking-wider">Wind</span>
          </div>
        </div>
      </div>
    </div>
  );
}
