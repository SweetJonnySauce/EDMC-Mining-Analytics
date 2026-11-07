# Stage 2.1 progress

- [x] Read instructions and inspect existing code/harness patterns.
- [x] Select mixed unit/harness coverage and document plan before code.
- [x] Write tests and capture RED against original source.
- [x] Implement minimum delivery boundary and review/refactor.
- [x] Run targeted and full gates; record demo.
- [x] Return reviewable handoff (no commit authorized).

## RED → GREEN evidence

Original source: `source .venv-issue81/bin/activate && python -m pytest -q tests/test_harness_version_notifications.py -k 'real_version_worker_never_calls_tk or actual_update_ready_callback_never_calls_tk'` -> 3 failed, 11 deselected. Each failure exposes worker access to UI/Tk `get_root`; actual worker release/fallback and supplied updater callback exercised. See logs/red-producers.log.

`source .venv-issue81/bin/activate && python -m pytest -q tests/test_version_notifications.py` -> 1 collection error for absent version_notifications module, separately recorded in logs/red-mailbox.log.

Implemented data-only frozen messages and mailbox. Startup creates mailbox before either producer; publishers capture it. Main-thread app drains then owns 100ms timer with stored scheduling root; stop closes/discards/cancels before waits. Original handler comparison/merge bodies retained. Removed worker-side thread-reference clearing: workers cannot clear ownership of a later lifecycle; the main thread retains its thread reference until stop/start. Unexpected per-message delivery exceptions log tracebacks and later notifications continue outside locks.

`source .venv-issue81/bin/activate && python -m pytest -q tests/test_version_notifications.py tests/test_harness_version_notifications.py` -> 17 passed in 0.61s, logs/green-delivery.log.

Review found existing smoke test could enable live version/updater work. Updated only its non-vendored helper to disable those producers explicitly; dedicated new harness tests exercise actual producers with fake adapters. No source runtime behavior changed for that test isolation fix.

## Validation and demo

- `source .venv-issue81/bin/activate && python -m pytest -q tests/test_version_notifications.py tests/test_harness_version_notifications.py tests/test_harness_smoke.py tests/test_harness_integration.py` -> **30 passed, 1 skipped in 1.10s**; logs/targeted.log.
- `source .venv-issue81/bin/activate && python -m pytest` -> **166 passed, 1 skipped in 1.89s**; logs/full-suite.log. Interpreter Python 3.13.5, pytest 9.0.2.
- Both skips: `tests/test_harness_integration.py::test_harness_full_mining_run_writes_session_data_file`, explicitly requires `EDMCMA_HARNESS_GENERATE_SESSION_FILE=1` to run the session export harness. No relevant version test skipped.
- `git diff --check` -> passed.

Normal fake-adapter demo executed in the passing harness cases `test_real_version_worker_never_calls_tk[release]`, `[tag-fallback]`, `test_actual_update_ready_callback_never_calls_tk`, and `test_result_before_app_is_retained`. Real worker requests fake release metadata with timeout=5; 404 repeats existing tag fallback. After synchronized worker completion, `_latest_version` remains None and labels remain unchanged. Manually ticking the one owned fake timer on the main thread renders `(1.4.0, 99.0.0, False)`. Actual UpdateManager callback invoked from a worker leaves presentation state untouched until ticking, then renders `(1.4.0, 99.0.0, True)`. Pre-app result causes no UI/root operation and is applied on app attachment. Every recorded Tk-like operation is checked against the test's main thread. These executions are included in the targeted gate; no redundant check rerun was needed for the demo.

No vendored files, load.py, release packaging, updater implementation, or unrelated features changed. No new dependencies, no commit/staging, no external write, no live API/update execution. Dedicated stage 2.2 remains for adversarial lifecycle matrix and exception probes. Real GUI/Windows validation is parent-owned; current Linux display is unavailable.
