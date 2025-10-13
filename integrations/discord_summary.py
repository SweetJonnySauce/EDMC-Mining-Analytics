"""Discord integration helpers for EDMC Mining Analytics."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib import error as urlerror, request as urlrequest

from state import MiningState
from .discord_image_manager import DiscordImageManager

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

    summary = payload.get("commodities", {})
    top_value = _format_top_commodities(summary)
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
        lines.append(f"**{name}** — {tons:.1f} tons ({tph_text})")
    return "\n".join(lines)


def _format_materials(materials: Iterable[Dict[str, Any]]) -> Optional[str]:
    if not materials:
        return Non
