# Goal: Fix issue #81 version-worker access to Tk

Status: Completed; implementation and available validation finished, GUI/Windows checks explicitly skipped.
Created: 2026-11-07.
Source: https://github.com/SweetJonnySauce/EDMC-Mining-Analytics/issues/81

Follow `AGENTS.md`. Update stages as work completes; mark a phase Completed only when every stage in it is complete. Record exact verification commands and outcomes below, in phase/stage order.

## Problem and scope

The version-check worker calls `_handle_latest_version()` -> `_log_version_status()` -> `_schedule_version_label_update()` -> `root.after()`. Registering the callback itself accesses Tk from the worker. The issue reports `RuntimeError: main thread is not in main loop`. The auto-update worker invokes `_handle_update_ready()`, which reaches the same Tk scheduling method.

Fix only delivery of version-check and auto-update-ready notifications to the UI. Preserve release/tag lookup behavior, version comparison, label wording, update-ready precedence, download/install behavior, and existing user settings. The only intended visible difference is reliable label updates, with at most one short polling interval of delivery delay.

Out of scope: mining detection, cargo, RPM, overlays, session logging, logger identity, preferences, generic UI dispatch, EDSM/market refresh callbacks, and unrelated worker/resource cleanup. This change does not claim to make every plugin worker Tk-safe.

## Contracts and design

1. Version/update workers perform network work and publish data only. They must not call UI methods, obtain a Tk root, call `after`, `winfo_exists`, `event_generate`, or update Tk variables.
2. Version state used for presentation (`_latest_version`, `_update_ready_version`) is applied on the main thread. Preserve the existing normalization, comparisons, and merge rules by moving the current handlers behind the notification consumer rather than rewriting them.
3. Introduce a small data-only `version_notifications.py` module containing typed latest-version/update-ready notifications and a thread-safe mailbox. Publishing must be nonblocking with respect to the UI; processing must never hold a mailbox lock while invoking UI/application callbacks.
4. Create a fresh mailbox for each `plugin_start()` lifecycle before starting either worker. Bind each worker's publisher to that specific mailbox at launch/construction; never resolve the current mailbox dynamically when an old worker completes.
5. Notifications arriving before `plugin_app()` are retained. `plugin_app()` drains them on the main thread after building the UI and then establishes one recurring `after` timer (proposed interval: 100 ms). Repeated attachment must not create duplicate timers.
6. The main-thread consumer dispatches notifications to the existing version-state handlers and renders the label directly on the main thread. Remove the worker-accessible `root.after()` path. Preserve arrival ordering; test latest-version and update-ready results in either order using the existing merge rules.
7. `plugin_stop()` marks notification delivery inactive and closes its mailbox, cancels the owned timer on the main thread, and discards pending results before waiting for workers. Late results are rejected without touching Tk. Stop-before-app and repeated stop are harmless.
8. An old worker must never deliver results into a subsequent start's mailbox. A stale timer must not render or rearm after stop/restart; bind callbacks to the lifecycle mailbox and verify identity before dispatch/rearm. Clear timer ownership consistently when callbacks run or cancellation occurs.
9. Keep timer creation/cancellation and widget interaction on the main thread. No direct-render fallback from a worker and no broad exception catch that merely hides the original Tk error. Handle expected Tk destruction/cancellation errors narrowly; log unexpected consumer failures with tracebacks and avoid silently losing the remaining valid notifications.

Flow: worker -> lifecycle-bound data mailbox -> main-thread timer -> existing version-state handlers -> version label.

## Touch points

- New `edmc_mining_analytics/version_notifications.py`: data-only notification/mailbox boundary, with a minimal public surface.
- `edmc_mining_analytics/plugin.py`: lifecycle ownership, worker result publication, main-thread consumption, and version-label delivery.
- `UpdateManager` callback wiring in `plugin.py`: supply a publisher bound to the lifecycle mailbox. Its download/install implementation should not need changes.
- New `tests/test_version_notifications.py`: unit contracts.
- New `tests/test_harness_version_notifications.py`: hook and worker wiring contracts.
- `tests/harness_test_utils.py`: only if a small opt-in fixture seam is needed; preserve defaults for existing tests.
- `RELEASE_NOTES.md`: brief issue #81 threading fix after implementation.
- `load.py`: remains a thin shim; no edit expected.

Vendored guardrail: do not modify `tests/harness.py`, `tests/edmc/**`, or `tests/journal_config/**`.

## Testing strategy (selected before coding)

Mixed unit and harness coverage is required: the mailbox is deterministic and independent of EDMC, while delivery depends on plugin startup, UI attachment, worker callbacks, and shutdown.

| Change area | Invariant | Test type | Planned file |
| --- | --- | --- | --- |
| Mailbox | Typed messages retain order; early results survive until drained; closing discards pending results and rejects late publication | Unit | `tests/test_version_notifications.py` |
| Concurrency | Real worker threads can publish without touching Tk; publication/close interleavings are deterministic and safe | Unit | `tests/test_version_notifications.py` |
| Version-check wiring | Mock release success and tag fallback publish notifications; UI/state application occurs only when the main-thread consumer runs | Harness | `tests/test_harness_version_notifications.py` |
| Auto-update wiring | Invoke the actual callback supplied to a fake UpdateManager from a worker; update-ready state and label apply on the main thread | Harness | `tests/test_harness_version_notifications.py` |
| Startup/UI | Results before app creation survive; no-root startup touches no Tk; attachment displays retained results and owns one timer | Harness | `tests/test_harness_version_notifications.py` |
| Shutdown/restart | Stop cancels polling; pending, late, and previous-lifecycle results cannot render/rearm; repeated stop is safe | Harness | `tests/test_harness_version_notifications.py` |
| Behavior parity | Older/equal/newer versions and both arrival orders retain existing version/update-ready rules | Harness | `tests/test_harness_version_notifications.py` |

Use a fake root that records and asserts the calling thread for every Tk-like operation, plus a recording UI. Run real publisher threads with explicit events/barriers and bounded joins, not timing sleeps. Execute scheduled fake-root callbacks explicitly on the test thread. Mock HTTP and update download/install work; tests must not contact GitHub or modify the installed plugin.

Important fixture gap: `harness_context()` currently disables `_ensure_version_check`, and DummyUI exposes no root. New tests must deliberately restore/exercise the real version worker path with fake HTTP and supply a fake UI root; otherwise the regression remains hidden. Do not assume existing smoke tests reproduce it.

## Phase overview

| Phase | Description | Status |
| --- | --- | --- |
| 1 | Establish contracts and implementation plan | Completed |
| 2 | Implement and verify version notification delivery | Completed |
| 3 | Validate integration and document results | Completed |

### Phase 1: Contract and plan — Completed

| Stage | Description | Status |
| --- | --- | --- |
| 1.1 | Trace version and auto-update worker callbacks and identify fixture gaps | Completed |
| 1.2 | Specify mailbox, timer, lifecycle invariants, scope, and test types | Completed |

### Phase 2: Implementation — Completed

| Stage | Description | Status |
| --- | --- | --- |
| 2.1 | Add mailbox with unit tests; wire both publishers and the main-thread consumer, with harness regression coverage | Completed |
| 2.2 | Complete shutdown/restart guards and timer ownership, with adversarial lifecycle tests | Completed |

#### Stage 2.1

Write mailbox unit tests and a harness regression first. The harness must fail if a version worker calls any Tk/root method, including `after`. Implement the data boundary, bind both producers, and start consumption from `plugin_app()`. Lift existing version handlers intact into the consumer path. Deliver a working end-to-end increment, including basic timer cancellation/closed-mailbox guards rather than leaving unsafe shutdown for later.

Acceptance: normal lookup, fallback lookup, and update-ready callbacks use no Tk from workers; pre-app results are applied after attachment; the label reflects existing comparison rules. Demo using fake HTTP and a manually driven scheduler: worker completion updates the label only on the main thread.

Run the targeted unit/harness command below, then the full headless suite because lifecycle wiring changed.

#### Stage 2.2

Add tests before completing edge handling: completion during stop, publication after mailbox closure, stop before app, duplicate attachment, repeated stop, stale scheduled callbacks, and old workers finishing after restart. Preserve isolation even when worker joins time out. Verify that worker/thread-reference cleanup cannot accidentally clear ownership of a newer run; adjust only version-worker ownership if the tests expose that race.

Acceptance: no worker UI calls, no stopped lifecycle renders, no stale lifecycle notifications, and no duplicate/rearmed timers. Demo: stop with a worker held on a barrier, restart, release the old worker, and show that only the new lifecycle can update the UI.

Run the targeted command and the full suite after the lifecycle milestone.

### Phase 3: Validation and notes — Completed

| Stage | Description | Status |
| --- | --- | --- |
| 3.1 | Review version call paths and perform available real-Tk startup/shutdown smoke checks | Completed |
| 3.2 | Update release notes and record exact automated/manual outcomes and limitations | Completed |

Manually check startup with fast and delayed release responses, completion while preferences are open, and shutdown with a version request in flight. Include Windows EDMC when available because the report is from Windows. Confirm the label updates and EDMC exits without the reported exception. If GUI/platform access is unavailable, record that check as skipped with the reason; headless tests do not prove all real Tcl/Tk behavior.

## Commands and acceptance gates

Before implementation, recheck EDMC core `docs/Releasing.md` and the README runtime requirement; use the supported Python 3.13 environment. Do not rely on the previously observed patch version as a permanent baseline.

Targeted:

```bash
source .venv/bin/activate && python -m pytest -q tests/test_version_notifications.py tests/test_harness_version_notifications.py tests/test_harness_smoke.py tests/test_harness_integration.py
```

Milestone:

```bash
source .venv/bin/activate && python -m pytest
```

- [x] Regression fails on the original worker-to-Tk behavior.
- [x] Unit and harness tests pass with exact counts recorded.
- [x] Full headless suite passes after lifecycle wiring changes.
- [x] Real-Tk checks pass or are explicitly recorded as skipped.
- [x] Version checks and update-ready callbacks have no route to Tk from workers.
- [x] No mining/session behavior changes or vendored harness edits.
- [x] Release notes and phase/stage statuses reflect completed work.

## Risks and rollback

- Polling adds up to 100 ms of label latency. Keep the callback small and idle work minimal; this is a low-frequency notification stream.
- Late callbacks after restart can be misattributed if they reference mutable plugin mailbox state. Capture the lifecycle mailbox in each publisher and timer, and test cross-lifecycle completion explicitly.
- Existing harness defaults mask real worker/UI wiring. Use thread-asserting fakes and explicitly exercise producers; retain a real-Tk smoke check where possible.
- Keep the change in one behavior-scoped implementation commit (plus plan/docs as appropriate). Revert it as a unit if needed; do not keep an escape hatch that restores worker Tk calls.

## Open questions

None blocking planning. Real Windows/EDMC smoke-test availability must be recorded during validation.

## Implementation results

### Phase 1 — Completed

- 1.1 Completed: original worker paths and fixture gaps confirmed; existing untracked plan/prompt preserved.
- 1.2 Completed: approved contracts/test types retained. Upstream EDMC `docs/Releasing.md` checked 2026-11-07: Python 3.13, tested patch 3.13.9; README agrees on 3.13. System/original `.venv` is 3.12.3. Existing local runtime enabled Python 3.13.5 validation through `.venv-issue81`; original `.venv` preserved. No new dependencies. See [dashboard](issue-81-version-threading-execution/execution-status.md) for environment limitations and activation substitution.

### Phase 2 — Completed

- 2.1 Completed: parent reviewed generated task, source/test diffs and original RED evidence. Original actual release worker, tag-fallback worker and supplied updater callback each failed for worker UI access: 3 failed, 11 deselected. Separate mailbox RED: 1 expected missing-module collection error. Delivery GREEN: 17 passed. Targeted gate: 30 passed, 1 skipped; full milestone: 166 passed, 1 skipped. Fake-adapter normal delivery and pre-app retention demonstrated. Exact commands and logs: [stage 2.1 progress](issue-81-version-threading-execution/stage-2.1/implementation/progress.md).
- 2.2 Completed: 11 adversarial probes passed immediately against accepted stage 2.1; no further source correction needed. Targeted gate: 41 passed, 1 skipped; full milestone: 177 passed, 1 skipped. Tests prove close/discard/cancel before joins, old worker completion after timed-out join/restart, stale updater/timer isolation, single timer/exact-root cancellation, unlocked application callbacks, traceback/remaining-message delivery and narrow TclError handling. Fake-adapter stop/restart demo passed using real synchronized workers and manually driven callbacks. Exact commands and logs: [stage 2.2 progress](issue-81-version-threading-execution/stage-2.2/implementation/progress.md).
- Both stages used dedicated generator and code-assist agents sequentially; no remediation attempts needed. No vendored changes or changes to `load.py`, updater implementation, settings or mining/session code.
- Only automated skip: existing opt-in `test_harness_full_mining_run_writes_session_data_file`, requiring `EDMCMA_HARNESS_GENERATE_SESSION_FILE=1`; no relevant version test skipped.

### Phase 3 — Completed

- 3.1 Completed: parent reviewed both producer call paths and scoped diff. AST comparison confirms `_fetch_latest_tag`, both merge handlers and version-status logging preserved after normalizing the render-method rename. No worker path to UI/root scheduling remains for these two producers. Normal/restart demos reviewed in executed harness evidence without redundant reruns.
- Real-Tk probe: `tk.Tk()` failed with `TclError: couldn't connect to display ":1"`; no Xvfb available. Fast/delayed startup, completion with preferences open, shutdown with request in flight and screenshot checks skipped for unavailable GUI. Windows EDMC skipped: Linux environment only. Headless tests do not prove real Tcl/Tk or Windows integration.
- 3.2 Completed: narrow Unreleased note added without a version bump. Exact commands, all test outcomes, demos, manual limitations and supplied compliance-rule assessment recorded in [final review](issue-81-version-threading-execution/validation-review.md). Documentation/log scan: 21 files, zero secret-pattern flags. Final whitespace/staging/scope checks passed; no staged changes, commits or external writes. Worktree retains scoped modifications and original untracked plan/prompt for review.
