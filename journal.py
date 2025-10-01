"""Journal event processing for the EDMC Mining Analytics plugin."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Callable, Optional, Tuple

from state import MiningState, reset_mining_state, recompute_histograms
from logging_utils import get_logger

try:  # pragma: no cover - only available inside EDMC
    from edmc_data import ship_name_map  # type: ignore[import]
except ImportError:  # pragma: no cover - fallback when not running inside EDMC
    ship_name_map = {}


_log = get_logger("journal")


class JournalProcessor:
    """Transforms EDMC journal events into mining analytics state updates."""

    def __init__(
        self,
        state: MiningState,
        refresh_ui: Callable[[], None],
        on_session_start: Callable[[], None],
        on_session_end: Callable[[], None],
    ) -> None:
        self._state = state
        self._refresh_ui = refresh_ui
        self._on_session_start = on_session_start
        self._on_session_end = on_session_end

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def handle_entry(self, entry: dict, shared_state: Optional[dict] = None) -> None:
        if not entry:
            return

        edmc_state = shared_state if isinstance(shared_state, dict) else None

        event = entry.get("event")
        if event == "LaunchDrone":
            self._process_launch_drone(entry, edmc_state)
        elif event == "ProspectedAsteroid" and self._state.is_mining:
            self._register_prospected_asteroid(entry)
        elif event == "Cargo":
            self._process_cargo(entry, edmc_state, is_mining=self._state.is_mining)
        elif event == "SupercruiseEntry" and self._state.is_mining:
            self._update_mining_state(False, "Entered Supercruise", entry.get("timestamp"), state=edmc_state)
        elif event == "MaterialCollected" and self._state.is_mining:
            self._register_material_collected(entry)

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
                self._update_mining_state(True, "Prospector drone launched", entry.get("timestamp"), state=edmc_state)
            self._state.prospector_launched_count += 1
        elif dtype == "collection" and self._state.is_mining:
            self._state.collection_drones_launched += 1

        self._state.last_event_was_drone_launch = True
        self._refresh_ui()

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
        if edmc_state:
            raw_capacity = edmc_state.get("CargoCapacity")
            if isinstance(raw_capacity, (int, float)) and raw_capacity >= 0:
                capacity_value = int(raw_capacity)
        if capacity_value is None:
            raw_capacity = entry.get("Capacity")
            if isinstance(raw_capacity, (int, float)) and raw_capacity >= 0:
                capacity_value = int(raw_capacity)
        if capacity_value is not None:
            self._state.cargo_capacity = capacity_value

        if _log.isEnabledFor(logging.DEBUG):
            _log.debug(
                "Cargo update: total=%st capacity=%s (source=%s)",
                self._state.current_cargo_tonnage,
                self._state.cargo_capacity,
                "shared" if edmc_state and edmc_state.get("CargoCapacity") is not None else "journal",
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

    # ------------------------------------------------------------------
    # Mining session helpers
    # ------------------------------------------------------------------
    def _update_mining_state(
        self,
        active: bool,
        reason: str,
        timestamp: Optional[str],
        state: Optional[dict] = None,
    ) -> None:
        if self._state.is_mining == active:
            return

        if active:
            # Capture capacity and ship info before the reset wipes state
            capacity = None
            capacity_source = "unknown"
            if state:
                try:
                    raw_capacity = state.get("CargoCapacity")
                except Exception:
                    raw_capacity = None
                if isinstance(raw_capacity, (int, float)) and raw_capacity >= 0:
                    capacity = int(raw_capacity)
                    capacity_source = "shared_state"
                    self._state.cargo_capacity = capacity
            ship_display = self._resolve_ship_name(state)
            if ship_display is None and _log.isEnabledFor(logging.DEBUG):
                _log.debug("Mining start: unable to resolve ship name from state=%s", state)
            start_time = self._parse_timestamp(timestamp) or datetime.now(timezone.utc)
            reset_mining_state(self._state)
            self._state.is_mining = True
            self._state.mining_start = start_time
            self._state.mining_end = None
            self._state.mining_location = self._detect_current_location(state)
            system_name = self._detect_current_system(state)
            if system_name:
                self._set_current_system(system_name)
            _log.info("Mining started")
            if _log.isEnabledFor(logging.INFO):
                _log.info(
                    "Mining started in %s (cargo capacity %s)",
                    ship_display or "Unknown ship",
                    f"{capacity}t ({capacity_source})" if capacity is not None else "unknown",
                )
            elif _log.isEnabledFor(logging.DEBUG):
                _log.debug("Mining start: unable to determine cargo capacity (state=%s)", state)
            self._on_session_start()
            if self._state.mining_start:
                _log.info(
                    "Mining started at %s (location=%s) - reason: %s",
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
