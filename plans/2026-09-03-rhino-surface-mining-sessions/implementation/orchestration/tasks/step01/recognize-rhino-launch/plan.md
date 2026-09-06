# Task Plan: Recognize Rhino Launch

## Test strategy

- An inactive state receives a mixed-case, padded Rhino `LaunchSRV`: it starts
  at the journal timestamp and invokes the start callback.
- Other, missing, blank, and non-string `SRVType` values are no-ops.
- A second Rhino launch preserves start time, state data, and callback count.
- Existing Prospector tests remain selected by the focused command.

## Implementation approach

1. Add all focused journal simulation tests and run the required filtered test
   command to establish RED.
2. Add the smallest private predicate and dedicated `LaunchSRV` handler.
3. Re-run the command for GREEN, inspect the scoped diff, and record results.

## Checklist

- [x] Add focused RED tests.
- [x] Add minimum launch handling implementation.
- [x] Run focused validation and inspect scoped diff.
