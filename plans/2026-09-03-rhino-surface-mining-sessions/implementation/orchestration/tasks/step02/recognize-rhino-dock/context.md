# Task Context: Recognize Rhino Dock

## Requirements

- End the existing active mining session only for a stripped, case-insensitive
  Rhino `DockSRV` (`SRVType` `mev_rhino`), with reason `Rhino SRV docked`.
- Leave inactive, non-Rhino, missing, blank, and non-string dock values
  unchanged.
- Preserve the existing Rhino launch, Prospector launch, and
  supercruise/FSD stop paths.
- Demonstrate public shared-state transitions through the registered EDMC
  journal callback; do not change callback wiring.

## Existing Patterns

- `JournalProcessor.handle_entry` dispatches event names to private handlers.
- Step 1 provides `_is_rhino_srv` and `_process_launch_srv`; the predicate is
  the single defensive normalization seam to reuse.
- `_update_mining_state(False, ...)` sets the journal end time, ends the
  recorder session, invokes the end callback, refreshes EDSM, and leaves
  shared-state publication to `handle_entry`.
- Journal simulation tests use `unittest` and injected callbacks; harness
  tests call the registered `load.journal_entry` callback through
  `harness.fire_event`.

## Dependency Map

`DockSRV` -> `JournalProcessor.handle_entry` -> private Rhino dock handler ->
`_update_mining_state(False, ...)` -> `MiningState`, recorder, callbacks ->
existing shared `edmc_mining_active` publication.

## Constraints and Risks

- `load.py`, vendored harness files, UI, preferences, and schemas are out of
  scope.
- The installed `.venv` uses Python 3.12.3, while the documented EDMC runtime
  target is Python 3.13; test results are useful but need a 3.13 release check.
- No CODEASSIST.md exists. The repository AGENTS.md and approved Rhino design
  govern this task.
