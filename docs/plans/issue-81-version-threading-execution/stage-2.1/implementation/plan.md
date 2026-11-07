# Stage 2.1 implementation and tests

| Stage | Description | Status |
| --- | --- | --- |
| 2.1.1 | Write pure mailbox and real-producer harness regressions; capture RED | Completed |
| 2.1.2 | Implement data mailbox and main-thread consumer with lifecycle-bound producers | Completed |
| 2.1.3 | Review, targeted/full gates, and fake-adapter delivery demo | Completed |

Test types selected before code: unit for mailbox order/drain/close/thread publication; harness for hooks, workers, UI delivery and timer ownership. Inputs: ordered latest/update-ready messages -> same ordered immutable data; closed mailbox -> empty drain and rejected publication. Real fake-HTTP release `v99.0.0` and 404/tag fallback -> presentation state untouched before main-thread consumption, then normalized `99.0.0`. Actual updater callback `v99.0.0` from worker -> no UI access before consumption. Older/equal/newer plus both arrival orders -> existing exact normalization/merge rules. Duplicate app attachment -> one timer; stop -> none and no late delivery. Explicit Events and bounded joins, never sleep synchronization. A recording fake root and UI assert every Tk-like operation runs on the main thread.

Regression commands run separately to distinguish worker-to-Tk failures from absent mailbox module. Gates use Python 3.13 activation substitution documented in context.md. Full suite follows lifecycle wiring. No build/package change is needed for this Python plugin; pytest/imports validate the scoped source.
