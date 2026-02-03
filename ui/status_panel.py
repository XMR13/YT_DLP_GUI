import customtkinter as ctk


class StatusPanel(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTk,
        min_height: int = 160,
        max_height: int = 260,
        **kwargs: object,
    ) -> None:
        super().__init__(master, corner_radius=12, **kwargs)

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)

        log_label = ctk.CTkLabel(self, text="Status")
        log_label.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

        self.queue_label = ctk.CTkLabel(
            self,
            text="Queue: 0",
            font=ctk.CTkFont("Segoe UI", 11),
            anchor="e",
        )
        self.queue_label.grid(row=0, column=1, sticky="e", padx=12, pady=(12, 4))

        self.activity_label = ctk.CTkLabel(
            self,
            text="Now: Idle",
            font=ctk.CTkFont("Segoe UI", 11),
            anchor="w",
        )
        self.activity_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 6))

        self._min_height = min_height
        self._max_height = max_height
        self.log_box = ctk.CTkTextbox(self, height=self._min_height, wrap="word")
        self.log_box.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.log_box.configure(state="disabled")

    def set_height(self, height: int) -> None:
        target = max(self._min_height, int(height))
        if self._max_height:
            target = min(self._max_height, target)
        # Avoid unnecessary re-layout churn during window resizing.
        try:
            current = int(self.log_box.cget("height"))
        except Exception:
            current = None
        if current is not None and current == target:
            return
        self.log_box.configure(height=target)

    def append(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def set_queue_summary(self, text: str) -> None:
        self.queue_label.configure(text=text)

    def set_activity(self, text: str) -> None:
        self.activity_label.configure(text=text)
