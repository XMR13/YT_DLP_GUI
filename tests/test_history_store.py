from __future__ import annotations

from controllers.history_store import HistoryEntry, HistoryStore


def test_history_store_append_and_clear(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    store = HistoryStore(app_name="yt-dlp-gui-test", max_entries=5)

    entry = HistoryEntry.create(
        status="completed",
        title="Example",
        url="https://example.com",
        output_dir=str(tmp_path / "out"),
        output_paths=[str(tmp_path / "out" / "file.mp4")],
    )
    store.append(entry)

    loaded = store.load()
    assert len(loaded) == 1
    assert loaded[0].title == "Example"

    store.clear()
    assert store.load() == []


def test_history_store_truncates(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    store = HistoryStore(app_name="yt-dlp-gui-test", max_entries=2)

    for idx in range(3):
        store.append(
            HistoryEntry.create(
                status="completed",
                title=f"Item {idx}",
                url=f"https://example.com/{idx}",
                output_dir=str(tmp_path / "out"),
            )
        )

    loaded = store.load()
    assert len(loaded) == 2
    assert loaded[0].title == "Item 2"
