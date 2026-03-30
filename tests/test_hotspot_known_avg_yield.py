from edmc_mining_analytics.mining_ui.hotspot_search_window import HotspotSearchWindow
from edmc_mining_analytics.integrations.spansh_hotspots import RingHotspot


def test_build_known_avg_yield_index_aggregates_weighted_by_asteroids() -> None:
    rows = [
        {
            "session_guid": "s1",
            "ring_name": "Ring A",
            "commodity_name": "Platinum",
            "asteroids_prospected": 3,
            "asteroids_with_commodity_present": 3,
            "sum_percentage": 90.0,
        },
        {
            "session_guid": "s2",
            "ring_name": "Ring A",
            "commodity_name": "Platinum",
            "asteroids_prospected": 5,
            "asteroids_with_commodity_present": 5,
            "sum_percentage": 100.0,
        },
        {
            "session_guid": "s3",
            "ring_name": "Ring A",
            "commodity_name": "Gold",
            "asteroids_prospected": 2,
            "asteroids_with_commodity_present": 2,
            "sum_percentage": 20.0,
        },
    ]

    index = HotspotSearchWindow._build_known_avg_yield_index(rows, "all")

    assert index[("ring a", "platinum")] == 23.75
    assert index[("ring a", "gold")] == 10.0


def test_build_known_avg_yield_index_supports_present_basis() -> None:
    rows = [
        {
            "ring_name": "Ring A",
            "commodity_name": "Platinum",
            "asteroids_prospected": 10,
            "asteroids_with_commodity_present": 4,
            "sum_percentage": 200.0,
        },
        {
            "ring_name": "Ring A",
            "commodity_name": "Platinum",
            "asteroids_prospected": 5,
            "asteroids_with_commodity_present": 1,
            "sum_percentage": 20.0,
        },
    ]

    index_all = HotspotSearchWindow._build_known_avg_yield_index(rows, "all")
    index_present = HotspotSearchWindow._build_known_avg_yield_index(rows, "present")

    # All asteroids: 220 / (10 + 5) = 14.666...
    assert round(index_all[("ring a", "platinum")], 3) == 14.667
    # Only with commodity: 220 / (4 + 1) = 44
    assert index_present[("ring a", "platinum")] == 44.0


def test_lookup_known_avg_yield_requires_full_ring_match_candidates() -> None:
    index = {
        ("synuefe uz-o c22-10 9 a ring", "platinum"): 37.65,
        ("synuefe uz-o c22-10", "platinum"): 39.32,
    }

    entry = RingHotspot(
        system_name="Synuefe UZ-O c22-10",
        body_name="Synuefe UZ-O c22-10 9",
        ring_name="Synuefe UZ-O c22-10 9 A Ring",
        ring_type="Metallic",
        distance_ls=1000.0,
        distance_ly=10.0,
        signals=tuple(),
    )
    candidates = HotspotSearchWindow._build_ring_lookup_candidates(entry)

    value = HotspotSearchWindow._lookup_known_avg_yield(
        index,
        "Platinum",
        candidates,
    )
    assert value == 37.65

    assert "Synuefe UZ-O c22-10" not in candidates

    system_only_index = {("synuefe uz-o c22-10", "platinum"): 39.32}
    no_match = HotspotSearchWindow._lookup_known_avg_yield(
        system_only_index,
        "Platinum",
        candidates,
    )
    assert no_match is None


def test_format_avg_yield_percentage_prefers_integer_when_possible() -> None:
    assert HotspotSearchWindow._format_avg_yield_percentage(14.0) == "14%"
    assert HotspotSearchWindow._format_avg_yield_percentage(36.24) == "36.2%"
    assert HotspotSearchWindow._format_avg_yield_percentage(None) is None
