import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from controllers.tooling import resolve_ffmpeg_location_dir, resolve_yt_dlp_bin


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
    ALLOWED_JS_RUNTIMES = {"node", "deno", "bun", "quickjs"}
    ALLOWED_REMOTE_COMPONENTS = {"ejs:github", "ejs:npm"}

    def __init__(
        self,
        logger: Optional[Logger] = None,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> None:
        self._log = logger or (lambda msg: None)
        self._progress = progress_cb or (lambda value: None)
        self._process: Optional[subprocess.Popen[str]] = None
        self._cancel_requested = False
        self._yt_dlp_bin = resolve_yt_dlp_bin()
        self._ffmpeg_location_dir = resolve_ffmpeg_location_dir()

    def check_available(self) -> bool:
        try:
            subprocess.run(
                [self._yt_dlp_bin, "--version"],
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
        args = [self._yt_dlp_bin, "-J"]
        if self._ffmpeg_location_dir:
            args.extend(["--ffmpeg-location", self._ffmpeg_location_dir])
        if playlist_mode:
            items = playlist_items or "1"
            args.extend(["--playlist-items", items])
        else:
            args.append("--no-playlist")

        if cookies_from_browser:
            args.extend(["--cookies-from-browser", cookies_from_browser])
        self._append_js_runtime_args(args, js_runtime, js_runtime_path, remote_components)
        self._append_url_arg(args, url)

        self._log("Fetching info...")
        info = self._run_json_with_retry(args, retry_android=True)
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
            self._yt_dlp_bin,
            "-J",
            "--flat-playlist",
            "--playlist-items",
            items_arg,
        ]
        if self._ffmpeg_location_dir:
            args.extend(["--ffmpeg-location", self._ffmpeg_location_dir])

        if cookies_from_browser:
            args.extend(["--cookies-from-browser", cookies_from_browser])
        self._append_js_runtime_args(args, js_runtime, js_runtime_path, remote_components)
        self._append_url_arg(args, url)

        self._log("Fetching playlist preview...")
        info = self._run_json_with_retry(args, retry_android=True)
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

    @staticmethod
    def estimate_filesize_bytes(tbr_kbps: float, duration_seconds: float) -> int:
        bytes_per_second = (tbr_kbps * 1000) / 8
        return int(bytes_per_second * float(duration_seconds))

    @staticmethod
    def resolve_format_entry_size_bytes(
        fmt: Optional[Dict],
        duration_seconds: Optional[object],
    ) -> Optional[int]:
        if not isinstance(fmt, dict):
            return None
        size_bytes = fmt.get("filesize") or fmt.get("filesize_approx")
        if isinstance(size_bytes, (int, float)) and size_bytes > 0:
            return int(size_bytes)
        tbr = fmt.get("tbr")
        if isinstance(tbr, (int, float)) and tbr > 0 and isinstance(duration_seconds, (int, float)):
            return YtDlpAdapter.estimate_filesize_bytes(float(tbr), float(duration_seconds))
        return None

    @staticmethod
    def pick_best_audio_format(
        formats: List[Dict],
        exclude_format_id: Optional[str] = None,
    ) -> Optional[Dict]:
        best: Optional[Dict] = None
        best_score: Optional[Tuple[int, float, float, float]] = None
        for fmt in formats:
            if not isinstance(fmt, dict):
                continue
            format_id = str(fmt.get("format_id") or "")
            if exclude_format_id and format_id == exclude_format_id:
                continue
            acodec = str(fmt.get("acodec") or "none")
            if acodec == "none":
                continue
            vcodec = str(fmt.get("vcodec") or "none")
            score = (
                1 if vcodec == "none" else 0,
                float(fmt.get("abr") or 0),
                float(fmt.get("tbr") or 0),
                float(fmt.get("filesize") or fmt.get("filesize_approx") or 0),
            )
            if best_score is None or score > best_score:
                best = fmt
                best_score = score
        return best

    @staticmethod
    def resolve_audio_only_size_bytes(info: Dict) -> Optional[int]:
        formats = info.get("formats")
        if not isinstance(formats, list):
            return None
        best_audio = YtDlpAdapter.pick_best_audio_format(formats)
        return YtDlpAdapter.resolve_format_entry_size_bytes(best_audio, info.get("duration"))

    @staticmethod
    def resolve_download_size_bytes(info: Dict, option: Optional[FormatOption]) -> Optional[int]:
        if not option:
            return None
        formats = info.get("formats")
        duration = info.get("duration")
        if not isinstance(formats, list):
            size_bytes = option.filesize or option.filesize_approx
            if not size_bytes and option.tbr and isinstance(duration, (int, float)):
                return YtDlpAdapter.estimate_filesize_bytes(option.tbr, duration)
            return size_bytes

        selected = next(
            (
                fmt
                for fmt in formats
                if isinstance(fmt, dict) and str(fmt.get("format_id") or "") == option.format_id
            ),
            None,
        )
        selected_size = YtDlpAdapter.resolve_format_entry_size_bytes(selected, duration)
        if not isinstance(selected, dict):
            if selected_size:
                return selected_size
            size_bytes = option.filesize or option.filesize_approx
            if not size_bytes and option.tbr and isinstance(duration, (int, float)):
                return YtDlpAdapter.estimate_filesize_bytes(option.tbr, duration)
            return size_bytes

        has_audio = str(selected.get("acodec") or "none") != "none"
        if has_audio:
            return selected_size

        best_audio = YtDlpAdapter.pick_best_audio_format(formats, exclude_format_id=option.format_id)
        audio_size = YtDlpAdapter.resolve_format_entry_size_bytes(best_audio, duration)
        if selected_size and audio_size:
            return selected_size + audio_size
        return selected_size or audio_size

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
            self._yt_dlp_bin,
            "-f",
            format_selector,
            "-o",
            output_template,
            "--newline",
            "--progress",
            "--print",
            f"after_move:{self.FILE_PRINT_PREFIX}%(filepath)s",
        ]
        if sys.platform.startswith("win"):
            args.append("--windows-filenames")
        if self._ffmpeg_location_dir:
            args.extend(["--ffmpeg-location", self._ffmpeg_location_dir])

        if playlist_mode:
            args.append("--yes-playlist")
            if playlist_items:
                args.extend(["--playlist-items", playlist_items])
        else:
            args.append("--no-playlist")

        if cookies_from_browser:
            args.extend(["--cookies-from-browser", cookies_from_browser])
        self._append_js_runtime_args(args, js_runtime, js_runtime_path, remote_components)
        self._append_url_arg(args, url)

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
        runtime = (js_runtime or "").strip()
        runtime_path = (js_runtime_path or "").strip()
        components = (remote_components or "").strip()

        if runtime and runtime not in YtDlpAdapter.ALLOWED_JS_RUNTIMES:
            raise ValueError(f"Unsupported JS runtime: {runtime}")

        if runtime_path and not runtime:
            raise ValueError("Runtime path requires a JS runtime selection.")

        runtime_arg: Optional[str] = None
        if runtime:
            if runtime_path:
                resolved_path = Path(runtime_path).expanduser()
                if not resolved_path.is_file():
                    raise ValueError(f"Runtime path not found: {runtime_path}")
                runtime_arg = f"{runtime}:{resolved_path}"
            else:
                runtime_arg = runtime

        if runtime_arg:
            args.extend(["--js-runtimes", runtime_arg])
            if components:
                if components not in YtDlpAdapter.ALLOWED_REMOTE_COMPONENTS:
                    raise ValueError(f"Unsupported remote components source: {components}")
                args.extend(["--remote-components", components])

    @staticmethod
    def _normalize_url(url: str) -> str:
        value = url.strip()
        if not value:
            raise ValueError("URL is required.")
        if value.startswith("-"):
            raise ValueError("Invalid URL: value cannot start with '-'.")
        return value

    @staticmethod
    def _append_url_arg(args: List[str], url: str) -> None:
        args.extend(["--", YtDlpAdapter._normalize_url(url)])

    def _run_json_with_retry(self, args: List[str], *, retry_android: bool) -> Dict:
        result = self._run_json_command(args, retry_android=retry_android)
        return json.loads(result.stdout)

    def _run_json_command(self, args: List[str], *, retry_android: bool) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                args,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            detail = self._format_process_error(exc)
            if retry_android and self._is_youtube_auth_error(detail):
                self._log("Retrying with YouTube android client to bypass auth checks...")
                retry_args = list(args)
                retry_args.extend(["--extractor-args", "youtube:player_client=android"])
                return self._run_json_command(retry_args, retry_android=False)
            if detail:
                self._log(detail)
                raise RuntimeError(detail) from exc
            raise
        if result.stderr:
            self._log(result.stderr.strip())
        return result

    @staticmethod
    def _format_process_error(exc: subprocess.CalledProcessError) -> str:
        detail = ""
        if isinstance(exc.stderr, str) and exc.stderr.strip():
            detail = exc.stderr.strip()
        elif isinstance(exc.stdout, str) and exc.stdout.strip():
            detail = exc.stdout.strip()
        return detail or f"yt-dlp failed (exit {exc.returncode})."

    @staticmethod
    def _is_youtube_auth_error(message: str) -> bool:
        lowered = message.lower()
        return "sign in to confirm you're not a bot" in lowered or "sign in to confirm you\u2019re not a bot" in lowered

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
