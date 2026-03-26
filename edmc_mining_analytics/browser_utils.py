"""Browser capability facade helpers."""

from __future__ import annotations

import secrets
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from typing import Optional

from .capabilities import (
    BROWSER_OPEN_RAISE,
    CapabilityRequest,
    CapabilityResult,
    CapabilityService,
    REASON_EXECUTION_ERROR,
    REASON_PROVIDER_UNAVAILABLE,
    STATUS_DEGRADED,
    STATUS_FAILED,
)
from .capabilities.providers.browser_common import open_browser_url


def open_analysis_url(
    capability_service: Optional[CapabilityService],
    url: str,
    *,
    policy_override: str | None = None,
    title_hints: tuple[str, ...] = (
        "EDMC Mining Analytics Web Page",
        "EDMC Mining Analytics local web page",
    ),
) -> CapabilityResult:
    """Execute browser open/raise capability for the analysis URL."""

    target = str(url or "").strip()
    if not target:
        return CapabilityResult(
            status=STATUS_FAILED,
            reason_code=REASON_EXECUTION_ERROR,
            message="Missing analysis URL",
        )

    if capability_service is None:
        opened = open_browser_url(target, prefer_foreground=True)
        if not opened:
            return CapabilityResult(
                status=STATUS_FAILED,
                reason_code=REASON_PROVIDER_UNAVAILABLE,
                metadata={"opened": False, "raised": False},
                message="Capability service unavailable and fallback open failed",
            )
        return CapabilityResult(
            status=STATUS_DEGRADED,
            reason_code=REASON_PROVIDER_UNAVAILABLE,
            metadata={"opened": True, "raised": False},
            message="Opened browser URL via fallback path",
        )

    focus_token = secrets.token_hex(4)
    tokenized_url = _append_query_param(target, "edmcma_focus_token", focus_token)
    resolved_title_hints = tuple(title_hints) + (focus_token,)
    request = CapabilityRequest(
        capability_id=BROWSER_OPEN_RAISE,
        payload={"url": tokenized_url, "title_hints": resolved_title_hints},
        policy_override=policy_override,
    )
    return capability_service.execute(request)


def did_open(result: CapabilityResult) -> bool:
    """Return whether a capability result reports URL open success."""

    return bool(result.metadata.get("opened")) or result.ok


def _append_query_param(url: str, key: str, value: str) -> str:
    """Append or replace a query parameter in a URL."""

    parsed = urlsplit(url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params[str(key)] = str(value)
    updated_query = urlencode(params, doseq=True)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, updated_query, parsed.fragment))
