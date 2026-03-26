"""X11 provider for browser open/raise capability."""

from __future__ import annotations

from ..environment import EnvironmentSnapshot
from ..ids import BROWSER_OPEN_RAISE
from ..models import (
    CapabilityRequest,
    CapabilityResult,
    HealthProbeResult,
    REASON_EXECUTION_ERROR,
    REASON_PARTIAL_SUCCESS,
    REASON_TOOL_MISSING,
    REASON_UNSUPPORTED_ENV,
    STATUS_DEGRADED,
    STATUS_FAILED,
    STATUS_SUCCESS,
)
from .browser_common import browser_tool_metadata, list_browser_windows, open_browser_url, try_raise_browser_x11


class BrowserLinuxX11Provider:
    provider_id = "browser_linux_x11"

    def supports(self, capability_id: str) -> bool:
        return capability_id == BROWSER_OPEN_RAISE

    def match_score(self, capability_id: str, env: EnvironmentSnapshot) -> int:
        if not self.supports(capability_id):
            return -1
        if env.is_linux and env.x11_display:
            return 90
        return -1

    def health_probe(self, env: EnvironmentSnapshot) -> HealthProbeResult:
        available = env.is_linux and env.x11_display
        if not available:
            return HealthProbeResult(
                provider_id=self.provider_id,
                available=False,
                reason_code=REASON_UNSUPPORTED_ENV,
                details="Not in X11 session",
            )

        tools = browser_tool_metadata(has_wmctrl=env.has_wmctrl, has_xdotool=env.has_xdotool)
        if tools["has_wmctrl"] or tools["has_xdotool"]:
            reason = None
            details = "X11 raise tools available"
        else:
            reason = REASON_TOOL_MISSING
            details = "No optional raise tool found (wmctrl/xdotool)"

        return HealthProbeResult(
            provider_id=self.provider_id,
            available=True,
            reason_code=reason,
            details=details,
            metadata=tools,
        )

    def execute(
        self,
        request: CapabilityRequest,
        *,
        env: EnvironmentSnapshot,
        timeout_seconds: float,
    ) -> CapabilityResult:
        url = str(request.payload.get("url") or "").strip()
        if not url:
            return CapabilityResult(
                status=STATUS_FAILED,
                provider=self.provider_id,
                reason_code=REASON_EXECUTION_ERROR,
                message="Missing URL payload for browser capability",
            )

        title_hints_raw = request.payload.get("title_hints")
        title_hints: tuple[str, ...]
        if isinstance(title_hints_raw, (list, tuple)):
            title_hints = tuple(str(item) for item in title_hints_raw if str(item or "").strip())
        else:
            title_hints = ()

        preexisting_window_titles: dict[str, str] = {}
        if env.has_wmctrl:
            preexisting_window_titles = {
                window.window_id: window.title
                for window in list_browser_windows(timeout=max(0.1, float(timeout_seconds)))
            }

        opened = open_browser_url(url, prefer_foreground=True)
        if not opened:
            return CapabilityResult(
                status=STATUS_FAILED,
                provider=self.provider_id,
                reason_code=REASON_EXECUTION_ERROR,
                metadata={"opened": False, "raised": False},
                message="Failed to open browser URL",
            )

        raised = try_raise_browser_x11(
            timeout_seconds=timeout_seconds,
            has_wmctrl=env.has_wmctrl,
            has_xdotool=env.has_xdotool,
            target_url=url,
            title_hints=title_hints,
            preexisting_window_titles=preexisting_window_titles,
        )
        if raised:
            return CapabilityResult(
                status=STATUS_SUCCESS,
                provider=self.provider_id,
                metadata={"opened": True, "raised": True},
                message="Opened and raised browser window",
            )

        return CapabilityResult(
            status=STATUS_DEGRADED,
            provider=self.provider_id,
            reason_code=REASON_PARTIAL_SUCCESS,
            metadata={
                "opened": True,
                "raised": False,
                **browser_tool_metadata(has_wmctrl=env.has_wmctrl, has_xdotool=env.has_xdotool),
            },
            message="Opened browser URL but could not raise browser window",
        )
