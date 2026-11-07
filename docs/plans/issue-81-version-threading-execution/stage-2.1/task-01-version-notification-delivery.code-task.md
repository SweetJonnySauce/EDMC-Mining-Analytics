# Task: Deliver version notifications on the main thread

## Description
Implement approved stage 2.1: introduce a data-only mailbox and route version-check and auto-update-ready worker results through a main-thread consumer. Deliver a working end-to-end increment with unit and harness regression coverage and basic shutdown guards.

## Background
Both workers currently reach `_schedule_version_label_update()` and call Tk's `root.after()` from worker threads. Preserve lookup requests, normalization, comparisons, update-ready precedence, label wording, settings, and updater behavior. Only notification delivery changes; delivery may take one polling interval.

Parameters acquired: approved stage 2.1 description from the plan; output directory is this directory; project is issue-81-version-threading. Description mode applies because the source is an approved phase/stage plan, not a PDD implementation checklist. The orchestration prompt authorizes this task breakdown and implementation without another approval round. Stage 2.2 follows this task for adversarial lifecycle tests and any resulting corrections.

## Reference Documentation
**Required:**
- Design: `docs/plans/issue-81-version-threading.md`, especially contracts, touch points, and stage 2.1.
- Authority: `docs/plans/issue-81-version-threading-orchestration-prompt.md`.
- Repository conventions: `AGENTS.md`, `README.md` runtime requirements, and `tests/README.md`.
- Skill: `/home/jon/src/agent-toolkit/skills/code-assist/SKILL.md` (auto mode).

**Note:** You MUST read the approved design before implementation. No separate PDD design document exists or is required; do not restart discovery.

## Technical Requirements
1. Add `edmc_mining_analytics/version_notifications.py` with typed latest-version/update-ready messages and a minimal thread-safe mailbox API. Preserve publication order, retain messages until draining, and discard pending messages/reject late publication when closed. Never invoke application/UI callbacks under a mailbox lock.
2. Create a fresh mailbox at plugin startup before either producer starts. Capture that mailbox in each version-worker publisher and in the callback supplied to `UpdateManager`; workers must never resolve a later lifecycle's mailbox dynamically.
3. Workers perform network work and publish data only. Neither producer may call UI methods, acquire a Tk root, access Tk variables, or invoke `after`, `winfo_exists`, or `event_generate`.
4. After `plugin_app()` builds the UI, drain retained messages on the main thread and establish one recurring timer of approximately 100 ms. Dispatch to the existing handlers, lifting their normalization/comparison/merge behavior intact. Render labels directly on the consumer/main thread rather than scheduling from workers.
5. Include basic safe shutdown in this increment: deactivate delivery, close/discard the mailbox, cancel the owned timer before joining workers, and guard callbacks by lifecycle identity. Do not leave an unsafe shutdown window for stage 2.2. Repeated attachment must not duplicate timers.
6. Handle expected Tk destruction/cancellation exceptions narrowly. Unexpected consumer errors need traceback logging and must not silently discard remaining valid messages. No broad catch or direct-render fallback may hide worker Tk calls.
7. Keep `load.py` unchanged unless evidence proves an essential in-scope need. Do not modify updater download/install logic, preferences, mining/session logic, unrelated worker cleanup, or vendored `tests/harness.py`, `tests/edmc/**`, or `tests/journal_config/**`.
8. Use Python 3.13 as required by the README and checked upstream EDMC release guidance. Coordinate any unavailable-runtime limitation with the parent; do not claim another interpreter proves 3.13 compatibility.
9. Use one initial implementation attempt and at most two fresh-context remediation attempts. Do not repeat an unchanged failing command more than once. No commits, external writes, credentials, live HTTP, or live updater.

## Dependencies
- Existing plugin lifecycle/version handlers in `edmc_mining_analytics/plugin.py` and UpdateManager constructor callback seam.
- Existing harness modules and non-vendored `tests/harness_test_utils.py`; its default helper suppresses `_ensure_version_check`, and DummyUI has no root. Tests must intentionally enable the real worker and supply a recording fake root.
- Existing requirements in a workspace-local virtualenv; no new dependencies.
- New `tests/test_version_notifications.py` for pure mailbox contracts and `tests/test_harness_version_notifications.py` for lifecycle/producer wiring.

## Implementation Approach
1. Inspect targeted source/tests and record concise context, implementation/test plan, and progress under an isolated task-notes directory within this stage. Choose mixed unit/harness coverage before coding. Send required stage/test/demo updates in the orchestration format.
2. RED: write mailbox contracts plus regressions using real producer threads, fake HTTP and fake UpdateManager, and a UI/root that records and asserts the calling thread for every Tk-like operation. Restore the real version-worker path despite harness defaults. Run the harness regression against original source separately from missing-module unit tests, and save the intended worker-to-Tk failure evidence before implementation.
3. GREEN: add the mailbox, capture per-lifecycle publishers, wire startup/app/stop and a main-thread consumer, preserving existing handler behavior. Use explicit events/barriers, bounded thread joins, and manually driven fake timer callbacks; no synchronization sleeps or real downloads.
4. REFACTOR: review minimal API, unchanged behavior, callbacks outside locks, exception handling, lifecycle bindings, and diff scope. Add no unrelated cleanup.
5. Run and record the targeted gate, then the full headless suite because lifecycle wiring changed. Commands (from repository root):
   - `source .venv/bin/activate && python -m pytest -q tests/test_version_notifications.py tests/test_harness_version_notifications.py tests/test_harness_smoke.py tests/test_harness_integration.py`
   - `source .venv/bin/activate && python -m pytest`
6. Demonstrate normal delivery using fake HTTP and a manually driven scheduler: worker completion leaves presentation state untouched until main-thread consumption, then updates the expected label. Record exact results and interpreter, plus unrelated failures separately. Leave stage 2.2 adversarial lifecycle completion to the next task.
7. Return handoff with `Status; Files changed; Validation commands/results; Decisions; Risks; Next exact action.` Do not commit or mark parent plan phases complete yourself without parent review.

## Acceptance Criteria

1. **Mailbox unit contracts**
   - Given typed messages published in a known order, including publication from real synchronized threads,
   - When draining, draining again, closing with pending messages, and publishing after closure,
   - Then messages retain order, drained results are not duplicated, closure discards pending results, and late publication is rejected without UI access. Unit tests prove these contracts.

2. **Original regression evidence**
   - Given original plugin source and a main-thread-asserting fake root/UI,
   - When the real version-check worker receives a fake release response and the actual updater callback runs on a worker,
   - Then pre-fix harness evidence identifies the worker-to-Tk violation for the intended reason; post-fix tests prove neither path performs Tk-like operations off the main thread.

3. **Real lookup producer wiring**
   - Given fake HTTP adapters for release success and release failure followed by tag fallback,
   - When the actual version-check worker completes,
   - Then requests retain existing behavior, results are published to the startup-bound mailbox, and presentation state/label changes occur only after main-thread delivery. Tests must exercise actual producers rather than only enqueue manually.

4. **Pre-app delivery and owned polling**
   - Given a result before UI creation and no root available to workers,
   - When `plugin_app()` builds the recording UI and the fake scheduler advances,
   - Then retained results update the label on the main thread and one recurring timer exists, including repeated attachment.

5. **Version behavior parity**
   - Given older/equal/newer version strings and latest-version/update-ready notifications in either arrival order,
   - When consumed on the main thread,
   - Then normalization, comparisons, update-ready precedence, merge rules, and label wording match the original handlers. Harness tests cover these cases.

6. **Basic shutdown safety**
   - Given pending delivery and an owned polling timer,
   - When stopping, including before UI attachment or repeatedly,
   - Then delivery deactivates, pending results are discarded, late publication is harmless, and the timer is cancelled before worker waits. Stale callbacks cannot apply or rearm another lifecycle; stage 2.2 supplies the adversarial interleaving matrix.

7. **Validation and scope evidence**
   - Given implemented delivery and fake-adapter demo,
   - When running both exact validation gates and reviewing the scoped diff,
   - Then outcomes/counts and original RED failure are recorded, unrelated failures remain identified separately, vendored files and out-of-scope behavior are unchanged, and no commit or external write occurred.

## Metadata
- **Complexity**: High
- **Labels**: issue-81, threading, Tk, mailbox, lifecycle, regression
- **Required Skills**: Python threading, Tk main-loop ownership, pytest unit testing, EDMC harness testing, code-assist auto mode
