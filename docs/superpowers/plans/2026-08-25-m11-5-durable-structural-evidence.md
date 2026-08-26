# M11-5 Durable Structural Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish one immutable, independently verifiable structural Evidence record for trusted M11-4 PASS, FAIL, and NOT_EVALUABLE outcomes, with bounded repeatability and mesh-convergence evidence.

**Architecture:** Keep `EvidenceStore` as the sole evidence persistence boundary and add one optional frozen `StructuralEvidencePayload` to the generic `Evidence` model. A structural-only publication/verifier service will reconstruct the request from evidence semantics, reload the immutable state revision and durable manifest/artifacts, and rederive M11-4 result, verification, material authority, and optional analytical equations without starting external runtimes. Separate pure services compare normal evidence records for repeatability and convergence; each convergence level first becomes normal structural evidence.

**Tech Stack:** Python 3.11+, Pydantic v2, SHA-256 canonical JSON, existing `StateManager`, `ArtifactStore`, `EvidenceStore`, FreeCAD 1.1.3, Gmsh 4.15.0, CalculiX 2.22, pytest.

## Global Constraints

- Preserve Python 3.11+, Pydantic v2, UTC-aware datetime requirements, and existing canonical JSON/hash conventions.
- Do not reset, stash, clean, checkout, revert, discard, commit, or push existing work.
- Reuse existing `EvidenceStore`; do not add a structural evidence database or raw store mutation API.
- `Evidence` may import only typed structural data models, never structural services, runtime discovery, verifier code, or `ProductionApplication`.
- Keep `DesignState` canonical: it contains `StructuralAnalysisDefinition`, not `StructuralAnalysisRequest`; reconstruct requests from durable evidence semantics.
- Preserve M11-2/M11-3/M11-4 definition, request, semantic-region, C3D10, load-lowering, parser, criterion, stress-representation, and analytical-validation semantics.
- Reverify every referenced STEP/MSH/INP/FRD/DAT/LOG/manifest byte through `ArtifactStore`; never directly read artifact paths or parse unverified bytes.
- Accepted Evidence may preserve trusted engineering `PASS`, `FAIL`, or `NOT_EVALUABLE`; integrity/execution failures never become `NOT_EVALUABLE` or accepted evidence.
- Historical verification must not invoke or require FreeCAD/Gmsh/CalculiX. Runtime compatibility is only for new execution/reproduction.
- `semantic_hash` must hash the complete canonical structural payload with `semantic_hash` itself excluded; exclude run ID and storage/volatile fields.
- Evidence records are immutable. State advancement makes a record stale relative to current state, not corrupt; currentness is `CURRENT`, `STALE_RELATIVE_TO_CURRENT_STATE`, or `CURRENTNESS_UNAVAILABLE`.
- Repeatability policy is declared and hashed before the first compared live execution. Do not require raw artifact bytes or mesh node/element IDs to be equal.
- Convergence uses predeclared bounded mesh levels and the existing FE-consistent free-end displacement metric only; no adaptive refinement, generic mesh isomorphism, stress convergence, global marker, or M11-6 acceptance.

---

## File Structure

- Create: `src/mechcad_harness/structural/evidence.py`
  - Frozen structural evidence payload, provenance/binding models, schema/hash helpers, currentness/result status types, and pure policy/result models for repeatability and convergence.
- Create: `src/mechcad_harness/structural/evidence_service.py`
  - Trusted publication, runtime-independent reload verification, and separate repeatability/convergence evaluators.
- Modify: `src/mechcad_harness/models/evidence.py`
  - Add the optional typed structural payload while preserving legacy Evidence parsing.
- Modify: `src/mechcad_harness/structural/validation.py`
  - Add pure analytical-validation reconstruction from persisted policy/observations/result/manifest/mesh bytes without FreeCAD realization.
- Modify: `src/mechcad_harness/application.py`
  - Compose the structural evidence service and expose only high-level publish/verify/currentness/repeatability/convergence operations.
- Modify: `src/mechcad_harness/state/manager.py`
  - Add the smallest public read-only current-pointer accessor for currentness checks; structural evidence code must not call `_read_current()`.
- Modify: `src/mechcad_harness/structural/__init__.py`
  - Export public structural evidence types/services.
- Modify: `config/dependencies.yaml` only if `analysis.structural` cannot store an Evidence record with the existing graph; do not redefine historical validity semantics.
- Create: `tests/unit/test_structural_evidence_models.py`
  - Hashing, schema, immutability, legacy Evidence compatibility, policy validation, and pure comparison tests.
- Create: `tests/unit/test_structural_evidence_verifier.py`
  - Fresh-store verification, tamper/replay/currentness/runtime-independent tests using persisted fixture records.
- Create: `tests/integration/test_m11_5_live_structural.py`
  - Real PASS/FAIL/NOT_EVALUABLE publication/reload, historical stale check, policy-predeclared repeatability, and three-level convergence capstones.
- Modify: `README.md`, `AGENTS.md`, and the six normative architecture documents listed in the M11-5 request.
  - State the bounded M11-5 capability and limitations without claiming M11-6 acceptance.
- Create: `docs/audit/MECHCAD_M11_5_COMPLETION_REPORT.md`
  - Required acceptance evidence, commands, counts/timing, live measurements, limitations, and M11-6 boundary.

## Task 1: Define Frozen Structural Evidence and Study Models

**Files:**
- Create: `src/mechcad_harness/structural/evidence.py`
- Create: `tests/unit/test_structural_evidence_models.py`

**Interfaces:**
- Consumes: `StructuralAnalysisRequest`, `StructuralExecutionManifest`, `StructuralAnalysisResult`, `StructuralVerificationResult`, `StructuralAnalyticalValidationResult`, `StructuralMeshManifest`, `BackendProvenance`.
- Produces: `StructuralEvidencePayload`, `StructuralPipelineProvenance`, `StructuralEvidenceCurrentness`, `StructuralEvidenceVerification`, `StructuralRepeatabilityPolicy`, `StructuralRepeatabilityResult`, `StructuralMeshConvergenceStudy`, `StructuralMeshConvergenceResult`, `structural_evidence_hash(payload)`.

Use an explicit typed subject discriminator for durable records:
`EvidenceSubject.STRUCTURAL_ANALYSIS` for ordinary M11-4 level evidence and
`EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY` for a convergence-study record.
The ordinary record uses `kind="analysis.structural"`; the study record uses
`kind="analysis.structural.convergence"` and binds only verified level evidence
IDs/hashes plus study policy/result. It must not masquerade as an M11-4
physical analysis result.

- [ ] **Step 1: Write failing payload/hash/legacy model tests**

```python
def test_structural_evidence_hash_excludes_only_its_own_field(evidence_payload):
    first = evidence_payload
    second = first.model_copy(update={"semantic_hash": "sha256:" + "0" * 64})

    assert structural_evidence_hash(first) == structural_evidence_hash(second)
    assert first.semantic_hash == structural_evidence_hash(first)
    assert structural_evidence_hash(
        first.model_copy(update={"request": first.request.model_copy(
            update={"request_hash": "sha256:" + "f" * 64}
        )})
    ) != first.semantic_hash


def test_payload_rejects_unknown_schema_version(evidence_payload):
    with pytest.raises(ValidationError, match="schema"):
        StructuralEvidencePayload.model_validate({
            **evidence_payload.model_dump(mode="json"),
            "schema_version": "structural-evidence@999",
            "semantic_hash": "pending",
        })


def test_repeatability_and_convergence_policies_reject_unbounded_or_invalid_sequences():
    with pytest.raises(ValidationError, match="unique"):
        StructuralMeshConvergenceStudy(
            policy_id="study", mesh_specifications=(MESH_5, MESH_5, MESH_2),
            load_case_id="LC-1", response_metric=FREE_END_TRANSVERSE_DISPLACEMENT,
            relative_change_threshold=0.02, epsilon=1e-12, max_levels=3,
            required_runtime_identities=TRUSTED_RUNTIME_IDENTITIES,
        )


def test_structural_models_are_frozen_and_currentness_is_separate(evidence_payload):
    with pytest.raises(ValidationError):
        evidence_payload.schema_version = "structural-evidence@2"
    assert tuple(StructuralEvidenceCurrentness) == (
        StructuralEvidenceCurrentness.CURRENT,
        StructuralEvidenceCurrentness.STALE_RELATIVE_TO_CURRENT_STATE,
        StructuralEvidenceCurrentness.CURRENTNESS_UNAVAILABLE,
    )
```

- [ ] **Step 2: Run the new model test file and verify it fails**

Run: `py -3 -m pytest tests/unit/test_structural_evidence_models.py -q`

Expected: collection failure because `mechcad_harness.structural.evidence` does not exist.

- [ ] **Step 3: Implement payload and policy models using current structural hashing conventions**

```python
STRUCTURAL_EVIDENCE_SCHEMA_VERSION = "structural-evidence@1"


class StructuralEvidencePayload(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[STRUCTURAL_EVIDENCE_SCHEMA_VERSION] = STRUCTURAL_EVIDENCE_SCHEMA_VERSION
    request: StructuralAnalysisRequest
    execution_manifest_artifact_id: str = Field(min_length=1)
    execution_manifest_artifact_hash: str = Field(min_length=1)
    execution_manifest: StructuralExecutionManifest
    result: StructuralAnalysisResult
    verification: StructuralVerificationResult
    analytical_validation: StructuralAnalyticalValidationResult | None = None
    analytical_geometry_observation: CantileverGeometryObservation | None = None
    analytical_material_observation: CantileverMaterialObservation | None = None
    aggregate_provenance: StructuralPipelineProvenance
    mesh_convergence_status: StructuralMeshConvergenceStatus = StructuralMeshConvergenceStatus.NOT_EVALUATED
    repeatability: StructuralRepeatabilityResult | None = None
    convergence: StructuralMeshConvergenceResult | None = None
    subject: EvidenceSubject = EvidenceSubject.STRUCTURAL_ANALYSIS
    semantic_hash: str = "pending"

    @model_validator(mode="after")
    def validate_hash_and_bindings(self):
        if self.subject is EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY and self.convergence is None:
            raise ValueError("convergence-study evidence requires a convergence payload")
        expected = structural_evidence_hash(self)
        if self.semantic_hash == "pending":
            object.__setattr__(self, "semantic_hash", expected)
        elif self.semantic_hash != expected:
            raise ValueError("structural evidence semantic hash does not match canonical payload")
        return self


def structural_evidence_hash(payload: StructuralEvidencePayload) -> str:
    core = payload.model_dump(mode="json")
    core.pop("semantic_hash", None)
    return _hash_payload(_engineering_payload(core))
```

Implement source/request/definition/result/verification/manifest equality validators, ordered unique level evidence bindings, finite numeric thresholds, bounded `max_levels`, enum outcomes, and a policy hash helper that excludes only the policy hash itself. Make `StructuralRepeatabilityPolicy` list semantic summaries by explicit IDs and prohibit node/element correspondence fields.

- [ ] **Step 4: Run the model tests and existing structural model regressions**

Run: `py -3 -m pytest tests/unit/test_structural_evidence_models.py tests/unit/test_structural_models.py tests/unit/test_structural_results.py -q`

Expected: PASS.

## Task 2: Add Structural Payload to Generic Evidence Without Layer Leakage

**Files:**
- Modify: `src/mechcad_harness/models/evidence.py`
- Modify: `src/mechcad_harness/structural/__init__.py`
- Modify: `tests/unit/test_structural_evidence_models.py`

**Interfaces:**
- Consumes: `StructuralEvidencePayload` as a frozen typed data model only.
- Produces: `Evidence.structural_evidence_payload: StructuralEvidencePayload | None`, typed structural subject/discriminator fields for structural payloads, and normal `EvidenceStore` persistence compatibility.

- [ ] **Step 1: Write failing compatibility/layering tests**

```python
def test_legacy_evidence_round_trip_has_no_structural_payload():
    legacy = Evidence(id="EVD-1", kind="analysis.structural", summary="legacy", revision=1, state_hash="sha256:state")
    reloaded = Evidence.model_validate_json(legacy.model_dump_json())

    assert reloaded.structural_evidence_payload is None


def test_generic_evidence_module_imports_only_structural_data_model():
    source = Path("src/mechcad_harness/models/evidence.py").read_text(encoding="utf-8")

    assert "structural.evidence_service" not in source
    assert "ProductionApplication" not in source
    assert "discover_" not in source
```

- [ ] **Step 2: Run compatibility tests and verify failure**

Run: `py -3 -m pytest tests/unit/test_structural_evidence_models.py::test_legacy_evidence_round_trip_has_no_structural_payload -q`

Expected: FAIL because `Evidence` has no `structural_evidence_payload` field.

- [ ] **Step 3: Add the optional typed field and lazy data-model export**

```python
from mechcad_harness.structural.evidence import StructuralEvidencePayload


class Evidence(StateBinding):
    # Existing fields remain unchanged.
    subject: EvidenceSubject | None = None
    structural_evidence_payload: StructuralEvidencePayload | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
```

Set ordinary structural records to `kind="analysis.structural"` and
`subject=EvidenceSubject.STRUCTURAL_ANALYSIS`; set convergence-study records to
`kind="analysis.structural.convergence"` and
`subject=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY`. Legacy records keep
`subject=None`. Keep `EvidenceStore.write_evidence()` and `load_evidence()`
generic. Do not add structural checks, structural service imports, or direct
filesystem access to `dependency/storage.py`.

- [ ] **Step 4: Run compatibility and existing evidence regressions**

Run: `py -3 -m pytest tests/unit/test_structural_evidence_models.py tests/unit/test_state_foundation.py tests/unit/test_production_application.py -q`

Expected: PASS.

## Task 3: Implement Runtime-Independent Structural Evidence Verification

**Files:**
- Create: `src/mechcad_harness/structural/evidence_service.py`
- Modify: `src/mechcad_harness/structural/validation.py`
- Create: `tests/unit/test_structural_evidence_verifier.py`

**Interfaces:**
- Consumes: workspace path, project ID, fresh `StateManager`, fresh `ArtifactStore`, fresh `EvidenceStore`, `evidence_id`.
- Produces: `StructuralEvidenceVerifier.verify(evidence_id) -> StructuralEvidenceVerification` and `StructuralEvidenceVerifier.currentness(evidence_id) -> StructuralEvidenceCurrentness`.

Add this smallest public StateManager accessor before using it from production
structural evidence code:

```python
def load_current_pointer(self, project_id: str) -> dict[str, Any]:
    return dict(self._read_current(project_id))
```

The private helper remains an internal implementation detail; structural
evidence code calls only `load_current_pointer()`.

The verifier must explicitly own/use a fresh `ArtifactStore` dependency in
addition to `StateManager` and `EvidenceStore`. Because artifacts are
run-scoped, the verifier may construct a run-scoped `ArtifactStore` from the
durable run identity in the Evidence payload, but every raw read still goes
through `read_verified_strict()` or the existing trusted equivalent. Fresh
process tests must construct fresh `StateManager`, `ArtifactStore`,
`EvidenceStore`, and `StructuralEvidenceVerifier` instances.

- [ ] **Step 1: Write failing verifier tests using only durable records**

```python
def test_verifier_reconstructs_request_from_payload_and_immutable_definition(persisted_evidence):
    verifier = fresh_verifier(persisted_evidence.workspace, persisted_evidence.project_id)

    verified = verifier.verify(persisted_evidence.evidence_id)

    assert verified.valid is True
    assert verified.request_hash == persisted_evidence.request_hash
    assert verified.engineering_status is StructuralCriterionStatus.PASS


@pytest.mark.parametrize("artifact_type", [ArtifactType.MSH, ArtifactType.INP, ArtifactType.FRD, ArtifactType.DAT, ArtifactType.LOG])
def test_verifier_fails_before_parsing_tampered_artifact(persisted_evidence, artifact_type, monkeypatch):
    tamper_artifact_bytes(persisted_evidence, artifact_type)
    parser = Mock(wraps=CalculiXFrdResultParser().parse)
    monkeypatch.setattr("mechcad_harness.structural.evidence_service.CalculiXFrdResultParser", lambda: parser)

    with pytest.raises(StructuralEvidenceIntegrityError):
        fresh_verifier(persisted_evidence.workspace, persisted_evidence.project_id).verify(persisted_evidence.evidence_id)

    assert parser.call_count == 0


def test_historical_verification_does_not_call_runtime_discovery(persisted_evidence, monkeypatch):
    monkeypatch.setattr("mechcad_harness.structural.runtime.discover_freecad", lambda: pytest.fail("unexpected runtime discovery"))
    monkeypatch.setattr("mechcad_harness.structural.runtime.discover_gmsh", lambda: pytest.fail("unexpected runtime discovery"))
    monkeypatch.setattr("mechcad_harness.structural.runtime.discover_calculix", lambda: pytest.fail("unexpected runtime discovery"))

    assert fresh_verifier(persisted_evidence.workspace, persisted_evidence.project_id).verify(persisted_evidence.evidence_id).valid
```

- [ ] **Step 2: Run verifier tests and verify failure**

Run: `py -3 -m pytest tests/unit/test_structural_evidence_verifier.py -q`

Expected: collection failure because `StructuralEvidenceVerifier` does not exist.

- [ ] **Step 3: Implement strict dependency reload and pure analytical reconstruction**

```python
class StructuralEvidenceVerifier:
    def __init__(self, *, workspace: str | Path, project_id: str, state_manager: StateManager, artifact_store: ArtifactStore, evidence_store: EvidenceStore):
        self.workspace = Path(workspace)
        self.project_id = project_id
        self.state_manager = state_manager
        self.artifact_store = artifact_store
        self.evidence_store = evidence_store

    def verify(self, evidence_id: str) -> StructuralEvidenceVerification:
        evidence = self.evidence_store.load_evidence(self.project_id, evidence_id)
        payload = _require_structural_payload(evidence)
        _verify_payload_hash(payload)
        definition = self._load_bound_definition(payload)
        request = _reconstruct_request(payload.request, definition)
        manifest = self._load_verified_manifest(payload, request)
        result = _reconstruct_result_from_verified_artifacts(self.workspace, self.project_id, request, definition, manifest)
        verification = StructuralVerificationService().evaluate(result, definition)
        _verify_payload_result_and_verification(payload, result, verification)
        _verify_material_authority_findings(payload, definition)
        _verify_persisted_analytical_validation(payload, request, definition, manifest, result)
        _verify_pipeline_provenance(payload, manifest)
        return StructuralEvidenceVerification(
            evidence_id=evidence.id,
            payload=payload,
            valid=True,
            engineering_status=verification.overall_status,
        )
```

`_load_verified_manifest` must use the payload's manifest artifact ID and expected byte hash through `ArtifactStore.read_verified_strict(..., expected_type=ArtifactType.JSON, expected_hash=...)`; do not make deterministic manifest-ID derivation the authority. `StructuralResultInterpreter` may parse verified persisted artifact bytes but must be used with no runtime discovery. Add a pure validation helper that reuses typed persisted `CantileverGeometryObservation` and `CantileverMaterialObservation`, parsed trusted MSH bytes, the policy, request, definition, manifest, and result; it must not call `StructuralFreeCADGeometryAdapter`.

- [ ] **Step 4: Implement separate currentness lookup**

```python
    def currentness(self, evidence_id: str) -> StructuralEvidenceCurrentness:
        payload = _require_structural_payload(self.evidence_store.load_evidence(self.project_id, evidence_id))
        try:
            current = self.state_manager.load_current_pointer(self.project_id)
        except Exception:
            return StructuralEvidenceCurrentness.CURRENTNESS_UNAVAILABLE
        return (
            StructuralEvidenceCurrentness.CURRENT
            if (current.get("revision"), current.get("state_hash")) == (
                payload.request.source_binding.source_revision,
                payload.request.source_binding.source_state_hash,
            )
            else StructuralEvidenceCurrentness.STALE_RELATIVE_TO_CURRENT_STATE
        )
```

Do not call currentness from `verify`; a missing/corrupt current pointer must not change the internal validity result.

- [ ] **Step 5: Run verifier and M11-4 integrity regressions**

Run: `py -3 -m pytest tests/unit/test_structural_evidence_verifier.py tests/unit/test_structural_results.py tests/unit/test_structural_validation_observations.py tests/unit/test_artifacts.py -q`

Expected: PASS.

## Task 4: Publish Complete Evidence Only From Durable M11-4 Authority

**Files:**
- Modify: `src/mechcad_harness/structural/evidence_service.py`
- Modify: `src/mechcad_harness/application.py`
- Modify: `tests/unit/test_structural_evidence_verifier.py`

**Interfaces:**
- Produces: `ProductionApplication.publish_structural_evidence(*, execution_manifest, request=None, analytical_policy=None) -> Evidence`.
- Produces: `ProductionApplication.verify_structural_evidence(evidence_id) -> StructuralEvidenceVerification` and `check_structural_evidence_currentness(evidence_id) -> StructuralEvidenceCurrentness`.

- [ ] **Step 1: Write failing publication authority tests**

```python
def test_publish_reconstructs_trusted_result_not_caller_evaluation(app, completed_execution, policy):
    forged = StructuralAnalysisEvaluation(
        result=completed_execution.evaluation.result.model_copy(update={"result_hash": "sha256:" + "0" * 64}),
        verification=completed_execution.evaluation.verification,
    )

    evidence = app.publish_structural_evidence(
        execution_manifest=completed_execution.manifest,
        request=completed_execution.request,
        analytical_policy=policy,
    )

    assert evidence.structural_evidence_payload.result.result_hash != forged.result.result_hash


@pytest.mark.parametrize("mutator", [tamper_manifest, tamper_frd, tamper_dat, tamper_mesh, tamper_deck, tamper_log])
def test_integrity_failure_does_not_publish_accepted_evidence(app, completed_execution, mutator):
    mutator(completed_execution)

    with pytest.raises(StructuralEvidenceIntegrityError):
        app.publish_structural_evidence(execution_manifest=completed_execution.manifest, request=completed_execution.request)

    assert list_evidence_ids(app) == []
```

- [ ] **Step 2: Run publication tests and verify failure**

Run: `py -3 -m pytest tests/unit/test_structural_evidence_verifier.py::test_publish_reconstructs_trusted_result_not_caller_evaluation -q`

Expected: FAIL because `ProductionApplication.publish_structural_evidence` does not exist.

- [ ] **Step 3: Implement publication sequence and immediate fresh verification**

```python
class StructuralEvidencePublisher:
    def publish(self, *, execution_manifest, request, analytical_policy=None) -> Evidence:
        # Reconstruct from durable manifest/artifacts/revision; arguments only locate authority.
        payload = self._construct_verified_payload(execution_manifest=execution_manifest, request=request, analytical_policy=analytical_policy)
        evidence = Evidence(
            id=structural_evidence_id(payload),
            kind="analysis.structural",
            summary=_structural_evidence_summary(payload),
            revision=payload.request.source_binding.source_revision,
            state_hash=payload.request.source_binding.source_state_hash,
            producer_type="structural_evidence",
            producer_name="mechcad-structural-evidence@1",
            producer_version="1",
            producer_result_id=payload.result.result_hash,
            input_hash=payload.request.request_hash,
            output_hash=payload.semantic_hash,
            structural_evidence_payload=payload,
        )
        self.evidence_store.write_evidence(self.project_id, evidence)
        self.fresh_verifier_factory().verify(evidence.id)
        return evidence
```

`_construct_verified_payload` must first verify source revision/definition/request, then all raw artifacts and manifest, then derive result/verification/analytical data. It must reject fake/test provider provenance using exact trusted backend provenance/identity equality rather than a substring check. Do not catch post-write verifier exceptions and return the Evidence; allow failure to surface without mutation or repair.

Add composition-owned publisher/verifier instances to `ProductionApplication._READ_ONLY_DEPENDENCIES`, create them from existing `state_manager`, `evidence_store`, workspace, and project ID, and expose only the named high-level methods. Do not add a ToolBroker registration.

- [ ] **Step 4: Run publication and production regression tests**

Run: `py -3 -m pytest tests/unit/test_structural_evidence_verifier.py tests/unit/test_production_application.py tests/unit/test_structural_service.py tests/unit/test_structural_pipeline_contracts.py -q`

Expected: PASS.

## Task 5: Add Replay, Tamper, Historical, and Runtime-Independent Coverage

**Files:**
- Modify: `tests/unit/test_structural_evidence_verifier.py`
- Modify: `tests/unit/test_artifacts.py` only when an existing hardening assertion is missing.

**Interfaces:**
- Consumes: durable Evidence IDs and fresh stores/verifier only.
- Produces: regression proof that payload/artifact tampering and replay fail closed while old source-bound evidence remains valid after state advance.

- [ ] **Step 1: Write failing adversarial tests**

```python
@pytest.mark.parametrize("path,value", [
    (("verification", "overall_status"), "pass"),
    (("verification", "criterion_results", 0, "observed_value"), 999.0),
    (("result", "result_hash"), "sha256:" + "0" * 64),
    (("execution_manifest", "mesh_artifact_hash"), "sha256:" + "0" * 64),
    (("result", "parser_provenance", "frd_parser_identity"), "foreign-parser@1"),
    (("request", "source_binding", "source_state_hash"), "sha256:" + "0" * 64),
])
def test_evidence_payload_tamper_fails_without_rehashing(persisted_evidence, path, value):
    mutate_evidence_json(persisted_evidence, path, value)

    with pytest.raises(StructuralEvidenceIntegrityError):
        fresh_verifier(persisted_evidence.workspace, persisted_evidence.project_id).verify(persisted_evidence.evidence_id)


def test_old_evidence_is_valid_but_stale_after_revision_advance(persisted_evidence, advance_state):
    advance_state(persisted_evidence.project_id)
    verifier = fresh_verifier(persisted_evidence.workspace, persisted_evidence.project_id)

    assert verifier.verify(persisted_evidence.evidence_id).valid
    assert verifier.currentness(persisted_evidence.evidence_id) is StructuralEvidenceCurrentness.STALE_RELATIVE_TO_CURRENT_STATE


def test_replay_to_another_project_revision_case_criterion_material_or_policy_fails(persisted_evidence):
    for attack in (replay_project, replay_revision, replay_load_case, replay_criterion, replay_material_authority, replay_analytical_policy):
        attacked = copy_durable_workspace(persisted_evidence.workspace)
        attack(attacked)
        with pytest.raises(StructuralEvidenceIntegrityError):
            fresh_verifier(attacked, persisted_evidence.project_id).verify(persisted_evidence.evidence_id)
```

- [ ] **Step 2: Run adversarial tests and verify failure**

Run: `py -3 -m pytest tests/unit/test_structural_evidence_verifier.py -q`

Expected: FAIL until each verifier binding is explicit.

- [ ] **Step 3: Implement every explicit revalidation check**

Verify exact project ID, revision/state hash, definition ID/hash, request hash/full semantics, target body, selected ordered cases, criterion ID/hash/limit/domain, material assignment snapshots and authority decisions, analytical policy/full semantics, result/verification/validation hashes, field representation, parser identities, direct artifact producer identity/version/backend provenance, aggregate provenance, artifact scope/type/input/hash/size, and manifest ID/hash/content.

For historical runtime proof, construct a fresh verifier only and patch all discovery functions to return unavailable/incompatible values. Assert no discovery functions, `subprocess.run`, FreeCAD adapter, mesher, or solver provider are invoked. Keep Artifacts byte-verified through the existing store.

- [ ] **Step 4: Run adversarial and ArtifactStore hardening suites**

Run: `py -3 -m pytest tests/unit/test_structural_evidence_verifier.py tests/unit/test_artifacts.py tests/unit/test_structural_results.py -q`

Expected: PASS, including lookup-ID, traversal, escaping path, symlink/reparse, dangling symlink, scope/type, size, and SHA regression cases.

## Task 6: Implement Repeatability Comparison Over Verified Evidence

**Files:**
- Modify: `src/mechcad_harness/structural/evidence_service.py`
- Modify: `tests/unit/test_structural_evidence_models.py`
- Modify: `tests/unit/test_structural_evidence_verifier.py`

**Interfaces:**
- Produces: `StructuralRepeatabilityService.compare(*, policy, first_evidence_id, second_evidence_id) -> StructuralRepeatabilityResult`.
- Produces: `ProductionApplication.compare_structural_repeatability(...) -> StructuralRepeatabilityResult`.

- [ ] **Step 1: Write failing semantic-summary comparison tests**

```python
def test_repeatability_ignores_raw_bytes_and_mesh_ids_but_compares_declared_summaries(two_verified_evidences, repeatability_policy):
    result = StructuralRepeatabilityService(two_verified_evidences.verifier).compare(
        policy=repeatability_policy,
        first_evidence_id=two_verified_evidences.first_id,
        second_evidence_id=two_verified_evidences.second_id,
    )

    assert result.status is StructuralRepeatabilityStatus.REPEATABLE
    assert "mesh_node_ids" not in result.compared_fields


def test_repeatability_returns_not_repeatable_for_predeclared_tolerance_exceedance(two_verified_evidences, repeatability_policy):
    change_persisted_summary(two_verified_evidences, "free_end_displacement_mm", 10.0)

    assert StructuralRepeatabilityService(two_verified_evidences.verifier).compare(
        policy=repeatability_policy,
        first_evidence_id=two_verified_evidences.first_id,
        second_evidence_id=two_verified_evidences.second_id,
    ).status is StructuralRepeatabilityStatus.INTEGRITY_FAILURE
```

The second expected status is `INTEGRITY_FAILURE` because direct persisted-byte tampering invalidates Evidence. Add a separate fixture that publishes two valid evidence records whose trusted semantic summaries differ beyond tolerance; that expected status is `NOT_REPEATABLE`.

- [ ] **Step 2: Run repeatability tests and verify failure**

Run: `py -3 -m pytest tests/unit/test_structural_evidence_models.py tests/unit/test_structural_evidence_verifier.py -q`

Expected: FAIL because `StructuralRepeatabilityService` does not exist.

- [ ] **Step 3: Implement comparison after independent verification**

```python
class StructuralRepeatabilityService:
    def __init__(self, verifier: StructuralEvidenceVerifier):
        self.verifier = verifier

    def compare(self, *, policy, first_evidence_id: str, second_evidence_id: str) -> StructuralRepeatabilityResult:
        first = self.verifier.verify(first_evidence_id)
        second = self.verifier.verify(second_evidence_id)
        _require_repeatability_identity(policy, first, second)
        comparisons = _compare_declared_semantic_summaries(policy, first.payload, second.payload)
        return StructuralRepeatabilityResult(
            policy=policy,
            first_evidence_id=first_evidence_id,
            second_evidence_id=second_evidence_id,
            status=(StructuralRepeatabilityStatus.REPEATABLE if all(item.within_tolerance for item in comparisons) else StructuralRepeatabilityStatus.NOT_REPEATABLE),
            comparisons=comparisons,
        )
```

Compare only source/definition/request/runtime identity requirements and declared summaries: free-end metric, maximum displacement, extrapolated-nodal von-Mises summary with explicit representation, reaction force/moment, criterion results, and analytical validation. Do not compare mesh node IDs, element IDs, raw fields, raw bytes, or run IDs. Map verifier failure to `INTEGRITY_FAILURE` in the result without converting it to `NOT_REPEATABLE`.

- [ ] **Step 4: Run repeatability tests**

Run: `py -3 -m pytest tests/unit/test_structural_evidence_models.py tests/unit/test_structural_evidence_verifier.py -q`

Expected: PASS.

## Task 7: Implement Ordered Per-Evidence Mesh-Convergence Evaluation

**Files:**
- Modify: `src/mechcad_harness/structural/evidence_service.py`
- Modify: `src/mechcad_harness/application.py`
- Modify: `tests/unit/test_structural_evidence_models.py`
- Modify: `tests/unit/test_structural_evidence_verifier.py`

**Interfaces:**
- Produces: `StructuralMeshConvergenceService.evaluate(*, study, level_evidence_ids) -> StructuralMeshConvergenceResult`.
- Produces: `ProductionApplication.evaluate_structural_mesh_convergence(...) -> StructuralMeshConvergenceResult`.

- [ ] **Step 1: Write failing convergence outcome tests**

```python
def test_convergence_uses_ordered_independently_verified_level_evidence(convergence_study, level_evidence_ids, verifier):
    result = StructuralMeshConvergenceService(verifier).evaluate(
        study=convergence_study,
        level_evidence_ids=level_evidence_ids,
    )

    assert result.status is StructuralMeshConvergenceStatus.CONVERGED
    assert tuple(level.evidence_id for level in result.levels) == level_evidence_ids
    assert result.levels[-1].previous_relative_change <= convergence_study.relative_change_threshold


@pytest.mark.parametrize("invalid", ["insufficient", "duplicate_mesh", "mismatched_source", "mismatched_case", "missing_metric", "tampered_level"])
def test_convergence_classifies_semantic_and_integrity_failures(convergence_study, invalid, make_levels, verifier):
    result = StructuralMeshConvergenceService(verifier).evaluate(
        study=convergence_study,
        level_evidence_ids=make_levels(invalid),
    )

    assert result.status is {
        "insufficient": StructuralMeshConvergenceStatus.INTEGRITY_FAILURE,
        "duplicate_mesh": StructuralMeshConvergenceStatus.INTEGRITY_FAILURE,
        "mismatched_source": StructuralMeshConvergenceStatus.INTEGRITY_FAILURE,
        "mismatched_case": StructuralMeshConvergenceStatus.INTEGRITY_FAILURE,
        "missing_metric": StructuralMeshConvergenceStatus.NOT_EVALUABLE,
        "tampered_level": StructuralMeshConvergenceStatus.INTEGRITY_FAILURE,
    }[invalid]
```

- [ ] **Step 2: Run convergence tests and verify failure**

Run: `py -3 -m pytest tests/unit/test_structural_evidence_models.py tests/unit/test_structural_evidence_verifier.py -q`

Expected: FAIL because `StructuralMeshConvergenceService` does not exist.

- [ ] **Step 3: Implement bounded evaluator and convergence-study evidence publication**

```python
class StructuralMeshConvergenceService:
    def evaluate(self, *, study, level_evidence_ids: tuple[str, ...]) -> StructuralMeshConvergenceResult:
        if len(level_evidence_ids) < study.minimum_mesh_levels or len(level_evidence_ids) > study.max_levels:
            return _integrity_failure(study, "level_count_mismatch")
        verified = tuple(self.verifier.verify(evidence_id) for evidence_id in level_evidence_ids)
        _require_ordered_mesh_specs(study, verified)
        _require_same_problem_and_runtime(study, verified)
        levels = _extract_displacement_metric(study, verified)
        if levels is None:
            return _not_evaluable(study, "response_metric_unavailable")
        return _classify_relative_changes(study, levels)
```

Require each level to be normal structural Evidence with `mesh_convergence_status=NOT_EVALUATED`, a unique expected mesh specification hash, the same source/definition/load-case semantics, and policy-required persisted identities. Extract only the declared free-end transverse-displacement metric/domain from verified result/analytical data. Record analytical reference/error if present but do not use it for convergence classification. Publish any convergence-study record as a new complete `StructuralEvidencePayload`, retaining the three prior evidence IDs and semantic hashes; never mutate E1/E2/E3.

- [ ] **Step 4: Run convergence tests**

Run: `py -3 -m pytest tests/unit/test_structural_evidence_models.py tests/unit/test_structural_evidence_verifier.py -q`

Expected: PASS.

## Task 8: Prove Live PASS, FAIL, NOT_EVALUABLE, Repeatability, and Convergence

**Files:**
- Create: `tests/integration/test_m11_5_live_structural.py`
- Modify: `tests/integration/test_m11_4_live_structural.py` only to expose reusable fixture helpers without changing assertions.

**Interfaces:**
- Consumes: existing real M11-4 cantilever fixture and production app composition.
- Produces: six M11-5 live capstones using freshly reloaded durable evidence.

- [ ] **Step 1: Write live capstone tests before adding helper orchestration**

```python
def test_live_pass_evidence_fresh_reload(live_app, tmp_path):
    execution, request, policy = execute_live_pass_cantilever(live_app, tmp_path)
    evidence = live_app.publish_structural_evidence(execution_manifest=execution.manifest, request=request, analytical_policy=policy)

    verified = fresh_live_verifier(tmp_path, live_app.project_id).verify(evidence.id)

    assert verified.valid
    assert verified.engineering_status is StructuralCriterionStatus.PASS


def test_live_fail_and_not_evaluable_evidence_fresh_reload(live_app, tmp_path):
    for execution, request, expected_status, expected_reason in (
        (*execute_live_fail_cantilever(live_app, tmp_path), StructuralCriterionStatus.FAIL, "maximum_displacement_exceeded"),
        (*execute_live_missing_yield_cantilever(live_app, tmp_path), StructuralCriterionStatus.NOT_EVALUABLE, "missing_material_property"),
    ):
        evidence = live_app.publish_structural_evidence(execution_manifest=execution.manifest, request=request)
        verified = fresh_live_verifier(tmp_path, live_app.project_id).verify(evidence.id)
        assert verified.engineering_status is expected_status
        assert verified.payload.verification.criterion_results[0].reason == expected_reason


def test_live_repeatability_policy_is_hashed_before_either_run(live_app, tmp_path):
    policy = declared_repeatability_policy()
    policy_hash = structural_repeatability_policy_hash(policy)
    first = execute_publish_live_pass(live_app, tmp_path)
    second = execute_publish_live_pass(live_app, tmp_path)

    result = live_app.compare_structural_repeatability(policy=policy, first_evidence_id=first.id, second_evidence_id=second.id)
    assert result.policy_hash == policy_hash
    assert result.status is StructuralRepeatabilityStatus.REPEATABLE


def test_live_three_level_convergence_uses_predeclared_policy_and_level_evidence(live_app, tmp_path):
    study = declared_convergence_study(mesh_sizes_mm=(10.0, 7.5, 5.0), threshold=0.05)
    study_hash = structural_mesh_convergence_study_hash(study)
    evidence_ids = tuple(execute_publish_live_pass(live_app, tmp_path, mesh_size_mm=size).id for size in (10.0, 7.5, 5.0))

    result = live_app.evaluate_structural_mesh_convergence(study=study, level_evidence_ids=evidence_ids)
    assert result.study_hash == study_hash
    assert result.status in {StructuralMeshConvergenceStatus.CONVERGED, StructuralMeshConvergenceStatus.NOT_CONVERGED}
```

- [ ] **Step 2: Run the live test module and verify failure**

Run: `py -3 -m pytest tests/integration/test_m11_5_live_structural.py -q`

Expected: collection failure until the new high-level APIs and test helpers exist. Runtime-gated skipping is acceptable only when required real runtimes are actually unavailable; it is not acceptance.

- [ ] **Step 3: Add fresh-store test helper and historical runtime-independence capstone**

```python
def fresh_live_verifier(workspace: Path, project_id: str, evidence_id: str) -> StructuralEvidenceVerifier:
    manager = StateManager(workspace)
    store = EvidenceStore(workspace, manager, DependencyGraph.from_yaml("config/dependencies.yaml"))
    durable_evidence = store.load_evidence(project_id, evidence_id)
    run_id = durable_evidence.structural_evidence_payload.execution_manifest.run_id
    artifact_store = ArtifactStore(workspace, project_id=project_id, run_id=run_id)
    return StructuralEvidenceVerifier(
        workspace=workspace,
        project_id=project_id,
        state_manager=manager,
        artifact_store=artifact_store,
        evidence_store=store,
    )


def test_live_historical_evidence_is_valid_stale_and_runtime_independent(live_app, tmp_path, monkeypatch):
    evidence = execute_publish_live_pass(live_app, tmp_path)
    advance_project_to_next_revision(live_app)
    monkeypatch.setattr("mechcad_harness.structural.runtime.discover_freecad", unavailable_runtime)
    monkeypatch.setattr("mechcad_harness.structural.runtime.discover_gmsh", unavailable_runtime)
    monkeypatch.setattr("mechcad_harness.structural.runtime.discover_calculix", unavailable_runtime)

    verifier = fresh_live_verifier(tmp_path, live_app.project_id, evidence.id)
    assert verifier.verify(evidence.id).engineering_status is StructuralCriterionStatus.PASS
    assert verifier.currentness(evidence.id) is StructuralEvidenceCurrentness.STALE_RELATIVE_TO_CURRENT_STATE
```

Ensure the test creates new StateManager/ArtifactStore/EvidenceStore/verifier instances and reloads only evidence ID plus persisted state/artifacts. It must neither reuse M11-4 evaluation objects nor instantiate a runtime-discovering production application for verification.

- [ ] **Step 4: Run M11-3/M11-4/M11-5 live structural tests**

Run: `py -3 -m pytest tests/integration/test_m11_3_live_structural.py tests/integration/test_m11_4_live_structural.py tests/integration/test_m11_5_live_structural.py -q`

Expected: PASS with live M11-5 capstones. Record the exact count, elapsed time, policy hashes, mesh sizes, values, and convergence status for the completion report.

## Task 9: Update Bounded Capability Documentation and Verify the Repository

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/architecture/MECHCAD_PROJECT_OVERVIEW.md`
- Modify: `docs/architecture/MECHCAD_SYSTEM_CONTRACT.md`
- Modify: `docs/architecture/MECHCAD_ENGINEERING_WORKFLOW.md`
- Modify: `docs/architecture/MECHCAD_RUNTIME_FLOW.md`
- Modify: `docs/architecture/MECHCAD_SUBSYSTEM_CONTRACTS.md`
- Modify: `docs/architecture/MECHCAD_CAPABILITY_MATRIX.md`
- Modify: `docs/architecture/MECHCAD_DOCUMENTATION_GAPS.md`
- Create: `docs/audit/MECHCAD_M11_5_COMPLETION_REPORT.md`

**Interfaces:**
- Consumes: verified test/live outputs from Tasks 1-8.
- Produces: bounded M11-5 documentation and the completion marker only if every required verification command passes.

- [ ] **Step 1: Write the completion report with required factual sections**

Use exactly these headings:

```markdown
## Final Disposition
## Accepted Baseline
## M11-5 Scope
## Structural Evidence Model
## EvidenceStore Integration
## Evidence Publication Preconditions
## Evidence Semantic Hash
## Artifact Binding
## Result Binding
## Criterion Binding
## Material Authority Binding
## Analytical Validation Binding
## Provider / Parser Provenance
## PASS Evidence
## FAIL Evidence
## NOT_EVALUABLE Evidence
## Result-Integrity Failure Semantics
## Fresh-Process Reload
## Historical Evidence / Currentness
## Tamper Detection
## Replay Protection
## Fake Provider Isolation
## Repeatability Policy
## Live Repeatability Result
## Mesh-Convergence Study Model
## Convergence Policy
## Live Convergence Result
## Convergence Limitations
## Live Runtime
## Live Evidence Capstones
## Focused Failure Tests
## M9/M10/M11-3/M11-4 Regression Results
## Full Suite Results
## Files Changed
## Remaining Limitations
## M11-6 Boundary
```

Populate observed command counts/times and actual IDs/measurements only after the commands run. Do not record M11-6 acceptance or a global convergence result.

- [ ] **Step 2: Update normative docs with the narrow accepted claim**

Add only this bounded capability statement, adapted to each document's style:

```text
MechCAD can durably publish and independently reload trusted structural engineering evidence for supported linear-static analyses, binding canonical source authority through geometry, mesh, solver execution, raw results, interpretation, engineering criteria, and analytical validation. It can also evaluate bounded repeatability and explicit mesh-convergence studies for declared response metrics.
```

Retain limitations: one source-bound single solid, linear static, stress remains CalculiX extrapolated nodal, no global safety/manufacturing/convergence claim, no adaptive refinement, and M11-6 remains unperformed. Update the capability matrix M11 traceability row and relevant subsystem/runtime-flow descriptions; do not alter M9/M10 claims.

- [ ] **Step 3: Run focused test suites**

Run: `py -3 -m pytest tests/unit/test_structural_evidence_models.py tests/unit/test_structural_evidence_verifier.py tests/unit/test_artifacts.py tests/unit/test_structural_models.py tests/unit/test_structural_pipeline_contracts.py tests/unit/test_structural_request.py tests/unit/test_structural_results.py tests/unit/test_structural_runtime.py tests/unit/test_structural_service.py tests/unit/test_structural_validation_observations.py tests/unit/test_production_application.py -q`

Expected: PASS.

- [ ] **Step 4: Run predecessor and live regressions**

Run: `py -3 -m pytest tests/test_m10_1_continuous_proof.py tests/unit/test_multi_joint_kinematics.py tests/unit/test_multi_joint_collision_sweep.py tests/unit/test_multi_joint_continuous_clearance.py tests/integration/test_m9_1_freecad_runtime_live.py tests/integration/test_m9_2_real_trusted_imported_artifact.py tests/integration/test_m9_3_live_mixed_assembly_exact_kinematic.py tests/integration/test_m9_4_trusted_analysis_backend_provenance.py tests/integration/test_m11_3_live_structural.py tests/integration/test_m11_4_live_structural.py tests/integration/test_m11_5_live_structural.py -q`

Expected: PASS; record runtime-gated skips separately and do not treat a timeout as success.

- [ ] **Step 5: Run required full verification**

Run: `py -3 -m pytest tests/`

Expected: zero failed and zero errors. Record passed, skipped, failed, errors, and elapsed time exactly.

Run: `py -3 -m compileall src/mechcad_harness -q`

Expected: exit code 0.

Run: `py -3 -m compileall -q src/mechcad_harness tests`

Expected: exit code 0.

Run: `git diff --check -- src/mechcad_harness/structural/evidence.py src/mechcad_harness/structural/evidence_service.py src/mechcad_harness/models/evidence.py src/mechcad_harness/structural/validation.py src/mechcad_harness/application.py tests/unit/test_structural_evidence_models.py tests/unit/test_structural_evidence_verifier.py tests/integration/test_m11_5_live_structural.py docs/audit/MECHCAD_M11_5_COMPLETION_REPORT.md`

Expected: no output.

Run: `git diff --check`

Expected: no output, or accurately report pre-existing unrelated diagnostics without modifying those files.

- [ ] **Step 6: Do not commit or push**

The user explicitly prohibited commits and pushes. Leave all M11-5 work in the current worktree and report the resulting status accurately.

## Plan Self-Review

- Spec coverage: Tasks 1-4 implement one versioned immutable payload in existing EvidenceStore, self-excluding hash, durable manifest/request/result/verification/analytical reconstruction, direct/aggregate provenance, publication ordering, PASS/FAIL/NOT_EVALUABLE, and composition-root APIs. Task 5 covers payload/raw artifact tamper, cross-boundary replay, historical currentness, fake provenance, ArtifactStore hardening, and runtime-independent fresh verification. Tasks 6-7 implement distinct predeclared repeatability and per-level evidence convergence semantics. Task 8 supplies all six real capstones. Task 9 covers docs, predecessor regression, full suite, compileall, and diff checks.
- Placeholder scan: no deferred implementation placeholders or unspecified validation steps remain; each task identifies its files, interface, test-first command, and expected outcome.
- Type consistency: generic `Evidence` only consumes `StructuralEvidencePayload`; `StructuralEvidenceVerifier` owns reload verification; publisher composes verifier; repeatability/convergence consume only verified evidence IDs and immutable policies; runtime discovery is absent from normal verification paths.
