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

### Known issues / Bugs to fix next
- Video info panel still gets clipped/looks wrong (Title display). Attempts in `ui/info_panel.py` (wrap labels, then CTkTextbox for title) did not fix it reliably. Needs a clean UI fix:
  - Likely solution: increase info panel height / ensure the body frame layout allows vertical expansion, and/or use a scrollable container for info fields.
  - Confirm whether issue is: lack of vertical space (panel too short) vs widget not expanding vs text rendering bug.

### FYI (not a bug)
- Playlist list shows `Size: fetch formats` because size is format-dependent; accurate size should be shown after fetching formats for selected item and choosing format, or by lazily fetching per-item formats.

## What’s next (recommended order)

### Phase 4 (next implementation phase)
1) Fix the Video info panel layout properly (stop clipping):
   - Prefer a dedicated `InfoPanel` layout with fixed minimum height and proper row weights; or switch the whole info area to a read-only textbox/grid that expands.
2) Lazy item details on selection (hybrid):
   - When selecting a playlist item, fetch full info for that item (or use playlist index via `--playlist-items`) to populate:
     - duration (if missing), uploader/channel, thumbnail override, and enable showing accurate size after formats load.
3) Improve playlist row metadata (optional):
   - If selected item’s formats are loaded, update the row meta to show approximate size for the selected format.

## Quick commands
- Install dev deps: `python -m pip install -e ".[dev]"`
- Run: `python app.py`
- Tests: `python -m pytest -q`

