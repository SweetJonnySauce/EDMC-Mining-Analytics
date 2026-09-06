# Progress: Surface estimated credits

- [x] Inspect the Rhino and asteroid cargo paths and the market-search service.
- [x] Add and run the expected-failing surface price-request test.
- [x] Implement the minimal request call.
- [x] Run focused and full validation.

Mode: automatic. No commit will be created.

## TDD record

- Red: the Rhino Gold scenario tracked `{"gold": 1}` but the injected market-search service received no request.
- Green: cargo reconciliation now calls the existing request seam; the focused test passed 4 tests.
- Full validation: `make check` passed 147 tests with 1 skipped.
- The existing service retains responsibility for deduplication, worker-thread lookup, cache updates, estimated-total recomputation, and UI refresh.
