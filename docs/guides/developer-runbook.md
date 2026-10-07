# Weather Buddy — Day-to-Day Developer Runbook & Extension Recipes

This runbook catalogs standard day-to-day engineering recipes for developers extending Weather Buddy with new tools, languages, UI components, and test fixtures.

---

## 1. Recipe: Adding a New Meteorological Tool

Follow this 5-step workflow to add a new agent tool (e.g. `get_air_quality`):

### Step 1: Implement the Tool Function in `tools.py`
In `lambdas/agent-handler/tools.py`:
```python
def get_air_quality(location: str) -> dict:
    """Fetch current Air Quality Index (AQI) metrics for a location."""
    lat, lon, city = _geocode(location)
    url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={OWM_API_KEY}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode())
        item = data["list"][0]
        return {
            "city": city,
            "aqi": item["main"]["aqi"],
            "pm2_5": item["components"]["pm2_5"],
            "pm10": item["components"]["pm10"],
        }
```

### Step 2: Register Tool in the Strands Agent Tool Registry
In `lambdas/agent-handler/agent.py`:
```python
# Add get_air_quality to the tool definitions list passed to strands Agent:
TOOLS = [
    get_current_weather,
    get_forecast,
    get_alerts,
    activity_advisor,
    get_air_quality,  # Newly registered tool
]
```

### Step 3: Update System Prompt Guidelines
In `lambdas/agent-handler/prompts.py`:
```python
# Add tool usage guidance to the agent system prompt instructions:
# "Use get_air_quality when the user asks about pollution, smoke, smog, or respiratory conditions."
```

### Step 4: Write Offline Mock Unit Test
In `lambdas/agent-handler/tests/test_tools.py`:
```python
def test_get_air_quality_mocked():
    mock_payload = {"list": [{"main": {"aqi": 2}, "components": {"pm2_5": 12.4, "pm10": 20.1}}]}
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode()
        mock_url.return_value = mock_resp
        result = get_air_quality("Seattle, US")
        assert result["aqi"] == 2
```

### Step 5: Verify via CLI
Run the local CLI test tool:
```bash
python lambdas/agent-handler/cli.py "How is the air quality in Seattle today?"
```

---

## 2. Recipe: Adding a New Supported Language to UI Dictionaries

To add localized labels for a new language (e.g. Italian `it`):

### Step 1: Add Dictionary Object to `frontend/lib/i18n.js`
```javascript
export const dictionaries = {
  // Existing languages (en, fr, es, hi, ta)...
  it: {
    weather: "Meteo",
    temperature: "Temperatura",
    feels_like: "Percepita",
    humidity: "Umidità",
    wind: "Vento",
    pressure: "Pressione",
    hourly_forecast: "Previsioni orarie",
    daily_forecast: "Previsioni a 5 giorni",
    alerts: "Avvisi meteorologici",
    search_placeholder: "Cerca città o paese...",
    listening: "Ascolto in corso...",
    processing: "Elaborazione in corso...",
    ask_placeholder: "Chiedi informazioni sul meteo in qualsiasi lingua...",
    suggestion_1: "Pioverà domani?",
    suggestion_2: "Posso fare una passeggiata questo weekend?",
    suggestion_3: "Velocità attuale del vento a Roma"
  }
};
```

### Step 2: Register Language in Language Selector
In `frontend/components/TopBar.js`, ensure the ISO code is included in the available language array.

### Step 3: Verify with Local Dev Server
```bash
cd frontend && npm run dev
```
Select Italian from the dropdown or speak in Italian; all UI labels and cards will update dynamically.

---

## 3. Recipe: Local SAM Testing with Docker

To test Lambdas in an emulated local AWS container before deploying:

```bash
# 1. Build serverless artifacts
sam build

# 2. Invoke AgentFunction locally with mock test event
sam local invoke AgentFunction -e events/sample_query.json --docker-network host

# 3. Start local API Gateway on port 3001
sam local start-api -p 3001
```
