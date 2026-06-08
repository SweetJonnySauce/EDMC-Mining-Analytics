

### Execute plan prompt
```
Execute each phase in order. For each phase, create and document a detailed execution plan. Implement the execution plan and document the results. Once done with that phase, move on to the next one. If you have questions that I need to answer, stop and ask me. 

Before you get started, make sure your environment is properly set up for testing.
```

### Add Population Filter To Hotspot Finder Prompt
```
Implement the plan in docs/plans/hotspot-population-filter.md.

Stay aligned with AGENTS.md:
- Before coding, read the plan and current hotspot search code.
- Keep changes behavior-scoped and avoid unrelated refactors.
- Do not edit tests/harness.py or anything under tests/edmc/.
- Keep load.py minimal; only touch lifecycle wiring if truly required.
- Choose test type by touchpoint before coding and record that choice in the plan.
- Update stage statuses as work completes. When all stages in a phase are complete, mark the phase Completed.
- Document implementation results, exact test commands, and pass/fail/skip outcomes in the plan.

Important locked decisions from the plan:
- /api/bodies/search does not accept population filters.
- Population filtering must use returned body-search `system_id64` values and fresh cached system populations.
- Before a reference-system hotspot body search, run Spansh system-search page 0 using the same reference system value.
- The warmup endpoint is `/api/systems/search/save`.
- The warmup must use a normal JSON search object body. Do not wrap the serialized JSON request as a form/key payload because Spansh ignores the search fields in that shape.
- The warmup distance range must map to the Hotspot Finder UI distance settings.
- The system-search page size is `100`.
- Fetch/cache page 0 before using cached population values for the body-search results.
- Fetch additional system-search pages in a background worker thread.
- Background pagination must update only the persistent cache and debug logs, never Tk widgets directly.
- A newer reference-system search must cancel or supersede older background pagination work.
- The warmup caches returned system-search `results[].id64 -> results[].population` values.
- Do not issue individual `GET /api/system/{id64}` lookups for each body result in the normal Hotspot Finder population flow.
- Cache is plugin-owned, persistent across EDMC restarts, and has a one-month TTL.
- Cache storage must stay out of git; .gitignore already ignores cache/.
- Unknown/unresolved Population result values display blank.
- Use INARA-style Population presets.
- Any means no population filter.
- None means population == 0.
- Below ... filters are inclusive population <= threshold.
- Population filter goes below the existing Min Hotspots filter.
- Hotspot Finder search results include a Population column.
- Do not make extra Spansh requests to fill the Population column when the warmup cache does not contain a body result's parent system.
- Unknown population rows remain visible even when a Population filter is selected.
- Spansh system search responses are paginated. Use page 0 synchronously for the immediate search path and continue additional pages in the background.

Implementation order:
1. Verify the test environment is ready. If dependencies are missing, set up the venv using the command in AGENTS.md.
2. Inspect edmc_mining_analytics/integrations/spansh_hotspots.py and edmc_mining_analytics/mining_ui/hotspot_search_window.py.
3. Verify completed Phases 2, 3, and 4 still match the current plan; do not redo unrelated completed work.
4. Implement Phase 6 from the plan: replace normal per-ID lookup with reference-system system-search page 0 before body search plus background pagination.
5. Keep the persistent one-month cache, UI dropdown below Min Hotspots, selected option plumbing, and Population result column behavior intact.
6. Update or replace tests that still assert per-ID lookup behavior.
7. Run targeted tests after each phase, then run the broader relevant test suite.
8. Update docs/plans/hotspot-population-filter.md with completed stages, implementation results, tests run, and remaining risks.

Do not do live broad API probing. The plan already establishes that body search cannot filter by population. If a live Spansh request is needed for a narrow manual smoke, ask first and keep it to the smallest useful request count.
```
