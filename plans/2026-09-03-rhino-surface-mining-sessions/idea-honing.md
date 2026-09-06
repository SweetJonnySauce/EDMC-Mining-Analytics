# Requirements clarification

## Question 1

When a new `LaunchSRV` event for `mev_rhino` arrives while a Rhino surface-mining session is already active (as appears in the supplied log), should the plugin finalize the existing session and immediately start a new one, or ignore the duplicate launch and keep the existing session open?

### Answer 1

Continue the active Rhino session unless EDMC has reported a `SupercruiseEntry` event. If a `SupercruiseEntry` event has been observed, a subsequent Rhino `LaunchSRV` starts a new session.

This rule applies to a repeated Rhino launch: absence of an observed supercruise transition means it is a continuation, while a launch after that transition is a new session boundary.

## Requirements-completeness checkpoint

Confirmed by the user on 2026-09-04: requirements clarification is complete.

## Question 2

How should a Planetary Mining Location identified by `Touchdown` participate in a Rhino mining session?

### Answer 2

After `ApproachBody` and before the next supercruise/FSD transition, a `Touchdown` whose `NearestDestination` is `$SAA_Unknown_Signal:#type=$PlanetaryMiningLocation_Name;:#index=N;` identifies `Planetary Mining Location Signal (N)` on the current body. It is session location metadata, not a mining-session boundary. The next Rhino launch inherits it, and a valid touchdown while a Rhino session is active updates that session.
