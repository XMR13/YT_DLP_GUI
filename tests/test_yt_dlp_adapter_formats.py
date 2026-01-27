from __future__ import annotations

from yt_dlp_adapter import YtDlpAdapter


def test_infer_fps_prefers_explicit_value() -> None:
    fmt = {"fps": 60}
    assert YtDlpAdapter._infer_fps(fmt) == 60.0  # type: ignore[attr-defined]


def test_infer_fps_from_format_note() -> None:
    fmt = {"format_note": "1080p60"}
    assert YtDlpAdapter._infer_fps(fmt) == 60.0  # type: ignore[attr-defined]


def test_infer_fps_from_format_string() -> None:
    fmt = {"format": "video 1920x1080 (60fps)"}
    assert YtDlpAdapter._infer_fps(fmt) == 60.0  # type: ignore[attr-defined]


def test_infer_fps_returns_none_when_unknown() -> None:
    fmt = {"format_note": "1080p"}
    assert YtDlpAdapter._infer_fps(fmt) is None  # type: ignore[attr-defined]


def test_extract_video_formats_keeps_distinct_fps_variants() -> None:
    info = {
        "formats": [
            {"format_id": "1", "vcodec": "avc1", "height": 1080, "format_note": "1080p", "ext": "mp4", "tbr": 1000},
            {"format_id": "2", "vcodec": "avc1", "height": 1080, "format_note": "1080p60", "ext": "mp4", "tbr": 1500},
        ]
    }
    adapter = YtDlpAdapter()
    options = adapter.extract_video_formats(info)
    labels = {opt.label for opt in options}
    assert any("60fps" in label for label in labels)
    assert len(labels) == 2
