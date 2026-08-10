# Product

<!-- impeccable:product-schema 1 -->

## Platform

adaptive

Current product target: native Windows desktop. No other platform is promised.

## Users

Software developers, AI engineers, computer engineers, and system architects who dictate technical language while working in coding agents, editors, terminals, chat tools, and architecture documents.

## Product Purpose

AgentWisper turns speech into paste-ready technical text from anywhere in Windows. Success means fast activation, dependable technical spelling, clear privacy boundaries, and almost no interruption to the user's current task.

## Positioning

Local-first developer dictation with an opinionated technical vocabulary and explicit control over local, Groq, or compatible transcription providers.

## Operating Context

- Invoked globally with a configurable push-to-talk hotkey, currently Right Ctrl by default.
- Used while another application has the user's active text cursor.
- A persistent desktop control exposes availability, listening, processing, success, and failure states.
- The main app manages transcript history and provider, microphone, hotkey, and paste settings.

## Capabilities and Constraints

- Windows desktop application using local HTML/CSS in WebView2, plus a tiny native Signal Node; no Electron runtime or background web server.
- Closing the management window hides it while dictation keeps running; a second launch reopens the existing instance.
- Local Parakeet v3, Groq, and custom OpenAI-compatible transcription providers.
- Local SQLite transcript history; audio is discarded after transcription.
- API keys are protected with Windows DPAPI.
- Must stay lightweight and avoid speculative features.
- The floating voice surface may learn from ambient dictation products but must not copy Wispr Flow's centered bar.

## Brand Commitments

- Product name: AgentWisper.
- Professional, precise, calm, and technically literate.
- Original interaction design rather than a visual clone.
- Plain language and honest provider/privacy state.

## Evidence on Hand

- Working desktop application and packaged Windows executable.
- Installed local Parakeet model.
- Automated tests covering providers, encrypted storage, hotkeys, history, and vocabulary correction.
- No customer claims, benchmarks, testimonials, or commercial proof should be fabricated.

## Product Principles

1. Stay out of the way until the user speaks.
2. Make recording and privacy state unmistakable.
3. Prefer technical accuracy over decorative intelligence.
4. Keep every persistent control justified by frequent use.
5. Make recovery obvious when transcription or paste fails.

## Accessibility & Inclusion

Maintain strong text contrast, keyboard-operable controls, readable status labels in addition to color, and motion that communicates state without blocking input.
