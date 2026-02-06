from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _frozen_app_dir() -> Optional[Path]:
    if not _is_frozen():
        return None
    try:
        return Path(sys.executable).resolve().parent
    except Exception:
        return None


def resolve_yt_dlp_bin() -> str:
    override = (os.environ.get("YTDLP_GUI_YTDLP_PATH") or "").strip()
    if override:
        return override

    app_dir = _frozen_app_dir()
    if app_dir:
        candidate = app_dir / "yt-dlp.exe"
        if candidate.is_file():
            return str(candidate)

    which = shutil.which("yt-dlp")
    return which or "yt-dlp"


def resolve_ffmpeg_location_dir() -> Optional[str]:
    override = (os.environ.get("YTDLP_GUI_FFMPEG_DIR") or "").strip()
    if override:
        return override

    app_dir = _frozen_app_dir()
    if app_dir:
        ffmpeg = app_dir / "ffmpeg.exe"
        ffprobe = app_dir / "ffprobe.exe"
        if ffmpeg.is_file() and ffprobe.is_file():
            return str(app_dir)

    ffmpeg_which = shutil.which("ffmpeg")
    ffprobe_which = shutil.which("ffprobe")
    if ffmpeg_which and ffprobe_which:
        try:
            ffmpeg_dir = Path(ffmpeg_which).resolve().parent
            ffprobe_dir = Path(ffprobe_which).resolve().parent
            if ffmpeg_dir == ffprobe_dir:
                return str(ffmpeg_dir)
        except Exception:
            return None
    return None
