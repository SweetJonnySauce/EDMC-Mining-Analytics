from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from edmc_mining_analytics.capabilities.models import CapabilityResult, STATUS_SUCCESS
import edmc_mining_analytics.integrations.mining_inara as mining_inara
from edmc_mining_analytics.integrations.mining_inara import InaraClient
from edmc_mining_analytics.state import MiningState


def test_open_link_routes_through_capability_browser_helper(monkeypatch) -> None:
    state = MiningState()
    state.current_system = "Sol"
    capability_service = object()
    client = InaraClient(state, capability_service=capability_service)
    client.commodity_map["platinum"] = 81

    captured: dict[str, object] = {}

    def _fake_open_url_with_capability(service, url, **kwargs):
        captured["service"] = service
        captured["url"] = url
        captured["kwargs"] = kwargs
        return CapabilityResult(status=STATUS_SUCCESS, metadata={"opened": True, "raised": True})

    monkeypatch.setattr(mining_inara, "open_url_with_capability", _fake_open_url_with_capability)

    client.open_link("platinum")

    assert captured["service"] is capability_service
    url = str(captured["url"])
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    assert parsed.netloc == "inara.cz"
    assert params["ps1"] == ["Sol"]
    kwargs = captured["kwargs"]
    assert kwargs["append_focus_token"] is False
    assert kwargs["title_hints"] == ("inara.cz", "Inara", "platinum")


def test_open_link_skips_when_url_cannot_be_built(monkeypatch) -> None:
    state = MiningState()
    state.current_system = None
    client = InaraClient(state, capability_service=object())
    client.commodity_map["platinum"] = 81

    called = {"value": False}

    def _fake_open_url_with_capability(*_args, **_kwargs):
        called["value"] = True
        return CapabilityResult(status=STATUS_SUCCESS, metadata={"opened": True, "raised": True})

    monkeypatch.setattr(mining_inara, "open_url_with_capability", _fake_open_url_with_capability)

    client.open_link("platinum")

    assert called["value"] is False
