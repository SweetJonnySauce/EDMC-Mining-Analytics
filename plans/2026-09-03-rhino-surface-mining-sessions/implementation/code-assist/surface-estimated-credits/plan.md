# Plan: Surface estimated credits

| Stage | Description | Status |
|---|---|---|
| 8.1 | Add a journal simulation asserting reconciled Rhino Gold requests one price lookup. | Completed |
| 8.2 | Reuse the existing market-search request seam during surface cargo reconciliation. | Completed |
| 8.3 | Run focused journal tests and the full suite. | Completed |

## Test scenario

| Input | Expected output |
|---|---|
| Rhino launch, SRV baseline cargo 0, Gold refinement, SRV cargo 1 | Gold is tracked as 1t and the injected market-search service receives one `gold` price request. |
