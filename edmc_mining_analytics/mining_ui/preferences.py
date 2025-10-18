"""Preferences pane construction for EDMC Mining Analytics UI."""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING

try:
    import tkinter as tk
    from tkinter import ttk, font as tkfont
except ImportError as exc:  # pragma: no cover - EDMC always provides tkinter
    raise RuntimeError("Tkinter must be available for EDMC plugins") from exc

if TYPE_CHECKING:  # pragma: no cover
    from .main_mining_ui import edmcmaMiningUI

from ..edmc_mining_analytics_version import PLUGIN_REPO_URL, PLUGIN_VERSION, display_version
from .components.button_factory import create_theme_checkbox
from .preferences_discord import create_discord_section
from .preferences_inara import create_inara_section
from .preferences_overlay import create_overlay_section


def build_preferences(ui: "edmcmaMiningUI", parent: tk.Widget) -> tk.Widget:
    frame = tk.Frame(parent, highlightthickness=0, bd=0)

    section_heading_font = tkfont.nametofont("TkDefaultFont").copy()
    section_heading_font.configure(weight="bold")

    header = tk.Frame(frame, highlightthickness=0, bd=0)
    header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
    header.columnconfigure(0, weight=1)

    title = tk.Label(header, text="EDMC Mining Analytics", anchor="w", font=("TkDefaultFont", 10, "bold"))
    title.grid(row=0, column=0, sticky="w")

    version_text = display_version(PLUGIN_VERSION)
    version_label = tk.Label(
        header,
        text=version_text,
        anchor="e",
        cursor="hand2",
        font=("TkDefaultFont", 9, "underline"),
    )
    version_label.grid(row=0, column=1, sticky="e")
    version_label.configure(foreground="#1e90ff")
    version_label.bind("<Button-1>", lambda _evt: webbrowser.open(PLUGIN_REPO_URL))

    frame.columnconfigure(0, weight=1)
    frame.columnconfigure(1, weight=1)

    general_frame = tk.LabelFrame(frame, text="General", font=section_heading_font)
    general_frame.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=(0, 10))
    general_frame.columnconfigure(0, weight=0)
    general_frame.columnconfigure(1, weight=1)

    ui._prefs_bin_var = tk.IntVar(master=general_frame, value=ui._state.histogram_bin_size)
    ui._prefs_bin_var.trace_add("write", ui._on_histogram_bin_change)
    bin_spin = ttk.Spinbox(
        general_frame,
        from_=1,
        to=100,
        textvariable=ui._prefs_bin_var,
        width=6,
    )
    bin_spin.grid(row=0, column=0, sticky="w", pady=(4, 2))

    bin_label = tk.Label(
        general_frame,
        text="Prospecting histogram bin size (%)",
        anchor="w",
    )
    bin_label.grid(row=0, column=0, sticky="w", padx=(80, 0), pady=(4, 2))

    rate_label = tk.Label(
        general_frame,
        text="Tons/hour auto-update interval (seconds)",
        anchor="w",
    )
    rate_label.grid(row=1, column=0, sticky="w", padx=(80, 0), pady=(0, 2))

    ui._prefs_rate_var = tk.IntVar(master=general_frame, value=ui._state.rate_interval_seconds)
    ui._prefs_rate_var.trace_add("write", ui._on_rate_interval_change)
    rate_spin = ttk.Spinbox(
        general_frame,
        from_=5,
        to=3600,
        increment=5,
        textvariable=ui._prefs_rate_var,
        width=6,
    )
    rate_spin.grid(row=1, column=0, sticky="w", pady=(0, 2))

    ui._prefs_auto_unpause_var = tk.BooleanVar(
        master=general_frame, value=ui._state.auto_unpause_on_event
    )
    ui._prefs_auto_unpause_var.trace_add("write", ui._on_auto_unpause_change)
    auto_unpause_cb = create_theme_checkbox(
        general_frame,
        text="Mining event automatically un-pauses the plugin",
        variable=ui._prefs_auto_unpause_var,
    )
    auto_unpause_cb.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 4))
    ui._theme.style_checkbox(auto_unpause_cb)

    ui._prefs_warn_non_metallic_var = tk.BooleanVar(
        master=general_frame,
        value=ui._state.warn_on_non_metallic_ring,
    )
    ui._prefs_warn_non_metallic_var.trace_add("write", ui._on_warn_non_metallic_change)
    warn_non_metallic_cb = create_theme_checkbox(
        general_frame,
        text="Warn on non-metallic rings (helpful when laser mining platinum)",
        variable=ui._prefs_warn_non_metallic_var,
    )
    warn_non_metallic_cb.grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 6))
    ui._theme.style_checkbox(warn_non_metallic_cb)

    reset_cap_btn = ttk.Button(
        general_frame,
        text="Reset inferred cargo estimates",
        command=ui._on_reset_inferred_capacities,
    )
    reset_cap_btn.grid(row=4, column=0, sticky="w", pady=(0, 4))
    ui._reset_capacities_btn = reset_cap_btn

    overlay_frame = create_overlay_section(ui, frame, section_heading_font)
    overlay_frame.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=(0, 10))

    refinement_frame = tk.LabelFrame(frame, text="Refinement Session Logging", font=section_heading_font)
    refinement_frame.grid(row=2, column=0, sticky="nsew", padx=(10, 5), pady=(0, 10))
    refinement_frame.columnconfigure(0, weight=1)

    refinement_desc = tk.Label(
        refinement_frame,
        text=(
            "Historical refinement windows control how far back we capture and average "
            "mining performance for rate calculations."
        ),
        anchor="w",
        justify="left",
        wraplength=400,
    )
    refinement_desc.grid(row=0, column=0, sticky="w", pady=(4, 4))

    ui._prefs_refinement_window_var = tk.IntVar(
        master=refinement_frame, value=ui._state.refinement_lookback_seconds
    )
    ui._prefs_refinement_window_var.trace_add("write", ui._on_refinement_window_change)
    refinement_window_container = tk.Frame(refinement_frame, highlightthickness=0, bd=0)
    refinement_window_container.grid(row=1, column=0, sticky="w", pady=(0, 4))

    ttk.Spinbox(
        refinement_window_container,
        from_=5,
        to=240,
        increment=5,
        textvariable=ui._prefs_refinement_window_var,
        width=6,
    ).grid(row=0, column=0, sticky="w")

    refinement_seconds_label = tk.Label(
        refinement_window_container,
        text="seconds",
        anchor="w",
    )
    refinement_seconds_label.grid(row=0, column=1, sticky="w", padx=(8, 0))

    thresholds_container = tk.Frame(refinement_frame, highlightthickness=0, bd=0)
    thresholds_container.grid(row=2, column=0, sticky="ew", pady=(6, 4))
    thresholds_container.columnconfigure((0, 1, 2), weight=1)

    thresholds_desc = tk.Label(
        thresholds_container,
        text="RPM thresholds control when the RPM card changes colour.",
        anchor="w",
    )
    thresholds_desc.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))

    ui._prefs_rpm_red_var = tk.IntVar(master=thresholds_container, value=ui._state.rpm_threshold_red)
    ui._prefs_rpm_red_var.trace_add("write", ui._on_rpm_threshold_change)
    red_label = tk.Label(thresholds_container, text="Red threshold")
    red_label.grid(row=1, column=0, sticky="w")
    ttk.Spinbox(
        thresholds_container,
        from_=1,
        to=500,
        textvariable=ui._prefs_rpm_red_var,
        width=6,
    ).grid(row=2, column=0, sticky="w")

    ui._prefs_rpm_yellow_var = tk.IntVar(master=thresholds_container, value=ui._state.rpm_threshold_yellow)
    ui._prefs_rpm_yellow_var.trace_add("write", ui._on_rpm_threshold_change)
    yellow_label = tk.Label(thresholds_container, text="Yellow threshold")
    yellow_label.grid(row=1, column=1, sticky="w")
    ttk.Spinbox(
        thresholds_container,
        from_=1,
        to=500,
        textvariable=ui._prefs_rpm_yellow_var,
        width=6,
    ).grid(row=2, column=1, sticky="w")

    ui._prefs_rpm_green_var = tk.IntVar(master=thresholds_container, value=ui._state.rpm_threshold_green)
    ui._prefs_rpm_green_var.trace_add("write", ui._on_rpm_threshold_change)
    green_label = tk.Label(thresholds_container, text="Green threshold")
    green_label.grid(row=1, column=2, sticky="w")
    ttk.Spinbox(
        thresholds_container,
        from_=1,
        to=500,
        textvariable=ui._prefs_rpm_green_var,
        width=6,
    ).grid(row=2, column=2, sticky="w")

    logging_frame = tk.LabelFrame(frame, text="Session Logging", font=section_heading_font)
    logging_frame.grid(row=2, column=1, sticky="nsew", padx=(5, 10), pady=(0, 10))
    logging_frame.columnconfigure(0, weight=1)

    logging_desc = tk.Label(
        logging_frame,
        text="Persist session data for post-run analysis and Discord summaries.",
        anchor="w",
        justify="left",
        wraplength=400,
    )
    logging_desc.grid(row=0, column=0, sticky="w", pady=(4, 4))

    ui._prefs_session_logging_var = tk.BooleanVar(
        master=logging_frame,
        value=ui._state.session_logging_enabled,
    )
    ui._prefs_session_logging_var.trace_add("write", ui._on_session_logging_change)
    session_logging_cb = create_theme_checkbox(
        logging_frame,
        text="Enable session logging",
        variable=ui._prefs_session_logging_var,
    )
    session_logging_cb.grid(row=1, column=0, sticky="w", pady=(0, 4))
    ui._theme.style_checkbox(session_logging_cb)
    ui._send_summary_cb = session_logging_cb

    retention_container = tk.Frame(logging_frame, highlightthickness=0, bd=0)
    retention_container.grid(row=2, column=0, sticky="w", pady=(4, 0))

    ui._prefs_session_retention_var = tk.IntVar(
        master=retention_container, value=ui._state.session_log_retention
    )
    ui._prefs_session_retention_var.trace_add("write", ui._on_session_retention_change)
    retention_spin = ttk.Spinbox(
        retention_container,
        from_=1,
        to=500,
        increment=1,
        width=6,
        textvariable=ui._prefs_session_retention_var,
    )
    retention_spin.grid(row=0, column=0, sticky="w", padx=(0, 8))

    retention_label = tk.Label(retention_container, text="Sessions to retain")
    retention_label.grid(row=0, column=1, sticky="w")

    session_path_container = tk.Frame(logging_frame, highlightthickness=0, bd=0)
    session_path_container.grid(row=3, column=0, sticky="w", pady=(6, 10))

    copy_session_path_btn = ttk.Button(
        session_path_container,
        text="Copy session log folder location",
        command=ui._copy_session_log_path,
    )
    copy_session_path_btn.grid(row=0, column=0, sticky="w")

    ui._session_path_feedback = tk.StringVar(master=session_path_container, value="")
    session_path_feedback_label = tk.Label(
        session_path_container,
        textvariable=ui._session_path_feedback,
        anchor="w",
    )
    session_path_feedback_label.grid(row=0, column=1, sticky="w", padx=(8, 0))

    discord_frame = create_discord_section(ui, frame, section_heading_font)
    discord_frame.grid(row=3, column=0, sticky="nsew", padx=(10, 5), pady=(0, 10))

    inara_frame = create_inara_section(ui, frame, section_heading_font)
    inara_frame.grid(row=3, column=1, sticky="nsew", padx=(5, 10), pady=(0, 10))

    return frame


__all__ = ["build_preferences"]
