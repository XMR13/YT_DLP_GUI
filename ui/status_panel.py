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

        log_label = ctk.CTkLabel(self, text="Status")
        log_label.pack(anchor="w", padx=12, pady=(12, 4))

        self._min_height = min_height
        self._max_height = max_height
        self.log_box = ctk.CTkTextbox(self, height=self._min_height, wrap="word")
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.log_box.configure(state="disabled")

    def set_height(self, height: int) -> None:
        target = max(self._min_height, int(height))
        if self._max_height:
            target = min(self._max_height, target)
        self.log_box.configure(height=target)

    def append(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
