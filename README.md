# AgentWisper

Minimal, local-first voice dictation for developers using coding agents.

AgentWisper records from a global hotkey, shows a compact live waveform, transcribes through local Parakeet or a selected cloud provider, fixes common technical terms, pastes at the active cursor, and keeps searchable history on the PC.

## What is included

- Native Windows desktop interface
- Right Ctrl toggle-to-talk hotkey, changeable in Settings
- Persistent bottom-right Signal Node with idle, listening, processing, success, and error states
- Local Parakeet TDT 0.6B v3 transcription
- Groq Cloud using `whisper-large-v3-turbo` or `whisper-large-v3`
- Custom OpenAI-compatible transcription endpoint
- Windows DPAPI-encrypted API keys
- Local SQLite transcript history
- Technical vocabulary correction
- Automatic cursor paste with clipboard restoration

No account, analytics, online database, Electron runtime, saved recordings, or background web server.

## Screens

### Speak

Shows the selected provider, one recording control, current state, and latest transcript.

### History

Stores corrected and raw transcripts locally in `%APPDATA%\AgentWisper\history.db`.

### Settings

Select Local, Groq, or a custom OpenAI-compatible provider. Configure the hotkey, microphone, language, model, and paste behavior.

Right Ctrl is the default. The editable hotkey dropdown also offers Left Ctrl, F8, and two Ctrl combinations.

## Tech stack

- Python 3.11
- Tkinter native UI
- sherpa-onnx and local Parakeet
- sounddevice microphone capture
- SQLite from the Python standard library
- Windows DPAPI through `ctypes`
- Standard-library HTTPS client for cloud transcription

## Quick start

### Install as a Windows desktop app

```powershell
.\build.ps1
.\install.ps1
```

This installs AgentWisper for the current user, registers it in Windows Installed Apps, and creates a Start Menu entry searchable as `AgentWisper`. Application files go to `%LOCALAPPDATA%\Programs\AgentWisper`; private settings and history remain in `%APPDATA%\AgentWisper`.

The main window is a light signal-routing workspace. The always-on-top Signal Node stays at the bottom-right of the desktop: click it or press the configured hotkey to start and stop dictation; right-click it to reopen the main window.

To remove the application while keeping its settings and transcript history:

```powershell
& "$env:LOCALAPPDATA\Programs\AgentWisper\uninstall.ps1"
```

### Run from source

```powershell
uv venv .venv --python 3.11
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
.\run-app.ps1
```

The local model is auto-detected at:

```text
%APPDATA%\orca\speech-models\parakeet-tdt-0.6b-v3-int8
```

AgentWisper reads the model without copying or modifying it. A different compatible model folder can be selected in Settings.

## Providers

### Local Parakeet

Audio stays in memory and is processed on-device. Nothing is uploaded.

### Groq

AgentWisper calls Groq's OpenAI-compatible audio transcription endpoint. Enter a Groq API key in Settings; it is encrypted for the current Windows user with DPAPI. Selecting Groq means recorded audio is sent to Groq. See [Groq Speech-to-Text documentation](https://console.groq.com/docs/speech-to-text).

### Custom compatible provider

Enter an API base URL, model ID, and key. HTTPS is required. Plain HTTP is accepted only for `localhost`, allowing local tools such as LM Studio-compatible gateways.

## Privacy and security

- Audio is held in memory and discarded after transcription.
- History remains in the Windows user profile.
- API keys are never written as plaintext.
- API keys are never logged or included in transcript history.
- Cloud calls happen only when a cloud provider is selected.
- Provider URLs cannot contain embedded credentials, query strings, or fragments.
- Existing clipboard text is restored after paste when enabled.
- `.env`, credentials, build output, and local configuration are excluded from Git.

DPAPI protects secrets from repository leakage and offline copying into another Windows account. It cannot protect against malware already running as the same Windows user.

## Test

```powershell
.venv\Scripts\python.exe -m pytest
```

## Build Windows app

```powershell
.\build.ps1
```

Output:

```text
dist\AgentWisper\AgentWisper.exe
```

The ONNX model is intentionally external and is not bundled into the executable directory.

## Project layout

```text
src/agent_whisper/gui.py          Desktop UI and recording workflow
src/agent_whisper/providers.py    Local, Groq, and compatible providers
src/agent_whisper/storage.py      Settings, encrypted secrets, SQLite history
src/agent_whisper/audio.py        Microphone and WAV handling
src/agent_whisper/vocabulary.py   Technical correction rules
```

## License

MIT
