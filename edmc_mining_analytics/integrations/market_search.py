"""Background market search service for estimated commodity sell prices."""

from __future__ import annotations

import threading
from typing import Callable, Optional

from ..logging_utils import get_logger
from ..state import MiningState, recompute_market_sell_totals
from .spansh_market import MarketSearchPreferences, SpanshMarketClient


_log = get_logger("market_search")


class MarketSearchService:
    """Queue Spansh market searches and update cached sell prices."""

    def __init__(
        self,
        state: MiningState,
        on_updated: Callable[[], None],
        *,
        client: Optional[SpanshMarketClient] = None,
    ) -> None:
        self._state = state
        self._on_updated = on_updated
        self._client = client or SpanshMarketClient()
        self._lock = threading.Lock()

    def request_price(self, commodity_key: str) -> None:
        key = (commodity_key or "").strip().lower()
        if not key:
            return

        with self._lock:
            if key in self._state.market_search_attempted:
                return
            if key in self._state.market_search_inflight:
                return
            if self._state.is_paused:
                return
            reference_system = self._state.current_system
            if not reference_system:
                return

            localized_name = self._state.commodity_display_names.get(key)
            canonical_name = self._state.commodity_canonical_names.get(key)

            prefs = self._build_preferences()
            self._state.market_search_inflight.add(key)

        thread = threading.Thread(
            target=self._lookup_price,
            args=(key, localized_name, canonical_name, reference_system, prefs),
            name="edmcma-spansh-market",
            daemon=True,
        )
        thread.start()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_preferences(self) -> MarketSearchPreferences:
        has_large_pad = True if self._state.market_search_has_large_pad is True else None
        min_demand = _coerce_int(self._state.market_search_min_demand, default=0)
        min_demand = max(0, min_demand)
        age_days = _coerce_int(self._state.market_search_age_days, default=0)
        age_days = max(0, age_days)
        distance = _coerce_float(self._state.market_search_distance_ly)
        distance_ly = distance if distance and distance > 0 else None
        sort_mode = (self._state.market_search_sort_mode or "best_price").strip().lower()

        return MarketSearchPreferences(
            has_large_pad=has_large_pad,
            min_demand=min_demand,
            age_days=age_days,
            distance_ly=distance_ly,
            sort_mode=sort_mode,
        )

    def _lookup_price(
        self,
        key: str,
        localized_name: Optional[str],
        canonical_name: Optional[str],
        reference_system: str,
        prefs: MarketSearchPreferences,
    ) -> None:
        candidates = _build_name_candidates(localized_name, canonical_name, key)
        estimate = None
        for candidate in candidates:
            estimate = self._client.search_best_price(candidate, reference_system, prefs)
            if estimate is not None:
                break

        should_refresh = False
        applied_estimate = None
        with self._lock:
            if key not in self._state.market_search_inflight:
                return
            self._state.market_search_inflight.discard(key)
            self._state.market_search_attempted.add(key)
            if estimate is not None and self._state.is_mining and key in self._state.cargo_totals:
                self._state.market_sell_prices[key] = estimate.sell_price
                self._state.market_sell_details[key] = estimate.to_dict()
                recompute_market_sell_totals(self._state)
                should_refresh = True
                applied_estimate = estimate

        if applied_estimate is not None:
            _log.debug(
                "Market search price set: commodity=%s (key=%s) system=%s station=%s sell_price=%s",
                applied_estimate.commodity,
                key,
                applied_estimate.system_name,
                applied_estimate.station_name,
                applied_estimate.sell_price,
            )

        if should_refresh:
            try:
                self._on_updated()
            except Exception:
                _log.exception("Failed to notify UI after market search update")


def _build_name_candidates(
    localized_name: Optional[str],
    canonical_name: Optional[str],
    fallback_key: str,
) -> list[str]:
    candidates: list[str] = []
    for value in (localized_name, canonical_name):
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                candidates.append(cleaned)
    if not candidates:
        candidates.append(fallback_key.strip())

    seen: set[str] = set()
    unique: list[str] = []
    for name in candidates:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(name)
    return unique


def _coerce_int(value: object, *, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _coerce_float(value: object) -> Optional[float]:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


__all__ = ["MarketSearchService"]
