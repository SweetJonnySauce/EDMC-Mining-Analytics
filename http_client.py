"""Shared HTTP helpers using EDMC's timeout_session."""

from __future__ import annotations

from typing import Optional

import requests

from edmc_mining_analytics_version import PLUGIN_VERSION

try:  # pragma: no cover - only available inside EDMC
    from timeout_session import new_session  # type: ignore[import]
except ImportError:  # pragma: no cover
    new_session = None  # type: ignore[assignment]

try:  # pragma: no cover - only available inside EDMC
    from config import config  # type: ignore[import]
except ImportError:  # pragma: no cover
    config = None  # type: ignore[assignment]

_SESSION: Optional[requests.Session] = None
_PLUGIN_AGENT = f"EDMC-Mining-Analytics/{PLUGIN_VERSION}"


def _build_user_agent(existing: Optional[str]) -> str:
    base = existing or ""
    candidate = base.strip()
    if candidate and _PLUGIN_AGENT in candidate:
        return candidate
    if candidate:
        return f"{candidate} {_PLUGIN_AGENT}"

    config_agent = None
    if config is not None:
        try:
            config_agent = getattr(config, "user_agent", None)
        except Exception:
            config_agent = None

    if config_agent:
        return f"{config_agent} {_PLUGIN_AGENT}"

    return _PLUGIN_AGENT


def get_shared_session() -> requests.Session:
    """Return the shared requests session configured with EDMC defaults."""

    global _SESSION
    if _SESSION is None:
        if new_session is not None:
            session = new_session()
        else:  # pragma: no cover - fallback for tests
            session = requests.Session()
        session.headers["User-Agent"] = _build_user_agent(session.headers.get("User-Agent"))
        _SESSION = session
    return _SESSION


__all__ = ["get_shared_session"]
