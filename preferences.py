"""Preference loading and persistence for the EDMC Mining Analytics plugin."""

from __future__ import annotations

import json
import logging
from typing import Dict, Optional

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
