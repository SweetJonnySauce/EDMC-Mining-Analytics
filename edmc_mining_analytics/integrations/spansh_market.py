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
DEFAULT_RESULT_SIZE = 10
MAX_RANGE_VALUE = 1_000_000_000

STATION_TYPES: tuple[str, ...] = (
    "Asteroid base",
    "Coriolis Starport",
    "Dodec Starport",
    "Mega ship",
    "Ocellus Starport",
    "Orbis Starport",
    "Space Construction Depot",
)
SURFACE_TYPES: tuple[str, ...] = (
    "Dockable Planet Station",
    "Outpost",
    "Planetary Construction Depot",
    "Planetary Port",
    "Settlement",
    "Surface Settlement",
)
CARRIER_TYPES: tuple[str, ...] = ("Drake-Class carrier",)


@dataclass(frozen=True)
class MarketSearchPreferences:
    has_large_pad: Optional[bool]
    min_demand: int
    age_days: int
    distance_ly: Optional[float]
    distance_to_arrival_ls: Optional[float]
    sort_mode: str  # best_price | nearest
    include_carriers: bool
    include_surface: bool


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

        now = datetime.now(timezone.utc)
        payload = self._build_payload(commodity_name, reference, prefs)
        url = f"{API_BASE}/stations/search"
        _log.debug("Spansh market search request: url=%s payload=%s", url, payload)
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
        search_reference = data.get("search_reference")
        search_url = _format_search_reference_url(search_reference)
        _log.debug(
            "Spansh market search response: search_reference_url=%s result_count=%s",
            search_url,
            len(results) if isinstance(results, list) else "unknown",
        )
        if not isinstance(results, list):
            return None

        cutoff = None
        if prefs.age_days and prefs.age_days > 0:
            cutoff = now - timedelta(days=prefs.age_days)

        filtered_results = self._filter_distance_to_arrival(results, prefs.distance_to_arrival_ls)
        for entry in self._filter_recent(filtered_results, cutoff):
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
            "type": {"value": _build_station_types(prefs)},
            "market": [
                {
                    "name": commodity,
                    "demand": {"comparison": "<=>", "value": [prefs.min_demand, MAX_RANGE_VALUE]},
                }
            ],
        }

        if prefs.has_large_pad is not None:
            filters["has_large_pad"] = {"value": prefs.has_large_pad}

        if prefs.distance_ly is not None:
            filters["distance"] = {"min": 0.0, "max": float(prefs.distance_ly)}

        if prefs.distance_to_arrival_ls is not None:
            filters["distance_to_arrival"] = {
                "comparison": "<=>",
                "value": [0, float(prefs.distance_to_arrival_ls)],
            }

        if prefs.age_days and prefs.age_days > 0:
            days = max(0, int(prefs.age_days))
            filters["market_updated_at"] = {
                "comparison": "<=>",
                "value": [f"now-{days}d", "now"],
            }

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

    def _filter_distance_to_arrival(
        self,
        results: Iterable[Dict[str, object]],
        max_distance: Optional[float],
    ) -> List[Dict[str, object]]:
        if max_distance is None:
            return [item for item in results if isinstance(item, dict)]
        try:
            max_value = float(max_distance)
        except (TypeError, ValueError):
            return [item for item in results if isinstance(item, dict)]

        filtered: List[Dict[str, object]] = []
        dropped = 0
        for item in results:
            if not isinstance(item, dict):
                continue
            value = item.get("distance_to_arrival")
            if value is None:
                filtered.append(item)
                continue
            try:
                if float(value) <= max_value:
                    filtered.append(item)
                else:
                    dropped += 1
            except (TypeError, ValueError):
                filtered.append(item)
        if dropped:
            _log.debug(
                "Spansh market search filtered %s station(s) beyond distance_to_arrival=%s",
                dropped,
                max_value,
            )
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


def _format_search_reference_url(value: object) -> Optional[str]:
    if not value:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    return f"https://spansh.co.uk/stations/search/{candidate}/1"


def _build_station_types(prefs: MarketSearchPreferences) -> List[str]:
    values: List[str] = list(STATION_TYPES)
    if prefs.include_carriers:
        values.extend(CARRIER_TYPES)
    if prefs.include_surface:
        values.extend(SURFACE_TYPES)
    return values


__all__ = ["MarketSearchPreferences", "MarketPriceEstimate", "SpanshMarketClient"]
