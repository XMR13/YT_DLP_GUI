from __future__ import annotations

from typing import Callable, List, Optional, Tuple

import customtkinter as ctk

from controllers.history_store import HistoryEntry


HistoryAction = Callable[[HistoryEntry], None]


class HistoryPage(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTk,
        on_clear: Optional[Callable[[], None]] = None,
        on_open_folder: Optional[HistoryAction] = None,
        on_retry: Optional[HistoryAction] = None,
        **kwargs: object,
    ) -> None:
        super().__init__(master, **kwargs)
        self._on_clear = on_clear
        self._on_open_folder = on_open_folder
        self._on_retry = on_retry
        self._rows: List[ctk.CTkFrame] = []
        self._badge_colors = {
            "completed": ("#2E7D32", "#2E7D32"),
            "cancelled": ("#3A3A3A", "#3A3A3A"),
            "failed": ("#B71C1C", "#B71C1C"),
        }
        self._build()

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(6, 12))

        title = ctk.CTkLabel(
            header,
            text="History",
            font=ctk.CTkFont("Segoe UI", 18, weight="bold"),
        )
        title.pack(side="left")

        clear_btn = ctk.CTkButton(
            header,
            text="Clear",
            width=80,
            command=self._handle_clear,
        )
        clear_btn.pack(side="right")

        self._list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._list.pack(fill="both", expand=True)
        self._list_canvas = getattr(self._list, "_parent_canvas", None) or getattr(self._list, "_canvas", None)
        if self._list_canvas:
            try:
                self._list_canvas.configure(yscrollincrement=1)
            except Exception:
                pass

        self._empty = ctk.CTkLabel(
            self._list,
            text="No history yet.",
            font=ctk.CTkFont("Segoe UI", 13),
        )
        self._empty.pack(pady=20)

    def set_items(self, items: List[HistoryEntry]) -> None:
        for row in self._rows:
            row.destroy()
        self._rows.clear()

        if not items:
            self._empty.pack(pady=20)
            return
        self._empty.pack_forget()

        for entry in items:
            row = self._build_row(self._list, entry)
            row.pack(fill="x", pady=6, padx=6)
            self._rows.append(row)

    def get_scroll_frame(self) -> ctk.CTkScrollableFrame:
        return self._list

    def get_scroll_canvas(self) -> Optional[object]:
        return self._list_canvas

    def _build_row(self, master: ctk.CTkFrame, entry: HistoryEntry) -> ctk.CTkFrame:
        row = ctk.CTkFrame(master, corner_radius=12)
        row.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            row,
            text=entry.title or "Untitled",
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))

        badge = self._build_status_badge(row, entry.status)
        badge.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 6))

        meta = ctk.CTkLabel(
            row,
            text=entry.timestamp,
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 11),
        )
        meta.grid(row=1, column=0, sticky="w", padx=(96, 12), pady=(0, 6))

        url = ctk.CTkLabel(
            row,
            text=entry.url,
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 11),
            wraplength=520,
        )
        url.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 6))

        output_label = self._format_output(entry)
        output = ctk.CTkLabel(
            row,
            text=output_label,
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 11),
        )
        output.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 10))

        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.grid(row=0, column=1, rowspan=4, sticky="e", padx=12, pady=10)

        if self._on_open_folder:
            open_btn = ctk.CTkButton(
                actions,
                text="Open folder",
                width=110,
                command=lambda e=entry: self._on_open_folder(e),
            )
            open_btn.pack(pady=4)

        if self._on_retry:
            retry_btn = ctk.CTkButton(
                actions,
                text="Retry",
                width=90,
                command=lambda e=entry: self._on_retry(e),
            )
            retry_btn.pack(pady=4)

        return row

    @staticmethod
    def _format_output(entry: HistoryEntry) -> str:
        if entry.output_paths:
            if len(entry.output_paths) == 1:
                return f"File: {entry.output_paths[0]}"
            return f"{len(entry.output_paths)} files • {entry.output_dir}"
        if entry.output_dir:
            return f"Folder: {entry.output_dir}"
        return "Output: Unknown"

    def _handle_clear(self) -> None:
        if self._on_clear:
            self._on_clear()

    def _build_status_badge(self, master: ctk.CTkFrame, status: str) -> ctk.CTkFrame:
        key = status.lower()
        label = status.title()
        color = self._badge_colors.get(key, ("#555555", "#555555"))

        badge = ctk.CTkFrame(master, corner_radius=10, fg_color=color)
        text = ctk.CTkLabel(
            badge,
            text=label,
            text_color="white",
            font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
        )
        text.pack(padx=10, pady=2)
        return badge
