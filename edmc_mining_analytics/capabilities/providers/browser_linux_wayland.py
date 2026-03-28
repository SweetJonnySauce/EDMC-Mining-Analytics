"""Wayland provider for browser open/raise capability."""

from __future__ import annotations

from ..environment import EnvironmentSnapshot
from ..ids import BROWSER_OPEN_RAISE
from ..models import (
    CapabilityRequest,
    CapabilityResult,
    HealthProbeResult,
    REASON_PARTIAL_SUCCESS,
    REASON_UNSUPPORTED_ENV,
    REASON_EXECUTION_ERROR,
    STATUS_DEGRADED,
    STATUS_FAILED,
)
from .browser_common import open_browser_url


class BrowserLinuxWaylandProvider:
    provider_id = "browser_linux_wayland"

    def supports(self, capability_id: str) -> bool:
        return capability_id == BROWSER_OPEN_RAISE

    def match_score(self, capability_id: str, env: EnvironmentSnapshot) -> int:
        if not self.supports(capability_id):
            return -1
        if env.is_linux and env.wayland_display:
            return 100
        return -1

    def health_probe(self, env: EnvironmentSnapshot) -> HealthProbeResult:
        available = env.is_linux and env.wayland_display
        reason = None if available else REASON_UNSUPPORTED_ENV
        details = "Wayland baseline is open-only" if available else "Not in Wayland session"
        return HealthProbeResult(
            provider_id=self.provider_id,
            available=available,
            reason_code=reason,
            details=details,
        )

    def execute(
        self,
        request: CapabilityRequest,
        *,
        env: EnvironmentSnapshot,
        timeout_seconds: float,
    ) -> CapabilityResult:
        del timeout_seconds
        url = str(request.payload.get("url") or "").strip()
        if not url:
            return CapabilityResult(
                status=STATUS_FAILED,
                provider=self.provider_id,
                reason_code=REASON_EXECUTION_ERROR,
                message="Missing URL payload for browser capability",
            )

        opened = open_browser_url(url, prefer_foreground=False)
        if not opened:
            return CapabilityResult(
                status=STATUS_FAILED,
                provider=self.provider_id,
                reason_code=REASON_EXECUTION_ERROR,
                metadata={"opened": False, "raised": False},
                message="Failed to open browser URL",
            )

        return CapabilityResult(
            status=STATUS_DEGRADED,
            provider=self.provider_id,
            reason_code=REASON_PARTIAL_SUCCESS,
            metadata={
                "opened": True,
                "raised": False,
                "mode": "wayland_open_only",
            },
            message="Opened browser URL (Wayland open-only baseline)",
        )
