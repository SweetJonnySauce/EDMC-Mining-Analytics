from edmc_mining_analytics.integrations.edmcoverlay import EdmcOverlayHelper
from edmc_mining_analytics.state import MiningState


def test_overlay_bars_sorted_and_filtered() -> None:
    state = MiningState()
    state.overlay_show_bars = True
    state.cargo_capacity = 100
    state.cargo_totals = {"platinum": 30, "gold": 20, "silver": 20, "painite": 5}
    state.harvested_commodities = {"platinum", "gold", "silver"}
    state.limpets_remaining = 10

    bars = EdmcOverlayHelper(state)._build_overlay_bars()
    labels = [bar.label for bar in bars]

    assert labels == ["Platinum", "Gold", "Silver", "Limpets"]


def test_overlay_bars_respects_max_rows() -> None:
    state = MiningState()
    state.overlay_show_bars = True
    state.cargo_capacity = 100
    state.cargo_totals = {"platinum": 30, "gold": 20, "silver": 20}
    state.harvested_commodities = {"platinum", "gold", "silver"}
    state.limpets_remaining = 10
    state.overlay_bars_max_rows = 2

    bars = EdmcOverlayHelper(state)._build_overlay_bars()
    labels = [bar.label for bar in bars]

    assert labels == ["Platinum", "Gold"]


def test_overlay_bars_hidden_without_capacity() -> None:
    state = MiningState()
    state.overlay_show_bars = True
    state.cargo_capacity = 0
    state.cargo_totals = {"platinum": 30}
    state.harvested_commodities = {"platinum"}
    state.limpets_remaining = 5

    bars = EdmcOverlayHelper(state)._build_overlay_bars()

    assert bars == []


def test_overlay_bars_use_abbreviations_when_available() -> None:
    state = MiningState()
    state.overlay_show_bars = True
    state.cargo_capacity = 100
    state.cargo_totals = {"methanolmonohydratecrystals": 10}
    state.harvested_commodities = {"methanolmonohydratecrystals"}
    state.commodity_abbreviations = {"methanolmonohydratecrystals": "M.M.Crystals"}

    bars = EdmcOverlayHelper(state)._build_overlay_bars()

    assert bars[0].label == "M.M.Crystals"
