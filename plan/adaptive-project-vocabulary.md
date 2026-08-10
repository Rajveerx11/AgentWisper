# Adaptive Project Vocabulary

## Goal

Make AgentWisper learn developer-specific language without sending repository data or corrections off the PC.

## User-visible outcome

1. A user can select one local project folder in Settings.
2. AgentWisper scans a bounded set of dependency manifests and technical filenames, then corrects spoken forms to their exact project spelling.
3. Every History item offers **Teach correction**. The user enters what AgentWisper heard and the exact spelling it should use.
4. Learned corrections appear in Settings and can be removed individually.
5. Project terms and learned corrections apply to subsequent local or cloud transcripts.
6. Existing provider, hotkey, history, paste, privacy, and background behavior remains intact.
7. Local Parakeet remains preloaded so first-use latency does not return.

## Scope

### In scope

- One optional local project folder.
- Bounded local scan of existing supported manifests and distinctive file identifiers.
- Durable `%APPDATA%\AgentWisper\vocabulary.json` storage with atomic writes.
- Explicit learned pairs: `heard phrase` to `exact spelling`.
- History teaching dialog, vocabulary list, removal, project term count.
- Input validation and limits that keep regex correction predictable.
- Automated backend/UI-contract tests, production package build, installed-app smoke test.

### Out of scope

- Screen scraping, automatic foreground-project detection, IDE extensions, Git indexing, or cloud repository access.
- LLM rewriting, voice commands, meeting transcription, TTS, telemetry, or accounts.
- Multiple simultaneous project profiles.
- Editing repository files.

## Constraints

- Repository contents, learned terms, history, and audio stay local unless a cloud transcription provider is selected; only recorded audio and the existing technical prompt reach that provider.
- Scan at most 2,000 files, skip dependency/build/cache directories, and tolerate unreadable files.
- Read at most 1 MB from each supported manifest and inspect at most 2,000
  manifest dependency entries.
- Store at most 500 learned heard-to-spelling pairs total and 20 spoken forms per
  spelling within that total cap.
- Never execute repository content or follow it as instructions.
- Preserve fast warm transcription: 3.3 seconds of test speech should remain near the measured 0.3-second decode after model preparation.
- Keep interface within existing three pages and Signal Desk visual system.

## Implementation

1. Add validated `VocabularyStore` and learned-term records in `storage.py`.
2. Harden and reuse `scan_repository`; keep scan bounded and local.
3. Add `project_path` to versioned settings and rebuild `CorrectionEngine` when settings or learned terms change.
4. Add explicit bridge methods to teach, forget, and read vocabulary state.
5. Add one Settings section for project context and learned terms.
6. Add an accessible teaching dialog opened from each History row.
7. Update product/readme documentation and release version.
8. Run lint, unit tests, JavaScript syntax validation, real transcription benchmark, PyInstaller build, install smoke test, independent review, PR publication, and GitHub CI.

## Acceptance evidence

- A repository dependency or filename spoken with spaces is corrected to exact project spelling.
- A learned alias persists across a fresh store/controller and corrects later speech.
- Duplicate, empty, oversized, or excessive vocabulary entries are rejected safely.
- Removing a learned pair stops that custom correction without affecting built-ins.
- UI bundle contains project controls and accessible teaching dialog; bridge exposes only explicit methods.
- `ruff`, `pytest`, JavaScript syntax check, PyInstaller, installed app, independent review, and GitHub Actions all pass.

## Delivery checkpoint

- Base: `main` at `2c4b1e01c990b0cd82a6722c12fe36c252cd65bc`
- Branch: `codex/adaptive-project-vocabulary`
- Existing PR: none
- Required CI: `.github/workflows/test.yml` Windows lint, tests, PyInstaller
- Preserved prior work: uncommitted 0.5.1 local-model preload changes
- Merge: explicitly excluded; human decision required
