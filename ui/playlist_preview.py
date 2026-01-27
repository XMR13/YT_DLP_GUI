from __future__ import annotations

from io import BytesIO
import threading
from typing import Callable, Dict, List, Optional

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
        self._row_color = ("#E9E9E9", "#2B2B2B")
        self._selected_color = ("#D6D6D6", "#3A3A3A")

    def set_items(self, items: List[PlaylistItem]) -> None:
        for item in self._items:
            item.destroy()
        self._items.clear()
        self._selected_row = None

        if not items:
            empty = ctk.CTkLabel(self._list_frame, text="No items to preview.")
            empty.pack(anchor="w", pady=2)
            self._items.append(empty)
            return

        for item in items:
            row = ctk.CTkFrame(self._list_frame, corner_radius=8, fg_color=self._row_color)
            row.pack(fill="x", pady=4, padx=4)

            thumb = ctk.CTkLabel(row, text="", image=self._placeholder, width=120, height=68)
            thumb.pack(side="left", padx=(8, 12), pady=8)

            text_frame = ctk.CTkFrame(row, fg_color="transparent")
            text_frame.pack(side="left", fill="both", expand=True, pady=8)

            title = ctk.CTkLabel(
                text_frame,
                text=f"{item.index}. {item.title}",
                anchor="w",
                justify="left",
            )
            title.pack(anchor="w")

            duration = self._format_duration(item.duration)
            meta = ctk.CTkLabel(
                text_frame,
                text=f"Duration: {duration}  •  Size: —",
                anchor="w",
            )
            meta.pack(anchor="w")

            self._items.append(row)

            self._bind_select(row, thumb, title, meta, item)

            if item.thumbnail_url:
                self._load_thumbnail_async(item.thumbnail_url, thumb)

    def _build_placeholder(self) -> ctk.CTkImage:
        image = Image.new("RGB", (120, 68), color=(40, 40, 40))
        return ctk.CTkImage(light_image=image, dark_image=image, size=(120, 68))

    def _load_thumbnail_async(self, url: str, label: ctk.CTkLabel) -> None:
        if url in self._image_cache:
            label.configure(image=self._image_cache[url])
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
                label.after(0, lambda: self._apply_thumbnail(label, ctk_image))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _apply_thumbnail(label: ctk.CTkLabel, image: ctk.CTkImage) -> None:
        label.configure(image=image)
        label.image = image

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
        if self._on_select:
            self._on_select(item)

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
