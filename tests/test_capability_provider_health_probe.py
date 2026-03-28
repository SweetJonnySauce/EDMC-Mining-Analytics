from __future__ import annotations

from dataclasses import dataclass

from edmc_mining_analytics.capabilities.dispatcher import CapabilityDispatcher
from edmc_mining_analytics.capabilities.environment import EnvironmentSnapshot
from edmc_mining_analytics.capabilities.models import CapabilityDescriptor, CapabilityRequest, CapabilityResult, HealthProbeResult, STATUS_FAILED
from edmc_mining_analytics.capabilities.registry import CapabilityRegistry
from edmc_mining_analytics.capabilities.resolver import CapabilityResolver
from edmc_mining_analytics.capabilities.service import CapabilityService


@dataclass
class _ProbeProvider:
    provider_id: str = "probe_provider"
    probe_calls: int = 0
    execute_calls: int = 0

    def supports(self, capability_id: str) -> bool:
        return capability_id == "example.cap"

    def match_score(self, capability_id: str, env: EnvironmentSnapshot) -> int:
        del capability_id, env
        return 1

    def health_probe(self, env: EnvironmentSnapshot) -> HealthProbeResult:
        del env
        self.probe_calls += 1
        return HealthProbeResult(provider_id=self.provider_id, available=True, details="ok")

    def execute(self, request: CapabilityRequest, *, env: EnvironmentSnapshot, timeout_seconds: float) -> CapabilityResult:
        del request, env, timeout_seconds
        self.execute_calls += 1
        return CapabilityResult(status=STATUS_FAILED, provider=self.provider_id)


def _snapshot() -> EnvironmentSnapshot:
    return EnvironmentSnapshot(
        platform="linux",
        wayland_display=False,
        x11_display=True,
        has_wmctrl=False,
        has_xdotool=False,
    )


def test_health_probe_runs_on_startup_and_on_demand(monkeypatch) -> None:
    registry = CapabilityRegistry()
    registry.register_descriptor(CapabilityDescriptor(capability_id="example.cap"))
    provider = _ProbeProvider()
    registry.register_provider(provider)

    resolver = CapabilityResolver(registry)
    dispatcher = CapabilityDispatcher(max_workers=1)
    service = CapabilityService(resolver, dispatcher)

    monkeypatch.setattr("edmc_mining_analytics.capabilities.service.detect_environment", _snapshot)
    monkeypatch.setattr("edmc_mining_analytics.capabilities.resolver.detect_environment", _snapshot)

    startup = service.run_startup_probes()
    ondemand = service.probe_all()

    assert provider.probe_calls == 2
    assert provider.execute_calls == 0
    assert startup[provider.provider_id].available is True
    assert ondemand[provider.provider_id].available is True
    assert service.startup_probe_cache[provider.provider_id].available is True

    service.shutdown()
