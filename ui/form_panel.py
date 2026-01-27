from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class FormPanel(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTk,
        url_var: ctk.StringVar,
        playlist_var: ctk.BooleanVar | None,
        on_fetch: Callable[[], None],
        on_download: Callable[[], None],
        on_cancel: Callable[[], None],
        on_diagnostics: Callable[[], None],
        url_label_text: str = "Video or Playlist URL",
        **kwargs: object,
    ) -> None:
        super().__init__(master, corner_radius=12, **kwargs)

        use_playlist_toggle = playlist_var is not None
        columns = 3 if use_playlist_toggle else 2

        url_label = ctk.CTkLabel(self, text=url_label_text)
        url_label.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

        url_entry = ctk.CTkEntry(self, textvariable=url_var)
        url_entry.grid(
            row=1,
            column=0,
            columnspan=columns,
            sticky="ew",
            padx=12,
            pady=(0, 12),
        )

        if use_playlist_toggle:
            playlist_check = ctk.CTkCheckBox(
                self,
                text="Playlist URL",
                variable=playlist_var,
            )
            playlist_check.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 10))

        fetch_frame = ctk.CTkFrame(self, fg_color="transparent")
        fetch_column = 1 if use_playlist_toggle else 0
        fetch_frame.grid(row=2, column=fetch_column, sticky="e", padx=12, pady=(0, 10))

        self.fetch_button = ctk.CTkButton(
            fetch_frame,
            text="Fetch Formats",
            command=on_fetch,
            width=140,
        )
        self.fetch_button.pack(side="left", padx=(0, 8))

        self.diag_button = ctk.CTkButton(
            fetch_frame,
            text="Diagnostics",
            command=on_diagnostics,
            width=120,
        )
        self.diag_button.pack(side="left")

        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_column = 2 if use_playlist_toggle else 1
        action_frame.grid(row=2, column=action_column, sticky="e", padx=12, pady=(0, 10))

        self.download_button = ctk.CTkButton(
            action_frame,
            text="Download",
            command=on_download,
            width=140,
        )
        self.download_button.pack(side="left", padx=(0, 8))

        self.cancel_button = ctk.CTkButton(
            action_frame,
            text="Cancel",
            command=on_cancel,
            width=100,
            fg_color="#444444",
            hover_color="#555555",
            state="disabled",
        )
        self.cancel_button.pack(side="left")

        self.progress = ctk.CTkProgressBar(self, height=10)
        self.progress.grid(
            row=3,
            column=0,
            columnspan=columns,
            sticky="ew",
            padx=12,
            pady=(0, 6),
        )
        self.progress.set(0)

        self.progress_label = ctk.CTkLabel(self, text="Idle")
        self.progress_label.grid(
            row=4,
            column=0,
            columnspan=columns,
            sticky="w",
            padx=12,
            pady=(0, 12),
        )

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        if use_playlist_toggle:
            self.columnconfigure(2, weight=0)
