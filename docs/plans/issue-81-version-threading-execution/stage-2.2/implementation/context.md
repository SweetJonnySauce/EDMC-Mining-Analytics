# Stage 2.2 context

Parameters acquired: accepted stage 2.2 task; current repository; auto mode; this isolated implementation directory. No further confirmation is needed; commits/staging are prohibited. No CODEASSIST.md or nested AGENTS.md exists. Existing AGENTS.md and approved plan provide the relevant conventions without adding another project instruction file.

Existing documentation: README requires Python 3.13 / EDMC 6. tests/README.md marks harness.py, tests/edmc and journal_config as immutable and documents opt-in export testing. Stage 2.1 progress anchors the original producer RED and normal delivery gates. Use `source .venv-issue81/bin/activate` for the established Python 3.13.5 environment; no dependency installation.

Dependency map: load hooks -> plugin lifecycle -> captured mailbox publishers <- actual version worker / actual supplied updater callback; app -> owned main-thread poll -> existing merge handlers -> recording UI. Test helpers provide fake HTTP gates, timer history, captured updater callback and thread assertions. Source seams already close/discard/cancel before waits, retain the scheduling root, check mailbox identity before callback ownership mutation, and avoid worker-side thread-reference clearing.

Touchpoints: extend pure mailbox tests and lifecycle harness tests; source correction only if a new test proves a defect. Parent owns dashboard, approved plan, release notes and final platform review. No live network/updater, vendored changes, unrelated cleanup, or new dependencies.
