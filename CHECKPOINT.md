# CHECKPOINT (yt-dlp GUI)

Use this file to resume work after resetting Codex context.

## Current status (as of 2026-01-27)

### Implemented
- Fixed duplicate/invalid `--remote-components` arg behavior in `yt_dlp_adapter.py`.
- Added line endings policy via `.gitattributes` (`* text=auto eol=lf`).
- Added pytest import support via `pytest.ini` (`pythonpath = .`).
- Added adapter unit tests:
  - `tests/test_yt_dlp_adapter_args.py`
  - `tests/test_yt_dlp_adapter_formats.py` (FPS inference + distinct 30/60 variants)
- Added `ROADMAP.md` with phased direction (lightweight + modern).
- Updated `AGENTS.md` with Python workflow + “Codex Medium vs High” guidance.
- Added playlist tab refactor + per-item selection + per-item download using `--playlist-items`:
  - `app.py`: `CTkTabview` (Single/Playlist), playlist actions, selection state, shared progress, duration in info.
  - `ui/playlist_form_panel.py`: playlist controls (fetch playlist, fetch selected formats, download selected, download playlist).
  - `ui/playlist_preview.py`: thumbnail list (Pillow) + duration, selectable rows, async thumbnail loading + caching.
  - `yt_dlp_adapter.py`: `PlaylistItem` dataclass, structured playlist preview extraction, thumbnail derivation for YouTube, added `playlist_items` support in `fetch_info()` and `download()`.
  - `controllers/download_controller.py`: pass `playlist_items` through; preview uses `PlaylistItem`.
- Added Pillow dependency (`pillow>=10.2.0`) to `pyproject.toml`.
- UI/UX updates:
  - Main content uses a lightweight canvas scroll container; playlist preview remains scrollable.
  - Global mouse-wheel routing targets playlist preview under cursor, else main content.
  - Playlist preview scroll speed matches main `SCROLL_SPEED`.
  - Status panel expands with the window (no manual height recompute).
  - Playlist selection auto-fetches formats (debounced) with request-id gating to avoid stale updates.
  - Selected playlist row shows size (estimated via tbr*duration when filesize missing).
  - yt-dlp JS runtime/SABR warnings are shown only once per session to reduce log spam.
- Video info panel clipping: reported fixed (reconfirm visually).
- Resize performance tweaks:
  - Reintroduced main scroll with a lightweight canvas (custom scrollregion updates) and grid layout.
  - Windows-only redraw freeze during active resize to reduce lag/re-render flashes.
  - Scroll handling tuned; current feel acceptable (latest feedback).
- YouTube download fallback:
  - If 403/SABR warning occurs, retry download with `youtube:player_client=android`.
- Auto JS runtime:
  - In JS runtime "Auto" mode, app now auto-detects `node`/`deno`/`bun` and passes `--js-runtimes` + `--remote-components` for EJS challenge solving when available.
  - Download retry is now cancellation-aware (won’t start a retry after user hits Cancel).
- Mix handling:
  - Treat YouTube mix `list=RD...` URLs as single videos by default (avoid forced playlist flow).

### Known issues / Bugs to fix next
- Resize lag/jitter when dragging window:
  - Suspected cause: canvas-based scrollable frame + dynamic resizing churn.
  - Current mitigation: lightweight canvas scroll + redraw freeze.
  - If it resurfaces: consider removing remaining scrollable frames or switching to a non-canvas layout for the playlist preview.
  - If scroll jitter returns: disable CTk’s internal wheel handling on the preview scrollable.

### FYI (not a bug)
- Playlist list shows `Size: fetch formats` because size is format-dependent; accurate size should be shown after fetching formats for selected item and choosing format, or by lazily fetching per-item formats.

## What’s next (recommended order)

### Phase 4 (next implementation phase)
1) Finish addressing resize lag/jitter (verify after the mitigations above):
   - If needed: switch dynamic layout update to a larger debounce (e.g. 120-200ms) and/or apply only after resize settles.
2) Lazy item details on selection (hybrid):
   - When selecting a playlist item, fetch full info for that item (or use playlist index via `--playlist-items`) to populate:
     - duration (if missing), uploader/channel, thumbnail override, and enable showing accurate size after formats load.
3) Improve playlist row metadata (optional):
   - If selected item’s formats are loaded, update the row meta to show approximate size for the selected format.

### Next focus (UI performance)
- Resize lag/jitter when dragging window:
  - Reduce layout churn by throttling resize handlers and avoiding repeated scroll-region recalcs.
  - Cache widget heights during resize to avoid repeated `winfo_height()` calls.
  - Prefer `after_idle` batching and skip layout updates while user is dragging (resume on settle).

## Quick commands
- Install dev deps: `python -m pip install -e ".[dev]"`
- Run: `python app.py`
- Tests: `python -m pytest -q`
