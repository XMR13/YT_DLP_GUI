from __future__ import annotations

from datetime import datetime
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
from ui.playlist_form_panel import PlaylistFormPanel
from ui.playlist_preview import PlaylistPreviewPanel
from ui.status_panel import StatusPanel
from yt_dlp_adapter import FormatOption, PlaylistItem, YtDlpAdapter


class App(ctk.CTk):
    SCROLL_SPEED = 20
    STATUS_MIN_HEIGHT = 160
    STATUS_MAX_HEIGHT = 260
    PLAYLIST_AUTO_FETCH_DELAY_MS = 250
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
        self._layout_job: Optional[str] = None
        self._auto_fetch_job: Optional[str] = None
        self._expected_formats_request_id: Optional[int] = None
        self._warning_once: set[str] = set()

        self.url_var = ctk.StringVar()
        self.playlist_url_var = ctk.StringVar()
        self.format_type_var = ctk.StringVar(value="Video + Audio")
        self.resolution_var = ctk.StringVar(value="Best available")
        self.output_dir_var = ctk.StringVar(value=str(Path.cwd()))
        self.cookies_var = ctk.StringVar(value="None")
        self.js_runtime_var = ctk.StringVar(value="Auto")
        self.js_runtime_path_var = ctk.StringVar(value="")
        self.remote_components_var = ctk.StringVar(value="ejs:github")
        self._selected_playlist_item: Optional[PlaylistItem] = None

        self._log_file = self._init_log_file()
        self._build_ui()
        self._poll_events()
        self._check_yt_dlp()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.format_type_var.trace_add("write", self._on_selection_change)
        self.resolution_var.trace_add("write", self._on_selection_change)

    def _build_ui(self) -> None:
        header = Header(self)
        header.pack(fill="x", padx=20, pady=(20, 10))

        self._body = ctk.CTkFrame(self, corner_radius=18)
        self._body.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self._content = ctk.CTkScrollableFrame(self._body, corner_radius=0, fg_color="transparent")
        self._content.pack(fill="both", expand=True)
        self._bind_scroll_events(self._content, speed=self.SCROLL_SPEED)

        self.tabview = ctk.CTkTabview(self._content)
        self.tabview.pack(fill="x", padx=18, pady=18)

        single_tab = self.tabview.add("Single")
        playlist_tab = self.tabview.add("Playlist")

        self.form_panel = FormPanel(
            single_tab,
            url_var=self.url_var,
            playlist_var=None,
            on_fetch=self._on_fetch_single_formats,
            on_download=self._on_download_single,
            on_cancel=self._on_cancel,
            on_diagnostics=self._on_diagnostics,
            url_label_text="Video URL",
        )
        self.form_panel.pack(fill="x", padx=18, pady=18)

        self.playlist_form_panel = PlaylistFormPanel(
            playlist_tab,
            url_var=self.playlist_url_var,
            on_fetch=self._on_fetch_playlist,
            on_fetch_selected=self._on_fetch_selected_formats,
            on_download_selected=self._on_download_selected,
            on_download_playlist=self._on_download_playlist,
            on_cancel=self._on_cancel,
            on_diagnostics=self._on_diagnostics,
        )
        self.playlist_form_panel.pack(fill="x", padx=18, pady=(18, 10))

        self.options_panel = OptionsPanel(
            self._content,
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

        self.info_panel = InfoPanel(self._content)
        self.info_panel.pack(fill="x", padx=18, pady=(0, 18))

        self.preview_panel = PlaylistPreviewPanel(
            playlist_tab,
            on_select=self._on_playlist_item_selected,
            scroll_speed=self.SCROLL_SPEED,
        )
        self.preview_panel.pack(fill="x", padx=18, pady=(0, 18))
        self.preview_panel.set_items([])

        self.status_panel = StatusPanel(
            self._content,
            min_height=self.STATUS_MIN_HEIGHT,
            max_height=self.STATUS_MAX_HEIGHT,
        )
        self.status_panel.pack(fill="x", padx=18, pady=(0, 18))
        self._append_log("Ready.")

        self._progress_targets = [
            (self.form_panel.progress, self.form_panel.progress_label),
            (self.playlist_form_panel.progress, self.playlist_form_panel.progress_label),
        ]
        self._set_playlist_selection_state(False)
        self._body.bind("<Configure>", self._schedule_layout_update)
        self._schedule_layout_update()

    @staticmethod
    def _bind_scroll_events(scrollable: ctk.CTkScrollableFrame, speed: int = 5) -> None:
        canvas = getattr(scrollable, "_parent_canvas", None) or getattr(scrollable, "_canvas", None)
        if canvas is None:
            return

        def on_mousewheel(event: object) -> None:
            delta = 0
            wheel_delta = int(getattr(event, "delta", 0))
            if wheel_delta:
                delta = int(-1 * (wheel_delta / 120))
                if delta == 0:
                    delta = -1 if wheel_delta > 0 else 1
            elif getattr(event, "num", None) == 4:
                delta = -1
            elif getattr(event, "num", None) == 5:
                delta = 1
            if delta:
                canvas.yview_scroll(delta * max(1, speed), "units")

        def bind_to_mousewheel(_event: object) -> None:
            scrollable.bind_all("<MouseWheel>", on_mousewheel)
            scrollable.bind_all("<Button-4>", on_mousewheel)
            scrollable.bind_all("<Button-5>", on_mousewheel)

        def unbind_from_mousewheel(_event: object) -> None:
            scrollable.unbind_all("<MouseWheel>")
            scrollable.unbind_all("<Button-4>")
            scrollable.unbind_all("<Button-5>")

        scrollable.bind("<Enter>", bind_to_mousewheel)
        scrollable.bind("<Leave>", unbind_from_mousewheel)

    def _schedule_layout_update(self, _event: object | None = None) -> None:
        if self._layout_job:
            self.after_cancel(self._layout_job)
        self._layout_job = self.after(60, self._apply_dynamic_layout)

    def _apply_dynamic_layout(self) -> None:
        self._layout_job = None
        if not self._content.winfo_exists():
            return
        view_height = self._content.winfo_height()
        if view_height <= 1:
            self._layout_job = self.after(60, self._apply_dynamic_layout)
            return
        fixed = (
            self.tabview.winfo_height()
            + self.options_panel.winfo_height()
            + self.info_panel.winfo_height()
        )
        available = view_height - fixed - 60
        self.status_panel.set_height(available)

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
        self.playlist_form_panel.fetch_button.configure(state=state)
        self.playlist_form_panel.download_playlist_button.configure(state=state)
        self.playlist_form_panel.diag_button.configure(state=state)
        self.playlist_form_panel.cancel_button.configure(state="disabled")
        self._set_playlist_selection_state(state == "normal" and self._selected_playlist_item is not None)

    def _choose_output_dir(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self.output_dir_var.set(folder)

    def _choose_runtime_path(self) -> None:
        file_path = filedialog.askopenfilename()
        if file_path:
            self.js_runtime_path_var.set(file_path)

    def _on_fetch_single_formats(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a URL first.")
            return

        if self._resolve_playlist_mode(url):
            messagebox.showinfo("Playlist detected", "Use the Playlist tab for playlist URLs.")
            self.playlist_url_var.set(url)
            self.tabview.set("Playlist")
            return

        self._set_busy(True, task="fetch")
        self._expected_formats_request_id = self._controller.fetch_formats(
            url=url,
            playlist_mode=False,
            playlist_items=None,
            cookies=self._normalize_cookies(),
            js_runtime=self._normalize_js_runtime(),
            js_runtime_path=self._normalize_runtime_path(),
            remote_components=self._normalize_remote_components(),
        )

    def _on_download_single(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a URL first.")
            return

        if self._resolve_playlist_mode(url):
            messagebox.showinfo("Playlist detected", "Use the Playlist tab for playlist URLs.")
            self.playlist_url_var.set(url)
            self.tabview.set("Playlist")
            return

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
            playlist_mode=False,
            playlist_items=None,
            cookies=self._normalize_cookies(),
            js_runtime=self._normalize_js_runtime(),
            js_runtime_path=self._normalize_runtime_path(),
            remote_components=self._normalize_remote_components(),
        )

    def _on_fetch_playlist(self) -> None:
        url = self.playlist_url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a playlist URL first.")
            return

        self._selected_playlist_item = None
        self._set_playlist_selection_state(False)
        self.preview_panel.set_items([])
        self._controller.fetch_preview(
            url=url,
            cookies=self._normalize_cookies(),
            js_runtime=self._normalize_js_runtime(),
            js_runtime_path=self._normalize_runtime_path(),
            remote_components=self._normalize_remote_components(),
            limit=20,
        )

    def _on_fetch_selected_formats(self) -> None:
        if not self._selected_playlist_item:
            messagebox.showwarning("No selection", "Please select a playlist item first.")
            return

        url = self.playlist_url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a playlist URL first.")
            return

        self._set_busy(True, task="fetch")
        self._expected_formats_request_id = self._controller.fetch_formats(
            url=url,
            playlist_mode=True,
            playlist_items=str(self._selected_playlist_item.index),
            cookies=self._normalize_cookies(),
            js_runtime=self._normalize_js_runtime(),
            js_runtime_path=self._normalize_runtime_path(),
            remote_components=self._normalize_remote_components(),
        )

    def _on_download_selected(self) -> None:
        if not self._selected_playlist_item:
            messagebox.showwarning("No selection", "Please select a playlist item first.")
            return

        url = self.playlist_url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a playlist URL first.")
            return

        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            messagebox.showwarning("Missing output", "Please choose an output folder.")
            return

        self._set_busy(True, task="download_item")
        self._controller.start_download(
            url=url,
            output_dir=output_dir,
            format_id=self._resolve_format_id(),
            audio_only=self.format_type_var.get() == "Audio only",
            playlist_mode=True,
            playlist_items=str(self._selected_playlist_item.index),
            cookies=self._normalize_cookies(),
            js_runtime=self._normalize_js_runtime(),
            js_runtime_path=self._normalize_runtime_path(),
            remote_components=self._normalize_remote_components(),
        )

    def _on_download_playlist(self) -> None:
        url = self.playlist_url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a playlist URL first.")
            return

        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            messagebox.showwarning("Missing output", "Please choose an output folder.")
            return

        self._set_busy(True, task="download_playlist")
        self._controller.start_download(
            url=url,
            output_dir=output_dir,
            format_id=self._resolve_format_id(),
            audio_only=self.format_type_var.get() == "Audio only",
            playlist_mode=True,
            playlist_items=None,
            cookies=self._normalize_cookies(),
            js_runtime=self._normalize_js_runtime(),
            js_runtime_path=self._normalize_runtime_path(),
            remote_components=self._normalize_remote_components(),
        )

    def _on_cancel(self) -> None:
        if self._current_task not in ("download", "download_item", "download_playlist"):
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
        try:
            query = parse_qs(urlparse(url).query)
            return "list" in query
        except ValueError:
            return False

    def _on_selection_change(self, *_args: object) -> None:
        self._update_info_display()

    def _on_playlist_item_selected(self, item: PlaylistItem) -> None:
        self._selected_playlist_item = item
        self._set_playlist_selection_state(True)
        self._current_info = {"title": item.title, "duration": item.duration}
        self._update_info_display()
        self._schedule_auto_fetch_selected()

    def _set_playlist_selection_state(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.playlist_form_panel.fetch_selected_button.configure(state=state)
        self.playlist_form_panel.download_selected_button.configure(state=state)

    def _set_busy(self, busy: bool, task: Optional[str] = None) -> None:
        state = "disabled" if busy else "normal"
        self.form_panel.fetch_button.configure(state=state)
        self.form_panel.download_button.configure(state=state)
        self.form_panel.diag_button.configure(state=state)
        self.playlist_form_panel.fetch_button.configure(state=state)
        self.playlist_form_panel.download_playlist_button.configure(state=state)
        self.playlist_form_panel.diag_button.configure(state=state)
        self._set_playlist_selection_state(not busy and self._selected_playlist_item is not None)
        self._current_task = task if busy else None
        cancel_state = "normal" if busy and task in ("download", "download_item", "download_playlist") else "disabled"
        self.form_panel.cancel_button.configure(state=cancel_state)
        self.playlist_form_panel.cancel_button.configure(state=cancel_state)
        if busy:
            self._append_log("Working...")
        else:
            self._update_progress(0.0)

    def _enqueue_log(self, message: str) -> None:
        self._event_queue.put(("log", message))

    def _enqueue_progress(self, value: float) -> None:
        self._event_queue.put(("progress", value))

    def _append_log(self, message: str) -> None:
        once_markers = (
            "No supported JavaScript runtime could be found.",
            "Some web_safari client https formats have been skipped",
            "Some web client https formats have been skipped",
        )
        for marker in once_markers:
            if marker in message:
                if marker in self._warning_once:
                    return
                self._warning_once.add(marker)
                break
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
        if self._log_file:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._log_file.write(f"[{timestamp}] {message}\n")
            self._log_file.flush()

    def _update_progress(self, value: float) -> None:
        value = max(0.0, min(1.0, value))
        percent = int(value * 100)
        label = f"{percent}%"
        if value == 0.0:
            label = "Idle"
        elif value >= 1.0:
            label = "Completed"
        for bar, bar_label in self._progress_targets:
            bar.set(value)
            bar_label.configure(text=label)

    def _update_info_display(self) -> None:
        info = self._current_info or {}
        title = info.get("title") or "—"
        duration = self._format_duration(info.get("duration"))
        duration_seconds = info.get("duration") if isinstance(info.get("duration"), (int, float)) else None

        if self.format_type_var.get() == "Audio only":
            resolution = "Audio only"
            fmt = "bestaudio"
            size = "Unknown"
        else:
            selected = self.resolution_var.get()
            option = self._format_map.get(selected)
            if selected == "Best available" and self._format_options:
                option = self._format_options[0]
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
                if not size_bytes and option.tbr and duration_seconds:
                    size_bytes = self._estimate_filesize_bytes(option.tbr, duration_seconds)
                size = self._format_size(size_bytes)
            else:
                resolution = "Best available"
                fmt = "Auto"
                size = "Unknown"

        self.info_panel.update_values(
            {
                "title": title,
                "duration": duration,
                "resolution": resolution,
                "format": fmt,
                "size": size,
            }
        )
        if self._selected_playlist_item:
            self.preview_panel.update_selected_size(size)

    def _schedule_auto_fetch_selected(self) -> None:
        if self._auto_fetch_job:
            self.after_cancel(self._auto_fetch_job)
        self._auto_fetch_job = self.after(
            self.PLAYLIST_AUTO_FETCH_DELAY_MS, self._auto_fetch_selected_formats
        )

    def _auto_fetch_selected_formats(self) -> None:
        self._auto_fetch_job = None
        if not self._selected_playlist_item:
            return
        url = self.playlist_url_var.get().strip()
        if not url:
            return
        self.preview_panel.update_selected_size("loading...")
        self._expected_formats_request_id = self._controller.fetch_formats(
            url=url,
            playlist_mode=True,
            playlist_items=str(self._selected_playlist_item.index),
            cookies=self._normalize_cookies(),
            js_runtime=self._normalize_js_runtime(),
            js_runtime_path=self._normalize_runtime_path(),
            remote_components=self._normalize_remote_components(),
        )

    @staticmethod
    def _format_duration(value: Optional[object]) -> str:
        if not isinstance(value, (int, float)):
            return "—"
        total = int(value)
        hours = total // 3600
        minutes = (total % 3600) // 60
        seconds = total % 60
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

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

    @staticmethod
    def _estimate_filesize_bytes(tbr_kbps: float, duration_seconds: float) -> int:
        bytes_per_second = (tbr_kbps * 1000) / 8
        return int(bytes_per_second * float(duration_seconds))

    def _poll_events(self) -> None:
        try:
            while True:
                event, payload = self._event_queue.get_nowait()
                if event == "formats":
                    request_id: Optional[int] = None
                    options = payload
                    if isinstance(payload, tuple) and len(payload) == 2 and isinstance(payload[0], int):
                        request_id, options = payload
                    if request_id is not None and request_id != self._expected_formats_request_id:
                        continue
                    self._format_options = list(options)  # type: ignore[arg-type]
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
                    self._selected_playlist_item = None
                    self._set_playlist_selection_state(False)
                    self._current_info = {}
                    self._update_info_display()
                elif event == "info":
                    request_id: Optional[int] = None
                    info = payload
                    if isinstance(payload, tuple) and len(payload) == 2 and isinstance(payload[0], int):
                        request_id, info = payload
                    if request_id is not None and request_id != self._expected_formats_request_id:
                        continue
                    self._current_info = dict(info)  # type: ignore[arg-type]
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

    def _init_log_file(self) -> Optional[object]:
        try:
            logs_dir = Path(__file__).resolve().parent / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_path = logs_dir / f"yt-dlp-gui_{stamp}.log"
            return log_path.open("a", encoding="utf-8")
        except OSError:
            return None

    def _on_close(self) -> None:
        if self._log_file:
            try:
                self._log_file.close()
            except OSError:
                pass
        self.destroy()


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
