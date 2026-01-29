## Goal: Overlay bars showing commodities



Requirements
- Under the current overlay, show a small bar for each commodity refined.
- The name of the commodity will be on the left in normal font size
- to the right of the commodity will be a bar (filled rect) showing the % of cargo that is that commodity
- additional commodities will be shown below the first one.
- order them from highest percentage to lowest
- show only commodities refined and limpets. Ignore anything else in the cargo
- All the bars should be justified with the 0% on the bar being at the same X value.
- The overall length of all the bars (if they would all be 100%) are the same
- bar color is Elite dangerous orange
- Provide a setting option on the overlay pref pane to show/hide the bars

## Questions to Answer
- Which overlay is this (EDMC overlay window vs. the in-game overlay integration), and where exactly should the bars appear relative to the existing content?
add it to the current edmc mining analytics plugin. it should be below the est. cr overlay.
- Should the bar percentages be based on total cargo capacity, current cargo tonnage, or refined cargo only (plus limpets)?
total cargo capacity
- Should limpets be included as its own bar (with the name "Limpets"), or only used in the denominator?
limpets should be its own bar
- For "show only commodities refined," should we use `mining_refined` events, or current cargo inventory filtered to items refined this session?
use current cargo inventory filtered
- How should we handle commodities with 0% (hide them entirely or show 0-length bars)?
hide them. they should never show up
- Any size constraints (max number of rows before scrolling, max width/height for the bar block)?
add an option for max number of rows in settings. default to 10
- What exact color value should we use for "Elite Dangerous orange" (hex/RGB), or should I reuse an existing theme color in the project?
do your research
- Preference setting: should it live in the existing overlay prefs panel (which module), and what should the config key/name be?
it should be in the edmc-mining-analytics pref pane in the overlay section
- For "Elite Dangerous orange," is it OK if I use web research to pick an accurate hex/RGB (with citation)?
yes
- What should the config keys be for: (1) show/hide bars and (2) max rows (default 10)?
overlay_show_bars (bool, default False) and overlay_bars_max_rows (int, default 10)
- For "current cargo inventory filtered to items refined this session," where should the "refined this session" list come from (existing tracked state vs new tracking)?
existing tracked state
- If cargo capacity is missing or 0, should the bars hide entirely, or fall back to current cargo tonnage for percentage?
hide entirely
- Any rule for ordering ties (same percent), or just stable order?
alphabetized



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
| Phase 1 | Discover touchpoints + data flow for overlay bars | Planned |
| Phase 2 | Implement overlay bar rendering + preferences wiring | Planned |
| Phase 3 | QA, tests, and documentation update | Planned |

### Phase 1 Stages

| Stage | Description | Status |
| --- | --- | --- |
| 1.1 | Identify overlay UI module + placement under est. CR overlay | Planned |
| 1.2 | Identify existing tracked state for refined commodities + cargo inventory access | Planned |
| 1.3 | Decide color source (web research) and confirm any theme reuse | Planned |

### Phase 2 Stages

| Stage | Description | Status |
| --- | --- | --- |
| 2.1 | Add preferences: `overlay_show_bars`, `overlay_bars_max_rows` to overlay prefs UI | Planned |
| 2.2 | Add data prep helper for overlay bar rows (filter refined + limpets, % of capacity, sort desc, tie alpha) | Planned |
| 2.3 | Render bars under est. CR overlay with fixed width, aligned baseline, ED orange | Planned |
| 2.4 | Wire show/hide + max rows settings to overlay rendering | Planned |

### Phase 3 Stages

| Stage | Description | Status |
| --- | --- | --- |
| 3.1 | Add/update tests for data prep helper (headless) | Planned |
| 3.2 | Manual overlay sanity check and doc update for new settings | Planned |
