from datetime import datetime, timezone

from edmc_mining_analytics.integrations.spansh_market import (
    MarketSearchPreferences,
    SpanshMarketClient,
)
import edmc_mining_analytics.integrations.spansh_market as spansh_market


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        return datetime(3300, 1, 2, tzinfo=timezone.utc)


def test_build_payload_best_price(monkeypatch) -> None:
    monkeypatch.setattr(spansh_market, "datetime", _FixedDateTime)

    prefs = MarketSearchPreferences(
        has_large_pad=True,
        min_demand=1000,
        age_days=1,
        distance_ly=100.0,
        distance_to_arrival_ls=5000.0,
        sort_mode="best_price",
        include_carriers=True,
        include_surface=True,
    )
    client = SpanshMarketClient()
    payload = client._build_payload("Platinum", "Sol", prefs)

    assert payload["reference_system"] == "Sol"
    filters = payload["filters"]
    assert filters["has_market"]["value"] is True
    assert filters["distance_to_arrival"] == {"comparison": "<=>", "value": [0.0, 5000.0]}
    assert filters["has_large_pad"]["value"] is True
    assert filters["distance"] == {"min": 0.0, "max": 100.0}
    assert filters["market_updated_at"]["value"] == ["now-1d", "now"]
    assert filters["market"][0]["name"] == "Platinum"
    assert filters["market"][0]["demand"]["comparison"] == "<=>"
    assert filters["market"][0]["demand"]["value"][0] == 1000
    assert "supply" not in filters["market"][0]
    assert payload["sort"][0]["market_sell_price"][0]["name"] == "Platinum"
    assert payload["sort"][0]["market_sell_price"][0]["direction"] == "desc"
    expected_types = set(
        spansh_market.STATION_TYPES
        + spansh_market.CARRIER_TYPES
        + spansh_market.SURFACE_TYPES
    )
    assert set(filters["type"]["value"]) == expected_types


def test_build_payload_nearest(monkeypatch) -> None:
    monkeypatch.setattr(spansh_market, "datetime", _FixedDateTime)

    prefs = MarketSearchPreferences(
        has_large_pad=None,
        min_demand=0,
        age_days=0,
        distance_ly=None,
        distance_to_arrival_ls=None,
        sort_mode="nearest",
        include_carriers=False,
        include_surface=False,
    )
    client = SpanshMarketClient()
    payload = client._build_payload("Gold", "Sol", prefs)

    filters = payload["filters"]
    assert "has_large_pad" not in filters
    assert "distance" not in filters
    assert "distance_to_arrival" not in filters
    assert "market_updated_at" not in filters
    assert payload["sort"] == [{"distance": {"direction": "asc"}}]
    assert filters["type"]["value"] == list(spansh_market.STATION_TYPES)
