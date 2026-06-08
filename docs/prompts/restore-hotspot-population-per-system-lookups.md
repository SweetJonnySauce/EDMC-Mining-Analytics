# Restore Hotspot Population Per-System Lookups

Use this prompt to implement Phase 8 of `docs/plans/hotspot-population-filter.md`.

## Objective

Back out the normal Hotspot Finder population flow that warms population through reference-system system search pages.

Restore a cache-first, bounded per-system detail lookup flow:

- Hotspot Finder body search still uses `/api/bodies/search`.
- Body result `system_id64` values drive population lookup.
- Cached population values are used first.
- Missing cached values may be fetched with `GET /api/system/{id64}` only when a non-`Any` Population filter is selected.
- `Any` Population selection is cache-only and must not trigger live population lookups.
- Live system detail lookups must be ordered by body result Distance, nearest first.
- Live system detail lookups must be deduped, throttled, and capped at 50 per user search action.
- Missing values beyond the cap remain blank/unknown.
- Failed or malformed live responses must be cached as unknown.
- Zero population values must be cached normally.
- Unknown population rows remain visible even when a Population filter is selected.
- Population values that are found must be written to the persistent plugin-owned cache with the existing one-month TTL.

## Required Reading

Before coding, read:

- `AGENTS.md`
- `docs/plans/hotspot-population-filter.md`
- this prompt

Follow the Phase 8 stages in the plan and update stage statuses as work completes.

## Required Removals

Remove the normal Hotspot Finder population path that uses:

- `POST /api/systems/search/save`
- `GET /api/systems/search/recall/{search_reference}`
- `GET /api/systems/search/recall/{search_reference}/{page}`
- background pagination for reference-system system-search pages
- warmup reuse keyed by reference-system/distance

The normal Hotspot Finder population flow must not call system-search save/recall endpoints.

## Required Implementation Behavior

Implement or restore the population lookup service so it:

- accepts body result `system_id64` values
- preserves first-seen order
- dedupes duplicate ids
- reads the persistent cache first
- only fetches cache misses
- performs live lookups only for non-`Any` Population filters
- orders live lookup candidates by body result Distance, nearest first
- performs at most 50 live `GET /api/system/{id64}` calls per user search action
- parses `population` from successful system detail responses
- writes successful live results to the persistent cache
- writes failed/malformed live responses as unknown
- writes `population: 0` as a normal known value
- returns cache hit/miss/cap information useful for debug logs and tests
- logs useful debug details without spamming in release behavior

Keep the existing Population UI behavior:

- Population dropdown below Min Hotspots
- INARA-style labels
- `Any` means no population filter
- `Any` is cache-only and does not trigger live population lookups
- `None` means `population == 0`
- `Below ...` filters are inclusive `population <= threshold`
- Population column remains in search results
- Known non-matching populations are filtered out
- Unknown population rows remain visible and show blank Population

## Required Tests

Choose tests per `AGENTS.md` before coding. For this change, unit tests should be sufficient unless you touch `load.py` or EDMC lifecycle/hook wiring.

Update or add tests for:

- cache hits do not issue live system detail requests
- duplicate `system_id64` values are fetched at most once
- live lookup cap of 50 is enforced
- live lookups are ordered by body result Distance, nearest first
- `Any` does not trigger live population lookups
- successful `GET /api/system/{id64}` responses populate the cache
- `population: 0` system detail responses populate the cache normally
- failed/malformed system detail responses are cached as unknown without crashing search
- Hotspot Finder normal population flow does not call `/api/systems/search/save`
- Hotspot Finder normal population flow does not call `/api/systems/search/recall/...`
- known population values display/filter correctly
- unknown population values remain blank and visible
- no obsolete tests still require system-search warmup/background pagination as the normal population path

## Required Commands

Run and record outcomes in `docs/plans/hotspot-population-filter.md`:

```bash
.venv/bin/python -m pytest -q tests/test_spansh_population_lookup.py tests/test_spansh_hotspots.py
.venv/bin/python -m pytest -q tests/test_hotspot_*.py tests/test_spansh_*.py tests/test_preferences.py
.venv/bin/python -m pytest -q
```

Also run focused `py_compile` for touched modules:

```bash
.venv/bin/python -m py_compile edmc_mining_analytics/integrations/spansh_hotspots.py edmc_mining_analytics/integrations/spansh_population.py
```

## Constraints

- Do not do broad live Spansh API probing.
- If a narrow live request is needed, stop and ask first.
- Do not edit `tests/harness.py`.
- Do not edit anything under `tests/edmc/`.
- Do not touch `load.py` unless truly necessary. If you do, add the required harness tests.
- Keep changes behavior-scoped and reversible.

## Completion Criteria

The implementation is done when:

- Phase 8 stages are marked completed in the plan.
- Implementation results are recorded in the plan.
- Exact test commands and outcomes are recorded in the plan.
- Normal Hotspot Finder population flow uses bounded `GET /api/system/{id64}` cache-miss lookups.
- Normal Hotspot Finder population flow no longer uses reference-system system-search save/recall warmup.
