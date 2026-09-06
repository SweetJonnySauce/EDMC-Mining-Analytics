# Supplied journal-log evidence

Source: `/home/jon/edmc-logs/EDMC-LogEventMiner-NoFilter.log`.

## Planetary Mining Location signals

The journal reports Planetary Mining Locations in `FSSBodySignals` and `SAASignalsFound` records. The signal type is `$PlanetaryMiningLocation_Name;`, localized as `Planetary Mining Location`.

Relevant Rhino-run context:

- `2026-09-03T14:48:03Z`: `SAASignalsFound` for `Colonia 7 e` (body ID `52`) in `Colonia`, with `22` Planetary Mining Locations.
- `2026-09-03T14:51:47Z`: `LaunchSRV` for `SRVType` `mev_rhino`.
- `2026-09-03T15:21:03Z`: matching Rhino `DockSRV`.

The same Planetary Mining Location signal is repeated for `Colonia 7 e` at `2026-09-03T15:21:52Z`.

Other observed bodies include Kinesi 6 d/b/a/c a/c/e/f/h and Colonia 3 d/c. Signal counts range from 4 to 25 in this log.

## Design implication

`LaunchSRV` does not itself contain the system or body. A Rhino session must inherit the most recently observed location from journal/shared state. Capturing Planetary Mining Location signal counts is a separate product decision; session boundaries only require the Rhino launch/dock events.
