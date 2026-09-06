# Progress: Overlay bar quantity

- [x] Set up implementation documentation and inspect overlay dispatch seams.
- [x] Write and run the expected-failing rendering regression test.
- [x] Implement quantity dispatch and cleanup.
- [x] Run focused and full validation.

Mode: automatic. No commit will be created, per the existing workspace instruction.

## TDD record

- Red: `python -m pytest tests/test_overlay_bars.py` failed because `edmcma.bar.0.quantity` was absent.
- Green: the same command passed with 6 tests after adding the quantity payload and cleanup path.
- Full validation: `make check` passed with 146 tests and 1 skipped.
- Simplification: reused existing `_OverlayBar.amount`, text dispatch, and per-row cleanup rather than changing overlay state or preferences.
