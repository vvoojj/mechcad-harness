# F12 Canonical Multi-Joint Application Capability Design

## Status

Design/specification only. This document authorizes no implementation plan,
production or test modification, audit/map modification, reconstruction change,
F21 work, commit, push, or release.

```text
F12_DESIGN_BOUNDARY = APPROVED
F12 = SUPPORTED_APPLICATION_CAPABILITY
F12_CURRENT_ONLY = YES
HISTORICAL_REPLAY_IN_SCOPE = NO
```

## Problem

M13-3 established an independently executable, fresh canonical multi-joint M10
replay. It rebuilds canonical physical semantics, fresh canonical CAD, a fresh
physical-to-M10 v2 bridge, and a fresh v2 collision-sweep request without
candidate analysis objects. The real service is composed by
`ProductionApplication`, but it has no application-level entrypoint and no
production caller. F12 makes that existing capability explicitly callable at the
product boundary without changing M10 semantics or promotion behavior.

Candidate multi-joint evaluation is insufficient for this purpose. A candidate
request/result is source-bound noncanonical authority. Once a mechanism is
canonical, its verification must be replayed from canonical state rather than
reusing candidate M10 data.

## Binding HITL Decision

The human product/architecture owner selected
`SUPPORTED_APPLICATION_CAPABILITY` with these binding constraints:

- Invocation is explicit.
- Verification never auto-runs during promotion.
- Canonical replay remains fresh and candidate-free.
- Existing M10-v2 request, result, and hash contracts remain unchanged.
- The application delegates to the existing
  `CanonicalMultiJointM10VerificationService`; it does not create a second
  verifier.
- `ProductionApplication` is thin orchestration only.
- The F12 public API accepts `mechanism_id` only. It does not accept a caller
  supplied revision or state hash.
- Historical canonical replay is a distinct future capability and is outside
  F12. It must not be silently added through F12.

## Baseline And Current Evidence

This design was inspected at `69c11dc809fe8622d371f891bc7b5216aa1875d2`
(`docs(p3): record human-in-the-loop triage decisions`). That P3 artifact
records F12 as composed and integration-tested but not reachable through an
application API, and records the binding decision above. Pre-existing modified
and untracked worktree material is unrelated and outside this design.

The accepted historical boundaries are informative, not overrides of current
code:

- M13-3 established the shared physical-to-M10 v2 lowering and fresh,
  candidate-free canonical replay.
- M13-4 established explicit promotion and durable promotion Evidence, but does
  not make canonical multi-joint replay an automatic promotion action.
- The current ownership map identifies F12 as the composed-but-unused
  `CanonicalMultiJointM10VerificationService`.

## Current Call Graph

Current construction occurs once in `ProductionApplication.__init__`:

```text
ProductionApplication.create(...)
  -> ProductionApplication.__init__(...)
    -> CanonicalPhysicalMechanismCompiler(state_manager, artifact resolver)
    -> CanonicalPhysicalCadCompiler(artifact resolver)
    -> CanonicalMultiJointM10VerificationService(self)
       assigned to canonical_multi_joint_m10_verification_service
```

There is no current `src/` caller of the composed service. The M13-3 and M13-4
acceptance/integration tests directly invoke the composed attribute after
separately reconstructing canonical mechanism authority and realizing canonical
CAD:

```text
test/acceptance setup
  -> reconstruct_promoted_mechanism(revision, state_hash, mechanism_id)
  -> canonical_cad_compiler.realize(reconstruction)
  -> canonical_multi_joint_m10_verification_service.execute(reconstruction, cad)
```

The current service path is:

```text
CanonicalMultiJointM10VerificationService.execute(reconstruction, cad)
  -> validate/copy CanonicalMechanismReconstruction and CanonicalCadRealization
  -> require exactly one canonical multi-joint verification obligation
  -> PhysicalToM10V2BridgeCompiler.compile_canonical(reconstruction, cad)
  -> validate canonical configurations against the fresh bridge/model
  -> construct MultiJointCollisionSweepRequestV2
  -> ProductionApplication._execute_candidate_v2_sweep(...)
  -> analyze_multi_joint_collision_sweep_v2(...)
  -> _analyze_multi_joint_collision_sweep_v2(...)
  -> trusted M10-v2 provider and result validation
  -> _record_multi_joint_collision_sweep_provenance(...)
  -> CanonicalMultiJointM10Verification
```

The internal helper name `_execute_candidate_v2_sweep` is an existing trusted
tolerance adapter. Its use by canonical replay preserves the accepted M13-3
execution path; it does not confer candidate authority on the replay.

## Existing Inputs, Results, And Persistence

`CanonicalPhysicalMechanismCompiler.reconstruct(project_id, revision,
state_hash, mechanism_id)` loads one exact canonical state revision, verifies
the revision/hash binding, resolves exactly one mechanism, verifies trusted STEP
sources, and returns `CanonicalMechanismReconstruction`. The canonical mechanism
owns the sole `CanonicalMultiJointVerificationObligation`, including the exact
ordered configurations and collision tolerances.

`CanonicalPhysicalCadCompiler.realize(reconstruction)` creates a fresh
`CanonicalCadRealization`. It binds project, revision, state hash, mechanism and
mechanism hash, mappings, source provenance, request identity, assembly hash,
and realization hash.

The service derives the M10-v2 model, exact pair scope, and request from those
fresh canonical inputs. It returns `CanonicalMultiJointM10Verification`, which
currently contains only the v2 `request` and `result`. The request/result bind
the fresh assembly/model/request identity, but do not by themselves expose the
canonical revision, state hash, or mechanism identity.

The existing v2 execution path publishes idempotent Evidence:

```text
kind = analysis.multi_joint_collision_sweep
id = EVD-MJCS-<sha256(request_hash + result_hash) prefix>
revision = captured source revision
state_hash = captured source state hash
input_hash = request hash
output_hash = result hash
```

This Evidence is execution provenance. It is not a canonical M10 result store,
does not carry promotion authority, and is the only Evidence side effect F12
retains.

## Proposed Application Boundary

Add one additive public Python API on `ProductionApplication`:

```python
def verify_current_canonical_multi_joint_m10(
    self,
    *,
    mechanism_id: str,
) -> CanonicalMultiJointM10Verification: ...
```

`mechanism_id` is a required nonblank canonical physical-mechanism identifier.
It is the sole caller-supplied canonical locator/selector. The captured
`DesignState` snapshot is the sole canonical engineering authority. The method
has no candidate, candidate CAD,
candidate bridge, candidate request/result/evaluation/selection, promotion
receipt, v2 request, configuration, tolerance, revision, state hash, CAD, run,
artifact-store, or Evidence input.

The method is explicit: no application flow calls it implicitly, and promotion
does not call it directly or indirectly. The current
`promote_selected_multi_joint_candidate()` route remains unchanged.

### Snapshot Rule

At invocation start, the method calls `ProductionApplication.load_state()`
exactly once and captures its trusted `ProductionStateBinding`. The captured
binding supplies the sole `revision` and `state_hash` for the entire invocation.

```text
mechanism_id
  -> one load_state()
  -> captured (project_id, revision, state_hash)
  -> reconstruct_promoted_mechanism(revision, state_hash, mechanism_id)
  -> canonical_cad_compiler.realize(reconstruction)
  -> canonical_multi_joint_m10_verification_service.execute(reconstruction, cad)
  -> CanonicalMultiJointM10Verification
```

The method must not reload the current pointer, mix records from a later or
earlier revision, select a newer revision, retry, or start a second verification
because the current pointer advances during execution. A completed result remains
valid for its captured revision/state hash. Ordinary Evidence/currentness logic
may later classify it as no longer current after a new canonical revision, but
F12 does not alter that logic.

### Return Identity

The existing `CanonicalMultiJointM10Verification` type lacks enough canonical
identity for a public application return. F12 therefore extends that existing
transient type rather than introducing a wrapper, a persisted F12 result, or a
new M10-v2 schema. The application result must expose and validate at least:

```text
project_id
revision
state_hash
mechanism_id
mechanism_hash
canonical_cad_realization_hash
normalized_projection_hash
request
result
```

The extension must validate that its project/revision/state/mechanism/mechanism
hash/projection values match the reconstructed canonical authority; that its CAD
realization hash and request source assembly hash match the fresh canonical CAD;
and that the result remains bound to the returned request. It is a transient
application result, not a replacement for `MultiJointCollisionSweepRequestV2`
or `MultiJointCollisionSweepResultV2`.
This is necessary to make the returned value unambiguously identify the verified
canonical snapshot and mechanism. It does not add a v2 wire format, alter a v2
request/result hash payload, add an F12 hash, or create a result store.

## Authority And Trust Boundaries

- `DesignState` at the captured current revision is the only canonical authority.
- `mechanism_id` selects one mechanism from that exact state; absent or ambiguous
  selection fails closed.
- `CanonicalPhysicalMechanismCompiler` remains the owner of reconstruction and
  source verification.
- `CanonicalPhysicalCadCompiler` remains the owner of canonical CAD realization.
- `CanonicalMultiJointM10VerificationService` remains the sole owner of fresh
  bridge compilation, obligation cardinality/configuration validation, M10-v2
  request construction, and request/result binding validation.
- The application method sequences existing owners and validates only the
  root-level input/snapshot/result identity needed for its public contract. It
  must not recreate lowering, request construction, provider execution, or
  semantic verification logic.
- Candidate result authority is prohibited. Candidate M10 results may support
  candidate evaluation/selection, but are never input to this canonical replay.
- Canonical obligation authority comes only from
  `CanonicalPhysicalMechanism.multi_joint_verification_obligations` in the
  captured reconstructed mechanism. F12 accepts no caller-authored obligation.

## Error And Idempotency Contract

The method fails closed with the existing relevant exception family or a
root-level integrity/value error for:

- blank, missing, or ambiguous canonical `mechanism_id`;
- invalid current-state pointer or state-hash binding;
- canonical authority unavailable or mismatched against the captured invocation
  snapshot;
- invalid/missing trusted geometry source or canonical CAD realization;
- zero or multiple canonical multi-joint obligations;
- configuration/joint-key/limit mismatch against the fresh bridge;
- unavailable trusted v2 execution adapter/provider failure; and
- fresh request/result, assembly, model, CAD, or returned canonical-identity
  binding mismatch.

There is no fallback to candidate data, no inference of a configuration or
tolerance, and no historical lookup fallback.

A later current-pointer advance after snapshot capture is not an F12 failure.
The result remains valid for the captured revision/state hash and may later be
classified as non-current by ordinary currentness logic.

The method does not mutate `DesignState`, create a proposal, select a candidate,
promote a candidate, publish a promotion artifact, or change a run. Repeated
calls may execute the trusted sweep again. For identical request/result identities
the existing Evidence publication remains idempotent; a pre-existing mismatched
Evidence record fails closed. F12 itself has no additional idempotency record.

## M10-v1/v2 Compatibility

F12 is strictly a consumer of the existing M10-v2 discrete collision-sweep
contract. It continues to use:

- `MultiJointCollisionSweepRequestV2` with
  `multi-joint-collision-sweep-request@2`;
- `MultiJointCollisionSweepResultV2` with
  `multi-joint-collision-sweep-result@2`; and
- the existing evaluator and result-hash validation.

No M10-v1 path, v1 serializer, v1 hash, v2 request payload, v2 result payload,
v2 model/FK behavior, collision algorithm, tolerance semantics, or Evidence
format changes. F12 neither introduces a second verifier nor exposes low-level
M10 request construction to application callers.

## Alternatives Rejected

| Alternative | Disposition | Reason |
| --- | --- | --- |
| Accept `mechanism_id`, `revision`, and `state_hash` | Rejected | Allows caller authority to select historical/stale state and conflicts with the current-only HITL decision. |
| Accept a typed canonical reconstruction, CAD realization, or obligation | Rejected | Exposes internal orchestration inputs, duplicates trusted derivation responsibility at callers, and weakens the product boundary. |
| Expose `canonical_multi_joint_m10_verification_service` as the public API | Rejected | Leaves a composition/test seam rather than a supported application capability. |
| Accept a candidate M10 result, candidate evaluation, or promotion receipt | Rejected | Candidate authority cannot supply canonical replay inputs. |
| Invoke canonical replay automatically from promotion | Rejected | Violates explicit invocation and no-auto-promotion requirements. |
| Reimplement bridge/request/execution logic in `application.py` | Rejected | Creates a second verifier and risks diverging M10-v2 semantics. |
| Add F12-specific Evidence, artifact manifest, or result store | Rejected | Existing collision-sweep Evidence already records execution provenance; F12 adds no durable result authority. |
| Add historical replay through optional revision/state parameters | Rejected | Historical replay has separate trust, Evidence, and compatibility concerns and requires a future explicit design. |

## AZ/EL Rotator Architecture Check

An AZ/EL rotator is represented as a canonical physical mechanism with at least
two linked revolute physical-joint bindings: azimuth from the root body to the
elevation support and elevation from that support to the payload body. The
canonical mechanism persists one canonical multi-joint obligation with an
ordered configuration set whose commands contain both stable physical-joint
identifiers.

An explicit caller invokes:

```python
verification = application.verify_current_canonical_multi_joint_m10(
    mechanism_id="az-el-rotator",
)
```

The method captures one current canonical snapshot, reconstructs only that
mechanism, realizes fresh CAD, lowers the linked two-joint tree to the existing
v2 model, and verifies the complete supplied combined AZ/EL configuration set.
The discrete result retains `continuous_path_verified = False`; a continuous
claim would require the separately bounded explicit M10-4 path capability.

No candidate result, candidate bridge, candidate configuration request, or
candidate CAD object is read. The rotator is an architecture validation example
only; F12 adds no rotator-specific production behavior, mechanism template, path
planner, configuration-space certification, or automatic synthesis.

## Non-Goals

- Historical canonical replay.
- Automatic replay on promotion or any other lifecycle event.
- Candidate generation, evaluation, selection, or promotion changes.
- Multi-objective or multi-obligation verification.
- M10-v1/v2 redesign, generic trajectory planning, or whole
  configuration-space certification.
- New CAD, collision, FK, Evidence, artifact, result-store, or persistence
  subsystem.
- M11/structural analysis, F21 work, or rotator-specific behavior.

## Compatibility Invariants

- The method is additive public Python API surface on `ProductionApplication`.
- Existing direct composed-service use remains available during transition.
- `CanonicalMultiJointM10Verification` is extended only as required to make the
  application return canonically identifiable; it remains transient and does
  not alter M10-v2 request/result contracts.
- Existing candidate and promotion APIs, including explicit multi-joint
  promotion, retain their signatures and behavior.
- Exactly one canonical obligation remains required; F12 does not select among
  multiple obligations.
- Candidate-free fresh replay and existing `analysis.multi_joint_collision_sweep`
  Evidence behavior remain unchanged.

## Verification Strategy

Implementation work, if later approved, should add focused tests that prove:

- the public method accepts only `mechanism_id` and captures `load_state()` once;
- reconstruction, CAD, request/result, and returned identity all bind to that
  snapshot;
- a concurrent newer revision does not trigger a reload, retry, or second run;
- missing/ambiguous mechanism, invalid state, CAD unavailable or mismatched
  against the captured snapshot, invalid obligation cardinality, and
  result-binding failures fail closed;
- candidate objects/results are neither required nor accepted;
- promotion does not auto-invoke F12;
- existing v2 request/result bytes and hashes remain unchanged;
- no F12-specific Evidence/artifact/result store is created and existing sweep
  Evidence remains idempotent; and
- a two-revolute-joint AZ/EL-style canonical mechanism replays a combined
  configuration set through fresh candidate-free canonical authority.

Required regression gates should include the focused F12 tests plus existing
M13-3 fresh-canonical replay, M13-3P v1/v2 compatibility, M13-4 promotion
composition, and relevant M10-v2 provenance tests. Live CAD/solver execution is
not authorized by this design document.

## Acceptance Criteria

- One explicit current-only `ProductionApplication` entrypoint is specified with
  `mechanism_id` as its sole caller-supplied canonical locator/selector and the
  captured `DesignState` snapshot as its sole canonical engineering authority.
- One `load_state()` snapshot supplies revision/state hash for the full call.
- No mid-call current-pointer reload, automatic retry, or revision mixing occurs.
- The application delegates to the existing canonical multi-joint verification
  service and does not create a second verifier.
- The returned verification exposes validated canonical snapshot/mechanism/CAD
  identity in addition to the existing v2 request/result.
- No candidate result authority is accepted or consumed.
- Promotion never auto-runs canonical multi-joint replay.
- Existing M10-v2 request/result/hash and sweep-Evidence behavior remain
  unchanged.
- The AZ/EL two-joint example is supported as canonical replay architecture only.
- Historical replay remains explicitly out of scope.

```text
F12_DESIGN_STATUS = READY_FOR_IMPLEMENTATION_PLANNING_AFTER_USER_REVIEW
```
