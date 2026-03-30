import json
from pathlib import Path


TARGET_RING = "Col 285 Sector HM-M c7-17 9 A Ring"
TARGET_COMMODITY = "Platinum"
FLOAT_TOLERANCE = 1e-6


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _compute_expected_from_prospected(prospected_path: Path) -> dict[str, float | int]:
    all_asteroids: set[tuple[str, int]] = set()
    present_asteroids: set[tuple[str, int]] = set()
    sum_percentage = 0.0

    with prospected_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            text = str(raw_line or "").strip()
            if not text:
                continue
            row = json.loads(text)
            ring_name = str(row.get("ring_name") or "").strip()
            if ring_name != TARGET_RING:
                continue

            session_guid = str(row.get("session_guid") or "").strip()
            asteroid_id = row.get("asteroid_id")
            if not session_guid or not isinstance(asteroid_id, (int, float)):
                continue
            asteroid_key = (session_guid, int(asteroid_id))
            all_asteroids.add(asteroid_key)

            commodity_name = str(row.get("commodity_name") or "").strip().lower()
            if commodity_name != TARGET_COMMODITY.lower():
                continue
            try:
                percentage = float(row.get("percentage"))
            except (TypeError, ValueError):
                continue
            present_asteroids.add(asteroid_key)
            sum_percentage += percentage

    return {
        "asteroids_prospected": len(all_asteroids),
        "asteroids_with_commodity_present": len(present_asteroids),
        "sum_percentage": sum_percentage,
    }


def _read_ring_summary_rows(ring_summary_path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
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
            if ring_name == TARGET_RING and commodity_name == TARGET_COMMODITY.lower():
                rows.append(row)
    return rows


def test_ring_summary_integrity_for_target_ring_and_commodity() -> None:
    root = _repo_root()
    prospected_path = root / "session_data" / "prospected_asteroid_summary.jsonl"
    ring_summary_path = root / "session_data" / "ring_summary.jsonl"

    expected = _compute_expected_from_prospected(prospected_path)
    matching_rows = _read_ring_summary_rows(ring_summary_path)

    if len(matching_rows) != 1:
        detail = (
            f"expected exactly 1 row for ({TARGET_RING!r}, {TARGET_COMMODITY!r}) "
            f"in {ring_summary_path}, found {len(matching_rows)} rows."
        )
        if matching_rows:
            detail += f" Rows: {matching_rows!r}"
        raise AssertionError(detail)

    actual_row = matching_rows[0]
    mismatches: list[str] = []

    actual_asteroids_prospected = int(actual_row.get("asteroids_prospected") or 0)
    if actual_asteroids_prospected != int(expected["asteroids_prospected"]):
        mismatches.append(
            "asteroids_prospected mismatch: "
            f"expected {expected['asteroids_prospected']}, got {actual_asteroids_prospected}"
        )

    actual_present = int(actual_row.get("asteroids_with_commodity_present") or 0)
    if actual_present != int(expected["asteroids_with_commodity_present"]):
        mismatches.append(
            "asteroids_with_commodity_present mismatch: "
            f"expected {expected['asteroids_with_commodity_present']}, got {actual_present}"
        )

    actual_sum = float(actual_row.get("sum_percentage") or 0.0)
    expected_sum = float(expected["sum_percentage"])
    if abs(actual_sum - expected_sum) > FLOAT_TOLERANCE:
        mismatches.append(
            "sum_percentage mismatch: "
            f"expected {expected_sum}, got {actual_sum}, tolerance {FLOAT_TOLERANCE}"
        )

    if mismatches:
        message = (
            "ring_summary integrity check failed for "
            f"ring={TARGET_RING!r}, commodity={TARGET_COMMODITY!r}:\n"
            + "\n".join(f"- {item}" for item in mismatches)
        )
        raise AssertionError(message)
