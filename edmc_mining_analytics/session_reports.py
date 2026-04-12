"""Helpers for managing saved session report files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


_SESSION_REPORT_PATTERN = re.compile(r"^session_data_\d+\.json$")


@dataclass(frozen=True)
class DeleteSessionReportResult:
    """Structured result for deleting a saved session report."""

    ok: bool
    reason: str
    path: Path | None = None


def resolve_session_report_path(plugin_dir: Path | str | None, filename: str) -> Path | None:
    """Return the session report path when the filename is valid."""

    if not plugin_dir:
        return None
    candidate_name = str(filename or "").strip()
    if not _SESSION_REPORT_PATTERN.fullmatch(candidate_name):
        return None
    return Path(str(plugin_dir)) / "session_data" / candidate_name


def delete_session_report(plugin_dir: Path | str | None, filename: str) -> DeleteSessionReportResult:
    """Delete a saved session report when it matches the allowed filename contract."""

    target = resolve_session_report_path(plugin_dir, filename)
    if target is None:
        reason = "plugin_dir_unavailable" if not plugin_dir else "invalid_filename"
        return DeleteSessionReportResult(ok=False, reason=reason)
    if not target.exists():
        return DeleteSessionReportResult(ok=False, reason="not_found", path=target)
    if not target.is_file():
        return DeleteSessionReportResult(ok=False, reason="invalid_target", path=target)
    try:
        target.unlink()
    except OSError:
        return DeleteSessionReportResult(ok=False, reason="delete_failed", path=target)
    return DeleteSessionReportResult(ok=True, reason="deleted", path=target)
