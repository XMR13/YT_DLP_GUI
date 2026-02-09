import customtkinter as ctk
from pathlib import Path
from typing import Optional

from PIL import Image


class Header(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk, logo_path: Optional[Path] = None, **kwargs: object) -> None:
        super().__init__(master, corner_radius=18, **kwargs)
        self._logo_image: Optional[ctk.CTkImage] = None

        content = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        content.pack(fill="x", padx=18, pady=16)

        if logo_path and logo_path.is_file():
            try:
                image = Image.open(logo_path)
                self._logo_image = ctk.CTkImage(light_image=image, dark_image=image, size=(72, 72))
                logo = ctk.CTkLabel(content, text="", image=self._logo_image)
                logo.pack(side="left", padx=(0, 12))
            except OSError:
                self._logo_image = None

        text_block = ctk.CTkFrame(content, fg_color="transparent", corner_radius=0)
        text_block.pack(side="left", fill="x", expand=True)

        title = ctk.CTkLabel(
            text_block,
            text="yt-dlp GUI",
            font=ctk.CTkFont("Segoe UI", 26, weight="bold"),
        )
        title.pack(anchor="w", pady=(0, 4))

        subtitle = ctk.CTkLabel(
            text_block,
            text="Simple downloads with format and resolution selection",
            font=ctk.CTkFont("Segoe UI", 13),
        )
        subtitle.pack(anchor="w")
