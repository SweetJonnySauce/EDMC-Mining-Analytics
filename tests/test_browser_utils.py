from __future__ import annotations

from edmc_mining_analytics.browser_utils import did_open, open_analysis_url
from edmc_mining_analytics.capabilities.models import CapabilityResult, STATUS_DEGRADED, STATUS_FAILED, STATUS_SUCCESS


class _FakeCapabilityService:
    def __init__(self, result: CapabilityResult) -> None:
        self.result = result
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        return self.result


def test_open_analysis_url_uses_capability_service_when_available() -> None:
    service = _FakeCapabilityService(CapabilityResult(status=STATUS_SUCCESS, metadata={"opened": True, "raised": True}))

    result = open_analysis_url(service, "http://127.0.0.1:8080/web/index.html")

    assert service.requests
    request = service.requests[0]
    assert request.payload.get("title_hints")
    assert "EDMC Mining Analytics Web Page" in request.payload.get("title_hints")
    assert "edmcma_focus_token=" in request.payload.get("url", "")
    assert result.status == STATUS_SUCCESS


def test_open_analysis_url_reports_missing_url() -> None:
    result = open_analysis_url(None, "")

    assert result.status == STATUS_FAILED


def test_did_open_respects_metadata_and_status() -> None:
    assert did_open(CapabilityResult(status=STATUS_SUCCESS)) is True
    assert did_open(CapabilityResult(status=STATUS_DEGRADED, metadata={"opened": True})) is True
    assert did_open(CapabilityResult(status=STATUS_FAILED, metadata={"opened": False})) is False
