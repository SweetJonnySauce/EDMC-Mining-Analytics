"""Preference loading and persistence for the EDMC Mining Analytics plugin."""

from __future__ import annotations

import logging
from typing import Optional

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
            return

        state.histogram_bin_size = clamp_bin_size(self._get_int("edmc_mining_histogram_bin", 10))
        state.rate_interval_seconds = clamp_rate_interval(self._get_int("edmc_mining_rate_interval", 30))

        search_mode = self._get_int("edmc_mining_inara_search_mode", 1)
        state.inara_settings.search_mode = 3 if search_mode == 3 else 1

        include_carriers = self._get_int("edmc_mining_inara_include_carriers", 1)
        state.inara_settings.include_carriers = bool(include_carriers)

        include_surface = self._get_int("edmc_mining_inara_include_surface", 1)
        state.inara_settings.include_surface = bool(include_surface)

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

    @staticmethod
    def _get_int(key: str, default: int) -> int:
        if config is None:
            return default
        try:
            return int(config.get_int(key=key, default=default))  # type: ignore[arg-type]
        except Exception:
            return default
