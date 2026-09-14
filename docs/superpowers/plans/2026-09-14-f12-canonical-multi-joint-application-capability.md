# F12 Canonical Multi-Joint Application Capability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose explicit, current-snapshot-only canonical multi-joint M10 replay through `ProductionApplication` without changing M10-v2 semantics, promotion behavior, or Evidence ownership.

**Architecture:** `ProductionApplication.verify_current_canonical_multi_joint_m10()` captures one trusted `load_state()` snapshot, reconstructs one canonical mechanism, realizes fresh canonical CAD, and delegates to the already-composed `CanonicalMultiJointM10VerificationService`. The existing transient verification result gains validated canonical snapshot/mechanism/CAD identity so the public return identifies its authority without a wrapper, new persisted result, or F12-specific Evidence.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, existing M13-3 canonical bridge/CAD services, existing M10-v2 collision sweep, existing EvidenceStore.

## Global Constraints

- Approved execution baseline: `69c11dc809fe8622d371f891bc7b5216aa1875d2`.
- Implement only F12; do not begin F21.
- Do not modify `docs/audit/**`, `docs/reconstruction/**`, production M10-v1/v2 schemas or hash payloads, promotion semantics, or rotator-specific production behavior.
- `verify_current_canonical_multi_joint_m10()` is public Python API and accepts only a nonblank `mechanism_id` keyword argument.
- `mechanism_id` is the sole caller-supplied canonical locator/selector. The one captured `DesignState` snapshot is the sole canonical engineering authority.
- At invocation start call `ProductionApplication.load_state()` exactly once. Bind reconstruction, source resolution, canonical CAD, obligation derivation, execution, Evidence, and return identity to that captured revision/state hash.
- Do not reload the current pointer, retry, or run a second verification when a newer canonical revision is created concurrently. Such a result remains valid for the captured revision/state hash and may later be non-current under ordinary currentness logic.
- The application method must delegate to the existing `CanonicalMultiJointM10VerificationService`; do not reproduce bridge lowering, v2 request construction, execution, or result verification in `application.py`.
- Candidate result authority is forbidden. The method must accept/read no candidate result, candidate request/evaluation/selection, candidate CAD, candidate bridge, or promotion receipt.
- Promotion must never auto-invoke this method.
- Preserve existing `analysis.multi_joint_collision_sweep` Evidence publication unchanged as provenance only. Do not add F12-specific Evidence, artifacts, manifests, or a result store.
- Do not commit, push, tag, or release without separate user authorization.

---

## Execution Baseline And Worktree Safety Gate

Before any implementation edit, run:

```powershell
git rev-parse HEAD
git status --short
```

The required `HEAD` is:

```text
69c11dc809fe8622d371f891bc7b5216aa1875d2
```

If `HEAD` differs, stop before implementation and report:

```text
F12_PLAN_BLOCKED_BY_BASELINE_MISMATCH
```

Do not silently rebase this plan onto a newer commit. Record every modified,
deleted, and untracked path reported by `git status --short` before the first
F12 implementation edit, and preserve all of them untouched unless a later,
separately authorized F12 task names the path.

The worktree observation at this plan revision already contains the following
pre-existing material, which is not F12 implementation scope:

```text
M  .coverage
M  .superpowers/sdd/progress.md
M  .superpowers/sdd/task-1-report.md
M  .superpowers/sdd/task-1-review-package.md
M  .superpowers/sdd/task-2-brief.md
M  .superpowers/sdd/task-2-report.md
M  .superpowers/sdd/task-3-brief.md
M  .superpowers/sdd/task-3-report.md
M  .superpowers/sdd/task-3-review-package.md
M  config/ownership.yaml
M  src/mechcad_harness/agents/__init__.py
D  src/mechcad_harness/agents/constraint_resolution_application.py
D  src/mechcad_harness/agents/constraint_resolution_workflow.py
M  src/mechcad_harness/changes/__init__.py
D  src/mechcad_harness/changes/provenance.py
M  src/mechcad_harness/state/manager.py
D  tests/unit/test_constraint_resolution_application.py
D  tests/unit/test_constraint_resolution_workflow.py
M  tests/unit/test_m7b1br_authority.py
M  tests/unit/test_m7b2a_yagi_authority.py
M  tests/unit/test_m7b2b_yagi_carrier.py
D  tests/unit/test_state_application_provenance.py
?? docs/audit/ROTATOR_V2_EPIC_01_INDEPENDENT_FINAL_CRIT_01_REREVIEW.md
?? docs/audit/ROTATOR_V2_EPIC_01_INDEPENDENT_PLAN_FINAL_REREVIEW.md
?? docs/audit/ROTATOR_V2_EPIC_01_INDEPENDENT_PLAN_REREVIEW.md
?? docs/audit/ROTATOR_V2_EPIC_01_INDEPENDENT_PLAN_REVIEW.md
?? docs/audit/ROTATOR_V2_EPIC_01_S4_PRODUCTION_GAP_ADJUDICATION.md
?? docs/superpowers/plans/2026-08-29-task-13-review-fixes.md
?? docs/superpowers/plans/2026-09-09-rotator-v2-epic-01-physical-mechanism-and-candidate-evaluation.md
?? docs/superpowers/plans/2026-09-14-f10-m6b4c-retirement.md
?? docs/superpowers/plans/2026-09-14-f12-canonical-multi-joint-application-capability.md
?? docs/superpowers/specs/2026-09-09-rotator-v2-epic-01-physical-mechanism-and-candidate-evaluation.md
?? docs/superpowers/specs/2026-09-14-f10-m6b4c-retirement-design.md
?? docs/superpowers/specs/2026-09-14-f12-canonical-multi-joint-application-capability-design.md
?? err.txt
?? projects/
?? src/mechcad-harness/
?? tests/unit/test_rotator_v2_epic_01_authority.py
?? tests/unit/test_rotator_v2_epic_01_candidate_cad.py
?? tests/unit/test_rotator_v2_epic_01_candidate_source_authority.py
?? tests/unit/test_rotator_v2_epic_01_physical_mechanism.py
```

The modified/deleted agent, provenance, and constraint-resolution paths and the
untracked F10 plan indicate F10 remediation activity in this worktree. Do not
run F12 concurrently here. Use an isolated worktree/session at the approved
baseline, or wait for an explicit baseline reconciliation. If neither is true,
stop before implementation and report the shared-worktree conflict.

---

## File Map

- Modify: `src/mechcad_harness/candidates/multi_joint_m10_bridge.py`
  - Keep the existing service as the sole verifier; extend its transient result with verified canonical identity from its existing reconstruction/CAD inputs.
- Modify: `src/mechcad_harness/application.py`
  - Import the result type and add exactly one thin current-only orchestration method.
- Create: `tests/integration/test_f12_canonical_multi_joint_application.py`
  - Exercise the public entrypoint, its snapshot rule, candidate-free behavior, Evidence reuse, and no-auto-promotion boundary.

## Task 1: Pre-Change Verification-Result Reference Census

**Files:**
- Inspect: `src/mechcad_harness/candidates/multi_joint_m10_bridge.py`
- Inspect: `src/mechcad_harness/candidates/__init__.py`
- Inspect: `src/mechcad_harness/application.py`
- Inspect: `tests/**/*.py`
- Inspect: `docs/superpowers/specs/2026-09-14-f12-canonical-multi-joint-application-capability-design.md`

**Interfaces:**
- Consumes: current `CanonicalMultiJointM10Verification` with only `request` and `result`.
- Produces: a written census decision that either permits the identity-field extension in Task 2 or stops F12 implementation.

- [ ] **Step 1: Record all pre-change type references and construction sites**

Run:

```powershell
rg -n --glob '*.py' 'CanonicalMultiJointM10Verification' src tests
```

Expected baseline census:

```text
src/mechcad_harness/candidates/multi_joint_m10_bridge.py
  class definition, service return annotation, and one service construction
src/mechcad_harness/candidates/__init__.py
  public re-export
src/mechcad_harness/application.py
  service import/composition only
tests/unit/test_m13_3_fresh_canonical_m10.py
  service-symbol existence check only
tests/integration/test_m13_3_generic_multi_joint_acceptance.py
  one direct service execution from reconstructed canonical inputs
tests/integration/test_m13_4_full_stack_acceptance.py
  direct service executions in fresh canonical restart/reload acceptance paths
```

- [ ] **Step 2: Inspect direct-service callers, serialization expectations, and compatibility coverage**

Run:

```powershell
rg -n --glob '*.py' 'canonical_multi_joint_m10_verification_service\.execute|CanonicalMultiJointM10Verification\(' src tests
rg -n --glob '*.py' 'model_dump\(|model_validate\(|json\.dumps\(' tests src/mechcad_harness/candidates/multi_joint_m10_bridge.py
pytest -q tests/unit/test_m13_3_fresh_canonical_m10.py tests/integration/test_m13_3_generic_multi_joint_acceptance.py
```

Expected: the only production construction is the existing service return; direct
service callers are acceptance/integration seams; no accepted constructor or
serialization expectation requires the two-field result payload; and the focused
M13-3 tests pass.

- [ ] **Step 3: Apply the stop gate before editing the type**

Stop implementation and report a compatibility conflict if the census discovers
an accepted direct constructor, direct-service caller, serialized payload,
public compatibility test, or external-facing contract whose behavior requires
the exact two-field `CanonicalMultiJointM10Verification` shape. Do not make
identity fields optional, do not add a wrapper as an unreviewed workaround, and
do not silently widen the accepted result contract.

Proceed to Task 2 only if the census documents no such conflict.

## Task 2: Bind Canonical Identity in the Existing Transient Result

**Files:**
- Modify: `src/mechcad_harness/candidates/multi_joint_m10_bridge.py:461-544`
- Test: `tests/unit/test_m13_3_fresh_canonical_m10.py`

**Interfaces:**
- Consumes: `CanonicalMechanismReconstruction`, `CanonicalCadRealization`, and
  the already-built `MultiJointCollisionSweepRequestV2`/result.
- Produces: `CanonicalMultiJointM10Verification` with `project_id`, `revision`,
  `state_hash`, `mechanism_id`, `mechanism_hash`,
  `canonical_cad_realization_hash`, `normalized_projection_hash`, `request`, and
  `result`.

- [ ] **Step 1: Write failing identity-binding tests**

Add focused tests that obtain the existing canonical reconstruction/CAD fixture,
execute the service, and assert all returned identity fields bind to the inputs:

```python
verification = application.canonical_multi_joint_m10_verification_service.execute(
    reconstruction, cad
)

assert verification.project_id == reconstruction.project_id
assert verification.revision == reconstruction.revision
assert verification.state_hash == reconstruction.state_hash
assert verification.mechanism_id == reconstruction.mechanism.id
assert verification.mechanism_hash == reconstruction.mechanism.mechanism_hash
assert verification.canonical_cad_realization_hash == cad.realization_hash
assert verification.normalized_projection_hash == reconstruction.normalized_projection_hash
assert verification.result.request_hash == verification.request.request_hash
```

Add intrinsic model-validation tests only for conditions knowable from the
result itself: blank required text, revision `<= 0`, malformed SHA-256 fields,
and `result.request_hash != request.request_hash`. The test must not alter a v2
request/result field or hash expectation.

Do not construct a standalone result payload with a different but well-formed
revision, state hash, mechanism ID/hash, CAD realization hash, or projection
hash and expect it to reject. The standalone result has no reconstruction or CAD
authority with which to prove those values semantically wrong.

Use the service-result assertions above for semantic source binding. Where
coverage is needed for bad reconstruction/CAD authority, invoke existing service
fail-closed tests with mismatched reconstruction/CAD inputs rather than making
the result model an omniscient authority.

- [ ] **Step 2: Run the new tests and verify they fail before implementation**

Run:

```powershell
pytest -q tests/unit/test_m13_3_fresh_canonical_m10.py -k canonical_identity
```

Expected: FAIL because the transient result does not yet expose required
canonical identity fields.

- [ ] **Step 3: Extend the existing transient model and service construction minimally**

In `CanonicalMultiJointM10Verification`, add required frozen-model fields using
the existing strict-model convention:

```python
class CanonicalMultiJointM10Verification(Model):
    """Transient fresh canonical M10 request/result pair with source identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: str = Field(min_length=1)
    revision: int = Field(gt=0)
    state_hash: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    mechanism_hash: str = Field(min_length=1)
    canonical_cad_realization_hash: str = Field(min_length=1)
    normalized_projection_hash: str = Field(min_length=1)
    request: MultiJointCollisionSweepRequestV2
    result: MultiJointCollisionSweepResultV2
```

Add model-level validation only for nonblank required fields, positive revision,
SHA-256 formatting for `state_hash`, `mechanism_hash`,
`canonical_cad_realization_hash`, and `normalized_projection_hash`, plus
`result.request_hash == request.request_hash`. Do not duplicate request or
result hash algorithms and do not compare the model's identity fields to absent
reconstruction/CAD authority. At the existing return statement, supply only
values already verified by the reconstruction/CAD/service path:

```python
return CanonicalMultiJointM10Verification(
    project_id=reconstruction.project_id,
    revision=reconstruction.revision,
    state_hash=reconstruction.state_hash,
    mechanism_id=mechanism.id,
    mechanism_hash=mechanism.mechanism_hash,
    canonical_cad_realization_hash=cad.realization_hash,
    normalized_projection_hash=reconstruction.normalized_projection_hash,
    request=request,
    result=result,
)
```

Do not add `schema_version`, an F12 result hash, persistence, Evidence, or a new
type. Do not modify `MultiJointCollisionSweepRequestV2` or
`MultiJointCollisionSweepResultV2`.

- [ ] **Step 4: Run focused result and M13-3 compatibility tests**

Run:

```powershell
pytest -q tests/unit/test_m13_3_fresh_canonical_m10.py tests/integration/test_m13_3_generic_multi_joint_acceptance.py
```

Expected: PASS. Confirm existing fresh-canonical test assertions for candidate
request-hash non-equality and result-to-request binding remain unchanged.

## Task 3: Add the Thin Current-Only Production Entry Point

**Files:**
- Modify: `src/mechcad_harness/application.py:150-199,2251-2263`
- Create: `tests/integration/test_f12_canonical_multi_joint_application.py`

**Interfaces:**
- Consumes: `ProductionApplication.load_state()`,
  `reconstruct_promoted_mechanism()`, `canonical_cad_compiler.realize()`, and
  `canonical_multi_joint_m10_verification_service.execute()`.
- Produces:

```python
def verify_current_canonical_multi_joint_m10(
    self,
    *,
    mechanism_id: str,
) -> CanonicalMultiJointM10Verification: ...
```

- [ ] **Step 1: Write failing public-entrypoint tests**

Create an integration fixture from the accepted M13-3 promotion/reconstruction
fixture that has one canonical multi-joint mechanism and a deterministic
measurement provider. Add tests for these exact behaviors:

```python
verification = application.verify_current_canonical_multi_joint_m10(
    mechanism_id=mechanism_id,
)

assert verification.revision == captured.revision
assert verification.state_hash == captured.state_hash
assert verification.mechanism_id == mechanism_id
assert verification.result.request_hash == verification.request.request_hash
assert application.get_multi_joint_collision_sweep_evidence(
    verification.result.result_hash
) is not None
```

Use `monkeypatch` spies around `ProductionApplication.load_state`,
`reconstruct_promoted_mechanism`, the canonical CAD compiler, and the composed
service to assert: one `load_state()` call; all downstream calls receive the
same captured revision/state hash; and no candidate input is accepted by the
method signature. Add parameterized invalid selector tests for `""`, a missing
ID, and an ambiguous mechanism ID, each expecting failure before M10 execution.

Add a concurrency-boundary test whose reconstruction spy advances the current
pointer only after the initial snapshot is captured. Assert the public method
still returns the original snapshot's revision/state hash, calls `load_state()`
once, and executes the sweep once. Do not assert the returned Evidence is
current after the advance.

Add a promotion-boundary test that spies on the new method while calling the
existing explicit multi-joint promotion flow; assert zero calls. Reuse the
accepted promotion fixture and do not modify promotion code.

- [ ] **Step 2: Run the new integration tests and verify they fail**

Run:

```powershell
pytest -q tests/integration/test_f12_canonical_multi_joint_application.py
```

Expected: FAIL with the public method absent.

- [ ] **Step 3: Implement the root orchestration method only**

Import `CanonicalMultiJointM10Verification` from `mechcad_harness.candidates`.
Place the method beside `reconstruct_promoted_mechanism()` and implement only
this sequence:

```python
def verify_current_canonical_multi_joint_m10(
    self,
    *,
    mechanism_id: str,
) -> CanonicalMultiJointM10Verification:
    if not isinstance(mechanism_id, str) or not mechanism_id.strip():
        raise CandidateIntegrityError("canonical mechanism ID must be nonblank")
    snapshot = self.load_state()
    reconstruction = self.reconstruct_promoted_mechanism(
        revision=snapshot.revision,
        state_hash=snapshot.state_hash,
        mechanism_id=mechanism_id,
    )
    cad = self.canonical_cad_compiler.realize(reconstruction)
    verification = self.canonical_multi_joint_m10_verification_service.execute(
        reconstruction, cad
    )
    if (
        verification.project_id != self.project_id
        or verification.revision != snapshot.revision
        or verification.state_hash != snapshot.state_hash
        or verification.mechanism_id != mechanism_id
    ):
        raise CandidateIntegrityError("canonical multi-joint verification binding mismatch")
    return verification
```

Do not call `load_state()` after `snapshot`. Do not catch provider, canonical
reconstruction, CAD, obligation, or service integrity errors merely to retry or
translate them into candidate/promotion behavior. Do not change
`promote_selected_multi_joint_candidate()`.

- [ ] **Step 4: Run public-entrypoint and predecessor tests**

Run:

```powershell
pytest -q tests/integration/test_f12_canonical_multi_joint_application.py
pytest -q tests/unit/test_m13_3_fresh_canonical_m10.py tests/integration/test_m13_3_generic_multi_joint_acceptance.py tests/integration/test_m13_4p_production_composition.py
```

Expected: PASS. The F12 tests prove exactly-one-snapshot behavior, no retry on
advance, candidate-free replay, unchanged Evidence provenance, and no
auto-invocation by promotion.

## Task 4: Protect the M10-v2 and Public-Boundary Regression Surface

**Files:**
- Modify: `tests/integration/test_f12_canonical_multi_joint_application.py`
- Inspect: `tests/unit/test_m13_3p_legacy_goldens.py`
- Inspect: `tests/integration/test_m10_3_provenance.py`

**Interfaces:**
- Consumes: the completed F12 public entrypoint and existing v2 request/result
  type contracts.
- Produces: regression coverage proving F12 does not alter M10-v2 bytes/hashes
  or Evidence behavior.

- [ ] **Step 1: Add non-regression assertions after the F12 path exists**

In the F12 integration test, compare the public method's returned request/result
with an independently constructed direct service call for the same captured
snapshot. Assert request hash, result hash, source assembly hash, model hash,
evaluator version, and Evidence input/output hashes are identical. Assert the
candidate M10 request hash is not used as the canonical request identity.

- [ ] **Step 2: Run the non-regression assertions against the completed F12 path**

Run:

```powershell
pytest -q tests/integration/test_f12_canonical_multi_joint_application.py -k 'v2 or evidence'
```

Expected: PASS. If request hash, result hash, source assembly hash, model hash,
evaluator version, or Evidence input/output identity differs from the accepted
direct-service path, stop and report:

```text
F12_PLAN_BLOCKED_BY_PROTECTED_M10_REGRESSION
```

- [ ] **Step 3: Keep the test assertion-only; make no M10/persistence changes**

The production change must remain limited to Task 2's transient identity fields
and Task 3's orchestration method. If satisfying this task requires editing any
M10 request/result/hash implementation, Evidence model/store, promotion method,
audit/map, or reconstruction record, stop and report
`F12_PLAN_BLOCKED_BY_PROTECTED_M10_REGRESSION`.

- [ ] **Step 4: Run focused protected regressions and static checks**

Run:

```powershell
pytest -q tests/integration/test_f12_canonical_multi_joint_application.py tests/unit/test_m13_3_fresh_canonical_m10.py tests/integration/test_m13_3_generic_multi_joint_acceptance.py tests/integration/test_m13_4p_production_composition.py tests/unit/test_m13_3p_legacy_goldens.py tests/integration/test_m10_3_provenance.py
python -m compileall -q src tests
git diff --check
```

Expected: all selected tests pass, `compileall` exits 0, and `git diff --check`
emits no whitespace errors. Do not run live CAD/solver verification unless a
later task explicitly authorizes it.

## Task 5: Complete Unit Regression Gate

**Files:**
- Inspect: `tests/unit/**`
- Inspect: baseline status captured by the execution safety gate

**Interfaces:**
- Consumes: the completed focused F12/M13/M10 regression results and the approved
  baseline/worktree inventory.
- Produces: a unit-suite comparison that isolates F12-caused regressions from
  unrelated baseline failures.

- [ ] **Step 1: Run the complete unit suite after focused gates pass**

Run:

```powershell
pytest -q tests/unit
```

Record the command exit status, collection status, complete pass/fail/skip
summary, and every reported failure.

- [ ] **Step 2: Compare the result to the approved baseline and scope**

Require no new F12-caused unit failure, import/collection failure, regression
from the required-field extension of `CanonicalMultiJointM10Verification`, or
regression from the new `ProductionApplication` method. If unrelated baseline
failures exist, record their exact node IDs and baseline comparison; do not widen
F12 to repair them. Do not require the full live FreeCAD/Gmsh/CalculiX suite for
this F12 plan.

## Task 6: Final Skeptical Implementation Review

**Files:**
- Inspect: `src/mechcad_harness/application.py`
- Inspect: `src/mechcad_harness/candidates/multi_joint_m10_bridge.py`
- Inspect: `tests/integration/test_f12_canonical_multi_joint_application.py`
- Inspect: `git status --short` output captured by the execution safety gate

**Interfaces:**
- Consumes: the completed implementation and all focused/unit regression output.
- Produces: an implementation-acceptance review record or an explicit blocking
  finding before F12 can be accepted.

- [ ] **Step 1: Inspect the public/application boundary and authority flow**

Verify from the diff and source that exactly one public current-only method,
`verify_current_canonical_multi_joint_m10`, was added; `load_state()` occurs
exactly once per invocation; no historical revision/state-hash parameter exists;
and no candidate object/result is accepted or consulted.

- [ ] **Step 2: Inspect verifier/result and protected-M10 boundaries**

Verify that `CanonicalMultiJointM10VerificationService` remains the sole
verifier; return identity is populated from trusted reconstruction/CAD inputs;
no second M10 implementation exists; M10-v2 request/result/hash behavior is
unchanged; and existing `analysis.multi_joint_collision_sweep` Evidence behavior
is unchanged.

- [ ] **Step 3: Inspect lifecycle, persistence, and worktree boundaries**

Verify promotion never invokes F12; no F12 persistence/result store exists; no
F21, audit/map, or reconstruction file changed; and every unrelated
modified/untracked path recorded by the execution safety gate remains untouched.
If a required assertion fails, stop implementation acceptance and report the
specific failed invariant rather than repairing adjacent scope.

## Plan Self-Review

- Spec coverage: the execution gate protects the approved baseline and unrelated
  worktree; Task 1 protects the existing transient type before extension; Task 2
  separates intrinsic model validation from service-owned semantic binding; Task
  3 supplies the one-snapshot thin public API plus candidate-free/no-promotion
  behavior; Task 4 protects M10-v2 and Evidence invariants; Task 5 provides the
  complete unit regression gate; Task 6 performs the required skeptical review.
- Scope: no task modifies F21, audit/map, reconstruction, promotion behavior,
  M10-v2 contracts, or adds persistence.
- Stop conditions: the execution gate blocks a mismatched baseline or shared F10
  worktree; Task 1 blocks incompatible result-type extension; Task 4 blocks a
  protected M10/Evidence regression; Task 6 blocks acceptance when any required
  authority, lifecycle, persistence, or worktree invariant fails.
- Placeholder scan: no incomplete implementation steps remain.
- Type consistency: Task 2 produces the exact result type returned by Task 3;
  Task 3 supplies the identity fields asserted by Task 4.
