# Release Checklist (Windows Portable)

1. Update version in `pyproject.toml` (if needed).
2. Update pinned binary versions/hashes in `packaging/binaries.lock.json`.
3. Build artifacts:
   - `scripts\\build_windows.ps1`
4. Smoke test on a clean Windows machine:
   - Launch Lite zip: app opens, `yt-dlp: OK`, basic download works.
   - Launch Full zip: best video+audio download merges (ffmpeg is used).
   - Verify files appear under `%APPDATA%\\yt-dlp-gui\\`:
     - `history.json`, `queue.json`, `logs\\*.log`
5. Publish `*-lite.zip` and `*-full.zip` with notes:
   - Lite may require ffmpeg for some merges.
   - Full includes ffmpeg for out-of-box merges.

