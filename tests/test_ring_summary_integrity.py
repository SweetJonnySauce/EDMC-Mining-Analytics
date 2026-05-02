import json
from collections import defaultdict
from pathlib import Path

import pytest


FLOAT_TOLERANCE = 1e-6


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _compute_expected_from_prospected(
    prospected_path: Path,
) -> dict[tuple[str, str], dict[str, float | int]]:
    all_asteroids_by_ring: dict[str, set[tuple[str, int]]] = defaultdict(set)
    present_asteroids: dict[tuple[str, str], set[tuple[str, int]]] = defaultdict(set)
    sum_percentage: dict[tuple[str, str], float] = defaultdict(float)

    with prospected_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            text = str(raw_line or "").strip()
            if not text:
                continue
            row = json.loads(text)
            ring_name = str(row.get("ring_name") or "").strip()
            commodity_name = str(row.get("commodity_name") or "").strip()
            session_guid = str(row.get("session_guid") or "").strip()
            asteroid_id = row.get("asteroid_id")
            if not ring_name or not commodity_name or not session_guid or not isinstance(asteroid_id, (int, float)):
                continue

            asteroid_key = (session_guid, int(asteroid_id))
            all_asteroids_by_ring[ring_name].add(asteroid_key)

            try:
                percentage = float(row.get("percentage"))
            except (TypeError, ValueError):
                continue

            key = (ring_name, commodity_name.lower())
            present_asteroids[key].add(asteroid_key)
            sum_percentage[key] += percentage

    expected: dict[tuple[str, str], dict[str, float | int]] = {}
    for key, asteroid_keys in present_asteroids.items():
        ring_name, _commodity_name = key
        expected[key] = {
            "asteroids_prospected": len(all_asteroids_by_ring[ring_name]),
            "asteroids_with_commodity_present": len(asteroid_keys),
            "sum_percentage": sum_percentage[key],
        }
    return expected


def _read_ring_summary_rows(
    ring_summary_path: Path,
) -> dict[tuple[str, str], list[dict[str, object]]]:
    rows: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    with ring_summary_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            text = str(raw_line or "").strip()
            if not text:
                continue
            row = json.loads(text)
            if not isinstance(row, dict):
                continue
            ring_name = str(row.get("ring_name") or "").strip()
            commodity_name = str(row.get("commodity_name") or "").strip().lower()
            if not ring_name or not commodity_name:
                continue
            rows[(ring_name, commodity_name)].append(row)
    return rows


def test_ring_summary_integrity_matches_local_prospected_data() -> None:
    root = _repo_root()
    prospected_path = root / "session_data" / "prospected_asteroid_summary.jsonl"
    ring_summary_path = root / "session_data" / "ring_summary.jsonl"

    if not prospected_path.is_file() or not ring_summary_path.is_file():
        pytest.skip("real session_data summary artifacts are not present")

    expected = _compute_expected_from_prospected(prospected_path)
    actual = _read_ring_summary_rows(ring_summary_path)

    if not expected:
        pytest.skip("local prospected_asteroid_summary.jsonl does not contain any valid summary rows")
    if not actual:
        raise AssertionError(f"expected summary rows in {ring_summary_path}, found none")

    expected_keys = set(expected)
    actual_keys = set(actual)
    mismatches: list[str] = []

    missing_keys = sorted(expected_keys - actual_keys)
    if missing_keys:
        mismatches.append(f"missing summary rows for keys: {missing_keys!r}")

    unexpected_keys = sorted(actual_keys - expected_keys)
    if unexpected_keys:
        mismatches.append(f"unexpected summary rows for keys: {unexpected_keys!r}")

    for key in sorted(expected_keys & actual_keys):
        rows = actual[key]
        if len(rows) != 1:
            mismatches.append(f"expected exactly 1 summary row for {key!r}, found {len(rows)} rows: {rows!r}")
            continue

        row = rows[0]
        expected_row = expected[key]

        actual_asteroids_prospected = int(row.get("asteroids_prospected") or 0)
        if actual_asteroids_prospected != int(expected_row["asteroids_prospected"]):
            mismatches.append(
                f"{key!r} asteroids_prospected mismatch: "
                f"expected {expected_row['asteroids_prospected']}, got {actual_asteroids_prospected}"
            )

        actual_present = int(row.get("asteroids_with_commodity_present") or 0)
        if actual_present != int(expected_row["asteroids_with_commodity_present"]):
            mismatches.append(
                f"{key!r} asteroids_with_commodity_present mismatch: "
                f"expected {expected_row['asteroids_with_commodity_present']}, got {actual_present}"
            )

        actual_sum = float(row.get("sum_percentage") or 0.0)
        expected_sum = float(expected_row["sum_percentage"])
        if abs(actual_sum - expected_sum) > FLOAT_TOLERANCE:
            mismatches.append(
                f"{key!r} sum_percentage mismatch: "
                f"expected {expected_sum}, got {actual_sum}, tolerance {FLOAT_TOLERANCE}"
            )

    if mismatches:
        raise AssertionError("ring_summary integrity check failed:\n" + "\n".join(f"- {item}" for item in mismatches))
