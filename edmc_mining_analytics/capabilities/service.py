"""Capability service that orchestrates resolve/execute/probe flows."""

from __future__ import annotations

from concurrent.futures import Future
from typing import Callable, Dict, Mapping, Optional

from ..logging_utils import get_logger
from .environment import detect_environment
from .dispatcher import CapabilityDispatcher
from .models import (
    CapabilityRequest,
    CapabilityResult,
    HealthProbeResult,
    POLICY_DISABLED,
    POLICY_STRICT,
    REASON_EXECUTION_ERROR,
    REASON_PARTIAL_SUCCESS,
    REASON_POLICY_BLOCKED,
    REASON_PROVIDER_UNAVAILABLE,
    STATUS_DEGRADED,
    STATUS_FAILED,
    STATUS_UNSUPPORTED,
)
from .resolver import CapabilityResolver

_log = get_logger("capabilities")


class CapabilityService:
    """Coordinates capability resolution, provider execution, and diagnostics."""

    def __init__(self, resolver: CapabilityResolver, dispatcher: CapabilityDispatcher) -> None:
        self._resolver = resolver
        self._dispatcher = dispatcher
        self._startup_probe_cache: Dict[str, HealthProbeResult] = {}

    @property
    def startup_probe_cache(self) -> Mapping[str, HealthProbeResult]:
        return dict(self._startup_probe_cache)

    def run_startup_probes(self) -> Mapping[str, HealthProbeResult]:
        """Run one startup diagnostic pass and cache results."""

        probes = self.probe_all()
        self._startup_probe_cache = dict(probes)
        return dict(probes)

    def probe_all(self) -> Mapping[str, HealthProbeResult]:
        """Run on-demand diagnostics for all providers in the current environment."""

        env = detect_environment()
        registry = self._resolver.registry
        results: dict[str, HealthProbeResult] = {}
        for provider in registry.providers():
            try:
                probe = provider.health_probe(env)
            except Exception as exc:
                probe = HealthProbeResult(
                    provider_id=provider.provider_id,
                    available=False,
                    reason_code=REASON_EXECUTION_ERROR,
                    details=str(exc),
                )
            results[provider.provider_id] = probe
            _log.debug(
                "Capability provider probe: provider=%s available=%s reason=%s details=%s",
                probe.provider_id,
                probe.available,
                probe.reason_code,
                probe.details,
            )
        return results

    def execute(self, request: CapabilityRequest) -> CapabilityResult:
        """Resolve and execute a capability request synchronously."""

        resolved = self._resolver.resolve(request)
        if resolved is None:
            return CapabilityResult(
                status=STATUS_UNSUPPORTED,
                reason_code=REASON_PROVIDER_UNAVAILABLE,
                message=f"Unknown capability: {request.capability_id}",
            )

        if resolved.effective_policy == POLICY_DISABLED:
            return CapabilityResult(
                status=STATUS_FAILED,
                reason_code=REASON_POLICY_BLOCKED,
                message="Capability disabled by policy",
            )

        if not resolved.provider_chain:
            return CapabilityResult(
                status=STATUS_UNSUPPORTED,
                reason_code=REASON_PROVIDER_UNAVAILABLE,
                message=f"No providers available for capability {request.capability_id}",
            )

        last_result: Optional[CapabilityResult] = None
        for provider in resolved.provider_chain:
            try:
                result = provider.execute(
                    request,
                    env=resolved.env,
                    timeout_seconds=resolved.descriptor.timeout_seconds,
                )
            except Exception as exc:
                result = CapabilityResult(
                    status=STATUS_FAILED,
                    provider=provider.provider_id,
                    reason_code=REASON_EXECUTION_ERROR,
                    message=str(exc),
                )

            _log.debug(
                "Capability execution result: capability=%s provider=%s status=%s reason=%s",
                request.capability_id,
                result.provider,
                result.status,
                result.reason_code,
            )

            last_result = result
            if result.ok:
                if resolved.effective_policy == POLICY_STRICT and result.status == STATUS_DEGRADED:
                    continue
                return result

        if last_result is not None:
            if resolved.effective_policy == POLICY_STRICT and last_result.status == STATUS_DEGRADED:
                return CapabilityResult(
                    status=STATUS_FAILED,
                    provider=last_result.provider,
                    reason_code=REASON_PARTIAL_SUCCESS,
                    metadata=dict(last_result.metadata),
                    message=last_result.message or "Strict policy requires full success",
                )
            return last_result

        return CapabilityResult(
            status=STATUS_FAILED,
            reason_code=REASON_PROVIDER_UNAVAILABLE,
            message=f"No executable provider chain for capability {request.capability_id}",
        )

    def execute_async(
        self,
        request: CapabilityRequest,
        on_done: Optional[Callable[[CapabilityResult], None]] = None,
    ) -> Future[CapabilityResult]:
        """Execute capability request on the dispatcher executor."""

        return self._dispatcher.submit(self.execute, request, on_done=on_done)

    def shutdown(self) -> None:
        self._dispatcher.shutdown()
