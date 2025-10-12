"""Preference loading and persistence for the EDMC Mining Analytics plugin."""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional, Sequence

try:
    from config import config  # type: ignore[import]
except ImportError:  # pragma: no cover - only available inside EDMC
    config = None  # type: ignore[assignment]

from state import MiningState
from logging_utils import get_logger


_log = get_logger("preferences")


def clamp_bin_size(value: int) -> int:
    try:
        size = int(value)
    except (TypeError, ValueError):
        size = 10
    return max(1, min(100, size))


def clamp_rate_interval(value: int) -> int:
    try:
        interval = int(value)
    except (TypeError, ValueError):
        interval = 30
    return max(5, min(3600, interval))


def clamp_session_retention(value: int) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = 30
    return max(1, min(500, limit))


def clamp_positive_int(value: int, default: int, maximum: int = 10_000) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    return max(1, min(maximum, result))


def clamp_overlay_coordinate(value: int, default: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    return max(0, min(4000, result))


def clamp_overlay_interval(value: int, default: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    return max(200, min(60_000, result))


class PreferencesManager:
    """Loads and persists user preferences via EDMC's config object."""

    def load(self, state: MiningState) -> None:
        if config is None:
            state.histogram_bin_size = 10
            state.rate_interval_seconds = 30
            state.inara_settings.search_mode = 1
            state.inara_settings.include_carriers = True
            state.inara_settings.include_surface = True
            state.inferred_capacity_map = {}
            state.auto_unpause_on_event = True
            state.session_logging_enabled = False
            state.session_log_retention = 30
            state.discord_webhook_url = ""
            state.send_summary_to_discord = False
            state.send_reset_summary = False
            state.discord_image_url = ""
            state.refinement_lookback_seconds = 10
            state.rpm_threshold_red = 1
            state.rpm_threshold_yellow = 20
            state.rpm_threshold_green = 40
            state.overlay_enabled = False
            state.overlay_anchor_x = 40
            state.overlay_anchor_y = 120
            state.overlay_refresh_interval_ms = 1000
            return

        state.histogram_bin_size = clamp_bin_size(self._get_int("edmc_mining_histogram_bin", 10))
        state.rate_interval_seconds = clamp_rate_interval(self._get_int("edmc_mining_rate_interval", 30))

        search_mode = self._get_int("edmc_mining_inara_search_mode", 1)
        state.inara_settings.search_mode = 3 if search_mode == 3 else 1

        include_carriers = self._get_int("edmc_mining_inara_include_carriers", 1)
        state.inara_settings.include_carriers = bool(include_carriers)

        include_surface = self._get_int("edmc_mining_inara_include_surface", 1)
        state.inara_settings.include_surface = bool(include_surface)

        state.inferred_capacity_map = self._load_inferred_capacities()
        state.auto_unpause_on_event = bool(self._get_int("edmc_mining_auto_unpause", 1))
        state.session_logging_enabled = bool(self._get_int("edmc_mining_session_logging", 0))
        state.session_log_retention = clamp_session_retention(
            self._get_int("edmc_mining_session_retention", 30)
        )
        state.discord_webhook_url = self._get_str("edmc_mining_discord_webhook", "").strip()
        state.send_summary_to_discord = bool(self._get_int("edmc_mining_discord_summary", 0))
        state.send_reset_summary = bool(self._get_int("edmc_mining_discord_reset_summary", 0))
        state.discord_image_url = self._get_str("edmc_mining_discord_image", "").strip()
        state.show_mined_commodities = bool(
            self._get_int("edmc_mining_show_commodities", int(state.show_mined_commodities))
        )
        state.show_materials_collected = bool(
            self._get_int("edmc_mining_show_materials", int(state.show_materials_collected))
        )
        state.warn_on_non_metallic_ring = bool(
            self._get_int(
                "edmc_mining_warn_non_metallic",
                int(state.warn_on_non_metallic_ring),
            )
        )
        state.refinement_lookback_seconds = clamp_positive_int(
            self._get_int("edmc_mining_refinement_window", state.refinement_lookback_seconds),
            state.refinement_lookback_seconds,
            maximum=3600,
        )

        raw_red_threshold = self._get_int("edmc_mining_rpm_red", state.rpm_threshold_red)
        if raw_red_threshold == 10:  # migrate legacy default to the new baseline
            raw_red_threshold = 1
        state.rpm_threshold_red = clamp_positive_int(
            raw_red_threshold,
            1,
            maximum=10_000,
        )
        state.rpm_threshold_yellow = clamp_positive_int(
            self._get_int("edmc_mining_rpm_yellow", state.rpm_threshold_yellow),
            state.rpm_threshold_yellow,
            maximum=10_000,
        )

        raw_green_threshold = self._get_int("edmc_mining_rpm_green", state.rpm_threshold_green)
        if raw_green_threshold == 30:  # migrate legacy default to new baseline
            raw_green_threshold = 40
        state.rpm_threshold_green = clamp_positive_int(
            raw_green_threshold,
            40,
            maximum=10_000,
        )
        state.overlay_enabled = bool(self._get_int("edmc_mining_overlay_enabled", int(state.overlay_enabled)))
        state.overlay_anchor_x = clamp_overlay_coordinate(
            self._get_int("edmc_mining_overlay_anchor_x", state.overlay_anchor_x),
            state.overlay_anchor_x,
        )
        state.overlay_anchor_y = clamp_overlay_coordinate(
            self._get_int("edmc_mining_overlay_anchor_y", state.overlay_anchor_y),
            state.overlay_anchor_y,
        )
        state.overlay_refresh_interval_ms = clamp_overlay_interval(
            self._get_int("edmc_mining_overlay_refresh_ms", state.overlay_refresh_interval_ms),
            state.overlay_refresh_interval_ms,
        )
        state.spansh_last_distance_min = self._get_float("edmc_mining_spansh_distance_min", None)
        state.spansh_last_distance_max = self._get_float("edmc_mining_spansh_distance_max", None)
        state.spansh_last_ring_signals = self._load_string_list("edmc_mining_spansh_ring_signals")
        state.spansh_last_reserve_levels = self._load_string_list("edmc_mining_spansh_reserve_levels")
        state.spansh_last_ring_types = self._load_string_list("edmc_mining_spansh_ring_types")

    def save(self, state: MiningState) -> None:
        if config is None:
            return

        try:
            config.set("edmc_mining_histogram_bin", state.histogram_bin_size)
        except Exception:
            _log.exception("Failed to persist histogram bin size preference")

        try:
            config.set("edmc_mining_rate_interval", state.rate_interval_seconds)
        except Exception:
            _log.exception("Failed to persist rate update interval")

        try:
            config.set("edmc_mining_inara_search_mode", state.inara_settings.search_mode)
        except Exception:
            _log.exception("Failed to persist Inara search mode preference")

        try:
            config.set("edmc_mining_inara_include_carriers", int(state.inara_settings.include_carriers))
        except Exception:
            _log.exception("Failed to persist Inara carrier preference")

        try:
            config.set("edmc_mining_inara_include_surface", int(state.inara_settings.include_surface))
        except Exception:
            _log.exception("Failed to persist Inara surface preference")

        self.save_inferred_capacities(state)

        try:
            config.set("edmc_mining_auto_unpause", int(state.auto_unpause_on_event))
        except Exception:
            _log.exception("Failed to persist auto-unpause preference")

        try:
            config.set("edmc_mining_session_logging", int(state.session_logging_enabled))
        except Exception:
            _log.exception("Failed to persist session logging preference")

        try:
            config.set(
                "edmc_mining_session_retention",
                clamp_session_retention(state.session_log_retention),
            )
        except Exception:
            _log.exception("Failed to persist session log retention preference")

        try:
            config.set("edmc_mining_discord_webhook", state.discord_webhook_url or "")
        except Exception:
            _log.exception("Failed to persist Discord webhook")

        try:
            config.set("edmc_mining_discord_summary", int(state.send_summary_to_discord))
        except Exception:
            _log.exception("Failed to persist Discord summary preference")

        try:
            config.set("edmc_mining_discord_reset_summary", int(state.send_reset_summary))
        except Exception:
            _log.exception("Failed to persist Discord reset summary preference")

        try:
            config.set("edmc_mining_discord_image", state.discord_image_url or "")
        except Exception:
            _log.exception("Failed to persist Discord image URL")

        try:
            config.set("edmc_mining_show_commodities", int(state.show_mined_commodities))
        except Exception:
            _log.exception("Failed to persist commodities visibility preference")

        try:
            config.set("edmc_mining_show_materials", int(state.show_materials_collected))
        except Exception:
            _log.exception("Failed to persist materials visibility preference")

        try:
            config.set("edmc_mining_warn_non_metallic", int(state.warn_on_non_metallic_ring))
        except Exception:
            _log.exception("Failed to persist non-metallic warning preference")

        try:
            config.set(
                "edmc_mining_refinement_window",
                clamp_positive_int(state.refinement_lookback_seconds, 10, maximum=3600),
            )
        except Exception:
            _log.exception("Failed to persist refinement lookback preference")

        try:
            config.set(
                "edmc_mining_rpm_red",
                clamp_positive_int(state.rpm_threshold_red, 1),
            )
        except Exception:
            _log.exception("Failed to persist RPM red threshold")

        try:
            config.set(
                "edmc_mining_rpm_yellow",
                clamp_positive_int(state.rpm_threshold_yellow, 20),
            )
        except Exception:
            _log.exception("Failed to persist RPM yellow threshold")

        try:
            config.set(
                "edmc_mining_rpm_green",
                clamp_positive_int(state.rpm_threshold_green, 40),
            )
        except Exception:
            _log.exception("Failed to persist RPM green threshold")

        try:
            config.set("edmc_mining_overlay_enabled", int(state.overlay_enabled))
        except Exception:
            _log.exception("Failed to persist overlay enabled preference")

        try:
            config.set(
                "edmc_mining_overlay_anchor_x",
                clamp_overlay_coordinate(state.overlay_anchor_x, state.overlay_anchor_x),
            )
        except Exception:
            _log.exception("Failed to persist overlay anchor X preference")

        try:
            config.set(
                "edmc_mining_overlay_anchor_y",
                clamp_overlay_coordinate(state.overlay_anchor_y, state.overlay_anchor_y),
            )
        except Exception:
            _log.exception("Failed to persist overlay anchor Y preference")

        try:
            config.set(
                "edmc_mining_overlay_refresh_ms",
                clamp_overlay_interval(state.overlay_refresh_interval_ms, state.overlay_refresh_interval_ms),
            )
        except Exception:
            _log.exception("Failed to persist overlay refresh interval preference")

        try:
            value = "" if state.spansh_last_distance_min is None else str(float(state.spansh_last_distance_min))
            config.set("edmc_mining_spansh_distance_min", value)
        except Exception:
            _log.exception("Failed to persist Spansh minimum distance")

        try:
            value = "" if state.spansh_last_distance_max is None else str(float(state.spansh_last_distance_max))
            config.set("edmc_mining_spansh_distance_max", value)
        except Exception:
            _log.exception("Failed to persist Spansh maximum distance")

        if state.spansh_last_ring_signals is not None:
            try:
                payload = json.dumps(self._normalise_string_list(state.spansh_last_ring_signals))
                config.set("edmc_mining_spansh_ring_signals", payload)
            except Exception:
                _log.exception("Failed to persist Spansh ring signals")

        if state.spansh_last_reserve_levels is not None:
            try:
                payload = json.dumps(self._normalise_string_list(state.spansh_last_reserve_levels))
                config.set("edmc_mining_spansh_reserve_levels", payload)
            except Exception:
                _log.exception("Failed to persist Spansh reserve levels")

        if state.spansh_last_ring_types is not None:
            try:
                payload = json.dumps(self._normalise_string_list(state.spansh_last_ring_types))
                config.set("edmc_mining_spansh_ring_types", payload)
            except Exception:
                _log.exception("Failed to persist Spansh ring types")


    @staticmethod
    def _get_int(key: str, default: int) -> int:
        if config is None:
            return default
        try:
            return int(config.get_int(key=key, default=default))  # type: ignore[arg-type]
        except Exception:
            return default

    def _get_str(self, key: str, default: str) -> str:
        if config is None:
            return default
        try:
            raw = config.get_str(key)  # type: ignore[arg-type]
        except Exception:
            raw = None
        if not raw:
            return default
        return str(raw)

    def _get_optional_str(self, key: str) -> Optional[str]:
        if config is None:
            return None
        try:
            raw = config.get_str(key)  # type: ignore[arg-type]
        except Exception:
            return None
        if raw is None:
            return None
        value = str(raw).strip()
        return value or None

    def _get_float(self, key: str, default: Optional[float]) -> Optional[float]:
        text = self._get_optional_str(key)
        if not text:
            return default
        try:
            return float(text)
        except (TypeError, ValueError):
            return default

    def _load_inferred_capacities(self) -> Dict[str, int]:
        payload = self._get_str("edmc_mining_inferred_cargo_map", "{}")
        try:
            data = json.loads(payload)
        except Exception:
            data = {}

        inferred: Dict[str, int] = {}
        if isinstance(data, dict):
            for key, value in data.items():
                if not isinstance(key, str):
                    key = str(key)
                try:
                    capacity = int(value)
                except (TypeError, ValueError):
                    continue
                if capacity > 0:
                    inferred[key] = capacity
        return inferred

    def save_inferred_capacities(self, state: MiningState) -> None:
        if config is None:
            return

        sanitized: Dict[str, int] = {}
        for key, value in state.inferred_capacity_map.items():
            if not key or value is None:
                continue
            try:
                capacity = int(value)
            except (TypeError, ValueError):
                continue
            if capacity > 0:
                sanitized[str(key)] = capacity

        try:
            payload = json.dumps(sanitized, separators=(",", ":"))
        except Exception:
            _log.exception("Failed to encode inferred cargo capacities for persistence")
            return

        try:
            config.set("edmc_mining_inferred_cargo_map", payload)
        except Exception:
            _log.exception("Failed to persist inferred cargo capacities")

    @staticmethod
    def _normalise_string_list(values: Optional[Sequence[str]]) -> List[str]:
        if not values:
            return []
        cleaned: List[str] = []
        for value in values:
            if not value:
                continue
            item = str(value)
            if item not in cleaned:
                cleaned.append(item)
        return cleaned

    def _load_string_list(self, key: str) -> Optional[List[str]]:
        payload = self._get_optional_str(key)
        if payload is None:
            return None
        try:
            data = json.loads(payload)
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        cleaned: List[str] = []
        for item in data:
            if isinstance(item, str) and item and item not in cleaned:
                cleaned.append(item)
        return cleaned

    def reset_inferred_capacities(self, state: MiningState) -> None:
        state.inferred_capacity_map.clear()
        if config is None:
            return
        try:
            config.set("edmc_mining_inferred_cargo_map", "{}")
        except Exception:
            _log.exception("Failed to clear inferred cargo capacities from config")
