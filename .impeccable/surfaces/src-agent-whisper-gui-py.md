---
version: 1
slug: "src-agent-whisper-gui-py"
primary_target: "src/agent_whisper/gui.py"
related_targets: ["src/agent_whisper/hotkeys.py"]
---

# AgentWisper desktop surface

- Scope: `src/agent_whisper/gui.py`, main Windows app plus persistent floating voice control.
- Mode: Operate.
- Audience: technical professionals dictating into coding agents and developer tools.
- Job: start dictation without leaving the active app, understand state instantly, recover the latest transcript, and configure provider/privacy controls.
- Primary action: start or stop dictation with Right Ctrl or the floating control.
- Chosen direction: Signal Desk, a light Windows workbench derived from audio patch bays and signal routing.
- Memorable moment: the bottom-right Signal Node fans one routed line into three live traces while listening, then resolves into a green completion path.
- Approved composition: `.impeccable/mocks/signal-desk-approved.png`.
- Constraints: no Wispr Flow clone, no centered bar, no fake metrics, no live transcript before the provider returns one, no feature expansion, no Electron.
- Unresolved: custom icon and code signing are outside this UI pass.

## Implementation inventory

| Ingredient | Medium | Decision |
| --- | --- | --- |
| Main navigation and title rail | Local HTML/CSS in WebView2 | Produce |
| Signal route stage | HTML Canvas | Produce |
| Latest transcript and history | Semantic local HTML | Produce |
| Persistent Signal Node | Frameless topmost WebView2 child process | Produce |
| Icons and signal glyphs | Inline SVG, Canvas, and CSS geometry | Produce |
| State motion | Bounded requestAnimationFrame and CSS motion | Produce |
| Raster imagery | None | Intentionally omitted |

## Direction contract

- THESIS: Dictation is a visible route from microphone to model to cursor; reject the generic dark card dashboard and the giant microphone button.
- OWN-WORLD: Mineral-gray work surface, paper-white content, deep navy ink, cobalt interaction, jade success, carbon floating control, precise rules and routed nodes.
- STORY: See readiness and privacy, invoke speech, watch the signal move, receive paste-ready technical text, recover it from history.
- FIRST VIEWPORT: Compact title rail and left navigation frame one signal stage, one latest-transcript surface, and a small action area; no decorative analytics.
- FORM: Focused command surface using grounded direction 4, audio patch-bay signal routing, with command-sentence staging; concept seed `c63dcfa6`.
