# Task Plan: Recognize Rhino Dock

## Test Strategy

- A normalized Rhino dock after Rhino launch ends at the dock timestamp and
  records the exact end reason.
- Non-Rhino, missing, blank, non-string, and inactive Rhino docks are no-ops.
- Rhino launch, supercruise, then Rhino launch creates a second session.
- The registered EDMC journal callback publishes Rhino active then inactive
  shared state, while Prospector/supercruise remains covered in that scope.

## Implementation Approach

1. Add all unit and harness tests, run the focused tests to establish RED.
2. Route `DockSRV` to one private handler that reuses `_is_rhino_srv` and the
   existing stop transition.
3. Run scoped unit, focused harness, and full test commands; only then update
   the approved implementation-plan status.

## Checklist

- [x] Add focused RED tests.
- [x] Add the minimum dock handling implementation.
- [x] Run all required validation and inspect the scoped diff.
