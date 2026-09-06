# Plan: buffered SRV cargo reconciliation

| Stage | Description | Status |
|---|---|---|
| 6.1 | Add a pending positive SRV cargo-delta counter and reconcile it with queued Rhino refinements in either arrival order. | Completed |
| 6.2 | At a Rhino commodity transition, discard any unfulfilled prior refinement only after a Cargo snapshot has observed it. | Completed |
| 6.3 | Add journal simulation regressions for cargo-first ordering, stale prior commodity handling, and asteroid isolation. | Completed |
| 6.4 | Run targeted and full test suites. | Completed |

No `load.py`, UI, preferences, network, timer, or vendored-harness changes are expected.
