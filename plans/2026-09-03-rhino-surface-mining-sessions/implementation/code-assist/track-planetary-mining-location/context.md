# Context — Track Planetary Mining Location

## Requirement

For a Rhino surface-mining visit, a `Touchdown` following `ApproachBody` and preceding the next supercruise/FSD transition may identify a site through `NearestDestination`. When that value encodes a Planetary Mining Location index, retain the site for the Rhino mining session on the current body.

## Relevant paths

| Path | Role |
|---|---|
| `edmc_mining_analytics/journal.py` | Owns journal order, mining state transitions, and location detection. |
| `edmc_mining_analytics/state.py` | Holds resettable per-session metadata. |
| `edmc_mining_analytics/session_recorder.py` | Builds the persisted `meta.location` payload. |
| `tests/test_journal_simulation.py` | Unit-level journal event simulation. |
| `tests/test_session_recorder_prospect_summary.py` | Unit-level payload assertions. |

## Dependency map

`ApproachBody` → approach context → valid `Touchdown` candidate → `LaunchSRV(mev_rhino)` → `MiningState` location fields → `SessionRecorder._build_payload()` → `meta.location`.

`SupercruiseEntry` or `FSDJump` clears the approach candidate and keeps the existing session-stop behavior unchanged.

## Constraints and decisions

- Use the exact journal `NearestDestination` marker shape and require a positive decimal index.
- Preserve the body in `meta.location.body`; store the human-readable site label separately.
- No boundary, preference, network, UI, schema migration, or `load.py` change.
- The repository's current virtual environment is Python 3.12.3; EDMC release validation still requires Python 3.13.
