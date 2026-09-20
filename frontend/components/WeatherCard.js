import React from 'react';
import { MapPin, Droplets, Wind, ThermometerSun } from 'lucide-react';
import { getTranslation } from '../lib/i18n';

export default function WeatherCard({ weatherData, currentLang = 'en' }) {
  if (!weatherData || !weatherData.temp) return null;

  const { location, temp, feels_like, humidity, wind_speed, description, icon } = weatherData;
  const iconUrl = icon ? `https://openweathermap.org/img/wn/${icon}@4x.png` : null;

  return (
    <section className="relative animate-fade-in-up">
      {/* Place — quiet, above the hero number */}
      <div className="flex items-center gap-1.5 text-white/70 text-sm font-medium">
        <MapPin className="w-4 h-4" strokeWidth={1.75} />
        <span className="tracking-wide">{location}</span>
      </div>

      {/* The hero: temperature as a display element, sitting in the sky */}
      <div className="flex items-start gap-3 lg:gap-6 mt-2 -ml-1">
        <div className="font-hero font-semibold tracking-tighter tabular-nums leading-[0.82]
          text-[6.5rem] sm:text-[8rem] lg:text-[10rem] text-white
          drop-shadow-[0_8px_30px_rgba(0,0,0,0.35)]">
          {Math.round(temp)}<span className="text-white/45">°</span>
        </div>
        {iconUrl && (
          <img
            src={iconUrl}
            alt={description || 'Weather'}
            className="w-24 h-24 lg:w-36 lg:h-36 object-contain drop-shadow-[0_6px_20px_rgba(0,0,0,0.35)] mt-2"
            loading="lazy"
          />
        )}
      </div>

      {/* Condition + feels-like — one honest line each, no labels */}
      <div className="mt-1">
        <p className="text-2xl lg:text-3xl font-medium text-white capitalize leading-tight">{description}</p>
        <p className="text-white/60 text-base mt-1">
          {getTranslation(currentLang, 'feelsLike')} {Math.round(feels_like)}°
        </p>
      </div>

      {/* Secondary readings — a single quiet strip with dividers, not separate cards */}
      <div className="inline-flex items-center gap-6 lg:gap-8 mt-6 px-5 py-3 rounded-full
        bg-white/[0.06] border border-white/10 backdrop-blur-md text-sm">
        <span className="flex items-center gap-2 text-white/85">
          <ThermometerSun className="w-4 h-4 text-white/55" strokeWidth={1.75} />
          <span className="tabular-nums font-semibold">{Math.round(feels_like)}°</span>
          <span className="text-white/45">{getTranslation(currentLang, 'feelsLike')}</span>
        </span>
        <span className="w-px h-4 bg-white/15" />
        <span className="flex items-center gap-2 text-white/85">
          <Droplets className="w-4 h-4 text-white/55" strokeWidth={1.75} />
          <span className="tabular-nums font-semibold">{humidity}%</span>
          <span className="text-white/45">{getTranslation(currentLang, 'humidity')}</span>
        </span>
        <span className="w-px h-4 bg-white/15" />
        <span className="flex items-center gap-2 text-white/85">
          <Wind className="w-4 h-4 text-white/55" strokeWidth={1.75} />
          <span className="tabular-nums font-semibold">{wind_speed}</span>
          <span className="text-white/45">m/s {getTranslation(currentLang, 'wind')}</span>
        </span>
      </div>
    </section>
  );
}
