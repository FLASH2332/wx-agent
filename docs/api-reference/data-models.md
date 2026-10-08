# Weather Buddy — Complete Data Models & JSON Schemas

This reference documents the internal and external data structures, JSON serialization schemas, and database/caching representations used throughout Weather Buddy.

---

## 1. Meteorological Entities

### 1.1 `WeatherData` (Current Observation)

Represents normalized real-time weather metrics ingested from OpenWeatherMap or Open-Meteo.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "WeatherData",
  "type": "object",
  "properties": {
    "city": { "type": "string", "example": "San Francisco" },
    "country": { "type": "string", "example": "US" },
    "temp": { "type": "number", "description": "Temperature in Celsius", "example": 18.5 },
    "feels_like": { "type": "number", "description": "Apparent temperature in Celsius", "example": 17.8 },
    "temp_min": { "type": "number", "example": 14.2 },
    "temp_max": { "type": "number", "example": 21.0 },
    "humidity": { "type": "integer", "description": "Relative humidity percentage (0-100)", "example": 68 },
    "pressure": { "type": "integer", "description": "Atmospheric pressure in hPa", "example": 1014 },
    "wind_speed": { "type": "number", "description": "Wind speed in meters per second", "example": 4.5 },
    "wind_deg": { "type": "integer", "description": "Wind direction in meteorological degrees (0-360)", "example": 280 },
    "condition": { "type": "string", "description": "Primary condition descriptor", "example": "Clear" },
    "description": { "type": "string", "description": "Localized descriptive string", "example": "ciel dégagé" },
    "icon": { "type": "string", "description": "OpenWeatherMap icon identifier", "example": "01d" },
    "timestamp": { "type": "integer", "description": "Unix timestamp in seconds", "example": 1728302400 }
  },
  "required": ["city", "temp", "condition", "humidity", "wind_speed", "icon"]
}
```

### 1.2 `ForecastSlice` (Hourly & Daily Intervals)

Represents individual 3-hour or daily time intervals within the forward-looking forecast window.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ForecastSlice",
  "type": "object",
  "properties": {
    "dt": { "type": "integer", "description": "Epoch timestamp in seconds", "example": 1728313200 },
    "date_str": { "type": "string", "example": "2026-10-07 15:00:00" },
    "temp": { "type": "number", "example": 19.2 },
    "temp_min": { "type": "number", "example": 15.0 },
    "temp_max": { "type": "number", "example": 22.4 },
    "pop": { "type": "number", "description": "Probability of precipitation from 0.0 to 1.0", "example": 0.25 },
    "rain_3h": { "type": "number", "description": "Precipitation volume in millimeters", "example": 0.8 },
    "condition": { "type": "string", "example": "Rain" },
    "icon": { "type": "string", "example": "10d" }
  },
  "required": ["dt", "temp", "pop", "condition"]
}
```

### 1.3 `WeatherAlert` (Hazard Warnings)

Represents official bulletins parsed from US National Weather Service (NWS) or European GDACS feeds.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "WeatherAlert",
  "type": "object",
  "properties": {
    "id": { "type": "string", "example": "NWS-ID-2026-10928" },
    "event": { "type": "string", "example": "Severe Thunderstorm Warning" },
    "headline": { "type": "string", "example": "Severe Thunderstorm Warning in effect until 7:00 PM" },
    "severity": { "type": "string", "enum": ["Extreme", "Severe", "Moderate", "Minor", "Unknown"], "example": "Severe" },
    "urgency": { "type": "string", "enum": ["Immediate", "Expected", "Future", "Past", "Unknown"], "example": "Immediate" },
    "certainty": { "type": "string", "enum": ["Observed", "Likely", "Possible", "Unlikely", "Unknown"], "example": "Likely" },
    "areas": { "type": "array", "items": { "type": "string" }, "example": ["Cook County", "DuPage County"] },
    "effective": { "type": "string", "format": "date-time", "example": "2026-10-07T14:30:00Z" },
    "expires": { "type": "string", "format": "date-time", "example": "2026-10-07T19:00:00Z" },
    "description": { "type": "string", "example": "Winds up to 60 mph and quarter-size hail possible." },
    "instruction": { "type": "string", "example": "Move to an interior room on the lowest floor." }
  },
  "required": ["id", "event", "severity", "expires"]
}
```

---

## 2. Conversational & Agent Entities

### 2.1 `AgentTurn` (Conversational State History)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AgentTurn",
  "type": "object",
  "properties": {
    "role": { "type": "string", "enum": ["user", "assistant", "tool", "system"] },
    "content": { "type": "string" },
    "tool_calls": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": { "type": "string", "example": "call_abc123" },
          "type": { "type": "string", "enum": ["function"] },
          "function": {
            "type": "object",
            "properties": {
              "name": { "type": "string", "example": "get_current_weather" },
              "arguments": { "type": "string", "example": "{\"location\":\"Paris, FR\",\"lang\":\"fr\"}" }
            }
          }
        }
      }
    }
  },
  "required": ["role", "content"]
}
```

### 2.2 `ActivityRecommendation`

Generated by the `activity_advisor` tool to evaluate environmental conditions for human activity.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ActivityRecommendation",
  "type": "object",
  "properties": {
    "activity": { "type": "string", "example": "Running" },
    "location": { "type": "string", "example": "London, GB" },
    "suitability_score": { "type": "integer", "minimum": 0, "maximum": 100, "example": 88 },
    "verdict": { "type": "string", "enum": ["Ideal", "Acceptable", "Caution", "Not Recommended"], "example": "Ideal" },
    "factors": {
      "type": "object",
      "properties": {
        "temperature_comfort": { "type": "string", "example": "Comfortable (17°C)" },
        "precipitation_risk": { "type": "string", "example": "Zero rain expected" },
        "wind_conditions": { "type": "string", "example": "Light breeze (7 km/h)" },
        "uv_index": { "type": "string", "example": "Low (2)" }
      }
    },
    "advisory_note": { "type": "string", "example": "Great conditions for an afternoon jog. Light clothing recommended." }
  },
  "required": ["activity", "suitability_score", "verdict"]
}
```
