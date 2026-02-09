# Windows Packaging (Portable Zip)

This project ships as a portable zip for Windows users.

## Artifacts
- Lite: includes `yt-dlp-gui.exe` + `yt-dlp.exe`
- Full: includes Lite + `ffmpeg.exe` + `ffprobe.exe`

The app writes user data to `%APPDATA%\\yt-dlp-gui\\` (history/queue/logs).

## Branding assets
- Runtime logo/icon source: `assets/icon.png`
- Windows app icon (`.exe` and title bar): `assets/app_icon.ico`
- To rebrand, replace those files and rebuild with `scripts\build_windows.ps1`.

## Overrides
- `YTDLP_GUI_YTDLP_PATH`: path to a `yt-dlp` executable.
- `YTDLP_GUI_FFMPEG_DIR`: directory containing `ffmpeg.exe` and `ffprobe.exe`.

## Build (Windows)
Run:
```powershell
scripts\build_windows.ps1
```

This produces zip files under `dist\\`.
