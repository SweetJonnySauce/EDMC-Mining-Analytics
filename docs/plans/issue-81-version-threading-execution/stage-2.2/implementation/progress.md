# Stage 2.2 progress

- [x] Read governing files, source and prior evidence; confirm auto-mode parameters.
- [x] Select unit/harness scenarios and document ordered plan before coding.
- [x] Add adversarial tests and probe accepted source.
- [x] Apply only necessary corrections and review scope.
- [x] Run targeted/full gates and record stop/restart demo.
- [x] Complete task statuses and return handoff; no commit authorized.

## Adversarial probe / review

`source .venv-issue81/bin/activate && python -m pytest -q tests/test_version_notifications.py tests/test_harness_version_notifications.py -k 'multiple_publishers or stop_before_app or stop_closes or timed_out or original_scheduling_root or consumer_error or application_callback or destroyed or unexpected_timer_error'` -> **11 passed, 17 deselected in 0.56s** on first execution against accepted stage 2.1. Log: logs/adversarial-first.log. All new contracts passed immediately; no new RED defect was found or manufactured. Stage 2.1 preserves the original producer RED evidence.

Added one synchronized multi-publisher unit test and ten harness tests. Actual producer callbacks and real version threads prove the lifecycle contracts; temporary plugin directories and fake network/updater adapters remain in use. Review confirms held threads are released/joined in finally blocks, stale callbacks execute only on the main thread, and all involved Tk-like operations assert thread identity. Consumer traceback is asserted via LogRecord.exc_info, and a worker publishes while the application handler is executing to prove mailbox locks are released. Narrow TclError creation/cancellation/render probes pass; an unexpected scheduler RuntimeError propagates rather than being hidden. No production source changes are needed for stage 2.2.

## Gates and demo

- `source .venv-issue81/bin/activate && python -m pytest -q tests/test_version_notifications.py tests/test_harness_version_notifications.py tests/test_harness_smoke.py tests/test_harness_integration.py` -> **41 passed, 1 skipped in 1.44s**; logs/targeted.log.
- `source .venv-issue81/bin/activate && python -m pytest` -> **177 passed, 1 skipped in 2.12s**; logs/full-suite.log. Interpreter: Python 3.13.5; pytest 9.0.2.
- Both skips are existing `tests/test_harness_integration.py::test_harness_full_mining_run_writes_session_data_file`, requiring explicit `EDMCMA_HARNESS_GENERATE_SESSION_FILE=1`. No version-notification checks skipped.
- `git diff --check` -> passed.

Stop/restart fake-adapter demo executed in `test_timed_out_old_worker_and_callbacks_cannot_affect_restart` (included in the probe and gates). The old real version thread remains alive after the actual bounded `join(0)` stop path. Startup creates a distinct mailbox and real current worker, still held at fake HTTP. Releasing the old response, running its actual captured updater callback on a worker, and manually invoking its stale timer leaves current thread identity, owned timer token/root, labels and presentation state unchanged. The old mailbox drains empty; a current timer tick before current completion produces no label change. Releasing only the current fake response and manually ticking renders `(1.4.0, 101.0.0, False)`; its actual updater callback followed by another main-thread tick renders `(1.4.0, 101.0.0, True)`. No UI thread violation or worker error occurs. All held threads are released and bounded-joined in finally blocks. No redundant standalone rerun was needed.

Stop-order demo in `test_stop_closes_and_cancels_before_worker_waits` asserts inactive delivery, rejected publication and absent owned timer before either updater stop or version wait. Actual producer completion and stale callback execution inside the wait phase cannot update labels or rearm. Stop-before-app, repeated stop and original-root cancellation also pass.

No production corrections or speculative refactors were made in this stage because accepted stage 2.1 already satisfies the adversarial contracts. Stage 2.2 changes only the two new test files and these isolated notes. No vendored files, load.py, updater implementation, requirements, release packaging or unrelated behavior changed. No commits/staging, external writes, live HTTP or live updater execution. GUI/Windows checks and final release notes remain parent-owned phase 3 work; no claim of real Tcl/Tk or Windows execution is made.
