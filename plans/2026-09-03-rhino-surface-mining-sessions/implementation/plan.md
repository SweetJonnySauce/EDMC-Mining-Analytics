# Rhino Surface-Mining Sessions: Implementation Plan

## Implementation checklist

- [x] Step 1: Recognize Rhino launch as a mining-session start
- [x] Step 2: Recognize Rhino dock as a session end and prove the full event flow

## Phase status

| Phase | Status | Goal |
|---|---|---|
| 1 | Completed | Add the Rhino launch boundary without changing asteroid mining behavior. |
| 2 | Completed | Add the Rhino dock boundary and prove both session types through the EDMC harness. |
| 3 | Completed | Capture a valid planetary-mining touchdown and persist its signal index with the Rhino session location. |
| 4 | Completed | Reconcile Rhino refinements with assumed total SRV cargo counts. |
| 5 | Completed | Persist session kind and gate asteroid-only limpet behavior. |
| 6 | Completed | Tolerate out-of-order Rhino `Cargo` and `MiningRefined` journal events. |
| 7 | Completed | Request estimated sell prices for surface-mined commodities. |
| 8 | Completed | Use the Rhino's 72t capacity for live surface-mining cargo metrics. |

## Phase 1 — Rhino launch boundary

| Stage | Description | Status |
|---|---|---|
| 1.1 | Add normalized Rhino `LaunchSRV` recognition and reuse the established session-start transition. | Completed |
| 1.2 | Add focused journal simulation coverage for start, ignore, and duplicate-launch behavior. | Completed |

### Step 1: Recognize Rhino launch as a mining-session start

**Objective:** Extend `JournalProcessor` so an inactive session starts when a `LaunchSRV` journal event has `SRVType` `mev_rhino`, while preserving the existing Prospector start contract.

**Implementation guidance:**

- Add a small, private SRV-type normalization/predicate seam in the journal processor. It must safely reject missing, non-string, blank, and non-Rhino types.
- Route `LaunchSRV` through a dedicated Rhino handler rather than expanding the existing `LaunchDrone` handler.
- If the normalized type is Rhino and `state.is_mining` is false, call the existing `_update_mining_state(True, "Rhino SRV launched", ...)` path with the journal timestamp, entry, and EDMC shared state.
- If a Rhino session is already active, return without resetting state, recorder contents, counters, timestamps, or UI scheduling. This implements the agreed continuation rule when no supercruise transition was observed.
- Do not add session-kind, SRV-ID, configuration, preference, thread, or UI state. Existing mutually exclusive `is_mining` state remains authoritative.

**Tests to add or update alongside the code:**

- In `tests/test_journal_simulation.py`, prove a Rhino launch activates mining, uses the journal timestamp, invokes the start callback/recorder, and records the Rhino start reason.
- Prove non-Rhino and malformed `LaunchSRV` entries leave state unchanged.
- Prove a repeated Rhino launch retains the original start timestamp and existing session state.
- Retain or run the existing Prospector-start assertions as regression coverage.

**Integration:** This step only reuses the current session-transition, recorder, shared-state, UI, and overlay pathways. It does not alter their contracts.

**Demo:** Replay a synthetic `LaunchSRV` event for `mev_rhino`; the plugin reports an active mining session with `Rhino SRV launched` as its start reason. Replaying that event without a supercruise transition leaves the same session active.

**Verification:**

```bash
source .venv/bin/activate && python -m pytest tests/test_journal_simulation.py -k 'rhino or prospect'
```

**Phase completion rule:** Mark stages 1.1 and 1.2 completed, then set Phase 1 to `Completed` only after the targeted test command passes.

## Phase 2 — Rhino dock boundary and end-to-end proof

| Stage | Description | Status |
|---|---|---|
| 2.1 | Add normalized Rhino `DockSRV` recognition and reuse the established session-end transition. | Completed |
| 2.2 | Extend unit and harness coverage for start, stop, supercruise, and unrelated-event contracts. | Completed |

### Step 2: Recognize Rhino dock as a session end and prove the full event flow

**Objective:** End an active mining session when a Rhino `DockSRV` arrives, while preserving all existing supercruise/FSD, session-recorder, and asteroid-mining behavior.

**Implementation guidance:**

- Route `DockSRV` through a dedicated Rhino handler using the same normalization seam from Step 1.
- When the entry is Rhino and `state.is_mining` is true, call `_update_mining_state(False, "Rhino SRV docked", ...)` with the journal timestamp and context.
- Treat an inactive session or a non-Rhino dock as a no-op.
- Leave existing `SupercruiseEntry` and `FSDJump` stop paths unchanged. A supercruise entry naturally closes the active Rhino session; a subsequent Rhino launch then starts a new session through Step 1.
- Do not use Planetary Mining Location scans as boundaries. They remain observational context only.

**Tests to add or update alongside the code:**

- In `tests/test_journal_simulation.py`, prove Rhino dock ends an active session, preserves the journal end timestamp, calls the end callback/recorder, and uses `Rhino SRV docked` as its reason.
- Prove non-Rhino and malformed dock events do not end an active session.
- Prove Rhino start → `SupercruiseEntry` → Rhino start creates two distinct sessions, meeting the agreed recovery rule.
- In `tests/test_harness_integration.py`, replay Rhino launch/dock through the registered EDMC journal callback and assert shared `edmc_mining_active` changes from `True` to `False`.
- Keep a Prospector launch → supercruise stop harness assertion in the same test scope to protect existing behavior.

**Integration:** This completes the event-to-state-to-recorder path introduced in Step 1. It verifies the actual `load.py` callback wiring without modifying the immutable vendored harness.

**Demo:** Through the harness, replay `LaunchSRV(mev_rhino)` followed by `DockSRV(mev_rhino)`. The public EDMC shared state starts active and ends inactive, with the recorder finalizing the session using Rhino-specific reasons.

**Verification:**

```bash
source .venv/bin/activate && python -m pytest tests/test_journal_simulation.py
source .venv/bin/activate && python -m pytest tests/test_harness_integration.py -k 'rhino or session'
source .venv/bin/activate && python -m pytest
```

## Phase 7 — Surface estimated credits

| Stage | Description | Status |
|---|---|---|
| 7.1 | Request a market price when Rhino cargo reconciliation confirms a commodity. | Completed |
| 7.2 | Prove the Gold request through a focused journal simulation. | Completed |

The existing `MarketSearchService` continues to deduplicate requests and run the lookup outside the journal/UI thread. Asteroid pricing flow is unchanged.

## Phase 8 — Rhino cargo capacity

| Stage | Description | Status |
|---|---|---|
| 8.1 | Model the 72t Rhino capacity without replacing the ship-capacity state. | Completed |
| 8.2 | Use short SRV Cargo totals for live surface cargo tonnage. | Completed |
| 8.3 | Apply the session capacity to `% Full`, overlay bars, and the in-plugin summary. | Completed |

Asteroid sessions continue to use the ship cargo capacity. Session reports retain the separately recorded ship capacity.

**Phase completion rule:** Mark stages 2.1 and 2.2 completed, then set Phase 2 to `Completed` only after all three commands pass.

## Phase 3 — Planetary mining location metadata

| Stage | Description | Status |
|---|---|---|
| 3.1 | Capture only an approach-scoped `Touchdown` whose `NearestDestination` is a Planetary Mining Location signal and parse its index. | Completed |
| 3.2 | Seed the next Rhino session with the captured body and signal label, then persist it in session location metadata. | Completed |
| 3.3 | Add focused unit coverage for valid capture, malformed/unrelated input, and supercruise expiry. | Completed |

### Step 3: Track the planetary mining location for a Rhino session

**Objective:** When a ship touches down after `ApproachBody` and before the next supercruise/FSD transition at a `NearestDestination` matching `$SAA_Unknown_Signal:#type=$PlanetaryMiningLocation_Name;:#index=N;`, associate `Planetary Mining Location Signal (N)` with the Rhino session on that body.

**Implementation guidance:**

- Treat the touchdown as metadata, never as a session boundary.
- Keep the most recent valid touchdown as a journal-processor candidate for the current approach leg. Clear it on `SupercruiseEntry` or `FSDJump`.
- On the following Rhino launch, use the candidate body as the missing launch-location fallback and store the parsed positive index in session state. A valid touchdown received while a session is active updates that session's metadata directly.
- Persist the label under the existing session payload's `meta.location` object while retaining `body` as the planetary body, not a composite display string.
- Ignore missing/non-string/malformed destinations, non-positive indexes, touchdowns without an approach context, and a touchdown for a different body. Do not add settings, networking, UI work, or changes to asteroid mining behavior.

**Tests to add or update alongside the code:**

- A synthetic `ApproachBody` → matching `Touchdown` (`index=13`) → Rhino launch records the body and `Planetary Mining Location Signal (13)` in session metadata.
- Unrelated or malformed touchdown destinations do not populate the location.
- A supercruise/FSD transition expires a pending touchdown so a later Rhino launch cannot inherit it.
- Existing Rhino start/stop and asteroid tests remain green.

**Verification:**

```bash
source .venv/bin/activate && python -m pytest tests/test_journal_simulation.py tests/test_session_recorder_prospect_summary.py
source .venv/bin/activate && python -m pytest
```

**Phase completion rule:** Mark stages 3.1 through 3.3 completed, then set Phase 3 to `Completed` only after both verification commands pass.

## Phase 4 — SRV refinement cargo reconciliation

| Stage | Description | Status |
|---|---|---|
| 4.1 | Queue active-session `MiningRefined` commodity identities for SRV cargo reconciliation. | Completed |
| 4.2 | Allocate positive total-count deltas across queued refinements. | Completed |
| 4.3 | Prove mixed commodities and non-increasing counts do not misattribute cargo. | Completed |

### Step 4: Reconcile Rhino refinements with SRV cargo totals

Treat `Cargo.Count` as the total of all SRV commodities, by explicit user direction. Never assign that total wholesale to the most recently refined type; allocate only each positive delta across queued refinements in journal order.

## Phase 5 — Session-kind discrimination

| Stage | Description | Status |
|---|---|---|
| 5.1 | Persist `ASTEROID` or `SURFACE` with the active mining session. | Completed |
| 5.2 | Gate asteroid-only limpet, prospector, collector, and asteroid-prospect handling. | Completed |
| 5.3 | Prove Rhino and Prospector session kinds with unit coverage. | Completed |

Rhino `LaunchSRV` starts `SURFACE`; Prospector `LaunchDrone` starts `ASTEROID`. The kind resets with session state.

## Phase 6 — Order-tolerant surface cargo reconciliation

| Stage | Description | Status |
|---|---|---|
| 6.1 | Buffer positive short-SRV cargo deltas until their Rhino refinements arrive. | Completed |
| 6.2 | Drop an unfulfilled prior commodity at a surface-mining commodity transition. | Completed |
| 6.3 | Add focused regression coverage and prove asteroid sessions remain unaffected. | Completed |

**Objective:** Reconcile the Rhino journal ordering observed on 2026-09-06, where a short `Cargo.Count` increase can precede its corresponding `MiningRefined` event. The reconciliation applies exclusively to active `SURFACE` sessions. It retains positive cargo credits until refinements arrive and discards refinements that never materialize when the player moves to a different commodity. Full cargo-inventory and limpet handling for asteroid sessions remains unchanged.

**Verification:**

```bash
source .venv/bin/activate && python -m pytest tests/test_journal_simulation.py -k 'srv_cargo or session_kind'
source .venv/bin/activate && python -m pytest
```

## Implementation guardrails

| Check | Expected result | Status before implementation |
|---|---|---|
| EDMC entry point and supported APIs | No change to `load.py`; only journal dispatch changes. | Yes |
| Runtime responsiveness and Tk safety | No worker, network, timer, or widget behavior added. | Yes |
| Preferences and persisted configuration | No new settings or keys. | Yes |
| Logger and error handling | Existing logger and safe no-op paths are reused; no `print`. | Yes |
| Python compatibility | Validate under EDMC's Python 3.13 runtime before release. | Pending environment validation |
| Vendored harness integrity | Do not edit `tests/harness.py` or `tests/edmc/`. | Yes |

## Final handoff requirements

The implementation report must list changed test files, the exact commands above, pass/fail/skip outcomes, and any unrun EDMC manual smoke test. It must also note that the supplied log has unmatched Rhino boundary records and that the approved duplicate-launch rule governs them.
