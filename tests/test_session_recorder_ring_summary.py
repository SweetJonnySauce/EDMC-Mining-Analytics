import json
from datetime import datetime, timezone

from edmc_mining_analytics.session_recorder import SessionRecorder
from edmc_mining_analytics.state import MiningState


def _build_state(tmp_path) -> MiningState:
    state = MiningState()
    state.plugin_dir = tmp_path
    state.mining_start = datetime(2026, 3, 28, 15, 0, 0, tzinfo=timezone.utc)
    state.mining_end = datetime(2026, 3, 28, 15, 30, 0, tzinfo=timezone.utc)
    state.current_system = "Synuefe UZ-O c22-10"
    return state


def test_build_ring_summary_records_aggregates_by_ring_and_commodity(tmp_path) -> None:
    state = _build_state(tmp_path)
    recorder = SessionRecorder(state)

    payload = {
        "meta": {
            "session_guid": "session-guid-1",
            "location": {"ring": "Fallback Ring"},
        },
        "events": [
            {
                "type": "prospected_asteroid",
                "details": {
                    "body": "Ring A",
                    "materials": [
                        {"name": "Platinum", "percentage": 20.0},
                        {"name": "Gold", "percentage": 10.0},
                    ],
                },
            },
            {
                "type": "prospected_asteroid",
                "details": {
                    "body": "Ring A",
                    "materials": [
                        {"name": "Platinum", "percentage": 15.0},
                    ],
                },
            },
            {
                "type": "prospected_asteroid",
                "details": {
                    "body": "Ring B",
                    "materials": [
                        {"name": "Gold", "percentage": 5.0},
                    ],
                },
            },
        ],
    }

    records = recorder._build_ring_summary_records(payload)
    by_key = {(row["ring_name"], row["commodity_name"]): row for row in records}

    assert by_key[("Ring A", "Platinum")]["asteroids_prospected"] == 2
    assert by_key[("Ring A", "Platinum")]["asteroids_with_commodity_present"] == 2
    assert by_key[("Ring A", "Platinum")]["sum_percentage"] == 35.0

    assert by_key[("Ring A", "Gold")]["asteroids_prospected"] == 2
    assert by_key[("Ring A", "Gold")]["asteroids_with_commodity_present"] == 1
    assert by_key[("Ring A", "Gold")]["sum_percentage"] == 10.0

    assert by_key[("Ring B", "Gold")]["asteroids_prospected"] == 1
    assert by_key[("Ring B", "Gold")]["asteroids_with_commodity_present"] == 1
    assert by_key[("Ring B", "Gold")]["sum_percentage"] == 5.0
    assert "session_guid" not in by_key[("Ring A", "Platinum")]


def test_upsert_ring_summary_adds_to_existing_row_by_ring_and_commodity(tmp_path) -> None:
    state = _build_state(tmp_path)
    recorder = SessionRecorder(state)
    summary_dir = tmp_path / "session_data"
    summary_dir.mkdir(parents=True, exist_ok=True)
    path = summary_dir / "ring_summary.jsonl"
    existing_rows = [
        {
            "session_guid": "legacy-guid",
            "ring_name": "Ring A",
            "commodity_name": "Platinum",
            "asteroids_prospected": 1,
            "asteroids_with_commodity_present": 1,
            "sum_percentage": 12.0,
        },
        {
            "ring_name": "Ring B",
            "commodity_name": "Gold",
            "asteroids_prospected": 2,
            "asteroids_with_commodity_present": 2,
            "sum_percentage": 20.0,
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in existing_rows) + "\n", encoding="utf-8")

    payload = {
        "meta": {"session_guid": "session-guid-1", "location": {"ring": "Ring A"}},
        "events": [
            {
                "type": "prospected_asteroid",
                "details": {"body": "Ring A", "materials": [{"name": "Platinum", "percentage": 30.0}]},
            },
            {
                "type": "prospected_asteroid",
                "details": {"body": "Ring A", "materials": [{"name": "Gold", "percentage": 8.0}]},
            },
        ],
    }

    recorder._upsert_ring_summary(payload)

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 3

    platinum = next(
        row
        for row in rows
        if row["ring_name"] == "Ring A"
        and row["commodity_name"] == "Platinum"
    )
    assert platinum["asteroids_prospected"] == 3
    assert platinum["asteroids_with_commodity_present"] == 2
    assert platinum["sum_percentage"] == 42.0
    assert "session_guid" not in platinum

    preserved = next(
        row
        for row in rows
        if row["ring_name"] == "Ring B"
        and row["commodity_name"] == "Gold"
    )
    assert preserved["sum_percentage"] == 20.0


def test_end_session_writes_ring_summary_jsonl(tmp_path) -> None:
    state = _build_state(tmp_path)
    state.session_logging_enabled = True
    recorder = SessionRecorder(state)
    start = datetime(2026, 3, 28, 15, 0, 0, tzinfo=timezone.utc)
    recorder.start_session(start, reason="manual")
    recorder.record_prospected_asteroid(
        datetime(2026, 3, 28, 15, 5, 0, tzinfo=timezone.utc),
        materials=[{"Name": "Platinum", "Proportion": 22.5}],
        content_level="High",
        remaining=100.0,
        already_mined=False,
        duplicate=False,
        body="Ring C",
    )
    recorder.end_session(
        datetime(2026, 3, 28, 15, 30, 0, tzinfo=timezone.utc),
        reason="supercruise_entry",
    )

    path = tmp_path / "session_data" / "ring_summary.jsonl"
    assert path.exists()
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows
    row = rows[0]
    assert row["ring_name"] == "Ring C"
    assert row["commodity_name"] == "Platinum"
    assert row["asteroids_prospected"] == 1
    assert row["asteroids_with_commodity_present"] == 1
    assert row["sum_percentage"] == 22.5
    assert "session_guid" not in row
