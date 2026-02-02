from __future__ import annotations

import threading
from dataclasses import replace
from queue import Queue
from typing import Callable, List, Optional, Protocol, Tuple

from controllers.queue_store import QueueItem, QueueStore, _now_iso
from yt_dlp_adapter import DownloadCancelled


EventQueue = Queue[Tuple[str, object]]


class DownloadExecutor(Protocol):
    def download(self, item: QueueItem) -> List[str]: ...

    def cancel(self, output_dir: Optional[str], delete_partials: bool = True) -> None: ...


class QueueRunner:
    """A lightweight sequential runner (1 active download at a time).

    This is UI-agnostic. The UI can subscribe by passing an EventQueue and
    consuming `queue_updated` events, plus `log/progress/busy` if desired.
    """

    def __init__(
        self,
        store: QueueStore,
        executor: DownloadExecutor,
        event_queue: Optional[EventQueue] = None,
    ) -> None:
        self._store = store
        self._executor = executor
        self._events = event_queue

        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._wake = threading.Event()
        self._run_requested = False
        self._shutdown = False
        self._active_id: Optional[str] = None
        self._active_output_dir: Optional[str] = None

    def load(self) -> List[QueueItem]:
        # If the app crashed with a running item, reset it to queued.
        original = self._store.load()
        items: List[QueueItem] = []
        for item in original:
            if item.status == "running":
                items.append(replace(item, status="queued", updated_at=_now_iso()))
            else:
                items.append(item)
        if items != original:
            self._store.save(items)
        self._emit_queue_updated(items)
        return items

    def enqueue(self, item: QueueItem, *, dedupe: bool = True) -> List[QueueItem]:
        items = self._store.append(item, dedupe=dedupe)
        self._emit_queue_updated(items)
        self._wake.set()
        return items

    def remove(self, item_id: str) -> List[QueueItem]:
        items = self._store.remove(item_id)
        self._emit_queue_updated(items)
        return items

    def clear(self) -> List[QueueItem]:
        self._store.clear()
        items: List[QueueItem] = []
        self._emit_queue_updated(items)
        return items

    def clear_completed(self) -> List[QueueItem]:
        items = [item for item in self._store.load() if item.status != "completed"]
        self._store.save(items)
        self._emit_queue_updated(items)
        return items

    def clear_failed(self) -> List[QueueItem]:
        items = [item for item in self._store.load() if item.status not in ("failed", "cancelled")]
        self._store.save(items)
        self._emit_queue_updated(items)
        return items

    def move(self, item_id: str, direction: int) -> List[QueueItem]:
        if direction == 0:
            return self._store.load()
        items = self._store.load()
        current_index = None
        for idx, item in enumerate(items):
            if item.id == item_id:
                current_index = idx
                break
        if current_index is None:
            return items
        if items[current_index].status != "queued":
            return items

        queued_positions = [idx for idx, item in enumerate(items) if item.status == "queued"]
        try:
            queued_index = queued_positions.index(current_index)
        except ValueError:
            return items

        step = -1 if direction < 0 else 1
        target_index = queued_index + step
        if target_index < 0 or target_index >= len(queued_positions):
            return items

        swap_pos = queued_positions[target_index]
        items[current_index], items[swap_pos] = items[swap_pos], items[current_index]
        self._store.save(items)
        self._emit_queue_updated(items)
        return items

    def start(self) -> None:
        with self._lock:
            self._run_requested = True
            if self._thread and self._thread.is_alive():
                self._wake.set()
                return
            self._shutdown = False
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            self._wake.set()

    def stop_after_current(self) -> None:
        with self._lock:
            self._run_requested = False
        self._wake.set()

    def is_running_requested(self) -> bool:
        with self._lock:
            return self._run_requested

    def cancel_current(self) -> None:
        with self._lock:
            output_dir = self._active_output_dir
        self._executor.cancel(output_dir, delete_partials=True)

    def shutdown(self) -> None:
        with self._lock:
            self._run_requested = False
            self._shutdown = True
        self._wake.set()

    def retry(self, item_id: str) -> List[QueueItem]:
        items = self._store.load()
        updated: List[QueueItem] = []
        for item in items:
            if item.id != item_id:
                updated.append(item)
                continue
            refreshed = replace(
                item,
                status="queued",
                error=None,
                output_paths=[],
                updated_at=_now_iso(),
            )
            updated.append(refreshed)
        self._store.save(updated)
        self._emit_queue_updated(updated)
        self._wake.set()
        return updated

    def run_next_blocking(self) -> bool:
        """Run a single queued item synchronously (useful for unit tests)."""
        item = self._next_queued_item()
        if not item:
            return False
        self._run_one(item)
        return True

    def _run_loop(self) -> None:
        while True:
            with self._lock:
                if self._shutdown:
                    return
                run = self._run_requested
            if not run:
                self._wake.wait(timeout=0.25)
                self._wake.clear()
                continue

            item = self._next_queued_item()
            if not item:
                self._wake.wait(timeout=0.25)
                self._wake.clear()
                continue

            self._run_one(item)

    def _next_queued_item(self) -> Optional[QueueItem]:
        items = self._store.load()
        for item in items:
            if item.status == "queued":
                return item
        return None

    def _run_one(self, item: QueueItem) -> None:
        running = replace(item, status="running", updated_at=_now_iso())
        with self._lock:
            self._active_id = running.id
            self._active_output_dir = running.output_dir
        self._store.replace(running)
        self._emit_busy(True, "download")
        self._emit_queue_updated(self._store.load())
        self._emit_log(f"Queue: starting {running.title or running.url}")

        try:
            output_paths = self._executor.download(running)
            completed = replace(
                running,
                status="completed",
                output_paths=list(output_paths or []),
                updated_at=_now_iso(),
            )
            self._store.replace(completed)
            self._emit_log("Queue: completed.")
            self._emit("download_complete", {"item": completed.to_dict(), "output_paths": completed.output_paths})
        except DownloadCancelled:
            cancelled = replace(running, status="cancelled", updated_at=_now_iso())
            self._store.replace(cancelled)
            self._emit_log("Queue: cancelled current item.")
            self._emit("download_cancelled", {"item": cancelled.to_dict()})
        except Exception as exc:  # noqa: BLE001 - surface to UI/log
            failed = replace(running, status="failed", error=str(exc), updated_at=_now_iso())
            self._store.replace(failed)
            self._emit_log(f"Queue: failed: {exc}")
            self._emit_error(str(exc))
            self._emit("download_error", {"item": failed.to_dict(), "error": str(exc)})
        finally:
            with self._lock:
                self._active_id = None
                self._active_output_dir = None
            self._emit_busy(False, None)
            self._emit_queue_updated(self._store.load())
            # If stop was requested while running, we won't pick up the next item.
            self._wake.set()

    def _emit(self, event: str, payload: object) -> None:
        if self._events is None:
            return
        self._events.put((event, payload))

    def _emit_log(self, message: str) -> None:
        self._emit("log", message)

    def _emit_error(self, message: str) -> None:
        self._emit("error", message)

    def _emit_busy(self, busy: bool, task: Optional[str]) -> None:
        self._emit("busy", (busy, task))

    def _emit_queue_updated(self, items: List[QueueItem]) -> None:
        # Keep this a simple structure to decouple UI from dataclass internals.
        self._emit("queue_updated", [item.to_dict() for item in items])


class YtDlpExecutor:
    """Adapter wrapper to satisfy DownloadExecutor protocol."""

    def __init__(self, adapter: object) -> None:
        self._adapter = adapter

    def download(self, item: QueueItem) -> List[str]:
        return self._adapter.download(  # type: ignore[no-any-return]
            url=item.url,
            output_dir=item.output_dir,
            format_id=item.format_id,
            audio_only=item.audio_only,
            playlist_mode=item.playlist_mode,
            playlist_items=item.playlist_items,
            cookies_from_browser=item.cookies,
            js_runtime=item.js_runtime,
            js_runtime_path=item.js_runtime_path,
            remote_components=item.remote_components,
        )

    def cancel(self, output_dir: Optional[str], delete_partials: bool = True) -> None:
        self._adapter.cancel(output_dir, delete_partials=delete_partials)
