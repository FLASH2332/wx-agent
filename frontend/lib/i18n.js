export const TRANSLATIONS = {
  en: {
    humidity: "Humidity",
    wind: "Wind",
    feelsLike: "Feels like",
    sunrise: "Sunrise",
    sunset: "Sunset",
    pressure: "Pressure",
    today: "Today",
    tomorrow: "Tomorrow",
    weatherBuddy: "Weather Buddy",
    searchPlaceholder: "Search location...",
  },
  hi: {
    humidity: "नमी",
    wind: "हवा",
    feelsLike: "महसूस होता है",
    sunrise: "सूर्योदय",
    sunset: "सूर्यास्त",
    pressure: "दबाव",
    today: "आज",
    tomorrow: "कल",
    weatherBuddy: "मौसम साथी",
    searchPlaceholder: "स्थान खोजें...",
  },
  fr: {
    humidity: "Humidité",
    wind: "Vent",
    feelsLike: "Ressenti",
    sunrise: "Lever du soleil",
    sunset: "Coucher du soleil",
    pressure: "Pression",
    today: "Aujourd'hui",
    tomorrow: "Demain",
    weatherBuddy: "Compagnon Météo",
    searchPlaceholder: "Rechercher un lieu...",
  },
  de: {
    humidity: "Feuchtigkeit",
    wind: "Wind",
    feelsLike: "Gefühlt wie",
    sunrise: "Sonnenaufgang",
    sunset: "Sonnenuntergang",
    pressure: "Druck",
    today: "Heute",
    tomorrow: "Morgen",
    weatherBuddy: "Wetter-Kumpel",
    searchPlaceholder: "Ort suchen...",
  },
  es: {
    humidity: "Humedad",
    wind: "Viento",
    feelsLike: "Sensación",
    sunrise: "Amanecer",
    sunset: "Atardecer",
    pressure: "Presión",
    today: "Hoy",
    tomorrow: "Mañana",
    weatherBuddy: "Compañero del Clima",
    searchPlaceholder: "Buscar ubicación...",
  },
  ta: {
    humidity: "ஈரப்பதம்",
    wind: "காற்று",
    feelsLike: "உணரப்படுவது",
    sunrise: "சூரியோதயம்",
    sunset: "சூரிய அஸ்தமனம்",
    pressure: "அழுத்தம்",
    today: "இன்று",
    tomorrow: "நாளை",
    weatherBuddy: "வானிலை நண்பன்",
    searchPlaceholder: "இடத்தை தேடுக...",
  }
};

export function getTranslation(lang, key) {
  // Fallback to English if the language or key doesn't exist
  if (!TRANSLATIONS[lang]) {
    return TRANSLATIONS["en"][key] || key;
  }
  return TRANSLATIONS[lang][key] || TRANSLATIONS["en"][key] || key;
}
