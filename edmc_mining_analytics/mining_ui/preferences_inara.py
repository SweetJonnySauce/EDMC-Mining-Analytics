"""Inara preferences section for EDMC Mining Analytics."""

from __future__ import annotations

from typing import TYPE_CHECKING

try:
    import tkinter as tk
    from tkinter import ttk, font as tkfont
except ImportError as exc:  # pragma: no cover - EDMC always provides tkinter
    raise RuntimeError("Tkinter must be available for EDMC plugins") from exc

if TYPE_CHECKING:  # pragma: no cover
    from .main_mining_ui import edmcmaMiningUI

from .components.button_factory import create_theme_checkbox


def create_inara_section(
    ui: "edmcmaMiningUI",
    parent: tk.Widget,
    heading_font: tkfont.Font,
) -> tk.LabelFrame:
    """Build and return the Inara link preferences section."""

    frame = tk.LabelFrame(parent, text="Inara Links", font=heading_font)
    frame.columnconfigure(0, weight=1)

    inara_desc = tk.Label(
        frame,
        text="Configure how commodity hyperlinks open Inara searches.",
        anchor="w",
        justify="left",
        wraplength=380,
    )
    inara_desc.grid(row=0, column=0, sticky="w", pady=(4, 6))

    ui._prefs_inara_mode_var = tk.IntVar(master=frame, value=ui._state.inara_settings.search_mode)
    ui._prefs_inara_mode_var.trace_add("write", ui._on_inara_mode_change)
    mode_container = tk.Frame(frame, highlightthickness=0, bd=0)
    mode_container.grid(row=1, column=0, sticky="w", pady=(0, 6))

    ttk.Radiobutton(
        mode_container,
        text="Best price search",
        value=1,
        variable=ui._prefs_inara_mode_var,
    ).grid(row=0, column=0, sticky="w", padx=(0, 12))
    ttk.Radiobutton(
        mode_container,
        text="Distance search",
        value=3,
        variable=ui._prefs_inara_mode_var,
    ).grid(row=0, column=1, sticky="w")

    ui._prefs_inara_carriers_var = tk.BooleanVar(
        master=frame, value=ui._state.inara_settings.include_carriers
    )
    ui._prefs_inara_carriers_var.trace_add("write", ui._on_inara_carriers_change)
    carriers_cb = create_theme_checkbox(
        frame,
        text="Include fleet carriers in results",
        variable=ui._prefs_inara_carriers_var,
    )
    carriers_cb.grid(row=2, column=0, sticky="w", pady=(0, 4))
    ui._theme.style_checkbox(carriers_cb)

    ui._prefs_inara_surface_var = tk.BooleanVar(
        master=frame, value=ui._state.inara_settings.include_surface
    )
    ui._prefs_inara_surface_var.trace_add("write", ui._on_inara_surface_change)
    surface_cb = create_theme_checkbox(
        frame,
        text="Include surface stations in results",
        variable=ui._prefs_inara_surface_var,
    )
    surface_cb.grid(row=3, column=0, sticky="w", pady=(0, 4))
    ui._theme.style_checkbox(surface_cb)

    return frame


__all__ = ["create_inara_section"]
