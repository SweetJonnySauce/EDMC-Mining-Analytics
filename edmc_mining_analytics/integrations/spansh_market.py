"""Spansh market search client for station commodity pricing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional

import requests

from ..http_client import get_shared_session
from ..logging_utils import get_logger


_log = get_logger("spansh_market")

API_BASE = "https://spansh.co.uk/api"
DEFAULT_TIMEOUT = 15
DEFAULT_RESULT_SIZE = 25
MAX_RANGE_VALUE = 1_000_000_000


@dataclass(frozen=True)
class MarketSearchPreferences:
    has_large_pad: Optional[bool]
    min_demand: int
    age_days: int
    distance_ly: Optional[float]
    sort_mode: str  # best_price | nearest


@dataclass(frozen=True)
class MarketPriceEstimate:
    commodity: str
    sell_price: float
    station_name: str
    system_name: str
    market_updated_at: Optional[str]
    distance_ly: Optional[float]
    distance_to_arrival: Optional[float]
    demand: Optional[float]
    supply: Optional[float]

    def to_dict(self) -> Dict[str, object]:
        return {
            "commodity": self.commodity,
            "sell_price": self.sell_price,
            "station_name": self.station_name,
            "system_name": self.system_name,
            "market_updated_at": self.market_updated_at,
            "distance_ly": self.distance_ly,
            "distance_to_arrival": self.distance_to_arrival,
            "demand": self.demand,
            "supply": self.supply,
        }


def _parse_market_updated_at(value: object) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _normalise_sort_mode(value: str) -> str:
    candidate = (value or "").strip().lower()
    return "best_price" if candidate == "best_price" else "nearest"


class SpanshMarketClient:
    """Encapsulates Spansh station market lookups."""

    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self._session = session or get_shared_session()

    def search_best_price(
        self,
        commodity: str,
        reference_system: str,
        prefs: MarketSearchPreferences,
    ) -> Optional[MarketPriceEstimate]:
        commodity_name = (commodity or "").strip()
        reference = (reference_system or "").strip()
        if not commodity_name or not reference:
            return None

        payload = self._build_payload(commodity_name, reference, prefs)
        url = f"{API_BASE}/stations/search"
        try:
            response = self._session.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
        except requests.RequestException as exc:
            _log.debug("Spansh market search failed: %s", exc)
            return None

        if response.status_code != 200:
            _log.debug("Spansh market search status %s", response.status_code)
            return None

        try:
            data = response.json()
        except ValueError:
            _log.debug("Spansh market search returned invalid JSON")
            return None

        results = data.get("results") or []
        if not isinstance(results, list):
            return None

        cutoff = None
        if prefs.age_days and prefs.age_days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=prefs.age_days)

        for entry in self._filter_recent(results, cutoff):
            estimate = self._extract_estimate(entry, commodity_name)
            if estimate is not None:
                return estimate
        return None

    def _build_payload(
        self,
        commodity: str,
        reference_system: str,
        prefs: MarketSearchPreferences,
    ) -> Dict[str, object]:
        filters: Dict[str, object] = {
            "has_market": {"value": True},
            "market": [
                {
                    "name": commodity,
                    "demand": {"comparison": "<=>", "value": [prefs.min_demand, MAX_RANGE_VALUE]},
                    "supply": {"comparison": "<=>", "value": [0, MAX_RANGE_VALUE]},
                }
            ],
        }

        if prefs.has_large_pad is not None:
            filters["has_large_pad"] = {"value": prefs.has_large_pad}

        if prefs.distance_ly is not None:
            filters["distance"] = {"min": 0.0, "max": float(prefs.distance_ly)}

        if prefs.age_days and prefs.age_days > 0:
            now = datetime.now(timezone.utc)
            start_date = (now - timedelta(days=prefs.age_days)).date().isoformat()
            end_date = now.date().isoformat()
            filters["market_updated_at"] = {"comparison": "<=>", "value": [start_date, end_date]}

        sort_mode = _normalise_sort_mode(prefs.sort_mode)
        if sort_mode == "best_price":
            sort = [
                {"market_sell_price": [{"name": commodity, "direction": "desc"}]},
                {"distance": {"direction": "asc"}},
            ]
        else:
            sort = [{"distance": {"direction": "asc"}}]

        return {
            "filters": filters,
            "reference_system": reference_system,
            "sort": sort,
            "size": DEFAULT_RESULT_SIZE,
            "page": 0,
        }

    def _filter_recent(
        self,
        results: Iterable[Dict[str, object]],
        cutoff: Optional[datetime],
    ) -> List[Dict[str, object]]:
        if cutoff is None:
            return [item for item in results if isinstance(item, dict)]

        filtered: List[Dict[str, object]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            updated_at = _parse_market_updated_at(item.get("market_updated_at"))
            if updated_at and updated_at >= cutoff:
                filtered.append(item)
        return filtered

    def _extract_estimate(
        self,
        station: Dict[str, object],
        commodity: str,
    ) -> Optional[MarketPriceEstimate]:
        market_entries = station.get("market") or []
        if not isinstance(market_entries, list):
            return None

        target = commodity.lower()
        for entry in market_entries:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("commodity") or "").strip()
            if not name or name.lower() != target:
                continue
            sell_price = entry.get("sell_price")
            try:
                price_value = float(sell_price)
            except (TypeError, ValueError):
                price_value = None
            if price_value is None:
                continue
            return MarketPriceEstimate(
                commodity=name,
                sell_price=price_value,
                station_name=str(station.get("name") or ""),
                system_name=str(station.get("system_name") or ""),
                market_updated_at=(
                    str(station.get("market_updated_at"))
                    if station.get("market_updated_at") is not None
                    else None
                ),
                distance_ly=_safe_float(station.get("distance")),
                distance_to_arrival=_safe_float(station.get("distance_to_arrival")),
                demand=_safe_float(entry.get("demand")),
                supply=_safe_float(entry.get("supply")),
            )
        return None


def _safe_float(value: object) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["MarketSearchPreferences", "MarketPriceEstimate", "SpanshMarketClient"]
