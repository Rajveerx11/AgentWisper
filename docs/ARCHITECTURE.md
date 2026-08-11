# AgentWisper Architecture

## System overview

AgentWisper is a Windows desktop process with a local WebView2 management UI,
a native always-on-top Signal Node, a global push-to-talk listener, and one
selected transcription provider. No local HTTP server or Electron runtime is
used.

```mermaid
flowchart TB
    HK["Global hotkey listener"] --> DC["DesktopController"]
    SN["Signal Node"] --> DC
    WV["WebView2 UI"] --> API["Explicit DesktopApi bridge"] --> DC
    DC --> AR["AudioRecorder"]
    AR --> LP["LocalTranscriberPool"]
    AR --> CP["CloudTranscriber"]
    LP --> CE["CorrectionEngine"]
    CP --> CE
    VS["VocabularyStore"] --> CE
    RS["Bounded repository scan"] --> CE
    CE --> HS["SQLite HistoryStore"]
    CE --> PT["Active cursor paste"]
```

## Main components

| Component | Responsibility |
| --- | --- |
| `gui.py` | Single-instance Windows lifecycle, WebView2 host, explicit bridge methods |
| `desktop.py` | Thread-safe recording, provider, correction, history, and paste orchestration |
| `overlay.py` | Persistent Signal Node and desktop recording feedback |
| `audio.py` | Microphone stream and in-memory sample collection |
| `providers.py` | Local model pooling and cloud transcription requests |
| `vocabulary.py` | Built-in, repository, and learned technical correction rules |
| `storage.py` | Versioned settings, DPAPI secrets, vocabulary JSON, SQLite history |
| `web/` | Local HTML, CSS, and JavaScript application UI |

## Dictation lifecycle

1. Hotkey press captures the current external foreground window and starts the
   microphone stream.
2. Hotkey release stops recording and snapshots current settings.
3. The selected local or cloud provider transcribes the in-memory audio.
4. `CorrectionEngine` applies learned, repository, then built-in rules without
   cascading over newly inserted spellings.
5. Corrected and raw text are stored locally in SQLite.
6. When enabled, the previous foreground window is restored and the corrected
   text is pasted. Existing clipboard text is restored on a best-effort basis.

Controller states are `idle`, `listening`, `transcribing`, `success`, and
`error`. The controller lock protects transitions and settings replacement.

## Privacy boundaries

```mermaid
flowchart LR
    subgraph PC["Windows user profile"]
        AUDIO["Microphone audio"]
        TERMS["Project and learned terms"]
        HISTORY["Transcript history"]
        KEYS["DPAPI-encrypted keys"]
        LOCAL["Local Parakeet"]
    end
    CLOUD["Selected cloud provider"]
    AUDIO --> LOCAL
    AUDIO -->|"Only when cloud selected"| CLOUD
    TERMS --> LOCAL
    CLOUD -->|"Raw transcript"| TERMS
```

- Repository terms and learned corrections do not enter cloud prompts.
- Audio is not saved by AgentWisper.
- History and settings remain in `%APPDATA%\AgentWisper`.
- Cloud privacy and retention are controlled by the chosen provider.

## Repository vocabulary bounds

The repository scanner follows no symlinks, skips common dependency/build/cache
directories, inspects at most 2,000 files, reads at most 1 MB per supported
manifest, and returns at most 500 usable terms. Learned storage accepts at most
500 mappings and 20 spoken forms for one exact spelling.

## Packaging

PyInstaller creates an onedir Windows distribution. The ONNX speech model stays
external. The package includes:

- AgentWisper executable and runtime dependencies;
- local WebView UI assets;
- project license and notices;
- available license files for bundled runtime Python distributions.

Tag-based release automation verifies that the Git tag matches
`agent_whisper.__version__`, creates a ZIP, produces a SHA-256 checksum, and
publishes both to GitHub Releases.

## Design constraints

- Windows is the only promised platform.
- The main window may hide, but the process and hotkey remain active.
- Cloud use must be explicit and accurately labeled.
- No repository execution, telemetry, account system, or background web server.
- New persistent controls require a frequent developer-dictation use case.

