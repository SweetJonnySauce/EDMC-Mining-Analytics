"""Helper utilities for sending mining metrics to EDMCOverlay."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional, Sequence, Tuple

from logging_utils import get_logger
from state import MiningState, update_rpm

try:  # pragma: no cover - runtime environment provides this module
    from EDMCOverlay import edmcoverlay as _overlay_module  # type: ignore[import]
except ImportError:  # pragma: no cover - fallback to legacy package name
    try:
        from edmcoverlay import edmcoverlay as _overlay_module  # type: ignore[import]
    except ImportError:
        _overlay_module = None  # type: ignore[assignment]

_log = get_logger("overlay")

RPM_COLOR_RED = "#e74c3c"
RPM_COLOR_YELLOW = "#f7931e"
RPM_COLOR_GREEN = "#2ecc71"
DEFAULT_LABEL_COLOR = "#b4b7bf"
DEFAULT_VALUE_COLOR = "#ffffff"
_METRIC_ORDER: Sequence[Tuple[str, str]] = (
    ("tons_per_hour", "Tons/hr"),
    ("rpm", "RPM"),
    ("percent_full", "% Full"),
    ("limpets", "Limpets"),
)


def is_overlay_available() -> bool:
    """Check whether the EDMCOverlay module is importable."""

    return _overlay_module is not None


def determine_rpm_color(state: MiningState, rpm: float, *, default: str = DEFAULT_VALUE_COLOR) -> str:
    """Resolve the RPM colour based on user-configured thresholds."""

    try:
        green_threshold = int(state.rpm_threshold_green)
        yellow_threshold = int(state.rpm_threshold_yellow)
        red_threshold = int(state.rpm_threshold_red)
    except (TypeError, ValueError):
        green_threshold = state.rpm_threshold_green
        yellow_threshold = state.rpm_threshold_yellow
        red_threshold = state.rpm_threshold_red

    rpm_value = max(0.0, float(rpm))
    if rpm_value >= max(1, green_threshold):
        return RPM_COLOR_GREEN
    if rpm_value >= max(1, yellow_threshold):
        return RPM_COLOR_YELLOW
    if rpm_value >= max(1, red_threshold):
        return RPM_COLOR_RED
    return default


@dataclass
class _OverlayMetric:
    key: str
    label: str
    value: str
    color: str


class EdmcOverlayHelper:
    """Coordinates EDMCOverlay availability checks and payload broadcasting."""

    def __init__(self, state: MiningState) -> None:
        self._state = state
        self._overlay: Optional[object] = None
        self._last_enabled = False
        self._last_failure_logged = False
        self._logger = logging.getLogger("EDMC.MiningAnalytics.Overlay")
        self._preview_until: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Availability lifecycle
    # ------------------------------------------------------------------
    def is_supported(self) -> bool:
        """Return True when the edmcoverlay compatibility layer is importable."""

        return is_overlay_available()

    def refresh_availability(self) -> bool:
        """Synchronise the state flag with current availability."""

        available = self.is_supported()
        self._state.overlay_available = available
        return available

    def reset(self) -> None:
        """Drop the cached overlay client so we reconnect on next use."""

        self._overlay = None
        self._last_enabled = False

    # ------------------------------------------------------------------
    # Metric dispatch
    # ------------------------------------------------------------------
    def trigger_preview(self, duration_seconds: int = 5) -> None:
        if duration_seconds <= 0:
            self._preview_until = None
            return
        now = datetime.now(timezone.utc)
        self._preview_until = now + timedelta(seconds=duration_seconds)

    def clear_preview(self) -> None:
        self._preview_until = None

    def is_preview_active(self) -> bool:
        return self._preview_active(datetime.now(timezone.utc))

    def preview_seconds_remaining(self) -> Optional[float]:
        now = datetime.now(timezone.utc)
        if not self._preview_active(now):
            return None
        if self._preview_until is None:
            return None
        remaining = (self._preview_until - now).total_seconds()
        return max(0.0, remaining)

    def push_metrics(self) -> None:
        """Emit the latest mining metrics to the overlay when enabled."""

        now = datetime.now(timezone.utc)
        preview_active = self._preview_active(now)

        if not self._state.overlay_enabled:
            self.clear_preview()
            if self._last_enabled:
                self._clear_overlay()
            return

        if not self.refresh_availability():
            self.clear_preview()
            if self._last_enabled:
                self._clear_overlay()
            return

        if self._state.is_mining:
            self.clear_preview()

        if not self._state.is_mining and not preview_active:
            if self._last_enabled:
                self._clear_overlay()
            return

        client = self._resolve_overlay()
        if client is None:
            if not self._last_failure_logged:
                _log.debug("EDMCOverlay helper unavailable; metrics not sent")
                self._last_failure_logged = True
            return

        self._last_failure_logged = False
        metrics = self._build_metrics()
        if not metrics:
            if self._last_enabled:
                self._clear_overlay()
            return

        ttl = 5 if (preview_active and not self._state.is_mining) else self._derive_ttl()
        anchor_x = max(0, int(self._state.overlay_anchor_x or 0))
        anchor_y = max(0, int(self._state.overlay_anchor_y or 0))
        row_height = 58
        label_offset = 26

        for index, metric in enumerate(metrics):
            base_y = anchor_y + index * row_height
            try:
                client.send_message(
                    f"edmcma.metric.{metric.key}.value",
                    metric.value,
                    metric.color,
                    anchor_x,
                    base_y,
                    ttl=ttl,
                    size="large",
                )
                client.send_message(
                    f"edmcma.metric.{metric.key}.label",
                    metric.label,
                    DEFAULT_LABEL_COLOR,
                    anchor_x,
                    base_y + label_offset,
                    ttl=ttl,
                    size="normal",
                )
            except Exception:  # pragma: no cover - runtime specific failures
                self._logger.exception("Failed to send overlay metric payload for %s", metric.key)
                self.reset()
                self._state.overlay_available = self.is_supported()
                return

        self._last_enabled = True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _resolve_overlay(self) -> Optional[object]:
        if not self.is_supported():
            return None
        if self._overlay is not None:
            return self._overlay
        try:
            self._overlay = _overlay_module.Overlay()  # type: ignore[call-arg]
        except Exception:  # pragma: no cover - runtime dependent
            self._logger.exception("Unable to initialise EDMCOverlay compatibility client")
            self._overlay = None
        return self._overlay

    def _build_metrics(self) -> Sequence[_OverlayMetric]:
        metrics: list[_OverlayMetric] = []

        total_rate = self._compute_total_tph()
        metrics.append(
            _OverlayMetric(
                key="tons_per_hour",
                label="Tons/hr",
                value=self._format_rate(total_rate) if total_rate is not None else "--",
                color=DEFAULT_VALUE_COLOR,
            )
        )

        # Mirror UI behavior: only recompute RPM when actively mining
        # and not paused; otherwise use last computed value.
        if self._state.is_mining and not self._state.is_paused:
            rpm = update_rpm(self._state)
        else:
            rpm = float(self._state.current_rpm or 0.0)
        rpm_color = determine_rpm_color(self._state, rpm, default=self._state.rpm_display_color or DEFAULT_VALUE_COLOR)
        self._state.rpm_display_color = rpm_color
        metrics.append(
            _OverlayMetric(
                key="rpm",
                label="RPM",
                value=f"{rpm:.1f}" if rpm is not None else "--",
                color=rpm_color,
            )
        )

        percent_full = self._compute_percent_full()
        metrics.append(
            _OverlayMetric(
                key="percent_full",
                label="% Full",
                value=f"{percent_full:.1f}%" if percent_full is not None else "--",
                color=DEFAULT_VALUE_COLOR,
            )
        )

        limpets_remaining = self._state.limpets_remaining
        limpets_label = "--" if limpets_remaining is None else str(max(0, int(limpets_remaining)))
        metrics.append(
            _OverlayMetric(
                key="limpets",
                label="Limpets Remaining",
                value=limpets_label,
                color=DEFAULT_VALUE_COLOR,
            )
        )

        return metrics

    def _compute_total_tph(self) -> Optional[float]:
        if not self._state.mining_start:
            return None
        total_amount = sum(amount for amount in self._state.cargo_additions.values() if amount > 0)
        if total_amount <= 0:
            return None
        start_time = self._ensure_aware(self._state.mining_start)
        end_time = self._ensure_aware(self._state.mining_end or datetime.now(timezone.utc))
        elapsed_seconds = (end_time - start_time).total_seconds()
        if elapsed_seconds <= 0:
            return None
        return total_amount / (elapsed_seconds / 3600.0)

    def _compute_percent_full(self) -> Optional[float]:
        capacity = self._state.cargo_capacity
        if capacity is None or capacity <= 0:
            return None
        mined = max(0, self._state.current_cargo_tonnage)
        limpets_remaining = self._state.limpets_remaining or 0
        total_loaded = max(0, mined + max(0, limpets_remaining))
        return min(100.0, max(0.0, (total_loaded / capacity) * 100.0))

    def _derive_ttl(self) -> int:
        interval_ms = self._state.overlay_refresh_interval_ms or 1000
        try:
            interval_ms = int(interval_ms)
        except (TypeError, ValueError):
            interval_ms = 1000
        interval_ms = max(200, interval_ms)
        interval_seconds = interval_ms / 1000.0
        ttl_seconds = max(5.0, min(300.0, interval_seconds * 3 + 5.0))
        return int(ttl_seconds)

    @staticmethod
    def _format_rate(rate: Optional[float]) -> str:
        if rate is None:
            return "--"
        if rate >= 10:
            return f"{rate:.0f}"
        if rate >= 1:
            return f"{rate:.1f}"
        return f"{rate:.2f}"

    def _clear_overlay(self) -> None:
        client = self._resolve_overlay()
        if client is None:
            self._last_enabled = False
            return
        anchor_x = max(0, int(self._state.overlay_anchor_x or 0))
        anchor_y = max(0, int(self._state.overlay_anchor_y or 0))
        row_height = 58
        label_offset = 26
        for index, (key, _label) in enumerate(_METRIC_ORDER):
            base_y = anchor_y + index * row_height
            try:
                client.send_message(
                    f"edmcma.metric.{key}.value",
                    "",
                    DEFAULT_VALUE_COLOR,
                    anchor_x,
                    base_y,
                    ttl=1,
                    size="large",
                )
                client.send_message(
                    f"edmcma.metric.{key}.label",
                    "",
                    DEFAULT_LABEL_COLOR,
                    anchor_x,
                    base_y + label_offset,
                    ttl=1,
                    size="normal",
                )
            except Exception:  # pragma: no cover
                self._logger.exception("Failed to clear overlay message %s", key)
                break
        self._last_enabled = False
        self.clear_preview()

    @staticmethod
    def _ensure_aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _preview_active(self, now: datetime) -> bool:
        if self._preview_until is None:
            return False
        if now >= self._preview_until:
            self._preview_until = None
            return False
        return True
