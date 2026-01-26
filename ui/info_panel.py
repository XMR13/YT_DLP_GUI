from __future__ import annotations

from typing import Dict

import customtkinter as ctk


class InfoPanel(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk, **kwargs: object) -> None:
        super().__init__(master, corner_radius=12, **kwargs)

        info_title = ctk.CTkLabel(self, text="Video info")
        info_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 6))

        self.values: Dict[str, ctk.CTkLabel] = {}
        info_fields = [
            ("Title", "title"),
            ("Resolution / FPS", "resolution"),
            ("Format", "format"),
            ("Size", "size"),
        ]

        for idx, (label, key) in enumerate(info_fields, start=1):
            name_label = ctk.CTkLabel(self, text=label)
            name_label.grid(row=idx, column=0, sticky="w", padx=12, pady=(0, 6))
            value_label = ctk.CTkLabel(self, text="—")
            value_label.grid(row=idx, column=1, sticky="w", padx=12, pady=(0, 6))
            self.values[key] = value_label

        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)

    def update_values(self, values: Dict[str, str]) -> None:
        for key, label in self.values.items():
            label.configure(text=values.get(key, "—"))
