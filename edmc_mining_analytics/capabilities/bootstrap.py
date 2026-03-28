"""Bootstrap helpers for capability subsystem wiring."""

from __future__ import annotations

from .dispatcher import CapabilityDispatcher
from .ids import BROWSER_OPEN_RAISE
from .models import CapabilityDescriptor, POLICY_BEST_EFFORT
from .providers import (
    BrowserGenericProvider,
    BrowserLinuxWaylandProvider,
    BrowserLinuxX11Provider,
    BrowserWindowsProvider,
)
from .registry import CapabilityRegistry
from .resolver import CapabilityResolver
from .service import CapabilityService


def build_default_capability_service() -> CapabilityService:
    """Create default capability service with registered capabilities/providers."""

    registry = CapabilityRegistry()
    registry.register_descriptor(
        CapabilityDescriptor(
            capability_id=BROWSER_OPEN_RAISE,
            default_policy=POLICY_BEST_EFFORT,
            timeout_seconds=0.35,
            provider_precedence=(
                "browser_windows",
                "browser_linux_wayland",
                "browser_linux_x11",
                "browser_generic",
            ),
        )
    )

    registry.register_provider(BrowserWindowsProvider())
    registry.register_provider(BrowserLinuxWaylandProvider())
    registry.register_provider(BrowserLinuxX11Provider())
    registry.register_provider(BrowserGenericProvider())

    resolver = CapabilityResolver(registry)
    dispatcher = CapabilityDispatcher(max_workers=2)
    return CapabilityService(resolver, dispatcher)
