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
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Tuple
from urllib import error, request

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

try:
    from config import config  # type: ignore[import]
except ImportError:  # pragma: no cover - only available inside EDMC
    config = None  # type: ignore[assignment]

from .util.tooltip import TreeTooltip

PLUGIN_NAME = "EDMC Mining Analytics"
PLUGIN_VERSION = "0.1.0"
GITHUB_RELEASES_API = (
    "https://api.github.com/repos/SweetJonnySauce/EDMC-Mining-Analytics/releases/latest"
)

_log = logging.getLogger("EDMC." + PLUGIN_NAME.replace(" ", ""))

class MiningAnalyticsPlugin:
    """Encapsulates plugin state and behaviour for EDMC."""

    def __init__(self) -> None:
        self.plugin_dir: Optional[Path] = None
        self._is_mining = False
        self._status_var: Optional[tk.StringVar] = None
        self._ui_frame: Optional[tk.Widget] = None
        self._table_frame: Optional[tk.Widget] = None
        self._cargo_tree: Optional[ttk.Treeview] = None
        self._materials_frame: Optional[ttk.Frame] = None
        self._materials_tree: Optional[ttk.Treeview] = None
        self._cargo_label: Optional[ttk.Label] = None
        self._materials_label: Optional[ttk.Label] = None
        self._mining_start: Optional[datetime] = None
        self._prospected_count = 0
        self._already_mined_count = 0
        self._latest_version: Optional[str] = None
        self._version_check_started = False
        self._cargo_additions: dict[str, int] = {}
        self._cargo_totals: dict[str, int] = {}
        self._limpets_remaining: Optional[int] = None
        self._collection_drones_launched = 0
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
        self._clear_button: Optional[ttk.Button] = None
        self._hist_windows: dict[str, tk.Toplevel] = {}
        self._cargo_item_to_commodity: dict[str, str] = {}
        self._range_link_labels: dict[str, tk.Label] = {}
        self._range_link_font: Optional[tkfont.Font] = None
        self._expand_button: Optional[ttk.Button] = None
        self._user_expanded = False
        self._content_widgets: list[tk.Widget] = []
        self._content_collapsed = False

    # ------------------------------------------------------------------
    # EDMC lifecycle hooks
    # ------------------------------------------------------------------
    def plugin_start(self, plugin_dir: str) -> str:
        self.plugin_dir = Path(plugin_dir)
        _log.info("Starting %s v%s", PLUGIN_NAME, PLUGIN_VERSION)
        self._load_configuration()
        self._ensure_version_check()
        return PLUGIN_NAME

    def plugin_app(self, parent: tk.Widget) -> ttk.Frame:
        frame = ttk.Frame(parent)

        self._ui_frame = frame
        self._status_var = tk.StringVar(master=frame, value=self._idle_status_text)
        ttk.Label(frame, textvariable=self._status_var, justify="left", anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=4, pady=2
        )
        self._expand_button = ttk.Button(frame, text="Show data", command=self._on_toggle_expand)
        self._expand_button.grid(row=0, column=2, sticky="e", padx=4, pady=2)

        self._cargo_label = ttk.Label(frame, text="Cargo Changes", font=(None, 9, "bold"), anchor="w")
        self._cargo_label.grid(row=1, column=0, sticky="w", padx=4)

        self._table_frame = ttk.Frame(frame)
        self._table_frame.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=4, pady=(2, 6))
        self._cargo_tree = ttk.Treeview(
            self._table_frame,
            columns=("commodity", "added", "total", "range", "tph"),
            show="headings",
            height=5,
            selectmode="none",
        )
        self._cargo_tree.heading("commodity", text="Commodity")
        self._cargo_tree.heading("added", text="Added")
        self._cargo_tree.heading("total", text="Total")
        self._cargo_tree.heading("range", text="Range")
        self._cargo_tree.heading("tph", text="Tons/hr")
        self._cargo_tree.column("commodity", anchor="w", stretch=True, width=160)
        self._cargo_tree.column("added", anchor="center", stretch=False, width=70)
        self._cargo_tree.column("total", anchor="center", stretch=False, width=70)
        self._cargo_tree.column("range", anchor="center", stretch=False, width=120)
        self._cargo_tree.column("tph", anchor="center", stretch=False, width=80)
        self._cargo_tree.pack(fill="both", expand=True)
        self._cargo_tooltip = TreeTooltip(self._cargo_tree)
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
        self._total_tph_label.grid(row=3, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 6))
        self._clear_button = ttk.Button(frame, text="Clear Mining Data", command=self._clear_mining_data)
        self._clear_button.grid(row=3, column=2, sticky="e", padx=4, pady=(0, 6))

        self._materials_label = ttk.Label(frame, text="Materials Collected", font=(None, 9, "bold"), anchor="w")
        self._materials_label.grid(row=4, column=0, sticky="w", padx=4)

        self._materials_frame = ttk.Frame(frame)
        self._materials_frame.grid(row=5, column=0, columnspan=3, sticky="nsew", padx=4, pady=(2, 6))
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
        frame.rowconfigure(5, weight=1)

        self._content_widgets = [
            self._cargo_label,
            self._total_tph_label,
            self._table_frame,
            self._clear_button,
            self._materials_label,
            self._materials_frame,
        ]

        self._apply_ui_state(self._status_var.get())
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
        self._refresh_status_ui()

    # ------------------------------------------------------------------
    # Journal handling
    # ------------------------------------------------------------------
    def handle_journal_entry(self, entry: dict, shared_state: Optional[dict] = None) -> None:
        if not entry:
            return

        event = entry.get("event")
        if event == "LaunchDrone":
            drone_type = entry.get("Type")
            if isinstance(drone_type, str):
                dtype = drone_type.lower()
                if dtype == "prospector":
                    if not self._is_mining:
                        self._update_mining_state(True, "Prospector drone launched", entry.get("timestamp"))
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
                self._update_mining_state(False, "Entered Supercruise", entry.get("timestamp"))
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
    def _update_mining_state(self, active: bool, reason: str, timestamp: Optional[str]) -> None:
        if self._is_mining == active:
            return

        self._is_mining = active
        if active:
            self._mining_start = self._parse_timestamp(timestamp) or datetime.now(timezone.utc)
            self._prospected_count = 0
            self._already_mined_count = 0
            self._cargo_additions = {}
            self._cargo_totals = {}
            self._limpets_remaining = None
            self._collection_drones_launched = 0
            self._abandoned_limpets = 0
            self._prospected_seen.clear()
            self._prospected_samples.clear()
            self._prospected_histogram.clear()
            self._duplicate_prospected = 0
            self._harvested_commodities.clear()
            self._prospector_launched_count = 0
            self._commodity_start_times.clear()
            self._prospect_content_counts.clear()
            self._materials_collected.clear()
            self._last_cargo_counts.clear()
            self._user_expanded = True
        else:
            self._user_expanded = False

        state_text = "active" if active else "inactive"
        _log.info("Mining state changed to %s (%s)", state_text, reason)
        self._refresh_status_ui()

    def _refresh_status_ui(self) -> None:
        if not self._status_var:
            return

        text = self._active_status_text if self._is_mining else self._idle_status_text
        if self._ui_frame and getattr(self._ui_frame, "winfo_exists", lambda: False)():
            self._ui_frame.after(0, self._apply_ui_state, text)
        else:
            self._apply_ui_state(text)

    @property
    def _active_status_text(self) -> str:
        parts = ["You're mining!"]
        if self._mining_start:
            start_dt = self._ensure_aware(self._mining_start).astimezone(timezone.utc)
            start_str = start_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            parts.append(f"Started: {start_str}")
        parts.extend(self._status_summary_lines())
        return "\n".join(parts)

    @property
    def _idle_status_text(self) -> str:
        parts = ["Not mining"]
        parts.extend(self._status_summary_lines())
        return "\n".join(parts)

    def _status_summary_lines(self) -> list[str]:
        lines = []
        # First line: Prospected, Already mined, Duplicates
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
        # Third line: Limpets, drones, abandoned
        limpets = f"Limpets: Remaining: {self._limpets_remaining}" if self._limpets_remaining is not None else None
        drones = f"Launched: {self._collection_drones_launched}"
        abandoned = f"Abandoned: {self._abandoned_limpets}" if self._abandoned_limpets > 0 else None
        third = " | ".join(x for x in [limpets, drones, abandoned] if x)
        if third:
            lines.append(third)
        # Optionally: Materials summary
        if self._materials_collected:
            lines.append("Materials summary below")
        # Optionally: No cargo data
        if not (self._cargo_totals or self._cargo_additions):
            lines.append("No cargo data yet")
        return lines

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

    def _clear_mining_data(self) -> None:
        if self._is_mining:
            return
        self._reset_mining_metrics()
        self._refresh_status_ui()

    def _clear_range_link_labels(self) -> None:
        for label in self._range_link_labels.values():
            if label.winfo_exists():
                label.destroy()
        self._range_link_labels.clear()

    def _render_range_links(self) -> None:
        tree = self._cargo_tree
        if not tree or not getattr(tree, "winfo_exists", lambda: False)() or self._content_collapsed:
            return

        self._clear_range_link_labels()

        style = ttk.Style(tree)
        background = style.lookup("Treeview", "background") or tree.cget("background") or "SystemWindow"
        if not background or background in {"", "SystemWindow"}:
            background = style.lookup("Treeview", "fieldbackground") or tree.cget("background") or "SystemWindow"
        base_font = tree.cget("font")
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
            bbox = tree.bbox(item, "#4")
            if not bbox:
                pending = True
                continue
            x, y, width, height = bbox
            label = tk.Label(
                tree,
                text=range_label,
                fg="#1a4bf6",
                bg=background,
                cursor="hand2",
                font=self._range_link_font,
                anchor="center",
            )
            label.place(x=x + 2, y=y + 1, width=width - 4, height=height - 2)
            label.bind("<Button-1>", lambda _event, commodity=commodity: self._open_histogram_window(commodity))
            self._range_link_labels[item] = label

        if pending:
            tree.after(16, self._render_range_links)

    def _reset_mining_metrics(self) -> None:
        self._close_histogram_windows()
        self._clear_range_link_labels()
        self._cargo_item_to_commodity.clear()
        self._mining_start = None
        self._prospected_count = 0
        self._already_mined_count = 0
        self._cargo_additions = {}
        self._cargo_totals = {}
        self._limpets_remaining = None
        self._collection_drones_launched = 0
        self._abandoned_limpets = 0
        self._last_event_was_drone_launch = False
        self._prospected_seen.clear()
        self._prospected_samples.clear()
        self._prospected_histogram.clear()
        self._duplicate_prospected = 0
        self._harvested_commodities.clear()
        self._prospector_launched_count = 0
        self._commodity_start_times.clear()
        self._prospect_content_counts.clear()
        self._materials_collected.clear()
        self._last_cargo_counts.clear()
        self._user_expanded = False

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

        if (
            limpets is not None
            and previous_limpets is not None
            and limpets < previous_limpets
            and not self._last_event_was_drone_launch
        ):
            abandoned = previous_limpets - limpets
            if abandoned > 0:
                self._abandoned_limpets += abandoned
                _log.info("Detected %s limpets abandoned", abandoned)

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
        now = datetime.now(timezone.utc)
        elapsed_hours = (now - start).total_seconds() / 3600.0
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

    def _make_tph_tooltip(self, commodity: str) -> Optional[str]:
        rate = self._compute_tph(commodity)
        start = self._commodity_start_times.get(commodity)
        amount = self._cargo_additions.get(commodity, 0)
        if rate is None or start is None or amount <= 0:
            return None

        duration = (datetime.now(timezone.utc) - self._ensure_aware(start)).total_seconds()
        return f"{amount}t over {self._format_duration(duration)}"

    def _on_cargo_click(self, event: tk.Event) -> None:  # type: ignore[override]
        if not self._cargo_tree:
            return
        column = self._cargo_tree.identify_column(event.x)
        if column != "#4":
            return
        item = self._cargo_tree.identify_row(event.y)
        commodity = self._cargo_item_to_commodity.get(item)
        if not commodity:
            return
        if not self._format_range_label(commodity):
            return
        self._open_histogram_window(commodity)

    def _on_cargo_motion(self, event: tk.Event) -> None:  # type: ignore[override]
        if not self._cargo_tree:
            return
        column = self._cargo_tree.identify_column(event.x)
        item = self._cargo_tree.identify_row(event.y)
        commodity = self._cargo_item_to_commodity.get(item)
        if column == "#4" and commodity and self._format_range_label(commodity):
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

        elapsed_hours = (
            datetime.now(timezone.utc) - self._ensure_aware(self._mining_start)
        ).total_seconds() / 3600.0
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

        canvas = tk.Canvas(window, background="white", width=420, height=300)
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

        if not items:
            canvas.create_text(
                width // 2,
                height // 2,
                text="No prospecting data",
                fill="#555555",
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
            canvas.create_rectangle(x0, y0, x1, y1, fill="#4c8eda", outline="#224f84")
            canvas.create_text((x0 + x1) / 2, y0 - 10, text=str(count), fill="#333333", font=(None, 10))
            canvas.create_text((x0 + x1) / 2, y1 + 12, text=self._format_bin_label(bin_index), fill="#333333", font=(None, 9))

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

    def _apply_ui_state(self, status_text: str) -> None:
        if self._status_var:
            self._status_var.set(status_text)

        if self._clear_button and getattr(self._clear_button, "winfo_exists", lambda: False)():
            self._clear_button.configure(state="disabled" if self._is_mining else "normal")

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
                    "", "end", values=("No cargo changes yet", "", "", "", "")
                )
                if self._cargo_tooltip:
                    self._cargo_tooltip.set_cell_text(item, "#5", None)
            else:
                for name in rows:
                    range_label = self._format_range_label(name)
                    item = cargo_tree.insert(
                        "",
                        "end",
                        values=(
                            self._format_cargo_name(name),
                            self._cargo_additions.get(name, 0),
                            self._cargo_totals.get(name, 0),
                            range_label,
                            self._format_tph(name),
                        ),
                    )
                    self._cargo_item_to_commodity[item] = name
                    if self._cargo_tooltip:
                        self._cargo_tooltip.set_cell_text(
                            item,
                            "#5",
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
                    duration = (datetime.now(timezone.utc) - self._ensure_aware(self._mining_start)).total_seconds()
                duration_str = self._format_duration(duration)
                self._total_tph_var.set(
                    f"Total Tons/hr: {self._format_rate(total_rate)} ({total_amount}t over {duration_str})"
                )

        self._update_collapsed_state()

    def _has_data(self) -> bool:
        return bool(
            self._cargo_additions
            or self._materials_collected
            or self._prospected_count
            or self._prospector_launched_count
            or self._prospect_content_counts
        )

    def _update_collapsed_state(self) -> None:
        if not self._content_widgets:
            return

        has_data = self._has_data()

        if self._is_mining:
            self._user_expanded = True
            desired_visible = True
        else:
            if not has_data:
                self._user_expanded = False
            desired_visible = has_data and self._user_expanded

        if desired_visible and self._content_collapsed:
            for widget in self._content_widgets:
                if widget and widget.winfo_exists():
                    widget.grid()
            self._content_collapsed = False
            self._ui_frame.after(0, self._render_range_links)
        elif not desired_visible and not self._content_collapsed:
            self._clear_range_link_labels()
            for widget in self._content_widgets:
                if widget and widget.winfo_exists():
                    widget.grid_remove()
            self._content_collapsed = True

        if self._expand_button and self._expand_button.winfo_exists():
            if self._is_mining or not has_data:
                self._expand_button.grid_remove()
            else:
                self._expand_button.grid(row=0, column=2, sticky="e", padx=4, pady=2)
                self._expand_button.configure(
                    text="Hide data" if self._user_expanded else "Show data"
                )

        if self._content_collapsed:
            self._clear_range_link_labels()

    def _on_toggle_expand(self) -> None:
        if self._is_mining:
            return
        if not self._has_data():
            return
        self._user_expanded = not self._user_expanded
        self._update_collapsed_state()

    def _schedule_rate_update(self) -> None:
        self._cancel_rate_update()
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

    def prefs_changed(self, cmdr: Optional[str], is_beta: bool) -> None:
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

    def _ensure_version_check(self) -> None:
        if self._version_check_started:
            return

        self._version_check_started = True
        thread = threading.Thread(target=self._check_for_updates, name="EDMCMiningVersion", daemon=True)
        thread.start()

    def _check_for_updates(self) -> None:
        try:
            req = request.Request(
                GITHUB_RELEASES_API,
                headers={"User-Agent": f"{PLUGIN_NAME}/{PLUGIN_VERSION}"},
            )
            with request.urlopen(req, timeout=5) as response:
                payload = json.load(response)
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
