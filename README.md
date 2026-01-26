## yt-dlp GUI (MVP)

Simple Windows-friendly GUI wrapper around `yt-dlp`.

### Features
- Download from a single URL or playlist
- Fetch available resolutions and FPS
- Choose basic format (video+audio or audio-only)
- Optional cookies-from-browser support for restricted videos
- Optional JS runtime + EJS scripts source settings for signature/challenge solving

### Setup
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -e .
```

### Run
```bash
python main.py
```

### Notes on 403 / signature warnings
- If you see "Signature solving failed", select a JS runtime (node/deno/bun) and set
  "EJS scripts source" to `ejs:github` or `ejs:npm` in the UI, then retry.
