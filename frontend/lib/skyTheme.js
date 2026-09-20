// The "living sky": derive the whole page's atmosphere from the current
// condition + local time of day. The sky is the design's hero, so the palette
// is data-driven rather than a fixed brand color.

// OWM-style icon codes (our Open-Meteo mapping emits the daytime variants):
//   01 clear · 02/03/04 clouds · 09/10 rain · 11 thunder · 13 snow · 50 mist

const NIGHT = {
  // Deep indigo night — stars implied by the faint top glow.
  gradient: 'linear-gradient(180deg, #060a18 0%, #0b1226 45%, #131a33 100%)',
  glow: 'rgba(99,102,241,0.16)',
  accent: '#8ea2ff',
  scheme: 'night',
};

const SKIES = {
  clear: {
    day: {
      gradient: 'linear-gradient(180deg, #0e3c72 0%, #1c5aa0 40%, #3b82c4 100%)',
      glow: 'rgba(250,204,21,0.22)',
      accent: '#ffd66b',
      scheme: 'day',
    },
    night: NIGHT,
  },
  clouds: {
    day: {
      gradient: 'linear-gradient(180deg, #24313f 0%, #38475a 45%, #52627a 100%)',
      glow: 'rgba(203,213,225,0.14)',
      accent: '#cbd5e1',
      scheme: 'day',
    },
    night: {
      gradient: 'linear-gradient(180deg, #0a0f1c 0%, #141a2b 50%, #232a3d 100%)',
      glow: 'rgba(148,163,184,0.12)',
      accent: '#aab6c9',
      scheme: 'night',
    },
  },
  rain: {
    day: {
      gradient: 'linear-gradient(180deg, #1a2733 0%, #26414f 45%, #34586a 100%)',
      glow: 'rgba(56,189,248,0.16)',
      accent: '#7dd3fc',
      scheme: 'day',
    },
    night: {
      gradient: 'linear-gradient(180deg, #070c15 0%, #101a26 50%, #1b2b3a 100%)',
      glow: 'rgba(56,189,248,0.12)',
      accent: '#67c9f0',
      scheme: 'night',
    },
  },
  thunder: {
    day: {
      gradient: 'linear-gradient(180deg, #14121f 0%, #241f38 45%, #372f52 100%)',
      glow: 'rgba(167,139,250,0.20)',
      accent: '#c4b5fd',
      scheme: 'day',
    },
    night: {
      gradient: 'linear-gradient(180deg, #0a0812 0%, #17132a 50%, #241d3f 100%)',
      glow: 'rgba(167,139,250,0.18)',
      accent: '#b7a6f7',
      scheme: 'night',
    },
  },
  snow: {
    day: {
      gradient: 'linear-gradient(180deg, #2a3646 0%, #3c4c60 45%, #56697f 100%)',
      glow: 'rgba(226,232,240,0.18)',
      accent: '#e2e8f0',
      scheme: 'day',
    },
    night: NIGHT,
  },
  mist: {
    day: {
      gradient: 'linear-gradient(180deg, #2b3138 0%, #3d454e 45%, #566069 100%)',
      glow: 'rgba(203,213,225,0.12)',
      accent: '#c3ccd6',
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
  // Prefer the icon's own day/night suffix; fall back to the local clock.
  if (icon && icon.endsWith('n')) return true;
  if (icon && icon.endsWith('d')) return false;
  const h = new Date().getHours();
  return h < 6 || h >= 19;
}

// A calm default sky for the empty/idle state (pre-dawn blue).
export const DEFAULT_SKY = {
  gradient: 'linear-gradient(180deg, #0a1020 0%, #111a2e 50%, #1a2540 100%)',
  glow: 'rgba(99,102,241,0.12)',
  accent: '#93a4d4',
  scheme: 'night',
};

export function skyFor(weatherData) {
  if (!weatherData || !weatherData.icon) return DEFAULT_SKY;
  const condition = conditionFromIcon(weatherData.icon);
  const slot = isNight(weatherData.icon) ? 'night' : 'day';
  return SKIES[condition]?.[slot] || DEFAULT_SKY;
}
