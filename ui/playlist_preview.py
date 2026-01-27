from __future__ import annotations

from io import BytesIO
import threading
from typing import Callable, Dict, List, Optional
import tkinter as tk

import customtkinter as ctk
from PIL import Image
from urllib.request import urlopen

from yt_dlp_adapter import PlaylistItem


class PlaylistPreviewPanel(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTk,
        on_select: Optional[Callable[[PlaylistItem], None]] = None,
        **kwargs: object,
    ) -> None:
        super().__init__(master, corner_radius=12, **kwargs)

        title = ctk.CTkLabel(self, text="Playlist preview (first 20)")
        title.pack(anchor="w", padx=12, pady=(12, 6))

        self._list_frame = ctk.CTkScrollableFrame(self, height=180, corner_radius=8)
        self._list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._items: List[ctk.CTkFrame] = []
        self._image_cache: Dict[str, ctk.CTkImage] = {}
        self._placeholder = self._build_placeholder()
        self._on_select = on_select
        self._selected_row: Optional[ctk.CTkFrame] = None
        self._selected_item_index: Optional[int] = None
        self._row_color = ("#E9E9E9", "#2B2B2B")
        self._selected_color = ("#D6D6D6", "#3A3A3A")
        self._row_meta: Dict[int, ctk.CTkLabel] = {}
        self._row_duration: Dict[int, str] = {}

    def get_scroll_frame(self) -> ctk.CTkScrollableFrame:
        return self._list_frame

    def get_scroll_canvas(self) -> Optional[object]:
        return getattr(self._list_frame, "_parent_canvas", None) or getattr(self._list_frame, "_canvas", None)

    def set_items(self, items: List[PlaylistItem]) -> None:
        # Clear existing (keep this)
        for item in self._items:
            item.destroy()
        self._items.clear()
        # ... (clear caches) ...

        for item in items:
            # Use standard tk.Frame - much faster than CTkFrame
            row = tk.Frame(self._list_frame, bg=self._row_color[1] if ctk.get_appearance_mode() == "Dark" else self._row_color[0])
            row.pack(fill="x", pady=2, padx=4)
            
            # Standard tk.Label for thumbnail placeholder
            thumb = tk.Label(row, text="", bg="#2B2B2B" if ctk.get_appearance_mode() == "Dark" else "#E9E9E9", width=17, height=4)
            thumb.pack(side="left", padx=(8, 12), pady=4)
            
            text_frame = tk.Frame(row, bg=self._row_color[1] if ctk.get_appearance_mode() == "Dark" else self._row_color[0])
            text_frame.pack(side="left", fill="both", expand=True, pady=4)
            
            # Standard labels
            title = tk.Label(
                text_frame,
                text=f"{item.index}. {item.title}",
                anchor="w",
                justify="left",
                bg=text_frame.cget("bg"),
                fg="white" if ctk.get_appearance_mode() == "Dark" else "black",
                font=("Arial", 12)
            )
            title.pack(anchor="w")
            
            duration = self._format_duration(item.duration)
            self._row_duration[item.index] = duration
            meta = tk.Label(
                text_frame,
                text=f"Duration: {duration}  •  Size: fetch formats",
                anchor="w",
                bg=text_frame.cget("bg"),
                fg="gray70" if ctk.get_appearance_mode() == "Dark" else "gray30",
                font=("Arial", 10)
            )
            meta.pack(anchor="w")
            self._row_meta[item.index] = meta
            
            # Handle selection highlighting manually since tk.Label doesn't have fg_color
            def make_select_handler(r=row, t=title, m=meta, th=thumb, item=item):
                return lambda e: self._select_row_tk(r, t, m, th, item)
                
            for widget in (row, thumb, title, meta):
                widget.bind("<Button-1>", make_select_handler())
                
            self._items.append(row)

    def _select_row_tk(self, row: tk.Frame, title: tk.Label, meta: tk.Label, thumb: tk.Label, item: PlaylistItem):
        # Reset previous selection
        if self._selected_row and self._selected_row.winfo_exists():
            bg = self._row_color[1] if ctk.get_appearance_mode() == "Dark" else self._row_color[0]
            self._selected_row.configure(bg=bg)
            # Reset children bg...
        
        # Highlight new selection
        sel_bg = self._selected_color[1] if ctk.get_appearance_mode() == "Dark" else self._selected_color[0]
        row.configure(bg=sel_bg)
        self._selected_row = row
        self._selected_item_index = item.index
        if self._on_select:
            self._on_select(item)

    def _build_placeholder(self) -> ctk.CTkImage:
        image = Image.new("RGB", (120, 68), color=(40, 40, 40))
        return ctk.CTkImage(light_image=image, dark_image=image, size=(120, 68))

    def _load_thumbnail_async(self, url: str, label: ctk.CTkLabel) -> None:
        if url in self._image_cache:
            try:
                if label.winfo_exists():
                    label.configure(image=self._image_cache[url])
            except tk.TclError:
                pass
            return

        def worker() -> None:
            try:
                with urlopen(url, timeout=5) as response:
                    data = response.read()
                image = Image.open(BytesIO(data))
                image = image.convert("RGB")
                image.thumbnail((120, 68))
                ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
                self._image_cache[url] = ctk_image
                self.after(0, lambda: self._apply_thumbnail(label, ctk_image))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _apply_thumbnail(label: ctk.CTkLabel, image: ctk.CTkImage) -> None:
        try:
            if not label.winfo_exists():
                return
            label.configure(image=image)
            label.image = image
        except tk.TclError:
            pass

    def _bind_select(
        self,
        row: ctk.CTkFrame,
        thumb: ctk.CTkLabel,
        title: ctk.CTkLabel,
        meta: ctk.CTkLabel,
        item: PlaylistItem,
    ) -> None:
        def handler(_event: object) -> None:
            self._select_row(row, item)

        for widget in (row, thumb, title, meta):
            widget.bind("<Button-1>", handler)

    def _select_row(self, row: ctk.CTkFrame, item: PlaylistItem) -> None:
        if self._selected_row and self._selected_row.winfo_exists():
            self._selected_row.configure(fg_color=self._row_color)
        row.configure(fg_color=self._selected_color)
        self._selected_row = row
        self._selected_item_index = item.index
        if self._on_select:
            self._on_select(item)

    def update_selected_size(self, size_text: str) -> None:
        if self._selected_item_index is None:
            return
        meta = self._row_meta.get(self._selected_item_index)
        duration = self._row_duration.get(self._selected_item_index, "—")
        if not meta or not meta.winfo_exists():
            return
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
