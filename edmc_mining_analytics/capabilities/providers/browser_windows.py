"""Windows provider for browser open/raise capability."""

from __future__ import annotations

import os

from ..environment import EnvironmentSnapshot
from ..ids import BROWSER_OPEN_RAISE
from ..models import (
    CapabilityRequest,
    CapabilityResult,
    HealthProbeResult,
    REASON_EXECUTION_ERROR,
    REASON_PARTIAL_SUCCESS,
    REASON_UNSUPPORTED_ENV,
    STATUS_DEGRADED,
    STATUS_FAILED,
    STATUS_SUCCESS,
)
from .browser_common import open_browser_url


class BrowserWindowsProvider:
    provider_id = "browser_windows"

    def supports(self, capability_id: str) -> bool:
        return capability_id == BROWSER_OPEN_RAISE

    def match_score(self, capability_id: str, env: EnvironmentSnapshot) -> int:
        if not self.supports(capability_id):
            return -1
        if env.is_windows:
            return 100
        return -1

    def health_probe(self, env: EnvironmentSnapshot) -> HealthProbeResult:
        available = env.is_windows
        reason = None if available else REASON_UNSUPPORTED_ENV
        startfile = getattr(os, "startfile", None)
        details = "os.startfile available" if callable(startfile) else "os.startfile unavailable"
        return HealthProbeResult(
            provider_id=self.provider_id,
            available=available,
            reason_code=reason,
            details=details,
            metadata={"has_startfile": callable(startfile)},
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

        startfile = getattr(os, "startfile", None)
        if callable(startfile):
            try:
                startfile(url)
                return CapabilityResult(
                    status=STATUS_SUCCESS,
                    provider=self.provider_id,
                    metadata={"opened": True, "raised": True, "method": "startfile"},
                    message="Opened browser URL via os.startfile",
                )
            except Exception:
                pass

        opened = open_browser_url(url, prefer_foreground=True)
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
            metadata={"opened": True, "raised": False, "method": "webbrowser"},
            message="Opened browser URL but foreground raise was not confirmed",
        )
