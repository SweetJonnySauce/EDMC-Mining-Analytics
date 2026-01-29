"""Preference loading and persistence for the EDMC Mining Analytics plugin."""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional, Sequence

try:
    from config import config  # type: ignore[import]
except ImportError:  # pragma: no cover - only available inside EDMC
    config = None  # type: ignore[assignment]

from .state import MiningState
from .logging_utils import get_logger


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
    return max(100, min(60_000, result))


class PreferencesManager:
    """Loads and persists user preferences via EDMC's config object."""

    def load(self, state: MiningState) -> None:
        if config is None:
            state.histogram_bin_size = 10
            state.rate_interval_seconds = 30
            state.inferred_capacity_map = {}
            state.auto_unpause_on_event = True
            state.session_logging_enabled = False
            state.session_log_retention = 30
            state.discord_webhook_url = ""
            state.send_summary_to_discord = False
            state.send_reset_summary = False
            state.discord_images = []
            state.refinement_lookback_seconds = 10
            state.rpm_threshold_red = 1
            state.rpm_threshold_yellow = 20
            state.rpm_threshold_green = 40
            state.overlay_enabled = False
            state.overlay_anchor_x = 40
            state.overlay_anchor_y = 120
            state.overlay_refresh_interval_ms = 1000
            state.market_search_has_large_pad = None
            state.market_search_sort_mode = "best_price"
            state.market_search_include_carriers = True
            state.market_search_include_surface = True
            state.market_search_min_demand = 1000
            state.market_search_age_days = 30
            state.market_search_distance_ly = 100.0
            state.market_search_distance_ls = 5000.0
            return

        state.histogram_bin_size = clamp_bin_size(self._get_int("edmc_mining_histogram_bin", 10))
        state.rate_interval_seconds = clamp_rate_interval(self._get_int("edmc_mining_rate_interval", 30))

        state.inferred_capacity_map = self._load_inferred_capacities()
        state.auto_unpause_on_event = bool(self._get_int("edmc_mining_auto_unpause", 1))
        state.session_logging_enabled = bool(self._get_int("edmc_mining_session_logging", 0))
        state.session_log_retention = clamp_session_retention(
            self._get_int("edmc_mining_session_retention", 30)
        )
        state.discord_webhook_url = self._get_str("edmc_mining_discord_webhook", "").strip()
        state.send_summary_to_discord = bool(self._get_int("edmc_mining_discord_summary", 0))
        state.send_reset_summary = bool(self._get_int("edmc_mining_discord_reset_summary", 0))
        state.discord_images = self._load_discord_images("edmc_mining_discord_images")
        legacy_image = self._get_optional_str("edmc_mining_discord_image")
        if legacy_image:
            state.discord_images.append(("", legacy_image))
        state.discord_image_cycle = {}
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
        state.overlay_show_bars = bool(self._get_int("overlay_show_bars", int(state.overlay_show_bars)))
        state.overlay_bars_max_rows = clamp_positive_int(
            self._get_int("overlay_bars_max_rows", state.overlay_bars_max_rows),
            state.overlay_bars_max_rows,
            maximum=50,
        )
        state.spansh_last_distance_min = self._get_float("edmc_mining_spansh_distance_min", None)
        state.spansh_last_distance_max = self._get_float("edmc_mining_spansh_distance_max", None)
        state.spansh_last_ring_signals = self._load_string_list("edmc_mining_spansh_ring_signals")
        state.spansh_last_reserve_levels = self._load_string_list("edmc_mining_spansh_reserve_levels")
        state.spansh_last_ring_types = self._load_string_list("edmc_mining_spansh_ring_types")
        state.spansh_last_min_hotspots = self._get_optional_int("edmc_mining_spansh_min_hotspots")

        market_large_pad_raw = self._get_optional_str("edmc_mining_market_large_pad")
        if market_large_pad_raw is not None and market_large_pad_raw.strip().lower() in ("1", "true", "yes"):
            state.market_search_has_large_pad = True
        else:
            state.market_search_has_large_pad = None
        raw_sort = self._get_str("edmc_mining_market_sort", state.market_search_sort_mode).strip().lower()
        state.market_search_sort_mode = "nearest" if raw_sort == "nearest" else "best_price"
        state.market_search_include_carriers = bool(
            self._get_int("edmc_mining_market_include_carriers", int(state.market_search_include_carriers))
        )
        state.market_search_include_surface = bool(
            self._get_int("edmc_mining_market_include_surface", int(state.market_search_include_surface))
        )
        min_demand = self._get_int("edmc_mining_market_min_demand", state.market_search_min_demand)
        state.market_search_min_demand = max(0, min_demand)
        age_days = self._get_int("edmc_mining_market_age_days", state.market_search_age_days)
        state.market_search_age_days = max(0, age_days)
        distance = self._get_float("edmc_mining_market_distance_ly", None)
        if distance is None or distance <= 0:
            distance = state.market_search_distance_ly
        state.market_search_distance_ly = float(distance)
        distance_ls = None
        if config is not None:
            try:
                raw_distance_ls = config.get_str(key="edmc_mining_market_distance_ls")  # type: ignore[arg-type]
            except Exception:
                raw_distance_ls = None
            if raw_distance_ls is None:
                distance_ls = 5000.0
            else:
                text = str(raw_distance_ls).strip()
                if text:
                    try:
                        parsed = float(text)
                    except (TypeError, ValueError):
                        parsed = None
                    if parsed and parsed > 0:
                        distance_ls = parsed
                else:
                    distance_ls = None
        if distance_ls is None and config is None:
            distance_ls = 5000.0
        state.market_search_distance_ls = distance_ls

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
            payload = json.dumps(state.discord_images)
            config.set("edmc_mining_discord_images", payload)
        except Exception:
            _log.exception("Failed to persist Discord image list")

        try:
            config.set("edmc_mining_discord_image", "")
        except Exception:
            pass

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
            config.set("overlay_show_bars", int(state.overlay_show_bars))
        except Exception:
            _log.exception("Failed to persist overlay show bars preference")

        try:
            config.set(
                "overlay_bars_max_rows",
                clamp_positive_int(state.overlay_bars_max_rows, 10, maximum=50),
            )
        except Exception:
            _log.exception("Failed to persist overlay bars max rows preference")


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

        try:
            value = (
                str(max(1, int(state.spansh_last_min_hotspots)))
                if state.spansh_last_min_hotspots is not None
                else ""
            )
            config.set("edmc_mining_spansh_min_hotspots", value)
        except Exception:
            _log.exception("Failed to persist Spansh minimum hotspots")

        try:
            value = "1" if state.market_search_has_large_pad else ""
            config.set("edmc_mining_market_large_pad", value)
        except Exception:
            _log.exception("Failed to persist market search large pad preference")

        try:
            config.set("edmc_mining_market_sort", state.market_search_sort_mode or "best_price")
        except Exception:
            _log.exception("Failed to persist market search sort preference")

        try:
            config.set("edmc_mining_market_include_carriers", int(state.market_search_include_carriers))
        except Exception:
            _log.exception("Failed to persist market search carriers preference")

        try:
            config.set("edmc_mining_market_include_surface", int(state.market_search_include_surface))
        except Exception:
            _log.exception("Failed to persist market search surface preference")

        try:
            config.set("edmc_mining_market_min_demand", int(state.market_search_min_demand))
        except Exception:
            _log.exception("Failed to persist market search min demand")

        try:
            config.set("edmc_mining_market_age_days", int(state.market_search_age_days))
        except Exception:
            _log.exception("Failed to persist market search age days")

        try:
            config.set("edmc_mining_market_distance_ly", str(float(state.market_search_distance_ly)))
        except Exception:
            _log.exception("Failed to persist market search distance")

        try:
            value = "" if state.market_search_distance_ls is None else str(float(state.market_search_distance_ls))
            config.set("edmc_mining_market_distance_ls", value)
        except Exception:
            _log.exception("Failed to persist market search distance to arrival")


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

    def _get_optional_int(self, key: str) -> Optional[int]:
        text = self._get_optional_str(key)
        if text is None:
            return None
        try:
            value = int(text)
        except (TypeError, ValueError):
            return None
        if value < 1:
            return 1
        return value

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

    def _load_discord_images(self, key: str) -> List[tuple[str, str]]:
        payload = self._get_optional_str(key)
        if not payload:
            return []
        try:
            data = json.loads(payload)
        except Exception:
            return []
        entries: List[tuple[str, str]] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    ship = str(item[0] or "")
                    url = str(item[1] or "").strip()
                    if url:
                        entries.append((ship, url))
                elif isinstance(item, dict):
                    ship = str(item.get("ship") or "")
                    url = str(item.get("url") or "").strip()
                    if url:
                        entries.append((ship, url))
        return entries

    def reset_inferred_capacities(self, state: MiningState) -> None:
        state.inferred_capacity_map.clear()
        if config is None:
            return
        try:
            config.set("edmc_mining_inferred_cargo_map", "{}")
        except Exception:
            _log.exception("Failed to clear inferred cargo capacities from config")
