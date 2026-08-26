from __future__ import annotations

import json
import inspect
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mechcad_harness.artifacts.models import ArtifactType
from mechcad_harness.artifacts.storage import ArtifactStore
from mechcad_harness.backends.provenance import provenance_from_identity
from mechcad_harness.dependency import DependencyEdge, DependencyGraph, EvidenceStore
from mechcad_harness.models import DesignState, Evidence
from mechcad_harness.models.structural import MaximumDisplacementCriterion
from mechcad_harness.state import StateManager
from mechcad_harness.structural.evidence import (
    FREE_END_TRANSVERSE_DISPLACEMENT,
    EvidenceSubject,
    StructuralEvidenceCurrentness,
    StructuralEvidencePayload,
    StructuralEvidenceVerification,
    StructuralMeshConvergenceStatus,
    StructuralMeshConvergenceStudy,
    StructuralMeshConvergenceResult,
    StructuralPipelineProvenance,
    StructuralRepeatabilityPolicy,
    StructuralRepeatabilityStatus,
    structural_mesh_specification_hash,
    structural_mesh_convergence_study_hash,
    structural_mesh_convergence_result_hash,
    structural_evidence_hash,
)
from mechcad_harness.structural.evidence_models import (
    AnalyticalValidationCheck,
    RectangularCantileverValidationPolicy,
    StructuralAnalyticalValidationResult,
    cantilever_validation_policy_hash,
)
from mechcad_harness.structural.evidence_service import (
    StructuralEvidenceIntegrityError,
    StructuralEvidencePublisher,
    StructuralRepeatabilityService,
    StructuralMeshConvergenceService,
    StructuralEvidenceVerifier,
    structural_evidence_id,
)
from mechcad_harness.structural.results import (
    CalculiXFrdResultParser,
    StructuralAnalysisEvaluation,
    StructuralResultInterpreter,
    StructuralVerificationService,
)
from mechcad_harness.structural.models import structural_result_hash, structural_verification_hash
from mechcad_harness.structural.models import StructuralCriterionStatus
from mechcad_harness.structural.runtime import CALCULIX_IDENTITY, GMSH_IDENTITY
from mechcad_harness.structural.models import (
    StructuralAnalysisResult,
    StructuralExecutionManifest,
    StructuralVerificationResult,
    execution_manifest_hash,
)
from mechcad_harness.structural_request import MeshSpecification, StructuralAnalysisRequest


def _persisted_evidence(
    tmp_path: Path, monkeypatch, *, with_criterion: bool = False, manifest_artifact_id: str = "MANIFEST-EXPLICIT"
) -> SimpleNamespace:
    from test_structural_results import _trusted_interpreter_case
    from test_structural_service import _definition

    project_id = "PRJ-1"
    definition = _definition()
    if with_criterion:
        definition = definition.model_copy(update={
            "acceptance_criteria": (
                MaximumDisplacementCriterion(
                    criterion_id="DISP-1",
                    load_case_id="LC-1",
                    assessment_region_id="free",
                    maximum_allowed_displacement_mm=999.0,
                ),
            ),
        })
    manager = StateManager(tmp_path)
    monkeypatch.setattr(
        "mechcad_harness.state.manager.state_hash",
        lambda _state: "sha256:" + "a" * 64,
    )
    manager.create_project(project_id, DesignState(id="DES-EVIDENCE", revision=1, structural_analysis_definitions=[definition]))
    workspace, request, trusted_definition, manifest, frd_artifact = _trusted_interpreter_case(
        tmp_path, definition_override=definition
    )

    # The historical M11-4 helper predates source input binding. The durable
    # fixture supplies the Task 3 binding without changing production records.
    source_metadata_path = workspace / "projects" / project_id / "runs" / "RUN-1" / "artifacts" / "GEO-1" / "metadata.json"
    source_metadata = json.loads(source_metadata_path.read_text(encoding="utf-8"))
    source_metadata["input_hash"] = request.source_binding.source_program_hash
    source_metadata_path.write_text(json.dumps(source_metadata), encoding="utf-8")

    monkeypatch.setattr(
        "mechcad_harness.structural.evidence_service.state_hash",
        lambda _state: request.source_binding.source_state_hash,
    )
    result = StructuralResultInterpreter(
        workspace=workspace,
        project_id=project_id,
        request=request,
        definition=trusted_definition,
    ).interpret(manifest)
    verification = StructuralVerificationService().evaluate(result, trusted_definition)
    manifest_bytes = json.dumps(
        manifest.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    store = ArtifactStore(workspace, project_id=project_id, run_id=manifest.run_id)
    manifest_artifact = store.publish(
        manifest_artifact_id,
        ArtifactType.JSON,
        "execution_manifest.json",
        manifest_bytes,
        manifest.deck_builder_identity,
        manifest.deck_builder_version,
        manifest.revision,
        manifest.state_hash,
        input_hash=request.request_hash,
    )
    payload = StructuralEvidencePayload(
        request=request,
        execution_manifest_artifact_id=manifest_artifact.artifact_id,
        execution_manifest_artifact_hash=manifest_artifact.sha256,
        execution_manifest=manifest,
        result=result,
        verification=verification,
        aggregate_provenance=StructuralPipelineProvenance(
            pipeline_identity="mechcad-structural-pipeline@1",
            geometry_provenance=manifest.geometry_provider_provenance,
            mesh_provenance=provenance_from_identity(GMSH_IDENTITY),
            solver_provenance=provenance_from_identity(CALCULIX_IDENTITY),
            parser_provenance=result.parser_provenance,
        ),
    )
    evidence = Evidence(
        id=structural_evidence_id(payload),
        kind=EvidenceSubject.STRUCTURAL_ANALYSIS.value,
        subject=EvidenceSubject.STRUCTURAL_ANALYSIS,
        summary="durable structural fixture",
        revision=request.source_binding.source_revision,
        state_hash=request.source_binding.source_state_hash,
        producer_type="structural_evidence",
        producer_name="mechcad-structural-evidence@1",
        producer_version="1",
        producer_result_id=result.result_hash,
        input_hash=request.request_hash,
        output_hash=payload.semantic_hash,
        structural_evidence_payload=payload,
    )
    graph = DependencyGraph([], [DependencyEdge(source=EvidenceSubject.STRUCTURAL_ANALYSIS.value, target="analysis.result")])
    evidence_store = EvidenceStore(workspace, manager, graph)
    evidence_store.write_evidence(project_id, evidence)
    case = manifest.case_manifests[0]
    artifact_paths = {
        name: store.path_for(store.existing(artifact_id))
        for name, artifact_id in {
            "frd": case.frd_artifact_id,
            "dat": case.dat_artifact_id,
            "inp": case.deck_artifact_id,
            "log": case.log_artifact_id,
        }.items()
    }
    return SimpleNamespace(
        workspace=workspace,
        project_id=project_id,
        evidence_id=evidence.id,
        request=request,
        state_manager=manager,
        graph=graph,
        manifest_artifact=manifest_artifact,
        frd_artifact=frd_artifact,
        result=result,
        verification=verification,
        manifest=manifest,
        manifest_path=store.path_for(manifest_artifact),
        msh_path=store.path_for(store.existing(manifest.mesh_artifact_id)),
        artifact_paths=artifact_paths,
    )


def _fresh_verifier(persisted: SimpleNamespace) -> StructuralEvidenceVerifier:
    manager = StateManager(persisted.workspace)
    evidence_store = EvidenceStore(persisted.workspace, manager, persisted.graph)
    artifact_store = ArtifactStore(
        persisted.workspace,
        project_id=persisted.project_id,
        run_id="RUN-1",
    )
    return StructuralEvidenceVerifier(
        workspace=persisted.workspace,
        project_id=persisted.project_id,
        state_manager=manager,
        artifact_store=artifact_store,
        evidence_store=evidence_store,
    )


def _mesh_convergence_study(**updates) -> StructuralMeshConvergenceStudy:
    values = {
        "policy_id": "study@1",
        "mesh_specifications": tuple(
            MeshSpecification(
                global_target_size_mm=size,
                quality_policy_id="quality@1",
                mesher_settings_version="gmsh-settings@1",
            )
            for size in (10.0, 7.5, 5.0)
        ),
        "load_case_id": "LC-1",
        "response_metric": FREE_END_TRANSVERSE_DISPLACEMENT,
        "response_domain": "free-end",
        "relative_change_threshold": 0.02,
        "epsilon": 1e-12,
        "max_levels": 3,
        "required_runtime_identities": ("freecad@1", "gmsh@1", "calculix@1"),
    }
    values.update(updates)
    return StructuralMeshConvergenceStudy(**values)


def _level_payload(
    base: StructuralEvidencePayload,
    size: float,
    response: float,
    *,
    metric=True,
    source_project: str | None = None,
    load_case_id: str | None = None,
    max_elements: int | None = None,
    runtime_update: dict[str, str] | None = None,
):
    request_values = base.request.model_dump(mode="json")
    request_values["mesh_specification"]["global_target_size_mm"] = size
    if source_project is not None:
        request_values["source_binding"]["project_id"] = source_project
    if load_case_id is not None:
        request_values["selected_load_case_ids"] = [load_case_id]
    if max_elements is not None:
        request_values["execution_settings"]["max_elements"] = max_elements
    request_values["request_hash"] = "pending"
    request = StructuralAnalysisRequest.model_validate(request_values)
    mesh_specification_hash = structural_mesh_specification_hash(request.mesh_specification)
    mesh_hash = "sha256:" + hashlib.sha256(f"mesh:{size}".encode()).hexdigest()

    manifest_values = base.execution_manifest.model_dump(mode="json")
    manifest_values.update(
        request_hash=request.request_hash,
        mesh_specification_hash=mesh_specification_hash,
        mesh_artifact_hash=mesh_hash,
        request_manifest_hash=None,
    )
    if source_project is not None:
        manifest_values["project_id"] = source_project
    if runtime_update:
        manifest_values.update(runtime_update)
    manifest_values["mesh_manifest"].update(
        mesh_specification_hash=mesh_specification_hash,
        mesh_hash=mesh_hash,
    )
    manifest_values["case_manifests"][0].update(
        mesh_artifact_hash=mesh_hash,
        case_manifest_hash="pending",
    )
    if load_case_id is not None:
        manifest_values["selected_load_case_ids"] = [load_case_id]
        manifest_values["case_manifests"][0]["load_case_id"] = load_case_id
    for artifact in manifest_values["artifacts"]:
        if artifact["artifact_type"] == "msh":
            artifact["sha256"] = mesh_hash
    manifest = StructuralExecutionManifest.model_validate(manifest_values)

    result_values = base.result.model_dump(mode="json")
    result_values.update(
        request_hash=request.request_hash,
        execution_manifest_hash=execution_manifest_hash(manifest),
        mesh_hash=mesh_hash,
    )
    result_values["source_binding"] = request.source_binding.model_dump(mode="json")
    if load_case_id is not None:
        result_values["load_case_results"][0]["load_case_id"] = load_case_id
    result_values["load_case_results"][0].update(mesh_hash=mesh_hash, result_hash="pending")
    result_values["result_hash"] = "pending"
    result = StructuralAnalysisResult.model_validate(result_values)

    verification_values = base.verification.model_dump(mode="json")
    verification_values.update(
        project_id=request.source_binding.project_id,
        request_hash=request.request_hash,
        execution_manifest_hash=execution_manifest_hash(manifest),
        result_hash=result.result_hash,
        mesh_hash=mesh_hash,
        raw_artifact_hashes=[mesh_hash],
        verification_hash="pending",
    )
    verification = StructuralVerificationResult.model_validate(verification_values)

    analytical_validation = None
    if metric:
        policy = RectangularCantileverValidationPolicy(
            request_hash=request.request_hash,
            geometry_artifact_hash=request.source_binding.geometry_artifact_hash,
            material_identity="MAT-1",
            length_mm=10.0,
            width_mm=2.0,
            height_mm=2.0,
            elastic_modulus_mpa=1000.0,
            poisson_ratio=0.3,
            resultant_force_n=(0.0, -15.0, 0.0),
            mesh_specification_hash=mesh_specification_hash,
            mesh_hash=mesh_hash,
            region_map_hash=manifest.region_map_hash,
            free_end_region_id="free",
            fixed_end_region_id="fixed",
            free_end_area_mm2=4.0,
            displacement_relative_tolerance=0.03,
            reaction_relative_tolerance=0.03,
        )
        checks = tuple(
            AnalyticalValidationCheck(
                check_id=check_id,
                expected_value=response if check_id == "tip_displacement" else 0.0,
                observed_value=response if check_id == "tip_displacement" else 0.0,
                absolute_error=0.0,
                relative_error=0.0,
                tolerance=1.0,
                status="pass",
            )
            for check_id in (
                "geometry", "material", "load", "tip_displacement", "reaction_force", "reaction_moment",
            )
        )
        analytical_validation = StructuralAnalyticalValidationResult(
            policy=policy,
            policy_hash=cantilever_validation_policy_hash(policy),
            source_result_hash=result.result_hash,
            source_request_hash=request.request_hash,
            source_execution_manifest_hash=execution_manifest_hash(manifest),
            status="pass",
            checks=checks,
        )

    values = base.model_dump(mode="json")
    values.update(
        request=request.model_dump(mode="json"),
        execution_manifest=manifest.model_dump(mode="json"),
        result=result.model_dump(mode="json"),
        verification=verification.model_dump(mode="json"),
        analytical_validation=(
            analytical_validation.model_dump(mode="json") if analytical_validation is not None else None
        ),
        semantic_hash="pending",
    )
    return StructuralEvidencePayload.model_validate(values)


class _ConvergenceVerifier:
    def __init__(self, records):
        self.records = records

    def verify(self, evidence_id):
        payload = self.records[evidence_id]
        return StructuralEvidenceVerification(
            evidence_id=evidence_id,
            payload=payload,
            valid=True,
            engineering_status=payload.verification.overall_status,
        )


def test_convergence_uses_ordered_independently_verified_level_evidence():
    from test_structural_evidence_models import _payload

    base = _payload()
    study = _mesh_convergence_study()
    payloads = tuple(
        _level_payload(base, size, response)
        for size, response in zip((10.0, 7.5, 5.0), (1.0, 1.005, 1.006), strict=True)
    )
    ids = tuple(structural_evidence_id(payload) for payload in payloads)
    records = dict(zip(ids, payloads, strict=True))

    result = StructuralMeshConvergenceService(_ConvergenceVerifier(records)).evaluate(
        study=study,
        level_evidence_ids=ids,
    )

    assert result.status is StructuralMeshConvergenceStatus.CONVERGED
    assert tuple(level.evidence_id for level in result.levels) == ids
    assert result.levels[-1].previous_relative_change <= study.relative_change_threshold
    assert tuple(level.evidence_hash for level in result.levels) == tuple(
        records[evidence_id].semantic_hash for evidence_id in ids
    )


def test_convergence_requires_magnitude_semantics_and_records_magnitude_reference():
    from test_structural_evidence_models import _payload

    base = _payload()
    study = _mesh_convergence_study()
    payloads = tuple(
        _level_payload(base, size, -response)
        for size, response in zip((10.0, 7.5, 5.0), (1.0, 1.005, 1.006), strict=True)
    )
    ids = tuple(structural_evidence_id(payload) for payload in payloads)
    records = dict(zip(ids, payloads, strict=True))

    result = StructuralMeshConvergenceService(_ConvergenceVerifier(records)).evaluate(
        study=study,
        level_evidence_ids=ids,
    )

    assert result.status is StructuralMeshConvergenceStatus.CONVERGED
    assert all(level.response_value > 0 for level in result.levels)
    assert tuple(level.analytical_reference for level in result.levels) == (1.0, 1.005, 1.006)
    assert all(level.analytical_error == 0.0 for level in result.levels)

    tampered_study = study.model_copy(update={"response_semantics": "signed"})
    with pytest.raises(StructuralEvidenceIntegrityError, match="response semantics"):
        StructuralMeshConvergenceService(_ConvergenceVerifier(records)).evaluate(
            study=tampered_study,
            level_evidence_ids=ids,
        )


def test_convergence_requires_all_declared_mesh_levels():
    from test_structural_evidence_models import _payload

    base = _payload()
    study = _mesh_convergence_study(
        mesh_specifications=tuple(
            MeshSpecification(
                global_target_size_mm=size,
                quality_policy_id="quality@1",
                mesher_settings_version="gmsh-settings@1",
            )
            for size in (10.0, 7.5, 5.0, 2.5)
        ),
        max_levels=4,
    )
    payloads = tuple(
        _level_payload(base, size, response)
        for size, response in zip((10.0, 7.5, 5.0), (1.0, 1.005, 1.006), strict=True)
    )
    ids = tuple(structural_evidence_id(payload) for payload in payloads)

    result = StructuralMeshConvergenceService(
        _ConvergenceVerifier(dict(zip(ids, payloads, strict=True)))
    ).evaluate(study=study, level_evidence_ids=ids)

    assert result.status is StructuralMeshConvergenceStatus.INTEGRITY_FAILURE


def test_convergence_returns_not_converged_for_excessive_relative_change():
    from test_structural_evidence_models import _payload

    base = _payload()
    study = _mesh_convergence_study()
    payloads = tuple(
        _level_payload(base, size, response)
        for size, response in zip((10.0, 7.5, 5.0), (1.0, 1.1, 1.3), strict=True)
    )
    ids = tuple(structural_evidence_id(payload) for payload in payloads)
    records = dict(zip(ids, payloads, strict=True))

    result = StructuralMeshConvergenceService(_ConvergenceVerifier(records)).evaluate(
        study=study,
        level_evidence_ids=ids,
    )

    assert result.status is StructuralMeshConvergenceStatus.NOT_CONVERGED


@pytest.mark.parametrize(
    ("ids", "records", "expected"),
    [
        (("EVD-L1", "EVD-L2"), {}, StructuralMeshConvergenceStatus.INTEGRITY_FAILURE),
        (("EVD-L1", "EVD-L2", "EVD-L3", "EVD-L4"), {}, StructuralMeshConvergenceStatus.INTEGRITY_FAILURE),
        (("EVD-L1", "EVD-L2", "EVD-L2"), {}, StructuralMeshConvergenceStatus.INTEGRITY_FAILURE),
    ],
)
def test_convergence_rejects_count_and_duplicate_level_ids(ids, records, expected):
    result = StructuralMeshConvergenceService(_ConvergenceVerifier(records)).evaluate(
        study=_mesh_convergence_study(),
        level_evidence_ids=ids,
    )

    assert result.status is expected


def test_convergence_maps_tampered_level_verification_to_integrity_failure(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)

    class TamperedVerifier:
        def verify(self, evidence_id):
            if evidence_id == persisted.evidence_id:
                return _fresh_verifier(persisted).verify(evidence_id)
            if evidence_id == "EVD-L2":
                raise StructuralEvidenceIntegrityError("tampered level")
            raise AssertionError("the tampered level must fail closed")

    result = StructuralMeshConvergenceService(TamperedVerifier()).evaluate(
        study=_mesh_convergence_study(),
        level_evidence_ids=(persisted.evidence_id, "EVD-L2", "EVD-L3"),
    )

    assert result.status is StructuralMeshConvergenceStatus.INTEGRITY_FAILURE


def test_convergence_missing_declared_metric_is_not_evaluable():
    from test_structural_evidence_models import _payload

    base = _payload()
    study = _mesh_convergence_study()
    payloads = tuple(
        _level_payload(base, size, 1.0, metric=False)
        for size in (10.0, 7.5, 5.0)
    )
    ids = tuple(structural_evidence_id(payload) for payload in payloads)

    result = StructuralMeshConvergenceService(_ConvergenceVerifier(dict(zip(ids, payloads)))).evaluate(
        study=study,
        level_evidence_ids=ids,
    )

    assert result.status is StructuralMeshConvergenceStatus.NOT_EVALUABLE
    assert len(result.levels) == len(study.mesh_specifications)
    assert result.levels[1].response_value is None
    assert result.levels[1].previous_relative_change is None
    assert result.levels[1].status is StructuralMeshConvergenceStatus.NOT_EVALUABLE
    assert result.levels[1].reason == "response_metric_unavailable"


def test_convergence_missing_previous_metric_removes_next_relative_change():
    from test_structural_evidence_models import _payload

    base = _payload()
    study = _mesh_convergence_study()
    payloads = tuple(
        _level_payload(base, size, 1.0, metric=index != 1)
        for index, size in enumerate((10.0, 7.5, 5.0))
    )
    ids = tuple(structural_evidence_id(payload) for payload in payloads)

    result = StructuralMeshConvergenceService(_ConvergenceVerifier(dict(zip(ids, payloads)))).evaluate(
        study=study,
        level_evidence_ids=ids,
    )

    assert result.status is StructuralMeshConvergenceStatus.NOT_EVALUABLE
    assert result.levels[0].previous_relative_change is None
    assert result.levels[1].response_value is None
    assert result.levels[1].previous_relative_change is None
    assert result.levels[2].response_value == 1.0
    assert result.levels[2].previous_relative_change is None


def test_convergence_rejects_duplicate_mesh_level_evidence():
    from test_structural_evidence_models import _payload

    base = _payload()
    payloads = (
        _level_payload(base, 10.0, 1.0),
        _level_payload(base, 10.0, 1.005),
        _level_payload(base, 5.0, 1.006),
    )
    ids = tuple(structural_evidence_id(payload) for payload in payloads)

    result = StructuralMeshConvergenceService(_ConvergenceVerifier(dict(zip(ids, payloads)))).evaluate(
        study=_mesh_convergence_study(),
        level_evidence_ids=ids,
    )

    assert result.status is StructuralMeshConvergenceStatus.INTEGRITY_FAILURE


def test_convergence_rejects_missing_required_runtime_identity():
    from test_structural_evidence_models import _payload

    base = _payload()
    payloads = tuple(
        _level_payload(base, size, response)
        for size, response in zip((10.0, 7.5, 5.0), (1.0, 1.005, 1.006), strict=True)
    )
    ids = tuple(structural_evidence_id(payload) for payload in payloads)

    result = StructuralMeshConvergenceService(_ConvergenceVerifier(dict(zip(ids, payloads)))).evaluate(
        study=_mesh_convergence_study(required_runtime_identities=("missing@1",)),
        level_evidence_ids=ids,
    )

    assert result.status is StructuralMeshConvergenceStatus.INTEGRITY_FAILURE


@pytest.mark.parametrize("invalid", ["source", "case", "request", "runtime", "mesh"])
def test_convergence_rejects_mismatched_level_identity(invalid):
    from test_structural_evidence_models import _payload

    base = _payload()
    study = _mesh_convergence_study()
    payloads = [
        _level_payload(base, size, response)
        for size, response in zip((10.0, 7.5, 5.0), (1.0, 1.005, 1.006), strict=True)
    ]
    if invalid == "source":
        payloads[1] = _level_payload(base, 7.5, 1.005, source_project="OTHER")
    elif invalid == "case":
        payloads[1] = _level_payload(base, 7.5, 1.005, load_case_id="LC-2")
    elif invalid == "request":
        payloads[1] = _level_payload(base, 7.5, 1.005, max_elements=999)
    elif invalid == "runtime":
        payloads[1] = _level_payload(base, 7.5, 1.005, runtime_update={"resolver_version": "forged"})
    else:
        payloads[1] = _level_payload(base, 6.0, 1.005)
    ids = tuple(structural_evidence_id(payload) for payload in payloads)

    result = StructuralMeshConvergenceService(_ConvergenceVerifier(dict(zip(ids, payloads)))).evaluate(
        study=study,
        level_evidence_ids=ids,
    )

    assert result.status is StructuralMeshConvergenceStatus.INTEGRITY_FAILURE


def test_convergence_rejects_convergence_study_evidence_as_a_level():
    from test_structural_evidence_models import _convergence_result, _study

    payloads = tuple(
        StructuralEvidencePayload(
            subject=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY,
            mesh_convergence_status=StructuralMeshConvergenceStatus.CONVERGED,
            convergence=_convergence_result(_study(policy_id=f"study-{index}")),
        )
        for index in range(3)
    )
    evidence_ids = tuple(structural_evidence_id(payload) for payload in payloads)
    result = StructuralMeshConvergenceService(
        _ConvergenceVerifier(dict(zip(evidence_ids, payloads, strict=True)))
    ).evaluate(
        study=_mesh_convergence_study(),
        level_evidence_ids=evidence_ids,
    )

    assert result.status is StructuralMeshConvergenceStatus.INTEGRITY_FAILURE


def test_convergence_study_currentness_does_not_require_physical_request(tmp_path):
    from test_structural_evidence_models import _convergence_payload

    payload = _convergence_payload()
    evidence = Evidence(
        id=structural_evidence_id(payload),
        kind=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY.value,
        subject=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY,
        summary="convergence study",
        revision=1,
        state_hash="sha256:" + "a" * 64,
        producer_type="structural_mesh_convergence",
        producer_name="mechcad-structural-convergence@1",
        producer_version="1",
        producer_result_id=payload.convergence.result_hash,
        input_hash=payload.convergence.study_hash,
        output_hash=payload.semantic_hash,
        structural_evidence_payload=payload,
    )

    class EvidenceStoreStub:
        def load_evidence(self, project_id, evidence_id):
            return evidence

    class StateManagerStub:
        def load_current_pointer(self, project_id):
            return {"project_id": project_id, "revision": 1, "state_hash": "sha256:" + "a" * 64}

    verifier = StructuralEvidenceVerifier(
        workspace=tmp_path,
        project_id="PRJ-1",
        state_manager=StateManagerStub(),
        artifact_store=object(),
        evidence_store=EvidenceStoreStub(),
    )

    with pytest.raises(StructuralEvidenceIntegrityError, match="level"):
        verifier.currentness(evidence.id)


@pytest.mark.parametrize(
    ("pointer_revision", "pointer_state_hash", "expected"),
    [
        (1, "sha256:" + "s" * 64, StructuralEvidenceCurrentness.CURRENT),
        (2, "sha256:" + "t" * 64, StructuralEvidenceCurrentness.STALE_RELATIVE_TO_CURRENT_STATE),
    ],
)
def test_convergence_currentness_uses_first_durable_ordinary_level_binding(
    tmp_path, pointer_revision, pointer_state_hash, expected
):
    from test_structural_evidence_models import _payload

    base = _payload()
    study = _mesh_convergence_study()
    level_payloads = tuple(
        _level_payload(base, size, response)
        for size, response in zip((10.0, 7.5, 5.0), (1.0, 1.005, 1.006), strict=True)
    )
    level_ids = tuple(structural_evidence_id(payload) for payload in level_payloads)
    level_records = {
        evidence_id: Evidence(
            id=evidence_id,
            kind=EvidenceSubject.STRUCTURAL_ANALYSIS.value,
            subject=EvidenceSubject.STRUCTURAL_ANALYSIS,
            summary="ordinary level",
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
        for evidence_id, payload in zip(level_ids, level_payloads, strict=True)
    }
    convergence = StructuralMeshConvergenceService(_ConvergenceVerifier(dict(
        zip(level_ids, level_payloads, strict=True)
    ))).evaluate(study=study, level_evidence_ids=level_ids)
    convergence_payload = StructuralEvidencePayload(
        subject=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY,
        mesh_convergence_status=convergence.status,
        convergence=convergence,
    )
    convergence_evidence = Evidence(
        id=structural_evidence_id(convergence_payload),
        kind=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY.value,
        subject=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY,
        summary="convergence study",
        revision=base.request.source_binding.source_revision,
        state_hash=base.request.source_binding.source_state_hash,
        producer_type="structural_mesh_convergence",
        producer_name="mechcad-structural-convergence@1",
        producer_version="1",
        producer_result_id=convergence.result_hash,
        input_hash=convergence.study_hash,
        output_hash=convergence_payload.semantic_hash,
        structural_evidence_payload=convergence_payload,
    )
    records = {**level_records, convergence_evidence.id: convergence_evidence}

    class EvidenceStoreStub:
        def load_evidence(self, _project_id, evidence_id):
            return records[evidence_id]

    class StateManagerStub:
        def load_current_pointer(self, project_id):
            return {
                "project_id": project_id,
                "revision": pointer_revision,
                "state_hash": pointer_state_hash,
            }

    verifier = StructuralEvidenceVerifier(
        workspace=tmp_path,
        project_id="PRJ-1",
        state_manager=StateManagerStub(),
        artifact_store=object(),
        evidence_store=EvidenceStoreStub(),
    )

    assert verifier.currentness(convergence_evidence.id) is expected


def test_convergence_currentness_rejects_missing_durable_level_binding(tmp_path):
    from test_structural_evidence_models import _payload

    base = _payload()
    study = _mesh_convergence_study()
    payloads = tuple(
        _level_payload(base, size, response)
        for size, response in zip((10.0, 7.5, 5.0), (1.0, 1.005, 1.006), strict=True)
    )
    level_ids = tuple(structural_evidence_id(payload) for payload in payloads)
    convergence = StructuralMeshConvergenceService(_ConvergenceVerifier(dict(
        zip(level_ids, payloads, strict=True)
    ))).evaluate(study=study, level_evidence_ids=level_ids)
    convergence_payload = StructuralEvidencePayload(
        subject=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY,
        mesh_convergence_status=convergence.status,
        convergence=convergence,
    )
    convergence_evidence = Evidence(
        id=structural_evidence_id(convergence_payload),
        kind=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY.value,
        subject=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY,
        summary="convergence study",
        revision=1,
        state_hash=base.request.source_binding.source_state_hash,
        producer_type="structural_mesh_convergence",
        producer_name="mechcad-structural-convergence@1",
        producer_version="1",
        producer_result_id=convergence.result_hash,
        input_hash=convergence.study_hash,
        output_hash=convergence_payload.semantic_hash,
        structural_evidence_payload=convergence_payload,
    )

    class EvidenceStoreStub:
        def load_evidence(self, _project_id, evidence_id):
            if evidence_id == convergence_evidence.id:
                return convergence_evidence
            raise KeyError(evidence_id)

    class StateManagerStub:
        def load_current_pointer(self, _project_id):
            return {"revision": 1, "state_hash": base.request.source_binding.source_state_hash}

    verifier = StructuralEvidenceVerifier(
        workspace=tmp_path,
        project_id="PRJ-1",
        state_manager=StateManagerStub(),
        artifact_store=object(),
        evidence_store=EvidenceStoreStub(),
    )

    with pytest.raises(StructuralEvidenceIntegrityError, match="level"):
        verifier.currentness(convergence_evidence.id)


def test_currentness_rejects_tampered_outer_evidence_binding(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    path = persisted.workspace / "projects" / persisted.project_id / "evidence" / f"{persisted.evidence_id}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["output_hash"] = "sha256:" + "0" * 64
    path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(StructuralEvidenceIntegrityError, match="output hash"):
        _fresh_verifier(persisted).currentness(persisted.evidence_id)


def test_convergence_invalid_study_hash_returns_typed_integrity_failure():
    study = _mesh_convergence_study()
    tampered = study.model_copy(update={"study_hash": "sha256:" + "0" * 64})

    result = StructuralMeshConvergenceService(_ConvergenceVerifier({})).evaluate(
        study=tampered,
        level_evidence_ids=("EVD-L1", "EVD-L2", "EVD-L3"),
    )

    assert isinstance(result, StructuralMeshConvergenceResult)
    assert result.status is StructuralMeshConvergenceStatus.INTEGRITY_FAILURE
    assert result.reason
    assert result.study.study_hash == structural_mesh_convergence_study_hash(result.study)


@pytest.mark.parametrize("metric", [True, False])
def test_convergence_publication_persists_only_study_data_and_retains_level_bindings(tmp_path, metric):
    from test_structural_evidence_models import _payload

    base = _payload()
    study = _mesh_convergence_study()
    payloads = tuple(
        _level_payload(base, size, response, metric=metric)
        for size, response in zip((10.0, 7.5, 5.0), (1.0, 1.005, 1.006), strict=True)
    )
    ids = tuple(structural_evidence_id(payload) for payload in payloads)
    records = dict(zip(ids, payloads, strict=True))
    manager = StateManager(tmp_path)
    graph = DependencyGraph(
        [],
        [
            DependencyEdge(source="analysis.structural", target="analysis.result"),
            DependencyEdge(source="analysis.structural.convergence", target="analysis.result"),
        ],
    )
    store = EvidenceStore(tmp_path, manager, graph)
    manager.create_project("PRJ-1", DesignState(id="DES-1", revision=1))
    ordinary_records = {}
    for evidence_id, payload in records.items():
        ordinary = Evidence(
            id=evidence_id,
            kind=EvidenceSubject.STRUCTURAL_ANALYSIS.value,
            subject=EvidenceSubject.STRUCTURAL_ANALYSIS,
            summary="ordinary level",
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
        store.write_evidence("PRJ-1", ordinary)
        ordinary_records[evidence_id] = store.load_evidence("PRJ-1", evidence_id).model_dump_json()

    class DurableVerifier(_ConvergenceVerifier):
        project_id = "PRJ-1"

        def __init__(self):
            super().__init__(records)
            self.evidence_store = store
            self.calls = []

        def verify(self, evidence_id):
            self.calls.append(evidence_id)
            if evidence_id in self.records:
                payload = self.records[evidence_id]
            else:
                evidence = store.load_evidence("PRJ-1", evidence_id)
                payload = evidence.structural_evidence_payload
                self.records[evidence_id] = payload
            return StructuralEvidenceVerification(
                evidence_id=evidence_id,
                payload=payload,
                valid=True,
                engineering_status=(
                    payload.verification.overall_status
                    if payload.verification is not None
                    else None
                ),
            )

    verifier = DurableVerifier()
    service = StructuralMeshConvergenceService(verifier)
    evidence = service.publish(study=study, level_evidence_ids=ids)

    reloaded = store.load_evidence("PRJ-1", evidence.id)
    payload = reloaded.structural_evidence_payload
    assert reloaded.kind == EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY.value
    assert payload.subject is EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY
    assert payload.convergence.status is (
        StructuralMeshConvergenceStatus.CONVERGED
        if metric
        else StructuralMeshConvergenceStatus.NOT_EVALUABLE
    )
    assert payload.request is None
    assert payload.result is None
    assert payload.convergence.levels[-1].evidence_id == ids[-1]
    assert tuple(level.evidence_hash for level in payload.convergence.levels) == tuple(
        records[evidence_id].semantic_hash for evidence_id in ids
    )
    assert tuple(
        store.load_evidence("PRJ-1", evidence_id).model_dump_json()
        for evidence_id in ids
    ) == tuple(ordinary_records[evidence_id] for evidence_id in ids)
    assert verifier.calls[-1] == evidence.id


def test_verifier_reloads_complete_not_evaluable_convergence_result(tmp_path, monkeypatch):
    evidence, verifier, _store = _persisted_convergence_study(tmp_path, missing_metric=True)

    verified = verifier.verify(evidence.id)

    assert verified.valid is True
    assert verified.payload.convergence.status is StructuralMeshConvergenceStatus.NOT_EVALUABLE
    assert len(verified.payload.convergence.levels) == 3
    assert all(level.response_value is None for level in verified.payload.convergence.levels)


def _persisted_convergence_study(tmp_path, *, missing_metric=False):
    from test_structural_evidence_models import _payload

    base = _payload()
    study = _mesh_convergence_study()
    payloads = tuple(
        _level_payload(base, size, response, metric=not missing_metric)
        for size, response in zip((10.0, 7.5, 5.0), (1.0, 1.005, 1.006), strict=True)
    )
    ids = tuple(structural_evidence_id(payload) for payload in payloads)
    records = dict(zip(ids, payloads, strict=True))
    level_verifications = {
        evidence_id: StructuralEvidenceVerification(
            evidence_id=evidence_id,
            payload=payload,
            valid=True,
            engineering_status=payload.verification.overall_status,
        )
        for evidence_id, payload in records.items()
    }
    result = StructuralMeshConvergenceService(_ConvergenceVerifier(records)).evaluate(
        study=study,
        level_evidence_ids=ids,
    )
    payload = StructuralEvidencePayload(
        subject=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY,
        mesh_convergence_status=result.status,
        convergence=result,
    )
    evidence = Evidence(
        id=structural_evidence_id(payload),
        kind=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY.value,
        subject=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY,
        summary="durable convergence fixture",
        revision=1,
        state_hash=base.request.source_binding.source_state_hash,
        producer_type="structural_mesh_convergence",
        producer_name="mechcad-structural-convergence@1",
        producer_version="1",
        producer_result_id=result.result_hash,
        input_hash=study.study_hash,
        output_hash=payload.semantic_hash,
        structural_evidence_payload=payload,
    )
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-1", DesignState(id="DES-1", revision=1))
    graph = DependencyGraph(
        [],
        [
            DependencyEdge(source=EvidenceSubject.STRUCTURAL_ANALYSIS.value, target="analysis.result"),
            DependencyEdge(source=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY.value, target="analysis.result"),
        ],
    )
    store = EvidenceStore(tmp_path, manager, graph)
    store.write_evidence("PRJ-1", evidence)

    class DurableLevelVerifier(StructuralEvidenceVerifier):
        def verify(self, evidence_id):
            if evidence_id in level_verifications:
                return level_verifications[evidence_id]
            return super().verify(evidence_id)

    verifier = DurableLevelVerifier(
        workspace=tmp_path,
        project_id="PRJ-1",
        state_manager=StateManager(tmp_path),
        artifact_store=ArtifactStore(tmp_path, project_id="PRJ-1", run_id="PUBLISH"),
        evidence_store=EvidenceStore(tmp_path, StateManager(tmp_path), graph),
    )
    return evidence, verifier, store


def test_verifier_reloads_convergence_record_and_recomputes_ordered_levels_without_runtime(
    tmp_path, monkeypatch
):
    evidence, verifier, _store = _persisted_convergence_study(tmp_path)
    for name in ("discover_freecad", "discover_gmsh", "discover_calculix"):
        monkeypatch.setattr(
            f"mechcad_harness.structural.runtime.{name}",
            lambda: pytest.fail("convergence verification performed runtime discovery"),
        )
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: pytest.fail("convergence verification launched a process"),
    )

    verified = verifier.verify(evidence.id)

    assert verified.valid is True
    assert verified.engineering_status is None
    assert verified.result_hash == evidence.structural_evidence_payload.convergence.result_hash


@pytest.mark.parametrize("tampered_field", ["study_hash", "result_hash"])
def test_verifier_rejects_tampered_convergence_study_or_result_hash(tmp_path, tampered_field):
    evidence, verifier, store = _persisted_convergence_study(tmp_path)
    path = tmp_path / "projects" / "PRJ-1" / "evidence" / f"{evidence.id}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["producer_result_id"] = "sha256:" + "0" * 64 if tampered_field == "result_hash" else record["producer_result_id"]
    record["input_hash"] = "sha256:" + "0" * 64 if tampered_field == "study_hash" else record["input_hash"]
    record["structural_evidence_payload"]["convergence"][tampered_field] = "sha256:" + "0" * 64
    path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(StructuralEvidenceIntegrityError):
        verifier.verify(evidence.id)


def test_convergence_result_hash_is_canonical_and_level_hashes_are_exact():
    study = _mesh_convergence_study()
    result = StructuralMeshConvergenceResult(
        study=study,
        status=StructuralMeshConvergenceStatus.INTEGRITY_FAILURE,
        reason="tampered level",
    )

    assert result.result_hash == structural_mesh_convergence_result_hash(result)


def test_state_manager_exposes_a_read_only_current_pointer(tmp_path: Path):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-EVIDENCE", DesignState(id="DES-EVIDENCE", revision=1))

    pointer = manager.load_current_pointer("PRJ-EVIDENCE")

    assert pointer["project_id"] == "PRJ-EVIDENCE"
    assert pointer["revision"] == 1
    assert pointer["state_hash"].startswith("sha256:")


def test_structural_evidence_verifier_has_a_durable_id_only_read_api():
    parameters = tuple(inspect.signature(StructuralEvidenceVerifier.verify).parameters)
    assert parameters == ("self", "evidence_id")


def test_structural_evidence_publisher_exposes_durable_authority_api():
    parameters = tuple(inspect.signature(StructuralEvidencePublisher.publish).parameters)
    assert parameters == (
        "self",
        "execution_manifest",
        "request",
        "analytical_policy",
        "execution_manifest_artifact_id",
        "execution_manifest_artifact_hash",
    )


def test_publisher_reconstructs_trusted_result_without_caller_evaluation(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    old_evidence_path = (
        persisted.workspace / "projects" / persisted.project_id / "evidence" / f"{persisted.evidence_id}.json"
    )
    old_evidence_path.unlink()
    publisher = StructuralEvidencePublisher(
        workspace=persisted.workspace,
        project_id=persisted.project_id,
        state_manager=StateManager(persisted.workspace),
        artifact_store=ArtifactStore(persisted.workspace, project_id=persisted.project_id, run_id="RUN-1"),
        evidence_store=EvidenceStore(persisted.workspace, StateManager(persisted.workspace), persisted.graph),
    )
    monkeypatch.setattr(
        publisher,
        "_caller_evaluation",
        StructuralAnalysisEvaluation(
            result=persisted.result.model_copy(update={"result_hash": "sha256:" + "0" * 64}),
            verification=persisted.verification,
        ),
        raising=False,
    )

    evidence = publisher.publish(
        execution_manifest=persisted.manifest,
        request=persisted.request,
        execution_manifest_artifact_id=persisted.manifest_artifact.artifact_id,
        execution_manifest_artifact_hash=persisted.manifest_artifact.sha256,
    )

    assert evidence.structural_evidence_payload.result.result_hash == persisted.result.result_hash
    assert evidence.structural_evidence_payload.verification == persisted.verification


def test_publisher_fresh_verifies_only_after_persisting_evidence(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    evidence_path = (
        persisted.workspace / "projects" / persisted.project_id / "evidence" / f"{persisted.evidence_id}.json"
    )
    evidence_path.unlink()
    publisher = StructuralEvidencePublisher(
        workspace=persisted.workspace,
        project_id=persisted.project_id,
        state_manager=StateManager(persisted.workspace),
        artifact_store=ArtifactStore(persisted.workspace, project_id=persisted.project_id, run_id="RUN-1"),
        evidence_store=EvidenceStore(persisted.workspace, StateManager(persisted.workspace), persisted.graph),
    )
    calls = []

    class FreshVerifier:
        def verify(self, evidence_id):
            published_path = (
                persisted.workspace / "projects" / persisted.project_id / "evidence" / f"{evidence_id}.json"
            )
            calls.append((evidence_id, published_path.exists()))

    monkeypatch.setattr(publisher, "_fresh_verifier", lambda run_id: FreshVerifier())

    evidence = publisher.publish(
        execution_manifest=persisted.manifest,
        request=persisted.request,
        execution_manifest_artifact_id=persisted.manifest_artifact.artifact_id,
        execution_manifest_artifact_hash=persisted.manifest_artifact.sha256,
    )

    assert calls == [(evidence.id, True)]


def test_publisher_does_not_return_evidence_when_post_write_verification_fails(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    old_evidence_path = (
        persisted.workspace / "projects" / persisted.project_id / "evidence" / f"{persisted.evidence_id}.json"
    )
    old_evidence_path.unlink()
    publisher = StructuralEvidencePublisher(
        workspace=persisted.workspace,
        project_id=persisted.project_id,
        state_manager=StateManager(persisted.workspace),
        artifact_store=ArtifactStore(persisted.workspace, project_id=persisted.project_id, run_id="RUN-1"),
        evidence_store=EvidenceStore(persisted.workspace, StateManager(persisted.workspace), persisted.graph),
    )

    class FailingFreshVerifier:
        def verify(self, evidence_id):
            raise StructuralEvidenceIntegrityError("fresh verification failed")

    monkeypatch.setattr(publisher, "_fresh_verifier", lambda run_id: FailingFreshVerifier())

    with pytest.raises(StructuralEvidenceIntegrityError, match="fresh verification failed"):
        publisher.publish(
            execution_manifest=persisted.manifest,
            request=persisted.request,
            execution_manifest_artifact_id=persisted.manifest_artifact.artifact_id,
            execution_manifest_artifact_hash=persisted.manifest_artifact.sha256,
        )

    published = list(
        (persisted.workspace / "projects" / persisted.project_id / "evidence").glob("*.json")
    )
    assert len(published) == 1


@pytest.mark.parametrize("artifact_kind", ["manifest", "frd", "dat", "msh", "inp", "log"])
def test_publisher_rejects_tampered_authority_without_publishing(tmp_path, monkeypatch, artifact_kind):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    evidence_path = (
        persisted.workspace / "projects" / persisted.project_id / "evidence" / f"{persisted.evidence_id}.json"
    )
    evidence_path.unlink()
    if artifact_kind == "manifest":
        path = persisted.manifest_path
    elif artifact_kind == "msh":
        path = persisted.msh_path
    else:
        path = persisted.artifact_paths[artifact_kind]
    path.write_bytes(b"tampered")

    publisher = StructuralEvidencePublisher(
        workspace=persisted.workspace,
        project_id=persisted.project_id,
        state_manager=StateManager(persisted.workspace),
        artifact_store=ArtifactStore(persisted.workspace, project_id=persisted.project_id, run_id="RUN-1"),
        evidence_store=EvidenceStore(persisted.workspace, StateManager(persisted.workspace), persisted.graph),
    )

    with pytest.raises(StructuralEvidenceIntegrityError):
        publisher.publish(
            execution_manifest=persisted.manifest,
            request=persisted.request,
            execution_manifest_artifact_id=persisted.manifest_artifact.artifact_id,
            execution_manifest_artifact_hash=persisted.manifest_artifact.sha256,
        )

    assert not evidence_path.exists()


def test_publisher_requires_explicit_manifest_artifact_binding(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    publisher = StructuralEvidencePublisher(
        workspace=persisted.workspace,
        project_id=persisted.project_id,
        state_manager=StateManager(persisted.workspace),
        artifact_store=ArtifactStore(persisted.workspace, project_id=persisted.project_id, run_id="RUN-1"),
        evidence_store=EvidenceStore(persisted.workspace, StateManager(persisted.workspace), persisted.graph),
    )

    with pytest.raises(StructuralEvidenceIntegrityError):
        publisher.publish(
            execution_manifest=persisted.manifest,
            request=persisted.request,
            execution_manifest_artifact_id="WRONG-MANIFEST",
            execution_manifest_artifact_hash=persisted.manifest_artifact.sha256,
        )


def test_verifier_rejects_noncanonical_id_and_outer_producer_tampering(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    evidence_path = (
        persisted.workspace / "projects" / persisted.project_id / "evidence" / f"{persisted.evidence_id}.json"
    )
    record = json.loads(evidence_path.read_text(encoding="utf-8"))
    record["id"] = "EVD-ALIAS"
    record["producer_name"] = "foreign-producer@1"
    evidence_path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(StructuralEvidenceIntegrityError):
        _fresh_verifier(persisted).verify(persisted.evidence_id)


def test_verifier_reloads_durable_evidence_and_reconstructs_result(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)

    verified = _fresh_verifier(persisted).verify(persisted.evidence_id)

    assert verified.valid is True
    assert verified.request_hash == persisted.request.request_hash
    assert verified.payload.execution_manifest_artifact_id == "MANIFEST-EXPLICIT"


def test_verifier_rejects_tampered_frd_before_parser_invocation(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    parser = Mock(wraps=CalculiXFrdResultParser().parse)
    monkeypatch.setattr(
        "mechcad_harness.structural.evidence_service.CalculiXFrdResultParser",
        lambda: parser,
    )
    frd_path = persisted.workspace / persisted.frd_artifact.relative_path
    frd_path.write_bytes(b"tampered")

    with pytest.raises(StructuralEvidenceIntegrityError):
        _fresh_verifier(persisted).verify(persisted.evidence_id)

    parser.assert_not_called()


def test_historical_verification_does_not_discover_runtimes_or_launch_processes(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    for name in ("discover_freecad", "discover_gmsh", "discover_calculix"):
        monkeypatch.setattr(
            f"mechcad_harness.structural.runtime.{name}",
            lambda: pytest.fail("historical verification performed runtime discovery"),
        )
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: pytest.fail("historical verification launched a process"))

    assert _fresh_verifier(persisted).verify(persisted.evidence_id).valid


def test_currentness_is_independent_from_historical_verification(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    pointer_path = persisted.workspace / "projects" / persisted.project_id / "current.json"
    verifier = _fresh_verifier(persisted)

    assert verifier.currentness(persisted.evidence_id) is StructuralEvidenceCurrentness.STALE_RELATIVE_TO_CURRENT_STATE
    pointer_path.write_text(
        json.dumps({"project_id": persisted.project_id, "revision": 2, "state_hash": "sha256:" + "x" * 64}),
        encoding="utf-8",
    )
    assert _fresh_verifier(persisted).currentness(persisted.evidence_id) is StructuralEvidenceCurrentness.CURRENTNESS_UNAVAILABLE
    pointer_path.unlink()
    assert _fresh_verifier(persisted).currentness(persisted.evidence_id) is StructuralEvidenceCurrentness.CURRENTNESS_UNAVAILABLE
    assert verifier.verify(persisted.evidence_id).valid


def test_currentness_rejects_malformed_or_cross_project_current_pointer(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    pointer_path = persisted.workspace / "projects" / persisted.project_id / "current.json"
    verifier = _fresh_verifier(persisted)

    pointer_path.write_text(
        json.dumps({
            "project_id": "OTHER-PROJECT",
            "revision": persisted.request.source_binding.source_revision,
            "state_hash": persisted.request.source_binding.source_state_hash,
        }),
        encoding="utf-8",
    )
    assert verifier.currentness(persisted.evidence_id) is StructuralEvidenceCurrentness.CURRENTNESS_UNAVAILABLE

    pointer_path.write_text(
        json.dumps({"project_id": persisted.project_id, "revision": 1}),
        encoding="utf-8",
    )
    assert verifier.currentness(persisted.evidence_id) is StructuralEvidenceCurrentness.CURRENTNESS_UNAVAILABLE


def test_direct_provenance_rejects_fake_deck_and_aggregate_pipeline(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    evidence = _fresh_verifier(persisted).evidence_store.load_evidence(
        persisted.project_id, persisted.evidence_id
    )
    payload = evidence.structural_evidence_payload

    fake_deck_manifest = payload.execution_manifest.model_copy(
        update={"deck_builder_identity": "fake-deck-builder@1"}
    )
    with pytest.raises(StructuralEvidenceIntegrityError):
        StructuralEvidenceVerifier._verify_direct_provenance(payload, fake_deck_manifest)

    fake_pipeline = payload.aggregate_provenance.model_copy(
        update={"pipeline_identity": "fake-pipeline@1"}
    )
    with pytest.raises(StructuralEvidenceIntegrityError):
        StructuralEvidenceVerifier._verify_direct_provenance(
            payload.model_copy(update={"aggregate_provenance": fake_pipeline}),
            payload.execution_manifest,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [("resolver_identity", "foreign-region-resolver@9"), ("resolver_version", "9")],
)
def test_direct_provenance_rejects_tampered_region_resolver_binding(
    tmp_path, monkeypatch, field, value
):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    evidence = _fresh_verifier(persisted).evidence_store.load_evidence(
        persisted.project_id, persisted.evidence_id
    )
    payload = evidence.structural_evidence_payload
    tampered_manifest = payload.execution_manifest.model_copy(update={field: value})

    with pytest.raises(StructuralEvidenceIntegrityError):
        StructuralEvidenceVerifier._verify_direct_provenance(payload, tampered_manifest)


@pytest.mark.parametrize(
    ("field", "value"),
    [("resolver_identity", "foreign-region-resolver@9"), ("resolver_version", "9")],
)
def test_publisher_rejects_tampered_durable_region_resolver_binding(
    tmp_path, monkeypatch, field, value
):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    tampered_manifest = persisted.manifest.model_copy(update={field: value})
    manifest_bytes = json.dumps(
        tampered_manifest.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    persisted.manifest_path.write_bytes(manifest_bytes)
    metadata_path = persisted.manifest_path.with_name("metadata.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update({
        "sha256": "sha256:" + hashlib.sha256(manifest_bytes).hexdigest(),
        "size_bytes": len(manifest_bytes),
    })
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    publisher = StructuralEvidencePublisher(
        workspace=persisted.workspace,
        project_id=persisted.project_id,
        state_manager=StateManager(persisted.workspace),
        artifact_store=ArtifactStore(persisted.workspace, project_id=persisted.project_id, run_id="RUN-1"),
        evidence_store=EvidenceStore(persisted.workspace, StateManager(persisted.workspace), persisted.graph),
    )

    with pytest.raises(StructuralEvidenceIntegrityError):
        publisher.publish(
            execution_manifest=tampered_manifest,
            request=persisted.request,
            execution_manifest_artifact_id=persisted.manifest_artifact.artifact_id,
            execution_manifest_artifact_hash=metadata["sha256"],
        )


def test_step_artifact_requires_manifest_reference(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    verifier = _fresh_verifier(persisted)
    payload = verifier.evidence_store.load_evidence(
        persisted.project_id, persisted.evidence_id
    ).structural_evidence_payload
    store = ArtifactStore(persisted.workspace, project_id=persisted.project_id, run_id="RUN-1")
    source_artifact, _ = store.read_verified_strict(
        payload.request.source_binding.geometry_artifact_id,
        expected_type=ArtifactType.STEP,
        expected_hash=payload.request.source_binding.geometry_artifact_hash,
    )
    manifest_without_step_ref = payload.execution_manifest.model_copy(
        update={
            "artifacts": tuple(
                ref for ref in payload.execution_manifest.artifacts
                if ref.artifact_id != source_artifact.artifact_id
            )
        }
    )

    with pytest.raises(StructuralEvidenceIntegrityError):
        verifier._verify_artifact_metadata(
            source_artifact,
            manifest_without_step_ref,
            ArtifactType.STEP,
            expected_producer="mechcad-freecad",
            expected_version=manifest_without_step_ref.geometry_provider_provenance.backend_adapter_version,
            expected_input_hash=payload.request.source_binding.source_program_hash,
            expected_backend=manifest_without_step_ref.geometry_provider_provenance,
            require_manifest_ref=True,
        )


def test_verifier_binds_requested_evidence_id_to_loaded_record(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    evidence_path = (
        persisted.workspace
        / "projects"
        / persisted.project_id
        / "evidence"
        / f"{persisted.evidence_id}.json"
    )
    copied_id = "EVD-COPIED-NAME"
    evidence_path.with_name(f"{copied_id}.json").write_bytes(evidence_path.read_bytes())

    with pytest.raises(StructuralEvidenceIntegrityError):
        _fresh_verifier(persisted).verify(copied_id)


def test_analytical_reconstruction_uses_persisted_observations_without_runtime(monkeypatch):
    from test_structural_results import (
        _cantilever_mesh,
        _cantilever_manifest,
        _cantilever_policy,
        _cantilever_request,
        _cantilever_result,
    )
    from mechcad_harness.structural.evidence_models import (
        CantileverGeometryObservation,
        CantileverMaterialObservation,
    )
    from mechcad_harness.structural.validation import (
        StructuralAnalyticalValidator,
        reconstruct_analytical_validation,
    )

    request = _cantilever_request()
    mesh = _cantilever_mesh()
    manifest = _cantilever_manifest(request, mesh)
    policy = _cantilever_policy(request=request)
    geometry = CantileverGeometryObservation(
        project_id=request.source_binding.project_id,
        source_revision=request.source_binding.source_revision,
        source_state_hash=request.source_binding.source_state_hash,
        definition_id=request.source_binding.definition_id,
        definition_hash=request.source_binding.definition_hash,
        geometry_artifact_id=request.source_binding.geometry_artifact_id,
        geometry_artifact_hash=request.source_binding.geometry_artifact_hash,
        length_mm=10.0,
        width_mm=2.0,
        height_mm=2.0,
        free_end_area_mm2=4.0,
    )
    material = CantileverMaterialObservation(
        project_id=request.source_binding.project_id,
        source_revision=request.source_binding.source_revision,
        source_state_hash=request.source_binding.source_state_hash,
        definition_id=request.source_binding.definition_id,
        definition_hash=request.source_binding.definition_hash,
        geometry_artifact_id=request.source_binding.geometry_artifact_id,
        geometry_artifact_hash=request.source_binding.geometry_artifact_hash,
        material_identity="MAT-1",
        elastic_modulus_mpa=1000.0,
        poisson_ratio=0.3,
    )
    result = _cantilever_result()
    persisted = StructuralAnalyticalValidator().validate(
        result,
        policy,
        request=request,
        execution_manifest=manifest,
        mesh=mesh,
        mesh_artifact_bytes=mesh.mesh_bytes,
        geometry_observation=geometry,
        material_observation=material,
    )
    for name in ("discover_freecad", "discover_gmsh", "discover_calculix"):
        monkeypatch.setattr(
            f"mechcad_harness.structural.runtime.{name}",
            lambda: pytest.fail("analytical reconstruction performed runtime discovery"),
        )
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: pytest.fail("analytical reconstruction launched a process"))

    reconstructed = reconstruct_analytical_validation(
        result,
        persisted,
        request=request,
        execution_manifest=manifest,
        mesh_artifact_bytes=mesh.mesh_bytes,
        geometry_observation=geometry,
        material_observation=material,
        definition=None,
    )

    assert reconstructed == persisted


def _evidence_json_path(persisted: SimpleNamespace) -> Path:
    return (
        persisted.workspace
        / "projects"
        / persisted.project_id
        / "evidence"
        / f"{persisted.evidence_id}.json"
    )


def _mutate_persisted_evidence_json(persisted: SimpleNamespace, path: tuple[object, ...], value) -> None:
    evidence_path = _evidence_json_path(persisted)
    record = json.loads(evidence_path.read_text(encoding="utf-8"))
    cursor = record["structural_evidence_payload"]
    for component in path[:-1]:
        cursor = cursor[component]
    cursor[path[-1]] = value
    evidence_path.write_text(json.dumps(record), encoding="utf-8")


def _rewrite_with_rehashed_inner_tamper(persisted: SimpleNamespace, kind: str) -> None:
    evidence_path = _evidence_json_path(persisted)
    record = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload_data = record["structural_evidence_payload"]

    if kind == "result":
        payload_data["result"]["load_case_results"][0]["maximum_displacement_mm"] = 123.456
        payload_data["result"]["load_case_results"][0]["result_hash"] = "pending"
        payload_data["result"]["result_hash"] = "pending"
        from mechcad_harness.structural.models import StructuralAnalysisResult, StructuralVerificationResult

        rebuilt_result = StructuralAnalysisResult.model_validate(payload_data["result"])
        payload_data["result"] = rebuilt_result.model_dump(mode="json")
        payload_data["verification"]["result_hash"] = rebuilt_result.result_hash
        payload_data["verification"]["verification_hash"] = "pending"
        rebuilt_verification = StructuralVerificationResult.model_validate(payload_data["verification"])
        payload_data["verification"] = rebuilt_verification.model_dump(mode="json")
    else:
        from mechcad_harness.structural.models import StructuralVerificationResult

        payload_data["verification"]["raw_artifact_hashes"][0] = "sha256:" + "f" * 64
        payload_data["verification"]["verification_hash"] = "pending"
        rebuilt_verification = StructuralVerificationResult.model_validate(payload_data["verification"])
        payload_data["verification"] = rebuilt_verification.model_dump(mode="json")

    payload_data["semantic_hash"] = "pending"
    updated_payload = StructuralEvidencePayload.model_validate(payload_data)
    record["id"] = structural_evidence_id(updated_payload)
    record["producer_result_id"] = updated_payload.result.result_hash
    record["output_hash"] = updated_payload.semantic_hash
    record["structural_evidence_payload"] = updated_payload.model_dump(mode="json")
    new_path = evidence_path.with_name(f"{record['id']}.json")
    new_path.write_text(json.dumps(record), encoding="utf-8")
    evidence_path.unlink()
    persisted.evidence_id = record["id"]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("verification", "overall_status"), "pass"),
        (("verification", "criterion_results", 0, "observed_value"), 999.0),
        (("verification", "verification_hash"), "sha256:" + "0" * 64),
        (("result", "result_hash"), "sha256:" + "0" * 64),
        (("result", "parser_provenance", "frd_parser_identity"), "foreign-parser@1"),
        (("execution_manifest", "mesh_artifact_hash"), "sha256:" + "0" * 64),
        (("execution_manifest_artifact_hash",), "sha256:" + "0" * 64),
        (("request", "source_binding", "source_state_hash"), "sha256:" + "0" * 64),
        (("semantic_hash",), "sha256:" + "0" * 64),
    ],
)
def test_persisted_evidence_payload_tamper_fails_without_rehashing(tmp_path, monkeypatch, path, value):
    persisted = _persisted_evidence(
        tmp_path, monkeypatch, with_criterion="criterion_results" in path
    )
    _mutate_persisted_evidence_json(persisted, path, value)

    with pytest.raises(StructuralEvidenceIntegrityError):
        _fresh_verifier(persisted).verify(persisted.evidence_id)


def _tamper_raw_evidence_artifact(persisted: SimpleNamespace, artifact_kind: str) -> None:
    if artifact_kind == "manifest":
        path = persisted.manifest_path
    elif artifact_kind == "step":
        store = ArtifactStore(persisted.workspace, project_id=persisted.project_id, run_id="RUN-1")
        path = store.path_for(store.existing(persisted.request.source_binding.geometry_artifact_id))
    elif artifact_kind == "msh":
        path = persisted.msh_path
    else:
        path = persisted.artifact_paths[artifact_kind]
    assert path is not None
    path.write_bytes(b"tampered")


def _persisted_evidence_with_analytical_validation(tmp_path: Path, monkeypatch) -> SimpleNamespace:
    from mechcad_harness.structural.evidence_models import (
        CantileverGeometryObservation,
        CantileverMaterialObservation,
        RectangularCantileverValidationPolicy,
    )
    from mechcad_harness.structural.results import parse_trusted_msh_bytes
    from mechcad_harness.structural.validation import StructuralAnalyticalValidator

    persisted = _persisted_evidence(tmp_path, monkeypatch)
    definition = persisted.state_manager.load_revision(
        persisted.project_id, persisted.request.source_binding.source_revision
    ).structural_analysis_definitions[0]
    mesh_bytes = persisted.msh_path.read_bytes()
    policy = RectangularCantileverValidationPolicy(
        request_hash=persisted.request.request_hash,
        geometry_artifact_hash=persisted.request.source_binding.geometry_artifact_hash,
        material_identity=definition.material_assignment.material_identity,
        length_mm=10.0,
        width_mm=10.0,
        height_mm=10.0,
        elastic_modulus_mpa=70000.0,
        poisson_ratio=0.33,
        resultant_force_n=(0.0, -1.0, 0.0),
        mesh_specification_hash=persisted.manifest.mesh_specification_hash,
        mesh_hash=persisted.manifest.mesh_artifact_hash,
        region_map_hash=persisted.manifest.region_map_hash,
        free_end_region_id="free",
        fixed_end_region_id="fixed",
        free_end_area_mm2=50.0,
        displacement_relative_tolerance=0.1,
        reaction_relative_tolerance=0.1,
    )
    geometry = CantileverGeometryObservation(
        project_id=persisted.project_id,
        source_revision=persisted.request.source_binding.source_revision,
        source_state_hash=persisted.request.source_binding.source_state_hash,
        definition_id=persisted.request.source_binding.definition_id,
        definition_hash=persisted.request.source_binding.definition_hash,
        geometry_artifact_id=persisted.request.source_binding.geometry_artifact_id,
        geometry_artifact_hash=persisted.request.source_binding.geometry_artifact_hash,
        length_mm=10.0,
        width_mm=10.0,
        height_mm=10.0,
        free_end_area_mm2=50.0,
    )
    material = CantileverMaterialObservation(
        project_id=persisted.project_id,
        source_revision=persisted.request.source_binding.source_revision,
        source_state_hash=persisted.request.source_binding.source_state_hash,
        definition_id=persisted.request.source_binding.definition_id,
        definition_hash=persisted.request.source_binding.definition_hash,
        geometry_artifact_id=persisted.request.source_binding.geometry_artifact_id,
        geometry_artifact_hash=persisted.request.source_binding.geometry_artifact_hash,
        material_identity=definition.material_assignment.material_identity,
        elastic_modulus_mpa=70000.0,
        poisson_ratio=0.33,
    )
    analytical = StructuralAnalyticalValidator().validate(
        persisted.result,
        policy,
        request=persisted.request,
        execution_manifest=persisted.manifest,
        mesh=parse_trusted_msh_bytes(mesh_bytes),
        mesh_artifact_bytes=mesh_bytes,
        geometry_observation=geometry,
        material_observation=material,
        definition=definition,
    )
    evidence_path = _evidence_json_path(persisted)
    record = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload = StructuralEvidencePayload.model_validate(
        record["structural_evidence_payload"]
    ).model_copy(update={
        "analytical_validation": analytical,
        "analytical_geometry_observation": geometry,
        "analytical_material_observation": material,
    })
    record["id"] = structural_evidence_id(payload)
    record["output_hash"] = payload.semantic_hash
    record["structural_evidence_payload"] = payload.model_dump(mode="json")
    evidence_path.write_text(json.dumps(record), encoding="utf-8")
    persisted.evidence_id = record["id"]
    return persisted


@pytest.mark.parametrize("artifact_kind", ["step", "msh", "inp", "frd", "dat", "log", "manifest"])
def test_every_persisted_raw_artifact_is_verified_before_result_parsers(
    tmp_path, monkeypatch, artifact_kind
):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    _tamper_raw_evidence_artifact(persisted, artifact_kind)
    frd_parser = Mock()
    dat_parser = Mock()
    monkeypatch.setattr(
        "mechcad_harness.structural.evidence_service.CalculiXFrdResultParser",
        lambda: frd_parser,
    )
    monkeypatch.setattr(
        "mechcad_harness.structural.evidence_service.CalculiXDatResultParser",
        lambda: dat_parser,
    )

    with pytest.raises(StructuralEvidenceIntegrityError):
        _fresh_verifier(persisted).verify(persisted.evidence_id)

    frd_parser.parse.assert_not_called()
    dat_parser.parse_reactions.assert_not_called()


def test_historical_evidence_remains_valid_but_becomes_stale_after_state_advance(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    before = persisted.state_manager.load_current_pointer(persisted.project_id)
    current_state = persisted.state_manager.load_current_state(persisted.project_id)
    persisted.state_manager.create_revision(persisted.project_id, current_state)
    after = persisted.state_manager.load_current_pointer(persisted.project_id)
    verifier = _fresh_verifier(persisted)

    assert before["revision"] == 1
    assert after["revision"] == 2
    assert verifier.verify(persisted.evidence_id).valid
    assert verifier.currentness(persisted.evidence_id) is StructuralEvidenceCurrentness.STALE_RELATIVE_TO_CURRENT_STATE


def test_persisted_analytical_validation_hash_tamper_fails_closed(tmp_path, monkeypatch):
    persisted = _persisted_evidence_with_analytical_validation(tmp_path, monkeypatch)
    _mutate_persisted_evidence_json(
        persisted,
        ("analytical_validation", "validation_hash"),
        "sha256:" + "0" * 64,
    )

    with pytest.raises(StructuralEvidenceIntegrityError):
        _fresh_verifier(persisted).verify(persisted.evidence_id)


@pytest.mark.parametrize("kind", ["result", "verification"])
def test_rehashed_inner_tamper_reaches_explicit_verifier_checks(tmp_path, monkeypatch, kind):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    _rewrite_with_rehashed_inner_tamper(persisted, kind)

    with pytest.raises(StructuralEvidenceIntegrityError):
        _fresh_verifier(persisted).verify(persisted.evidence_id)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("request", "source_binding", "project_id"), "OTHER-PROJECT"),
        (("request", "source_binding", "source_revision"), 2),
        (("request", "selected_load_case_ids", 0), "OTHER-CASE"),
        (("verification", "criterion_results", 0, "criterion_id"), "OTHER-CRITERION"),
        (("verification", "criterion_results", 0, "allowable_value"), 0.001),
        (("request", "analytical_policy_hash"), "sha256:" + "p" * 64),
    ],
)
def test_replayed_project_revision_case_criterion_material_or_policy_fails_closed(
    tmp_path, monkeypatch, path, value
):
    persisted = _persisted_evidence(
        tmp_path, monkeypatch, with_criterion="criterion_results" in path
    )
    _mutate_persisted_evidence_json(persisted, path, value)

    with pytest.raises(StructuralEvidenceIntegrityError):
        _fresh_verifier(persisted).verify(persisted.evidence_id)


def test_historical_verification_is_runtime_independent_at_all_launch_boundaries(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    for name in ("discover_freecad", "discover_gmsh", "discover_calculix"):
        monkeypatch.setattr(
            f"mechcad_harness.structural.runtime.{name}",
            lambda: pytest.fail("historical verification performed runtime discovery"),
        )
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: pytest.fail("historical verification launched a process"),
    )
    monkeypatch.setattr(
        "mechcad_harness.structural.geometry.StructuralFreeCADGeometryAdapter",
        lambda *args, **kwargs: pytest.fail("historical verification launched FreeCAD adapter"),
    )
    monkeypatch.setattr(
        "mechcad_harness.structural.mesh.StructuralGmshMeshingProvider",
        lambda *args, **kwargs: pytest.fail("historical verification launched Gmsh mesher"),
    )
    monkeypatch.setattr(
        "mechcad_harness.structural.solver.StructuralCalculiXSolverProvider",
        lambda *args, **kwargs: pytest.fail("historical verification launched CalculiX solver"),
    )

    assert _fresh_verifier(persisted).verify(persisted.evidence_id).valid


def _repeatability_policy(persisted: SimpleNamespace, *, summary_fields=("criterion_results",)):
    return StructuralRepeatabilityPolicy(
        policy_id="repeatability@1",
        source_project_id=persisted.project_id,
        source_definition_id=persisted.request.source_binding.definition_id,
        source_definition_hash=persisted.request.source_binding.definition_hash,
        source_request_hash=persisted.request.request_hash,
        required_provider_identities=("freecad", "gmsh", "calculix"),
        required_runtime_identities=("FreeCAD@1.1.3", "Gmsh@4.15.0", "CalculiX@2.22"),
        semantic_summary_fields=summary_fields,
        absolute_tolerances=tuple((field, 0.01) for field in summary_fields),
        relative_tolerances=tuple((field, 0.01) for field in summary_fields),
    )


def test_repeatability_compares_only_declared_summaries_and_ignores_run_raw_and_mesh_ids(
    tmp_path, monkeypatch
):
    first_persisted = _persisted_evidence(tmp_path / "first", monkeypatch)
    second_persisted = _persisted_evidence(
        tmp_path / "second", monkeypatch, manifest_artifact_id="MANIFEST-SECOND"
    )
    first = _fresh_verifier(first_persisted).verify(first_persisted.evidence_id)
    second = _fresh_verifier(second_persisted).verify(second_persisted.evidence_id)
    policy = _repeatability_policy(first_persisted)

    class Verifier:
        def verify(self, evidence_id):
            return first if evidence_id == first_persisted.evidence_id else second

    result = StructuralRepeatabilityService(Verifier()).compare(
        policy=policy,
        first_evidence_id=first_persisted.evidence_id,
        second_evidence_id=second_persisted.evidence_id,
    )

    assert result.status is StructuralRepeatabilityStatus.REPEATABLE
    assert tuple(item.field_id for item in result.comparisons) == ("criterion_results",)
    assert "mesh_node_ids" not in tuple(item.field_id for item in result.comparisons)


def test_repeatability_returns_not_repeatable_for_valid_summary_tolerance_exceedance(
    tmp_path, monkeypatch
):
    persisted = _persisted_evidence(tmp_path, monkeypatch, with_criterion=True)
    verified = _fresh_verifier(persisted).verify(persisted.evidence_id)
    criterion = verified.payload.verification.criterion_results[0].model_copy(
        update={"observed_value": 10.0}
    )
    changed_verification = verified.payload.verification.model_copy(
        update={"criterion_results": (criterion,), "verification_hash": "pending"}
    )
    changed_payload_data = verified.payload.model_dump(mode="json")
    changed_payload_data["verification"] = changed_verification.model_dump(mode="json")
    changed_payload_data["semantic_hash"] = "pending"
    changed_payload = StructuralEvidencePayload.model_validate(changed_payload_data)
    second = StructuralEvidenceVerification.model_validate(
        {
            **verified.model_dump(mode="json"),
            "evidence_id": "EVD-SECOND",
            "payload": changed_payload.model_dump(mode="json"),
        }
    )
    policy = _repeatability_policy(persisted)

    class Verifier:
        def verify(self, evidence_id):
            return verified if evidence_id == persisted.evidence_id else second

    result = StructuralRepeatabilityService(Verifier()).compare(
        policy=policy,
        first_evidence_id=persisted.evidence_id,
        second_evidence_id="EVD-SECOND",
    )

    assert result.status is StructuralRepeatabilityStatus.NOT_REPEATABLE


def test_repeatability_rejects_verifier_id_mismatch(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    verified = _fresh_verifier(persisted).verify(persisted.evidence_id)

    class Verifier:
        def verify(self, evidence_id):
            return verified

    result = StructuralRepeatabilityService(Verifier()).compare(
        policy=_repeatability_policy(persisted),
        first_evidence_id=persisted.evidence_id,
        second_evidence_id="EVD-SECOND",
    )

    assert result.status is StructuralRepeatabilityStatus.INTEGRITY_FAILURE


def test_repeatability_maps_verifier_failure_to_integrity_failure(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    policy = _repeatability_policy(persisted)

    _mutate_persisted_evidence_json(
        persisted,
        ("semantic_hash",),
        "sha256:" + "0" * 64,
    )

    result = StructuralRepeatabilityService(_fresh_verifier(persisted)).compare(
        policy=policy,
        first_evidence_id=persisted.evidence_id,
        second_evidence_id="EVD-SECOND",
    )

    assert result.status is StructuralRepeatabilityStatus.INTEGRITY_FAILURE
    assert result.comparisons == ()


def test_repeatability_independently_verifies_both_evidence_ids(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch, with_criterion=True)
    verified = _fresh_verifier(persisted).verify(persisted.evidence_id)
    calls = []

    class Verifier:
        def verify(self, evidence_id):
            calls.append(evidence_id)
            return verified.model_copy(update={"evidence_id": evidence_id})

    result = StructuralRepeatabilityService(Verifier()).compare(
        policy=_repeatability_policy(persisted),
        first_evidence_id=persisted.evidence_id,
        second_evidence_id="EVD-SECOND",
    )

    assert result.status is StructuralRepeatabilityStatus.REPEATABLE
    assert calls == [persisted.evidence_id, "EVD-SECOND"]


def test_repeatability_rejects_policy_source_identity_mismatch(tmp_path, monkeypatch):
    persisted = _persisted_evidence(tmp_path, monkeypatch)
    verified = _fresh_verifier(persisted).verify(persisted.evidence_id)
    policy_values = _repeatability_policy(persisted).model_dump(mode="python")
    policy_values.update({"source_project_id": "OTHER", "policy_hash": "pending"})
    policy = StructuralRepeatabilityPolicy(**policy_values)

    class Verifier:
        def verify(self, evidence_id):
            return verified.model_copy(update={"evidence_id": evidence_id})

    result = StructuralRepeatabilityService(Verifier()).compare(
        policy=policy,
        first_evidence_id=persisted.evidence_id,
        second_evidence_id="EVD-SECOND",
    )

    assert result.status is StructuralRepeatabilityStatus.INTEGRITY_FAILURE
