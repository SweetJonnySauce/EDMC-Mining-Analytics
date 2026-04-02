# Web Index Modularization Plan

## Phase 1: Asset Decomposition
| Stage | Description | Status |
|---|---|---|
| 1.1 | Extract inline CSS from `web/index.html` into `web/css/index.css` | Completed |
| 1.2 | Extract inline CSS from `web/compare.html` into `web/css/compare.css` | Completed |
| 1.3 | Extract inline JS from `web/index.html` into `web/js/index/main.js` | Completed |
| 1.4 | Extract inline JS from `web/compare.html` into `web/js/compare/main.js` | Completed |

## Phase 2: Shared Runtime Modules
| Stage | Description | Status |
|---|---|---|
| 2.1 | Add shared theme controller module (`web/js/shared/theme.js`) | Completed |
| 2.2 | Add shared tooltip controller module (`web/js/shared/tooltip.js`) | Completed |
| 2.3 | Add shared normalization/number/svg helpers (`web/js/shared/*.js`) | Completed |
| 2.4 | Add shared adaptive label helper (`web/js/shared/labels.js`) | Completed |
| 2.5 | Wire index/compare to shared modules | Completed |

## Phase 3: Data Access Boundary
| Stage | Description | Status |
|---|---|---|
| 3.1 | Add HTTP helper module (`web/js/data/http.js`) | Completed |
| 3.2 | Add session API wrapper (`web/js/data/session_api.js`) | Completed |
| 3.3 | Migrate index fetch callsites to session API wrapper | Completed |
| 3.4 | Migrate compare fetch callsites to session API wrapper | Completed |

## Phase 4: Feature Module Extraction
| Stage | Description | Status |
|---|---|---|
| 4.1 | Extract prospect histogram/cumulative rendering from index main into chart modules | Completed |
| 4.2 | Extract material percent rendering from index main into chart module | Completed |
| 4.3 | Extract timeline/cumulative commodity rendering into chart modules | Completed |
| 4.4 | Extract compare chart rendering into compare feature modules | Completed |

### Phase 4.1 Detailed Stages
| Stage | Description | Status |
|---|---|---|
| 4.1.1 | Add prospect model module (`web/js/index/models/prospect_model.js`) and move pure model builders intact | Completed |
| 4.1.2 | Add prospect histogram chart module (`web/js/index/charts/prospect_histogram.js`) and migrate selected-histogram renderer | Completed |
| 4.1.3 | Add prospect cumulative chart module (`web/js/index/charts/prospect_cumulative.js`) and migrate cumulative DOM/SVG renderer | Completed |
| 4.1.4 | Keep `web/js/index/main.js` thin orchestration wrappers and preserve hover/highlight contracts | Completed |
| 4.1.5 | Verify with targeted + full headless pytest and update phase status | Completed |

### Phase 4.2 Detailed Stages
| Stage | Description | Status |
|---|---|---|
| 4.2.1 | Add material percent model module (`web/js/index/models/material_percent_model.js`) and move model builder intact | Completed |
| 4.2.2 | Add material percent chart module (`web/js/index/charts/material_percent.js`) and migrate DOM/SVG rendering intact | Completed |
| 4.2.3 | Keep `web/js/index/main.js` thin orchestration wrappers and preserve hover/highlight contracts | Completed |
| 4.2.4 | Verify with targeted + full headless pytest and update phase status | Completed |

### Phase 4.3 Detailed Stages
| Stage | Description | Status |
|---|---|---|
| 4.3.1 | Add cumulative commodity model module (`web/js/index/models/cumulative_commodity_model.js`) and move pure model builder intact | Completed |
| 4.3.2 | Add cumulative commodity chart module (`web/js/index/charts/cumulative_commodities.js`) and migrate renderer with injected state/dependencies | Completed |
| 4.3.3 | Add timeline chart module (`web/js/index/charts/timeline.js`) and migrate timeline helpers/renderer intact | Completed |
| 4.3.4 | Keep `web/js/index/main.js` thin orchestration wrappers for refinement/event timelines and cumulative chart | Completed |
| 4.3.5 | Verify with targeted + full headless pytest and update phase status | Completed |

### Phase 4.4 Detailed Stages
| Stage | Description | Status |
|---|---|---|
| 4.4.1 | Add compare model module (`web/js/compare/models/compare_model.js`) and move compare data/model builders intact | Completed |
| 4.4.2 | Add compare ring chart module (`web/js/compare/charts/ring_chart.js`) and move histogram/cumulative renderer intact | Completed |
| 4.4.3 | Keep `web/js/compare/main.js` thin orchestration wrappers with injected shared dependencies | Completed |
| 4.4.4 | Verify with targeted + full headless pytest and update phase status | Completed |

## Phase 5: State and Orchestration
| Stage | Description | Status |
|---|---|---|
| 5.1 | Introduce page-level store/controller for index state updates | Completed |
| 5.2 | Introduce page-level store/controller for compare state updates | Completed |
| 5.3 | Remove remaining direct global state coupling in render/model functions | Completed |

## Phase 6: UI Wiring Decomposition
| Stage | Description | Status |
|---|---|---|
| 6.1 | Extract compare control rendering/wiring into dedicated UI module | Completed |
| 6.2 | Extract index display-settings control wiring into dedicated UI module | Completed |
| 6.3 | Wire index/compare mains to thin wrappers over extracted UI modules | Completed |
| 6.4 | Verify with targeted + full headless pytest and update phase status | Completed |

## Phase 7: Timeline Filter Decomposition
| Stage | Description | Status |
|---|---|---|
| 7.1 | Extract reusable checkbox-filter UI wiring for timeline/event panels into dedicated index UI module | Completed |
| 7.2 | Replace index event timeline filter builder with thin wrapper over extracted module | Completed |
| 7.3 | Replace index refinement timeline filter builder with thin wrapper over extracted module | Completed |
| 7.4 | Verify with targeted + full headless pytest and update phase status | Completed |

## Phase 8: Event Journal UI Decomposition
| Stage | Description | Status |
|---|---|---|
| 8.1 | Extract event journal + timeline bar linking/highlight behavior into dedicated index UI module | Completed |
| 8.2 | Replace index event timeline journal/highlight helpers with thin wrapper over extracted module | Completed |
| 8.3 | Verify behavior parity and run targeted + full headless pytest | Completed |

### Phase 5.1 Detailed Stages
| Stage | Description | Status |
|---|---|---|
| 5.1.1 | Add index state store module (`web/js/index/state/store.js`) with subscribe/get/patch primitives | Completed |
| 5.1.2 | Add index state controller module (`web/js/index/state/controller.js`) with explicit state-update actions | Completed |
| 5.1.3 | Wire `web/js/index/main.js` to controller/store and route core session/display/histogram state writes through controller actions | Completed |
| 5.1.4 | Verify with targeted + full headless pytest and update phase status | Completed |

### Phase 5.2 Detailed Stages
| Stage | Description | Status |
|---|---|---|
| 5.2.1 | Add compare state store module (`web/js/compare/state/store.js`) with subscribe/get/patch primitives | Completed |
| 5.2.2 | Add compare state controller module (`web/js/compare/state/controller.js`) with explicit state-update actions | Completed |
| 5.2.3 | Wire `web/js/compare/main.js` to controller/store and route compare page state writes through controller actions | Completed |
| 5.2.4 | Verify with targeted + full headless pytest and update phase status | Completed |

### Phase 5.3 Detailed Stages
| Stage | Description | Status |
|---|---|---|
| 5.3.1 | Add explicit render-state selectors/snapshots for index and compare orchestration | Completed |
| 5.3.2 | Refactor index render/model orchestration call paths to pass explicit state snapshots instead of relying on mutable globals | Completed |
| 5.3.3 | Refactor compare render/model orchestration call paths to pass explicit state snapshots instead of relying on mutable globals | Completed |
| 5.3.4 | Verify with targeted + full headless pytest and update phase status | Completed |

### Phase 6.1 Detailed Stages
| Stage | Description | Status |
|---|---|---|
| 6.1.1 | Add compare controls module (`web/js/compare/ui/controls.js`) and lift control DOM rendering/wiring intact | Completed |
| 6.1.2 | Replace compare main control builders with thin wrappers over module exports | Completed |
| 6.1.3 | Verify compare behavior parity and keep state/controller boundaries intact | Completed |

### Phase 6.2 Detailed Stages
| Stage | Description | Status |
|---|---|---|
| 6.2.1 | Add index display-controls module (`web/js/index/ui/display_controls.js`) and lift checkbox/radio wiring intact | Completed |
| 6.2.2 | Replace index main bottom-of-file listener block with module wiring call | Completed |
| 6.2.3 | Verify histogram/material/cumulative control behavior parity | Completed |

### Phase 7 Detailed Stages
| Stage | Description | Status |
|---|---|---|
| 7.1.1 | Add timeline filter controls module (`web/js/index/ui/timeline_filters.js`) with reusable all+item checkbox wiring | Completed |
| 7.1.2 | Migrate event filter DOM wiring/listener logic from `web/js/index/main.js` to module | Completed |
| 7.1.3 | Migrate refinement filter DOM wiring/listener logic from `web/js/index/main.js` to module | Completed |
| 7.1.4 | Verify behavior parity and run headless pytest gate | Completed |

### Phase 8 Detailed Stages
| Stage | Description | Status |
|---|---|---|
| 8.1.1 | Add event journal module (`web/js/index/ui/event_journal.js`) and lift journal row rendering/highlight/bin-link helpers intact | Completed |
| 8.1.2 | Migrate event timeline-to-journal click wiring from `web/js/index/main.js` to module | Completed |
| 8.1.3 | Replace event timeline filtered render path with thin orchestration calls into module | Completed |
| 8.1.4 | Verify behavior parity and run headless pytest gate | Completed |

## Tests Run
- `source .venv/bin/activate && python -m pytest -q` (pass)
- `source .venv/bin/activate && python -m pytest -q tests` (pass)
- `source .venv/bin/activate && python -m pytest -q` (pass)
- `source .venv/bin/activate && python -m pytest -q tests` (pass)
- `source .venv/bin/activate && python -m pytest -q` (pass)
- `source .venv/bin/activate && python -m pytest -q tests` (pass)
- `source .venv/bin/activate && python -m pytest -q` (pass)
- `source .venv/bin/activate && python -m pytest -q tests` (pass)
- `source .venv/bin/activate && python -m pytest -q` (pass)
- `source .venv/bin/activate && python -m pytest -q tests` (pass)
- `source .venv/bin/activate && python -m pytest -q` (pass)
- `source .venv/bin/activate && python -m pytest -q tests` (pass)
- `source .venv/bin/activate && python -m pytest -q` (pass)
- `source .venv/bin/activate && python -m pytest -q tests` (pass)
- `source .venv/bin/activate && python -m pytest -q` (pass)
- `source .venv/bin/activate && python -m pytest -q tests` (pass)
- `source .venv/bin/activate && python -m pytest -q` (pass)
- `source .venv/bin/activate && python -m pytest -q tests` (pass)
- `source .venv/bin/activate && python -m pytest -q` (pass)
- `source .venv/bin/activate && python -m pytest -q tests` (pass)
- `source .venv/bin/activate && python -m pytest -q` (pass)

## Planned Tests For Phase 4.1
- `source .venv/bin/activate && python -m pytest -q tests/test_analysis_*.py`
- `source .venv/bin/activate && python -m pytest -q`

## Planned Tests For Phase 4.2
- `source .venv/bin/activate && python -m pytest -q tests`
- `source .venv/bin/activate && python -m pytest -q`

## Planned Tests For Phase 4.3
- `source .venv/bin/activate && python -m pytest -q tests`
- `source .venv/bin/activate && python -m pytest -q`

## Planned Tests For Phase 4.4
- `source .venv/bin/activate && python -m pytest -q tests`
- `source .venv/bin/activate && python -m pytest -q`

## Planned Tests For Phase 5.1
- `source .venv/bin/activate && python -m pytest -q tests`
- `source .venv/bin/activate && python -m pytest -q`

## Planned Tests For Phase 5.2
- `source .venv/bin/activate && python -m pytest -q tests`
- `source .venv/bin/activate && python -m pytest -q`

## Planned Tests For Phase 5.3
- `source .venv/bin/activate && python -m pytest -q tests`
- `source .venv/bin/activate && python -m pytest -q`

## Planned Tests For Phase 6
- `source .venv/bin/activate && python -m pytest -q tests`
- `source .venv/bin/activate && python -m pytest -q`

## Planned Tests For Phase 7
- `source .venv/bin/activate && python -m pytest -q tests`
- `source .venv/bin/activate && python -m pytest -q`

## Planned Tests For Phase 8
- `source .venv/bin/activate && python -m pytest -q tests`
- `source .venv/bin/activate && python -m pytest -q`

## Notes
- Node.js is not installed in this environment, so `node --check` syntax validation could not be run for JS modules.
