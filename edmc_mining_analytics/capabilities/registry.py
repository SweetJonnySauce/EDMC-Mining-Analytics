"""Registry for capability descriptors and providers."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Sequence

from .models import CapabilityDescriptor
from .providers.base import CapabilityProvider


class CapabilityRegistry:
    """Stores capability descriptors and registered providers."""

    def __init__(self) -> None:
        self._descriptors: Dict[str, CapabilityDescriptor] = {}
        self._providers: List[CapabilityProvider] = []
        self._providers_by_id: Dict[str, CapabilityProvider] = {}
        self._provider_order: Dict[str, int] = {}

    def register_descriptor(self, descriptor: CapabilityDescriptor) -> None:
        self._descriptors[descriptor.capability_id] = descriptor

    def descriptor(self, capability_id: str) -> CapabilityDescriptor | None:
        return self._descriptors.get(capability_id)

    def register_provider(self, provider: CapabilityProvider) -> None:
        self._providers.append(provider)
        self._providers_by_id[provider.provider_id] = provider
        self._provider_order[provider.provider_id] = len(self._provider_order)

    def providers(self) -> Sequence[CapabilityProvider]:
        return tuple(self._providers)

    def provider_by_id(self, provider_id: str) -> CapabilityProvider | None:
        return self._providers_by_id.get(provider_id)

    def provider_registration_order(self, provider_id: str) -> int:
        return self._provider_order.get(provider_id, 10_000)

    def providers_for(self, capability_id: str) -> Sequence[CapabilityProvider]:
        return tuple(p for p in self._providers if p.supports(capability_id))

    def providers_by_capability(self) -> Dict[str, Sequence[CapabilityProvider]]:
        grouped: dict[str, list[CapabilityProvider]] = defaultdict(list)
        for provider in self._providers:
            for capability_id in self._descriptors:
                if provider.supports(capability_id):
                    grouped[capability_id].append(provider)
        return {key: tuple(value) for key, value in grouped.items()}
