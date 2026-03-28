## Goal: Establish a reusable capability subsystem architecture for OS/runtime-dependent features

Follow persona details in `AGENTS.md`.
Document implementation results in the `Implementation Results` section.
After each stage is complete, change stage status to `Completed`.
When all stages in a phase are complete, change phase status to `Completed`.
If something is unclear, capture it under `Open Questions`.

## Requirements (Initial)
- Build a general capability subsystem that allows new capabilities to be added without spreading platform-branching logic through UI/business modules.
- Define explicit contracts for capability invocation, capability discovery, and capability execution results.
- Define async execution as a first-class contract now, with UI-safe completion handling.
- Keep call sites capability-oriented, not OS-oriented: callers request capabilities, not platform behavior.
- Ensure graceful degradation when capabilities are unsupported in the current environment.
- Use per-capability default policies, with per-request override support.
- Require providers to expose a lightweight `health_probe()` for diagnostics and resolver visibility.
- Run `health_probe()` both on-demand and once at startup to populate initial diagnostics state.
- Keep user controls internal/dev-only for capability behavior tuning in this phase.
- Keep `load.py` minimal: new feature/business logic should be implemented in helper modules/services, with `load.py` limited to orchestration/wiring and thin delegating methods.
- Capability 1 (first implementation) will be browser open/raise behavior, but subsystem must be designed for future capabilities.

## Capability Subsystem Scope
- In scope:
- Capability contract and result schema.
- Resolver/registry design for selecting capability providers.
- Adapter boundaries for platform/runtime specifics.
- Capability policy model (best-effort/strict/disabled).
- Async dispatch contract and completion semantics.
- Observability contract (debug logging + reason codes).
- Observability must use EDMC's logger pipeline (`get_logger` -> EDMC handlers), not standalone logging sinks.
- First capability profile definition: browser open/raise.
- Out of scope (for foundation phase):
- Implementing every future capability now.
- Major refactors outside capability call paths.
- New mandatory third-party dependencies.

## Capability Model (General)
- Core abstractions:
- `CapabilityId`:
  - Stable identifier (for example: `browser.open_raise`, `clipboard.copy`, `notifications.toast`).
- `CapabilityRequest`:
  - Capability id + payload + optional policy override (`best_effort`, `strict`, `disabled`).
- `CapabilityDescriptor`:
  - Declares capability-level defaults (default policy, timeout budget, provider precedence hints).
- `CapabilityResult`:
  - `success`, `degraded`, `unsupported`, `failed` plus `reason_code`, `provider`, and optional metadata.
- `CapabilityProvider`:
  - Advertises supported capability ids, executes requests, and exposes lightweight `health_probe()` diagnostics.
- `CapabilityRegistry`:
  - Holds providers and provider precedence.
- `CapabilityResolver`:
  - Chooses provider for a request using environment detection and policy.
- `CapabilityDispatcher`:
  - Executes capability requests asynchronously and emits structured completion results to callers.

- System invariants:
- Callers must not inspect `sys.platform` directly for capability behavior.
- All capability execution paths return structured results; no uncaught exceptions escape UI handlers.
- Async execution must not block the Tk main thread.
- Unsupported capability requests degrade according to policy, not ad-hoc branching.
- Provider selection and fallback reasons are observable in debug logs.

## Provider Selection & Fallback Requirements
- Resolver input dimensions:
- OS family, session type (X11/Wayland/etc.), binary availability, runtime constraints.
- Resolver output:
- selected provider + attempted provider chain.
- Provider diagnostics:
- Resolver may consult provider `health_probe()` hints for debugging/selection visibility; probes must be fast and side-effect free.
- Startup behavior: perform one startup probe pass and cache initial provider diagnostics for later inspection.
- Diagnostics surfacing for this phase: EDMC debug logger output only (no UI diagnostics surface).
- Linux baseline:
- Wayland defaults to open-only behavior for Capability 1 until compositor-specific providers are added.
- Future path: compositor-specific providers (for example GNOME/KDE/Sway) can override the baseline via resolver rules.
- Fallback behavior:
- `best_effort`: attempt fallback providers; return `degraded` if partial success.
- `strict`: no fallback that changes semantics; return `failed`/`unsupported`.
- `disabled`: short-circuit without side effects.
- Timeout behavior:
- Provider operations must be bounded (short, explicit timeouts for subprocess-based strategies).

## First Capability Profile (Capability 1)
- Capability id:
- `browser.open_raise`
- Intent:
- Open Analysis page and raise browser if feasible.
- Expected policies:
- Capability default policy is `best_effort`.
- `strict` mode optional for tests/dev diagnostics.
- Degradation contract:
- If raise is unavailable, opening the URL still counts as `degraded` success.

## Standard Reason Codes (Initial)
- `unsupported_env` (environment cannot support requested capability behavior)
- `policy_blocked` (disabled by configured/effective policy)
- `provider_unavailable` (no provider available for capability)
- `tool_missing` (optional external tool unavailable)
- `timeout` (provider attempt exceeded time budget)
- `partial_success` (requested full behavior not achieved, degraded path succeeded)
- `execution_error` (provider raised an error)

## Vendored Paths Guardrail (Required)
- `tests/harness.py` is vendored and immutable by default.
- Everything under `tests/edmc/` is vendored and immutable by default.
- If this plan requires changes in either path, mark that explicitly as a re-vendor/sync task and record the upstream source.

## Testing Strategy (Required Before Implementation)

| Change Area | Behavior / Invariant | Test Type (Unit/Harness) | Why This Level | Test File(s) | Command |
| --- | --- | --- | --- | --- | --- |
| Capability contracts + result schema | Stable request/result semantics across capabilities | Unit | Pure data and deterministic mapping | `tests/test_capability_contracts.py` | `source .venv/bin/activate && python -m pytest tests/test_capability_contracts.py` |
| Provider health probes | `health_probe()` is fast, side-effect free, supports startup + on-demand use, and returns structured diagnostics | Unit | Pure provider contract validation | `tests/test_capability_provider_health_probe.py` | `source .venv/bin/activate && python -m pytest tests/test_capability_provider_health_probe.py` |
| Async dispatcher | Async completion semantics and non-blocking behavior are preserved | Unit | Deterministic with mocked executor/threading | `tests/test_capability_dispatcher_async.py` | `source .venv/bin/activate && python -m pytest tests/test_capability_dispatcher_async.py` |
| Registry + resolver | Provider selection/fallback by environment + policy | Unit | Deterministic with mocked environment probes | `tests/test_capability_resolver.py` | `source .venv/bin/activate && python -m pytest tests/test_capability_resolver.py` |
| Capability 1 provider chain | Browser open/raise degrades correctly under failures | Unit | Pure adapter behavior with mocks | `tests/test_browser_capability.py` | `source .venv/bin/activate && python -m pytest tests/test_browser_capability.py` |
| UI wiring to capability facade | Analysis action handles structured results correctly | Unit | Handler-level integration without lifecycle complexity | `tests/test_browser_capability_integration.py` | `source .venv/bin/activate && python -m pytest tests/test_browser_capability_integration.py` |
| Plugin lifecycle baseline | No regression in plugin startup/shutdown path | Harness | Guard against wiring regressions outside pure logic | `tests/test_harness_smoke.py` | `source .venv/bin/activate && python -m pytest tests/test_harness_smoke.py` |

## Test Scope Decision (Required)
- Unit-only? Why: Not sufficient; subsystem wiring touches runtime integration points.
- Harness required? Why: Yes, at least smoke validation after integration milestones.
- Mixed (Unit + Harness)? Why: Yes. Unit for contracts/resolver/providers; harness for lifecycle safety.

## Test Acceptance Gates (Required)
- [x] Unit tests added/updated for pure logic changes.
- [x] Harness tests added/updated for lifecycle/wiring changes.
- [x] Exact commands listed and executed.
- [x] Any skips documented with reasons.

## Out Of Scope (This Change)
- Building all future capabilities now.
- Changing unrelated UI workflows not needed for capability integration.
- Editing `tests/harness.py` or `tests/edmc/**` unless this plan explicitly includes an upstream re-vendor/sync stage.

## Current Touch Points
- Code:
- `edmc_mining_analytics/browser_utils.py` (capability facade for browser open/raise)
- `edmc_mining_analytics/capabilities/*` (core contracts, resolver, dispatcher, providers, bootstrap)
- `edmc_mining_analytics/plugin.py` (startup probe execution + service wiring)
- `edmc_mining_analytics/mining_ui/main_mining_ui.py` (Analysis action capability call site)
- `edmc_mining_analytics/logging_utils.py` (EDMC logger wiring patterns)
- Tests:
- `tests/test_capability_contracts.py`
- `tests/test_capability_resolver.py`
- `tests/test_capability_dispatcher_async.py`
- `tests/test_capability_provider_health_probe.py`
- `tests/test_browser_capability.py`
- `tests/test_browser_capability_integration.py`
- `tests/test_browser_utils.py`
- `tests/test_harness_smoke.py` (baseline harness smoke)
- Docs/notes:
- `docs/plans/capability-subsystem-foundation.md`

## Assumptions
- More OS/runtime-sensitive features will be added after browser focus.
- Capability subsystem should stay lightweight and plugin-local (no external framework).

## Risks
- Risk: Over-engineering before real second/third capabilities exist.
- Mitigation: Keep contracts minimal and validate via Capability 1 first.
- Risk: Resolver complexity grows quickly.
- Mitigation: Explicit provider precedence rules and narrow provider responsibilities.
- Risk: Poor observability causes hard-to-debug fallbacks.
- Mitigation: Standard reason codes + debug logs at resolver/provider boundaries.

## Open Questions
- None currently.

## Decisions (Locked)
- Subsystem-first design: define generic contracts before expanding OS-specific logic.
- Provider/resolver architecture will isolate platform branching from feature call sites.
- Capability 1 is browser open/raise and serves as the proving path for the subsystem.
- Async support is in scope now as part of the core capability contract.
- Policy defaults are defined per capability, with per-request override support.
- Linux Wayland baseline for Capability 1 is open-only; compositor-specific providers are planned as follow-up.
- Capability behavior controls are internal/dev-only in this phase.
- Reason codes are standardized now using the initial catalog in this plan.
- Providers must implement lightweight, side-effect-free `health_probe()` diagnostics.
- `health_probe()` runs both once at startup (cached diagnostics) and on-demand.
- Startup `health_probe()` diagnostics are surfaced via EDMC debug logger only.
- Provider module naming is intentionally not fixed yet; naming evolves as providers are introduced.

## Phase Overview

| Phase | Description | Status |
| --- | --- | --- |
| 1 | Foundation requirements and architecture | Completed |
| 2 | Core subsystem implementation (contracts/resolver/dispatcher/probes) | Completed |
| 3 | Capability 1 implementation and UI wiring | Completed |
| 4 | Validation and rollout execution | Completed |
| 5 | Future capability onboarding model | Completed |

## Phase Details

### Phase 1: Foundation Requirements and Architecture
- Define the generic subsystem language, boundaries, and acceptance criteria.
- Risks: too broad or too vague foundation.
- Mitigations: lock explicit contracts, invariants, and non-goals.

| Stage | Description | Status |
| --- | --- | --- |
| 1.1 | Create general subsystem plan from template | Completed |
| 1.2 | Define generic capability contracts and invariants | Completed |
| 1.3 | Lock foundation acceptance criteria and guardrails | Completed |

#### Stage 1.1 Detailed Plan
- Objective:
- Establish a reusable planning artifact not tied to a single capability.
- Primary touch points:
- `docs/plans/capability-subsystem-foundation.md`
- Steps:
- Create plan file from template.
- Replace feature-specific framing with subsystem-level requirements.
- Acceptance criteria:
- Plan is capability-framework oriented.
- Capability 1 is defined as first profile, not the whole architecture.
- Verification to run:
- `ls -la docs/plans`

#### Stage 1.2 Detailed Plan
- Objective:
- Define request/result/provider/registry/resolver contracts.
- Steps:
- Specify required fields and status semantics.
- Specify invariants and caller responsibilities.
- Acceptance criteria:
- Contracts are implementation-ready and unambiguous.
- Verification to run:
- `rg -n "Capability Model|System invariants|Provider Selection" docs/plans/capability-subsystem-foundation.md`

#### Stage 1.3 Detailed Plan
- Objective:
- Lock acceptance gates and architectural constraints for implementation.
- Steps:
- Confirm test gates and out-of-scope boundaries.
- Lock decisions and open questions.
- Acceptance criteria:
- Foundation is ready for implementation planning.
- Verification to run:
- `rg -n "Test Acceptance Gates|Out Of Scope|Decisions \(Locked\)" docs/plans/capability-subsystem-foundation.md`

#### Phase 1 Execution Order
- Implement in strict order: `1.1` -> `1.2` -> `1.3`.

#### Phase 1 Exit Criteria
- Generic capability architecture is documented and agreed.
- Acceptance gates are explicit.

### Phase 2: Core Subsystem Implementation (Contracts/Resolver/Dispatcher/Probes)
- Implement the capability core modules and runtime behavior defined in Phase 1.
- Risks: premature coupling to Capability 1 specifics.
- Mitigations: keep capability-agnostic core module and pluggable providers.

| Stage | Description | Status |
| --- | --- | --- |
| 2.1 | Implement core module boundaries and public interfaces | Completed |
| 2.2 | Implement resolver precedence plus startup/on-demand health probes | Completed |
| 2.3 | Implement provider registration and policy-based fallback | Completed |

#### Stage 2.1 Detailed Plan
- Objective:
- Split and implement core contracts separate from capability providers.
- Primary touch points:
- `edmc_mining_analytics/<new capability core modules>`
- Steps:
- Implement file/module ownership for core contracts and resolver/dispatcher.
- Expose public API used by feature call sites.
- Acceptance criteria:
- No feature module imports platform probes directly.
- Verification to run:
- `rg -n "module boundaries|public API" docs/plans/capability-subsystem-foundation.md`

#### Stage 2.2 Detailed Plan
- Objective:
- Implement deterministic resolver behavior under environment differences.
- Steps:
- Implement probe inputs and precedence rules.
- Implement startup probe pass and on-demand probe behavior surfaced via EDMC debug logger.
- Acceptance criteria:
- Resolver outputs are deterministic for a given environment snapshot.
- Verification to run:
- `rg -n "precedence|probe|resolver" docs/plans/capability-subsystem-foundation.md`

#### Stage 2.3 Detailed Plan
- Objective:
- Implement provider registration and fallback semantics by policy.
- Steps:
- Implement provider chain evaluation and stop conditions.
- Implement strict vs best-effort behavior.
- Acceptance criteria:
- Fallback semantics are explicit and testable.
- Verification to run:
- `rg -n "fallback|best_effort|strict|disabled" docs/plans/capability-subsystem-foundation.md`

#### Phase 2 Execution Order
- Implement in strict order: `2.1` -> `2.2` -> `2.3`.

#### Phase 2 Exit Criteria
- Core subsystem is implemented with async dispatcher, resolver, and health-probe lifecycle behavior.

### Phase 3: Capability 1 (Browser) Implementation and Wiring
- Implement browser open/raise behavior on the subsystem as proof-of-design.
- Risks: Capability 1 drives architecture too narrowly.
- Mitigations: enforce core/adapter separation in plan and tests.

| Stage | Description | Status |
| --- | --- | --- |
| 3.1 | Implement Capability 1 request/result profile | Completed |
| 3.2 | Implement provider chain for Capability 1 | Completed |
| 3.3 | Implement call-site migration and rollback hook | Completed |

#### Stage 3.1 Detailed Plan
- Objective:
- Implement browser behavior entirely via generic request/result contracts.
- Steps:
- Implement payload schema and reason codes.
- Implement degradation semantics (`open` succeeds, `raise` unavailable).
- Acceptance criteria:
- Capability 1 can be invoked without OS-specific branching in caller.
- Verification to run:
- `rg -n "First Capability Profile|degraded|reason" docs/plans/capability-subsystem-foundation.md`

#### Stage 3.2 Detailed Plan
- Objective:
- Implement provider strategies per environment for Capability 1.
- Steps:
- Implement provider ordering and timeouts.
- Implement tool/probe feature detection (optional helpers) with Wayland open-only baseline.
- Acceptance criteria:
- Provider chain is bounded and safely degradable.
- Verification to run:
- `rg -n "provider chain|timeouts|optional" docs/plans/capability-subsystem-foundation.md`

#### Stage 3.3 Detailed Plan
- Objective:
- Implement low-risk migration for the Analysis button call path.
- Steps:
- Replace direct helper usage with capability facade.
- Implement rollback switch/strategy if regressions appear.
- Acceptance criteria:
- Migration is reversible and behavior-scoped.
- Verification to run:
- `rg -n "rollback|Analysis|call-site" docs/plans/capability-subsystem-foundation.md`

#### Phase 3 Execution Order
- Implement in strict order: `3.1` -> `3.2` -> `3.3`.

#### Phase 3 Exit Criteria
- Capability 1 is implemented and wired to the Analysis action with rollback path available.

### Phase 4: Validation and Rollout Execution
- Execute validation and produce release-ready notes for subsystem + Capability 1.
- Risks: insufficient cross-environment confidence.
- Mitigations: mixed test model + documented manual checks.

| Stage | Description | Status |
| --- | --- | --- |
| 4.1 | Execute unit and harness command matrix | Completed |
| 4.2 | Execute manual verification checklist | Completed |
| 4.3 | Publish release notes and troubleshooting guidance | Completed |

#### Stage 4.1 Detailed Plan
- Objective:
- Execute exact test commands and collect outcomes.
- Steps:
- Run file/command matrix for CI/local runs.
- Record required vs optional gate outcomes.
- Acceptance criteria:
- Test execution plan is reproducible by another maintainer.
- Verification to run:
- `rg -n "Testing Strategy|Test Acceptance Gates" docs/plans/capability-subsystem-foundation.md`

#### Stage 4.2 Detailed Plan
- Objective:
- Ensure manual runtime validation is completed and recorded.
- Steps:
- Define click-path/manual desktop checks.
- Define expected status/log outputs for success/degraded cases.
- Acceptance criteria:
- Manual checks detect key regressions.
- Verification to run:
- `rg -n "manual|status|degraded" docs/plans/capability-subsystem-foundation.md`

#### Stage 4.3 Detailed Plan
- Objective:
- Publish user-facing and maintainer-facing rollout notes.
- Steps:
- Document best-effort limitations and troubleshooting flow.
- Document known unsupported scenarios.
- Acceptance criteria:
- Release guidance is concise and actionable.
- Verification to run:
- `rg -n "troubleshooting|unsupported|best-effort" docs/plans/capability-subsystem-foundation.md`

#### Phase 4 Execution Order
- Implement in strict order: `4.1` -> `4.2` -> `4.3`.

#### Phase 4 Exit Criteria
- Validation evidence and rollout artifacts are complete.

### Phase 5: Future Capability Onboarding Model
- Define a repeatable process for adding capabilities after Capability 1.
- Risks: architecture drift as new features are added.
- Mitigations: onboarding checklist and contribution guardrails.

| Stage | Description | Status |
| --- | --- | --- |
| 5.1 | Define "new capability" onboarding checklist | Completed |
| 5.2 | Define contribution guardrails for providers/resolver | Completed |
| 5.3 | Define follow-up backlog and prioritization model | Completed |

#### Stage 5.1 Detailed Plan
- Objective:
- Make future capability additions predictable and low-risk.
- Steps:
- Define required docs/tests per new capability.
- Define approval checklist before merge.
- Acceptance criteria:
- New capability workflow is explicit and repeatable.
- Verification to run:
- `rg -n "onboarding checklist|new capability" docs/plans/capability-subsystem-foundation.md`

#### Stage 5.2 Detailed Plan
- Objective:
- Prevent ad-hoc platform branching from creeping back in.
- Steps:
- Define guardrails (no caller platform checks, provider-only branching).
- Define review checklist for resolver/provider changes.
- Acceptance criteria:
- Guardrails are enforceable in code review.
- Verification to run:
- `rg -n "guardrails|provider-only branching|review checklist" docs/plans/capability-subsystem-foundation.md`

#### Stage 5.3 Detailed Plan
- Objective:
- Keep roadmap visible for next capabilities.
- Steps:
- Define candidate capabilities and prioritization rubric.
- Track dependencies/risks per candidate.
- Acceptance criteria:
- Backlog is actionable and ranked.
- Verification to run:
- `rg -n "candidate capabilities|prioritization" docs/plans/capability-subsystem-foundation.md`

#### Phase 5 Execution Order
- Implement in strict order: `5.1` -> `5.2` -> `5.3`.

#### Phase 5 Exit Criteria
- Future capability onboarding model is documented and accepted.

### Phase 5 Outputs
- New Capability Onboarding Checklist:
- Add `CapabilityDescriptor` with per-capability defaults (`default_policy`, timeout, precedence hints).
- Implement provider(s) with required `supports`, `match_score`, `health_probe`, and `execute`.
- Ensure startup probe behavior and on-demand probe behavior produce EDMC debug logs only.
- Add/extend unit tests for contracts, resolver selection, provider probes, and capability behavior.
- Add/extend harness smoke validation when plugin wiring changes.
- Document rollout notes and troubleshooting behavior for degraded/unsupported modes.
- Contribution Guardrails:
- No platform checks in feature call sites; platform branching lives in providers/resolver only.
- Provider `health_probe()` must be fast, side-effect free, and safe on startup.
- Do not bypass EDMC logging; use `get_logger` so diagnostics route through EDMC handlers.
- Preserve policy semantics (`best_effort`, `strict`, `disabled`) and reason-code vocabulary.
- Follow-up Backlog Prioritization Model:
- `P1`: User-visible failures or silent regressions in capability execution.
- `P2`: Reliability improvements for major desktop/session combinations.
- `P3`: New providers for narrower environments/compositors.
- `P4`: Developer ergonomics, diagnostics depth, and non-critical refactors.

## Test Plan (Per Iteration)
- Env setup (once per machine):
- `python3 -m venv .venv && source .venv/bin/activate && python -m pip install -U pip && python -m pip install -r requirements-dev.txt`
- Headless quick pass:
- `source .venv/bin/activate && python -m pytest`
- Targeted tests:
- `source .venv/bin/activate && python -m pytest <path/to/tests> -k "<pattern>"`
- Milestone checks:
- `make check`
- `make test`
- Compliance baseline check (release/compliance work):
- `python scripts/check_edmc_python.py`

## Implementation Results
- Plan created on 2026-03-26.
- Phase 1 foundation completed on 2026-03-26.
- Phase 2 implemented on 2026-03-26.
- Phase 3 implemented on 2026-03-26.
- Phase 4 validated on 2026-03-26.
- Phase 5 onboarding model finalized on 2026-03-26.

### Phase 1 Execution Summary
- Stage 1.1:
- Completed. Generalized the plan from a single-feature focus to a subsystem foundation plan.
- Stage 1.2:
- Completed. Locked async-first contract, per-capability defaults, and standardized reason codes.
- Stage 1.3:
- Completed. Locked guardrails, Wayland baseline policy, and dev-only control scope.

### Tests Run For Phase 1
- None (planning-only update).
- Result: skipped; no runtime or test code changes in this step.

### Phase 2 Execution Summary
- Stage 2.1:
- Completed. Implemented core capability modules (`models`, `registry`, `resolver`, `dispatcher`, `service`) and package bootstrap wiring.
- Stage 2.2:
- Completed. Implemented resolver precedence and startup/on-demand health probes with EDMC debug logger diagnostics.
- Stage 2.3:
- Completed. Implemented provider registration and policy-based fallback behavior in capability service.

### Tests Run For Phase 2
- `source .venv/bin/activate && python -m pytest tests/test_capability_contracts.py tests/test_capability_resolver.py tests/test_capability_dispatcher_async.py tests/test_capability_provider_health_probe.py`
- Result: passed.

### Phase 3 Execution Summary
- Stage 3.1:
- Completed. Implemented Capability 1 request/result profile (`browser.open_raise`) and standardized metadata/reason usage.
- Stage 3.2:
- Completed. Implemented browser provider chain (`windows`, `linux_wayland`, `linux_x11`, `generic`) with Wayland open-only baseline.
- Stage 3.3:
- Completed. Migrated Analysis button path to capability facade and preserved fallback/error status behavior.

### Tests Run For Phase 3
- `source .venv/bin/activate && python -m pytest tests/test_browser_capability.py tests/test_browser_capability_integration.py tests/test_browser_utils.py`
- Result: passed.

### Phase 4 Execution Summary
- Stage 4.1:
- Completed. Executed targeted matrix and full headless suite including harness smoke.
- Stage 4.2:
- Completed (skipped manual GUI check in this environment). Reason: EDMC GUI runtime/manual desktop interaction is unavailable in this headless execution context.
- Stage 4.3:
- Completed. Recorded rollout guidance and troubleshooting boundaries in this plan (best-effort behavior, Wayland baseline, reason-code diagnostics).

### Tests Run For Phase 4
- `source .venv/bin/activate && python -m pytest tests/test_capability_contracts.py tests/test_capability_resolver.py tests/test_capability_dispatcher_async.py tests/test_capability_provider_health_probe.py tests/test_browser_capability.py tests/test_browser_capability_integration.py tests/test_browser_utils.py tests/test_harness_smoke.py`
- Result: passed.
- `source .venv/bin/activate && python -m pytest`
- Result: passed (35 tests).

### Phase 5 Execution Summary
- Stage 5.1:
- Completed. Added concrete onboarding checklist deliverable for future capabilities.
- Stage 5.2:
- Completed. Added provider/resolver contribution guardrails to prevent platform-branching drift.
- Stage 5.3:
- Completed. Added prioritized follow-up backlog model (`P1`-`P4`).

### Tests Run For Phase 5
- None (documentation/process phase).
- Result: completed; no additional runtime code changes required in this phase.
