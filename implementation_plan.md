# UI Polish & Dynamic Layout Plan

## Goal
Implement the design aesthetics from the provided screenshots, refine the chat layout, fix scrolling issues, synchronize the UI language state with the agent's detected language, and introduce a 3-state dynamic layout controlled by the UI Router Agent.

## Proposed Changes

### 1. 3-State Dynamic Layout (Backend & Frontend)
- **Backend (`prompts.py`)**: Update the `ROUTER_PROMPT` to output one of three `ui_mode`s:
  - `"chat"`: For pure conversation (e.g., "Is it going to rain?").
  - `"dashboard"`: For general weather requests (e.g., "What's the weather in London?").
  - `"comparison"`: For evaluating multiple locations.
- **Frontend (`index.js`)**: 
  - If `ui_mode === "chat"`, the Left Column (widgets) collapses, and the Chat Column expands to fill the main view (centered and prominent).
  - If `"dashboard"`, the Left Column displays standard Weather/Forecast widgets.
  - If `"comparison"`, the Left Column displays the `ComparisonCard`.

### 2. Chat Bubble Styling (`ChatHistory.js`)
- Update the message bubbles to match the dark, sleek design in the screenshot.
- Add small headers to the bubbles: `"You said"` for the user and `"Weather Buddy"` for the assistant.
- Use the darker gray backgrounds (`bg-[#1a1a1a]` or similar) with subtle borders.

### 3. Voice Input & Suggestion Styling (`VoiceInput.js` / `SuggestionChips.js`)
- Redesign the voice button into a prominent blue circle.
- Add a static or animated waveform visual above the microphone button.
- Add the "Tap to speak" label.
- Update the suggestion chips to use the dark pill styling (`Try: rain query`, etc.) and place them below the voice button.

### 4. Scrolling Fix (`ChatHistory.js` / `index.js`)
- Fix the CSS overflow and height properties of the conversation panel. Ensure `overflow-y-auto` is correctly applied to the chat container and that the bottom isn't obscured by fixed footers or padding.
- Ensure the `endOfChatRef` properly brings the latest message into full view.

### 5. Language State Sync (`index.js`)
- When the agent responds, it returns the `lang` it processed.
- Update `index.js` to explicitly call `setSelectedLang(response.lang)` upon receiving a successful payload, ensuring the dropdown stays in sync with the agent's auto-detected language.

### 6. Activity Pills
- Add an `ActivityChips` component (Hiking, Beach, Cycling, Photography) that functions similarly to suggestion chips but is tailored for rapid comparison testing. We will place these prominently when the `ComparisonCard` is active, or at the top of the chat.

## Verification Plan
- Send a conversational query and verify the widgets hide and chat centers.
- Send a general weather query and verify widgets appear.
- Send a Hindi voice query and verify the language dropdown automatically switches to Hindi.
- Visually verify chat bubbles, the voice button, and scrolling behavior against the screenshots.

---
> [!IMPORTANT]
> ## User Review Required
> 1. **Activity Pills Placement:** Should the "Hiking / Beach / Cycling / Photography" pills be placed above the chat input, or should they be pinned to the top of the Comparison Card / Weather widgets?
> 2. **Default State:** When the app first loads (before the user asks anything), should it show the full Dashboard (Weather widgets) or just the centered Chat view?
