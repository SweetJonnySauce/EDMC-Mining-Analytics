"""Tkinter UI for the EDMC Mining Analytics plugin."""

from __future__ import annotations

import logging
import random
import webbrowser
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

try:
    import tkinter as tk
    from tkinter import ttk
    import tkinter.font as tkfont
except ImportError as exc:  # pragma: no cover - EDMC always provides tkinter
    raise RuntimeError("Tkinter must be available for EDMC plugins") from exc

from tooltip import TreeTooltip, WidgetTooltip
from state import MiningState, compute_percentage_stats, update_rpm
from integrations.mining_inara import InaraClient
from integrations.edmcoverlay import determine_rpm_color
from preferences import (
    clamp_bin_size,
    clamp_positive_int,
    clamp_rate_interval,
    clamp_session_retention,
    clamp_overlay_coordinate,
    clamp_overlay_interval,
)
from logging_utils import get_logger
from edmc_mining_analytics_version import (
    PLUGIN_VERSION,
    PLUGIN_REPO_URL,
    display_version,
    is_newer_version,
)
from mining_ui.theme_adapter import ThemeAdapter
from mining_ui.preferences import build_preferences as build_preferences_ui
from mining_ui.histograms import (
    close_histogram_window as _hist_close_window,
    close_histogram_windows as _hist_close_windows,
    draw_histogram as _hist_draw,
    open_histogram_window as _hist_open,
    recompute_histograms as _hist_recompute,
    refresh_histogram_windows as _hist_refresh,
)

_log = get_logger("ui")

NON_METAL_WARNING_COLOR = "#ff4d4d"
NON_METAL_WARNING_TEXT = " (Warning: Non-Metallic ring)"


class edmcmaMiningUI:
    """Encapsulates widget construction and refresh logic."""

    def __init__(
        self,
        state: MiningState,
        inara: InaraClient,
        on_reset: Callable[[], None],
        on_pause_changed: Optional[Callable[[bool, str, datetime], None]] = None,
        on_reset_inferred_capacities: Optional[Callable[[], None]] = None,
        on_test_webhook: Optional[Callable[[], None]] = None,
        on_settings_changed: Optional[Callable[[], None]] = None,
    ) -> None:
        self._state = state
        self._inara = inara
        self._on_reset = on_reset
        self._pause_callback = on_pause_changed
        self._reset_capacities_callback = on_reset_inferred_capacities
        self._test_webhook_callback = on_test_webhook
        self._on_settings_changed = on_settings_changed
        self._theme = ThemeAdapter()

        self._frame: Optional[tk.Widget] = None
        self._status_var: Optional[tk.StringVar] = None
        self._reserve_var: Optional[tk.StringVar] = None
        self._summary_var: Optional[tk.StringVar] = None
        self._summary_label: Optional[tk.Label] = None
        self._summary_tooltip: Optional[WidgetTooltip] = None
        self._summary_inferred_bounds: Optional[Tuple[int, int, int, int]] = None
        self._reserve_line: Optional[tk.Frame] = None
        self._reserve_label: Optional[tk.Label] = None
        self._reserve_warning_label: Optional[tk.Label] = None
        self._rpm_var: Optional[tk.StringVar] = None
        self._rpm_label: Optional[tk.Label] = None
        self._rpm_title_label: Optional[tk.Label] = None
        self._rpm_tooltip: Optional[WidgetTooltip] = None
        self._rpm_font: Optional[tkfont.Font] = None
        self._rpm_frame: Optional[tk.Frame] = None
        self._rpm_display_value: float = 0.0
        self._rpm_target_value: float = 0.0
        self._rpm_animation_after: Optional[str] = None
        self._pause_btn: Optional[tk.Button] = None
        self._cargo_tree: Optional[ttk.Treeview] = None
        self._materials_tree: Optional[ttk.Treeview] = None
        self._materials_frame: Optional[tk.Frame] = None
        self._total_tph_var: Optional[tk.StringVar] = None
        self._total_tph_font: Optional[tkfont.Font] = None
        self._range_link_labels: Dict[str, tk.Label] = {}
        self._commodity_link_labels: Dict[str, tk.Label] = {}
        self._range_link_font: Optional[tkfont.Font] = None
        self._commodity_link_font: Optional[tkfont.Font] = None
        self._cargo_tooltip: Optional[TreeTooltip] = None
        self._cargo_item_to_commodity: Dict[str, str] = {}
        self._content_widgets: Sequence[tk.Widget] = ()
        self._version_label: Optional[tk.Label] = None
        self._version_font: Optional[tkfont.Font] = None
        self._show_commodities_var: Optional[tk.BooleanVar] = None
        self._show_materials_var: Optional[tk.BooleanVar] = None
        self._commodities_header: Optional[tk.Frame] = None
        self._materials_header: Optional[tk.Frame] = None
        self._commodities_frame: Optional[tk.Frame] = None
        self._commodities_grid: Optional[Dict[str, Any]] = None
        self._materials_grid: Optional[Dict[str, Any]] = None

        self._prefs_bin_var: Optional[tk.IntVar] = None
        self._prefs_rate_var: Optional[tk.IntVar] = None
        self._prefs_inara_mode_var: Optional[tk.IntVar] = None
        self._prefs_inara_carriers_var: Optional[tk.BooleanVar] = None
        self._prefs_inara_surface_var: Optional[tk.BooleanVar] = None
        self._prefs_auto_unpause_var: Optional[tk.BooleanVar] = None
        self._prefs_session_logging_var: Optional[tk.BooleanVar] = None
        self._prefs_session_retention_var: Optional[tk.IntVar] = None
        self._prefs_refinement_window_var: Optional[tk.IntVar] = None
        self._prefs_rpm_red_var: Optional[tk.IntVar] = None
        self._prefs_rpm_yellow_var: Optional[tk.IntVar] = None
        self._prefs_rpm_green_var: Optional[tk.IntVar] = None
        self._prefs_webhook_var: Optional[tk.StringVar] = None
        self._prefs_send_summary_var: Optional[tk.BooleanVar] = None
        self._prefs_send_reset_summary_var: Optional[tk.BooleanVar] = None
        self._prefs_image_var: Optional[tk.StringVar] = None
        self._prefs_warn_non_metallic_var: Optional[tk.BooleanVar] = None
        self._prefs_overlay_enabled_var: Optional[tk.BooleanVar] = None
        self._prefs_overlay_x_var: Optional[tk.IntVar] = None
        self._prefs_overlay_y_var: Optional[tk.IntVar] = None
        self._prefs_overlay_interval_var: Optional[tk.IntVar] = None
        self._reset_capacities_btn: Optional[ttk.Button] = None
        self._send_summary_cb: Optional[ttk.Checkbutton] = None
        self._send_reset_summary_cb: Optional[ttk.Checkbutton] = None
        self._test_webhook_btn: Optional[ttk.Button] = None
        self._session_path_feedback: Optional[tk.StringVar] = None
        self._session_path_feedback_after: Optional[str] = None
        self._overlay_controls: list[tk.Widget] = []
        self._overlay_hint_label: Optional[tk.Label] = None

        self._updating_bin_var = False
        self._updating_rate_var = False
        self._updating_inara_mode_var = False
        self._updating_inara_carriers_var = False
        self._updating_inara_surface_var = False
        self._updating_session_logging_var = False
        self._updating_session_retention_var = False
        self._updating_refinement_window_var = False
        self._updating_rpm_vars = False
        self._updating_webhook_var = False
        self._updating_send_summary_var = False
        self._updating_send_reset_summary_var = False
        self._updating_image_var = False
        self._updating_warn_non_metallic_var = False
        self._updating_overlay_enabled_var = False
        self._updating_overlay_x_var = False
        self._updating_overlay_y_var = False
        self._updating_overlay_interval_var = False

        self._rate_update_job: Optional[str] = None
        self._content_collapsed = False
        self._hist_windows: Dict[str, tk.Toplevel] = {}
        self._hist_canvases: Dict[str, tk.Canvas] = {}
        self._details_visible = False
        self._last_is_mining: Optional[bool] = None
        self._rpm_update_job: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def build(self, parent: tk.Widget) -> tk.Frame:
        frame = tk.Frame(parent, highlightthickness=0, bd=0)
        self._frame = frame
        self._theme.register(frame)

        status_container = tk.Frame(frame, highlightthickness=0, bd=0)
        status_container.grid(row=0, column=0, sticky="w", padx=4, pady=(4, 2))
        status_container.columnconfigure(0, weight=1)
        self._theme.register(status_container)

        self._status_var = tk.StringVar(master=status_container, value="Not mining")
        status_label = tk.Label(
            status_container,
            textvariable=self._status_var,
            justify="left",
            anchor="w",
        )
        status_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 0))
        status_label.configure(pady=0)
        self._theme.register(status_label)

        reserve_line = tk.Frame(status_container, highlightthickness=0, bd=0)
        reserve_line.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 0))
        self._theme.register(reserve_line)
        self._reserve_line = reserve_line

        self._reserve_var = tk.StringVar(master=reserve_line, value="")
        reserve_label = tk.Label(
            reserve_line,
            textvariable=self._reserve_var,
            justify="left",
            anchor="w",
        )
        reserve_label.pack(side="left", anchor="w", pady=0)
        reserve_label.configure(pady=0)
        self._theme.register(reserve_label)
        self._reserve_label = reserve_label

        warning_label = tk.Label(
            reserve_line,
            text="",
            justify="left",
            anchor="w",
        )
        warning_label.pack(side="left", anchor="w", pady=0)
        warning_label.configure(pady=0)
        try:
            base_font = tkfont.nametofont(reserve_label.cget("font"))
            warning_label.configure(font=base_font)
        except tk.TclError:
            pass
        try:
            background = reserve_line.cget("background")
            warning_label.configure(background=background)
        except tk.TclError:
            pass
        warning_label.configure(foreground=NON_METAL_WARNING_COLOR)
        self._reserve_warning_label = warning_label

        version_text = display_version(PLUGIN_VERSION)
        version_label = tk.Label(frame, text=version_text, anchor="e", cursor="hand2")
        try:
            base_font = tkfont.nametofont(version_label.cget("font"))
            self._version_font = tkfont.Font(font=base_font)
            self._version_font.configure(underline=True)
            version_label.configure(font=self._version_font)
        except tk.TclError:
            self._version_font = None
        version_label.grid(row=0, column=1, sticky="e", padx=(4, 4), pady=(4, 2))
        version_label.bind("<Button-1>", lambda _evt: webbrowser.open(PLUGIN_REPO_URL))
        self._theme.register(version_label)
        self._version_label = version_label

        self._summary_var = tk.StringVar(master=frame, value="")
        summary_label = tk.Label(
            frame,
            textvariable=self._summary_var,
            justify="left",
            anchor="w",
        )
        summary_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 6))
        self._theme.register(summary_label)
        self._summary_label = summary_label
        self._summary_tooltip = WidgetTooltip(
            summary_label,
            hover_predicate=self._is_pointer_over_inferred,
        )

        rpm_frame = tk.Frame(frame, highlightthickness=0, bd=0)
        rpm_frame.grid(row=1, column=2, sticky="ne", padx=(0, 8), pady=(0, 6))
        self._theme.register(rpm_frame)
        rpm_frame.columnconfigure(0, weight=1)
        self._rpm_frame = rpm_frame

        self._rpm_var = tk.StringVar(master=rpm_frame, value="0.0")
        rpm_value = tk.Label(
            rpm_frame,
            textvariable=self._rpm_var,
            anchor="center",
            justify="center",
        )
        try:
            base_font = tkfont.nametofont(rpm_value.cget("font"))
            self._rpm_font = tkfont.Font(font=base_font)
            self._rpm_font.configure(size=max(18, int(base_font.cget("size")) + 8), weight="bold")
            rpm_value.configure(font=self._rpm_font)
        except tk.TclError:
            self._rpm_font = None
        rpm_value.grid(row=0, column=0, sticky="ew")
        self._theme.register(rpm_value)
        self._rpm_label = rpm_value

        rpm_title = tk.Label(rpm_frame, text="RPM", anchor="center")
        rpm_title.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        self._theme.register(rpm_title)
        self._rpm_title_label = rpm_title
        self._rpm_tooltip = WidgetTooltip(rpm_title)

        button_frame = tk.Frame(frame, highlightthickness=0, bd=0)
        button_frame.grid(row=0, column=2, sticky="e", padx=4, pady=(4, 2))
        self._theme.register(button_frame)
        self._details_toggle = tk.Button(
            button_frame,
            text="",
            command=self._toggle_details,
            cursor="hand2",
        )
        self._theme.style_button(self._details_toggle)
        self._details_toggle.grid(row=0, column=0, padx=0, pady=0)

        commodities_header = tk.Frame(frame, highlightthickness=0, bd=0)
        self._commodities_header = commodities_header
        commodities_header.grid(row=3, column=0, sticky="w", padx=4)
        self._theme.register(commodities_header)

        commodities_label = tk.Label(
            commodities_header,
            text="Mined Commodities",
            font=(None, 9, "bold"),
            anchor="w",
        )
        commodities_label.pack(side="left")
        self._theme.register(commodities_label)

        self._show_commodities_var = tk.BooleanVar(
            master=frame, value=self._state.show_mined_commodities
        )
        commodities_toggle = tk.Checkbutton(
            commodities_header,
            variable=self._show_commodities_var,
            command=self._on_toggle_commodities,
        )
        commodities_toggle.pack(side="left", padx=(6, 0))
        self._theme.register(commodities_toggle)
        self._theme.style_checkbox(commodities_toggle)

        table_frame = tk.Frame(frame, highlightthickness=0, bd=0)
        self._commodities_frame = table_frame
        self._commodities_grid = {
            "row": 4,
            "column": 0,
            "columnspan": 3,
            "sticky": "nsew",
            "padx": 4,
            "pady": (2, 6),
        }
        table_frame.grid(**self._commodities_grid)
        self._theme.register(table_frame)

        header_font = tkfont.Font(family="TkDefaultFont", size=9, weight="normal")
        ttk.Style().configure("Treeview.Heading", font=header_font)

        tree_style = self._theme.treeview_style()
        self._cargo_tree = ttk.Treeview(
            table_frame,
            columns=("commodity", "present", "percent", "total", "range", "tph"),
            show="headings",
            height=5,
            selectmode="none",
            style=tree_style,
        )
        self._cargo_tree.heading("commodity", text="Commodity", anchor="center")
        self._cargo_tree.heading("present", text="#", anchor="center")
        self._cargo_tree.heading("percent", text="%", anchor="center")
        self._cargo_tree.heading("total", text="Total", anchor="center")
        self._cargo_tree.heading("range", text="%Range", anchor="center")
        self._cargo_tree.heading("tph", text="Tons/hr", anchor="center")
        self._cargo_tree.column("commodity", anchor="w", width=160, stretch=True)
        self._cargo_tree.column("present", anchor="center", width=60, stretch=False)
        self._cargo_tree.column("percent", anchor="center", width=60, stretch=False)
        self._cargo_tree.column("total", anchor="center", width=80, stretch=False)
        self._cargo_tree.column("range", anchor="center", width=140, stretch=False)
        self._cargo_tree.column("tph", anchor="center", width=80, stretch=False)
        self._cargo_tree.pack(fill="both", expand=True)
        # Only apply explicit zebra striping on dark theme; in the EDMC
        # default (light) theme we inherit platform colors to keep rows
        # readable.
        if self._theme.is_dark_theme:
            self._cargo_tree.tag_configure(
                "even",
                background=self._theme.table_background_color(),
                foreground=self._theme.table_foreground_color(),
            )
            self._cargo_tree.tag_configure(
                "odd",
                background=self._theme.table_stripe_color(),
                foreground=self._theme.table_foreground_color(),
            )
        self._theme.register(self._cargo_tree)

        self._cargo_tooltip = TreeTooltip(self._cargo_tree)
        if self._cargo_tooltip:
            self._cargo_tooltip.set_heading_tooltip(
                "present",
                "Number of asteroids prospected where this commodity is present.",
            )
            self._cargo_tooltip.set_heading_tooltip(
                "percent",
                "Percentage of asteroids prospected where this commodity is present.",
            )
            self._cargo_tooltip.set_heading_tooltip(
                "total",
                "Total number of tons collected.",
            )
            self._cargo_tooltip.set_heading_tooltip(
                "range",
                "Minimum, average, and maximum percentages of this commodity on an asteroid when found.",
            )
            self._cargo_tooltip.set_heading_tooltip(
                "tph",
                "Projected tons collected per hour of mining.",
            )

        self._total_tph_var = tk.StringVar(master=frame, value="Total Tons/hr: -")
        total_label = tk.Label(
            frame,
            textvariable=self._total_tph_var,
            anchor="w",
        )
        try:
            base_font = tkfont.nametofont(total_label.cget("font"))
            self._total_tph_font = tkfont.Font(font=base_font)
            self._total_tph_font.configure(weight="bold")
            total_label.configure(font=self._total_tph_font)
        except tk.TclError:
            self._total_tph_font = None
        total_label.grid(row=2, column=0, sticky="w", padx=4, pady=(0, 6))
        self._theme.register(total_label)

        button_bar = tk.Frame(frame, highlightthickness=0, bd=0)
        button_bar.grid(row=2, column=2, sticky="e", padx=4, pady=(0, 6))
        self._theme.register(button_bar)

        pause_btn = tk.Button(button_bar, text="Pause", command=self._toggle_pause, cursor="hand2")
        self._theme.style_button(pause_btn)
        pause_btn.grid(row=0, column=0, padx=(0, 4), pady=0)
        self._pause_btn = pause_btn

        reset_btn = tk.Button(button_bar, text="Reset", command=self._on_reset, cursor="hand2")
        self._theme.style_button(reset_btn)
        reset_btn.grid(row=0, column=1, padx=0, pady=0)

        materials_header = tk.Frame(frame, highlightthickness=0, bd=0)
        self._materials_header = materials_header
        materials_header.grid(row=5, column=0, sticky="w", padx=4)
        self._theme.register(materials_header)

        materials_label = tk.Label(
            materials_header,
            text="Materials Collected",
            font=(None, 9, "bold"),
            anchor="w",
        )
        materials_label.pack(side="left")
        self._theme.register(materials_label)

        self._show_materials_var = tk.BooleanVar(
            master=frame, value=self._state.show_materials_collected
        )
        materials_toggle = tk.Checkbutton(
            materials_header,
            variable=self._show_materials_var,
            command=self._on_toggle_materials,
        )
        materials_toggle.pack(side="left", padx=(6, 0))
        self._theme.register(materials_toggle)
        self._theme.style_checkbox(materials_toggle)

        self._materials_frame = tk.Frame(frame, highlightthickness=0, bd=0)
        self._materials_grid = {
            "row": 6,
            "column": 0,
            "columnspan": 3,
            "sticky": "nsew",
            "padx": 4,
            "pady": (2, 6),
        }
        self._materials_frame.grid(**self._materials_grid)
        self._theme.register(self._materials_frame)

        self._materials_tree = ttk.Treeview(
            self._materials_frame,
            columns=("material", "quantity"),
            show="headings",
            height=5,
            selectmode="none",
            style=self._theme.treeview_style(),
        )
        self._materials_tree.heading("material", text="Material")
        self._materials_tree.heading("quantity", text="Count")
        self._materials_tree.column("material", anchor="w", stretch=True, width=160)
        self._materials_tree.column("quantity", anchor="center", stretch=False, width=80)
        self._materials_tree.pack(fill="both", expand=True)
        if self._theme.is_dark_theme:
            self._materials_tree.tag_configure(
                "even",
                background=self._theme.table_background_color(),
                foreground=self._theme.table_foreground_color(),
            )
            self._materials_tree.tag_configure(
                "odd",
                background=self._theme.table_stripe_color(),
                foreground=self._theme.table_foreground_color(),
            )
        self._theme.register(self._materials_tree)

        self._cargo_tree.bind("<Configure>", lambda _e: self._render_range_links(), add="+")
        self._cargo_tree.bind("<ButtonRelease-3>", lambda _e: self._render_range_links(), add="+")
        self._cargo_tree.bind("<KeyRelease>", lambda _e: self._render_range_links(), add="+")
        self._cargo_tree.bind("<MouseWheel>", lambda _e: self._render_range_links(), add="+")
        self._cargo_tree.bind("<ButtonRelease-4>", lambda _e: self._render_range_links(), add="+")
        self._cargo_tree.bind("<ButtonRelease-5>", lambda _e: self._render_range_links(), add="+")
        self._cargo_tree.bind("<Button-1>", self._on_cargo_click, add="+")
        self._cargo_tree.bind("<Motion>", self._on_cargo_motion, add="+")

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=0)
        frame.rowconfigure(4, weight=1)
        frame.rowconfigure(6, weight=1)

        self._content_widgets = (
            summary_label,
            rpm_frame,
            total_label,
            button_bar,
            commodities_header,
            table_frame,
            materials_header,
            self._materials_frame,
        )

        self._update_pause_button()

        self._apply_initial_visibility()
        self._apply_table_visibility()

        self._update_rpm_indicator()
        # Ensure RPM continues to evaluate over time, even without events
        self._schedule_rpm_update()

        return frame

    def _schedule_rpm_update(self) -> None:
        frame = self._frame
        if frame is None or not frame.winfo_exists():
            return
        # Avoid multiple scheduled jobs
        if self._rpm_update_job is not None:
            return
        # Always keep RPM evaluated on a timer so it decays after the window
        self._rpm_update_job = frame.after(1000, self._on_rpm_update_tick)

    def _cancel_rpm_update(self) -> None:
        frame = self._frame
        if self._rpm_update_job and frame and frame.winfo_exists():
            try:
                frame.after_cancel(self._rpm_update_job)
            except Exception:
                pass
        self._rpm_update_job = None

    def _on_rpm_update_tick(self) -> None:
        # Clear the handle first to allow rescheduling even if exceptions occur
        self._rpm_update_job = None
        # Respect pause if the user paused updates
        if not self._state.is_paused:
            self._update_rpm_indicator()
        # Reschedule if the UI is still alive
        self._schedule_rpm_update()

    def update_version_label(
        self,
        current_version: str,
        latest_version: Optional[str],
        update_ready: bool,
    ) -> None:
        label = self._version_label
        if label is None or not getattr(label, "winfo_exists", lambda: False)():
            return
        text = display_version(current_version)
        if latest_version:
            if is_newer_version(latest_version, current_version):
                if update_ready:
                    text = f"{text} (restart to update)"
                else:
                    text = f"{text} (a newer version exists)"
            elif is_newer_version(current_version, latest_version):
                text = f"{text} (development)"
        label.configure(text=text)

    def refresh(self) -> None:
        self._update_pause_button()
        self._refresh_status_line()
        self._populate_tables()
        self._render_range_links()
        self._update_overlay_controls()

    def _on_auto_unpause_change(self, *_: object) -> None:
        if self._prefs_auto_unpause_var is None:
            return
        try:
            value = bool(self._prefs_auto_unpause_var.get())
        except (tk.TclError, ValueError):
            return
        self._state.auto_unpause_on_event = value

    def _on_warn_non_metallic_change(self, *_: object) -> None:
        if (
            self._prefs_warn_non_metallic_var is None
            or self._updating_warn_non_metallic_var
        ):
            return
        try:
            value = bool(self._prefs_warn_non_metallic_var.get())
        except (tk.TclError, ValueError):
            return
        if value == self._state.warn_on_non_metallic_ring:
            return
        self._state.warn_on_non_metallic_ring = value
        self._notify_settings_changed()
        self._refresh_status_line()

    def _on_overlay_enabled_change(self, *_: object) -> None:
        if self._prefs_overlay_enabled_var is None or self._updating_overlay_enabled_var:
            return
        try:
            value = bool(self._prefs_overlay_enabled_var.get())
        except (tk.TclError, ValueError):
            return
        if value == self._state.overlay_enabled:
            return
        self._state.overlay_enabled = value
        self._notify_settings_changed()

    def _on_overlay_anchor_x_change(self, *_: object) -> None:
        if self._prefs_overlay_x_var is None or self._updating_overlay_x_var:
            return
        try:
            raw_value = int(self._prefs_overlay_x_var.get())
        except (tk.TclError, TypeError, ValueError):
            return
        clamped = clamp_overlay_coordinate(raw_value, self._state.overlay_anchor_x)
        if clamped == self._state.overlay_anchor_x:
            return
        self._state.overlay_anchor_x = clamped
        self._updating_overlay_x_var = True
        self._prefs_overlay_x_var.set(clamped)
        self._updating_overlay_x_var = False
        self._notify_settings_changed()

    def _on_overlay_anchor_y_change(self, *_: object) -> None:
        if self._prefs_overlay_y_var is None or self._updating_overlay_y_var:
            return
        try:
            raw_value = int(self._prefs_overlay_y_var.get())
        except (tk.TclError, TypeError, ValueError):
            return
        clamped = clamp_overlay_coordinate(raw_value, self._state.overlay_anchor_y)
        if clamped == self._state.overlay_anchor_y:
            return
        self._state.overlay_anchor_y = clamped
        self._updating_overlay_y_var = True
        self._prefs_overlay_y_var.set(clamped)
        self._updating_overlay_y_var = False
        self._notify_settings_changed()

    def _on_overlay_interval_change(self, *_: object) -> None:
        if self._prefs_overlay_interval_var is None or self._updating_overlay_interval_var:
            return
        try:
            raw_value = int(self._prefs_overlay_interval_var.get())
        except (tk.TclError, TypeError, ValueError):
            return
        clamped = clamp_overlay_interval(raw_value, self._state.overlay_refresh_interval_ms)
        if clamped == self._state.overlay_refresh_interval_ms:
            return
        self._state.overlay_refresh_interval_ms = clamped
        self._updating_overlay_interval_var = True
        self._prefs_overlay_interval_var.set(clamped)
        self._updating_overlay_interval_var = False
        self._notify_settings_changed()

    def _update_overlay_controls(self) -> None:
        controls = tuple(self._overlay_controls)
        available = self._state.overlay_available
        desired_state = tk.NORMAL if available else tk.DISABLED
        for widget in controls:
            if widget is None:
                continue
            try:
                widget.configure(state=desired_state)
            except tk.TclError:
                continue
        hint = self._overlay_hint_label
        if hint is not None:
            try:
                if available:
                    hint.configure(text="")
                    hint.grid_remove()
                else:
                    hint.configure(
                        text="EDMCOverlay plugin not detected. Install it to enable in-game metrics."
                    )
                    hint.grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 4))
            except tk.TclError:
                pass

    def _on_session_logging_change(self, *_: object) -> None:
        if (
            self._prefs_session_logging_var is None
            or self._updating_session_logging_var
        ):
            return
        try:
            value = bool(self._prefs_session_logging_var.get())
        except (tk.TclError, ValueError):
            return
        if value == self._state.session_logging_enabled:
            return
        self._state.session_logging_enabled = value

    def _on_session_retention_change(self, *_: object) -> None:
        if (
            self._prefs_session_retention_var is None
            or self._updating_session_retention_var
        ):
            return
        try:
            value = int(self._prefs_session_retention_var.get())
        except (tk.TclError, ValueError, TypeError):
            return
        limit = clamp_session_retention(value)
        if limit == self._state.session_log_retention:
            return
        self._state.session_log_retention = limit
        if self._prefs_session_retention_var.get() != limit:
            self._updating_session_retention_var = True
            self._prefs_session_retention_var.set(limit)
            self._updating_session_retention_var = False

    def _copy_session_log_path(self) -> None:
        frame = self._frame
        if frame is None:
            return
        plugin_dir = self._state.plugin_dir
        if plugin_dir is None:
            self._update_session_path_feedback("Plugin folder unavailable")
            _log.warning("Unable to copy session log path; plugin directory unknown")
            return

        target = (plugin_dir / "session_data").resolve()
        try:
            frame.clipboard_clear()
            frame.clipboard_append(str(target))
            frame.update_idletasks()
        except Exception:
            self._update_session_path_feedback("Copy failed")
            _log.exception("Failed to copy session log directory to clipboard")
            return

        self._update_session_path_feedback("Copied folder path")

    def _update_session_path_feedback(self, message: str, *, clear_after: int = 3000) -> None:
        var = self._session_path_feedback
        frame = self._frame
        if var is None or frame is None:
            return

        var.set(message)
        if self._session_path_feedback_after is not None:
            try:
                frame.after_cancel(self._session_path_feedback_after)
            except Exception:
                pass
            self._session_path_feedback_after = None

        if message:
            self._session_path_feedback_after = frame.after(
                clear_after,
                self._clear_session_path_feedback,
            )

    def _clear_session_path_feedback(self) -> None:
        self._session_path_feedback_after = None
        if self._session_path_feedback is not None:
            self._session_path_feedback.set("")

    def _on_reset_inferred_capacities(self) -> None:
        callback = self._reset_capacities_callback
        if not callback:
            return
        try:
            callback()
        except Exception:
            _log.exception("Failed to reset inferred cargo capacities")

    def _on_webhook_change(self, *_: object) -> None:
        if self._prefs_webhook_var is None or self._updating_webhook_var:
            return
        value = self._prefs_webhook_var.get()
        trimmed = value.strip() if isinstance(value, str) else ""
        self._state.discord_webhook_url = trimmed
        if not trimmed and self._state.send_summary_to_discord:
            self._state.send_summary_to_discord = False
            if self._prefs_send_summary_var is not None:
                self._updating_send_summary_var = True
                self._prefs_send_summary_var.set(False)
                self._updating_send_summary_var = False
        self._update_discord_controls()

    def _on_send_summary_change(self, *_: object) -> None:
        if self._prefs_send_summary_var is None or self._updating_send_summary_var:
            return
        try:
            value = bool(self._prefs_send_summary_var.get())
        except (tk.TclError, ValueError):
            return
        if value and not self._state.discord_webhook_url:
            self._updating_send_summary_var = True
            self._prefs_send_summary_var.set(False)
            self._updating_send_summary_var = False
            self._state.send_summary_to_discord = False
            return
        self._state.send_summary_to_discord = value
        self._update_discord_controls()

    def _on_send_reset_summary_change(self, *_: object) -> None:
        if (
            self._prefs_send_reset_summary_var is None
            or self._updating_send_reset_summary_var
        ):
            return
        try:
            value = bool(self._prefs_send_reset_summary_var.get())
        except (tk.TclError, ValueError):
            return
        if value and not self._state.discord_webhook_url:
            self._updating_send_reset_summary_var = True
            self._prefs_send_reset_summary_var.set(False)
            self._updating_send_reset_summary_var = False
            self._state.send_reset_summary = False
            return
        self._state.send_reset_summary = value
        self._update_discord_controls()

    def _on_test_webhook(self) -> None:
        callback = self._test_webhook_callback
        if not callback:
            return
        try:
            callback()
        except ValueError as exc:
            _log.warning("Test webhook failed: %s", exc)
        except Exception:
            _log.exception("Failed to invoke webhook test")

    def _on_discord_image_change(self, *_: object) -> None:
        if self._prefs_image_var is None or self._updating_image_var:
            return
        value = self._prefs_image_var.get()
        self._state.discord_image_url = value.strip() if isinstance(value, str) else ""

    def _update_discord_controls(self) -> None:
        has_url = bool(self._state.discord_webhook_url.strip())
        if not has_url and self._state.send_summary_to_discord:
            self._state.send_summary_to_discord = False
            if self._prefs_send_summary_var is not None:
                self._updating_send_summary_var = True
                self._prefs_send_summary_var.set(False)
                self._updating_send_summary_var = False
        elif has_url and self._prefs_send_summary_var is not None:
            self._updating_send_summary_var = True
            self._prefs_send_summary_var.set(bool(self._state.send_summary_to_discord))
            self._updating_send_summary_var = False
        if not has_url and self._state.send_reset_summary:
            self._state.send_reset_summary = False
            if self._prefs_send_reset_summary_var is not None:
                self._updating_send_reset_summary_var = True
                self._prefs_send_reset_summary_var.set(False)
                self._updating_send_reset_summary_var = False
        elif has_url and self._prefs_send_reset_summary_var is not None:
            self._updating_send_reset_summary_var = True
            self._prefs_send_reset_summary_var.set(bool(self._state.send_reset_summary))
            self._updating_send_reset_summary_var = False
        if self._send_summary_cb is not None:
            try:
                self._send_summary_cb.configure(state=tk.NORMAL if has_url else tk.DISABLED)
            except tk.TclError:
                pass
        if self._send_reset_summary_cb is not None:
            try:
                self._send_reset_summary_cb.configure(state=tk.NORMAL if has_url else tk.DISABLED)
            except tk.TclError:
                pass
        if self._test_webhook_btn is not None:
            try:
                self._test_webhook_btn.configure(state=tk.NORMAL if has_url else tk.DISABLED)
            except tk.TclError:
                pass

    def schedule_rate_update(self) -> None:
        frame = self._frame
        if frame is None or not frame.winfo_exists():
            return

        if not self._state.is_mining or self._state.is_paused:
            self.cancel_rate_update()
            return

        self.cancel_rate_update()
        interval = clamp_rate_interval(self._state.rate_interval_seconds)
        jitter = random.uniform(-0.2, 0.2) * interval
        delay_ms = max(1000, int((interval + jitter) * 1000))
        self._rate_update_job = frame.after(delay_ms, self._on_rate_update_tick)

    def cancel_rate_update(self) -> None:
        frame = self._frame
        if self._rate_update_job and frame and frame.winfo_exists():
            try:
                frame.after_cancel(self._rate_update_job)
            except Exception:
                pass
        self._rate_update_job = None

    def _toggle_details(self) -> None:
        self._details_visible = not self._details_visible
        self._sync_details_visibility()

    def _apply_initial_visibility(self) -> None:
        self._details_visible = bool(self._state.is_mining)
        self._last_is_mining = self._state.is_mining
        self._sync_details_visibility()

    def _sync_details_visibility(self) -> None:
        visible = self._details_visible
        for widget in self._content_widgets:
            if visible:
                widget.grid()
            else:
                widget.grid_remove()
        if visible:
            self._apply_table_visibility()
        if self._details_toggle:
            label = "Hide Details" if visible else "Show Details"
            try:
                self._details_toggle.configure(text=label)
            except Exception:
                pass

    def _apply_table_visibility(self) -> None:
        self._apply_commodities_visibility()
        self._apply_materials_visibility()

    def _apply_commodities_visibility(self) -> None:
        frame = self._commodities_frame
        if frame is None:
            return
        if not self._details_visible:
            frame.grid_remove()
            return
        should_show = self._bool_from_var(self._show_commodities_var, default=True)
        if should_show:
            self._restore_grid(frame, self._commodities_grid)
        else:
            frame.grid_remove()

    def _apply_materials_visibility(self) -> None:
        frame = self._materials_frame
        if frame is None:
            return
        if not self._details_visible:
            frame.grid_remove()
            return
        should_show = self._bool_from_var(self._show_materials_var, default=True)
        if should_show:
            self._restore_grid(frame, self._materials_grid)
        else:
            frame.grid_remove()

    def _notify_settings_changed(self) -> None:
        callback = self._on_settings_changed
        if callback is None:
            return
        try:
            callback()
        except Exception:
            _log.exception("Failed to persist UI settings")

    def _on_toggle_commodities(self) -> None:
        self._state.show_mined_commodities = self._bool_from_var(
            self._show_commodities_var, default=True
        )
        self._apply_commodities_visibility()
        self._notify_settings_changed()

    def _on_toggle_materials(self) -> None:
        self._state.show_materials_collected = self._bool_from_var(
            self._show_materials_var, default=True
        )
        self._apply_materials_visibility()
        self._notify_settings_changed()

    def _restore_grid(self, widget: tk.Widget, grid_options: Optional[Dict[str, Any]]) -> None:
        if grid_options is None:
            widget.grid()
            return
        widget.grid(**grid_options)

    @staticmethod
    def _bool_from_var(var: Optional[tk.BooleanVar], default: bool) -> bool:
        if var is None:
            return default
        try:
            return bool(var.get())
        except (tk.TclError, ValueError):
            return default

    def build_preferences(self, parent: tk.Widget) -> tk.Widget:
        return build_preferences_ui(self, parent)


    def get_root(self) -> Optional[tk.Widget]:
        return self._frame

    def clear_transient_widgets(self, *, close_histograms: bool = True) -> None:
        self._clear_range_link_labels()
        self._clear_commodity_link_labels()
        if close_histograms:
            self.close_histogram_windows()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _refresh_status_line(self) -> None:
        status_var = self._status_var
        summary_var = self._summary_var
        if status_var is None or summary_var is None:
            return

        if self._state.is_mining:
            if self._state.mining_location:
                status_base = f"You're mining {self._state.mining_location}"
            else:
                status_base = "You're mining!"
        else:
            status_base = "Not mining"

        prefix = "[PAUSED] " if self._state.is_paused else ""
        status_text = f"{prefix}{status_base}" if prefix else status_base

        summary_lines = self._status_summary_lines()

        reserve_text = ""
        warning_text = ""
        if self._state.is_mining:
            reserve_text = self._format_edsm_info()
            warning_text = self._non_metal_warning_text()

        status_var.set(status_text)
        reserve_var = self._reserve_var
        if reserve_var is not None:
            reserve_var.set(reserve_text)
        reserve_line = self._reserve_line
        if reserve_line is not None:
            if reserve_text:
                reserve_line.grid()
            else:
                reserve_line.grid_remove()
        warning_label = self._reserve_warning_label
        if warning_label is not None:
            warning_label.configure(text=warning_text, foreground=NON_METAL_WARNING_COLOR)
        summary_var.set("\n".join(summary_lines))
        self._update_summary_tooltip()
        self._update_rpm_indicator()

        if self._last_is_mining is None or self._last_is_mining != self._state.is_mining:
            self._details_visible = bool(self._state.is_mining)
            self._sync_details_visibility()
            # Align RPM timer with mining activity
            if self._state.is_mining and not self._state.is_paused:
                self._schedule_rpm_update()
            else:
                self._cancel_rpm_update()
        self._last_is_mining = self._state.is_mining

    def _status_summary_lines(self) -> list[str]:
        lines: list[str] = []
        if self._state.mining_start:
            if self._state.mining_end and not self._state.is_mining:
                elapsed = self._calculate_elapsed_seconds(self._state.mining_start, self._state.mining_end)
                lines.append(f"Elapsed: {self._format_duration(elapsed)}")
            else:
                start_dt = self._ensure_aware(self._state.mining_start).astimezone(timezone.utc)
                lines.append(f"Started: {start_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        else:
            label = "Elapsed" if self._state.mining_end and not self._state.is_mining else "Started"
            lines.append(f"{label}: --")

        lines.append(
            f"Prospected: {self._state.prospected_count} | Already mined: {self._state.already_mined_count} | Dupes: {self._state.duplicate_prospected}"
        )

        lost = max(0, self._state.prospector_launched_count - self._state.prospected_count)
        content_line = ""
        if self._state.prospect_content_counts:
            content_line = " | Content: " + ", ".join(
                f"{key[0]}:{self._state.prospect_content_counts.get(key, 0)}"
                for key in ("High", "Medium", "Low")
            )
        lines.append(
            f"Prospectors: Launched: {self._state.prospector_launched_count} | Lost: {lost}{content_line}"
        )

        limpets = (
            f"Limpets remaining: {self._state.limpets_remaining}"
            if self._state.limpets_remaining is not None
            else None
        )
        drones = f"Collectors launched: {self._state.collection_drones_launched}"
        abandoned = (
            f"Limpets abandoned: {self._state.abandoned_limpets}"
            if self._state.abandoned_limpets > 0
            else None
        )
        third = " | ".join(x for x in [limpets, drones, abandoned] if x)
        if third:
            lines.append(third)

        if not (self._state.cargo_totals or self._state.cargo_additions):
            lines.append("No cargo data yet")

        mined_cargo = max(0, self._state.current_cargo_tonnage)
        limpets_onboard = self._state.limpets_remaining if self._state.limpets_remaining is not None else 0
        total_cargo = mined_cargo + max(0, limpets_onboard)
        capacity = self._state.cargo_capacity
        if capacity is not None and capacity > 0:
            capacity_text = f"{capacity}t"
            if self._state.cargo_capacity_is_inferred:
                capacity_text = f"{capacity_text} (Inferred)"
            remaining = max(0, capacity - total_cargo)
            percent_full = ((capacity - remaining) / capacity) * 100.0
            summary = (
                f"Cargo: {total_cargo}t | Capacity: {capacity_text} | Remaining: {remaining}t | {percent_full:.1f}% full"
            )
            lines.append(summary)
        else:
            remaining_label = "unknown"
            lines.append(
                f"Cargo: {total_cargo}t | Capacity: unknown | Remaining: {remaining_label} | % full: unknown"
            )

        return lines

    def _format_edsm_info(self) -> str:
        reserve = (self._state.edsm_reserve_level or "").strip()
        ring_type = (self._state.edsm_ring_type or "").strip()
        parts = [value for value in (reserve, ring_type) if value]
        return " ".join(parts)

    def _non_metal_warning_text(self) -> str:
        if not (self._state.warn_on_non_metallic_ring and self._state.is_mining):
            return ""
        ring_type = (self._state.edsm_ring_type or "").strip()
        if not ring_type:
            return ""
        if "metallic" in ring_type.lower():
            return ""
        return NON_METAL_WARNING_TEXT

    def _update_summary_tooltip(self) -> None:
        tooltip = self._summary_tooltip
        if tooltip is None:
            return
        bounds: Optional[Tuple[int, int, int, int]] = None
        text: Optional[str] = None
        if self._state.cargo_capacity_is_inferred and self._state.cargo_capacity:
            summary_label = self._summary_label
            summary_text = self._summary_var.get() if self._summary_var is not None else None
            if summary_label and summary_text:
                bounds = self._compute_inferred_bounds(summary_label, summary_text)
            text = (
                "The plugin can't yet determine the cargo capacity. Try swapping ships, or filling your hold completely full of limpets."
            )
        tooltip.set_text(text)
        self._summary_inferred_bounds = bounds

    def _compute_inferred_bounds(self, label: tk.Label, text: str) -> Optional[Tuple[int, int, int, int]]:
        target = "(Inferred)"
        index = text.find(target)
        if index == -1:
            return None
        prefix = text[:index]
        lines = prefix.split("\n")
        line_index = max(0, len(lines) - 1)
        preceding = lines[-1] if lines else ""
        font = tkfont.nametofont(label.cget("font"))
        line_height = font.metrics("linespace")

        def _to_int(value: str) -> int:
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return 0

        pad_x = _to_int(label.cget("padx"))
        pad_y = _to_int(label.cget("pady"))
        border = _to_int(label.cget("borderwidth"))
        highlight = _to_int(label.cget("highlightthickness"))

        x_base = pad_x + border + highlight
        y_base = pad_y + border + highlight

        x_start = x_base + font.measure(preceding)
        x_end = x_start + font.measure(target)
        y_start = y_base + line_index * line_height
        y_end = y_start + line_height
        return (int(x_start), int(y_start), int(x_end), int(y_end))

    def _is_pointer_over_inferred(self, x: int, y: int) -> bool:
        bounds = self._summary_inferred_bounds
        if not bounds:
            return False
        x1, y1, x2, y2 = bounds
        return x1 <= x <= x2 and y1 <= y <= y2

    def _update_rpm_indicator(self) -> None:
        rpm_label = self._rpm_label
        rpm_var = self._rpm_var
        if rpm_label is None or rpm_var is None:
            return

        now = datetime.now(timezone.utc)
        rpm = update_rpm(self._state, now)
        self._start_rpm_animation(rpm)

        tooltip = self._rpm_tooltip
        if tooltip is not None:
            lookback = max(1, int(self._state.refinement_lookback_seconds or 1))
            tooltip.set_text(
                (
                    f"Refinements per minute over the last {lookback} seconds.\n"
                    f"Session max RPM: {self._state.max_rpm:.1f}"
                )
            )

    def _determine_rpm_color(self, rpm: float) -> str:
        default_color = self._theme.default_text_color()
        return determine_rpm_color(self._state, rpm, default=default_color)

    def _start_rpm_animation(self, target_rpm: float) -> None:
        self._rpm_target_value = target_rpm
        if self._frame is None:
            return

        if self._rpm_animation_after is not None:
            try:
                self._frame.after_cancel(self._rpm_animation_after)
            except Exception:
                pass
            self._rpm_animation_after = None

        if abs(self._rpm_display_value - target_rpm) < 0.05:
            self._set_rpm_display(target_rpm)
            return

        self._schedule_rpm_step()

    def _schedule_rpm_step(self) -> None:
        frame = self._frame
        if frame is None:
            return
        self._rpm_animation_after = frame.after(50, self._animate_rpm_step)

    def _animate_rpm_step(self) -> None:
        target_rpm = self._rpm_target_value
        current_display = self._rpm_display_value

        delta = target_rpm - current_display
        if abs(delta) < 0.05:
            self._set_rpm_display(target_rpm)
            self._rpm_animation_after = None
            return

        step = 0.2 if delta > 0 else -0.2
        next_value = round(current_display + step, 1)
        self._set_rpm_display(next_value)
        self._schedule_rpm_step()

    def _set_rpm_display(self, value: float) -> None:
        self._rpm_display_value = value
        rpm_var = self._rpm_var
        if rpm_var is not None:
            rpm_var.set(f"{value:.1f}")

        color = self._determine_rpm_color(value)
        self._state.rpm_display_color = color
        if self._rpm_label is not None:
            try:
                self._rpm_label.configure(foreground=color)
            except tk.TclError:
                pass

    def _populate_tables(self) -> None:
        cargo_tree = self._cargo_tree
        if cargo_tree and getattr(cargo_tree, "winfo_exists", lambda: False)():
            if self._theme.is_dark_theme:
                cargo_tree.tag_configure(
                    "even",
                    background=self._theme.table_background_color(),
                    foreground=self._theme.table_foreground_color(),
                )
                cargo_tree.tag_configure(
                    "odd",
                    background=self._theme.table_stripe_color(),
                    foreground=self._theme.table_foreground_color(),
                )
            cargo_tree.delete(*cargo_tree.get_children())
            if self._cargo_tooltip:
                self._cargo_tooltip.clear()
            self._cargo_item_to_commodity.clear()
            self.clear_transient_widgets(close_histograms=False)

            rows = sorted(
                name
                for name in set(self._state.cargo_totals) | set(self._state.cargo_additions)
                if self._state.cargo_additions.get(name, 0) > 0
            )
            if not rows:
                item = cargo_tree.insert(
                    "",
                    "end",
                    values=("No mined commodities", "", "", "", "", ""),
                    tags=("even",),
                )
                if self._cargo_tooltip:
                    self._cargo_tooltip.set_cell_text(item, "#6", None)
            else:
                present_counts = {k: len(v) for k, v in self._state.prospected_samples.items()}
                total_asteroids = self._state.prospected_count if self._state.prospected_count > 0 else 1
                for idx, name in enumerate(rows):
                    range_label = self._format_range_label(name)
                    present = present_counts.get(name, 0)
                    percent = (present / total_asteroids) * 100 if total_asteroids else 0
                    commodity_value = self._format_cargo_name(name)
                    range_value = range_label
                    item = cargo_tree.insert(
                        "",
                        "end",
                        values=(
                            commodity_value,
                            present,
                            f"{percent:.1f}",
                            self._state.cargo_totals.get(name, 0),
                            range_value,
                            self._format_tph(name),
                        ),
                        tags=("odd" if idx % 2 else "even",),
                    )
                    self._cargo_item_to_commodity[item] = name
                    if self._cargo_tooltip:
                        self._cargo_tooltip.set_cell_text(
                            item,
                            "#6",
                            self._make_tph_tooltip(name),
                        )
                cargo_tree.after(0, self._render_range_links)

        materials_tree = self._materials_tree
        if materials_tree and getattr(materials_tree, "winfo_exists", lambda: False)():
            if self._theme.is_dark_theme:
                materials_tree.tag_configure(
                    "even",
                    background=self._theme.table_background_color(),
                    foreground=self._theme.table_foreground_color(),
                )
                materials_tree.tag_configure(
                    "odd",
                    background=self._theme.table_stripe_color(),
                    foreground=self._theme.table_foreground_color(),
                )
            materials_tree.delete(*materials_tree.get_children())
            if not self._state.materials_collected:
                materials_tree.insert(
                    "", "end", values=("No materials collected yet", ""), tags=("even",)
                )
            else:
                for idx, name in enumerate(sorted(self._state.materials_collected)):
                    materials_tree.insert(
                        "",
                        "end",
                        values=(self._format_cargo_name(name), self._state.materials_collected[name]),
                        tags=("odd" if idx % 2 else "even",),
                    )

        if self._total_tph_var is not None:
            total_rate = self._compute_total_tph()
            total_amount = sum(self._state.cargo_additions.values())
            if total_rate is None:
                self._total_tph_var.set("Total Tons/hr: -")
            else:
                duration = 0.0
                if self._state.mining_start:
                    start_time = self._ensure_aware(self._state.mining_start)
                    end_time = self._ensure_aware(self._state.mining_end or datetime.now(timezone.utc))
                    duration = max(0.0, (end_time - start_time).total_seconds())
                duration_str = self._format_duration(duration)
                self._total_tph_var.set(
                    f"Total Tons/hr: {self._format_rate(total_rate)} ({total_amount}t over {duration_str})"
                )

        self._refresh_histogram_windows()

    # ------------------------------------------------------------------
    # Preference callbacks
    # ------------------------------------------------------------------
    def _on_histogram_bin_change(self, *_: object) -> None:
        if self._prefs_bin_var is None or self._updating_bin_var:
            return
        try:
            value = int(self._prefs_bin_var.get())
        except (TypeError, ValueError, tk.TclError):
            return
        size = clamp_bin_size(value)
        if size == self._state.histogram_bin_size:
            return
        self._state.histogram_bin_size = size
        if self._prefs_bin_var.get() != size:
            self._updating_bin_var = True
            self._prefs_bin_var.set(size)
            self._updating_bin_var = False
        self._recompute_histograms()
        self.refresh()

    def _on_rate_interval_change(self, *_: object) -> None:
        if self._prefs_rate_var is None or self._updating_rate_var:
            return
        try:
            value = int(self._prefs_rate_var.get())
        except (TypeError, ValueError, tk.TclError):
            return
        interval = clamp_rate_interval(value)
        if interval == self._state.rate_interval_seconds:
            return
        self._state.rate_interval_seconds = interval
        if self._prefs_rate_var.get() != interval:
            self._updating_rate_var = True
            self._prefs_rate_var.set(interval)
            self._updating_rate_var = False
        self.schedule_rate_update()

    def _on_refinement_window_change(self, *_: object) -> None:
        if (
            self._prefs_refinement_window_var is None
            or self._updating_refinement_window_var
        ):
            return
        try:
            value = int(self._prefs_refinement_window_var.get())
        except (TypeError, ValueError, tk.TclError):
            return
        window = clamp_positive_int(value, self._state.refinement_lookback_seconds, maximum=3600)
        if window == self._state.refinement_lookback_seconds:
            return
        self._state.refinement_lookback_seconds = window
        if self._prefs_refinement_window_var.get() != window:
            self._updating_refinement_window_var = True
            self._prefs_refinement_window_var.set(window)
            self._updating_refinement_window_var = False
        update_rpm(self._state)
        self._update_rpm_indicator()

    def _on_rpm_threshold_change(self, *_: object) -> None:
        if (
            self._prefs_rpm_red_var is None
            or self._prefs_rpm_yellow_var is None
            or self._prefs_rpm_green_var is None
            or self._updating_rpm_vars
        ):
            return
        try:
            red_value = int(self._prefs_rpm_red_var.get())
            yellow_value = int(self._prefs_rpm_yellow_var.get())
            green_value = int(self._prefs_rpm_green_var.get())
        except (TypeError, ValueError, tk.TclError):
            return

        red = clamp_positive_int(red_value, self._state.rpm_threshold_red)
        yellow = clamp_positive_int(yellow_value, self._state.rpm_threshold_yellow)
        green = clamp_positive_int(green_value, self._state.rpm_threshold_green)

        if red > yellow:
            yellow = red
        if yellow > green:
            green = yellow

        changed = (
            red != self._state.rpm_threshold_red
            or yellow != self._state.rpm_threshold_yellow
            or green != self._state.rpm_threshold_green
        )

        self._state.rpm_threshold_red = red
        self._state.rpm_threshold_yellow = yellow
        self._state.rpm_threshold_green = green

        self._updating_rpm_vars = True
        self._prefs_rpm_red_var.set(red)
        self._prefs_rpm_yellow_var.set(yellow)
        self._prefs_rpm_green_var.set(green)
        self._updating_rpm_vars = False

        if changed:
            self._update_rpm_indicator()

    def _on_inara_mode_change(self, *_: object) -> None:
        if self._prefs_inara_mode_var is None or self._updating_inara_mode_var:
            return
        try:
            value = int(self._prefs_inara_mode_var.get())
        except (TypeError, ValueError, tk.TclError):
            return
        self._inara.set_search_mode(value)
        if self._prefs_inara_mode_var.get() != self._state.inara_settings.search_mode:
            self._updating_inara_mode_var = True
            self._prefs_inara_mode_var.set(self._state.inara_settings.search_mode)
            self._updating_inara_mode_var = False
        self._render_range_links()

    def _on_inara_carriers_change(self, *_: object) -> None:
        if self._prefs_inara_carriers_var is None or self._updating_inara_carriers_var:
            return
        try:
            value = bool(self._prefs_inara_carriers_var.get())
        except (tk.TclError, ValueError):
            return
        self._inara.set_include_carriers(value)
        if bool(self._prefs_inara_carriers_var.get()) != self._state.inara_settings.include_carriers:
            self._updating_inara_carriers_var = True
            self._prefs_inara_carriers_var.set(self._state.inara_settings.include_carriers)
            self._updating_inara_carriers_var = False
        self._render_range_links()

    def _on_inara_surface_change(self, *_: object) -> None:
        if self._prefs_inara_surface_var is None or self._updating_inara_surface_var:
            return
        try:
            value = bool(self._prefs_inara_surface_var.get())
        except (tk.TclError, ValueError):
            return
        self._inara.set_include_surface(value)
        if bool(self._prefs_inara_surface_var.get()) != self._state.inara_settings.include_surface:
            self._updating_inara_surface_var = True
            self._prefs_inara_surface_var.set(self._state.inara_settings.include_surface)
            self._updating_inara_surface_var = False
        self._render_range_links()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_reset(self) -> None:
        self._on_reset()

    def _toggle_pause(self) -> None:
        self.set_paused(not self._state.is_paused, source="manual")

    def set_paused(self, paused: bool, *, source: str = "manual") -> None:
        target = bool(paused)
        if target == self._state.is_paused:
            self._update_pause_button()
            self._refresh_status_line()
            self._update_summary_tooltip()
            return
        self._state.is_paused = target
        if self._pause_callback:
            try:
                self._pause_callback(target, source, datetime.now(timezone.utc))
            except Exception:
                _log.exception("Failed to notify pause state change")
        if target:
            self.cancel_rate_update()
            self._cancel_rpm_update()
        else:
            # Always keep RPM timer active when not paused
            self._schedule_rpm_update()
            if self._state.is_mining:
                self.schedule_rate_update()
        self._update_pause_button()
        self._refresh_status_line()
        self._update_summary_tooltip()

    def is_paused(self) -> bool:
        return self._state.is_paused

    def _update_pause_button(self) -> None:
        button = self._pause_btn
        if not button:
            return
        label = "Resume" if self._state.is_paused else "Pause"
        try:
            button.configure(text=label)
        except tk.TclError:
            pass

    def _on_rate_update_tick(self) -> None:
        self._rate_update_job = None
        if self._state.is_paused:
            return
        frame = self._frame
        if frame and frame.winfo_exists():
            self.refresh()
        self.schedule_rate_update()

    def _on_cargo_click(self, event: tk.Event) -> None:  # type: ignore[override]
        tree = self._cargo_tree
        if not tree:
            return
        column = tree.identify_column(event.x)
        item = tree.identify_row(event.y)
        commodity = self._cargo_item_to_commodity.get(item)
        if not commodity:
            return
        if column == "#5":
            if not self._format_range_label(commodity):
                return
            self.open_histogram_window(commodity)
        elif column == "#1":
            self._inara.open_link(commodity)

    def _on_cargo_motion(self, event: tk.Event) -> None:  # type: ignore[override]
        tree = self._cargo_tree
        if not tree:
            return
        column = tree.identify_column(event.x)
        item = tree.identify_row(event.y)
        commodity = self._cargo_item_to_commodity.get(item)
        if column == "#5" and commodity and self._format_range_label(commodity):
            tree.configure(cursor="hand2")
        elif (
            column == "#1"
            and commodity
            and commodity.lower() in self._inara.commodity_map
            and self._state.current_system
        ):
            tree.configure(cursor="hand2")
        else:
            tree.configure(cursor="")

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _render_range_links(self) -> None:
        tree = self._cargo_tree
        if not tree or not getattr(tree, "winfo_exists", lambda: False)() or self._content_collapsed:
            self._clear_range_link_labels()
            self._clear_commodity_link_labels()
            return

        self._clear_range_link_labels()
        self._clear_commodity_link_labels()

        try:
            base_font = tree.cget("font")
        except tk.TclError:
            self._clear_commodity_link_labels()
            return

        if not self._range_link_font:
            try:
                font = tkfont.nametofont(base_font)
                self._range_link_font = tkfont.Font(font=font)
                self._range_link_font.configure(underline=True)
            except tk.TclError:
                self._range_link_font = tkfont.Font(family="TkDefaultFont", size=9, underline=True)

        pending = False
        for item, commodity in self._cargo_item_to_commodity.items():
            range_label = self._format_range_label(commodity)
            if not range_label:
                continue
            try:
                bbox = tree.bbox(item, "#5")
            except tk.TclError:
                bbox = None
            if not bbox:
                pending = True
                continue
            x, y, width, height = bbox
            if width <= 0 or height <= 0:
                continue
            tags = tree.item(item, "tags") or ()
            bg_color = self._theme.table_background_color()
            if "odd" in tags:
                bg_color = self._theme.table_stripe_color()
            label = tk.Label(
                tree,
                text=range_label,
                cursor="hand2",
                anchor="center",
                background=bg_color,
                foreground=self._theme.link_color(),
                bd=0,
                highlightthickness=0,
            )
            try:
                label.configure(font=self._range_link_font)
            except Exception:
                pass
            self._theme.register(label)
            try:
                label.place(x=x + 2, y=y + 1, width=width - 4, height=height - 2)
                try:
                    label.lift()
                except Exception:
                    pass
                label.bind("<Button-1>", lambda _evt, commodity=commodity: self.open_histogram_window(commodity))
                self._range_link_labels[item] = label
            except Exception:
                try:
                    label.destroy()
                except Exception:
                    pass
                pending = True
                continue

        commodity_pending = self._render_commodity_links()
        if pending or commodity_pending:
            tree.after(16, self._render_range_links)

    def _render_commodity_links(self) -> bool:
        tree = self._cargo_tree
        if not tree or not getattr(tree, "winfo_exists", lambda: False)() or self._content_collapsed:
            self._clear_commodity_link_labels()
            return False

        if not self._state.current_system or not self._inara.commodity_map:
            self._clear_commodity_link_labels()
            return False

        self._clear_commodity_link_labels()

        try:
            base_font = tree.cget("font")
        except tk.TclError:
            return False

        if not self._commodity_link_font:
            try:
                font = tkfont.nametofont(base_font)
                self._commodity_link_font = tkfont.Font(font=font)
                self._commodity_link_font.configure(underline=True)
            except tk.TclError:
                self._commodity_link_font = tkfont.Font(family="TkDefaultFont", size=9, underline=True)

        pending = False
        for item, commodity in self._cargo_item_to_commodity.items():
            if commodity.lower() not in self._inara.commodity_map:
                continue
            bbox = tree.bbox(item, "#1")
            if not bbox:
                pending = True
                continue
            x, y, width, height = bbox
            if width <= 0 or height <= 0:
                continue
            tags = tree.item(item, "tags") or ()
            bg_color = self._theme.table_background_color()
            if "odd" in tags:
                bg_color = self._theme.table_stripe_color()
            label = tk.Label(
                tree,
                text=self._format_cargo_name(commodity),
                cursor="hand2",
                anchor="w",
                background=bg_color,
                foreground=self._theme.link_color(),
                bd=0,
                highlightthickness=0,
            )
            try:
                label.configure(font=self._commodity_link_font)
            except Exception:
                pass
            self._theme.register(label)
            pad_x, pad_y = 4, 1
            try:
                label.place(
                    x=x + pad_x,
                    y=y + pad_y,
                    width=max(0, width - pad_x * 2),
                    height=max(0, height - pad_y * 2),
                )
                try:
                    label.lift()
                except Exception:
                    pass
            except Exception:
                continue
            label.bind("<Button-1>", lambda _evt, commodity=commodity: self._inara.open_link(commodity))
            self._commodity_link_labels[item] = label

        return pending

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _format_cargo_name(name: str) -> str:
        return name.replace("_", " ").title()

    def _compute_tph(self, commodity: str) -> Optional[float]:
        start = self._state.commodity_start_times.get(commodity)
        if not start:
            return None
        start = self._ensure_aware(start)
        end_time = self._ensure_aware(self._state.mining_end or datetime.now(timezone.utc))
        elapsed_hours = (end_time - start).total_seconds() / 3600.0
        if elapsed_hours <= 0:
            return None
        amount = self._state.cargo_additions.get(commodity, 0)
        if amount <= 0:
            return None
        return amount / elapsed_hours

    def _format_tph(self, commodity: str) -> str:
        rate = self._compute_tph(commodity)
        if rate is None:
            return ""
        return self._format_rate(rate)

    def _make_tph_tooltip(self, commodity: str) -> Optional[str]:
        rate = self._compute_tph(commodity)
        start = self._state.commodity_start_times.get(commodity)
        amount = self._state.cargo_additions.get(commodity, 0)
        if rate is None or start is None or amount <= 0:
            return None
        end_time = self._ensure_aware(self._state.mining_end or datetime.now(timezone.utc))
        duration = max(0.0, (end_time - self._ensure_aware(start)).total_seconds())
        return f"{amount}t over {self._format_duration(duration)}"

    def _format_range_label(self, commodity: str) -> str:
        if commodity not in self._state.harvested_commodities:
            return ""
        samples = self._state.prospected_samples.get(commodity)
        if not samples:
            return ""
        numeric_samples: list[float] = []
        for value in samples:
            try:
                numeric_samples.append(float(value))
            except (TypeError, ValueError):
                continue
        if not numeric_samples:
            return ""
        if len(numeric_samples) == 1:
            return f"{numeric_samples[0]:.1f}%"
        stats = compute_percentage_stats(numeric_samples)
        if not stats:
            return ""
        low, avg, high = stats
        return f"{low:.1f}%-{avg:.1f}%-{high:.1f}%"

    def _compute_total_tph(self) -> Optional[float]:
        if not self._state.mining_start:
            return None
        total_amount = sum(amount for amount in self._state.cargo_additions.values() if amount > 0)
        if total_amount <= 0:
            return None
        start_time = self._ensure_aware(self._state.mining_start)
        end_time = self._ensure_aware(self._state.mining_end or datetime.now(timezone.utc))
        elapsed_hours = (end_time - start_time).total_seconds() / 3600.0
        if elapsed_hours <= 0:
            return None
        return total_amount / elapsed_hours

    @staticmethod
    def _format_rate(rate: float) -> str:
        if rate >= 10:
            return f"{rate:.0f}"
        if rate >= 1:
            return f"{rate:.1f}"
        return f"{rate:.2f}"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        total_seconds = max(0, int(seconds))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes}m {secs}s"
        if minutes:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    @staticmethod
    def _ensure_aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @staticmethod
    def _calculate_elapsed_seconds(start: datetime, end: datetime) -> float:
        start_time = edmcmaMiningUI._ensure_aware(start)
        end_time = edmcmaMiningUI._ensure_aware(end)
        return max(0.0, (end_time - start_time).total_seconds())

    @staticmethod
    def _format_bin_label(bin_index: int, size: int) -> str:
        start = bin_index * size
        end = min(start + size, 100)
        return f"{int(start)}-{int(end)}%"

    def _clear_range_link_labels(self) -> None:
        for label in self._range_link_labels.values():
            if label.winfo_exists():
                label.destroy()
        self._range_link_labels.clear()

    def _clear_commodity_link_labels(self) -> None:
        for label in self._commodity_link_labels.values():
            if label.winfo_exists():
                label.destroy()
        self._commodity_link_labels.clear()

    def open_histogram_window(self, commodity: str) -> None:
        _hist_open(self, commodity)
        if window and window.winfo_exists():
            canvas = self._hist_canvases.get(commodity)
            if canvas and canvas.winfo_exists():
                self._draw_histogram(canvas, commodity)
            window.lift()
            return

        parent = self._frame
        if parent is None:
            return

        top = tk.Toplevel(parent)
        self._theme.register(top)
        top.title(f"{self._format_cargo_name(commodity)} histogram")
        canvas = tk.Canvas(
            top,
            width=360,
            height=200,
            background=self._theme.table_background_color(),
            highlightthickness=0,
        )
        canvas.pack(fill="both", expand=True)
        self._theme.register(canvas)
        top.bind(
            "<Configure>",
            lambda event, c=commodity, cv=canvas: self._draw_histogram(cv, c),
        )
        if not hasattr(canvas, "_theme_change_bound"):
            canvas.bind(
                "<<ThemeChanged>>",
                lambda _evt, c=commodity, cv=canvas: self._draw_histogram(cv, c),
                add="+",
            )
            canvas._theme_change_bound = True
        self._draw_histogram(canvas, commodity, counter)
        top.protocol("WM_DELETE_WINDOW", lambda c=commodity: self._close_histogram_window(c))
        self._hist_windows[commodity] = top
        self._hist_canvases[commodity] = canvas

    def close_histogram_windows(self) -> None:
        _hist_close_windows(self)

    def _close_histogram_window(self, commodity: str) -> None:
        _hist_close_window(self, commodity)

    def _draw_histogram(self, canvas: tk.Canvas, commodity: str, counter: Optional[Counter[int]] = None) -> None:
        _hist_draw(self, canvas, commodity, counter)

    def _refresh_histogram_windows(self) -> None:
        _hist_refresh(self)


    def _recompute_histograms(self) -> None:
        _hist_recompute(self)
