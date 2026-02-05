# Roadmap: yt-dlp GUI (Lightweight + Modern)

This roadmap grows the app into a full-fledged downloader while keeping it small,
fast to launch, and maintainable. Each phase is meant to be shippable on its own.

## Product principles
- Lightweight: minimal dependencies, fast startup, no always-on background services.
- Modern UX: clear states, safe cancellation, helpful errors, sane defaults.
- Maintainable: clean boundaries (UI vs controller vs adapter), testable logic.
- Optional power features: advanced features should not burden basic usage.

## What makes it stand out
- Queue-first workflow: paste many URLs, start once, walk away.
- Clear per-item states: queued/running/completed/failed/cancelled, with safe cancel/retry.
- Useful history: search, open file/folder, and retry without re-entering URLs.
- Smart UX: fast startup (no UI freeze), minimal clicks, sensible defaults.
- Windows-first distribution: one `.exe` build path via PyInstaller (no auto-update).

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

## Phase 1: UX clarity + daily-use polish
Focus: make day-to-day usage smooth and obvious without adding heavy features.

Deliverables
- Status clarity: current item title + percent; best-effort speed/ETA parsing.
- Output actions: "Open output folder" and "Copy output path".
- Safer defaults: output template + filename sanitization (simple, predictable).
- Startup performance: non-blocking checks (yt-dlp availability/version); no UI freeze.

Done when
- Users can understand progress at a glance.
- Startup feels instant and responsive.

Non-goals
- Background download manager/service.
- Parallel downloads.

## Phase 2: Queue and history (lightweight persistence)
Focus: make the app a reliable downloader for many items, with lightweight persistence.

Deliverables
- Queue: add multiple URLs and playlist items, dedupe, reorder, remove, clear.
- Sequential runner: 1 active download at a time; per-item cancel/retry.
- Queue items snapshot settings at enqueue-time (format/audio-only/output/cookies/js-runtime/EJS source).
- Queue UI (basic list + actions) and compact queue status summary in the Status panel.
- History persisted to JSON: search + filter + retry + open file/folder.
- Per-item failures show reason and a clear "Retry" action.

Done when
- Users can paste many URLs, press Start, walk away, and reliably find outputs later.
- History is readable, searchable, and actionable (open/retry/clear).

Non-goals
- Complex scheduling or rate rules.
- Parallel workers.

## Phase 3: Distribution (Windows .exe)
Focus: easy install for Windows users.

Deliverables
- PyInstaller build plan and build script.
- Windows `.exe` packaging notes (what is bundled vs required).
- Minimal release checklist (no auto-update infrastructure).

Done when
- A non-developer can download and run with no Python setup.

Non-goals
- Auto-update infrastructure (can be considered later).

## Phase 4: Power features (opt-in)
Focus: advanced options that stay out of the default path.

Deliverables
- Format browser (codec/bitrate filtering).
- Subtitle and metadata controls.
- Audio conversion presets (mp3/m4a/flac) using yt-dlp post-processing.

Done when
- Power users can access advanced options without affecting basic flow.

Non-goals
- Full media library management.

## Decision points (to resolve at phase boundaries)
- Persistence format: JSON (locked; revisit SQLite only if needed).
- Packaging: Windows `.exe` via PyInstaller (locked).
- Concurrency: sequential downloads (locked for now).
- Optional: expose a small "manager" API for integration into other Python projects.
