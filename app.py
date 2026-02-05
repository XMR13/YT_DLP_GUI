from __future__ import annotations

from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from typing import Callable, Dict, List, Optional, Tuple, TYPE_CHECKING
import re
import sys
import os
import shutil
import subprocess
import threading

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from urllib.parse import parse_qs, urlparse

from controllers.download_controller import DownloadController
from controllers.history_store import HistoryEntry, HistoryStore
from controllers.queue_runner import QueueRunner, YtDlpExecutor
from controllers.queue_store import QueueItem, QueueStore
from ui.form_panel import FormPanel
from ui.header import Header
from ui.info_panel import InfoPanel
from ui.options_panel import OptionsPanel
from ui.playlist_form_panel import PlaylistFormPanel
from ui.status_panel import StatusPanel
from ui.sidebar import SidebarNav
from yt_dlp_adapter import FormatOption, PlaylistItem, YtDlpAdapter

if TYPE_CHECKING:
    from ui.playlist_preview import PlaylistPreviewPanel
    from ui.history_page import HistoryPage
    from ui.queue_page import QueuePage


PROGRESS_PERCENT_RE = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")
PROGRESS_SPEED_RE = re.compile(r"\bat\s+([^\s]+)")
PROGRESS_ETA_RE = re.compile(r"\bETA\s+([0-9:]+|Unknown)")


class App(ctk.CTk):
    SCROLL_SPEED = 50
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
        self._queue_store = QueueStore()
        self._queue_runner = QueueRunner(
            self._queue_store,
            YtDlpExecutor(self._adapter),
            self._event_queue,
        )
        self._format_options: List[FormatOption] = []
        self._format_map: Dict[str, FormatOption] = {}
        self._current_info: Dict = {}
        self._current_task: Optional[str] = None
        self._solver_warning_shown = False
        self._auto_fetch_job: Optional[str] = None
        self._expected_formats_request_id: Optional[int] = None
        self._expected_formats_index: Optional[int] = None
        self._formats_request_index: Dict[int, Optional[int]] = {}
        self._formats_pending_options: Dict[int, List[FormatOption]] = {}
        self._formats_pending_info: Dict[int, Dict] = {}
        self._formats_inflight_by_index: Dict[int, int] = {}
        self._info_inflight_by_index: Dict[int, int] = {}
        self._warning_once: set[str] = set()
        self._wheel_remainders: Dict[object, float] = {}
        self._main_scroll_canvas: Optional[tk.Canvas] = None
        self._pending_history: Optional[dict] = None
        self._history_store: Optional[HistoryStore] = None
        self._history_loaded = False
        self._history_page_built = False
        self._queue_page_built = False
        self._queue_items: List[dict] = []
        self._queue_running_id: Optional[str] = None
        self._queue_running_title: Optional[str] = None
        self._progress_detail: Dict[str, Optional[str]] = {"percent": None, "speed": None, "eta": None}
        self._progress_targets: List[Tuple[ctk.CTkProgressBar, ctk.CTkLabel]] = []
        self._playlist_download_count: Optional[int] = None
        self._queue_total_count: Optional[int] = None
        self._queue_done_count: Optional[int] = None
        self._closing = False
        self._build_job: Optional[str] = None
        self._build_queue_job: Optional[str] = None
        self._build_queue: List[Callable[[], None]] = []

        self.url_var = ctk.StringVar()
        self.playlist_url_var = ctk.StringVar()
        self.format_type_var = ctk.StringVar(value="Video + Audio")
        self.resolution_var = ctk.StringVar(value="Best available")
        self.output_dir_var = ctk.StringVar(value=str(Path.cwd()))
        self.cookies_var = ctk.StringVar(value="None")
        self.js_runtime_var = ctk.StringVar(value="Auto")
        self.js_runtime_path_var = ctk.StringVar(value="")
        self.remote_components_var = ctk.StringVar(value="None")
        self._selected_playlist_item: Optional[PlaylistItem] = None
        self._selected_playlist_items: List[PlaylistItem] = []
        self._playlist_item_info_cache: Dict[int, Dict] = {}
        self._playlist_item_formats_cache: Dict[int, List[FormatOption]] = {}
        self._preview_page_size = 20
        self._preview_loaded = 0
        self._preview_total: Optional[int] = None
        self._preview_loading = False
        self.preview_panel: Optional["PlaylistPreviewPanel"] = None

        self._log_file = self._init_log_file()
        self._download_ui_built = False
        self._schedule_build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.format_type_var.trace_add("write", self._on_selection_change)
        self.resolution_var.trace_add("write", self._on_selection_change)
        self._queue_runner.load()

    def _schedule_build_ui(self) -> None:
        if self._build_job:
            self.after_cancel(self._build_job)
        self._build_job = self.after(0, self._build_ui)

    def _build_ui(self) -> None:
        self._build_job = None
        if self._closing or not self.winfo_exists():
            return
        header = Header(self)
        header.pack(fill="x", padx=20, pady=(20, 10))
        self._sync_root_bg(header.cget("fg_color"))

        self._body = ctk.CTkFrame(self, corner_radius=18)
        self._body.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self._main = ctk.CTkFrame(self._body, corner_radius=0, fg_color="transparent")
        self._main.pack(fill="both", expand=True)
        self._main.grid_rowconfigure(0, weight=1)
        self._main.grid_columnconfigure(1, weight=1)

        self.sidebar = SidebarNav(self._main, on_select=self._on_nav_select)
        self.sidebar.grid(row=0, column=0, sticky="nsw", padx=(12, 0), pady=12)

        self._pages_container = ctk.CTkFrame(self._main, corner_radius=0, fg_color="transparent")
        self._pages_container.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        self._pages_container.grid_rowconfigure(0, weight=1)
        self._pages_container.grid_columnconfigure(0, weight=1)

        self._download_page = ctk.CTkFrame(self._pages_container, corner_radius=0, fg_color="transparent")
        self._download_page.grid(row=0, column=0, sticky="nsew")
        self._download_page.grid_rowconfigure(0, weight=1)
        self._download_page.grid_columnconfigure(0, weight=1)

        self._history_host = ctk.CTkFrame(self._pages_container, corner_radius=0, fg_color="transparent")
        self._history_host.grid(row=0, column=0, sticky="nsew")
        self._history_page: Optional[HistoryPage] = None

        self._queue_host = ctk.CTkFrame(self._pages_container, corner_radius=0, fg_color="transparent")
        self._queue_host.grid(row=0, column=0, sticky="nsew")
        self._queue_page: Optional[QueuePage] = None

        self._show_page("download")

        self._download_placeholder = ctk.CTkLabel(
            self._download_page,
            text="Loading…",
            font=ctk.CTkFont("Segoe UI", 14),
        )
        self._download_placeholder.pack(expand=True, pady=40)

        self.after_idle(self._build_download_content)

    def _build_download_content(self) -> None:
        if self._closing or not self.winfo_exists():
            return
        if self._download_ui_built:
            return
        self._download_ui_built = True
        if getattr(self, "_download_placeholder", None):
            try:
                self._download_placeholder.destroy()
            except Exception:
                pass

        self._content = ctk.CTkScrollableFrame(self._download_page, corner_radius=0, fg_color="transparent")
        self._content.pack(fill="both", expand=True)
        self._content.grid_columnconfigure(0, weight=1)
        self._main_scroll_canvas = getattr(self._content, "_parent_canvas", None)

        self.tabview = ctk.CTkTabview(self._content)
        self.tabview.grid(row=0, column=0, sticky="ew", padx=18, pady=18)

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

        self._set_controls_state("disabled")
        self._build_queue = [
            lambda: self._build_options_panel(),
            lambda: self._build_info_panel(),
            lambda: self._build_preview_panel(playlist_tab),
            lambda: self._build_status_panel(),
            lambda: self._finish_download_build(),
        ]
        self._run_build_queue()

    def _run_build_queue(self) -> None:
        if self._closing or not self.winfo_exists():
            return
        if not self._build_queue:
            self._build_queue_job = None
            return
        step = self._build_queue.pop(0)
        step()
        if self._build_queue:
            self._build_queue_job = self.after_idle(self._run_build_queue)

    def _build_options_panel(self) -> None:
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
        self.options_panel.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 18))

    def _build_info_panel(self) -> None:
        self.info_panel = InfoPanel(self._content)
        self.info_panel.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 18))

    def _build_preview_panel(self, playlist_tab: ctk.CTkBaseClass) -> None:
        if self.preview_panel is not None:
            return
        from ui.playlist_preview import PlaylistPreviewPanel

        self.preview_panel = PlaylistPreviewPanel(
            playlist_tab,
            on_select=self._on_playlist_selection_changed,
            on_load_more=self._on_load_more_preview,
        )
        self.preview_panel.pack(fill="x", padx=18, pady=(0, 18))
        self.preview_panel.set_items([])
        self.preview_panel.set_load_more_state(False, "Load more")
        preview_canvas = self.preview_panel.get_scroll_canvas()
        if preview_canvas:
            try:
                preview_canvas.configure(yscrollincrement=1)
            except Exception:
                pass

    def _build_status_panel(self) -> None:
        self.status_panel = StatusPanel(
            self._content,
            min_height=self.STATUS_MIN_HEIGHT,
            max_height=self.STATUS_MAX_HEIGHT,
        )
        self.status_panel.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self._content.grid_rowconfigure(3, weight=1)
        self._update_queue_summary(self._queue_items)

    def _finish_download_build(self) -> None:
        self._append_log("Ready.")
        self._progress_targets = [
            (self.form_panel.progress, self.form_panel.progress_label),
            (self.playlist_form_panel.progress, self.playlist_form_panel.progress_label),
        ]
        self._add_queue_progress_target()
        self._set_controls_state("normal")
        self._set_playlist_selection_state(False, False)
        self._bind_global_scroll_events()
        # Keep startup light: avoid extra redraw hooks on window state changes.
        self._poll_events()
        self._check_yt_dlp()

    def _on_nav_select(self, key: str) -> None:
        self._show_page(key)

    def _show_page(self, key: str) -> None:
        if key == "history":
            self._ensure_history_page()
            self._history_host.tkraise()
            if not self._history_loaded:
                self.after_idle(self._refresh_history)
        elif key == "queue":
            self._ensure_queue_page()
            self._queue_host.tkraise()
            self.after_idle(self._refresh_queue)
        else:
            self._download_page.tkraise()
            key = "download"
        self.sidebar.set_active(key)

    def _bind_global_scroll_events(self) -> None:
        def on_mousewheel(event: object) -> str:
            delta = 0.0
            wheel_delta = int(getattr(event, "delta", 0))
            if wheel_delta:
                delta = (-wheel_delta / 120.0) * self.SCROLL_SPEED
            elif getattr(event, "num", None) == 4:
                delta = -float(self.SCROLL_SPEED)
            elif getattr(event, "num", None) == 5:
                delta = float(self.SCROLL_SPEED)
            if not delta:
                return ""
            widget = self.winfo_containing(event.x_root, event.y_root)
            canvas = self._resolve_scroll_canvas(widget)
            if canvas is None:
                return ""
            remainder = self._wheel_remainders.get(canvas, 0.0) + delta
            step = int(remainder)
            if step != 0:
                try:
                    canvas.yview_scroll(step, "units")
                except Exception:
                    return ""
                remainder -= step
            self._wheel_remainders[canvas] = remainder
            if self.preview_panel and canvas == self.preview_panel.get_scroll_canvas():
                self.preview_panel.on_canvas_scroll()
            if self._queue_page and canvas == self._queue_page.get_scroll_canvas():
                self._queue_page.on_canvas_scroll()
            return "break"

        self.bind_all("<MouseWheel>", on_mousewheel)
        self.bind_all("<Button-4>", on_mousewheel)
        self.bind_all("<Button-5>", on_mousewheel)

    def _resolve_scroll_canvas(self, widget: Optional[ctk.CTkBaseClass]) -> Optional[object]:
        if widget and self.preview_panel:
            preview_frame = self.preview_panel.get_scroll_frame()
            if self._is_descendant(widget, preview_frame):
                return self.preview_panel.get_scroll_canvas()
        if widget and self._history_page:
            history_frame = self._history_page.get_scroll_frame()
            if self._is_descendant(widget, history_frame):
                return self._history_page.get_scroll_canvas()
        if widget and self._queue_page:
            queue_frame = self._queue_page.get_scroll_frame()
            if self._is_descendant(widget, queue_frame):
                return self._queue_page.get_scroll_canvas()
        return self._main_scroll_canvas

    @staticmethod
    def _is_descendant(widget: ctk.CTkBaseClass, ancestor: ctk.CTkBaseClass) -> bool:
        current: Optional[ctk.CTkBaseClass] = widget
        while current:
            if current == ancestor:
                return True
            parent = current.winfo_parent()
            if not parent:
                return False
            try:
                current = current.nametowidget(parent)
            except Exception:
                return False
        return False



    @staticmethod
    def _resolve_color(color: object) -> object:
        if isinstance(color, (tuple, list)) and len(color) >= 2:
            mode = ctk.get_appearance_mode()
            return color[0] if mode == "Light" else color[1]
        return color

    def _sync_root_bg(self, color: object) -> None:
        try:
            self.configure(fg_color=color)
        except Exception:
            pass
        try:
            self.configure(bg=self._resolve_color(color))
        except Exception:
            pass


    def _check_yt_dlp(self) -> None:
        def worker() -> None:
            available = self._adapter.check_available()
            if not available:
                self.after(0, self._handle_missing_yt_dlp)
        threading.Thread(target=worker, daemon=True).start()

    def _handle_missing_yt_dlp(self) -> None:
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
        self._set_playlist_selection_state(
            state == "normal" and bool(self._selected_playlist_items),
            state == "normal" and self._selected_playlist_item is not None,
        )

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
        self._expected_formats_index = None
        request_id = self._controller.fetch_formats(
            url=url,
            playlist_mode=False,
            playlist_items=None,
            cookies=self._normalize_cookies(),
            js_runtime=self._normalize_js_runtime(),
            js_runtime_path=self._normalize_runtime_path(),
            remote_components=self._normalize_remote_components(),
        )
        self._expected_formats_request_id = request_id
        self._formats_request_index[request_id] = None

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

        item = QueueItem.create(
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
            title=self._current_info.get("title") if self._current_info else None,
        )
        self._playlist_download_count = None
        self._enqueue_queue_items([item])

    def _on_fetch_playlist(self) -> None:
        url = self.playlist_url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a playlist URL first.")
            return

        self._selected_playlist_item = None
        self._selected_playlist_items = []
        self._playlist_item_info_cache.clear()
        self._playlist_item_formats_cache.clear()
        self._info_inflight_by_index.clear()
        self._expected_formats_request_id = None
        self._expected_formats_index = None
        self._formats_request_index.clear()
        self._formats_pending_options.clear()
        self._formats_pending_info.clear()
        self._formats_inflight_by_index.clear()
        if self._auto_fetch_job:
            try:
                self.after_cancel(self._auto_fetch_job)
            except Exception:
                pass
            self._auto_fetch_job = None
        self._set_playlist_selection_state(False, False)
        self.preview_panel.set_items([])
        self._preview_page_size = 20
        self._preview_loaded = 0
        self._preview_total: Optional[int] = None
        self._preview_loading = True
        self.preview_panel.set_load_more_state(False, "Loading...")
        self._controller.fetch_preview(
            url=url,
            cookies=self._normalize_cookies(),
            js_runtime=self._normalize_js_runtime(),
            js_runtime_path=self._normalize_runtime_path(),
            remote_components=self._normalize_remote_components(),
            start=1,
            limit=self._preview_page_size,
            append=False,
        )

    def _on_fetch_selected_formats(self) -> None:
        if not self._selected_playlist_item:
            messagebox.showwarning("No selection", "Please select a playlist item first.")
            return
        self._start_playlist_item_fetch(self._selected_playlist_item.index, emit_busy=True)

    def _on_download_selected(self) -> None:
        if not self._selected_playlist_items:
            messagebox.showwarning("No selection", "Please select at least one playlist item.")
            return

        url = self.playlist_url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a playlist URL first.")
            return

        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            messagebox.showwarning("Missing output", "Please choose an output folder.")
            return

        selections = {item.index: item for item in self._selected_playlist_items}
        ordered = [selections[idx] for idx in sorted(selections)]
        items: List[QueueItem] = []
        for selection in ordered:
            items.append(
                QueueItem.create(
                    url=url,
                    output_dir=output_dir,
                    format_id=self._resolve_format_id(),
                    audio_only=self.format_type_var.get() == "Audio only",
                    playlist_mode=True,
                    playlist_items=str(selection.index),
                    cookies=self._normalize_cookies(),
                    js_runtime=self._normalize_js_runtime(),
                    js_runtime_path=self._normalize_runtime_path(),
                    remote_components=self._normalize_remote_components(),
                    title=selection.title,
                )
            )
        self._playlist_download_count = len(items)
        self._enqueue_queue_items(items, dedupe=False)

    def _on_download_playlist(self) -> None:
        url = self.playlist_url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a playlist URL first.")
            return

        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            messagebox.showwarning("Missing output", "Please choose an output folder.")
            return

        item = QueueItem.create(
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
            title=self._resolve_playlist_history_title(full_playlist=True),
        )
        if isinstance(self._preview_total, int) and self._preview_total > 0:
            self._playlist_download_count = self._preview_total
        else:
            self._playlist_download_count = None
        self._enqueue_queue_items([item])

    def _on_cancel(self) -> None:
        if self._current_task not in ("download", "download_item", "download_playlist"):
            return
        self._queue_runner.cancel_current()

    def _enqueue_queue_items(self, items: List[QueueItem], *, dedupe: bool = True) -> None:
        if not items:
            return
        before = len(self._queue_store.load())
        for item in items:
            self._queue_runner.enqueue(item, dedupe=dedupe)
        after = len(self._queue_store.load())
        added = max(0, after - before)
        if added <= 0:
            self._append_log("Already queued.")
        elif added == 1:
            self._append_log("Queued 1 item.")
        else:
            self._append_log(f"Queued {added} items.")
        self._queue_items = [item.to_dict() for item in self._queue_store.load()]
        self._refresh_queue()
        self._queue_runner.start()

    def _refresh_queue(self) -> None:
        if not self._queue_page:
            return
        items = self._queue_items or [item.to_dict() for item in self._queue_store.load()]
        self._queue_page.set_items(items)
        self._update_queue_summary(items)

    def _on_queue_start(self) -> None:
        self._queue_runner.start()
        self._update_queue_summary(self._queue_items)

    def _on_queue_stop(self) -> None:
        self._queue_runner.stop_after_current()
        self._update_queue_summary(self._queue_items)

    def _on_queue_cancel(self) -> None:
        was_running = self._queue_runner.is_running_requested()
        self._append_log("Queue: cancel requested for current item.")
        self._queue_runner.cancel_current()
        if was_running:
            self._append_log("Queue: moving to next queued item.")
            self._queue_runner.start()

    def _on_queue_clear(self) -> None:
        if any(item.get("status") == "running" for item in self._queue_items):
            messagebox.showwarning("Queue running", "Stop or cancel the current item before clearing.")
            return
        self._queue_runner.clear()
        self._queue_items = []
        self._refresh_queue()

    def _on_queue_remove(self, item_id: str) -> None:
        if not item_id:
            return
        for item in self._queue_items:
            if item.get("id") == item_id and item.get("status") == "running":
                messagebox.showwarning("Item running", "Stop or cancel the current item first.")
                return
        self._queue_runner.remove(item_id)
        self._queue_items = [item for item in self._queue_items if item.get("id") != item_id]
        self._refresh_queue()

    def _on_queue_remove_selected(self, item_ids: List[str]) -> None:
        if not item_ids:
            return
        running_ids = {item.get("id") for item in self._queue_items if item.get("status") == "running"}
        remove_ids = [item_id for item_id in item_ids if item_id and item_id not in running_ids]
        if not remove_ids:
            messagebox.showwarning("Item running", "Stop or cancel the current item first.")
            return
        if len(remove_ids) != len(item_ids):
            messagebox.showwarning("Item running", "Running items were skipped.")
        for item_id in remove_ids:
            self._queue_runner.remove(item_id)
        self._queue_items = [item for item in self._queue_items if item.get("id") not in remove_ids]
        self._refresh_queue()

    def _on_queue_retry(self, item_id: str) -> None:
        if not item_id:
            return
        self._queue_runner.retry(item_id)
        self._queue_runner.start()
        self._update_queue_summary(self._queue_items)

    def _on_queue_retry_selected(self, item_ids: List[str]) -> None:
        if not item_ids:
            return
        failed_ids = {
            item.get("id")
            for item in self._queue_items
            if item.get("status") in ("failed", "cancelled")
        }
        retry_ids = [item_id for item_id in item_ids if item_id in failed_ids]
        if not retry_ids:
            messagebox.showinfo("Nothing to retry", "Select failed or cancelled items to retry.")
            return
        for item_id in retry_ids:
            self._queue_runner.retry(item_id)
        self._queue_runner.start()
        self._update_queue_summary(self._queue_items)

    def _on_queue_clear_completed(self) -> None:
        self._queue_runner.clear_completed()

    def _on_queue_clear_failed(self) -> None:
        self._queue_items = [item.to_dict() for item in self._queue_runner.clear_failed()]
        self._refresh_queue()

    def _on_queue_move_up(self, item_id: str) -> None:
        self._queue_items = [item.to_dict() for item in self._queue_runner.move(item_id, -1)]
        self._refresh_queue()

    def _on_queue_move_top(self, item_id: str) -> None:
        self._queue_items = [item.to_dict() for item in self._queue_runner.move_to_top(item_id)]
        self._refresh_queue()

    def _on_queue_move_down(self, item_id: str) -> None:
        self._queue_items = [item.to_dict() for item in self._queue_runner.move(item_id, 1)]
        self._refresh_queue()

    def _on_queue_move_bottom(self, item_id: str) -> None:
        self._queue_items = [item.to_dict() for item in self._queue_runner.move_to_bottom(item_id)]
        self._refresh_queue()

    def _on_queue_move_selected_top(self, item_ids: List[str]) -> None:
        if not item_ids:
            return
        self._queue_items = [item.to_dict() for item in self._queue_runner.move_many_to_top(item_ids)]
        self._refresh_queue()

    def _on_queue_move_selected_bottom(self, item_ids: List[str]) -> None:
        if not item_ids:
            return
        self._queue_items = [item.to_dict() for item in self._queue_runner.move_many_to_bottom(item_ids)]
        self._refresh_queue()

    def _on_queue_move_to_index(self, item_id: str, target_queued_index: int) -> None:
        self._queue_items = [
            item.to_dict()
            for item in self._queue_runner.move_to_queued_index(item_id, target_queued_index)
        ]
        self._refresh_queue()

    def _update_queue_summary(self, items: List[dict]) -> None:
        total = len(items)
        counts = {"queued": 0, "running": 0, "completed": 0, "failed": 0, "cancelled": 0}
        running_item = None
        for item in items:
            status = str(item.get("status") or "queued").lower()
            if status in counts:
                counts[status] += 1
            if status == "running" and running_item is None:
                running_item = item
        run_requested = self._queue_runner.is_running_requested()
        running = counts["running"]
        queued = counts["queued"]
        if running:
            state_label = "Running" if run_requested else "Stopping after current"
        elif run_requested:
            state_label = "Waiting to start" if queued else "Idle (auto-start on)"
        else:
            state_label = "Stopped"
        parts: List[str] = []
        for label, key in (
            ("queued", "queued"),
            ("running", "running"),
            ("failed", "failed"),
            ("cancelled", "cancelled"),
        ):
            count = counts[key]
            if count:
                parts.append(f"{label} {count}")
        if total == 0:
            summary = f"Queue: empty • State: {state_label}"
        else:
            summary = f"Queue: {total}"
            if parts:
                summary = f"{summary} • " + " • ".join(parts)
            summary = f"{summary} • State: {state_label}"
        running_id = str(running_item.get("id") or "") if running_item else None
        if running_id != self._queue_running_id:
            self._queue_running_id = running_id
            self._progress_detail = {"percent": None, "speed": None, "eta": None}
        if running_item:
            title = str(running_item.get("title") or running_item.get("url") or "").strip()
            if len(title) > 64:
                title = title[:61] + "..."
            self._queue_running_title = title or None
        else:
            self._queue_running_title = None
        if total:
            self._queue_total_count = total
            self._queue_done_count = total - counts["queued"] - counts["running"]
        else:
            self._queue_total_count = None
            self._queue_done_count = None
        if not hasattr(self, "status_panel") or self.status_panel is None:
            return
        self.status_panel.set_queue_summary(summary)
        self._update_status_activity()
        self._apply_progress_label_overrides(self._progress_targets[0][1].cget("text") if self._progress_targets else "Idle")

    def _prepare_history_context(
        self,
        *,
        url: str,
        title: Optional[str],
        output_dir: str,
        mode: str,
    ) -> None:
        resolved_title = (title or "").strip() or url
        self._pending_history = {
            "url": url,
            "title": resolved_title,
            "output_dir": output_dir,
            "mode": mode,
        }

    def _resolve_playlist_history_title(self, full_playlist: bool = False) -> str:
        if full_playlist:
            return "Playlist download"
        if len(self._selected_playlist_items) == 1:
            return self._selected_playlist_items[0].title
        count = len(self._selected_playlist_items)
        return f"{count} playlist items"

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
        if choice.lower() != "auto":
            return choice
        # Auto: prefer node, then deno, then bun if installed.
        for candidate in ("node", "deno", "bun"):
            if shutil.which(candidate):
                return candidate
        return None

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
            list_values = query.get("list") or []
            if not list_values:
                return False
            list_id = str(list_values[0])
            # YouTube mixes use list ids like RD..., treat them as single videos by default.
            if list_id.startswith(("RD", "RDCM", "RDMM", "RDUA", "RDGMEM")):
                return False
            return True
        except ValueError:
            return False

    def _on_selection_change(self, *_args: object) -> None:
        self._update_info_display()
        self._refresh_cached_playlist_row_sizes()

    def _on_playlist_selection_changed(
        self,
        active_item: Optional[PlaylistItem],
        selected_items: List[PlaylistItem],
    ) -> None:
        self._selected_playlist_item = active_item
        self._selected_playlist_items = selected_items
        self._set_playlist_selection_state(bool(selected_items), active_item is not None)
        if active_item:
            index = active_item.index
            self._current_info = {"title": active_item.title, "duration": active_item.duration}
            cached_info = self._playlist_item_info_cache.get(index)
            if cached_info:
                self._apply_playlist_item_info(index, cached_info, update_current=True)
            else:
                self._update_info_display()
                url = self.playlist_url_var.get().strip()
                if url and index not in self._info_inflight_by_index:
                    request_id = self._controller.fetch_item_info(
                        url=url,
                        playlist_mode=True,
                        playlist_items=str(index),
                        cookies=self._normalize_cookies(),
                        js_runtime=self._normalize_js_runtime(),
                        js_runtime_path=self._normalize_runtime_path(),
                        remote_components=self._normalize_remote_components(),
                        index=index,
                    )
                    self._info_inflight_by_index[index] = request_id
            cached_formats = self._playlist_item_formats_cache.get(index)
            if cached_formats:
                self._apply_formats(cached_formats)
                if cached_info:
                    self._update_playlist_row_size(index, cached_info, cached_formats)
            else:
                self._schedule_auto_fetch_selected(index)
        else:
            self._current_info = {}
            if self._auto_fetch_job:
                try:
                    self.after_cancel(self._auto_fetch_job)
                except Exception:
                    pass
                self._auto_fetch_job = None
            self._update_info_display()

    def _on_load_more_preview(self) -> None:
        if self._preview_loading:
            return
        if self._preview_total is not None and self._preview_loaded >= self._preview_total:
            self.preview_panel.set_load_more_state(False, "All loaded")
            return
        url = self.playlist_url_var.get().strip()
        if not url:
            return
        self._preview_loading = True
        self.preview_panel.set_load_more_state(False, "Loading...")
        start = self._preview_loaded + 1
        self._controller.fetch_preview(
            url=url,
            cookies=self._normalize_cookies(),
            js_runtime=self._normalize_js_runtime(),
            js_runtime_path=self._normalize_runtime_path(),
            remote_components=self._normalize_remote_components(),
            start=start,
            limit=self._preview_page_size,
            append=True,
        )

    def _get_selected_playlist_items_arg(self) -> Optional[str]:
        if not self._selected_playlist_items:
            return None
        indices = sorted({item.index for item in self._selected_playlist_items})
        return ",".join(str(index) for index in indices)

    def _apply_formats(self, options: List[FormatOption]) -> None:
        current_selection = self.resolution_var.get()
        self._format_options = list(options)
        self._format_map = {opt.label: opt for opt in self._format_options}
        values = [opt.label for opt in self._format_options]
        if values:
            values.insert(0, "Best available")
        else:
            values = ["Best available"]
        self.options_panel.resolution_menu.configure(values=values)
        selected_value = current_selection if current_selection in values else values[0]
        if self.resolution_var.get() != selected_value:
            self.resolution_var.set(selected_value)
        else:
            self._update_info_display()

    def _set_playlist_selection_state(self, has_selection: bool, has_active: bool) -> None:
        fetch_state = "normal" if has_active else "disabled"
        download_state = "normal" if has_selection else "disabled"
        self.playlist_form_panel.fetch_selected_button.configure(state=fetch_state)
        self.playlist_form_panel.download_selected_button.configure(state=download_state)

    def _set_busy(self, busy: bool, task: Optional[str] = None) -> None:
        block_ui = bool(busy and task == "fetch")
        state = "disabled" if block_ui else "normal"
        self.form_panel.fetch_button.configure(state=state)
        self.form_panel.download_button.configure(state=state)
        self.form_panel.diag_button.configure(state=state)
        self.playlist_form_panel.fetch_button.configure(state=state)
        self.playlist_form_panel.download_playlist_button.configure(state=state)
        self.playlist_form_panel.diag_button.configure(state=state)
        self._set_playlist_selection_state(
            not block_ui and bool(self._selected_playlist_items),
            not block_ui and self._selected_playlist_item is not None,
        )
        self._current_task = task if busy else None
        cancel_state = "normal" if busy and task in ("download", "download_item", "download_playlist") else "disabled"
        self.form_panel.cancel_button.configure(state=cancel_state)
        self.playlist_form_panel.cancel_button.configure(state=cancel_state)
        if busy and task == "fetch":
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
        self._maybe_update_progress_detail(message)
        if self._log_file:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._log_file.write(f"[{timestamp}] {message}\n")
            self._log_file.flush()

    def _handle_known_error(self, message: str) -> bool:
        lowered = message.lower()
        if "sign in to confirm you\u2019re not a bot" in lowered or "sign in to confirm you're not a bot" in lowered:
            self._append_log(f"Error: {message}")
            if "youtube_auth" not in self._warning_once:
                self._warning_once.add("youtube_auth")
                cookies_choice = self.cookies_var.get().strip()
                if cookies_choice.lower() == "none":
                    hint = (
                        "YouTube requires a logged-in browser. Choose a browser in "
                        "Cookies (browser), close it fully, then retry."
                    )
                else:
                    hint = (
                        f"YouTube requires a logged-in session. Make sure you're signed "
                        f"in on {cookies_choice}, close the browser, then retry."
                    )
                self._append_log(hint)
                messagebox.showwarning("YouTube login required", hint)
            return True
        return False

    def _maybe_update_progress_detail(self, message: str) -> None:
        if "[download]" not in message:
            return
        updated = False
        match = PROGRESS_PERCENT_RE.search(message)
        if match:
            percent_value = float(match.group(1))
            percent = f"{int(percent_value)}%"
            if percent != self._progress_detail.get("percent"):
                self._progress_detail["percent"] = percent
                updated = True
            self._update_progress(percent_value / 100.0)
        match = PROGRESS_SPEED_RE.search(message)
        if match:
            speed = match.group(1)
            if speed != self._progress_detail.get("speed"):
                self._progress_detail["speed"] = speed
                updated = True
        match = PROGRESS_ETA_RE.search(message)
        if match:
            eta = match.group(1)
            if eta != self._progress_detail.get("eta"):
                self._progress_detail["eta"] = eta
                updated = True
        if updated:
            self._update_status_activity()

    def _update_status_activity(self) -> None:
        title = self._queue_running_title
        percent = self._progress_detail.get("percent")
        speed = self._progress_detail.get("speed")
        eta = self._progress_detail.get("eta")
        parts = [part for part in (percent, speed, f"ETA {eta}" if eta else None) if part]
        detail = " • ".join(parts)
        if title:
            label = f"Now: {title}"
            if detail:
                label = f"{label} — {detail}"
        elif detail:
            label = f"Now: {detail}"
        else:
            label = "Now: Idle"
        self.status_panel.set_activity(label)

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
        self._apply_progress_label_overrides(label)

    def _apply_progress_label_overrides(self, base_label: str) -> None:
        if self._queue_page:
            label = base_label
            if self._queue_total_count:
                done = self._queue_done_count or 0
                label = f"{base_label} • {done}/{self._queue_total_count} items"
            self._queue_page.progress_label.configure(text=label)
        if self.playlist_form_panel:
            label = base_label
            if self._playlist_download_count:
                suffix = "item" if self._playlist_download_count == 1 else "items"
                label = f"{base_label} • {self._playlist_download_count} {suffix}"
            self.playlist_form_panel.progress_label.configure(text=label)

    def _update_info_display(self) -> None:
        info = self._current_info or {}
        title = info.get("title") or "—"
        uploader = self._resolve_uploader(info)
        duration = self._format_duration(info.get("duration"))
        selected = self.resolution_var.get()
        option = self._format_map.get(selected)
        if selected == "Best available" and self._format_options:
            option = self._format_options[0]

        if self.format_type_var.get() == "Audio only":
            resolution = "Audio only"
            fmt = "bestaudio"
            size_bytes = self._adapter.resolve_audio_only_size_bytes(info)
            size = self._format_size(size_bytes)
        else:
            if option:
                resolution = f"{option.height}p" if option.height else "Unknown"
                if option.fps:
                    if isinstance(option.fps, float):
                        fps_text = int(option.fps) if option.fps.is_integer() else option.fps
                    else:
                        fps_text = option.fps
                    resolution = f"{resolution} @ {fps_text}fps"
                fmt = option.ext or "Unknown"
                size_bytes = self._adapter.resolve_download_size_bytes(info, option)
                size = self._format_size(size_bytes)
            else:
                resolution = "Best available"
                fmt = "Auto"
                size = "Unknown"

        self.info_panel.update_values(
            {
                "title": title,
                "uploader": uploader,
                "duration": duration,
                "resolution": resolution,
                "format": fmt,
                "size": size,
            }
        )
        if self._selected_playlist_item:
            self.preview_panel.update_item_size(self._selected_playlist_item.index, size)

    def _schedule_auto_fetch_selected(self, index: int) -> None:
        if self._auto_fetch_job:
            self.after_cancel(self._auto_fetch_job)
        self._auto_fetch_job = self.after(
            self.PLAYLIST_AUTO_FETCH_DELAY_MS,
            lambda: self._auto_fetch_selected_formats(index),
        )

    def _auto_fetch_selected_formats(self, index: int) -> None:
        self._auto_fetch_job = None
        if not self._selected_playlist_item or self._selected_playlist_item.index != index:
            return
        if index in self._playlist_item_formats_cache:
            cached_formats = self._playlist_item_formats_cache[index]
            self._apply_formats(cached_formats)
            cached_info = self._playlist_item_info_cache.get(index)
            if cached_info:
                self._update_playlist_row_size(index, cached_info, cached_formats)
            return
        self._start_playlist_item_fetch(index, emit_busy=False)

    def _start_playlist_item_fetch(self, index: int, *, emit_busy: bool) -> None:
        cached_formats = self._playlist_item_formats_cache.get(index)
        if cached_formats:
            self._expected_formats_index = index
            self._expected_formats_request_id = None
            self._apply_formats(cached_formats)
            cached_info = self._playlist_item_info_cache.get(index)
            if cached_info:
                self._update_playlist_row_size(index, cached_info, cached_formats)
            return

        url = self.playlist_url_var.get().strip()
        if not url:
            if emit_busy:
                messagebox.showwarning("Missing URL", "Please enter a playlist URL first.")
            return

        inflight_request = self._formats_inflight_by_index.get(index)
        if inflight_request is not None:
            self._expected_formats_request_id = inflight_request
            self._expected_formats_index = index
            if self._selected_playlist_item and self._selected_playlist_item.index == index:
                self.preview_panel.update_item_size(index, "loading...")
            return

        if emit_busy:
            self._set_busy(True, task="fetch")
        if self._selected_playlist_item and self._selected_playlist_item.index == index:
            self.preview_panel.update_item_size(index, "loading...")

        request_id = self._controller.fetch_formats(
            url=url,
            playlist_mode=True,
            playlist_items=str(index),
            cookies=self._normalize_cookies(),
            js_runtime=self._normalize_js_runtime(),
            js_runtime_path=self._normalize_runtime_path(),
            remote_components=self._normalize_remote_components(),
            emit_busy=emit_busy,
        )
        self._expected_formats_index = index
        self._expected_formats_request_id = request_id
        self._formats_request_index[request_id] = index
        self._formats_inflight_by_index[index] = request_id

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

    def _refresh_cached_playlist_row_sizes(self) -> None:
        if not self.preview_panel:
            return
        for index, options in self._playlist_item_formats_cache.items():
            info = self._playlist_item_info_cache.get(index)
            if info:
                self._update_playlist_row_size(index, info, options)

    def _update_playlist_row_size(self, index: int, info: Dict, options: List[FormatOption]) -> None:
        if not self.preview_panel:
            return
        if self.format_type_var.get() == "Audio only":
            size_bytes = self._adapter.resolve_audio_only_size_bytes(info)
        else:
            selected = self.resolution_var.get()
            option = next((opt for opt in options if opt.label == selected), None)
            if selected == "Best available" or option is None:
                option = options[0] if options else None
            size_bytes = self._adapter.resolve_download_size_bytes(info, option)
        self.preview_panel.update_item_size(index, self._format_size(size_bytes))

    def _resolve_formats_request(self, request_id: int) -> None:
        options = self._formats_pending_options.get(request_id)
        info = self._formats_pending_info.get(request_id)
        if options is None or info is None:
            return

        self._formats_pending_options.pop(request_id, None)
        self._formats_pending_info.pop(request_id, None)
        index = self._formats_request_index.pop(request_id, None)

        if isinstance(index, int):
            current = self._formats_inflight_by_index.get(index)
            if current == request_id:
                self._formats_inflight_by_index.pop(index, None)
            self._playlist_item_formats_cache[index] = list(options)
            self._apply_playlist_item_info(index, dict(info), update_current=False)
            self._update_playlist_row_size(index, dict(info), list(options))
            if self._selected_playlist_item and self._selected_playlist_item.index == index:
                self._expected_formats_index = index
                self._expected_formats_request_id = request_id
                self._apply_formats(list(options))
                self._apply_playlist_item_info(index, dict(info), update_current=True)
            return

        if self._expected_formats_request_id is not None and request_id != self._expected_formats_request_id:
            return
        self._apply_formats(list(options))
        self._apply_playlist_item_info(None, dict(info), update_current=True)

    def _clear_formats_request(self, request_id: int) -> None:
        self._formats_pending_options.pop(request_id, None)
        self._formats_pending_info.pop(request_id, None)
        index = self._formats_request_index.pop(request_id, None)
        if isinstance(index, int) and self._formats_inflight_by_index.get(index) == request_id:
            self._formats_inflight_by_index.pop(index, None)


    def _apply_playlist_item_info(self, index: Optional[int], info: Dict, update_current: bool) -> None:
        if index is not None:
            self._playlist_item_info_cache[index] = dict(info)
            duration_value = info.get("duration")
            if isinstance(duration_value, (int, float)):
                if self.preview_panel:
                    self.preview_panel.update_item_duration(index, int(duration_value))
            uploader = self._resolve_uploader(info)
            if uploader != "—" and self.preview_panel:
                self.preview_panel.update_item_uploader(index, uploader)
            thumb_url = self._resolve_thumbnail_url(info)
            if thumb_url and self.preview_panel:
                self.preview_panel.update_item_thumbnail(index, thumb_url)
            cached_formats = self._playlist_item_formats_cache.get(index)
            if cached_formats:
                self._update_playlist_row_size(index, dict(info), cached_formats)
        if update_current:
            self._current_info = dict(info)
            self._update_info_display()

    @staticmethod
    def _resolve_uploader(info: Dict) -> str:
        for key in ("channel", "uploader", "uploader_id", "channel_id"):
            value = info.get(key)
            if isinstance(value, str):
                value = value.strip()
                if value:
                    return value
        return "—"

    @staticmethod
    def _resolve_thumbnail_url(info: Dict) -> Optional[str]:
        for key in ("thumbnail", "thumbnail_url"):
            value = info.get(key)
            if isinstance(value, str):
                value = value.strip()
                if value:
                    return value
        thumbs = info.get("thumbnails")
        if isinstance(thumbs, list) and thumbs:
            last = thumbs[-1]
            if isinstance(last, dict):
                url = last.get("url")
                if isinstance(url, str) and url.strip():
                    return url.strip()
        return None

    def _poll_events(self) -> None:
        processed = 0
        try:
            while processed < 50:
                event, payload = self._event_queue.get_nowait()
                processed +=1
                if event == "download_complete":
                    if isinstance(payload, dict) and isinstance(payload.get("item"), dict):
                        item = payload["item"]
                        output_paths = payload.get("output_paths") if isinstance(payload.get("output_paths"), list) else []
                        self._record_history_from_queue_item(item, "completed", output_paths=output_paths)
                    else:
                        output_paths = payload if isinstance(payload, list) else []
                        self._record_history("completed", output_paths=output_paths)
                elif event == "download_cancelled":
                    if isinstance(payload, dict) and isinstance(payload.get("item"), dict):
                        self._record_history_from_queue_item(payload["item"], "cancelled")
                    else:
                        self._record_history("cancelled")
                elif event == "download_error":
                    if isinstance(payload, dict) and isinstance(payload.get("item"), dict):
                        error = payload.get("error")
                        self._record_history_from_queue_item(payload["item"], "failed", error=str(error) if error else None)
                    else:
                        self._record_history("failed", error=str(payload))
                if event == "formats":
                    request_id: Optional[int] = None
                    options = payload
                    if isinstance(payload, tuple) and len(payload) == 2 and isinstance(payload[0], int):
                        request_id, options = payload
                    if request_id is None:
                        self._apply_formats(list(options))  # type: ignore[arg-type]
                    else:
                        self._formats_pending_options[request_id] = list(options)  # type: ignore[arg-type]
                        self._resolve_formats_request(request_id)
                elif event == "preview":
                    items = payload
                    total_count: Optional[int] = None
                    append = False
                    if isinstance(payload, tuple):
                        if len(payload) == 3:
                            items, total_count, append = payload
                        elif len(payload) == 2:
                            items, total_count = payload
                    if append:
                        self.preview_panel.append_items(list(items), total_count)  # type: ignore[arg-type]
                        self._preview_loaded += len(items)  # type: ignore[arg-type]
                    else:
                        self.preview_panel.set_items(list(items), total_count)  # type: ignore[arg-type]
                        self._preview_loaded = len(items)  # type: ignore[arg-type]
                    self._preview_total = total_count
                    self._preview_loading = False
                    if self._preview_total is not None and self._preview_loaded >= self._preview_total:
                        self.preview_panel.set_load_more_state(False, "All loaded")
                    else:
                        self.preview_panel.set_load_more_state(True, "Load more")
                    if not append:
                        self._selected_playlist_item = None
                        self._selected_playlist_items = []
                        self._expected_formats_request_id = None
                        self._expected_formats_index = None
                        if self._auto_fetch_job:
                            try:
                                self.after_cancel(self._auto_fetch_job)
                            except Exception:
                                pass
                            self._auto_fetch_job = None
                        self._set_playlist_selection_state(False, False)
                        self._current_info = {}
                        self._update_info_display()
                elif event == "info":
                    request_id: Optional[int] = None
                    info = payload
                    if isinstance(payload, tuple) and len(payload) == 2 and isinstance(payload[0], int):
                        request_id, info = payload
                    if request_id is None:
                        self._apply_playlist_item_info(self._expected_formats_index, dict(info), update_current=True)  # type: ignore[arg-type]
                    else:
                        self._formats_pending_info[request_id] = dict(info)  # type: ignore[arg-type]
                        self._resolve_formats_request(request_id)
                elif event == "item_info":
                    index = None
                    info = payload
                    request_id = None
                    if isinstance(payload, tuple) and len(payload) == 3:
                        request_id, index, info = payload
                    if isinstance(index, int) and request_id is not None:
                        inflight = self._info_inflight_by_index.get(index)
                        if inflight is None or inflight != request_id:
                            continue
                        self._info_inflight_by_index.pop(index, None)
                    update_current = bool(
                        self._selected_playlist_item
                        and isinstance(index, int)
                        and self._selected_playlist_item.index == index
                    )
                    self._apply_playlist_item_info(index, dict(info), update_current=update_current)  # type: ignore[arg-type]
                elif event == "formats_error":
                    if isinstance(payload, int):
                        self._clear_formats_request(payload)
                elif event == "log":
                    self._append_log(str(payload))
                elif event == "progress":
                    self._update_progress(float(payload))
                elif event == "queue_updated":
                    if isinstance(payload, list):
                        self._queue_items = list(payload)
                        if self._queue_page:
                            self._queue_page.set_items(self._queue_items)
                        self._update_queue_summary(self._queue_items)
                elif event == "error":
                    message = str(payload)
                    if not self._handle_known_error(message):
                        self._append_log(f"Error: {message}")
                        messagebox.showerror("Error", message)
                    if self._preview_loading:
                        self._preview_loading = False
                        self.preview_panel.set_load_more_state(True, "Load more")
                elif event == "busy":
                    if isinstance(payload, tuple):
                        busy, task = payload
                        self._set_busy(bool(busy), task=str(task) if task else None)
                    else:
                        self._set_busy(bool(payload))
        except Empty:
            pass
        
        #dynamic scheduling
        delay = 20 if self._current_task else 100
        self.after(delay, self._poll_events)

    def _record_history(
        self,
        status: str,
        *,
        output_paths: Optional[List[str]] = None,
        error: Optional[str] = None,
    ) -> None:
        if not self._pending_history:
            return
        self._ensure_history_store()
        entry = HistoryEntry.create(
            status=status,
            title=self._pending_history.get("title", ""),
            url=self._pending_history.get("url", ""),
            output_dir=self._pending_history.get("output_dir", ""),
            output_paths=output_paths,
            error=error,
        )
        if self._history_store:
            self._history_store.append(entry)
        self._pending_history = None
        self._refresh_history()

    def _record_history_from_queue_item(
        self,
        item: dict,
        status: str,
        *,
        output_paths: Optional[List[str]] = None,
        error: Optional[str] = None,
    ) -> None:
        self._ensure_history_store()
        if not self._history_store:
            return
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        output_dir = str(item.get("output_dir") or "").strip()
        entry = HistoryEntry.create(
            status=status,
            title=title or url,
            url=url,
            output_dir=output_dir,
            output_paths=output_paths,
            error=error,
        )
        self._history_store.append(entry)
        self._refresh_history()

    def _refresh_history(self) -> None:
        self._ensure_history_store()
        if not self._history_store or not self._history_page:
            return
        entries = self._history_store.load()
        self._history_page.set_items(entries)
        self._history_loaded = True

    def _on_clear_history(self) -> None:
        self._ensure_history_store()
        if self._history_store:
            self._history_store.clear()
        self._refresh_history()

    def _on_open_history_folder(self, entry: HistoryEntry) -> None:
        if entry.output_dir:
            self._open_path(entry.output_dir)

    def _on_retry_history(self, entry: HistoryEntry) -> None:
        if not entry.url:
            return
        self._show_page("download")
        self.url_var.set(entry.url)
        self._on_download_single()

    def _ensure_history_store(self) -> None:
        if self._history_store is None:
            self._history_store = HistoryStore()

    def _ensure_history_page(self) -> None:
        if self._history_page_built:
            return
        from ui.history_page import HistoryPage

        self._history_page = HistoryPage(
            self._history_host,
            on_clear=self._on_clear_history,
            on_open_folder=self._on_open_history_folder,
            on_retry=self._on_retry_history,
        )
        self._history_page.pack(fill="both", expand=True)
        self._history_page_built = True

    def _ensure_queue_page(self) -> None:
        if self._queue_page_built:
            return
        from ui.queue_page import QueuePage

        self._queue_page = QueuePage(
            self._queue_host,
            on_start=self._on_queue_start,
            on_stop=self._on_queue_stop,
            on_cancel=self._on_queue_cancel,
            on_clear=self._on_queue_clear,
            on_clear_completed=self._on_queue_clear_completed,
            on_clear_failed=self._on_queue_clear_failed,
            on_remove=self._on_queue_remove,
            on_retry=self._on_queue_retry,
            on_bulk_remove=self._on_queue_remove_selected,
            on_bulk_retry=self._on_queue_retry_selected,
            on_bulk_move_top=self._on_queue_move_selected_top,
            on_bulk_move_bottom=self._on_queue_move_selected_bottom,
            on_move_to_index=self._on_queue_move_to_index,
        )
        self._queue_page.pack(fill="both", expand=True)
        self._queue_page_built = True
        self._add_queue_progress_target()

    def _add_queue_progress_target(self) -> None:
        if not self._queue_page:
            return
        target = (self._queue_page.progress, self._queue_page.progress_label)
        if target not in self._progress_targets:
            self._progress_targets.append(target)

    @staticmethod
    def _open_path(path: str) -> None:
        try:
            candidate = Path(path).expanduser()
            if not candidate.is_dir():
                return
            safe_path = str(candidate)
            if sys.platform.startswith("win"):
                os.startfile(safe_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", safe_path], check=False)
            else:
                subprocess.run(["xdg-open", safe_path], check=False)
        except Exception:
            return

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
        self._closing = True
        try:
            self._queue_runner.shutdown()
        except Exception:
            pass
        if self._build_job:
            try:
                self.after_cancel(self._build_job)
            except Exception:
                pass
            self._build_job = None
        if self._build_queue_job:
            try:
                self.after_cancel(self._build_queue_job)
            except Exception:
                pass
            self._build_queue_job = None
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
