"""Core data contracts for capability execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

POLICY_BEST_EFFORT = "best_effort"
POLICY_STRICT = "strict"
POLICY_DISABLED = "disabled"

STATUS_SUCCESS = "success"
STATUS_DEGRADED = "degraded"
STATUS_UNSUPPORTED = "unsupported"
STATUS_FAILED = "failed"

REASON_UNSUPPORTED_ENV = "unsupported_env"
REASON_POLICY_BLOCKED = "policy_blocked"
REASON_PROVIDER_UNAVAILABLE = "provider_unavailable"
REASON_TOOL_MISSING = "tool_missing"
REASON_TIMEOUT = "timeout"
REASON_PARTIAL_SUCCESS = "partial_success"
REASON_EXECUTION_ERROR = "execution_error"


@dataclass(frozen=True)
class CapabilityDescriptor:
    """Defines static metadata for a capability."""

    capability_id: str
    default_policy: str = POLICY_BEST_EFFORT
    timeout_seconds: float = 0.5
    provider_precedence: Sequence[str] = ()


@dataclass(frozen=True)
class CapabilityRequest:
    """Represents a capability invocation request."""

    capability_id: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    policy_override: Optional[str] = None


@dataclass(frozen=True)
class HealthProbeResult:
    """Represents provider availability diagnostics."""

    provider_id: str
    available: bool
    reason_code: Optional[str] = None
    details: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityResult:
    """Result returned by providers and the capability service."""

    status: str
    provider: Optional[str] = None
    reason_code: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    message: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status in {STATUS_SUCCESS, STATUS_DEGRADED}


def resolve_policy(descriptor: CapabilityDescriptor, request: CapabilityRequest) -> str:
    """Resolve effective policy using per-capability default and request override."""

    policy = request.policy_override or descriptor.default_policy
    if policy in {POLICY_BEST_EFFORT, POLICY_STRICT, POLICY_DISABLED}:
        return policy
    return descriptor.default_policy
