"""Client for querying Spansh hotspots."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import requests

from ..logging_utils import get_logger
from ..state import MiningState
from ..http_client import get_shared_session

_log = get_logger("spansh")
_plugin_log = get_logger()

API_BASE = "https://spansh.co.uk/api"
DEFAULT_TIMEOUT = 10
DEFAULT_MIN_INTERVAL = 1.5  # configurable throttling to the Spansh hotspot client so consecutive searches respect a minimum interval.
MAX_SIGNAL_COUNT = 9999
DEFAULT_RESULT_SIZE = 50


@dataclass(frozen=True)
class RingSignal:
    """Represents a single hotspot signal entry from Spansh."""

    name: str
    count: int


@dataclass(frozen=True)
class RingHotspot:
    """Represents a single ring hotspot row."""

    system_name: str
    body_name: str
    ring_name: str
    ring_type: str
    distance_ls: float
    distance_ly: float
    signals: Tuple[RingSignal, ...]
    signals_updated_at: Optional[str] = None


@dataclass(frozen=True)
class HotspotSearchResult:
    """Normalised representation of a Spansh hotspot search."""

    total_count: int
    reference_system: Optional[str]
    entries: Tuple[RingHotspot, ...]


class SpanshHotspotClient:
    """Encapsulates Spansh hotspot lookups."""

    def __init__(
        self,
        state: MiningState,
        session: Optional[requests.Session] = None,
        min_interval_seconds: float = DEFAULT_MIN_INTERVAL,
    ) -> None:
        self._state = state
        self._session = session or get_shared_session()
        self._field_cache: Dict[str, List[str]] = {}
        self._min_interval = max(0.0, float(min_interval_seconds))
        self._last_search_completed_at: float = 0.0

    # ------------------------------------------------------------------
    # Field metadata
    # ------------------------------------------------------------------
    def list_ring_types(self) -> List[str]:
        return self._get_field_values("rings")

    def list_ring_signals(self) -> List[str]:
        return self._get_field_values("ring_signals")

    def list_reserve_levels(self) -> List[str]:
        return self._get_field_values("reserve_level")

    def suggest_system_names(self, query: str, limit: int = 10) -> List[str]:
        candidate = (query or "").strip()
        if len(candidate) < 2:
            return []

        url = f"{API_BASE}/systems/field_values/system_names"
        params = {"q": candidate}
        try:
            response = self._session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        except Exception:
            _plugin_log.debug("Spansh reference suggestions failed (query=%r): request error", candidate)
            return []

        if response.status_code != 200:
            _plugin_log.debug(
                "Spansh reference suggestions failed (query=%r): status %s",
                candidate,
                response.status_code,
            )
            return []

        try:
            data = response.json()
        except Exception:
            _plugin_log.debug("Spansh reference suggestions failed (query=%r): invalid JSON", candidate)
            return []

        values = data.get("values")
        if not isinstance(values, list):
            _plugin_log.debug("Spansh reference suggestions unexpected payload (query=%r): %s", candidate, data)
            return []

        cleaned = []
        seen: set[str] = set()
        candidate_lower = candidate.lower()

        for value in values:
            if not isinstance(value, str):
                continue
            name = value.strip()
            if not name:
                continue
            if name.lower() in seen:
                continue
            seen.add(name.lower())
            cleaned.append(name)
            if len(cleaned) >= limit:
                break

        # Ensure the user's current system is considered when it matches the query
        current_system = (self._state.current_system or "").strip()
        if current_system and current_system.lower().startswith(candidate_lower):
            if current_system.lower() not in seen:
                cleaned.insert(0, current_system)

        _plugin_log.debug(
            "Spansh reference suggestions query=%r params=%s returned %d candidate(s)",
            candidate,
            params,
            len(cleaned),
        )

        return cleaned

    def resolve_reference_system(self, reference: Optional[str]) -> str:
        candidate = (reference or "").strip()
        current_system = (self._state.current_system or "").strip()

        if not candidate:
            if current_system:
                return current_system
            raise ValueError("Reference system is unknown; please enter a system name.")

        if current_system and candidate.lower() == current_system.lower():
            return current_system

        url = f"{API_BASE}/systems/field_values/system_names"
        params = {"q": candidate}
        try:
            response = self._session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        except Exception as exc:
            _log.exception("Spansh reference system lookup failed: %s", exc)
            raise RuntimeError("Failed to contact spansh.co.uk systems API") from exc

        if response.status_code != 200:
            raise RuntimeError(f"Spansh reference system lookup failed with status {response.status_code}")

        try:
            data = response.json()
        except Exception as exc:
            _log.exception("Failed to parse Spansh reference system response: %s", exc)
            raise RuntimeError("Unable to decode Spansh reference system response") from exc

        values = data.get("values")
        if not isinstance(values, list):
            values = []

        cleaned = [str(value).strip() for value in values if isinstance(value, str) and str(value).strip()]
        if not cleaned:
            raise ValueError(f"Reference system '{candidate}' was not found on spansh.co.uk")

        candidate_lower = candidate.lower()
        for name in cleaned:
            if name.lower() == candidate_lower:
                return name

        return cleaned[0]

    def _get_field_values(self, field: str) -> List[str]:
        cached = self._field_cache.get(field)
        if cached is not None:
            return cached

        url = f"{API_BASE}/bodies/field_values/{field}"
        try:
            response = self._session.get(url, timeout=DEFAULT_TIMEOUT)
        except Exception:
            _log.exception("Failed to fetch Spansh field values for %s", field)
            return []

        if response.status_code != 200:
            _log.warning("Non-200 response when fetching field values for %s: %s", field, response.status_code)
            return []

        try:
            payload = response.json()
        except Exception:
            _log.exception("Failed to decode field values response for %s", field)
            return []

        values = payload.get("values")
        if not isinstance(values, list):
            _log.debug("Unexpected payload for field values %s: %s", field, payload)
            return []

        cleaned = [str(value) for value in values if isinstance(value, str)]
        self._field_cache[field] = cleaned
        return cleaned

    # ------------------------------------------------------------------
    # Hotspot search
    # ------------------------------------------------------------------
    def search_hotspots(
        self,
        distance_min: float,
        distance_max: float,
        ring_signals: Sequence[str],
        reserve_levels: Sequence[str],
        ring_types: Sequence[str],
        limit: int = DEFAULT_RESULT_SIZE,
        page: int = 0,
        reference_system: Optional[str] = None,
        min_hotspots: int = 1,
    ) -> HotspotSearchResult:
        """Query Spansh for hotspots near the current system."""

        system = (reference_system or self._state.current_system or "").strip()
        if not system:
            raise ValueError("Reference system is unknown; cannot perform hotspot search.")

        filters: Dict[str, object] = {}

        min_count = max(1, int(min_hotspots))

        if distance_min is not None or distance_max is not None:
            min_val = float(distance_min if distance_min is not None else 0.0)
            max_val = float(distance_max if distance_max is not None else MAX_SIGNAL_COUNT)
            if max_val < min_val:
                min_val, max_val = max_val, min_val
            filters["distance"] = {"min": min_val, "max": max_val}

        cleaned_signals = [signal for signal in (ring_signals or []) if signal]
        if cleaned_signals:
            filters["ring_signals"] = [
                {
                    "comparison": "<=>",
                    "count": [min_count, MAX_SIGNAL_COUNT],
                    "name": cleaned_signals,
                }
            ]

        cleaned_reserves = [reserve for reserve in (reserve_levels or []) if reserve]
        if cleaned_reserves:
            if len(cleaned_reserves) == 1:
                filters["reserve_level"] = {"value": cleaned_reserves[0]}
            else:
                filters["reserve_level"] = {"value": cleaned_reserves}

        cleaned_rings = [ring_type for ring_type in (ring_types or []) if ring_type]
        if cleaned_rings:
            filters["rings"] = [{"type": cleaned_rings}]

        payload = {
            "filters": filters,
            "reference_system": system,
            "sort": [{"distance": {"direction": "asc"}}],
            "size": max(1, min(int(limit or DEFAULT_RESULT_SIZE), 200)),
            "page": max(0, int(page)),
        }

        delay = 0.0
        now = time.monotonic()
        elapsed = now - self._last_search_completed_at
        if elapsed < self._min_interval:
            delay = self._min_interval - elapsed
            time.sleep(delay)

        url = f"{API_BASE}/bodies/search"
        try:
            response = self._session.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
        except Exception as exc:
            _log.exception("Spansh hotspot request failed: %s", exc)
            raise RuntimeError("Failed to contact spansh.co.uk bodies API") from exc

        if response.status_code != 200:
            _log.warning("Spansh hotspot search returned status %s", response.status_code)
            raise RuntimeError(f"Spansh hotspot search failed with status {response.status_code}")

        try:
            data = response.json()
        except Exception as exc:
            _log.exception("Failed to parse Spansh hotspot response: %s", exc)
            raise RuntimeError("Unable to decode Spansh hotspot results") from exc

        results = data.get("results") or []
        entries = self._extract_ring_entries(
            results,
            set(cleaned_signals) if cleaned_signals else None,
            set(cleaned_rings) if cleaned_rings else None,
        )

        reference = data.get("reference") or {}
        reference_name = reference.get("name") if isinstance(reference, dict) else None
        if not reference_name:
            reference_name = system
        total_count = int(data.get("count") or 0)

        if _log.isEnabledFor(logging.DEBUG) or _plugin_log.isEnabledFor(logging.DEBUG):
            log_args = (
                system,
                len(results),
                len(entries),
                total_count,
                payload["size"],
                payload["page"],
                filters,
            )
            if _log.isEnabledFor(logging.DEBUG):
                _log.debug(
                    "Spansh hotspot search for %s returned %d rows (hotspots=%d, total_count=%d, limit=%d, page=%d) with filters %s",
                    *log_args,
                )
            if _plugin_log is not _log and _plugin_log.isEnabledFor(logging.DEBUG):
                _plugin_log.debug(
                    "Spansh hotspot search for %s returned %d rows (hotspots=%d, total_count=%d, limit=%d, page=%d) with filters %s",
                    *log_args,
        )

        self._last_search_completed_at = time.monotonic()

        return HotspotSearchResult(
            total_count=total_count,
            reference_system=reference_name,
            entries=tuple(entries),
        )

    def _extract_ring_entries(
        self,
        bodies: Iterable[Dict[str, object]],
        required_signals: Optional[set[str]],
        allowed_ring_types: Optional[set[str]],
    ) -> List[RingHotspot]:
        rows: List[RingHotspot] = []
        for body in bodies:
            if not isinstance(body, dict):
                continue
            system_name = str(body.get("system_name") or "")
            body_name = str(body.get("name") or "")
            distance_ls = float(body.get("distance_to_arrival") or 0.0)
            distance_ly = float(body.get("distance") or 0.0)

            rings = body.get("rings") or []
            if not isinstance(rings, list):
                continue

            for ring in rings:
                if not isinstance(ring, dict):
                    continue
                ring_type = str(ring.get("type") or "")
                if allowed_ring_types and ring_type not in allowed_ring_types:
                    continue
                ring_name = str(ring.get("name") or "")
                signals_payload = ring.get("signals") or []
                if not isinstance(signals_payload, list):
                    signals_payload = []

                signals: List[RingSignal] = []
                for entry in signals_payload:
                    if not isinstance(entry, dict):
                        continue
                    name = entry.get("name")
                    count = entry.get("count", 0)
                    if not isinstance(name, str):
                        continue
                    try:
                        count_value = int(count)
                    except (TypeError, ValueError):
                        count_value = 0
                    signals.append(RingSignal(name=name, count=count_value))

                if required_signals:
                    signal_names = {signal.name for signal in signals}
                    if not signal_names & required_signals:
                        continue

                rows.append(
                    RingHotspot(
                        system_name=system_name,
                        body_name=body_name,
                        ring_name=ring_name,
                        ring_type=ring_type,
                        distance_ls=distance_ls,
                        distance_ly=distance_ly,
                        signals=tuple(signals),
                        signals_updated_at=str(ring.get("signals_updated_at") or None),
                    )
                )

        return rows
