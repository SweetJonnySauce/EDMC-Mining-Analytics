"""Market search preferences section for EDMC Mining Analytics."""

from __future__ import annotations

from typing import TYPE_CHECKING

try:
    import tkinter as tk
    from tkinter import ttk, font as tkfont
except ImportError as exc:  # pragma: no cover - EDMC always provides tkinter
    raise RuntimeError("Tkinter must be available for EDMC plugins") from exc

if TYPE_CHECKING:  # pragma: no cover
    from .main_mining_ui import edmcmaMiningUI


def create_market_search_section(
    ui: "edmcmaMiningUI",
    parent: tk.Widget,
    heading_font: tkfont.Font,
) -> tk.LabelFrame:
    """Build and return the market search preferences section."""

    frame = tk.LabelFrame(parent, text="Market search", font=heading_font)
    frame.columnconfigure(1, weight=1)

    desc = tk.Label(
        frame,
        text="Configure market search filters for estimated sell prices.",
        anchor="w",
        justify="left",
        wraplength=420,
    )
    desc.grid(row=0, column=0, columnspan=2, sticky="w", pady=(4, 8))

    ui._prefs_market_has_large_pad_var = tk.BooleanVar(
        master=frame,
        value=bool(ui._state.market_search_has_large_pad),
    )
    ui._prefs_market_has_large_pad_var.trace_add("write", ui._on_market_has_large_pad_change)
    has_large_pad_cb = ttk.Checkbutton(
        frame,
        text="Has large landing pad",
        variable=ui._prefs_market_has_large_pad_var,
    )
    has_large_pad_cb.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 6))

    ui._prefs_market_include_carriers_var = tk.BooleanVar(
        master=frame,
        value=bool(ui._state.market_search_include_carriers),
    )
    ui._prefs_market_include_carriers_var.trace_add("write", ui._on_market_include_carriers_change)
    carriers_cb = ttk.Checkbutton(
        frame,
        text="Include fleet carriers in results",
        variable=ui._prefs_market_include_carriers_var,
    )
    carriers_cb.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 4))

    ui._prefs_market_include_surface_var = tk.BooleanVar(
        master=frame,
        value=bool(ui._state.market_search_include_surface),
    )
    ui._prefs_market_include_surface_var.trace_add("write", ui._on_market_include_surface_change)
    surface_cb = ttk.Checkbutton(
        frame,
        text="Include surface stations in results",
        variable=ui._prefs_market_include_surface_var,
    )
    surface_cb.grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 8))

    sort_label = tk.Label(frame, text="Sort by", anchor="w")
    sort_label.grid(row=4, column=0, sticky="w", pady=(0, 6))

    ui._prefs_market_sort_var = tk.StringVar(master=frame)
    ui._prefs_market_sort_var.set(ui._format_market_sort_label(ui._state.market_search_sort_mode))
    sort_combo = ttk.Combobox(
        frame,
        textvariable=ui._prefs_market_sort_var,
        values=("Best price", "Nearest station"),
        state="readonly",
        width=18,
    )
    sort_combo.grid(row=4, column=1, sticky="w", pady=(0, 6))
    sort_combo.bind("<<ComboboxSelected>>", ui._on_market_sort_change)

    min_demand_label = tk.Label(frame, text="Minimum demand", anchor="w")
    min_demand_label.grid(row=5, column=0, sticky="w", pady=(0, 6))
    ui._prefs_market_min_demand_var = tk.StringVar(
        master=frame,
        value=str(int(ui._state.market_search_min_demand)),
    )
    min_demand_entry = ttk.Entry(
        frame,
        textvariable=ui._prefs_market_min_demand_var,
        width=12,
    )
    min_demand_entry.grid(row=5, column=1, sticky="w", pady=(0, 6))
    min_demand_entry.bind("<FocusOut>", ui._on_market_min_demand_commit)
    min_demand_entry.bind("<Return>", ui._on_market_min_demand_commit)

    age_label = tk.Label(frame, text="Age of market data (days)", anchor="w")
    age_label.grid(row=6, column=0, sticky="w", pady=(0, 6))
    ui._prefs_market_age_days_var = tk.StringVar(
        master=frame,
        value=str(int(ui._state.market_search_age_days)),
    )
    age_entry = ttk.Entry(frame, textvariable=ui._prefs_market_age_days_var, width=12)
    age_entry.grid(row=6, column=1, sticky="w", pady=(0, 6))
    age_entry.bind("<FocusOut>", ui._on_market_age_days_commit)
    age_entry.bind("<Return>", ui._on_market_age_days_commit)

    distance_label = tk.Label(frame, text="Distance (LY)", anchor="w")
    distance_label.grid(row=7, column=0, sticky="w", pady=(0, 6))
    ui._prefs_market_distance_var = tk.StringVar(
        master=frame,
        value=_format_distance(ui._state.market_search_distance_ly),
    )
    distance_entry = ttk.Entry(frame, textvariable=ui._prefs_market_distance_var, width=12)
    distance_entry.grid(row=7, column=1, sticky="w", pady=(0, 6))
    distance_entry.bind("<FocusOut>", ui._on_market_distance_commit)
    distance_entry.bind("<Return>", ui._on_market_distance_commit)

    arrival_label = tk.Label(frame, text="Distance to arrival (Ls)", anchor="w")
    arrival_label.grid(row=8, column=0, sticky="w", pady=(0, 6))
    ui._prefs_market_distance_ls_var = tk.StringVar(
        master=frame,
        value="" if ui._state.market_search_distance_ls is None else _format_distance(ui._state.market_search_distance_ls),
    )
    arrival_entry = ttk.Entry(frame, textvariable=ui._prefs_market_distance_ls_var, width=12)
    arrival_entry.grid(row=8, column=1, sticky="w", pady=(0, 6))
    arrival_entry.bind("<FocusOut>", ui._on_market_distance_ls_commit)
    arrival_entry.bind("<Return>", ui._on_market_distance_ls_commit)

    return frame


def _format_distance(value: float) -> str:
    try:
        distance = float(value)
    except (TypeError, ValueError):
        return "0"
    if distance.is_integer():
        return str(int(distance))
    return str(distance)


__all__ = ["create_market_search_section"]
