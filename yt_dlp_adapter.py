import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


Logger = Callable[[str], None]
ProgressCallback = Callable[[float], None]

class DownloadCancelled(Exception):
    """Raised when the user cancels an in-flight download."""


@dataclass(frozen=True)
class FormatOption:
    label: str
    format_id: str
    height: Optional[int]
    fps: Optional[float]
    ext: Optional[str]
    filesize: Optional[int]
    filesize_approx: Optional[int]
    tbr: Optional[float]


@dataclass(frozen=True)
class PlaylistItem:
    index: int
    title: str
    webpage_url: Optional[str]
    id: Optional[str]
    ie_key: Optional[str]
    thumbnail_url: Optional[str]
    duration: Optional[int]


class YtDlpAdapter:
    FILE_PRINT_PREFIX = "__FILE__:"

    def __init__(
        self,
        logger: Optional[Logger] = None,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> None:
        self._log = logger or (lambda msg: None)
        self._progress = progress_cb or (lambda value: None)
        self._process: Optional[subprocess.Popen[str]] = None
        self._cancel_requested = False

    def check_available(self) -> bool:
        try:
            subprocess.run(
                ["yt-dlp", "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def fetch_info(
        self,
        url: str,
        playlist_mode: bool,
        playlist_items: Optional[str] = None,
        cookies_from_browser: Optional[str] = None,
        js_runtime: Optional[str] = None,
        js_runtime_path: Optional[str] = None,
        remote_components: Optional[str] = None,
    ) -> Dict:
        args = ["yt-dlp", "-J", url]
        if playlist_mode:
            items = playlist_items or "1"
            args.extend(["--playlist-items", items])
        else:
            args.append("--no-playlist")

        if cookies_from_browser:
            args.extend(["--cookies-from-browser", cookies_from_browser])
        self._append_js_runtime_args(args, js_runtime, js_runtime_path, remote_components)

        self._log("Fetching info...")
        result = subprocess.run(
            args,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.stderr:
            self._log(result.stderr.strip())

        info = json.loads(result.stdout)
        if playlist_mode and info.get("entries"):
            entry = next((e for e in info["entries"] if e), None)
            if isinstance(entry, dict):
                return entry
        return info

    def fetch_playlist_preview(
        self,
        url: str,
        start: int = 1,
        limit: int = 20,
        cookies_from_browser: Optional[str] = None,
        js_runtime: Optional[str] = None,
        js_runtime_path: Optional[str] = None,
        remote_components: Optional[str] = None,
    ) -> Tuple[List[PlaylistItem], Optional[int]]:
        start_index = max(1, start)
        end_index = max(start_index, start_index + max(1, limit) - 1)
        items_arg = f"{start_index}:{end_index}"
        args = [
            "yt-dlp",
            "-J",
            "--flat-playlist",
            "--playlist-items",
            items_arg,
            url,
        ]

        if cookies_from_browser:
            args.extend(["--cookies-from-browser", cookies_from_browser])
        self._append_js_runtime_args(args, js_runtime, js_runtime_path, remote_components)

        self._log("Fetching playlist preview...")
        result = subprocess.run(
            args,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.stderr:
            self._log(result.stderr.strip())

        info = json.loads(result.stdout)
        entries = info.get("entries") or []
        total_count = None
        for key in ("playlist_count", "n_entries", "total_entries", "playlist_entries"):
            value = info.get(key)
            if isinstance(value, int) and value > 0:
                total_count = value
                break
        items: List[PlaylistItem] = []
        for index, entry in enumerate(entries, start=start_index):
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("title") or f"Item {index}")
            webpage_url = entry.get("url") or entry.get("webpage_url")
            entry_id = entry.get("id")
            ie_key = entry.get("ie_key") or entry.get("extractor_key")
            duration = entry.get("duration")
            thumbnail_url = entry.get("thumbnail") or entry.get("thumbnails", [{}])[-1].get("url")
            if not thumbnail_url:
                thumbnail_url = self._derive_thumbnail_url(ie_key, entry_id)
            items.append(
                PlaylistItem(
                    index=index,
                    title=title,
                    webpage_url=str(webpage_url) if webpage_url else None,
                    id=str(entry_id) if entry_id else None,
                    ie_key=str(ie_key) if ie_key else None,
                    thumbnail_url=thumbnail_url,
                    duration=int(duration) if isinstance(duration, (int, float)) else None,
                )
            )
        if total_count is None:
            total_count = len(items)
        return items, total_count

    def extract_video_formats(self, info: Dict) -> List[FormatOption]:
        formats = info.get("formats") or []
        grouped: Dict[Tuple[Optional[int], Optional[float], Optional[str]], Dict] = {}

        for fmt in formats:
            if fmt.get("vcodec") in (None, "none"):
                continue
            height = fmt.get("height")
            fps = self._infer_fps(fmt)
            ext = fmt.get("ext")
            key = (height, fps, ext)
            current = grouped.get(key)
            if not current or self._format_score(fmt) > self._format_score(current):
                grouped[key] = fmt

        options: List[FormatOption] = []
        for key, fmt in grouped.items():
            height, fps, ext = key
            label = self._build_label(height, fps, ext, fmt.get("format_note"))
            options.append(
                FormatOption(
                    label=label,
                    format_id=str(fmt.get("format_id")),
                    height=height,
                    fps=fps,
                    ext=ext,
                    filesize=fmt.get("filesize"),
                    filesize_approx=fmt.get("filesize_approx"),
                    tbr=fmt.get("tbr"),
                )
            )

        options.sort(key=lambda opt: (opt.height or 0, opt.fps or 0), reverse=True)
        return options

    def download(
        self,
        url: str,
        output_dir: str,
        format_id: Optional[str],
        audio_only: bool,
        playlist_mode: bool,
        playlist_items: Optional[str] = None,
        cookies_from_browser: Optional[str] = None,
        js_runtime: Optional[str] = None,
        js_runtime_path: Optional[str] = None,
        remote_components: Optional[str] = None,
    ) -> List[str]:
        self._cancel_requested = False
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        if audio_only:
            format_selector = "bestaudio"
        elif format_id:
            format_selector = f"{format_id}+bestaudio/best"
        else:
            format_selector = "best"

        output_template = str(Path(output_dir) / "%(title)s.%(ext)s")
        args = [
            "yt-dlp",
            "-f",
            format_selector,
            "-o",
            output_template,
            "--newline",
            "--progress",
            "--print",
            f"after_move:{self.FILE_PRINT_PREFIX}%(filepath)s",
            url,
        ]

        if playlist_mode:
            args.append("--yes-playlist")
            if playlist_items:
                args.extend(["--playlist-items", playlist_items])
        else:
            args.append("--no-playlist")

        if cookies_from_browser:
            args.extend(["--cookies-from-browser", cookies_from_browser])
        self._append_js_runtime_args(args, js_runtime, js_runtime_path, remote_components)

        self._log("Starting download...")
        output_paths: List[str] = []
        self._run_download_with_retry(args, output_paths)
        return output_paths

    def cancel(self, output_dir: Optional[str], delete_partials: bool = True) -> None:
        self._cancel_requested = True
        if self._process and self._process.poll() is None:
            self._log("Cancelling download...")
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            if delete_partials and output_dir:
                self._delete_partials(output_dir)
            self._log("Download cancelled.")

    def _run_download_with_retry(self, args: List[str], output_paths: List[str]) -> None:
        had_forbidden = False
        had_sabr_warning = False
        if self._cancel_requested:
            raise DownloadCancelled()
        try:
            self._process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            process = self._process
            assert process.stdout is not None
            for line in process.stdout:
                if self._cancel_requested:
                    raise DownloadCancelled()
                line = line.strip()
                if not line:
                    continue
                if line.startswith(self.FILE_PRINT_PREFIX):
                    path = line.removeprefix(self.FILE_PRINT_PREFIX).strip()
                    if path:
                        output_paths.append(path)
                    continue
                if "HTTP Error 403" in line or "403: Forbidden" in line:
                    had_forbidden = True
                if "Some web client https formats have been skipped" in line:
                    had_sabr_warning = True
                self._log(line)
                self._update_progress_from_line(line)
            process.wait()
            if self._cancel_requested:
                raise DownloadCancelled()
            if process.returncode == 0:
                self._progress(1.0)
                return
        finally:
            self._process = None

        # Retry once with a different YouTube client to avoid SABR/HLS issues.
        if self._cancel_requested:
            raise DownloadCancelled()
        if had_forbidden or had_sabr_warning:
            retry_args = list(args)
            retry_args.extend(["--extractor-args", "youtube:player_client=android"])
            self._log("Retrying with YouTube android client due to 403/SABR warning...")
            self._process = subprocess.Popen(
                retry_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            process = self._process
            try:
                assert process.stdout is not None
                for line in process.stdout:
                    if self._cancel_requested:
                        raise DownloadCancelled()
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith(self.FILE_PRINT_PREFIX):
                        path = line.removeprefix(self.FILE_PRINT_PREFIX).strip()
                        if path:
                            output_paths.append(path)
                        continue
                    self._log(line)
                    self._update_progress_from_line(line)
                process.wait()
                if self._cancel_requested:
                    raise DownloadCancelled()
                if process.returncode != 0:
                    raise RuntimeError("yt-dlp exited with a non-zero status.")
                self._progress(1.0)
                return
            finally:
                self._process = None

        raise RuntimeError("yt-dlp exited with a non-zero status.")

    @staticmethod
    def _build_label(
        height: Optional[int],
        fps: Optional[float],
        ext: Optional[str],
        note: Optional[str],
    ) -> str:
        parts: List[str] = []
        if height:
            parts.append(f"{height}p")
        if fps:
            if isinstance(fps, float):
                parts.append(f"{int(fps)}fps" if fps.is_integer() else f"{fps}fps")
            else:
                parts.append(f"{fps}fps")
        if ext:
            parts.append(ext)
        if note:
            parts.append(note)
        return " / ".join(parts) if parts else "Unknown"

    @staticmethod
    def _format_score(fmt: Dict) -> float:
        return float(fmt.get("tbr") or fmt.get("filesize") or 0)

    def _update_progress_from_line(self, line: str) -> None:
        match = re.search(r"\[download\]\s+(\d+(?:\.\d+)?)%", line)
        if match:
            percent = float(match.group(1)) / 100.0
            self._progress(max(0.0, min(1.0, percent)))

    @staticmethod
    def _derive_thumbnail_url(ie_key: Optional[str], entry_id: Optional[str]) -> Optional[str]:
        if not entry_id or not ie_key:
            return None
        if ie_key.lower() in {"youtube", "youtube:tab"}:
            return f"https://i.ytimg.com/vi/{entry_id}/hqdefault.jpg"
        return None

    def check_runtime(self, runtime: str, runtime_path: Optional[str]) -> Tuple[bool, str]:
        binary = runtime_path or runtime
        try:
            result = subprocess.run(
                [binary, "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            version = result.stdout.strip() or "OK"
            return True, version
        except (subprocess.SubprocessError, FileNotFoundError) as exc:
            return False, str(exc)

    def _delete_partials(self, output_dir: str) -> None:
        base = Path(output_dir)
        for suffix in ("*.part", "*.ytdl", "*.tmp"):
            for path in base.glob(suffix):
                try:
                    path.unlink()
                except OSError:
                    continue

    @staticmethod
    def _append_js_runtime_args(
        args: List[str],
        js_runtime: Optional[str],
        js_runtime_path: Optional[str],
        remote_components: Optional[str],
    ) -> None:
        # Ensure js runtime and remote-components flags are appended at most once.
        runtime_arg: Optional[str] = None
        if js_runtime:
            runtime_arg = f"{js_runtime}:{js_runtime_path}" if js_runtime_path else js_runtime
        elif js_runtime_path:
            runtime_arg = js_runtime_path

        if runtime_arg:
            args.extend(["--js-runtimes", runtime_arg])
            if remote_components:
                args.extend(["--remote-components", remote_components])

    @staticmethod
    def _infer_fps(fmt: Dict) -> Optional[float]:
        fps = fmt.get("fps")
        if isinstance(fps, (int, float)):
            return float(fps)

        candidates = [
            fmt.get("format_note"),
            fmt.get("format"),
            fmt.get("format_id"),
        ]
        text = " ".join(str(value) for value in candidates if value)
        if not text:
            return None

        match = re.search(r"(\d+(?:\.\d+)?)\s*fps", text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None

        match = re.search(r"\b(\d{3,4})p(\d{2,3})\b", text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(2))
            except ValueError:
                return None

        match = re.search(r"\b(\d{3,4})p\s*(\d{2,3})\b", text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(2))
            except ValueError:
                return None

        return None
