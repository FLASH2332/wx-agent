# UI Polish & Dynamic Layout Tasks

- `[x]` 1. **Backend Routing:** Update `ROUTER_PROMPT` in `prompts.py` to support 3 `ui_mode`s: `"chat"`, `"dashboard"`, and `"comparison"`.
- `[x]` 2. **Backend Fallback:** Update `agent.py` so the fallback defaults to `"dashboard"`.
- `[x]` 3. **Chat Styling:** Update `ChatHistory.js` to add "You said" / "Weather Buddy" headers and darker sleek bubbles.
- `[x]` 4. **Voice Button & Chips:** Update `VoiceInput.js` and `index.js` to implement the blue circle, waveform, and bottom-aligned suggestion chips.
- `[x]` 5. **Activity Pills:** Create `ActivityChips.js` and insert it above the `ComparisonCard` in `index.js`.
- `[x]` 6. **Dynamic Layout Toggle:** Update `index.js` so that if `ui_mode === "chat"`, the left column hides entirely and the chat view is centered.
- `[x]` 7. **Language Sync:** Update `index.js` to `setSelectedLang(response.lang)` upon receiving a backend response.
- `[x]` 8. **Scrolling Fix:** Fix CSS height/overflow in the conversation panel to prevent clipping.
