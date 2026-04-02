from __future__ import annotations

import importlib
import sys
import types

import pytest

import edmc_mining_analytics.http_client as http_client
from tests.harness_test_utils import harness_context


@pytest.fixture
def http_client_in_harness(monkeypatch):
    try:
        import psutil  # noqa: F401
    except ModuleNotFoundError:
        psutil_stub = types.ModuleType("psutil")

        class _NoSuchProcess(Exception):
            pass

        class _Process:
            def __init__(self, _pid: int | None = None) -> None:
                self.pid = _pid or 0

            def status(self):
                return "running"

        psutil_stub.NoSuchProcess = _NoSuchProcess  # type: ignore[attr-defined]
        psutil_stub.Process = _Process  # type: ignore[attr-defined]
        psutil_stub.STATUS_RUNNING = "running"  # type: ignore[attr-defined]
        psutil_stub.STATUS_SLEEPING = "sleeping"  # type: ignore[attr-defined]
        psutil_stub.process_iter = lambda _attrs=None: []  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "psutil", psutil_stub)

    with harness_context(start_plugin=False):
        module = importlib.reload(http_client)
        try:
            yield module
        finally:
            module._SESSION = None


def test_get_shared_session_sets_user_agent_when_headers_supported(monkeypatch, http_client_in_harness) -> None:
    class SessionWithHeaders:
        def __init__(self) -> None:
            self.headers = {}

    session = SessionWithHeaders()
    monkeypatch.setattr(http_client_in_harness, "_SESSION", None)
    monkeypatch.setattr(http_client_in_harness, "new_session", lambda: session)
    monkeypatch.setattr(http_client_in_harness, "config", None)

    shared = http_client_in_harness.get_shared_session()

    assert shared is session
    assert "User-Agent" in session.headers
    assert "EDMC-Mining-Analytics/" in session.headers["User-Agent"]


def test_get_shared_session_appends_plugin_agent_to_existing_user_agent(monkeypatch, http_client_in_harness) -> None:
    class SessionWithHeaders:
        def __init__(self) -> None:
            self.headers = {"User-Agent": "BaseAgent/1.0"}

    session = SessionWithHeaders()
    monkeypatch.setattr(http_client_in_harness, "_SESSION", None)
    monkeypatch.setattr(http_client_in_harness, "new_session", lambda: session)
    monkeypatch.setattr(http_client_in_harness, "config", None)

    shared = http_client_in_harness.get_shared_session()

    assert shared is session
    assert session.headers["User-Agent"].startswith("BaseAgent/1.0 ")
    assert "EDMC-Mining-Analytics/" in session.headers["User-Agent"]


def test_get_shared_session_handles_sessions_without_headers(monkeypatch, http_client_in_harness) -> None:
    class SessionWithoutHeaders:
        pass

    session = SessionWithoutHeaders()
    monkeypatch.setattr(http_client_in_harness, "_SESSION", None)
    monkeypatch.setattr(http_client_in_harness, "new_session", lambda: session)
    monkeypatch.setattr(http_client_in_harness, "config", None)

    shared = http_client_in_harness.get_shared_session()

    assert shared is session


def test_get_shared_session_raises_when_header_assignment_fails(monkeypatch, http_client_in_harness) -> None:
    class ReadOnlyHeaders:
        def get(self, _key: str) -> str:
            return "BaseAgent/1.0"

        def __setitem__(self, _key: str, _value: str) -> None:
            raise RuntimeError("headers are read-only")

    class SessionWithReadOnlyHeaders:
        def __init__(self) -> None:
            self.headers = ReadOnlyHeaders()

    session = SessionWithReadOnlyHeaders()
    monkeypatch.setattr(http_client_in_harness, "_SESSION", None)
    monkeypatch.setattr(http_client_in_harness, "new_session", lambda: session)
    monkeypatch.setattr(http_client_in_harness, "config", None)

    with pytest.raises(RuntimeError, match="read-only"):
        http_client_in_harness.get_shared_session()


def test_get_shared_session_raises_when_config_user_agent_access_fails(monkeypatch, http_client_in_harness) -> None:
    class SessionWithHeaders:
        def __init__(self) -> None:
            self.headers = {}

    class BrokenConfig:
        @property
        def user_agent(self) -> str:
            raise RuntimeError("config user_agent unavailable")

    session = SessionWithHeaders()
    monkeypatch.setattr(http_client_in_harness, "_SESSION", None)
    monkeypatch.setattr(http_client_in_harness, "new_session", lambda: session)
    monkeypatch.setattr(http_client_in_harness, "config", BrokenConfig())

    with pytest.raises(RuntimeError, match="user_agent unavailable"):
        http_client_in_harness.get_shared_session()
