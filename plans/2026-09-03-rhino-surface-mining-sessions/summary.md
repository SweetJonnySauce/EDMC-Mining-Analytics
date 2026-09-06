# Rhino surface-mining session planning summary

## Artifacts

- `rough-idea.md`: original Rhino boundary request.
- `idea-honing.md`: confirmed requirements, including duplicate-launch recovery behavior.
- `research/log-evidence.md`: supplied journal-log evidence for Rhino and Planetary Mining Location events.
- `design/detailed-design.md`: standalone design for extending the existing single-session state machine.
- `implementation/plan.md`: completed three-phase, test-driven implementation plan and release checks.

## Approved design

Rhino surface mining starts on normalized `LaunchSRV` type `mev_rhino` and ends on normalized `DockSRV` of the same type. The plugin retains one mutually exclusive mining-session state. A repeated Rhino launch continues an active session unless a supercruise entry has already ended it; then the next launch starts a fresh session.

Planetary Mining Location signals remain non-boundary context. An approach-scoped touchdown at one persists its signal index as Rhino session location metadata, paired with the current body.

## Next step

Review the uncommitted implementation and rerun under EDMC's Python 3.13 runtime before release.
