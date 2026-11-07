# Stage 2.2 implementation and tests

| Stage | Description | Status |
| --- | --- | --- |
| 2.2.1 | Extend unit and harness contracts before source edits | Completed |
| 2.2.2 | Probe accepted implementation and make only proven corrections | Completed |
| 2.2.3 | Review, targeted/full gates and stop/restart demo evidence | Completed |

Selected test types before coding: unit for deterministic mailbox concurrency/order/closure; harness for startup/stop hooks, real producer ownership, timers, consumer callbacks and Tk errors.

| Input / trigger | Expected output / contract |
| --- | --- |
| Two synchronized publishers, then close with pending data | Publication order retained; close discards and late publisher rejected |
| Pending actual producer results, stop before app, repeated stop | Mailbox absent/closed, results discarded, no timer/UI delivery |
| Producer completion inside updater stop and version wait | Mailbox already closed and timer already cancelled before waits |
| Old actual version worker survives join(0), restart with new active worker | Old completion cannot mutate UI/mailbox/current worker or timer |
| Old actual updater callback and old scheduled callback after stop/restart | No delivery/rearm or current timer/root ownership mutation |
| Duplicate app and root-reference replacement before stop | One timer; cancellation uses original scheduling root |
| Unexpected handler exception followed by valid results | Traceback logged; remaining results still apply in order |
| Publisher completes during application callback | No mailbox lock held around callback; newly published result delivered next tick |
| TclError during timer creation/cancellation/rendering | Narrow expected-error handling; coherent timer ownership; no worker fallback |

Use Events and bounded joins, including guaranteed release/cleanup in finally blocks. No timing sleeps. Existing correct cases may pass immediately; preserve stage 2.1 RED rather than manufacture failure. Required targeted four-file gate and full pytest gate run once after final changes. Record exact outcomes and interpreter in progress.md. The executable pytest/import path validates this Python-only change; no packaging build is needed.
