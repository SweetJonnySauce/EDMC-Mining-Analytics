"""Overlay preferences section for EDMC Mining Analytics."""

from __future__ import annotations

from typing import TYPE_CHECKING

try:
    import tkinter as tk
    from tkinter import ttk, font as tkfont
except ImportError as exc:  # pragma: no cover - EDMC always provides tkinter
    raise RuntimeError("Tkinter must be available for EDMC plugins") from exc

from ..integrations.edmcoverlay import is_overlay_available

if TYPE_CHECKING:  # pragma: no cover
    from .main_mining_ui import edmcmaMiningUI


def create_overlay_section(
    ui: "edmcmaMiningUI",
    parent: tk.Widget,
    heading_font: tkfont.Font,
) -> tk.LabelFrame:
    """Build and return the overlay settings section."""

    ui._state.overlay_available = is_overlay_available()

    frame = tk.LabelFrame(parent, text="Overlay", font=heading_font)
    frame.columnconfigure(0, weight=0)
    frame.columnconfigure(1, weight=1)

    ui._prefs_overlay_enabled_var = tk.BooleanVar(
        master=frame,
        value=ui._state.overlay_enabled,
    )
    ui._prefs_overlay_enabled_var.trace_add("write", ui._on_overlay_enabled_change)
    overlay_enable_cb = ttk.Checkbutton(
        frame,
        text="Enable EDMCOverlay metrics",
        variable=ui._prefs_overlay_enabled_var,
    )
    overlay_enable_cb.grid(row=0, column=0, columnspan=2, sticky="w", pady=(6, 4))

    x_label = tk.Label(
        frame,
        text="Anchor X (px from left)",
        anchor="w",
    )
    x_label.grid(row=1, column=1, sticky="w", padx=(8, 0))

    ui._prefs_overlay_x_var = tk.IntVar(master=frame, value=ui._state.overlay_anchor_x)
    ui._prefs_overlay_x_var.trace_add("write", ui._on_overlay_anchor_x_change)
    overlay_x_spin = ttk.Spinbox(
        frame,
        from_=0,
        to=4000,
        textvariable=ui._prefs_overlay_x_var,
        width=6,
    )
    overlay_x_spin.grid(row=1, column=0, sticky="w", padx=(0, 8))

    y_label = tk.Label(
        frame,
        text="Anchor Y (px from top)",
        anchor="w",
    )
    y_label.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(0, 2))

    ui._prefs_overlay_y_var = tk.IntVar(master=frame, value=ui._state.overlay_anchor_y)
    ui._prefs_overlay_y_var.trace_add("write", ui._on_overlay_anchor_y_change)
    overlay_y_spin = ttk.Spinbox(
        frame,
        from_=0,
        to=4000,
        textvariable=ui._prefs_overlay_y_var,
        width=6,
    )
    overlay_y_spin.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(0, 2))

    overlay_hint = tk.Label(
        frame,
        text="",
        anchor="w",
        justify="left",
        wraplength=380,
    )
    overlay_hint.grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 4))

    interval_label = tk.Label(
        frame,
        text="Refresh interval (milliseconds)",
        anchor="w",
    )
    interval_label.grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(0, 2))

    ui._prefs_overlay_interval_var = tk.IntVar(
        master=frame,
        value=ui._state.overlay_refresh_interval_ms,
    )
    ui._prefs_overlay_interval_var.trace_add("write", ui._on_overlay_interval_change)
    overlay_interval_spin = ttk.Spinbox(
        frame,
        from_=100,
        to=60000,
        increment=100,
        textvariable=ui._prefs_overlay_interval_var,
        width=6,
    )
    overlay_interval_spin.grid(row=3, column=0, sticky="w", padx=(0, 8), pady=(0, 2))

    ui._overlay_controls = [overlay_enable_cb, overlay_x_spin, overlay_y_spin, overlay_interval_spin]
    ui._overlay_hint_label = overlay_hint
    ui._update_overlay_controls()

    return frame
