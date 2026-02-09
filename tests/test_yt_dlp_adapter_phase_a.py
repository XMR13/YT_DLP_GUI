from __future__ import annotations

import subprocess
from typing import Any, List

from yt_dlp_adapter import YtDlpAdapter


def test_fetch_info_retries_with_android_client_on_skipped_format_warning(monkeypatch) -> None:
    calls: List[List[str]] = []
    responses = [
        subprocess.CompletedProcess(
            args=["yt-dlp"],
            returncode=0,
            stdout='{"id":"first","formats":[]}',
            stderr="WARNING: Some web client https formats have been skipped\n",
        ),
        subprocess.CompletedProcess(
            args=["yt-dlp"],
            returncode=0,
            stdout='{"id":"second","formats":[]}',
            stderr="",
        ),
    ]

    def fake_run(args: List[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        assert kwargs["check"] is True
        return responses.pop(0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = YtDlpAdapter()

    info = adapter.fetch_info("https://example.com/watch?v=1", playlist_mode=False)

    assert info["id"] == "second"
    assert len(calls) == 2
    retry_args = calls[1]
    assert "--extractor-args" in retry_args
    assert "youtube:player_client=android" in retry_args
    assert retry_args.index("--extractor-args") < retry_args.index("--")


def test_download_best_available_uses_bestvideo_plus_bestaudio(monkeypatch, tmp_path) -> None:
    captured: dict[str, List[str]] = {}

    class FakePopen:
        def __init__(self, args: List[str], **kwargs: Any) -> None:
            captured["args"] = list(args)
            self.stdout: List[str] = []
            self.returncode = 0

        def wait(self, timeout: float | None = None) -> int:
            return self.returncode

        def poll(self) -> int:
            return self.returncode

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    adapter = YtDlpAdapter()

    output_paths = adapter.download(
        url="https://example.com/watch?v=1",
        output_dir=str(tmp_path),
        format_id=None,
        audio_only=False,
        playlist_mode=False,
    )

    assert output_paths == []
    args = captured["args"]
    selector_index = args.index("-f") + 1
    assert args[selector_index] == "bestvideo+bestaudio/best"


def test_with_extractor_args_inserts_before_url_marker() -> None:
    args = ["yt-dlp", "-J", "--", "https://example.com/watch?v=1"]
    updated = YtDlpAdapter._with_extractor_args(args, "youtube:player_client=android")  # type: ignore[attr-defined]
    assert updated == [
        "yt-dlp",
        "-J",
        "--extractor-args",
        "youtube:player_client=android",
        "--",
        "https://example.com/watch?v=1",
    ]
