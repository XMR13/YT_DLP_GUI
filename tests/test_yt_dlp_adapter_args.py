from __future__ import annotations

import pytest

from yt_dlp_adapter import YtDlpAdapter


def _build_args(
    js_runtime: str | None,
    js_runtime_path: str | None,
    remote_components: str | None,
) -> list[str]:
    args: list[str] = []
    YtDlpAdapter._append_js_runtime_args(  # type: ignore[attr-defined]
        args,
        js_runtime,
        js_runtime_path,
        remote_components,
    )
    return args


def _count_flag(args: list[str], flag: str) -> int:
    return sum(1 for item in args if item == flag)


def test_runtime_with_remote_components() -> None:
    args = _build_args("node", None, "ejs:github")
    assert args == ["--js-runtimes", "node", "--remote-components", "ejs:github"]
    assert _count_flag(args, "--remote-components") == 1


def test_runtime_with_path_and_remote_components(tmp_path) -> None:
    runtime_path = tmp_path / "node"
    runtime_path.write_text("", encoding="utf-8")
    args = _build_args("node", str(runtime_path), "ejs:npm")
    assert args == [
        "--js-runtimes",
        f"node:{runtime_path}",
        "--remote-components",
        "ejs:npm",
    ]
    assert _count_flag(args, "--remote-components") == 1


def test_runtime_without_remote_components() -> None:
    args = _build_args("node", None, None)
    assert args == ["--js-runtimes", "node"]
    assert _count_flag(args, "--remote-components") == 0


def test_path_only_with_remote_components_is_rejected() -> None:
    with pytest.raises(ValueError, match="Runtime path requires"):
        _build_args(None, "/path/to/node", "ejs:github")


def test_path_only_without_remote_components_is_rejected() -> None:
    with pytest.raises(ValueError, match="Runtime path requires"):
        _build_args(None, "/path/to/node", None)


def test_remote_components_without_runtime_is_ignored() -> None:
    args = _build_args(None, None, "ejs:github")
    assert args == []
    assert _count_flag(args, "--remote-components") == 0


def test_unsupported_runtime_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported JS runtime"):
        _build_args("powershell", None, None)


def test_unsupported_remote_components_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported remote components"):
        _build_args("node", None, "ejs:evil")


def test_normalize_url_strips_whitespace() -> None:
    value = YtDlpAdapter._normalize_url("  https://example.com/video  ")  # type: ignore[attr-defined]
    assert value == "https://example.com/video"


def test_normalize_url_rejects_empty_value() -> None:
    with pytest.raises(ValueError, match="URL is required"):
        YtDlpAdapter._normalize_url("   ")  # type: ignore[attr-defined]


def test_normalize_url_rejects_option_like_value() -> None:
    with pytest.raises(ValueError, match="cannot start with '-'"):
        YtDlpAdapter._normalize_url("--exec echo pwned")  # type: ignore[attr-defined]


def test_append_url_arg_adds_end_of_options_marker() -> None:
    args = ["yt-dlp", "-J"]
    YtDlpAdapter._append_url_arg(args, " https://example.com/watch?v=1 ")  # type: ignore[attr-defined]
    assert args[-2:] == ["--", "https://example.com/watch?v=1"]
