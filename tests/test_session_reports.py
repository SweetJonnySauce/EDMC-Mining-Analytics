from pathlib import Path

from edmc_mining_analytics.session_reports import (
    delete_session_report,
    resolve_session_report_path,
)


def test_resolve_session_report_path_accepts_valid_filename(tmp_path: Path) -> None:
    assert resolve_session_report_path(tmp_path, "session_data_123.json") == (
        tmp_path / "session_data" / "session_data_123.json"
    )


def test_resolve_session_report_path_rejects_invalid_filenames(tmp_path: Path) -> None:
    assert resolve_session_report_path(tmp_path, "../session_data_123.json") is None
    assert resolve_session_report_path(tmp_path, "session_data_latest.json") is None
    assert resolve_session_report_path(tmp_path, "ring_summary.jsonl") is None


def test_delete_session_report_deletes_valid_file(tmp_path: Path) -> None:
    session_dir = tmp_path / "session_data"
    session_dir.mkdir()
    target = session_dir / "session_data_123.json"
    target.write_text("{}", encoding="utf-8")

    result = delete_session_report(tmp_path, target.name)

    assert result.ok is True
    assert result.reason == "deleted"
    assert result.path == target
    assert not target.exists()


def test_delete_session_report_rejects_invalid_filename(tmp_path: Path) -> None:
    result = delete_session_report(tmp_path, "../session_data_123.json")
    assert result.ok is False
    assert result.reason == "invalid_filename"


def test_delete_session_report_returns_not_found_for_missing_file(tmp_path: Path) -> None:
    result = delete_session_report(tmp_path, "session_data_456.json")
    assert result.ok is False
    assert result.reason == "not_found"
