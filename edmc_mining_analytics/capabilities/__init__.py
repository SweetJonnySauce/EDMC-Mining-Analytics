"""Capability subsystem package."""

from .bootstrap import build_default_capability_service
from .ids import BROWSER_OPEN_RAISE
from .models import (
    CapabilityDescriptor,
    CapabilityRequest,
    CapabilityResult,
    HealthProbeResult,
    POLICY_BEST_EFFORT,
    POLICY_DISABLED,
    POLICY_STRICT,
    REASON_EXECUTION_ERROR,
    REASON_PARTIAL_SUCCESS,
    REASON_POLICY_BLOCKED,
    REASON_PROVIDER_UNAVAILABLE,
    REASON_TIMEOUT,
    REASON_TOOL_MISSING,
    REASON_UNSUPPORTED_ENV,
    STATUS_DEGRADED,
    STATUS_FAILED,
    STATUS_SUCCESS,
    STATUS_UNSUPPORTED,
)
from .service import CapabilityService

__all__ = [
    "build_default_capability_service",
    "BROWSER_OPEN_RAISE",
    "CapabilityDescriptor",
    "CapabilityRequest",
    "CapabilityResult",
    "HealthProbeResult",
    "CapabilityService",
    "POLICY_BEST_EFFORT",
    "POLICY_DISABLED",
    "POLICY_STRICT",
    "REASON_EXECUTION_ERROR",
    "REASON_PARTIAL_SUCCESS",
    "REASON_POLICY_BLOCKED",
    "REASON_PROVIDER_UNAVAILABLE",
    "REASON_TIMEOUT",
    "REASON_TOOL_MISSING",
    "REASON_UNSUPPORTED_ENV",
    "STATUS_DEGRADED",
    "STATUS_FAILED",
    "STATUS_SUCCESS",
    "STATUS_UNSUPPORTED",
]
