from edmc_mining_analytics.state import MiningState, recompute_market_sell_totals


def test_recompute_market_sell_totals() -> None:
    state = MiningState()
    state.cargo_totals = {"platinum": 10, "gold": 5, "silver": 2}
    state.market_sell_prices = {"platinum": 1_000_000, "gold": 500_000}

    recompute_market_sell_totals(state)

    assert state.market_sell_totals["platinum"] == 10_000_000
    assert state.market_sell_totals["gold"] == 2_500_000
    assert "silver" not in state.market_sell_totals
    assert state.market_sell_total == 12_500_000
