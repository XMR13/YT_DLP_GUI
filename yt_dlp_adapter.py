import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


Logger = Callable[[str], None]


@dataclass(frozen=True)
class FormatOption:
    label: str
    format_id: str
    height: Optional[int]
    fps: Optional[float]
    ext: Optional[str]


class YtDlpAdapter:
    def __init__(self, logger: Optional[Logger] = None) -> None:
        self._log = logger or (lambda msg: None)

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

    def fetch_info(self, url: str, playlist_mode: bool) -> Dict:
        args = ["yt-dlp", "-J", url]
        if playlist_mode:
            args.extend(["--playlist-items", "1"])
        else:
            args.append("--no-playlist")

        self._log("Fetching format info...")
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

    def extract_video_formats(self, info: Dict) -> List[FormatOption]:
        formats = info.get("formats") or []
        grouped: Dict[Tuple[Optional[int], Optional[float], Optional[str]], Dict] = {}

        for fmt in formats:
            if fmt.get("vcodec") in (None, "none"):
                continue
            height = fmt.get("height")
            fps = fmt.get("fps")
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
    ) -> None:
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
            url,
        ]

        if playlist_mode:
            args.append("--yes-playlist")
        else:
            args.append("--no-playlist")

        self._log("Starting download...")
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert process.stdout is not None
        for line in process.stdout:
            line = line.strip()
            if line:
                self._log(line)
        process.wait()
        if process.returncode != 0:
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
