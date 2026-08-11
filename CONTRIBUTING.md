# Contributing to AgentWisper

Thank you for helping improve developer-focused dictation. Keep changes small,
testable, privacy-conscious, and aligned with the Windows desktop scope.

## Before starting

1. Search existing issues and pull requests.
2. Open an issue before large UI, provider, storage, or architecture changes.
3. Never include API keys, transcripts, private repository content, model
   files, personal paths, or generated build output in a contribution.
4. Report security problems through [SECURITY.md](SECURITY.md), not a public
   issue containing exploit details.

## Development setup

Requirements: Windows, Python 3.11, uv, Node.js for the JavaScript syntax check,
and WebView2 for UI testing.

```powershell
git clone https://github.com/Rajveerx11/AgentWisper.git
Set-Location AgentWisper
uv venv .venv --python 3.11
uv sync --locked --extra dev
```

Run the desktop app:

```powershell
.\run-app.ps1
```

## Make a focused change

- Create a branch from the latest `main`.
- Follow existing module boundaries and plain-language UI copy.
- Avoid unrelated refactors or speculative features.
- Preserve local-first behavior and explicit cloud-provider boundaries.
- Add tests for new behavior and failure paths.
- Update README, architecture, security, or changelog documentation when the
  public contract changes.

## Required checks

Run these before opening a pull request:

```powershell
uv lock --check
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest
node --check src\agent_whisper\web\app.js
uv build
.\build.ps1
```

For UI changes, also launch the packaged app and verify Speak, History,
Settings, Signal Node, keyboard focus, scaling, and close-to-background behavior
on Windows.

## Pull requests

A ready pull request should include:

- the user-visible problem and outcome;
- important privacy, security, or compatibility effects;
- exact test and manual verification evidence;
- screenshots for visible UI changes;
- a rollback note for risky changes.

Use a Conventional Commit-style title when practical, for example:

```text
feat: add microphone selector
fix: preserve paste target after overlay click
docs: clarify local model setup
```

Maintainers may ask to split oversized pull requests. CI must pass before
merge.

## Licensing contributions

By submitting a contribution, you agree that it may be distributed under the
project's [MIT License](LICENSE). Do not contribute code, media, model files, or
other material that you do not have permission to redistribute. Record new
runtime dependencies in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and
ensure their required license files are included in packaged builds.
