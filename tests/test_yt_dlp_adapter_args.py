from __future__ import annotations

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


def test_runtime_with_path_and_remote_components() -> None:
    args = _build_args("node", "/path/to/node", "ejs:npm")
    assert args == [
        "--js-runtimes",
        "node:/path/to/node",
        "--remote-components",
        "ejs:npm",
    ]
    assert _count_flag(args, "--remote-components") == 1


def test_runtime_without_remote_components() -> None:
    args = _build_args("node", None, None)
    assert args == ["--js-runtimes", "node"]
    assert _count_flag(args, "--remote-components") == 0


def test_path_only_with_remote_components() -> None:
    args = _build_args(None, "/path/to/node", "ejs:github")
    assert args == ["--js-runtimes", "/path/to/node", "--remote-components", "ejs:github"]
    assert _count_flag(args, "--remote-components") == 1


def test_path_only_without_remote_components() -> None:
    args = _build_args(None, "/path/to/node", None)
    assert args == ["--js-runtimes", "/path/to/node"]
    assert _count_flag(args, "--remote-components") == 0


def test_remote_components_without_runtime_is_ignored() -> None:
    args = _build_args(None, None, "ejs:github")
    assert args == []
    assert _count_flag(args, "--remote-components") == 0
