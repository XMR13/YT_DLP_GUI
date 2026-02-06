from __future__ import annotations

import controllers.tooling as tooling


def test_resolve_yt_dlp_bin_env_override(monkeypatch) -> None:
    monkeypatch.setenv("YTDLP_GUI_YTDLP_PATH", r"C:\tools\yt-dlp.exe")
    assert tooling.resolve_yt_dlp_bin() == r"C:\tools\yt-dlp.exe"


def test_resolve_yt_dlp_bin_frozen_prefers_app_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("YTDLP_GUI_YTDLP_PATH", raising=False)
    monkeypatch.setattr(tooling.shutil, "which", lambda _: None)
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "yt-dlp.exe").write_text("x", encoding="utf-8")
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(app_dir / "yt-dlp-gui.exe"), raising=False)
    assert tooling.resolve_yt_dlp_bin() == str(app_dir / "yt-dlp.exe")


def test_resolve_ffmpeg_location_dir_requires_both_binaries(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("YTDLP_GUI_FFMPEG_DIR", raising=False)
    monkeypatch.setattr(tooling.shutil, "which", lambda _: None)
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "ffmpeg.exe").write_text("x", encoding="utf-8")
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(app_dir / "yt-dlp-gui.exe"), raising=False)
    assert tooling.resolve_ffmpeg_location_dir() is None

    (app_dir / "ffprobe.exe").write_text("x", encoding="utf-8")
    assert tooling.resolve_ffmpeg_location_dir() == str(app_dir)
