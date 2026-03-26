from edmc_mining_analytics.capabilities.models import (
    CapabilityDescriptor,
    CapabilityRequest,
    CapabilityResult,
    POLICY_BEST_EFFORT,
    POLICY_DISABLED,
    POLICY_STRICT,
    STATUS_DEGRADED,
    STATUS_FAILED,
    STATUS_SUCCESS,
    resolve_policy,
)


def test_resolve_policy_uses_capability_default() -> None:
    descriptor = CapabilityDescriptor(capability_id="example", default_policy=POLICY_STRICT)
    request = CapabilityRequest(capability_id="example")

    assert resolve_policy(descriptor, request) == POLICY_STRICT


def test_resolve_policy_uses_override_when_valid() -> None:
    descriptor = CapabilityDescriptor(capability_id="example", default_policy=POLICY_BEST_EFFORT)
    request = CapabilityRequest(capability_id="example", policy_override=POLICY_DISABLED)

    assert resolve_policy(descriptor, request) == POLICY_DISABLED


def test_resolve_policy_falls_back_for_unknown_policy() -> None:
    descriptor = CapabilityDescriptor(capability_id="example", default_policy=POLICY_BEST_EFFORT)
    request = CapabilityRequest(capability_id="example", policy_override="nonsense")

    assert resolve_policy(descriptor, request) == POLICY_BEST_EFFORT


def test_capability_result_ok_for_success_and_degraded_only() -> None:
    assert CapabilityResult(status=STATUS_SUCCESS).ok is True
    assert CapabilityResult(status=STATUS_DEGRADED).ok is True
    assert CapabilityResult(status=STATUS_FAILED).ok is False
