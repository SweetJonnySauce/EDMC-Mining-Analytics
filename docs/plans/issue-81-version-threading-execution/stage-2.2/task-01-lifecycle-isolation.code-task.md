# Task: Prove and complete version notification lifecycle isolation

## Description
Complete approved stage 2.2 by testing adversarial version-worker, updater-callback, mailbox, and timer interleavings, then making only corrections those tests show necessary. Establish that stopping permanently closes delivery for that lifecycle and that previous workers or scheduled callbacks cannot affect a subsequent startup. Include failure isolation and narrow Tk destruction handling in the same functional task.

## Background
Stage 2.1 is accepted: a data-only mailbox receives both captured producers, app attachment drains results and starts a 100 ms main-thread timer, and stop closes/discards/cancels before waits. Worker-side clearing of `_version_thread` was removed so an old completion cannot clear a newer worker. Existing targeted gate passed with 30 passed/1 skipped; full suite passed with 166 passed/1 skipped under Python 3.13.5. The remaining work proves adversarial contracts rather than redesigning these seams.

Parameters acquired: approved stage 2.2 description; this output directory; project issue-81-version-threading. Description mode applies to the approved non-PDD phase/stage plan. The orchestration prompt already approves the single functional task and sequential implementation; no additional permission round is required. Tests are integrated into this task, not separate deliverables.

## Reference Documentation
**Required:**
- Design: `docs/plans/issue-81-version-threading.md`, especially contracts 3–9 and stage 2.2.
- Authority: `docs/plans/issue-81-version-threading-orchestration-prompt.md`.
- Repository conventions: `AGENTS.md`, README runtime requirement, and `tests/README.md`.
- Previous stage evidence: `docs/plans/issue-81-version-threading-execution/stage-2.1/implementation/progress.md`.
- Skill: `/home/jon/src/agent-toolkit/skills/code-assist/SKILL.md`, auto mode.

**Note:** Read the approved design before implementation. No separate PDD document is required; do not restart requirements discovery.

## Technical Requirements
1. Extend `tests/test_version_notifications.py` with deterministic publication/closure interleavings and any uncovered mailbox ordering contracts. Closing discards queued messages and rejects later publications permanently, including publications from a real thread synchronized across closure. Keep these pure contracts in unit tests.
2. Extend `tests/test_harness_version_notifications.py` using its existing real-worker, fake-HTTP, captured UpdateManager callback, recording UI, and manually driven root helpers. Keep actual producers in the tests; manual enqueue alone does not prove wiring.
3. Cover stop before app, repeated stop, pending-result discard, completion during stop, late completion, duplicate attachment, and exact scheduling-root cancellation. Verify mailbox closure, delivery deactivation, and timer cancellation happen before UpdateManager stop or version-worker waits can complete or publish. Tests must observe the stop ordering rather than merely assert its eventual state.
4. Hold a real version worker on explicit synchronization while stop performs a bounded timed-out join. Restart the same plugin with a distinct fake response and current worker. Release the previous worker while the new worker remains active; its result must not change presentation state, clear the newer `_version_thread`, create a timer, or otherwise affect the new lifecycle. Clean up every held thread even if assertions fail.
5. Capture the actual UpdateManager callback and scheduled timer callback from the previous lifecycle. Invoke the old updater callback from a worker and the stale timer callback on the main thread after stop/restart. They must not deliver data to the new mailbox, render, rearm polling, cancel current work, or clear current timer/root ownership. Also prove a callback invoked after stop without restart remains inert.
6. Prove callback execution occurs outside mailbox locks: while a main-thread consumer handler executes, a synchronized worker can publish successfully without waiting for the handler to release a mailbox lock. An unexpected handler exception must be logged with traceback and must not prevent subsequent valid notifications from being applied. Preserve ordering of valid messages.
7. Probe expected `tk.TclError` from owned timer creation/cancellation and label delivery. Expected destroyed-root paths must be safe and leave coherent timer ownership; no worker UI fallback is permitted. Unexpected consumer exceptions require traceback logging, and broad exception swallowing must not conceal the threading regression.
8. Write adversarial tests before making any corresponding source correction. Existing correct contracts may pass immediately; record that outcome honestly and retain stage 2.1's original RED evidence. Do not deliberately break working code to fabricate another RED result. Where a new defect is found, capture its failing test before the minimal GREEN correction and review/refactor afterward.
9. Use Events/barriers, explicit main-thread fake scheduler execution, and bounded joins; no timing sleeps. All automated HTTP/update adapters must remain fake, output directories temporary, and Tk-like operations thread-asserting. Retain existing normal delivery and version-merge coverage.
10. Keep changes limited to notification delivery/lifecycle ownership in `plugin.py`, the small mailbox if needed, and non-vendored tests/fixtures and task notes. Preserve HTTP release/tag behavior, settings, label wording, update-ready precedence, and updater download/install behavior. Do not edit `load.py`, vendored harness sources, unrelated UI dispatch, mining/session/preferences/overlays, logger identity, release packaging, or dependency requirements.
11. Use `source .venv-issue81/bin/activate` for the already-established Python 3.13.5 environment; preserve original `.venv` and record this substitution from the plan's generic activation. Do not install dependencies or enable live HTTP/updater work.
12. One initial implementation attempt and at most two fresh-context remediation attempts are allowed. Do not repeat an unchanged failing command more than once. No commits, staging, pushes, PRs, credentials, external writes, or live updater execution.

## Dependencies
- Accepted stage 2.1 `VersionMailbox`, `_stop_version_notifications`, `_drain_version_notifications`, `_schedule_version_poll`, `_poll_version_notifications`, startup-bound publishers, and main-thread version handlers.
- Existing `RecordingRoot.history` permits retaining stale callbacks; `RecordingUI` verifies thread identity; `FakeHTTP` holds the actual version worker on Events; `CapturedUpdateManager` stores the callback actually passed by startup.
- Existing test helper uses temporary plugin directories and restores `_ensure_version_check` despite the default harness suppression. Preserve those safeguards.
- Parent owns approved-plan/dashboard updates, final call-path review, release notes, and GUI/Windows skip documentation. This task owns its isolated implementation notes and test/source changes only.

## Implementation Approach
1. Create isolated `implementation/context.md`, `plan.md`, `progress.md`, and logs within this stage directory; record selected unit/harness test types and the ordered scenario matrix before editing source.
2. Add unit and harness contracts covering the listed interleavings using existing helpers. Run the new scenarios first against accepted stage 2.1. Record immediate passes and real failures separately; investigate harness mistakes before treating failures as source defects.
3. Apply the smallest behavior-scoped fixes for any proven gaps. Keep mailbox publishers bound to their startup instance, callbacks outside mailbox locks, stale-callback identity checks before timer ownership mutation, and main-thread ownership of worker references. No speculative cleanup.
4. Review source and tests, including cleanup on failed assertions, fake adapter isolation, narrow expected Tk errors, traceback evidence for unexpected errors, and unchanged version handlers.
5. Run the required targeted gate after substantive lifecycle changes, then the lifecycle milestone full suite. Commands from repository root:
   - `source .venv-issue81/bin/activate && python -m pytest -q tests/test_version_notifications.py tests/test_harness_version_notifications.py tests/test_harness_smoke.py tests/test_harness_integration.py`
   - `source .venv-issue81/bin/activate && python -m pytest`
   Record exact commands, interpreter, pass/fail/skip counts and reasons, and logs. Do not repeat successful gates without a subsequent change or unresolved concern; report unrelated failures without expanding scope.
6. Demonstrate stop/restart isolation with fake HTTP and a manually driven scheduler: stop while the first real worker is held, observe a timed-out join, start a new lifecycle, release the old worker and old updater callback, invoke its stale timer, and then allow only the current worker to update the label. Record observable worker/state/timer results; this may use the executed test evidence without a redundant rerun.
7. Update all task checklists/statuses and return the required handoff: `Status; Files changed; Validation commands/results; Decisions; Risks; Next exact action.` Leave parent phase 3 validation/documentation as the next action; do not commit.

## Acceptance Criteria

1. **Mailbox closure and publication race**
   - Given ordered publications and a real publisher held across mailbox closure,
   - When the main thread closes/discards and releases the publisher,
   - Then pending data is absent, late publication is rejected, and further drains remain empty. Unit tests prove the outcome without UI dependencies.

2. **Stop ordering and idempotency**
   - Given no app yet, pending data, or an active timer,
   - When stopping before app, stopping repeatedly, or a producer completes inside the worker-stop/wait phase,
   - Then delivery is already inactive, the old mailbox is closed/discarded, and the owned timer has been cancelled before waiting. No version label update or rearm occurs.

3. **Timed-out old worker across restart**
   - Given an actual old version worker held through a bounded timed-out stop join and an actual new worker still active after restart,
   - When releasing the old worker,
   - Then the old result cannot render or enter the current mailbox and cannot clear the new worker reference; only current-worker results apply when the main-thread consumer runs.

4. **Stale callback isolation**
   - Given captured previous-lifecycle updater and timer callbacks plus a current lifecycle with an owned timer,
   - When invoking the old updater callback from a worker and stale timer callback on the main thread, both after stop alone and after restart,
   - Then no old result reaches the UI, no timer is rearmed, and the current timer/root/thread ownership remains unchanged.

5. **Single timer and exact-root cancellation**
   - Given repeated UI attachment and an owned scheduled poll,
   - When attaching again or changing the UI's root reference before stop,
   - Then only one polling timer exists and stop cancels through the root that originally scheduled it; repeated stop is harmless.

6. **Consumer isolation and observability**
   - Given multiple valid messages with one handler deliberately raising an unexpected error and another synchronized publisher active during handler execution,
   - When draining on the main thread,
   - Then the error is logged with traceback, later valid notifications still apply in order, and publication can finish while the handler runs because the mailbox lock is released.

7. **Expected Tk destruction**
   - Given fake roots/label delivery raising `tk.TclError` during creation, cancellation, or consumption,
   - When those main-thread paths execute,
   - Then expected destruction is handled narrowly with coherent timer ownership and no worker/direct-render fallback; the original threading regression remains detectable.

8. **Validation and demo evidence**
   - Given the completed adversarial matrix and any minimal fixes,
   - When running the targeted and full gates plus reviewing the fake-adapter stop/restart demo,
   - Then exact outcomes, skips, original/new RED evidence where applicable, and remaining limits are recorded; scope is preserved and no live network/update or external write occurred.

## Metadata
- **Complexity**: High
- **Labels**: issue-81, lifecycle, threading, Tk, mailbox, regression
- **Required Skills**: Python synchronization, Tk timer ownership, pytest unit testing, EDMC harness testing, code-assist auto mode
