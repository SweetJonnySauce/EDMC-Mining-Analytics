"""Discord integration helpers for EDMC Mining Analytics."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib import error as urlerror, request as urlrequest

from state import MiningState

USER_AGENT = "EDMC-Mining-Analytics/0.1"
EMBED_COLOR = 0x1d9bf0
TEST_COLOR = 0x95a5a6


def send_webhook(webhook_url: str, payload: Dict[str, Any]) -> Tuple[bool, str]:
    """Send a JSON payload to the provided Discord webhook URL."""

    if not webhook_url:
        return False, "Webhook URL is empty"
    if not payload:
        return False, "No payload to send"

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    req = urlrequest.Request(webhook_url, data=data, headers=headers, method="POST")
    try:
        with urlrequest.urlopen(req, timeout=5):
            return True, ""
    except urlerror.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.reason}"
    except urlerror.URLError as exc:
        return False, str(exc.reason)
    except Exception as exc:  # pragma: no cover
        return False, str(exc)


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

    if body and body.strip():
        location_value = body.strip()
    elif system and system.strip():
        location_value = system.strip()
    else:
        location_value = "Unknown"

    duration_seconds = float(meta.get("duration_seconds", 0.0) or 0.0)
    duration_text = format_duration(duration_seconds)

    overall = meta.get("overall_tph", {})
    total_tons = overall.get("tons")
    tph_value = overall.get("tons_per_hour")
    tph_text = f"{tph_value:.1f} TPH" if isinstance(tph_value, (int, float)) else "-"
    output_text = f"{total_tons}t @ {tph_text}" if total_tons is not None else tph_text

    prospected = meta.get("prospected", {})
    content = meta.get("content_summary", {})
    lost = meta.get("prospectors_lost", max(0, state.prospector_launched_count - state.prospected_count))

    refinement_meta = meta.get("refinement_activity", {})
    raw_max_rpm = refinement_meta.get("max_rpm", state.max_rpm)

    def _format_rpm(value: Any) -> str:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "-"
        return f"{numeric:.1f}"

    rpm_field_value = f"Max {_format_rpm(raw_max_rpm)} RPM"

    fields: List[Dict[str, Any]] = [
        {
            "name": "Location",
            "value": _clamp_text(location_value, 1024),
            "inline": False,
        },
        {
            "name": "Duration",
            "value": duration_text,
            "inline": True,
        },
        {
            "name": "Output",
            "value": output_text,
            "inline": True,
        },
        {
            "name": "Refinements",
            "value": rpm_field_value,
            "inline": True,
        },
        {
            "name": "Asteroids",
            "value": (
                f"{prospected.get('total', 0)} total\n"
                f"H:{content.get('High', 0)} | M:{content.get('Medium', 0)} | L:{content.get('Low', 0)}"
            ),
            "inline": True,
        },
        {
            "name": "Prospectors",
            "value": (
                f"Launched {meta.get('prospectors_launched', 0)}\n"
                f"Lost {lost} | Duplicates {prospected.get('duplicates', 0)}"
            ),
            "inline": True,
        },
        {
            "name": "Collectors",
            "value": (
                f"Launched {meta.get('collectors_launched', 0)}\n"
                f"Abandoned {meta.get('collectors_abandoned', 0)} | Limpets left {meta.get('limpets_remaining', 0)}"
            ),
            "inline": True,
        },
    ]

    top_value = _format_top_commodities(commodities)
    if top_value:
        fields.append({"name": "Top Commodities", "value": top_value, "inline": False})

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

    image_url = (state.discord_image_url or "").strip()
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
        "materials": _materials_snapshot(state.materials_collected),
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
    image_url = (state.discord_image_url or "").strip()
    if image_url:
        embed["image"] = {"url": image_url}
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
        avg_fragment = ""
        stats = info.get("percentage_stats")
        if isinstance(stats, dict):
            avg_value = stats.get("avg")
            if isinstance(avg_value, (int, float)):
                avg_fragment = f" | Avg {avg_value:.1f}%"
        lines.append(f"{name}: {tons}t ({tph_text}){avg_fragment}")
    value = "\n".join(lines)
    return _clamp_text(value, 1024) if value else None


def _format_materials(materials: Iterable[Dict[str, Any]]) -> Optional[str]:
    parts = []
    for entry in materials:
        name = entry.get("name")
        count = entry.get("count")
        if not name:
            continue
        parts.append(f"{name} x{count}")
    if not parts:
        return None
    return _clamp_text(", ".join(parts), 1024)


def _materials_snapshot(materials: Counter[str]) -> List[Dict[str, Any]]:
    snapshot: List[Dict[str, Any]] = []
    for name, count in sorted(materials.items()):
        snapshot.append({"name": name.title(), "count": count})
    return snapshot


def _clamp_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"
