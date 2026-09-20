// The "living sky": derive the whole page's atmosphere from the current
// condition + local time of day. Tones are kept MODERATE — mid-range skies that
// are never near-black or washed out, so white text stays readable throughout.

// OWM-style icon codes (our Open-Meteo mapping emits the daytime variants):
//   01 clear · 02/03/04 clouds · 09/10 rain · 11 thunder · 13 snow · 50 mist

const NIGHT = {
  gradient: 'linear-gradient(180deg, #243456 0%, #2f4368 55%, #3d5480 100%)',
  glow: 'rgba(129,140,248,0.20)',
  accent: '#aeb9ff',
  scheme: 'night',
};

const SKIES = {
  clear: {
    day: {
      gradient: 'linear-gradient(180deg, #2f6bad 0%, #4a8fce 45%, #6aa9e0 100%)',
      glow: 'rgba(253,224,71,0.28)',
      accent: '#ffe08a',
      scheme: 'day',
    },
    night: NIGHT,
  },
  clouds: {
    day: {
      gradient: 'linear-gradient(180deg, #41556b 0%, #55697f 45%, #6a7e93 100%)',
      glow: 'rgba(226,232,240,0.18)',
      accent: '#e2e8f0',
      scheme: 'day',
    },
    night: {
      gradient: 'linear-gradient(180deg, #28344a 0%, #33415a 55%, #43526e 100%)',
      glow: 'rgba(203,213,225,0.16)',
      accent: '#cdd6e3',
      scheme: 'night',
    },
  },
  rain: {
    day: {
      gradient: 'linear-gradient(180deg, #37525f 0%, #476777 45%, #5a7c8e 100%)',
      glow: 'rgba(125,211,252,0.22)',
      accent: '#a5e3ff',
      scheme: 'day',
    },
    night: {
      gradient: 'linear-gradient(180deg, #243743 0%, #2f4756 55%, #3d5768 100%)',
      glow: 'rgba(103,201,240,0.18)',
      accent: '#8fd6f5',
      scheme: 'night',
    },
  },
  thunder: {
    day: {
      gradient: 'linear-gradient(180deg, #3a3552 0%, #4a4468 45%, #5b5480 100%)',
      glow: 'rgba(196,181,253,0.26)',
      accent: '#d6caff',
      scheme: 'day',
    },
    night: {
      gradient: 'linear-gradient(180deg, #2a2542 0%, #363057 55%, #453e6e 100%)',
      glow: 'rgba(183,166,247,0.22)',
      accent: '#c7bafc',
      scheme: 'night',
    },
  },
  snow: {
    day: {
      gradient: 'linear-gradient(180deg, #4a5a6e 0%, #5d6f84 45%, #74889d 100%)',
      glow: 'rgba(241,245,249,0.24)',
      accent: '#f1f5f9',
      scheme: 'day',
    },
    night: NIGHT,
  },
  mist: {
    day: {
      gradient: 'linear-gradient(180deg, #44515c 0%, #56636f 45%, #6b7883 100%)',
      glow: 'rgba(226,232,240,0.16)',
      accent: '#dbe2ea',
      scheme: 'day',
    },
    night: NIGHT,
  },
};

function conditionFromIcon(icon) {
  const code = (icon || '').slice(0, 2);
  if (code === '01') return 'clear';
  if (code === '02' || code === '03' || code === '04') return 'clouds';
  if (code === '09' || code === '10') return 'rain';
  if (code === '11') return 'thunder';
  if (code === '13') return 'snow';
  if (code === '50') return 'mist';
  return 'clouds';
}

function isNight(icon) {
  if (icon && icon.endsWith('n')) return true;
  if (icon && icon.endsWith('d')) return false;
  const h = new Date().getHours();
  return h < 6 || h >= 19;
}

// A calm, moderate default sky for the empty/idle state (soft afternoon blue).
export const DEFAULT_SKY = {
  gradient: 'linear-gradient(180deg, #33507a 0%, #40608c 55%, #5074a0 100%)',
  glow: 'rgba(147,164,212,0.18)',
  accent: '#bcd0ee',
  scheme: 'day',
};

export function skyFor(weatherData) {
  if (!weatherData || !weatherData.icon) return DEFAULT_SKY;
  const condition = conditionFromIcon(weatherData.icon);
  const slot = isNight(weatherData.icon) ? 'night' : 'day';
  return SKIES[condition]?.[slot] || DEFAULT_SKY;
}
