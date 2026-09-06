# Context: buffered SRV cargo reconciliation

The 2026-09-06 Rhino journal shows `Cargo.Count` records arriving before related `MiningRefined` records. The existing FIFO allocator discards those unmatched positive deltas, resulting in 7 Copper and 45 Samarium in the UI instead of the confirmed 10 Copper and 44 Samarium.

`Cargo.Count` is an explicitly accepted total across all SRV commodities. The solution must only operate during an active `MiningSessionKind.SURFACE` session. Asteroid full-inventory cargo processing and limpet accounting must retain their present behavior.
