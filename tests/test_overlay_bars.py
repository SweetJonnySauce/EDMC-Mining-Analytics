from datetime import datetime, timedelta, timezone

from edmc_mining_analytics.integrations.edmcoverlay import EdmcOverlayHelper
from edmc_mining_analytics.state import MiningSessionKind, MiningState


class _OverlayClientStub:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []
        self.shapes: list[dict[str, object]] = []

    def send_message(self, message_id: str, text: str, color: str, x: int, y: int, **kwargs: object) -> None:
        self.messages.append({
            "id": message_id,
            "text": text,
            "color": color,
            "x": x,
            "y": y,
            **kwargs,
        })

    def send_shape(self, **kwargs: object) -> None:
        self.shapes.append(kwargs)


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


def test_surface_overlay_uses_rhino_capacity_for_bars_and_percent_full() -> None:
    state = MiningState()
    state.mining_session_kind = MiningSessionKind.SURFACE
    state.cargo_capacity = 168
    state.current_cargo_tonnage = 36
    state.overlay_show_bars = True
    state.cargo_totals = {"gold": 36}
    state.harvested_commodities = {"gold"}

    helper = EdmcOverlayHelper(state)
    bars = helper._build_overlay_bars()

    assert bars[0].percent == 50.0
    assert helper._compute_percent_full() == 50.0


def test_overlay_bar_quantity_follows_bar_and_clears_with_removed_row() -> None:
    state = MiningState()
    state.overlay_show_bars = True
    state.cargo_capacity = 100
    state.cargo_totals = {"platinum": 30}
    state.harvested_commodities = {"platinum"}
    helper = EdmcOverlayHelper(state)
    client = _OverlayClientStub()
    bars = helper._build_overlay_bars()

    helper._dispatch_overlay_bars(client, bars, anchor_x=10, anchor_y=20, ttl=5, metrics_count=5)

    quantity = next(message for message in client.messages if message["id"] == "edmcma.bar.0.quantity")
    assert quantity["text"] == "(30t)"
    assert quantity["color"] == "#ff6f00"
    assert quantity["x"] == 204

    helper._dispatch_overlay_bars(client, [], anchor_x=10, anchor_y=20, ttl=5, metrics_count=5)

    cleared_quantity = [
        message for message in client.messages
        if message["id"] == "edmcma.bar.0.quantity" and message["text"] == ""
    ]
    assert len(cleared_quantity) == 1
    assert cleared_quantity[0]["ttl"] == 1


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
