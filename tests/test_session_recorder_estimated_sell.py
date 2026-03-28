from datetime import datetime, timezone

import pytest

from edmc_mining_analytics.session_recorder import SessionRecorder
from edmc_mining_analytics.state import MiningState


def _build_state() -> MiningState:
    state = MiningState()
    state.mining_start = datetime(2026, 3, 26, 22, 0, 0, tzinfo=timezone.utc)
    state.mining_end = datetime(2026, 3, 26, 23, 0, 0, tzinfo=timezone.utc)
    state.current_system = "Sol"
    state.current_ship = "Type-11 Prospector"
    return state


def test_session_payload_includes_estimated_sell_full_coverage() -> None:
    state = _build_state()
    state.cargo_totals = {"platinum": 10, "gold": 5}
    state.commodity_display_names = {"platinum": "Platinum", "gold": "Gold"}
    state.market_search_sort_mode = "best_price"
    state.market_search_has_large_pad = True
    state.market_search_include_carriers = False
    state.market_search_include_surface = True
    state.market_search_min_demand = 1250
    state.market_search_age_days = 14
    state.market_search_distance_ly = 88.5
    state.market_search_distance_ls = 4200.0
    state.market_sell_prices = {"platinum": 1_000_000.0, "gold": 500_000.0}
    state.market_sell_totals = {"platinum": 10_000_000.0, "gold": 2_500_000.0}
    state.market_sell_total = 12_500_000.0
    state.market_sell_details = {
        "platinum": {
            "system_name": "Sol",
            "station_name": "Jameson Memorial",
            "market_updated_at": "2026-03-26T23:00:00Z",
            "distance_ly": 12.5,
            "distance_to_arrival": 500.0,
        }
    }

    payload = SessionRecorder(state)._build_payload()
    estimated = payload["meta"]["estimated_sell"]

    assert estimated["sort_mode"] == "best_price"
    assert estimated["total_value_cr"] == pytest.approx(12_500_000.0)
    assert estimated["priced_commodities"] == 2
    assert estimated["unpriced_commodities"] == 0
    assert estimated["priced_tons"] == pytest.approx(15.0)
    assert estimated["total_tons"] == pytest.approx(15.0)
    assert estimated["coverage_ratio"] == pytest.approx(1.0)
    assert len(estimated["by_commodity"]) == 2
    assert estimated["by_commodity"][0]["name"] == "Platinum"
    assert estimated["by_commodity"][0]["price_source"]["station_name"] == "Jameson Memorial"
    criteria = estimated["search_criteria"]
    assert criteria["sort_mode"] == "best_price"
    assert criteria["reference_system"] == "Sol"
    assert criteria["has_large_pad"] is True
    assert criteria["include_carriers"] is False
    assert criteria["include_surface"] is True
    assert criteria["min_demand"] == 1250
    assert criteria["age_days"] == 14
    assert criteria["distance_ly"] == pytest.approx(88.5)
    assert criteria["distance_ls"] == pytest.approx(4200.0)


def test_session_payload_includes_estimated_sell_partial_coverage() -> None:
    state = _build_state()
    state.cargo_totals = {"platinum": 10, "gold": 5, "silver": 2}
    state.commodity_display_names = {"platinum": "Platinum", "gold": "Gold", "silver": "Silver"}
    state.market_search_sort_mode = "nearest"
    state.market_search_has_large_pad = None
    state.market_search_include_carriers = True
    state.market_search_include_surface = False
    state.market_search_min_demand = 0
    state.market_search_age_days = 30
    state.market_search_distance_ly = 100.0
    state.market_search_distance_ls = None
    state.market_sell_prices = {"platinum": 1_000_000.0, "gold": 500_000.0}
    state.market_sell_totals = {"platinum": 10_000_000.0, "gold": 2_500_000.0}
    state.market_sell_total = 12_500_000.0

    payload = SessionRecorder(state)._build_payload()
    estimated = payload["meta"]["estimated_sell"]

    assert estimated["sort_mode"] == "nearest"
    assert estimated["total_value_cr"] == pytest.approx(12_500_000.0)
    assert estimated["priced_commodities"] == 2
    assert estimated["unpriced_commodities"] == 1
    assert estimated["priced_tons"] == pytest.approx(15.0)
    assert estimated["total_tons"] == pytest.approx(17.0)
    assert estimated["coverage_ratio"] == pytest.approx(15.0 / 17.0)
    silver = next(entry for entry in estimated["by_commodity"] if entry["name"] == "Silver")
    assert silver["sell_price"] is None
    assert silver["estimated_value_cr"] is None
    criteria = estimated["search_criteria"]
    assert criteria["sort_mode"] == "nearest"
    assert criteria["has_large_pad"] is False
    assert criteria["include_carriers"] is True
    assert criteria["include_surface"] is False
    assert criteria["distance_ls"] is None


def test_session_payload_includes_estimated_sell_empty_prices() -> None:
    state = _build_state()
    state.cargo_totals = {"methanolmonohydratecrystals": 12}
    state.commodity_display_names = {"methanolmonohydratecrystals": "Methanol Monohydrate Crystals"}

    payload = SessionRecorder(state)._build_payload()
    estimated = payload["meta"]["estimated_sell"]

    assert estimated["total_value_cr"] == pytest.approx(0.0)
    assert estimated["priced_commodities"] == 0
    assert estimated["unpriced_commodities"] == 1
    assert estimated["priced_tons"] == pytest.approx(0.0)
    assert estimated["total_tons"] == pytest.approx(12.0)
    assert estimated["coverage_ratio"] == pytest.approx(0.0)
