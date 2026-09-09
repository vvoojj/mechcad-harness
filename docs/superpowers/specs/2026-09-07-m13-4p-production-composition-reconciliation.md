# M13-4P Production Composition Reconciliation

## Status

**Disposition: `M13_4P_NARROW_COMPOSITION_WIRING_REQUIRED`.**

This specification freezes only the additive production-composition work that
may follow accepted M13-4E. It authorizes no M13-4 acceptance, Rotator V2,
M10/CAD/M11/M13-3 semantic change, schema change, dependency change, commit,
tag, push, or release.

```text
M13_4P_GAP_CLASSIFICATION = M13_4P_NARROW_COMPOSITION_WIRING_REQUIRED
M13_4_MAY_RESUME = NO
ROTATOR_V2_MAY_RESUME = NO
```

## Input Authority

- `docs/audit/MECHCAD_M13_4E_R12_INDEPENDENT_REAUDIT.md` establishes
  `M13_4E_INDEPENDENT_R12_ACCEPTED` and authorizes M13-4P only.
- `docs/superpowers/specs/2026-09-06-m13-4p-multi-joint-production-composition.md`
  records the historical production-composition blocker.
- `docs/superpowers/specs/2026-09-06-m13-4e-multi-joint-promotion-evidence-contract.md`
  is the accepted typed decision, application, and result-evidence authority.
- `docs/superpowers/specs/2026-09-06-m13-4-representative-live-full-stack-capstone.md`
  remains blocked pending this reconciliation and independent audit.

The prior M13-4P blocker specification is not an implementation plan. No
accepted post-M13-4E M13-4P implementation plan existed before this document.

## Current Route And Gaps

The actual production root is `ProductionApplication.create()` and
`ProductionApplication`.

```text
ProductionApplication.evaluate_candidate_multi_joint_m10()
  -> CandidateMultiJointM10EvaluationService.execute()
  -> _execute_candidate_v2_sweep()
  -> analyze_multi_joint_collision_sweep_v2()
  -> trusted M10 v2 result and M13-3 evaluation
  -> GAP A: no production multi-joint selection entry
  -> GAP B: no public typed M13-4E multi-joint promotion entry
  -> GAP C: no root-level M13-4E receipt verifier delegation
```

M13-4E supplies the accepted private route from a
`CandidateMultiJointPromotionRequest` through readiness, the original
`CandidatePromotionCompilation`, typed decision evidence, `RunController`,
`ChangeEngine`, durable `DesignState` N+1, typed result evidence, and the full
receipt verifier. All three gaps are narrow composition wiring. The read-only
verifier-scope reconciliation confirmed that the accepted R8 bootstrap supplies
the missing scope through a trusted exact-ID project locator.

## Frozen Public Surface

Add exactly these asymmetric typed `ProductionApplication` methods:

```python
def select_candidate_multi_joint(
    self,
    candidate: MechanicalDesignCandidate,
    cad_realization: CandidateCadRealization,
    bridge: PhysicalToM10V2Bridge,
    request: CandidateMultiJointM10EvaluationRequest,
    evaluation: CandidateMultiJointM10Evaluation,
    selector_identity: str,
    rationale: str,
) -> CandidateMultiJointSelection: ...

def promote_selected_multi_joint_candidate(
    self,
    request: CandidateMultiJointPromotionRequest,
) -> CandidateMultiJointPromotionApplicationResult: ...

def verify_multi_joint_promotion_application(
    self,
    receipt: CandidateMultiJointPromotionApplicationResult,
) -> None: ...
```

The existing legacy `promote_selected_candidate(request: CandidatePromotionRequest)`
remains unchanged. It must not dispatch over a union, receive a multi-joint
request, or return a multi-joint receipt.

The methods intentionally have different inputs. CAD realization and bridge are
required only for the independent physical replay at selection. Promotion
starts only from the accepted typed promotion request. Verification starts only
from the accepted typed receipt and durable dependencies.

## Selection Composition

`select_candidate_multi_joint()` owns a call-scoped trusted replay closure. It
must not retain CAD realization, bridge, reconstructed request, or replay result
on `ProductionApplication`, on a selection service, or in a new store.

```text
candidate + cad_realization + bridge + stored evaluation request
  -> CandidateMultiJointM10EvaluationService.reconstruct_m10_request()
  -> exact reconstructed request-hash check
  -> ProductionApplication._execute_candidate_v2_sweep()
  -> public analyze_multi_joint_collision_sweep_v2() path
  -> CandidateMultiJointM10Replay(request, result)
  -> unchanged CandidateMultiJointSelectionService.select()
```

The closure is passed to a call-local `CandidateMultiJointSelectionService`
configured with the root's existing `CandidateCurrentnessService`. It must use
the replayed request's assembly, model, ordered configurations, exact pair
scope, and scope tolerances when calling `_execute_candidate_v2_sweep()`.
The replayed result must bind to the reconstructed request and reproduce
`evaluation.m10_v2_result_hash`. The existing selection service remains the
owner of the exact replay/result checks and selection record construction.

No M10 result store is added. Candidate M10 Evidence remains provenance, not a
serialized result database.

## Promotion Composition

`promote_selected_multi_joint_candidate()` performs only root-level concrete
type and project binding, then delegates to an additive public typed method on
the existing `CandidatePromotionApplicationService`. That service method accepts
only `CandidateMultiJointPromotionRequest` and delegates to its accepted private
M13-4E route.

```text
CandidateMultiJointPromotionRequest
  -> validate_multi_joint_readiness()
  -> ORIGINAL compile_multi_joint() CandidatePromotionCompilation
  -> M13-4E typed decision artifact
  -> RunController
  -> ChangeProposal -> ChangeSet -> ChangeEngine
  -> durable DesignState N+1
  -> M13-4E typed result artifact and receipt
```

Neither `ProductionApplication` nor the additive service entry may accept or
construct arbitrary readiness, compilation, proposal, canonical mechanism,
mapping, projection, decision manifest, result manifest, run ID, or artifact
scope. The generic application machinery remains internal.

The original compilation returned by `compile_multi_joint()` flows unchanged.
Its compilation hash, projection hash, projection order, mapping order, and
exact candidate-instance-to-canonical-instance pairs retain the accepted M13-4E
semantics. No normalization, projection reordering, mapping-driven compilation,
or second compilation is permitted.

## Verification Composition

`verify_multi_joint_promotion_application()` is read-only and delegates to
`verify_multi_joint_promotion_application_result()` with root-owned durable
dependencies. It must not mutate state, apply a proposal, republish artifacts,
repair a manifest, infer a run, select a latest/only run, or directly glob
artifact directories.

The root creates a project-scoped locator `ArtifactStore` with a sentinel run ID
and calls its accepted public boundary:

```text
read_verified_in_project(receipt.decision_artifact_id, expected_type=JSON)
  -> exactly one strict verified EngineeringArtifact, or failure
  -> require root project and nonblank persisted artifact.run_id
  -> fresh ArtifactStore(project_id, run_id=artifact.run_id)
  -> accepted verify_multi_joint_promotion_application_result(...)
```

`read_verified_in_project()` internally enumerates project run directories, but
the caller supplies only one exact artifact ID and never selects a run. It
reuses each run-scoped strict verification boundary, rejects zero or multiple
matches, and returns persisted metadata including `run_id`. This is the exact
accepted R8 test bootstrap and the accepted M12-6 locator precedent. It is a
locator only; the M13-4E full verifier remains responsible for decision/result,
state, invalidation, and durable run verification.

The root must reject a missing locator result, a non-JSON decision artifact,
wrong project, blank run ID, or a non-multi-joint-decision namespace before
constructing the scoped store. It must not derive scope from `Run` active fields
or accept caller-supplied run/store inputs.

## Authorized Scope

Expected production changes are limited to:

- `src/mechcad_harness/application.py`: imports, composition dependency list,
  and the three typed root delegations.
- `src/mechcad_harness/candidates/promotion.py`: one additive typed public
  service delegation to the existing private M13-4E route.

Expected test changes are limited to focused M13-4P production-composition
coverage. Expected documentation changes are this specification, its plan, and
the later reconciliation report. No M13-4E semantics, M13-3 contracts, M10,
CAD, state schemas, legacy promotion records, or Rotator inputs may change.

## Test And Gate Requirements

Focused tests must enter via `ProductionApplication.create()` and use real
`StateManager`, `RunController`, `ChangeEngine`, `ArtifactStore`,
`EvidenceStore`, selection/promotion services, and M10 v2 execution. They must
observe the entry method, project/run/base binding, candidate request identity,
selected compilation identity, decision artifact ID, applied revision/hash,
result artifact ID when complete, and final status.

Required negatives are limited to composition boundaries: wrong project input,
cross-run or wrong-base evidence rejection, candidate/compilation mismatch, and
missing required composition dependency only where the implementation plan can
exercise them without duplicating M13-4E's internal adversarial matrix.

The implementation gate must include the focused M13-4P suite with zero skips,
the exact 116-test M13-4E gate, the exact 75-test M13-3/predecessor gate, the
full suite with a 6000-second-or-greater timeout, `compileall`, `git diff
--check`, and a targeted static architecture audit.

## Non-Goals And Candidate Status

This work does not start M13-4 acceptance, live FreeCAD capstone execution, or
Rotator V2. It does not make a whole-assembly FEA, manufacturing, robotics, or
configuration-space claim.

Successful implementation may establish only:

```text
M13_4P_RECONCILIATION_READY_FOR_INDEPENDENT_AUDIT
M13_4_MAY_RESUME = NO
ROTATOR_V2_MAY_RESUME = NO
```
