import json
import logging
from types import SimpleNamespace

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


def test_load_known_avg_yield_index_reads_ring_summary_file(tmp_path) -> None:
    session_dir = tmp_path / "session_data"
    session_dir.mkdir()
    ring_summary_path = session_dir / "ring_summary.jsonl"
    rows = [
        {
            "ring_name": "Col 285 Sector LB-O c6-3 A 8 A Ring",
            "commodity_name": "Platinum",
            "asteroids_prospected": 98,
            "asteroids_with_commodity_present": 44,
            "sum_percentage": 1303.284618,
        }
    ]
    ring_summary_path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    window = HotspotSearchWindow.__new__(HotspotSearchWindow)
    window._controller = SimpleNamespace(state=SimpleNamespace(plugin_dir=tmp_path))
    window._ring_summary_avg_cache = {}
    window._ring_summary_avg_mtime_ns = None

    index = window._load_known_avg_yield_index(HotspotSearchWindow.YIELD_BASIS_ALL)

    assert round(index[("col 285 sector lb-o c6-3 a 8 a ring", "platinum")], 3) == 13.299


def test_load_known_avg_yield_index_logs_debug_for_invalid_row(tmp_path, caplog) -> None:
    session_dir = tmp_path / "session_data"
    session_dir.mkdir()
    ring_summary_path = session_dir / "ring_summary.jsonl"
    ring_summary_path.write_text(
        "{not valid json}\n"
        + json.dumps(
            {
                "ring_name": "Ring A",
                "commodity_name": "Platinum",
                "asteroids_prospected": 4,
                "asteroids_with_commodity_present": 2,
                "sum_percentage": 40.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    window = HotspotSearchWindow.__new__(HotspotSearchWindow)
    window._controller = SimpleNamespace(state=SimpleNamespace(plugin_dir=tmp_path))
    window._ring_summary_avg_cache = {}
    window._ring_summary_avg_mtime_ns = None

    with caplog.at_level(logging.DEBUG, logger="edmc_mining_analytics.ui"):
        index = window._load_known_avg_yield_index(HotspotSearchWindow.YIELD_BASIS_ALL)

    assert index[("ring a", "platinum")] == 10.0
    assert "Skipping invalid ring summary row" in caplog.text
