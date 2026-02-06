## yt-dlp GUI

Simple Windows-friendly GUI wrapper around `yt-dlp`.

### Highlights
- Download: single URL or playlist (including selected playlist items).
- Formats: fetch available resolutions/FPS and pick video+audio or audio-only.
- Playlist preview: thumbnails, multi-select, and "Load more" paging.
- History (MVP): persisted download history with Open folder + Retry.
- Optional: cookies-from-browser and JS runtime + EJS scripts source for YouTube challenges.

See `CHECKPOINT.md` for recent changes.

### Setup (dev)

Create a venv and install dependencies:

```bash
python -m venv .venv
```

Activate:

- Windows (PowerShell):
  ```powershell
  .venv\Scripts\Activate.ps1
  ```
- Windows (cmd):
  ```bat
  .venv\Scripts\activate.bat
  ```
- macOS/Linux:
  ```bash
  source .venv/bin/activate
  ```

Install:

```bash
python -m pip install -e ".[dev]"
```

### Run

```bash
python app.py
```

### Logs

- Each run writes a log file in the per-user app data folder.
  - Windows: `%APPDATA%\\yt-dlp-gui\\logs\\`
  - macOS: `~/Library/Application Support/yt-dlp-gui/logs/`
  - Linux: `${XDG_DATA_HOME:-~/.local/share}/yt-dlp-gui/logs/`

### History storage

History is stored as JSON in the per-user app data folder:

- Windows: `%APPDATA%\yt-dlp-gui\history.json`
- macOS: `~/Library/Application Support/yt-dlp-gui/history.json`
- Linux: `${XDG_DATA_HOME:-~/.local/share}/yt-dlp-gui/history.json`

### Notes on 403 / signature warnings

- If you see "Signature solving failed", select a JS runtime (node/deno/bun) and set
  "EJS scripts source" to `ejs:github` or `ejs:npm` in the UI, then retry.

### Windows portable build

See `packaging/README_WINDOWS.md` and `scripts/build_windows.ps1`.
