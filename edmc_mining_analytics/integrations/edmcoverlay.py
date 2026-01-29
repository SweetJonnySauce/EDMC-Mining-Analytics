"""Helper utilities for sending mining metrics to EDMCOverlay."""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional, Sequence, Tuple

from ..logging_utils import get_logger
from ..state import MiningState, resolve_commodity_display_name
from ..formatting import format_compact_number

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
ED_ORANGE = "#ff6f00"
PLUGIN_IDENTIFIER = "EDMC-MiningAnalytics"
OVERLAY_ROW_HEIGHT = 32
OVERLAY_BAR_ROW_HEIGHT = 16
OVERLAY_BAR_START_OFFSET = 140
OVERLAY_BAR_MAX_WIDTH = 160
OVERLAY_BAR_HEIGHT = 8
OVERLAY_TEXT_SIZE = "large"
OVERLAY_BAR_TEXT_SIZE = "normal"
OVERLAY_BAR_TOP_PADDING = 0
_METRIC_ORDER: Sequence[Tuple[str, str]] = (
    ("tons_per_hour", "Tons/hr"),
    ("rpm", "RPM"),
    ("percent_full", "% Full"),
    ("limpets", "Limpets"),
    ("est_cr", "Est. CR"),
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


@dataclass
class _OverlayBar:
    label: str
    percent: float
    amount: float


class EdmcOverlayHelper:
    """Coordinates EDMCOverlay availability checks and payload broadcasting."""

    def __init__(self, state: MiningState) -> None:
        self._state = state
        self._overlay: Optional[object] = None
        self._last_enabled = False
        self._last_failure_logged = False
        self._logger = logging.getLogger("EDMC.MiningAnalytics.Overlay")
        self._preview_until: Optional[datetime] = None
        self._plugin_kw_strategy: Optional[str] = None
        self._plugin_warning_emitted = False
        self._last_bar_count = 0

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
        row_height = OVERLAY_ROW_HEIGHT

        for index, metric in enumerate(metrics):
            base_y = anchor_y + index * row_height
            text = f"{metric.value} {metric.label}".strip()
            color = metric.color if metric.key == "rpm" else DEFAULT_LABEL_COLOR
            try:
                self._dispatch_overlay_message(
                    client,
                    f"edmcma.metric.{metric.key}.value",
                    text,
                    color,
                    anchor_x,
                    base_y,
                    ttl=ttl,
                    size=OVERLAY_TEXT_SIZE,
                )
            except Exception:  # pragma: no cover - runtime specific failures
                self._logger.exception("Failed to send overlay metric payload for %s", metric.key)
                self.reset()
                self._state.overlay_available = self.is_supported()
                return

        bars = self._build_overlay_bars()
        if bars:
            self._dispatch_overlay_bars(
                client,
                bars,
                anchor_x=anchor_x,
                anchor_y=anchor_y,
                ttl=ttl,
                metrics_count=len(metrics),
            )
        elif self._last_bar_count > 0:
            self._clear_overlay_bars(anchor_x=anchor_x, anchor_y=anchor_y)

        self._last_enabled = True

    def push_rpm_metric(self) -> None:
        """Emit just the RPM metric to the overlay on a faster cadence."""

        now = datetime.now(timezone.utc)
        preview_active = self._preview_active(now)

        if not self._state.overlay_enabled:
            return

        if not self.refresh_availability():
            return

        if self._state.is_mining:
            self.clear_preview()

        if not self._state.is_mining and not preview_active:
            return

        if not self._last_enabled:
            return

        client = self._resolve_overlay()
        if client is None:
            if not self._last_failure_logged:
                _log.debug("EDMCOverlay helper unavailable; RPM metric not sent")
                self._last_failure_logged = True
            return

        self._last_failure_logged = False
        metric = self._build_rpm_metric()
        ttl = 5 if (preview_active and not self._state.is_mining) else self._derive_ttl()
        anchor_x = max(0, int(self._state.overlay_anchor_x or 0))
        anchor_y = max(0, int(self._state.overlay_anchor_y or 0))
        row_height = OVERLAY_ROW_HEIGHT
        rpm_index = next(
            (index for index, (key, _label) in enumerate(_METRIC_ORDER) if key == "rpm"),
            0,
        )
        base_y = anchor_y + rpm_index * row_height
        text = f"{metric.value} {metric.label}".strip()
        try:
            self._dispatch_overlay_message(
                client,
                f"edmcma.metric.{metric.key}.value",
                text,
                metric.color,
                anchor_x,
                base_y,
                ttl=ttl,
                size=OVERLAY_TEXT_SIZE,
            )
        except Exception:  # pragma: no cover - runtime specific failures
            self._logger.exception("Failed to send overlay RPM payload")
            self.reset()
            self._state.overlay_available = self.is_supported()
            return

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

    def _build_rpm_metric(self) -> _OverlayMetric:
        rpm = float(self._state.rpm_display_value or 0.0)
        rpm_color = self._state.rpm_display_color or DEFAULT_VALUE_COLOR
        return _OverlayMetric(
            key="rpm",
            label="RPM",
            value=f"{rpm:.1f}" if rpm is not None else "--",
            color=rpm_color,
        )

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

        metrics.append(self._build_rpm_metric())

        percent_full = self._compute_percent_full()
        metrics.append(
            _OverlayMetric(
                key="percent_full",
                label="full",
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

        total_est = None
        if self._state.market_sell_totals:
            total_est = self._state.market_sell_total
        metrics.append(
            _OverlayMetric(
                key="est_cr",
                label="Est. CR",
                value=format_compact_number(total_est),
                color=DEFAULT_VALUE_COLOR,
            )
        )

        return metrics

    def _build_overlay_bars(self) -> list[_OverlayBar]:
        if not self._state.overlay_show_bars:
            return []
        capacity = self._state.cargo_capacity
        if capacity is None or capacity <= 0:
            return []
        max_rows = max(1, int(self._state.overlay_bars_max_rows or 0))

        items: list[_OverlayBar] = []
        harvested = self._state.harvested_commodities
        for commodity, amount in self._state.cargo_totals.items():
            if amount <= 0:
                continue
            if commodity not in harvested:
                continue
            label = self._resolve_bar_label(commodity)
            percent = (float(amount) / float(capacity)) * 100.0
            if percent <= 0:
                continue
            items.append(_OverlayBar(label=label, percent=percent, amount=float(amount)))

        limpets = self._state.limpets_remaining or 0
        if limpets > 0:
            percent = (float(limpets) / float(capacity)) * 100.0
            if percent > 0:
                items.append(_OverlayBar(label="Limpets", percent=percent, amount=float(limpets)))

        items.sort(key=lambda item: (-item.percent, item.label.casefold()))
        return items[:max_rows]

    def _resolve_bar_label(self, commodity: str) -> str:
        key = str(commodity or "").strip().lower()
        abbr = self._state.commodity_abbreviations.get(key)
        if abbr:
            return abbr
        return resolve_commodity_display_name(self._state, commodity)

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
        interval_ms = max(100, interval_ms)
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

    def _bar_width(self, percent: float) -> int:
        if percent <= 0:
            return 0
        capped = min(100.0, percent)
        width = int(round((capped / 100.0) * OVERLAY_BAR_MAX_WIDTH))
        return max(1, width)

    def _dispatch_overlay_rect(
        self,
        client: object,
        message_id: str,
        *,
        x: int,
        y: int,
        width: int,
        height: int,
        color: str,
        fill: str,
        ttl: int,
        include_plugin: bool = True,
    ) -> None:
        payload = {
            "shapeid": message_id,
            "shape": "rect",
            "x": x,
            "y": y,
            "w": width,
            "h": height,
            "color": color,
            "fill": fill,
            "ttl": ttl,
        }
        if include_plugin:
            payload["plugin"] = PLUGIN_IDENTIFIER

        send_shape = getattr(client, "send_shape", None)
        if callable(send_shape):
            try:
                send_shape(
                    shapeid=message_id,
                    shape="rect",
                    x=x,
                    y=y,
                    w=width,
                    h=height,
                    color=color,
                    fill=fill,
                    ttl=ttl,
                )
                return
            except TypeError:
                try:
                    send_shape(message_id, "rect", color, fill, x, y, width, height, ttl)
                    return
                except TypeError:
                    pass
        if not self._try_send_via_raw(client, payload):
            raise RuntimeError("Overlay client does not support shape payloads")

    def _dispatch_overlay_bars(
        self,
        client: object,
        bars: Sequence[_OverlayBar],
        *,
        anchor_x: int,
        anchor_y: int,
        ttl: int,
        metrics_count: int,
    ) -> None:
        base_y = anchor_y + (metrics_count * OVERLAY_ROW_HEIGHT) + OVERLAY_BAR_TOP_PADDING
        for index, bar in enumerate(bars):
            y = base_y + (index * OVERLAY_BAR_ROW_HEIGHT)
            label_id = f"edmcma.bar.{index}.label"
            bar_id = f"edmcma.bar.{index}.bar"
            try:
                self._dispatch_overlay_message(
                    client,
                    label_id,
                    bar.label,
                    DEFAULT_LABEL_COLOR,
                    anchor_x,
                    y,
                    ttl=ttl,
                    size=OVERLAY_BAR_TEXT_SIZE,
                )
                width = self._bar_width(bar.percent)
                if width <= 0:
                    continue
                bar_x = anchor_x + OVERLAY_BAR_START_OFFSET
                bar_y = y + max(0, (OVERLAY_BAR_ROW_HEIGHT - OVERLAY_BAR_HEIGHT) // 2)
                self._dispatch_overlay_rect(
                    client,
                    bar_id,
                    x=bar_x,
                    y=bar_y,
                    width=width,
                    height=OVERLAY_BAR_HEIGHT,
                    color=ED_ORANGE,
                    fill=ED_ORANGE,
                    ttl=ttl,
                )
            except Exception:  # pragma: no cover - runtime specific failures
                self._logger.exception("Failed to send overlay bar payload for %s", bar.label)
                break
        if len(bars) < self._last_bar_count:
            for index in range(len(bars), self._last_bar_count):
                y = base_y + (index * OVERLAY_BAR_ROW_HEIGHT)
                for suffix in ("label", "bar"):
                    message_id = f"edmcma.bar.{index}.{suffix}"
                    x = anchor_x if suffix == "label" else anchor_x + OVERLAY_BAR_START_OFFSET
                    try:
                        if suffix == "label":
                            self._dispatch_overlay_message(
                                client,
                                message_id,
                                "",
                                DEFAULT_LABEL_COLOR,
                                x,
                                y,
                                ttl=1,
                                size=OVERLAY_BAR_TEXT_SIZE,
                            )
                        else:
                            self._dispatch_overlay_rect(
                                client,
                                message_id,
                                x=x,
                                y=y,
                                width=0,
                                height=0,
                                color=ED_ORANGE,
                                fill=ED_ORANGE,
                                ttl=1,
                            )
                    except Exception:  # pragma: no cover
                        self._logger.exception("Failed to clear overlay bar message %s", message_id)
                        break
        self._last_bar_count = len(bars)

    def _clear_overlay_bars(self, *, anchor_x: int, anchor_y: int) -> None:
        client = self._resolve_overlay()
        if client is None:
            self._last_bar_count = 0
            return
        max_rows = max(self._last_bar_count, int(self._state.overlay_bars_max_rows or 0), 0)
        if max_rows <= 0:
            self._last_bar_count = 0
            return
        base_y = anchor_y + (len(_METRIC_ORDER) * OVERLAY_ROW_HEIGHT) + OVERLAY_BAR_TOP_PADDING
        for index in range(max_rows):
            y = base_y + (index * OVERLAY_BAR_ROW_HEIGHT)
            for suffix in ("label", "bar"):
                message_id = f"edmcma.bar.{index}.{suffix}"
                x = anchor_x if suffix == "label" else anchor_x + OVERLAY_BAR_START_OFFSET
                try:
                    if suffix == "label":
                        self._dispatch_overlay_message(
                            client,
                            message_id,
                            "",
                            DEFAULT_LABEL_COLOR,
                            x,
                            y,
                            ttl=1,
                            size=OVERLAY_BAR_TEXT_SIZE,
                        )
                    else:
                        self._dispatch_overlay_rect(
                            client,
                            message_id,
                            x=x,
                            y=y,
                            width=0,
                            height=0,
                            color=ED_ORANGE,
                            fill=ED_ORANGE,
                            ttl=1,
                        )
                except Exception:  # pragma: no cover
                    self._logger.exception("Failed to clear overlay bar message %s", message_id)
                    break
        self._last_bar_count = 0

    def _clear_overlay(self) -> None:
        client = self._resolve_overlay()
        if client is None:
            self._last_enabled = False
            return
        anchor_x = max(0, int(self._state.overlay_anchor_x or 0))
        anchor_y = max(0, int(self._state.overlay_anchor_y or 0))
        row_height = OVERLAY_ROW_HEIGHT
        for index, (key, _label) in enumerate(_METRIC_ORDER):
            base_y = anchor_y + index * row_height
            try:
                self._dispatch_overlay_message(
                    client,
                    f"edmcma.metric.{key}.value",
                    "",
                    DEFAULT_LABEL_COLOR,
                    anchor_x,
                    base_y,
                    ttl=1,
                    size=OVERLAY_TEXT_SIZE,
                )
            except Exception:  # pragma: no cover
                self._logger.exception("Failed to clear overlay message %s", key)
                break
        self._clear_overlay_bars(anchor_x=anchor_x, anchor_y=anchor_y)
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

    # ------------------------------------------------------------------
    # Payload helpers
    # ------------------------------------------------------------------
    def _dispatch_overlay_message(
        self,
        client: object,
        message_id: str,
        text: str,
        colour: str,
        x: int,
        y: int,
        *,
        ttl: int,
        size: str,
        include_plugin: bool = True,
    ) -> None:
        payload = self._build_overlay_payload(
            message_id,
            text,
            colour,
            x,
            y,
            ttl=ttl,
            size=size,
            include_plugin=include_plugin,
        )
        strategy = self._determine_plugin_strategy(client)

        if include_plugin and strategy == "unsupported":
            if self._try_send_via_raw(client, payload):
                return

        kwargs = {"ttl": ttl, "size": size}
        if include_plugin and strategy not in (None, "unsupported"):
            kwargs.update(self._plugin_kwargs_for_strategy(strategy))

        try:
            client.send_message(message_id, text, colour, x, y, **kwargs)
        except TypeError as exc:
            if include_plugin and self._handle_plugin_send_type_error(exc):
                if include_plugin and self._try_send_via_raw(client, payload):
                    return
                client.send_message(message_id, text, colour, x, y, ttl=ttl, size=size)
                return
            raise

    def _build_overlay_payload(
        self,
        message_id: str,
        text: str,
        colour: str,
        x: int,
        y: int,
        *,
        ttl: int,
        size: str,
        include_plugin: bool,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": message_id,
            "text": text,
            "color": colour,
            "size": size,
            "x": x,
            "y": y,
            "ttl": ttl,
        }
        if include_plugin:
            payload["plugin"] = PLUGIN_IDENTIFIER
        return payload

    def _plugin_kwargs_for_strategy(self, strategy: Optional[str]) -> dict[str, object]:
        if strategy == "direct":
            return {"plugin": PLUGIN_IDENTIFIER}
        if strategy in {"meta", "metadata", "payload", "extra", "extras", "context"}:
            return {strategy: {"plugin": PLUGIN_IDENTIFIER}}
        return {}

    def _determine_plugin_strategy(self, client: object) -> Optional[str]:
        if self._plugin_kw_strategy is not None:
            return self._plugin_kw_strategy
        strategy = self._inspect_plugin_strategy(client)
        self._plugin_kw_strategy = strategy
        if strategy == "unsupported" and not self._plugin_warning_emitted:
            self._logger.info(
                "EDMCOverlay client send_message signature lacks plugin metadata support; attempting raw payload injection"
            )
            self._plugin_warning_emitted = True
        return strategy

    def _inspect_plugin_strategy(self, client: object) -> Optional[str]:
        send_message = getattr(client, "send_message", None)
        if send_message is None:
            return "unsupported"
        try:
            signature = inspect.signature(send_message)
        except (TypeError, ValueError):
            return "direct"
        params = list(signature.parameters.values())
        if params and params[0].kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
            if params[0].name == "self":
                params = params[1:]
        has_var_kw = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params)
        if "plugin" in signature.parameters:
            param = signature.parameters["plugin"]
            if param.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
                inspect.Parameter.VAR_KEYWORD,
            ):
                return "direct"
        for candidate in ("meta", "metadata", "payload", "extra", "extras", "context"):
            if candidate in signature.parameters:
                return candidate
        if has_var_kw:
            return "direct"
        return "unsupported"

    def _try_send_via_raw(self, client: object, payload: dict[str, object]) -> bool:
        send_raw = getattr(client, "send_raw", None)
        if send_raw is None:
            return False

        ensure_service = getattr(_overlay_module, "ensure_service", None)
        connect = getattr(client, "connect", None)
        try:
            if getattr(client, "connection", None) is None:
                if ensure_service is not None:
                    try:
                        ensure_service(getattr(client, "args", []))
                    except Exception:  # pragma: no cover - runtime dependent safeguards
                        self._logger.debug("EDMCOverlay ensure_service raised; continuing with raw send", exc_info=True)
                if callable(connect):
                    connect()
                else:
                    return False
            send_raw(payload)
            return True
        except Exception:
            self._logger.exception("Failed to deliver overlay payload via raw channel for %s", payload.get("id"))
            return False

    def _handle_plugin_send_type_error(self, exc: TypeError) -> bool:
        message = str(exc)
        if not any(keyword in message for keyword in ("plugin", "meta", "metadata", "payload", "extra")):
            return False
        self._plugin_kw_strategy = "unsupported"
        if not self._plugin_warning_emitted:
            self._logger.warning(
                "EDMCOverlay rejected plugin metadata keyword; falling back to raw payload injection"
            )
            self._plugin_warning_emitted = True
        return True
