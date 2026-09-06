# Context: Rhino cargo capacity

## Requirements

- Use the Rhino's fixed 72t capacity for active Rhino surface sessions.
- Treat short SRV `Cargo.Count` as the current Rhino cargo total, as already agreed.
- Use the Rhino capacity for `% Full`, overlay bar percentages, and the in-plugin cargo summary.
- Preserve the ship `cargo_capacity` field and asteroid behavior.

## Design

`MiningSessionKind.SURFACE` is exclusive to Rhino sessions. A pure state helper will select 72t for that session kind and otherwise return the existing ship capacity. The short SRV Cargo handler will copy its validated total count into `current_cargo_tonnage`. Overlay and UI summary consumers will use the helper.

## Dependency map

Short SRV `Cargo.Count` → `current_cargo_tonnage` → active-session capacity helper → overlay `% Full` / bars and UI cargo summary.

No journal capacity field exists for the Rhino; current `CargoCapacity` is the ship's 168t capacity. The 72t Rhino specification is therefore a fixed domain constant.

## Existing documentation

`docs/overlay-bars.md` establishes that bar percentages use cargo capacity. `tests/README.md` prohibits modifying vendored harness files. No `CODEASSIST.md` exists.
