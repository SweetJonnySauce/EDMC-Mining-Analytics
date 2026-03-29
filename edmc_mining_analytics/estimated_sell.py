"""Shared helpers for estimated sell/profit calculations."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from .state import MiningState, resolve_commodity_display_name


def build_estimated_sell_breakdown(
    state: MiningState,
    *,
    quantities_by_commodity: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build priced commodity rows and totals for estimated sell value.

    Quantity source priority:
    1) explicit ``quantities_by_commodity`` if provided
    2) ``state.last_cargo_counts`` (end inventory snapshot)
    3) ``state.cargo_totals`` (session mined totals fallback)
    """

    if quantities_by_commodity is None:
        if state.last_cargo_counts:
            quantity_source: Mapping[str, Any] = state.last_cargo_counts
        else:
            quantity_source = state.cargo_totals
    else:
        quantity_source = quantities_by_commodity

    by_commodity: list[dict[str, Any]] = []
    priced_tons = 0.0
    total_tons = 0.0

    for commodity_key, tons_raw in sorted(quantity_source.items()):
        key = str(commodity_key or "").strip().lower()
        if not key or key == "drones":
            continue
        try:
            tons = float(tons_raw)
        except (TypeError, ValueError):
            continue
        if tons <= 0:
            continue

        total_tons += tons
        sell_price_raw = state.market_sell_prices.get(key)

        sell_price: Optional[float]
        try:
            sell_price = float(sell_price_raw) if sell_price_raw is not None else None
        except (TypeError, ValueError):
            sell_price = None

        estimated_value_cr: Optional[float]
        if sell_price is None:
            estimated_value_cr = None
        else:
            estimated_value_cr = sell_price * tons
            priced_tons += tons

        detail = state.market_sell_details.get(key, {})
        source: Optional[dict[str, Any]] = None
        if isinstance(detail, dict):
            source_candidate = {
                "system_name": detail.get("system_name"),
                "station_name": detail.get("station_name"),
                "market_updated_at": detail.get("market_updated_at"),
                "distance_ly": detail.get("distance_ly"),
                "distance_to_arrival": detail.get("distance_to_arrival"),
            }
            source_clean = {field: value for field, value in source_candidate.items() if value is not None}
            if source_clean:
                source = source_clean

        entry: dict[str, Any] = {
            "key": key,
            "name": resolve_commodity_display_name(state, key),
            "tons": tons,
            "sell_price": sell_price,
            "estimated_value_cr": estimated_value_cr,
        }
        if source:
            entry["price_source"] = source
        by_commodity.append(entry)

    by_commodity.sort(
        key=lambda item: (
            item.get("estimated_value_cr") is None,
            -(float(item.get("estimated_value_cr")) if item.get("estimated_value_cr") is not None else 0.0),
            str(item.get("name") or ""),
        )
    )

    priced_entries = [entry for entry in by_commodity if entry.get("sell_price") is not None]
    total_estimated_value_cr = sum(
        float(entry.get("estimated_value_cr") or 0.0)
        for entry in by_commodity
        if entry.get("estimated_value_cr") is not None
    )

    coverage_ratio: Optional[float]
    if total_tons > 0:
        coverage_ratio = priced_tons / total_tons
    else:
        coverage_ratio = None

    return {
        "by_commodity": by_commodity,
        "total_estimated_value_cr": total_estimated_value_cr,
        "priced_commodities": len(priced_entries),
        "unpriced_commodities": max(0, len(by_commodity) - len(priced_entries)),
        "priced_tons": priced_tons,
        "total_tons": total_tons,
        "coverage_ratio": coverage_ratio,
    }


__all__ = ["build_estimated_sell_breakdown"]
