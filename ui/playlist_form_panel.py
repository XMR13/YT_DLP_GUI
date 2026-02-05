from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class PlaylistFormPanel(ctk.CTkFrame):
    COMPACT_WIDTH = 1060

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
        self._layout_job: str | None = None
        self._compact_mode: bool | None = None

        url_label = ctk.CTkLabel(self, text="Playlist URL")
        url_label.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

        url_entry = ctk.CTkEntry(self, textvariable=url_var)
        url_entry.grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 12))

        self.fetch_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.fetch_frame.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 10))

        self.fetch_button = ctk.CTkButton(
            self.fetch_frame,
            text="Fetch Playlist",
            command=on_fetch,
            width=150,
        )
        self.fetch_button.pack(side="left", padx=(0, 8))

        self.fetch_selected_button = ctk.CTkButton(
            self.fetch_frame,
            text="Fetch Selected Formats",
            command=on_fetch_selected,
            width=190,
        )
        self.fetch_selected_button.pack(side="left")

        self.download_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.download_frame.grid(row=2, column=1, sticky="e", padx=12, pady=(0, 10))

        self.download_selected_button = ctk.CTkButton(
            self.download_frame,
            text="Download Selected",
            command=on_download_selected,
            width=170,
        )
        self.download_selected_button.pack(side="left", padx=(0, 8))

        self.download_playlist_button = ctk.CTkButton(
            self.download_frame,
            text="Download Playlist",
            command=on_download_playlist,
            width=170,
        )
        self.download_playlist_button.pack(side="left")

        self.actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.actions_frame.grid(row=2, column=2, sticky="e", padx=12, pady=(0, 10))

        self.diag_button = ctk.CTkButton(
            self.actions_frame,
            text="Diagnostics",
            command=on_diagnostics,
            width=120,
        )
        self.diag_button.pack(side="left", padx=(0, 8))

        self.cancel_button = ctk.CTkButton(
            self.actions_frame,
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
        self.bind("<Configure>", self._schedule_layout_update)
        self.bind("<Map>", self._schedule_layout_update)
        self.after_idle(self._apply_layout_mode)

    def _schedule_layout_update(self, _event: object) -> None:
        if self._layout_job:
            try:
                self.after_cancel(self._layout_job)
            except Exception:
                pass
        self._layout_job = self.after_idle(self._apply_layout_mode)

    def _apply_layout_mode(self) -> None:
        self._layout_job = None
        width = max(self.winfo_width(), 1)
        compact = width < self.COMPACT_WIDTH
        if self._compact_mode == compact:
            return
        self._compact_mode = compact

        if compact:
            self.fetch_frame.grid_configure(row=2, column=0, columnspan=3, sticky="w")
            self.download_frame.grid_configure(row=3, column=0, columnspan=3, sticky="w")
            self.actions_frame.grid_configure(row=4, column=0, columnspan=3, sticky="w")
            self.progress.grid_configure(row=5, column=0, columnspan=3, sticky="ew")
            self.progress_label.grid_configure(row=6, column=0, columnspan=3, sticky="w")
            return

        self.fetch_frame.grid_configure(row=2, column=0, columnspan=1, sticky="w")
        self.download_frame.grid_configure(row=2, column=1, columnspan=1, sticky="e")
        self.actions_frame.grid_configure(row=2, column=2, columnspan=1, sticky="e")
        self.progress.grid_configure(row=3, column=0, columnspan=3, sticky="ew")
        self.progress_label.grid_configure(row=4, column=0, columnspan=3, sticky="w")
