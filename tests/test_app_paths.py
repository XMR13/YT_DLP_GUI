from __future__ import annotations

from pathlib import Path

from controllers.app_paths import resolve_app_data_dir, resolve_default_output_dir


def test_resolve_app_data_dir_windows_prefers_appdata(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert resolve_app_data_dir("yt-dlp-gui-test") == tmp_path / "yt-dlp-gui-test"


def test_resolve_app_data_dir_linux_uses_xdg_data_home(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert resolve_app_data_dir("yt-dlp-gui-test") == tmp_path / "yt-dlp-gui-test"


def test_resolve_default_output_dir_windows_prefers_downloads(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    assert resolve_default_output_dir() == downloads


def test_resolve_default_output_dir_windows_falls_back_to_home(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    assert resolve_default_output_dir() == tmp_path

