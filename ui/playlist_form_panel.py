from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class PlaylistFormPanel(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTk,
        url_var: ctk.StringVar,
        on_fetch: Callable[[], None],
        on_fetch_selected: Callable[[], None],
        on_download_selected: Callable[[], None],
        on_download_playlist: Callable[[], None],
        on_cancel: Callable[[], None],
        on_diagnostics: Callable[[], None],
        **kwargs: object,
    ) -> None:
        super().__init__(master, corner_radius=12, **kwargs)

        url_label = ctk.CTkLabel(self, text="Playlist URL")
        url_label.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

        url_entry = ctk.CTkEntry(self, textvariable=url_var)
        url_entry.grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 12))

        fetch_frame = ctk.CTkFrame(self, fg_color="transparent")
        fetch_frame.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 10))

        self.fetch_button = ctk.CTkButton(
            fetch_frame,
            text="Fetch Playlist",
            command=on_fetch,
            width=150,
        )
        self.fetch_button.pack(side="left", padx=(0, 8))

        self.fetch_selected_button = ctk.CTkButton(
            fetch_frame,
            text="Fetch Selected Formats",
            command=on_fetch_selected,
            width=190,
        )
        self.fetch_selected_button.pack(side="left")

        download_frame = ctk.CTkFrame(self, fg_color="transparent")
        download_frame.grid(row=2, column=1, sticky="e", padx=12, pady=(0, 10))

        self.download_selected_button = ctk.CTkButton(
            download_frame,
            text="Download Selected",
            command=on_download_selected,
            width=170,
        )
        self.download_selected_button.pack(side="left", padx=(0, 8))

        self.download_playlist_button = ctk.CTkButton(
            download_frame,
            text="Download Playlist",
            command=on_download_playlist,
            width=170,
        )
        self.download_playlist_button.pack(side="left")

        actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        actions_frame.grid(row=2, column=2, sticky="e", padx=12, pady=(0, 10))

        self.diag_button = ctk.CTkButton(
            actions_frame,
            text="Diagnostics",
            command=on_diagnostics,
            width=120,
        )
        self.diag_button.pack(side="left", padx=(0, 8))

        self.cancel_button = ctk.CTkButton(
            actions_frame,
            text="Cancel",
            command=on_cancel,
            width=100,
            fg_color="#444444",
            hover_color="#555555",
            state="disabled",
        )
        self.cancel_button.pack(side="left")

        self.progress = ctk.CTkProgressBar(self, height=10)
        self.progress.grid(row=3, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 6))
        self.progress.set(0)

        self.progress_label = ctk.CTkLabel(self, text="Idle")
        self.progress_label.grid(row=4, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 12))

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.columnconfigure(2, weight=0)
