import logging

from edmc_mining_analytics.integrations.spansh_hotspots import (
    POPULATION_FILTER_ANY,
    POPULATION_FILTER_OPTIONS,
    SpanshHotspotClient,
)
from edmc_mining_analytics.integrations.spansh_population import (
    CachedPopulationResult,
)
from edmc_mining_analytics.state import MiningState


class _FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, payload, system_payloads=None):
        self.payload = payload
        self.system_payloads = dict(system_payloads or {})
        self.requests = []

    def post(self, url, json=None, data=None, timeout=None):
        self.requests.append((url, json, data, timeout))
        return _FakeResponse(self.payload)

    def get(self, url, timeout):
        self.requests.append((url, None, None, timeout))
        if "/api/system/" in url:
            system_id64 = int(url.rsplit("/", 1)[-1])
            return _FakeResponse(self.system_payloads.get(system_id64, {}))
        return _FakeResponse({})


class _FakePopulationLookup:
    def __init__(self, populations=None):
        self.populations = dict(populations or {})
        self.lookup_calls = []
        self.allow_live_calls = []
        self.live_limit_calls = []
        self.progress_callback_calls = []

    def lookup_populations(
        self,
        system_id64_values,
        *,
        allow_live,
        live_lookup_limit,
        progress_callback=None,
    ):
        ids = list(system_id64_values)
        self.lookup_calls.append(ids)
        self.allow_live_calls.append(allow_live)
        self.live_limit_calls.append(live_lookup_limit)
        self.progress_callback_calls.append(progress_callback)
        if allow_live and progress_callback is not None:
            for index, _system_id64 in enumerate(ids, start=1):
                progress_callback(index, len(ids))
        return CachedPopulationResult(
            populations=dict(self.populations),
            cache_hits=0,
            cache_misses=len(ids),
        )


def test_extract_system_id64_values_preserves_first_seen_order() -> None:
    bodies = [
        {"system_id64": 9655339499},
        {"system_id64": "9655339507"},
        {"system_id64": 9655339499},
        {"system_id64": None},
        {"system_id64": "not-a-number"},
        {"system_id64": True},
    ]

    assert SpanshHotspotClient._extract_system_id64_values(bodies) == [
        9655339499,
        9655339507,
    ]


def test_search_hotspots_logs_system_id64_values(caplog) -> None:
    payload = {
        "count": 2,
        "reference": {"name": "Sol"},
        "results": [
            {
                "system_id64": 9655339499,
                "system_name": "Sifou JR-D d12-0",
                "name": "Sifou JR-D d12-0 6",
                "distance": 10.0,
                "distance_to_arrival": 1180.0,
                "rings": [
                    {
                        "name": "Sifou JR-D d12-0 6 A Ring",
                        "type": "Metal Rich",
                        "signals": [{"name": "Platinum", "count": 2}],
                    }
                ],
            },
            {
                "system_id64": 9655339507,
                "system_name": "Sifou NX-B d13-0",
                "name": "Sifou NX-B d13-0 1",
                "distance": 11.0,
                "distance_to_arrival": 451.0,
                "rings": [],
            },
        ],
    }
    state = MiningState(current_system="Sol")
    client = SpanshHotspotClient(state, session=_FakeSession(payload), min_interval_seconds=0)

    with caplog.at_level(logging.DEBUG, logger="edmc_mining_analytics.spansh"):
        result = client.search_hotspots(
            distance_min=0.0,
            distance_max=100.0,
            ring_signals=["Platinum"],
            reserve_levels=[],
            ring_types=[],
        )

    assert result.reference_system == "Sol"
    assert "Spansh hotspot search system_id64 values: [9655339499, 9655339507]" in caplog.text


def test_population_filter_options_match_inara_style_mapping() -> None:
    options = {option.key: option for option in POPULATION_FILTER_OPTIONS}

    assert [option.label for option in POPULATION_FILTER_OPTIONS] == [
        "Any",
        "None",
        "Above 1",
        "Above 10,000",
        "Above 100,000",
        "Above 1,000,000",
        "Above 1,000,000,000",
        "Below 10,000",
        "Below 100,000",
        "Below 1,000,000",
        "Below 1,000,000,000",
    ]
    assert options[POPULATION_FILTER_ANY].comparison is None
    assert options["none"].comparison == "=="
    assert options["none"].value == 0
    assert options["above_1"].matches(1) is True
    assert options["above_1"].matches(0) is False
    assert options["below_10000"].matches(10_000) is True
    assert options["below_10000"].matches(10_001) is False
    assert SpanshHotspotClient.population_filter_key_for_label("Below 10,000") == "below_10000"
    assert SpanshHotspotClient.population_filter_label_for_key("below_10000") == "Below 10,000"


def test_population_filter_does_not_add_body_search_population_payload() -> None:
    payload = {"count": 0, "reference": {"name": "Sol"}, "results": []}
    session = _FakeSession(payload, system_payloads={1: {"population": 0}})
    lookup = _FakePopulationLookup()
    state = MiningState(current_system="Sol")
    client = SpanshHotspotClient(
        state,
        session=session,
        min_interval_seconds=0,
        population_lookup=lookup,
    )

    client.search_hotspots(
        distance_min=0.0,
        distance_max=100.0,
        ring_signals=[],
        reserve_levels=[],
        ring_types=[],
        population_filter="below_10000",
    )

    request_payload = session.requests[0][1]
    assert "population" not in request_payload["filters"]


def test_population_filter_excludes_known_non_matching_and_keeps_unknown_blank() -> None:
    payload = {
        "count": 3,
        "reference": {"name": "Sol"},
        "results": [
            _body_payload(1, "Zero", 1.0),
            _body_payload(2, "Populated", 2.0),
            _body_payload(3, "Unknown", 3.0),
        ],
    }
    lookup = _FakePopulationLookup(populations={1: 0, 2: 50_000})
    state = MiningState(current_system="Sol")
    client = SpanshHotspotClient(
        state,
        session=_FakeSession(payload),
        min_interval_seconds=0,
        population_lookup=lookup,
    )

    result = client.search_hotspots(
        distance_min=0.0,
        distance_max=100.0,
        ring_signals=[],
        reserve_levels=[],
        ring_types=[],
        population_filter="below_10000",
    )

    assert lookup.lookup_calls == [[1, 2, 3]]
    assert lookup.allow_live_calls == [True]
    assert [entry.system_name for entry in result.entries] == ["Zero", "Unknown"]
    assert [entry.population for entry in result.entries] == [0, None]


def test_population_any_uses_cache_only_lookup() -> None:
    payload = {
        "count": 1,
        "reference": {"name": "Sol"},
        "results": [_body_payload(1, "Cached", 1.0)],
    }
    lookup = _FakePopulationLookup(populations={1: 1234})
    state = MiningState(current_system="Sol")
    client = SpanshHotspotClient(
        state,
        session=_FakeSession(payload),
        min_interval_seconds=0,
        population_lookup=lookup,
    )

    result = client.search_hotspots(
        distance_min=0.0,
        distance_max=100.0,
        ring_signals=[],
        reserve_levels=[],
        ring_types=[],
    )

    assert lookup.lookup_calls == [[1]]
    assert lookup.allow_live_calls == [False]
    assert result.entries[0].population == 1234


def test_population_lookup_orders_candidates_by_distance() -> None:
    payload = {
        "count": 3,
        "reference": {"name": "Sol"},
        "results": [
            _body_payload(1, "Far", 30.0),
            _body_payload(2, "Near", 5.0),
            _body_payload(3, "Middle", 10.0),
        ],
    }
    lookup = _FakePopulationLookup()
    state = MiningState(current_system="Sol")
    client = SpanshHotspotClient(
        state,
        session=_FakeSession(payload),
        min_interval_seconds=0,
        population_lookup=lookup,
    )

    client.search_hotspots(
        distance_min=0.0,
        distance_max=100.0,
        ring_signals=[],
        reserve_levels=[],
        ring_types=[],
        population_filter="none",
    )

    assert lookup.lookup_calls == [[2, 3, 1]]
    assert lookup.allow_live_calls == [True]
    assert lookup.live_limit_calls == [50]


def test_search_hotspots_forwards_population_progress_callback() -> None:
    payload = {
        "count": 2,
        "reference": {"name": "Sol"},
        "results": [
            _body_payload(1, "Far", 30.0),
            _body_payload(2, "Near", 5.0),
        ],
    }
    lookup = _FakePopulationLookup()
    state = MiningState(current_system="Sol")
    client = SpanshHotspotClient(
        state,
        session=_FakeSession(payload),
        min_interval_seconds=0,
        population_lookup=lookup,
    )
    progress: list[tuple[int, int]] = []

    client.search_hotspots(
        distance_min=0.0,
        distance_max=100.0,
        ring_signals=[],
        reserve_levels=[],
        ring_types=[],
        population_filter="none",
        population_progress_callback=lambda current, total: progress.append((current, total)),
    )

    assert lookup.progress_callback_calls[0] is not None
    assert lookup.lookup_calls == [[2, 1]]
    assert progress == [(1, 2), (2, 2)]


def test_population_lookup_resolves_cache_path_after_plugin_dir_is_set(tmp_path) -> None:
    payload = {
        "count": 1,
        "reference": {"name": "Sol"},
        "results": [_body_payload(1, "LatePluginDir", 1.0)],
    }
    state = MiningState(current_system="Sol")
    session = _FakeSession(payload, system_payloads={1: {"population": 0}})
    client = SpanshHotspotClient(state, session=session, min_interval_seconds=0)

    state.plugin_dir = tmp_path
    result = client.search_hotspots(
        distance_min=0.0,
        distance_max=100.0,
        ring_signals=[],
        reserve_levels=[],
        ring_types=[],
        population_filter="none",
    )

    assert result.entries[0].population == 0
    assert (tmp_path / "cache" / "spansh_system_population.json").is_file()
    assert any("/api/system/1" in request[0] for request in session.requests)
    assert not any("/api/systems/search" in request[0] for request in session.requests)


def _body_payload(system_id64: int, system_name: str, distance: float):
    return {
        "system_id64": system_id64,
        "system_name": system_name,
        "name": f"{system_name} 1",
        "distance": distance,
        "distance_to_arrival": 100.0,
        "rings": [
            {
                "name": f"{system_name} 1 A Ring",
                "type": "Metallic",
                "signals": [{"name": "Platinum", "count": 2}],
            }
        ],
    }
