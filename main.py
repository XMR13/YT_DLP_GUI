from __future__ import annotations

import threading
from pathlib import Path
from queue import Empty, Queue
from typing import List, Optional, Tuple

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
        self._adapter = YtDlpAdapter(self._enqueue_log)
        self._format_options: List[FormatOption] = []

        self.url_var = ctk.StringVar()
        self.playlist_var = ctk.BooleanVar(value=False)
        self.format_type_var = ctk.StringVar(value="Video + Audio")
        self.resolution_var = ctk.StringVar(value="Best available")
        self.output_dir_var = ctk.StringVar(value=str(Path.cwd()))

        self._build_ui()
        self._poll_events()
        self._check_yt_dlp()

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

        fetch_button = ctk.CTkButton(
            form,
            text="Fetch Formats",
            command=self._on_fetch_formats,
            width=140,
        )
        fetch_button.grid(row=2, column=1, sticky="e", padx=12, pady=(0, 10))
        self.fetch_button = fetch_button

        download_button = ctk.CTkButton(
            form,
            text="Download",
            command=self._on_download,
            width=140,
        )
        download_button.grid(row=2, column=2, sticky="e", padx=12, pady=(0, 10))
        self.download_button = download_button

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

        options.columnconfigure(0, weight=1)
        options.columnconfigure(1, weight=1)
        options.columnconfigure(2, weight=1)

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
            messagebox.showerror("yt-dlp missing", "yt-dlp is not installed or not on PATH.")

    def _choose_output_dir(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self.output_dir_var.set(folder)

    def _on_fetch_formats(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a URL first.")
            return

        self._set_busy(True)
        threading.Thread(
            target=self._fetch_formats_worker,
            args=(url, self.playlist_var.get()),
            daemon=True,
        ).start()

    def _on_download(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a URL first.")
            return

        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            messagebox.showwarning("Missing output", "Please choose an output folder.")
            return

        self._set_busy(True)
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

    def _fetch_formats_worker(self, url: str, playlist_mode: bool) -> None:
        try:
            info = self._adapter.fetch_info(url, playlist_mode)
            options = self._adapter.extract_video_formats(info)
            self._event_queue.put(("formats", options))
            title = info.get("title") or "Selection loaded."
            self._event_queue.put(("log", f"Formats loaded for: {title}"))
        except Exception as exc:  # noqa: BLE001 - UI surface for any failures.
            self._event_queue.put(("error", str(exc)))
        finally:
            self._event_queue.put(("busy", False))

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
            )
            self._event_queue.put(("log", "Download completed."))
        except Exception as exc:  # noqa: BLE001
            self._event_queue.put(("error", str(exc)))
        finally:
            self._event_queue.put(("busy", False))

    def _resolve_format_id(self) -> Optional[str]:
        if self.format_type_var.get() == "Audio only":
            return None

        selected = self.resolution_var.get()
        for option in self._format_options:
            if option.label == selected:
                return option.format_id
        return None

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.fetch_button.configure(state=state)
        self.download_button.configure(state=state)
        if busy:
            self._append_log("Working...")

    def _enqueue_log(self, message: str) -> None:
        self._event_queue.put(("log", message))

    def _append_log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _poll_events(self) -> None:
        try:
            while True:
                event, payload = self._event_queue.get_nowait()
                if event == "formats":
                    self._format_options = list(payload)  # type: ignore[arg-type]
                    values = [opt.label for opt in self._format_options]
                    if values:
                        values.insert(0, "Best available")
                    else:
                        values = ["Best available"]
                    self.resolution_menu.configure(values=values)
                    self.resolution_var.set(values[0])
                elif event == "log":
                    self._append_log(str(payload))
                elif event == "error":
                    self._append_log(f"Error: {payload}")
                    messagebox.showerror("Error", str(payload))
                elif event == "busy":
                    self._set_busy(bool(payload))
        except Empty:
            pass
        self.after(200, self._poll_events)


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
