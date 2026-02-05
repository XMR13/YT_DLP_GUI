from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

ALLOWED_COOKIE_BROWSERS = {"chrome", "edge", "firefox"}
ALLOWED_JS_RUNTIMES = {"node", "deno", "bun", "quickjs"}
ALLOWED_REMOTE_COMPONENTS = {"ejs:github", "ejs:npm"}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _none_if_blank(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _normalize_choice(value: Optional[str], allowed: set[str]) -> Optional[str]:
    normalized = _none_if_blank(value)
    if normalized is None:
        return None
    lowered = normalized.lower()
    if lowered not in allowed:
        return None
    return lowered


def _normalize_playlist_items(value: Optional[str]) -> Optional[str]:
    """Normalize simple comma-separated playlist item indices ("3,1,2" -> "1,2,3").

    If the string includes non-comma syntax (e.g. "1:20" or "1-3"), we keep it as-is.
    """
    value = _none_if_blank(value)
    if not value:
        return None
    if any(ch in value for ch in (":", "-")):
        return value
    parts: List[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            parts.append(int(part))
        except ValueError:
            return value
    if not parts:
        return None
    return ",".join(str(idx) for idx in sorted(set(parts)))


def _compute_signature(payload: dict) -> str:
    # Deterministic "request signature" used for dedupe (same URL + same settings).
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class QueueItem:
    id: str
    created_at: str
    status: str  # queued|running|completed|failed|cancelled
    url: str
    output_dir: str
    format_id: Optional[str]
    audio_only: bool
    playlist_mode: bool
    playlist_items: Optional[str]
    cookies: Optional[str]
    js_runtime: Optional[str]
    js_runtime_path: Optional[str]
    remote_components: Optional[str]
    title: Optional[str] = None
    output_paths: List[str] = field(default_factory=list)
    error: Optional[str] = None
    signature: Optional[str] = None
    updated_at: Optional[str] = None

    @staticmethod
    def create(
        *,
        url: str,
        output_dir: str,
        format_id: Optional[str],
        audio_only: bool,
        playlist_mode: bool,
        playlist_items: Optional[str],
        cookies: Optional[str],
        js_runtime: Optional[str],
        js_runtime_path: Optional[str],
        remote_components: Optional[str],
        title: Optional[str] = None,
    ) -> "QueueItem":
        playlist_items_norm = _normalize_playlist_items(playlist_items)
        item = QueueItem(
            id=str(uuid4()),
            created_at=_now_iso(),
            status="queued",
            url=url.strip(),
            output_dir=output_dir.strip(),
            format_id=_none_if_blank(format_id),
            audio_only=bool(audio_only),
            playlist_mode=bool(playlist_mode),
            playlist_items=playlist_items_norm,
            cookies=_normalize_choice(cookies, ALLOWED_COOKIE_BROWSERS),
            js_runtime=_normalize_choice(js_runtime, ALLOWED_JS_RUNTIMES),
            js_runtime_path=_none_if_blank(js_runtime_path),
            remote_components=_normalize_choice(remote_components, ALLOWED_REMOTE_COMPONENTS),
            title=_none_if_blank(title),
            signature=None,
            updated_at=None,
        )
        if item.js_runtime is None:
            item = QueueItem(**{**asdict(item), "js_runtime_path": None, "remote_components": None})
        return item.with_signature()

    def with_signature(self) -> "QueueItem":
        payload = {
            "url": self.url,
            "output_dir": self.output_dir,
            "format_id": self.format_id,
            "audio_only": self.audio_only,
            "playlist_mode": self.playlist_mode,
            "playlist_items": self.playlist_items,
            "cookies": self.cookies,
            "js_runtime": self.js_runtime,
            "js_runtime_path": self.js_runtime_path,
            "remote_components": self.remote_components,
        }
        return QueueItem(**{**asdict(self), "signature": _compute_signature(payload)})

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(raw: dict) -> "QueueItem":
        output_paths = raw.get("output_paths") or []
        playlist_items = _normalize_playlist_items(raw.get("playlist_items"))
        item = QueueItem(
            id=str(raw.get("id") or uuid4()),
            created_at=str(raw.get("created_at") or ""),
            status=str(raw.get("status") or "queued"),
            url=str(raw.get("url") or ""),
            output_dir=str(raw.get("output_dir") or ""),
            format_id=_none_if_blank(raw.get("format_id")),
            audio_only=bool(raw.get("audio_only") or False),
            playlist_mode=bool(raw.get("playlist_mode") or False),
            playlist_items=playlist_items,
            cookies=_normalize_choice(raw.get("cookies"), ALLOWED_COOKIE_BROWSERS),
            js_runtime=_normalize_choice(raw.get("js_runtime"), ALLOWED_JS_RUNTIMES),
            js_runtime_path=_none_if_blank(raw.get("js_runtime_path")),
            remote_components=_normalize_choice(raw.get("remote_components"), ALLOWED_REMOTE_COMPONENTS),
            title=_none_if_blank(raw.get("title")),
            output_paths=[str(path) for path in output_paths if path],
            error=_none_if_blank(raw.get("error")),
            signature=_none_if_blank(raw.get("signature")),
            updated_at=_none_if_blank(raw.get("updated_at")),
        )
        if item.js_runtime is None:
            item = QueueItem(**{**asdict(item), "js_runtime_path": None, "remote_components": None})
        return item.with_signature() if not item.signature else item


class QueueStore:
    def __init__(self, app_name: str = "yt-dlp-gui", max_entries: int = 500) -> None:
        self._path = self._resolve_queue_path(app_name)
        self._max_entries = max_entries

    def load(self) -> List[QueueItem]:
        if not self._path.exists():
            return []
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                return []
            items = [QueueItem.from_dict(item) for item in raw if isinstance(item, dict)]
            return items[: self._max_entries]
        except (OSError, json.JSONDecodeError):
            return []

    def save(self, items: List[QueueItem]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = [item.to_dict() for item in items[: self._max_entries]]
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        if os.name == "posix":
            try:
                os.chmod(self._path.parent, 0o700)
            except OSError:
                pass
            try:
                os.chmod(self._path, 0o600)
            except OSError:
                pass

    def append(self, item: QueueItem, *, dedupe: bool = True) -> List[QueueItem]:
        items = self.load()
        item_to_add = item if item.signature else item.with_signature()
        item_sig = item_to_add.signature
        if dedupe and item_sig:
            for existing in items:
                if (existing.signature or existing.with_signature().signature) == item_sig:
                    return items
        items.append(item_to_add)
        self.save(items)
        return items

    def replace(self, item: QueueItem) -> List[QueueItem]:
        item_to_store = item if item.signature else item.with_signature()
        items = self.load()
        replaced = False
        updated: List[QueueItem] = []
        for existing in items:
            if existing.id == item_to_store.id:
                updated.append(item_to_store)
                replaced = True
            else:
                updated.append(existing)
        if not replaced:
            updated.append(item_to_store)
        self.save(updated)
        return updated

    def remove(self, item_id: str) -> List[QueueItem]:
        items = [item for item in self.load() if item.id != item_id]
        self.save(items)
        return items

    def clear(self) -> None:
        self.save([])

    @staticmethod
    def _resolve_queue_path(app_name: str) -> Path:
        if sys.platform.startswith("win"):
            base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
        return base / app_name / "queue.json"
