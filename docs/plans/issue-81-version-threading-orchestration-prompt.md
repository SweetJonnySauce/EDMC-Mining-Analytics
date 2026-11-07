# Implement issue #81: version-worker Tk threading fix

## Scope and authority

Implement the approved plan in `docs/plans/issue-81-version-threading.md` to completion.

Repository: `/home/jon/edmc_plugins/EDMC-Mining-Analytics`.
Governing files: `AGENTS.md`, the approved plan, `README.md` runtime requirements, `tests/README.md`, and any applicable nested `AGENTS.md`.
Task-artifact directory: `docs/plans/issue-81-version-threading-execution/`.
Status dashboard: `docs/plans/issue-81-version-threading-execution/execution-status.md`.

Do not use the PDD skill or restart requirements discovery. The plan is approved. Proceed with ordinary in-scope local code, test, fixture, and documentation work without asking for approval at every stage. Resolve routine implementation choices using the plan and existing patterns.

Do not commit, push, create a PR, post to GitHub, publish a release, or run the live updater. Do not access credentials, perform destructive Git operations, overwrite unrelated work, or change files outside the workspace. Read-only primary documentation access and installation of existing requirements into a workspace-local virtualenv are permitted. Stop with evidence if necessary work requires new scope, dependencies, credentials, external writes, or unavailable permissions. Missing optional GUI access is a documented skip, not a reason to abandon headless implementation.

## Start and restart recovery

Read the governing files before editing. Inspect Git status and targeted diffs. Preserve existing work, including the previously created plan if it is untracked. Do not overwrite existing execution artifacts; reconcile and resume them.

On every restart, compare the status dashboard and plan checkboxes against the actual source, tests, diffs, and recorded validation evidence. Resume at the first incomplete or unverified action. Do not rerun completed work solely because the conversation restarted.

Before implementation, verify the supported Python version from EDMC core `docs/Releasing.md` and compare it with this repository's README and available interpreter. Use the required Python 3.13 environment; report any unavailable runtime honestly. Do not silently claim another interpreter proves compatibility.

Maintain phase/stage statuses in the plan, ordered by phase then stage, and record exact test commands and outcomes. Do not mark implementation stages complete based only on a proposed design.

Send updates before and after each stage, test run, and demo, plus at least every 60 seconds during sustained work. Use:

`Step: [stage]; Task: [task ID]; Phase: [planning|implementation|validation|demo]; Action: [current/completed action]; Next: [next action]`.

## Required implementation

The current version worker calls `_handle_latest_version()` -> `_log_version_status()` -> `_schedule_version_label_update()` -> `root.after()` off the main thread. The auto-update completion callback reaches the same unsafe scheduling method. Fix both paths.

- Introduce the small data-only `edmc_mining_analytics/version_notifications.py` mailbox described in the plan. Keep the API minimal, with typed messages and tests for ordering, publication, draining, closure, and late publication.
- Bind each worker publisher to the mailbox belonging to its startup lifecycle. Do not have old workers discover the current mailbox dynamically.
- Workers must publish data only: no UI methods, Tk root access, `after`, `winfo_exists`, `event_generate`, or Tk-variable access.
- Apply `_latest_version` and `_update_ready_version` changes on the main thread, preserving the existing normalization, comparisons, and merge rules. Lift existing handler logic intact wherever possible.
- Retain notifications before UI creation. After `plugin_app()` builds the UI, consume queued results and establish one main-thread polling timer, approximately every 100 ms. Avoid duplicate timers on repeated attachment.
- Stop notification delivery, close/discard the mailbox, and cancel the owned timer before waiting for workers during shutdown. Make repeated stop and stop-before-app safe.
- Stale workers and stale scheduled callbacks must never update or rearm a new lifecycle. Test completion across stop/restart and timed-out worker joins. Adjust version-worker ownership only as needed to satisfy these contracts.
- Keep locks away from application/UI callbacks. Handle expected Tk destruction/cancellation errors narrowly. Log unexpected errors with tracebacks; do not mask the threading bug with a broad catch or direct-render fallback.

Preserve release/tag HTTP behavior, user settings, label text, update-ready precedence, and download/install behavior. Keep `load.py` thin; no edit is expected. Do not expand into mining, cargo, RPM, overlays, session logging, preferences, logger identity, EDSM/market UI dispatch, or generic worker cleanup.

Never edit vendored `tests/harness.py`, `tests/edmc/**`, or `tests/journal_config/**`.

## Execute sequentially

Implement stage 2.1, then 2.2, then validate/document stages 3.1 and 3.2. Do not stop after producing tasks or scaffolding.

For each implementation stage, use one dedicated `code-task-generator` subagent to create the current stage's tasks under the execution directory. Review its tasks against the approved scope. For each accepted task, use one dedicated `code-assist` subagent in auto mode with RED -> GREEN -> REFACTOR and isolated task notes. Run writing agents sequentially; never overlap editors. This prompt explicitly authorizes this limited delegation. If subagent tools are unavailable, perform the same steps sequentially in the main agent and document that limitation.

Require each handoff to contain: `Status; Files changed; Validation commands/results; Decisions; Risks; Next exact action.` Review actual diffs and test evidence in the main thread before accepting completion.

Allow one initial implementation attempt and at most two fresh-context remediation attempts per task. Do not repeat an unchanged failing command more than once. If the limit is reached, or no substantive progress occurs for 20 minutes, stop with the failure evidence, current diff, and next exact action. Do not hide unresolved failures or declare completion.

## Test and validation gates

Use both unit tests and harness tests, as selected in the plan. Write the regression before the fix and show that the original worker-to-Tk behavior fails it for the intended reason.

Planned new test files:

- `tests/test_version_notifications.py`
- `tests/test_harness_version_notifications.py`

Use a recording UI and fake root that assert the calling thread for every Tk-like operation. Run real publisher threads with explicit synchronization and bounded joins. Execute fake timer callbacks on the test's main thread. No timing sleeps as a substitute for synchronization.

Do not overlook the harness gap: its default helper disables `_ensure_version_check`, and DummyUI has no root. Exercise the real version-check worker with fake HTTP and a fake UI root. Invoke the callback actually supplied to a fake UpdateManager from a worker. Do not settle for tests that manually enqueue messages and never prove producer wiring.

Cover release success, tag fallback, results before UI creation, both version/update-ready arrival orders, older/equal/newer versions, duplicate attachment, stop-before-app, repeated stop, late publication, stale timer callbacks, and previous-lifecycle completion after restart.

Automated tests must use fake network/update adapters and temporary output directories. They must not contact GitHub or download/install an update in the running plugin directory.

Run after stage 2.1 and again after substantive lifecycle changes in 2.2:

```bash
source .venv/bin/activate && python -m pytest -q tests/test_version_notifications.py tests/test_harness_version_notifications.py tests/test_harness_smoke.py tests/test_harness_integration.py
```

Run the milestone gate after lifecycle wiring changes:

```bash
source .venv/bin/activate && python -m pytest
```

Do not broaden or repeat successful checks without a new change or unresolved concern. Record existing unrelated failures separately; do not fix them under this task or misreport the full suite as passing.

Review all changed call paths and the scoped diff. Demonstrate normal delivery and stop/restart isolation with fake HTTP and a manually driven scheduler. If a safe real-Tk environment is available, check fast/delayed startup responses, completion while preferences are open, and shutdown with a request in flight using fake adapters; capture a screenshot if feasible and inspect it for sensitive content. Record Windows EDMC and GUI checks as skipped with a reason when unavailable. Do not enable live APIs or the updater to satisfy manual checks.

Scan changed documentation and recorded logs for accidental secrets. Update `RELEASE_NOTES.md` with the narrow issue #81 fix; do not bump the version or modify release packaging.

## Completion report

Finish the authorized local work; do not ask whether to begin implementation. Report:

1. What changed and why worker threads can no longer reach Tk through these two paths.
2. Completed plan phases/stages and changed files, explicitly listing test files.
3. Exact commands, pass/fail/skip counts, interpreter used, and evidence of the original regression failure.
4. Fake-adapter demo results and any skipped real-Tk/Windows checks with reasons.
5. Remaining risks or unresolved failures and the final worktree state. State that no commit or external write was made.

Leave the fix and documentation ready for user review.
