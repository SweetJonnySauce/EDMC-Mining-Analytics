from __future__ import annotations

import edmc_mining_analytics.http_client as http_client


def test_get_shared_session_sets_user_agent_when_headers_supported(monkeypatch) -> None:
    class SessionWithHeaders:
        def __init__(self) -> None:
            self.headers = {}

    session = SessionWithHeaders()
    monkeypatch.setattr(http_client, "_SESSION", None)
    monkeypatch.setattr(http_client, "new_session", lambda: session)
    monkeypatch.setattr(http_client, "config", None)

    shared = http_client.get_shared_session()

    assert shared is session
    assert "User-Agent" in session.headers
    assert "EDMC-Mining-Analytics/" in session.headers["User-Agent"]


def test_get_shared_session_appends_plugin_agent_to_existing_user_agent(monkeypatch) -> None:
    class SessionWithHeaders:
        def __init__(self) -> None:
            self.headers = {"User-Agent": "BaseAgent/1.0"}

    session = SessionWithHeaders()
    monkeypatch.setattr(http_client, "_SESSION", None)
    monkeypatch.setattr(http_client, "new_session", lambda: session)
    monkeypatch.setattr(http_client, "config", None)

    shared = http_client.get_shared_session()

    assert shared is session
    assert session.headers["User-Agent"].startswith("BaseAgent/1.0 ")
    assert "EDMC-Mining-Analytics/" in session.headers["User-Agent"]


def test_get_shared_session_handles_sessions_without_headers(monkeypatch) -> None:
    class SessionWithoutHeaders:
        pass

    session = SessionWithoutHeaders()
    monkeypatch.setattr(http_client, "_SESSION", None)
    monkeypatch.setattr(http_client, "new_session", lambda: session)
    monkeypatch.setattr(http_client, "config", None)

    shared = http_client.get_shared_session()

    assert shared is session

