# Progress — Track Planetary Mining Location

## Checklist

- [x] Setup: created task documentation and inspected applicable repository guidance.
- [x] Explore: mapped the journal-to-session-recorder metadata path.
- [x] Plan: documented tests, boundaries, and the approach-candidate design.
- [x] RED: added tests and confirmed the prior implementation failed them (missing state field/body fallback).
- [x] GREEN: implemented the smallest approach candidate, Rhino launch fallback, and payload label behavior.
- [x] Refactor/review and validate: focused tests passed (21); full suite passed (141 passed, 1 skipped); `git diff --check` passed.
- [x] Commit: skipped by explicit user instruction; do not stage or commit.

## Decision log

- A touchdown is context, not a start or stop event.
- The site candidate remains valid only for one approach leg and is cleared on supercruise/FSD transitions.
- The existing body field remains a body name. The derived site label is persisted separately in `meta.location`.
- Validation used Python 3.12.3. EDMC Python 3.13 verification remains a release prerequisite.
