from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from typing import Callable, List, Optional, Set
import tkinter as tk

import customtkinter as ctk


QueueAction = Callable[[str], None]
QueueMoveAction = Callable[[str, int], None]
QueueBulkAction = Callable[[List[str]], None]
QueueBulkMoveAction = Callable[[List[str]], None]


@dataclass
class _DragCandidate:
    item_id: str
    start_x: int
    start_y: int
    source_index: int
    source_queued_index: int


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
    btn_retry: ctk.CTkButton
    btn_remove: ctk.CTkButton
    bound_index: Optional[int] = None


class QueuePage(ctk.CTkFrame):
    ROW_HEIGHT = 170
    ROW_PADDING_Y = 8
    DRAG_THRESHOLD = 6
    DRAG_SCROLL_MARGIN = 36
    DRAG_SCROLL_STEP = 3

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
        on_bulk_remove: Optional[QueueBulkAction] = None,
        on_bulk_retry: Optional[QueueBulkAction] = None,
        on_bulk_move_top: Optional[QueueBulkMoveAction] = None,
        on_bulk_move_bottom: Optional[QueueBulkMoveAction] = None,
        on_move_to_index: Optional[QueueMoveAction] = None,
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
        self._on_bulk_remove = on_bulk_remove
        self._on_bulk_retry = on_bulk_retry
        self._on_bulk_move_top = on_bulk_move_top
        self._on_bulk_move_bottom = on_bulk_move_bottom
        self._on_move_to_index = on_move_to_index

        self._badge_colors = {
            "queued": ("#455A64", "#455A64"),
            "running": ("#1565C0", "#1565C0"),
            "completed": ("#2E7D32", "#2E7D32"),
            "cancelled": ("#3A3A3A", "#3A3A3A"),
            "failed": ("#B71C1C", "#B71C1C"),
        }
        self._badge_labels = {
            "queued": "Queued",
            "running": "Running",
            "completed": "Done",
            "cancelled": "Canceled",
            "failed": "Failed",
        }
        self._row_color = ("#F2F2F2", "#2B2B2B")
        self._selected_color = ("#D8D8D8", "#3A3A3A")
        self._filter_var = ctk.StringVar(value="All")
        self._filter_values = ["All", "Queued", "Running", "Failed", "Cancelled", "Done"]
        self._all_items: List[dict] = []
        self._items: List[dict] = []
        self._queued_positions: List[int] = []
        self._queued_lookup: dict[int, int] = {}
        self._selected_ids: Set[str] = set()
        self._selection_order: List[str] = []
        self._row_pool: List[_QueueRowWidget] = []
        self._visible_rows: dict[int, _QueueRowWidget] = {}
        self._empty_label: Optional[ctk.CTkLabel] = None
        self._canvas_configure_job: Optional[str] = None
        self._drag_candidate: Optional[_DragCandidate] = None
        self._drag_active = False
        self._drag_item_id: Optional[str] = None
        self._drag_source_queued_index: Optional[int] = None
        self._drag_target_slot: Optional[int] = None
        self._drag_indicator_id: Optional[int] = None
        self._drag_scroll_job: Optional[str] = None
        self._drag_pointer_y_widget: Optional[int] = None
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

        filter_bar = ctk.CTkFrame(self, fg_color="transparent")
        filter_bar.pack(fill="x", padx=6, pady=(0, 6))
        filter_label = ctk.CTkLabel(
            filter_bar,
            text="Filter:",
            font=ctk.CTkFont("Segoe UI", 12),
        )
        filter_label.pack(side="left", padx=(6, 8))
        self._filter_segment = ctk.CTkSegmentedButton(
            filter_bar,
            values=self._filter_values,
            variable=self._filter_var,
            command=self._on_filter_change,
        )
        self._filter_segment.pack(side="left")

        self._selection_bar = ctk.CTkFrame(self, fg_color="transparent")
        self._selection_label = ctk.CTkLabel(
            self._selection_bar,
            text="0 selected",
            font=ctk.CTkFont("Segoe UI", 12),
        )
        self._selection_label.pack(side="left", padx=(6, 12))

        self._bulk_retry_btn = ctk.CTkButton(
            self._selection_bar,
            text="Retry selected",
            width=120,
            command=self._handle_bulk_retry,
        )
        self._bulk_retry_btn.pack(side="left", padx=4)

        self._bulk_move_top_btn = ctk.CTkButton(
            self._selection_bar,
            text="Move to top",
            width=110,
            command=self._handle_bulk_move_top,
        )
        self._bulk_move_top_btn.pack(side="left", padx=4)

        self._bulk_move_bottom_btn = ctk.CTkButton(
            self._selection_bar,
            text="Move to bottom",
            width=130,
            command=self._handle_bulk_move_bottom,
        )
        self._bulk_move_bottom_btn.pack(side="left", padx=4)

        self._bulk_remove_btn = ctk.CTkButton(
            self._selection_bar,
            text="Remove selected",
            width=130,
            command=self._handle_bulk_remove,
        )
        self._bulk_remove_btn.pack(side="left", padx=4)

        self._clear_selection_btn = ctk.CTkButton(
            self._selection_bar,
            text="Clear selection",
            width=130,
            command=self.clear_selection,
        )
        self._clear_selection_btn.pack(side="left", padx=4)

        self.progress = ctk.CTkProgressBar(self, height=8)
        self.progress.pack(fill="x", padx=12, pady=(0, 6))
        self.progress.set(0)
        self.progress_label = ctk.CTkLabel(self, text="Idle")
        self.progress_label.pack(anchor="w", padx=12, pady=(0, 8))

        self._list_container = ctk.CTkFrame(self, corner_radius=8)
        self._list_container.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._list_container.grid_rowconfigure(0, weight=1)
        self._list_container.grid_columnconfigure(0, weight=1)

        self._list_canvas = tk.Canvas(self._list_container, highlightthickness=0, bd=0)
        self._list_canvas.grid(row=0, column=0, sticky="nsew")
        self._list_canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self._list_canvas.bind("<B1-Motion>", self._on_canvas_motion)
        self._list_canvas.bind("<ButtonRelease-1>", self._on_canvas_release)

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
        self._all_items = list(items)
        self._apply_filter()

    def _apply_filter(self) -> None:
        label = (self._filter_var.get() or "All").strip()
        key = label.lower()
        if key == "all":
            self._items = list(self._all_items)
        elif key == "done":
            self._items = [item for item in self._all_items if str(item.get("status") or "").lower() == "completed"]
        else:
            self._items = [
                item for item in self._all_items if str(item.get("status") or "").lower() == key
            ]
        total = len(self._all_items)
        filtered = len(self._items)
        counts = {"queued": 0, "running": 0, "completed": 0, "failed": 0, "cancelled": 0}
        for item in self._all_items:
            status = str(item.get("status") or "queued").lower()
            if status in counts:
                counts[status] += 1
        parts: List[str] = []
        for label, key in (
            ("queued", "queued"),
            ("running", "running"),
            ("done", "completed"),
            ("failed", "failed"),
            ("cancelled", "cancelled"),
        ):
            count = counts[key]
            if count:
                parts.append(f"{count} {label}")
        if total == 0:
            text = "0 items"
        else:
            text = f"{total} item" + ("s" if total != 1 else "")
            if parts:
                text = f"{text} • " + " • ".join(parts)
            if key != "all":
                text = f"{text} • Filter: {label} ({filtered})"
        self._count.configure(text=text)

        self._queued_positions = [
            idx
            for idx, item in enumerate(self._items)
            if str(item.get("status") or "queued").lower() == "queued"
        ]
        self._queued_lookup = {pos: index for index, pos in enumerate(self._queued_positions)}
        self._sync_selection_with_items()
        if self._drag_active and self._drag_item_id:
            self._sync_drag_source()

        self._sync_empty_state()
        self._update_scrollregion()
        self._ensure_row_pool()
        self._sync_selection_bar()

    def _on_filter_change(self, _value: str) -> None:
        self._apply_filter()

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
            message = "Queue is empty."
            if self._all_items:
                label = (self._filter_var.get() or "All").strip()
                message = f"No items in {label}."
            self._empty_label = ctk.CTkLabel(
                self._list_container,
                text=message,
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

        btn_retry = ctk.CTkButton(actions, text="Retry", width=80)
        btn_remove = ctk.CTkButton(actions, text="Remove", width=80)

        row_widget = _QueueRowWidget(
            frame=row,
            window_id=window_id,
            title=title,
            badge=badge,
            badge_text=badge_text,
            url=url,
            output=output,
            actions=actions,
            btn_retry=btn_retry,
            btn_remove=btn_remove,
        )
        self._bind_drag_sources(row_widget)
        return row_widget

    def _bind_drag_sources(self, row: _QueueRowWidget) -> None:
        if not self._on_move_to_index:
            return
        widgets = [row.frame, row.title, row.badge, row.badge_text, row.url, row.output]
        for widget in widgets:
            widget.bind("<ButtonPress-1>", lambda event, r=row: self._on_row_press(event, r))
            widget.bind("<B1-Motion>", lambda event, r=row: self._on_row_motion(event, r))
            widget.bind("<ButtonRelease-1>", lambda event, r=row: self._on_row_release(event, r))
            try:
                widget.configure(cursor="hand2")
            except Exception:
                pass

    def _on_canvas_press(self, event: tk.Event) -> None:
        if not self._on_move_to_index:
            return
        index = int(self._list_canvas.canvasy(event.y) // self.ROW_HEIGHT)
        if index < 0 or index >= len(self._items):
            return
        item = self._items[index]
        if str(item.get("status") or "queued").lower() != "queued":
            return
        if len(self._queued_positions) <= 1:
            return
        item_id = str(item.get("id") or "")
        if not item_id:
            return
        source_queued_index = self._queued_lookup.get(index)
        if source_queued_index is None:
            return
        self._drag_candidate = _DragCandidate(
            item_id=item_id,
            start_x=event.x_root,
            start_y=event.y_root,
            source_index=index,
            source_queued_index=source_queued_index,
        )
        self._drag_pointer_y_widget = self._event_y_widget(event)

    def _on_canvas_motion(self, event: tk.Event) -> None:
        self._on_row_motion(event, None)  # type: ignore[arg-type]

    def _on_canvas_release(self, event: tk.Event) -> None:
        if self._drag_candidate:
            self._on_row_release(event, None)  # type: ignore[arg-type]
            return
        index = int(self._list_canvas.canvasy(event.y) // self.ROW_HEIGHT)
        if index < 0 or index >= len(self._items):
            self.clear_selection()
            return
        self._toggle_select(index)

    def _on_row_press(self, event: tk.Event, row: _QueueRowWidget) -> None:
        if not self._on_move_to_index:
            return
        index = row.bound_index
        if index is None:
            return
        item = self._items[index]
        if str(item.get("status") or "queued").lower() != "queued":
            return
        if len(self._queued_positions) <= 1:
            return
        item_id = str(item.get("id") or "")
        if not item_id:
            return
        source_queued_index = self._queued_lookup.get(index)
        if source_queued_index is None:
            return
        self._drag_candidate = _DragCandidate(
            item_id=item_id,
            start_x=event.x_root,
            start_y=event.y_root,
            source_index=index,
            source_queued_index=source_queued_index,
        )
        self._drag_pointer_y_widget = self._event_y_widget(event)

    def _on_row_motion(self, event: tk.Event, _row: _QueueRowWidget) -> None:
        if not self._drag_candidate:
            return
        self._drag_pointer_y_widget = self._event_y_widget(event)
        if not self._drag_active:
            dx = abs(event.x_root - self._drag_candidate.start_x)
            dy = abs(event.y_root - self._drag_candidate.start_y)
            if max(dx, dy) < self.DRAG_THRESHOLD:
                return
            self._begin_drag()
        self._update_drag_indicator()

    def _on_row_release(self, event: tk.Event, _row: _QueueRowWidget) -> None:
        row = _row
        if not self._drag_candidate:
            if row and row.bound_index is not None:
                self._toggle_select(row.bound_index)
            return
        self._drag_pointer_y_widget = self._event_y_widget(event)
        if not self._drag_active:
            self._drag_candidate = None
            if row and row.bound_index is not None:
                self._toggle_select(row.bound_index)
            return
        self._finish_drag()

    def _event_y_widget(self, event: tk.Event) -> int:
        return int(event.y_root - self._list_canvas.winfo_rooty())

    def _begin_drag(self) -> None:
        if not self._drag_candidate:
            return
        self._drag_active = True
        self._drag_item_id = self._drag_candidate.item_id
        self._drag_source_queued_index = self._drag_candidate.source_queued_index
        self._drag_target_slot = None
        try:
            self._list_canvas.configure(cursor="fleur")
        except Exception:
            pass
        self._start_drag_scroll()

    def _finish_drag(self) -> None:
        item_id = self._drag_item_id
        source_index = self._drag_source_queued_index
        slot = self._queued_slot_for_pointer()
        total = len(self._queued_positions)
        if (
            item_id
            and slot is not None
            and source_index is not None
            and total > 1
            and self._on_move_to_index
        ):
            target_index = self._target_index_from_slot(slot, source_index, total)
            if target_index != source_index:
                self._on_move_to_index(item_id, target_index)
        self._cancel_drag()

    def _cancel_drag(self) -> None:
        self._drag_candidate = None
        self._drag_active = False
        self._drag_item_id = None
        self._drag_source_queued_index = None
        self._drag_target_slot = None
        self._drag_pointer_y_widget = None
        if self._drag_scroll_job:
            try:
                self.after_cancel(self._drag_scroll_job)
            except Exception:
                pass
            self._drag_scroll_job = None
        self._hide_drag_indicator()
        try:
            self._list_canvas.configure(cursor="")
        except Exception:
            pass

    def _sync_drag_source(self) -> None:
        if not self._drag_item_id:
            return
        for index, item in enumerate(self._items):
            if str(item.get("id") or "") == self._drag_item_id:
                self._drag_source_queued_index = self._queued_lookup.get(index)
                return
        self._cancel_drag()

    def _start_drag_scroll(self) -> None:
        if self._drag_scroll_job:
            return
        self._drag_scroll_job = self.after(16, self._drag_scroll_tick)

    def _drag_scroll_tick(self) -> None:
        if not self._drag_active:
            self._drag_scroll_job = None
            return
        height = max(self._list_canvas.winfo_height(), 1)
        y_widget = self._drag_pointer_y_widget
        if y_widget is None:
            y_widget = 0
        y_widget = max(0, min(y_widget, height))
        scroll_step = 0
        if y_widget < self.DRAG_SCROLL_MARGIN:
            scroll_step = -self.DRAG_SCROLL_STEP
        elif y_widget > height - self.DRAG_SCROLL_MARGIN:
            scroll_step = self.DRAG_SCROLL_STEP
        if scroll_step:
            self._list_canvas.yview_scroll(scroll_step, "units")
            self._update_visible_rows()
        self._update_drag_indicator()
        self._drag_scroll_job = self.after(16, self._drag_scroll_tick)

    def _queued_slot_for_pointer(self) -> Optional[int]:
        if not self._queued_positions:
            return None
        y_widget = self._drag_pointer_y_widget
        if y_widget is None:
            return None
        y_canvas = self._list_canvas.canvasy(y_widget)
        total_height = len(self._items) * self.ROW_HEIGHT + self.ROW_PADDING_Y
        y_canvas = max(0, min(y_canvas, total_height))
        row_index = int(max(0, min(len(self._items) - 1, (y_canvas - self.ROW_PADDING_Y) // self.ROW_HEIGHT)))
        offset = y_canvas - (row_index * self.ROW_HEIGHT + self.ROW_PADDING_Y)
        before_count = bisect_left(self._queued_positions, row_index)
        is_queued_row = row_index in self._queued_lookup
        if is_queued_row and offset > (self.ROW_HEIGHT / 2):
            slot = before_count + 1
        else:
            slot = before_count
        return max(0, min(slot, len(self._queued_positions)))

    def _target_index_from_slot(self, slot: int, source_index: int, total: int) -> int:
        if total <= 1:
            return source_index
        if slot <= source_index:
            target = slot
        else:
            target = slot - 1
        if target < 0:
            target = 0
        if target >= total:
            target = total - 1
        return target

    def _update_drag_indicator(self) -> None:
        slot = self._queued_slot_for_pointer()
        if slot is None:
            self._hide_drag_indicator()
            return
        if slot != self._drag_target_slot or self._drag_indicator_id is None:
            self._drag_target_slot = slot
            self._draw_drag_indicator(slot)

    def _draw_drag_indicator(self, slot: int) -> None:
        y = self._indicator_y_for_slot(slot)
        if y is None:
            self._hide_drag_indicator()
            return
        width = max(self._list_canvas.winfo_width(), 1)
        x0 = 10
        x1 = max(x0 + 10, width - 10)
        color = "#4FC3F7" if ctk.get_appearance_mode() == "Dark" else "#1E88E5"
        if self._drag_indicator_id is None:
            self._drag_indicator_id = self._list_canvas.create_line(
                x0,
                y,
                x1,
                y,
                fill=color,
                width=3,
            )
        else:
            self._list_canvas.coords(self._drag_indicator_id, x0, y, x1, y)
        try:
            self._list_canvas.tag_raise(self._drag_indicator_id)
        except Exception:
            pass

    def _indicator_y_for_slot(self, slot: int) -> Optional[float]:
        if not self._queued_positions:
            return None
        if slot <= 0:
            target_index = self._queued_positions[0]
            y = target_index * self.ROW_HEIGHT + self.ROW_PADDING_Y - 2
        elif slot >= len(self._queued_positions):
            target_index = self._queued_positions[-1]
            y = target_index * self.ROW_HEIGHT + self.ROW_PADDING_Y + self.ROW_HEIGHT - 2
        else:
            target_index = self._queued_positions[slot]
            y = target_index * self.ROW_HEIGHT + self.ROW_PADDING_Y - 2
        return max(2, y)

    def _hide_drag_indicator(self) -> None:
        if self._drag_indicator_id is None:
            return
        try:
            self._list_canvas.delete(self._drag_indicator_id)
        except Exception:
            pass
        self._drag_indicator_id = None

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
        if self._drag_active and self._drag_target_slot is not None:
            self._draw_drag_indicator(self._drag_target_slot)
        self._ensure_row_pool()

    def _update_visible_rows(self) -> None:
        if not self._items:
            for row in self._row_pool:
                self._list_canvas.itemconfigure(row.window_id, state="hidden")
                row.bound_index = None
            self._visible_rows.clear()
            self._hide_drag_indicator()
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
        badge_label = self._badge_labels.get(status, status.title())
        color = self._badge_colors.get(status, ("#555555", "#555555"))
        row.badge.configure(fg_color=color)
        row.badge_text.configure(text=badge_label)

        row.url.configure(text=str(item.get("url") or ""))
        row.output.configure(text=self._format_output(item))

        item_id = str(item.get("id") or "")

        self._sync_actions(
            row,
            status,
            item_id,
        )
        self._apply_row_state(row, item_id)

    def _sync_actions(
        self,
        row: _QueueRowWidget,
        status: str,
        item_id: str,
    ) -> None:
        def show(btn: ctk.CTkButton, enabled: bool = True) -> None:
            btn.configure(state="normal" if enabled else "disabled")
            if not btn.winfo_ismapped():
                btn.pack(pady=4)

        def hide(btn: ctk.CTkButton) -> None:
            if btn.winfo_ismapped():
                btn.pack_forget()

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

    def _apply_row_state(self, row: _QueueRowWidget, item_id: str) -> None:
        selected = item_id in self._selected_ids
        bg = self._get_selected_bg() if selected else self._get_row_bg()
        row.frame.configure(fg_color=bg)

    def _get_row_bg(self) -> str:
        return self._row_color[1] if ctk.get_appearance_mode() == "Dark" else self._row_color[0]

    def _get_selected_bg(self) -> str:
        return self._selected_color[1] if ctk.get_appearance_mode() == "Dark" else self._selected_color[0]

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

    def _toggle_select(self, index: int) -> None:
        item = self._items[index]
        item_id = str(item.get("id") or "")
        if not item_id:
            return
        if item_id in self._selected_ids:
            self._selected_ids.remove(item_id)
            if item_id in self._selection_order:
                self._selection_order.remove(item_id)
        else:
            self._selected_ids.add(item_id)
            self._selection_order.append(item_id)
        row = self._visible_rows.get(index)
        if row:
            self._apply_row_state(row, item_id)
        self._sync_selection_bar()

    def clear_selection(self) -> None:
        if not self._selected_ids:
            return
        self._selected_ids.clear()
        self._selection_order.clear()
        self._update_visible_rows()
        self._sync_selection_bar()

    def _sync_selection_with_items(self) -> None:
        valid_ids = {str(item.get("id") or "") for item in self._items if item.get("id")}
        if not self._selected_ids:
            return
        self._selected_ids = {item_id for item_id in self._selected_ids if item_id in valid_ids}
        self._selection_order = [item_id for item_id in self._selection_order if item_id in self._selected_ids]

    def _sync_selection_bar(self) -> None:
        count = len(self._selected_ids)
        if count <= 0:
            if self._selection_bar.winfo_ismapped():
                self._selection_bar.pack_forget()
            return
        if not self._selection_bar.winfo_ismapped():
            self._selection_bar.pack(fill="x", padx=6, pady=(0, 6), before=self.progress)
        self._selection_label.configure(text=f"{count} selected")
        status_by_id = {str(item.get("id") or ""): str(item.get("status") or "").lower() for item in self._items}
        retry_enabled = any(
            status_by_id.get(item_id) in ("failed", "cancelled") for item_id in self._selected_ids
        )
        remove_enabled = any(
            status_by_id.get(item_id) != "running" for item_id in self._selected_ids
        )
        move_enabled = any(
            status_by_id.get(item_id) == "queued" for item_id in self._selected_ids
        )
        self._bulk_retry_btn.configure(state="normal" if retry_enabled else "disabled")
        self._bulk_move_top_btn.configure(state="normal" if move_enabled else "disabled")
        self._bulk_move_bottom_btn.configure(state="normal" if move_enabled else "disabled")
        self._bulk_remove_btn.configure(state="normal" if remove_enabled else "disabled")

    def _handle_bulk_retry(self) -> None:
        if self._on_bulk_retry and self._selected_ids:
            self._on_bulk_retry(list(self._selection_order))

    def _handle_bulk_remove(self) -> None:
        if self._on_bulk_remove and self._selected_ids:
            self._on_bulk_remove(list(self._selection_order))

    def _handle_bulk_move_top(self) -> None:
        if self._on_bulk_move_top and self._selected_ids:
            self._on_bulk_move_top(list(self._selection_order))

    def _handle_bulk_move_bottom(self) -> None:
        if self._on_bulk_move_bottom and self._selected_ids:
            self._on_bulk_move_bottom(list(self._selection_order))
