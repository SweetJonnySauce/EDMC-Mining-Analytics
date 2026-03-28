"""Asynchronous dispatcher for capability execution."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Optional

from .models import CapabilityRequest, CapabilityResult


class CapabilityDispatcher:
    """Runs capability execution work off the caller thread."""

    def __init__(self, max_workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="edmcma-cap",
        )

    def submit(
        self,
        execute: Callable[[CapabilityRequest], CapabilityResult],
        request: CapabilityRequest,
        on_done: Optional[Callable[[CapabilityResult], None]] = None,
    ) -> Future[CapabilityResult]:
        future: Future[CapabilityResult] = self._executor.submit(execute, request)
        if on_done is not None:
            future.add_done_callback(lambda fut: on_done(fut.result()))
        return future

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
