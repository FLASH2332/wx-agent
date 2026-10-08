// lib/api.js
// NEXT_PUBLIC_API_URL is the backend base URL (e.g. http://127.0.0.1:3001 or a Lambda
// Function URL). A trailing /query is tolerated for older .env.local files.
const RAW_API_URL = process.env.NEXT_PUBLIC_API_URL || "";
export const API_BASE = RAW_API_URL.replace(/\/(query|sync|transcribe|tts)\/?$/, "").replace(/\/$/, "");

async function postJson(path, payload) {
  if (!API_BASE) {
    throw new Error("NEXT_PUBLIC_API_URL environment variable is not set.");
  }

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    throw new Error(`Cannot reach the backend at ${API_BASE}. Is it running? (python -m agent_service)`);
  }

  if (!res.ok) {
    let errMsg = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      errMsg = err.error || errMsg;
    } catch (e) {
      errMsg = `Got a non-JSON response from ${API_BASE}${path}. Check that NEXT_PUBLIC_API_URL points at the agent backend, not Next.js.`;
    }
    throw new Error(errMsg);
  }

  return res.json();
}

export function queryAgent(payload) {
  return postJson("/query", payload);
}

export function transcribeAudio(audioB64, mime) {
  return postJson("/transcribe", { audio_b64: audioB64, mime });
}

export function synthesizeSpeech(text, lang) {
  return postJson("/tts", { text, lang });
}

export async function fetchInstantWeather(location, lang = "en") {
  const data = await postJson("/sync", { location, lang });

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
