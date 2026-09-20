# Adaptive UI & Context Injection Plan

## User Review Required
Please review the proposed approach for injecting the current location into the agent's context, as well as the design for the Advanced Adaptive UI. Let me know if you approve this direction or if you'd like to adjust the layout ideas for the comparison view.

## 1. Location Context Injection (Implementation Next)

### Goal
Allow the user to ask "Will it rain tomorrow?" and have the agent automatically know they are asking about the city currently displayed on the dashboard, without explicitly stating the city name.

### Proposed Changes

#### [MODIFY] `frontend/pages/index.js`
- Update `handleQuery` to pass the current dashboard location (`weatherData?.location`) as a new `contextLocation` parameter in the API request body to `queryAgent`.
- Update `queryAgent` in `frontend/lib/api.js` to include this field.

#### [MODIFY] `run_local.py` & `lambdas/agent-handler/handler.py`
- Extract `contextLocation` from the incoming JSON payload.
- Pass `contextLocation` as a new keyword argument to `run_agent(text, messages, contextLocation)`.

#### [MODIFY] `lambdas/agent-handler/agent.py`
- Modify `run_agent` to accept `contextLocation`.
- If `contextLocation` is provided, dynamically inject it into the `SYSTEM_PROMPT`. 
  - *Example:* `system_prompt = SYSTEM_PROMPT + f"\n\nContext: The user is currently viewing the weather for {contextLocation}."`
- **Why this is the best approach:** It keeps the user's chat history clean (no ugly injected text in the chat bubbles) while giving the agent perfect awareness of what the user is looking at.

---

## 2. Advanced Adaptive UI (Design & Planning)

### Goal
When the user asks for a comparison or queries multiple locations (e.g., "Compare the weather in Paris, Berlin, and Rome"), the UI should dynamically adapt from a single-city dashboard to a Multi-City Comparison view.

### Backend Changes Required

Currently, `latest_weather_data` in `agent.py` iterates through tool results and only returns the **last** found location. We need to upgrade the backend parsing logic:

- Create a `extract_turn_weather_data(messages)` function that looks only at the tool results from the **most recent turn**.
- If the agent called `get_current_weather` multiple times in that turn, return an array of all those locations: `[{location: "Paris", temp...}, {location: "Berlin", temp...}]`.
- Return this array to the frontend as `weather_data_list`.

### Frontend Adaptive Layout Strategy

The frontend will use a conditional rendering strategy based on `weather_data_list.length`:

#### State A: Single Location (Length === 1)
- The UI remains exactly as it is now: A giant Hero Weather Card, Hourly Timeline, and a 5-day Forecast Sidebar.

#### State B: Two-City Comparison (Length === 2)
- **Layout:** Split the main content area down the middle (50/50 split).
- **Components:** Render two medium-sized `WeatherCard` components side-by-side. 
- **Comparison Highlight:** Add a central divider that automatically computes and highlights the differences (e.g., "Paris is 5° Warmer", "Berlin has 20% more humidity").
- **Forecast:** The right sidebar is hidden or moves below, replaced by mini 3-day forecasts under each respective city card.

#### State C: Multi-City Grid (Length >= 3)
- **Layout:** Masonry grid or horizontal scrollable carousel (`overflow-x-auto`).
- **Components:** Render compact `MiniWeatherCard` components.
- This allows the user to say "Show me the weather in all major European capitals" and get a beautiful, swipeable row of cities instantly.

### Component Architecture Additions
- **`ComparisonView.js`**: A new wrapper component that handles the layout logic when multiple cities are active.
- **`MiniWeatherCard.js`**: A condensed version of the current weather card that omits the large background glows and hourly timelines to save space.

---

## 3. UI Revamp & Accessibility (Design & Planning)

### Goal
Revamp the overall styling of the page to adopt a more formal, professional aesthetic that prioritizes accessibility and clean layouts over experimental "AI-like" elements.

### Proposed Style Changes
- **Color Palette:** Move away from intense neon glows (cyan/amber) and adopt a formal, high-contrast palette (e.g., deep navy blues, crisp whites, and muted slate grays) suitable for professional tools.
- **Typography & Layout:** Ensure a strict, predictable grid layout for all components. Remove overlapping translucent elements (glassmorphism) that reduce readability and replace them with solid panels that have clear borders and subtle drop shadows.
- **Accessibility (A11y) Improvements:**
  - **Color Contrast:** Verify all text meets WCAG AA contrast ratios (at least 4.5:1 for normal text).
  - **Focus States:** Add distinct, high-contrast `focus-visible` rings to all interactive elements (buttons, inputs, language selectors) for keyboard navigation.
  - **ARIA Labels:** Ensure `VoiceInput`, `TopBar` search, and dynamically updating weather data areas have proper `aria-live` regions and descriptive `aria-labels` for screen readers.
- **Removal of "AI-like" Elements:** 
  - Remove typing animations from chat bubbles.
  - Remove the pulsating glow behind the weather cards.
  - Remove the dynamic equalizer bars in the `AudioPlayer` component.
  - Replace abstract conversational interfaces with a structured, data-first "dashboard" approach.
