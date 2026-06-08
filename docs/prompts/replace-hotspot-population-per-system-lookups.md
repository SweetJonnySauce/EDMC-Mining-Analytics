### Replace Hotspot Population Per-System Lookups Prompt
```
Implement Phase 6 of docs/plans/hotspot-population-filter.md.

Goal:
- Replace the current normal Hotspot Finder population lookup flow that calls individual `GET /api/system/{id64}` requests.
- Use Spansh reference-system system-search pages to warm/populate the persistent population cache instead.
- Body search results must pull population from the persistent cache by `system_id64`.

Stay aligned with AGENTS.md:
- Before coding, read AGENTS.md, docs/plans/hotspot-population-filter.md, and this prompt.
- Before coding, inspect:
  - edmc_mining_analytics/integrations/spansh_hotspots.py
  - edmc_mining_analytics/integrations/spansh_population.py
  - edmc_mining_analytics/mining_ui/hotspot_search_window.py
  - tests/test_spansh_hotspots.py
  - tests/test_spansh_population_lookup.py
  - tests/test_hotspot_population_filter.py
- Keep changes behavior-scoped and avoid unrelated refactors.
- Do not edit tests/harness.py or anything under tests/edmc/.
- Keep load.py minimal; only touch lifecycle wiring if truly required.
- Choose test type by touchpoint before coding and record that choice in the plan.
- Update Phase 6 stage statuses as work completes. When all Phase 6 stages are complete, mark Phase 6 Completed.
- Document implementation results, exact test commands, and pass/fail/skip outcomes in the plan.

Locked behavior:
- `/api/bodies/search` does not accept population filters.
- Body search still returns bodies, and body result `system_id64` is used to read population from the persistent cache.
- Normal Hotspot Finder population flow must not issue individual `GET /api/system/{id64}` requests for body-search results.
- The system-search endpoint is `/api/systems/search/save`.
- Use a normal JSON search object body. Do not wrap the serialized search request as a form/key payload because Spansh ignores the search fields in that shape.
- The system-search request JSON must include:
  - `filters.distance.min` mapped from the Hotspot Finder UI distance setting
  - `filters.distance.max` mapped from the Hotspot Finder UI distance setting
  - `filters.bodies: [{"type": {"value": ["Planet"]}}]`
  - `sort: []`
  - `size: 100`
  - `page`
  - `reference_system` equal to the Hotspot Finder reference system, whether typed or default/current
- Fetch/cache page `0` before using cached population values for the body-search results.
- Parse system-search responses with top-level `results`; cache every usable `results[].id64 -> results[].population`.
- Continue pages after page `0` in a background worker thread.
- Background pagination must update only the persistent cache and debug logs, never Tk widgets directly.
- A newer reference-system/distance search must cancel or supersede older background pagination.
- Missing cache values remain blank.
- Unknown population rows remain visible even when a Population filter is selected.
- Do not make extra Spansh requests to fill individual blank Population cells.
- Cache remains plugin-owned, persistent across EDMC restarts, and one-month TTL.
- Keep existing UI behavior:
  - Population dropdown below Min Hotspots
  - INARA-style labels
  - `Any` means no population filter
  - `None` means `population == 0`
  - `Below ...` filters are inclusive `population <= threshold`
  - Population column remains in search results

Implementation order:
1. Verify the test environment is ready. If dependencies are missing, set up the venv using the command in AGENTS.md.
2. Update the plan's test type decision for Phase 6 before coding.
3. Implement a system-search page fetch/cache service in `edmc_mining_analytics/integrations/spansh_population.py`.
4. Implement background pagination with cancellation/supersession in `edmc_mining_analytics/integrations/spansh_population.py` or a focused helper.
5. Update `edmc_mining_analytics/integrations/spansh_hotspots.py` so reference-system searches:
   - fetch/cache system-search page `0`
   - schedule background pagination for later pages
   - read populations from cache by body result `system_id64`
   - do not call individual `/api/system/{id64}` for body results
6. Update or replace tests that currently assert per-system lookup behavior.
7. Add tests for:
   - normal JSON `/api/systems/search/save` payload with `size: 100`
   - page `0` cache population
   - page metadata / remaining page scheduling
   - background pagination cache writes
   - cancellation/supersession of stale pagination
   - no individual `/api/system/{id64}` calls in normal body-result population flow
   - blank/missing population values remain visible
8. Run targeted tests after each implementation stage, then run:
   - `.venv/bin/python -m pytest -q tests/test_spansh_population_lookup.py`
   - `.venv/bin/python -m pytest -q tests/test_spansh_hotspots.py`
   - `.venv/bin/python -m pytest -q tests/test_hotspot_population_filter.py tests/test_preferences.py`
   - `.venv/bin/python -m pytest -q tests/test_hotspot_*.py tests/test_spansh_*.py tests/test_preferences.py`
   - `.venv/bin/python -m pytest -q`
9. Update docs/plans/hotspot-population-filter.md with completed Phase 6 stages, implementation results, tests run, and remaining risks.

Do not do broad live Spansh API probing. If a narrow live request is needed to verify `/api/systems/search/save`, stop and ask first.
```
