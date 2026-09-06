# Task Context: Recognize Rhino Launch

## Requirements

- Start the existing mining session on `LaunchSRV` only when `SRVType` is the
  stripped, case-insensitive Rhino identifier `mev_rhino` and mining is inactive.
- Ignore malformed and non-Rhino values safely.
- Treat a repeated Rhino launch while active as an idempotent continuation.
- Preserve Prospector and all existing stop handling. Dock handling is out of scope.

## Existing Patterns

- `JournalProcessor.handle_entry` dispatches journal event names to dedicated
  private handlers in `edmc_mining_analytics/journal.py`.
- `_process_launch_drone` starts a Prospector session through
  `_update_mining_state`; that transition owns reset, recorder, UI, and
  shared-state behavior.
- `tests/test_journal_simulation.py` uses `unittest` with injected session
  callbacks and synthetic timestamped events.

## Dependencies and Boundaries

`LaunchSRV` dispatch -> private Rhino predicate/handler -> existing
`_update_mining_state(True, ...)` -> `MiningState` and callbacks.

No state schema, preferences, UI, `load.py`, harness files, or DockSRV behavior
may change. The existing task file is the code-task-generator dossier; no
separate code-task-generator agent was available in this task context.
