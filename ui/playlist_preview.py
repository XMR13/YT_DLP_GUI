from __future__ import annotations

from io import BytesIO
import threading
from typing import Callable, Dict, List, Optional, Set, Tuple
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageTk
from urllib.request import urlopen

from yt_dlp_adapter import PlaylistItem


class PlaylistPreviewPanel(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTk,
        on_select: Optional[Callable[[Optional[PlaylistItem], List[PlaylistItem]], None]] = None,
        on_load_more: Optional[Callable[[], None]] = None,
        **kwargs: object,
    ) -> None:
        super().__init__(master, corner_radius=12, **kwargs)

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

        self._list_frame = ctk.CTkScrollableFrame(self, height=180, corner_radius=8)
        self._list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._load_more_button = ctk.CTkButton(
            self,
            text="Load more",
            command=on_load_more or (lambda: None),
            width=140,
        )
        self._load_more_button.pack(pady=(0, 12))

        self._items: List[tk.Widget] = []
        self._image_cache: Dict[str, ImageTk.PhotoImage] = {}
        self._placeholder = self._build_placeholder()
        self._on_select = on_select
        self._on_load_more = on_load_more
        self._row_widgets: Dict[int, Tuple[tk.Frame, tk.Frame, tk.Label, tk.Label, tk.Label]] = {}
        self._item_by_index: Dict[int, PlaylistItem] = {}
        self._selected_indices: Set[int] = set()
        self._selection_order: List[int] = []
        self._hovered_indices: Set[int] = set()
        self._active_index: Optional[int] = None
        self._row_color = ("#E9E9E9", "#2B2B2B")
        self._selected_color = ("#D6D6D6", "#3A3A3A")
        self._hover_color = ("#E1E1E1", "#343434")
        self._selected_hover_color = ("#CFCFCF", "#464646")
        self._row_meta: Dict[int, tk.Label] = {}
        self._row_duration: Dict[int, str] = {}
        self._row_size: Dict[int, str] = {}
        self._total_count = 0
        self._empty_label: Optional[ctk.CTkLabel] = None

    def get_scroll_frame(self) -> ctk.CTkScrollableFrame:
        return self._list_frame

    def get_scroll_canvas(self) -> Optional[object]:
        return getattr(self._list_frame, "_parent_canvas", None) or getattr(self._list_frame, "_canvas", None)

    def set_items(self, items: List[PlaylistItem], total_count: Optional[int] = None) -> None:
        for item in self._items:
            item.destroy()
        self._items.clear()
        if hasattr(self, "_empty_label") and self._empty_label:
            self._empty_label.destroy()
            self._empty_label = None
        self._row_widgets.clear()
        self._item_by_index.clear()
        self._selected_indices.clear()
        self._selection_order.clear()
        self._hovered_indices.clear()
        self._active_index = None
        self._row_meta.clear()
        self._row_duration.clear()
        self._row_size.clear()
        self._image_cache.clear()
        self._total_count = total_count if isinstance(total_count, int) and total_count > 0 else len(items)
        self._update_selected_count()

        for item in items:
            self._add_item(item)
        
        if not items:
            self._empty_label = ctk.CTkLabel(self._list_frame, text="No items to preview.")
            self._empty_label.pack(anchor="w", pady=2)
            self._items.append(self._empty_label)
        self._notify_selection_changed()

    def append_items(self, items: List[PlaylistItem], total_count: Optional[int] = None) -> None:
        if hasattr(self, "_empty_label") and self._empty_label:
            self._empty_label.destroy()
            self._empty_label = None
        if isinstance(total_count, int) and total_count > 0:
            self._total_count = total_count
        for item in items:
            if item.index in self._row_widgets:
                continue
            self._add_item(item)
        self._update_selected_count()

    def _add_item(self, item: PlaylistItem) -> None:
        # Use standard tk.Frame - much faster than CTkFrame
        row_bg = self._get_row_bg()
        row = tk.Frame(self._list_frame, bg=row_bg)
        row.pack(fill="x", pady=2, padx=4)

        # Standard tk.Label for thumbnail placeholder
        thumb = tk.Label(row, text="", bg=row_bg, image=self._placeholder)
        thumb.image = self._placeholder
        thumb.pack(side="left", padx=(8, 12), pady=4)

        text_frame = tk.Frame(row, bg=row_bg)
        text_frame.pack(side="left", fill="both", expand=True, pady=4)

        # Standard labels
        title = tk.Label(
            text_frame,
            text=f"{item.index}. {item.title}",
            anchor="w",
            justify="left",
            bg=row_bg,
            fg=self._get_title_fg(),
            font=("Arial", 12),
        )
        title.pack(anchor="w")

        duration = self._format_duration(item.duration)
        self._row_duration[item.index] = duration
        self._row_size[item.index] = self._row_size.get(item.index, "fetch formats")
        meta = tk.Label(
            text_frame,
            text=f"Duration: {duration}  •  Size: {self._row_size[item.index]}",
            anchor="w",
            bg=row_bg,
            fg=self._get_meta_fg(),
            font=("Arial", 10),
        )
        meta.pack(anchor="w")
        self._row_meta[item.index] = meta
        self._row_widgets[item.index] = (row, text_frame, title, meta, thumb)
        self._item_by_index[item.index] = item

        # Handle selection highlighting manually since tk.Label doesn't have fg_color
        def make_select_handler(index=item.index):
            return lambda _e: self._toggle_select(index)

        def make_hover_handler(index=item.index, entering=True):
            return lambda _e: self._set_hover(index, entering)

        for widget in (row, thumb, title, meta, text_frame):
            widget.bind("<Button-1>", make_select_handler())
            widget.bind("<Enter>", make_hover_handler(entering=True))
            widget.bind("<Leave>", make_hover_handler(entering=False))

        self._items.append(row)

        if item.thumbnail_url:
            self._load_thumbnail_async(item.thumbnail_url, thumb)

    def set_load_more_state(self, enabled: bool, text: str = "Load more") -> None:
        self._load_more_button.configure(state="normal" if enabled else "disabled", text=text)
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
        widgets = self._row_widgets.get(index)
        if not widgets:
            return
        if index in self._selected_indices:
            bg = self._get_selected_hover_bg() if index in self._hovered_indices else self._get_selected_bg()
        else:
            bg = self._get_hover_bg() if index in self._hovered_indices else self._get_row_bg()
        row, text_frame, title, meta, thumb = widgets
        self._apply_row_colors(row, text_frame, title, meta, thumb, bg)

    def _build_placeholder(self) -> ImageTk.PhotoImage:
        color = (40, 40, 40) if ctk.get_appearance_mode() == "Dark" else (220, 220, 220)
        image = Image.new("RGB", (120, 68), color=color)
        return ImageTk.PhotoImage(image)

    def _load_thumbnail_async(self, url: str, label: tk.Label) -> None:
        if url in self._image_cache:
            try:
                if label.winfo_exists():
                    label.configure(image=self._image_cache[url])
                    label.image = self._image_cache[url]
            except tk.TclError:
                pass
            return

        def worker() -> None:
            try:
                with urlopen(url, timeout=5) as response:
                    data = response.read()
                image = Image.open(BytesIO(data))
                image = image.convert("RGB")
                image.thumbnail((120, 68), Image.LANCZOS)
                self.after(0, lambda: self._apply_thumbnail(label, image, url))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _apply_thumbnail(self, label: tk.Label, image: Image.Image, url: str) -> None:
        try:
            if not label.winfo_exists():
                return
            photo = ImageTk.PhotoImage(image)
            self._image_cache[url] = photo
            label.configure(image=photo)
            label.image = photo
        except tk.TclError:
            pass

    def update_selected_size(self, size_text: str) -> None:
        if self._active_index is None:
            return
        self._row_size[self._active_index] = size_text
        self._render_row_meta(self._active_index)

    def update_item_duration(self, index: int, duration_seconds: Optional[int]) -> None:
        if index not in self._row_duration:
            return
        self._row_duration[index] = self._format_duration(duration_seconds)
        self._render_row_meta(index)

    def _render_row_meta(self, index: int) -> None:
        meta = self._row_meta.get(index)
        if not meta or not meta.winfo_exists():
            return
        duration = self._row_duration.get(index, "—")
        size_text = self._row_size.get(index, "fetch formats")
        meta.configure(text=f"Duration: {duration}  •  Size: {size_text}")

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
