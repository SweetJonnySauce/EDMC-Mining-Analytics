"""EDMC Mining Analytics plugin entry point.

This module integrates with EDMC to track mining activity, surface
stateful information on the UI, expose a preferences pane, and perform
housekeeping tasks such as version checking and logging.
"""

from __future__ import annotations

import json
import logging
import random
import threading
import webbrowser
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Tuple
from urllib import error, request
from urllib.parse import urlencode

try:
    import tkinter as tk
    from tkinter import ttk
    import tkinter.font as tkfont
except ImportError as exc:  # pragma: no cover - EDMC always provides tkinter
    raise RuntimeError("Tkinter must be available for EDMC plugins") from exc

try:
    import myNotebook as nb  # type: ignore[import]
except ImportError:  # pragma: no cover - only available inside EDMC
    nb = None  # type: ignore[assignment]

_PLUGIN_FILE = Path(__file__).resolve()
try:
    _PLUGIN_ROOT_NAME = _PLUGIN_FILE.parents[1].name
except IndexError:  # pragma: no cover - only triggered in non-standard layouts
    _PLUGIN_ROOT_NAME = _PLUGIN_FILE.parent.name

try:
    from config import appname, config  # type: ignore[import]
except ImportError:  # pragma: no cover - only available inside EDMC
    appname = "EDMarketConnector"  # type: ignore[assignment]
    config = None  # type: ignore[assignment]

from .util.tooltip import TreeTooltip

PLUGIN_NAME = "EDMC Mining Analytics"
PLUGIN_VERSION = "0.1.2"
GITHUB_RELEASES_API = (
    "https://api.github.com/repos/SweetJonnySauce/EDMC-Mining-Analytics/releases/latest"
)
GITHUB_TAGS_API = "https://api.github.com/repos/SweetJonnySauce/EDMC-Mining-Analytics/tags?per_page=1"

_LOGGER_NAMESPACE = f"{appname}.{_PLUGIN_ROOT_NAME}" if appname else _PLUGIN_ROOT_NAME


def _coerce_log_level(value: object) -> Optional[int]:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        if candidate.isdigit():
            try:
                return int(candidate)
            except ValueError:
                return None
        upper = candidate.upper()
        return logging._nameToLevel.get(upper)  # type: ignore[attr-defined]
    return None


def _resolve_edmc_log_level() -> int:
    base_logger = logging.getLogger(appname) if appname else logging.getLogger()
    fallback = base_logger.getEffectiveLevel()
    if config is None:
        return fallback

    candidates = ("loglevel", "log_level", "logging_level")
    getters = ("getint", "get", "get_str")

    for key in candidates:
        for getter_name in getters:
            getter = getattr(config, getter_name, None)
            if getter is None:
                continue
            try:
                raw_value = getter(key)
            except Exception:
                continue
            level = _coerce_log_level(raw_value)
            if level is not None:
                return level
    return fallback


def _initialise_plugin_logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAMESPACE)
    logger.setLevel(_resolve_edmc_log_level())
    logger.propagate = True
    return logger


_log = _initialise_plugin_logger()

class MiningAnalyticsPlugin:
    """Encapsulates plugin state and behaviour for EDMC."""

    def __init__(self) -> None:
        self.plugin_dir: Optional[Path] = None
        self._is_mining = False
        self._status_var: Optional[tk.StringVar] = None
        self._summary_var: Optional[tk.StringVar] = None
        self._ui_frame: Optional[tk.Widget] = None
        self._table_frame: Optional[tk.Widget] = None
        self._cargo_tree: Optional[ttk.Treeview] = None
        self._materials_frame: Optional[ttk.Frame] = None
        self._materials_tree: Optional[ttk.Treeview] = None
        self._status_label: Optional[ttk.Label] = None
        self._summary_label: Optional[ttk.Label] = None
        self._cargo_label: Optional[ttk.Label] = None
        self._materials_label: Optional[ttk.Label] = None
        self._mining_start: Optional[datetime] = None
        self._mining_end: Optional[datetime] = None
        self._prospected_count = 0
        self._already_mined_count = 0
        self._latest_version: Optional[str] = None
        self._version_check_started = False
        self._cargo_additions: dict[str, int] = {}
        self._cargo_totals: dict[str, int] = {}
        self._limpets_remaining: Optional[int] = None
        self._limpets_start: Optional[int] = None
        self._limpets_start_initialized = False
        self._collection_drones_launched = 0
        self._prospector_launched_count = 0  # already present, but ensure it's here for clarity
        self._abandoned_limpets = 0
        self._last_event_was_drone_launch = False
        self._harvested_commodities: set[str] = set()
        self._commodity_start_times: dict[str, datetime] = {}
        self._prospector_launched_count = 0
        self._prospect_content_counts: Counter[str] = Counter()
        self._materials_collected: Counter[str] = Counter()
        self._last_cargo_counts: dict[str, int] = {}
        self._histogram_bin_size = 10
        self._prefs_bin_var: Optional[tk.IntVar] = None
        self._updating_bin_var = False
        self._rate_interval_seconds = 30
        self._prefs_rate_var: Optional[tk.IntVar] = None
        self._updating_rate_var = False
        self._rate_update_job: Optional[int] = None
        self._prospected_seen: set[Tuple[str, Tuple[Tuple[str, float], ...]]] = set()
        self._prospected_samples: dict[str, list[float]] = defaultdict(list)
        self._prospected_histogram: dict[str, Counter[int]] = defaultdict(Counter)
        self._duplicate_prospected = 0
        self._cargo_tooltip: Optional[TreeTooltip] = None
        self._total_tph_label: Optional[ttk.Label] = None
        self._total_tph_var: Optional[tk.StringVar] = None
        self._reset_button: Optional[ttk.Button] = None
        self._hist_windows: dict[str, tk.Toplevel] = {}
        self._cargo_item_to_commodity: dict[str, str] = {}
        self._range_link_labels: dict[str, tk.Label] = {}
        self._range_link_font: Optional[tkfont.Font] = None
        self._commodity_link_labels: dict[str, tk.Label] = {}
        self._commodity_link_font: Optional[tkfont.Font] = None
        self._content_widgets: list[tk.Widget] = []
        self._content_collapsed = False
        self._user_expanded = False
        self._mining_location: Optional[str] = None
        self._current_system: Optional[str] = None
        self._commodity_link_map: dict[str, int] = {}
        self._inara_search_mode = 1
        self._inara_include_carriers = True
        self._inara_include_surface = True
        self._prefs_inara_mode_var: Optional[tk.IntVar] = None
        self._prefs_inara_carriers_var: Optional[tk.BooleanVar] = None
        self._prefs_inara_surface_var: Optional[tk.BooleanVar] = None
        self._updating_inara_mode_var = False
        self._updating_inara_carriers_var = False
        self._updating_inara_surface_var = False

    # ------------------------------------------------------------------
    # EDMC lifecycle hooks
    # ------------------------------------------------------------------
    def plugin_start(self, plugin_dir: str) -> str:
        self.plugin_dir = Path(plugin_dir)
        self._sync_logger_level()
        _log.info("Starting %s v%s", PLUGIN_NAME, PLUGIN_VERSION)
        self._load_configuration()
        self._load_commodity_link_map()
        self._ensure_version_check()
        return PLUGIN_NAME

    def plugin_app(self, parent: tk.Widget) -> ttk.Frame:
        frame = ttk.Frame(parent)

        self._ui_frame = frame
        self._status_var = tk.StringVar(master=frame, value="Not mining")
        self._status_label = ttk.Label(frame, textvariable=self._status_var, justify="left", anchor="w")
        self._status_label.grid(row=0, column=0, columnspan=3, sticky="w", padx=4, pady=(4, 2))

        self._summary_var = tk.StringVar(master=frame, value="")
        self._summary_label = ttk.Label(frame, textvariable=self._summary_var, justify="left", anchor="w")
        self._summary_label.grid(row=1, column=0, columnspan=3, sticky="w", padx=4, pady=(0, 6))

        self._cargo_label = ttk.Label(frame, text="Mined Commodities", font=(None, 9, "bold"), anchor="w")
        self._cargo_label.grid(row=2, column=0, sticky="w", padx=4)

        self._table_frame = ttk.Frame(frame)
        self._table_frame.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=4, pady=(2, 6))
        header_font = tkfont.Font(family="TkDefaultFont", size=9, weight="normal")
        self._cargo_tree = ttk.Treeview(
            self._table_frame,
            columns=("commodity", "present", "percent", "total", "range", "tph"),
            show="headings",
            height=5,
            selectmode="none",
        )
        self._cargo_tree.heading("commodity", text="Commodity", anchor="center")
        self._cargo_tree.heading("present", text="#", anchor="center")
        self._cargo_tree.heading("percent", text="%", anchor="center")
        self._cargo_tree.heading("total", text="Total", anchor="center")
        self._cargo_tree.heading("range", text="%Range", anchor="center")
        self._cargo_tree.heading("tph", text="Tons/hr", anchor="center")

        # Header tooltips will be registered after the TreeTooltip instance is created
        for col in ("commodity", "present", "percent", "total", "range", "tph"):
            self._cargo_tree.column(col, anchor="center", stretch=True, width=60)
        self._cargo_tree.column("commodity", width=110)
        self._cargo_tree.column("range", width=80)
        self._cargo_tree.pack(fill="both", expand=True)
        style = ttk.Style()
        style.configure("Treeview.Heading", font=header_font)
        self._cargo_tooltip = TreeTooltip(self._cargo_tree)
        # Add tooltips for column headers
        if self._cargo_tooltip:
            self._cargo_tooltip.set_heading_tooltip("present", "Number of asteroids prospected where this commodity is present.")
            self._cargo_tooltip.set_heading_tooltip("percent", "Percentage of asteroids prospected where this commodity is present.")
            self._cargo_tooltip.set_heading_tooltip("total", "Total number of tons collected.")
            self._cargo_tooltip.set_heading_tooltip("range", "Min/Max percentages of this commodity on an asteroid when found.")
            self._cargo_tooltip.set_heading_tooltip("tph", "Projected tons collected per hour of mining.")
        self._cargo_tree.bind("<ButtonRelease-1>", self._on_cargo_click, add="+")
        self._cargo_tree.bind("<Motion>", self._on_cargo_motion, add="+")
        self._cargo_tree.bind("<Configure>", lambda _e: self._render_range_links(), add="+")
        self._cargo_tree.bind("<ButtonRelease-3>", lambda _e: self._render_range_links(), add="+")
        self._cargo_tree.bind("<KeyRelease>", lambda _e: self._render_range_links(), add="+")
        self._cargo_tree.bind("<MouseWheel>", lambda _e: self._render_range_links(), add="+")
        self._cargo_tree.bind("<ButtonRelease-4>", lambda _e: self._render_range_links(), add="+")
        self._cargo_tree.bind("<ButtonRelease-5>", lambda _e: self._render_range_links(), add="+")

        self._total_tph_var = tk.StringVar(master=frame, value="Total Tons/hr: -")
        self._total_tph_label = ttk.Label(frame, textvariable=self._total_tph_var, anchor="w")
        self._total_tph_label.grid(row=4, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 6))
        self._reset_button = ttk.Button(frame, text="Reset", command=self._on_reset)
        self._reset_button.grid(row=4, column=2, sticky="e", padx=4, pady=(0, 6))

        self._materials_label = ttk.Label(frame, text="Materials Collected", font=(None, 9, "bold"), anchor="w")
        self._materials_label.grid(row=5, column=0, sticky="w", padx=4)

        self._materials_frame = ttk.Frame(frame)
        self._materials_frame.grid(row=6, column=0, columnspan=3, sticky="nsew", padx=4, pady=(2, 6))
        self._materials_tree = ttk.Treeview(
            self._materials_frame,
            columns=("material", "quantity"),
            show="headings",
            height=5,
            selectmode="none",
        )
        self._materials_tree.heading("material", text="Material")
        self._materials_tree.heading("quantity", text="Count")
        self._materials_tree.column("material", anchor="w", stretch=True, width=160)
        self._materials_tree.column("quantity", anchor="center", stretch=False, width=80)
        self._materials_tree.pack(fill="both", expand=True)

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=0)
        frame.columnconfigure(2, weight=0)
        frame.rowconfigure(6, weight=1)

        self._content_widgets = [
            self._cargo_label,
            self._total_tph_label,
            self._table_frame,
            self._reset_button,
            self._materials_label,
            self._materials_frame,
        ]

        self._refresh_status_ui()
        self._schedule_rate_update()

        return frame

    def plugin_prefs(
        self,
        parent: tk.Widget,
        cmdr: Optional[str] = None,
        is_beta: bool = False,
    ) -> tk.Widget:
        if nb is not None:
            frame: tk.Widget = nb.Frame(parent)
        else:
            frame = ttk.Frame(parent)
        ttk.Label(frame, text="EDMC Mining Analytics").grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 2)
        )
        ttk.Label(
            frame,
            text="Prospecting histogram bin size (percentage range per bin)",
            wraplength=400,
            justify="left",
        ).grid(row=1, column=0, sticky="w", padx=10, pady=(0, 4))

        self._prefs_bin_var = tk.IntVar(master=frame, value=self._histogram_bin_size)
        self._prefs_bin_var.trace_add("write", self._on_bin_var_change)
        ttk.Spinbox(
            frame,
            from_=1,
            to=100,
            textvariable=self._prefs_bin_var,
            width=6,
        ).grid(row=2, column=0, sticky="w", padx=10, pady=(0, 10))

        ttk.Label(
            frame,
            text="Tons/hour auto-update interval (seconds)",
            wraplength=400,
            justify="left",
        ).grid(row=3, column=0, sticky="w", padx=10, pady=(0, 4))

        self._prefs_rate_var = tk.IntVar(master=frame, value=self._rate_interval_seconds)
        self._prefs_rate_var.trace_add("write", self._on_rate_var_change)
        ttk.Spinbox(
            frame,
            from_=5,
            to=3600,
            increment=5,
            textvariable=self._prefs_rate_var,
            width=6,
        ).grid(row=4, column=0, sticky="w", padx=10, pady=(0, 10))

        inara_frame = ttk.LabelFrame(frame, text="Inara Links")
        inara_frame.grid(row=5, column=0, sticky="ew", padx=10, pady=(0, 10))
        inara_frame.columnconfigure(0, weight=1)

        ttk.Label(
            inara_frame,
            text="Configure how commodity hyperlinks open Inara searches.",
            wraplength=380,
            justify="left",
        ).grid(row=0, column=0, sticky="w", pady=(4, 6))

        self._prefs_inara_mode_var = tk.IntVar(master=inara_frame, value=self._inara_search_mode)
        self._prefs_inara_mode_var.trace_add("write", self._on_inara_mode_change)
        mode_container = ttk.Frame(inara_frame)
        mode_container.grid(row=1, column=0, sticky="w", pady=(0, 6))
        ttk.Radiobutton(
            mode_container,
            text="Best price search",
            value=1,
            variable=self._prefs_inara_mode_var,
        ).grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Radiobutton(
            mode_container,
            text="Distance search",
            value=3,
            variable=self._prefs_inara_mode_var,
        ).grid(row=0, column=1, sticky="w")

        self._prefs_inara_carriers_var = tk.BooleanVar(master=inara_frame, value=self._inara_include_carriers)
        self._prefs_inara_carriers_var.trace_add("write", self._on_inara_carriers_change)
        ttk.Checkbutton(
            inara_frame,
            text="Include fleet carriers in results",
            variable=self._prefs_inara_carriers_var,
        ).grid(row=2, column=0, sticky="w", pady=(0, 4))

        self._prefs_inara_surface_var = tk.BooleanVar(master=inara_frame, value=self._inara_include_surface)
        self._prefs_inara_surface_var.trace_add("write", self._on_inara_surface_change)
        ttk.Checkbutton(
            inara_frame,
            text="Include surface stations in results",
            variable=self._prefs_inara_surface_var,
        ).grid(row=3, column=0, sticky="w", pady=(0, 4))

        return frame

    def plugin_stop(self) -> None:
        _log.info("Stopping %s", PLUGIN_NAME)
        self._cancel_rate_update()
        self._is_mining = False
        self._ui_frame = None
        self._table_frame = None
        self._cargo_tree = None
        self._materials_frame = None
        self._materials_tree = None
        self._cargo_label = None
        self._materials_label = None
        self._cargo_tooltip = None
        self._total_tph_label = None
        self._total_tph_var = None
        self._clear_button = None
        self._expand_button = None
        self._content_widgets = []
        self._reset_mining_metrics()
        self._cargo_item_to_commodity = {}
        self._set_current_system(None)
        self._refresh_status_ui()

    # ------------------------------------------------------------------
    # Journal handling
    # ------------------------------------------------------------------
    def handle_journal_entry(self, entry: dict, shared_state: Optional[dict] = None) -> None:
        if not entry:
            return

        try:
            system_name = self._detect_current_system(entry)
        except Exception:
            system_name = None
        if system_name:
            self._set_current_system(system_name)

        event = entry.get("event")
        if event == "LaunchDrone":
            drone_type = entry.get("Type")
            if isinstance(drone_type, str):
                dtype = drone_type.lower()
                if dtype == "prospector":
                    if not self._is_mining:
                        # Pass shared_state to allow detection of current Body/System
                        self._update_mining_state(True, "Prospector drone launched", entry.get("timestamp"), state=shared_state)
                    self._prospector_launched_count += 1
                    self._refresh_status_ui()
                elif dtype == "collection" and self._is_mining:
                    self._collection_drones_launched += 1
                    self._refresh_status_ui()
            self._last_event_was_drone_launch = True
        else:
            self._last_event_was_drone_launch = False
            if event == "ProspectedAsteroid" and self._is_mining:
                self._register_prospected_asteroid(entry)
            elif event == "Cargo" and self._is_mining:
                self._process_cargo(entry)
            elif event == "SupercruiseEntry" and self._is_mining:
                self._update_mining_state(False, "Entered Supercruise", entry.get("timestamp"), state=shared_state)
            elif event == "MaterialCollected" and self._is_mining:
                self._register_material_collected(entry)

        if shared_state is not None:
            shared_state.update(
                {
                    "edmc_mining_active": self._is_mining,
                    "edmc_mining_start": self._mining_start.isoformat() if self._mining_start else None,
                    "edmc_mining_prospected": self._prospected_count,
                    "edmc_mining_already_mined": self._already_mined_count,
                    "edmc_mining_cargo": self._cargo_additions,
                    "edmc_mining_cargo_totals": self._cargo_totals,
                    "edmc_mining_limpets": self._limpets_remaining,
                    "edmc_mining_collection_drones": self._collection_drones_launched,
                    "edmc_mining_prospect_histogram": self._serialize_histogram(),
                    "edmc_mining_prospect_duplicates": self._duplicate_prospected,
                    "edmc_mining_histogram_bin": self._histogram_bin_size,
                    "edmc_mining_limpets_abandoned": self._abandoned_limpets,
                    "edmc_mining_prospect_content": dict(self._prospect_content_counts),
                    "edmc_mining_materials_collected": dict(self._materials_collected),
                    "edmc_mining_cargo_tph": self._serialize_tph(),
                    "edmc_mining_total_tph": self._compute_total_tph(),
                    "edmc_mining_prospectors_launched": self._prospector_launched_count,
                    "edmc_mining_prospectors_lost": max(0, self._prospector_launched_count - self._prospected_count),
                }
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _update_mining_state(self, active: bool, reason: str, timestamp: Optional[str], state: Optional[dict] = None) -> None:
        if self._is_mining == active:
            return

        if active:
            self._is_mining = True
            self._mining_start = self._parse_timestamp(timestamp) or datetime.now(timezone.utc)
            self._mining_end = None
            self._prospected_count = 0
            self._already_mined_count = 0
            self._cargo_additions = {}
            self._cargo_totals = {}
            self._reset_limpet_counters()
            self._prospected_seen.clear()
            self._prospected_samples.clear()
            self._prospected_histogram.clear()
            self._duplicate_prospected = 0
            self._harvested_commodities.clear()
            self._commodity_start_times.clear()
            self._prospect_content_counts.clear()
            self._materials_collected.clear()
            self._last_cargo_counts.clear()
            self._user_expanded = True
            # Attempt to detect the body or system we're mining at the moment mining starts
            try:
                loc = self._detect_current_location(state)
                self._mining_location = loc
            except Exception:
                self._mining_location = None
            try:
                system_name = self._detect_current_system(state)
                if system_name:
                    self._set_current_system(system_name)
            except Exception:
                # Ignore failures retrieving system name
                pass
            # Log an informational message so EDMC logs record mining start
            try:
                _log.info("Mining started at %s (location=%s) - reason: %s", self._mining_start.isoformat(), self._mining_location, reason)
            except Exception:
                # Logging must not interfere with plugin operation
                pass
            self._schedule_rate_update()
        else:
            self._is_mining = False
            self._mining_end = self._parse_timestamp(timestamp) or datetime.now(timezone.utc)
            self._user_expanded = False
            self._cancel_rate_update()
            try:
                system_name = self._detect_current_system(state)
                if system_name:
                    self._set_current_system(system_name)
            except Exception:
                pass

        _log.info("Mining state changed to %s (%s)", "active" if active else "inactive", reason)
        self._refresh_status_ui()

    def _refresh_status_ui(self) -> None:
        if self._is_mining:
            if getattr(self, "_mining_location", None):
                status_text = f"You're mining {self._mining_location}"
            else:
                status_text = "You're mining!"
        else:
            status_text = "Not mining"
        summary_text = "\n".join(self._status_summary_lines())

        if self._ui_frame and getattr(self._ui_frame, "winfo_exists", lambda: False)():
            self._ui_frame.after(0, self._apply_ui_state, status_text, summary_text)
        else:
            self._apply_ui_state(status_text, summary_text)

    def _status_summary_lines(self) -> list[str]:
        lines: list[str] = []
        if self._mining_start:
            if self._mining_end and not self._is_mining:
                start_time = self._ensure_aware(self._mining_start)
                end_time = self._ensure_aware(self._mining_end)
                elapsed_seconds = max(0.0, (end_time - start_time).total_seconds())
                lines.append(f"Elapsed: {self._format_duration(elapsed_seconds)}")
            else:
                start_dt = self._ensure_aware(self._mining_start).astimezone(timezone.utc)
                lines.append(f"Started: {start_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        else:
            label = "Elapsed" if self._mining_end and not self._is_mining else "Started"
            lines.append(f"{label}: --")

        lines.append(
            f"Prospected: {self._prospected_count} | Already mined: {self._already_mined_count} | Dupes: {self._duplicate_prospected}"
        )
        # Second line: Prospectors launched, lost, content
        lost = max(0, self._prospector_launched_count - self._prospected_count)
        content_line = ""
        if self._prospect_content_counts:
            content_line = " | Content: " + ", ".join(
                f"{l[0]}:{self._prospect_content_counts.get(l, 0)}" for l in ("High", "Medium", "Low")
            )
        lines.append(
            f"Prospectors: Launched: {self._prospector_launched_count} | Lost: {lost}{content_line}"
        )
        limpets = f"Limpets remaining: {self._limpets_remaining}" if self._limpets_remaining is not None else None
        drones = f"Collectors launched: {self._collection_drones_launched}"
        abandoned = f"Limpets abandoned: {self._abandoned_limpets}" if self._abandoned_limpets > 0 else None
        third = " | ".join(x for x in [limpets, drones, abandoned] if x)
        if third:
            lines.append(third)
        # Optionally: Materials summary (removed as per user request)
        # Optionally: No cargo data
        if not (self._cargo_totals or self._cargo_additions):
            lines.append("No cargo data yet")
        return lines

    def _detect_current_location(self, state: Optional[dict]) -> Optional[str]:
        """Return a string describing the current mining location.

        Priority: Body name -> System name -> None
        Accepts the `state` dict provided by EDMC (may be None).
        """
        if state:
            # Prefer explicit Body name
            try:
                body = state.get("Body")
                if body:
                    return str(body)
            except Exception:
                pass
            try:
                system = state.get("System") or state.get("SystemName") or state.get("StarSystem")
                if system:
                    return str(system)
            except Exception:
                pass

        # Last resort: None
        return None

    def _detect_current_system(self, state: Optional[dict]) -> Optional[str]:
        """Return the name of the current star system, if available."""
        if not state:
            return None

        for key in ("System", "SystemName", "StarSystem"):
            try:
                value = state.get(key)
            except Exception:
                value = None
            if value:
                return str(value)
        return None

    def _register_prospected_asteroid(self, entry: dict) -> None:
        key = self._make_prospect_key(entry)
        if key is None:
            _log.debug("Prospected asteroid entry missing key data: %s", entry)
            return

        if key in self._prospected_seen:
            self._duplicate_prospected += 1
            _log.debug("Duplicate prospected asteroid detected; ignoring for stats")
            self._refresh_status_ui()
            return

        self._prospected_seen.add(key)
        self._prospected_count += 1

        content_level = self._extract_content_level(entry)
        if content_level:
            self._prospect_content_counts[content_level] += 1

        remaining = entry.get("Remaining")
        try:
            remaining_value = float(remaining)
        except (TypeError, ValueError):
            remaining_value = None

        if remaining_value is not None and remaining_value < 100:
            self._already_mined_count += 1

        materials = entry.get("Materials")
        if isinstance(materials, list):
            for material in materials:
                if not isinstance(material, dict):
                    continue
                name_raw = material.get("Name")
                proportion_raw = material.get("Proportion")
                if not isinstance(name_raw, str):
                    continue
                try:
                    proportion = float(proportion_raw)
                except (TypeError, ValueError):
                    continue
                normalized = name_raw.lower()
                self._prospected_samples[normalized].append(proportion)

        self._recompute_histograms()
        self._refresh_status_ui()

    def _register_material_collected(self, entry: dict) -> None:
        name = entry.get("Name")
        if not isinstance(name, str):
            return

        count = entry.get("Count")
        try:
            quantity = max(1, int(count))
        except (TypeError, ValueError):
            quantity = 1

        normalized = name.lower()
        self._materials_collected[normalized] += quantity
        self._refresh_status_ui()


    def _on_reset(self) -> None:
        # Reset all mining data and set state to Not mining
        self._is_mining = False
        self._reset_mining_metrics()
        self._cancel_rate_update()
        self._refresh_status_ui()

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

    # Theme helpers: prefer theme lookups where possible so widgets follow EDMC's theme
    def _theme_bg_for(self, widget: tk.Widget) -> Optional[str]:
        """Return a theme-appropriate background color for the given widget.

        This uses ttk.Style lookups and falls back to the widget's current bg.
        """
        style = ttk.Style(widget)
        # Prefer treeview fieldbackground (used by tree cells), then frame background
        for style_name, option in (("Treeview", "fieldbackground"), ("TFrame", "background"), ("TLabel", "background")):
            try:
                val = style.lookup(style_name, option)
            except Exception:
                val = None
            if val:
                return val
        try:
            return widget.cget("background")
        except Exception:
            return None

    def _theme_fg_for(self, widget: tk.Widget) -> Optional[str]:
        """Return a theme-appropriate foreground/text color for the given widget.

        Uses ttk style lookups and falls back to None if not found so callers can choose a safe default.
        """
        style = ttk.Style(widget)
        for style_name, option in (("Treeview", "foreground"), ("TLabel", "foreground"), ("TButton", "foreground")):
            try:
                val = style.lookup(style_name, option)
            except Exception:
                val = None
            if val:
                return val
        return None

    def _render_range_links(self) -> None:
        tree = self._cargo_tree
        if not tree or not getattr(tree, "winfo_exists", lambda: False)() or self._content_collapsed:
            self._clear_commodity_link_labels()
            return

        self._clear_range_link_labels()

        style = ttk.Style(tree)
        # Use theme-aware background/foreground helpers to avoid hard-coded light colors
        background = self._theme_bg_for(tree) or tree.cget("background")
        base_font = tree.cget("font")
        if not self._range_link_font:
            try:
                font = tkfont.nametofont(base_font)
                self._range_link_font = tkfont.Font(font=font)
                self._range_link_font.configure(underline=True)
            except tk.TclError:
                self._range_link_font = tkfont.Font(family="TkDefaultFont", size=9, underline=True)

        pending = False
        # Move the hyperlink to the %Range column (column #5)
        for item, commodity in self._cargo_item_to_commodity.items():
            range_label = self._format_range_label(commodity)
            if not range_label:
                continue
            bbox = tree.bbox(item, "#5")  # %Range column is #5
            if not bbox:
                pending = True
                continue
            x, y, width, height = bbox
            # Use a themed ttk.Label so it follows EDMC/ttk themes. Configure a small style
            link_fg = self._theme_fg_for(tree) or "#1a4bf6"
            style = ttk.Style(tree)
            style_name = "EDMC.RangeLink.TLabel"
            # Configure style with theme-aware foreground/background where possible
            try:
                style.configure(style_name, foreground=link_fg)
                # Some themes won't honor background on labels; configure if available
                if background:
                    style.configure(style_name, background=background)
            except Exception:
                pass

            label = ttk.Label(
                tree,
                text=range_label,
                style=style_name,
                cursor="hand2",
                anchor="center",
            )
            # Ensure font/underline matches previous behavior
            try:
                label.configure(font=self._range_link_font)
            except Exception:
                # Some ttk themes may ignore font on style; ignore failures
                pass
            label.place(x=x + 2, y=y + 1, width=width - 4, height=height - 2)
            label.bind("<Button-1>", lambda _event, commodity=commodity: self._open_histogram_window(commodity))
            self._range_link_labels[item] = label

        commodity_pending = self._render_commodity_links()
        if pending or commodity_pending:
            tree.after(16, self._render_range_links)

    def _render_commodity_links(self) -> bool:
        tree = self._cargo_tree
        if not tree or not getattr(tree, "winfo_exists", lambda: False)() or self._content_collapsed:
            self._clear_commodity_link_labels()
            return False

        if self._get_system_for_links() is None or not self._commodity_link_map:
            self._clear_commodity_link_labels()
            return False

        self._clear_commodity_link_labels()

        background = self._theme_bg_for(tree) or tree.cget("background")
        base_font = tree.cget("font")
        if not self._commodity_link_font:
            try:
                font = tkfont.nametofont(base_font)
                self._commodity_link_font = tkfont.Font(font=font)
                self._commodity_link_font.configure(underline=True)
            except tk.TclError:
                self._commodity_link_font = tkfont.Font(family="TkDefaultFont", size=9, underline=True)

        style = ttk.Style(tree)
        link_fg = "#1a4bf6"
        try:
            style.configure("EDMC.CommodityLink.TLabel", foreground=link_fg)
            if background:
                style.configure("EDMC.CommodityLink.TLabel", background=background)
        except Exception:
            pass

        pending = False
        for item, commodity in self._cargo_item_to_commodity.items():
            commodity_id = self._commodity_link_map.get(commodity.lower())
            if commodity_id is None:
                continue

            bbox = tree.bbox(item, "#1")
            if not bbox:
                pending = True
                continue
            x, y, width, height = bbox
            if width <= 0 or height <= 0:
                continue

            label = ttk.Label(
                tree,
                text=self._format_cargo_name(commodity),
                style="EDMC.CommodityLink.TLabel",
                cursor="hand2",
                anchor="w",
            )
            try:
                label.configure(font=self._commodity_link_font)
            except Exception:
                pass

            pad_x = 4
            pad_y = 1
            try:
                label.place(
                    x=x + pad_x,
                    y=y + pad_y,
                    width=max(0, width - (pad_x * 2)),
                    height=max(0, height - (pad_y * 2)),
                )
            except Exception:
                continue

            label.bind(
                "<Button-1>",
                lambda _event, commodity=commodity: self._open_commodity_link(commodity),
            )
            self._commodity_link_labels[item] = label

        return pending

    def _reset_mining_metrics(self) -> None:
        self._close_histogram_windows()
        self._clear_range_link_labels()
        self._clear_commodity_link_labels()
        self._cargo_item_to_commodity.clear()
        self._mining_start = None
        self._prospected_count = 0
        self._already_mined_count = 0
        self._cargo_additions = {}
        self._cargo_totals = {}
        self._reset_limpet_counters()
        self._last_event_was_drone_launch = False
        self._prospected_seen.clear()
        self._prospected_samples.clear()
        self._prospected_histogram.clear()
        self._duplicate_prospected = 0
        self._harvested_commodities.clear()
        self._commodity_start_times.clear()
        self._prospect_content_counts.clear()
        self._materials_collected.clear()
        self._last_cargo_counts.clear()
        self._user_expanded = False
        self._mining_end = None

    def _reset_limpet_counters(self) -> None:
        self._limpets_remaining = None
        self._limpets_start = 0
        self._limpets_start_initialized = False
        self._collection_drones_launched = 0
        self._prospector_launched_count = 0
        self._abandoned_limpets = 0

    @staticmethod
    def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None

        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            _log.debug("Unable to parse timestamp: %s", value)
            return None

    @staticmethod
    def _ensure_aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def _process_cargo(self, entry: dict) -> None:
        inventory = entry.get("Inventory")
        if not isinstance(inventory, list):
            return

        # Debug: log that a Cargo entry is being processed and current limpets state
        try:
            _log.debug("Processing Cargo entry: previous_limpets=%s, limpets_in_entry=%s", self._limpets_remaining, next((i.get('Count') for i in inventory if isinstance(i, dict) and i.get('Name', '').lower() == 'drones'), None))
        except Exception:
            # Don't let logging interfere with processing
            pass

        cargo_counts: dict[str, int] = {}
        limpets = None
        for item in inventory:
            if not isinstance(item, dict):
                continue
            name = item.get("Name")
            count = item.get("Count")
            if not isinstance(name, str) or not isinstance(count, int):
                continue
            normalized = name.lower()
            cargo_counts[normalized] = count
            if normalized == "drones":
                limpets = count

        previous_limpets = self._limpets_remaining
        if limpets is not None:
            if not self._limpets_start_initialized:
                self._limpets_start = limpets
                self._limpets_start_initialized = True
            self._limpets_remaining = limpets

        if not self._last_cargo_counts:
            self._last_cargo_counts = dict(cargo_counts)
            return

        previous_counts = self._last_cargo_counts
        additions_made = False

        for name, count in cargo_counts.items():
            if name == "drones":
                continue
            prev = previous_counts.get(name, 0)
            increment = count - prev
            if increment > 0:
                additions_made = True
                new_total = self._cargo_additions.get(name, 0) + increment
                self._cargo_additions[name] = new_total
                self._cargo_totals[name] = new_total
                self._harvested_commodities.add(name)
                if name not in self._commodity_start_times:
                    timestamp = self._parse_timestamp(entry.get("timestamp"))
                    self._commodity_start_times[name] = timestamp or datetime.now(timezone.utc)

        # Prune any zeroed entries
        self._cargo_additions = {k: v for k, v in self._cargo_additions.items() if v > 0}
        self._cargo_totals = dict(self._cargo_additions)

        # Calculate abandoned limpets: starting - current - launched (prospector + collection)
        if self._limpets_start is not None and self._limpets_remaining is not None:
            launched = self._prospector_launched_count + self._collection_drones_launched - 1 #factor in initial propsector that starts mining. 
            # Treat launched limpets as contributing to abandonment: subtract launched from the delta
            abandoned = self._limpets_start - self._limpets_remaining - launched
            # Debug log with component values
            _log.debug(
                "Abandoned limpets calc: L_start=%s, L_current=%s, P=%s, C=%s, raw=%s",
                self._limpets_start,
                self._limpets_remaining,
                self._prospector_launched_count,
                self._collection_drones_launched,
                abandoned,
            )
            self._abandoned_limpets = max(0, abandoned)

        self._last_cargo_counts = dict(cargo_counts)

        should_refresh = additions_made or (
            limpets is not None
            and previous_limpets is not None
            and limpets != previous_limpets
        )

        if should_refresh:
            self._refresh_status_ui()

    @staticmethod
    def _format_cargo_name(name: str) -> str:
        return name.replace("_", " ").title()

    def _compute_tph(self, commodity: str) -> Optional[float]:
        start = self._commodity_start_times.get(commodity)
        if not start:
            return None

        start = self._ensure_aware(start)
        end_raw = self._mining_end or datetime.now(timezone.utc)
        end_time = self._ensure_aware(end_raw)
        elapsed_hours = (end_time - start).total_seconds() / 3600.0
        if elapsed_hours <= 0:
            return None

        amount = self._cargo_additions.get(commodity, 0)
        if amount <= 0:
            return None

        return amount / elapsed_hours

    def _format_tph(self, commodity: str) -> str:
        rate = self._compute_tph(commodity)
        if rate is None:
            return ""

        return self._format_rate(rate)

    def _get_system_for_links(self) -> Optional[str]:
        if self._current_system:
            return self._current_system
        return None

    def _set_current_system(self, value: Optional[str]) -> None:
        normalized = str(value).strip() if value else None
        if normalized == "":
            normalized = None
        if normalized == self._current_system:
            return
        self._current_system = normalized
        tree = self._cargo_tree
        if tree and getattr(tree, "winfo_exists", lambda: False)():
            try:
                tree.after(0, self._render_range_links)
            except Exception:
                pass

    def _build_inara_url(self, commodity: str) -> Optional[str]:
        commodity_id = self._commodity_link_map.get(commodity.lower())
        if commodity_id is None:
            return None

        system_name = self._get_system_for_links()
        if not system_name:
            _log.debug("Cannot build Inara link for %s: system unknown", commodity)
            return None

        include_carriers = "0" if self._inara_include_carriers else "1"
        include_surface = "0" if self._inara_include_surface else "1"
        search_mode = "3" if self._inara_search_mode == 3 else "1"

        query: dict[str, object] = {
            "formbrief": "1",
            "pi1": "2",
            "pa1[]": [str(commodity_id)],
            "ps1": system_name,
            "pi10": search_mode,
            "pi11": "0",
            "pi3": "3",
            "pi9": "0",
            "pi4": include_surface,
            "pi8": include_carriers,
            "pi13": "0",
            "pi5": "720",
            "pi12": "0",
            "pi7": "500",
            "pi14": "0",
            "ps3": "",
        }

        try:
            return "https://inara.cz/elite/commodities/?" + urlencode(query, doseq=True)
        except Exception:
            _log.exception("Failed to encode Inara URL for commodity %s", commodity)
        return None

    def _open_commodity_link(self, commodity: str) -> None:
        url = self._build_inara_url(commodity)
        if not url:
            return
        try:
            webbrowser.open(url)
        except Exception:
            _log.exception("Failed to open browser for commodity %s", commodity)

    def _make_tph_tooltip(self, commodity: str) -> Optional[str]:
        rate = self._compute_tph(commodity)
        start = self._commodity_start_times.get(commodity)
        amount = self._cargo_additions.get(commodity, 0)
        if rate is None or start is None or amount <= 0:
            return None

        end_raw = self._mining_end or datetime.now(timezone.utc)
        end_time = self._ensure_aware(end_raw)
        duration = max(0.0, (end_time - self._ensure_aware(start)).total_seconds())
        return f"{amount}t over {self._format_duration(duration)}"

    def _on_cargo_click(self, event: tk.Event) -> None:  # type: ignore[override]
        if not self._cargo_tree:
            return
        column = self._cargo_tree.identify_column(event.x)
        item = self._cargo_tree.identify_row(event.y)
        commodity = self._cargo_item_to_commodity.get(item)
        if not commodity:
            return
        if column == "#5":  # %Range column
            if not self._format_range_label(commodity):
                return
            self._open_histogram_window(commodity)
        elif column == "#1":  # Commodity hyperlink
            self._open_commodity_link(commodity)

    def _on_cargo_motion(self, event: tk.Event) -> None:  # type: ignore[override]
        if not self._cargo_tree:
            return
        column = self._cargo_tree.identify_column(event.x)
        item = self._cargo_tree.identify_row(event.y)
        commodity = self._cargo_item_to_commodity.get(item)
        if column == "#5" and commodity and self._format_range_label(commodity):  # %Range column
            self._cargo_tree.configure(cursor="hand2")
        elif column == "#1" and commodity and self._commodity_link_map.get(commodity.lower()) and self._get_system_for_links():
            self._cargo_tree.configure(cursor="hand2")
        else:
            self._cargo_tree.configure(cursor="")

    def _format_range_label(self, commodity: str) -> str:
        if commodity not in self._harvested_commodities:
            return ""
        samples = self._prospected_samples.get(commodity)
        if not samples:
            return ""
        cleaned = [value for value in samples if isinstance(value, (int, float))]
        if not cleaned:
            return ""
        min_val = min(cleaned)
        max_val = max(cleaned)
        if abs(max_val - min_val) < 1e-6:
            return f"{min_val:.1f}%"
        return f"{min_val:.1f}%-{max_val:.1f}%"

    def _compute_total_tph(self) -> Optional[float]:
        if not self._mining_start:
            return None

        total_amount = sum(amount for amount in self._cargo_additions.values() if amount > 0)
        if total_amount <= 0:
            return None

        start_time = self._ensure_aware(self._mining_start)
        end_raw = self._mining_end or datetime.now(timezone.utc)
        end_time = self._ensure_aware(end_raw)
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

    def _extract_content_level(self, entry: dict) -> Optional[str]:
        for key in ("Content_Localised", "Content"):
            value = entry.get(key)
            if not value:
                continue
            text = str(value).lower()
            if "high" in text:
                return "High"
            if "medium" in text:
                return "Medium"
            if "low" in text:
                return "Low"
        return None

    def _set_histogram_bin_size(self, value: int) -> None:
        size = self._clamp_bin_size(value)
        if size == self._histogram_bin_size:
            return

        self._histogram_bin_size = size
        if self._prefs_bin_var is not None:
            try:
                current = int(self._prefs_bin_var.get())
            except (TypeError, ValueError, tk.TclError):
                current = size
            if current != size:
                self._updating_bin_var = True
                self._prefs_bin_var.set(size)
                self._updating_bin_var = False

        self._recompute_histograms()
        self._refresh_status_ui()

    def _on_bin_var_change(self, *_: object) -> None:
        if self._prefs_bin_var is None or self._updating_bin_var:
            return
        try:
            value = int(self._prefs_bin_var.get())
        except (TypeError, ValueError, tk.TclError):
            return
        self._set_histogram_bin_size(value)

    def _recompute_histograms(self) -> None:
        histogram: dict[str, Counter[int]] = defaultdict(Counter)
        for material, samples in self._prospected_samples.items():
            if not samples:
                continue
            counter = histogram[material]
            for value in samples:
                bin_index = self._bin_percentage(value)
                counter[bin_index] += 1
        self._prospected_histogram = histogram

    def _bin_percentage(self, value: float) -> int:
        size = max(1, self._histogram_bin_size)
        clamped = max(0.0, min(value, 100.0))
        if clamped >= 100.0:
            clamped = 100.0 - 1e-9
        return int(clamped // size)

    def _format_bin_label(self, bin_index: int) -> str:
        size = max(1, self._histogram_bin_size)
        start = bin_index * size
        end = min(start + size, 100)
        return f"{int(start)}-{int(end)}%"

    def _get_histogram_rows(self) -> Iterable[Tuple[str, str, int]]:
        harvested = self._harvested_commodities
        if not harvested:
            return

        for material in sorted(self._prospected_histogram):
            if material not in harvested:
                continue
            counter = self._prospected_histogram[material]
            for bin_index in sorted(counter):
                count = counter[bin_index]
                if count <= 0:
                    continue
                yield material, self._format_bin_label(bin_index), count

    def _serialize_histogram(self) -> dict[str, dict[str, int]]:
        serialized: dict[str, dict[str, int]] = {}
        harvested = self._harvested_commodities
        if not harvested:
            return serialized

        for material, counter in self._prospected_histogram.items():
            if material not in harvested:
                continue
            if not counter:
                continue
            serialized[self._format_cargo_name(material)] = {
                self._format_bin_label(bin_index): count
                for bin_index, count in sorted(counter.items())
                if count > 0
            }
        return serialized

    def _serialize_tph(self) -> dict[str, float]:
        data: dict[str, float] = {}
        for commodity in self._cargo_additions:
            rate = self._compute_tph(commodity)
            if rate is None:
                continue
            data[self._format_cargo_name(commodity)] = round(rate, 3)
        return data

    def _open_histogram_window(self, commodity: str) -> None:
        counter = self._prospected_histogram.get(commodity)
        if not counter:
            return

        window = self._hist_windows.get(commodity)
        if window and window.winfo_exists():
            window.lift()
            window.focus_set()
            return

        parent = self._ui_frame or self._cargo_tree
        window = tk.Toplevel(parent)
        window.title(f"{self._format_cargo_name(commodity)} Yield Distribution")
        window.geometry("420x300")
        window.resizable(False, False)
        # Use a themed frame as the container so the background follows the theme
        container = ttk.Frame(window)
        container.pack(fill="both", expand=True)
        # Canvas will inherit the frame's background where possible; avoid forcing white
        canvas_bg = self._theme_bg_for(container) or container.cget("background")
        canvas = tk.Canvas(container, background=canvas_bg, width=420, height=300)
        canvas.pack(fill="both", expand=True)
        canvas.bind(
            "<Configure>",
            lambda event, c=commodity, cv=canvas: self._draw_histogram(cv, c),
        )
        self._draw_histogram(canvas, commodity)

        window.protocol("WM_DELETE_WINDOW", lambda c=commodity: self._close_histogram_window(c))
        self._hist_windows[commodity] = window

    def _draw_histogram(self, canvas: tk.Canvas, commodity: str, counter: Optional[Counter[int]] = None) -> None:
        canvas.delete("all")
        if counter is None:
            counter = self._prospected_histogram.get(commodity, Counter())
        items = [(bin_index, counter[bin_index]) for bin_index in sorted(counter) if counter[bin_index] > 0]
        width = int(canvas.winfo_width()) or 420
        height = int(canvas.winfo_height()) or 300
        padding_x = 40
        padding_y = 40

        style = ttk.Style(canvas)
        text_fg = self._theme_fg_for(canvas) or "#555555"
        bar_fill = style.lookup("TButton", "background") or "#4c8eda"
        bar_outline = style.lookup("TButton", "foreground") or "#224f84"

        if not items:
            canvas.create_text(
                width // 2,
                height // 2,
                text="No prospecting data",
                fill=text_fg,
                font=(None, 12),
            )
            return

        bar_area_width = width - padding_x * 2
        bar_area_height = height - padding_y * 2
        max_count = max(count for _, count in items)
        if max_count <= 0:
            max_count = 1

        bar_width = bar_area_width / max(1, len(items))
        canvas.create_line(padding_x, height - padding_y, width - padding_x, height - padding_y)
        canvas.create_line(padding_x, height - padding_y, padding_x, padding_y)

        for index, (bin_index, count) in enumerate(items):
            bar_height = (count / max_count) * (bar_area_height - 20)
            x0 = padding_x + index * bar_width + 8
            x1 = x0 + bar_width - 16
            y1 = height - padding_y
            y0 = y1 - bar_height
            canvas.create_rectangle(x0, y0, x1, y1, fill=bar_fill, outline=bar_outline)
            canvas.create_text((x0 + x1) / 2, y0 - 10, text=str(count), fill=text_fg, font=(None, 10))
            canvas.create_text((x0 + x1) / 2, y1 + 12, text=self._format_bin_label(bin_index), fill=text_fg, font=(None, 9))

    def _close_histogram_window(self, commodity: str) -> None:
        window = self._hist_windows.pop(commodity, None)
        if window and window.winfo_exists():
            window.destroy()

    def _close_histogram_windows(self) -> None:
        for commodity in list(self._hist_windows):
            self._close_histogram_window(commodity)
        self._hist_windows.clear()

    def _make_prospect_key(self, entry: dict) -> Optional[Tuple[str, Tuple[Tuple[str, float], ...]]]:
        materials = entry.get("Materials")
        if not isinstance(materials, list):
            return None

        items: list[Tuple[str, float]] = []
        for material in materials:
            if not isinstance(material, dict):
                continue
            name_raw = material.get("Name")
            proportion_raw = material.get("Proportion")
            if not isinstance(name_raw, str):
                continue
            try:
                proportion = float(proportion_raw)
            except (TypeError, ValueError):
                continue
            items.append((name_raw.lower(), round(proportion, 4)))

        if not items:
            return None

        items.sort()
        content = str(entry.get("Content", ""))
        content_localised = str(entry.get("Content_Localised", ""))
        return (f"{content}|{content_localised}", tuple(items))

    def _load_configuration(self) -> None:
        if config is None:
            self._histogram_bin_size = 10
            self._rate_interval_seconds = 30
            self._inara_search_mode = 1
            self._inara_include_carriers = True
            self._inara_include_surface = True
            return

        try:
            value = config.get_int(key="edmc_mining_histogram_bin", default=10)
        except Exception:  # pragma: no cover - defensive against config issues
            value = 10
        self._histogram_bin_size = self._clamp_bin_size(value)

        try:
            rate_value = config.get_int(key="edmc_mining_rate_interval", default=30)
        except Exception:
            rate_value = 30
        self._rate_interval_seconds = self._clamp_rate_interval(rate_value)

        try:
            search_mode_value = config.get_int(key="edmc_mining_inara_search_mode", default=1)
        except Exception:
            search_mode_value = 1
        self._inara_search_mode = 3 if search_mode_value == 3 else 1

        try:
            include_carriers_value = config.get_int(key="edmc_mining_inara_include_carriers", default=1)
        except Exception:
            include_carriers_value = 1
        self._inara_include_carriers = bool(include_carriers_value)

        try:
            include_surface_value = config.get_int(key="edmc_mining_inara_include_surface", default=1)
        except Exception:
            include_surface_value = 1
        self._inara_include_surface = bool(include_surface_value)

    def _load_commodity_link_map(self) -> None:
        mapping_path = _PLUGIN_FILE.parent / "commodity_links.json"
        if not mapping_path.exists():
            _log.debug("Commodity link mapping file not found at %s", mapping_path)
            self._commodity_link_map = {}
            return

        try:
            with mapping_path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except Exception:
            _log.exception("Failed to load commodity link mapping from %s", mapping_path)
            self._commodity_link_map = {}
            return

        if not isinstance(raw, dict):
            _log.warning("Commodity link mapping file is not a JSON object: %s", mapping_path)
            self._commodity_link_map = {}
            return

        processed: dict[str, int] = {}
        for key, value in raw.items():
            if not isinstance(key, str):
                continue
            try:
                identifier = int(value)
            except (TypeError, ValueError):
                _log.debug("Skipping commodity link mapping with non-int value: %s=%r", key, value)
                continue
            processed[key.strip().lower()] = identifier

        self._commodity_link_map = processed

    def _clamp_bin_size(self, value: int) -> int:
        try:
            size = int(value)
        except (TypeError, ValueError):
            size = 10
        return max(1, min(100, size))

    def _clamp_rate_interval(self, value: int) -> int:
        try:
            interval = int(value)
        except (TypeError, ValueError):
            interval = 30
        return max(5, min(3600, interval))

    def _apply_ui_state(self, status_text: str, summary_text: str) -> None:
        if self._status_var:
            self._status_var.set(status_text)
        if self._summary_var is not None:
            self._summary_var.set(summary_text)

        cargo_tree = self._cargo_tree
        if cargo_tree and getattr(cargo_tree, "winfo_exists", lambda: False)():
            cargo_tree.delete(*cargo_tree.get_children())
            if self._cargo_tooltip:
                self._cargo_tooltip.clear()
            self._cargo_item_to_commodity = {}
            self._clear_range_link_labels()

            rows = sorted(
                name
                for name in set(self._cargo_totals) | set(self._cargo_additions)
                if self._cargo_additions.get(name, 0) > 0
            )
            if not rows:
                item = cargo_tree.insert(
                    "",
                    "end",
                    values=("No mined commodities yet", "", "", "", "", "")
                )
                if self._cargo_tooltip:
                    self._cargo_tooltip.set_cell_text(item, "#6", None)
            else:
                # Calculate present# and percent for each commodity
                present_counts = {k: len(v) for k, v in self._prospected_samples.items()}
                total_asteroids = self._prospected_count if self._prospected_count > 0 else 1
                for name in rows:
                    range_label = self._format_range_label(name)
                    present = present_counts.get(name, 0)
                    percent = (present / total_asteroids) * 100 if total_asteroids else 0
                    item = cargo_tree.insert(
                        "",
                        "end",
                        values=(
                            self._format_cargo_name(name),
                            present,
                            f"{percent:.1f}",
                            self._cargo_totals.get(name, 0),
                            range_label,
                            self._format_tph(name),
                        ),
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
            materials_tree.delete(*materials_tree.get_children())

            if not self._materials_collected:
                materials_tree.insert("", "end", values=("No materials collected yet", ""))
            else:
                for name in sorted(self._materials_collected):
                    materials_tree.insert(
                        "",
                        "end",
                        values=(self._format_cargo_name(name), self._materials_collected[name]),
                    )

        if self._total_tph_var is not None:
            total_rate = self._compute_total_tph()
            total_amount = sum(self._cargo_additions.values())
            if total_rate is None:
                self._total_tph_var.set("Total Tons/hr: -")
            else:
                duration = 0.0
                if self._mining_start:
                    start_time = self._ensure_aware(self._mining_start)
                    end_raw = self._mining_end or datetime.now(timezone.utc)
                    end_time = self._ensure_aware(end_raw)
                    duration = max(0.0, (end_time - start_time).total_seconds())
                duration_str = self._format_duration(duration)
                self._total_tph_var.set(
                    f"Total Tons/hr: {self._format_rate(total_rate)} ({total_amount}t over {duration_str})"
                )

    def _has_data(self) -> bool:
        return bool(
            self._cargo_additions
            or self._materials_collected
            or self._prospected_count
            or self._prospector_launched_count
            or self._prospect_content_counts
        )

    # Removed: Show/Hide Data button logic

    def _schedule_rate_update(self) -> None:
        self._cancel_rate_update()
        if not self._is_mining:
            return
        if not self._ui_frame or not self._ui_frame.winfo_exists():
            return
        interval = self._clamp_rate_interval(self._rate_interval_seconds)
        jitter = random.uniform(-0.2, 0.2) * interval
        delay_ms = max(1000, int((interval + jitter) * 1000))
        self._rate_update_job = self._ui_frame.after(delay_ms, self._rate_update_tick)

    def _cancel_rate_update(self) -> None:
        if self._rate_update_job and self._ui_frame and self._ui_frame.winfo_exists():
            try:
                self._ui_frame.after_cancel(self._rate_update_job)
            except Exception:
                pass
        self._rate_update_job = None

    def _rate_update_tick(self) -> None:
        self._rate_update_job = None
        if self._ui_frame and self._ui_frame.winfo_exists():
            self._refresh_status_ui()
        if self._is_mining:
            self._schedule_rate_update()

    def _set_rate_interval(self, value: int) -> None:
        interval = self._clamp_rate_interval(value)
        if interval == self._rate_interval_seconds:
            return
        self._rate_interval_seconds = interval
        if self._prefs_rate_var is not None:
            current = self._prefs_rate_var.get()
            if current != interval:
                self._updating_rate_var = True
                self._prefs_rate_var.set(interval)
                self._updating_rate_var = False
        self._schedule_rate_update()

    def _on_rate_var_change(self, *_: object) -> None:
        if self._prefs_rate_var is None or self._updating_rate_var:
            return
        try:
            value = int(self._prefs_rate_var.get())
        except (TypeError, ValueError, tk.TclError):
            return
        self._set_rate_interval(value)

    def _set_inara_search_mode(self, value: int) -> None:
        mode = 3 if value == 3 else 1
        if mode == self._inara_search_mode:
            return
        self._inara_search_mode = mode
        if self._prefs_inara_mode_var is not None:
            current = self._prefs_inara_mode_var.get()
            if current != mode:
                self._updating_inara_mode_var = True
                self._prefs_inara_mode_var.set(mode)
                self._updating_inara_mode_var = False

    def _on_inara_mode_change(self, *_: object) -> None:
        if self._prefs_inara_mode_var is None or self._updating_inara_mode_var:
            return
        try:
            value = int(self._prefs_inara_mode_var.get())
        except (TypeError, ValueError, tk.TclError):
            return
        self._set_inara_search_mode(value)

    def _set_inara_include_carriers(self, include: bool) -> None:
        include = bool(include)
        if include == self._inara_include_carriers:
            return
        self._inara_include_carriers = include
        if self._prefs_inara_carriers_var is not None:
            current = bool(self._prefs_inara_carriers_var.get())
            if current != include:
                self._updating_inara_carriers_var = True
                self._prefs_inara_carriers_var.set(include)
                self._updating_inara_carriers_var = False

    def _on_inara_carriers_change(self, *_: object) -> None:
        if self._prefs_inara_carriers_var is None or self._updating_inara_carriers_var:
            return
        try:
            value = bool(self._prefs_inara_carriers_var.get())
        except (tk.TclError, ValueError):
            return
        self._set_inara_include_carriers(value)

    def _set_inara_include_surface(self, include: bool) -> None:
        include = bool(include)
        if include == self._inara_include_surface:
            return
        self._inara_include_surface = include
        if self._prefs_inara_surface_var is not None:
            current = bool(self._prefs_inara_surface_var.get())
            if current != include:
                self._updating_inara_surface_var = True
                self._prefs_inara_surface_var.set(include)
                self._updating_inara_surface_var = False

    def _on_inara_surface_change(self, *_: object) -> None:
        if self._prefs_inara_surface_var is None or self._updating_inara_surface_var:
            return
        try:
            value = bool(self._prefs_inara_surface_var.get())
        except (tk.TclError, ValueError):
            return
        self._set_inara_include_surface(value)

    def prefs_changed(self, cmdr: Optional[str], is_beta: bool) -> None:
        self._sync_logger_level()
        if config is None:
            return
        try:
            config.set("edmc_mining_histogram_bin", self._histogram_bin_size)
        except Exception:  # pragma: no cover - configuration failures should not crash plugin
            _log.exception("Failed to persist histogram bin size preference")
        try:
            config.set("edmc_mining_rate_interval", self._rate_interval_seconds)
        except Exception:
            _log.exception("Failed to persist rate update interval")
        try:
            config.set("edmc_mining_inara_search_mode", self._inara_search_mode)
        except Exception:
            _log.exception("Failed to persist Inara search mode preference")
        try:
            config.set("edmc_mining_inara_include_carriers", int(self._inara_include_carriers))
        except Exception:
            _log.exception("Failed to persist Inara carrier preference")
        try:
            config.set("edmc_mining_inara_include_surface", int(self._inara_include_surface))
        except Exception:
            _log.exception("Failed to persist Inara surface preference")

    def _sync_logger_level(self) -> None:
        try:
            _log.setLevel(_resolve_edmc_log_level())
        except Exception:
            # Ensure logging issues never break the plugin lifecycle
            pass

    def _ensure_version_check(self) -> None:
        if self._version_check_started:
            return

        self._version_check_started = True
        thread = threading.Thread(target=self._check_for_updates, name="EDMCMiningVersion", daemon=True)
        thread.start()

    def _fetch_latest_tag(self) -> Optional[str]:
        try:
            req = request.Request(
                GITHUB_TAGS_API,
                headers={"User-Agent": f"{PLUGIN_NAME}/{PLUGIN_VERSION}"},
            )
            with request.urlopen(req, timeout=5) as response:
                payload = json.load(response)
        except error.URLError as exc:
            _log.debug("Tag lookup failed: %s", exc)
            return None
        except Exception:
            _log.exception("Unexpected error during tag lookup")
            return None

        if not isinstance(payload, list) or not payload:
            return None
        tag_payload = payload[0]
        tag = tag_payload.get("name") or tag_payload.get("ref")
        if isinstance(tag, str) and tag.startswith("refs/tags/"):
            tag = tag.split("/", 2)[-1]
        return tag

    def _check_for_updates(self) -> None:
        try:
            req = request.Request(
                GITHUB_RELEASES_API,
                headers={"User-Agent": f"{PLUGIN_NAME}/{PLUGIN_VERSION}"},
            )
            with request.urlopen(req, timeout=5) as response:
                payload = json.load(response)
        except error.HTTPError as exc:
            if exc.code == 404:
                _log.debug("GitHub releases endpoint returned 404; falling back to tags")
                latest = self._fetch_latest_tag()
                if latest:
                    self._latest_version = latest
                    if self._latest_version != PLUGIN_VERSION:
                        _log.info(
                            "A newer version of %s is available: %s (current %s)",
                            PLUGIN_NAME,
                            self._latest_version,
                            PLUGIN_VERSION,
                        )
                    else:
                        _log.debug("%s is up to date (version %s)", PLUGIN_NAME, PLUGIN_VERSION)
                else:
                    _log.debug("Version check fallback to tags did not return any versions")
                return
            _log.debug("Version check failed with HTTP status %s: %s", exc.code, exc)
            return
        except error.URLError as exc:
            _log.debug("Version check failed: %s", exc)
            return
        except Exception:  # noqa: BLE001 - log unexpected issues verbosely
            _log.exception("Unexpected error during version check")
            return

        latest = payload.get("tag_name") or payload.get("name")
        if not latest:
            _log.debug("Version check succeeded but no tag information was found")
            return

        self._latest_version = latest
        if self._latest_version != PLUGIN_VERSION:
            _log.info(
                "A newer version of %s is available: %s (current %s)",
                PLUGIN_NAME,
                self._latest_version,
                PLUGIN_VERSION,
            )
        else:
            _log.debug("%s is up to date (version %s)", PLUGIN_NAME, PLUGIN_VERSION)
