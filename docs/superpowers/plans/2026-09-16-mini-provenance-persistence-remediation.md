# MINI Provenance Persistence Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist and strictly reload the candidate-to-promotion-to-canonical-M10 provenance chain with ordinary `ArtifactStore` JSON artifacts, without changing canonical authority or historical MINI records.

**Architecture:** Add `CandidateProvenanceArtifactService`, a domain-owned publisher/resolver for deterministic JSON envelopes. Every envelope carries a full typed immutable record plus typed `EngineeringArtifact` references for upstream artifacts; resolver checks bytes, project/run/task execution scope, source revision/state, nested semantic hashes, source STEP artifacts, and M10 Evidence. `ProductionApplication` publishes at the existing result-creation boundaries, while promotion manifests retain their unchanged wire and semantic hashes and are linked by strict resolution rather than embedded candidate payload.

**Tech Stack:** Python 3.11+, Pydantic v2, existing `canonical_json_bytes`, `ArtifactStore`, `EvidenceStore`, `StateManager`, pytest.

## Global Constraints

- Do not run the live MINI Revision 3 -> Revision 4 rerun, FreeCAD, M10, promotion, or M11 during this remediation.
- Do not create a MINI-specific store, sidecar, schema, fixture persistence format, or retrospective artifact.
- Use only `ArtifactStore` `ArtifactType.JSON` for the new domain records and preserve its project/run/task metadata in every cross-artifact reference.
- Preserve existing immutable domain semantic hashes, `CandidatePromotionRequest` wire/hash semantics, promotion decision/result manifests, `ArtifactStore`, `EvidenceStore`, and `DesignState` authority.
- Do not alter historical MINI Revision 3 or Revision 4, including Revision 4 hash `sha256:bae8d54368e127408e027bf875da5ef9edfa62de0dda9af8999ebd1ed4f20767`.
- Reuse the existing single-axis Evidence writers only: `ProductionApplication.prove_continuous_single_axis_clearance()` writes `analysis.continuous_clearance_proof`; `ProductionApplication.analyze_assembly_kinematics()` writes `analysis.kinematic_sweep` for required home checks.
- A semantic hash is not an execution locator. Every persisted reference must retain `artifact_id`, artifact-byte `sha256`, `project_id`, `run_id`, `task_id`, artifact type, bound revision, and bound state hash, and resolution must use the exact recorded run scope.
- No commit, push, tag, or history operation is authorized by this task.

---

## File Structure

- Create: `src/mechcad_harness/candidates/provenance_artifacts.py` - immutable artifact-reference model, all six deterministic envelopes, publisher, strict resolvers, and chain resolver.
- Modify: `src/mechcad_harness/candidates/__init__.py` - export the provenance service and typed publication/resolution records.
- Modify: `src/mechcad_harness/application.py` - compose the service and publish candidate CAD/evaluation/comparison/selection/canonical CAD/canonical M10 at the existing production boundaries.
- Modify: `src/mechcad_harness/candidates/promotion.py` - resolve the published selection artifact through the existing decision's `selection_hash` before canonical verification, without changing promotion manifest bytes or models.
- Modify: `src/mechcad_harness/candidates/canonical_m10.py` only if a read-only helper is needed to derive the aggregate limiting pair/metric from already validated proofs. Do not add persistence fields or change `outcome_hash`.
- Create: `tests/unit/test_candidate_provenance_artifacts.py` - deterministic publish/resolve and adversarial resolver coverage using current unit fixtures and fake result records.
- Modify: `tests/integration/test_m12_candidate_cad_m10_production.py` - non-live production wiring and restart-style candidate CAD -> evaluation -> comparison -> selection -> promotion coverage.
- Modify: `tests/integration/test_m12_promotion_production.py` - canonical CAD/M10 publication, promotion-selection durable edge, and restart reconstruction coverage using the existing integration fixture boundaries.

## Durable Envelope Contract

All new envelopes use canonical JSON bytes and an explicit schema version. The service must set `EngineeringArtifact.input_hash` to the primary immutable domain identity and independently verify the artifact-byte hash via `ArtifactStore`.

| Envelope schema | Artifact ID prefix | Primary identity | Bound revision/state | Required upstream references |
|---|---|---|---|---|
| `candidate-cad-provenance@1` | `CANDIDATE-CAD-` | `CandidateCadRealization.realization_hash` | candidate source revision/state | candidate publication and each source STEP artifact |
| `candidate-evaluation-provenance@1` | `CANDIDATE-EVALUATION-` | `CandidateEvaluation.evaluation_hash` | candidate source revision/state | candidate CAD artifact, candidate publication, every proof/home Evidence |
| `candidate-comparison-provenance@1` | `CANDIDATE-COMPARISON-` | `CandidateComparisonResult.result_hash` | common source revision/state | each ordered candidate/evaluation artifact |
| `candidate-selection-provenance@1` | `CANDIDATE-SELECTION-` | `CandidateSelection.selection_hash` | candidate source revision/state | selected candidate/evaluation artifacts and optional comparison artifact |
| `canonical-cad-provenance@1` | `CANONICAL-CAD-` | `CanonicalCadRealization.realization_hash` | canonical revision/state | every selected source STEP artifact |
| `canonical-m10-provenance@1` | `CANONICAL-M10-` | `CanonicalM10VerificationOutcome.outcome_hash` | canonical revision/state | canonical CAD artifact and every proof/home Evidence |

The artifact ID is deterministic from the primary semantic hash, but every envelope reference is an exact `EngineeringArtifact` snapshot. A resolver must never use `existing_in_project()` for a nested reference because that loses execution identity and becomes ambiguous when identical semantic artifacts exist in more than one run. It must open `ArtifactStore(workspace, project_id=reference.project_id, run_id=reference.run_id, task_id=reference.task_id)` and require the exact artifact metadata and byte hash.

## Promotion Selection Edge

The existing decision manifest contains `input_reference.selection_hash` and must remain byte-for-byte/semantically unchanged. The edge is closed as follows:

1. `select_candidate()` publishes `candidate-selection-provenance@1` and returns the unchanged `CandidateSelection`; the service records an exact `EngineeringArtifact` snapshot internally for this selected identity.
2. The selection artifact has deterministic ID `CANDIDATE-SELECTION-<selection_hash fragment>` and immutable metadata including its actual `project_id`, `run_id`, `task_id`, and artifact-byte hash.
3. During `verify_promoted_mechanism()`, after the existing decision/result manifests resolve, the provenance service derives the expected selection artifact ID from `decision.input_reference.selection_hash`, resolves its exact artifact metadata from the project only to obtain its recorded execution scope, then reopens that exact run-scoped store and verifies bytes/hash/schema.
4. The resolver requires the resolved selection's `selection_hash`, candidate hash, evaluation hash, source binding hash, scope hash, and comparison-result hash to equal the decision input reference. It resolves the selected evaluation, candidate CAD, candidate publication, and optional comparison artifacts recursively.
5. The returned resolved chain includes the selection `EngineeringArtifact` ID and byte hash. The promotion decision/result manifests are not rewritten, extended, or used as a candidate-stage store. Their existing selection semantic hash remains the immutable semantic join; the resolved selection artifact snapshot supplies the independent execution identity.

## Task 1: Define Strict Provenance Envelopes And Artifact References

**Files:**
- Create: `src/mechcad_harness/candidates/provenance_artifacts.py`
- Modify: `src/mechcad_harness/candidates/__init__.py`
- Test: `tests/unit/test_candidate_provenance_artifacts.py`

**Interfaces:**
- Consumes: `ArtifactStore`, `EngineeringArtifact`, `EvidenceStore`, `StateManager`, existing candidate/canonical Pydantic domain objects.
- Produces: `ArtifactReference`, `CandidateCadProvenance`, `CandidateEvaluationProvenance`, `CandidateComparisonProvenance`, `CandidateSelectionProvenance`, `CanonicalCadProvenance`, `CanonicalM10Provenance`, and `CandidateProvenanceArtifactService`.

- [ ] **Step 1: Write failing model and deterministic-payload tests**

```python
def test_candidate_cad_payload_is_canonical_and_keeps_execution_reference(tmp_path):
    service, candidate_publication, realization, request = candidate_cad_fixture(tmp_path)

    first = service.publish_candidate_cad(candidate_publication, request, realization)
    second = service.publish_candidate_cad(candidate_publication, request, realization)

    assert first.artifact == second.artifact
    assert first.artifact.input_hash == realization.realization_hash
    assert first.artifact.run_id == candidate_publication.artifact.run_id
    assert first.payload.realization == realization
    assert first.payload.candidate_artifact.sha256 == candidate_publication.artifact.sha256
```

Add parametrized validation tests that reject an `ArtifactReference` when `project_id`, `run_id`, `artifact_type`, `sha256`, `bound_revision`, or `bound_state_hash` disagrees with its `EngineeringArtifact` snapshot. Build fixtures from the existing `_fixture` helpers in `test_m12_candidate_cad_replay.py` and `test_m12_canonical_cad.py`; publish a nonempty synthetic STEP only through `ArtifactStore`.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `py -3 -m pytest tests/unit/test_candidate_provenance_artifacts.py -q`

Expected: FAIL because `CandidateProvenanceArtifactService` and envelope models do not exist.

- [ ] **Step 3: Add immutable envelope and reference models**

Implement exact reference semantics in `provenance_artifacts.py`:

```python
class ArtifactReference(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact: EngineeringArtifact

    @model_validator(mode="after")
    def validate_artifact(self) -> "ArtifactReference":
        if self.artifact.artifact_type is not ArtifactType.JSON:
            raise ValueError("provenance reference requires a JSON artifact")
        return self

    @property
    def artifact_id(self) -> str:
        return self.artifact.artifact_id
```

Use one frozen Pydantic envelope per row in the Durable Envelope Contract. Each envelope must hold the complete typed domain output, typed upstream records where needed for deterministic reconstruction, and `ArtifactReference` values rather than free-form IDs. Each validator must reparse nested values through `model_validate(value.model_dump(mode="json"))`, recompute existing domain identities, and require all source/project/revision/state bindings to agree.

Do not modify `CandidateCadRealization`, `CandidateEvaluation`, `CandidateComparisonResult`, `CandidateSelection`, `CanonicalCadRealization`, or `CanonicalM10VerificationOutcome` fields. Their current hashes are protected semantic identity.

- [ ] **Step 4: Add canonical serialization primitives**

Use one internal implementation for every envelope:

```python
def _content(value: Model) -> bytes:
    return canonical_json_bytes(value.model_dump(mode="json"))

def _artifact_id(prefix: str, identity: str) -> str:
    return f"{prefix}{identity[7:31]}"
```

Require the resolver to compare verified bytes to `_content(reparsed_envelope)`, not merely parse JSON. Define one expected producer identity/version and expected filename per envelope. Validate `artifact.input_hash`, `artifact.bound_revision`, `artifact.bound_state_hash`, producer identity, filename, and deterministic ID for every top-level artifact.

- [ ] **Step 5: Run model tests to verify they pass**

Run: `py -3 -m pytest tests/unit/test_candidate_provenance_artifacts.py -q`

Expected: PASS for deterministic payload/reference-model cases.

## Task 2: Implement Candidate Publishers And Strict Resolvers

**Files:**
- Modify: `src/mechcad_harness/candidates/provenance_artifacts.py`
- Modify: `src/mechcad_harness/candidates/__init__.py`
- Test: `tests/unit/test_candidate_provenance_artifacts.py`

**Interfaces:**
- Consumes: envelope models from Task 1, `CandidatePublicationService`, `CandidateEvaluationCurrentnessService`, existing candidate CAD/evaluation/comparison/selection models.
- Produces: `publish_candidate_cad`, `resolve_candidate_cad`, `publish_candidate_evaluation`, `resolve_candidate_evaluation`, `publish_candidate_comparison`, `resolve_candidate_comparison`, `publish_candidate_selection`, `resolve_candidate_selection`.

- [ ] **Step 1: Write failing candidate round-trip and rejection tests**

```python
def test_candidate_evaluation_round_trip_requires_every_proof_evidence(tmp_path):
    service, published = publish_feasible_candidate_evaluation(tmp_path)

    resolved = service.resolve_candidate_evaluation(published.artifact.artifact_id)

    assert resolved.payload.evaluation == published.payload.evaluation
    assert tuple(ref.artifact.id for ref in resolved.payload.proof_evidence) == expected_evidence_ids


@pytest.mark.parametrize("mutator", [tamper_content, wrong_json_type, foreign_project, missing_source_step])
def test_candidate_cad_resolver_rejects_invalid_artifact_dependency(tmp_path, mutator):
    service, published = publish_candidate_cad(tmp_path)
    mutator(tmp_path, published)

    with pytest.raises(CandidateProvenanceIntegrityError):
        service.resolve_candidate_cad(published.artifact.artifact_id)
```

Also add separate tests for: wrong source revision/state, candidate-hash substitution inside CAD mappings, missing candidate publication, omitted M10 proof Evidence, wrong Evidence `producer_result_id`, evaluation/CAD hash mismatch, reordered comparison pairs, comparison metric mismatch, selection/comparison mismatch, and wrong artifact type.

- [ ] **Step 2: Run candidate tests to verify they fail**

Run: `py -3 -m pytest tests/unit/test_candidate_provenance_artifacts.py -q`

Expected: FAIL because candidate publishers/resolvers do not exist.

- [ ] **Step 3: Implement exact artifact and Evidence resolution helpers**

Implement a run-scoped nested resolver rather than trusting semantic hashes:

```python
def _resolve_reference(self, reference: ArtifactReference, *, expected_input_hash: str) -> tuple[EngineeringArtifact, bytes]:
    artifact = reference.artifact
    if artifact.project_id != self.project_id:
        raise CandidateProvenanceIntegrityError("artifact reference project mismatch")
    store = ArtifactStore(
        self.workspace,
        project_id=artifact.project_id,
        run_id=artifact.run_id,
        task_id=artifact.task_id,
    )
    verified = store.read_verified_strict(
        artifact.artifact_id,
        expected_type=ArtifactType.JSON,
        expected_hash=artifact.sha256,
    )
    if verified is None or verified[0] != artifact or artifact.input_hash != expected_input_hash:
        raise CandidateProvenanceIntegrityError("artifact reference binding mismatch")
    return verified
```

For source STEP references, use the same exact-run reopening pattern with `expected_type=ArtifactType.STEP`. For Evidence, load exactly the recorded ID through `EvidenceStore`, require project/revision/state, `producer_result_id`, `input_hash`, `output_hash`, expected kind, and the result/request hashes embedded in the proof or home-check record. Do not write Evidence in this service.

- [ ] **Step 4: Implement candidate CAD and evaluation publication/resolution**

`publish_candidate_cad()` must first obtain the existing `CandidatePublication` via `CandidatePublicationService.publish(candidate, request, policy)` and retain its returned `EngineeringArtifact` snapshot. It must verify every trusted source geometry STEP artifact before publishing the CAD envelope.

`publish_candidate_evaluation()` must accept the already published candidate CAD artifact and derive Evidence references in exact proof order:

```python
proof_evidence = tuple(
    self._continuous_proof_evidence(
        proof.request_hash,
        proof.result_hash,
        candidate.source_binding.source_revision,
        candidate.source_binding.source_state_hash,
    )
    for proof in evaluation.m10_stage_outcome.pair_proofs
)
home_evidence = tuple(
    self._home_check_evidence(
        check.request_hash,
        check.result_hash,
        candidate.source_binding.source_revision,
        candidate.source_binding.source_state_hash,
    )
    for check in evaluation.m10_stage_outcome.home_exact_checks
)
```

The existing producers are confirmed as `analysis.continuous_clearance_proof` and `analysis.kinematic_sweep`; resolve their existing IDs only. The evaluation resolver must recompute the existing `CandidateEvaluation` model, call the existing CAD replay/currentness validation against the bound source revision, require proof/home coverage, and derive certified metric and limiting pair from the verified proofs instead of accepting envelope summary values.

- [ ] **Step 5: Implement comparison and selection publication/resolution**

The comparison envelope stores both exact `CandidateComparisonRequest` and `CandidateComparisonResult`, ordered candidate/evaluation artifact references, policy/result payload, and result identity. Its resolver loads every referenced evaluation and candidate CAD artifact in the preserved request order and invokes the existing comparison model validation.

The selection envelope stores the exact `CandidateSelection`, selected candidate/evaluation artifact references, and optional comparison artifact reference. Its resolver requires `comparison_used` to match the presence of the comparison reference and requires the resolved comparison result hash to match `selection.comparison_result_hash`.

- [ ] **Step 6: Run candidate unit suite to verify it passes**

Run: `py -3 -m pytest tests/unit/test_candidate_provenance_artifacts.py tests/unit/test_m12_candidate_cad_replay.py tests/unit/test_m12_candidate_evaluation.py tests/unit/test_m12_candidate_comparison.py tests/unit/test_m12_candidate_selection.py -q`

Expected: PASS with all original candidate hash/currentness/selection tests unchanged.

## Task 3: Implement Canonical CAD/M10 Publishers, Resolvers, And Aggregate Proof Validation

**Files:**
- Modify: `src/mechcad_harness/candidates/provenance_artifacts.py`
- Modify: `src/mechcad_harness/candidates/canonical_m10.py` only if needed for a pure aggregate-summary helper
- Test: `tests/unit/test_candidate_provenance_artifacts.py`
- Test: `tests/unit/test_m12_canonical_cad.py`
- Test: `tests/unit/test_m12_canonical_m10.py`

**Interfaces:**
- Consumes: `CanonicalMechanismReconstruction`, `CanonicalCadRealization`, `CanonicalM10VerificationOutcome`, existing `EvidenceStore` records.
- Produces: `publish_canonical_cad`, `resolve_canonical_cad`, `publish_canonical_m10`, `resolve_canonical_m10`.

- [ ] **Step 1: Write failing canonical round-trip and failure tests**

```python
def test_canonical_m10_round_trip_requires_canonical_cad_and_all_evidence(tmp_path):
    service, canonical_cad, outcome = canonical_fixture_with_evidence(tmp_path)
    cad_publication = service.publish_canonical_cad(canonical_cad)
    publication = service.publish_canonical_m10(cad_publication, outcome)

    resolved = service.resolve_canonical_m10(publication.artifact.artifact_id)

    assert resolved.payload.outcome == outcome
    assert resolved.payload.canonical_cad.artifact.sha256 == cad_publication.artifact.sha256
```

Add tests for tampered canonical artifact bytes, wrong project, source revision/state mismatch, altered canonical CAD realization hash, omitted proof/home Evidence, Evidence result/request mismatch, missing selected STEP, altered inventory, incomplete pair proof coverage, and a rehashed nested proof that changes the limiting pair or metric.

- [ ] **Step 2: Run canonical tests to verify they fail**

Run: `py -3 -m pytest tests/unit/test_candidate_provenance_artifacts.py -q`

Expected: FAIL because canonical publishers/resolvers do not exist.

- [ ] **Step 3: Implement canonical CAD publication and strict reload**

The canonical CAD envelope holds the complete `CanonicalCadRealization` and exact source STEP references copied from `selected_source_provenance`. Its resolver must:

```python
state = self.state_manager.load_revision(cad.project_id, cad.revision)
if state_hash(state) != cad.state_hash:
    raise CandidateProvenanceIntegrityError("canonical CAD source state mismatch")
cad.validated_canonical_copy()
```

Then resolve every source STEP in its recorded run scope and require its complete `TrustedSourceArtifact` values and content hashes to match `selected_source_provenance`. This is historical-source verification, not a currentness assertion: a later revision must not make a valid artifact for its bound revision unreadable.

- [ ] **Step 4: Implement canonical M10 aggregate publication and strict reload**

The canonical M10 envelope contains the full `CanonicalM10VerificationOutcome`, the canonical CAD artifact reference, and ordered Evidence references for every `pair_proofs` and `home_exact_checks`. Resolve existing Evidence by exact result/request binding, exactly as Task 2 does.

The resolver must require:

```python
if outcome.cad_realization_hash != canonical_cad.realization_hash:
    raise CandidateProvenanceIntegrityError("canonical M10 CAD identity mismatch")
if set(proof.pair for proof in outcome.pair_proofs) != set(outcome.inventory.checked_pairs):
    raise CandidateProvenanceIntegrityError("canonical M10 proof coverage mismatch")
```

Derive aggregate status using existing outcome validation. Derive the certified metric as the minimum certificate lower-clearance over `VERIFIED_CLEAR` proofs and derive the limiting pair from the same deterministic proof/certificate order. For `COLLISION_WITNESS` or `NOT_PROVEN`, persist the complete result payload and the explicit aggregate status, but do not fabricate a certified metric.

- [ ] **Step 5: Run canonical and regression unit suites**

Run: `py -3 -m pytest tests/unit/test_candidate_provenance_artifacts.py tests/unit/test_m12_canonical_cad.py tests/unit/test_m12_canonical_m10.py -q`

Expected: PASS with unchanged canonical result identities and complete rejection coverage.

## Task 4: Compose Publishers At Production Result Boundaries

**Files:**
- Modify: `src/mechcad_harness/application.py`
- Modify: `src/mechcad_harness/candidates/__init__.py`
- Test: `tests/integration/test_m12_candidate_cad_m10_production.py`

**Interfaces:**
- Consumes: `CandidateProvenanceArtifactService` from Tasks 1-3 and current `ProductionApplication` methods.
- Produces: `ProductionApplication.candidate_provenance_artifact_service` and publication at candidate CAD/evaluation/comparison/selection boundaries.

- [ ] **Step 1: Write failing production composition/delegation tests**

```python
def test_candidate_entrypoints_publish_after_typed_result_exists(tmp_path, monkeypatch):
    application = build_application(tmp_path)
    calls = []
    monkeypatch.setattr(
        application.candidate_provenance_artifact_service,
        "publish_candidate_cad",
        lambda *args: calls.append("cad"),
    )
    monkeypatch.setattr(
        application.candidate_provenance_artifact_service,
        "publish_candidate_evaluation",
        lambda *args: calls.append("evaluation"),
    )

    run_candidate_cad_and_evaluation(application)

    assert calls == ["cad", "evaluation"]
```

Add assertions that an unsuccessful/nonexistent CAD realization does not publish a CAD artifact, no comparison artifact is published when `compare_candidates()` is not called, and selection publication does not select or promote anything.

- [ ] **Step 2: Run production wiring test to verify it fails**

Run: `py -3 -m pytest tests/integration/test_m12_candidate_cad_m10_production.py -q`

Expected: FAIL because no provenance service is composed or called.

- [ ] **Step 3: Compose the service without changing authority boundaries**

In `ProductionApplication.__init__`, construct one service with the existing workspace, project ID, `StateManager`, `EvidenceStore`, and `CandidatePublicationService`. Add it to `_READ_ONLY_DEPENDENCIES`; it must not own `ChangeEngine`, mutate `DesignState`, or create a new state API.

```python
self.candidate_provenance_artifact_service = CandidateProvenanceArtifactService(
    workspace=state_manager.workspace,
    project_id=project_id,
    state_manager=state_manager,
    evidence_store=evidence_store,
    candidate_publication_service=self.candidate_publication_service,
    cad_replay_verifier=self.candidate_cad_realization_service.validate_realization,
)
```

The service must use the existing run-scoped `ArtifactStore` convention. Top-level publish calls select their `ArtifactStore` from the actual participating artifact/reference when available; when a bounded public entrypoint has no caller run/task context, use the established candidate-publication `PUBLISH` run scope and preserve that explicit scope in every downstream `ArtifactReference`. Never infer a run from a semantic hash.

- [ ] **Step 4: Publish only after each existing typed result is valid**

Modify the application methods in this order:

```python
def realize_candidate_cad(...):
    stage = self.candidate_cad_realization_service.realize(...)
    if stage.status is CandidateCadStageStatus.SUCCESS:
        self.candidate_provenance_artifact_service.publish_candidate_cad(...)
    return stage

def evaluate_candidate(...):
    evaluation = self.candidate_evaluation_service.evaluate(...)
    self.candidate_provenance_artifact_service.publish_candidate_evaluation(...)
    return evaluation

def compare_candidates(self, request, evaluations):
    result = self.candidate_comparison_service.compare(request, evaluations)
    self.candidate_provenance_artifact_service.publish_candidate_comparison(request, result, evaluations)
    return result

def select_candidate(...):
    selection = self.candidate_selection_service.select(...)
    self.candidate_provenance_artifact_service.publish_candidate_selection(selection, ...)
    return selection
```

Pass the exact candidate/request/policy/evaluation context already received by each entrypoint. Do not change return types, add selection fields to canonical state, automatically compare/select/promote, or persist not-reached objects as successful CAD/M10 execution artifacts.

- [ ] **Step 5: Run candidate production regression coverage**

Run: `py -3 -m pytest tests/integration/test_m12_candidate_cad_m10_production.py tests/integration/test_m12_revolute_drive_production.py -q`

Expected: PASS without live FreeCAD invocation unless the environment already marks existing live tests runnable.

## Task 5: Close Selection-to-Promotion And Canonical Publication Wiring

**Files:**
- Modify: `src/mechcad_harness/application.py`
- Modify: `src/mechcad_harness/candidates/promotion.py`
- Test: `tests/integration/test_m12_promotion_production.py`

**Interfaces:**
- Consumes: selected candidate provenance artifact, existing `SelectedCandidateDecisionManifest` / `CandidatePromotionResultManifest`, canonical compilers and M10 service.
- Produces: strict `resolve_promoted_candidate_chain`, canonical CAD/M10 publication at normal promotion verification.

- [ ] **Step 1: Write failing durable selection-to-promotion tests**

```python
def test_promotion_verification_resolves_selection_artifact_not_only_selection_hash(tmp_path):
    application, receipt, selection_publication = promoted_fixture(tmp_path)

    result = application.verify_promoted_mechanism(receipt)

    assert result.status is PromotedMechanismVerificationStatus.VERIFIED
    resolved = application.candidate_provenance_artifact_service.resolve_selection_for_promotion(
        receipt.decision_artifact_id
    )
    assert resolved.artifact.artifact_id == selection_publication.artifact.artifact_id
    assert resolved.artifact.sha256 == selection_publication.artifact.sha256
```

Add separate failures for a deleted selection artifact, a selection artifact copied into a foreign project, an artifact with matching selection semantic hash but mismatched recorded run/task metadata, and an optional comparison artifact whose result hash differs from the promotion decision reference. Assert the existing promotion decision/result artifact bytes and semantic hashes are unchanged in every negative case.

- [ ] **Step 2: Run promotion test to verify it fails**

Run: `py -3 -m pytest tests/integration/test_m12_promotion_production.py -q`

Expected: FAIL because promotion verification currently resolves only manifest semantic identities.

- [ ] **Step 3: Expose the provenance service to promotion verification context**

Add `candidate_provenance_artifact_service` to `_PromotionVerificationContext`. In `verify_promoted_mechanism()` immediately after the existing decision/result manifest checks, call the new resolver with the typed decision and receipt. It must resolve the selection artifact using the decision `selection_hash`, obtain the exact artifact metadata and recorded run/task scope, then recursively validate candidate/evaluation/CAD/comparison dependencies.

```python
selection_publication = provenance_service.resolve_selection_for_promotion(
    decision=decision,
    result_manifest=result_manifest,
)
if selection_publication.payload.selection.selection_hash != decision.input_reference.selection_hash:
    raise PromotedMechanismVerificationIntegrityError("promotion selection artifact binding mismatch")
```

Do not add artifact IDs or hashes to `PromotionDecisionInputReference`, `SelectedCandidateDecisionManifest`, `CandidatePromotionResultManifest`, `CandidatePromotionRequest`, or their hash calculations. The exact selection artifact snapshot is a separately durable execution record, joined by the already-protected semantic selection hash.

- [ ] **Step 4: Publish canonical CAD and canonical M10 from fresh canonical results**

In the existing `verify_promoted_mechanism()` canonical sequence, publish only after `CanonicalCadRealization` and `CanonicalM10VerificationOutcome` pass their existing typed validation:

```python
cad_publication = provenance_service.publish_canonical_cad(reconstruction, cad)
m10_publication = provenance_service.publish_canonical_m10(cad_publication, m10)
provenance_service.resolve_canonical_m10(m10_publication.artifact.artifact_id)
```

Use the canonical result's actual bound revision/state and canonical source STEP metadata. Do not reuse candidate CAD, candidate M10, candidate Evidence, or candidate artifact identities as canonical evidence. Keep the existing scope-equivalence and M11 eligibility ordering intact.

- [ ] **Step 5: Run promotion/canonical integration coverage**

Run: `py -3 -m pytest tests/integration/test_m12_promotion_production.py tests/unit/test_m12_promotion_replay.py tests/unit/test_m12_promotion_provenance.py -q`

Expected: PASS; existing decision/result manifests retain their prior semantic hashes.

## Task 6: Prove Restart-Only Reconstruction And Full Failure Matrix

**Files:**
- Modify: `tests/integration/test_m12_promotion_production.py`
- Modify: `tests/integration/test_m12_candidate_cad_m10_production.py`
- Test: `tests/unit/test_candidate_provenance_artifacts.py`

**Interfaces:**
- Consumes: all publishers/resolvers and only scalar artifact locators after process restart.
- Produces: end-to-end candidate and canonical persistence proof without retained typed runtime objects.

- [ ] **Step 1: Write the restart-style test before implementation completion**

```python
def test_restart_reconstructs_full_candidate_and_canonical_chain_from_artifacts_only(tmp_path):
    application, locators = create_and_publish_candidate_promotion_chain(tmp_path)
    del application
    gc.collect()

    restarted = build_application_from_same_workspace(tmp_path)
    chain = restarted.candidate_provenance_artifact_service.resolve_promotion_chain(
        decision_artifact_id=locators.decision_artifact_id,
        decision_artifact_hash=locators.decision_artifact_hash,
        selection_artifact_id=locators.selection_artifact_id,
        selection_artifact_hash=locators.selection_artifact_hash,
        canonical_m10_artifact_id=locators.canonical_m10_artifact_id,
        canonical_m10_artifact_hash=locators.canonical_m10_artifact_hash,
    )

    assert chain.selection.payload.selection.selection_hash == locators.selection_hash
    assert chain.canonical_m10.payload.outcome.outcome_hash == locators.canonical_m10_outcome_hash
```

The test must retain only scalar artifact IDs/hashes and declared project/workspace configuration after deletion. It must not pass original candidate/evaluation/CAD/Python object references into any resolver.

- [ ] **Step 2: Add focused mutation matrix tests**

For each resolver boundary, mutate one persisted byte file or metadata file in a copied temporary workspace and assert a specific rejection:

```python
@pytest.mark.parametrize(
    "mutation, expected",
    [
        ("artifact-content", "byte/hash"),
        ("wrong-artifact-type", "type"),
        ("foreign-project", "project"),
        ("source-revision", "source"),
        ("missing-step", "source"),
        ("missing-evidence", "Evidence"),
        ("nested-hash", "identity"),
    ],
)
def test_restart_chain_rejects_tampered_dependency(tmp_path, mutation, expected):
    ...
```

Cover candidate CAD, evaluation, comparison, selection, canonical CAD, and canonical M10. Verify a semantic-hash collision/replay in a distinct run is rejected as ambiguous unless the enclosing `ArtifactReference` identifies the exact recorded run and byte hash.

- [ ] **Step 3: Run focused persistence and integration suites**

Run: `py -3 -m pytest tests/unit/test_candidate_provenance_artifacts.py tests/integration/test_m12_candidate_cad_m10_production.py tests/integration/test_m12_promotion_production.py -q`

Expected: PASS. Do not invoke the MINI project test or any live command.

## Task 7: Run Required Regression And Static Verification

**Files:**
- Modify only files completed by Tasks 1-6.

**Interfaces:**
- Consumes: complete implementation and focused tests.
- Produces: command-scoped regression evidence for the remediation report.

- [ ] **Step 1: Run M12/M13 protected regression suites**

Run:

```text
py -3 -m pytest tests/unit/test_m12_candidate_cad_replay.py tests/unit/test_m12_candidate_evaluation.py tests/unit/test_m12_candidate_comparison.py tests/unit/test_m12_candidate_selection.py tests/unit/test_m12_canonical_cad.py tests/unit/test_m12_canonical_m10.py tests/unit/test_m12_promotion_replay.py tests/unit/test_m12_promotion_provenance.py tests/unit/test_m13_3_candidate_evaluation.py tests/unit/test_m13_3_fresh_canonical_m10.py tests/unit/test_m13_4e_promotion_application.py -q
```

Expected: PASS. Record exact collection/pass/fail/skip totals from this invocation only.

- [ ] **Step 2: Run non-live integration regressions**

Run:

```text
py -3 -m pytest tests/integration/test_m12_candidate_cad_m10_production.py tests/integration/test_m12_promotion_production.py tests/integration/test_m13_4e_promotion_evidence_acceptance.py -q
```

Expected: PASS or only pre-existing environment-gated skips. Do not enable `MECHCAD_FREECADCMD` or invoke MINI.

- [ ] **Step 3: Run static checks**

Run:

```text
py -3 -m compileall -q src/mechcad_harness tests
git diff --check
```

Expected: `compileall` exit code 0. For `git diff --check`, distinguish any pre-existing unrelated diagnostics from newly introduced diagnostics; do not edit unrelated files.

- [ ] **Step 4: Verify protected historical records remain untouched**

Run:

```text
git diff -- projects/mini_rotary_fixture docs/audit/MECHCAD_MINI_ROTARY_FIXTURE_COMPLETION_REPORT.md docs/audit/MECHCAD_MINI_ROTARY_FIXTURE_2026-09-16_AXIAL_LOWERING_REMEDIATION.md
```

Expected: no remediation-authored changes to historical MINI execution material, and no generated artifacts attached to Revision 3 or Revision 4.

## Remediation Report Requirements

Report after successful implementation:

- exact files changed;
- each durable artifact schema/prefix and whether `ArtifactStore`/`EvidenceStore` was reused;
- every publisher/resolver and production call site;
- exact semantic bindings, artifact execution references, source STEP references, and Evidence bindings retained by each envelope;
- selection-to-promotion resolution mechanics and confirmation that promotion manifest wire/hash contracts were unchanged;
- focused and regression command results with exact observed totals;
- `compileall` and `git diff --check` results;
- confirmation that historical MINI Revision 3 and Revision 4 were not modified and no historical execution evidence was fabricated;
- no live MINI rerun claim or execution.

## Plan Self-Review

- Spec coverage: Tasks 1-3 implement deterministic serialization, strict publish/resolve, source/project/run/task/state/hash validation, source STEP verification, Evidence bindings, and every required durable object. Tasks 4-5 wire normal production candidate and canonical paths, including the selection-to-promotion edge. Task 6 proves restart reconstruction and failure behavior. Task 7 preserves M12/M13 gates and executes requested static checks.
- Staleness correction: existing single-axis continuous-proof and home-check Evidence writers were verified in current `application.py`; this plan binds them and does not create duplicate Evidence.
- Wire/hash safety: no task changes existing result model fields or promotion manifest payloads. The only promotion join is strict resolution from the protected selection semantic hash to a deterministic, byte-verified selection artifact with exact execution metadata.
- Scope: M13 multi-joint result models are deliberately not added to the six MINI/M12 durable object envelopes requested here. Their existing M13-4 decision/result and Evidence tests remain regression gates; this avoids unauthorized broadening.
- Historical safety: no task writes to MINI retained workspaces, revisions, reports, or fixtures, and Task 7 explicitly checks that condition.
