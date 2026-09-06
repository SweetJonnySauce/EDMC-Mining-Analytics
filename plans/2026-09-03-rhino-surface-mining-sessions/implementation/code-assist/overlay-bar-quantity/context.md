# Context: Overlay bar quantity

## Requirements

- Render each overlay-bar quantity as `(Nt)` immediately to the right of its filled bar.
- Use the same Elite Dangerous orange (`#ff6f00`) as the bar.
- Clear the quantity message when a bar row is removed.
- Preserve existing labels, bar dimensions, ordering, and max-row behavior.

## Existing pattern and dependency map

`MiningState` → `EdmcOverlayHelper._build_overlay_bars()` → `_dispatch_overlay_bars()` → EDMCOverlay message/shape API.

`_OverlayBar.amount` already carries the quantity. The existing overlay-bar unit tests are pure/headless and the rendering helper dispatches both text and rectangle payloads. This change belongs only in `edmc_mining_analytics/integrations/edmcoverlay.py` and `tests/test_overlay_bars.py`; it requires no settings, lifecycle, or thread changes.

## Existing documentation

`docs/overlay-bars.md` establishes that bars are orange, fixed-width relative to capacity, and rendered under Est. CR. `tests/README.md` confirms vendored harness files are immutable; they are outside this change.
