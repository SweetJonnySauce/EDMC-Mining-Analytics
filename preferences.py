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
            state.discord_image_url = ""
            state.refinement_lookback_seconds = 10
            state.rpm_threshold_red = 10
            state.rpm_threshold_yellow = 20
            state.rpm_threshold_green = 30
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
        state.discord_image_url = self._get_str("edmc_mining_discord_image", "").strip()
        state.refinement_lookback_seconds = clamp_positive_int(
            self._get_int("edmc_mining_refinement_window", state.refinement_lookback_seconds),
            state.refinement_lookback_seconds,
            maximum=3600,
        )
        state.rpm_threshold_red = clamp_positive_int(
            self._get_int("edmc_mining_rpm_red", state.rpm_threshold_red),
            state.rpm_threshold_red,
            maximum=10_000,
        )
        state.rpm_threshold_yellow = clamp_positive_int(
            self._get_int("edmc_mining_rpm_yellow", state.rpm_threshold_yellow),
            state.rpm_threshold_yellow,
            maximum=10_000,
        )
        state.rpm_threshold_green = clamp_positive_int(
            self._get_int("edmc_mining_rpm_green", state.rpm_threshold_green),
            state.rpm_threshold_green,
            maximum=10_000,
        )

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
            config.set("edmc_mining_discord_image", state.discord_image_url or "")
        except Exception:
            _log.exception("Failed to persist Discord image URL")

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
                clamp_positive_int(state.rpm_threshold_red, 10),
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
                clamp_positive_int(state.rpm_threshold_green, 30),
            )
        except Exception:
            _log.exception("Failed to persist RPM green threshold")

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

    def reset_inferred_capacities(self, state: MiningState) -> None:
        state.inferred_capacity_map.clear()
        if config is None:
            return
        try:
            config.set("edmc_mining_inferred_cargo_map", "{}")
        except Exception:
            _log.exception("Failed to clear inferred cargo capacities from config")
