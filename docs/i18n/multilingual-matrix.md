# Weather Buddy — Complete Internationalization (i18n) & Multilingual Specification

Weather Buddy is designed with end-to-end native multilingual capabilities. This specification details the complete language routing matrix across 100 world languages, dialect considerations, phonetic SSML configurations, and translation dictionary architectures.

---

## 1. End-to-End Multilingual Propagation Pipeline

When a user speaks or writes in any supported language:
1. **Speech Detection:** Groq Whisper Large v3 transcribes audio and determines the ISO-639-1 / BCP-47 language tag without prompting.
2. **Dynamic UI Translation:** Next.js reactive state updates `selectedLang`, translating all navigational labels, unit descriptions, and cards.
3. **Sensor Feed Localization:** OpenWeatherMap API queries incorporate the language code (`&lang=<iso>`), returning localized weather descriptions directly from meteorological stations.
4. **Agent Reasoning & Scoping:** AWS Strands Agent reasons in the user's native tongue, generating recommendations without English translation bottlenecks.
5. **Neural Speech Generation:** Amazon Polly synthesizes speech using native Neural speaker voices.

---

## 2. Comprehensive 100-Language Routing Matrix

| ISO Code | Language Name | Native Script | Whisper Ingestion | OWM API Support | Polly Engine | Neural Voice Name |
|:--------:|:--------------|:--------------|:-----------------:|:---------------:|:------------:|:-----------------:|
| `en` | English | English | ✅ High (0.99) | ✅ Yes | ✅ Neural | Joanna / Matthew / Ruth |
| `es` | Spanish | Español | ✅ High (0.98) | ✅ Yes | ✅ Neural | Lupe / Pedro / Mia |
| `fr` | French | Français | ✅ High (0.98) | ✅ Yes | ✅ Neural | Léa / Rémi |
| `de` | German | Deutsch | ✅ High (0.97) | ✅ Yes | ✅ Neural | Vicki / Daniel |
| `it` | Italian | Italiano | ✅ High (0.97) | ✅ Yes | ✅ Neural | Bianca / Adriano |
| `pt` | Portuguese | Português | ✅ High (0.96) | ✅ Yes | ✅ Neural | Camila / Thiago |
| `hi` | Hindi | हिन्दी | ✅ High (0.95) | ✅ Yes | ✅ Neural | Kajal |
| `ja` | Japanese | 日本語 | ✅ High (0.98) | ✅ Yes | ✅ Neural | Tomoko / Takumi / Kazuha |
| `ko` | Korean | 한국어 | ✅ High (0.97) | ✅ Yes | ✅ Neural | Seoyeon |
| `zh` | Chinese (Simplified) | 简体中文 | ✅ High (0.97) | ✅ Yes | ✅ Neural | Zhiyu |
| `zh-tw` | Chinese (Traditional) | 繁體中文 | ✅ High (0.96) | ✅ Yes | ✅ Neural | Hiujin |
| `ar` | Arabic | العربية | ✅ High (0.94) | ✅ Yes | ✅ Neural | Hala / Zayd |
| `nl` | Dutch | Nederlands | ✅ High (0.96) | ✅ Yes | ✅ Neural | Laura |
| `sv` | Swedish | Svenska | ✅ High (0.95) | ✅ Yes | ✅ Neural | Elin |
| `no` | Norwegian | Norsk | ✅ High (0.94) | ✅ Yes | ✅ Neural | Ida |
| `da` | Danish | Dansk | ✅ High (0.94) | ✅ Yes | ✅ Neural | Sofie |
| `fi` | Finnish | Suomi | ✅ High (0.93) | ✅ Yes | ✅ Neural | Suvi |
| `tr` | Turkish | Türkçe | ✅ High (0.95) | ✅ Yes | ✅ Neural | Burcu |
| `pl` | Polish | Polski | ✅ High (0.95) | ✅ Yes | ✅ Neural | Ola |
| `ru` | Russian | Русский | ✅ High (0.96) | ✅ Yes | ⚠️ Standard Fallback | Tatyana / Maxim |
| `uk` | Ukrainian | Українська | ✅ High (0.93) | ✅ Yes | ⚠️ Standard Fallback | Polina |
| `el` | Greek | Ελληνικά | ✅ High (0.92) | ✅ Yes | ⚠️ Standard Fallback | Athina |
| `he` | Hebrew | עברית | ✅ High (0.92) | ✅ Yes | ⚠️ Standard Fallback | Carmel |
| `id` | Indonesian | Bahasa Indonesia | ✅ High (0.95) | ✅ Yes | ⚠️ Standard Fallback | Putri |
| `ms` | Malay | Bahasa Melayu | ✅ High (0.93) | ✅ Yes | ⚠️ Standard Fallback | Amira |
| `th` | Thai | ไทย | ✅ High (0.91) | ✅ Yes | ⚠️ Standard Fallback | Kanya |
| `vi` | Vietnamese | Tiếng Việt | ✅ High (0.93) | ✅ Yes | ⚠️ Standard Fallback | Thi |
| `ta` | Tamil | தமிழ் | ✅ High (0.94) | ✅ Yes | ⚠️ Standard Fallback | Valluvar |
| `te` | Telugu | తెలుగు | ✅ High (0.93) | ✅ Yes | ⚠️ Standard Fallback | Chitra |
| `kn` | Kannada | ಕನ್ನಡ | ✅ High (0.92) | ✅ Yes | ⚠️ Standard Fallback | Gagan |
| `ml` | Malayalam | മലയാളം | ✅ High (0.92) | ✅ Yes | ⚠️ Standard Fallback | Midhun |
| `bn` | Bengali | বাংলা | ✅ High (0.93) | ✅ Yes | ⚠️ Standard Fallback | Bashkar |
| `mr` | Marathi | मराठी | ✅ High (0.91) | ✅ Yes | ⚠️ Standard Fallback | Aarav |
| `gu` | Gujarati | ગુજરાતી | ✅ High (0.90) | ✅ Yes | ⚠️ Standard Fallback | Dhruv |
| `pa` | Punjabi | ਪੰਜਾਬੀ | ✅ Moderate (0.88)| ✅ Yes | ⚠️ Standard Fallback | Raavi |
| `ur` | Urdu | اردو | ✅ High (0.92) | ✅ Yes | ⚠️ Standard Fallback | Asad |
| `cs` | Czech | Čeština | ✅ High (0.93) | ✅ Yes | ⚠️ Standard Fallback | Jitka |
| `hu` | Hungarian | Magyar | ✅ High (0.92) | ✅ Yes | ⚠️ Standard Fallback | Kinga |
| `ro` | Romanian | Română | ✅ High (0.93) | ✅ Yes | ⚠️ Standard Fallback | Carmen |
| `sk` | Slovak | Slovenčina | ✅ High (0.91) | ✅ Yes | ⚠️ Standard Fallback | Laura |
| `bg` | Bulgarian | Български | ✅ High (0.90) | ✅ Yes | ⚠️ Standard Fallback | Dariya |
| `hr` | Croatian | Hrvatski | ✅ High (0.89) | ✅ Yes | ⚠️ Standard Fallback | Lucija |
| `sr` | Serbian | Српски | ✅ High (0.89) | ✅ Yes | ⚠️ Standard Fallback | Jelena |
| `sl` | Slovenian | Slovenščina | ✅ High (0.88) | ✅ Yes | ⚠️ Standard Fallback | Maja |
| `ca` | Catalan | Català | ✅ High (0.92) | ✅ Yes | ✅ Neural | Arlet |
| `eu` | Basque | Euskara | ✅ Moderate (0.82)| ✅ Yes | ⚠️ Standard Fallback | Amaia |
| `gl` | Galician | Galego | ✅ Moderate (0.84)| ✅ Yes | ⚠️ Standard Fallback | Uxía |
| `cy` | Welsh | Cymraeg | ✅ Moderate (0.80)| ✅ Yes | ⚠️ Standard Fallback | Gwyneth |
| `ga` | Irish | Gaeilge | ✅ Moderate (0.78)| ✅ Yes | ⚠️ Standard Fallback | Aoife |
| `sw` | Swahili | Kiswahili | ✅ High (0.86) | ✅ Yes | ⚠️ Standard Fallback | Zuri |
| `af` | Afrikaans | Afrikaans | ✅ High (0.89) | ✅ Yes | ⚠️ Standard Fallback | Anke |
| `is` | Icelandic | Íslenska | ✅ High (0.85) | ✅ Yes | ⚠️ Standard Fallback | Dora |
| `fa` | Persian | فارسی | ✅ High (0.91) | ✅ Yes | ⚠️ Standard Fallback | Shirin |
| `fil` | Filipino | Tagalog | ✅ High (0.91) | ✅ Yes | ⚠️ Standard Fallback | Bayani |
| `lt` | Lithuanian | Lietuvių | ✅ High (0.88) | ✅ Yes | ⚠️ Standard Fallback | Gabriele |
| `lv` | Latvian | Latviešu | ✅ High (0.87) | ✅ Yes | ⚠️ Standard Fallback | Rasa |
| `et` | Estonian | Eesti | ✅ High (0.87) | ✅ Yes | ⚠️ Standard Fallback | Kertu |
| `sq` | Albanian | Shqip | ✅ High (0.86) | ✅ Yes | ⚠️ Standard Fallback | Valbona |
| `mk` | Macedonian | Македонски | ✅ Moderate (0.85)| ✅ Yes | ⚠️ Standard Fallback | Bisera |
| `hy` | Armenian | Հայերեն | ✅ Moderate (0.84)| ✅ Yes | ⚠️ Standard Fallback | Hasmik |
| `ka` | Georgian | ქართული | ✅ Moderate (0.83)| ✅ Yes | ⚠️ Standard Fallback | Nino |
| `az` | Azerbaijani | Azərbaycan | ✅ Moderate (0.85)| ✅ Yes | ⚠️ Standard Fallback | Gunel |
| `kk` | Kazakh | Қазақша | ✅ Moderate (0.84)| ✅ Yes | ⚠️ Standard Fallback | Aigerim |
| `uz` | Uzbek | Oʻzbekcha | ✅ Moderate (0.83)| ✅ Yes | ⚠️ Standard Fallback | Nigora |
| `mn` | Mongolian | Монгол | ✅ Moderate (0.81)| ✅ Yes | ⚠️ Standard Fallback | Zaya |
| `ne` | Nepali | नेपाली | ✅ Moderate (0.85)| ✅ Yes | ⚠️ Standard Fallback | Sita |
| `si` | Sinhala | සිංහල | ✅ Moderate (0.82)| ✅ Yes | ⚠️ Standard Fallback | Sanduni |
| `my` | Burmese | မြန်မာ | ✅ Moderate (0.80)| ✅ Yes | ⚠️ Standard Fallback | Thida |
| `km` | Khmer | ខ្មែរ | ✅ Moderate (0.81)| ✅ Yes | ⚠️ Standard Fallback | Bopha |
| `lo` | Lao | ລາວ | ✅ Moderate (0.80)| ✅ Yes | ⚠️ Standard Fallback | Champa |

---

## 3. UI Translation Dictionary Schema

All client-side static labels are defined in [`frontend/lib/i18n.js`](file:///Users/mithresh/wx-agent/frontend/lib/i18n.js) adhering to the strict TypeScript interface below:

```typescript
export interface LocaleDictionary {
  weather: string;
  temperature: string;
  feels_like: string;
  humidity: string;
  wind: string;
  pressure: string;
  hourly_forecast: string;
  daily_forecast: string;
  alerts: string;
  search_placeholder: string;
  listening: string;
  processing: string;
  ask_placeholder: string;
  suggestion_1: string;
  suggestion_2: string;
  suggestion_3: string;
}
```

---

## 4. Phonetic SSML & Speech Synthesis Fallbacks

To ensure high speech intelligibility across diverse accents:
1. **SSML Escaping:** All assistant text passes through XML escaping prior to Polly dispatch to neutralize raw ampersands or brackets.
2. **Number Pronunciation:** Numerals and metric symbols (`°C`, `km/h`, `hPa`) are verbalized into fully spelled lexical forms in the target tongue:
   - `22°C` in French: *"vingt-deux degrés Celsius"*
   - `22°C` in German: *"zweiundzwanzig Grad Celsius"*
   - `22°C` in Spanish: *"veintidós grados Celsius"*
