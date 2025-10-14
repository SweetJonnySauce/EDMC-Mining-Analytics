"""Hotspot search window components (controller + view)."""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, replace
from typing import Callable, Dict, List, Optional, Sequence, Tuple

try:
    import tkinter as tk
    from tkinter import ttk
    import tkinter.font as tkfont
except ImportError as exc:  # pragma: no cover - EDMC always provides tkinter
    raise RuntimeError("Tkinter must be available for EDMC plugins") from exc

from logging_utils import get_logger
from state import MiningState
from integrations.spansh_hotspots import (
    DEFAULT_RESULT_SIZE,
    HotspotSearchResult,
    RingHotspot,
    SpanshHotspotClient,
)
from mining_ui.theme_adapter import ThemeAdapter

_log = get_logger("ui")


@dataclass(frozen=True)
class HotspotSearchParams:
    distance_min: float
    distance_max: float
    ring_signals: Tuple[str, ...]
    reserve_levels: Tuple[str, ...]
    ring_types: Tuple[str, ...]
    min_hotspots: int
    reference_text: str
    page: int
    limit: int


@dataclass(frozen=True)
class HotspotSavedFilters:
    distance_min: Optional[float]
    distance_max: Optional[float]
    reserve_levels: Optional[Sequence[str]]
    ring_types: Optional[Sequence[str]]
    ring_signals: Optional[Sequence[str]]
    min_hotspots: Optional[int]


@dataclass(frozen=True)
class SearchStartResult:
    status: str
    started: bool
    token: Optional[int]


class HotspotSearchController:
    """Handle hotspot search logic and state coordination."""

    FALLBACK_RING_SIGNALS = [
        "Platinum",
        "Painite",
        "Void Opal",
        "Tritium",
        "Serendibite",
        "Rhodplumsite",
        "Monazite",
    ]
    FALLBACK_RING_TYPES = ["Metallic", "Metal Rich", "Icy", "Rocky"]
    FALLBACK_RESERVE_LEVELS = ["Pristine", "Major", "Common", "Low", "Depleted"]

    def __init__(self, state: MiningState, client: SpanshHotspotClient) -> None:
        self._state = state
        self._client = client

        self._ring_signal_options = self._sorted_unique(
            client.list_ring_signals(),
            self.FALLBACK_RING_SIGNALS,
        )
        self._ring_type_options = self._sorted_unique(
            client.list_ring_types(),
            self.FALLBACK_RING_TYPES,
        )
        self._reserve_level_options = self._sorted_unique(
            client.list_reserve_levels(),
            self.FALLBACK_RESERVE_LEVELS,
            preserve_order=True,
        )

        self._search_thread: Optional[threading.Thread] = None
        self._pending_search_params: Optional[HotspotSearchParams] = None
        self._search_token: int = 0
        self._search_result_queue: "queue.Queue[tuple[int, tuple[str, object]]]" = queue.Queue()
        self._reference_suggestion_queue: "queue.Queue[tuple[int, List[str]]]" = queue.Queue()
        self._reference_suggestion_token: int = 0


    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def state(self) -> MiningState:
        return self._state

    @property
    def ring_signal_options(self) -> Sequence[str]:
        return self._ring_signal_options

    @property
    def ring_type_options(self) -> Sequence[str]:
        return self._ring_type_options

    @property
    def reserve_level_options(self) -> Sequence[str]:
        return self._reserve_level_options

    def get_saved_filters(self) -> HotspotSavedFilters:
        return HotspotSavedFilters(
            distance_min=self._state.spansh_last_distance_min,
            distance_max=self._state.spansh_last_distance_max,
            reserve_levels=self._state.spansh_last_reserve_levels,
            ring_types=self._state.spansh_last_ring_types,
            ring_signals=self._state.spansh_last_ring_signals,
            min_hotspots=self._state.spansh_last_min_hotspots,
        )

    def get_current_system(self) -> str:
        return self._state.current_system or ""

    def persist_filters_from_ui(
        self,
        distance_min_text: str,
        distance_max_text: str,
        reserves: Sequence[str],
        ring_types: Sequence[str],
        ring_signals: Sequence[str],
        min_hotspots: int,
    ) -> None:
        self._state.spansh_last_distance_min = self._parse_optional_float(distance_min_text, None)
        self._state.spansh_last_distance_max = self._parse_optional_float(distance_max_text, None)
        self._state.spansh_last_reserve_levels = list(reserves)
        self._state.spansh_last_ring_types = list(ring_types)
        self._state.spansh_last_ring_signals = list(ring_signals)
        self._state.spansh_last_min_hotspots = min_hotspots

    def begin_search(self, params: HotspotSearchParams, display_reference: str) -> SearchStartResult:
        self._state.spansh_last_distance_min = params.distance_min
        self._state.spansh_last_distance_max = params.distance_max
        self._state.spansh_last_ring_signals = list(params.ring_signals)
        self._state.spansh_last_reserve_levels = list(params.reserve_levels)
        self._state.spansh_last_ring_types = list(params.ring_types)
        self._state.spansh_last_min_hotspots = max(1, int(params.min_hotspots))

        if self._search_thread and self._search_thread.is_alive():
            self._pending_search_params = params
            status = (
                f"Waiting for previous Spansh search to finish before searching near {display_reference}..."
            )
            return SearchStartResult(status=status, started=False, token=None)

        self._pending_search_params = None
        self._search_token += 1
        token = self._search_token

        thread = threading.Thread(
            target=self._search_worker,
            args=(token, params),
            name="EDMC-SpanshSearch",
            daemon=True,
        )
        self._search_thread = thread
        thread.start()

        status = f"Searching for hotspots near {display_reference}..."
        return SearchStartResult(status=status, started=True, token=token)

    def poll_search_results(self) -> Optional[tuple[int, tuple[str, object]]]:
        try:
            return self._search_result_queue.get_nowait()
        except queue.Empty:
            return None

    def on_search_complete(self) -> Optional[HotspotSearchParams]:
        self._search_thread = None
        pending = self._pending_search_params
        self._pending_search_params = None
        return pending

    def request_reference_suggestions(self, query: str) -> Optional[int]:
        trimmed = query.strip()
        if len(trimmed) < 2:
            return None

        self._reference_suggestion_token += 1
        token = self._reference_suggestion_token

        def worker() -> None:
            try:
                suggestions = self._client.suggest_system_names(trimmed, limit=10)
            except Exception:
                suggestions = []
            try:
                self._reference_suggestion_queue.put((token, suggestions))
            except Exception:
                pass

        threading.Thread(target=worker, name="EDMC-SpanshSuggestions", daemon=True).start()
        return token

    def poll_reference_suggestions(self) -> Optional[tuple[int, List[str]]]:
        try:
            return self._reference_suggestion_queue.get_nowait()
        except queue.Empty:
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _search_worker(self, token: int, params: HotspotSearchParams) -> None:
        reference_text_input = (params.reference_text or "").strip()
        try:
            resolved_reference = self._client.resolve_reference_system(reference_text_input)
            result = self._client.search_hotspots(
                distance_min=params.distance_min,
                distance_max=params.distance_max,
                ring_signals=params.ring_signals,
                reserve_levels=params.reserve_levels,
                ring_types=params.ring_types,
                limit=params.limit,
                page=params.page,
                min_hotspots=max(1, int(params.min_hotspots)),
                reference_system=resolved_reference,
            )
            result = self._filter_results_by_min_hotspots(result, params)
            outcome: tuple[str, object] = ("success", (result, resolved_reference))
        except ValueError as exc:
            outcome = ("value_error", str(exc))
        except RuntimeError as exc:
            outcome = ("runtime_error", str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            _log.exception("Unexpected error during hotspot search: %s", exc)
            outcome = ("exception", str(exc))

        try:
            self._search_result_queue.put_nowait((token, outcome))
        except Exception:  # pragma: no cover - defensive
            pass

    def _filter_results_by_min_hotspots(
        self,
        result: HotspotSearchResult,
        params: HotspotSearchParams,
    ) -> HotspotSearchResult:
        min_required = max(1, int(params.min_hotspots))
        if params.ring_signals:
            return result

        filtered_entries = tuple(
            entry for entry in result.entries if self._total_signal_count(entry) >= min_required
        )

        if len(filtered_entries) == len(result.entries):
            return result

        return HotspotSearchResult(
            total_count=result.total_count,
            reference_system=result.reference_system,
            entries=filtered_entries,
        )

    @staticmethod
    def _total_signal_count(entry: RingHotspot) -> int:
        total = 0
        for signal in entry.signals:
            try:
                count = int(signal.count)
            except (TypeError, ValueError):
                continue
            if count > 0:
                total += count
        return total

    @staticmethod
    def _sorted_unique(
        values: Sequence[str],
        fallback: Sequence[str],
        *,
        preserve_order: bool = False,
    ) -> List[str]:
        if not values:
            return list(fallback)
        seen: set[str] = set()
        result: List[str] = []
        iterable = values if preserve_order else sorted(values)
        for item in iterable:
            cleaned = item.strip()
            lowered = cleaned.lower()
            if not cleaned or lowered in seen:
                continue
            seen.add(lowered)
            result.append(cleaned)
        return result or list(fallback)

    @staticmethod
    def _parse_optional_float(value: str, default: Optional[float]) -> Optional[float]:
        try:
            cleaned = value.strip()
        except AttributeError:
            return default
        if not cleaned:
            return default
        try:
            return float(cleaned)
        except ValueError:
            return default


class HotspotSearchWindow:
    """Toplevel window that performs and displays Spansh hotspot searches."""

    DEFAULT_DISTANCE_MIN = "0"
    DEFAULT_DISTANCE_MAX = "100"
    DEFAULT_SIGNAL = "Platinum"
    DEFAULT_RESERVE = "Pristine"
    DEFAULT_RING_TYPE = "Metallic"
    DEFAULT_MIN_HOTSPOTS = 1
    RESULTS_PER_PAGE = DEFAULT_RESULT_SIZE

    FALLBACK_RING_SIGNALS = [
        "Platinum",
        "Painite",
        "Void Opal",
        "Tritium",
        "Serendibite",
        "Rhodplumsite",
        "Monazite",
    ]
    FALLBACK_RING_TYPES = ["Metallic", "Metal Rich", "Icy", "Rocky"]
    FALLBACK_RESERVE_LEVELS = ["Pristine", "Major", "Common", "Low", "Depleted"]

    def __init__(
        self,
        parent: tk.Widget,
        theme: ThemeAdapter,
        controller: HotspotSearchController,
        on_close: Callable[["HotspotSearchWindow"], None],
    ) -> None:
        self._parent = parent
        self._theme = theme
        self._controller = controller
        self._on_close = on_close
        self._search_job: Optional[str] = None

        self._toplevel = tk.Toplevel(parent)
        self._toplevel.title("Nearby Hotspots")
        self._toplevel.transient(parent.winfo_toplevel())
        self._toplevel.protocol("WM_DELETE_WINDOW", self.close)
        self._toplevel.minsize(960, 420)
        self._theme.register(self._toplevel)

        self._distance_min_var = tk.StringVar(master=self._toplevel, value=self.DEFAULT_DISTANCE_MIN)
        self._distance_max_var = tk.StringVar(master=self._toplevel, value=self.DEFAULT_DISTANCE_MAX)
        self._reserve_var = tk.StringVar(master=self._toplevel, value=self.DEFAULT_RESERVE)
        self._reference_system_var = tk.StringVar(master=self._toplevel, value="")

        self._ring_signal_options = list(self._controller.ring_signal_options)
        self._ring_type_options = list(self._controller.ring_type_options)
        self._reserve_level_options = list(self._controller.reserve_level_options)

        self._signals_listbox: Optional[tk.Listbox] = None
        self._ring_type_listbox: Optional[tk.Listbox] = None
        self._reserve_combobox: Optional[ttk.Combobox] = None
        self._min_hotspots_var: Optional[tk.StringVar] = None
        self._reference_entry: Optional[ttk.Entry] = None
        self._reference_frame: Optional[tk.Frame] = None
        self._results_tree: Optional[ttk.Treeview] = None
        self._hotspot_container: Optional[tk.Frame] = None
        self._hotspot_controls_frame: Optional[tk.Frame] = None
        self._results_frame: Optional[tk.Frame] = None
        self._active_search_token: Optional[int] = None
        self._result_poll_job: Optional[str] = None
        self._reference_suggestions_listbox: Optional[tk.Listbox] = None
        self._reference_suggestions_visible = False
        self._reference_suggestion_job: Optional[str] = None
        self._reference_suggestion_poll_job: Optional[str] = None
        self._reference_suggestion_token: int = 0
        self._reference_last_query: str = ""
        self._reference_suggestions_suppressed = False
        self._status_var = tk.StringVar(master=self._toplevel, value="")
        self._pagination_frame: Optional[tk.Frame] = None
        self._pagination_pack_options: Dict[str, object] = {}
        self._prev_page_button: Optional[ttk.Button] = None
        self._next_page_button: Optional[ttk.Button] = None
        self._page_label_var: Optional[tk.StringVar] = None
        self._active_params: Optional[HotspotSearchParams] = None
        self._last_successful_params: Optional[HotspotSearchParams] = None
        self._last_result_total: int = 0
        self._last_results_count: int = 0
        self._pagination_has_prev: bool = False
        self._pagination_has_next: bool = False
        self._search_started_at: Optional[float] = None
        self._last_search_duration: Optional[float] = None

        self._build_ui()
        self._schedule_initial_search()

    # ------------------------------------------------------------------
    # Window lifecycle helpers
    # ------------------------------------------------------------------
    @property
    def is_open(self) -> bool:
        return bool(self._toplevel and self._toplevel.winfo_exists())

    def focus(self) -> None:
        if not self.is_open:
            return
        try:
            self._toplevel.deiconify()
            self._toplevel.lift()
            self._toplevel.focus_force()
        except Exception:
            pass

    def close(self) -> None:
        if self._search_job and self._toplevel and self._toplevel.winfo_exists():
            try:
                self._toplevel.after_cancel(self._search_job)
            except Exception:
                pass
        self._search_job = None

        if self._toplevel and self._toplevel.winfo_exists():
            if self._result_poll_job:
                try:
                    self._toplevel.after_cancel(self._result_poll_job)
                except Exception:
                    pass
            if self._reference_suggestion_job:
                try:
                    self._toplevel.after_cancel(self._reference_suggestion_job)
                except Exception:
                    pass
            if self._reference_suggestion_poll_job:
                try:
                    self._toplevel.after_cancel(self._reference_suggestion_poll_job)
                except Exception:
                    pass
            try:
                self._toplevel.destroy()
            except Exception:
                pass
        elif self._result_poll_job and self._toplevel:
            try:
                self._toplevel.after_cancel(self._result_poll_job)
            except Exception:
                pass
        self._result_poll_job = None
        self._reference_suggestion_job = None
        self._reference_suggestion_poll_job = None
        self._pending_search_params = None
        self._search_thread = None

        if self._on_close:
            try:
                self._on_close(self)
            except Exception:
                pass

        self._toplevel = None
        self._hotspot_container = None
        self._hotspot_controls_frame = None
        self._results_frame = None
        self._results_tree = None
        self._reference_entry = None
        self._reference_frame = None
        self._reference_system_var = None
        self._min_hotspots_var = None
        self._hide_reference_suggestions()
        self._reference_suggestions_listbox = None
        self._reference_suggestions_visible = False
        self._reference_suggestions_suppressed = False
        self._pagination_frame = None
        self._pagination_pack_options = {}
        self._prev_page_button = None
        self._next_page_button = None
        self._page_label_var = None
        self._active_params = None
        self._last_successful_params = None
        self._last_result_total = 0
        self._last_results_count = 0
        self._pagination_has_prev = False
        self._pagination_has_next = False
        self._search_started_at = None
        self._last_search_duration = None

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        container = tk.Frame(self._toplevel, highlightthickness=0, bd=0)
        container.pack(fill="both", expand=True, padx=12, pady=12)
        self._theme.register(container)
        self._hotspot_container = container

        filters = self._controller.get_saved_filters()

        reference_initial = self._controller.get_current_system()
        self._reference_system_var.set(reference_initial)
        self._reference_last_query = reference_initial.strip().lower()

        layout_frame = tk.Frame(container, highlightthickness=0, bd=0)
        layout_frame.pack(fill="x", pady=(0, 12))
        self._theme.register(layout_frame)
        layout_frame.columnconfigure(0, weight=1)
        layout_frame.columnconfigure(1, weight=1)
        layout_frame.rowconfigure(0, weight=0)
        layout_frame.rowconfigure(1, weight=1)

        reference_frame = tk.Frame(layout_frame, highlightthickness=0, bd=0)
        reference_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=(0, 8))
        self._theme.register(reference_frame)
        self._reference_frame = reference_frame

        reference_frame.columnconfigure(0, weight=0)
        reference_frame.columnconfigure(1, weight=1)

        reference_label = tk.Label(reference_frame, text="Reference System", anchor="w")
        reference_label.grid(row=0, column=0, sticky="w", padx=0)
        self._theme.register(reference_label)

        reference_entry = ttk.Entry(reference_frame, textvariable=self._reference_system_var, width=28)
        reference_entry.grid(row=0, column=1, sticky="ew")
        self._theme.register(reference_entry)
        reference_entry.bind("<KeyRelease>", self._handle_reference_key_release, add="+")
        reference_entry.bind("<Down>", self._handle_reference_entry_down, add="+")
        reference_entry.bind("<Return>", self._handle_reference_entry_return, add="+")
        self._reference_entry = reference_entry

        suggestions_listbox = tk.Listbox(reference_frame, height=6, exportselection=False)
        self._theme.register(suggestions_listbox)
        suggestions_listbox.grid(row=1, column=1, sticky="ew", pady=(0, 0))
        suggestions_listbox.grid_remove()
        suggestions_listbox.bind("<Return>", self._apply_reference_suggestion_event, add="+")
        suggestions_listbox.bind("<Double-Button-1>", self._apply_reference_suggestion_event, add="+")
        suggestions_listbox.bind("<Escape>", self._hide_reference_suggestions_event, add="+")
        suggestions_listbox.bind("<FocusOut>", self._on_reference_suggestions_focus_out, add="+")
        suggestions_listbox.bind("<Up>", self._handle_suggestion_navigation, add="+")
        suggestions_listbox.bind("<Down>", self._handle_suggestion_navigation, add="+")
        self._reference_suggestions_listbox = suggestions_listbox

        self._distance_min_var.set(self._format_distance(filters.distance_min, self.DEFAULT_DISTANCE_MIN))
        self._distance_max_var.set(self._format_distance(filters.distance_max, self.DEFAULT_DISTANCE_MAX))

        left_controls_frame = tk.Frame(layout_frame, highlightthickness=0, bd=0)
        left_controls_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        left_controls_frame.columnconfigure(0, weight=1)
        left_controls_frame.columnconfigure(1, weight=0)
        left_controls_frame.rowconfigure(1, weight=1)
        self._theme.register(left_controls_frame)
        self._hotspot_controls_frame = left_controls_frame

        distance_frame = tk.LabelFrame(left_controls_frame, text="Distance (LY)")
        distance_frame.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._theme.register(distance_frame)

        tk.Label(distance_frame, text="Min").grid(row=0, column=0, sticky="w", padx=(4, 4), pady=(2, 2))
        min_entry = ttk.Entry(distance_frame, textvariable=self._distance_min_var, width=8)
        min_entry.grid(row=0, column=1, sticky="w", padx=(0, 8), pady=(2, 2))

        tk.Label(distance_frame, text="Max").grid(row=1, column=0, sticky="w", padx=(4, 4), pady=(2, 2))
        max_entry = ttk.Entry(distance_frame, textvariable=self._distance_max_var, width=8)
        max_entry.grid(row=1, column=1, sticky="w", padx=(0, 8), pady=(2, 2))

        reserve_frame = tk.LabelFrame(left_controls_frame, text="Reserve Level")
        reserve_frame.grid(row=0, column=1, sticky="ew")
        self._theme.register(reserve_frame)

        reserve_values = self._reserve_level_options or self.FALLBACK_RESERVE_LEVELS
        reserve_combo = ttk.Combobox(
            reserve_frame,
            textvariable=self._reserve_var,
            values=reserve_values,
            width=12,
            state="readonly",
        )
        reserve_combo.grid(row=0, column=0, padx=6, pady=6)
        reserve_default = self._resolve_single_default(filters.reserve_levels, reserve_values, self.DEFAULT_RESERVE)
        self._reserve_var.set(reserve_default)
        if reserve_default in reserve_values:
            reserve_combo.set(reserve_default)
        elif reserve_values:
            reserve_combo.current(0)
        self._reserve_combobox = reserve_combo

        ring_type_frame = tk.LabelFrame(left_controls_frame, text="Ring Filters")
        ring_type_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 0), padx=(0, 8))
        self._theme.register(ring_type_frame)

        ring_type_list = tk.Listbox(
            ring_type_frame,
            selectmode="extended",
            height=min(6, max(3, len(self._ring_type_options))),
            exportselection=False,
        )
        ring_type_list.grid(row=0, column=0, padx=6, pady=6)
        self._theme.register(ring_type_list)
        for option in self._ring_type_options:
            ring_type_list.insert("end", option)
        self._ring_type_listbox = ring_type_list
        default_ring_types = self._filter_defaults(filters.ring_types, self._ring_type_options)
        allow_empty_rings = filters.ring_types is not None
        self._select_defaults(
            ring_type_list,
            default_ring_types,
            fallback=self.DEFAULT_RING_TYPE,
            allow_empty=allow_empty_rings,
        )
        ring_type_list.bind("<<ListboxSelect>>", self._on_filters_changed, add="+")

        min_hotspots_initial = filters.min_hotspots or self.DEFAULT_MIN_HOTSPOTS
        min_hotspots_initial = max(1, int(min_hotspots_initial or self.DEFAULT_MIN_HOTSPOTS))
        self._min_hotspots_var = tk.StringVar(master=self._toplevel, value=str(min_hotspots_initial))
        min_hotspots_frame = tk.LabelFrame(left_controls_frame, text="Minimum Hotspots")
        min_hotspots_frame.grid(row=1, column=1, sticky="ew", pady=(8, 0))
        self._theme.register(min_hotspots_frame)
        spinbox_kwargs = {
            "from_": 1,
            "to": 999,
            "width": 6,
            "textvariable": self._min_hotspots_var,
            "increment": 1,
        }
        try:
            min_hotspots_spin = ttk.Spinbox(min_hotspots_frame, **spinbox_kwargs)
        except AttributeError:
            min_hotspots_spin = tk.Spinbox(min_hotspots_frame, **spinbox_kwargs)
        min_hotspots_spin.grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self._theme.register(min_hotspots_spin)
        self._min_hotspots_var.trace_add("write", self._on_filters_changed)

        signal_frame = tk.LabelFrame(layout_frame, text="Ring Signals")
        signal_frame.grid(row=0, column=1, rowspan=2, sticky="nsew")
        self._theme.register(signal_frame)

        signal_list = tk.Listbox(
            signal_frame,
            selectmode="extended",
            height=10,
            exportselection=False,
        )
        signal_list.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        self._theme.register(signal_list)
        signal_scroll = tk.Scrollbar(signal_frame, orient="vertical", command=signal_list.yview)
        signal_scroll.grid(row=0, column=1, sticky="ns", pady=6, padx=(0, 6))
        signal_list.configure(yscrollcommand=signal_scroll.set)
        for option in self._ring_signal_options:
            signal_list.insert("end", option)
        self._signals_listbox = signal_list
        default_signals = self._filter_defaults(filters.ring_signals, self._ring_signal_options)
        allow_empty_signals = filters.ring_signals is not None
        self._select_defaults(
            signal_list,
            default_signals,
            fallback=self.DEFAULT_SIGNAL,
            allow_empty=allow_empty_signals,
        )
        signal_list.bind("<<ListboxSelect>>", self._on_filters_changed, add="+")
        signal_frame.columnconfigure(0, weight=1)

        action_frame = tk.Frame(container, highlightthickness=0, bd=0)
        action_frame.pack(fill="x", pady=(0, 8))
        self._theme.register(action_frame)

        search_button = ttk.Button(action_frame, text="Search", command=self._perform_search)
        search_button.pack(side="left")

        status_label = tk.Label(action_frame, textvariable=self._status_var, anchor="w", justify="left")
        status_label.pack(side="left", fill="x", expand=True, padx=(12, 0))
        self._theme.register(status_label)

        results_frame = tk.Frame(container, highlightthickness=0, bd=0)
        results_frame.pack(fill="both", expand=True)
        self._theme.register(results_frame)
        self._results_frame = results_frame

        columns = ("copy", "system", "body", "ring", "type", "distance_ly", "distance_ls", "signals")
        tree = ttk.Treeview(results_frame, columns=columns, show="headings")
        tree.heading("copy", text="")
        tree.heading("system", text="System")
        tree.heading("body", text="Body")
        tree.heading("ring", text="Ring")
        tree.heading("type", text="Type")
        tree.heading("distance_ly", text="Distance (LY)")
        tree.heading("distance_ls", text="Dist2Arrival (LS)")
        tree.heading("signals", text="Signals")

        tree.column("copy", width=28, minwidth=28, anchor="center", stretch=False)
        tree.column("system", width=140, minwidth=140, anchor="w", stretch=False)
        tree.column("body", width=140, anchor="w")
        tree.column("ring", width=160, anchor="w")
        tree.column("type", width=120, anchor="w")
        tree.column("distance_ly", width=110, anchor="e")
        tree.column("distance_ls", width=110, anchor="e")
        tree.column("signals", width=260, anchor="w")

        try:
            heading_font = tkfont.nametofont("TkHeadingFont")
        except tk.TclError:
            heading_font = tkfont.nametofont("TkDefaultFont")
        label_widths = {
            "body": "Body",
            "ring": "Ring",
            "type": "Type",
            "distance_ly": "Distance (LY)",
            "distance_ls": "Dist2Arrival (LS)",
        }
        padding = 16
        for column, label in label_widths.items():
            width = heading_font.measure(label) + padding
            tree.column(column, width=width, minwidth=width, stretch=False)

        tree_scroll = ttk.Scrollbar(results_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        self._results_tree = tree
        pagination_frame = tk.Frame(container, highlightthickness=0, bd=0)
        pagination_frame.pack(fill="x", pady=(6, 0))
        self._theme.register(pagination_frame)
        self._pagination_frame = pagination_frame
        self._pagination_pack_options = {"fill": "x", "pady": (6, 0)}

        self._page_label_var = tk.StringVar(master=self._toplevel, value="")
        page_label = tk.Label(pagination_frame, textvariable=self._page_label_var, anchor="e")
        page_label.pack(side="right", padx=(0, 8))
        self._theme.register(page_label)

        next_button = ttk.Button(pagination_frame, text="Next", command=self._goto_next_page, state="disabled")
        next_button.pack(side="right")
        self._theme.register(next_button)
        self._next_page_button = next_button

        prev_button = ttk.Button(pagination_frame, text="Previous", command=self._goto_previous_page, state="disabled")
        prev_button.pack(side="right", padx=(0, 4))
        self._theme.register(prev_button)
        self._prev_page_button = prev_button

        pagination_frame.pack_forget()

        tree.bind("<ButtonRelease-1>", self._handle_result_click, add="+")
        self._schedule_result_poll()
        reserve_combo.bind("<<ComboboxSelected>>", self._on_filters_changed, add="+")
        self._distance_min_var.trace_add("write", self._on_filters_changed)
        self._distance_max_var.trace_add("write", self._on_filters_changed)
        self._reference_system_var.trace_add("write", self._on_filters_changed)
        self._on_filters_changed()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _schedule_initial_search(self) -> None:
        if not self.is_open:
            return
        self._last_search_duration = None
        self._set_search_status("Searching for hotspots...", include_duration=False)
        self._search_job = self._toplevel.after(50, self._perform_search)

    @staticmethod
    def _sorted_unique(values: Sequence[str], fallback: Sequence[str], preserve_order: bool = False) -> List[str]:
        cleaned = [value for value in values if isinstance(value, str) and value]
        if not cleaned:
            cleaned = list(fallback)
        if preserve_order:
            seen: set[str] = set()
            ordered: List[str] = []
            for value in cleaned:
                if value in seen:
                    continue
                seen.add(value)
                ordered.append(value)
            return ordered
        return sorted(set(cleaned), key=str.casefold)

    @staticmethod
    def _select_defaults(
        listbox: Optional[tk.Listbox],
        defaults: Sequence[str],
        *,
        fallback: Optional[str] = None,
        allow_empty: bool = False,
    ) -> None:
        if not listbox:
            return
        options = listbox.get(0, "end")
        selected = False
        for default in defaults:
            try:
                index = options.index(default)
            except ValueError:
                continue
            listbox.selection_set(index)
            listbox.see(index)
            selected = True

        if selected:
            return

        if allow_empty:
            listbox.selection_clear(0, "end")
            return

        if fallback and fallback in options:
            try:
                index = options.index(fallback)
                listbox.selection_set(index)
                listbox.see(index)
                return
            except ValueError:
                pass

        if options:
            listbox.selection_set(0)

    @staticmethod
    def _format_distance(value: Optional[float], fallback: str) -> str:
        if value is None:
            return fallback
        try:
            return f"{float(value):g}"
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _filter_defaults(candidates: Optional[Sequence[str]], options: Sequence[str]) -> List[str]:
        if not candidates:
            return []
        filtered: List[str] = []
        option_set = {opt for opt in options}
        for candidate in candidates:
            if candidate in option_set and candidate not in filtered:
                filtered.append(candidate)
        return filtered

    @staticmethod
    def _resolve_single_default(
        candidates: Optional[Sequence[str]],
        options: Sequence[str],
        fallback: str,
    ) -> str:
        if candidates:
            for candidate in candidates:
                if candidate in options:
                    return candidate
        if fallback in options:
            return fallback
        return options[0] if options else fallback

    @staticmethod
    def _parse_float(value: str, fallback: float) -> float:
        stripped = value.strip() if value else ""
        if not stripped:
            return fallback
        return float(stripped)

    @staticmethod
    def _parse_optional_float(value: Optional[str]) -> Optional[float]:
        stripped = value.strip() if value else ""
        if not stripped:
            return None
        try:
            return float(stripped)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_min_hotspots(value: Optional[str], default: int) -> int:
        stripped = value.strip() if value else ""
        if not stripped:
            return max(1, default)
        try:
            parsed = int(stripped)
        except (TypeError, ValueError):
            return max(1, default)
        return max(1, parsed)

    @staticmethod
    def _get_listbox_selection(listbox: Optional[tk.Listbox]) -> List[str]:
        if not listbox:
            return []
        selections: List[str] = []
        try:
            indices = listbox.curselection()
        except Exception:
            return []
        for index in indices:
            try:
                value = listbox.get(index)
            except Exception:
                continue
            if isinstance(value, str):
                selections.append(value)
        return selections

    def _handle_reference_key_release(self, event: tk.Event) -> Optional[str]:
        keysym = getattr(event, "keysym", "")
        if keysym in {"Up", "Down", "Left", "Right", "Escape", "Return", "Tab"}:
            if keysym == "Escape":
                self._hide_reference_suggestions()
            return None
        self._queue_reference_suggestion_fetch()
        return None

    def _handle_reference_entry_down(self, event: tk.Event) -> Optional[str]:
        if self._reference_suggestions_visible and self._reference_suggestions_listbox:
            if self._reference_suggestions_listbox.size() > 0:
                self._reference_suggestions_listbox.selection_clear(0, "end")
                self._reference_suggestions_listbox.selection_set(0)
                self._reference_suggestions_listbox.activate(0)
                self._reference_suggestions_listbox.focus_set()
                return "break"
        return None

    def _handle_reference_entry_return(self, _event: tk.Event) -> str:
        self._reference_suggestions_suppressed = True
        self._hide_reference_suggestions()
        self._perform_search()
        return "break"

    def _handle_result_click(self, event: tk.Event) -> None:
        tree = self._results_tree
        if not tree or not tree.winfo_exists():
            return

        item_id = tree.identify_row(event.y)
        if not item_id:
            return
        column = tree.identify_column(event.x)
        if column != "#1":
            return

        values = tree.item(item_id, "values")
        if not values or len(values) < 2:
            return
        system_name = values[1]
        if not isinstance(system_name, str) or not system_name.strip():
            return
        self._copy_system_to_clipboard(system_name.strip())

    def _queue_reference_suggestion_fetch(self) -> None:
        if not self._reference_system_var or not self._toplevel:
            return
        query = self._reference_system_var.get().strip()
        query_key = query.lower()
        if query_key == self._reference_last_query:
            if self._reference_suggestions_suppressed:
                return
            return
        self._reference_suggestions_suppressed = False
        self._reference_last_query = query_key
        if self._reference_suggestion_job:
            try:
                self._toplevel.after_cancel(self._reference_suggestion_job)
            except Exception:
                pass
        self._reference_suggestion_job = self._toplevel.after(200, lambda q=query: self._request_reference_suggestions(q))

    def _request_reference_suggestions(self, query: str) -> None:
        self._reference_suggestion_job = None
        if not self.is_open:
            return
        trimmed = query.strip()
        if len(trimmed) < 2:
            self._update_reference_suggestions([])
            return

        token = self._controller.request_reference_suggestions(trimmed)
        if token is None:
            self._update_reference_suggestions([])
            return

        self._reference_suggestion_token = token
        self._schedule_reference_suggestion_poll()

    def _schedule_reference_suggestion_poll(self) -> None:
        if not self._toplevel or not self._toplevel.winfo_exists():
            return
        if self._reference_suggestion_poll_job:
            return
        self._reference_suggestion_poll_job = self._toplevel.after(100, self._poll_reference_suggestions)

    def _poll_reference_suggestions(self) -> None:
        self._reference_suggestion_poll_job = None
        if not self.is_open:
            return

        latest: Optional[List[str]] = None
        while True:
            item = self._controller.poll_reference_suggestions()
            if not item:
                break
            token, suggestions = item
            if token >= self._reference_suggestion_token:
                latest = suggestions

        if latest is not None:
            self._update_reference_suggestions(latest)

        if self._reference_suggestion_token:
            self._schedule_reference_suggestion_poll()

    def _update_reference_suggestions(self, suggestions: List[str]) -> None:
        if not self._reference_suggestions_listbox:
            return

        self._reference_suggestions_listbox.delete(0, "end")
        if not suggestions:
            self._hide_reference_suggestions()
            return

        seen: set[str] = set()
        for item in suggestions:
            lowered = item.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            self._reference_suggestions_listbox.insert("end", item)

        if self._reference_suggestions_listbox.size() > 0:
            self._reference_suggestions_listbox.selection_clear(0, "end")
            self._reference_suggestions_listbox.selection_set(0)
            self._reference_suggestions_listbox.activate(0)

        if not self._reference_suggestions_visible:
            try:
                self._reference_suggestions_listbox.grid(row=1, column=1, sticky="ew", pady=(0, 0))
            except tk.TclError:
                pass
            self._reference_suggestions_visible = True

    def _hide_reference_suggestions(self) -> None:
        if self._reference_suggestions_listbox and self._reference_suggestions_visible:
            try:
                self._reference_suggestions_listbox.grid_remove()
            except tk.TclError:
                self._reference_suggestions_listbox.pack_forget()
            self._reference_suggestions_listbox.selection_clear(0, "end")
            self._reference_suggestions_visible = False

    def _hide_reference_suggestions_event(self, _event: tk.Event) -> str:
        self._hide_reference_suggestions()
        if self._reference_entry:
            self._reference_entry.focus_set()
        return "break"

    def _on_reference_suggestions_focus_out(self, _event: tk.Event) -> None:
        if not self._toplevel or not self._toplevel.winfo_exists():
            return
        self._toplevel.after(150, self._hide_reference_suggestions)

    def _apply_reference_suggestion_event(self, _event: tk.Event) -> str:
        self._apply_reference_suggestion()
        self._reference_last_query = self._reference_system_var.get().strip().lower() if self._reference_system_var else ""
        self._reference_suggestions_suppressed = True
        return "break"

    def _apply_reference_suggestion(self) -> None:
        if not self._reference_suggestions_listbox or not self._reference_system_var:
            return
        selection = self._reference_suggestions_listbox.curselection()
        if not selection:
            return
        value = self._reference_suggestions_listbox.get(selection[0])
        if not isinstance(value, str):
            return
        trimmed = value.strip()
        lowered = trimmed.lower()
        self._reference_last_query = lowered
        self._reference_suggestions_suppressed = True
        self._reference_system_var.set(trimmed)
        self._perform_search()
        self._hide_reference_suggestions()
        if self._reference_entry:
            self._reference_entry.focus_set()
            self._reference_entry.icursor("end")

    def _handle_suggestion_navigation(self, event: tk.Event) -> str:
        if not self._reference_suggestions_listbox:
            return "break"
        size = self._reference_suggestions_listbox.size()
        if size == 0:
            return "break"
        selection = self._reference_suggestions_listbox.curselection()
        index = selection[0] if selection else -1
        if event.keysym == "Up":
            index = 0 if index <= 0 else index - 1
        elif event.keysym == "Down":
            index = 0 if index < 0 else min(size - 1, index + 1)
        else:
            return "break"
        self._reference_suggestions_listbox.selection_clear(0, "end")
        self._reference_suggestions_listbox.selection_set(index)
        self._reference_suggestions_listbox.activate(index)
        return "break"

    def _collect_selections(self) -> Tuple[float, float, List[str], List[str], List[str], int]:
        min_distance = self._parse_float(self._distance_min_var.get(), float(self.DEFAULT_DISTANCE_MIN))
        max_distance = self._parse_float(self._distance_max_var.get(), float(self.DEFAULT_DISTANCE_MAX))

        reserve_value = self._reserve_var.get().strip()
        reserves = [reserve_value] if reserve_value else []

        signal_list = self._signals_listbox
        signals = []
        if signal_list:
            signals = [signal_list.get(index) for index in signal_list.curselection()]

        ring_type_list = self._ring_type_listbox
        ring_types = []
        if ring_type_list:
            ring_types = [ring_type_list.get(index) for index in ring_type_list.curselection()]

        min_hotspots = self._parse_min_hotspots(
            self._min_hotspots_var.get() if self._min_hotspots_var else None,
            self.DEFAULT_MIN_HOTSPOTS,
        )

        return min_distance, max_distance, signals, reserves, ring_types, min_hotspots

    def _set_search_status(self, message: str, *, include_duration: bool = True) -> None:
        if not self._status_var:
            return
        if include_duration and self._last_search_duration is not None:
            formatted = self._format_query_duration(self._last_search_duration)
            if formatted:
                message = f"{message} (Query {formatted})" if message else f"Query {formatted}"
        self._status_var.set(message)

    @staticmethod
    def _format_query_duration(duration: float) -> str:
        if duration < 0:
            duration = 0.0
        if duration < 1:
            return f"{duration * 1000:.0f} ms"
        if duration < 10:
            return f"{duration:.2f} s"
        if duration < 60:
            return f"{duration:.1f} s"
        minutes = int(duration // 60)
        seconds = duration - minutes * 60
        if minutes and seconds >= 1:
            return f"{minutes}m {seconds:.0f}s"
        if minutes:
            return f"{minutes}m"
        return f"{duration:.1f} s"

    def _finalize_search_duration(self) -> Optional[float]:
        if self._search_started_at is None:
            return self._last_search_duration
        elapsed = max(0.0, time.perf_counter() - self._search_started_at)
        self._last_search_duration = elapsed
        self._search_started_at = None
        return elapsed

    def _set_pagination_visible(self, visible: bool) -> None:
        frame = self._pagination_frame
        if not frame:
            return
        managed = frame.winfo_manager()
        if visible:
            options = self._pagination_pack_options or {"fill": "x", "pady": (6, 0)}
            if managed != "pack":
                frame.pack(**options)
        else:
            if managed:
                frame.pack_forget()
            if self._page_label_var:
                self._page_label_var.set("")

    def _set_pagination_buttons_state(self, prev_enabled: bool, next_enabled: bool) -> None:
        if self._prev_page_button:
            self._prev_page_button.configure(state="normal" if prev_enabled else "disabled")
        if self._next_page_button:
            self._next_page_button.configure(state="normal" if next_enabled else "disabled")

    def _is_search_in_progress(self) -> bool:
        return self._active_search_token is not None

    def _apply_pagination_button_state(self) -> None:
        buttons_enabled = not self._is_search_in_progress()
        self._set_pagination_buttons_state(
            self._pagination_has_prev and buttons_enabled,
            self._pagination_has_next and buttons_enabled,
        )
        self._set_pagination_visible(self._pagination_has_prev or self._pagination_has_next)

    def _update_pagination_controls(self, result: HotspotSearchResult) -> None:
        params = self._active_params or self._last_successful_params
        if not params:
            self._pagination_has_prev = False
            self._pagination_has_next = False
            self._set_pagination_visible(False)
            return

        limit = max(1, int(params.limit or self.RESULTS_PER_PAGE))
        page_index = max(0, int(params.page))
        entries_count = len(result.entries)
        total = int(result.total_count or 0)

        self._last_results_count = entries_count
        self._last_result_total = total

        has_prev = page_index > 0
        if total > 0:
            has_next = (page_index + 1) * limit < total
        else:
            has_next = entries_count >= limit

        self._pagination_has_prev = has_prev
        self._pagination_has_next = has_next

        if self._page_label_var:
            if not (has_prev or has_next):
                self._page_label_var.set("")
            elif total > 0:
                total_pages = max(1, (total + limit - 1) // limit)
                self._page_label_var.set(f"Page {page_index + 1} of {total_pages}")
            else:
                self._page_label_var.set(f"Page {page_index + 1}")

        self._apply_pagination_button_state()

    def _goto_previous_page(self) -> None:
        if self._is_search_in_progress():
            return
        params = self._last_successful_params
        if not params:
            return
        target_page = max(0, int(params.page) - 1)
        if target_page == params.page:
            return
        self._request_page(target_page)

    def _goto_next_page(self) -> None:
        if self._is_search_in_progress():
            return
        params = self._last_successful_params
        if not params:
            return
        limit = max(1, int(params.limit or self.RESULTS_PER_PAGE))
        total = self._last_result_total
        entries_count = self._last_results_count
        next_page = int(params.page) + 1
        if total > 0 and next_page * limit >= total:
            return
        if total <= 0 and entries_count < limit:
            return
        self._request_page(next_page)

    def _request_page(self, target_page: int) -> None:
        params = self._last_successful_params
        if not params:
            return
        target = max(0, target_page)
        new_params = replace(params, page=target)
        self._start_search(new_params)

    def _on_filters_changed(self, *_: object) -> None:
        distance_min_text = self._distance_min_var.get() if self._distance_min_var else ""
        distance_max_text = self._distance_max_var.get() if self._distance_max_var else ""
        reserve_value = self._reserve_var.get().strip() if self._reserve_var else ""
        reserves = [reserve_value] if reserve_value else []
        ring_types = self._get_listbox_selection(self._ring_type_listbox)
        ring_signals = self._get_listbox_selection(self._signals_listbox)
        min_hotspots = self._parse_min_hotspots(
            self._min_hotspots_var.get() if self._min_hotspots_var else None,
            self.DEFAULT_MIN_HOTSPOTS,
        )

        self._controller.persist_filters_from_ui(
            distance_min_text,
            distance_max_text,
            reserves,
            ring_types,
            ring_signals,
            min_hotspots,
        )

        self._queue_reference_suggestion_fetch()

    # ------------------------------------------------------------------
    # Search + render
    # ------------------------------------------------------------------
    def _perform_search(self) -> None:
        self._search_job = None
        if not self.is_open:
            return

        try:
            min_distance, max_distance, signals, reserves, ring_types, min_hotspots = self._collect_selections()
        except ValueError as exc:
            self._set_search_status(f"Invalid input: {exc}", include_duration=False)
            return

        reference_input = self._reference_system_var.get().strip() if self._reference_system_var else ""
        self._controller.persist_filters_from_ui(
            self._distance_min_var.get() if self._distance_min_var else "",
            self._distance_max_var.get() if self._distance_max_var else "",
            reserves,
            ring_types,
            signals,
            min_hotspots,
        )
        fallback_system = reference_input or self._controller.get_current_system() or ""
        if not fallback_system:
            self._set_search_status(
                "Reference system unknown. Enter a system name to search for hotspots.",
                include_duration=False,
            )
            return

        params = HotspotSearchParams(
            distance_min=float(min_distance),
            distance_max=float(max_distance),
            ring_signals=tuple(signals),
            reserve_levels=tuple(reserves),
            ring_types=tuple(ring_types),
            min_hotspots=int(min_hotspots),
            reference_text=reference_input,
            page=0,
            limit=self.RESULTS_PER_PAGE,
        )
        self._start_search(params)

    def _start_search(self, params: HotspotSearchParams) -> None:
        if not self.is_open:
            return

        self._active_params = params
        self._last_results_count = 0
        self._set_pagination_buttons_state(False, False)
        self._schedule_result_poll()

        reference_text = (params.reference_text or "").strip()
        display_reference = reference_text or self._controller.get_current_system() or "Unknown system"

        self._hide_reference_suggestions()

        result = self._controller.begin_search(params, display_reference)
        self._last_search_duration = None
        self._set_search_status(result.status, include_duration=False)

        if not result.started:
            self._apply_pagination_button_state()
            return

        self._active_search_token = result.token
        self._search_started_at = time.perf_counter()

        tree = self._results_tree
        if tree:
            for item in tree.get_children():
                tree.delete(item)

        if self._toplevel:
            try:
                self._toplevel.update_idletasks()
            except Exception:
                pass
        self._apply_pagination_button_state()

    def _render_results(self, result: HotspotSearchResult) -> None:
        tree = self._results_tree
        if not tree:
            return

        params = self._active_params
        if params:
            self._last_successful_params = params

        for item in tree.get_children():
            tree.delete(item)

        entries = list(result.entries)
        system_labels: List[str] = []
        signals_labels: List[str] = []
        ring_labels: List[str] = []
        type_labels: List[str] = []
        for entry in entries:
            signals_text = ", ".join(
                f"{signal.name} ({signal.count})" if signal.count else signal.name for signal in entry.signals
            )
            if not signals_text:
                signals_text = "—"
            signals_labels.append(signals_text)
            system_display = entry.system_name or "—"
            system_labels.append(system_display)
            body_display = entry.body_name or "—"
            if entry.system_name and entry.body_name:
                system = entry.system_name.strip()
                body = entry.body_name.strip()
                if system and body.lower().startswith(system.lower()):
                    trimmed_body = body[len(system) :].lstrip(" -")
                    if trimmed_body:
                        body_display = trimmed_body
            if not body_display or body_display == entry.body_name:
                body_display = entry.body_name or "—"
            ring_display = entry.ring_name or "—"
            if entry.body_name and entry.ring_name:
                body = entry.body_name.strip()
                ring = entry.ring_name.strip()
                if body and ring.lower().startswith(body.lower()):
                    trimmed = ring[len(body) :].lstrip(" -")
                    if trimmed:
                        ring_display = trimmed
            if not ring_display or ring_display == entry.ring_name:
                ring_display = entry.ring_name or "—"
            ring_labels.append(ring_display or "—")
            type_labels.append(entry.ring_type or "—")
            tree.insert(
                "",
                "end",
                values=(
                    "📋",
                    system_display,
                    body_display,
                    ring_display,
                    entry.ring_type or "—",
                    f"{entry.distance_ly:.2f}",
                    f"{entry.distance_ls:.0f}",
                    signals_text,
                ),
            )

        if entries:
            try:
                item_font_name = tree.cget("font")
            except tk.TclError:
                item_font_name = ""
            try:
                item_font = (
                    tkfont.nametofont(item_font_name)
                    if item_font_name
                    else tkfont.nametofont("TkDefaultFont")
                )
            except tk.TclError:
                item_font = None

            try:
                heading_font = tkfont.nametofont("TkHeadingFont")
            except tk.TclError:
                heading_font = None

            system_width = 0
            if item_font:
                max_width = max(item_font.measure(label) for label in (*system_labels, "System"))
                system_width = max(140, max_width + 16)
                tree.column("system", width=system_width, minwidth=system_width, stretch=False)
                signals_width = max(item_font.measure(label) for label in (*signals_labels, "Signals"))
                ring_width = max(item_font.measure(label) for label in (*ring_labels, "Ring"))
                type_width = max(item_font.measure(label) for label in (*type_labels, "Type"))
            else:
                system_width = 0
                signals_width = 0
                ring_width = 0
                type_width = 0

            header_width = heading_font.measure("Signals") if heading_font else signals_width
            target_signal_width = max(header_width, signals_width) + 16
            current_config = tree.column("signals")
            current_width = current_config.get("width", 0) if isinstance(current_config, dict) else 0
            current_min = current_config.get("minwidth", 0) if isinstance(current_config, dict) else 0
            effective_width = max(target_signal_width, current_width, current_min)
            if effective_width > 0:
                tree.column("signals", width=effective_width, minwidth=effective_width, stretch=False)

            def _resize_column(column: str, content_width: int, header_text: str) -> None:
                header_w = heading_font.measure(header_text) if heading_font else content_width
                target = max(header_w, content_width) + 16
                config = tree.column(column)
                current_w = config.get("width", 0) if isinstance(config, dict) else 0
                current_min_w = config.get("minwidth", 0) if isinstance(config, dict) else 0
                effective = max(target, current_w, current_min_w)
                if effective > 0:
                    tree.column(column, width=effective, minwidth=effective, stretch=False)

            if ring_width:
                _resize_column("ring", ring_width, "Ring")
            if type_width:
                _resize_column("type", type_width, "Type")

        self._update_pagination_controls(result)
        self._resize_to_fit_results()

        if not entries:
            self._set_search_status("No hotspots matched the selected filters.")
            return

        status_parts = [f"Displaying {len(entries)} hotspot(s)"]
        if result.total_count > len(entries):
            status_parts.append(f"of {result.total_count} total matches")
        if result.reference_system:
            status_parts.append(f"near {result.reference_system}")
        self._set_search_status("; ".join(status_parts))

    def _handle_search_outcome(self, token: int, outcome: tuple[str, object]) -> None:
        if not self.is_open:
            return

        if self._active_search_token is not None and token != self._active_search_token:
            return

        kind, payload = outcome
        if kind == "success":
            resolved_reference: Optional[str] = None
            result_obj: Optional[HotspotSearchResult] = None
            if isinstance(payload, tuple) and len(payload) == 2:
                candidate_result, candidate_reference = payload
                if isinstance(candidate_result, HotspotSearchResult):
                    result_obj = candidate_result
                if isinstance(candidate_reference, str) and candidate_reference:
                    resolved_reference = candidate_reference
            elif isinstance(payload, HotspotSearchResult):
                result_obj = payload

            if result_obj is None:
                self._finalize_search_duration()
                _log.warning("Unexpected search payload type: %r", type(payload))
            else:
                self._finalize_search_duration()
                if resolved_reference:
                    if (
                        self._reference_system_var
                        and self._reference_system_var.get().strip() != resolved_reference
                    ):
                        lowered = resolved_reference.strip().lower()
                        self._reference_last_query = lowered
                        self._reference_suggestions_suppressed = True
                        self._reference_system_var.set(resolved_reference)
                self._render_results(result_obj)
        elif kind in {"value_error", "runtime_error"}:
            message = str(payload) if payload else "An unexpected error occurred while searching for hotspots."
            self._finalize_search_duration()
            self._set_search_status(message)
        else:
            self._finalize_search_duration()
            self._set_search_status("An unexpected error occurred while searching for hotspots.")

        pending = self._controller.on_search_complete()
        self._active_search_token = None
        self._apply_pagination_button_state()
        if pending is not None:
            self._start_search(pending)

    def _resize_to_fit_results(self) -> None:
        if not self._toplevel or not self._results_tree:
            return
        try:
            self._toplevel.update_idletasks()
            if self._results_tree.winfo_exists():
                self._results_tree.update_idletasks()
            widths: List[int] = []
            if self._results_frame and self._results_frame.winfo_exists():
                widths.append(self._results_frame.winfo_reqwidth())
            if self._hotspot_controls_frame and self._hotspot_controls_frame.winfo_exists():
                widths.append(self._hotspot_controls_frame.winfo_reqwidth())
            if self._hotspot_container and self._hotspot_container.winfo_exists():
                widths.append(self._hotspot_container.winfo_reqwidth())
            if self._results_tree and self._results_tree.winfo_exists():
                total_columns = 0
                for column in self._results_tree["columns"]:
                    config = self._results_tree.column(column)
                    if isinstance(config, dict):
                        total_columns += config.get("width", 0)
                if total_columns:
                    widths.append(total_columns + 24)
            if not widths:
                widths.append(self._results_tree.winfo_reqwidth())
            padding = 24  # container has padx=12 on each side
            desired_width = max(widths) + padding
            current_width = self._toplevel.winfo_width()
            if current_width <= 1:
                current_width = self._toplevel.winfo_reqwidth()
            current_height = self._toplevel.winfo_height()
            if current_height <= 1:
                current_height = self._toplevel.winfo_reqheight()
            desired_height = self._toplevel.winfo_reqheight()
            if desired_height <= 1:
                desired_height = current_height
            target_width = max(current_width, int(desired_width))
            target_height = max(current_height, int(desired_height))
            self._toplevel.geometry(f"{target_width}x{target_height}")
        except Exception:
            pass

    def _copy_system_to_clipboard(self, system_name: str) -> None:
        if not self._toplevel or not system_name:
            return
        try:
            self._toplevel.clipboard_clear()
            self._toplevel.clipboard_append(system_name)
            self._status_var.set(f"Copied '{system_name}' to clipboard")
        except Exception:
            _log.exception("Failed to copy system name to clipboard")

    def _schedule_result_poll(self) -> None:
        if not self._toplevel or not self._toplevel.winfo_exists():
            return
        if self._result_poll_job:
            return
        self._result_poll_job = self._toplevel.after(100, self._poll_search_results)

    def _poll_search_results(self) -> None:
        self._result_poll_job = None
        if not self.is_open:
            return

        while True:
            item = self._controller.poll_search_results()
            if not item:
                break
            token, outcome = item
            self._handle_search_outcome(token, outcome)

        self._schedule_result_poll()


__all__ = [
    "HotspotSearchParams",
    "HotspotSavedFilters",
    "SearchStartResult",
    "HotspotSearchController",
    "HotspotSearchWindow",
]
