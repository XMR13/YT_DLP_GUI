from __future__ import annotations

from typing import Callable, List, Optional

import customtkinter as ctk


QueueAction = Callable[[str], None]


class QueuePage(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTk,
        on_start: Optional[Callable[[], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
        on_clear: Optional[Callable[[], None]] = None,
        on_clear_completed: Optional[Callable[[], None]] = None,
        on_remove: Optional[QueueAction] = None,
        on_retry: Optional[QueueAction] = None,
        **kwargs: object,
    ) -> None:
        super().__init__(master, **kwargs)
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_cancel = on_cancel
        self._on_clear = on_clear
        self._on_clear_completed = on_clear_completed
        self._on_remove = on_remove
        self._on_retry = on_retry
        self._rows: List[ctk.CTkFrame] = []
        self._badge_colors = {
            "queued": ("#455A64", "#455A64"),
            "running": ("#1565C0", "#1565C0"),
            "completed": ("#2E7D32", "#2E7D32"),
            "cancelled": ("#3A3A3A", "#3A3A3A"),
            "failed": ("#B71C1C", "#B71C1C"),
        }
        self._build()

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(6, 10))

        title = ctk.CTkLabel(
            header,
            text="Queue",
            font=ctk.CTkFont("Segoe UI", 18, weight="bold"),
        )
        title.pack(side="left")

        self._count = ctk.CTkLabel(
            header,
            text="0 items",
            font=ctk.CTkFont("Segoe UI", 12),
        )
        self._count.pack(side="left", padx=12)

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.pack(side="right")

        self._start_btn = ctk.CTkButton(
            controls,
            text="Start",
            width=70,
            command=self._handle_start,
        )
        self._start_btn.pack(side="left", padx=4)

        self._stop_btn = ctk.CTkButton(
            controls,
            text="Stop",
            width=70,
            command=self._handle_stop,
        )
        self._stop_btn.pack(side="left", padx=4)

        self._cancel_btn = ctk.CTkButton(
            controls,
            text="Cancel",
            width=80,
            command=self._handle_cancel,
        )
        self._cancel_btn.pack(side="left", padx=4)

        self._clear_btn = ctk.CTkButton(
            controls,
            text="Clear",
            width=70,
            command=self._handle_clear,
        )
        self._clear_btn.pack(side="left", padx=4)

        self._clear_done_btn = ctk.CTkButton(
            controls,
            text="Clear done",
            width=90,
            command=self._handle_clear_completed,
        )
        self._clear_done_btn.pack(side="left", padx=4)

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
            text="Queue is empty.",
            font=ctk.CTkFont("Segoe UI", 13),
        )
        self._empty.pack(pady=20)

    def set_items(self, items: List[dict]) -> None:
        for row in self._rows:
            row.destroy()
        self._rows.clear()

        total = len(items)
        self._count.configure(text=f"{total} item" + ("s" if total != 1 else ""))

        if not items:
            self._empty.pack(pady=20)
            return
        self._empty.pack_forget()

        for item in items:
            row = self._build_row(self._list, item)
            row.pack(fill="x", pady=6, padx=6)
            self._rows.append(row)

    def get_scroll_frame(self) -> ctk.CTkScrollableFrame:
        return self._list

    def get_scroll_canvas(self) -> Optional[object]:
        return self._list_canvas

    def _build_row(self, master: ctk.CTkFrame, item: dict) -> ctk.CTkFrame:
        row = ctk.CTkFrame(master, corner_radius=12)
        row.grid_columnconfigure(0, weight=1)

        title = (item.get("title") or "").strip() or (item.get("url") or "Untitled")
        title_label = ctk.CTkLabel(
            row,
            text=title,
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
        )
        title_label.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))

        status = str(item.get("status") or "queued").lower()
        badge = self._build_status_badge(row, status)
        badge.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 6))

        url = ctk.CTkLabel(
            row,
            text=str(item.get("url") or ""),
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 11),
            wraplength=520,
        )
        url.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 6))

        output_label = self._format_output(item)
        output = ctk.CTkLabel(
            row,
            text=output_label,
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 11),
        )
        output.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 10))

        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.grid(row=0, column=1, rowspan=4, sticky="e", padx=12, pady=10)

        item_id = str(item.get("id") or "")
        if self._on_retry and status in ("failed", "cancelled"):
            retry_btn = ctk.CTkButton(
                actions,
                text="Retry",
                width=80,
                command=lambda i=item_id: self._on_retry(i),
            )
            retry_btn.pack(pady=4)

        if self._on_remove and status != "running":
            remove_btn = ctk.CTkButton(
                actions,
                text="Remove",
                width=80,
                command=lambda i=item_id: self._on_remove(i),
            )
            remove_btn.pack(pady=4)

        return row

    @staticmethod
    def _format_output(item: dict) -> str:
        output_paths = item.get("output_paths") or []
        output_dir = item.get("output_dir") or ""
        if output_paths:
            if len(output_paths) == 1:
                return f"File: {output_paths[0]}"
            return f"{len(output_paths)} files • {output_dir}"
        if output_dir:
            return f"Folder: {output_dir}"
        return "Output: Unknown"

    def _build_status_badge(self, master: ctk.CTkFrame, status: str) -> ctk.CTkFrame:
        label = status.title()
        color = self._badge_colors.get(status, ("#555555", "#555555"))
        badge = ctk.CTkFrame(master, corner_radius=10, fg_color=color)
        text = ctk.CTkLabel(
            badge,
            text=label,
            text_color="white",
            font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
        )
        text.pack(padx=10, pady=2)
        return badge

    def _handle_start(self) -> None:
        if self._on_start:
            self._on_start()

    def _handle_stop(self) -> None:
        if self._on_stop:
            self._on_stop()

    def _handle_cancel(self) -> None:
        if self._on_cancel:
            self._on_cancel()

    def _handle_clear(self) -> None:
        if self._on_clear:
            self._on_clear()

    def _handle_clear_completed(self) -> None:
        if self._on_clear_completed:
            self._on_clear_completed()
