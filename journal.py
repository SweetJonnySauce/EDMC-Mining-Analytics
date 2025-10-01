"""Journal event processing for the EDMC Mining Analytics plugin."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Optional, Tuple
import threading

from state import MiningState, reset_mining_state, recompute_histograms
from logging_utils import get_logger

try:  # pragma: no cover - only available inside EDMC
    from edmc_data import ship_name_map  # type: ignore[import]
except ImportError:  # pragma: no cover - fallback when not running inside EDMC
    ship_name_map = {}


_log = get_logger("journal")
_plugin_log = get_logger()


@dataclass
class PendingShipUpdate:
    """Tracks ship-change events that expect a follow-up loadout."""

    key: str
    context: str
    ship_display: Optional[str]
    ship_source: Optional[str]
    capacity_value: Optional[int]
    capacity_source: Optional[str]
    initiated_at: datetime
    entry: Optional[dict]
    shared_state: Optional[dict]


_PENDING_SHIP_UPDATE_TIMEOUT = timedelta(seconds=10)


class JournalProcessor:
    """Transforms EDMC journal events into mining analytics state updates."""

    def __init__(
        self,
        state: MiningState,
        refresh_ui: Callable[[], None],
        on_session_start: Callable[[], None],
        on_session_end: Callable[[], None],
        persist_inferred_capacities: Callable[[], None],
        notify_mining_activity: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._state = state
        self._refresh_ui = refresh_ui
        self._on_session_start = on_session_start
        self._on_session_end = on_session_end
        self._persist_inferred_capacities = persist_inferred_capacities
        self._notify_mining_activity = notify_mining_activity
        self._initial_state_checked = False
        self._pending_ship_updates: dict[str, PendingShipUpdate] = {}
        self._pending_timeout_timer: Optional[threading.Timer] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def handle_entry(self, entry: dict, shared_state: Optional[dict] = None) -> None:
        if not entry:
            return

        edmc_state = shared_state if isinstance(shared_state, dict) else None

        event_time = self._parse_timestamp(entry.get("timestamp")) or datetime.now(timezone.utc)
        if (
            not self._initial_state_checked
            and edmc_state
            and any(
                key in edmc_state
                for key in ("Ship", "ShipType", "ShipName", "ShipLocalised", "CargoCapacity", "ShipID")
            )
        ):
            self._initial_state_checked = True
            self._handle_ship_update(
                entry=None,
                shared_state=edmc_state,
                context="Initial state detected",
                event_type="InitialState",
                event_time=event_time,
            )
            self._flush_expired_ship_updates(event_time)
            self._schedule_pending_timeout()
        self._schedule_pending_timeout()

        event = entry.get("event")
        if event == "LaunchDrone":
            self._process_launch_drone(entry, edmc_state)
        elif event == "ProspectedAsteroid" and self._state.is_mining:
            self._register_prospected_asteroid(entry)
        elif event == "Cargo":
            self._process_cargo(entry, edmc_state, is_mining=self._state.is_mining)
        elif event == "MiningRefined":
            self._emit_mining_activity("MiningRefined")
        elif event == "SupercruiseEntry" and self._state.is_mining:
            self._update_mining_state(
                False,
                "Entered Supercruise",
                entry.get("timestamp"),
                state=edmc_state,
                entry=entry,
            )
        elif event == "MaterialCollected" and self._state.is_mining:
            self._register_material_collected(entry)
        elif event == "LoadGame":
            self._handle_ship_update(
                entry,
                edmc_state,
                context="LoadGame detected",
                event_type=event,
                event_time=event_time,
            )
        elif event == "Loadout":
            message = f"Journal Loadout received: {entry}"
            _log.debug(message)
            if _plugin_log is not _log:
                _plugin_log.debug(message)
            self._handle_ship_update(
                entry,
                edmc_state,
                context="Loadout detected",
                event_type=event,
                event_time=event_time,
            )
        elif event == "ShipyardSwap":
            message = f"Journal ShipyardSwap received: {entry}"
            _log.debug(message)
            if _plugin_log is not _log:
                _plugin_log.debug(message)
            self._handle_ship_update(
                entry,
                edmc_state,
                context="Ship swap detected",
                event_type=event,
                event_time=event_time,
            )

        system_name = self._detect_current_system(entry)
        if system_name:
            self._set_current_system(system_name)

        if isinstance(shared_state, dict):
            shared_state.update(
                {
                    "edmc_mining_active": self._state.is_mining,
                    "edmc_mining_start": self._state.mining_start.isoformat() if self._state.mining_start else None,
                    "edmc_mining_prospected": self._state.prospected_count,
                    "edmc_mining_already_mined": self._state.already_mined_count,
                    "edmc_mining_cargo": dict(self._state.cargo_additions),
                    "edmc_mining_cargo_totals": dict(self._state.cargo_totals),
                    "edmc_mining_limpets": self._state.limpets_remaining,
                    "edmc_mining_collection_drones": self._state.collection_drones_launched,
                    "edmc_mining_prospect_histogram": self._serialize_histogram(),
                    "edmc_mining_prospect_duplicates": self._state.duplicate_prospected,
                    "edmc_mining_histogram_bin": self._state.histogram_bin_size,
                    "edmc_mining_limpets_abandoned": self._state.abandoned_limpets,
                    "edmc_mining_prospect_content": dict(self._state.prospect_content_counts),
                    "edmc_mining_materials_collected": dict(self._state.materials_collected),
                    "edmc_mining_cargo_tph": self._serialize_tph(),
                    "edmc_mining_total_tph": self._compute_total_tph(),
                    "edmc_mining_prospectors_launched": self._state.prospector_launched_count,
                    "edmc_mining_prospectors_lost": max(0, self._state.prospector_launched_count - self._state.prospected_count),
                }
            )

        self._refresh_ui()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _process_launch_drone(self, entry: dict, edmc_state: Optional[dict]) -> None:
        drone_type = entry.get("Type")
        if not isinstance(drone_type, str):
            self._state.last_event_was_drone_launch = False
            return

        dtype = drone_type.lower()
        if dtype == "prospector":
            if not self._state.is_mining:
                self._update_mining_state(
                    True,
                    "Prospector drone launched",
                    entry.get("timestamp"),
                    state=edmc_state,
                    entry=entry,
                )
            self._state.prospector_launched_count += 1
        elif dtype == "collection" and self._state.is_mining:
            self._state.collection_drones_launched += 1

        self._state.last_event_was_drone_launch = True
        self._refresh_ui()
        self._emit_mining_activity(f"LaunchDrone:{dtype}")

    def _register_prospected_asteroid(self, entry: dict) -> None:
        key = self._make_prospect_key(entry)
        if key is None:
            _log.debug("Prospected asteroid entry missing key data: %s", entry)
            return

        if key in self._state.prospected_seen:
            self._state.duplicate_prospected += 1
            _log.debug("Duplicate prospected asteroid detected; ignoring for stats")
            return

        self._state.prospected_seen.add(key)
        self._state.prospected_count += 1

        content_level = self._extract_content_level(entry)
        if content_level:
            self._state.prospect_content_counts[content_level] += 1

        remaining = entry.get("Remaining")
        try:
            remaining_value = float(remaining)
        except (TypeError, ValueError):
            remaining_value = None

        if remaining_value is not None and remaining_value < 100:
            self._state.already_mined_count += 1

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
                self._state.prospected_samples.setdefault(normalized, []).append(proportion)

        recompute_histograms(self._state)
        self._emit_mining_activity("ProspectedAsteroid")

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
        self._state.materials_collected[normalized] += quantity

    def _handle_ship_update(
        self,
        entry: Optional[dict],
        shared_state: Optional[dict],
        *,
        context: str,
        event_type: Optional[str],
        event_time: datetime,
    ) -> None:
        ship_display: Optional[str]
        ship_source: Optional[str]
        capacity_value: Optional[int]
        capacity_source: Optional[str]

        key = self._make_ship_key(entry, shared_state)

        if event_type == "ShipyardSwap" and key:
            ship_display, ship_source, _, _ = self._extract_ship_and_capacity(entry, None)

            if not ship_display and isinstance(entry, dict):
                raw_localised = entry.get("ShipType_Localised")
                if isinstance(raw_localised, str) and raw_localised.strip():
                    ship_display = raw_localised.strip()
                    ship_source = "journal"
                else:
                    raw_type = entry.get("ShipType")
                    if isinstance(raw_type, str) and raw_type.strip():
                        ship_display = raw_type.strip()
                        ship_source = "journal"

            self._apply_ship_state(
                ship_display,
                ship_source,
                None,
                None,
                ship_key=key,
                context=context,
                entry=entry,
                shared_state=shared_state,
                emit_log=False,
            )

            ship_summary = ship_display or "Unknown ship"
            _plugin_log.debug(
                "Ship swap initiated: ship=%s, cargo_capacity=unknown (awaiting loadout)",
                ship_summary,
            )

            self._state.cargo_capacity = None
            self._state.cargo_capacity_is_inferred = False

            self._pending_ship_updates[key] = PendingShipUpdate(
                key=key,
                context=context,
                ship_display=ship_display,
                ship_source=ship_source,
                capacity_value=None,
                capacity_source=None,
                initiated_at=event_time,
                entry=entry,
                shared_state=shared_state,
            )
            _log.debug(
                "Queued ship update for %s (%s); awaiting Loadout",
                key,
                context,
            )
            self._schedule_pending_timeout()
            return

        ship_display, ship_source, capacity_value, capacity_source = self._extract_ship_and_capacity(entry, shared_state)

        if event_type == "Loadout" and key:
            pending = self._pending_ship_updates.pop(key, None)
            if pending:
                elapsed = (event_time - pending.initiated_at).total_seconds()
                _log.debug(
                    "Loadout received for %s after %.2fs",
                    key,
                    max(0.0, elapsed),
                )
                if not ship_display:
                    ship_display = pending.ship_display
                    ship_source = pending.ship_source
            self._apply_ship_state(
                ship_display,
                ship_source,
                capacity_value,
                capacity_source,
                ship_key=key,
                context=context,
                entry=entry,
                shared_state=shared_state,
                emit_log=True,
            )
            if self._pending_ship_updates:
                self._schedule_pending_timeout()
            else:
                self._cancel_pending_timeout()
            return

        awaiting_initial_loadout = False
        if event_type == "InitialState" and key:
            if capacity_value is None:
                self._pending_ship_updates[key] = PendingShipUpdate(
                    key=key,
                    context=context,
                    ship_display=ship_display,
                    ship_source=ship_source,
                    capacity_value=None,
                    capacity_source=None,
                    initiated_at=event_time,
                    entry=entry,
                    shared_state=shared_state,
                )
                _log.debug("Initial state queued for %s; awaiting Loadout", key)
                awaiting_initial_loadout = True
            else:
                self._pending_ship_updates.pop(key, None)
                self._cancel_pending_timeout()

        self._apply_ship_state(
            ship_display,
            ship_source,
            capacity_value,
            capacity_source,
            ship_key=key,
            context=context,
            entry=entry,
            shared_state=shared_state,
            emit_log=True,
        )
        if awaiting_initial_loadout:
            self._schedule_pending_timeout()

    def _make_ship_key(self, entry: Optional[dict], shared_state: Optional[dict]) -> Optional[str]:
        ship_id: Optional[int] = None
        if isinstance(entry, dict):
            ship_id = entry.get("ShipID")
        if ship_id is None and isinstance(shared_state, dict):
            ship_id = shared_state.get("ShipID")
        if isinstance(ship_id, int):
            return f"id:{ship_id}"

        ship_type: Optional[str] = None
        if isinstance(entry, dict):
            for key in ("Ship", "ShipType", "ShipType_Localised"):
                value = entry.get(key)
                if isinstance(value, str) and value.strip():
                    ship_type = value.strip().lower()
                    break
        if ship_type is None and isinstance(shared_state, dict):
            value = shared_state.get("Ship") or shared_state.get("ShipType")
            if isinstance(value, str) and value.strip():
                ship_type = value.strip().lower()
        if ship_type is None:
            return None
        return f"type:{ship_type}"

    def _schedule_pending_timeout(self) -> None:
        if not self._pending_ship_updates:
            self._cancel_pending_timeout()
            return
        duration = _PENDING_SHIP_UPDATE_TIMEOUT.total_seconds()
        timer = self._pending_timeout_timer
        if timer is not None:
            timer.cancel()
        timer = threading.Timer(duration, self._pending_timeout_tick)
        timer.daemon = True
        timer.start()
        self._pending_timeout_timer = timer

    def _cancel_pending_timeout(self) -> None:
        timer = self._pending_timeout_timer
        if timer is not None:
            timer.cancel()
            self._pending_timeout_timer = None

    def _pending_timeout_tick(self) -> None:
        current_time = datetime.now(timezone.utc)
        self._flush_expired_ship_updates(current_time)
        if self._pending_ship_updates:
            self._schedule_pending_timeout()
        else:
            self._cancel_pending_timeout()

    def _flush_expired_ship_updates(self, current_time: datetime) -> None:
        expired: list[str] = []
        for key, pending in list(self._pending_ship_updates.items()):
            if current_time - pending.initiated_at >= _PENDING_SHIP_UPDATE_TIMEOUT:
                elapsed = (current_time - pending.initiated_at).total_seconds()
                _log.debug(
                    "Ship update for %s timed out after %.2fs; emitting pending data",
                    key,
                    max(0.0, elapsed),
                )
                ship_summary = pending.ship_display or "Unknown ship"
                self._state.current_ship = pending.ship_display
                self._state.current_ship_key = key
                self._state.cargo_capacity = pending.capacity_value
                self._state.cargo_capacity_is_inferred = False
                _plugin_log.debug(
                    "Ship swap timeout: ship=%s, cargo_capacity=unknown (no loadout received)",
                    ship_summary,
                )
                if _plugin_log is not _log:
                    _log.debug(
                        "Ship swap timeout for %s (no loadout received)",
                        key,
                    )
                self._activate_inferred_capacity(
                    key,
                    reason=f"timeout ({pending.context})",
                    force=True,
                )
                expired.append(key)
        for key in expired:
            self._pending_ship_updates.pop(key, None)
        if not self._pending_ship_updates:
            self._cancel_pending_timeout()

    def _apply_ship_state(
        self,
        ship_display: Optional[str],
        ship_source: Optional[str],
        capacity_value: Optional[int],
        capacity_source: Optional[str],
        ship_key: Optional[str],
        *,
        context: str,
        entry: Optional[dict],
        shared_state: Optional[dict],
        emit_log: bool,
    ) -> Tuple[str, str]:
        ship_before = self._state.current_ship
        capacity_before = self._state.cargo_capacity
        if ship_key is not None:
            self._state.current_ship_key = ship_key

        normalized_before = ship_before.lower() if isinstance(ship_before, str) else None
        normalized_incoming = ship_display.lower() if isinstance(ship_display, str) else None

        ship_changed = False
        if ship_display:
            if (
                ship_source != "shared_state"
                or self._state.current_ship is None
                or normalized_before != normalized_incoming
            ):
                ship_changed = normalized_before != normalized_incoming
                self._state.current_ship = ship_display
        else:
            if self._state.current_ship is not None:
                ship_changed = True
                self._state.current_ship = None

        if capacity_value is not None:
            should_apply_capacity = (
                capacity_source != "shared_state"
                or self._state.cargo_capacity is None
                or ship_changed
            )
            inferred_reason = f"{context} ({capacity_source or 'unknown'})"
            self._update_inferred_capacity(
                self._state.current_ship_key,
                capacity_value,
                reason=inferred_reason,
                activate=False,
            )
            if should_apply_capacity:
                self._state.cargo_capacity = capacity_value
                self._state.cargo_capacity_is_inferred = False
        elif ship_changed:
            self._state.cargo_capacity = None
            self._state.cargo_capacity_is_inferred = False

        ship_summary = self._state.current_ship or "Unknown ship (no data provided)"
        if capacity_value is not None and (
            capacity_source != "shared_state"
            or capacity_before is None
            or ship_changed
        ):
            capacity_origin = capacity_source or "unknown"
            capacity_summary = f"{self._state.cargo_capacity}t (source={capacity_origin})"
        elif self._state.cargo_capacity is not None:
            if self._state.cargo_capacity_is_inferred:
                capacity_summary = f"({self._state.cargo_capacity}t inferred)"
            else:
                capacity_summary = f"{self._state.cargo_capacity}t (existing)"
        else:
            capacity_origin = capacity_source or ("cleared" if ship_changed else "not provided")
            capacity_summary = f"unknown (capacity {capacity_origin})"

        if emit_log:
            _plugin_log.info(
                "%s: ship=%s, cargo_capacity=%s",
                context,
                ship_summary,
                capacity_summary,
            )
        if _plugin_log is not _log:
            _log.debug(
                "%s details: ship=%s ship_source=%s capacity=%s capacity_source=%s entry=%s shared_state=%s",
                context,
                ship_display,
                ship_source,
                capacity_value,
                capacity_source,
                entry,
                shared_state,
            )

        return ship_summary, capacity_summary

    def _extract_ship_and_capacity(
        self,
        entry: Optional[dict],
        shared_state: Optional[dict],
    ) -> Tuple[Optional[str], Optional[str], Optional[int], Optional[str]]:
        capacity_value: Optional[int] = None
        capacity_source: Optional[str] = None

        def coerce_capacity(source: Optional[dict], label: str) -> None:
            nonlocal capacity_value, capacity_source
            if capacity_value is not None or not isinstance(source, dict):
                return
            try:
                raw = source.get("CargoCapacity")
            except Exception:
                raw = None
            if isinstance(raw, (int, float)) and raw >= 0:
                capacity_value = int(raw)
                capacity_source = label

        coerce_capacity(entry, "journal")
        coerce_capacity(shared_state, "shared_state")

        entry_state: dict[str, Any] = {}
        if isinstance(entry, dict):
            for key in (
                "ShipName",
                "ShipLocalised",
                "Ship_Localised",
                "Ship",
                "ShipType",
                "ShipType_Localised",
            ):
                value = entry.get(key)
                if isinstance(value, str) and value.strip():
                    entry_state[key] = value.strip()

        shared_state_normalized: dict[str, Any] = {}
        if isinstance(shared_state, dict):
            for key in (
                "ShipName",
                "ShipLocalised",
                "Ship_Localised",
                "Ship",
                "ShipType",
                "ShipType_Localised",
            ):
                value = shared_state.get(key) if isinstance(shared_state, dict) else None
                if isinstance(value, str) and value.strip():
                    shared_state_normalized[key] = value.strip()

        ship_display = None
        ship_source = None
        if entry_state:
            ship_display = self._resolve_ship_name(entry_state)
            if ship_display:
                ship_source = "journal"
        if ship_display is None and shared_state_normalized:
            ship_display = self._resolve_ship_name(shared_state_normalized)
            if ship_display:
                ship_source = "shared_state"
        if ship_display is None and isinstance(entry, dict):
            for key in ("ShipType_Localised", "ShipType", "Ship"):
                value = entry.get(key)
                if isinstance(value, str) and value.strip():
                    ship_display = value.strip()
                    ship_source = "fallback"
                    break

        return ship_display, ship_source, capacity_value, capacity_source

    def _process_cargo(self, entry: dict, edmc_state: Optional[dict], *, is_mining: bool) -> None:
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

        previous_limpets = self._state.limpets_remaining
        if limpets is not None:
            if not self._state.limpets_start_initialized:
                self._state.limpets_start = limpets
                self._state.limpets_start_initialized = True
            self._state.limpets_remaining = limpets

        total_cargo = sum(count for commodity, count in cargo_counts.items() if commodity != "drones")
        self._state.current_cargo_tonnage = total_cargo

        capacity_value: Optional[int] = None
        capacity_source: Optional[str] = None
        if edmc_state:
            raw_capacity = edmc_state.get("CargoCapacity")
            if isinstance(raw_capacity, (int, float)) and raw_capacity >= 0:
                capacity_value = int(raw_capacity)
                capacity_source = "shared_state"
        if capacity_value is None:
            raw_capacity = entry.get("Capacity")
            if isinstance(raw_capacity, (int, float)) and raw_capacity >= 0:
                capacity_value = int(raw_capacity)
                capacity_source = "journal"

        ship_key = self._state.current_ship_key
        if ship_key is None:
            ship_key = self._make_ship_key(entry, edmc_state)
            if ship_key is not None:
                self._state.current_ship_key = ship_key
        if capacity_value is not None and capacity_value > 0:
            self._update_inferred_capacity(
                ship_key,
                capacity_value,
                reason=f"Cargo event ({capacity_source or 'unknown'})",
                activate=False,
            )
            should_apply = (
                capacity_source != "shared_state"
                or self._state.cargo_capacity is None
                or self._state.cargo_capacity_is_inferred
            )
            if should_apply:
                self._state.cargo_capacity = capacity_value
                self._state.cargo_capacity_is_inferred = False
        else:
            limpets_onboard = (
                limpets
                if limpets is not None
                else (self._state.limpets_remaining if self._state.limpets_remaining is not None else 0)
            )
            observed_total = max(0, total_cargo) + max(0, limpets_onboard)
            if observed_total > 0:
                self._update_inferred_capacity(
                    ship_key,
                    observed_total,
                    reason=f"Cargo event observed cargo ({observed_total}t)",
                    activate=True,
                )
            else:
                self._activate_inferred_capacity(
                    ship_key,
                    reason="Cargo event (no capacity data)",
                )

        if _log.isEnabledFor(logging.DEBUG):
            _log.debug(
                "Cargo update: total=%st capacity=%s (source=%s)",
                self._state.current_cargo_tonnage,
                self._state.cargo_capacity,
                "inferred"
                if self._state.cargo_capacity_is_inferred
                else (
                    "shared"
                    if edmc_state and edmc_state.get("CargoCapacity") is not None
                    else capacity_source or "journal"
                ),
            )

        if not is_mining:
            self._state.last_cargo_counts = dict(cargo_counts)
            return

        if not self._state.last_cargo_counts:
            self._state.last_cargo_counts = dict(cargo_counts)
            return

        additions_made = False
        for name, count in cargo_counts.items():
            if name == "drones":
                continue
            prev = self._state.last_cargo_counts.get(name, 0)
            increment = count - prev
            if increment > 0:
                additions_made = True
                new_total = self._state.cargo_additions.get(name, 0) + increment
                self._state.cargo_additions[name] = new_total
                self._state.cargo_totals[name] = new_total
                self._state.harvested_commodities.add(name)
                if name not in self._state.commodity_start_times:
                    timestamp = self._parse_timestamp(entry.get("timestamp"))
                    self._state.commodity_start_times[name] = timestamp or datetime.now(timezone.utc)

        self._state.cargo_additions = {k: v for k, v in self._state.cargo_additions.items() if v > 0}
        self._state.cargo_totals = dict(self._state.cargo_additions)

        if self._state.limpets_start is not None and self._state.limpets_remaining is not None:
            launched = self._state.prospector_launched_count + self._state.collection_drones_launched - 1
            abandoned = self._state.limpets_start - self._state.limpets_remaining - launched
            self._state.abandoned_limpets = max(0, abandoned)

        if additions_made or (
            limpets is not None and previous_limpets is not None and limpets != previous_limpets
        ):
            self._refresh_ui()

        self._state.last_cargo_counts = dict(cargo_counts)
        self._emit_mining_activity("Cargo")

    # ------------------------------------------------------------------
    # Inferred capacity helpers
    # ------------------------------------------------------------------
    def _update_inferred_capacity(
        self,
        ship_key: Optional[str],
        candidate: Optional[int],
        *,
        reason: str,
        activate: bool,
    ) -> None:
        if ship_key is None or candidate is None:
            return
        try:
            capacity = int(candidate)
        except (TypeError, ValueError):
            return
        if capacity <= 0:
            return

        prior = self._state.inferred_capacity_map.get(ship_key)
        changed = prior is None or capacity > prior
        if changed:
            self._state.inferred_capacity_map[ship_key] = capacity
            _plugin_log.debug(
                "Inferred cargo capacity updated: ship_key=%s capacity=%st (reason=%s)",
                ship_key,
                capacity,
                reason,
            )
            if _plugin_log is not _log:
                _log.debug(
                    "Inferred cargo capacity updated: ship_key=%s capacity=%s reason=%s prior=%s",
                    ship_key,
                    capacity,
                    reason,
                    prior,
                )
            try:
                self._persist_inferred_capacities()
            except Exception:
                _log.exception("Unable to persist inferred cargo capacities")

        if activate:
            self._activate_inferred_capacity(ship_key, reason, force=changed)

    def _activate_inferred_capacity(
        self,
        ship_key: Optional[str],
        reason: str,
        *,
        force: bool = False,
    ) -> None:
        if ship_key is None:
            return
        _plugin_log.debug(
            "Inference requested: ship_key=%s (reason=%s)",
            ship_key,
            reason,
        )
        if _plugin_log is not _log:
            _log.debug(
                "Inference requested: ship_key=%s reason=%s",
                ship_key,
                reason,
            )
        inferred = self._state.inferred_capacity_map.get(ship_key)
        if inferred is None or inferred <= 0:
            _plugin_log.debug(
                "No stored inferred cargo capacity for ship_key=%s; skipping",
                ship_key,
            )
            if _plugin_log is not _log:
                _log.debug(
                    "No stored inferred cargo capacity for ship_key=%s",
                    ship_key,
                )
            return
        if not self._state.cargo_capacity_is_inferred and self._state.cargo_capacity is not None:
            _plugin_log.debug(
                "Actual cargo capacity present; inference skipped for ship_key=%s",
                ship_key,
            )
            if _plugin_log is not _log:
                _log.debug(
                    "Actual cargo capacity present; inference skipped for ship_key=%s",
                    ship_key,
                )
            return

        already_active = (
            self._state.cargo_capacity_is_inferred
            and self._state.cargo_capacity == inferred
        )
        if already_active and not force:
            return

        _plugin_log.debug(
            "Inferring cargo capacity for ship_key=%s (reason=%s)",
            ship_key,
            reason,
        )
        if _plugin_log is not _log:
            _log.debug(
                "Inferring cargo capacity for ship_key=%s reason=%s",
                ship_key,
                reason,
            )

        self._state.cargo_capacity = inferred
        self._state.cargo_capacity_is_inferred = True
        _plugin_log.debug(
            "Applied inferred cargo capacity: ship_key=%s capacity=%st (reason=%s)",
            ship_key,
            inferred,
            reason,
        )
        if _plugin_log is not _log:
            _log.debug(
                "Applied inferred cargo capacity: ship_key=%s capacity=%s reason=%s",
                ship_key,
                inferred,
                reason,
            )
        self._refresh_ui()

    def _emit_mining_activity(self, reason: str) -> None:
        callback = getattr(self, "_notify_mining_activity", None)
        if not callback:
            return
        try:
            callback(reason)
        except Exception:
            _log.exception("Failed to notify mining activity (%s)", reason)

    # ------------------------------------------------------------------
    # Mining session helpers
    # ------------------------------------------------------------------
    def _update_mining_state(
        self,
        active: bool,
        reason: str,
        timestamp: Optional[str],
        state: Optional[dict] = None,
        entry: Optional[dict] = None,
    ) -> None:
        if self._state.is_mining == active:
            return

        if active:
            ship_display, ship_source, capacity_value, capacity_source = self._extract_ship_and_capacity(entry, state)
            existing_ship = self._state.current_ship
            existing_capacity = self._state.cargo_capacity
            existing_ship_key = self._state.current_ship_key
            existing_capacity_inferred = self._state.cargo_capacity_is_inferred
            ship_key = self._make_ship_key(entry, state)

            normalized_existing = existing_ship.lower() if isinstance(existing_ship, str) else None
            normalized_incoming = ship_display.lower() if isinstance(ship_display, str) else None
            ship_changed = False

            ship_to_use = existing_ship
            if ship_display:
                if (
                    ship_source != "shared_state"
                    or existing_ship is None
                    or normalized_existing != normalized_incoming
                ):
                    ship_changed = normalized_existing != normalized_incoming
                    ship_to_use = ship_display
            capacity_to_use = existing_capacity
            if capacity_value is not None:
                if (
                    capacity_source != "shared_state"
                    or existing_capacity is None
                    or ship_changed
                ):
                    capacity_to_use = capacity_value
            elif ship_changed:
                capacity_to_use = None

            start_time = self._parse_timestamp(timestamp) or datetime.now(timezone.utc)
            reset_mining_state(self._state)
            self._state.is_mining = True
            self._state.mining_start = start_time
            self._state.mining_end = None
            self._state.mining_location = self._detect_current_location(state or entry)
            system_name = self._detect_current_system(state or entry)
            if system_name:
                self._set_current_system(system_name)

            self._state.current_ship = ship_to_use
            self._state.current_ship_key = ship_key or existing_ship_key
            self._state.cargo_capacity = capacity_to_use
            if capacity_to_use is not None:
                if capacity_value is not None and capacity_to_use > 0:
                    self._state.cargo_capacity_is_inferred = False
                    self._update_inferred_capacity(
                        self._state.current_ship_key,
                        capacity_to_use,
                        reason="Mining start provided capacity",
                        activate=False,
                    )
                else:
                    self._state.cargo_capacity_is_inferred = bool(existing_capacity_inferred)
                    if existing_capacity_inferred:
                        self._update_inferred_capacity(
                            self._state.current_ship_key,
                            capacity_to_use,
                            reason="Mining start inferred capacity",
                            activate=False,
                        )
            else:
                self._state.cargo_capacity_is_inferred = False

            _plugin_log.info("Mining start event triggered (reason=%s)", reason)
            if _plugin_log is not _log:
                _log.debug(
                    "Mining start event logged via plugin logger (reason=%s, entry=%s, shared_state=%s)",
                    reason,
                    entry,
                    state,
                )

            ship_summary = ship_to_use or "Unknown ship (ship data unavailable)"
            if capacity_to_use is not None:
                if capacity_value is not None and (
                    capacity_source != "shared_state" or existing_capacity is None or ship_changed
                ):
                    capacity_origin = capacity_source or "unknown"
                elif existing_capacity is not None:
                    capacity_origin = "previous"
                else:
                    capacity_origin = "unknown"
                capacity_summary = f"{capacity_to_use}t (source={capacity_origin})"
            else:
                capacity_origin = capacity_source or ("cleared" if ship_changed else "not provided")
                capacity_summary = f"unknown (capacity {capacity_origin})"

            _plugin_log.info(
                "Mining started: ship=%s, cargo_capacity=%s",
                ship_summary,
                capacity_summary,
            )
            if _plugin_log is not _log:
                _log.debug(
                    "Mining started log dispatched: ship=%s, cargo_capacity=%s",
                    ship_summary,
                    capacity_summary,
                )

            self._on_session_start()
            if self._state.mining_start:
                _plugin_log.info(
                    "Mining started at %s (location=%s) - reason: %s",
                    self._state.mining_start.isoformat(),
                    self._state.mining_location,
                    reason,
                )
                if _plugin_log is not _log:
                    _log.debug(
                        "Mining start details logged: time=%s location=%s reason=%s",
                        self._state.mining_start.isoformat(),
                        self._state.mining_location,
                        reason,
                    )
        else:
            self._state.is_mining = False
            self._state.mining_end = self._parse_timestamp(timestamp) or datetime.now(timezone.utc)
            system_name = self._detect_current_system(state)
            if system_name:
                self._set_current_system(system_name)
            self._on_session_end()

        _log.info("Mining state changed to %s (%s)", "active" if active else "inactive", reason)

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _set_current_system(self, value: Optional[str]) -> None:
        normalized = str(value).strip() if value else None
        if normalized == "":
            normalized = None
        self._state.current_system = normalized

    def _detect_current_location(self, state: Optional[dict]) -> Optional[str]:
        if not state:
            return None
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
        return None

    @staticmethod
    def _detect_current_system(state: Optional[dict]) -> Optional[str]:
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

    def _resolve_ship_name(self, state: Optional[dict]) -> Optional[str]:
        if not state:
            return None
        try:
            ship_name = state.get("ShipName")
            if isinstance(ship_name, str) and ship_name.strip():
                return ship_name.strip()
        except Exception:
            pass
        try:
            ship_localised = state.get("ShipLocalised")
            if isinstance(ship_localised, str) and ship_localised.strip():
                return ship_localised.strip()
        except Exception:
            pass
        ship_type = None
        for key in ("Ship", "ShipType"):
            try:
                value = state.get(key)
            except Exception:
                value = None
            if isinstance(value, str) and value.strip():
                ship_type = value.strip()
                break
        if not ship_type:
            return None
        lookup_key = ship_type.lower()
        mapped = ship_name_map.get(lookup_key) or ship_name_map.get(ship_type)
        return mapped or ship_type

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
        except Exception:
            _log.debug("Unable to parse timestamp: %s", value)
            return None

    @staticmethod
    def _ensure_aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

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
        body = entry.get("Body")
        body_component = str(body) if isinstance(body, str) else ""
        content = str(entry.get("Content", ""))
        content_localised = str(entry.get("Content_Localised", ""))
        return ("|".join(filter(None, (body_component, content, content_localised))), tuple(items))

    @staticmethod
    def _extract_content_level(entry: dict) -> Optional[str]:
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

    def _serialize_histogram(self) -> dict[str, dict[str, int]]:
        serialized: dict[str, dict[str, int]] = {}
        harvested = self._state.harvested_commodities
        if not harvested:
            return serialized
        for material, counter in self._state.prospected_histogram.items():
            if material not in harvested or not counter:
                continue
            size = max(1, self._state.histogram_bin_size)
            labels = {
                self._format_bin_label(bin_index, size): count
                for bin_index, count in sorted(counter.items())
                if count > 0
            }
            serialized[self._format_cargo_name(material)] = labels
        return serialized

    def _serialize_tph(self) -> dict[str, float]:
        data: dict[str, float] = {}
        for commodity in self._state.cargo_additions:
            rate = self._compute_tph(commodity)
            if rate is None:
                continue
            data[self._format_cargo_name(commodity)] = round(rate, 3)
        return data

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

    @staticmethod
    def _format_cargo_name(name: str) -> str:
        return name.replace("_", " ").title()

    @staticmethod
    def _format_bin_label(bin_index: int, size: int) -> str:
        start = bin_index * size
        end = min(start + size, 100)
        return f"{int(start)}-{int(end)}%"
