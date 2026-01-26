import customtkinter as ctk


class StatusPanel(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk, **kwargs: object) -> None:
        super().__init__(master, corner_radius=12, **kwargs)

        log_label = ctk.CTkLabel(self, text="Status")
        log_label.pack(anchor="w", padx=12, pady=(12, 4))

        self.log_box = ctk.CTkTextbox(self, height=160, wrap="word")
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.log_box.configure(state="disabled")

    def append(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
