"""Tkinter UI for the EDMC Mining Analytics plugin."""

from __future__ import annotations

import logging
import random
from collections import Counter
from datetime import datetime, timezone
from typing import Callable, Dict, Optional, Sequence

try:
    import tkinter as tk
    from tkinter import ttk
    import tkinter.font as tkfont
except ImportError as exc:  # pragma: no cover - EDMC always provides tkinter
    raise RuntimeError("Tkinter must be available for EDMC plugins") from exc

from tooltip import TreeTooltip
from state import MiningState
from inara import InaraClient
from preferences import clamp_bin_size, clamp_rate_interval


_log = logging.getLogger(__name__)


class MiningUI:
    """Encapsulates widget construction and refresh logic."""

    def __init__(
        self,
        state: MiningState,
        inara: InaraClient,
        on_reset: Callable[[], None],
    ) -> None:
        self._state = state
        self._inara = inara
        self._on_reset = on_reset

        self._frame: Optional[tk.Widget] = None
        self._status_var: Optional[tk.StringVar] = None
        self._summary_var: Optional[tk.StringVar] = None
        self._cargo_tree: Optional[ttk.Treeview] = None
        self._materials_tree: Optional[ttk.Treeview] = None
        self._materials_frame: Optional[ttk.Frame] = None
        self._total_tph_var: Optional[tk.StringVar] = None
        self._range_link_labels: Dict[str, tk.Label] = {}
        self._commodity_link_labels: Dict[str, tk.Label] = {}
        self._range_link_font: Optional[tkfont.Font] = None
        self._commodity_link_font: Optional[tkfont.Font] = None
        self._cargo_tooltip: Optional[TreeTooltip] = None
        self._cargo_item_to_commodity: Dict[str, str] = {}
        self._content_widgets: Sequence[tk.Widget] = ()

        self._prefs_bin_var: Optional[tk.IntVar] = None
        self._prefs_rate_var: Optional[tk.IntVar] = None
        self._prefs_inara_mode_var: Optional[tk.IntVar] = None
        self._prefs_inara_carriers_var: Optional[tk.BooleanVar] = None
        self._prefs_inara_surface_var: Optional[tk.BooleanVar] = None

        self._updating_bin_var = False
        self._updating_rate_var = False
        self._updating_inara_mode_var = False
        self._updating_inara_carriers_var = False
        self._updating_inara_surface_var = False

        self._rate_update_job: Optional[str] = None
        self._content_collapsed = False
        self._hist_windows: Dict[str, tk.Toplevel] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def build(self, parent: tk.Widget) -> ttk.Frame:
        frame = ttk.Frame(parent)
        self._frame = frame

        self._status_var = tk.StringVar(master=frame, value="Not mining")
        ttk.Label(frame, textvariable=self._status_var, justify="left", anchor="w").grid(
            row=0, column=0, columnspan=3, sticky="w", padx=4, pady=(4, 2)
        )

        self._summary_var = tk.StringVar(master=frame, value="")
        ttk.Label(frame, textvariable=self._summary_var, justify="left", anchor="w").grid(
            row=1, column=0, columnspan=3, sticky="w", padx=4, pady=(0, 6)
        )

        ttk.Label(frame, text="Mined Commodities", font=(None, 9, "bold"), anchor="w").grid(
            row=2, column=0, sticky="w", padx=4
        )

        table_frame = ttk.Frame(frame)
        table_frame.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=4, pady=(2, 6))
        header_font = tkfont.Font(family="TkDefaultFont", size=9, weight="normal")
        self._cargo_tree = ttk.Treeview(
            table_frame,
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
        self._cargo_tree.column("commodity", anchor="w", width=160, stretch=True)
        self._cargo_tree.column("present", anchor="center", width=60, stretch=False)
        self._cargo_tree.column("percent", anchor="center", width=60, stretch=False)
        self._cargo_tree.column("total", anchor="center", width=80, stretch=False)
        self._cargo_tree.column("range", anchor="center", width=120, stretch=False)
        self._cargo_tree.column("tph", anchor="center", width=80, stretch=False)
        self._cargo_tree.pack(fill="both", expand=True)

        ttk.Style().configure("Treeview.Heading", font=header_font)

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
                "Min/Max percentages of this commodity on an asteroid when found.",
            )
            self._cargo_tooltip.set_heading_tooltip(
                "tph",
                "Projected tons collected per hour of mining.",
            )

        self._total_tph_var = tk.StringVar(master=frame, value="Total Tons/hr: -")
        ttk.Label(frame, textvariable=self._total_tph_var, anchor="w").grid(
            row=4, column=0, sticky="w", padx=4, pady=(0, 6)
        )

        reset_btn = ttk.Button(frame, text="Reset", command=self._on_reset)
        reset_btn.grid(row=4, column=2, sticky="e", padx=4, pady=(0, 6))

        ttk.Label(frame, text="Materials Collected", font=(None, 9, "bold"), anchor="w").grid(
            row=5, column=0, sticky="w", padx=4
        )

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

        self._cargo_tree.bind("<Configure>", lambda _e: self._render_range_links(), add="+")
        self._cargo_tree.bind("<ButtonRelease-3>", lambda _e: self._render_range_links(), add="+")
        self._cargo_tree.bind("<KeyRelease>", lambda _e: self._render_range_links(), add="+")
        self._cargo_tree.bind("<MouseWheel>", lambda _e: self._render_range_links(), add="+")
        self._cargo_tree.bind("<ButtonRelease-4>", lambda _e: self._render_range_links(), add="+")
        self._cargo_tree.bind("<ButtonRelease-5>", lambda _e: self._render_range_links(), add="+")
        self._cargo_tree.bind("<Button-1>", self._on_cargo_click, add="+")
        self._cargo_tree.bind("<Motion>", self._on_cargo_motion, add="+")

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=0)
        frame.columnconfigure(2, weight=0)
        frame.rowconfigure(3, weight=1)
        frame.rowconfigure(6, weight=1)

        self._content_widgets = (
            table_frame,
            reset_btn,
            self._materials_frame,
        )

        return frame

    def refresh(self) -> None:
        self._refresh_status_line()
        self._populate_tables()
        self._render_range_links()

    def schedule_rate_update(self) -> None:
        frame = self._frame
        if frame is None or not frame.winfo_exists():
            return

        if not self._state.is_mining:
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

    def build_preferences(self, parent: tk.Widget) -> tk.Widget:
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

        self._prefs_bin_var = tk.IntVar(master=frame, value=self._state.histogram_bin_size)
        self._prefs_bin_var.trace_add("write", self._on_histogram_bin_change)
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

        self._prefs_rate_var = tk.IntVar(master=frame, value=self._state.rate_interval_seconds)
        self._prefs_rate_var.trace_add("write", self._on_rate_interval_change)
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

        self._prefs_inara_mode_var = tk.IntVar(master=inara_frame, value=self._state.inara_settings.search_mode)
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

        self._prefs_inara_carriers_var = tk.BooleanVar(
            master=inara_frame, value=self._state.inara_settings.include_carriers
        )
        self._prefs_inara_carriers_var.trace_add("write", self._on_inara_carriers_change)
        ttk.Checkbutton(
            inara_frame,
            text="Include fleet carriers in results",
            variable=self._prefs_inara_carriers_var,
        ).grid(row=2, column=0, sticky="w", pady=(0, 4))

        self._prefs_inara_surface_var = tk.BooleanVar(
            master=inara_frame, value=self._state.inara_settings.include_surface
        )
        self._prefs_inara_surface_var.trace_add("write", self._on_inara_surface_change)
        ttk.Checkbutton(
            inara_frame,
            text="Include surface stations in results",
            variable=self._prefs_inara_surface_var,
        ).grid(row=3, column=0, sticky="w", pady=(0, 4))

        return frame

    def get_root(self) -> Optional[tk.Widget]:
        return self._frame

    def clear_transient_widgets(self) -> None:
        self._clear_range_link_labels()
        self._clear_commodity_link_labels()
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
                status_text = f"You're mining {self._state.mining_location}"
            else:
                status_text = "You're mining!"
        else:
            status_text = "Not mining"

        summary_lines = self._status_summary_lines()

        status_var.set(status_text)
        summary_var.set("\n".join(summary_lines))

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

        return lines

    def _populate_tables(self) -> None:
        cargo_tree = self._cargo_tree
        if cargo_tree and getattr(cargo_tree, "winfo_exists", lambda: False)():
            cargo_tree.delete(*cargo_tree.get_children())
            if self._cargo_tooltip:
                self._cargo_tooltip.clear()
            self._cargo_item_to_commodity.clear()
            self.clear_transient_widgets()

            rows = sorted(
                name
                for name in set(self._state.cargo_totals) | set(self._state.cargo_additions)
                if self._state.cargo_additions.get(name, 0) > 0
            )
            if not rows:
                item = cargo_tree.insert(
                    "",
                    "end",
                    values=("No mined commodities yet", "", "", "", "", ""),
                )
                if self._cargo_tooltip:
                    self._cargo_tooltip.set_cell_text(item, "#6", None)
            else:
                present_counts = {k: len(v) for k, v in self._state.prospected_samples.items()}
                total_asteroids = self._state.prospected_count if self._state.prospected_count > 0 else 1
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
                            self._state.cargo_totals.get(name, 0),
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
            if not self._state.materials_collected:
                materials_tree.insert("", "end", values=("No materials collected yet", ""))
            else:
                for name in sorted(self._state.materials_collected):
                    materials_tree.insert(
                        "",
                        "end",
                        values=(self._format_cargo_name(name), self._state.materials_collected[name]),
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

    def _on_rate_update_tick(self) -> None:
        self._rate_update_job = None
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
        for item, commodity in self._cargo_item_to_commodity.items():
            range_label = self._format_range_label(commodity)
            if not range_label:
                continue
            bbox = tree.bbox(item, "#5")
            if not bbox:
                pending = True
                continue
            x, y, width, height = bbox
            label = ttk.Label(
                tree,
                text=range_label,
                style="EDMC.RangeLink.TLabel",
                cursor="hand2",
                anchor="center",
            )
            try:
                label.configure(font=self._range_link_font)
            except Exception:
                pass
            link_fg = self._theme_fg_for(tree) or "#1a4bf6"
            style = ttk.Style(tree)
            try:
                style.configure("EDMC.RangeLink.TLabel", foreground=link_fg)
                if background:
                    style.configure("EDMC.RangeLink.TLabel", background=background)
            except Exception:
                pass
            label.place(x=x + 2, y=y + 1, width=width - 4, height=height - 2)
            label.bind("<Button-1>", lambda _evt, commodity=commodity: self.open_histogram_window(commodity))
            self._range_link_labels[item] = label

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
        try:
            style.configure("EDMC.CommodityLink.TLabel", foreground="#1a4bf6")
            if background:
                style.configure("EDMC.CommodityLink.TLabel", background=background)
        except Exception:
            pass

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
            pad_x, pad_y = 4, 1
            try:
                label.place(
                    x=x + pad_x,
                    y=y + pad_y,
                    width=max(0, width - pad_x * 2),
                    height=max(0, height - pad_y * 2),
                )
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
        cleaned = [value for value in samples if isinstance(value, (int, float))]
        if not cleaned:
            return ""
        min_val = min(cleaned)
        max_val = max(cleaned)
        if abs(max_val - min_val) < 1e-6:
            return f"{min_val:.1f}%"
        return f"{min_val:.1f}%-{max_val:.1f}%"

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
        start_time = MiningUI._ensure_aware(start)
        end_time = MiningUI._ensure_aware(end)
        return max(0.0, (end_time - start_time).total_seconds())

    @staticmethod
    def _format_bin_label(bin_index: int, size: int) -> str:
        start = bin_index * size
        end = min(start + size, 100)
        return f"{int(start)}-{int(end)}%"

    def _theme_bg_for(self, widget: tk.Widget) -> Optional[str]:
        style = ttk.Style(widget)
        for style_name, option in (
            ("Treeview", "fieldbackground"),
            ("TFrame", "background"),
            ("TLabel", "background"),
        ):
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
        style = ttk.Style(widget)
        for style_name, option in (
            ("Treeview", "foreground"),
            ("TLabel", "foreground"),
            ("TButton", "foreground"),
        ):
            try:
                val = style.lookup(style_name, option)
            except Exception:
                val = None
            if val:
                return val
        return None

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
        counter = self._state.prospected_histogram.get(commodity)
        if not counter:
            return

        window = self._hist_windows.get(commodity)
        if window and window.winfo_exists():
            window.lift()
            return

        parent = self._frame
        if parent is None:
            return

        top = tk.Toplevel(parent)
        top.title(f"{self._format_cargo_name(commodity)} histogram")
        canvas = tk.Canvas(top, width=360, height=200)
        canvas.pack(fill="both", expand=True)
        top.bind(
            "<Configure>",
            lambda event, c=commodity, cv=canvas: self._draw_histogram(cv, c),
        )
        self._draw_histogram(canvas, commodity, counter)
        top.protocol("WM_DELETE_WINDOW", lambda c=commodity: self._close_histogram_window(c))
        self._hist_windows[commodity] = top

    def close_histogram_windows(self) -> None:
        for commodity in list(self._hist_windows):
            self._close_histogram_window(commodity)
        self._hist_windows.clear()

    def _close_histogram_window(self, commodity: str) -> None:
        window = self._hist_windows.pop(commodity, None)
        if not window:
            return
        try:
            window.destroy()
        except Exception:
            pass

    def _draw_histogram(self, canvas: tk.Canvas, commodity: str, counter: Optional[Counter[int]] = None) -> None:
        canvas.delete("all")
        if counter is None:
            counter = self._state.prospected_histogram.get(commodity, Counter())
        if not counter:
            canvas.create_text(180, 100, text="No data available")
            return

        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        padding = 24
        bins = sorted(counter.keys())
        max_count = max(counter.values()) or 1
        bin_width = (width - padding * 2) / max(1, len(bins))
        size = max(1, self._state.histogram_bin_size)

        for idx, bin_index in enumerate(bins):
            count = counter[bin_index]
            x0 = padding + idx * bin_width
            x1 = x0 + bin_width * 0.8
            bar_height = (height - padding * 2) * (count / max_count)
            y0 = height - padding - bar_height
            y1 = height - padding
            canvas.create_rectangle(x0, y0, x1, y1, fill="#4a90e2")
            label = self._format_bin_label(bin_index, size)
            canvas.create_text((x0 + x1) / 2, height - padding / 2, text=label, anchor="n")
            canvas.create_text((x0 + x1) / 2, y0 - 4, text=str(count), anchor="s")

    def _recompute_histograms(self) -> None:
        from state import recompute_histograms  # local import to avoid circular deps

        recompute_histograms(self._state)
