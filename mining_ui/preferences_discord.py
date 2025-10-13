"""Discord preferences section for EDMC Mining Analytics."""

from __future__ import annotations

from typing import TYPE_CHECKING

try:
    import tkinter as tk
    from tkinter import ttk, font as tkfont
except ImportError as exc:  # pragma: no cover - EDMC always provides tkinter
    raise RuntimeError("Tkinter must be available for EDMC plugins") from exc

if TYPE_CHECKING:  # pragma: no cover
    from .main_mining_ui import edmcmaMiningUI


def create_discord_section(
    ui: "edmcmaMiningUI",
    parent: tk.Widget,
    heading_font: tkfont.Font,
) -> tk.LabelFrame:
    """Build and return the Discord summary preferences section."""

    frame = tk.LabelFrame(parent, text="Discord summary", font=heading_font)
    frame.columnconfigure(0, weight=1)
    ui._theme.register(frame)

    ui._prefs_send_summary_var = tk.BooleanVar(
        master=frame,
        value=ui._state.send_summary_to_discord,
    )
    ui._prefs_send_summary_var.trace_add("write", ui._on_send_summary_change)
    send_summary_cb = ttk.Checkbutton(
        frame,
        text="Send session summary to Discord",
        variable=ui._prefs_send_summary_var,
    )
    send_summary_cb.grid(row=0, column=0, sticky="w", pady=(4, 4))
    ui._theme.register(send_summary_cb)
    ui._send_summary_cb = send_summary_cb

    webhook_label = tk.Label(
        frame,
        text="Discord webhook URL",
        anchor="w",
    )
    webhook_label.grid(row=1, column=0, sticky="w", pady=(0, 2))
    ui._theme.register(webhook_label)

    ui._prefs_webhook_var = tk.StringVar(master=frame)
    ui._updating_webhook_var = True
    ui._prefs_webhook_var.set(ui._state.discord_webhook_url)
    ui._updating_webhook_var = False
    ui._prefs_webhook_var.trace_add("write", ui._on_webhook_change)
    webhook_entry = ttk.Entry(
        frame,
        textvariable=ui._prefs_webhook_var,
        width=60,
    )
    webhook_entry.grid(row=2, column=0, sticky="ew", pady=(0, 6))
    ui._theme.register(webhook_entry)

    images_label = tk.Label(
        frame,
        text="Discord images (optional, leave ship blank for Any)",
        anchor="w",
    )
    images_label.grid(row=3, column=0, sticky="w", pady=(0, 2))
    ui._theme.register(images_label)

    images_container = tk.Frame(frame, highlightthickness=0, bd=0)
    images_container.grid(row=4, column=0, sticky="nsew", pady=(0, 6))
    ui._theme.register(images_container)
    images_container.columnconfigure(0, weight=1)
    images_container.rowconfigure(0, weight=1)

    ui._discord_image_ship_var = tk.StringVar(master=frame, value="")
    ui._discord_image_url_var = tk.StringVar(master=frame, value="")

    images_tree = ttk.Treeview(
        images_container,
        columns=("ship", "url"),
        show="headings",
        height=4,
    )
    images_tree.heading("ship", text="Ship")
    images_tree.heading("url", text="Image URL")
    images_tree.column("ship", width=120, anchor="w")
    images_tree.column("url", anchor="w")
    images_tree.grid(row=0, column=0, columnspan=3, sticky="nsew")
    ui._theme.register(images_tree)

    images_scroll = ttk.Scrollbar(images_container, orient="vertical", command=images_tree.yview)
    images_scroll.grid(row=0, column=3, sticky="ns", padx=(4, 0))
    images_tree.configure(yscrollcommand=images_scroll.set)
    ui._theme.register(images_scroll)

    form = tk.Frame(images_container, highlightthickness=0, bd=0)
    form.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 0))
    ui._theme.register(form)
    form.columnconfigure(1, weight=1)

    ship_label = tk.Label(form, text="Ship name", anchor="w")
    ship_label.grid(row=0, column=0, sticky="w", padx=(0, 8))
    ui._theme.register(ship_label)
    ship_entry = ttk.Entry(form, textvariable=ui._discord_image_ship_var, width=20)
    ship_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
    ui._theme.register(ship_entry)

    url_label = tk.Label(form, text="Image URL", anchor="w")
    url_label.grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(4, 0))
    ui._theme.register(url_label)
    url_entry = ttk.Entry(form, textvariable=ui._discord_image_url_var, width=50)
    url_entry.grid(row=1, column=1, sticky="ew", pady=(4, 0), padx=(0, 8))
    ui._theme.register(url_entry)

    button_frame = tk.Frame(form, highlightthickness=0, bd=0)
    button_frame.grid(row=0, column=2, rowspan=2, sticky="ns")
    ui._theme.register(button_frame)

    add_button = ttk.Button(button_frame, text="Add", command=ui._on_discord_image_add)
    add_button.grid(row=0, column=0, sticky="ew", pady=(0, 4))
    ui._theme.register(add_button)

    remove_button = ttk.Button(button_frame, text="Delete selected", command=ui._on_discord_image_delete)
    remove_button.grid(row=1, column=0, sticky="ew")
    ui._theme.register(remove_button)

    ui._discord_images_tree = images_tree
    ui._refresh_discord_image_list()

    ui._prefs_send_reset_summary_var = tk.BooleanVar(
        master=frame,
        value=ui._state.send_reset_summary,
    )
    ui._prefs_send_reset_summary_var.trace_add("write", ui._on_send_reset_summary_change)
    send_reset_summary_cb = ttk.Checkbutton(
        frame,
        text="Send Discord summary when resetting session",
        variable=ui._prefs_send_reset_summary_var,
    )
    send_reset_summary_cb.grid(row=5, column=0, sticky="w", pady=(0, 4))
    ui._theme.register(send_reset_summary_cb)
    ui._send_reset_summary_cb = send_reset_summary_cb

    test_btn = ttk.Button(
        frame,
        text="Test webhook",
        command=ui._on_test_webhook,
    )
    test_btn.grid(row=6, column=0, sticky="w", pady=(0, 6))
    ui._theme.register(test_btn)
    ui._test_webhook_btn = test_btn

    ui._update_discord_controls()

    return frame


__all__ = ["create_discord_section"]
