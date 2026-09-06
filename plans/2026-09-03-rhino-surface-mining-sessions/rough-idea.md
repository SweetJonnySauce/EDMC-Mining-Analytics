# Rough idea

Add Rhino surface-mining sessions to EDMC Mining Analytics.

- Start a mining session when a journal `LaunchSRV` event has `SRVType` equal to `mev_rhino`.
- Stop it when a journal `DockSRV` event has the same Rhino type.
- A player cannot be in an asteroid-mining session and a Rhino surface-mining session at the same time.

The supplied EDMC log contains Rhino launch/dock examples, including unmatched boundary events that the design must handle safely.
