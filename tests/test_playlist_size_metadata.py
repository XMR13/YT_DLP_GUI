from __future__ import annotations

from yt_dlp_adapter import FormatOption, YtDlpAdapter


def test_resolve_download_size_adds_best_audio_for_video_only() -> None:
    info = {
        "duration": 120,
        "formats": [
            {"format_id": "137", "vcodec": "avc1", "acodec": "none", "filesize": 10_000_000},
            {"format_id": "140", "vcodec": "none", "acodec": "mp4a", "filesize": 2_000_000},
        ],
    }
    option = FormatOption(
        label="1080p",
        format_id="137",
        height=1080,
        fps=30.0,
        ext="mp4",
        filesize=None,
        filesize_approx=None,
        tbr=None,
    )
    assert YtDlpAdapter.resolve_download_size_bytes(info, option) == 12_000_000


def test_resolve_download_size_uses_tbr_when_sizes_missing() -> None:
    info = {
        "duration": 80,
        "formats": [
            {"format_id": "299", "vcodec": "avc1", "acodec": "none", "tbr": 1000},
            {"format_id": "251", "vcodec": "none", "acodec": "opus", "tbr": 128},
        ],
    }
    option = FormatOption(
        label="1080p60",
        format_id="299",
        height=1080,
        fps=60.0,
        ext="webm",
        filesize=None,
        filesize_approx=None,
        tbr=1000,
    )
    assert YtDlpAdapter.resolve_download_size_bytes(info, option) == 11_280_000


def test_resolve_audio_only_size_prefers_audio_only_stream() -> None:
    info = {
        "duration": 100,
        "formats": [
            {"format_id": "22", "vcodec": "avc1", "acodec": "mp4a", "filesize": 9_000_000, "abr": 192},
            {"format_id": "140", "vcodec": "none", "acodec": "mp4a", "filesize": 1_000_000, "abr": 128},
        ],
    }
    assert YtDlpAdapter.resolve_audio_only_size_bytes(info) == 1_000_000
