# Progress: Rhino cargo capacity

- [x] Inspect Cargo/Loadout evidence and all capacity consumers.
- [x] Add and run expected-failing state, journal, and overlay tests.
- [x] Implement the Rhino capacity selection and short-SRV total update.
- [x] Route visible capacity consumers and validate.

Mode: automatic. No commit will be created.

## TDD record

- Red: the state capacity selector was absent; the new tests could not import it.
- Green: 36t in a surface session resolves to 72t capacity, 50.0% full, and a 50% bar; asteroid capacity remains 168t.
- Full validation: `make check` passed 149 tests with 1 skipped.
- Scope: ship capacity is retained in its existing field; only active live surface-session consumers select the Rhino's fixed capacity.
