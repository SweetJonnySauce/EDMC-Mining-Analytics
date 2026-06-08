"""Population lookup helpers for Spansh systems."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional

import requests

from ..logging_utils import get_logger

_log = get_logger("spansh")

API_BASE = "https://spansh.co.uk/api"
DEFAULT_TIMEOUT = 10
DEFAULT_MIN_INTERVAL = 0.2
DEFAULT_LIVE_LOOKUP_LIMIT = 50
POPULATION_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
POPULATION_CACHE_RELATIVE_PATH = Path("cache") / "spansh_system_population.json"


@dataclass(frozen=True)
class CachedPopulationResult:
    """Result of reading and optionally fetching system populations."""

    populations: Dict[int, int]
    cache_hits: int
    cache_misses: int
    unknown_hits: int = 0
    live_lookups: int = 0
    live_failures: int = 0
    capped_misses: int = 0


@dataclass(frozen=True)
class PopulationCacheEntry:
    """Cached population state for one system."""

    population: Optional[int]
    known: bool


class PersistentSystemPopulationCache:
    """File-backed cache for system population values."""

    def __init__(
        self,
        path: Path,
        *,
        ttl_seconds: int = POPULATION_CACHE_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._path = Path(path)
        self._ttl_seconds = int(ttl_seconds)
        self._clock = clock
        self._entries: Dict[int, tuple[Optional[int], float, bool]] = {}
        self._loaded = False
        self._lock = threading.RLock()
        self._initialise_storage()

    @property
    def path(self) -> Path:
        return self._path

    def _initialise_storage(self) -> None:
        if self._path.exists():
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"version": 1, "entries": {}}
            tmp_path = self._path.with_name(f"{self._path.name}.tmp")
            tmp_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            tmp_path.replace(self._path)
            _log.debug("Created Spansh system population cache: %s", self._path)
        except Exception:
            _log.exception("Failed initializing Spansh system population cache: %s", self._path)

    def get(self, system_id64: int) -> Optional[int]:
        entry = self.get_entry(system_id64)
        if entry is None or not entry.known:
            return None
        return entry.population

    def get_entry(self, system_id64: int) -> Optional[PopulationCacheEntry]:
        with self._lock:
            self._ensure_loaded()
            entry = self._entries.get(int(system_id64))
            if entry is None:
                return None
            population, cached_at, known = entry
            if self._clock() - cached_at > self._ttl_seconds:
                self._entries.pop(int(system_id64), None)
                return None
            return PopulationCacheEntry(population=population, known=known)

    def set(self, system_id64: int, population: int) -> None:
        self.set_many({system_id64: population})

    def set_many(self, populations: Dict[int, int]) -> None:
        if not populations:
            return
        with self._lock:
            self._ensure_loaded()
            cached_at = float(self._clock())
            for system_id64, population in populations.items():
                self._entries[int(system_id64)] = (max(0, int(population)), cached_at, True)
            self.save()

    def set_unknown_many(self, system_id64_values: Iterable[int]) -> None:
        ordered_ids = _dedupe_system_ids(system_id64_values)
        if not ordered_ids:
            return
        with self._lock:
            self._ensure_loaded()
            cached_at = float(self._clock())
            for system_id64 in ordered_ids:
                self._entries[int(system_id64)] = (None, cached_at, False)
            self.save()

    def save(self) -> None:
        with self._lock:
            self._ensure_loaded()
            payload = {
                "version": 1,
                "entries": {
                    str(system_id64): {
                        "population": population,
                        "cached_at": cached_at,
                        "status": "known" if known else "unknown",
                    }
                    for system_id64, (population, cached_at, known) in sorted(self._entries.items())
                },
            }
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = self._path.with_name(f"{self._path.name}.tmp")
                tmp_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
                tmp_path.replace(self._path)
            except Exception:
                _log.exception("Failed saving Spansh system population cache: %s", self._path)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        self._entries = {}
        if not self._path.exists():
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            _log.debug("Ignoring unreadable Spansh system population cache: %s", self._path)
            return
        entries = payload.get("entries") if isinstance(payload, dict) else None
        if not isinstance(entries, dict):
            return
        for raw_id64, raw_entry in entries.items():
            if not isinstance(raw_entry, dict):
                continue
            try:
                system_id64 = int(raw_id64)
                cached_at = float(raw_entry.get("cached_at"))
            except (TypeError, ValueError):
                continue
            status = str(raw_entry.get("status") or "known").strip().lower()
            if status == "unknown":
                if self._clock() - cached_at > self._ttl_seconds:
                    continue
                self._entries[system_id64] = (None, cached_at, False)
                continue
            if self._clock() - cached_at > self._ttl_seconds:
                continue
            try:
                population = int(raw_entry.get("population"))
            except (TypeError, ValueError):
                continue
            if population < 0:
                continue
            self._entries[system_id64] = (population, cached_at, True)


class SpanshSystemPopulationLookup:
    """Cache-first, bounded lookup for Spansh system populations."""

    def __init__(
        self,
        session: requests.Session,
        cache: Optional[PersistentSystemPopulationCache],
        *,
        min_interval_seconds: float = DEFAULT_MIN_INTERVAL,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._session = session
        self._cache = cache
        self._min_interval_seconds = max(0.0, float(min_interval_seconds))
        self._clock = clock
        self._last_system_lookup_at: float = 0.0

    def lookup_cached(self, system_id64_values: Iterable[int]) -> CachedPopulationResult:
        ordered_ids = self._dedupe_system_ids(system_id64_values)
        populations: Dict[int, int] = {}
        cache_hits = 0
        cache_misses = 0
        unknown_hits = 0

        for system_id64 in ordered_ids:
            cached = self._cache.get_entry(system_id64) if self._cache is not None else None
            if cached is None:
                cache_misses += 1
                continue
            cache_hits += 1
            if cached.known and cached.population is not None:
                populations[system_id64] = cached.population
            else:
                unknown_hits += 1

        _log.debug(
            "Spansh system population cache lookup ids=%d cache_hits=%d unknown_hits=%d cache_misses=%d",
            len(ordered_ids),
            cache_hits,
            unknown_hits,
            cache_misses,
        )

        return CachedPopulationResult(
            populations=populations,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            unknown_hits=unknown_hits,
        )

    def lookup_populations(
        self,
        system_id64_values: Iterable[int],
        *,
        allow_live: bool,
        live_lookup_limit: int = DEFAULT_LIVE_LOOKUP_LIMIT,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> CachedPopulationResult:
        ordered_ids = self._dedupe_system_ids(system_id64_values)
        cached = self.lookup_cached(ordered_ids)
        if not allow_live or self._cache is None:
            capped_misses = cached.cache_misses if allow_live and self._cache is None else 0
            return CachedPopulationResult(
                populations=cached.populations,
                cache_hits=cached.cache_hits,
                cache_misses=cached.cache_misses,
                unknown_hits=cached.unknown_hits,
                capped_misses=capped_misses,
            )

        missing_ids = [system_id64 for system_id64 in ordered_ids if system_id64 not in cached.populations]
        missing_ids = [
            system_id64
            for system_id64 in missing_ids
            if (self._cache.get_entry(system_id64) if self._cache is not None else None) is None
        ]
        live_limit = max(0, int(live_lookup_limit))
        live_ids = missing_ids[:live_limit]
        capped_misses = max(0, len(missing_ids) - len(live_ids))
        live_populations: Dict[int, int] = {}
        unknown_ids: list[int] = []

        total_live_ids = len(live_ids)
        for index, system_id64 in enumerate(live_ids, start=1):
            self._notify_progress(progress_callback, index, total_live_ids)
            population = self._fetch_system_population(system_id64)
            if population is None:
                unknown_ids.append(system_id64)
                continue
            live_populations[system_id64] = population

        if live_populations:
            self._cache.set_many(live_populations)
        if unknown_ids:
            self._cache.set_unknown_many(unknown_ids)

        populations = dict(cached.populations)
        populations.update(live_populations)
        _log.debug(
            "Spansh system population lookup ids=%d cache_hits=%d cache_misses=%d unknown_hits=%d live_lookups=%d live_failures=%d capped_misses=%d",
            len(ordered_ids),
            cached.cache_hits,
            cached.cache_misses,
            cached.unknown_hits,
            len(live_ids),
            len(unknown_ids),
            capped_misses,
        )
        return CachedPopulationResult(
            populations=populations,
            cache_hits=cached.cache_hits,
            cache_misses=cached.cache_misses,
            unknown_hits=cached.unknown_hits,
            live_lookups=len(live_ids),
            live_failures=len(unknown_ids),
            capped_misses=capped_misses,
        )

    @staticmethod
    def _notify_progress(
        callback: Optional[Callable[[int, int], None]],
        current: int,
        total: int,
    ) -> None:
        if callback is None:
            return
        try:
            callback(current, total)
        except Exception:
            _log.exception("Failed to notify Spansh population lookup progress")

    def _fetch_system_population(self, system_id64: int) -> Optional[int]:
        delay = self._system_lookup_delay()
        if delay > 0:
            time.sleep(delay)
        url = f"{API_BASE}/system/{int(system_id64)}"
        _log.debug("Querying Spansh system population id64=%s url=%s", system_id64, url)
        try:
            response = self._session.get(url, timeout=DEFAULT_TIMEOUT)
        except Exception:
            self._last_system_lookup_at = self._clock()
            _log.debug("Spansh system population detail lookup failed id64=%s: request error", system_id64)
            return None

        self._last_system_lookup_at = self._clock()
        if response.status_code != 200:
            _log.debug(
                "Spansh system population detail lookup failed id64=%s: status %s",
                system_id64,
                response.status_code,
            )
            return None

        try:
            payload = response.json()
        except Exception:
            _log.debug("Spansh system population detail lookup failed id64=%s: invalid JSON", system_id64)
            return None
        if not isinstance(payload, dict):
            return None
        raw_population = payload.get("population")
        if raw_population is None:
            record = payload.get("record")
            if isinstance(record, dict):
                raw_population = record.get("population")
        if isinstance(raw_population, bool):
            return None
        try:
            return max(0, int(raw_population))
        except (TypeError, ValueError):
            return None

    def _system_lookup_delay(self) -> float:
        if self._last_system_lookup_at <= 0:
            return 0.0
        elapsed = self._clock() - self._last_system_lookup_at
        if elapsed >= self._min_interval_seconds:
            return 0.0
        return self._min_interval_seconds - elapsed

    @staticmethod
    def _dedupe_system_ids(system_id64_values: Iterable[int]) -> list[int]:
        return _dedupe_system_ids(system_id64_values)


def _dedupe_system_ids(system_id64_values: Iterable[int]) -> list[int]:
    values: list[int] = []
    seen: set[int] = set()
    for raw_value in system_id64_values:
        if isinstance(raw_value, bool):
            continue
        try:
            system_id64 = int(raw_value)
        except (TypeError, ValueError):
            continue
        if system_id64 in seen:
            continue
        seen.add(system_id64)
        values.append(system_id64)
    return values


def resolve_population_cache_path(plugin_dir: Optional[Path | str]) -> Optional[Path]:
    if not plugin_dir:
        return None
    return Path(str(plugin_dir)) / POPULATION_CACHE_RELATIVE_PATH


def create_system_population_lookup(
    plugin_dir: Optional[Path | str],
    session: requests.Session,
    *,
    min_interval_seconds: float = DEFAULT_MIN_INTERVAL,
) -> SpanshSystemPopulationLookup:
    cache_path = resolve_population_cache_path(plugin_dir)
    cache = PersistentSystemPopulationCache(cache_path) if cache_path is not None else None
    _log.debug(
        "Configured Spansh system population lookup plugin_dir=%s cache_path=%s cache_enabled=%s",
        plugin_dir,
        cache_path,
        cache is not None,
    )
    return SpanshSystemPopulationLookup(
        session,
        cache,
        min_interval_seconds=min_interval_seconds,
    )


__all__ = [
    "CachedPopulationResult",
    "POPULATION_CACHE_RELATIVE_PATH",
    "POPULATION_CACHE_TTL_SECONDS",
    "PersistentSystemPopulationCache",
    "SpanshSystemPopulationLookup",
    "DEFAULT_LIVE_LOOKUP_LIMIT",
    "create_system_population_lookup",
    "resolve_population_cache_path",
]
