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
5. Phase A format QA (manual):
   - Test at least 3 known YouTube videos that should expose 60fps formats.
   - Confirm the resolution menu shows a 60fps option when yt-dlp reports one.
   - If 60fps is not available, confirm the status log shows the no-60fps hint.
6. Publish `*-lite.zip` and `*-full.zip` with notes:
   - Lite may require ffmpeg for some merges.
   - Full includes ffmpeg for out-of-box merges.
