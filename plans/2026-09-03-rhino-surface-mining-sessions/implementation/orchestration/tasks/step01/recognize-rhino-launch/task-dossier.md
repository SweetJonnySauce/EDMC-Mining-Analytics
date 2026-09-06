# Task 01 Dossier: Recognize Rhino Launch

## Approved scope

Implement only `LaunchSRV` recognition for `mev_rhino` using the existing
mining-session start transition. Keep duplicate launches idempotent. Do not
implement Rhino docking.

## Constraints

- Use strict RED -> GREEN -> REFACTOR.
- Use the existing `.venv`; do not install dependencies.
- Do not touch `README.md`, `edmc_mining_analytics/version.py`, `load.py`,
  vendored harness files, UI, preferences, schema, or DockSRV behavior.
- Never stage, commit, push, or otherwise alter Git history/index.

## Execution record

Focused tests were added before production code. RED validation produced the
expected two Rhino-start failures because `LaunchSRV` had no handler, while
the selected Prospector tests passed. The minimal production change added
dedicated dispatch, a defensive `SRVType` predicate, and an inactive-only
start transition. The required command then passed with 4 tests selected.

The initial GREEN run found a test-only missing `timezone` import after the
behavioral assertions had passed; it was corrected and the focused command was
rerun once. Scoped review found no DockSRV behavior or prohibited file changes.
