from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import threading
from typing import Callable, Dict, List, Optional, Set
import tkinter as tk
from urllib.parse import urlparse

import customtkinter as ctk
from PIL import Image, ImageTk
from urllib.request import urlopen

from yt_dlp_adapter import PlaylistItem


@dataclass
class _RowWidget:
    frame: tk.Frame
    window_id: int
    text_frame: tk.Frame
    title: tk.Label
    meta: tk.Label
    thumb: tk.Label
    bound_index: Optional[int] = None
    thumb_url: Optional[str] = None


class PlaylistPreviewPanel(ctk.CTkFrame):
    ROW_HEIGHT = 86
    ROW_PADDING_Y = 6
    MAX_THUMBNAIL_BYTES = 2 * 1024 * 1024

    def __init__(
        self,
        master: ctk.CTk,
        on_select: Optional[Callable[[Optional[PlaylistItem], List[PlaylistItem]], None]] = None,
        on_load_more: Optional[Callable[[], None]] = None,
        **kwargs: object,
    ) -> None:
        super().__init__(master, corner_radius=12, **kwargs)

        self._row_color = ("#E9E9E9", "#2B2B2B")
        self._selected_color = ("#D6D6D6", "#3A3A3A")
        self._hover_color = ("#E1E1E1", "#343434")
        self._selected_hover_color = ("#CFCFCF", "#464646")

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(12, 6))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        title = ctk.CTkLabel(header, text="Playlist preview (first 20)")
        title.grid(row=0, column=0, sticky="w")

        self._count_label = ctk.CTkLabel(
            header,
            text="",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=12),
        )
        self._count_label.grid(row=0, column=1, sticky="e")

        self._list_container = ctk.CTkFrame(self, corner_radius=8, fg_color=self._get_row_bg())
        self._list_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._list_container.grid_rowconfigure(0, weight=1)
        self._list_container.grid_columnconfigure(0, weight=1)

        self._list_canvas = tk.Canvas(self._list_container, highlightthickness=0, bd=0)
        self._list_canvas.grid(row=0, column=0, sticky="nsew")
        self._list_scrollbar = ctk.CTkScrollbar(
            self._list_container,
            orientation="vertical",
            command=self._on_scrollbar,
        )
        self._list_scrollbar.grid(row=0, column=1, sticky="ns")
        self._list_canvas.configure(yscrollcommand=self._list_scrollbar.set)
        self._list_canvas.bind("<Configure>", self._on_canvas_configure)
        self._apply_canvas_bg()

        self._load_more_button = ctk.CTkButton(
            self,
            text="Load more",
            command=on_load_more or (lambda: None),
            width=140,
        )
        self._load_more_button.pack(pady=(0, 12))

        self._image_cache: Dict[str, ImageTk.PhotoImage] = {}
        self._thumb_loading: Set[str] = set()
        self._placeholder = self._build_placeholder()
        self._on_select = on_select
        self._on_load_more = on_load_more
        self._row_pool: List[_RowWidget] = []
        self._visible_rows: Dict[int, _RowWidget] = {}
        self._items: List[PlaylistItem] = []
        self._item_by_index: Dict[int, PlaylistItem] = {}
        self._selected_indices: Set[int] = set()
        self._selection_order: List[int] = []
        self._hovered_indices: Set[int] = set()
        self._active_index: Optional[int] = None
        self._row_duration: Dict[int, str] = {}
        self._row_size: Dict[int, str] = {}
        self._row_uploader: Dict[int, str] = {}
        self._thumb_override: Dict[int, str] = {}
        self._total_count = 0
        self._empty_label: Optional[ctk.CTkLabel] = None
        self._canvas_configure_job: Optional[str] = None
        self._last_canvas_width: Optional[int] = None
        self._last_canvas_height: Optional[int] = None
        self._pending_canvas_width: Optional[int] = None
        self._pending_canvas_height: Optional[int] = None

    def get_scroll_frame(self) -> tk.Canvas:
        return self._list_canvas

    def get_scroll_canvas(self) -> Optional[object]:
        return self._list_canvas

    def set_items(self, items: List[PlaylistItem], total_count: Optional[int] = None) -> None:
        self._items = list(items)
        self._item_by_index.clear()
        self._selected_indices.clear()
        self._selection_order.clear()
        self._hovered_indices.clear()
        self._active_index = None
        self._row_duration.clear()
        self._row_size.clear()
        self._row_uploader.clear()
        self._thumb_override.clear()
        self._image_cache.clear()
        self._thumb_loading.clear()
        self._total_count = total_count if isinstance(total_count, int) and total_count > 0 else len(items)
        self._update_selected_count()

        for item in items:
            self._item_by_index[item.index] = item
            self._row_duration[item.index] = self._format_duration(item.duration)
            self._row_size[item.index] = self._row_size.get(item.index, "fetch formats")

        self._sync_empty_state()
        self._update_scrollregion()
        self._ensure_row_pool()
        self._notify_selection_changed()

    def append_items(self, items: List[PlaylistItem], total_count: Optional[int] = None) -> None:
        if isinstance(total_count, int) and total_count > 0:
            self._total_count = total_count
        for item in items:
            if item.index in self._item_by_index:
                continue
            self._items.append(item)
            self._item_by_index[item.index] = item
            self._row_duration[item.index] = self._format_duration(item.duration)
            self._row_size[item.index] = self._row_size.get(item.index, "fetch formats")
        self._update_selected_count()
        self._sync_empty_state()
        self._update_scrollregion()
        self._ensure_row_pool()

    def _sync_empty_state(self) -> None:
        if self._items:
            if self._empty_label:
                self._empty_label.destroy()
                self._empty_label = None
            return
        if self._empty_label is None:
            self._empty_label = ctk.CTkLabel(
                self._list_container,
                text="No items to preview.",
                fg_color=self._get_row_bg(),
            )
            self._empty_label.place(relx=0.5, rely=0.5, anchor="center")
        try:
            self._list_canvas.configure(bg=self._get_row_bg())
        except Exception:
            pass

    def _ensure_row_pool(self) -> None:
        height = max(self._list_canvas.winfo_height(), 1)
        visible = max(1, int(height / self.ROW_HEIGHT) + 2)
        while len(self._row_pool) < visible:
            row = self._create_row()
            self._row_pool.append(row)
        self._update_visible_rows()

    def _create_row(self) -> "_RowWidget":
        # Use standard tk.Frame - much faster than CTkFrame
        row_bg = self._get_row_bg()
        row = tk.Frame(self._list_canvas, bg=row_bg)
        window_id = self._list_canvas.create_window(
            0,
            0,
            anchor="nw",
            window=row,
            width=max(self._list_canvas.winfo_width(), 1),
        )

        # Standard tk.Label for thumbnail placeholder
        thumb = tk.Label(row, text="", bg=row_bg, image=self._placeholder)
        thumb.image = self._placeholder
        thumb.pack(side="left", padx=(8, 12), pady=6)

        text_frame = tk.Frame(row, bg=row_bg)
        text_frame.pack(side="left", fill="both", expand=True, pady=6)

        # Standard labels
        title = tk.Label(
            text_frame,
            text="",
            anchor="w",
            justify="left",
            bg=row_bg,
            fg=self._get_title_fg(),
            font=("Arial", 12),
        )
        title.pack(anchor="w")

        meta = tk.Label(
            text_frame,
            text="",
            anchor="w",
            bg=row_bg,
            fg=self._get_meta_fg(),
            font=("Arial", 10),
        )
        meta.pack(anchor="w")

        # Handle selection highlighting manually since tk.Label doesn't have fg_color
        row_widget = _RowWidget(
            frame=row,
            window_id=window_id,
            text_frame=text_frame,
            title=title,
            meta=meta,
            thumb=thumb,
        )

        def make_select_handler(target: _RowWidget):
            return lambda _e: self._handle_row_select(target)

        def make_hover_handler(target: _RowWidget, entering: bool):
            return lambda _e: self._handle_row_hover(target, entering)

        for widget in (row, thumb, title, meta, text_frame):
            widget.bind("<Button-1>", make_select_handler(row_widget))
            widget.bind("<Enter>", make_hover_handler(row_widget, True))
            widget.bind("<Leave>", make_hover_handler(row_widget, False))

        return row_widget

    def _update_scrollregion(self) -> None:
        total_height = max(1, len(self._items) * self.ROW_HEIGHT + self.ROW_PADDING_Y)
        width = self._list_canvas.winfo_width()
        self._list_canvas.configure(scrollregion=(0, 0, width, total_height))

    def _on_canvas_configure(self, _event: object) -> None:
        self._pending_canvas_width = self._list_canvas.winfo_width()
        self._pending_canvas_height = self._list_canvas.winfo_height()
        if self._canvas_configure_job:
            try:
                self.after_cancel(self._canvas_configure_job)
            except Exception:
                pass
        self._canvas_configure_job = self.after_idle(self._apply_canvas_layout)

    def _apply_canvas_layout(self) -> None:
        self._canvas_configure_job = None
        width = max(self._pending_canvas_width or self._list_canvas.winfo_width(), 1)
        height = max(self._pending_canvas_height or self._list_canvas.winfo_height(), 1)
        self._pending_canvas_width = None
        self._pending_canvas_height = None

        width_changed = self._last_canvas_width != width
        height_changed = self._last_canvas_height != height
        self._last_canvas_width = width
        self._last_canvas_height = height

        if width_changed or height_changed:
            self._update_scrollregion()
            for row in self._row_pool:
                self._list_canvas.itemconfigure(row.window_id, width=width)
            self._ensure_row_pool()

    def _on_scrollbar(self, *args: object) -> None:
        self._list_canvas.yview(*args)
        self._update_visible_rows()

    def _update_visible_rows(self) -> None:
        if not self._items:
            for row in self._row_pool:
                self._list_canvas.itemconfigure(row.window_id, state="hidden")
                row.bound_index = None
            return
        self._visible_rows.clear()
        y0 = self._list_canvas.canvasy(0)
        first_index = max(0, int(y0 // self.ROW_HEIGHT))
        for i, row in enumerate(self._row_pool):
            item_pos = first_index + i
            if item_pos >= len(self._items):
                self._list_canvas.itemconfigure(row.window_id, state="hidden")
                row.bound_index = None
                continue
            item = self._items[item_pos]
            row.bound_index = item.index
            self._visible_rows[item.index] = row
            self._render_row(row, item)
            self._list_canvas.coords(
                row.window_id,
                0,
                item_pos * self.ROW_HEIGHT,
            )
            self._list_canvas.itemconfigure(row.window_id, state="normal")

    def set_load_more_state(self, enabled: bool, text: str = "Load more") -> None:
        self._load_more_button.configure(state="normal" if enabled else "disabled", text=text)

    def on_canvas_scroll(self) -> None:
        self._update_visible_rows()

    def _handle_row_select(self, row: _RowWidget) -> None:
        if row.bound_index is None:
            return
        self._toggle_select(row.bound_index)

    def _handle_row_hover(self, row: _RowWidget, entering: bool) -> None:
        if row.bound_index is None:
            return
        self._set_hover(row.bound_index, entering)
    def _toggle_select(self, index: int) -> None:
        if index in self._selected_indices:
            self._selected_indices.remove(index)
            if index in self._selection_order:
                self._selection_order.remove(index)
            if self._active_index == index:
                self._active_index = self._selection_order[-1] if self._selection_order else None
        else:
            self._selected_indices.add(index)
            self._selection_order.append(index)
            self._active_index = index

        self._apply_row_state(index)
        if self._active_index is not None:
            self._apply_row_state(self._active_index)
        self._update_selected_count()
        self._notify_selection_changed()

    def _set_hover(self, index: int, entering: bool) -> None:
        if entering:
            self._hovered_indices.add(index)
        else:
            self._hovered_indices.discard(index)
        self._apply_row_state(index)

    def _apply_row_state(self, index: int) -> None:
        row = self._visible_rows.get(index)
        if not row:
            return
        if index in self._selected_indices:
            bg = self._get_selected_hover_bg() if index in self._hovered_indices else self._get_selected_bg()
        else:
            bg = self._get_hover_bg() if index in self._hovered_indices else self._get_row_bg()
        self._apply_row_colors(row.frame, row.text_frame, row.title, row.meta, row.thumb, bg)

    def _build_placeholder(self) -> ImageTk.PhotoImage:
        color = (40, 40, 40) if ctk.get_appearance_mode() == "Dark" else (220, 220, 220)
        image = Image.new("RGB", (120, 68), color=color)
        return ImageTk.PhotoImage(image)

    def _load_thumbnail_async(self, url: str, row: _RowWidget) -> None:
        if url in self._image_cache:
            try:
                if row.thumb.winfo_exists():
                    row.thumb.configure(image=self._image_cache[url])
                    row.thumb.image = self._image_cache[url]
            except tk.TclError:
                pass
            return
        if url in self._thumb_loading:
            return
        self._thumb_loading.add(url)

        def worker() -> None:
            try:
                if not self._is_safe_thumbnail_url(url):
                    self.after(0, lambda: self._thumb_loading.discard(url))
                    return
                with urlopen(url, timeout=5) as response:
                    content_length = response.headers.get("Content-Length")
                    if content_length and int(content_length) > self.MAX_THUMBNAIL_BYTES:
                        self.after(0, lambda: self._thumb_loading.discard(url))
                        return
                    data = response.read(self.MAX_THUMBNAIL_BYTES + 1)
                    if len(data) > self.MAX_THUMBNAIL_BYTES:
                        self.after(0, lambda: self._thumb_loading.discard(url))
                        return
                image = Image.open(BytesIO(data))
                image = image.convert("RGB")
                image.thumbnail((120, 68), Image.LANCZOS)
                self.after(0, lambda: self._apply_thumbnail(row, image, url))
            except Exception:
                self.after(0, lambda: self._thumb_loading.discard(url))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_thumbnail(self, row: _RowWidget, image: Image.Image, url: str) -> None:
        try:
            if not row.thumb.winfo_exists():
                return
            if row.thumb_url != url:
                return
            photo = ImageTk.PhotoImage(image)
            self._image_cache[url] = photo
            row.thumb.configure(image=photo)
            row.thumb.image = photo
        except tk.TclError:
            pass
        finally:
            self._thumb_loading.discard(url)

    def update_selected_size(self, size_text: str) -> None:
        if self._active_index is None:
            return
        self.update_item_size(self._active_index, size_text)

    def update_item_size(self, index: int, size_text: str) -> None:
        if index not in self._row_duration:
            return
        self._row_size[index] = size_text
        self._render_row_meta(index)

    def update_item_duration(self, index: int, duration_seconds: Optional[int]) -> None:
        if index not in self._row_duration:
            return
        self._row_duration[index] = self._format_duration(duration_seconds)
        self._render_row_meta(index)

    def update_item_uploader(self, index: int, uploader: Optional[str]) -> None:
        if index not in self._row_duration:
            return
        if uploader:
            self._row_uploader[index] = uploader
        else:
            self._row_uploader.pop(index, None)
        self._render_row_meta(index)

    def update_item_thumbnail(self, index: int, thumbnail_url: Optional[str]) -> None:
        if thumbnail_url:
            self._thumb_override[index] = thumbnail_url
        else:
            self._thumb_override.pop(index, None)
        row = self._visible_rows.get(index)
        if not row:
            return
        url = self._thumb_override.get(index)
        if url:
            row.thumb_url = url
            self._load_thumbnail_async(url, row)
        else:
            row.thumb.configure(image=self._placeholder)
            row.thumb.image = self._placeholder

    def _render_row_meta(self, index: int) -> None:
        row = self._visible_rows.get(index)
        if not row or not row.meta.winfo_exists():
            return
        duration = self._row_duration.get(index, "—")
        size_text = self._row_size.get(index, "fetch formats")
        row.meta.configure(text=self._build_meta_text(index, duration, size_text))

    def _build_meta_text(self, index: int, duration: str, size_text: str) -> str:
        parts = [f"Duration: {duration}"]
        uploader = self._row_uploader.get(index)
        if uploader:
            if len(uploader) > 28:
                uploader = uploader[:25] + "..."
            parts.append(f"Channel: {uploader}")
        parts.append(f"Size: {size_text}")
        return "  •  ".join(parts)

    @staticmethod
    def _is_safe_thumbnail_url(url: str) -> bool:
        parsed = urlparse(url.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _format_duration(value: Optional[int]) -> str:
        if not value:
            return "—"
        total = int(value)
        hours = total // 3600
        minutes = (total % 3600) // 60
        seconds = total % 60
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def _get_row_bg(self) -> str:
        return self._row_color[1] if ctk.get_appearance_mode() == "Dark" else self._row_color[0]

    def _apply_canvas_bg(self) -> None:
        try:
            if self._list_container:
                self._list_container.configure(fg_color=self._get_row_bg())
            self._list_canvas.configure(bg=self._get_row_bg())
        except Exception:
            pass

    def _get_selected_bg(self) -> str:
        return self._selected_color[1] if ctk.get_appearance_mode() == "Dark" else self._selected_color[0]

    def _get_hover_bg(self) -> str:
        return self._hover_color[1] if ctk.get_appearance_mode() == "Dark" else self._hover_color[0]

    def _get_selected_hover_bg(self) -> str:
        return self._selected_hover_color[1] if ctk.get_appearance_mode() == "Dark" else self._selected_hover_color[0]

    @staticmethod
    def _get_title_fg() -> str:
        return "white" if ctk.get_appearance_mode() == "Dark" else "black"

    @staticmethod
    def _get_meta_fg() -> str:
        return "gray70" if ctk.get_appearance_mode() == "Dark" else "gray30"

    def _apply_row_colors(
        self,
        row: tk.Frame,
        text_frame: tk.Frame,
        title: tk.Label,
        meta: tk.Label,
        thumb: tk.Label,
        bg: str,
    ) -> None:
        row.configure(bg=bg)
        text_frame.configure(bg=bg)
        title.configure(bg=bg, fg=self._get_title_fg())
        meta.configure(bg=bg, fg=self._get_meta_fg())
        thumb.configure(bg=bg)

    def _update_selected_count(self) -> None:
        count = len(self._selected_indices)
        if self._total_count == 0:
            self._count_label.configure(text="0 items")
            return
        if count:
            self._count_label.configure(text=f"{self._total_count} items • {count} selected")
        else:
            self._count_label.configure(text=f"{self._total_count} items")

    def _notify_selection_changed(self) -> None:
        if not self._on_select:
            return
        selected_items = [self._item_by_index[i] for i in sorted(self._selected_indices)]
        active_item = self._item_by_index.get(self._active_index) if self._active_index else None
        self._on_select(active_item, selected_items)

    def _render_row(self, row: _RowWidget, item: PlaylistItem) -> None:
        thumb_url = self._thumb_override.get(item.index) or item.thumbnail_url
        row.thumb_url = thumb_url
        row.title.configure(text=f"{item.index}. {item.title}")
        duration = self._row_duration.get(item.index, self._format_duration(item.duration))
        size_text = self._row_size.get(item.index, "fetch formats")
        row.meta.configure(text=self._build_meta_text(item.index, duration, size_text))
        if thumb_url:
            self._load_thumbnail_async(thumb_url, row)
        else:
            row.thumb.configure(image=self._placeholder)
            row.thumb.image = self._placeholder
        self._apply_row_state(item.index)
