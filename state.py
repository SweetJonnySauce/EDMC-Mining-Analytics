"""Dataclasses that encapsulate runtime state for the EDMC Mining Analytics plugin."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Deque, Dict, List, Optional, Set, Tuple


ProspectKey = Tuple[str, Tuple[Tuple[str, float], ...]]


@dataclass
class InaraSettings:
    """User-configurable settings that influence Inara lookups."""

    search_mode: int = 1  # 1=Best price, 3=Distance
    include_carriers: bool = True
    include_surface: bool = True


@dataclass
class MiningState:
    """Represents the mutable mining session state shared across subsystems."""

    plugin_dir: Optional[Path] = None
    is_mining: bool = False
    mining_start: Optional[datetime] = None
    mining_end: Optional[datetime] = None
    mining_location: Optional[str] = None
    mining_ring: Optional[str] = None
    current_system: Optional[str] = None
    current_ship: Optional[str] = None
    current_ship_key: Optional[str] = None
    cmdr_name: Optional[str] = None

    prospected_count: int = 0
    already_mined_count: int = 0
    duplicate_prospected: int = 0

    cargo_additions: Dict[str, int] = field(default_factory=dict)
    cargo_totals: Dict[str, int] = field(default_factory=dict)
    harvested_commodities: Set[str] = field(default_factory=set)
    commodity_start_times: Dict[str, datetime] = field(default_factory=dict)

    limpets_remaining: Optional[int] = None
    limpets_start: Optional[int] = None
    limpets_start_initialized: bool = False
    collection_drones_launched: int = 0
    prospector_launched_count: int = 0
    abandoned_limpets: int = 0
    last_event_was_drone_launch: bool = False

    prospect_content_counts: Counter[str] = field(default_factory=Counter)
    materials_collected: Counter[str] = field(default_factory=Counter)
    last_cargo_counts: Dict[str, int] = field(default_factory=dict)

    histogram_bin_size: int = 10
    rate_interval_seconds: int = 30
    session_logging_enabled: bool = False
    session_log_retention: int = 30

    prospected_seen: Set[ProspectKey] = field(default_factory=set)
    prospected_samples: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    prospected_histogram: Dict[str, Counter[int]] = field(default_factory=lambda: defaultdict(Counter))

    inara_settings: InaraSettings = field(default_factory=InaraSettings)
    cargo_capacity: Optional[int] = None
    cargo_capacity_is_inferred: bool = False
    current_cargo_tonnage: int = 0
    inferred_capacity_map: Dict[str, int] = field(default_factory=dict)
    is_paused: bool = False
    auto_unpause_on_event: bool = True
    discord_webhook_url: str = ""
    send_summary_to_discord: bool = False
    send_reset_summary: bool = False
    last_session_summary: Optional[str] = None
    discord_image_url: str = ""

    refinement_lookback_seconds: int = 10
    rpm_threshold_red: int = 1
    rpm_threshold_yellow: int = 20
    rpm_threshold_green: int = 40
    recent_refinements: Deque[datetime] = field(default_factory=deque)
    current_rpm: float = 0.0
    max_rpm: float = 0.0


def reset_mining_state(state: MiningState) -> None:
    """Reset mutable mining metrics for a fresh session."""

    state.is_mining = False
    state.mining_start = None
    state.mining_end = None
    state.mining_location = None
    state.mining_ring = None

    state.prospected_count = 0
    state.already_mined_count = 0
    state.duplicate_prospected = 0

    state.cargo_additions.clear()
    state.cargo_totals.clear()
    state.harvested_commodities.clear()
    state.commodity_start_times.clear()

    state.limpets_remaining = None
    state.limpets_start = 0
    state.limpets_start_initialized = False
    state.collection_drones_launched = 0
    state.prospector_launched_count = 0
    state.abandoned_limpets = 0
    state.last_event_was_drone_launch = False

    state.prospect_content_counts.clear()
    state.materials_collected.clear()
    state.last_cargo_counts.clear()

    state.prospected_seen.clear()
    state.prospected_samples.clear()
    state.prospected_histogram.clear()
    state.current_cargo_tonnage = 0
    state.current_ship = None
    state.current_ship_key = None
    state.cargo_capacity_is_inferred = False
    state.is_paused = False
    state.recent_refinements.clear()
    state.current_rpm = 0.0
    state.max_rpm = 0.0


def recompute_histograms(state: MiningState) -> None:
    """Recompute prospecting histograms based on collected samples."""

    histogram: Dict[str, Counter[int]] = defaultdict(Counter)
    size = max(1, state.histogram_bin_size)
    for material, samples in state.prospected_samples.items():
        if not samples:
            continue
        counter = histogram[material]
        for value in samples:
            try:
                clamped = max(0.0, min(float(value), 100.0))
            except (TypeError, ValueError):
                continue
            if clamped >= 100.0:
                clamped = 100.0 - 1e-9
            bin_index = int(clamped // size)
            counter[bin_index] += 1
    state.prospected_histogram = histogram


def register_refinement(state: MiningState, timestamp: datetime) -> None:
    """Record a mining refinement event and refresh RPM metrics."""

    aware_time = _ensure_aware(timestamp)
    state.recent_refinements.append(aware_time)
    update_rpm(state, aware_time)


def update_rpm(state: MiningState, now: Optional[datetime] = None) -> float:
    """Recalculate current and max RPM based on recent refinements."""

    if now is None:
        now = datetime.now(timezone.utc)
    aware_now = _ensure_aware(now)

    window = max(1, int(state.refinement_lookback_seconds or 1))
    cutoff = aware_now - timedelta(seconds=window)

    refinements = state.recent_refinements
    while refinements and refinements[0] < cutoff:
        refinements.popleft()

    count = len(refinements)
    rpm = (count * 60.0) / window if window else 0.0
    state.current_rpm = rpm
    if rpm > state.max_rpm:
        state.max_rpm = rpm
    return rpm


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
