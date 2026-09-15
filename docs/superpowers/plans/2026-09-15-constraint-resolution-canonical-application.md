# Constraint Resolution Canonical Application Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a policy-authorized, source-run-bound, batch-only production edge
from retained constraint-resolution records to one ordinary canonical revision.

**Architecture:** A new admission module validates one persisted resolution
batch completely, compiles ordinary authoritative-parameter ADD operations, and
uses the existing source run's `RunController` and `ChangeEngine`. Existing
dependency logic records the parameter paths with zero impacted nodes; replay
uses ordinary run events and canonical/invalidation facts, never a recovery
store or another mutation.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, JSON/YAML repository
configuration, `python -m pytest`.

## Global Constraints

- Design authority: `docs/superpowers/specs/2026-09-15-constraint-resolution-canonical-application-design.md`.
- Do not restore any F10-retired workflow/application/provenance/recovery
  component, `_anchor_for`, `mechcad-resolution`, or compatibility shim.
- `ConstraintRequestMaterializer.anchor_for(...)` is the sole target mapping.
- Preserve `AuthoritativeParameter`/`DesignState` wire and hash semantics;
  `source_resolution_id` remains the sole canonical resolution provenance ID.
- Support all retained keys in implementation; explicit policy chooses an
  allowed subset and absence of policy denies all.
- A supplied policy is immutable and project-bound; positive tests use only
  explicit synthetic test-local resolver identities. Do not invent a real
  production resolver identity or global production allow-list.
- One persisted command is one atomic first-application unit; never apply one
  resolution at a time or directly mutate state.
- Do not modify dependency models, graph, storage, or `config/dependencies.yaml`.
  Empty dependency impact is correct for this capability.
- Preserve output-speed admission without staling `analysis.transmission.torque`.
- M12 scalar authority and MINI implementation/restart are out of scope.
- Use `apply_patch` for edits. Do not commit, push, edit accepted audits,
  normative architecture, capability inventory, F10 artifacts, or MINI files.

---

## Planned File Changes

### Create

- `src/mechcad_harness/changes/constraint_resolution_admission.py`: immutable
  policy, parser, validated batch compiler/admission service, and replay checks.
- `tests/unit/test_constraint_resolution_admission.py`: policy, lookup,
  compiler, validation, and replay unit coverage.
- `tests/integration/test_constraint_resolution_canonical_admission.py`:
  composed N -> N+1, reload, zero-impact, and torque-currentness coverage.

### Modify

- `src/mechcad_harness/agents/constraint_resolution.py`: minimal project-wide
  fail-closed persisted resolution lookup only.
- `src/mechcad_harness/runs/controller.py`: optional deterministic
  `changeset_id` forwarding only.
- `src/mechcad_harness/application.py`: policy composition and narrow batch API.
- `config/ownership.yaml`: authorize only
  `/authoritative_parameters/* -> mechcad-authority-admission`.

### Do Not Modify

- `src/mechcad_harness/models/design.py`
- `src/mechcad_harness/changes/operations.py`
- `src/mechcad_harness/changes/engine.py`
- `src/mechcad_harness/dependency/models.py`
- `src/mechcad_harness/dependency/graph.py`
- `src/mechcad_harness/dependency/storage.py`
- `config/dependencies.yaml`
- F10, MINI, M12, accepted audit, architecture, and capability-inventory files

### Task 1: Baseline and retained-capability characterization

**Files:** No edits. Test: existing request, resolution, dependency, run,
state/change/ownership, and transmission-roundtrip suites.

**Reuses:** Current retained M6B-4A models/materializers, ChangeEngine,
RunController, and DependencyGraph.

- [ ] Verify `git rev-parse HEAD`, read `AGENTS.md`, and record dirty paths
  without modifying them.
- [ ] Run `python -m pytest tests/unit/test_constraint_requests.py tests/unit/test_constraint_resolution.py tests/unit/test_dependency.py tests/unit/test_runs.py -q`.
- [ ] Run the current state/change/ownership tests and applicable transmission
  round-trip tests after identifying their exact filenames.
- [ ] Search for every F10-retired symbol and `mechcad-resolution`; classify any
  nonhistorical source match before implementation.

**Stop condition:** Stop if HEAD requires reconciliation, an F10-retired
consumer is required by the proposed route, or current generic tests expose a
contract contradiction.

### Task 2: Admission policy and deny-all composition

**Files:** Create `changes/constraint_resolution_admission.py`; modify
`application.py`; test `test_constraint_resolution_admission.py`.

**Reuses:** `SupportedConstraintKey`, existing model base class, and explicit
configuration composition patterns.

- [ ] Write tests that an absent policy denies every batch; malformed policy is
  rejected during composition; a synthetic test-local policy with the exact
  application project allows only its listed resolver type/id/scope/keys; a
  policy for another project and an enum-present but unlisted key are denied.
- [ ] Run those tests and confirm they fail before policy implementation.
- [ ] Implement frozen `ConstraintResolutionAdmissionPolicy` and rule models,
  a narrow file loader, exact matching, and production composition with an
  optional policy path whose absence creates deny-all policy.
- [ ] Permit an explicit caller-supplied policy path/config only after exact
  project binding validation. Keep the no-policy case deny-all; do not add a
  populated global config policy, environment fallback, wildcard, or resolver
  self-authorization.
- [ ] Run `python -m pytest tests/unit/test_constraint_resolution_admission.py -q`.

**Stop condition:** Stop if policy loading requires changing canonical models,
  permits resolver self-authorization, or creates an implicit allow path.

### Task 3: Fail-closed project-wide resolution lookup

**Files:** Modify `agents/constraint_resolution.py`; test
`test_constraint_resolution_admission.py`.

**Reuses:** `ConstraintResolutionStore`, `RunStore`,
`ConstraintResolutionRecord`, and `canonical_record_equivalent`.

- [ ] Write tests for exactly-one project-wide resolution ID lookup, no match,
  duplicate equivalent records, duplicate non-equivalent records, malformed
  matching record, and foreign-project record.
- [ ] Run the focused lookup tests and confirm the new lookup is absent.
- [ ] Add only a read-only store method that scans ordinary persisted
  resolution records across the named project's runs and returns exactly one
  validated record or raises a typed/fail-closed error.
- [ ] Add a source-request conflict lookup used by admission to reject a later
  accepted conflicting record across runs.
- [ ] Run `python -m pytest tests/unit/test_constraint_resolution.py tests/unit/test_constraint_resolution_admission.py -q`.

**Stop condition:** Stop if the solution requires a second provenance database,
  canonical run locator, or silently skips malformed persisted records.

### Task 4: Deterministic batch compiler and complete pre-mutation validation

**Files:** Modify `changes/constraint_resolution_admission.py`; test
`test_constraint_resolution_admission.py`.

**Reuses:** `ConstraintResolutionBatchCommand`, `ConstraintResolutionStore`,
`ConstraintRequestStore`, `canonical_value_for_answer`, `resolution_id`,
`parameter_id`, `AuthoritativeParameter`, and
`ConstraintRequestMaterializer.anchor_for`.

- [ ] Write failing tests for a two-record batch that produces deterministic
  proposal/ChangeSet IDs and ordered ADD operations, and for every negative
  validation: stale source, missing request, incomplete/extra resolution set,
  non-accepted record, request/record mismatch, canonical-value mismatch,
  missing canonical anchor, duplicate target, occupied target, conflicting
  source resolution, and wrong anchor. Define extra resolution as an extra
  record claiming the admitted command, and include an unrelated valid command
  record in the same run that must not cause rejection.
- [ ] Run the focused tests and confirm no compiler/service exists.
- [ ] Implement deterministic batch identity from project, source run, command,
  source revision/hash, and sorted resolution/parameter pairs. Compile exactly
  one ordinary `ChangeProposal` using actor
  `mechcad-authority-admission` and one ADD per parameter path.
- [ ] Scan only records claiming the admitted `source_command_id` and require
  their IDs to be the exact expected command-scoped set; leave unrelated valid
  command records in the same run untouched. For each derived anchor, require
  exactly one matching source requirement or constraint before `parameter_id`.
  Reject zero or duplicate matches and never create an anchor.
- [ ] Validate all command/run/request/task/record/policy/project-wide facts
  before returning a compilable first-application result. Require the source
  run active binding, current canonical pointer, and reloaded source snapshot
  hash to equal the command binding; retain the manifest only for project/run
  identity and original run provenance. Include a first-application rejection
  when active binding differs and a positive later-command-in-the-same-run case
  binding to a later active revision. Never copy the anchor map.
- [ ] Run `python -m pytest tests/unit/test_constraint_resolution_admission.py -q`.

**Stop condition:** Stop if validation cannot complete before mutation, requires
  an operation/ChangeSet schema field, or causes a duplicate key-to-anchor map.

### Task 5: Deterministic ChangeSet forwarding and ownership

**Files:** Modify `runs/controller.py`, `config/ownership.yaml`; test
`test_runs.py` and `test_constraint_resolution_admission.py`.

**Reuses:** `RunController.apply_approved_proposal`,
`ChangeEngine.apply_proposal(..., changeset_id=...)`, and `OwnershipPolicy`.

- [ ] Write a failing run test proving an optional supplied ChangeSet ID reaches
  the normal invalidation record unchanged, while existing calls retain their
  behavior.
- [ ] Add only keyword-only `changeset_id: str | None = None` to
  `apply_approved_proposal` and forward it to ChangeEngine.
- [ ] Add the single authority-admission ownership rule; do not add
  `mechcad-resolution`.
- [ ] Run `python -m pytest tests/unit/test_runs.py tests/unit/test_constraint_resolution_admission.py -q`.

**Stop condition:** Stop if forwarding requires recovery changes, application
transactions, or alteration of ChangeEngine/operation/ChangeSet models.

### Task 6: Admission service, source-run events, and exact replay

**Files:** Modify `changes/constraint_resolution_admission.py`; test
`test_constraint_resolution_admission.py`.

**Reuses:** source `RunStore.append_event`, `RunController`, compiled proposal,
ordinary invalidation record, and current source-binding checks.

- [ ] Write failing tests that first application appends one prepared event
  before mutation, then creates one N+1 revision without a custom applied
  event; exact replay performs no second ChangeEngine call; duplicate prepared
  event, conflicting prepared payload, partial parameter state, missing
  invalidation, wrong changed paths, or wrong ChangeSet ID fails closed.
- [ ] Implement prepared-event scanning over persisted source-run event files:
  append only when no matching identity exists, reuse one equivalent event, and
  reject multiple/conflicting events. Allow an exact prepared event at still-N
  to proceed through ordinary first application. Apply through the source run
  using the deterministic ChangeSet ID and validate the normal invalidation
  record, canonical N+1, active run state/history, and existing
  `REVISION_ADVANCED` evidence where available.
- [ ] Implement read-only replay verification requiring the complete durable
  chain before returning the original result. Do not selectively resume or
  mutate during replay.
- [ ] Preserve existing post-apply blocked/no-rollback behavior; surface an
  incomplete post-apply chain as failure rather than repairing it.
- [ ] Run `python -m pytest tests/unit/test_constraint_resolution_admission.py tests/unit/test_runs.py -q`.

**Stop condition:** Stop if replay needs a receipt/preparation store, creates
N+2, automatically rolls back, or automatically repairs post-apply state.

### Task 7: Production API and composed first-application path

**Files:** Modify `application.py`; test
`test_constraint_resolution_canonical_admission.py`.

**Reuses:** `ProductionApplication.create`, composed policy/admission service,
and source-run `RunController`.

- [ ] Write an integration test that materializes a source-bound multi-answer
  command, composes `ProductionApplication` with explicit policy, calls
  `admit_constraint_resolution_batch(resolution_run_id, command_id)`, and
  asserts one N+1 state with all typed parameters and exact source-resolution
  IDs.
- [ ] Implement only the narrow production method and composition dependency;
  expose no one-record admission API or direct mutation primitive.
- [ ] Reload a fresh `ProductionApplication` and assert exact batch replay
  returns the existing result without N+2.
- [ ] Run `python -m pytest tests/integration/test_constraint_resolution_canonical_admission.py -q`.

**Stop condition:** Stop if composition bypasses RunController, uses a new run,
or hides policy configuration.

### Task 8: All-seven-key, zero-impact, and torque-currentness regressions

**Files:** Modify both new admission test modules only.

**Reuses:** all retained typed answer/value conversions, existing
`DependencyGraph`, `EvidenceStore`, and torque tool Evidence.

- [ ] Add parameterized admission tests for every retained key under an
  explicitly authorizing policy. Assert canonical parameters have deterministic
  IDs, normalized anchors, typed values, and source-resolution IDs.
- [ ] Add a multi-key test asserting the normal invalidation record has all
  authoritative-parameter paths and empty direct/transitive node tuples.
- [ ] Seed pre-existing `analysis.transmission.torque` Evidence, admit only
  output angular speed, and assert freshness remains `CURRENT`.
- [ ] Run `python -m pytest tests/unit/test_dependency.py tests/unit/test_constraint_resolution_admission.py tests/integration/test_constraint_resolution_canonical_admission.py -q`.

**Stop condition:** Stop if a test requires adding a dependency rule, broad
transmission invalidation, semantic selector machinery, or an invented Evidence
consumer.

### Task 9: Negative integration, reload, and post-apply failure proof

**Files:** Modify `test_constraint_resolution_canonical_admission.py`.

**Reuses:** policy, project-wide lookup, RunController blocked transitions, and
fresh application composition.

- [ ] Add integration cases for deny-all, wrong-project policy, unauthorized resolver, malformed or
  missing source run, stale source, incomplete/extra batch, conflicting and
  project-wide duplicate resolution IDs, wrong anchor/value, occupied target,
  missing replay provenance, and partial replay state.
- [ ] Inject the existing post-apply invalidation-persistence failure seam;
  assert canonical N+1 remains, the source run is blocked, and a later call
  fails closed rather than creating N+2 or repairing history.
- [ ] Restart composition after a successful first application and after each
  durable failure fixture to prove reload-based behavior.
- [ ] Run `python -m pytest tests/integration/test_constraint_resolution_canonical_admission.py tests/unit/test_runs.py -q`.

**Stop condition:** Stop if a negative condition mutates canonical state before
complete validation or tests rely on fixture-only bypasses of persisted records.

### Task 10: Regression, documentation decision, and audit handoff

**Files:** No capability inventory change by default; later completion report
only when separately authorized.

**Reuses:** all predecessor suites and static checks.

- [ ] Run fresh focused predecessors:
  `python -m pytest tests/unit/test_constraint_requests.py tests/unit/test_constraint_resolution.py tests/unit/test_dependency.py tests/unit/test_runs.py -q`.
- [ ] Run current state/change/ownership tests, new policy/service tests, new
  production integration tests, and relevant transmission round-trip tests.
- [ ] Run broader regressions selected from every touched generic surface.
- [ ] Run `python -m compileall -q src` and `git diff --check`.
- [ ] Decide whether `docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md`
  merits an update only after implementation truth and fresh verification exist;
  do not update it during this planning wave.
- [ ] Prepare a completion report with exact commands/results, capability
  classification, scope limits, zero-impact and torque evidence, known
  post-apply boundary, and an independent-audit handoff request.

**Stop condition:** Stop and report if any required gate fails, any protected
surface changed, fresh proof is missing, or the implementation would be
misrepresented as independently accepted.
