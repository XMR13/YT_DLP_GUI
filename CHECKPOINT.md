# CHECKPOINT (yt-dlp GUI)

Use this file to resume work after resetting Codex context.

## Current status (as of 2026-02-05)

### Implemented
- Fixed duplicate/invalid `--remote-components` arg behavior in `yt_dlp_adapter.py`.
- Added line endings policy via `.gitattributes` (`* text=auto eol=lf`).
- Added pytest import support via `pytest.ini` (`pythonpath = .`).
- Added adapter unit tests:
  - `tests/test_yt_dlp_adapter_args.py`
  - `tests/test_yt_dlp_adapter_formats.py` (FPS inference + distinct 30/60 variants)
- Added `docs/ROADMAP.md` with phased direction (lightweight + modern).
- Updated `AGENTS.md` with Python workflow + “Codex Medium vs High” guidance.
- Added playlist tab refactor + per-item selection + per-item download using `--playlist-items`:
  - `app.py`: `CTkTabview` (Single/Playlist), playlist actions, selection state, shared progress, duration in info.
  - `ui/playlist_form_panel.py`: playlist controls (fetch playlist, fetch selected formats, download selected, download playlist).
  - `ui/playlist_preview.py`: thumbnail list (Pillow) + duration, selectable rows, async thumbnail loading + caching.
  - `yt_dlp_adapter.py`: `PlaylistItem` dataclass, structured playlist preview extraction, thumbnail derivation for YouTube, added `playlist_items` support in `fetch_info()` and `download()`.
  - `controllers/download_controller.py`: pass `playlist_items` through; preview uses `PlaylistItem`.
- Added Pillow dependency (`pillow>=10.2.0`) to `pyproject.toml`.
- UI/UX updates:
  - Main content uses `CTkScrollableFrame`; playlist preview remains scrollable.
  - Global mouse-wheel routing targets playlist preview under cursor, else main content.
  - Playlist preview scroll speed matches main `SCROLL_SPEED`.
  - Status panel expands with the window (no manual height recompute).
- Playlist selection auto-fetches formats (debounced) with request-id gating to avoid stale updates.
- Selected playlist row shows size (estimated via tbr*duration when filesize missing).
- yt-dlp JS runtime/SABR warnings are shown only once per session to reduce log spam.
- Playlist preview enhancements:
  - Multi-select with hover highlight + header count (total items + selected count).
  - Lazy per-item fetch with per-index cache (duration/size updates on selection).
  - Total playlist count in header (when extractor provides it).
  - Load-more paging to append items beyond the first 20.
- Added left sidebar navigation with icons and page stack (Download + History).
- Added History (MVP):
  - Persistent JSON store in per-user app data (`controllers/history_store.py`).
  - History UI with Clear / Open folder / Retry (`ui/history_page.py`).
  - Download events now record history on complete/cancel/fail.
- Added Queue (v1):
  - Persistent JSON store + sequential runner (`controllers/queue_store.py`, `controllers/queue_runner.py`).
  - Downloads now enqueue (single/playlist/selected items) and run sequentially.
  - Queue UI page with Start/Stop/Cancel/Clear/Clear done + per-item Retry/Remove.
  - Status panel shows queue summary + running item + state (Running/Stopping/Idle/Stopped).
  - History records now come from queue item metadata.
- Queue polish:
  - Added move-to-top/move-to-bottom controls for queued items.
  - Added drag-and-drop reorder for queued items.
  - Added bulk selection actions (retry/remove) for queue items.
  - Virtualized queue list rendering via canvas row pool for large queues.
  - Status panel now shows a running activity line (title + percent/speed/ETA parsed from yt-dlp logs).
  - Added queue runner tests for move-to-top/bottom behavior.
- Download output capture:
  - `yt_dlp_adapter.download()` now returns output paths via `--print after_move`.
  - `DownloadController` emits `download_complete/cancelled/error` events.
  - History records include output file paths when available.
- Playlist preview virtualization:
  - Replaced internal list with a canvas row pool to reuse widgets while scrolling.
- Roadmap updated: repositioned the project around Queue + History + smart UX + Windows `.exe` distribution.
- Playlist selection hybrid details:
  - Selecting a playlist item triggers an info-only fetch to populate duration/uploader/thumbnail while formats load separately.
- Security hardening:
  - Prevent `yt-dlp` option injection by always passing URLs after `--` and rejecting values starting with `-`.
  - Thumbnail fetch is restricted to `http/https` and capped to 2 MiB per image.
  - Remote components default to `None` (opt-in).
- Video info panel clipping: reported fixed (reconfirm visually).
- Resize performance tweaks:
  - Main content now uses `CTkScrollableFrame` (removed custom canvas).
  - Scroll handling tuned; resize is live (no redraw-freeze).
- YouTube download fallback:
  - If 403/SABR warning occurs, retry download with `youtube:player_client=android`.
- Auto JS runtime:
  - In JS runtime "Auto" mode, app now auto-detects `node`/`deno`/`bun` and passes `--js-runtimes` when available (remote components are opt-in).
  - Download retry is now cancellation-aware (won’t start a retry after user hits Cancel).
- Mix handling:
  - Treat YouTube mix `list=RD...` URLs as single videos by default (avoid forced playlist flow).

### Session log (2026-02-05)
- Playlist lazy fetch performance:
  - Removed duplicate item-info + formats fetch on selection; selection now triggers a single debounced fetch path (formats+info in one request).
  - Added in-flight dedupe and request-id caching so rapid selection churn doesn’t start extra yt-dlp calls; results are cached even if selection changes mid-flight.
  - Lazy selection fetch is non-blocking (doesn’t disable UI controls).
- Per-row size metadata (fast + accurate):
  - Size estimation moved to `yt_dlp_adapter.py` helpers and now uses real `filesize/filesize_approx` when present.
  - Adds audio size for video-only streams (video+audio combined), with bitrate-duration fallback when needed.
  - Row sizes refresh when switching format type/resolution (uses cached per-item formats+info).
- Playlist preview thumbnails:
  - Deduped concurrent thumbnail downloads per URL to reduce thread churn.
- Tests:
  - Added `tests/test_playlist_size_metadata.py` for size calculation behavior.
- QA (scripted):
  - Verified: rapid selection churn triggers 1 fetch per index; reselect cached item triggers 0 new fetches; in-flight reselect does not duplicate requests; row size updates correctly for Video+Audio vs Audio only.
- Queue status clarity:
  - Auto-clear `completed` items from the queue when idle (keep queue focused on pending/failed/cancelled; completed lives in History).
  - Status panel no longer shows `done` counts.
- Playlist form layout:
  - Responsive reflow + restore-triggered relayout so "Fetch Playlist" doesn’t disappear after minimize/restore on narrower window widths.

### Known issues / Bugs to fix next
- Windows maximize/minimize still causes full repaint (visible flash). This appears to be a Tk/CTk limitation versus GPU-accelerated apps (VSCode/Firefox).

### FYI (not a bug)
- Playlist list shows `Size: fetch formats` because size is format-dependent; accurate size should be shown after fetching formats for selected item and choosing format, or by lazily fetching per-item formats.

## What’s next (recommended order)

### Phase 4 (next implementation phase)
1) Queue polish:
   - (Optional) Add more queue UX polish (e.g., multi-select actions, filtering/search).
2) Improve playlist row metadata (optional):
   - If selected item’s formats are loaded, update the row meta to show approximate size for the selected format.

### Next focus (UI performance)
- If performance is still an issue, consider virtualization for History list and reducing row widget complexity.

## Quick commands
- Install dev deps: `python -m pip install -e ".[dev]"`
- Run: `python app.py`
- Tests: `python -m pytest -q`
