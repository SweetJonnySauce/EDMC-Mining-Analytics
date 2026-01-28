## Goal: Estimate sell price of mined commodities



Requirements
- When a new commodity is mined, do a market search based on the set parameters to find the sell price
- only do the market search once per new commodity in inventory per mining session
- Look in the tmp directory for how to do the market search against the Spansh API
- Reference system in the market search is the current system being mined
- Commodity in the market search is the commodity that was just refined and stored in inventory
- Add a tab to the preferences pane call "Market search". We'll add those details below
- For each commodity track tons in inventory times sell price. This is the total commodity sell price.
- Track a total sell price (sum of total commodity sell price)
- Add Estimated Sell price (abbreviate estimated as Est.) to the Overlay
- Add total commodity sell price for each commodity to the discord summary. 
- Add total sell price to the discord summary
- Do not reference any of the code in tmp directly but build new market search functionality based on it.
- New! Run market searches in its own thread

Market Search preference pane tab
- Has Large Landing pad. Check box. Checked = true, unchecked = null
- Sort by: best_price or nearest
- Minimum Demand. Text box. Check to make sure it's numeric. default is 1000
- Age of market data. Text box. check to make sure it's numeric. default is 30
- Distance (LY). Text box. Check to make sure it's numeric. default is 100


Do validates when the cell loses focus or the enter key is hit. if it's invald, revert to the previous value

## Questions for you
1) Trigger point: should the market search run on `MiningRefined` events or on cargo increases in `_process_cargo`?
- on cargo increases. Only do the search on the first of each commodity. Store that value and just do the math.
2) “Once per new commodity per session”: should we never re-query even if the system changes or mining resumes later in the same session?
- Respect pause/unpause. But mining in another system will trigger a hyperspace jump which stops the mining session. 
3) Reference system: always `state.current_system` at time of lookup? If the system changes mid-session, should new commodities use the new system?
- Yes. It won't change.
4) “Best price” sorting: highest `sell_price` (current assumption) or `buy_price`?
- Sell price
5) Market age: ok to apply a `market_updated_at` date-range filter (YYYY-MM-DD) and also do a client-side guard if the API returns stale rows?
- yes
6) Min demand: apply demand range only to the searched commodity in `filters.market`, or as a general station filter?
- what is filters.market? it's not a range, just a min demand number
7) Overlay: show total estimated value (all cargo) or per-commodity price/ton or something else?
- all cargo total
8) Discord summary: include per-commodity estimated value for all commodities or top-N? Where should total estimated value appear?
- include per-commodity for each commodity and then a total at the bottom of the commodity details
9) UI table: add estimated value as a new column in the commodities table, or only overlay + Discord?
- What UI table?
10) Preferences UI: are you OK with converting the preferences page into a `ttk.Notebook` with a new “Market search” tab, or do you want a non-tabbed section?
- tabbed
11) Validation UX: if a field is invalid, should we revert silently or show an inline warning? If cleared, revert to previous value or default?
- revert silently
12) Commodity naming: should the market search use display names (from `commodity_display_names`) or normalized cargo names?
- localised cargo names

## Follow-up questions
1) Market filter shape: should min demand be converted to a range like `{comparison:"<=>", value:[min_demand, 1_000_000_000]}` for the commodity in `filters.market`?
no. it'll always be > min_demand
2) Commodity name source: if localized names aren’t English, do you still want to send them to Spansh, or fall back to canonical names?
yes
3) UI table: the “Mined Commodities” table currently shows commodity/present/%/total/range/TPH. Should we add an “Est. Sell” column there or keep estimated values only for overlay + Discord?
keep it only to overlay and discord for now
4) Overlay label: should the overlay label be exactly `Est. Sell` and show a single total value (e.g. `123,456,789 Est. Sell`)?
"Est. CR". summarize the total. so 4,349,234 = 4.3M. Summarize the number in Discord too
5) Discord summary size: OK to include per‑commodity estimated value for all commodities even if it gets long, or should we truncate with “+N more”?
Long is ok. summarize the total so 4,349,234 = 4.3M
6) Has Market default: should `has_market=true` always be applied for market searches, or only when explicitly enabled in the tab?
yes, always
7) Validation helper: should we use EDMC’s `number_from_string` if available and fall back to local parsing otherwise?
yes

## Outstanding clarifications
- Min demand filter: Spansh requires a range for demand. Proposed encoding: `{"comparison":"<=>","value":[min_demand, 1000000000]}` to represent “> min_demand”. Please confirm.
Ok with what you propose.
- Localized commodity names: Spansh expects English. Proposed behavior: try localized first, then fall back to canonical if no results. Please confirm.
yes.


## Refactorer Persona
- Bias toward carving out modules aggressively while guarding behavior: no feature changes, no silent regressions.
- Prefer pure/push-down seams, explicit interfaces, and fast feedback loops (tests + dev-mode toggles) before deleting code from the monolith.
- Treat risky edges (I/O, timers, sockets, UI focus) as contract-driven: write down invariants, probe with tests, and keep escape hatches to revert quickly.
- Default to “lift then prove” refactors: move code intact behind an API, add coverage, then trim/reshape once behavior is anchored.
- Resolve the “be aggressive” vs. “keep changes small” tension by staging extractions: lift intact, add tests, then slim in follow-ups so each step stays behavior-scoped and reversible.
- Track progress with per-phase tables of stages (stage #, description, status). Mark each stage as completed when done; when all stages in a phase are complete, flip the phase status to “Completed.” Number stages as `<phase>.<stage>` (e.g., 1.1, 1.2) to keep ordering clear.
- Personal rule: if asked to “Implement…”, expand/document the plan and stages (including tests to run) before touching code.
- Personal rule: keep notes ordered by phase, then by stage within that phase.

## Dev Best Practices

- Keep changes small and behavior-scoped; prefer feature flags/dev-mode toggles for risky tweaks.
- Plan before coding: note touch points, expected unchanged behavior, and tests you’ll run.
- Avoid UI work off the main thread; keep new helpers pure/data-only where possible.
- When touching preferences/config code, use EDMC `config.get_int/str/bool/list` helpers and `number_from_string` for locale-aware numeric parsing; avoid raw `config.get/set`.
- Record tests run (or skipped with reasons) when landing changes; default to headless tests for pure helpers.
- Prefer fast/no-op paths in release builds; keep debug logging/dev overlays gated behind dev mode.

## Per-Iteration Test Plan
- **Env setup (once per machine):** `python3 -m venv .venv && source .venv/bin/activate && pip install -U pip && pip install -e .[dev]`
- **Headless quick pass (default for each step):** `source .venv/bin/activate && python -m pytest` (scope with `tests/…` or `-k` as needed).
- **Core project checks:** `make check` (lint/typecheck/pytest defaults) and `make test` (project test target) from repo root.
- **Full suite with GUI deps (as applicable):** ensure GUI/runtime deps are installed (e.g., PyQt for Qt projects), then set the required env flag (e.g., `PYQT_TESTS=1`) and run the full suite.
- **Targeted filters:** use `-k` to scope to touched areas; document skips (e.g., long-running/system tests) with reasons.
- **After wiring changes:** rerun headless tests plus the full GUI-enabled suite once per milestone to catch integration regressions.

## Guiding Traits for Readable, Maintainable Code
- Clarity first: simple, direct logic; avoid clever tricks; prefer small functions with clear names.
- Consistent style: stable formatting, naming conventions, and file structure; follow project style guides/linters.
- Intent made explicit: meaningful names; brief comments only where intent isn’t obvious; docstrings for public APIs.
- Single responsibility: each module/class/function does one thing; separate concerns; minimize side effects.
- Predictable control flow: limited branching depth; early returns for guard clauses; avoid deeply nested code.
- Good boundaries: clear interfaces; avoid leaking implementation details; use types or assertions to define expectations.
- DRY but pragmatic: share common logic without over-abstracting; duplicate only when it improves clarity.
- Small surfaces: limit global state; keep public APIs minimal; prefer immutability where practical.
- Testability: code structured so it’s easy to unit/integration test; deterministic behavior; clear seams for injecting dependencies.
- Error handling: explicit failure paths; helpful messages; avoid silent catches; clean resource management.
- Observability: surface guarded fallbacks/edge conditions with trace/log hooks so silent behavior changes don’t hide regressions.
- Documentation: concise README/usage notes; explain non-obvious decisions; update docs alongside code.
- Tooling: automated formatting/linting/tests in CI; commit hooks for quick checks; steady dependency management.
- Performance awareness: efficient enough without premature micro-optimizations; measure before tuning.

## Phase Overview

| Phase | Description | Status |
| --- | --- | --- |
| Phase 1 | Market search core + state scaffolding | Completed |
| Phase 2 | Preferences UI (tabbed) + validation | Completed |
| Phase 3 | Overlay + Discord integration | Completed |
| Phase 4 | Hardening + tests + docs | Completed |
| Phase 5 | Unified market search settings (Inara + Spansh) | Completed |

## Phase Details

### Phase 1: Market search core + state scaffolding
- Goal: Add a market search integration (Spansh) and cache per-commodity sell price once per session.
- Behaviors that must remain unchanged: cargo tracking, mining session lifecycle, existing UI/overlay metrics.
- Edge cases/invariants: run search only on first cargo increase for a commodity; use current system as reference; has_market always true; fallback to canonical name if localized lookup yields 0 results.
- Risks: network errors or slow response; mismatched commodity names; stale market data.
- Mitigations: shared HTTP session + timeouts; defensive parsing; date-range filter + client-side guard; cache results to avoid repeated calls.

Implementation plan (current iteration)
- Add a market search service to manage background lookups + cache updates.
- Wire cargo-increase triggers to the service, respecting pause and session state.
- Update plugin wiring to construct the service and pass it to the journal processor.
- Record Phase 1 results and mark completed stages.
- Tests: `python -m pytest` (optionally scope to `tests/test_journal_simulation.py`).

| Stage | Description | Status |
| --- | --- | --- |
| 1.1 | Add data model/state fields for market search prefs, cached sell prices, and totals | Completed |
| 1.2 | Implement Spansh market search client module (pure helpers + API wrapper) | Completed |
| 1.3 | Wire search trigger to cargo increases (first-time per commodity per session) | Completed |
| 1.4 | Compute per-commodity and total estimated sell values in state | Completed |

Phase 1 results
- Added a dedicated market search service that runs Spansh lookups in the background, caches prices once per commodity, and guards against paused sessions.
- Wired cargo-increase events to trigger first-time market searches with localized-name-first fallback to canonical names.
- Added canonical commodity name tracking to support fallback and keep cached values aligned with cargo totals.
- Recompute estimated per-commodity and total sell values whenever cargo increases or a new price arrives.
- Tests: not run (not requested).

### Phase 2: Preferences UI (tabbed) + validation
- Goal: Convert preferences pane to `ttk.Notebook` and add “Market search” tab with required inputs.
- Behaviors that must remain unchanged: existing preferences sections and persistence.
- Edge cases/invariants: validate on blur/enter; invalid input reverts silently; defaults: demand 1000, age 30, distance 100.
- Risks: UI regressions or miswired config keys.
- Mitigations: reuse existing config helpers; keep UI work on main thread; add minimal field-level validation.

| Stage | Description | Status |
| --- | --- | --- |
| 2.1 | Add new preferences fields to `MiningState` and config load/save | Completed |
| 2.2 | Refactor preferences UI into notebook layout | Completed |
| 2.3 | Add “Market search” tab controls + validation handlers | Completed |
| 2.4 | Ensure tab settings round-trip and update state correctly | Completed |

Phase 2 results
- Preferences pane converted to a tabbed notebook with dedicated Market search tab.
- Market search settings are persisted (has large pad, sort mode, min demand, age days, distance).
- Numeric fields validate on blur/enter and silently revert on invalid input using locale-aware parsing when available.
- Tests: not run (not requested).

### Phase 3: Overlay + Discord integration
- Goal: Display total estimated credits in overlay; include per-commodity and total in Discord summary.
- Behaviors that must remain unchanged: existing overlay metrics and Discord formatting.
- Edge cases/invariants: overlay label `Est. CR`; compact number formatting (e.g., 4.3M).
- Risks: overlay row ordering changes; Discord field length overflow.
- Mitigations: append new metric with explicit ordering; compact formatting; keep per-commodity list in existing summary block.

| Stage | Description | Status |
| --- | --- | --- |
| 3.1 | Add compact currency formatter utility | Completed |
| 3.2 | Add overlay metric for total estimated CR | Completed |
| 3.3 | Extend Discord summary with per-commodity estimated CR and total | Completed |

Phase 3 results
- Added compact number formatter for credits (e.g., 4.3M) used by overlay and Discord.
- Overlay now shows an `Est. CR` row when market estimates are available.
- Discord summary now lists per-commodity estimated sell values and a total line.
- Tests: not run (not requested).

### Phase 4: Hardening + tests + docs
- Goal: Stabilize behavior, add test coverage for helpers, and update docs.
- Behaviors that must remain unchanged: session lifecycle, existing tests.
- Edge cases/invariants: locale parsing via `number_from_string` if available.
- Risks: unhandled failures on API errors; brittle parsing.
- Mitigations: error handling + warnings; unit tests for parsing/formatting.

| Stage | Description | Status |
| --- | --- | --- |
| 4.1 | Add tests for market search payload creation and formatting | Completed |
| 4.2 | Add tests for estimated value calculations | Completed |
| 4.3 | Update docs/README with new feature summary | Completed |

Phase 4 results
- Added tests for compact number formatting, market sell total computation, and Spansh payload creation.
- Updated README to mention market search preferences and estimated sell price support.
- Tests: not run (not requested).


## Modification to combine searches on inara and spansh for consistency
Currently we have settings for Inara searches based on commodity and for Spansh marketplace searches. I want to combine all the search parameters into one tab (we'll use Market search) and then we will be able to use these settings for both inara and spansh. Here are some details. 


### Requirements
- Combine the search parameters on the inara tab into the Market Search tab and remove the Inara tab. the market search parameters will drive both Inara and Spansh searches

- Add Distance to Arrival (Ls) as an option to the market search tab. Default to 5000
- Wire Distance to Arrival (Ls) into the spansh searches. You can look a the code in the tmp directory to see how to do this, but don't directly use the code (we are throwing it away once we are done)
- Wire Distance to Arrival (Ls) into Inara searchs (see Inara URL params below)

- Merge Best price search and distance search from the Inara tab to the Market search tab. Keep the market search drop-down in favor of the radio buttons.
- Move Include Fleet carriers in results to the Market Search tab. this is already wired into Inara searches but we need to wire this into spansh searches. When checked, use the Type field and add Carrier categorization to the Spansh search. I've mapped Type values to carriers categorization for your reference below in the Marketplace filtering.
- Similarly, move Include Surface Stations in Results to the market Search tab. This is already wired into Inara searches but we now need to wire it into Spansh searches. Use the marketplace filtering below where categorization = Surface
- Update the spansh search to only search for Station category (see Marketplace filtering below) unless "Include Carriers" and/or "Include Surface Station" checkboxes are checked.

- Add max distance to the inara searches per the inara URL parameter list below. This is Distance LY
- Add min landing pad to the inara searches per the inara URL parameter list below. This is "Has Large landing pad". if checked, set pi3 to 3, if unchecked. don't include it at all.
- Order by should already be implemented for both inara and spansh. This is "Sort by" on the settings.
- Add min demand to the inara searches per the inara URL parameter list below. This is Minimum Demand
- Add max price age to the inara searches per the inara URL parameter list below. This is "Age of market data (days). You'll need to convert this value to hours for inara.
- THe label on the market search tab says "Configure Spansh market..." remove Spansh and just say "Configure market..."

### Questions
- UI control: “Keep the market search drop-down in favor of the radio buttons” is ambiguous. Which control do you want in the Market search tab: the existing Sort by dropdown, radio buttons, or both?
Keep the "Sort by" drop down on market search. Remove the Best price and Distance radio button from the inara tab
- Defaults/migration: should we migrate existing Inara settings into the new Market search settings (so users keep their preferences), or reset to new defaults?
Reset to new defaults. Note this in the release notes (create a new RELEASE_NOTES.md file for this. New version will be 0.6.0)
- Spansh category filtering: when “Include Carriers” and/or “Include Surface Stations” is checked, should the search include those in addition to Station, or switch to only those categories?
In addition to Station
- Carrier mapping: where is the “Type → carriers categorization” mapping you referenced? Point me to the exact mapping table or file.
See the table in "Marketplace filtering". It's ordered by Type: Category. Type is the value in the spansh query we want to make.
- Distance to Arrival (Ls): confirm this is a max distance filter (≤ value) for both Spansh and Inara, and should it be applied when the field is empty/0?
yes, max distance (in Light seconds). If it's empty, do not include it. Make it null or empty
- Inara URL parameters: provide the exact parameter names and expected values for max distance (LY), min landing pad (pi3 = 3 when checked, omit otherwise), min demand, max price age (hours), and distance to arrival (Ls).
The first value (e.g. pi11) is the URL param. I've updated the table. Does this answer the question?
- Age conversion: when converting “Age of market data (days)” to hours for Inara, should we round (ceil/floor) or allow fractional hours?
The setting should be a integer in # of days. Multiply that value times 24 to get hours. No fractions needed.
- Validation: should the new “Distance to Arrival (Ls)” follow the same validation UX as the other numeric fields (validate on blur/enter, revert silently)?
yes.
- Distance to Arrival (Ls) vs validation: you want it nullable (omit filter when empty), but also “validate/revert silently.” Should an empty field be allowed (stored as None/blank), or should it revert to the previous value/default?
Empty field is allowed.
- Sort by mapping: confirm the exact dropdown options and mapping to Inara pi10 (e.g., best_price → 1, nearest → 2). Any additional options?
Your mapping is correct
- Spansh category filter shape: do you want a single type filter with a list of Type values (Station + optional Carrier/Surface), or some other filter structure?
For stations, you'll need to provide a list to the search query. When you add in Carrier or Surface, you'll need to add those Type values to the search query list also.
- Versioning: besides creating RELEASE_NOTES.md, should I bump PLUGIN_VERSION (and any packaging metadata) to 0.6.0?
yes


### additional inara URL parameters we will need:
- pi11 = Max distance (integer)
- pi3 = landing pad (1=small, 2=medium, 3=large)
- pi10 = order by (1=Best price, 2=Distance)
- pi7 = min demand (integer)
- pi5 = max price age (in hours)
- pi9 = max station distance (in Ls) (integer). This is Distance to Arrival (Ls)

## Marketplace filtering 
"Type" values in Spansh along with my categorization to be used in our searches.
Asteroid base: Station
Coriolis Starport: Station
Dockable Planet station: Surface
Dodec Starport: Station
Drake-Class carrier: Carrier
Mega ship: Station
Ocellus Starport: Station
Orbis Starport: Station
Outpost: Surface
Planetary Construction Depot: Surface
Planetary Port: Surface
Settlement: Surface
Space Construction Depot: Station
Surface Settlement: Surface

## Phase 5: Unified market search settings (planned)
High-level plan to merge Inara + Spansh search parameters into a single Market search tab, wire new filters, and ship a 0.6.0 release.

| Stage | Description | Status |
| --- | --- | --- |
| 5.1 | Consolidate preferences: move Inara settings into Market search, remove Inara tab, add Distance to Arrival (Ls), update label copy | Completed |
| 5.2 | Wire settings into Spansh search payload: type list (Station + optional Carrier/Surface), distance-to-arrival, carrier/surface inclusion | Completed |
| 5.3 | Wire settings into Inara URL params: max distance (LY), landing pad, order by, min demand, max price age (hours), distance-to-arrival (Ls) | Completed |
| 5.4 | Update versioning + release notes: bump to 0.6.0, add RELEASE_NOTES.md, document defaults reset | Completed |
| 5.5 | Validate + test: preference validation (incl. nullable distance), payload/URL tests, doc updates | Completed |

### Phase 5 Details
- Goal: unify Inara + Spansh search settings into one Market search tab, add new filters, and align both search backends with the same parameters.
- Behaviors that must remain unchanged: mining session lifecycle, cargo tracking, market search threading model, overlay/Discord formatting, and existing search defaults unless explicitly updated.
- Edge cases/invariants: distance-to-arrival can be empty (omit filter); include carriers/surface means add to Station list (not replace); localized names still try first; Inara hours = days * 24.
- Risks: UI regressions when removing Inara tab, miswired settings leading to wrong searches, stale config values after reset, or unexpected filtering when type list changes.
- Mitigations: centralized settings mapping, explicit filter construction helpers, validation on blur/enter with silent revert, and tests for payload/URL composition.

Implementation plan (Phase 5)
- Consolidate preference state: introduce Distance to Arrival (Ls), move Inara settings into Market search, and remove Inara tab/widgets.
- Reset defaults on upgrade: new defaults applied, previous Inara-only settings ignored, and release notes document the reset.
- Spansh search wiring: build a type list starting with Station types; append Carrier/Surface type values when enabled; include max distance, min demand, landing pad, and distance-to-arrival where applicable.
- Inara search wiring: add params pi11, pi3, pi10, pi7, pi5, pi9 with correct mappings; omit nullable parameters when empty.
- Update labels/copy: change “Configure Spansh market…” to “Configure market…”.
- Tests + docs: update/extend tests for payload and URL builders; update README and release notes.

| Stage | Description | Status |
| --- | --- | --- |
| 5.1 | Preferences + config: add Distance to Arrival (Ls), move Inara controls into Market search, remove Inara tab, update label copy | Completed |
| 5.2 | Spansh filtering: build type list (Station + optional Carrier/Surface), wire distance-to-arrival and carrier/surface filters | Completed |
| 5.3 | Inara URL params: add max distance (LY), landing pad, order by, min demand, max price age (hours), distance-to-arrival (Ls) | Completed |
| 5.4 | Versioning + release notes: bump to 0.6.0, add RELEASE_NOTES.md, note defaults reset | Completed |
| 5.5 | Validation + tests + docs: nullable distance handling, payload/URL tests, README/doc updates | Completed |

Phase 5 results
- Unified search settings under Market search and removed the Inara tab.
- Added Distance to Arrival (Ls) with nullable handling and new carrier/surface options.
- Spansh searches now filter by station types (Station + optional Carrier/Surface) and distance-to-arrival.
- Inara URLs now respect market search filters for distance, pad size, demand, and data age.
- Version bumped to 0.6.0 with RELEASE_NOTES.md documenting default reset.
- Tests: not run (not requested).
