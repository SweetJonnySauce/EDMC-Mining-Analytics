"""Capability resolver for provider selection and policy resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .environment import EnvironmentSnapshot, detect_environment
from .models import CapabilityDescriptor, CapabilityRequest, resolve_policy
from .providers.base import CapabilityProvider
from .registry import CapabilityRegistry


@dataclass(frozen=True)
class ResolvedCapability:
    """Resolved execution context for a capability request."""

    descriptor: CapabilityDescriptor
    effective_policy: str
    env: EnvironmentSnapshot
    provider_chain: Sequence[CapabilityProvider]


class CapabilityResolver:
    """Builds provider chains from registry entries and runtime environment."""

    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry

    @property
    def registry(self) -> CapabilityRegistry:
        return self._registry

    def resolve(self, request: CapabilityRequest) -> ResolvedCapability | None:
        descriptor = self._registry.descriptor(request.capability_id)
        if descriptor is None:
            return None

        env = detect_environment()
        effective_policy = resolve_policy(descriptor, request)
        providers = self._registry.providers_for(request.capability_id)

        scored: list[tuple[int, int, CapabilityProvider]] = []
        for provider in providers:
            score = provider.match_score(request.capability_id, env)
            if score < 0:
                continue
            order = self._registration_order(provider)
            scored.append((score, -order, provider))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        chain = [entry[2] for entry in scored]
        chain = self._apply_precedence(chain, descriptor)

        return ResolvedCapability(
            descriptor=descriptor,
            effective_policy=effective_policy,
            env=env,
            provider_chain=tuple(chain),
        )

    def _registration_order(self, provider: CapabilityProvider) -> int:
        return self._registry.provider_registration_order(provider.provider_id)

    def _apply_precedence(
        self,
        providers: Sequence[CapabilityProvider],
        descriptor: CapabilityDescriptor,
    ) -> list[CapabilityProvider]:
        if not descriptor.provider_precedence:
            return list(providers)

        by_id = {provider.provider_id: provider for provider in providers}
        ordered: list[CapabilityProvider] = []
        seen: set[str] = set()

        for provider_id in descriptor.provider_precedence:
            provider = by_id.get(provider_id)
            if provider is None:
                continue
            ordered.append(provider)
            seen.add(provider.provider_id)

        for provider in providers:
            if provider.provider_id in seen:
                continue
            ordered.append(provider)

        return ordered
