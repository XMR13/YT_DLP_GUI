from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import uuid4


@dataclass(frozen=True)
class HistoryEntry:
    id: str
    timestamp: str
    status: str
    title: str
    url: str
    output_dir: str
    output_paths: List[str]
    error: Optional[str] = None

    @staticmethod
    def create(
        *,
        status: str,
        title: str,
        url: str,
        output_dir: str,
        output_paths: Optional[List[str]] = None,
        error: Optional[str] = None,
    ) -> "HistoryEntry":
        return HistoryEntry(
            id=str(uuid4()),
            timestamp=datetime.now().isoformat(timespec="seconds"),
            status=status,
            title=title,
            url=url,
            output_dir=output_dir,
            output_paths=output_paths or [],
            error=error,
        )

    @staticmethod
    def from_dict(raw: dict) -> "HistoryEntry":
        return HistoryEntry(
            id=str(raw.get("id") or uuid4()),
            timestamp=str(raw.get("timestamp") or ""),
            status=str(raw.get("status") or "unknown"),
            title=str(raw.get("title") or ""),
            url=str(raw.get("url") or ""),
            output_dir=str(raw.get("output_dir") or ""),
            output_paths=[str(path) for path in raw.get("output_paths") or []],
            error=str(raw.get("error")) if raw.get("error") else None,
        )

    def to_dict(self) -> dict:
        return asdict(self)


class HistoryStore:
    def __init__(self, app_name: str = "yt-dlp-gui", max_entries: int = 200) -> None:
        self._path = self._resolve_history_path(app_name)
        self._max_entries = max_entries

    def load(self) -> List[HistoryEntry]:
        if not self._path.exists():
            return []
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                return []
            return [HistoryEntry.from_dict(item) for item in raw if isinstance(item, dict)]
        except (OSError, json.JSONDecodeError):
            return []

    def save(self, entries: List[HistoryEntry]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = [entry.to_dict() for entry in entries[: self._max_entries]]
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def append(self, entry: HistoryEntry) -> List[HistoryEntry]:
        entries = self.load()
        entries.insert(0, entry)
        self.save(entries)
        return entries

    def clear(self) -> None:
        self.save([])

    @staticmethod
    def _resolve_history_path(app_name: str) -> Path:
        if sys.platform.startswith("win"):
            base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
        return base / app_name / "history.json"
