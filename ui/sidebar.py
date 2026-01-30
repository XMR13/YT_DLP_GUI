from __future__ import annotations

from typing import Callable, Dict, Optional

import customtkinter as ctk
from PIL import Image, ImageDraw


NavSelect = Callable[[str], None]


class SidebarNav(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTk,
        on_select: Optional[NavSelect] = None,
        **kwargs: object,
    ) -> None:
        super().__init__(master, corner_radius=18, **kwargs)
        self._on_select = on_select
        self._buttons: Dict[str, ctk.CTkButton] = {}
        self._active_key: Optional[str] = None
        self._default_button_fg = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        self._default_button_hover = ctk.ThemeManager.theme["CTkButton"]["hover_color"]
        self._icons = self._build_icons()
        self._build()

    def _build(self) -> None:
        title = ctk.CTkLabel(
            self,
            text="Menu",
            font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
        )
        title.pack(anchor="w", padx=16, pady=(16, 8))

        self._add_button("download", "Download", self._icons["download"])
        self._add_button("queue", "Queue", self._icons["queue"])
        self._add_button("history", "History", self._icons["history"])

        spacer = ctk.CTkFrame(self, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

    def _add_button(self, key: str, label: str, icon: ctk.CTkImage) -> None:
        button = ctk.CTkButton(
            self,
            text=label,
            image=icon,
            compound="left",
            anchor="w",
            height=44,
            corner_radius=12,
            fg_color="transparent",
            hover_color=self._default_button_hover,
            command=lambda k=key: self._handle_select(k),
        )
        button.pack(fill="x", padx=12, pady=6)
        self._buttons[key] = button

    def _handle_select(self, key: str) -> None:
        self.set_active(key)
        if self._on_select:
            self._on_select(key)

    def set_active(self, key: str) -> None:
        if key == self._active_key:
            return
        self._active_key = key
        for btn_key, button in self._buttons.items():
            if btn_key == key:
                button.configure(fg_color=self._default_button_fg)
            else:
                button.configure(fg_color="transparent")

    @staticmethod
    def _make_icon(draw_fn: Callable[[str, int], Image.Image], size: int = 18) -> ctk.CTkImage:
        light = draw_fn("#2b2b2b", size)
        dark = draw_fn("#e6e6e6", size)
        return ctk.CTkImage(light_image=light, dark_image=dark, size=(size, size))

    def _build_icons(self) -> Dict[str, ctk.CTkImage]:
        return {
            "download": self._make_icon(self._draw_download_icon),
            "queue": self._make_icon(self._draw_queue_icon),
            "history": self._make_icon(self._draw_history_icon),
        }

    @staticmethod
    def _draw_download_icon(color: str, size: int) -> Image.Image:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        center = size // 2
        draw.line((center, 3, center, size - 6), fill=color, width=2)
        draw.polygon(
            [
                (center - 4, size - 8),
                (center + 4, size - 8),
                (center, size - 3),
            ],
            fill=color,
        )
        draw.line((3, size - 3, size - 3, size - 3), fill=color, width=2)
        return img

    @staticmethod
    def _draw_history_icon(color: str, size: int) -> Image.Image:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        padding = 2
        draw.ellipse((padding, padding, size - padding, size - padding), outline=color, width=2)
        center = size // 2
        draw.line((center, center, center, center - 4), fill=color, width=2)
        draw.line((center, center, center + 4, center + 2), fill=color, width=2)
        return img

    @staticmethod
    def _draw_queue_icon(color: str, size: int) -> Image.Image:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        margin = 3
        line_height = 2
        gap = 3
        for idx in range(3):
            y = margin + idx * (line_height + gap)
            draw.rounded_rectangle(
                (margin, y, size - margin, y + line_height + 2),
                radius=2,
                outline=color,
                width=2,
            )
        return img
