// lib/api.js
const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function queryAgent(payload) {
  if (!API_URL) {
    throw new Error("NEXT_PUBLIC_API_URL environment variable is not set.");
  }
  
  let res;
  try {
    res = await fetch(`${API_URL}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    throw new Error(`Backend connection refused! Please ensure you have run 'sam local start-api -p 3001' in a separate terminal to start your AWS backend.`);
  }
  
  if (!res.ok) {
    let errMsg = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      errMsg = err.error || errMsg;
    } catch (e) {
      // If it fails to parse JSON, it's likely an HTML error page (e.g., Next.js 404 or misconfigured endpoint)
      errMsg = `Failed to connect to backend API (Got an HTML/non-JSON response). Check that NEXT_PUBLIC_API_URL is pointing to your SAM backend (e.g. http://127.0.0.1:3001/query) and not Next.js.`;
    }
    throw new Error(errMsg);
  }
  
  return res.json();
}

// Map Open-Meteo WMO codes to OpenWeatherMap-like icons
const getWmoIcon = (code) => {
  if (code === 0) return "01d";
  if (code === 1 || code === 2) return "02d";
  if (code === 3) return "03d";
  if (code >= 45 && code <= 48) return "50d";
  if (code >= 51 && code <= 55) return "09d";
  if (code >= 61 && code <= 65) return "10d";
  if (code >= 71 && code <= 77) return "13d";
  if (code >= 95) return "11d";
  return "01d";
};

const getWmoDesc = (code) => {
  const map = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog", 51: "Drizzle", 53: "Drizzle", 55: "Drizzle",
    61: "Rain", 63: "Rain", 65: "Heavy rain", 71: "Snow", 73: "Snow", 75: "Heavy snow",
    95: "Thunderstorm"
  };
  return map[code] || "Clear";
};

async function fetchWeatherFromOpenMeteo(latitude, longitude, name, country) {
  const wxUrl = `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current=temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m,weather_code&hourly=temperature_2m,weather_code&daily=weather_code,temperature_2m_max,temperature_2m_min`;
  const wxRes = await fetch(wxUrl);
  const wxData = await wxRes.json();
  
  const current = wxData.current;
  const weather_data = {
    location: `${name}, ${country || ''}`.replace(/, $/, ''),
    temp: current.temperature_2m,
    feels_like: current.apparent_temperature,
    humidity: current.relative_humidity_2m,
    wind_speed: current.wind_speed_10m,
    description: getWmoDesc(current.weather_code),
    icon: getWmoIcon(current.weather_code)
  };

  const days = [];
  if (wxData.daily && wxData.daily.time) {
    for (let i = 0; i < Math.min(5, wxData.daily.time.length); i++) {
      days.push({
        date: wxData.daily.time[i],
        temp_max: wxData.daily.temperature_2m_max[i],
        temp_min: wxData.daily.temperature_2m_min[i],
        description: getWmoDesc(wxData.daily.weather_code[i]),
        icon: getWmoIcon(wxData.daily.weather_code[i])
      });
    }
  }

  const hourly = [];
  if (wxData.hourly && wxData.hourly.time) {
    const now = new Date();
    const nowIso = now.toISOString().slice(0, 13) + ":00";
    let startIndex = wxData.hourly.time.findIndex(t => t >= nowIso);
    if (startIndex === -1) startIndex = 0;
    
    for (let i = 0; i < 8; i++) {
      const idx = startIndex + (i * 3);
      if (idx >= wxData.hourly.time.length) break;
      hourly.push({
        dt_txt: wxData.hourly.time[idx].replace("T", " ") + ":00",
        temp: wxData.hourly.temperature_2m[idx],
        description: getWmoDesc(wxData.hourly.weather_code[idx]),
        icon: getWmoIcon(wxData.hourly.weather_code[idx])
      });
    }
  }

  // Fetch alerts via Next.js API route to avoid CORS
  let alerts = [];
  try {
    const alertRes = await fetch(`/api/alerts?lat=${latitude}&lon=${longitude}&country=${country || ''}`);
    if (alertRes.ok) {
      const alertData = await alertRes.json();
      alerts = alertData.alerts || [];
    }
  } catch (e) {
    console.error("Failed to fetch alerts", e);
  }

  return {
    weather_data,
    forecast_data: { days, hourly },
    alerts
  };
}

export async function fetchInstantWeather(location, lang = "en") {
  const syncUrl = API_URL.replace('/query', '/sync');
  const res = await fetch(syncUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ location, lang }),
  });
  if (!res.ok) throw new Error("Sync failed");
  
  // Also try to fetch alerts for the location
  let alerts = [];
  try {
    const geoRes = await fetch(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(location)}&count=1`);
    const geoData = await geoRes.json();
    if (geoData.results && geoData.results.length > 0) {
      const { latitude, longitude, country } = geoData.results[0];
      const alertRes = await fetch(`/api/alerts?lat=${latitude}&lon=${longitude}&country=${country || ''}`);
      if (alertRes.ok) {
        const alertData = await alertRes.json();
        alerts = alertData.alerts || [];
      }
    }
  } catch (e) {
    console.error("Failed to fetch alerts", e);
  }

  const data = await res.json();
  return {
    ...data,
    alerts
  };
}

export async function fetchInstantWeatherByCoords(latitude, longitude, lang = "en") {
  // Reverse geocode to get city name
  const geoRes = await fetch(`https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${latitude}&longitude=${longitude}&localityLanguage=${lang}`);
  let name = "Current Location";
  if (geoRes.ok) {
    const geoData = await geoRes.json();
    name = geoData.city || geoData.locality || "Current Location";
  }
  return fetchInstantWeather(name, lang);
}
