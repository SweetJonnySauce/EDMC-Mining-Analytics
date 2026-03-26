from __future__ import annotations

from edmc_mining_analytics.capabilities.bootstrap import build_default_capability_service
from edmc_mining_analytics.capabilities.ids import BROWSER_OPEN_RAISE
from edmc_mining_analytics.capabilities.models import (
    CapabilityRequest,
    POLICY_DISABLED,
    POLICY_STRICT,
    REASON_PARTIAL_SUCCESS,
    REASON_POLICY_BLOCKED,
    STATUS_DEGRADED,
    STATUS_FAILED,
)
from edmc_mining_analytics.capabilities.environment import EnvironmentSnapshot


def _wayland_snapshot() -> EnvironmentSnapshot:
    return EnvironmentSnapshot(
        platform="linux",
        wayland_display=True,
        x11_display=False,
        has_wmctrl=False,
        has_xdotool=False,
    )


def test_browser_capability_wayland_is_open_only_best_effort(monkeypatch) -> None:
    service = build_default_capability_service()

    monkeypatch.setattr("edmc_mining_analytics.capabilities.resolver.detect_environment", _wayland_snapshot)
    monkeypatch.setattr(
        "edmc_mining_analytics.capabilities.providers.browser_linux_wayland.open_browser_url",
        lambda _url, prefer_foreground=False: True,
    )

    result = service.execute(
        CapabilityRequest(
            capability_id=BROWSER_OPEN_RAISE,
            payload={"url": "http://127.0.0.1:8080/web/index.html"},
        )
    )

    assert result.status == STATUS_DEGRADED
    assert result.provider == "browser_linux_wayland"
    assert result.metadata.get("opened") is True
    assert result.metadata.get("raised") is False


def test_browser_capability_strict_fails_when_only_degraded_paths_exist(monkeypatch) -> None:
    service = build_default_capability_service()

    monkeypatch.setattr("edmc_mining_analytics.capabilities.resolver.detect_environment", _wayland_snapshot)
    monkeypatch.setattr(
        "edmc_mining_analytics.capabilities.providers.browser_linux_wayland.open_browser_url",
        lambda _url, prefer_foreground=False: True,
    )
    monkeypatch.setattr(
        "edmc_mining_analytics.capabilities.providers.browser_generic.open_browser_url",
        lambda _url, prefer_foreground=False: True,
    )

    result = service.execute(
        CapabilityRequest(
            capability_id=BROWSER_OPEN_RAISE,
            payload={"url": "http://127.0.0.1:8080/web/index.html"},
            policy_override=POLICY_STRICT,
        )
    )

    assert result.status == STATUS_FAILED
    assert result.reason_code == REASON_PARTIAL_SUCCESS


def test_browser_capability_disabled_policy_blocks_execution(monkeypatch) -> None:
    service = build_default_capability_service()

    monkeypatch.setattr("edmc_mining_analytics.capabilities.resolver.detect_environment", _wayland_snapshot)

    result = service.execute(
        CapabilityRequest(
            capability_id=BROWSER_OPEN_RAISE,
            payload={"url": "http://127.0.0.1:8080/web/index.html"},
            policy_override=POLICY_DISABLED,
        )
    )

    assert result.status == STATUS_FAILED
    assert result.reason_code == REASON_POLICY_BLOCKED
