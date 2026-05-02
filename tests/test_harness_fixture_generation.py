from __future__ import annotations

from tests.harness_test_utils import (
    PLATINUM_ASTEROID_COUNT_MAX,
    PLATINUM_ASTEROID_COUNT_MIN,
    PLATINUM_PRESENT_AVERAGE_MAX,
    PLATINUM_PRESENT_AVERAGE_MIN,
    PLATINUM_PERCENTAGE_MAX,
    PLATINUM_PERCENTAGE_MIN,
    build_generated_platinum_session_profile,
    load_generated_platinum_session_profile,
    load_test_journal_events,
)


def test_generated_platinum_profile_respects_requested_bounds() -> None:
    profile = build_generated_platinum_session_profile(seed=12345)

    assert PLATINUM_ASTEROID_COUNT_MIN <= profile["asteroid_count"] <= PLATINUM_ASTEROID_COUNT_MAX
    assert len(profile["platinum_yields"]) == profile["asteroid_count"]
    assert profile["platinum_absent_count"] + profile["platinum_present_count"] == profile["asteroid_count"]
    assert profile["platinum_absent_count"] > 0
    assert sum(profile["content_summary"].values()) == profile["asteroid_count"]
    assert len(profile["platinum_percentages"]) == profile["platinum_present_count"]
    assert all(
        PLATINUM_PERCENTAGE_MIN <= float(value) <= PLATINUM_PERCENTAGE_MAX
        for value in profile["platinum_percentages"]
    )
    assert PLATINUM_PRESENT_AVERAGE_MIN <= float(profile["platinum_present_average"]) <= PLATINUM_PRESENT_AVERAGE_MAX


def test_generated_platinum_profile_is_applied_to_sample_journal(monkeypatch) -> None:
    monkeypatch.setenv("EDMCMA_HARNESS_PLATINUM_SEED", "24680")
    profile = load_generated_platinum_session_profile(force_refresh=True)
    payload = load_test_journal_events(rebase_to_now=False)
    sequence = payload["sample_mining_session"]

    prospected_events = [
        entry
        for entry in sequence
        if entry.get("event") == "ProspectedAsteroid"
    ]
    platinum_yields = []
    for entry in prospected_events:
        platinum = next(
            (
                round(float(material["Proportion"]), 6)
                for material in (entry.get("Materials") or [])
                if str(material.get("Name") or "").strip().lower() == "platinum"
            ),
            None,
        )
        platinum_yields.append(platinum)

    assert len(prospected_events) == profile["asteroid_count"]
    assert platinum_yields == [
        None if value is None else round(float(value), 6)
        for value in profile["platinum_yields"]
    ]
