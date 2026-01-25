"""Discord integration helpers for EDMC Mining Analytics."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

from ..http_client import get_shared_session
from ..state import MiningState, resolve_commodity_display_name
from ..formatting import format_compact_number
from .discord_image_manager import DiscordImageManager

EMBED_COLOR = 0x1d9bf0
TEST_COLOR = 0x95a5a6


def send_webhook(webhook_url: str, payload: Dict[str, Any]) -> Tuple[bool, str]:
    """Send a JSON payload to the provided Discord webhook URL."""

    if not webhook_url:
        return False, "Webhook URL is empty"
    if not payload:
        return False, "No payload to send"

    session = get_shared_session()
    try:
        response = session.post(webhook_url, json=payload, timeout=5)
    except requests.RequestException as exc:
        return False, str(exc)

    if 200 <= response.status_code < 300:
        return True, ""
    return False, f"HTTP {response.status_code}: {response.reason}"


def build_summary_message(
    state: MiningState,
    payload: Dict[str, Any],
    json_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Construct a Discord embed summarising the mining session."""

    meta = payload.get("meta", {})
    commodities = payload.get("commodities", {})

    commander = meta.get("commander") or state.cmdr_name or "Unknown"
    ship = meta.get("ship") or state.current_ship or "Unknown ship"

    location_info = meta.get("location", {})
    body = location_info.get("body") or state.mining_location or "Unknown body"
    system = location_info.get("system") or state.current_system or "Unknown system"
    ring = meta.get("ring") or state.mining_ring

    base_location = None
    if body and body.strip():
        base_location = body.strip()
    elif system and system.strip():
        base_location = system.strip()
    else:
        base_location = "Unknown"

    ring_suffix = _format_ring_info(
        location_info.get("reserve_level") or meta.get("reserve_level") or state.edsm_reserve_level,
        location_info.get("ring_type") or meta.get("ring_type") or state.edsm_ring_type,
    )
    if ring_suffix:
        location_value = f"{base_location} ({ring_suffix})"
    else:
        location_value = base_location

    fields: List[Dict[str, Any]] = [
        {
            "name": "Location",
            "value": location_value,
            "inline": False,
        }
    ]

    if ring and ring.strip():
        fields.append({"name": "Ring", "value": ring.strip(), "inline": False})

    overall = meta.get("overall_tph", {})
    duration_seconds = _safe_float(meta.get("duration_seconds")) or 0.0
    duration_text = format_duration(duration_seconds)
    total_tons = _safe_float(overall.get("tons"))
    total_text = f"{total_tons:.1f}t" if total_tons is not None else "-"
    tph_value = _safe_float(overall.get("tons_per_hour"))
    tph_text = f"{tph_value:.1f}" if tph_value is not None else "-"
    session_lines = [
        f"Duration: {duration_text}",
        f"Total: {total_text} @ {tph_text} TPH",
    ]
    fields.append({"name": "Session", "value": "\n".join(session_lines), "inline": False})

    inventory = _safe_float(meta.get("inventory_tonnage"))
    capacity = _safe_float(meta.get("cargo_capacity"))
    cargo_lines: List[str] = []
    if inventory is not None or capacity is not None:
        inv_text = f"{inventory:.0f}t" if inventory is not None else "-"
        cap_text = f"{capacity:.0f}t" if capacity is not None else "-"
        if capacity and capacity > 0 and inventory is not None:
            percent = (inventory / capacity) * 100.0
            cargo_lines.append(f"Cargo: {inv_text} / {cap_text} ({percent:.1f}%)")
        else:
            cargo_lines.append(f"Cargo: {inv_text} / {cap_text}")
    limpet_remaining = _safe_int(meta.get("limpets_remaining"))
    if limpet_remaining is not None:
        cargo_lines.append(f"Limpets remaining: {limpet_remaining}")
    if cargo_lines:
        fields.append({"name": "Inventory", "value": "\n".join(cargo_lines), "inline": False})

    prospected_meta = meta.get("prospected", {}) or {}
    content_summary = meta.get("content_summary", {}) or {}
    prospect_lines = []
    total_prospected = _safe_int(prospected_meta.get("total"))
    if total_prospected is not None:
        high = _safe_int(content_summary.get("High"), default=0) or 0
        medium = _safe_int(content_summary.get("Medium"), default=0) or 0
        low = _safe_int(content_summary.get("Low"), default=0) or 0
        prospect_lines.append(
            f"Asteroids: {total_prospected} (High {high}, Medium {medium}, Low {low})"
        )
    launched = _safe_int(meta.get("prospectors_launched"))
    lost = _safe_int(meta.get("prospectors_lost"))
    duplicates = _safe_int(prospected_meta.get("duplicates"))
    collectors = _safe_int(meta.get("collectors_launched"))
    collectors_abandoned = _safe_int(meta.get("collectors_abandoned"))
    if any(value is not None for value in (launched, lost, duplicates, collectors)):
        prospect_lines.append(
            "Prospectors: "
            f"{launched or 0} launched | Lost {lost or 0} | Duplicates {duplicates or 0}"
        )
        prospect_lines.append(
            f"Collectors: {collectors or 0} | Abandoned {collectors_abandoned or 0}"
        )
    if prospect_lines:
        fields.append({"name": "Prospecting", "value": "\n".join(prospect_lines), "inline": False})

    refinement_meta = meta.get("refinement_activity", {}) or {}
    max_rpm = _safe_float(refinement_meta.get("max_rpm", meta.get("max_rpm")))
    current_rpm = _safe_float(refinement_meta.get("current_rpm"))
    lookback = _safe_int(refinement_meta.get("lookback_seconds"))
    refinement_parts = []
    if max_rpm is not None:
        refinement_parts.append(f"Max {max_rpm:.1f} RPM")
    if current_rpm is not None:
        refinement_parts.append(f"Current {current_rpm:.1f} RPM")
    if lookback:
        refinement_parts.append(f"Lookback {lookback}s")
    if refinement_parts:
        fields.append({"name": "Refining", "value": " | ".join(refinement_parts), "inline": False})

    summary = payload.get("commodities", {})
    top_value = _format_top_commodities(summary)
    if top_value:
        fields.append({"name": "Top Commodities", "value": top_value, "inline": False})

    estimated_value = _format_estimated_sell_values(state)
    if estimated_value:
        fields.append({"name": "Estimated Sell (Est. CR)", "value": estimated_value, "inline": False})

    materials = meta.get("materials", [])
    materials_value = _format_materials(materials)
    if materials_value:
        fields.append({"name": "Materials", "value": materials_value, "inline": False})

    if meta.get("ended_via_reset"):
        fields.append(
            {
                "name": "Notes",
                "value": "Session ended via manual reset.",
                "inline": False,
            }
        )

    if json_path is not None:
        fields.append(
            {
                "name": "Log",
                "value": json_path.name,
                "inline": False,
            }
        )

    embed: Dict[str, Any] = {
        "title": f"CMDR {commander} — Mining Summary",
        "description": f"{ship}",
        "color": EMBED_COLOR,
        "fields": fields,
        "footer": {"text": "EDMC Mining Analytics"},
    }

    image_url = embed.get("image", {}).get("url")
    if not image_url:
        manager = DiscordImageManager(state)
        image_url = manager.select_image(meta.get("ship") or state.current_ship)
        if image_url:
            embed["image"] = {"url": image_url}

    end_time = meta.get("end_time")
    if isinstance(end_time, str) and end_time:
        embed["timestamp"] = end_time

    return {"embeds": [embed]}


def build_test_message(state: MiningState) -> Dict[str, Any]:
    """Create a payload that mimics a summary for webhook tests."""

    now = datetime.now(timezone.utc)
    meta = {
        "start_time": now.isoformat().replace("+00:00", "Z"),
        "end_time": now.isoformat().replace("+00:00", "Z"),
        "duration_seconds": 0.0,
        "overall_tph": {
            "tons": state.current_cargo_tonnage,
            "elapsed_seconds": 0.0,
            "tons_per_hour": 0.0,
        },
        "location": {
            "body": state.mining_location if state.mining_location else None,
            "system": state.current_system if state.current_system else None,
        },
        "ship": state.current_ship or "Unknown ship",
        "prospected": {
            "total": state.prospected_count,
            "already_mined": state.already_mined_count,
            "duplicates": state.duplicate_prospected,
        },
        "prospectors_launched": state.prospector_launched_count,
        "prospectors_lost": max(0, state.prospector_launched_count - state.prospected_count),
        "collectors_launched": state.collection_drones_launched,
        "collectors_abandoned": state.abandoned_limpets,
        "limpets_remaining": state.limpets_remaining,
        "content_summary": {
            "High": state.prospect_content_counts.get("High", 0),
            "Medium": state.prospect_content_counts.get("Medium", 0),
            "Low": state.prospect_content_counts.get("Low", 0),
        },
        "materials": _materials_snapshot(state, state.materials_collected),
        "commander": state.cmdr_name,
        "ring": state.mining_ring,
        "max_rpm": round(state.max_rpm, 2),
        "refinement_activity": {
            "lookback_seconds": state.refinement_lookback_seconds,
            "current_rpm": round(state.current_rpm, 2),
            "max_rpm": round(state.max_rpm, 2),
        },
    }

    payload = {"meta": meta, "commodities": {}}
    message = build_summary_message(state, payload, json_path=None)
    embed = message["embeds"][0]
    embed["title"] += " (Test)"
    embed["description"] = "Webhook test message"
    embed["color"] = TEST_COLOR
    return message


def format_duration(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: List[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes or (hours and secs):
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def _safe_float(value: Any) -> Optional[float]:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result


def _safe_int(value: Any, *, default: Optional[int] = None) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _format_top_commodities(commodities: Dict[str, Any]) -> Optional[str]:
    if not commodities:
        return None
    sorted_items = sorted(
        commodities.items(),
        key=lambda item: item[1].get("gathered", {}).get("tons", 0),
        reverse=True,
    )[:3]
    lines: List[str] = []
    for name, info in sorted_items:
        tons = info.get("gathered", {}).get("tons", 0)
        tph = info.get("tons_per_hour")
        tph_text = f"{tph:.1f} TPH" if isinstance(tph, (int, float)) else "-"
        lines.append(f"**{name}** — {tons:.1f} tons ({tph_text})")
    return "\n".join(lines)


def _format_materials(materials: Iterable[Dict[str, Any]]) -> Optional[str]:
    if not materials:
        return None
    entries: List[Tuple[str, int]] = []
    for material in materials:
        if not isinstance(material, dict):
            continue
        name = material.get("name")
        if not name or not isinstance(name, str):
            continue
        count_value = material.get("count")
        try:
            count = int(count_value)
        except (TypeError, ValueError):
            continue
        if count <= 0:
            continue
        entries.append((name, count))
    if not entries:
        return None
    entries.sort(key=lambda item: (-item[1], item[0]))
    top_entries = entries[:8]
    formatted = [f"{name} x{count}" for name, count in top_entries]
    remaining = len(entries) - len(top_entries)
    if remaining > 0:
        formatted.append(f"+{remaining} more")
    return ", ".join(formatted)


def _format_estimated_sell_values(state: MiningState) -> Optional[str]:
    totals = state.market_sell_totals
    if not totals:
        return None
    entries: List[Tuple[str, float]] = []
    for commodity, total in totals.items():
        try:
            value = float(total)
        except (TypeError, ValueError):
            continue
        entries.append((commodity, value))
    if not entries:
        return None
    entries.sort(key=lambda item: item[1], reverse=True)
    lines: List[str] = []
    for commodity, total in entries:
        name = resolve_commodity_display_name(state, commodity)
        lines.append(f"**{name}** — {format_compact_number(total)}")
    total_value = state.market_sell_total if entries else None
    if total_value is not None:
        lines.append(f"Total — {format_compact_number(total_value)}")
    return "\n".join(lines)


def _materials_snapshot(state: MiningState, materials: Counter[str]) -> List[Dict[str, Any]]:
    if not materials:
        return []
    if hasattr(materials, "items"):
        items_iter = materials.items()
    else:
        items_iter = materials
    snapshot: List[Dict[str, Any]] = []
    for entry in items_iter:
        try:
            raw_name, raw_count = entry
        except (TypeError, ValueError):
            continue
        if raw_count is None:
            continue
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            continue
        if count <= 0:
            continue
        name = _format_name(state, str(raw_name))
        snapshot.append({"name": name, "count": count})
    snapshot.sort(key=lambda entry: entry["name"])
    return snapshot


def _format_ring_info(reserve: Optional[Any], ring_type: Optional[Any]) -> Optional[str]:
    reserve_text = reserve.strip() if isinstance(reserve, str) else None
    ring_text = ring_type.strip() if isinstance(ring_type, str) else None
    parts = [value for value in (reserve_text, ring_text) if value]
    if not parts:
        return None
    return " ".join(parts)


def _format_name(state: MiningState, value: str) -> str:
    return resolve_commodity_display_name(state, value)
