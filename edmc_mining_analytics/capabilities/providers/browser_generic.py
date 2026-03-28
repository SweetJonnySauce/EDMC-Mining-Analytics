"""Generic fallback provider for browser capability."""

from __future__ import annotations

from ..environment import EnvironmentSnapshot
from ..ids import BROWSER_OPEN_RAISE
from ..models import (
    CapabilityRequest,
    CapabilityResult,
    HealthProbeResult,
    REASON_EXECUTION_ERROR,
    REASON_PARTIAL_SUCCESS,
    STATUS_DEGRADED,
    STATUS_FAILED,
)
from .browser_common import open_browser_url


class BrowserGenericProvider:
    provider_id = "browser_generic"

    def supports(self, capability_id: str) -> bool:
        return capability_id == BROWSER_OPEN_RAISE

    def match_score(self, capability_id: str, env: EnvironmentSnapshot) -> int:
        del env
        if not self.supports(capability_id):
            return -1
        return 10

    def health_probe(self, env: EnvironmentSnapshot) -> HealthProbeResult:
        del env
        return HealthProbeResult(
            provider_id=self.provider_id,
            available=True,
            details="Generic browser opener available",
        )

    def execute(
        self,
        request: CapabilityRequest,
        *,
        env: EnvironmentSnapshot,
        timeout_seconds: float,
    ) -> CapabilityResult:
        del env, timeout_seconds
        url = str(request.payload.get("url") or "").strip()
        if not url:
            return CapabilityResult(
                status=STATUS_FAILED,
                provider=self.provider_id,
                reason_code=REASON_EXECUTION_ERROR,
                message="Missing URL payload for browser capability",
            )

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
            metadata={"opened": True, "raised": False},
            message="Opened browser URL (generic fallback)",
        )
