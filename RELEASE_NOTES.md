# Release Notes

## Unreleased
- Fixed issue #81: deliver version-check and update-ready results on the Tk main thread, with safe notification shutdown and restart isolation.

## 0.6.0
- Unified market search settings for Inara and Spansh into a single Market search tab.
- Added Distance to Arrival (Ls) plus carrier/surface filters to Spansh market searches.
- Inara commodity searches now respect market search filters (distance, landing pad, demand, and data age).
- Note: search settings were reset to the new defaults as part of this consolidation.
