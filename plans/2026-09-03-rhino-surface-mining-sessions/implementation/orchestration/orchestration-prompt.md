# In-Session Implementation Orchestration: Rhino surface-mining sessions

## Execution environment

Execute this orchestration in the current Codex workspace and conversation. Do not launch an external `codex` CLI process, use `codex resume`, or ask the user to open a terminal.

The main agent is the coordinator. Execute autonomously after this prompt is accepted: each numbered task runs in a new, dedicated task-agent context launched from this conversation; task agents run sequentially, never in parallel; and the main agent reviews each handoff and validation evidence before automatically launching the next eligible task context. Do not wait for a user confirmation between successful tasks.

## Scope and authority

Repository: `/home/jon/.local/share/EDMarketConnector/plugins/EDMC-Mining-Analytics`

Approved plan: `plans/2026-09-03-rhino-surface-mining-sessions/implementation/plan.md`

Governing artifacts:

- `AGENTS.md`
- `plans/2026-09-03-rhino-surface-mining-sessions/rough-idea.md`
- `plans/2026-09-03-rhino-surface-mining-sessions/idea-honing.md`
- `plans/2026-09-03-rhino-surface-mining-sessions/research/log-evidence.md`
- `plans/2026-09-03-rhino-surface-mining-sessions/design/detailed-design.md`
- `plans/2026-09-03-rhino-surface-mining-sessions/implementation/plan.md`

Task-artifact directory: `plans/2026-09-03-rhino-surface-mining-sessions/implementation/orchestration/tasks/`

Status dashboard: `plans/2026-09-03-rhino-surface-mining-sessions/implementation/orchestration/execution-status.md`

The approved scope is deliberately minimal:

- Recognize `LaunchSRV` with normalized `SRVType == "mev_rhino"` as a mining-session start when no session is active.
- Recognize `DockSRV` with the same normalized type as an active-session stop.
- A repeated Rhino launch continues an active session; `SupercruiseEntry` has already ended the session, so a later Rhino launch begins a new one.
- Preserve all existing Prospector, supercruise, FSD-jump, session-recorder, UI, overlay, and shared-state behavior.
- Do not treat Planetary Mining Location signals as session boundaries.

Ordinary, in-scope local edits and non-destructive tests are authorized. Do not add a feature flag, preferences, new configuration, a parallel session kind, SRV ID persistence, new dependencies, production network requests, or UI work.

**Never commit.** Do not run `git add`, `git commit`, `git push`, create a branch, amend, reset, checkout, restore, stash, clean, or otherwise alter Git history/index. Do not overwrite, revert, stage, or incorporate unrelated changes.

At start, the worktree has unrelated user-owned changes in `README.md` and `edmc_mining_analytics/version.py`. Preserve those files exactly. Treat all existing changes outside the narrowly scoped journal, tests, and approved planning status artifacts as user-owned.

Stop and ask the user before any external write or live API operation; use of credentials, OAuth, uploads, or real game/EDMC activity; package installation or changing/recreating `.venv`; destructive commands; work outside this repository; scope expansion; a missing product decision; a security concern; or an unresolved test failure. Do not use web search or network access: the approved plan is complete and no external information is required. These are the only permitted autonomous-stop conditions.

## Start and restart recovery

Before editing in **every** task context, read all governing artifacts. Then inspect `git status --short`, the scoped diff, the implementation-plan checkboxes and phase tables, the status dashboard, task dossiers, and existing validation logs.

Create or reconcile `execution-status.md` with the current task. Never trust a prior completion claim without verifying the code and running the task's required focused test. Resume the first incomplete or unverified action for the selected task only.

Before and after every task, test, review, and demo, update the dashboard using exactly this format:

```text
Step: [n]; Task: [id]; Phase: [planning|implementation|validation|demo]; Action: [completed/running action]; Next: [next action]
```

While a command runs longer than 60 seconds, provide the same heartbeat format at least every 60 seconds.

## Task-context protocol

Each numbered task below runs in its own fresh task-agent context.

- The Task 01 context may complete **only** Task 01, update its own artifacts/status, report its result, and stop. It must not begin Task 02.
- Automatically launch Task 02 in a new task-agent context after Task 01 has completed and its focused validation has passed.
- If a task is interrupted, the main agent must launch a fresh recovery task-agent context for that same task. Never reuse a completed task's context to move to the next task.
- Run writing agents sequentially; do not overlap code-editing agents.

For the current task only, first use one dedicated `code-task-generator` agent to create a task dossier under the task-artifact directory. The main agent reviews its breakdown before implementation. Then use one dedicated `code-assist` agent, in a separate fresh task context, to implement the approved task using strict RED → GREEN → REFACTOR. If the current runtime cannot provide one of these named agents, the main agent performs the equivalent planning or TDD work in the current task context and records that limitation in the dossier.

Every agent handoff must contain exactly:

```text
Status; Files changed; Validation commands/results; Decisions; Risks; Next exact action.
```

Allow one implementation attempt and at most two fresh-context remediation attempts per task. Never rerun an unchanged failing command more than once. Stop with evidence after the retry limit or after 20 minutes without substantive progress.

## Task 01 — Rhino launch start boundary

Implement plan Step 1 only.

### Acceptance criteria

- Add a small private, defensive normalization/predicate seam for `SRVType`; missing, non-string, blank, and non-Rhino values are safe no-ops.
- Add a dedicated `LaunchSRV` handling path. An inactive mining state starts via the existing `_update_mining_state(True, "Rhino SRV launched", ...)` path.
- A repeated Rhino launch while mining is active makes no state transition and does not reset session state, counters, timestamps, or recorder data.
- Do not modify `load.py`, vendored harness files, configuration, preferences, UI, or session data schema.
- Add/update focused unit tests in `tests/test_journal_simulation.py` before or alongside implementation. Preserve existing Prospector-start coverage.

### Required validation and demo

Run, using the existing virtual environment only:

```bash
source .venv/bin/activate && python -m pytest tests/test_journal_simulation.py -k 'rhino or prospect'
```

Then independently inspect the scoped diff. Demonstrate from the test evidence that a Rhino launch starts an inactive session and a duplicate launch retains the original session. Update the Task 01 dossier, status dashboard, and the plan's Phase 1 stages/checklist only if the validation passes. Do not start Task 02.

## Task 02 — Rhino dock end boundary and harness proof

Implement plan Step 2 only, in a fresh context after Task 01 is verified complete.

### Acceptance criteria

- Add a dedicated `DockSRV` handling path using the Task 01 normalization seam.
- An active Rhino session ends only through existing `_update_mining_state(False, "Rhino SRV docked", ...)` behavior.
- Inactive, malformed, and non-Rhino dock events are no-ops.
- Existing `SupercruiseEntry` and `FSDJump` stop behavior remains unchanged. Rhino start → supercruise entry → Rhino start creates distinct sessions.
- Add/update unit tests in `tests/test_journal_simulation.py` and harness tests in `tests/test_harness_integration.py` before or alongside code. The harness must replay Rhino launch/dock through the registered EDMC journal callback and prove `edmc_mining_active` changes from true to false.
- Do not edit `tests/harness.py`, anything under `tests/edmc/`, `load.py`, preferences, UI, or session schema.

### Required validation and demo

Run, using the existing virtual environment only:

```bash
source .venv/bin/activate && python -m pytest tests/test_journal_simulation.py
source .venv/bin/activate && python -m pytest tests/test_harness_integration.py -k 'rhino or session'
source .venv/bin/activate && python -m pytest
```

If the current environment does not use Python 3.13, record that as a release-validation limitation; do not recreate the environment. Independently inspect the scoped diff, demonstrate the harness state transition, and update Phase 2 stages/checklist only after all required commands pass.

## Validation and completion

Use fake/in-process test adapters only. Do not interact with live EDMC, the real journal log, real APIs, webhooks, or uploads. Do not generate a test session export or write to the real `session_data/` directory.

Use `apply_patch` for source and test edits. Keep functions small and direct. Do not make unrelated formatting changes.

Before declaring each task complete, verify:

1. Exact task acceptance criteria are met.
2. Focused tests and broader required tests have passed, with commands and results recorded.
3. The scoped diff contains only expected task changes plus approved task/status artifacts.
4. The immutable harness paths remain unchanged.
5. The plan phase/stage table and task checklist accurately reflect verified progress.

## Final report

After Task 02, report:

- completed steps, stages, and demos;
- every changed source, test, and planning artifact file;
- each task dossier and dashboard path;
- exact validation commands and pass/fail/skip outcomes;
- confirmation that no commit, staging, push, or other Git history/index change occurred;
- manual work remaining, including Python 3.13 and live EDMC smoke validation if not performed; and
- known limitations, including the log's unmatched Rhino boundary records and the approved repeated-launch continuation rule.

Passing tests never authorize an external action or scope expansion.
