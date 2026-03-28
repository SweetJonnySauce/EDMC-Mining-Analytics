import json
from datetime import datetime, timezone
import uuid

from edmc_mining_analytics.session_recorder import SessionRecorder
from edmc_mining_analytics.state import MiningState


def _build_state(tmp_path) -> MiningState:
    state = MiningState()
    state.plugin_dir = tmp_path
    state.mining_start = datetime(2026, 3, 26, 22, 0, 0, tzinfo=timezone.utc)
    state.mining_end = datetime(2026, 3, 26, 23, 0, 0, tzinfo=timezone.utc)
    return state


def test_build_payload_includes_session_guid(tmp_path) -> None:
    state = _build_state(tmp_path)
    recorder = SessionRecorder(state)
    payload = recorder._build_payload()
    session_guid = payload.get("meta", {}).get("session_guid")
    assert isinstance(session_guid, str)
    assert len(session_guid) >= 16


def test_append_prospected_summary_writes_requested_fields(tmp_path) -> None:
    state = _build_state(tmp_path)
    recorder = SessionRecorder(state)
    payload = {
        "meta": {
            "session_guid": "session-guid-1",
            "location": {
                "ring": "Ring A",
                "ring_type": "Rocky",
                "reserve_level": "Pristine",
            },
        },
        "events": [
            {
                "type": "prospected_asteroid",
                "timestamp": "2026-03-26T22:10:00Z",
                "details": {
                    "body": "Ring A 1",
                    "duplicate": True,
                    "materials": [
                        {"name": "Platinum", "percentage": 22.5},
                        {"name": "Gold", "percentage": 10.0},
                    ],
                },
            }
        ],
    }

    recorder._append_prospected_asteroid_summary(payload)

    summary_path = tmp_path / "session_data" / "prospected_asteroid_summary.jsonl"
    lines = summary_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    records = [json.loads(line) for line in lines]

    first = records[0]
    assert first["session_guid"] == "session-guid-1"
    assert first["asteroid_id"] == 1
    assert first["ring_name"] == "Ring A 1"
    assert first["ring_type"] == "Rocky"
    assert first["reserve_level"] == "Pristine"
    assert first["commodity_name"] in {"Platinum", "Gold"}
    assert isinstance(first["percentage"], float)
    assert first["duplicate_prospector"] is True
    assert records[0]["asteroid_id"] == records[1]["asteroid_id"]


def test_append_prospected_summary_upgrades_legacy_timestamp_guid(tmp_path) -> None:
    state = _build_state(tmp_path)
    recorder = SessionRecorder(state)
    payload = {
        "meta": {
            "session_guid": "session_data_1769560746",
            "location": {
                "ring": "Ring B",
                "ring_type": "Metallic",
                "reserve_level": "Pristine",
            },
        },
        "events": [
            {
                "type": "prospected_asteroid",
                "timestamp": "2026-03-26T22:12:00Z",
                "details": {
                    "body": "Ring B 3",
                    "duplicate": False,
                    "materials": [
                        {"name": "Platinum", "percentage": 18.5},
                    ],
                },
            }
        ],
    }

    recorder._append_prospected_asteroid_summary(payload)

    summary_path = tmp_path / "session_data" / "prospected_asteroid_summary.jsonl"
    records = [json.loads(line) for line in summary_path.read_text(encoding="utf-8").strip().splitlines()]
    assert len(records) == 1
    session_guid = records[0]["session_guid"]
    assert session_guid != "session_data_1769560746"
    uuid.UUID(session_guid)


def test_resolve_prospect_context_fallbacks() -> None:
    # prefer event body, then ring, then body, then system, then Unknown
    assert SessionRecorder._resolve_prospect_context(
        {"location": {"ring": "Ring X", "ring_type": "Icy", "reserve_level": "Pristine"}},
        {"body": "Specific Body"},
    ) == ("Specific Body", "Icy", "Pristine")

    assert SessionRecorder._resolve_prospect_context(
        {"location": {"ring": "Ring X", "ring_type": "Metallic", "reserve_level": "Pristine"}},
        {},
    ) == ("Ring X", "Metallic", "Pristine")

    assert SessionRecorder._resolve_prospect_context(
        {"location": {"body": "Body X"}, "ring_type": "Rocky", "reserve_level": "Major"},
        {},
    ) == ("Body X", "Rocky", "Major")

    assert SessionRecorder._resolve_prospect_context(
        {"location": {"system": "System X"}},
        {},
    ) == ("System X", None, None)

    assert SessionRecorder._resolve_prospect_context({}, {}) == ("Unknown", None, None)
