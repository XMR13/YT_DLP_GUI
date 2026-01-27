from __future__ import annotations

import threading
from queue import Queue
from typing import Dict, List, Optional, Tuple

from yt_dlp_adapter import FormatOption, PlaylistItem, YtDlpAdapter


EventQueue = Queue[Tuple[str, object]]


class DownloadController:
    def __init__(self, event_queue: EventQueue, adapter: YtDlpAdapter) -> None:
        self._events = event_queue
        self._adapter = adapter
        self._active_output_dir: Optional[str] = None
        self._cancel_requested = False

    def fetch_formats(
        self,
        url: str,
        playlist_mode: bool,
        playlist_items: Optional[str] = None,
        cookies: Optional[str] = None,
        js_runtime: Optional[str] = None,
        js_runtime_path: Optional[str] = None,
        remote_components: Optional[str] = None,
    ) -> None:
        self._events.put(("busy", (True, "fetch")))
        threading.Thread(
            target=self._fetch_formats_worker,
            args=(
                url,
                playlist_mode,
                playlist_items,
                cookies,
                js_runtime,
                js_runtime_path,
                remote_components,
            ),
            daemon=True,
        ).start()

    def fetch_preview(
        self,
        url: str,
        cookies: Optional[str],
        js_runtime: Optional[str],
        js_runtime_path: Optional[str],
        remote_components: Optional[str],
        limit: int = 20,
    ) -> None:
        threading.Thread(
            target=self._fetch_preview_worker,
            args=(url, cookies, js_runtime, js_runtime_path, remote_components, limit),
            daemon=True,
        ).start()

    def start_download(
        self,
        url: str,
        output_dir: str,
        format_id: Optional[str],
        audio_only: bool,
        playlist_mode: bool,
        playlist_items: Optional[str] = None,
        cookies: Optional[str] = None,
        js_runtime: Optional[str] = None,
        js_runtime_path: Optional[str] = None,
        remote_components: Optional[str] = None,
    ) -> None:
        self._cancel_requested = False
        self._active_output_dir = output_dir
        self._events.put(("busy", (True, "download")))
        self._events.put(("progress", 0.0))
        threading.Thread(
            target=self._download_worker,
            args=(
                url,
                output_dir,
                format_id,
                audio_only,
                playlist_mode,
                playlist_items,
                cookies,
                js_runtime,
                js_runtime_path,
                remote_components,
            ),
            daemon=True,
        ).start()

    def cancel_download(self) -> None:
        self._cancel_requested = True
        self._adapter.cancel(self._active_output_dir, delete_partials=True)

    def _fetch_formats_worker(
        self,
        url: str,
        playlist_mode: bool,
        playlist_items: Optional[str],
        cookies: Optional[str],
        js_runtime: Optional[str],
        js_runtime_path: Optional[str],
        remote_components: Optional[str],
    ) -> None:
        try:
            info = self._adapter.fetch_info(
                url,
                playlist_mode,
                playlist_items,
                cookies,
                js_runtime,
                js_runtime_path,
                remote_components,
            )
            options = self._adapter.extract_video_formats(info)
            self._events.put(("formats", options))
            self._events.put(("info", info))
            title = info.get("title") or "Selection loaded."
            self._events.put(("log", f"Formats loaded for: {title}"))
        except Exception as exc:  # noqa: BLE001 - UI surface for any failures.
            self._events.put(("error", str(exc)))
        finally:
            self._events.put(("busy", (False, None)))

    def _download_worker(
        self,
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
    ) -> None:
        try:
            self._adapter.download(
                url=url,
                output_dir=output_dir,
                format_id=format_id,
                audio_only=audio_only,
                playlist_mode=playlist_mode,
                playlist_items=playlist_items,
                cookies_from_browser=cookies,
                js_runtime=js_runtime,
                js_runtime_path=js_runtime_path,
                remote_components=remote_components,
            )
            self._events.put(("log", "Download completed."))
        except Exception as exc:  # noqa: BLE001
            if self._cancel_requested:
                self._events.put(("log", "Download cancelled."))
            else:
                self._events.put(("error", str(exc)))
        finally:
            self._events.put(("busy", (False, None)))

    def _fetch_preview_worker(
        self,
        url: str,
        cookies: Optional[str],
        js_runtime: Optional[str],
        js_runtime_path: Optional[str],
        remote_components: Optional[str],
        limit: int,
    ) -> None:
        try:
            items: List[PlaylistItem] = self._adapter.fetch_playlist_preview(
                url,
                limit=limit,
                cookies_from_browser=cookies,
                js_runtime=js_runtime,
                js_runtime_path=js_runtime_path,
                remote_components=remote_components,
            )
            self._events.put(("preview", items))
            self._events.put(("log", f"Playlist preview loaded ({len(items)} items)."))
        except Exception as exc:  # noqa: BLE001
            self._events.put(("error", str(exc)))
