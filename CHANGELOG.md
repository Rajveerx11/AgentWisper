# Changelog

Notable changes to AgentWisper are documented here. The project follows
[Semantic Versioning](https://semver.org/) while public APIs remain subject to
change before version 1.0.

## [Unreleased]

### Added

- Conservative local speech-filler cleanup with raw transcript recovery.
- Real microphone-level animation in the main window and Signal Node.
- Silence trimming and a short release tail for faster, more complete results.
- Optional Start with Windows registration, direct background hiding, and an
  explicit in-app Quit action.

### Changed

- Rebuilt the floating Signal Node with local HTML, CSS, and JavaScript.
- Hardened Signal Node sizing so WebView backgrounds cannot appear around it.
- Added the waveform-to-cursor AgentWisper mark.
- Documented close-to-background, single-instance reopening, startup, and quit
  behavior.
- Professional project documentation, contribution guidance, licensing
  notices, CI, and release automation.

### Fixed

- Fixed Signal Node rounding on 64-bit Windows and per-monitor DPI scaling.
- Removed viewport width math that could squeeze or crop Settings content.

## [0.6.0] - 2026-08-10

### Added

- Optional bounded repository scan for project-specific spellings.
- Corrections taught directly from transcript history.
- Durable local vocabulary management in Settings.
- Background preloading for the local Parakeet model.

### Changed

- Correction matching now preserves custom exact spellings and remains fast at
  configured vocabulary limits.
- Windows package and installer metadata updated to 0.6.0.

[Unreleased]: https://github.com/Rajveerx11/AgentWisper/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/Rajveerx11/AgentWisper/releases/tag/v0.6.0
