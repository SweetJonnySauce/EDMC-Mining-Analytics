# Plan — Track Planetary Mining Location

## Test scenarios

| Case | Input | Expected result |
|---|---|---|
| Valid approach site | `ApproachBody(Colonia 3 d)` → `Touchdown` with index `13` → Rhino launch | State uses `Colonia 3 d`; session payload has `Planetary Mining Location Signal (13)`. |
| Invalid site | Missing, malformed, non-planetary, or zero index destination | No surface-site metadata. |
| Expired site | Valid touchdown → `SupercruiseEntry` → Rhino launch | No inherited site/body candidate. |
| Active session site | Rhino launch → approach → matching touchdown | The active Rhino session receives the body and site index. |
| Existing boundaries | Existing Rhino and Prospector sequences | No behavior change. |

## Implementation checklist

- [x] Inspect state, journal dispatch, recorder payload, and existing tests.
- [x] Add Phase 3 requirements and stage tracking to the approved feature plan.
- [x] Write failing unit tests for capture, expiry, and payload persistence.
- [x] Add minimal approach candidate and session metadata logic.
- [x] Run focused tests and the full suite.
- [x] Review scope, update stage status, and report results without committing.
