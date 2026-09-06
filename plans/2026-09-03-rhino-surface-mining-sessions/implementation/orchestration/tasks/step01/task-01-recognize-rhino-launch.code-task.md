# Task: Recognize Rhino Launch as a Mining-Session Start

## Description

Extend `JournalProcessor` so a `LaunchSRV` journal event for the Rhino SRV
(`SRVType` equal to `mev_rhino`, case-insensitively) starts the existing
single mining session when no session is active. This is the minimal first
half of Rhino surface-mining session support: it must reuse the established
session-start transition and must not introduce a parallel session model,
preferences, UI state, or SRV-ID tracking.

Implement and test this task only. Do not implement `DockSRV` handling; that
is Step 2.

## Background

Asteroid mining currently begins on a Prospector `LaunchDrone` event. Rhino
surface mining uses `LaunchSRV` with `SRVType: "mev_rhino"` instead. A player
cannot have both types of mining session simultaneously, so the existing
`MiningState.is_mining` flag remains authoritative.

The supplied log includes repeated Rhino launches without an intervening dock.
The approved rule is idempotency: while a mining session is active, a repeated
Rhino launch continues that same session and must not reset its timestamp,
counters, recorder data, or UI scheduling. If the existing supercruise path
has ended the session, a later Rhino launch starts a fresh one through this
same code path.

## Reference Documentation

**Required:**

- Design: `plans/2026-09-03-rhino-surface-mining-sessions/design/detailed-design.md`
- Implementation plan: `plans/2026-09-03-rhino-surface-mining-sessions/implementation/plan.md` (Step 1)

**Additional References (if relevant to this task):**

- `plans/2026-09-03-rhino-surface-mining-sessions/research/log-evidence.md` (observed Rhino event shape and boundary ambiguity)
- `tests/test_journal_simulation.py` (existing journal processor test conventions)

**Note:** You MUST read the detailed design document before beginning
implementation. Read the implementation plan and additional references as
needed for context.

## Technical Requirements

1. In `edmc_mining_analytics/journal.py`, add a small private normalization or
   predicate seam that treats only string `SRVType` values whose stripped,
   case-normalized form is `mev_rhino` as Rhino; safely reject missing,
   non-string, blank, and other values.
2. Route `LaunchSRV` through a dedicated Rhino-launch handler. Do not expand
   or change the existing `LaunchDrone`/Prospector handler contract.
3. When the event is Rhino and `self._state.is_mining` is false, call the
   existing `_update_mining_state` start path with the exact reason
   `Rhino SRV launched`, journal timestamp, EDMC shared state, and journal
   entry so the established recorder, UI, overlay, counters, and location
   behavior is reused.
4. When the event is Rhino and a mining session is already active, perform no
   state transition and do not reset session data. A non-Rhino or malformed
   `LaunchSRV` is also a no-op.
5. Do not add a session kind, SRV ID, configuration key, preference, thread,
   network call, persistent schema change, or Planetary Mining Location
   boundary handling.
6. Preserve existing Prospector launch behavior and all existing supercruise
   and FSD session-stop behavior unchanged.
7. Add or update focused unit tests in `tests/test_journal_simulation.py` with
   the existing injected-callback style. Do not modify `tests/harness.py` or
   anything under `tests/edmc/`.
8. Do not stage, commit, push, format unrelated files, or modify the existing
   unrelated `README.md` and `edmc_mining_analytics/version.py` worktree
   changes.

## Dependencies

- Existing `JournalProcessor.handle_entry`, `_process_launch_drone`, and
  `_update_mining_state` behavior in `edmc_mining_analytics/journal.py`.
- Existing `MiningState` session fields and injected `on_session_start`
  callback; no data-model changes are required.
- Python test environment documented by the repository. Use the existing
  `.venv` if it is usable; do not create or install an environment for this
  task without explicit direction.

## Implementation Approach

1. Read the required design and Step 1 plan, then inspect the current event
   dispatch, Prospector handler, session transition method, and the adjacent
   journal-simulation tests. Confirm the worktree before editing and preserve
   unrelated changes.
2. First add focused failing tests for: a Rhino launch starting an inactive
   session with the journal timestamp and start callback; non-Rhino and
   malformed `LaunchSRV` entries being ignored; and a repeated Rhino launch
   retaining the original start timestamp and active session state.
3. Make the smallest production change: a defensive Rhino predicate and a
   dedicated `LaunchSRV` handler that delegates to the established start
   transition only when inactive. Keep the duplicate-launch branch an
   explicit no-op.
4. Run the targeted Step 1 command. If it fails, diagnose and make only
   task-scoped corrections; do not begin `DockSRV` work. Report exact test
   results and any unrun validation.

## Acceptance Criteria

1. **Rhino launch begins an inactive session**
   - Given a new `JournalProcessor` with an inactive `MiningState`
   - When it receives `LaunchSRV` with `SRVType: "mev_rhino"` and a journal
     timestamp
   - Then `is_mining` becomes true through the existing session-start path,
     the state start time uses that journal timestamp, and the start callback
     or recorder-facing reason is `Rhino SRV launched`.

2. **SRV type matching is defensive and case-insensitive**
   - Given inactive mining state
   - When the processor receives `LaunchSRV` events with an upper/mixed-case
     Rhino type, another SRV type, missing `SRVType`, a blank value, or a
     non-string value
   - Then only the normalized Rhino value starts mining and all other entries
     leave mining state unchanged without raising an exception.

3. **Repeated Rhino launch continues the existing session**
   - Given a Rhino launch has already activated a session with established
     timestamp and non-default session data
   - When another normalized Rhino `LaunchSRV` arrives before a session-ending
     event
   - Then the session remains active and its original start timestamp,
     counters, recorder-facing state, and session-start callback count remain
     unchanged.

4. **Existing asteroid-mining start behavior remains intact**
   - Given an inactive session
   - When a Prospector `LaunchDrone` event is processed
   - Then the existing session-start behavior and reason remain unchanged;
     existing Prospector coverage stays green.

5. **Focused unit coverage passes**
   - Given the Step 1 implementation and updated
     `tests/test_journal_simulation.py`
   - When running `source .venv/bin/activate && python -m pytest
     tests/test_journal_simulation.py -k 'rhino or prospect'`
   - Then all selected tests pass.

## Metadata

- **Complexity**: Low
- **Labels**: journal-events, mining-sessions, rhino, srv, tdd
- **Required Skills**: Python, pytest, EDMC journal-plugin integration
