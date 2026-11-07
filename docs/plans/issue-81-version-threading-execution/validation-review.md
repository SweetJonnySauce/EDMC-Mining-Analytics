# Issue #81 final review

## Phase 2 evidence — Completed

Interpreter: Python 3.13.5, pytest 9.0.2, Linux. Use `.venv-issue81` instead of the plan's generic `.venv` so checks run under 3.13. Original `.venv` is 3.12.3 and was preserved. This environment reads existing EDMC runtime packages and installed pure Python test dependencies; these tests do not verify release dependency bundling. See [dashboard](execution-status.md).

Test files added: `tests/test_version_notifications.py`, `tests/test_harness_version_notifications.py`.
Test file updated: `tests/test_harness_smoke.py` (explicitly disables live version/updater producers; dedicated tests exercise real producers through fake adapters).

Exact test commands (from repository root):

```bash
source .venv-issue81/bin/activate && python -m pytest -q tests/test_harness_version_notifications.py -k 'real_version_worker_never_calls_tk or actual_update_ready_callback_never_calls_tk'
source .venv-issue81/bin/activate && python -m pytest -q tests/test_version_notifications.py
source .venv-issue81/bin/activate && python -m pytest -q tests/test_version_notifications.py tests/test_harness_version_notifications.py
source .venv-issue81/bin/activate && python -m pytest -q tests/test_version_notifications.py tests/test_harness_version_notifications.py -k 'multiple_publishers or stop_before_app or stop_closes or timed_out or original_scheduling_root or consumer_error or application_callback or destroyed or unexpected_timer_error'
source .venv-issue81/bin/activate && python -m pytest -q tests/test_version_notifications.py tests/test_harness_version_notifications.py tests/test_harness_smoke.py tests/test_harness_integration.py
source .venv-issue81/bin/activate && python -m pytest
```

| Stage/run | Command above | Outcome |
| --- | --- | --- |
| 2.1 original producer RED | 1 | 3 failed, 11 deselected; release, fallback and actual updater callback each reached UI `get_root` on a worker |
| 2.1 mailbox RED | 2 | 1 expected collection error: new module absent |
| 2.1 delivery GREEN | 3 | 17 passed |
| 2.1 targeted gate | 5 | 30 passed, 1 skipped |
| 2.1 full milestone | 6 | 166 passed, 1 skipped |
| 2.2 adversarial probe | 4 | 11 passed, 17 deselected; no additional production correction needed |
| 2.2 final targeted gate | 5 | 41 passed, 1 skipped |
| 2.2 final full milestone | 6 | 177 passed, 1 skipped |

The sole skip is `tests/test_harness_integration.py::test_harness_full_mining_run_writes_session_data_file`, an existing opt-in export requiring `EDMCMA_HARNESS_GENERATE_SESSION_FILE=1`. No relevant version test skipped. There are no unresolved automated failures; original RED failures are resolved. Logs and detailed test/demonstration evidence are under each stage's `implementation/` directory. Project `make check` delegates to pytest; no separate packaging build applies to this change.

## Phase 3.1 call paths and demonstrations — Completed

- Actual version worker: unchanged release/tag HTTP requests -> captured mailbox publisher -> typed data. No worker UI method, root lookup, Tk call or presentation-state mutation.
- Actual callback supplied to UpdateManager: captured startup mailbox -> update-ready data only. Download/install implementation untouched.
- Main-thread `plugin_app`: build -> render initial state -> drain retained messages -> one 100 ms poll. Poll dispatches existing handlers and renders directly. Identity checks precede stale-callback timer ownership mutations and rearming.
- Stop: deactivate/close/discard/cancel the exact scheduling root's timer before updater/version waits. Main thread owns worker references; an old completion cannot clear a newer worker's reference. Per-message application occurs outside the mailbox lock; unexpected errors retain tracebacks and later valid messages continue.
- AST comparison against HEAD confirms tag lookup and both normalization/merge handlers plus status logging remain identical after normalizing the render-method rename. Label wording/UI implementation, settings, HTTP constants/timeouts, updater, and `load.py` unchanged. Vendored paths have empty diffs.

Normal demo (executed tests, fake HTTP/manual scheduler): release and fallback completion leave state/label unchanged until main-thread consumption, then show latest `99.0.0`. The actual updater callback leaves state untouched until consumption, then shows ready status. Before app creation the worker performs zero UI operations and attachment consumes its retained result.

Restart demo (executed adversarial test): old real worker survives `join(0)`; a new real worker starts and remains held. Releasing the old result, invoking its updater callback from a worker, and invoking its stale timer on the main thread leave current mailbox/thread/timer/root/labels untouched. Only releasing the new response and ticking renders `101.0.0`; only the current updater callback plus another tick sets ready=True. Events, bounded joins and explicit callbacks replace sleeps. No live network/updater adapters are used.

GUI probe run under the same activated environment:

```python
import tkinter as tk
root = tk.Tk()
root.withdraw()
root.destroy()
```

Result: skipped after `TclError: couldn't connect to display ":1"`. No Xvfb is available. Real-Tk fast/delayed startup, preferences-open completion, in-flight shutdown and screenshot checks therefore skipped. Windows EDMC checks skipped because this machine is Linux. These remain manual validation limits, not automated passes.

## Phase 3.2 supplied EDMC compliance rules — Review recorded

Comparison source: [EDMC PLUGINS.md](https://github.com/EDCD/EDMarketConnector/blob/main/PLUGINS.md), with [runtime baseline](https://github.com/EDCD/EDMarketConnector/blob/main/docs/Releasing.md) checked 2026-11-07. This records applicable results and known existing gaps; the issue does not authorize unrelated repairs.

| Supplied rule group | Yes/No | Evidence and required follow-up for No |
| --- | --- | --- |
| Core alignment and monitoring | No (full group) | Runtime baseline matches 3.13 and `load.py` exposes `plugin_start3`; Releases/Discussions subscriptions and a weekly review process are unverified. Maintainer must establish/record monitoring; account settings were not changed. |
| Supported APIs/helpers | Yes (changed paths) | New mailbox imports only standard-library modules; plugin keeps the existing `timeout_session`-backed requests helper and relative imports. This fix performs no player-state detection or configuration writes. No new EDMC API is introduced. |
| Logging/versioning | No (full group; existing gap) | Existing `PLUGIN_NAME` is `EDMC Mining Analytics`, installed folder is `EDMC-Mining-Analytics`, while logger helper derives `edmc_mining_analytics` from its package directory. Align logger/plugin identity in a separately scoped change. This fix uses existing logger methods and tracebacks, no print or new version-specific branch. |
| Responsive, Tk-safe runtime | No (whole plugin); Yes (both issue #81 paths) | Both selected producers are now data-only workers with main-thread delivery and stop guards. Unrelated EDSM/market `_schedule_ui_refresh` still reaches root/Tk and remains out of scope; that dispatch needs its own thread-safety review/fix. |
| Preferences/UI integration | No (full group; existing gap) | Hooks, namespaced typed config reads and locale-aware market parsing exist, and `plugin_prefs` uses `nb.Frame`; inner preferences still construct raw Tk/ttk widgets. Review/migrate preference widgets to EDMC notebook/theme conventions separately. No preferences changed here. |
| Dependencies/debug HTTP | No (full group; existing gap) | Existing plugin folder contains hyphens, and runtime code has no `debug_senders` integration. Address namespace/packaging and debug HTTP separately. This change adds no third-party dependency and uses only fake adapters for validation. |

No release packaging/version changes, commits, staging, external writes, credential access, or live updater execution. Release notes contain only the narrow Unreleased issue #81 fix. Final documentation/log scan and worktree review are recorded in the dashboard.
