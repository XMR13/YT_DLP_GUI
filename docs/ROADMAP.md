# Roadmap: yt-dlp GUI (Modern • Fast • Lightweight)

This roadmap grows the app into a **modern, fast, lightweight** yt-dlp downloader.
Every phase is meant to be **shippable** and sized for a realistic release cadence.

## Product goals (what “next level” means)
- **Modern UX:** clear states, minimal friction, beautiful + consistent UI, sensible defaults.
- **Fast:** instant-feeling startup, no UI freezes, smooth scrolling for large queue/history.
- **Lightweight:** minimal dependencies, no always-on services, small-ish downloads (especially Lite).
- **Reliable formats:** when a video has 1080p60+ (or higher/FPS variants), users can pick it and get it.
- **Secure by default:** treat pasted URLs and on-disk JSON as untrusted; safe subprocess boundaries.

## Current status (as of 2026-02-05)

Already implemented (high level):
- Queue-first workflow + sequential runner + cancel/retry.
- History persisted to JSON with open folder + retry.
- Playlist preview + selection + per-item downloads.
- Windows packaging via PyInstaller; portable **Lite** and **Full** zips.
- Adapter tests exist for args + format/FPS parsing.
- Security baseline improvements:
  - Prevent yt-dlp option-injection (URLs passed after `--` + reject values starting with `-`).
  - Thumbnail fetch restricted to `http/https` + size cap.
  - Remote components default **None** (opt-in).

Known issue(s):
- Windows maximize/minimize can cause visible repaint/flash (likely CTk/Tk limitation; mitigate where possible).

## What makes it stand out (keep / amplify)
- Queue-first workflow: paste many URLs, press Start, walk away.
- Clear per-item states: queued/running/failed/cancelled with safe retry/cancel.
- Useful history: search, open output, retry without re-entering URLs.
- Smart defaults: minimal clicks, sane templates, consistent “open/copy” actions.
- Windows-first distribution: one portable `.zip` path (no auto-update required).

## Quality bar (non‑negotiables)
For every release:
- **UI never blocks** on network/subprocess work (controllers/worker threads only).
- **Cancel is safe** (no surprise retries after cancel; no unsafe cleanup).
- **No dangerous defaults** (remote components opt-in; runtime execution controlled).
- **Repro + tests** for any behavior change in adapter/controller.
- **Release notes** clearly explain Lite vs Full tradeoffs.

## Release phases (shippable)

### Phase A — Fix format availability (1080p60+ reliability) (next release)
Goal: if yt-dlp reports 1080p60+ formats, the GUI reliably shows and downloads them. If formats are skipped/limited, the app recovers automatically or explains why.

Deliverables
- Format listing resilience:
  - Detect “formats skipped” situations during *format fetch* (not only during download).
  - Add a controlled fallback strategy for YouTube format fetching when formats are missing/skipped (retry fetch with a safer alternative client/extractor-args path).
- Format selection clarity:
  - Labels must clearly show `height + fps` (and ideally ext/codec) so 1080p60 isn’t hidden.
  - If 60fps is not present, show an explicit UI hint (“No 60fps formats reported for this video”) rather than silently omitting.
- Regression coverage:
  - Unit tests for: distinct FPS variants, selection → correct `format_id` usage, fallback path selection.
  - Manual QA list (3–5 known 60fps URLs) maintained in docs/release checklist.

Done when
- For known 60fps sample videos, UI shows a 60fps option when yt-dlp exposes one.
- If yt-dlp emits a “skipped formats” warning, the app attempts a fallback and improves availability (or clearly states it can’t).
- Tests prevent regressions of FPS variants and fallback behavior.

Non-goals
- Full “format browser” UI (filters/search); that’s a later opt-in power feature.

### Phase B — UX glitches + modern polish (daily-use delight)
Goal: the app feels modern and stable: clean layout, consistent actions, fewer visual glitches.

Deliverables
- Glitch backlog + triage:
  - Track known UI glitches (resize/restore flash, clipping, scroll oddities) with status and mitigation attempts.
- Visual polish pass:
  - Consistent spacing/typography across Download/Queue/History.
  - Strong empty states (no queue/history/playlist loaded).
  - Clear “what is happening now” (running item title + progress detail always visible).
- Interaction polish:
  - Keyboard shortcuts for common actions (paste URL, start/stop, focus search).
  - Consistent “Open output folder” / “Copy path” placement and wording.

Done when
- No obvious layout breakage in normal window resizes/restores (or documented as upstream with best-known mitigation).
- First-time user can complete: paste → enqueue → start → find output in history without confusion.

### Phase C — Security + privacy hardening (focused release)
Goal: reduce foot-guns for a tool that runs external binaries and reads untrusted local state.

Deliverables
- Validate on load (queue/history):
  - Treat JSON as untrusted: schema-ish validation, drop/repair invalid fields safely.
  - Re-validate critical fields just before execution (`url`, `output_dir`, runtime path, option-like values).
- Runtime execution hardening:
  - Validate runtime paths exist + are files before running.
  - One-time confirmation when using a non-default/custom runtime path.
- Open-folder hardening:
  - Only open existing local directories; ignore/repair invalid paths from history.
- Logging privacy control:
  - Provide a user option to disable file logging **or** redact URLs by default (document tradeoff).

Done when
- Tampered `queue.json/history.json` cannot cause unsafe subprocess arguments or unsafe “open folder” behavior.
- Security regression tests cover URL validation and store validation.

### Phase D — Binary size + packaging efficiency (Lite + Full, measured)
Goal: keep downloads reasonable while preserving “it just works” for Full.

Reality check (documented in-app/docs)
- **Full will always be large** because it includes `ffmpeg.exe` + `ffprobe.exe`.
- **Lite exists to stay smaller**, but may require user-provided ffmpeg for merges/transcodes.

Deliverables
- Size budgeting:
  - Track Lite/Full zip sizes per release (release notes + internal checklist).
- Low-risk packaging wins:
  - Audit PyInstaller spec for excludes/unused modules (measured; reversible).
  - Evaluate UPX only if it meaningfully reduces size without harming startup or causing false positives.
- Docs + expectations:
  - Explain what drives size (Python runtime, UI deps, ffmpeg).
  - Clear user guidance: “If you want the smallest download, use Lite + install ffmpeg.”

Done when
- Size is measured and explained; no mystery bloat.
- Builds remain reproducible and smoke-tested.

### Phase E — Opt-in power features (keep default path simple)
Goal: add advanced features without burdening the default workflow.

Candidates (opt-in)
- Format browser (codec/bitrate filters; “why this format”).
- Subtitle + metadata controls.
- Audio conversion presets (mp3/m4a/flac) via yt-dlp post-processing.

Done when
- Power users can do advanced tasks without complicating default UI.

## Per-release checklist (short)
- Run tests (adapter/controller).
- Build Lite + Full zips.
- Smoke test:
  - Lite: basic download works.
  - Full: bestvideo+bestaudio merges successfully (ffmpeg used).
- Formats QA:
  - Confirm 60fps appears on known 60fps sample video(s).
- Security sanity:
  - Pasting a “URL” starting with `-` is rejected.
  - App doesn’t crash on partially corrupted queue/history.

## Decision points (locked unless strong reason)
- Persistence: JSON (revisit SQLite only if proven necessary).
- Concurrency: sequential downloads (for simplicity/reliability).
- Packaging: Windows portable via PyInstaller.
- Distribution: Lite + Full releases; Full includes ffmpeg; Lite may require external ffmpeg.
- Security: remote components remain opt-in; no hidden remote-code defaults.
