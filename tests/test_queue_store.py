from __future__ import annotations

import json

from controllers.queue_store import QueueItem, QueueStore


def test_queue_store_dedupe_by_signature(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    store = QueueStore(app_name="yt-dlp-gui-test", max_entries=50)

    item1 = QueueItem.create(
        url="https://example.com/video",
        output_dir=str(tmp_path / "out"),
        format_id="best",
        audio_only=False,
        playlist_mode=False,
        playlist_items=None,
        cookies=None,
        js_runtime=None,
        js_runtime_path=None,
        remote_components=None,
    )
    store.append(item1, dedupe=True)

    item2 = QueueItem.create(
        url="https://example.com/video",
        output_dir=str(tmp_path / "out"),
        format_id="best",
        audio_only=False,
        playlist_mode=False,
        playlist_items=None,
        cookies=None,
        js_runtime=None,
        js_runtime_path=None,
        remote_components=None,
    )
    store.append(item2, dedupe=True)

    loaded = store.load()
    assert len(loaded) == 1

    # Different settings => different signature => allowed.
    item3 = QueueItem.create(
        url="https://example.com/video",
        output_dir=str(tmp_path / "out2"),
        format_id="best",
        audio_only=False,
        playlist_mode=False,
        playlist_items=None,
        cookies=None,
        js_runtime=None,
        js_runtime_path=None,
        remote_components=None,
    )
    store.append(item3, dedupe=True)

    loaded = store.load()
    assert len(loaded) == 2


def test_queue_store_schema_tolerant_load(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    store = QueueStore(app_name="yt-dlp-gui-test", max_entries=50)

    # Simulate an older/partial schema.
    path = tmp_path / "yt-dlp-gui-test" / "queue.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([{"url": "https://example.com", "output_dir": "X"}]), encoding="utf-8")

    loaded = store.load()
    assert len(loaded) == 1
    assert loaded[0].url == "https://example.com"


def test_queue_store_truncates(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    store = QueueStore(app_name="yt-dlp-gui-test", max_entries=2)

    for idx in range(3):
        store.append(
            QueueItem.create(
                url=f"https://example.com/{idx}",
                output_dir=str(tmp_path / "out"),
                format_id=None,
                audio_only=True,
                playlist_mode=False,
                playlist_items=None,
                cookies=None,
                js_runtime=None,
                js_runtime_path=None,
                remote_components=None,
            ),
            dedupe=False,
        )

    loaded = store.load()
    assert len(loaded) == 2
    assert loaded[0].url == "https://example.com/0"
