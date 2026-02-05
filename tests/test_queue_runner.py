from __future__ import annotations

from dataclasses import replace
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


def test_queue_runner_rejects_invalid_queued_url(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    store = QueueStore(app_name="yt-dlp-gui-test")
    runner = QueueRunner(store, FakeExecutor(["ok"]))

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
    tampered = replace(item, url="--exec echo pwned")
    runner.enqueue(tampered, dedupe=False)

    assert runner.run_next_blocking() is True
    loaded = store.load()
    assert loaded[0].status == "failed"
    assert loaded[0].error == "Queue item URL is invalid."


def test_queue_runner_move_queued_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    store = QueueStore(app_name="yt-dlp-gui-test")
    runner = QueueRunner(store, FakeExecutor([]))

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
    item3 = QueueItem.create(
        url="https://example.com/3",
        output_dir=str(tmp_path / "out"),
        format_id=None,
        audio_only=True,
        playlist_mode=False,
        playlist_items=None,
        cookies=None,
        js_runtime=None,
        js_runtime_path=None,
        remote_components=None,
        title="Three",
    )

    store.save([item1, replace(item2, status="completed"), item3])
    runner.move(item3.id, -1)

    loaded = store.load()
    assert [item.id for item in loaded] == [item3.id, item2.id, item1.id]


def test_queue_runner_move_top_bottom(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    store = QueueStore(app_name="yt-dlp-gui-test")
    runner = QueueRunner(store, FakeExecutor([]))

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
    item3 = QueueItem.create(
        url="https://example.com/3",
        output_dir=str(tmp_path / "out"),
        format_id=None,
        audio_only=True,
        playlist_mode=False,
        playlist_items=None,
        cookies=None,
        js_runtime=None,
        js_runtime_path=None,
        remote_components=None,
        title="Three",
    )
    item4 = QueueItem.create(
        url="https://example.com/4",
        output_dir=str(tmp_path / "out"),
        format_id=None,
        audio_only=True,
        playlist_mode=False,
        playlist_items=None,
        cookies=None,
        js_runtime=None,
        js_runtime_path=None,
        remote_components=None,
        title="Four",
    )
    item5 = QueueItem.create(
        url="https://example.com/5",
        output_dir=str(tmp_path / "out"),
        format_id=None,
        audio_only=True,
        playlist_mode=False,
        playlist_items=None,
        cookies=None,
        js_runtime=None,
        js_runtime_path=None,
        remote_components=None,
        title="Five",
    )

    store.save(
        [
            item1,
            replace(item2, status="completed"),
            item3,
            item4,
            replace(item5, status="cancelled"),
        ]
    )
    runner.move_to_top(item4.id)
    loaded = store.load()
    assert [item.id for item in loaded] == [item4.id, item2.id, item1.id, item3.id, item5.id]

    store.save(
        [
            item1,
            replace(item2, status="completed"),
            item3,
            item4,
            replace(item5, status="cancelled"),
        ]
    )
    runner.move_to_bottom(item1.id)
    loaded = store.load()
    assert [item.id for item in loaded] == [item3.id, item2.id, item4.id, item1.id, item5.id]


def test_queue_runner_move_to_queued_index(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    store = QueueStore(app_name="yt-dlp-gui-test")
    runner = QueueRunner(store, FakeExecutor([]))

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
    item3 = QueueItem.create(
        url="https://example.com/3",
        output_dir=str(tmp_path / "out"),
        format_id=None,
        audio_only=True,
        playlist_mode=False,
        playlist_items=None,
        cookies=None,
        js_runtime=None,
        js_runtime_path=None,
        remote_components=None,
        title="Three",
    )
    item4 = QueueItem.create(
        url="https://example.com/4",
        output_dir=str(tmp_path / "out"),
        format_id=None,
        audio_only=True,
        playlist_mode=False,
        playlist_items=None,
        cookies=None,
        js_runtime=None,
        js_runtime_path=None,
        remote_components=None,
        title="Four",
    )
    item5 = QueueItem.create(
        url="https://example.com/5",
        output_dir=str(tmp_path / "out"),
        format_id=None,
        audio_only=True,
        playlist_mode=False,
        playlist_items=None,
        cookies=None,
        js_runtime=None,
        js_runtime_path=None,
        remote_components=None,
        title="Five",
    )

    store.save(
        [
            item1,
            replace(item2, status="completed"),
            item3,
            item4,
            replace(item5, status="cancelled"),
        ]
    )
    runner.move_to_queued_index(item1.id, 2)
    loaded = store.load()
    assert [item.id for item in loaded] == [item3.id, item2.id, item4.id, item1.id, item5.id]

    store.save(
        [
            item1,
            replace(item2, status="completed"),
            item3,
            item4,
            replace(item5, status="cancelled"),
        ]
    )
    runner.move_to_queued_index(item4.id, 1)
    loaded = store.load()
    assert [item.id for item in loaded] == [item1.id, item2.id, item4.id, item3.id, item5.id]


def test_queue_runner_clear_failed_and_cancelled(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    store = QueueStore(app_name="yt-dlp-gui-test")
    runner = QueueRunner(store, FakeExecutor([]))

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
    )
    item3 = QueueItem.create(
        url="https://example.com/3",
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

    store.save(
        [
            replace(item1, status="failed"),
            replace(item2, status="cancelled"),
            replace(item3, status="queued"),
        ]
    )
    runner.clear_failed()

    loaded = store.load()
    assert [item.status for item in loaded] == ["queued"]
