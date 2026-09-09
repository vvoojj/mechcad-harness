# M13-4E Multi-Joint Promotion Evidence Contract

## Marker

**Disposition: `M13_4E_CORRECTIVE_SPEC_PLAN_READY`.**

This is a specification-only architecture contract. It authorizes no production
code, test, M13-3 schema, M10, CAD, M11, M13-4P, M13-4, Rotator V2,
dependency, commit, tag, push, or release change.

M13-4E adds durable, typed evidence and an application receipt for the accepted
M13-3 multi-joint promotion chain. It adds neither mechanics nor authority,
selection/promotion policy, state-mutation semantics, analysis provider, result
store, or production composition API.

## Post-Implementation-Audit Reconciliation

The candidate implementation is **not accepted**. The independent audit found
that it treated two accepted M13-3 orderings as though they were one ordering:
`MultiJointPromotionReadiness.mapping` is ordered by ascending
`candidate_instance_id`, while `CandidatePromotionCompiler.compile_multi_joint()`
preserves canonical mechanism realization/projection order in
`PromotableMechanismProjection`. Reordering the latter created a second,
derived `CandidatePromotionCompilation` identity. This correction removes that
invalid positional requirement without changing any wire schema literal or any
M13-3 schema, compiler, hash, or semantics.

## Repository Evidence Audit

The local committed baseline is `ca294e0` (`feat: close M13-3 candidate
canonical M10 bridge`). The M13-3 trust path already exists and remains its
semantic owner:

```text
CandidateMultiJointM10EvaluationRequest@1
  -> CandidateMultiJointM10Evaluation@1
  -> CandidateMultiJointSelection@1
  -> CandidateMultiJointPromotionRequest@1
  -> MultiJointPromotionReadiness@1
  -> CandidatePromotionCompiler.compile_multi_joint()
  -> CandidatePromotionCompilation@1
  -> ChangeProposal -> ChangeSet -> ChangeEngine -> DesignState N+1
```

`CandidatePromotionCompiler.validate_multi_joint_readiness()` revalidates the
typed request, current source state, candidate, admissibility result,
multi-joint request/evaluation/selection chain, mappings, classifications, and
trusted geometry. `compile_multi_joint()` independently rechecks current state
and readiness before producing the existing generic
`CandidatePromotionCompilation@1` and its `ChangeProposal`.

`CandidatePromotionCompilation@1`, `ChangeProposal`, `ChangeSet`,
`ChangeEngine`, and `PromotionApplicationStatus` have genuinely generic
compilation or application semantics and may be reused unchanged. The existing
`ArtifactStore` is the durable owner of promotion manifests. The existing
`EvidenceStore` remains the durable owner of invalidation records. No second
manifest store, Evidence record family, or M10-result store is required.

The existing `ArtifactStore` publication contract is canonical JSON plus a
trailing newline, byte SHA-256 metadata, bound revision/state hash, and strict
fresh retrieval. The existing manifest pattern is typed `model_validate`,
self-hash recomputation, artifact-ID/input-hash/bound-state verification, then
fresh source verification. M13-4E retains that pattern.

## Legacy Evidence Boundary

The following accepted legacy `@1` records are immutable in wire fields,
serializers, hashes, validators, behavior, and artifact IDs:

- `PromotionDecisionInputReference@1`
- `SelectedCandidateDecisionManifest@1`
- `CandidatePromotionResultManifest@1`
- `CandidatePromotionApplicationResult@1`
- `CandidatePromotionRequest@1`
- `PromotionReadiness@1`
- `CandidateSelection@1`
- `CandidateEvaluation@1`
- all legacy M12 promotion artifacts and result-manifest consumers

`PrePromotionM10ScopeProjection@1` is legacy single-output M12 M10 scope
semantics. It is not a multi-joint projection and is not reused by M13-4E.

M13-4E uses the distinct additive family below. No legacy record gains an
optional multi-joint field, union member, discriminator, alias, or reinterpreted
field. In particular, a `CandidateMultiJointPromotionRequest` never occupies
`CandidatePromotionApplicationResult.request`.

## Multi-Joint Decision Input Reference

Add immutable, frozen, `extra="forbid"` model
`MultiJointPromotionDecisionInputReference@1` with literal
`schema_version="multi-joint-promotion-decision-input-reference@1"`.
It is the complete durable reference to the validated M13-3 decision inputs;
it is not canonical mechanism authority and it embeds none of the candidate,
CAD, M10 request/result, inventory, configuration, or placement payloads.

Its exact fields, ownership, and validation are:

| Field | Ownership | Exact source / validation |
| --- | --- | --- |
| `schema_version` | derived durable identity | Literal schema version. |
| `promotion_request_hash` | promotion identity | Equals `CandidateMultiJointPromotionRequest.request_hash`. |
| `readiness_hash` | promotion identity | Equals the exact validated `MultiJointPromotionReadiness.readiness_hash`; it is never inferred from `promotion_request_hash`. |
| `project_id` | source/currentness binding | Equals the request and readiness project ID; nonblank. |
| `source_revision` | source/currentness binding | Equals request/readiness source revision; positive integer. |
| `source_state_hash` | source/currentness binding | Equals request/readiness source state hash. |
| `source_binding_hash` | source/currentness binding | Equals request candidate source-binding hash and readiness source-binding hash. |
| `candidate_hash` | candidate semantic identity | Equals request candidate hash and readiness candidate hash. |
| `synthesis_request_hash` | candidate semantic identity | Equals request synthesis request hash and readiness synthesis request hash. |
| `synthesis_policy_hash` | candidate semantic identity | Equals request synthesis policy hash and readiness synthesis policy hash. |
| `m12_3_result_hash` | candidate semantic identity | Equals request admissibility-result hash and readiness M12-3 result hash. |
| `multi_joint_evaluation_request_hash` | analysis identity | Equals `request.multi_joint_request.request_hash`. |
| `multi_joint_evaluation_hash` | analysis identity | Equals `request.multi_joint_evaluation.evaluation_hash` and readiness multi-joint evaluation hash. |
| `multi_joint_selection_hash` | selection identity | Equals `request.multi_joint_selection.selection_hash` and readiness multi-joint selection hash. |
| `scope_hash` | analysis identity | Equals the accepted embedded multi-joint evaluation-scope hash in request, evaluation, selection, and readiness. |
| `configuration_set_hash` | analysis identity | Equals the accepted M13-3 configuration-set hash in request, evaluation, selection, and readiness. |
| `placement_derivations_hash` | analysis identity | Equals the request's placement-derivations hash. It is `None` only when the request contains the empty derivation tuple; otherwise it is a SHA-256 identity. |
| `physical_pair_classification_set_hash` | mapping/classification identity | Equals the request, evaluation, and selection physical-pair classification-set hash. |
| `m10_v2_request_hash` | analysis identity | Equals the request, evaluation, and selection exact M10 v2 request hash. |
| `m10_v2_result_hash` | analysis identity | Equals the evaluation and selection exact M10 v2 result hash. |
| `promotion_policy_hash` | promotion identity | Equals request policy hash and readiness policy hash. |
| `canonical_target_mechanism_id` | promotion identity | Equals request/readiness target ID; nonblank. |
| `mapping_identities` | mapping/classification identity | Tuple of `CandidateCanonicalInstanceMapping.mapping_hash` values in the exact canonical candidate-instance-ID order of readiness mapping. |
| `classification_identities` | mapping/classification identity | Tuple of promotion `classification_hash` values in lexical ascending order, equal to readiness classification identities. |
| `reference_hash` | derived durable identity | Self-hash below. |

Every hash field above except the explicit `None` placement-derivation case is a
repository-valid `sha256:` identity. Every member of `mapping_identities` and
`classification_identities` is independently validated with the same
`_require_hash` (or accepted equivalent) validator used for the other SHA-256
identity fields; nonblank text alone is insufficient. `mapping_identities` and
`classification_identities` are nonempty.

`mapping_identities` rejects duplicates. Its canonical order is the existing
`MultiJointPromotionReadiness.mapping` order: ascending
`candidate_instance_id`; full verification compares the tuple to the typed
mapping records, so lexical ordering of mapping hashes alone is not substituted.
`classification_identities` rejects duplicates and must be lexical ascending.
Unknown, substituted, or caller-ordered mapping/classification identity tuples
reject through exact comparison with readiness and the typed request.

`reference_hash` is `sha256:` plus SHA-256 of canonical JSON for exactly the
following map, with each right-hand side the serialized value of the same-named
field and serialized `null` retained for
`placement_derivations_hash` when it is absent:

```text
{
  "schema_version": <schema_version>,
  "promotion_request_hash": <promotion_request_hash>,
  "readiness_hash": <readiness_hash>,
  "project_id": <project_id>,
  "source_revision": <source_revision>,
  "source_state_hash": <source_state_hash>,
  "source_binding_hash": <source_binding_hash>,
  "candidate_hash": <candidate_hash>,
  "synthesis_request_hash": <synthesis_request_hash>,
  "synthesis_policy_hash": <synthesis_policy_hash>,
  "m12_3_result_hash": <m12_3_result_hash>,
  "multi_joint_evaluation_request_hash": <multi_joint_evaluation_request_hash>,
  "multi_joint_evaluation_hash": <multi_joint_evaluation_hash>,
  "multi_joint_selection_hash": <multi_joint_selection_hash>,
  "scope_hash": <scope_hash>,
  "configuration_set_hash": <configuration_set_hash>,
  "placement_derivations_hash": <placement_derivations_hash-or-null>,
  "physical_pair_classification_set_hash": <physical_pair_classification_set_hash>,
  "m10_v2_request_hash": <m10_v2_request_hash>,
  "m10_v2_result_hash": <m10_v2_result_hash>,
  "promotion_policy_hash": <promotion_policy_hash>,
  "canonical_target_mechanism_id": <canonical_target_mechanism_id>,
  "mapping_identities": <ordered mapping_identities>,
  "classification_identities": <ordered classification_identities>
}
```

`reference_hash` itself is excluded. The model must reconstruct and validate the
typed request, readiness, multi-joint evaluation request, evaluation, and
selection at publication; callers cannot construct a trusted reference from
arbitrary hash strings.

## Selected Decision Manifest

Add immutable, frozen, `extra="forbid"`
`SelectedMultiJointCandidateDecisionManifest@1` with literal
`schema_version="selected-multi-joint-candidate-decision-manifest@1"`.
It is compact pre-application decision provenance. It embeds the typed input
reference and the already accepted generic compilation/projection/mapping
records, but no legacy M12 scope projection and no duplicate multi-joint scope
payload.

Its exact fields are:

```text
schema_version
input_reference: MultiJointPromotionDecisionInputReference
promotion_policy_hash
base_revision
base_state_hash
compilation_hash
promotion_proposal_hash
projection_hash
projection: PromotableMechanismProjection
mapping: tuple[CandidateCanonicalInstanceMapping, ...]
decision_hash
```

`base_revision` and `base_state_hash` equal the reference source revision/state,
the compiled proposal base binding, and the state on which readiness was
validated. `promotion_policy_hash`, target mechanism, compilation hash,
proposal hash, projection hash, and mapping must equal the reference and
`CandidatePromotionCompilation` exactly. The typed `mapping` is nonempty,
ordered by ascending candidate instance ID, has unique candidate and canonical
instance IDs, and its ordered mapping hashes equal
`input_reference.mapping_identities`. The `CandidatePromotionCompilation`
passed to publication is the exact original object/identity returned by
`compile_multi_joint()`: `compilation_hash`, `projection`, and
`projection_hash` are copied without transformation. The mapping and projection
have independent ordering semantics. The mapping is candidate-instance ordered;
the projection retains its M13-3 compilation-defined realization/projection
order. Positional equality between `projection.canonical_instance_ids` and
`mapping.canonical_instance_id` is forbidden.

The sequences must nevertheless describe the same canonical-instance universe:
both canonical-ID sequences are nonblank and unique, have equal cardinality,
and their sets are equal. The complete typed manifest mapping must equal the
original `CandidatePromotionCompilation.mapping`, preserving every
`candidate_instance_id -> canonical_instance_id` pair and every mapping hash.
Set equality is not a substitute for this exact pairing comparison.

`projection.mapping_identities` has M13-3 projection semantics: it is the
canonical component-instance identity sequence embedded in the projection and
is currently emitted in that same realization/projection order. It is not the
tuple of `CandidateCanonicalInstanceMapping.mapping_hash` values. M13-4E
preserves its original content and order exactly and does not compare it to
`input_reference.mapping_identities`.

M13-4E MUST NOT construct a replacement `CandidatePromotionCompilation` or
`PromotableMechanismProjection` merely to satisfy evidence ordering. In
particular, no compilation-normalization or rehashing helper is permitted.

`decision_hash` is `sha256:` plus SHA-256 canonical JSON over exactly:

```text
{
  "schema_version": <schema_version>,
  "input_reference": <full serialized input_reference>,
  "promotion_policy_hash": <promotion_policy_hash>,
  "base_revision": <base_revision>,
  "base_state_hash": <base_state_hash>,
  "compilation_hash": <compilation_hash>,
  "promotion_proposal_hash": <promotion_proposal_hash>,
  "projection_hash": <projection_hash>,
  "projection": <full serialized projection>,
  "mapping": <ordered full serialized mapping>
}
```

It excludes only `decision_hash`. No separate durable multi-joint analysis-scope
projection is created: `input_reference` already binds `scope_hash`,
configuration-set, placement-derivation, pair-policy, and M10 request/result
identities without copying their authority payloads.

The future typed publication contract is:

```python
PromotionManifestService.publish_multi_joint_decision(
    store: ArtifactStore,
    *,
    run: Run,
    request: CandidateMultiJointPromotionRequest,
    readiness: MultiJointPromotionReadiness,
    compilation: CandidatePromotionCompilation,
) -> EngineeringArtifact
```

It reconstructs all three typed records; requires the compilation proposal to
be semantically valid; creates and validates the input reference and manifest;
verifies selected geometry sources using the existing strict ArtifactStore
boundary; publishes; then calls `resolve_multi_joint_decision`. It accepts no
arbitrary hashes, canonical mechanism, projection, proposal, or run ID as a
substitute for this typed route.

At decision publication, `run` is the exact `Run` returned by
`RunController.create_run()` for this promotion attempt. It must have a nonblank
`run_id`, `status == RunStatus.CREATED`, `project_id == request.project_id ==
readiness.project_id`, `initial_revision == active_revision ==
request.source_revision == readiness.source_revision == manifest.base_revision`,
and `initial_state_hash == active_state_hash == request.source_state_hash ==
readiness.source_state_hash == manifest.base_state_hash`. The publisher requires
`store.project_id == run.project_id` and `store.run_id == run.run_id`; no ambient
run lookup or caller-provided unrelated run ID is permitted.

The deterministic decision artifact ID is:

```text
MULTI-JOINT-PROMOTION-DECISION-{decision_hash[7:31]}
```

The exact ArtifactStore metadata is: filename `multi_joint_decision.json`;
type `ArtifactType.JSON`; producer tool name `mechcad-promotion-manifest`;
producer version `1`; `bound_revision=manifest.base_revision`; and
`bound_state_hash=manifest.base_state_hash`. Those base values must equal the
source N revision/state hash validated by the typed readiness and compiled
proposal. `input_hash=manifest.decision_hash`; and
`run_id=run.run_id`, as persisted by the scoped `ArtifactStore`. The complete
artifact ID is `MULTI-JOINT-PROMOTION-DECISION-{decision_hash[7:31]}`. This
follows the legacy decision-manifest run-scoped ArtifactStore convention with a
new typed run validation, distinct namespace, and filename.

## Result Manifest

Add immutable, frozen, `extra="forbid"` `MultiJointPromotionResultManifest@1`
with literal `schema_version="multi-joint-promotion-result-manifest@1"`.
The existing `CandidatePromotionResultManifest@1` cannot be reused because its
resolver requires a legacy `SelectedCandidateDecisionManifest@1` predecessor.
Its proposal, ChangeSet, changed-path, and N+1 concepts are generic, but its
decision-manifest type is not.

Its exact fields are:

```text
schema_version
decision_artifact_id
decision_artifact_hash
decision_hash
promotion_proposal_hash
proposal_id
changeset_id
changed_paths
canonical_target_mechanism_id
mechanism_path
base_revision
base_state_hash
resulting_revision
resulting_state_hash
result_hash
```

`decision_artifact_id`, `decision_artifact_hash`, and `decision_hash` bind the
exact resolved `SelectedMultiJointCandidateDecisionManifest`. The artifact hash
is the ArtifactStore byte hash, not its self-hash. `promotion_proposal_hash` and
`proposal_id` equal the compilation and proposal. `changeset_id` is nonblank and
equals the accepted `ChangeSet.id` in the invalidation record. The schema has no
`application_id`: the current promotion route and `AppliedChangeResult` expose
no stable promotion-application identity, and the unrelated constraint-
resolution state-application provenance is not promotion machinery.

`changed_paths` is the nonempty, duplicate-free ordered tuple produced by
`tuple(dict.fromkeys(operation.path for operation in proposal.operations))`.
That proposal operation order is semantic application order and is not sorted.
`mechanism_path` is exactly
`/physical_mechanisms/{canonical_target_mechanism_id}` and occurs in
`changed_paths`. `base_revision` equals the selected decision
`base_revision`, `proposal.base_revision`, and `ChangeSet.base_revision`.
`base_state_hash` equals the selected decision `base_state_hash`,
`proposal.base_state_hash`, `ChangeSet.base_state_hash`, and the actual
pre-apply state hash. `resulting_revision` equals the actual
`AppliedChangeResult.snapshot.revision` and is exactly `base_revision + 1` under
the current one-revision-per-`ChangeEngine.apply_proposal()` semantics.
`resulting_state_hash` equals the actual persisted
`AppliedChangeResult.snapshot.state_hash`.

`result_hash` is `sha256:` plus SHA-256 canonical JSON over exactly:

```text
{
  "schema_version": <schema_version>,
  "decision_artifact_id": <decision_artifact_id>,
  "decision_artifact_hash": <decision_artifact_hash>,
  "decision_hash": <decision_hash>,
  "promotion_proposal_hash": <promotion_proposal_hash>,
  "proposal_id": <proposal_id>,
  "changeset_id": <changeset_id>,
  "changed_paths": <ordered changed_paths>,
  "canonical_target_mechanism_id": <canonical_target_mechanism_id>,
  "mechanism_path": <mechanism_path>,
  "base_revision": <base_revision>,
  "base_state_hash": <base_state_hash>,
  "resulting_revision": <resulting_revision>,
  "resulting_state_hash": <resulting_state_hash>
}
```

It excludes only `result_hash`. The result cannot represent success without a
resolved typed multi-joint decision, an applied ChangeSet, exact changed paths,
the canonical target path, the exact base-N binding, and the actual persisted
N+1 revision/state binding.

The future typed publication contract is:

```python
PromotionManifestService.publish_multi_joint_result(
    store: ArtifactStore,
    *,
    decision_artifact: EngineeringArtifact,
    compilation: CandidatePromotionCompilation,
    proposal: ChangeProposal,
    applied: AppliedChangeResult,
    invalidation: InvalidationRecord,
    final_run: Run,
) -> EngineeringArtifact
```

It resolves the decision through `resolve_multi_joint_decision`, validates the
decision/compilation/proposal relationship, proves the applied snapshot,
invalidation, and final run agree on the N-to-N+1 transition, then publishes
and calls `resolve_multi_joint_result`. It accepts no caller-supplied arbitrary
decision ID, target mechanism, paths, state identities, or proposal hash.

`final_run` is the durable run returned by
`RunController.apply_approved_proposal(run.run_id, proposal)` after successful
invalidation completion. It must have nonblank `run_id`,
`project_id == store.project_id`, `run_id == store.run_id`, initial revision/state
equal to the resolved decision base binding, and active revision/state equal to
the applied/result N+1 binding. The result publisher resolves the decision
artifact before publication and requires `decision_artifact.run_id ==
final_run.run_id == store.run_id`; it does not accept a separate run ID.

The deterministic result artifact ID is:

```text
MULTI-JOINT-PROMOTION-RESULT-{result_hash[7:31]}
```

with filename `multi_joint_result.json`, JSON type, the existing promotion
manifest producer/version, bound revision/state equal to the resulting N+1
binding, `input_hash=decision_artifact_hash`, and `run_id=final_run.run_id` as
persisted by the scoped ArtifactStore. It must equal the resolved decision
artifact `run_id`. This is distinct from legacy `PROMOTION-RESULT-*`.

## Application Receipt

Add immutable, frozen, `extra="forbid"`
`CandidateMultiJointPromotionApplicationResult@1` with literal
`schema_version="candidate-multi-joint-promotion-application-result@1"`.
It is a typed transient application receipt; durable verification uses resolved
artifacts rather than requiring this in-memory object.

Its exact fields are:

```text
schema_version
request: CandidateMultiJointPromotionRequest | None
readiness: MultiJointPromotionReadiness | None
compilation: CandidatePromotionCompilation | None
decision_artifact_id: str | None
result_artifact_id: str | None
applied_revision: int | None
applied_state_hash: str | None
status: PromotionApplicationStatus
error: str | None
```

`request`, when present, must be exactly
`CandidateMultiJointPromotionRequest`; legacy request coercion is forbidden.
`readiness`, when present, must be self-valid and bind its request hash to the
request. `compilation`, when present, must self-validate and bind to the
request/readiness target and mappings. Artifact IDs are nonblank when present.
Applied revision is positive and applied state hash is SHA-256 when present.
Error is nonblank when present.

M13-4E does not add an application-receipt self-hash because the existing
application receipt semantics have no receipt hash. The two referenced durable
artifact IDs, typed request/readiness/compilation, status, and actual state
identity are the receipt boundary. A future verifier resolves and validates
those artifact IDs rather than trusting receipt copies.

For `PROMOTION_APPLIED`, all of `request`, `readiness`, `compilation`,
`decision_artifact_id`, `result_artifact_id`, `applied_revision`, and
`applied_state_hash` are required; `error` is absent. For a pre-apply or
ChangeEngine-rejected status, `result_artifact_id`, `applied_revision`, and
`applied_state_hash` are absent. For every post-apply failure, request,
readiness, compilation, decision artifact ID, applied revision, and applied
state hash are required; result artifact ID is absent; error is required.
`PROMOTION_APPLIED_BUT_RESULT_PROVENANCE_FAILED` also requires an absent result
artifact ID even if bytes were written before fresh verification failed.

`PromotionApplicationStatus` is reused unchanged because its values describe
generic application lifecycle states, not a legacy request schema:
`PRE_APPLY_FAILURE`, `CHANGEENGINE_REJECTED`,
`PROMOTION_APPLIED_BUT_RUN_TRANSITION_FAILED`,
`PROMOTION_APPLIED_BUT_INVALIDATION_PERSISTENCE_FAILED`,
`PROMOTION_APPLIED_BUT_INVALIDATION_VERIFICATION_FAILED`,
`PROMOTION_APPLIED_BUT_RESULT_PROVENANCE_FAILED`, and
`PROMOTION_APPLIED`.

## Currentness / Identity Binding

The decision reference retains separate identities for source currentness and
application transition. It proves that the selected candidate evaluation was
valid at source N through `project_id`, `source_revision`, `source_state_hash`,
`source_binding_hash`, candidate/synthesis/admissibility identities, multi-joint
evaluation request identity, evaluation identity, selection identity, readiness
identity, configuration-set identity, placement-derivation identity, pair-policy
identity, and exact M10 request/result identities.

The result manifest separately proves that the accepted proposal based on that
exact N binding mutated state N to N+1 through `base_revision`,
`base_state_hash`, `changeset_id`, `changed_paths`, `resulting_revision`, and
`resulting_state_hash`. These identities must not be collapsed into one generic
state hash.

Full N-to-N+1 verification cross-checks the result manifest against records
that actually expose each identity: its base fields against the resolved
decision and receipt compilation proposal; `changeset_id` and `changed_paths`
against the invalidation record; resulting revision/state against the
invalidation revision and persisted `StateManager.load_revision()` snapshot;
and source/active run bindings against the durable run loaded using the decision
artifact metadata `run_id`. It must not require `StateManager` current revision
to remain N+1 after later unrelated revisions; the persisted N+1 revision is the
required state check.

The following M13-3 authorities are explicitly retained through the decision
reference, selected decision, receipt verification, and result verification:

- `configuration_set_hash`; actual `JointConfiguration` values remain owned by
  the M13-3 scope/configuration-set and canonical obligation, not copied here.
- `placement_derivations_hash`; actual generated placement derivations remain
  request/canonical authority and are not numerically duplicated here.
- `physical_pair_classification_set_hash`; the durable semantic pair-policy
  owner remains M13-3 physical-pair classification bindings.
- `m10_v2_request_hash` and `m10_v2_result_hash`; the M10 result remains
  independently replayable, not serialized in a new result store.

## Publication Ordering

The conceptual acceptance gates are readiness, compilation, decision evidence,
application, complete post-apply lifecycle, and result evidence. The actual
operation order of the existing common machinery is fixed as follows:

```text
validate typed multi-joint readiness
  -> compile_multi_joint() and validate proposal
  -> create source-bound run and publish/resolve multi-joint decision artifact
  -> ChangeEngine prepares ChangeSet and persists DesignState N+1
  -> RunController records and persists the N+1 run transition
  -> RunController builds and persists invalidation, then marks stale tasks
  -> independently reload and verify run and invalidation
  -> publish/resolve multi-joint result artifact
  -> return typed multi-joint application receipt
```

`RunController.apply_approved_proposal()` first calls
`ChangeEngine.apply_proposal()`, then records/persists the run transition, and
only then builds/persists invalidation. M13-4E does not change that machinery.
The route treats application as successful only after both current run-transition
and invalidation operations have completed and been independently reloaded and
verified. Result publication is always after those checks.

Common internal application mechanics may perform ChangeSet construction,
ChangeEngine application, invalidation persistence, and run transition, but may
only receive an already validated, route-specific trusted context. They may not
accept arbitrary proposal, mechanism, hash, target, or request arguments and
may not select a legacy versus multi-joint evidence type.

The private multi-joint route context is used by the route and is strongly
typed. It contains only `request: CandidateMultiJointPromotionRequest`,
`readiness: MultiJointPromotionReadiness`, `compilation:
CandidatePromotionCompilation`, `run: Run`, `store: ArtifactStore`, and
`decision_artifact: EngineeringArtifact`. It derives the proposal only as
`compilation.proposal`; it accepts no duplicate proposal, mechanism,
projection, mapping, target, or arbitrary hash input. Its validator proves
request/readiness/compilation, run/store, and decision-artifact bindings before
application.

## Failure Semantics

The new typed receipt reuses the established status and no failure produces
optimistic success evidence.

| Failure class | Canonical N+1 / run / invalidation state | Decision artifact | Result artifact | Receipt status |
| --- | --- | --- | --- | --- |
| Readiness or compile/proposal validation failure | No N+1; no run; no invalidation. | None | None | `PRE_APPLY_FAILURE` |
| Run creation, decision construction/publication, or fresh decision-resolution failure | No N+1; created run is failed when available; no invalidation. | None in receipt; written-but-unverified bytes are not trusted evidence. | None | `PRE_APPLY_FAILURE` |
| Stale proposal, ChangeSet construction, or ChangeEngine rejection before revision creation | No N+1; created run is failed; no invalidation. | Resolved | None | `CHANGEENGINE_REJECTED` |
| Convergence/run-transition failure after `ChangeEngine.apply_proposal()` | N+1 exists. The run may persist as blocked at N+1; if persistence itself fails, its durable state is not claimed. No invalidation is attempted. | Resolved | None | `PROMOTION_APPLIED_BUT_RUN_TRANSITION_FAILED` |
| Invalidation persistence or stale-task update failure | N+1 exists. The run first persisted active at N+1, then is persisted blocked at N+1 when that blocked transition succeeds. Invalidation may be absent or may exist before a later stale-task update failure. | Resolved | None | `PROMOTION_APPLIED_BUT_INVALIDATION_PERSISTENCE_FAILED` |
| Post-apply invalidation reload/verification failure | N+1 and the returned active run exist; invalidation may exist but is not trusted until verified. | Resolved | None | `PROMOTION_APPLIED_BUT_INVALIDATION_VERIFICATION_FAILED` |
| Result publication failure before durable write, or fresh result-resolution failure after write | N+1, active run, and verified invalidation exist. | Resolved | None in the trusted receipt, even if unverified bytes exist. | `PROMOTION_APPLIED_BUT_RESULT_PROVENANCE_FAILED` |
| Complete route | N+1, active run, and verified invalidation exist. | Resolved | Resolved | `PROMOTION_APPLIED` |

The current common machinery can surface a `PostApplyInvalidationError` or
`PostApplyRunTransitionError` after ChangeEngine has mutated state. The typed
route preserves the actual applied snapshot identity in those receipts and never
publishes a trusted result artifact. A stale source detected by compiler
readiness is a pre-apply failure; a stale proposal detected during ChangeEngine
preparation is `CHANGEENGINE_REJECTED`.

## Artifact / Evidence Persistence

Decision and result manifests are only ArtifactStore JSON artifacts, following
the existing promotion-manifest architecture. They are not duplicated into
`EvidenceStore`. `EvidenceStore` continues to persist and load only the
invalidation record that binds changed paths, parent revision, resulting
revision, and ChangeSet ID.

The decision artifact-local resolver requires its ID namespace,
`input_hash=decision_hash`, base revision/state binding, canonical JSON bytes,
typed manifest validation, decision self-hash, embedded-reference integrity,
embedded projection/mapping integrity, and source-artifact checks that are
retrievable from source references embedded in the projection. The result
artifact-local resolver requires its result namespace,
`input_hash=decision_artifact_hash`, N+1 revision/state binding, canonical JSON
bytes, result self-hash, and the resolved typed multi-joint decision artifact.

No `Evidence(kind="analysis.multi_joint_collision_sweep")` payload is widened.
It remains provenance for M10 execution identities, not a typed result database.
Multi-joint selection replay remains request reconstruction, production M10 v2
re-execution, result self-hash recomputation, and equality with the evaluation
bound `m10_v2_result_hash`.

## Verification / Reload

Add pure service methods and module-level wrappers consistent with current
promotion-manifest naming:

```python
PromotionManifestService.resolve_multi_joint_decision(
    store: ArtifactStore, artifact_id: str
) -> SelectedMultiJointCandidateDecisionManifest

PromotionManifestService.resolve_multi_joint_result(
    store: ArtifactStore, artifact_id: str
) -> MultiJointPromotionResultManifest

verify_multi_joint_promotion_decision(
    manifest: SelectedMultiJointCandidateDecisionManifest,
    *,
    request: CandidateMultiJointPromotionRequest,
    readiness: MultiJointPromotionReadiness,
    compilation: CandidatePromotionCompilation,
) -> None

verify_multi_joint_promotion_application_result(
    receipt: CandidateMultiJointPromotionApplicationResult,
    *,
    manifest_service: PromotionManifestService,
    manifest_store: ArtifactStore,
    state_manager: StateManager,
    evidence_store: EvidenceStore,
    run_controller: RunController,
) -> None
```

`resolve_multi_joint_decision` performs strict ArtifactStore retrieval, JSON
object decoding, typed `model_validate`, decision self-hash recomputation,
project scope, deterministic artifact-ID, input hash, base revision/state,
canonical bytes, embedded input-reference validation, embedded projection/mapping
validation, and source-artifact verification that can be performed from source
references embedded in the projection. It does not reconstruct or claim to
validate `MultiJointPromotionReadiness`, `CandidatePromotionCompilation`, or
`CandidateMultiJointPromotionRequest` from stored hashes alone. The strict
retrieved `EngineeringArtifact` must have nonblank `run_id` equal to
`store.run_id`; this is artifact-local metadata validation, not a Run lookup.

`verify_multi_joint_promotion_decision` is the full decision trust verifier. It
first revalidates the three exact typed inputs, rebuilds the decision input
reference from request/readiness, and then requires equality of every reference,
base binding, policy, compilation, proposal hash, projection, and ordered
mapping field in the resolved manifest. It is the only decision-level boundary
that verifies request/readiness/compilation cross-chain facts. It accepts no
untyped hash, proposal, projection, canonical mechanism, or mapping substitute.

`resolve_multi_joint_result` performs strict retrieval, typed validation,
result self-hash recomputation, deterministic artifact-ID, input hash, N+1
binding, canonical bytes, and resolved selected-decision checks. From its own
persisted fields and the resolved decision it verifies the artifact byte hash,
the decision artifact reference, proposal hash, target/path relationship,
`base_revision == decision.base_revision`,
`base_state_hash == decision.base_state_hash`, and
`resulting_revision == base_revision + 1`. It does not claim to load or verify a
ChangeSet, invalidation, persisted state, or run because those dependencies are
not in its signature. It does require the strict retrieved result artifact
`run_id` equal to `store.run_id` and equal to the strict retrieved decision
artifact `run_id`.

`verify_multi_joint_promotion_application_result` revalidates the receipt's
concrete type, request, readiness, compilation, status-dependent artifact
presence, and state fields. For `PROMOTION_APPLIED`, it resolves both artifacts,
calls `verify_multi_joint_promotion_decision`, loads the exact N+1 invalidation,
loads the persisted N+1 state by `resulting_revision`, and loads the run using
the decision artifact metadata `run_id`. It validates result proposal ID/hash
against compilation proposal; ChangeSet ID and ordered changed paths against
invalidation; invalidation parent/revision against base/result revisions; the
persisted revision hash against result/receipt applied state; and run project,
initial N binding, active N+1 binding, and `RunStatus.CREATED` lifecycle state
against the decision/result. `RunController.apply_approved_proposal()` advances
the run's active binding and iteration but does not change its status, so
`CREATED` is the exact successful publication state exposed by the current Run
model. It also requires the decision and result artifact metadata `run_id` equal
the loaded run `run_id`. For every partial post-apply status
(`PROMOTION_APPLIED_BUT_RUN_TRANSITION_FAILED`,
`PROMOTION_APPLIED_BUT_INVALIDATION_PERSISTENCE_FAILED`,
`PROMOTION_APPLIED_BUT_INVALIDATION_VERIFICATION_FAILED`, and
`PROMOTION_APPLIED_BUT_RESULT_PROVENANCE_FAILED`), it requires applied revision
and state hash, loads `StateManager.load_revision(project_id, applied_revision)`,
requires the loaded snapshot hash to equal `receipt.applied_state_hash`, and,
after resolving the decision artifact, requires `applied_revision ==
decision.base_revision + 1`. It rejects a nonexistent revision, wrong-project
revision, hash mismatch, or wrong N+1 revision without claiming run,
invalidation, or result facts that the particular failure row does not
guarantee. It rejects a legacy receipt, legacy
manifest, unresolved artifact, substituted readiness, request, evaluation,
selection, configuration set, placement derivations, pair policy, M10
request/result, mapping, classification, state, or manifest identity.

Manifest identification and reload require only serialized ArtifactStore bytes,
JSON object decoding, typed `model_validate`, self-hash recomputation, and
artifact metadata verification; neither candidate nor runtime object is needed.
After restart, strict decision artifact retrieval yields its persisted
`EngineeringArtifact.run_id`; `RunController.get_run(run_id)` then loads that
one durable promotion run. The verifier rejects a missing, non-unique, or
metadata-mismatched run rather than selecting a run from the N+1 state.
Full cross-chain verification additionally receives durable typed request,
readiness, and compilation records plus the persisted state, invalidation, and
run dependencies named in the verifier signature. The request transitively
contains the typed multi-joint evaluation request, evaluation, and selection
records needed to revalidate their identities. Full verification never requires
an in-memory `MechanicalDesignCandidate`, candidate CAD realization, M10 result
object, or transient evaluation execution object.

## Legacy Compatibility

M13-4E uses separate family names and `@1` schema literals because the legacy
and multi-joint chains have different semantic types. A hypothetical
`PromotionDecisionInputReference@2` would ambiguously represent unrelated trust
models and is prohibited.

Existing legacy artifact IDs remain exactly `PROMOTION-DECISION-{hash[7:31]}`
and `PROMOTION-RESULT-{hash[7:31]}`. Legacy manifest and application
verification remain unchanged. New multi-joint resolvers never parse a legacy
manifest as a multi-joint manifest, and legacy resolvers never parse a
multi-joint manifest as legacy.

No M13-3 record, M10 record, CAD record, state schema, selection rule,
promotion-policy rule, or legacy promotion evidence schema/hash/artifact ID
changes in M13-4E. More precisely, M13-4E changes none of the M13-3
request/evaluation/selection/promotion schemas or hashes; M10 schemas or
semantics; CAD schemas or semantics; canonical state schema; selection
semantics; promotion-policy semantics; or legacy promotion evidence
schemas/hashes/artifact IDs.

## Expected Production Surface

Future implementation is limited to these additive or narrowly extended files:

- `src/mechcad_harness/candidates/promotion_models.py`: the decision input
  reference and typed multi-joint application receipt.
- `src/mechcad_harness/candidates/promotion_artifacts.py`: selected-decision and
  result manifests, deterministic namespaces, publication, resolution, and pure
  verification helpers.
- `src/mechcad_harness/candidates/promotion.py`: only a route-specific internal
  handoff/context and shared application-mechanics extraction if required to
  avoid duplicating ChangeEngine/invalidation/run mechanics.
- `src/mechcad_harness/candidates/__init__.py`: required additive exports only.

No M10, CAD, M11, M13-3 bridge/evaluation/selection schema, state, database, or
`ProductionApplication` file change is authorized by this specification.

## Test Strategy

Future implementation must add focused tests only after an implementation plan
is separately approved:

- Decision input reference: exact payload/hash; each mapping/classification
  identity rejects `abc`, `sha256:`, malformed length, and non-hex input, while
  a valid SHA-256 identity accepts; substitution rejection for
  request, readiness, evaluation request, evaluation, selection, configuration
  set, placement derivations, pair policy, M10 request/result, mapping, and
  classification identities.
- Selected decision: exact typed reference/original compilation/mapping binding;
  evidence compilation hash and projection hash equal the original
  `compile_multi_joint()` values; manifest projection and mapping equal the
  original compilation values; a valid differing projection/mapping order
  accepts; a self-consistent rehashed mapping that swaps canonical IDs between
  candidate IDs rejects; legacy
  manifest cannot parse as multi-joint; deterministic artifact ID; canonical
  byte publication; serialized fresh reload.
- Result manifest: exact selected-decision artifact binding; exact proposal,
  ChangeSet, base-N, N+1, and path-order binding; no success publication before
  fully applied and verified common application result; serialized fresh reload.
- Typed receipt: multi-joint request only; exact readiness and artifact IDs;
  status/failure preservation; no legacy request coercion; partial post-apply
  states retain N+1 without a success result artifact.
- Verification: resolver namespace, artifact byte hash, canonical bytes, result
  self-hash, decision artifact ID/byte hash/decision self-hash, base/result
  revision-state, target/path, and run-ID tampering failures; artifact-local
  resolver tests do not invoke `StateManager`, `EvidenceStore`, or
  `RunController`; full verifier request/readiness/hash substitution,
  invalidation/path/ChangeSet substitution, and full fresh-process verification
  without in-memory candidate/M10 result.
- Legacy regressions: independently recover literal legacy canonical JSON,
  self-hashes, artifact IDs, artifact bytes/hashes, receipt field/schema
  contract, and status values from committed baseline `ca294e0`; all current
  legacy behavior must match those literals without deriving an expectation from
  the helper under test.

## M13-4P Handoff

M13-4E implementation and acceptance resolves only
`M13_4P_BLOCKED_BY_PROMOTION_EVIDENCE_SCHEMA_GAP`. It does not resume M13-4P.
After acceptance, a separate M13-4P reconciliation must freeze the public
`ProductionApplication` selection and promotion entrypoints, composed trusted
M10 replay callback, exact multi-joint dispatch, route-specific trusted context,
common ChangeEngine handoff, typed publication calls, currentness/failure
translation, and legacy route compatibility.

The handoff split is fixed:

```text
legacy typed trust/evidence -> legacy decision -> common application mechanics
  -> legacy result/receipt

multi-joint typed trust/evidence -> multi-joint decision -> same common
application mechanics -> multi-joint result/receipt
```

The common mechanics do not decide which trust/evidence schema applies. M13-4P
must not expose a generic public `apply_compiled_promotion` bypass.

## Self-Review

The completed checklist is:

- No legacy manifest is overloaded.
- No legacy application receipt is widened.
- No legacy record hides runtime semantic type dispatch.
- `readiness_hash` is explicit and independently verified.
- `configuration_set_hash` is explicit and remains M13-3 configuration authority.
- `placement_derivations_hash` is explicit and does not duplicate placement data.
- `physical_pair_classification_set_hash` is explicit and does not duplicate pair policy.
- `m10_v2_request_hash` and `m10_v2_result_hash` are explicit.
- `application_id` is absent because promotion has no such stable identity.
- Artifact-local resolvers claim only persisted facts available from their signatures.
- Full trust verification receives every typed and durable dependency it validates.
- A result artifact is not trusted or returned in a receipt before fresh verification.
- No M10 result store or additional persistence subsystem is introduced.
- Manifest reload requires no candidate, CAD, M10 result, or transient execution object.
- Common application mechanics receive only typed route contexts and expose no generic trust bypass.
- No M13-4P `ProductionApplication` composition API is specified or implemented.
- No M13-4 acceptance, Rotator V2, M10, CAD, M11, or M13-3 semantic scope is added.

The proposed future implementation marker is:

```text
M13_4E_MULTI_JOINT_PROMOTION_EVIDENCE_CONTRACT_VERIFIED
```

## Worktree Status

Before this specification was added, the local worktree already contained
unrelated modifications to `.coverage` and `.superpowers/sdd/*`, plus unrelated
untracked historical specifications/plans, `err.txt`, `projects/`, and
`src/mechcad-harness/`. They are outside M13-4E and must remain untouched.

M13_4E_CORRECTIVE_SPEC_PLAN_READY
\n