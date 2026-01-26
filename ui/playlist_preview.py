from __future__ import annotations

from typing import List

import customtkinter as ctk


class PlaylistPreviewPanel(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk, **kwargs: object) -> None:
        super().__init__(master, corner_radius=12, **kwargs)

        title = ctk.CTkLabel(self, text="Playlist preview (first 20)")
        title.pack(anchor="w", padx=12, pady=(12, 6))

        self._list_frame = ctk.CTkScrollableFrame(self, height=120, corner_radius=8)
        self._list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._items: List[ctk.CTkLabel] = []

    def set_items(self, titles: List[str]) -> None:
        for item in self._items:
            item.destroy()
        self._items.clear()

        if not titles:
            empty = ctk.CTkLabel(self._list_frame, text="No items to preview.")
            empty.pack(anchor="w", pady=2)
            self._items.append(empty)
            return

        for index, title in enumerate(titles, start=1):
            label = ctk.CTkLabel(self._list_frame, text=f"{index}. {title}")
            label.pack(anchor="w", pady=2)
            self._items.append(label)
