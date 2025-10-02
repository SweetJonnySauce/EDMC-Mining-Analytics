"""Session recording utilities for EDMC Mining Analytics."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from urllib import error as urlerror, request as urlrequest

from logging_utils import get_logger
from state import MiningState


_log = get_logger("session_recorder")


class SessionRecorder:
    """Accumulates session telemetry and persists it to JSON when mining ends."""

    def __init__(self, state: MiningState) -> None:
        self._state = state
        self._events: list[dict[str, Any]] = []
        self._recording: bool = False
        self._session_start: Optional[datetime] = None
        self._session_end: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start_session(self, timestamp: datetime, *, reason: str) -> None:
        self._events.clear()
        self._session_start = self._ensure_aware(timestamp)
        self._session_end = None
        self._recording = bool(self._state.session_logging_enabled)
        if not self._recording:
            return
        self._record_event(
            "mining_session_started",
            self._session_start,
            {"reason": reason},
        )

    def end_session(self, timestamp: datetime, *, reason: str) -> None:
        self._session_end = self._ensure_aware(timestamp)
        if not self._recording:
            self._events.clear()
            self._session_start = None
            self._session_end = None
        else:
            self._record_event(
                "mining_session_stopped",
                self._session_end,
                {"reason": reason},
            )

        payload: Optional[dict[str, Any]] = None
        try:
            payload = self._build_payload()
        except Exception:
            _log.exception("Failed to build session payload; skipping export")

        json_path: Optional[Path] = None
        if payload and self._recording:
            json_path = self._write_payload(payload)

        if payload:
            self._maybe_send_summary(payload, json_path)

        self._events.clear()
        self._recording = False
        self._session_start = None
        self._session_end = None

    # ------------------------------------------------------------------
    # Event capture
    # ------------------------------------------------------------------
    def record_pause(self, timestamp: datetime, *, paused: bool, source: str) -> None:
        if not self._recording:
            return
        event_type = "mining_session_paused" if paused else "mining_session_resumed"
        details = {"mode": source, "auto": source == "auto"}
        self._record_event(event_type, timestamp, details)

    def record_mining_refined(
        self,
        timestamp: datetime,
        *,
        commodity_localised: Optional[str],
        commodity_type: Optional[str],
    ) -> None:
        if not self._recording:
            return
        details = {
            "type_localised": commodity_localised,
            "type": commodity_type,
        }
        self._record_event("mining_refined", timestamp, details)

    def record_cargo_event(
        self,
        timestamp: datetime,
        *,
        total_cargo: int,
        inventory: Dict[str, int],
        limpets: Optional[int],
        event_count: Optional[int],
    ) -> None:
        if not self._recording:
            return
        friendly_inventory = {
            self._format_name(name): qty for name, qty in sorted(inventory.items())
        }
        details = {
            "total_cargo": total_cargo,
            "count": event_count,
            "inventory": friendly_inventory,
            "limpets": limpets,
        }
        self._record_event("cargo", timestamp, details)

    def record_buy_drones(self, timestamp: datetime, *, count: Optional[int], drone_type: Optional[str]) -> None:
        if not self._recording:
            return
        details: dict[str, Any] = {}
        if count is not None:
            details["count"] = count
        if drone_type:
            details["type"] = drone_type
        self._record_event("buy_drones", timestamp, details)

    def record_launch_drone(self, timestamp: datetime, *, drone_type: Optional[str]) -> None:
        if not self._recording:
            return
        details = {"type": drone_type}
        self._record_event("launch_drone", timestamp, details)

    def record_prospected_asteroid(
        self,
        timestamp: datetime,
        *,
        materials: Iterable[dict[str, Any]],
        content_level: Optional[str],
        remaining: Optional[float],
        already_mined: bool,
        duplicate: bool,
        body: Optional[str],
    ) -> None:
        if not self._recording:
            return
        formatted_materials: list[dict[str, Any]] = []
        for material in materials:
            name = self._format_name(str(material.get("Name", "")))
            proportion = material.get("Proportion")
            try:
                proportion_value = float(proportion)
            except (TypeError, ValueError):
                proportion_value = None
            formatted_materials.append(
                {
                    "name": name,
                    "percentage": proportion_value,
                }
            )
        details: dict[str, Any] = {
            "materials": formatted_materials,
            "content": content_level,
            "remaining_percent": remaining,
            "already_mined": already_mined,
            "duplicate": duplicate,
        }
        if body:
            details["body"] = body
        self._record_event("prospected_asteroid", timestamp, details)

    # ------------------------------------------------------------------
    # Payload construction
    # ------------------------------------------------------------------
    def _build_payload(self) -> dict[str, Any]:
        state = self._state
        start = self._ensure_aware(
            state.mining_start or self._session_start or datetime.now(timezone.utc)
        )
        end = self._ensure_aware(
            state.mining_end or self._session_end or datetime.now(timezone.utc)
        )
        duration_seconds = max(0.0, (end - start).total_seconds())

        total_cargo = self._safe_sum(state.cargo_totals.values())
        tons_per_hour = self._compute_rate(total_cargo, duration_seconds)
        if tons_per_hour is not None:
            tons_per_hour = round(tons_per_hour, 3)

        meta: dict[str, Any] = {
            "start_time": self._isoformat(start),
            "end_time": self._isoformat(end),
            "duration_seconds": duration_seconds,
            "overall_tph": {
                "tons": total_cargo,
                "elapsed_seconds": duration_seconds,
                "tons_per_hour": tons_per_hour,
            },
            "location": {
                "body": state.mining_location,
                "system": state.current_system,
            },
            "ship": state.current_ship,
            "prospected": {
                "total": state.prospected_count,
                "already_mined": state.already_mined_count,
                "duplicates": state.duplicate_prospected,
            },
            "prospectors_launched": state.prospector_launched_count,
            "collectors_launched": state.collection_drones_launched,
            "collectors_abandoned": state.abandoned_limpets,
            "limpets_remaining": state.limpets_remaining,
            "content_summary": {
                "High": state.prospect_content_counts.get("High", 0),
                "Medium": state.prospect_content_counts.get("Medium", 0),
                "Low": state.prospect_content_counts.get("Low", 0),
            },
            "inventory_tonnage": state.current_cargo_tonnage,
            "cargo_capacity": state.cargo_capacity,
            "materials": self._materials_snapshot(state.materials_collected),
        }

        payload = {
            "meta": meta,
            "commodities": self._commodity_breakdown(end),
            "events": list(self._events),
        }
        return payload

    def _materials_snapshot(self, materials: Counter[str]) -> list[dict[str, Any]]:
        snapshot: list[dict[str, Any]] = []
        for name, count in sorted(materials.items()):
            snapshot.append({
                "name": self._format_name(name),
                "count": count,
            })
        return snapshot

    def _commodity_breakdown(self, end: datetime) -> dict[str, Any]:
        state = self._state
        result: dict[str, Any] = {}
        total_prospected = max(1, state.prospected_count)
        for commodity, total in sorted(state.cargo_totals.items()):
            friendly_name = self._format_name(commodity)
            samples = list(state.prospected_samples.get(commodity, []))
            sample_count = len(samples)
            percent = (sample_count / total_prospected) * 100.0 if state.prospected_count else 0.0
            percent = round(percent, 3)
            breakdown = self._percent_breakdown(samples)
            start_time = state.commodity_start_times.get(commodity)
            elapsed_seconds: Optional[float] = None
            if start_time:
                elapsed_seconds = max(0.0, (end - self._ensure_aware(start_time)).total_seconds())
            tph = self._compute_rate(total, elapsed_seconds) if elapsed_seconds else None
            if tph is not None:
                tph = round(tph, 3)
            result[friendly_name] = {
                "asteroids_prospected": sample_count,
                "percentage_of_asteroids": percent,
                "gathered": {
                    "tons": total,
                    "elapsed_seconds": elapsed_seconds,
                },
                "percentage_breakdown": breakdown,
                "tons_per_hour": tph,
            }
        return result

    def _percent_breakdown(self, samples: Iterable[float]) -> list[dict[str, Any]]:
        counter: Counter[str] = Counter()
        for value in samples:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            key = f"{numeric:.2f}"
            counter[key] += 1
        return [
            {"percentage": float(key), "count": counter[key]}
            for key in sorted(counter.keys(), key=lambda v: float(v))
        ]

    # ------------------------------------------------------------------
    # File management
    # ------------------------------------------------------------------
    def _write_payload(self, payload: dict[str, Any]) -> Optional[Path]:
        directory = self._resolve_output_directory()
        if directory is None:
            _log.warning("Plugin directory unavailable; skipping session export")
            return None
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except Exception:
            _log.exception("Failed to create session export directory: %s", directory)
            return None

        end_time = self._session_end or datetime.now(timezone.utc)
        filename = f"session_data_{int(end_time.timestamp())}.json"
        path = directory / filename

        try:
            with path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=False)
        except Exception:
            _log.exception("Failed to write session export: %s", path)
            return None

        self._enforce_retention(directory)
        return path

    def _resolve_output_directory(self) -> Optional[Path]:
        plugin_dir = self._state.plugin_dir
        if plugin_dir is None:
            return None
        return plugin_dir / "session_data"

    def _enforce_retention(self, directory: Path) -> None:
        limit = self._state.session_log_retention
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 30
        if limit <= 0:
            return

        files = sorted(directory.glob("session_data_*.json"), key=lambda path: path.stat().st_mtime)
        if len(files) <= limit:
            return

        excess = len(files) - limit
        for path in files[:excess]:
            try:
                path.unlink()
            except FileNotFoundError:
                continue
            except Exception:
                _log.exception("Failed to delete old session export: %s", path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _record_event(self, event_type: str, timestamp: datetime, details: Dict[str, Any]) -> None:
        aware_time = self._ensure_aware(timestamp)
        payload = {
            "type": event_type,
            "timestamp": self._isoformat(aware_time),
            "details": details,
        }
        self._events.append(payload)

    def _maybe_send_summary(self, payload: dict[str, Any], json_path: Optional[Path]) -> None:
        if not self._state.send_summary_to_discord:
            _log.debug("Discord summary disabled; skipping delivery")
            return
        url = (self._state.discord_webhook_url or "").strip()
        if not url:
            _log.debug("Discord summary disabled: webhook URL missing")
            return
        summary_text = self._render_summary(payload, json_path)
        self._state.last_session_summary = summary_text
        if not summary_text:
            _log.debug("Skipping Discord summary: nothing to send")
            return
        success, message = self._post_to_discord(summary_text)
        if success:
            _log.info("Posted mining session summary to Discord")
        else:
            detail = f": {message}" if message else ""
            _log.warning("Discord session summary delivery failed%s (see prior logs for details)", detail)

    def _render_summary(self, payload: dict[str, Any], json_path: Optional[Path]) -> str:
        meta = payload.get("meta", {})
        overall = meta.get("overall_tph", {})
        duration_seconds = float(meta.get("duration_seconds", 0.0) or 0.0)
        duration_text = self._format_duration(duration_seconds)
        total_tons = overall.get("tons")
        tph_value = overall.get("tons_per_hour")
        tph_text = f"{tph_value:.1f}" if isinstance(tph_value, (int, float)) else "-"
        body = meta.get("location", {}).get("body") or "Unknown"
        system = meta.get("location", {}).get("system") or "Unknown"
        ship = meta.get("ship") or "Unknown ship"
        prospected = meta.get("prospected", {})
        content = meta.get("content_summary", {})
        lines = [
            "**Mining Session Summary**",
            f"Location: {body} ({system})",
            f"Ship: {ship}",
            f"Duration: {duration_text}",
            f"Total: {total_tons}t @ {tph_text} TPH",
            (
                "Asteroids prospected: "
                f"{prospected.get('total', 0)} (High {content.get('High', 0)}, "
                f"Medium {content.get('Medium', 0)}, Low {content.get('Low', 0)})"
            ),
            (
                "Prospectors launched: "
                f"{meta.get('prospectors_launched', 0)} | Collectors: {meta.get('collectors_launched', 0)} | "
                f"Abandoned: {meta.get('collectors_abandoned', 0)} | Limpets remaining: {meta.get('limpets_remaining', 0)}"
            ),
        ]

        commodities = payload.get("commodities", {})
        if commodities:
            lines.append("Top commodities:")
            top = sorted(
                commodities.items(),
                key=lambda item: item[1].get("gathered", {}).get("tons", 0),
                reverse=True,
            )[:3]
            for name, info in top:
                tons = info.get("gathered", {}).get("tons", 0)
                tph = info.get("tons_per_hour")
                tph_text = f"{tph:.1f} TPH" if isinstance(tph, (int, float)) else "-"
                lines.append(f"• {name}: {tons}t ({tph_text})")

        materials = meta.get("materials", [])
        if materials:
            mat_parts = [
                f"{m.get('name')} x{m.get('count')}" for m in materials if m.get("name")
            ]
            if mat_parts:
                lines.append("Materials: " + ", ".join(mat_parts))

        if json_path is not None:
            lines.append(f"Log: {json_path.name}")

        summary = "\n".join(line for line in lines if line)
        if len(summary) > 1900:
            summary = summary[:1890].rstrip() + "…"
        return summary

    def send_test_message(self) -> Tuple[bool, str]:
        url = (self._state.discord_webhook_url or "").strip()
        if not url:
            raise ValueError("Discord webhook URL is not configured")
        content = "EDMC Mining Analytics: webhook test message"
        return self._post_to_discord(content)

    def _post_to_discord(self, content: str) -> Tuple[bool, str]:
        url = (self._state.discord_webhook_url or "").strip()
        if not url:
            return False, "Webhook URL is empty"
        if not content:
            return False, "No content to send"
        body = json.dumps({"content": content}).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "EDMC-Mining-Analytics/0.1",
        }
        req = urlrequest.Request(
            url,
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urlrequest.urlopen(req, timeout=5):
                return True, ""
        except urlerror.HTTPError as exc:
            _log.warning(
                "Discord webhook failed (status=%s): %s",
                exc.code,
                exc.reason,
            )
            return False, f"HTTP {exc.code}: {exc.reason}"
        except urlerror.URLError as exc:
            _log.warning("Discord webhook failed: %s", exc.reason)
            return False, str(exc.reason)
        except Exception as exc:
            _log.exception("Failed to deliver payload to Discord")
            return False, str(exc)

    @staticmethod
    def _ensure_aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _isoformat(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _format_name(value: str) -> str:
        return value.replace("_", " ").title()

    @staticmethod
    def _safe_sum(values: Iterable[int]) -> int:
        total = 0
        for value in values:
            try:
                total += int(value)
            except (TypeError, ValueError):
                continue
        return total

    @staticmethod
    def _compute_rate(total: int, elapsed_seconds: Optional[float]) -> Optional[float]:
        if total <= 0 or not elapsed_seconds or elapsed_seconds <= 0:
            return None
        hours = elapsed_seconds / 3600.0
        if hours <= 0:
            return None
        return total / hours

    @staticmethod
    def _format_duration(seconds: float) -> str:
        total_seconds = max(0, int(seconds))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        parts: list[str] = []
        if hours:
            parts.append(f"{hours}h")
        if minutes or (hours and secs):
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")
        return " ".join(parts)
