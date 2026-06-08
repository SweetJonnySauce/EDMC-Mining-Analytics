## Goal: Add a population filter to Hotspot Finder

Follow persona details in `AGENTS.md`.
Document implementation results in the `Implementation Results` section.
After each stage is complete, change stage status to `Completed`.
When all stages in a phase are complete, change phase status to `Completed`.
If something is unclear, capture it under `Open Questions`.

## Requirements
- Add a Population filter control to the Hotspot Finder search UI.
- Place the Population filter below the existing Min Hotspots filter in the Hotspot Finder UI.
- Use INARA's population filter presets as the UI template:
- `Any`
- `None`
- `Above 1`
- `Above 10,000`
- `Above 100,000`
- `Above 1,000,000`
- `Above 1,000,000,000`
- `Below 10,000`
- `Below 100,000`
- `Below 1,000,000`
- `Below 1,000,000,000`
- The low-population path must support zero-population systems. "Below" filters should be implemented as inclusive upper-bound filters (`population <= threshold`) rather than exclusive filters.
- `None` must mean `population == 0`.
- `Any` must omit the population filter entirely.
- When Population is `Any`, do not trigger live population lookups; use cache-only population values for display.
- Add Population as a column in the Hotspot Finder search results.
- The Population result column should show the parent system population when known.
- If population is unavailable because the cache has no fresh value and the per-search live lookup cap has been reached, show a clear unknown/blank state rather than making extra uncapped requests.
- Population filtering must not flood Spansh with unbounded N+1 system detail requests.
- `/api/bodies/search` does not accept population filters, so population filtering must use body result `system_id64` values, a persistent local cache, request deduping, throttling, and a hard cap on live system detail lookups per user search action.
- Normal population display/filtering must use cached values first, keyed by body result `system_id64`.
- For body result `system_id64` values missing from the fresh cache, perform bounded individual `GET /api/system/{id64}` lookups up to the configured live lookup cap when a non-`Any` Population filter is selected.
- Live population lookups must be ordered by body result Distance, nearest first.
- When a body result's `system_id64` is not present in the fresh cache and is beyond the live lookup cap, unresolved result population values must remain blank and must not trigger additional live requests.
- Failed or malformed live population lookups should be recorded as unknown to avoid repeated failed requests in the same cache TTL window.
- System population lookup caching must be persistent across EDMC restarts.
- Persistent cache entries must use a one-month TTL.
- Keep Hotspot Finder usable and responsive; bounded network-bound system detail lookups must run off the Tk main thread or stay within the existing Hotspot Finder worker path without blocking Tk.
- Keep `load.py` minimal: new feature/business logic should be implemented in helper modules/services, with `load.py` limited to orchestration/wiring and thin delegating methods.

## Spansh API Constraints
- Current Hotspot Finder searches bodies through `POST https://spansh.co.uk/api/bodies/search`.
- `/api/bodies/search` does not accept system-level `population` filters.
- Body search results include `system_id64`, which can identify the parent system.
- Population is a system-level field returned by Spansh system detail payloads.
- `GET https://spansh.co.uk/api/system/{id64}` accepts one system id64 at a time and returns the system `population`.
- The reference-system `/api/systems/search/save` warmup path is superseded for this feature because it can cache many systems that are unrelated to the current body result page and can restart/background-crawl more than needed.
- No public Spansh API rate limit has been found in the official docs or response headers.
- Because the rate limit is undocumented, individual system detail lookups must be deduped, cache-first, throttled, ordered by Distance, and capped per user search action. Initial cap: 50 live system detail lookups.

## Proposed Population Predicate Mapping

| UI Option | API Meaning | Notes |
| --- | --- | --- |
| `Any` | no population filter | Default behavior, no extra constraint. |
| `None` | `population == 0` | Explicit zero-population systems only. |
| `Above 1` | `population >= 1` | Includes any populated system. |
| `Above 10,000` | `population >= 10000` | INARA-style preset. |
| `Above 100,000` | `population >= 100000` | INARA-style preset. |
| `Above 1,000,000` | `population >= 1000000` | INARA-style preset. |
| `Above 1,000,000,000` | `population >= 1000000000` | INARA-style preset. |
| `Below 10,000` | `population <= 10000` | Inclusive so `0` remains possible. |
| `Below 100,000` | `population <= 100000` | Inclusive so `0` remains possible. |
| `Below 1,000,000` | `population <= 1000000` | Inclusive so `0` remains possible. |
| `Below 1,000,000,000` | `population <= 1000000000` | Inclusive so `0` remains possible. |

## Vendored Paths Guardrail (Required)
- `tests/harness.py` is vendored and immutable by default.
- Everything under `tests/edmc/` is vendored and immutable by default.
- This plan does not require changes in either vendored path.

## Testing Strategy (Required Before Implementation)

| Change Area | Behavior / Invariant | Test Type (Unit/Harness) | Why This Level | Test File(s) | Command |
| --- | --- | --- | --- | --- | --- |
| Population option mapping | UI options map to the correct comparison/value payloads, including inclusive `<=` below filters | Unit | Pure deterministic mapping | `tests/test_spansh_hotspots.py` or `tests/test_hotspot_population_filter.py` | `source .venv/bin/activate && python -m pytest -q tests/test_spansh_hotspots.py` |
| Body search payload construction | Population filter is not sent to `/api/bodies/search`; population filtering is applied locally from cached and bounded per-system detail values | Unit | Pure client payload behavior with mocked HTTP | `tests/test_spansh_hotspots.py` | `source .venv/bin/activate && python -m pytest -q tests/test_spansh_hotspots.py` |
| Bounded system detail lookup | Missing cached populations are fetched through `GET /api/system/{id64}` with distance ordering, dedupe, throttle, persistent cache writes, and a per-search live lookup cap of 50 for non-`Any` filters only | Unit | Pure client/service behavior with mocked HTTP and clock/session injection | `tests/test_spansh_population_lookup.py` or `tests/test_spansh_hotspots.py` | `source .venv/bin/activate && python -m pytest -q tests/test_spansh_population_lookup.py tests/test_spansh_hotspots.py` |
| Hotspot Finder UI state | Population selection is collected and passed into search options | Unit or Harness | Prefer unit if the window can be constructed with mocks; harness if EDMC/Tk lifecycle wiring is required | `tests/test_hotspot_search_window.py` or harness-specific test | `source .venv/bin/activate && python -m pytest -q tests/test_hotspot_search_window.py` |
| Search result Population column | Results render known population values and handle unknown population without extra uncapped lookups | Unit or Harness | Prefer unit if result rendering can be tested with mocked data; harness only if Tk lifecycle wiring requires it | `tests/test_hotspot_search_window.py` or TBD | `source .venv/bin/activate && python -m pytest -q tests/test_hotspot_search_window.py` |
| Persistent population cache | Cache survives service recreation, expires entries after one month, and ignores corrupt/unreadable cache files safely | Unit | File-backed cache can be tested with temp directories and an injected clock | `tests/test_spansh_population_lookup.py` | `source .venv/bin/activate && python -m pytest -q tests/test_spansh_population_lookup.py` |
| System detail population lookup | Cached values are reused, live lookup cap is enforced, and missing systems beyond the cap remain unknown without extra live requests | Unit | Pure service behavior with mocked clock/client | `tests/test_spansh_population_lookup.py` | `source .venv/bin/activate && python -m pytest -q tests/test_spansh_population_lookup.py` |
| Plugin lifecycle baseline | Hotspot Finder changes do not regress plugin startup/shutdown | Harness | Required only if implementation changes lifecycle wiring or `load.py` orchestration | `tests/test_harness_smoke.py` | `source .venv/bin/activate && python -m pytest -q tests/test_harness_smoke.py` |

## Test Scope Decision (Required)
- Unit-only? Why: Acceptable if the implementation only changes pure mapping, Spansh client payload construction, and Hotspot Finder window code tested with mocks.
- Harness required? Why: Required if implementation touches `load.py`, plugin lifecycle wiring, or EDMC hook flow.
- Mixed (Unit + Harness)? Why: Required if a network population service is wired into plugin lifecycle state or startup/shutdown behavior.
- Phase 8 decision: unit tests are required and sufficient because the rollback/rework is contained to Spansh integration helpers/client behavior with injected sessions/workers; no `load.py`, plugin lifecycle hooks, startup/shutdown wiring, or EDMC hook flow should be touched. Harness tests become required only if implementation changes those lifecycle touch points.

## Test Acceptance Gates (Required)
- [x] Unit tests added/updated for pure logic changes.
- [x] Harness tests added/updated for lifecycle/wiring changes, if any.
- [x] Exact commands listed and executed.
- [x] Any skips documented with reasons.

## Out Of Scope (This Change)
- Reworking the full Hotspot Finder search model beyond population filtering.
- Adding arbitrary custom population ranges unless explicitly requested later.
- Unbounded automatic system detail lookups outside the current body result page.
- Reference-system `/api/systems/search/save` warmup/background pagination for this population flow.
- Editing `tests/harness.py` or `tests/edmc/**`.

## Current Touch Points
- Code:
- `edmc_mining_analytics/mining_ui/hotspot_search_window.py` (Population control and selected option plumbing)
- `edmc_mining_analytics/mining_ui/hotspot_search_window.py` (Population result column rendering)
- `edmc_mining_analytics/integrations/spansh_hotspots.py` (Population payload mapping and bounded system detail lookup boundary)
- `edmc_mining_analytics/integrations/spansh_population.py` (persistent cache and bounded per-system detail population lookup service)
- `edmc_mining_analytics/state.py` (last selected Population filter)
- `edmc_mining_analytics/preferences.py` (persist last selected Population filter)
- Tests:
- `tests/test_spansh_hotspots.py`
- Possible new `tests/test_hotspot_population_filter.py`
- Possible new `tests/test_spansh_population_lookup.py` for per-system detail lookup/cache behavior
- `tests/test_preferences.py`
- Docs/notes:
- `docs/plans/hotspot-population-filter.md`

## Assumptions
- The default Population selection is `Any`.
- User-facing labels should mirror INARA-style wording unless a more compact EDMC UI label is needed.
- The existing Hotspot Finder UI has a Min Hotspots filter that should remain above the new Population filter.

## Risks
- Risk: Population is system-level while Hotspot Finder searches bodies.
- Mitigation: Use body result `system_id64` values to read cached populations first, then perform distance-ordered, deduped, throttled, capped system detail lookups only for missing systems in the current result page when a non-`Any` Population filter is selected.
- Risk: Per-result system lookups could overload Spansh or make the UI slow.
- Mitigation: Normal Hotspot Finder population flow may call `GET /api/system/{id64}` only for cache misses when a non-`Any` Population filter is selected, ordered by Distance, deduped, and capped to 50 live lookups per user search action. Missing values beyond the cap remain blank.
- Risk: Persistent cache file corruption could break population filtering after restart.
- Mitigation: Load defensively, log debug details, and fall back to an empty cache if the cache file is unreadable.
- Risk: Cached population data may become stale.
- Mitigation: Expire entries after one month and refresh through the same bounded per-system detail lookup path.
- Risk: Inclusive `Below` semantics differ from user expectations if "below" is read as strictly less than.
- Mitigation: Lock the product requirement that "Below" means `<=` because zero population must remain selectable.
- Risk: UI becomes crowded.
- Mitigation: Use a single dropdown/combobox modeled after INARA's compact population filter and add only one compact Population result column.
- Risk: Population control placement interrupts existing search flow.
- Mitigation: Place Population directly below Min Hotspots so related result-count/filter controls remain grouped.

## Open Questions
- None currently.

## Decisions (Locked)
- Population filter will use INARA-style presets.
- `Any` means no population filter.
- `Any` uses cache-only population values for display and must not trigger live population lookups.
- `None` means exactly zero population.
- Low-population filters must include zero-population systems by using inclusive `<=` comparisons.
- INARA-style `Below ...` labels will be kept even though the comparison is inclusive.
- Hotspot Finder search results will include a Population column.
- Unknown/unresolved Population result values will display as blank.
- The Population filter control will be placed below the existing Min Hotspots filter.
- The implementation must avoid unbounded per-body system API calls.
- `/api/bodies/search` does not accept population filters, so local cache plus bounded per-system detail lookup is required.
- Reference-system system-search warmup is superseded by Phase 8 and must be removed from the normal Hotspot Finder population flow.
- Do not call `/api/systems/search/save` or `/api/systems/search/recall/...` in the normal Hotspot Finder population flow.
- Population lookup must use body result `system_id64` values.
- Cache returned `GET /api/system/{id64}` population values persistently across EDMC restarts.
- Live per-system detail lookups must be cache-first, ordered by Distance, deduped, throttled, and capped at 50 live lookups per user search action.
- Live per-system detail lookups are only triggered by non-`Any` Population filters.
- Failed/malformed system detail lookups are cached as unknown. Zero population is cached normally.
- Lookup cap is `50`.
- Live lookup order is by body result Distance, nearest first.
- `Any` does not trigger live population lookups.
- Failed live lookups are cached as unknown.
- Population `0` is cached normally.
- Body results missing a fresh cached population after the live lookup cap is reached display blank and do not trigger more live requests.
- Unknown population rows remain visible even when a Population filter is selected.
- System population cache TTL is one month.
- The persistent system population cache will live in a plugin-owned cache/data path, not EDMC config.

## Phase Overview

| Phase | Description | Status |
| --- | --- | --- |
| 1 | Record Spansh payload contract | Completed |
| 2 | Implement population option model and request mapping | Completed |
| 3 | Wire Population control and result column into Hotspot Finder UI | Completed |
| 4 | Add persistent bounded per-ID fallback lookup path (superseded by Phase 6 for normal flow) | Completed |
| 5 | Validate, document results, and decide follow-ups | Completed |
| 6 | Replace per-ID lookup with reference-system system-search warmup | Completed |
| 7 | Avoid restarting population background pagination on result page navigation | Completed |
| 8 | Restore bounded per-system detail lookup and remove system-search warmup | Completed |

## Phase Details

### Phase 1: Record Spansh Payload Contract
- Record that body search does not accept system-level `population` filters and lock the fallback path.
- Risks: fallback design accidentally grows into unbounded live lookups.
- Mitigations: require persistent cache, dedupe, throttle, and a per-search live lookup cap.

| Stage | Description | Status |
| --- | --- | --- |
| 1.1 | Record `/api/bodies/search` population limitation | Completed |
| 1.2 | Lock fallback lookup requirements | Completed |
| 1.3 | Record fallback observability requirements | Completed |

#### Stage 1.1 Detailed Plan
- Objective:
- Record the known Spansh body-search limitation.
- Primary touch points:
- `docs/plans/hotspot-population-filter.md`
- Steps:
- Document that `/api/bodies/search` does not accept population filters.
- Document that population is system-level and requires lookup by `system_id64`.
- Acceptance criteria:
- The plan no longer treats server-side population filtering as an open question.
- Verification to run:
- Review this plan file.

#### Stage 1.2 Detailed Plan
- Objective:
- Lock request-volume safeguards for fallback lookups.
- Steps:
- Require deduplication of `system_id64` values.
- Require persistent cache lookup before live requests.
- Set live lookup cap to 50 per user-triggered search.
- Acceptance criteria:
- Fallback lookup path cannot issue unbounded live system requests.
- Verification to run:
- Review this plan file.

#### Stage 1.3 Detailed Plan
- Objective:
- Make capped fallback behavior observable and user-safe.
- Steps:
- Record that unresolved population values remain blank when the live lookup cap is reached.
- Require debug logging for cache hits, cache misses, expired entries, cap decisions, and skipped unknowns.
- Acceptance criteria:
- Later implementation stages have no ambiguity about capped fallback behavior.
- Verification to run:
- Review updated plan.

#### Phase 1 Execution Order
- Implement in strict order: `1.1` -> `1.2` -> `1.3`.

#### Phase 1 Exit Criteria
- Spansh body-search population limitation is recorded.
- The required persistent, capped fallback path is locked.

### Phase 2: Population Option Model and Request Mapping
- Add a small, testable model for Population options and payload predicates.
- Risks: comparison operators or values are mapped incorrectly.
- Mitigations: unit tests for every preset.

| Stage | Description | Status |
| --- | --- | --- |
| 2.1 | Define population option constants and labels | Completed |
| 2.2 | Map options to Spansh filter predicates | Completed |
| 2.3 | Add unit coverage for every option | Completed |

#### Stage 2.1 Detailed Plan
- Objective:
- Centralize INARA-style population presets.
- Primary touch points:
- `edmc_mining_analytics/integrations/spansh_hotspots.py` or a focused helper module
- Steps:
- Define stable option identifiers.
- Define user-facing labels.
- Acceptance criteria:
- UI labels are available without duplicating mapping logic.
- Verification to run:
- `source .venv/bin/activate && python -m pytest -q tests/test_spansh_hotspots.py`

#### Stage 2.2 Detailed Plan
- Objective:
- Convert selected option into an API filter or no filter.
- Steps:
- `Any` returns no filter.
- `None` returns exact zero population.
- `Above` options return inclusive lower-bound filters.
- `Below` options return inclusive upper-bound filters.
- Acceptance criteria:
- All mappings match the Proposed Population Predicate Mapping table.
- Verification to run:
- `source .venv/bin/activate && python -m pytest -q tests/test_spansh_hotspots.py`

#### Stage 2.3 Detailed Plan
- Objective:
- Anchor behavior before UI wiring.
- Steps:
- Add table-driven unit tests for each population option.
- Acceptance criteria:
- Tests fail on exclusive below filters or omitted zero handling.
- Verification to run:
- `source .venv/bin/activate && python -m pytest -q tests/test_spansh_hotspots.py`

#### Phase 2 Execution Order
- Implement in strict order: `2.1` -> `2.2` -> `2.3`.

#### Phase 2 Exit Criteria
- Population filter mapping is fully unit-tested.

### Phase 3: Hotspot Finder UI Wiring
- Add the Population dropdown, pass selection into search execution, and display population in search results.
- Risks: UI crowding or Tk-thread regressions.
- Mitigations: single compact control; no network work on UI thread beyond existing search behavior.

| Stage | Description | Status |
| --- | --- | --- |
| 3.1 | Add Population dropdown to Hotspot Finder search box | Completed |
| 3.2 | Include selected population option in search options | Completed |
| 3.3 | Add Population column to Hotspot Finder search results | Completed |
| 3.4 | Test UI plumbing with mocks where practical | Completed |

#### Stage 3.1 Detailed Plan
- Objective:
- Add a compact Population control modeled after INARA's dropdown.
- Primary touch points:
- `edmc_mining_analytics/mining_ui/hotspot_search_window.py`
- Steps:
- Add label/control below the existing Min Hotspots filter.
- Preserve the existing Min Hotspots layout and behavior.
- Default to `Any`.
- Acceptance criteria:
- Existing search fields remain usable.
- Population appears below Min Hotspots.
- Verification to run:
- Targeted unit/UI test or manual EDMC smoke if automated Tk coverage is unavailable.

#### Stage 3.2 Detailed Plan
- Objective:
- Pass selected option through to Spansh client search parameters.
- Steps:
- Extend the search request object/options with population selection.
- Preserve behavior when `Any` is selected.
- Acceptance criteria:
- Existing searches produce the same payload when Population is `Any`.
- Verification to run:
- `source .venv/bin/activate && python -m pytest -q tests/test_spansh_hotspots.py`

#### Stage 3.3 Detailed Plan
- Objective:
- Display known parent system population in Hotspot Finder search results.
- Primary touch points:
- `edmc_mining_analytics/mining_ui/hotspot_search_window.py`
- Steps:
- Add a compact Population column to the results table/list.
- Render known population values consistently with existing numeric display style.
- Render unknown population without triggering extra uncapped live lookups.
- Acceptance criteria:
- Search results include Population.
- Unknown population has a stable display state.
- Verification to run:
- `source .venv/bin/activate && python -m pytest -q tests/test_hotspot_search_window.py`

#### Stage 3.4 Detailed Plan
- Objective:
- Validate UI-to-client wiring.
- Steps:
- Add or update tests with mocked client/search options.
- Add or update tests for result population rendering where practical.
- Acceptance criteria:
- Selected Population option reaches the client exactly once per search.
- Known and unknown population values render as expected.
- Verification to run:
- `source .venv/bin/activate && python -m pytest -q tests/test_hotspot_search_window.py`

#### Phase 3 Execution Order
- Implement in strict order: `3.1` -> `3.2` -> `3.3` -> `3.4`.

#### Phase 3 Exit Criteria
- Hotspot Finder exposes Population, displays Population in results, and preserves default search behavior.

### Phase 4: Persistent Bounded Per-ID Fallback Lookup Path (Superseded)
- Implement the required bounded fallback because `/api/bodies/search` does not accept population filters.
- This phase describes the initial implementation. Phase 6 temporarily superseded normal Hotspot Finder use of per-ID system lookups with a reference-system system-search warmup; Phase 8 restores bounded per-system detail lookups as the active target.
- Risks: request flood, cache corruption, and stale population data.
- Mitigations: persistent one-month cache, defensive loading, dedupe, throttle, cap, and log fallback behavior.

| Stage | Description | Status |
| --- | --- | --- |
| 4.1 | Add persistent one-month population cache | Completed |
| 4.2 | Add cached population lookup service | Completed |
| 4.3 | Apply dedupe/throttle/hard-cap policy | Completed |
| 4.4 | Add fallback tests and debug logging | Completed |

#### Stage 4.1 Detailed Plan
- Objective:
- Add a file-backed system population cache that survives EDMC restarts.
- Primary touch points:
- Possible new `edmc_mining_analytics/integrations/spansh_population.py` or focused cache helper module
- Steps:
- Store entries by `system_id64`.
- Store population and cache timestamp for each entry.
- Load cache at service creation.
- Treat entries older than one month as expired.
- Write updates with atomic file replacement where practical.
- Handle missing, corrupt, or unreadable cache files without crashing search.
- Acceptance criteria:
- Cache values survive service recreation in tests.
- Expired entries are ignored.
- Corrupt cache files fall back to an empty cache with debug logging.
- Verification to run:
- `source .venv/bin/activate && python -m pytest -q tests/test_spansh_population_lookup.py`

#### Stage 4.2 Detailed Plan
- Objective:
- Isolate system population lookups behind a small service.
- Primary touch points:
- Possible new `edmc_mining_analytics/integrations/spansh_population.py`
- Steps:
- Check the persistent cache before live lookup.
- Save successful live lookup results into the persistent cache.
- Return known population or unknown without raising into UI paths.
- Acceptance criteria:
- Repeat systems do not trigger repeat live requests across service recreation when cache entries are fresh.
- Verification to run:
- `source .venv/bin/activate && python -m pytest -q tests/test_spansh_population_lookup.py`

#### Stage 4.3 Detailed Plan
- Objective:
- Prevent request floods.
- Steps:
- Deduplicate `system_id64` values from body results.
- Apply a minimum interval between live system requests.
- Apply a per-search hard cap.
- Prefer cached values before consuming the per-search live lookup budget.
- Acceptance criteria:
- A large body result set cannot generate unbounded system requests.
- Verification to run:
- `source .venv/bin/activate && python -m pytest -q tests/test_spansh_population_lookup.py`

#### Stage 4.4 Detailed Plan
- Objective:
- Make fallback behavior observable.
- Steps:
- Log deduped ids, persistent cache hits/misses/expired entries, cap decisions, and skipped unknowns at debug level.
- Acceptance criteria:
- Debug logs explain why fallback included or excluded systems.
- Verification to run:
- `source .venv/bin/activate && python -m pytest -q tests/test_spansh_population_lookup.py`

#### Phase 4 Execution Order
- Implement in strict order: `4.1` -> `4.2` -> `4.3` -> `4.4`.

#### Phase 4 Exit Criteria
- Fallback uses a persistent one-month cache, is bounded, and is tested.

### Phase 5: Validation and Documentation
- Validate behavior and document implementation results.
- Risks: feature works in tests but not in live EDMC UI.
- Mitigations: targeted tests plus manual smoke where Tk automation is limited.

| Stage | Description | Status |
| --- | --- | --- |
| 5.1 | Run targeted unit tests | Completed |
| 5.2 | Run harness tests if lifecycle wiring changed | Completed |
| 5.3 | Record implementation results and remaining risks | Completed |

#### Stage 5.1 Detailed Plan
- Objective:
- Confirm pure behavior.
- Steps:
- Run Spansh client and population mapping tests.
- Acceptance criteria:
- Targeted unit tests pass.
- Verification to run:
- `source .venv/bin/activate && python -m pytest -q tests/test_spansh_hotspots.py`

#### Stage 5.2 Detailed Plan
- Objective:
- Confirm plugin lifecycle safety if needed.
- Steps:
- Run harness smoke only if lifecycle or `load.py` changed.
- Acceptance criteria:
- Harness tests pass or are explicitly skipped as unnecessary.
- Verification to run:
- `source .venv/bin/activate && python -m pytest -q tests/test_harness_smoke.py`

#### Stage 5.3 Detailed Plan
- Objective:
- Close the plan with evidence.
- Steps:
- Update `Implementation Results`.
- List tests run and outcomes.
- Record any fallback or Spansh contract decisions.
- Acceptance criteria:
- The plan can be used as release/change evidence.
- Verification to run:
- Review final plan.

#### Phase 5 Execution Order
- Implement in strict order: `5.1` -> `5.2` -> `5.3`.

#### Phase 5 Exit Criteria
- Tests and results are documented.
- Open questions are either resolved or carried forward explicitly.

### Phase 6: Reference-System System-Search Warmup Revision
- Revise the completed implementation so population values are cached from reference-system system-search results, rather than from individual per-system detail lookups.
- Use `size: 100` for system-search pages.
- Fetch page 0 before/applicable to the body search cache lookup, then continue remaining pages in a background worker thread.
- Risks: background pagination may overlap with a newer search; malformed payload encoding can cause Spansh to ignore `size`, reference-system, distance, and bodies filters.
- Mitigations: treat missing cache entries as blank/unknown without further live requests; cancel or supersede older pagination when a newer reference-system search starts; never update Tk widgets from the background worker.

| Stage | Description | Status |
| --- | --- | --- |
| 6.1 | Confirm system-search request contract from local evidence or user-approved narrow request | Completed |
| 6.2 | Add system-search page service that caches `results[].id64 -> results[].population` with `size: 100` | Completed |
| 6.3 | Add background pagination worker with cancellation/supersession | Completed |
| 6.4 | Wire page 0 before reference-system body search and remove normal per-ID lookups | Completed |
| 6.5 | Update filtering/rendering/background tests for warmup cache hits and blank misses | Completed |
| 6.6 | Run targeted and broader test commands; record results | Completed |

#### Stage 6.1 Detailed Plan
- Objective:
- Lock the exact Spansh system-search request used for population warmup.
- Primary touch points:
- `docs/plans/hotspot-population-filter.md`
- `edmc_mining_analytics/integrations/spansh_population.py`
- Steps:
- Confirm endpoint path.
- Confirm payload encoding.
- Confirm warmup `size`, `page`, and distance range policy.
- Endpoint path is decided as `/api/systems/search/save`.
- Payload encoding is decided as a normal JSON object body. The previously observed serialized-key shape caused Spansh to ignore the search fields.
- Distance range is decided as the Hotspot Finder UI distance settings.
- Page size is decided as `100`.
- Additional pages are decided to run in a background worker thread.
- Unknown population rows are decided to remain visible.
- Acceptance criteria:
- The implementation can make page 0 before cache lookup and schedule remaining pages in a background worker without blocking Tk.
- Verification to run:
- Review this plan file, and only do a live request if the user approves it.

#### Stage 6.2 Detailed Plan
- Objective:
- Cache populations returned by one system-search page.
- Primary touch points:
- `edmc_mining_analytics/integrations/spansh_population.py`
- `tests/test_spansh_population_lookup.py`
- Steps:
- Build normal JSON system-search requests with `size: 100` and caller-specified `page`.
- Parse system-search responses with top-level `results`, `count`, and returned `search.page`/`search.size` when available.
- Store each result with `id64` and `population` into the existing persistent one-month cache.
- Ignore result rows without usable `id64` or numeric population.
- Acceptance criteria:
- A mocked system-search page response populates the persistent cache with all usable returned populations and exposes enough paging metadata for the background worker.
- Verification to run:
- `.venv/bin/python -m pytest -q tests/test_spansh_population_lookup.py`

#### Stage 6.3 Detailed Plan
- Objective:
- Fetch remaining system-search pages in the background.
- Primary touch points:
- `edmc_mining_analytics/integrations/spansh_population.py`
- `tests/test_spansh_population_lookup.py`
- Steps:
- Add a worker/thread boundary for pages after page 0.
- Ensure the worker updates only the persistent cache and debug logs.
- Add cancellation or supersession so newer reference-system searches stop older pagination from continuing.
- Handle Spansh errors defensively without crashing the UI.
- Acceptance criteria:
- Tests prove additional pages are fetched in order, cache is updated, and stale workers stop when superseded.
- Verification to run:
- `.venv/bin/python -m pytest -q tests/test_spansh_population_lookup.py`

#### Stage 6.4 Detailed Plan
- Objective:
- Use the warmup cache for Hotspot Finder body results.
- Primary touch points:
- `edmc_mining_analytics/integrations/spansh_hotspots.py`
- `tests/test_spansh_hotspots.py`
- Steps:
- Fetch/cache page 0 before the body search population cache lookup when the search has a reference system.
- Schedule remaining pages in the background worker.
- Use fresh cached population values keyed by body result `system_id64`.
- Remove or disable normal per-ID `GET /api/system/{id64}` calls in this flow.
- Leave unknown/missing values blank.
- Acceptance criteria:
- A mocked hotspot search performs the page 0 system-search warmup, schedules background pagination when applicable, and performs no per-ID system detail requests.
- Verification to run:
- `.venv/bin/python -m pytest -q tests/test_spansh_hotspots.py`

#### Stage 6.5 Detailed Plan
- Objective:
- Preserve UI behavior while changing the population source.
- Primary touch points:
- `tests/test_hotspot_population_filter.py`
- `tests/test_preferences.py`
- Steps:
- Verify known warmup/cache populations render in the Population column.
- Verify missing cache populations render blank.
- Verify selected population filters include/exclude only known values and do not force extra live requests.
- Verify unknown population rows remain visible even when a Population filter is selected.
- Acceptance criteria:
- UI/state tests pass without relying on per-ID lookup behavior.
- Verification to run:
- `.venv/bin/python -m pytest -q tests/test_hotspot_population_filter.py tests/test_preferences.py`

#### Stage 6.6 Detailed Plan
- Objective:
- Close the requirements revision with evidence.
- Steps:
- Run targeted population/hotspot tests.
- Run the broader relevant suite.
- Record implementation results and test outcomes in this plan.
- Acceptance criteria:
- Revised behavior is documented and tests pass or skips are explained.
- Verification to run:
- `.venv/bin/python -m pytest -q tests/test_hotspot_*.py tests/test_spansh_*.py tests/test_preferences.py`
- `.venv/bin/python -m pytest -q`

#### Phase 6 Execution Order
- Implement in strict order: `6.1` -> `6.2` -> `6.3` -> `6.4` -> `6.5` -> `6.6`.

#### Phase 6 Exit Criteria
- Hotspot Finder population values come from the reference-system system-search warmup cache.
- Normal population flow does not issue individual per-system detail lookups.
- System-search page size is `100`.
- Additional system-search pages run in a background worker and are cancelable or superseded by newer searches.
- Missing population values remain blank.
- Updated tests and results are documented.

### Phase 7: Reuse Population Warmup Across Result Page Navigation
- Prevent Hotspot Finder Next/Previous actions from restarting the reference-system population warmup/background pagination when the reference-system and distance query have not changed.
- Test type decision: unit tests are required and sufficient because this is contained to `SpanshHotspotClient` behavior with injected population lookup/session dependencies. No `load.py`, plugin lifecycle, or Tk hook flow is touched, so harness tests are not required.

| Stage | Description | Status |
| --- | --- | --- |
| 7.1 | Track the active reference-system population warmup key in the hotspot client | Completed |
| 7.2 | Reuse the active warmup/cache path for Next/Previous page navigation | Completed |
| 7.3 | Restart warmup/background pagination when the reference-system query changes | Completed |
| 7.4 | Add tests and record verification | Completed |

#### Phase 7 Exit Criteria
- Repeated Hotspot Finder searches for the same reference-system/distance query still read cached population values for the current body result page.
- Repeated Hotspot Finder searches for the same reference-system/distance query do not call `/api/systems/search/save` again and do not restart background pagination.
- A changed reference-system query starts a new warmup/background pagination flow.

### Phase 8: Restore Bounded Per-System Detail Lookup
- Supersede Phase 6 and Phase 7 for the normal Hotspot Finder population flow.
- Restore cache-first individual system detail lookup by body result `system_id64`.
- Remove `/api/systems/search/save` and `/api/systems/search/recall/...` from the normal Hotspot Finder population flow.
- Preserve the persistent one-month cache, Population UI filter, Population result column, and blank unknown behavior.
- Test type decision: unit tests are required and sufficient because the change is contained to Spansh integration helpers/client behavior with injected sessions/clocks/workers. Harness tests are required only if implementation touches `load.py`, plugin lifecycle, or EDMC hook flow.

| Stage | Description | Status |
| --- | --- | --- |
| 8.1 | Update population lookup service to provide cache-first bounded `GET /api/system/{id64}` lookup | Completed |
| 8.2 | Remove normal-flow `/api/systems/search/save` warmup and recall/background pagination wiring | Completed |
| 8.3 | Wire Hotspot Finder body results to bounded cache-first lookup by returned `system_id64` values | Completed |
| 8.4 | Update filtering/rendering behavior so known populations filter normally and unknown values remain blank/visible | Completed |
| 8.5 | Replace system-search tests with per-system detail lookup cap/cache/no-flood tests | Completed |
| 8.6 | Run targeted and broader test commands; record results | Completed |

#### Stage 8.1 Detailed Plan
- Objective:
- Reintroduce bounded per-system detail lookup behind the existing population lookup service.
- Primary touch points:
- `edmc_mining_analytics/integrations/spansh_population.py`
- `tests/test_spansh_population_lookup.py`
- Steps:
- Add or restore a method that accepts ordered `system_id64` values and returns cached plus newly fetched populations.
- Read the persistent cache first.
- Deduplicate system ids while preserving first-seen order.
- For cache misses, call `GET https://spansh.co.uk/api/system/{id64}` up to a cap of 50 live lookups per user search action when a non-`Any` Population filter is selected.
- Order live lookup candidates by body result Distance, nearest first.
- Parse the returned `population` and persist it to the cache.
- Respect existing throttling/minimum interval behavior for live calls.
- Cache failed/malformed live responses as unknown.
- Cache zero population values normally.
- Leave misses beyond the cap unresolved/blank.
- Acceptance criteria:
- Tests prove `Any` is cache-only, cache hits avoid live requests, duplicate ids are not fetched twice, candidates are fetched in Distance order, the cap is enforced at 50, successful live responses populate cache, zero values are cached normally, and failed/malformed responses are cached as unknown without crashing search.
- Verification to run:
- `.venv/bin/python -m pytest -q tests/test_spansh_population_lookup.py`

#### Stage 8.2 Detailed Plan
- Objective:
- Remove reference-system system-search warmup from normal Hotspot Finder population flow.
- Primary touch points:
- `edmc_mining_analytics/integrations/spansh_hotspots.py`
- `edmc_mining_analytics/integrations/spansh_population.py`
- `tests/test_spansh_hotspots.py`
- Steps:
- Remove calls to `warm_reference_system_page`.
- Remove calls to `start_background_pagination`.
- Remove or leave unused-only system-search helpers only if needed for compatibility; prefer deleting dead code and tests for the normal flow.
- Ensure normal Hotspot Finder search never calls `/api/systems/search/save` or `/api/systems/search/recall/...`.
- Acceptance criteria:
- Tests prove no normal Hotspot Finder population search issues system-search save/recall requests.
- Verification to run:
- `.venv/bin/python -m pytest -q tests/test_spansh_hotspots.py tests/test_spansh_population_lookup.py`

#### Stage 8.3 Detailed Plan
- Objective:
- Use body result `system_id64` values as the population lookup input.
- Primary touch points:
- `edmc_mining_analytics/integrations/spansh_hotspots.py`
- `tests/test_spansh_hotspots.py`
- Steps:
- Continue extracting returned body `system_id64` values.
- Call the bounded population lookup service once per Hotspot Finder body search result page.
- Pass enough body result context to order live lookup misses by Distance.
- Pass known populations into filtering and result row construction.
- Keep unknown population values as `None`.
- Acceptance criteria:
- Tests prove body results receive known population values from cache/live lookup and unknown values stay blank.
- Verification to run:
- `.venv/bin/python -m pytest -q tests/test_spansh_hotspots.py`

#### Stage 8.4 Detailed Plan
- Objective:
- Preserve Population filter semantics.
- Primary touch points:
- `edmc_mining_analytics/integrations/spansh_hotspots.py`
- `tests/test_spansh_hotspots.py`
- `tests/test_hotspot_population_filter.py`
- Steps:
- Keep INARA-style option mapping.
- Known non-matching populations should be filtered out.
- Unknown population rows remain visible even when a Population filter is selected.
- Acceptance criteria:
- Existing Population filter/rendering tests pass with the per-system detail lookup source.
- Verification to run:
- `.venv/bin/python -m pytest -q tests/test_spansh_hotspots.py tests/test_hotspot_population_filter.py`

#### Stage 8.5 Detailed Plan
- Objective:
- Replace obsolete Phase 6/7 tests and docs.
- Primary touch points:
- `tests/test_spansh_population_lookup.py`
- `tests/test_spansh_hotspots.py`
- `docs/plans/hotspot-population-filter.md`
- Steps:
- Remove or rewrite tests that assert system-search warmup, recall pagination, or Next/Previous background reuse.
- Add tests for cap behavior, Distance ordering, `Any` cache-only behavior, cache persistence, cache expiry, live response parsing, failed-as-unknown caching, no system-search calls, and blank misses beyond cap.
- Update implementation results and tests run.
- Acceptance criteria:
- Test suite no longer encodes `/api/systems/search/save` as the normal population path.
- Verification to run:
- `.venv/bin/python -m pytest -q tests/test_spansh_population_lookup.py tests/test_spansh_hotspots.py`

#### Stage 8.6 Detailed Plan
- Objective:
- Close the rollback/rework with evidence.
- Steps:
- Run targeted population/hotspot tests.
- Run the broader relevant suite.
- Run the full suite if feasible.
- Record implementation results and test outcomes in this plan.
- Acceptance criteria:
- Revised behavior is documented and tests pass or skips are explained.
- Verification to run:
- `.venv/bin/python -m pytest -q tests/test_spansh_population_lookup.py tests/test_spansh_hotspots.py`
- `.venv/bin/python -m pytest -q tests/test_hotspot_*.py tests/test_spansh_*.py tests/test_preferences.py`
- `.venv/bin/python -m pytest -q`

#### Phase 8 Exit Criteria
- Normal Hotspot Finder population flow uses `GET /api/system/{id64}` for cache misses only.
- Normal Hotspot Finder population flow does not call `/api/systems/search/save` or `/api/systems/search/recall/...`.
- Live lookups are ordered by Distance, deduped, throttled, and capped at 50 per user search action.
- `Any` Population selection does not trigger live population lookups.
- Failed/malformed live responses are cached as unknown; zero population is cached normally.
- Persistent cache remains plugin-owned with a one-month TTL.
- Known populations display/filter correctly; unknown values remain blank and visible.
- Updated tests and results are documented.

## Implementation Results
- Phase 8 completed: normal Hotspot Finder population flow now uses cache-first, bounded `GET /api/system/{id64}` lookups for cache misses when a non-`Any` Population filter is selected.
- Removed normal-flow `/api/systems/search/save`, `/api/systems/search/recall/...`, reference-system warmup reuse, and background system-search pagination wiring from Hotspot Finder population lookup.
- `Any` Population selection is cache-only and does not trigger live population lookups.
- Live lookup candidates are ordered by body result Distance, nearest first, deduped, throttled, and capped at 50 per user search action.
- Successful live detail lookups are written to the persistent plugin-owned cache, including `population: 0`.
- Failed or malformed live detail lookups are cached as unknown, so repeated searches do not immediately retry the same failed systems within the cache TTL.
- Unknown population rows remain visible with a blank Population value, including when a non-`Any` Population filter is selected.
- Replaced obsolete system-search warmup/background pagination tests with per-system detail lookup cache, cap, zero, failed-as-unknown, distance ordering, `Any` cache-only, and no-system-search-call tests.
- Phase 6 completed: normal Hotspot Finder population flow no longer performs individual `GET /api/system/{id64}` lookups for body results.
- Added Spansh system-search page warmup through `/api/systems/search/save` using a normal JSON search object, `size: 100`, caller-specified `page`, Hotspot Finder UI distance settings, and the Planet bodies filter.
- `/api/systems/search/save` returns a `search_reference`; the implementation follows it with `/api/systems/search/recall/{search_reference}/{page}` and caches populations from the recalled `results`.
- Page 0 is fetched and cached before body result population cache lookup.
- Added background pagination for remaining system-search pages. Background workers update only the persistent cache/debug logs and are superseded by newer searches.
- Body results read population from the persistent cache by `system_id64`; missing cache values remain blank and rows remain visible even when a Population filter is selected.
- Replaced per-ID lookup tests with system-search page, background pagination, supersession, cache-only lookup, and no-per-ID-request tests.
- Corrected `/api/systems/search/save` payload encoding to send the normal JSON search object body. The serialized-key payload shape caused Spansh to ignore the requested `size`, `reference_system`, distance, and Planet bodies filters, which produced 25-row default pages with incorrect zero-population cache entries.
- Added active population warmup tracking in `SpanshHotspotClient` so Next/Previous result page navigation reuses the existing reference-system/distance warmup and does not restart background pagination. Changing the reference-system/distance query starts a new warmup.
- Added INARA-style Population filter options and mapping in `edmc_mining_analytics/integrations/spansh_hotspots.py`.
- Added persistent plugin-owned system population cache and bounded lookup service in `edmc_mining_analytics/integrations/spansh_population.py`.
- The population cache file is initialized immediately once a plugin-owned cache path is available, making cache path issues visible before the first successful live population save.
- Added `system_id64` and optional `population` to `RingHotspot`.
- Hotspot searches now use returned `system_id64` values for cache-only population lookup.
- Population lookup cache path is resolved lazily at search time so EDMC startup order does not create a no-cache lookup before `state.plugin_dir` is available.
- Known non-matching populations are filtered out. Unknown/unresolved populations remain visible with a blank Population value.
- Added a Population dropdown below Minimum Hotspots in `HotspotSearchWindow`.
- Added a Population column to Hotspot Finder search results.
- Persisted the selected population filter through `MiningState` and `PreferencesManager`.
- Added `.gitignore` coverage for plugin-owned `cache/` data.
- No `load.py` or EDMC lifecycle wiring changes were required, so harness tests were not added.

## Tests Run
- `.venv/bin/python -m pytest -q tests/test_spansh_hotspots.py` - passed, 7 tests.
- `.venv/bin/python -m pytest -q tests/test_spansh_population_lookup.py` - passed, 10 tests.
- `.venv/bin/python -m pytest -q tests/test_spansh_hotspots.py tests/test_spansh_population_lookup.py` - passed, 17 tests.
- `.venv/bin/python -m pytest -q tests/test_hotspot_population_filter.py tests/test_preferences.py` - passed, 6 tests.
- `.venv/bin/python -m pytest -q tests/test_hotspot_*.py tests/test_spansh_*.py tests/test_preferences.py` - passed, 36 tests.
- `.venv/bin/python -m py_compile edmc_mining_analytics/integrations/spansh_hotspots.py edmc_mining_analytics/integrations/spansh_population.py edmc_mining_analytics/mining_ui/hotspot_search_window.py edmc_mining_analytics/preferences.py edmc_mining_analytics/state.py` - passed.
- `.venv/bin/python -m compileall -q edmc_mining_analytics` - passed.
- `.venv/bin/python -m pytest -q tests/test_spansh_population_lookup.py tests/test_spansh_hotspots.py` - passed, 17 tests after correcting `/api/systems/search/save` payload encoding.
- `.venv/bin/python -m py_compile edmc_mining_analytics/integrations/spansh_population.py edmc_mining_analytics/integrations/spansh_hotspots.py` - passed after correcting `/api/systems/search/save` payload encoding.
- `.venv/bin/python -m pytest -q tests/test_hotspot_*.py tests/test_spansh_*.py tests/test_preferences.py` - passed, 36 tests after correcting `/api/systems/search/save` payload encoding.
- `.venv/bin/python -m pytest -q` - passed, 123 tests, 1 skipped after correcting `/api/systems/search/save` payload encoding.
- `.venv/bin/python -m pytest -q tests/test_spansh_hotspots.py tests/test_spansh_population_lookup.py` - passed, 19 tests after adding warmup reuse for result page navigation.
- `.venv/bin/python -m py_compile edmc_mining_analytics/integrations/spansh_hotspots.py edmc_mining_analytics/integrations/spansh_population.py` - passed after adding warmup reuse for result page navigation.
- `.venv/bin/python -m pytest -q tests/test_hotspot_*.py tests/test_spansh_*.py tests/test_preferences.py` - passed, 38 tests after adding warmup reuse for result page navigation.
- `.venv/bin/python -m pytest -q` - passed, 125 tests, 1 skipped after adding warmup reuse for result page navigation.
- `.venv/bin/python -m pytest -q tests/test_spansh_population_lookup.py tests/test_spansh_hotspots.py` - passed, 18 tests after restoring bounded per-system detail lookups.
- `.venv/bin/python -m py_compile edmc_mining_analytics/integrations/spansh_hotspots.py edmc_mining_analytics/integrations/spansh_population.py` - passed after restoring bounded per-system detail lookups.
- `.venv/bin/python -m pytest -q tests/test_hotspot_*.py tests/test_spansh_*.py tests/test_preferences.py` - passed, 37 tests after restoring bounded per-system detail lookups.
- `.venv/bin/python -m pytest -q` - passed, 124 tests, 1 skipped after restoring bounded per-system detail lookups.
- `.venv/bin/python -m pytest -q` - passed, 123 tests and 1 skipped.
- Harness tests were not separately required because implementation did not touch `load.py`, plugin lifecycle hooks, startup/shutdown wiring, or EDMC hook flow.
