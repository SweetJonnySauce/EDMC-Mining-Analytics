# Context: Surface estimated credits

## Requirements

- When a Rhino short-SRV cargo increase is reconciled to a surface-mined commodity, request that commodity's market price.
- Reuse `MarketSearchService`; it owns deduplication, worker-thread lookup, price storage, estimate recomputation, and UI refresh.
- Do not change asteroid cargo processing, preferences, or the Spansh client.

## Integration path

`MiningRefined` + short SRV `Cargo` → `JournalProcessor._reconcile_pending_srv_cargo()` → `MarketSearchService.request_price()` → cached `market_sell_prices` → existing estimated-credit recomputation.

The asteroid inventory path already makes this request. The Rhino reconciliation path tracks the same commodity totals but omitted it.

## Existing documentation

`README.md` describes market search as an optional estimated-price source. `tests/README.md` requires vendored harness files to remain unchanged. No `CODEASSIST.md` exists.
