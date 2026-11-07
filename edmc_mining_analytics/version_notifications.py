"""Data-only delivery of version worker results to the main thread."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class LatestVersion:
    """A version discovered by the release/tag lookup worker."""

    version: str


@dataclass(frozen=True)
class UpdateReady:
    """A version installed by the auto-update worker."""

    version: str


VersionNotification = LatestVersion | UpdateReady


class VersionMailbox:
    """Retain ordered notifications until drained or closed by the owner."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._pending: list[VersionNotification] = []
        self._closed = False

    def publish(self, notification: VersionNotification) -> bool:
        """Queue data without calling application code; reject closed lifecycles."""
        with self._lock:
            if self._closed:
                return False
            self._pending.append(notification)
            return True

    def drain(self) -> list[VersionNotification]:
        """Transfer pending data to the caller, releasing the lock before delivery."""
        with self._lock:
            pending = self._pending
            self._pending = []
            return pending

    def close(self) -> None:
        """Discard pending data and permanently reject further publication."""
        with self._lock:
            self._closed = True
            self._pending.clear()
