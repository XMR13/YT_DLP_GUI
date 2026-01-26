import customtkinter as ctk


class Header(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk, **kwargs: object) -> None:
        super().__init__(master, corner_radius=18, **kwargs)
        title = ctk.CTkLabel(
            self,
            text="yt-dlp GUI",
            font=ctk.CTkFont("Segoe UI", 26, weight="bold"),
        )
        title.pack(anchor="w", padx=18, pady=(16, 4))

        subtitle = ctk.CTkLabel(
            self,
            text="Simple downloads with format and resolution selection",
            font=ctk.CTkFont("Segoe UI", 13),
        )
        subtitle.pack(anchor="w", padx=18, pady=(0, 16))
