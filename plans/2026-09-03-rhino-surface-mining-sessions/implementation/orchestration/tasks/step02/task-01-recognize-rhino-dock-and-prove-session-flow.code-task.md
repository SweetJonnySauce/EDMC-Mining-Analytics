# Task: Recognize Rhino Dock as a Mining-Session End and Prove the Session Flow

## Description

Extend `JournalProcessor` so a `DockSRV` journal event for the Rhino SRV
(`SRVType` equal to `mev_rhino`, case-insensitively) ends the existing active
mining session. Complete the minimal Rhino surface-mining boundary feature by
proving the journal-to-EDMC-callback behavior without creating a parallel
session model, new configuration, or UI state.

This task includes only the Step 2 dock boundary and its required coverage.
It must reuse the Rhino normalization seam and launch behavior already added
in Step 1; do not broaden the feature to other SRVs, location scans, or
session persistence changes.

## Background

Asteroid sessions start from a Prospector `LaunchDrone` and stop at
`SupercruiseEntry` or `FSDJump`. Rhino surface-mining sessions now start from
`LaunchSRV` for `mev_rhino`. The corresponding Rhino end boundary is
`DockSRV` for the same normalized type.

Only one mining session can be active, so `MiningState.is_mining` remains the
single authority. A valid Rhino dock ends an active session through the
established session-transition path. A non-Rhino, malformed, or inactive dock
is a no-op. The existing supercruise path also ends an active Rhino session;
therefore a later Rhino launch creates a distinct new session. Planetary
Mining Location scans are observational context, never boundaries.

## Reference Documentation

**Required:**

- Design: `plans/2026-09-03-rhino-surface-mining-sessions/design/detailed-design.md`
- Implementation plan: `plans/2026-09-03-rhino-surface-mining-sessions/implementation/plan.md` (Step 2)

**Additional References (if relevant to this task):**

- `plans/2026-09-03-rhino-surface-mining-sessions/research/log-evidence.md` (observed event shapes)
- `tests/test_journal_simulation.py` (injected journal callback and recorder conventions)
- `tests/test_harness_integration.py` (registered EDMC journal callback conventions)

**Note:** You MUST read the detailed design document before beginning
implementation. Read the implementation plan and additional references as
needed for context.

## Technical Requirements

1. In `edmc_mining_analytics/journal.py`, route `DockSRV` to a dedicated
   private handler using the existing `_is_rhino_srv` normalization/predicate
   seam from Step 1. Do not duplicate or weaken that defensive type check.
2. If a normalized Rhino `DockSRV` arrives while `self._state.is_mining` is
   true, call the established `_update_mining_state` stop path with the exact
   reason `Rhino SRV docked`, the journal timestamp, EDMC shared state, and
   journal entry.
3. A non-Rhino, missing, blank, or non-string `SRVType` dock, and a valid
   Rhino dock while inactive, must be safe no-ops. They must not alter session
   state, timestamps, recorder data, or invoke the session-end callback.
4. Preserve the current `LaunchSRV` start contract, Prospector start
   behavior, and `SupercruiseEntry`/`FSDJump` stop paths. A Rhino start,
   supercruise stop, then Rhino start must result in two separate starts.
5. Add focused unit coverage in `tests/test_journal_simulation.py` for a
   Rhino dock ending an active session with its journal end timestamp,
   callback/recorder reason, ignored invalid docks, and the
   Rhino-start/supercruise/Rhino-start recovery sequence.
6. Add a harness test in `tests/test_harness_integration.py` that dispatches
   Rhino launch and dock events through the registered EDMC journal callback
   and verifies public shared `edmc_mining_active` transitions from true to
   false. Keep a Prospector launch to supercruise-stop assertion in that test
   scope as regression coverage.
7. Do not modify `load.py`, `tests/harness.py`, anything under `tests/edmc/`,
   preferences, schemas, session data contracts, dependencies, or UI code.
8. Do not stage, commit, push, format unrelated files, or modify the existing
   unrelated `README.md` and `edmc_mining_analytics/version.py` worktree
   changes. Use the existing `.venv` if usable; do not install or recreate an
   environment without explicit direction.

## Dependencies

- Step 1's existing `JournalProcessor._is_rhino_srv` and
  `_process_launch_srv` behavior.
- Existing `JournalProcessor._update_mining_state`, session recorder, and
  shared-state publication contracts.
- Existing EDMC harness callback shim and non-vendored integration-test file.
- Python test environment already present in the repository.

## Implementation Approach

1. Read the required design and Step 2 plan. Inspect the existing dispatch,
   Rhino launch helper, stop transition, journal-simulation tests, and
   harness callback registration. Confirm the worktree and preserve unrelated
   changes.
2. First add focused failing unit tests that exercise an active Rhino session
   ending at `DockSRV`, ignored invalid/inactive docks, and a Rhino launch →
   supercruise → Rhino launch sequence. Extend the recorder stub only as
   needed to observe the established stop call.
3. Add the smallest production change: a `DockSRV` dispatch branch and a
   dedicated handler that delegates to the established stop transition only
   for an active normalized Rhino session.
4. Add one focused harness test that uses the registered journal callback to
   verify Rhino launch/dock shared-state transitions and retains an explicit
   Prospector/supercruise assertion. Do not change the vendored harness or
   runtime wiring.
5. Run all three Step 2 verification commands. Only after all pass, update
   the plan's Step 2 checkbox, stages 2.1/2.2, and Phase 2 status according
   to its stated completion rule. Record exact test outcomes for handoff.

## Acceptance Criteria

1. **Rhino dock ends an active session**
   - Given an active mining state started by a normalized Rhino `LaunchSRV`
   - When the processor receives a normalized Rhino `DockSRV` with a journal
     timestamp
   - Then mining becomes inactive through the existing stop path, the end
     time uses that timestamp, and the session-end callback or recorder-facing
     reason is `Rhino SRV docked`.

2. **Invalid and inactive docks are harmless**
   - Given either an inactive mining state or dock entries whose `SRVType` is
     non-Rhino, missing, blank, or non-string
   - When those `DockSRV` entries are processed
   - Then no session state, timestamp, recorder data, or end callback changes
     and no exception is raised.

3. **Supercruise recovery creates a new Rhino session**
   - Given a Rhino launch has activated a mining session
   - When `SupercruiseEntry` ends it and a later normalized Rhino launch is
     processed
   - Then the second launch starts a distinct session with its new journal
     timestamp, while the unchanged supercruise stop path remains the reason
     for the first end.

4. **EDMC callback flow publishes both Rhino boundaries**
   - Given the plugin is initialized in the existing harness and its journal
     callback is registered
   - When the harness fires normalized Rhino launch then dock events
   - Then public shared `edmc_mining_active` is true after launch and false
     after dock; a Prospector launch followed by supercruise also still
     transitions from true to false in the same test scope.

5. **Step 2 validation and plan completion evidence are complete**
   - Given the scoped source and test updates
   - When running `source .venv/bin/activate && python -m pytest
     tests/test_journal_simulation.py`, `source .venv/bin/activate && python
     -m pytest tests/test_harness_integration.py -k 'rhino or session'`, and
     `source .venv/bin/activate && python -m pytest`
   - Then all commands pass, no immutable harness files changed, and the plan
     marks Step 2, stages 2.1/2.2, and Phase 2 completed only after that
     evidence exists.

## Metadata

- **Complexity**: Medium
- **Labels**: journal-events, mining-sessions, rhino, srv, harness, tdd
- **Required Skills**: Python, pytest, EDMC journal-plugin integration
