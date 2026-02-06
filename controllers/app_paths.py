from __future__ import annotations

import os
import sys
from pathlib import Path


def resolve_app_data_dir(app_name: str = "yt-dlp-gui") -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / app_name


def resolve_default_output_dir() -> Path:
    # Portable apps commonly run from locations users may not have write permission to.
    # Default to a user-owned directory.
    if sys.platform.startswith("win"):
        downloads = Path.home() / "Downloads"
        return downloads if downloads.is_dir() else Path.home()
    return Path.cwd()

