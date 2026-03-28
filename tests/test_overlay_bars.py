from datetime import datetime, timedelta, timezone

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


def test_overlay_rpm_metric_uses_live_fixed_lookback_value() -> None:
    state = MiningState()
    helper = EdmcOverlayHelper(state)
    now = datetime(2026, 3, 28, 12, 0, 0, tzinfo=timezone.utc)
    state.recent_refinements.extend(
        [
            now - timedelta(seconds=61),
            now - timedelta(seconds=45),
            now - timedelta(seconds=10),
        ]
    )
    state.rpm_display_value = 4.2
    state.rpm_display_color = "#123456"

    metric = helper._build_rpm_metric(now)
    follow_up_metric = helper._build_rpm_metric(now + timedelta(seconds=30))

    assert metric.value == "4.2"
    assert metric.color == "#123456"
    assert follow_up_metric.value == "4.2"
    assert len(state.recent_refinements) == 0
