from __future__ import annotations

from typing import List, Optional

from controllers.queue_runner import QueueRunner
from controllers.queue_store import QueueItem, QueueStore
from yt_dlp_adapter import DownloadCancelled


class FakeExecutor:
    def __init__(self, outcomes: List[str]) -> None:
        self._outcomes = list(outcomes)
        self.cancel_calls: List[Optional[str]] = []

    def download(self, item: QueueItem) -> List[str]:
        outcome = self._outcomes.pop(0) if self._outcomes else "ok"
        if outcome == "ok":
            return [f"{item.output_dir}/file.mp4"]
        if outcome == "cancel":
            raise DownloadCancelled()
        raise RuntimeError("boom")

    def cancel(self, output_dir: Optional[str], delete_partials: bool = True) -> None:
        self.cancel_calls.append(output_dir)


def test_queue_runner_sequential_success(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    store = QueueStore(app_name="yt-dlp-gui-test")
    exec_ = FakeExecutor(["ok", "ok"])
    runner = QueueRunner(store, exec_)

    item1 = QueueItem.create(
        url="https://example.com/1",
        output_dir=str(tmp_path / "out"),
        format_id=None,
        audio_only=True,
        playlist_mode=False,
        playlist_items=None,
        cookies=None,
        js_runtime=None,
        js_runtime_path=None,
        remote_components=None,
        title="One",
    )
    item2 = QueueItem.create(
        url="https://example.com/2",
        output_dir=str(tmp_path / "out"),
        format_id=None,
        audio_only=True,
        playlist_mode=False,
        playlist_items=None,
        cookies=None,
        js_runtime=None,
        js_runtime_path=None,
        remote_components=None,
        title="Two",
    )

    runner.enqueue(item1, dedupe=False)
    runner.enqueue(item2, dedupe=False)

    assert runner.run_next_blocking() is True
    assert runner.run_next_blocking() is True
    assert runner.run_next_blocking() is False

    loaded = store.load()
    assert [item.status for item in loaded] == ["completed", "completed"]
    assert loaded[0].output_paths


def test_queue_runner_cancel_marks_cancelled(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    store = QueueStore(app_name="yt-dlp-gui-test")
    exec_ = FakeExecutor(["cancel"])
    runner = QueueRunner(store, exec_)

    item = QueueItem.create(
        url="https://example.com/1",
        output_dir=str(tmp_path / "out"),
        format_id=None,
        audio_only=True,
        playlist_mode=False,
        playlist_items=None,
        cookies=None,
        js_runtime=None,
        js_runtime_path=None,
        remote_components=None,
    )
    runner.enqueue(item, dedupe=False)

    assert runner.run_next_blocking() is True
    loaded = store.load()
    assert loaded[0].status == "cancelled"


def test_queue_runner_failure_marks_failed_and_retry(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    store = QueueStore(app_name="yt-dlp-gui-test")
    exec_ = FakeExecutor(["fail", "ok"])
    runner = QueueRunner(store, exec_)

    item = QueueItem.create(
        url="https://example.com/1",
        output_dir=str(tmp_path / "out"),
        format_id=None,
        audio_only=True,
        playlist_mode=False,
        playlist_items=None,
        cookies=None,
        js_runtime=None,
        js_runtime_path=None,
        remote_components=None,
    )
    runner.enqueue(item, dedupe=False)

    assert runner.run_next_blocking() is True
    loaded = store.load()
    assert loaded[0].status == "failed"
    assert loaded[0].error

    runner.retry(loaded[0].id)
    assert runner.run_next_blocking() is True
    loaded = store.load()
    assert loaded[0].status == "completed"
