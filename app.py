from __future__ import annotations

from pathlib import Path
from queue import Empty, Queue
from typing import Dict, List, Optional, Tuple

import customtkinter as ctk
from tkinter import filedialog, messagebox
from urllib.parse import parse_qs, urlparse

from controllers.download_controller import DownloadController
from ui.form_panel import FormPanel
from ui.header import Header
from ui.info_panel import InfoPanel
from ui.options_panel import OptionsPanel
from ui.playlist_preview import PlaylistPreviewPanel
from ui.status_panel import StatusPanel
from yt_dlp_adapter import FormatOption, YtDlpAdapter


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("dark-blue")

        self.title("yt-dlp GUI")
        self.geometry("900x680")
        self.minsize(860, 620)

        self._event_queue: Queue[Tuple[str, object]] = Queue()
        self._adapter = YtDlpAdapter(self._enqueue_log, self._enqueue_progress)
        self._controller = DownloadController(self._event_queue, self._adapter)
        self._format_options: List[FormatOption] = []
        self._format_map: Dict[str, FormatOption] = {}
        self._current_info: Dict = {}
        self._current_task: Optional[str] = None
        self._solver_warning_shown = False

        self.url_var = ctk.StringVar()
        self.playlist_var = ctk.BooleanVar(value=False)
        self.format_type_var = ctk.StringVar(value="Video + Audio")
        self.resolution_var = ctk.StringVar(value="Best available")
        self.output_dir_var = ctk.StringVar(value=str(Path.cwd()))
        self.cookies_var = ctk.StringVar(value="None")
        self.js_runtime_var = ctk.StringVar(value="Auto")
        self.js_runtime_path_var = ctk.StringVar(value="")
        self.remote_components_var = ctk.StringVar(value="ejs:github")

        self._build_ui()
        self._poll_events()
        self._check_yt_dlp()

        self.format_type_var.trace_add("write", self._on_selection_change)
        self.resolution_var.trace_add("write", self._on_selection_change)
        self.playlist_var.trace_add("write", self._on_playlist_toggle)

    def _build_ui(self) -> None:
        header = Header(self)
        header.pack(fill="x", padx=20, pady=(20, 10))

        body = ctk.CTkFrame(self, corner_radius=18)
        body.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.form_panel = FormPanel(
            body,
            url_var=self.url_var,
            playlist_var=self.playlist_var,
            on_fetch=self._on_fetch_formats,
            on_download=self._on_download,
            on_cancel=self._on_cancel,
            on_diagnostics=self._on_diagnostics,
        )
        self.form_panel.pack(fill="x", padx=18, pady=18)

        self.options_panel = OptionsPanel(
            body,
            format_type_var=self.format_type_var,
            resolution_var=self.resolution_var,
            output_dir_var=self.output_dir_var,
            cookies_var=self.cookies_var,
            js_runtime_var=self.js_runtime_var,
            js_runtime_path_var=self.js_runtime_path_var,
            remote_components_var=self.remote_components_var,
            on_choose_output=self._choose_output_dir,
            on_choose_runtime_path=self._choose_runtime_path,
        )
        self.options_panel.pack(fill="x", padx=18, pady=(0, 18))

        self.info_panel = InfoPanel(body)
        self.info_panel.pack(fill="x", padx=18, pady=(0, 18))

        self.preview_panel = PlaylistPreviewPanel(body)
        self.preview_panel.pack(fill="x", padx=18, pady=(0, 18))
        self.preview_panel.set_items([])

        self.status_panel = StatusPanel(body)
        self.status_panel.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self._append_log("Ready.")

    def _check_yt_dlp(self) -> None:
        if not self._adapter.check_available():
            self._append_log("yt-dlp not found. Install it with: pip install yt-dlp")
            self._set_controls_state("disabled")
            messagebox.showerror("yt-dlp missing", "yt-dlp is not installed or not on PATH.")

    def _set_controls_state(self, state: str) -> None:
        self.form_panel.fetch_button.configure(state=state)
        self.form_panel.download_button.configure(state=state)
        self.form_panel.cancel_button.configure(state="disabled")
        self.form_panel.diag_button.configure(state=state)

    def _choose_output_dir(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self.output_dir_var.set(folder)

    def _choose_runtime_path(self) -> None:
        file_path = filedialog.askopenfilename()
        if file_path:
            self.js_runtime_path_var.set(file_path)

    def _on_fetch_formats(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a URL first.")
            return

        playlist_mode = self._resolve_playlist_mode(url)
        if playlist_mode and not self.playlist_var.get():
            self.playlist_var.set(True)
            self._append_log("Detected playlist URL — enabling Playlist mode.")

        self._set_busy(True, task="fetch")
        self._controller.fetch_formats(
            url=url,
            playlist_mode=playlist_mode,
            cookies=self._normalize_cookies(),
            js_runtime=self._normalize_js_runtime(),
            js_runtime_path=self._normalize_runtime_path(),
            remote_components=self._normalize_remote_components(),
        )

        if playlist_mode:
            self._controller.fetch_preview(
                url=url,
                cookies=self._normalize_cookies(),
                js_runtime=self._normalize_js_runtime(),
                js_runtime_path=self._normalize_runtime_path(),
                remote_components=self._normalize_remote_components(),
                limit=20,
            )
        else:
            self.preview_panel.set_items([])

    def _on_download(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a URL first.")
            return

        playlist_mode = self._resolve_playlist_mode(url)
        if playlist_mode and not self.playlist_var.get():
            self.playlist_var.set(True)
            self._append_log("Detected playlist URL — enabling Playlist mode.")

        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            messagebox.showwarning("Missing output", "Please choose an output folder.")
            return

        self._set_busy(True, task="download")
        self._controller.start_download(
            url=url,
            output_dir=output_dir,
            format_id=self._resolve_format_id(),
            audio_only=self.format_type_var.get() == "Audio only",
            playlist_mode=playlist_mode,
            cookies=self._normalize_cookies(),
            js_runtime=self._normalize_js_runtime(),
            js_runtime_path=self._normalize_runtime_path(),
            remote_components=self._normalize_remote_components(),
        )

    def _on_cancel(self) -> None:
        if self._current_task != "download":
            return
        self._controller.cancel_download()

    def _on_diagnostics(self) -> None:
        self._append_log("Running diagnostics...")
        if self._adapter.check_available():
            self._append_log("yt-dlp: OK")
        else:
            self._append_log("yt-dlp: Not found on PATH.")

        runtime = self._normalize_js_runtime()
        if runtime:
            ok, details = self._adapter.check_runtime(runtime, self._normalize_runtime_path())
            status = "OK" if ok else "Failed"
            self._append_log(f"{runtime}: {status} ({details})")
        else:
            self._append_log("JS runtime: Auto (no explicit runtime selected)")

    def _on_playlist_toggle(self, *_args: object) -> None:
        if not self.playlist_var.get():
            self.preview_panel.set_items([])

    def _resolve_format_id(self) -> Optional[str]:
        if self.format_type_var.get() == "Audio only":
            return None

        selected = self.resolution_var.get()
        for option in self._format_options:
            if option.label == selected:
                return option.format_id
        return None

    def _normalize_cookies(self) -> Optional[str]:
        choice = self.cookies_var.get().strip()
        return None if choice.lower() == "none" else choice

    def _normalize_js_runtime(self) -> Optional[str]:
        choice = self.js_runtime_var.get().strip()
        return None if choice.lower() == "auto" else choice

    def _normalize_runtime_path(self) -> Optional[str]:
        path = self.js_runtime_path_var.get().strip()
        if self.js_runtime_var.get().strip().lower() == "auto":
            return None
        return path or None

    def _normalize_remote_components(self) -> Optional[str]:
        choice = self.remote_components_var.get().strip()
        return None if choice.lower() == "none" else choice

    def _resolve_playlist_mode(self, url: str) -> bool:
        if self.playlist_var.get():
            return True
        try:
            query = parse_qs(urlparse(url).query)
            return "list" in query
        except ValueError:
            return False

    def _on_selection_change(self, *_args: object) -> None:
        self._update_info_display()

    def _set_busy(self, busy: bool, task: Optional[str] = None) -> None:
        state = "disabled" if busy else "normal"
        self.form_panel.fetch_button.configure(state=state)
        self.form_panel.download_button.configure(state=state)
        self.form_panel.diag_button.configure(state=state)
        self._current_task = task if busy else None
        cancel_state = "normal" if busy and task == "download" else "disabled"
        self.form_panel.cancel_button.configure(state=cancel_state)
        if busy:
            self._append_log("Working...")
        else:
            self._update_progress(0.0)

    def _enqueue_log(self, message: str) -> None:
        self._event_queue.put(("log", message))

    def _enqueue_progress(self, value: float) -> None:
        self._event_queue.put(("progress", value))

    def _append_log(self, message: str) -> None:
        if not self._solver_warning_shown and (
            "Signature solving failed" in message or "challenge solving failed" in message
        ):
            self._solver_warning_shown = True
            hint = (
                "Hint: Enable a JS runtime (node/deno/bun) and set EJS scripts source "
                "to ejs:github or ejs:npm."
            )
            self._append_log(hint)
        self.status_panel.append(message)

    def _update_progress(self, value: float) -> None:
        value = max(0.0, min(1.0, value))
        self.form_panel.progress.set(value)
        percent = int(value * 100)
        label = f"{percent}%"
        if value == 0.0:
            label = "Idle"
        elif value >= 1.0:
            label = "Completed"
        self.form_panel.progress_label.configure(text=label)

    def _update_info_display(self) -> None:
        info = self._current_info or {}
        title = info.get("title") or "—"

        if self.format_type_var.get() == "Audio only":
            resolution = "Audio only"
            fmt = "bestaudio"
            size = "Unknown"
        else:
            selected = self.resolution_var.get()
            option = self._format_map.get(selected)
            if option:
                resolution = f"{option.height}p" if option.height else "Unknown"
                if option.fps:
                    if isinstance(option.fps, float):
                        fps_text = int(option.fps) if option.fps.is_integer() else option.fps
                    else:
                        fps_text = option.fps
                    resolution = f"{resolution} @ {fps_text}fps"
                fmt = option.ext or "Unknown"
                size_bytes = option.filesize or option.filesize_approx
                size = self._format_size(size_bytes)
            else:
                resolution = "Best available"
                fmt = "Auto"
                size = "Unknown"

        self.info_panel.update_values(
            {
                "title": title,
                "resolution": resolution,
                "format": fmt,
                "size": size,
            }
        )

    @staticmethod
    def _format_size(size_bytes: Optional[int]) -> str:
        if not size_bytes:
            return "Unknown"
        size = float(size_bytes)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def _poll_events(self) -> None:
        try:
            while True:
                event, payload = self._event_queue.get_nowait()
                if event == "formats":
                    self._format_options = list(payload)  # type: ignore[arg-type]
                    self._format_map = {opt.label: opt for opt in self._format_options}
                    values = [opt.label for opt in self._format_options]
                    if values:
                        values.insert(0, "Best available")
                    else:
                        values = ["Best available"]
                    self.options_panel.resolution_menu.configure(values=values)
                    self.resolution_var.set(values[0])
                    self._update_info_display()
                elif event == "preview":
                    self.preview_panel.set_items(list(payload))  # type: ignore[arg-type]
                elif event == "info":
                    self._current_info = dict(payload)  # type: ignore[arg-type]
                    self._update_info_display()
                elif event == "log":
                    self._append_log(str(payload))
                elif event == "progress":
                    self._update_progress(float(payload))
                elif event == "error":
                    self._append_log(f"Error: {payload}")
                    messagebox.showerror("Error", str(payload))
                elif event == "busy":
                    if isinstance(payload, tuple):
                        busy, task = payload
                        self._set_busy(bool(busy), task=str(task) if task else None)
                    else:
                        self._set_busy(bool(payload))
        except Empty:
            pass
        self.after(200, self._poll_events)


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
