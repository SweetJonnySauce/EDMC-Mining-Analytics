from collections import deque
from datetime import datetime, timedelta, timezone

from edmc_mining_analytics.state import (
    MiningState,
    MiningSessionKind,
    RPM_LOOKBACK_SECONDS,
    active_session_cargo_capacity,
    register_refinement,
    update_rpm,
)


def test_update_rpm_uses_fixed_lookback_window() -> None:
    state = MiningState()
    now = datetime(2026, 3, 28, 15, 0, 0, tzinfo=timezone.utc)
    state.refinement_lookback_seconds = 2
    state.recent_refinements = deque(
        [
            now - timedelta(seconds=61),
            now - timedelta(seconds=59),
            now - timedelta(seconds=10),
        ]
    )

    rpm = update_rpm(state, now)

    expected_rpm = 60.0 / float(RPM_LOOKBACK_SECONDS)
    assert rpm == expected_rpm
    assert state.current_rpm == expected_rpm
    assert state.refinement_lookback_seconds == RPM_LOOKBACK_SECONDS
    assert len(state.recent_refinements) == 1


def test_register_refinement_tracks_max_with_fixed_window() -> None:
    state = MiningState()
    base = datetime(2026, 3, 28, 15, 0, 0, tzinfo=timezone.utc)

    register_refinement(state, base - timedelta(seconds=70))
    register_refinement(state, base - timedelta(seconds=30))
    register_refinement(state, base - timedelta(seconds=20))
    register_refinement(state, base - timedelta(seconds=5))
    rpm = update_rpm(state, base)

    expected_rpm = 60.0 / float(RPM_LOOKBACK_SECONDS)
    assert rpm == expected_rpm
    assert state.current_rpm == expected_rpm
    assert state.max_rpm >= expected_rpm


def test_active_session_cargo_capacity_uses_rhino_capacity_only_for_surface_mining() -> None:
    state = MiningState(cargo_capacity=168)

    state.mining_session_kind = MiningSessionKind.SURFACE
    assert active_session_cargo_capacity(state) == 72

    state.mining_session_kind = MiningSessionKind.ASTEROID
    assert active_session_cargo_capacity(state) == 168
