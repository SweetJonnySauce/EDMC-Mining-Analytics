from __future__ import annotations

import logging

from edmc_mining_analytics.integrations.spansh_population import (
    DEFAULT_LIVE_LOOKUP_LIMIT,
    POPULATION_CACHE_TTL_SECONDS,
    PersistentSystemPopulationCache,
    SpanshSystemPopulationLookup,
    resolve_population_cache_path,
)


class _Clock:
    def __init__(self, value: float = 1000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _FakeSession:
    def __init__(self, payloads=None):
        self.payloads = dict(payloads or {})
        self.requests = []

    def get(self, url, timeout):
        self.requests.append((url, timeout))
        system_id64 = int(url.rsplit("/", 1)[-1])
        payload = self.payloads.get(system_id64, {})
        if isinstance(payload, tuple):
            return _FakeResponse(payload[0], status_code=payload[1])
        return _FakeResponse(payload)


def test_population_cache_survives_recreation(tmp_path) -> None:
    clock = _Clock()
    path = tmp_path / "cache" / "spansh_system_population.json"
    cache = PersistentSystemPopulationCache(path, clock=clock)

    cache.set(123, 4567)

    recreated = PersistentSystemPopulationCache(path, clock=clock)
    assert recreated.get(123) == 4567


def test_population_cache_creates_file_on_initialization(tmp_path) -> None:
    path = tmp_path / "cache" / "spansh_system_population.json"

    PersistentSystemPopulationCache(path)

    assert path.is_file()


def test_population_cache_expires_after_one_month(tmp_path) -> None:
    clock = _Clock()
    path = tmp_path / "cache" / "spansh_system_population.json"
    cache = PersistentSystemPopulationCache(path, clock=clock)
    cache.set(123, 4567)

    clock.value += POPULATION_CACHE_TTL_SECONDS + 1
    recreated = PersistentSystemPopulationCache(path, clock=clock)

    assert recreated.get(123) is None


def test_population_cache_ignores_corrupt_files(tmp_path) -> None:
    path = tmp_path / "cache" / "spansh_system_population.json"
    path.parent.mkdir(parents=True)
    path.write_text("not json", encoding="utf-8")

    cache = PersistentSystemPopulationCache(path)

    assert cache.get(123) is None


def test_population_cache_path_is_plugin_owned(tmp_path) -> None:
    assert resolve_population_cache_path(tmp_path) == tmp_path / "cache" / "spansh_system_population.json"


def test_population_lookup_reads_cache_only_when_live_disabled(tmp_path) -> None:
    cache = PersistentSystemPopulationCache(tmp_path / "cache.json")
    cache.set(1, 100)
    session = _FakeSession({2: {"population": 200}})
    lookup = SpanshSystemPopulationLookup(session, cache, min_interval_seconds=0)

    result = lookup.lookup_populations([1, 2, 1], allow_live=False)

    assert result.populations == {1: 100}
    assert result.cache_hits == 1
    assert result.cache_misses == 1
    assert result.live_lookups == 0
    assert session.requests == []


def test_population_lookup_fetches_cache_misses_deduped_and_caches_zero(tmp_path) -> None:
    cache = PersistentSystemPopulationCache(tmp_path / "cache.json")
    session = _FakeSession({1: {"record": {"population": 0}}, 2: {"record": {"population": 200}}})
    lookup = SpanshSystemPopulationLookup(session, cache, min_interval_seconds=0)

    result = lookup.lookup_populations([1, 2, 1], allow_live=True)

    assert result.populations == {1: 0, 2: 200}
    assert result.live_lookups == 2
    assert [request[0] for request in session.requests] == [
        "https://spansh.co.uk/api/system/1",
        "https://spansh.co.uk/api/system/2",
    ]
    assert cache.get(1) == 0
    assert cache.get(2) == 200


def test_population_lookup_reports_live_lookup_progress(tmp_path) -> None:
    cache = PersistentSystemPopulationCache(tmp_path / "cache.json")
    session = _FakeSession({1: {"population": 100}, 2: {"population": 200}})
    lookup = SpanshSystemPopulationLookup(session, cache, min_interval_seconds=0)
    progress: list[tuple[int, int]] = []

    lookup.lookup_populations(
        [1, 2],
        allow_live=True,
        progress_callback=lambda current, total: progress.append((current, total)),
    )

    assert progress == [(1, 2), (2, 2)]


def test_population_lookup_logs_each_live_spansh_population_query(tmp_path, caplog) -> None:
    cache = PersistentSystemPopulationCache(tmp_path / "cache.json")
    session = _FakeSession({1: {"population": 100}})
    lookup = SpanshSystemPopulationLookup(session, cache, min_interval_seconds=0)

    with caplog.at_level(logging.DEBUG, logger="edmc_mining_analytics.spansh"):
        lookup.lookup_populations([1], allow_live=True)

    assert "Querying Spansh system population id64=1 url=https://spansh.co.uk/api/system/1" in caplog.text


def test_population_lookup_enforces_live_lookup_cap(tmp_path) -> None:
    cache = PersistentSystemPopulationCache(tmp_path / "cache.json")
    payloads = {system_id64: {"population": system_id64} for system_id64 in range(1, DEFAULT_LIVE_LOOKUP_LIMIT + 2)}
    session = _FakeSession(payloads)
    lookup = SpanshSystemPopulationLookup(session, cache, min_interval_seconds=0)

    result = lookup.lookup_populations(range(1, DEFAULT_LIVE_LOOKUP_LIMIT + 2), allow_live=True)

    assert result.live_lookups == DEFAULT_LIVE_LOOKUP_LIMIT
    assert result.capped_misses == 1
    assert len(session.requests) == DEFAULT_LIVE_LOOKUP_LIMIT
    assert (DEFAULT_LIVE_LOOKUP_LIMIT + 1) not in result.populations


def test_population_lookup_caches_failed_or_malformed_responses_as_unknown(tmp_path) -> None:
    cache = PersistentSystemPopulationCache(tmp_path / "cache.json")
    session = _FakeSession(
        {
            1: ({}, 500),
            2: {"not_population": 2},
            3: ValueError("invalid json"),
        }
    )
    lookup = SpanshSystemPopulationLookup(session, cache, min_interval_seconds=0)

    first = lookup.lookup_populations([1, 2, 3], allow_live=True)
    second = lookup.lookup_populations([1, 2, 3], allow_live=True)

    assert first.populations == {}
    assert first.live_failures == 3
    assert second.live_lookups == 0
    assert second.unknown_hits == 3
    assert len(session.requests) == 3


def test_population_lookup_throttles_live_requests(tmp_path) -> None:
    clock = _Clock(100.0)
    cache = PersistentSystemPopulationCache(tmp_path / "cache.json")
    session = _FakeSession({1: {"population": 1}, 2: {"population": 2}})
    lookup = SpanshSystemPopulationLookup(session, cache, min_interval_seconds=0.2, clock=clock)

    lookup.lookup_populations([1], allow_live=True)
    clock.value += 0.1
    lookup.lookup_populations([2], allow_live=True)

    assert len(session.requests) == 2
