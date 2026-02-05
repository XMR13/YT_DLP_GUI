from __future__ import annotations

import threading
from queue import Queue
from typing import Dict, List, Optional, Tuple

from yt_dlp_adapter import DownloadCancelled, FormatOption, PlaylistItem, YtDlpAdapter


EventQueue = Queue[Tuple[str, object]]


class DownloadController:
    def __init__(self, event_queue: EventQueue, adapter: YtDlpAdapter) -> None:
        self._events = event_queue
        self._adapter = adapter
        self._active_output_dir: Optional[str] = None
        self._cancel_requested = False
        self._formats_request_id = 0
        self._formats_lock = threading.Lock()
        self._info_request_id = 0
        self._info_lock = threading.Lock()

    def fetch_formats(
        self,
        url: str,
        playlist_mode: bool,
        playlist_items: Optional[str] = None,
        cookies: Optional[str] = None,
        js_runtime: Optional[str] = None,
        js_runtime_path: Optional[str] = None,
        remote_components: Optional[str] = None,
        emit_busy: bool = True,
    ) -> int:
        with self._formats_lock:
            self._formats_request_id += 1
            request_id = self._formats_request_id
        if emit_busy:
            self._events.put(("busy", (True, "fetch")))
        threading.Thread(
            target=self._fetch_formats_worker,
            args=(
                request_id,
                url,
                playlist_mode,
                playlist_items,
                cookies,
                js_runtime,
                js_runtime_path,
                remote_components,
                emit_busy,
            ),
            daemon=True,
        ).start()
        return request_id

    def fetch_preview(
        self,
        url: str,
        cookies: Optional[str],
        js_runtime: Optional[str],
        js_runtime_path: Optional[str],
        remote_components: Optional[str],
        start: int = 1,
        limit: int = 20,
        append: bool = False,
    ) -> None:
        threading.Thread(
            target=self._fetch_preview_worker,
            args=(url, cookies, js_runtime, js_runtime_path, remote_components, start, limit, append),
            daemon=True,
        ).start()

    def fetch_item_info(
        self,
        url: str,
        playlist_mode: bool,
        playlist_items: Optional[str],
        cookies: Optional[str],
        js_runtime: Optional[str],
        js_runtime_path: Optional[str],
        remote_components: Optional[str],
        index: int,
    ) -> int:
        with self._info_lock:
            self._info_request_id += 1
            request_id = self._info_request_id
        threading.Thread(
            target=self._fetch_item_info_worker,
            args=(
                request_id,
                index,
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
        return request_id

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
        request_id: int,
        url: str,
        playlist_mode: bool,
        playlist_items: Optional[str],
        cookies: Optional[str],
        js_runtime: Optional[str],
        js_runtime_path: Optional[str],
        remote_components: Optional[str],
        emit_busy: bool,
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
            self._events.put(("formats", (request_id, options)))
            self._events.put(("info", (request_id, info)))
            title = info.get("title") or "Selection loaded."
            self._events.put(("log", f"Formats loaded for: {title}"))
        except Exception as exc:  # noqa: BLE001 - UI surface for any failures.
            self._events.put(("formats_error", request_id))
            self._events.put(("error", str(exc)))
        finally:
            if emit_busy:
                self._events.put(("busy", (False, None)))

    def _fetch_item_info_worker(
        self,
        request_id: int,
        index: int,
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
            self._events.put(("item_info", (request_id, index, info)))
            title = info.get("title") or f"Item {index}"
            self._events.put(("log", f"Item details loaded: {title}"))
        except Exception as exc:  # noqa: BLE001 - UI surface for any failures.
            self._events.put(("error", str(exc)))

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
            output_paths = self._adapter.download(
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
            self._events.put(("download_complete", output_paths))
            self._events.put(("log", "Download completed."))
        except DownloadCancelled:
            self._events.put(("download_cancelled", None))
            self._events.put(("log", "Download cancelled."))
        except Exception as exc:  # noqa: BLE001
            self._events.put(("download_error", str(exc)))
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
        start: int,
        limit: int,
        append: bool,
    ) -> None:
        try:
            items, total_count = self._adapter.fetch_playlist_preview(
                url,
                start=start,
                limit=limit,
                cookies_from_browser=cookies,
                js_runtime=js_runtime,
                js_runtime_path=js_runtime_path,
                remote_components=remote_components,
            )
            self._events.put(("preview", (items, total_count, append)))
            self._events.put(("log", f"Playlist preview loaded ({len(items)} items)."))
        except Exception as exc:  # noqa: BLE001
            self._events.put(("error", str(exc)))
