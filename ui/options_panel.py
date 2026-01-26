from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class OptionsPanel(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTk,
        format_type_var: ctk.StringVar,
        resolution_var: ctk.StringVar,
        output_dir_var: ctk.StringVar,
        cookies_var: ctk.StringVar,
        js_runtime_var: ctk.StringVar,
        js_runtime_path_var: ctk.StringVar,
        remote_components_var: ctk.StringVar,
        on_choose_output: Callable[[], None],
        on_choose_runtime_path: Callable[[], None],
        **kwargs: object,
    ) -> None:
        super().__init__(master, corner_radius=12, **kwargs)

        format_label = ctk.CTkLabel(self, text="Format")
        format_label.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

        self.format_menu = ctk.CTkOptionMenu(
            self,
            values=["Video + Audio", "Audio only"],
            variable=format_type_var,
        )
        self.format_menu.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

        resolution_label = ctk.CTkLabel(self, text="Resolution / FPS")
        resolution_label.grid(row=0, column=1, sticky="w", padx=12, pady=(12, 4))

        self.resolution_menu = ctk.CTkOptionMenu(
            self,
            values=["Best available"],
            variable=resolution_var,
        )
        self.resolution_menu.grid(row=1, column=1, sticky="ew", padx=12, pady=(0, 12))

        output_label = ctk.CTkLabel(self, text="Output folder")
        output_label.grid(row=0, column=2, sticky="w", padx=12, pady=(12, 4))

        output_frame = ctk.CTkFrame(self, fg_color="transparent")
        output_frame.grid(row=1, column=2, sticky="ew", padx=12, pady=(0, 12))

        output_entry = ctk.CTkEntry(output_frame, textvariable=output_dir_var)
        output_entry.pack(side="left", fill="x", expand=True)

        output_button = ctk.CTkButton(
            output_frame,
            text="Browse",
            command=on_choose_output,
            width=80,
        )
        output_button.pack(side="left", padx=(8, 0))

        cookies_label = ctk.CTkLabel(self, text="Cookies (browser)")
        cookies_label.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 4))

        self.cookies_menu = ctk.CTkOptionMenu(
            self,
            values=["None", "chrome", "edge", "firefox"],
            variable=cookies_var,
        )
        self.cookies_menu.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))

        runtime_label = ctk.CTkLabel(self, text="JS runtime")
        runtime_label.grid(row=2, column=1, sticky="w", padx=12, pady=(0, 4))

        self.runtime_menu = ctk.CTkOptionMenu(
            self,
            values=["Auto", "node", "deno", "bun", "quickjs"],
            variable=js_runtime_var,
        )
        self.runtime_menu.grid(row=3, column=1, sticky="ew", padx=12, pady=(0, 12))

        runtime_path_label = ctk.CTkLabel(self, text="Runtime path (optional)")
        runtime_path_label.grid(row=2, column=2, sticky="w", padx=12, pady=(0, 4))

        runtime_path_frame = ctk.CTkFrame(self, fg_color="transparent")
        runtime_path_frame.grid(row=3, column=2, sticky="ew", padx=12, pady=(0, 12))

        runtime_path_entry = ctk.CTkEntry(runtime_path_frame, textvariable=js_runtime_path_var)
        runtime_path_entry.pack(side="left", fill="x", expand=True)

        runtime_path_button = ctk.CTkButton(
            runtime_path_frame,
            text="Browse",
            command=on_choose_runtime_path,
            width=80,
        )
        runtime_path_button.pack(side="left", padx=(8, 0))

        components_label = ctk.CTkLabel(self, text="EJS scripts source")
        components_label.grid(row=4, column=0, sticky="w", padx=12, pady=(0, 4))

        self.components_menu = ctk.CTkOptionMenu(
            self,
            values=["None", "ejs:github", "ejs:npm"],
            variable=remote_components_var,
        )
        self.components_menu.grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 12))

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=1)
