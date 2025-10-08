"""Preferences pane construction for EDMC Mining Analytics UI."""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError as exc:  # pragma: no cover - EDMC always provides tkinter
    raise RuntimeError("Tkinter must be available for EDMC plugins") from exc

if TYPE_CHECKING:  # pragma: no cover
    from .main_mining_ui import edmcmaMiningUI

from version import PLUGIN_REPO_URL, PLUGIN_VERSION, display_version


def build_preferences(ui: "edmcmaMiningUI", parent: tk.Widget) -> tk.Widget:
    frame = tk.Frame(parent, highlightthickness=0, bd=0)
    ui._theme.register(frame)

    header = tk.Frame(frame, highlightthickness=0, bd=0)
    header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
    header.columnconfigure(0, weight=1)
    ui._theme.register(header)

    title = tk.Label(header, text="EDMC Mining Analytics", anchor="w", font=("TkDefaultFont", 10, "bold"))
    title.grid(row=0, column=0, sticky="w")
    ui._theme.register(title)

    version_text = display_version(PLUGIN_VERSION)
    version_label = tk.Label(
        header,
        text=version_text,
        anchor="e",
        cursor="hand2",
        font=("TkDefaultFont", 9, "underline"),
    )
    version_label.grid(row=0, column=1, sticky="e")
    ui._theme.register(version_label)
    version_label.configure(foreground="#1e90ff")
    version_label.bind("<Button-1>", lambda _evt: webbrowser.open(PLUGIN_REPO_URL))

    general_frame = tk.LabelFrame(frame, text="General")
    general_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
    general_frame.columnconfigure(0, weight=0)
    general_frame.columnconfigure(1, weight=1)
    ui._theme.register(general_frame)

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
    ui._theme.register(bin_label)

    rate_label = tk.Label(
        general_frame,
        text="Tons/hour auto-update interval (seconds)",
        anchor="w",
    )
    rate_label.grid(row=1, column=0, sticky="w", padx=(80, 0), pady=(0, 2))
    ui._theme.register(rate_label)

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
    auto_unpause_cb = ttk.Checkbutton(
        general_frame,
        text="Mining event automatically un-pauses the plugin",
        variable=ui._prefs_auto_unpause_var,
    )
    auto_unpause_cb.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 4))
    ui._theme.register(auto_unpause_cb)

    ui._prefs_warn_non_metallic_var = tk.BooleanVar(
        master=general_frame,
        value=ui._state.warn_on_non_metallic_ring,
    )
    ui._prefs_warn_non_metallic_var.trace_add("write", ui._on_warn_non_metallic_change)
    warn_non_metallic_cb = ttk.Checkbutton(
        general_frame,
        text="Warn on non-metallic rings (helpful when laser mining platinum)",
        variable=ui._prefs_warn_non_metallic_var,
    )
    warn_non_metallic_cb.grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 6))
    ui._theme.register(warn_non_metallic_cb)

    reset_cap_btn = ttk.Button(
        general_frame,
        text="Reset inferred cargo estimates",
        command=ui._on_reset_inferred_capacities,
    )
    reset_cap_btn.grid(row=4, column=0, sticky="w", pady=(0, 4))
    ui._theme.register(reset_cap_btn)
    ui._reset_capacities_btn = reset_cap_btn

    overlay_frame = tk.LabelFrame(frame, text="Overlay")
    overlay_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
    overlay_frame.columnconfigure(0, weight=0)
    overlay_frame.columnconfigure(1, weight=1)
    ui._theme.register(overlay_frame)

    ui._prefs_overlay_enabled_var = tk.BooleanVar(
        master=overlay_frame,
        value=ui._state.overlay_enabled,
    )
    ui._prefs_overlay_enabled_var.trace_add("write", ui._on_overlay_enabled_change)
    overlay_enable_cb = ttk.Checkbutton(
        overlay_frame,
        text="Enable EDMCOverlay metrics",
        variable=ui._prefs_overlay_enabled_var,
    )
    overlay_enable_cb.grid(row=0, column=0, columnspan=2, sticky="w", pady=(6, 4))
    ui._theme.register(overlay_enable_cb)

    x_label = tk.Label(
        overlay_frame,
        text="Anchor X (px from left)",
        anchor="w",
    )
    x_label.grid(row=1, column=0, sticky="w", padx=(0, 8))
    ui._theme.register(x_label)

    ui._prefs_overlay_x_var = tk.IntVar(master=overlay_frame, value=ui._state.overlay_anchor_x)
    ui._prefs_overlay_x_var.trace_add("write", ui._on_overlay_anchor_x_change)
    overlay_x_spin = ttk.Spinbox(
        overlay_frame,
        from_=0,
        to=4000,
        textvariable=ui._prefs_overlay_x_var,
        width=8,
    )
    overlay_x_spin.grid(row=1, column=1, sticky="w")

    y_label = tk.Label(
        overlay_frame,
        text="Anchor Y (px from top)",
        anchor="w",
    )
    y_label.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(4, 0))
    ui._theme.register(y_label)

    ui._prefs_overlay_y_var = tk.IntVar(master=overlay_frame, value=ui._state.overlay_anchor_y)
    ui._prefs_overlay_y_var.trace_add("write", ui._on_overlay_anchor_y_change)
    overlay_y_spin = ttk.Spinbox(
        overlay_frame,
        from_=0,
        to=4000,
        textvariable=ui._prefs_overlay_y_var,
        width=8,
    )
    overlay_y_spin.grid(row=2, column=1, sticky="w", pady=(4, 0))

    overlay_hint = tk.Label(
        overlay_frame,
        text="",
        anchor="w",
        justify="left",
        wraplength=380,
    )
    overlay_hint.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 4))
    ui._theme.register(overlay_hint)
    interval_label = tk.Label(
        overlay_frame,
        text="Refresh interval (milliseconds)",
        anchor="w",
    )
    interval_label.grid(row=4, column=0, sticky="w", padx=(0, 8))
    ui._theme.register(interval_label)

    ui._prefs_overlay_interval_var = tk.IntVar(
        master=overlay_frame,
        value=ui._state.overlay_refresh_interval_ms,
    )
    ui._prefs_overlay_interval_var.trace_add("write", ui._on_overlay_interval_change)
    overlay_interval_spin = ttk.Spinbox(
        overlay_frame,
        from_=200,
        to=60000,
        increment=100,
        textvariable=ui._prefs_overlay_interval_var,
        width=8,
    )
    overlay_interval_spin.grid(row=4, column=1, sticky="w")
    ui._theme.register(overlay_interval_spin)

    ui._overlay_controls = [overlay_enable_cb, overlay_x_spin, overlay_y_spin, overlay_interval_spin]
    ui._overlay_hint_label = overlay_hint
    ui._update_overlay_controls()

    refinement_frame = tk.LabelFrame(frame, text="Refinement Session Logging")
    refinement_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
    refinement_frame.columnconfigure(0, weight=1)
    ui._theme.register(refinement_frame)

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
    ui._theme.register(refinement_desc)

    ui._prefs_refinement_window_var = tk.IntVar(
        master=refinement_frame, value=ui._state.refinement_lookback_seconds
    )
    ui._prefs_refinement_window_var.trace_add("write", ui._on_refinement_window_change)
    ttk.Spinbox(
        refinement_frame,
        from_=5,
        to=240,
        increment=5,
        textvariable=ui._prefs_refinement_window_var,
        width=6,
    ).grid(row=1, column=0, sticky="w", pady=(0, 4))

    thresholds_container = tk.Frame(refinement_frame, highlightthickness=0, bd=0)
    thresholds_container.grid(row=2, column=0, sticky="ew", pady=(6, 4))
    thresholds_container.columnconfigure((0, 1, 2), weight=1)
    ui._theme.register(thresholds_container)

    thresholds_desc = tk.Label(
        thresholds_container,
        text="RPM thresholds control when the RPM card changes colour.",
        anchor="w",
    )
    thresholds_desc.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
    ui._theme.register(thresholds_desc)

    ui._prefs_rpm_red_var = tk.IntVar(master=thresholds_container, value=ui._state.rpm_threshold_red)
    ui._prefs_rpm_red_var.trace_add("write", ui._on_rpm_threshold_change)
    red_label = tk.Label(thresholds_container, text="Red threshold")
    red_label.grid(row=1, column=0, sticky="w")
    ui._theme.register(red_label)
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
    ui._theme.register(yellow_label)
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
    ui._theme.register(green_label)
    ttk.Spinbox(
        thresholds_container,
        from_=1,
        to=500,
        textvariable=ui._prefs_rpm_green_var,
        width=6,
    ).grid(row=2, column=2, sticky="w")

    logging_frame = tk.LabelFrame(frame, text="Session Logging")
    logging_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 10))
    logging_frame.columnconfigure(0, weight=1)
    ui._theme.register(logging_frame)

    logging_desc = tk.Label(
        logging_frame,
        text="Persist session data for post-run analysis and Discord summaries.",
        anchor="w",
        justify="left",
        wraplength=400,
    )
    logging_desc.grid(row=0, column=0, sticky="w", pady=(4, 4))
    ui._theme.register(logging_desc)

    ui._prefs_session_logging_var = tk.BooleanVar(
        master=logging_frame,
        value=ui._state.session_logging_enabled,
    )
    ui._prefs_session_logging_var.trace_add("write", ui._on_session_logging_change)
    session_logging_cb = ttk.Checkbutton(
        logging_frame,
        text="Enable session logging",
        variable=ui._prefs_session_logging_var,
    )
    session_logging_cb.grid(row=1, column=0, sticky="w", pady=(0, 4))
    ui._theme.register(session_logging_cb)
    ui._send_summary_cb = session_logging_cb

    retention_container = tk.Frame(logging_frame, highlightthickness=0, bd=0)
    retention_container.grid(row=2, column=0, sticky="w", pady=(4, 0))
    ui._theme.register(retention_container)

    retention_label = tk.Label(retention_container, text="Sessions to retain")
    retention_label.grid(row=0, column=0, sticky="w", padx=(0, 8))
    ui._theme.register(retention_label)

    ui._prefs_session_retention_var = tk.IntVar(
        master=retention_container, value=ui._state.session_log_retention
    )
    ui._prefs_session_retention_var.trace_add("write", ui._on_session_retention_change)
    ttk.Spinbox(
        retention_container,
        from_=1,
        to=500,
        increment=1,
        width=6,
        textvariable=ui._prefs_session_retention_var,
    ).grid(row=0, column=1, sticky="w")

    session_path_container = tk.Frame(logging_frame, highlightthickness=0, bd=0)
    session_path_container.grid(row=3, column=0, sticky="w", pady=(6, 0))
    ui._theme.register(session_path_container)

    copy_session_path_btn = ttk.Button(
        session_path_container,
        text="Copy session log folder location",
        command=ui._copy_session_log_path,
    )
    copy_session_path_btn.grid(row=0, column=0, sticky="w")
    ui._theme.register(copy_session_path_btn)

    ui._session_path_feedback = tk.StringVar(master=session_path_container, value="")
    session_path_feedback_label = tk.Label(
        session_path_container,
        textvariable=ui._session_path_feedback,
        anchor="w",
    )
    session_path_feedback_label.grid(row=0, column=1, sticky="w", padx=(8, 0))
    ui._theme.register(session_path_feedback_label)

    discord_frame = tk.LabelFrame(frame, text="Discord summary")
    discord_frame.grid(row=5, column=0, sticky="ew", padx=10, pady=(0, 10))
    discord_frame.columnconfigure(0, weight=1)
    ui._theme.register(discord_frame)

    ui._prefs_send_summary_var = tk.BooleanVar(
        master=discord_frame,
        value=ui._state.send_summary_to_discord,
    )
    ui._prefs_send_summary_var.trace_add("write", ui._on_send_summary_change)
    send_summary_cb = ttk.Checkbutton(
        discord_frame,
        text="Send session summary to Discord",
        variable=ui._prefs_send_summary_var,
    )
    send_summary_cb.grid(row=0, column=0, sticky="w", pady=(4, 4))
    ui._theme.register(send_summary_cb)
    ui._send_summary_cb = send_summary_cb

    webhook_label = tk.Label(
        discord_frame,
        text="Discord webhook URL",
        anchor="w",
    )
    webhook_label.grid(row=1, column=0, sticky="w", pady=(0, 2))
    ui._theme.register(webhook_label)

    ui._prefs_webhook_var = tk.StringVar(master=discord_frame)
    ui._updating_webhook_var = True
    ui._prefs_webhook_var.set(ui._state.discord_webhook_url)
    ui._updating_webhook_var = False
    ui._prefs_webhook_var.trace_add("write", ui._on_webhook_change)
    webhook_entry = ttk.Entry(
        discord_frame,
        textvariable=ui._prefs_webhook_var,
        width=60,
    )
    webhook_entry.grid(row=2, column=0, sticky="ew", pady=(0, 6))
    ui._theme.register(webhook_entry)

    image_label = tk.Label(
        discord_frame,
        text="Discord image URL (optional)",
        anchor="w",
    )
    image_label.grid(row=3, column=0, sticky="w", pady=(0, 2))
    ui._theme.register(image_label)

    ui._prefs_image_var = tk.StringVar(master=discord_frame)
    ui._updating_image_var = True
    ui._prefs_image_var.set(ui._state.discord_image_url)
    ui._updating_image_var = False
    ui._prefs_image_var.trace_add("write", ui._on_discord_image_change)
    image_entry = ttk.Entry(
        discord_frame,
        textvariable=ui._prefs_image_var,
        width=60,
    )
    image_entry.grid(row=4, column=0, sticky="ew", pady=(0, 6))
    ui._theme.register(image_entry)

    ui._prefs_send_reset_summary_var = tk.BooleanVar(
        master=discord_frame,
        value=ui._state.send_reset_summary,
    )
    ui._prefs_send_reset_summary_var.trace_add("write", ui._on_send_reset_summary_change)
    send_reset_summary_cb = ttk.Checkbutton(
        discord_frame,
        text="Send Discord summary when resetting session",
        variable=ui._prefs_send_reset_summary_var,
    )
    send_reset_summary_cb.grid(row=5, column=0, sticky="w", pady=(0, 4))
    ui._theme.register(send_reset_summary_cb)
    ui._send_reset_summary_cb = send_reset_summary_cb

    test_btn = ttk.Button(
        discord_frame,
        text="Test webhook",
        command=ui._on_test_webhook,
    )
    test_btn.grid(row=6, column=0, sticky="w", pady=(0, 6))
    ui._theme.register(test_btn)
    ui._test_webhook_btn = test_btn

    ui._update_discord_controls()

    inara_frame = tk.LabelFrame(frame, text="Inara Links")
    inara_frame.grid(row=6, column=0, sticky="ew", padx=10, pady=(0, 10))
    inara_frame.columnconfigure(0, weight=1)
    ui._theme.register(inara_frame)

    inara_desc = tk.Label(
        inara_frame,
        text="Configure how commodity hyperlinks open Inara searches.",
        anchor="w",
        justify="left",
        wraplength=380,
    )
    inara_desc.grid(row=0, column=0, sticky="w", pady=(4, 6))
    ui._theme.register(inara_desc)

    ui._prefs_inara_mode_var = tk.IntVar(master=inara_frame, value=ui._state.inara_settings.search_mode)
    ui._prefs_inara_mode_var.trace_add("write", ui._on_inara_mode_change)
    mode_container = tk.Frame(inara_frame, highlightthickness=0, bd=0)
    mode_container.grid(row=1, column=0, sticky="w", pady=(0, 6))
    ui._theme.register(mode_container)
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
        master=inara_frame, value=ui._state.inara_settings.include_carriers
    )
    ui._prefs_inara_carriers_var.trace_add("write", ui._on_inara_carriers_change)
    ttk.Checkbutton(
        inara_frame,
        text="Include fleet carriers in results",
        variable=ui._prefs_inara_carriers_var,
    ).grid(row=2, column=0, sticky="w", pady=(0, 4))

    ui._prefs_inara_surface_var = tk.BooleanVar(
        master=inara_frame, value=ui._state.inara_settings.include_surface
    )
    ui._prefs_inara_surface_var.trace_add("write", ui._on_inara_surface_change)
    ttk.Checkbutton(
        inara_frame,
        text="Include surface stations in results",
        variable=ui._prefs_inara_surface_var,
    ).grid(row=3, column=0, sticky="w", pady=(0, 4))

    return frame


__all__ = ["build_preferences"]
