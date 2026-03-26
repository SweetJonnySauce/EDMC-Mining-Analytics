from __future__ import annotations

from pathlib import Path

from edmc_mining_analytics.capabilities.models import CapabilityResult, STATUS_DEGRADED, STATUS_FAILED
from edmc_mining_analytics.mining_ui.main_mining_ui import edmcmaMiningUI
from edmc_mining_analytics.state import MiningState


class _FakeStatusVar:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


class _FakeCapabilityService:
    def __init__(self, result: CapabilityResult) -> None:
        self.result = result
        self.requests: list[object] = []

    def execute(self, request):
        self.requests.append(request)
        return self.result


def _build_ui(capability_service: _FakeCapabilityService) -> edmcmaMiningUI:
    state = MiningState()
    state.plugin_dir = Path(__file__).resolve().parents[1]
    ui = object.__new__(edmcmaMiningUI)
    ui._state = state
    ui._capability_service = capability_service
    ui._status_var = _FakeStatusVar()  # type: ignore[assignment]
    return ui


def test_open_local_web_page_uses_capability_facade_without_status_message(monkeypatch) -> None:
    service = _FakeCapabilityService(
        CapabilityResult(
            status=STATUS_DEGRADED,
            provider="browser_linux_wayland",
            metadata={"opened": True, "raised": False},
        )
    )
    ui = _build_ui(service)

    monkeypatch.setattr(ui, "_ensure_local_web_server", lambda _plugin_dir: 8080)

    ui._open_local_web_page()

    assert service.requests
    assert ui._status_var.value == ""


def test_open_local_web_page_sets_error_status_from_capability_result(monkeypatch) -> None:
    service = _FakeCapabilityService(
        CapabilityResult(
            status=STATUS_FAILED,
            provider="browser_generic",
            message="Unable to open local page in browser.",
            metadata={"opened": False, "raised": False},
        )
    )
    ui = _build_ui(service)

    monkeypatch.setattr(ui, "_ensure_local_web_server", lambda _plugin_dir: 8080)

    ui._open_local_web_page()

    assert service.requests
    assert ui._status_var.value == "Unable to open local page in browser."
