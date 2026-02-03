from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional
import tkinter as tk

import customtkinter as ctk


QueueAction = Callable[[str], None]


@dataclass
class _QueueRowWidget:
    frame: ctk.CTkFrame
    window_id: int
    title: ctk.CTkLabel
    badge: ctk.CTkFrame
    badge_text: ctk.CTkLabel
    url: ctk.CTkLabel
    output: ctk.CTkLabel
    actions: ctk.CTkFrame
    btn_top: ctk.CTkButton
    btn_up: ctk.CTkButton
    btn_down: ctk.CTkButton
    btn_bottom: ctk.CTkButton
    btn_retry: ctk.CTkButton
    btn_remove: ctk.CTkButton
    bound_index: Optional[int] = None


class QueuePage(ctk.CTkFrame):
    ROW_HEIGHT = 170
    ROW_PADDING_Y = 8

    def __init__(
        self,
        master: ctk.CTk,
        on_start: Optional[Callable[[], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
        on_clear: Optional[Callable[[], None]] = None,
        on_clear_completed: Optional[Callable[[], None]] = None,
        on_clear_failed: Optional[Callable[[], None]] = None,
        on_remove: Optional[QueueAction] = None,
        on_retry: Optional[QueueAction] = None,
        on_move_top: Optional[QueueAction] = None,
        on_move_up: Optional[QueueAction] = None,
        on_move_down: Optional[QueueAction] = None,
        on_move_bottom: Optional[QueueAction] = None,
        **kwargs: object,
    ) -> None:
        super().__init__(master, **kwargs)
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_cancel = on_cancel
        self._on_clear = on_clear
        self._on_clear_completed = on_clear_completed
        self._on_clear_failed = on_clear_failed
        self._on_remove = on_remove
        self._on_retry = on_retry
        self._on_move_top = on_move_top
        self._on_move_up = on_move_up
        self._on_move_down = on_move_down
        self._on_move_bottom = on_move_bottom

        self._badge_colors = {
            "queued": ("#455A64", "#455A64"),
            "running": ("#1565C0", "#1565C0"),
            "completed": ("#2E7D32", "#2E7D32"),
            "cancelled": ("#3A3A3A", "#3A3A3A"),
            "failed": ("#B71C1C", "#B71C1C"),
        }
        self._items: List[dict] = []
        self._queued_positions: List[int] = []
        self._queued_lookup: dict[int, int] = {}
        self._row_pool: List[_QueueRowWidget] = []
        self._visible_rows: dict[int, _QueueRowWidget] = {}
        self._empty_label: Optional[ctk.CTkLabel] = None
        self._canvas_configure_job: Optional[str] = None
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

        self._clear_failed_btn = ctk.CTkButton(
            controls,
            text="Clear failed",
            width=100,
            command=self._handle_clear_failed,
        )
        self._clear_failed_btn.pack(side="left", padx=4)

        self._list_container = ctk.CTkFrame(self, corner_radius=8)
        self._list_container.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._list_container.grid_rowconfigure(0, weight=1)
        self._list_container.grid_columnconfigure(0, weight=1)

        self._list_canvas = tk.Canvas(self._list_container, highlightthickness=0, bd=0)
        self._list_canvas.grid(row=0, column=0, sticky="nsew")

        self._list_scrollbar = ctk.CTkScrollbar(
            self._list_container,
            orientation="vertical",
            command=self._on_scrollbar,
        )
        self._list_scrollbar.grid(row=0, column=1, sticky="ns")
        self._list_canvas.configure(yscrollcommand=self._list_scrollbar.set)
        self._list_canvas.bind("<Configure>", self._on_canvas_configure)
        self._apply_canvas_bg()
        try:
            self._list_canvas.configure(yscrollincrement=1)
        except Exception:
            pass

        self._sync_empty_state()

    def set_items(self, items: List[dict]) -> None:
        self._items = list(items)
        total = len(self._items)
        self._count.configure(text=f"{total} item" + ("s" if total != 1 else ""))

        self._queued_positions = [
            idx
            for idx, item in enumerate(self._items)
            if str(item.get("status") or "queued").lower() == "queued"
        ]
        self._queued_lookup = {pos: index for index, pos in enumerate(self._queued_positions)}

        self._sync_empty_state()
        self._update_scrollregion()
        self._ensure_row_pool()

    def get_scroll_frame(self) -> tk.Canvas:
        return self._list_canvas

    def get_scroll_canvas(self) -> Optional[object]:
        return self._list_canvas

    def on_canvas_scroll(self) -> None:
        self._update_visible_rows()

    def _sync_empty_state(self) -> None:
        if self._items:
            if self._empty_label:
                self._empty_label.destroy()
                self._empty_label = None
            return
        if self._empty_label is None:
            self._empty_label = ctk.CTkLabel(
                self._list_container,
                text="Queue is empty.",
                font=ctk.CTkFont("Segoe UI", 13),
            )
            self._empty_label.place(relx=0.5, rely=0.5, anchor="center")

    def _ensure_row_pool(self) -> None:
        height = max(self._list_canvas.winfo_height(), 1)
        visible = max(1, int(height / self.ROW_HEIGHT) + 2)
        while len(self._row_pool) < visible:
            row = self._create_row()
            self._row_pool.append(row)
        self._update_visible_rows()

    def _create_row(self) -> _QueueRowWidget:
        row = ctk.CTkFrame(self._list_canvas, corner_radius=12)
        row.grid_columnconfigure(0, weight=1)
        window_id = self._list_canvas.create_window(
            0,
            0,
            anchor="nw",
            window=row,
            width=max(self._list_canvas.winfo_width(), 1),
        )

        title = ctk.CTkLabel(
            row,
            text="",
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))

        badge = ctk.CTkFrame(row, corner_radius=10)
        badge_text = ctk.CTkLabel(
            badge,
            text="",
            text_color="white",
            font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
        )
        badge_text.pack(padx=10, pady=2)
        badge.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 6))

        url = ctk.CTkLabel(
            row,
            text="",
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 11),
            wraplength=520,
        )
        url.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 6))

        output = ctk.CTkLabel(
            row,
            text="",
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 11),
        )
        output.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 10))

        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.grid(row=0, column=1, rowspan=4, sticky="e", padx=12, pady=10)

        btn_top = ctk.CTkButton(actions, text="Top", width=60)
        btn_up = ctk.CTkButton(actions, text="Up", width=60)
        btn_down = ctk.CTkButton(actions, text="Down", width=60)
        btn_bottom = ctk.CTkButton(actions, text="Bottom", width=60)
        btn_retry = ctk.CTkButton(actions, text="Retry", width=80)
        btn_remove = ctk.CTkButton(actions, text="Remove", width=80)

        return _QueueRowWidget(
            frame=row,
            window_id=window_id,
            title=title,
            badge=badge,
            badge_text=badge_text,
            url=url,
            output=output,
            actions=actions,
            btn_top=btn_top,
            btn_up=btn_up,
            btn_down=btn_down,
            btn_bottom=btn_bottom,
            btn_retry=btn_retry,
            btn_remove=btn_remove,
        )

    def _update_scrollregion(self) -> None:
        total_height = max(1, len(self._items) * self.ROW_HEIGHT + self.ROW_PADDING_Y)
        width = self._list_canvas.winfo_width()
        self._list_canvas.configure(scrollregion=(0, 0, width, total_height))

    def _on_canvas_configure(self, _event: object) -> None:
        if self._canvas_configure_job:
            try:
                self.after_cancel(self._canvas_configure_job)
            except Exception:
                pass
        self._canvas_configure_job = self.after_idle(self._apply_canvas_layout)

    def _apply_canvas_layout(self) -> None:
        self._canvas_configure_job = None
        self._update_scrollregion()
        width = max(self._list_canvas.winfo_width(), 1)
        for row in self._row_pool:
            try:
                self._list_canvas.itemconfigure(row.window_id, width=width)
            except Exception:
                pass
        self._ensure_row_pool()

    def _update_visible_rows(self) -> None:
        if not self._items:
            for row in self._row_pool:
                self._list_canvas.itemconfigure(row.window_id, state="hidden")
                row.bound_index = None
            self._visible_rows.clear()
            return

        y0 = self._list_canvas.canvasy(0)
        height = self._list_canvas.winfo_height()
        start = max(0, int(y0 // self.ROW_HEIGHT))
        end = min(len(self._items), int((y0 + height) // self.ROW_HEIGHT) + 2)

        new_visible: dict[int, _QueueRowWidget] = {}
        pool_index = 0
        for index in range(start, end):
            row = self._row_pool[pool_index]
            pool_index += 1
            self._bind_row(row, index)
            y = index * self.ROW_HEIGHT + self.ROW_PADDING_Y
            self._list_canvas.coords(row.window_id, 0, y)
            self._list_canvas.itemconfigure(row.window_id, state="normal")
            new_visible[index] = row

        for row in self._row_pool[pool_index:]:
            self._list_canvas.itemconfigure(row.window_id, state="hidden")
            row.bound_index = None

        self._visible_rows = new_visible

    def _bind_row(self, row: _QueueRowWidget, index: int) -> None:
        item = self._items[index]
        row.bound_index = index

        title = (item.get("title") or "").strip() or (item.get("url") or "Untitled")
        row.title.configure(text=title)

        status = str(item.get("status") or "queued").lower()
        badge_label = status.title()
        color = self._badge_colors.get(status, ("#555555", "#555555"))
        row.badge.configure(fg_color=color)
        row.badge_text.configure(text=badge_label)

        row.url.configure(text=str(item.get("url") or ""))
        row.output.configure(text=self._format_output(item))

        queued_index = self._queued_lookup.get(index)
        can_move_top = queued_index is not None and queued_index > 0
        can_move_up = can_move_top
        can_move_down = queued_index is not None and queued_index < len(self._queued_positions) - 1
        can_move_bottom = can_move_down
        item_id = str(item.get("id") or "")

        self._sync_actions(
            row,
            status,
            item_id,
            can_move_top=can_move_top,
            can_move_up=can_move_up,
            can_move_down=can_move_down,
            can_move_bottom=can_move_bottom,
        )

    def _sync_actions(
        self,
        row: _QueueRowWidget,
        status: str,
        item_id: str,
        *,
        can_move_top: bool,
        can_move_up: bool,
        can_move_down: bool,
        can_move_bottom: bool,
    ) -> None:
        def show(btn: ctk.CTkButton, enabled: bool = True) -> None:
            btn.configure(state="normal" if enabled else "disabled")
            if not btn.winfo_ismapped():
                btn.pack(pady=4)

        def hide(btn: ctk.CTkButton) -> None:
            if btn.winfo_ismapped():
                btn.pack_forget()

        if status == "queued":
            if self._on_move_top:
                row.btn_top.configure(command=lambda i=item_id: self._on_move_top(i))
                show(row.btn_top, can_move_top)
            else:
                hide(row.btn_top)

            if self._on_move_up:
                row.btn_up.configure(command=lambda i=item_id: self._on_move_up(i))
                show(row.btn_up, can_move_up)
            else:
                hide(row.btn_up)

            if self._on_move_down:
                row.btn_down.configure(command=lambda i=item_id: self._on_move_down(i))
                show(row.btn_down, can_move_down)
            else:
                hide(row.btn_down)

            if self._on_move_bottom:
                row.btn_bottom.configure(command=lambda i=item_id: self._on_move_bottom(i))
                show(row.btn_bottom, can_move_bottom)
            else:
                hide(row.btn_bottom)
        else:
            hide(row.btn_top)
            hide(row.btn_up)
            hide(row.btn_down)
            hide(row.btn_bottom)

        if self._on_retry and status in ("failed", "cancelled"):
            row.btn_retry.configure(command=lambda i=item_id: self._on_retry(i))
            show(row.btn_retry, True)
        else:
            hide(row.btn_retry)

        if self._on_remove and status != "running":
            row.btn_remove.configure(command=lambda i=item_id: self._on_remove(i))
            show(row.btn_remove, True)
        else:
            hide(row.btn_remove)

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

    def _apply_canvas_bg(self) -> None:
        color = self._resolve_color(self._list_container.cget("fg_color"))
        if color:
            try:
                self._list_canvas.configure(bg=color)
            except Exception:
                pass

    @staticmethod
    def _resolve_color(color: object) -> Optional[str]:
        if isinstance(color, (tuple, list)) and len(color) >= 2:
            return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]
        if isinstance(color, str):
            return color
        return None

    def _on_scrollbar(self, *args: object) -> None:
        self._list_canvas.yview(*args)
        self._update_visible_rows()

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

    def _handle_clear_failed(self) -> None:
        if self._on_clear_failed:
            self._on_clear_failed()
