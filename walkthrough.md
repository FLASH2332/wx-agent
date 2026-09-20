# Location & Time Planning Intelligence Walkthrough

I have successfully refactored the Strands AI agent to become a true context-aware planner! The agent now silently resolves ambiguous queries based on the user's location and parses natural language time into precise hourly windows.

## What changed?

### 1. Context Capture (Frontend)
- The frontend now captures the user's coordinates on page load via `navigator.geolocation` and saves them to `userLat` and `userLon`.
- Before querying the agent, the frontend captures the precise `localTime` (ISO string with timezone offset).
- These three variables are sent silently alongside every query in the `handleQuery` payload.

### 2. Location Disambiguation (Haversine Formula)
- The `_geocode` helper in `tools.py` has been completely rewritten to support **distance ranking**.
- If a user searches for an ambiguous city (e.g. "Springfield"), OWM returns up to 5 results.
- `_geocode` computes the Haversine distance from the user's coordinates to each result, and automatically selects the closest one.
- **Agent Awareness:** The tool returns a `disambiguation_note` to the LLM. The LLM now knows *why* a location was picked (e.g., "Resolved 'Springfield' to Springfield, Illinois because it is 20km from your location.") and can weave that reasoning into its response.

### 3. Natural Time Parsing (`parse_time_expression`)
- The agent has a brand new tool: `parse_time_expression`.
- The system prompt injects the user's `localTime`. 
- When a user asks about "this weekend" or "tonight at 8pm", the agent passes that string to the tool, which uses the powerful `dateparser` library (anchored to the user's timezone) to resolve it into exact Unix timestamps.

### 4. Precise Hourly Windows (`get_hourly_window`)
- Once the agent has the exact Unix timestamps (e.g. Saturday 00:00 to Sunday 23:59), it calls the new `get_hourly_window` tool.
- This tool fetches the 5-day/3-hour forecast from OpenWeatherMap but **slices the data strictly to the requested time bounds**.
- The LLM receives a perfectly clean, highly relevant window of data (e.g., only the 8 hourly blocks for the weekend), dramatically improving its planning capabilities and reducing context token waste!

### 5. Dual-Agent Orchestration & Comparison UI
- The system now features a **Two-Step LLM Pipeline**:
  - **The Analyst:** An unconstrained, detailed meteorological agent that scores days on a 1-5 scale, deeply evaluates weather models, and flags risks (e.g. black ice).
  - **The UI Router:** A fast, JSON-mode agent that consumes the Analyst's output and extracts structured data to control the frontend.
- When the UI Router detects a comparison query, it outputs `ui_mode: "comparison"`.
- The frontend dynamically drops the standard weather widgets and mounts the sleek new `ComparisonCard.js`, which renders side-by-side data columns, beautiful color-coded weekend score progress bars, and the winner's reasoning!
