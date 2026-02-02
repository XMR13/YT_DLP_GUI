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
            ("Uploader", "uploader"),
            ("Duration", "duration"),
            ("Resolution / FPS", "resolution"),
            ("Format", "format"),
            ("Size", "size"),
        ]

        for idx, (label, key) in enumerate(info_fields, start=1):
            name_label = ctk.CTkLabel(self, text=label)
            name_label.grid(row=idx, column=0, sticky="nw", padx=12, pady=(0, 6))

            value_label = ctk.CTkLabel(
                self,
                text="—",
                anchor="w",
                justify="left",
            )
            value_label.grid(row=idx, column=1, sticky="ew", padx=12, pady=(0, 6))
            self.values[key] = value_label

        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)

        self._wrap_job: str | None = None
        self._last_wraplength: int | None = None
        self.bind("<Configure>", self._on_configure)
        self.after(0, self._update_title_wraplength)

    def _update_title_wraplength(self) -> None:
        self._wrap_job = None
        title_label = self.values.get("title")
        if not title_label:
            return
        width = self.winfo_width()
        wraplength = max(200, width - 280)
        if self._last_wraplength == wraplength:
            return
        self._last_wraplength = wraplength
        title_label.configure(wraplength=wraplength)

    def _on_configure(self, _event: object) -> None:
        # Coalesce rapid configure events during window resize.
        if self._wrap_job is not None:
            try:
                self.after_cancel(self._wrap_job)
            except Exception:
                pass
        self._wrap_job = self.after_idle(self._update_title_wraplength)

    def update_values(self, values: Dict[str, str]) -> None:
        for key, widget in self.values.items():
            widget.configure(text=values.get(key, "—"))
