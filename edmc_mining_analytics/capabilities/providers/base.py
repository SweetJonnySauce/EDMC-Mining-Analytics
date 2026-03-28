"""Provider interface for capability implementations."""

from __future__ import annotations

from typing import Protocol

from ..environment import EnvironmentSnapshot
from ..models import CapabilityRequest, CapabilityResult, HealthProbeResult


class CapabilityProvider(Protocol):
    """Capability provider contract."""

    provider_id: str

    def supports(self, capability_id: str) -> bool:
        """Return whether this provider supports the given capability id."""

    def match_score(self, capability_id: str, env: EnvironmentSnapshot) -> int:
        """Return match score; values <0 indicate unsupported for the environment."""

    def health_probe(self, env: EnvironmentSnapshot) -> HealthProbeResult:
        """Return fast, side-effect-free diagnostics for this provider."""

    def execute(
        self,
        request: CapabilityRequest,
        *,
        env: EnvironmentSnapshot,
        timeout_seconds: float,
    ) -> CapabilityResult:
        """Execute capability request and return structured result."""
