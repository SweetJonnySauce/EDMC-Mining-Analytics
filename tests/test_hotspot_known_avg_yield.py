from edmc_mining_analytics.mining_ui.hotspot_search_window import HotspotSearchWindow


def test_build_known_avg_yield_index_aggregates_weighted_by_asteroids() -> None:
    rows = [
        {
            "session_guid": "s1",
            "ring_name": "Ring A",
            "commodity_name": "Platinum",
            "asteroids_prospected": 3,
            "sum_percentage": 90.0,
        },
        {
            "session_guid": "s2",
            "ring_name": "Ring A",
            "commodity_name": "Platinum",
            "asteroids_prospected": 5,
            "sum_percentage": 100.0,
        },
        {
            "session_guid": "s3",
            "ring_name": "Ring A",
            "commodity_name": "Gold",
            "asteroids_prospected": 2,
            "sum_percentage": 20.0,
        },
    ]

    index = HotspotSearchWindow._build_known_avg_yield_index(rows)

    assert index[("ring a", "platinum")] == 23.75
    assert index[("ring a", "gold")] == 10.0


def test_lookup_known_avg_yield_uses_ring_candidates() -> None:
    index = {
        ("synuefe uz-o c22-10 9 a ring", "platinum"): 37.65,
        ("synuefe uz-o c22-10", "platinum"): 39.32,
    }

    value = HotspotSearchWindow._lookup_known_avg_yield(
        index,
        "Platinum",
        ["Synuefe UZ-O c22-10 9 A Ring", "Synuefe UZ-O c22-10"],
    )
    assert value == 37.65

    fallback_value = HotspotSearchWindow._lookup_known_avg_yield(
        index,
        "Platinum",
        ["Unknown Ring", "Synuefe UZ-O c22-10"],
    )
    assert fallback_value == 39.32


def test_format_avg_yield_percentage_prefers_integer_when_possible() -> None:
    assert HotspotSearchWindow._format_avg_yield_percentage(14.0) == "14%"
    assert HotspotSearchWindow._format_avg_yield_percentage(36.24) == "36.2%"
    assert HotspotSearchWindow._format_avg_yield_percentage(None) is None
