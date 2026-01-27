# Roadmap: yt-dlp GUI (Lightweight + Modern)

This roadmap grows the app into a full-fledged downloader while keeping it small,
fast to launch, and maintainable. Each phase is meant to be shippable on its own.

## Product principles
- Lightweight: minimal dependencies, fast startup, no always-on background services.
- Modern UX: clear states, safe cancellation, helpful errors, sane defaults.
- Maintainable: clean boundaries (UI vs controller vs adapter), testable logic.
- Optional power features: advanced features should not burden basic usage.

## Phase 0: Stability and correctness
Focus: polish the core loop and prevent regressions.

Deliverables
- Correct, deterministic adapter argument building.
- Regression tests for adapter arg combinations.
- Clear error surfacing and safe cancel behavior.

Done when
- Tests cover the arg matrix (runtime/path/remote-components).
- No duplicate or invalid flags are emitted.
- Errors are actionable and appear in status log and popup.

Non-goals
- Large UI changes.
- Advanced download queue features.

## Phase 1: UX clarity (still minimal)
Focus: smoother day-to-day experience without adding complexity.

Deliverables
- Better status clarity (current item title, speed, ETA parsing if available).
- "Open output folder" action.
- Safer defaults for output template and filename sanitization.
- Clearer playlist mode indicator.

Done when
- Users can understand what is happening at a glance.
- Basic UX actions are no more than 1-2 clicks away.

Non-goals
- Background download manager or service.
- Persistent queue/history.

## Phase 2: Queue and history (lightweight persistence)
Focus: process multiple URLs reliably with minimal state.

Deliverables
- Queue multiple URLs and playlist items.
- Per-item cancel/retry.
- History panel (persisted to JSON or SQLite, decided at phase start).

Done when
- Users can paste many URLs and walk away.
- History is readable and can be cleared.

Non-goals
- Complex scheduling or rate-based scheduling.

## Phase 3: Power features (opt-in)
Focus: advanced options that stay out of the default path.

Deliverables
- Format browser (codec/bitrate filtering).
- Subtitle and metadata controls.
- Audio conversion presets (mp3/m4a/flac) using yt-dlp post-processing.

Done when
- Power users can access advanced options without affecting basic flow.

Non-goals
- Full media library management.

## Phase 4: Distribution
Focus: easy install for Windows users.

Deliverables
- PyInstaller packaging plan and build script.
- Optional: versioned releases and changelog.

Done when
- A non-developer can download and run with no Python setup.

Non-goals
- Auto-update infrastructure (can be considered later).

## Decision points (to resolve at phase boundaries)
- Persistence: JSON vs SQLite for history and queue.
- Packaging target: Python-only vs Windows executable.
- Whether to expose a small "manager" API for integration into other Python projects.
