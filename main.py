from __future__ import annotations

import threading
from pathlib import Path
from queue import Empty, Queue
from typing import Dict, List, Optional, Tuple

import customtkinter as ctk
from tkinter import filedialog, messagebox

from yt_dlp_adapter import FormatOption, YtDlpAdapter


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("dark-blue")

        self.title("yt-dlp GUI")
        self.geometry("860x520")
        self.minsize(820, 480)

        self._event_queue: Queue[Tuple[str, object]] = Queue()
        self._adapter = YtDlpAdapter(self._enqueue_log, self._enqueue_progress)
        self._format_options: List[FormatOption] = []
        self._format_map: Dict[str, FormatOption] = {}
        self._current_info: Dict = {}
        self._current_task: Optional[str] = None
        self._cancel_requested = False
        self._active_output_dir: Optional[str] = None
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

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, corner_radius=18)
        header.pack(fill="x", padx=20, pady=(20, 10))

        title = ctk.CTkLabel(
            header,
            text="yt-dlp GUI",
            font=ctk.CTkFont("Segoe UI", 26, weight="bold"),
        )
        title.pack(anchor="w", padx=18, pady=(16, 4))

        subtitle = ctk.CTkLabel(
            header,
            text="Simple downloads with format and resolution selection",
            font=ctk.CTkFont("Segoe UI", 13),
        )
        subtitle.pack(anchor="w", padx=18, pady=(0, 16))

        body = ctk.CTkFrame(self, corner_radius=18)
        body.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        form = ctk.CTkFrame(body, corner_radius=12)
        form.pack(fill="x", padx=18, pady=18)

        url_label = ctk.CTkLabel(form, text="Video or Playlist URL")
        url_label.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

        url_entry = ctk.CTkEntry(form, textvariable=self.url_var)
        url_entry.grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 12))

        playlist_check = ctk.CTkCheckBox(
            form,
            text="Playlist URL",
            variable=self.playlist_var,
        )
        playlist_check.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 10))

        fetch_frame = ctk.CTkFrame(form, fg_color="transparent")
        fetch_frame.grid(row=2, column=1, sticky="e", padx=12, pady=(0, 10))

        fetch_button = ctk.CTkButton(
            fetch_frame,
            text="Fetch Formats",
            command=self._on_fetch_formats,
            width=140,
        )
        fetch_button.pack(side="left", padx=(0, 8))
        self.fetch_button = fetch_button

        diag_button = ctk.CTkButton(
            fetch_frame,
            text="Diagnostics",
            command=self._on_diagnostics,
            width=120,
        )
        diag_button.pack(side="left")
        self.diag_button = diag_button

        action_frame = ctk.CTkFrame(form, fg_color="transparent")
        action_frame.grid(row=2, column=2, sticky="e", padx=12, pady=(0, 10))

        download_button = ctk.CTkButton(
            action_frame,
            text="Download",
            command=self._on_download,
            width=140,
        )
        download_button.pack(side="left", padx=(0, 8))
        self.download_button = download_button

        cancel_button = ctk.CTkButton(
            action_frame,
            text="Cancel",
            command=self._on_cancel,
            width=100,
            fg_color="#444444",
            hover_color="#555555",
            state="disabled",
        )
        cancel_button.pack(side="left")
        self.cancel_button = cancel_button

        self.progress = ctk.CTkProgressBar(form, height=10)
        self.progress.grid(row=3, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 6))
        self.progress.set(0)

        self.progress_label = ctk.CTkLabel(form, text="Idle")
        self.progress_label.grid(row=4, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 12))

        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=0)
        form.columnconfigure(2, weight=0)

        options = ctk.CTkFrame(body, corner_radius=12)
        options.pack(fill="x", padx=18, pady=(0, 18))

        format_label = ctk.CTkLabel(options, text="Format")
        format_label.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

        format_menu = ctk.CTkOptionMenu(
            options,
            values=["Video + Audio", "Audio only"],
            variable=self.format_type_var,
        )
        format_menu.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

        resolution_label = ctk.CTkLabel(options, text="Resolution / FPS")
        resolution_label.grid(row=0, column=1, sticky="w", padx=12, pady=(12, 4))

        resolution_menu = ctk.CTkOptionMenu(
            options,
            values=["Best available"],
            variable=self.resolution_var,
        )
        resolution_menu.grid(row=1, column=1, sticky="ew", padx=12, pady=(0, 12))
        self.resolution_menu = resolution_menu

        output_label = ctk.CTkLabel(options, text="Output folder")
        output_label.grid(row=0, column=2, sticky="w", padx=12, pady=(12, 4))

        output_frame = ctk.CTkFrame(options, fg_color="transparent")
        output_frame.grid(row=1, column=2, sticky="ew", padx=12, pady=(0, 12))

        output_entry = ctk.CTkEntry(output_frame, textvariable=self.output_dir_var)
        output_entry.pack(side="left", fill="x", expand=True)

        output_button = ctk.CTkButton(
            output_frame,
            text="Browse",
            command=self._choose_output_dir,
            width=80,
        )
        output_button.pack(side="left", padx=(8, 0))

        cookies_label = ctk.CTkLabel(options, text="Cookies (browser)")
        cookies_label.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 4))

        cookies_menu = ctk.CTkOptionMenu(
            options,
            values=["None", "chrome", "edge", "firefox"],
            variable=self.cookies_var,
        )
        cookies_menu.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))

        runtime_label = ctk.CTkLabel(options, text="JS runtime")
        runtime_label.grid(row=2, column=1, sticky="w", padx=12, pady=(0, 4))

        runtime_menu = ctk.CTkOptionMenu(
            options,
            values=["Auto", "node", "deno", "bun", "quickjs"],
            variable=self.js_runtime_var,
        )
        runtime_menu.grid(row=3, column=1, sticky="ew", padx=12, pady=(0, 12))

        runtime_path_label = ctk.CTkLabel(options, text="Runtime path (optional)")
        runtime_path_label.grid(row=2, column=2, sticky="w", padx=12, pady=(0, 4))

        runtime_path_frame = ctk.CTkFrame(options, fg_color="transparent")
        runtime_path_frame.grid(row=3, column=2, sticky="ew", padx=12, pady=(0, 12))

        runtime_path_entry = ctk.CTkEntry(runtime_path_frame, textvariable=self.js_runtime_path_var)
        runtime_path_entry.pack(side="left", fill="x", expand=True)

        runtime_path_button = ctk.CTkButton(
            runtime_path_frame,
            text="Browse",
            command=self._choose_runtime_path,
            width=80,
        )
        runtime_path_button.pack(side="left", padx=(8, 0))

        components_label = ctk.CTkLabel(options, text="EJS scripts source")
        components_label.grid(row=4, column=0, sticky="w", padx=12, pady=(0, 4))

        components_menu = ctk.CTkOptionMenu(
            options,
            values=["None", "ejs:github", "ejs:npm"],
            variable=self.remote_components_var,
        )
        components_menu.grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 12))

        options.columnconfigure(0, weight=1)
        options.columnconfigure(1, weight=1)
        options.columnconfigure(2, weight=1)

        info_frame = ctk.CTkFrame(body, corner_radius=12)
        info_frame.pack(fill="x", padx=18, pady=(0, 18))

        info_title = ctk.CTkLabel(info_frame, text="Video info")
        info_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 6))

        self.info_values: Dict[str, ctk.CTkLabel] = {}
        info_fields = [
            ("Title", "title"),
            ("Resolution / FPS", "resolution"),
            ("Format", "format"),
            ("Size", "size"),
        ]

        for idx, (label, key) in enumerate(info_fields, start=1):
            name_label = ctk.CTkLabel(info_frame, text=label)
            name_label.grid(row=idx, column=0, sticky="w", padx=12, pady=(0, 6))
            value_label = ctk.CTkLabel(info_frame, text="—")
            value_label.grid(row=idx, column=1, sticky="w", padx=12, pady=(0, 6))
            self.info_values[key] = value_label

        info_frame.columnconfigure(0, weight=0)
        info_frame.columnconfigure(1, weight=1)

        log_frame = ctk.CTkFrame(body, corner_radius=12)
        log_frame.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        log_label = ctk.CTkLabel(log_frame, text="Status")
        log_label.pack(anchor="w", padx=12, pady=(12, 4))

        self.log_box = ctk.CTkTextbox(log_frame, height=160, wrap="word")
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._append_log("Ready.")

    def _check_yt_dlp(self) -> None:
        if not self._adapter.check_available():
            self._append_log("yt-dlp not found. Install it with: pip install yt-dlp")
            self.fetch_button.configure(state="disabled")
            self.download_button.configure(state="disabled")
            self.cancel_button.configure(state="disabled")
            messagebox.showerror("yt-dlp missing", "yt-dlp is not installed or not on PATH.")

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

        self._set_busy(True, task="fetch")
        threading.Thread(
            target=self._fetch_formats_worker,
            args=(url, self.playlist_var.get()),
            daemon=True,
        ).start()

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

    def _on_download(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a URL first.")
            return

        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            messagebox.showwarning("Missing output", "Please choose an output folder.")
            return

        self._cancel_requested = False
        self._active_output_dir = output_dir
        self._set_busy(True, task="download")
        self._event_queue.put(("progress", 0.0))
        threading.Thread(
            target=self._download_worker,
            args=(
                url,
                output_dir,
                self._resolve_format_id(),
                self.format_type_var.get() == "Audio only",
                self.playlist_var.get(),
            ),
            daemon=True,
        ).start()

    def _on_cancel(self) -> None:
        if self._current_task != "download":
            return
        self._cancel_requested = True
        self._adapter.cancel(self._active_output_dir, delete_partials=True)

    def _fetch_formats_worker(self, url: str, playlist_mode: bool) -> None:
        try:
            info = self._adapter.fetch_info(
                url,
                playlist_mode,
                self._normalize_cookies(),
                self._normalize_js_runtime(),
                self._normalize_runtime_path(),
                self._normalize_remote_components(),
            )
            options = self._adapter.extract_video_formats(info)
            self._event_queue.put(("formats", options))
            self._event_queue.put(("info", info))
            title = info.get("title") or "Selection loaded."
            self._event_queue.put(("log", f"Formats loaded for: {title}"))
        except Exception as exc:  # noqa: BLE001 - UI surface for any failures.
            self._event_queue.put(("error", str(exc)))
        finally:
            self._event_queue.put(("busy", (False, None)))

    def _download_worker(
        self,
        url: str,
        output_dir: str,
        format_id: Optional[str],
        audio_only: bool,
        playlist_mode: bool,
    ) -> None:
        try:
            self._adapter.download(
                url=url,
                output_dir=output_dir,
                format_id=format_id,
                audio_only=audio_only,
                playlist_mode=playlist_mode,
                cookies_from_browser=self._normalize_cookies(),
                js_runtime=self._normalize_js_runtime(),
                js_runtime_path=self._normalize_runtime_path(),
                remote_components=self._normalize_remote_components(),
            )
            self._event_queue.put(("log", "Download completed."))
        except Exception as exc:  # noqa: BLE001
            if self._cancel_requested:
                self._event_queue.put(("log", "Download cancelled."))
            else:
                self._event_queue.put(("error", str(exc)))
        finally:
            self._event_queue.put(("busy", (False, None)))

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
        if choice.lower() != "auto":
            return choice
        return self._auto_js_runtime()

    def _normalize_runtime_path(self) -> Optional[str]:
        path = self.js_runtime_path_var.get().strip()
        if self.js_runtime_var.get().strip().lower() == "auto":
            return None
        return path or None

    def _normalize_remote_components(self) -> Optional[str]:
        choice = self.remote_components_var.get().strip()
        return None if choice.lower() == "none" else choice

    def _auto_js_runtime(self) -> Optional[str]:
        for runtime in ("deno", "bun", "node", "quickjs"):
            ok, _ = self._adapter.check_runtime(runtime, None)
            if ok:
                return None if runtime == "deno" else runtime
        return None

    def _on_selection_change(self, *_args: object) -> None:
        self._update_info_display()

    def _set_busy(self, busy: bool, task: Optional[str] = None) -> None:
        state = "disabled" if busy else "normal"
        self.fetch_button.configure(state=state)
        self.diag_button.configure(state=state)
        self.download_button.configure(state=state)
        self._current_task = task if busy else None
        cancel_state = "normal" if busy and task == "download" else "disabled"
        self.cancel_button.configure(state=cancel_state)
        if busy:
            self._append_log("Working...")
        else:
            self._cancel_requested = False
            self._active_output_dir = None
            self._update_progress(0.0)

    def _enqueue_progress(self, value: float) -> None:
        self._event_queue.put(("progress", value))

    def _enqueue_log(self, message: str) -> None:
        self._event_queue.put(("log", message))

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
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _update_progress(self, value: float) -> None:
        value = max(0.0, min(1.0, value))
        self.progress.set(value)
        percent = int(value * 100)
        label = f"{percent}%"
        if value == 0.0:
            label = "Idle"
        elif value >= 1.0:
            label = "Completed"
        self.progress_label.configure(text=label)

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

        self.info_values["title"].configure(text=title)
        self.info_values["resolution"].configure(text=resolution)
        self.info_values["format"].configure(text=fmt)
        self.info_values["size"].configure(text=size)

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
                    self.resolution_menu.configure(values=values)
                    self.resolution_var.set(values[0])
                    self._update_info_display()
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
