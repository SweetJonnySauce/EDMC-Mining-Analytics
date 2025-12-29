# EDMC 6.0.0 Compatibility Plan (EDMC Mining Analytics)

Track progress for updating this plugin to work with EDMarketConnector 6.0.0.

## Context
- EDMC 6.0.0 introduces a new config system (config.toml), removes deprecated APIs,
  and adds plugin enable/disable behavior that relies on `plugin_stop()`.
- Runtime Python version is now 3.13.

## Plan and Progress
- [x] Audit for removed/deprecated EDMC APIs (`_`, `_Translations`, `nb.Entry`,
  `nb.ColoredButton`, `help_open_log_folder`).
- [x] Align config access to the EDMC 6.0.0 stable API (`config.get_*`, `config.set`).
  - [x] Simplify log level lookup to avoid non-stable getters in
    `edmc_mining_analytics/plugin.py`.
  - [x] Simplify theme config lookups in `edmc_mining_analytics/mining_ui/theme_adapter.py`.
- [x] Verify plugin enable/disable lifecycle:
  - [x] Ensure `plugin_stop()` is idempotent and stops background threads and UI timers.
  - [x] Confirm auto-update thread shutdown is safe under disable/enable.
- [x] Validate UI behavior with updated ttk defaults (check background/foreground usage).
- [ ] Run EDMC 6.0.0 smoke test:
  - [x] Run local journal simulation unit tests.
  - [ ] Start EDMC, load plugin, open prefs.
  - [ ] Disable/enable plugin from Preferences and confirm clean restart.
  - [ ] Verify preferences persist to `config.toml`.
  - [ ] Replay journal sample if possible and check UI updates.
- [x] Update README to note EDMC 6.0.0 / Python 3.13 compatibility and any changes.

## Notes
- EDMC 6.0.0 release notes highlight config migration and deprecated API removals.
- Plugin should avoid non-documented config APIs outside `config.get_*`/`config.set`.

## Results
- Cleaned config access in log level/theme detection to stick to `config.get_int` and `config.get_str`.
- Added shutdown guard to prevent UI/overlay refreshes from re-scheduling during `plugin_stop()`.
- Added lifecycle logging to help verify enable/disable behavior in EDMC logs.
- Updated README requirements to call out EDMC 6.0.0 / Python 3.13.
- Ran `python3 -m unittest edmc_mining_analytics.tests.test_journal_simulation` (2 tests, OK).

## Reproducible Test Flow (EDMC 6.0.0)
1. Start EDMC 6.0.0 with this plugin installed and open `Help -> Open Log Folder`.
2. Open `Preferences -> Plugins` and confirm the plugin loads without errors.
3. Open the plugin panel and the plugin preferences tab; verify the UI renders.
4. Disable the plugin from `Preferences -> Plugins`, then re-enable it.
5. Re-open the plugin panel and confirm it refreshes and responds to inputs.
6. In `config.toml`, confirm plugin settings persist (example keys:
   `edmc_mining_histogram_bin`, `edmc_mining_rate_interval`).
7. Review the EDMC log for lifecycle messages:
   `Plugin start requested`, `Plugin stop requested; shutting down EDMC Mining Analytics`,
   and `Skipping refresh scheduling because plugin is stopping`.
