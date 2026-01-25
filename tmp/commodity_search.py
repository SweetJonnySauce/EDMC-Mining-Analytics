"""Quick Spansh station search for a commodity (default: Platinum)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import requests


API_BASE = "https://spansh.co.uk/api"
DEFAULT_ENDPOINT = f"{API_BASE}/stations/search"
# Spansh does not publish stable public docs; adjust this key if needed.
DEFAULT_COMMODITY_FILTER_KEY = os.environ.get("SPANSH_COMMODITY_FILTER", "commodities")
DEFAULT_TIMEOUT = 15
DEFAULT_OUTPUT_PATH = os.path.join("tmp", "commodity_search.json")
DEFAULT_PARAMS_PATH = os.path.join("tmp", "search_params.json")
DEFAULT_TABLE_PATH = os.path.join("tmp", "commodity_search_table.md")
DEFAULT_MARKET_RANGE = (0.0, 1_000_000_000.0)
DEFAULT_SORT_MODE = "nearest"
PARAM_FILTER_SKIP = {
    "commodity",
    "reference_system",
    "distance_ly",
    "distance_to_arrival_ls",
    "distance_min_ly",
    "distance_max_ly",
    "min_demand",
    "market_age_days",
    "market_updated_at",
    "market",
    "sort_mode",
}


def _coerce_range(value: object) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None


def build_market_filters(market_spec: object) -> list[Dict[str, Any]]:
    items: list[Dict[str, Any]] = []

    if isinstance(market_spec, list):
        candidates = market_spec
    elif isinstance(market_spec, dict):
        if "name" in market_spec:
            candidates = [market_spec]
        else:
            candidates = []
            for name, fields in market_spec.items():
                if not isinstance(fields, dict):
                    continue
                entry: Dict[str, Any] = {"name": str(name)}
                for field in ("buy_price", "sell_price", "demand", "supply"):
                    rng = _coerce_range(fields.get(field))
                    if rng is not None:
                        entry[field] = {"comparison": "<=>", "value": [rng[0], rng[1]]}
                if len(entry) > 1:
                    candidates.append(entry)
    else:
        candidates = []

    for candidate in candidates:
        if not isinstance(candidate, dict) or "name" not in candidate:
            continue
        entry: Dict[str, Any] = {"name": candidate["name"]}
        for field in ("buy_price", "sell_price", "demand", "supply"):
            if field not in candidate:
                continue
            raw = candidate[field]
            if isinstance(raw, dict) and "value" in raw:
                entry[field] = raw
                continue
            rng = _coerce_range(raw)
            if rng is not None:
                entry[field] = {"comparison": "<=>", "value": [rng[0], rng[1]]}
        if len(entry) > 1:
            items.append(entry)

    return items


def parse_market_updated_at(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def build_payload(commodity: str, filter_key: str, size: int, page: int) -> Dict[str, Any]:
    cleaned = commodity.strip()
    if not cleaned:
        raise ValueError("Commodity name cannot be empty.")

    return {
        "filters": {
            filter_key: {"value": [cleaned]},
        },
        "sort": [{"distance": {"direction": "asc"}}],
        "size": max(1, min(int(size), 200)),
        "page": max(0, int(page)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search Spansh stations for a commodity.")
    parser.add_argument("--commodity", default=None, help="Commodity name (default: from params or Platinum).")
    parser.add_argument(
        "--filter-key",
        default=DEFAULT_COMMODITY_FILTER_KEY,
        help="Spansh filter field for commodities (default from $SPANSH_COMMODITY_FILTER or 'commodities').",
    )
    parser.add_argument(
        "--reference-system",
        default=None,
        help="Reference system for distance-based searches (default: from params).",
    )
    parser.add_argument("--size", type=int, default=25, help="Result size (default: 25).")
    parser.add_argument("--page", type=int, default=0, help="Result page (default: 0).")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Spansh stations search endpoint.")
    parser.add_argument(
        "--sort-mode",
        default=None,
        help="Sort mode: best_price or nearest (default: from params or nearest).",
    )
    parser.add_argument("--raw", action="store_true", help="Print raw JSON without trimming.")
    parser.add_argument(
        "--params",
        default=DEFAULT_PARAMS_PATH,
        help=f"Path to search params JSON (default: {DEFAULT_PARAMS_PATH}).",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        help=f"Write response JSON to this file (default: {DEFAULT_OUTPUT_PATH}).",
    )
    parser.add_argument(
        "--table-output",
        default=DEFAULT_TABLE_PATH,
        help=f"Write a markdown table to this file (default: {DEFAULT_TABLE_PATH}).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    params: Dict[str, Any] = {}
    if args.params and os.path.exists(args.params):
        try:
            with open(args.params, "r", encoding="utf-8") as handle:
                params = json.load(handle) or {}
        except (OSError, ValueError) as exc:
            print(f"error: unable to read params file {args.params!r}: {exc}", file=sys.stderr)
            return 2

    commodity = args.commodity or str(params.get("commodity") or "Platinum")
    reference_system = args.reference_system or str(params.get("reference_system") or "").strip()
    sort_mode = (args.sort_mode or params.get("sort_mode") or DEFAULT_SORT_MODE).strip().lower()

    try:
        payload = build_payload(commodity, args.filter_key, args.size, args.page)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if sort_mode == "best_price":
        if not commodity:
            print("error: best_price sorting requires a commodity name.", file=sys.stderr)
            return 2
        payload["sort"] = [
            {"market_sell_price": [{"name": commodity, "direction": "desc"}]},
            {"distance": {"direction": "asc"}},
        ]
    elif sort_mode == "nearest":
        payload["sort"] = [{"distance": {"direction": "asc"}}]
    else:
        print(f"error: invalid sort_mode {sort_mode!r} (use 'best_price' or 'nearest')", file=sys.stderr)
        return 2
    if reference_system:
        payload["reference_system"] = reference_system

    distance_min = params.get("distance_min_ly")
    distance_max = params.get("distance_max_ly")
    if distance_min is None and distance_max is None:
        distance_max = params.get("distance_ly")
    if distance_min is not None or distance_max is not None:
        min_val = float(distance_min) if distance_min is not None else 0.0
        max_val = float(distance_max) if distance_max is not None else min_val
        if max_val < min_val:
            min_val, max_val = max_val, min_val
        payload.setdefault("filters", {})["distance"] = {"min": min_val, "max": max_val}

    distance_to_arrival = params.get("distance_to_arrival_ls")
    if distance_to_arrival is not None:
        try:
            max_arrival = float(distance_to_arrival)
        except (TypeError, ValueError):
            print(f"error: invalid distance_to_arrival_ls {distance_to_arrival!r}", file=sys.stderr)
            return 2
        payload.setdefault("filters", {})["distance_to_arrival"] = {"min": 0.0, "max": max_arrival}

    filters = payload.setdefault("filters", {})
    market_spec = params.get("market")
    market_filters = build_market_filters(market_spec)
    if market_filters:
        filters["market"] = market_filters

    if "market" not in filters and commodity:
        filters["market"] = [
            {
                "name": commodity,
                "supply": {"comparison": "<=>", "value": [DEFAULT_MARKET_RANGE[0], DEFAULT_MARKET_RANGE[1]]},
            }
        ]

    min_demand = params.get("min_demand")
    if min_demand is not None and "market" in filters:
        try:
            min_demand_value = float(min_demand)
        except (TypeError, ValueError):
            print(f"error: invalid min_demand {min_demand!r}", file=sys.stderr)
            return 2
        for entry in filters.get("market", []):
            if not isinstance(entry, dict):
                continue
            existing = entry.get("demand")
            if isinstance(existing, dict):
                value = existing.get("value")
                if isinstance(value, list) and len(value) == 2:
                    value[0] = max(min_demand_value, value[0])
                else:
                    entry["demand"] = {
                        "comparison": "<=>",
                        "value": [min_demand_value, DEFAULT_MARKET_RANGE[1]],
                    }
            else:
                entry["demand"] = {
                    "comparison": "<=>",
                    "value": [min_demand_value, DEFAULT_MARKET_RANGE[1]],
                }

    market_age_days = params.get("market_age_days")
    cutoff: datetime | None = None
    if market_age_days is not None and "market_updated_at" not in filters:
        try:
            days = float(market_age_days)
        except (TypeError, ValueError):
            print(f"error: invalid market_age_days {market_age_days!r}", file=sys.stderr)
            return 2
        now = datetime.now(timezone.utc)
        end_date = now.date()
        start_date = (now - timedelta(days=days)).date()
        filters["market_updated_at"] = {
            "comparison": "<=>",
            "value": [start_date.isoformat(), end_date.isoformat()],
        }
        cutoff = now - timedelta(days=days)

    raw_filters = params.get("filters")
    if isinstance(raw_filters, dict):
        for key, value in raw_filters.items():
            if key not in filters:
                filters[key] = value

    for key, value in params.items():
        if key in PARAM_FILTER_SKIP or key == "filters":
            continue
        if value is None or key in filters:
            continue
        if isinstance(value, dict):
            filters[key] = value
        else:
            filters[key] = {"value": value}

    try:
        response = requests.post(args.endpoint, json=payload, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        print(f"error: request failed: {exc}", file=sys.stderr)
        return 1

    if response.status_code != 200:
        print(f"error: HTTP {response.status_code}", file=sys.stderr)
        print(response.text, file=sys.stderr)
        return 1

    try:
        data = response.json()
    except ValueError:
        print(response.text)
        return 0

    if distance_to_arrival is not None:
        try:
            max_arrival = float(distance_to_arrival)
        except (TypeError, ValueError):
            print(f"error: invalid distance_to_arrival_ls {distance_to_arrival!r}", file=sys.stderr)
            return 2
        filtered_results = []
        dropped = 0
        for result in data.get("results") or []:
            if not isinstance(result, dict):
                continue
            value = result.get("distance_to_arrival")
            if value is None:
                filtered_results.append(result)
                continue
            try:
                if float(value) <= max_arrival:
                    filtered_results.append(result)
                else:
                    dropped += 1
            except (TypeError, ValueError):
                filtered_results.append(result)
        if dropped:
            print(f"warning: API returned {dropped} station(s) beyond distance_to_arrival_ls; filtered client-side.", file=sys.stderr)
        data["results"] = filtered_results
        data["count"] = len(filtered_results)

    if market_age_days is not None and cutoff is not None:
        filtered_results = []
        dropped = 0
        for result in data.get("results") or []:
            if not isinstance(result, dict):
                continue
            updated_at = parse_market_updated_at(result.get("market_updated_at"))
            if updated_at and updated_at >= cutoff:
                filtered_results.append(result)
            else:
                dropped += 1
        if dropped:
            print(f"warning: API returned {dropped} stale market(s); filtered client-side.", file=sys.stderr)
        data["results"] = filtered_results
        data["count"] = len(filtered_results)

    if args.raw:
        print(json.dumps(data, indent=2, sort_keys=True))
        write_payload = json.dumps(data, indent=2, sort_keys=True)
    else:
        count = int(data.get("count") or 0)
        results = data.get("results") or []
        print(f"count={count} results={len(results)} filter_key={args.filter_key!r}")
        print(json.dumps(results[:5], indent=2, sort_keys=True))
        write_payload = json.dumps(data, indent=2, sort_keys=True)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    try:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(write_payload)
    except OSError as exc:
        print(f"error: unable to write {args.output!r}: {exc}", file=sys.stderr)
        return 1

    print(f"saved={args.output}")

    commodity_target = commodity.lower() if commodity else ""
    table_rows = [
        [
            "System Name",
            "Station",
            "Distance (LY)",
            "Distance to Arrival (LS)",
            "Has Large Pad",
            "Commodity",
            "Sell Price",
            "Demand",
            "Market Updated At",
        ]
    ]

    results = data.get("results") or []
    for result in results:
        if not isinstance(result, dict):
            continue
        market_entries = result.get("market") or []
        if not isinstance(market_entries, list):
            market_entries = []
        if commodity_target:
            match = next(
                (
                    entry
                    for entry in market_entries
                    if isinstance(entry, dict)
                    and str(entry.get("commodity") or "").lower() == commodity_target
                ),
                None,
            )
            if not match:
                continue
            entries = [match]
        else:
            entries = [entry for entry in market_entries if isinstance(entry, dict)]

        for entry in entries:
            table_rows.append(
                [
                    str(result.get("system_name") or ""),
                    str(result.get("name") or ""),
                    str(result.get("distance") or ""),
                    str(result.get("distance_to_arrival") or ""),
                    str(result.get("has_large_pad") or ""),
                    str(entry.get("commodity") or ""),
                    str(entry.get("sell_price") or ""),
                    str(entry.get("demand") or ""),
                    str(result.get("market_updated_at") or ""),
                ]
            )

    def escape(value: str) -> str:
        return value.replace("|", "\\|")

    if len(table_rows) > 1:
        header = "| " + " | ".join(escape(cell) for cell in table_rows[0]) + " |"
        separator = "| " + " | ".join("---" for _ in table_rows[0]) + " |"
        lines = [header, separator]
        for row in table_rows[1:]:
            lines.append("| " + " | ".join(escape(cell) for cell in row) + " |")
        table_content = "\n".join(lines) + "\n"
        os.makedirs(os.path.dirname(args.table_output) or ".", exist_ok=True)
        with open(args.table_output, "w", encoding="utf-8") as handle:
            handle.write(table_content)
        print(f"table_saved={args.table_output}")
    else:
        print("table_saved=none (no matching market entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
