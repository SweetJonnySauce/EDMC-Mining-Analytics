from __future__ import annotations

import threading
import time

from edmc_mining_analytics.capabilities.dispatcher import CapabilityDispatcher
from edmc_mining_analytics.capabilities.models import CapabilityRequest, CapabilityResult, STATUS_SUCCESS


def test_dispatcher_executes_request_asynchronously() -> None:
    dispatcher = CapabilityDispatcher(max_workers=1)
    event = threading.Event()

    def _execute(_request: CapabilityRequest) -> CapabilityResult:
        time.sleep(0.01)
        return CapabilityResult(status=STATUS_SUCCESS, metadata={"opened": True})

    callback_result: dict[str, CapabilityResult] = {}

    def _on_done(result: CapabilityResult) -> None:
        callback_result["value"] = result
        event.set()

    future = dispatcher.submit(_execute, CapabilityRequest(capability_id="x"), on_done=_on_done)

    assert event.wait(timeout=1.0)
    assert future.done()
    assert future.result().status == STATUS_SUCCESS
    assert callback_result["value"].metadata.get("opened") is True

    dispatcher.shutdown()
