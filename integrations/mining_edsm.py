"""EDSM integration helpers for reserve level and ring type lookups."""

from __future__ import annotations

import threading
from typing import Callable, Optional, Tuple
from urllib import parse as urlparse

import requests

from http_client import get_shared_session
from logging_utils import get_logger
from state import MiningState


_log = get_logger("edsm")
_plugin_log = get_logger()


class EdsmClient:
    """Fetch reserve levels and ring types from EDSM without blocking the UI."""

    def __init__(
        self,
        state: MiningState,
        on_updated: Callable[[], None],
        *,
        request_timeout: float = 5.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._state = state
        self._on_updated = on_updated
        self._timeout = max(1.0, float(request_timeout))
        self._session = session or get_shared_session()
        self._lock = threading.Lock()
        self._last_system: Optional[str] = None
        self._last_ring: Optional[Tuple[str, str]] = None
        self._last_body: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def refresh(
        self,
        *,
        system: Optional[str],
        ring_name: Optional[str],
    ) -> None:
        """Queue background refreshes for the provided location details."""

        normalized_system = self._normalize(system)
        normalized_ring = self._normalize(ring_name)

        start_system_thread = False
        start_ring_thread = False

        with self._lock:
            if normalized_system != self._last_system:
                self._last_system = normalized_system
                self._last_body = None
                if not normalized_system:
                    start_system_thread = False
                    updated = False
                    if self._update_reserve_level(None):
                        updated = True
                    if self._update_ring_type(None):
                        updated = True
                    if self._update_body_name(None):
                        updated = True
                    if updated:
                        self._notify_updated()
                else:
                    start_system_thread = True

            ring_combo = (
                (normalized_system, normalized_ring)
                if normalized_ring and normalized_system
                else None
            )
            if ring_combo != self._last_ring:
                self._last_ring = ring_combo
                if ring_combo is None:
                    updated = False
                    if self._update_ring_type(None):
                        updated = True
                    if self._update_body_name(None):
                        updated = True
                    if updated:
                        self._notify_updated()
                else:
                    start_ring_thread = True

        if start_system_thread and normalized_system:
            thread = threading.Thread(
                target=self._fetch_reserve_level,
                args=(normalized_system,),
                name="edmcma-edsm-reserve",
                daemon=True,
            )
            thread.start()

        if start_ring_thread and normalized_system and normalized_ring:
            thread = threading.Thread(
                target=self._fetch_ring_type,
                args=(normalized_system, normalized_ring),
                name="edmcma-edsm-ring",
                daemon=True,
            )
            thread.start()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _fetch_reserve_level(self, system: str) -> None:
        url = (
            "https://www.edsm.net/api-v1/system?systemName="
            + urlparse.quote(system)
            + "&showId=1&showCoordinates=1&showInformation=1"
        )
        _log.debug("Requesting EDSM reserve level: %s", url)

        data = None
        try:
            response = self._session.get(url, timeout=self._timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            _log.debug("EDSM reserve request failed for %s: %s", system, exc)
        else:
            try:
                data = response.json()
            except ValueError:
                _log.debug("EDSM reserve response for %s was not valid JSON", system)

        reserve = None
        if isinstance(data, dict):
            info = data.get("information") or data.get("Information")
            if isinstance(info, dict):
                reserve_value = (
                    info.get("reserveLevel")
                    or info.get("ReserveLevel")
                    or info.get("reserve")
                    or info.get("Reserve")
                )
                if isinstance(reserve_value, str) and reserve_value.strip():
                    reserve = reserve_value.strip()

        with self._lock:
            if system != self._last_system:
                return

        if self._update_reserve_level(reserve):
            self._notify_updated()

    def _fetch_ring_type(self, system: str, ring_name: str) -> None:
        url = (
            "https://www.edsm.net/api-system-v1/bodies?systemName="
            + urlparse.quote(system)
        )
        _log.debug("Requesting EDSM ring data: %s", url)

        data = None
        try:
            response = self._session.get(url, timeout=self._timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            _log.debug("EDSM ring request failed for %s (%s): %s", system, ring_name, exc)
        else:
            try:
                data = response.json()
            except ValueError:
                _log.debug("EDSM ring response for %s (%s) was not valid JSON", system, ring_name)

        ring_type = None
        reserve_level = None
        body_name = None
        if isinstance(data, dict):
            bodies = data.get("bodies")
            if isinstance(bodies, list):
                target = ring_name.lower()
                for body in bodies:
                    if not isinstance(body, dict):
                        continue
                    rings = body.get("rings")
                    if not isinstance(rings, list):
                        continue
                    for ring in rings:
                        if not isinstance(ring, dict):
                            continue
                        name = ring.get("name") or ring.get("Name")
                        if not isinstance(name, str):
                            continue
                        if name.lower() != target:
                            continue
                        ring_value = ring.get("type") or ring.get("Type")
                        if isinstance(ring_value, str) and ring_value.strip():
                            ring_type = ring_value.strip()
                        reserve_value = (
                            ring.get("reserveLevel")
                            or ring.get("reserve")
                            or ring.get("ReserveLevel")
                            or ring.get("Reserve")
                        )
                        if isinstance(reserve_value, str) and reserve_value.strip():
                            reserve_level = reserve_value.strip()
                        break
                    if ring_type:
                        name_value = body.get("name") or body.get("Name")
                        if isinstance(name_value, str) and name_value.strip():
                            body_name = name_value.strip()
                        break

        with self._lock:
            if (system, ring_name) != self._last_ring:
                return

        updated = False
        if self._update_ring_type(ring_type):
            updated = True
        if reserve_level is not None and self._update_reserve_level(reserve_level):
            updated = True
        if body_name and self._update_body_name(body_name):
            updated = True
        if updated:
            self._notify_updated()

    def _update_reserve_level(self, value: Optional[str]) -> bool:
        if value == self._state.edsm_reserve_level:
            if value:
                _log.debug("EDSM reserve level unchanged: %s", value)
                _plugin_log.debug("EDSM reserve level unchanged: %s", value)
            else:
                _log.debug("EDSM reserve level unchanged: <none>")
                _plugin_log.debug("EDSM reserve level unchanged: <none>")
            return False
        if value:
            _log.debug("EDSM reserve level detected: %s", value)
            _plugin_log.debug("EDSM reserve level detected: %s", value)
        else:
            _log.debug("Clearing EDSM reserve level")
            _plugin_log.debug("Clearing EDSM reserve level")
        self._state.edsm_reserve_level = value
        return True

    def _update_ring_type(self, value: Optional[str]) -> bool:
        if value == self._state.edsm_ring_type:
            if value:
                _log.debug("EDSM ring type unchanged: %s", value)
                _plugin_log.debug("EDSM ring type unchanged: %s", value)
            else:
                _log.debug("EDSM ring type unchanged: <none>")
                _plugin_log.debug("EDSM ring type unchanged: <none>")
            return False
        if value:
            _log.debug("EDSM ring type detected: %s", value)
            _plugin_log.debug("EDSM ring type detected: %s", value)
        else:
            _log.debug("Clearing EDSM ring type")
            _plugin_log.debug("Clearing EDSM ring type")
        self._state.edsm_ring_type = value
        return True

    def _update_body_name(self, value: Optional[str]) -> bool:
        if value == self._state.edsm_body_name:
            if value:
                _log.debug("EDSM body name unchanged: %s", value)
                _plugin_log.debug("EDSM body name unchanged: %s", value)
            else:
                _log.debug("EDSM body name unchanged: <none>")
                _plugin_log.debug("EDSM body name unchanged: <none>")
            return False
        if value:
            _log.debug("EDSM body name detected: %s", value)
            _plugin_log.debug("EDSM body name detected: %s", value)
        else:
            _log.debug("Clearing EDSM body name")
            _plugin_log.debug("Clearing EDSM body name")
        self._state.edsm_body_name = value
        return True

    def _notify_updated(self) -> None:
        try:
            self._on_updated()
        except Exception:
            _log.exception("Failed to process EDSM update notification")

    @staticmethod
    def _normalize(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        stripped = value.strip()
        return stripped or None


__all__ = ["EdsmClient"]
