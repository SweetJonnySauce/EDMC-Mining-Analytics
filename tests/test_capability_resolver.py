from __future__ import annotations

from dataclasses import dataclass

from edmc_mining_analytics.capabilities.environment import EnvironmentSnapshot
from edmc_mining_analytics.capabilities.models import CapabilityDescriptor, CapabilityRequest
from edmc_mining_analytics.capabilities.registry import CapabilityRegistry
from edmc_mining_analytics.capabilities.resolver import CapabilityResolver


@dataclass
class _FakeProvider:
    provider_id: str
    score: int

    def supports(self, capability_id: str) -> bool:
        return capability_id == "example.cap"

    def match_score(self, capability_id: str, env: EnvironmentSnapshot) -> int:
        del capability_id, env
        return self.score

    def health_probe(self, env: EnvironmentSnapshot):
        del env
        raise NotImplementedError

    def execute(self, request, *, env: EnvironmentSnapshot, timeout_seconds: float):
        del request, env, timeout_seconds
        raise NotImplementedError


def _snapshot() -> EnvironmentSnapshot:
    return EnvironmentSnapshot(
        platform="linux",
        wayland_display=False,
        x11_display=True,
        has_wmctrl=False,
        has_xdotool=False,
    )


def test_resolver_orders_by_score_then_registration_order(monkeypatch) -> None:
    registry = CapabilityRegistry()
    registry.register_descriptor(CapabilityDescriptor(capability_id="example.cap"))
    registry.register_provider(_FakeProvider("p1", score=30))
    registry.register_provider(_FakeProvider("p2", score=30))
    registry.register_provider(_FakeProvider("p3", score=40))

    resolver = CapabilityResolver(registry)
    monkeypatch.setattr("edmc_mining_analytics.capabilities.resolver.detect_environment", _snapshot)

    resolved = resolver.resolve(CapabilityRequest(capability_id="example.cap"))

    assert resolved is not None
    assert [p.provider_id for p in resolved.provider_chain] == ["p3", "p1", "p2"]


def test_resolver_applies_descriptor_precedence(monkeypatch) -> None:
    registry = CapabilityRegistry()
    registry.register_descriptor(
        CapabilityDescriptor(
            capability_id="example.cap",
            provider_precedence=("p2", "p3"),
        )
    )
    registry.register_provider(_FakeProvider("p1", score=90))
    registry.register_provider(_FakeProvider("p2", score=10))
    registry.register_provider(_FakeProvider("p3", score=20))

    resolver = CapabilityResolver(registry)
    monkeypatch.setattr("edmc_mining_analytics.capabilities.resolver.detect_environment", _snapshot)

    resolved = resolver.resolve(CapabilityRequest(capability_id="example.cap"))

    assert resolved is not None
    assert [p.provider_id for p in resolved.provider_chain] == ["p2", "p3", "p1"]


def test_resolver_returns_none_for_unknown_capability(monkeypatch) -> None:
    registry = CapabilityRegistry()
    resolver = CapabilityResolver(registry)
    monkeypatch.setattr("edmc_mining_analytics.capabilities.resolver.detect_environment", _snapshot)

    resolved = resolver.resolve(CapabilityRequest(capability_id="missing.cap"))

    assert resolved is None
