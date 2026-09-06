# Plan: Rhino cargo capacity

| Stage | Description | Status |
|---|---|---|
| 9.1 | Add unit tests for 72t surface capacity selection, short SRV total tracking, and unchanged asteroid capacity selection. | Completed |
| 9.2 | Add the pure capacity helper and set Rhino current cargo from short SRV Cargo. | Completed |
| 9.3 | Route overlay and in-plugin summary capacity consumers through the helper. | Completed |
| 9.4 | Run focused and full validation. | Completed |

## Test scenarios

| Input | Expected output |
|---|---|
| Surface session with ship capacity 168 and SRV count 36 | Active capacity is 72, current cargo is 36, `% Full` is 50.0%, and bar width is based on 72. |
| Asteroid session with ship capacity 168 | Active capacity remains 168. |
