# M13-4P Multi-Joint Production Composition

## Marker

**Disposition: `M13_4P_BLOCKED_BY_PROMOTION_EVIDENCE_SCHEMA_GAP`.**

This is a specification-only blocker disposition. It authorizes no production
code, test, M13-4E, M13-4, M10, CAD, M11, M12, M13-1, M13-2, M13-3P, or M13-3
contract change; no dependency; no commit, tag, push, or release; and no
Rotator V2 work.

M13-4P was intended to expose the accepted M13-3 multi-joint selection and
promotion path through `ProductionApplication` and the existing
`ChangeProposal -> ChangeSet -> ChangeEngine -> DesignState N+1` machinery.
The local production audit establishes that this cannot be truthfully finalized
until the separately typed promotion evidence/application boundary exists.

## Selection Composition Audit

### Current Production Composition

`ProductionApplication` is the trusted production composition root. Its
constructor composes these relevant accepted M13 services:

- `CandidateCurrentnessService` as `candidate_currentness_service`;
- `CandidateCadRealizationService` as `candidate_cad_realization_service`;
- `CandidateMultiJointM10EvaluationService` as
  `candidate_multi_joint_m10_evaluation_service`;
- `CandidatePromotionCompiler` as `candidate_promotion_compiler`; and
- `CandidatePromotionApplicationService` as
  `promotion_application_service`.

The exact existing public M13 candidate evaluation entrypoint is:

```python
ProductionApplication.evaluate_candidate_multi_joint_m10(
    self,
    candidate,
    cad_realization,
    bridge,
    request,
)
```

It calls:

```python
CandidateMultiJointM10EvaluationService.execute(
    candidate,
    cad_realization,
    bridge,
    request,
)
```

That service is composed with the application-private production callback:

```python
ProductionApplication._execute_candidate_v2_sweep(**kwargs)
```

The callback reaches the existing public production M10 v2 entrypoint:

```python
ProductionApplication.analyze_multi_joint_collision_sweep_v2(
    *,
    source_revision,
    source_state_hash,
    assembly,
    model,
    configurations,
    exact_pair_scope,
) -> MultiJointCollisionSweepResultV2
```

The candidate evaluation service reconstructs the accepted
`MultiJointCollisionSweepRequestV2` from the candidate, trusted candidate CAD
realization, trusted physical-to-M10 bridge, and replayable scope. It validates
the reconstructed M10 request hash against
`CandidateMultiJointM10EvaluationRequest.m10_v2_request_hash`, executes the
production sweep, and binds the returned `result_hash` into
`CandidateMultiJointM10Evaluation.m10_v2_result_hash`.

### Missing Selection Composition

`CandidateMultiJointSelectionService` exists with this required constructor:

```python
CandidateMultiJointSelectionService(
    *,
    project_id: str,
    currentness_verifier,
    result_replayer,
)
```

Its public operation is:

```python
CandidateMultiJointSelectionService.select(
    candidate: MechanicalDesignCandidate,
    request: CandidateMultiJointM10EvaluationRequest,
    evaluation: CandidateMultiJointM10Evaluation,
    selector_identity: str,
    rationale: str,
) -> CandidateMultiJointSelection
```

`ProductionApplication.__init__` and `ProductionApplication.create()` do not
compose this service. `ProductionApplication` has no public multi-joint
selection entrypoint. Existing M13-3 unit tests construct the service directly
with a custom trusted result replayer.

This is a real production-composition gap, but it is not the blocker that
terminates M13-4P. The required replay dependency can be truthfully composed
from existing production services without a new store, as recorded below.

No new `ProductionApplication` API is frozen by this blocker specification.
The preferred future explicit additive selection route remains an architectural
question for the later evidence-contract milestone and must not be inferred as
authorization to implement an API now.

## Trusted Result Replay Finding

### Finding

**The selection replay path is not blocked by result storage. No new M10 result
store is required.**

`CandidateMultiJointSelectionService.select()` requires its trusted
`result_replayer` to return a typed `CandidateMultiJointM10Replay` containing:

```python
CandidateMultiJointM10Replay(
    request: MultiJointCollisionSweepRequestV2,
    result: MultiJointCollisionSweepResultV2,
)
```

The service independently reconstructs and validates the returned M10 request
and result, then requires all of the following before it emits
`CandidateMultiJointSelection@1`:

- replayed request hash equals
  `CandidateMultiJointM10EvaluationRequest.m10_v2_request_hash`;
- replayed model, ordered configurations, tolerances, evaluator version, and
  exact pair-scope hash equal the accepted request chain;
- replayed result request, model, source assembly, evaluator version, and
  ordered configuration identities agree with the replayed request;
- replayed result recomputes to its own exact result hash; and
- replayed result hash equals
  `CandidateMultiJointM10Evaluation.m10_v2_result_hash`.

The existing production stack can fulfill that contract by reconstructing the
accepted discrete v2 request through
`CandidateMultiJointM10EvaluationService.reconstruct_m10_request(...)` and
independently re-executing it through the composed
`ProductionApplication._execute_candidate_v2_sweep(...)` /
`ProductionApplication.analyze_multi_joint_collision_sweep_v2(...)` path. The
new result must equal the evaluation-bound result hash. It is not permitted to
trust an in-memory evaluation result without this reconstruction and execution
check.

The ordinary M10 Evidence record is deliberately not a result database:
`Evidence(kind="analysis.multi_joint_collision_sweep")` stores the request and
result identities plus `AnalysisExecutionProvenance`, but no typed discrete
M10-3 result payload. This does not prevent trusted replay because the accepted
request is reconstructible from the M13-3 records and can be re-executed by the
existing production method. The existing Evidence lookup remains useful to
verify that trusted M10 provenance was published for a result hash; it is not
the source of a serialized result replay payload.

Any future production selection composition must use this bounded trusted
reconstruction/re-execution route, preserve all accepted M13-3 currentness and
identity checks, and introduce neither a test-only callback nor a second result
database.

## Promotion Evidence Gap

### Existing Multi-Joint Promotion Trust Path

M13-3 already provides the distinct non-mutating promotion trust path:

```python
CandidatePromotionCompiler.validate_multi_joint_readiness(
    request: CandidateMultiJointPromotionRequest,
) -> MultiJointPromotionReadiness

CandidatePromotionCompiler.compile_multi_joint(
    state,
    request: CandidateMultiJointPromotionRequest,
) -> CandidatePromotionCompilation
```

Both methods revalidate the exact multi-joint request, recheck current state
revision/hash, validate the selected multi-joint candidate/evaluation/selection
chain, and produce the existing generic `CandidatePromotionCompilation` with a
`ChangeProposal`. `compile_multi_joint()` creates the normal proposal to add
the projected `CanonicalPhysicalMechanism@3`; it does not directly mutate
state.

### Existing Application Path Is Legacy-Typed

The only public application route is:

```python
ProductionApplication.promote_selected_candidate(self, request)
```

It project-checks the request and delegates to:

```python
CandidatePromotionApplicationService.promote_selected_candidate(
    self,
    request: CandidatePromotionRequest,
) -> CandidatePromotionApplicationResult
```

That method unconditionally calls the legacy compiler operations:

```python
CandidatePromotionCompiler.validate_readiness(request)
CandidatePromotionCompiler.compile(state, request)
```

It also creates the legacy `PrePromotionM10ScopeProjection` before decision
publication. This projection encodes the legacy single-output M12 M10 scope;
exact constituent scope, physical pair-policy identity, or multi-joint
request/result chain.

The M13-3 request must instead enter:

```text
CandidateMultiJointPromotionRequest
  -> validate_multi_joint_readiness()
  -> compile_multi_joint()
  -> generic ChangeEngine application machinery
```

The required generic application machinery does exist in the legacy service:
run creation and source binding; decision and result publication; application
through `RunController.apply_approved_proposal`; invalidation persistence and
verification; run transition; and `CandidatePromotionApplicationResult` status
translation. However, its public receipt and decision inputs are legacy-typed.
The generic machinery cannot be safely reused until a truthful multi-joint
evidence/application contract is separately designed.

## Affected Legacy Records

The blocking records are all accepted legacy `@1` contracts:

### `PromotionDecisionInputReference@1`

`PromotionDecisionInputReference@1` contains legacy
`promotion_request_hash`, candidate/synthesis/admissibility hashes,
`evaluation_hash`, `selection_hash`, optional legacy comparison fields,
promotion policy, target, M11 intent, mapping identities, and classification
identities. Its fields and validations name the legacy
`CandidatePromotionRequest@1` / `CandidateEvaluation@1` /
`CandidateSelection@1` chain.

It has no fields or semantic discriminator for:

- `CandidateMultiJointPromotionRequest.request_hash`;
- `MultiJointPromotionReadiness.readiness_hash`;
- `CandidateMultiJointSelection.selection_hash` as an explicitly multi-joint
  selection identity;
- `CandidateMultiJointM10Evaluation.evaluation_hash` as an explicitly
  multi-joint evaluation identity;
- `configuration_set_hash`;
- `placement_derivations_hash`;
- `physical_pair_classification_set_hash`; or
- the exact multi-joint M10 v2 request and result hashes.

### `SelectedCandidateDecisionManifest@1`

`SelectedCandidateDecisionManifest@1` embeds
`PromotionDecisionInputReference@1` and
`PrePromotionM10ScopeProjection@1`. It therefore binds a decision to legacy
evaluation/selection and legacy single-output scope semantics. Its schema has
no multi-joint decision-reference branch and no multi-joint scope projection.

### `CandidatePromotionApplicationResult@1`

`CandidatePromotionApplicationResult@1.request` is explicitly typed as:

```python
CandidatePromotionRequest | None
```

Its receipt cannot faithfully return the request that was validated and
compiled by the M13-3 multi-joint compiler. Returning a
`CandidateMultiJointPromotionRequest` would violate its accepted schema;
converting that request to `CandidatePromotionRequest` would discard or
misrepresent the M13-3 trust chain.

### Result Manifest Consequence

`CandidatePromotionResultManifest@1` obtains its trusted decision binding by
resolving `SelectedCandidateDecisionManifest@1`. It therefore inherits the
decision-reference gap. Its `ChangeProposal`, `ChangeSet`, changed paths, and
N+1 fields are generic and reusable only after the selected decision has a
truthful multi-joint typed predecessor.

## Why Legacy Reuse Is Invalid

M13-4P must not resolve this gap by any of the following:

- overloading legacy fields;
- widening legacy schemas to an implicit "either legacy or multi-joint"
  semantics;
- runtime type dispatch inside legacy manifest records;
- putting multi-joint hashes into semantically unrelated legacy fields;
- converting `CandidateMultiJointPromotionRequest` to
  `CandidatePromotionRequest`;
- rebuilding multi-joint trust records into M12 records; or
- dropping identities from the evidence chain.

Those approaches would make the durable decision and receipt claim a legacy
trust chain while the actual compiler had consumed a different multi-joint
trust chain. They would obscure the dispatch boundary, make replay ambiguous,
and risk changing accepted M12 JSON/hashes and behavior.

The following exact M13-3 identities must remain explicit and independently
meaningful in any future promotion decision and application receipt:

- `CandidateMultiJointPromotionRequest.request_hash`;
- `MultiJointPromotionReadiness.readiness_hash`;
- `CandidateMultiJointSelection.selection_hash`;
- `CandidateMultiJointM10Evaluation.evaluation_hash`;
- candidate/source currentness binding;
- `configuration_set_hash`;
- `placement_derivations_hash`;
- `physical_pair_classification_set_hash`;
- M10 v2 request identity; and
- M10 v2 result identity.

The legacy manifest and receipt schemas cannot represent these identities
without semantic misuse. This is the final blocking condition for M13-4P.

## Required Next Architecture Step

```text
NEXT ARCHITECTURE PREREQUISITE:
    M13-4E -- Multi-Joint Promotion Evidence Contract
```

M13-4E must be a separate specification, review, implementation, and
acceptance cycle. Its future purpose is to add distinct multi-joint promotion
decision/reference evidence, a distinct multi-joint selected-decision manifest,
and a distinct multi-joint promotion application/result receipt, while
preserving all legacy schemas and hashes byte-for-byte.

M13-4E must define, before implementation:

- exact versioned models and their field/hash payloads;
- exact binding of every M13-3 identity listed in this specification;
- exact typed route from multi-joint readiness and compilation to generic
  run/ChangeEngine/invalidation/ArtifactStore publication machinery;
- exact failure translation and stale-currentness behavior; and
- exact fresh manifest/result verification rules.

It must not change M13-3 schemas or trust semantics, M10/CAD semantics, or
legacy promotion evidence semantics. It must not expose a generic public helper
that accepts an arbitrary canonical mechanism or proposal and bypasses either
promotion compiler.

## M13-4P Handoff

M13-4P production composition cannot be finalized until M13-4E is separately
specified, reviewed, implemented, and accepted.

After M13-4E acceptance, a new M13-4P reconciliation must freeze the public
production selection and multi-joint promotion entrypoints, the composed
trusted replayer, the typed multi-joint dispatch, generic application helper
boundary, evidence publication, currentness checkpoints, focused composition
tests, and legacy compatibility proof. It must then establish that:

```text
ProductionApplication
  -> accepted M13-3 selection with independent trusted replay
  -> CandidateMultiJointPromotionRequest
  -> validate_multi_joint_readiness()
  -> compile_multi_joint()
  -> typed multi-joint decision/result evidence
  -> ChangeProposal -> ChangeSet -> ChangeEngine
  -> immutable DesignState N+1
```

M13-4 remains blocked. This disposition does not resume its planning or
implementation, does not alter its acceptance requirements, and does not start
Rotator V2.

## Worktree Status

The local worktree contains unrelated pre-existing modifications and untracked
files, including `.coverage`, `.superpowers/sdd/`, historical specification and
plan files, `err.txt`, `projects/`, and `src/mechcad-harness/`. They are outside
this specification-only task and are not modified by it.

The local committed baseline includes M13-3 at `ca294e0`
(`feat: close M13-3 candidate canonical M10 bridge`). The specified M13-3
symbols and contracts were audited from the actual local worktree, not assumed
from a remote default branch.

M13_4P_BLOCKED_BY_PROMOTION_EVIDENCE_SCHEMA_GAP
