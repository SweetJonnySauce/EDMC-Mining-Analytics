# Stage 2.1 context

Auto-mode parameters confirmed: task-01-version-notification-delivery.code-task.md; current repository root; implementation notes in this directory. No further confirmation required. No CODEASSIST.md exists; the approved plan and AGENTS.md provide project instructions.

Existing documentation: README requires EDMC 6 / Python 3.13; tests/README.md prohibits vendored harness edits and describes headless testing. Parent checked upstream docs/Releasing.md before coding. Use `source .venv-issue81/bin/activate` for Python 3.13.5; original `.venv` remains Python 3.12 and is not the validation interpreter.

Dependency map: load.py hooks -> MiningAnalyticsPlugin lifecycle -> lifecycle-owned mailbox <- actual version worker and UpdateManager callback; plugin_app -> main-thread timer -> existing version handlers -> UI label. Mailbox imports only standard-library data/threading modules. Existing handler merge rules and HTTP paths are lifted intact.

Harness gap: harness_context(start_plugin=False) allows replacing UI, restoring `_ensure_version_check`, substituting fake HTTP/UpdateManager before the hook starts. No fixture edits needed. New tests use temporary plugin directories; no network/update adapter may reach real HTTP or install files.
