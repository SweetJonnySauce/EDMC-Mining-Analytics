# Plan: Overlay bar quantity

| Stage | Description | Status |
|---|---|---|
| 7.1 | Add a headless dispatch test for an orange `(Nt)` message immediately after a bar, including stale-row clearing. | Completed |
| 7.2 | Add a small quantity-message offset and dispatch it next to each bar; include it in bar cleanup. | Completed |
| 7.3 | Run overlay tests and the full test suite. | Completed |

## Test scenarios

| Input | Expected output |
|---|---|
| A 30-ton, 30%-width bar at a known anchor | `edmcma.bar.0.quantity` text is `(30t)`, orange, and positioned after the computed bar width. |
| A previously rendered row is removed | Its quantity message is sent as empty text with a short TTL, matching label cleanup. |
