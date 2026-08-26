from __future__ import annotations

import json
from math import inf, nan
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError

from mechcad_harness.backends.models import BackendProvenance
from mechcad_harness.dependency import DependencyEdge, DependencyGraph, EvidenceStore
from mechcad_harness.models import DesignState, Evidence
from mechcad_harness.state import StateManager
from mechcad_harness.structural.evidence import (
    FREE_END_TRANSVERSE_DISPLACEMENT,
    STRUCTURAL_EVIDENCE_SCHEMA_VERSION,
    EvidenceSubject,
    StructuralEvidenceCurrentness,
    StructuralEvidencePayload,
    StructuralMeshConvergenceResult,
    StructuralMeshConvergenceLevel,
    StructuralMeshConvergenceStatus,
    StructuralMeshConvergenceStudy,
    StructuralPipelineProvenance,
    StructuralRepeatabilityComparison,
    StructuralRepeatabilityPolicy,
    StructuralRepeatabilityResult,
    StructuralRepeatabilityStatus,
    structural_evidence_hash,
    structural_mesh_convergence_study_hash,
    structural_repeatability_policy_hash,
    structural_repeatability_result_hash,
)
from mechcad_harness.models.structural import structural_definition_hash
from mechcad_harness.structural.models import (
    StructuralAnalysisResult,
    StructuralArtifactRef,
    StructuralCaseExecutionManifest,
    StructuralCriterionResult,
    StructuralCriterionStatus,
    StructuralExecutionManifest,
    StructuralExecutionStatus,
    StructuralLoadCaseResult,
    StructuralMeshManifest,
    StructuralResultParserProvenance,
    StructuralSolverManifest,
    StructuralVerificationResult,
    execution_manifest_hash,
)
from mechcad_harness.structural_request import (
    MeshSpecification,
    StructuralAnalysisRequest,
    StructuralExecutionSettings,
    StructuralResultField,
    StructuralSourceBinding,
)


HASHES = {
    "state": "sha256:" + "s" * 64,
    "definition": "sha256:" + "d" * 64,
    "program": "sha256:" + "p" * 64,
    "geometry": "sha256:" + "g" * 64,
    "mesh": "sha256:" + "m" * 64,
    "mesh_spec": "sha256:" + "q" * 64,
    "manifest": "sha256:" + "n" * 64,
}


def _provenance(name: str) -> BackendProvenance:
    return BackendProvenance(
        backend_name=name,
        backend_adapter_version="adapter@1",
        library_name=name,
        library_version="1.0",
        library_source="test",
        library_revision=f"{name}@1",
    )


def _request() -> StructuralAnalysisRequest:
    return StructuralAnalysisRequest(
        source_binding=StructuralSourceBinding(
            project_id="PRJ-1",
            source_revision=1,
            source_state_hash=HASHES["state"],
            definition_id="DEF-1",
            definition_hash=HASHES["definition"],
            target_body_id="BODY-1",
            source_program_hash=HASHES["program"],
            geometry_identity="freecad:body-1",
            geometry_artifact_id="STEP-1",
            geometry_artifact_hash=HASHES["geometry"],
        ),
        selected_load_case_ids=("LC-1",),
        mesh_specification=MeshSpecification(
            global_target_size_mm=5.0,
            quality_policy_id="quality@1",
            mesher_settings_version="gmsh-settings@1",
        ),
        requested_result_fields=(StructuralResultField.DISPLACEMENT,),
        execution_settings=StructuralExecutionSettings(
            max_elements=1000,
            max_runtime_seconds=30.0,
            max_output_bytes=100000,
            retain_raw_artifacts=True,
        ),
    )


def _manifest(request: StructuralAnalysisRequest) -> StructuralExecutionManifest:
    mesh_manifest = StructuralMeshManifest(
        mesh_specification_hash=HASHES["mesh_spec"],
        gmsh_identity="gmsh@1",
        gmsh_version="4.15.0",
        element_family="c3d10",
        node_count=10,
        volume_element_count=1,
        boundary_element_count=4,
        volume_entity_id=1,
        physical_groups=(),
        mesh_hash=HASHES["mesh"],
        region_map_hash="sha256:" + "r" * 64,
    )
    case_manifest = StructuralCaseExecutionManifest(
        load_case_id="LC-1",
        mesh_artifact_id="MSH-1",
        mesh_artifact_hash=HASHES["mesh"],
        frd_artifact_id="FRD-1",
        frd_artifact_hash="sha256:" + "f" * 64,
        dat_artifact_id="DAT-1",
        dat_artifact_hash="sha256:" + "a" * 64,
        log_artifact_id="LOG-1",
        log_artifact_hash="sha256:" + "l" * 64,
        execution_status=StructuralExecutionStatus.SUCCEEDED,
    )
    return StructuralExecutionManifest(
        project_id=request.source_binding.project_id,
        revision=request.source_binding.source_revision,
        state_hash=request.source_binding.source_state_hash,
        definition_id=request.source_binding.definition_id,
        definition_hash=request.source_binding.definition_hash,
        request_hash=request.request_hash,
        run_id="RUN-1",
        geometry_artifact_id=request.source_binding.geometry_artifact_id,
        geometry_artifact_hash=request.source_binding.geometry_artifact_hash,
        geometry_provider_provenance=_provenance("freecad"),
        region_map_hash=mesh_manifest.region_map_hash,
        resolver_identity="resolver@1",
        resolver_version="1",
        gmsh_identity=mesh_manifest.gmsh_identity,
        gmsh_version=mesh_manifest.gmsh_version,
        mesh_specification_hash=HASHES["mesh_spec"],
        mesh_artifact_id="MSH-1",
        mesh_artifact_hash=HASHES["mesh"],
        mesh_manifest=mesh_manifest,
        mesh_manifest_hash="sha256:" + "h" * 64,
        deck_builder_identity="deck@1",
        deck_builder_version="1",
        calculix_identity="calculix@1",
        calculix_version="2.22",
        execution_status=StructuralExecutionStatus.SUCCEEDED,
        solver_manifest=StructuralSolverManifest(
            calculix_identity="calculix@1",
            calculix_version="2.22",
            backend_provenance=_provenance("calculix"),
            exit_code=0,
            job_finished=True,
            produced_frd=True,
            produced_dat=True,
            produced_log=True,
        ),
        log_artifact_id="LOG-1",
        log_artifact_hash="sha256:" + "l" * 64,
        frd_artifact_id="FRD-1",
        frd_artifact_hash="sha256:" + "f" * 64,
        dat_artifact_id="DAT-1",
        dat_artifact_hash="sha256:" + "a" * 64,
        artifacts=(
            StructuralArtifactRef(
                artifact_type="msh",
                artifact_id="MSH-1",
                sha256=HASHES["mesh"],
                producer_identity="gmsh@1",
                producer_version="4.15.0",
            ),
        ),
        selected_load_case_ids=("LC-1",),
        case_manifests=(case_manifest,),
    )


def _payload() -> StructuralEvidencePayload:
    request = _request()
    manifest = _manifest(request)
    result = StructuralAnalysisResult(
        source_binding=request.source_binding,
        definition_id=request.source_binding.definition_id,
        definition_hash=request.source_binding.definition_hash,
        request_hash=request.request_hash,
        execution_manifest_hash=execution_manifest_hash(manifest),
        mesh_hash=HASHES["mesh"],
        load_case_results=(
            StructuralLoadCaseResult(
                load_case_id="LC-1",
                mesh_hash=HASHES["mesh"],
            ),
        ),
    )
    verification = StructuralVerificationResult(
        project_id=request.source_binding.project_id,
        source_revision=request.source_binding.source_revision,
        source_state_hash=request.source_binding.source_state_hash,
        definition_id=request.source_binding.definition_id,
        definition_hash=request.source_binding.definition_hash,
        request_hash=request.request_hash,
        execution_manifest_hash=execution_manifest_hash(manifest),
        result_hash=result.result_hash,
        mesh_hash=HASHES["mesh"],
        raw_artifact_hashes=(HASHES["mesh"],),
        parser_provenance=StructuralResultParserProvenance(),
        overall_status=StructuralCriterionStatus.PASS,
        criterion_results=(
            StructuralCriterionResult(
                criterion_id="criterion-1",
                status=StructuralCriterionStatus.PASS,
            ),
        ),
    )
    return StructuralEvidencePayload(
        request=request,
        execution_manifest_artifact_id="MANIFEST-1",
        execution_manifest_artifact_hash=HASHES["manifest"],
        execution_manifest=manifest,
        result=result,
        verification=verification,
        aggregate_provenance=StructuralPipelineProvenance(
            pipeline_identity="mechcad-structural-pipeline@1",
            geometry_provenance=_provenance("freecad"),
            mesh_provenance=_provenance("gmsh"),
            solver_provenance=_provenance("calculix"),
            parser_provenance=StructuralResultParserProvenance(),
        ),
    )


@pytest.fixture
def evidence_payload() -> StructuralEvidencePayload:
    return _payload()


def _mesh(size: float) -> MeshSpecification:
    return MeshSpecification(
        global_target_size_mm=size,
        quality_policy_id="quality@1",
        mesher_settings_version="gmsh-settings@1",
    )


def _study(**updates) -> StructuralMeshConvergenceStudy:
    values = {
        "policy_id": "study@1",
        "mesh_specifications": (_mesh(10.0), _mesh(7.5), _mesh(5.0)),
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


def test_payload_is_frozen_finite_and_subject_defaults_to_ordinary(evidence_payload):
    assert evidence_payload.schema_version == STRUCTURAL_EVIDENCE_SCHEMA_VERSION
    assert evidence_payload.subject is EvidenceSubject.STRUCTURAL_ANALYSIS
    assert evidence_payload.mesh_convergence_status is StructuralMeshConvergenceStatus.NOT_EVALUATED

    with pytest.raises(ValidationError):
        evidence_payload.schema_version = STRUCTURAL_EVIDENCE_SCHEMA_VERSION
    with pytest.raises(ValidationError):
        StructuralRepeatabilityPolicy(
            policy_id="policy@1",
            source_project_id="project",
            source_definition_id="definition",
            source_definition_hash="sha256:" + "a" * 64,
            source_request_hash="sha256:" + "b" * 64,
            required_provider_identities=("provider@1",),
            required_runtime_identities=("runtime@1",),
            relative_tolerances=(("free_end_transverse_displacement_mm", inf),),
        )


def test_pipeline_provenance_is_separate_from_direct_manifest_producers(evidence_payload):
    assert evidence_payload.aggregate_provenance.solver_provenance is not None
    assert evidence_payload.execution_manifest.solver_manifest.backend_provenance is not None
    assert evidence_payload.aggregate_provenance.solver_provenance is not (
        evidence_payload.execution_manifest.solver_manifest.backend_provenance
    )


def test_repeatability_policy_hash_excludes_only_its_own_field():
    policy = StructuralRepeatabilityPolicy(
        policy_id="repeatability@1",
        source_project_id="project",
        source_definition_id="definition",
        source_definition_hash="sha256:" + "a" * 64,
        source_request_hash="sha256:" + "b" * 64,
        required_provider_identities=("provider@1",),
        required_runtime_identities=("freecad@1", "gmsh@1", "calculix@1"),
        semantic_summary_fields=("free_end_displacement_mm", "maximum_displacement_mm"),
        absolute_tolerances=(
            ("free_end_displacement_mm", 0.01),
            ("maximum_displacement_mm", 0.01),
        ),
        relative_tolerances=(
            ("free_end_displacement_mm", 0.02),
            ("maximum_displacement_mm", 0.02),
        ),
    )
    changed = policy.model_copy(update={"policy_hash": "sha256:" + "0" * 64})

    assert policy.policy_hash == structural_repeatability_policy_hash(policy)
    assert structural_repeatability_policy_hash(policy) == structural_repeatability_policy_hash(changed)
    with pytest.raises(ValidationError, match="mesh"):
        StructuralRepeatabilityPolicy(
            policy_id="repeatability@1",
            semantic_summary_fields=("mesh_node_ids",),
        )


def test_repeatability_policy_requires_complete_source_and_runtime_binding():
    with pytest.raises(ValidationError, match="source"):
        StructuralRepeatabilityPolicy(
            policy_id="repeatability@1",
            required_provider_identities=("provider@1",),
            required_runtime_identities=("runtime@1",),
        )

    with pytest.raises(ValidationError, match="summary"):
        StructuralRepeatabilityPolicy(
            policy_id="repeatability@1",
            source_project_id="project",
            source_definition_id="definition",
            source_definition_hash="sha256:" + "a" * 64,
            source_request_hash="sha256:" + "b" * 64,
            required_provider_identities=("provider@1",),
            required_runtime_identities=("runtime@1",),
            semantic_summary_fields=(),
        )


def test_convergence_kind_requires_typed_convergence_payload():
    with pytest.raises(ValidationError, match="convergence"):
        Evidence(
            id="EVD-CONVERGENCE-1",
            kind=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY.value,
            subject=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY,
            summary="untyped convergence",
            revision=1,
            state_hash="sha256:" + "a" * 64,
        )

def test_repeatability_and_convergence_policies_reject_unbounded_or_invalid_sequences():
    with pytest.raises(ValidationError, match="unique"):
        _study(mesh_specifications=(_mesh(5.0), _mesh(5.0), _mesh(2.0)))
    with pytest.raises(ValidationError, match="at least 3"):
        _study(mesh_specifications=(_mesh(5.0), _mesh(2.0)))
    with pytest.raises(ValidationError, match="max_levels"):
        _study(max_levels=2)
    with pytest.raises(ValidationError):
        _study(relative_change_threshold=nan)


def test_convergence_study_hash_and_statuses_are_typed_and_immutable():
    study = _study()
    assert study.study_hash == structural_mesh_convergence_study_hash(study)
    assert study.response_semantics == "magnitude"
    assert StructuralMeshConvergenceStatus.NOT_EVALUATED.value == "not_evaluated"
    assert {
        StructuralMeshConvergenceStatus.CONVERGED,
        StructuralMeshConvergenceStatus.NOT_CONVERGED,
        StructuralMeshConvergenceStatus.NOT_EVALUABLE,
        StructuralMeshConvergenceStatus.INTEGRITY_FAILURE,
    }.issubset(set(StructuralMeshConvergenceStatus))
    assert tuple(StructuralRepeatabilityStatus) == (
        StructuralRepeatabilityStatus.REPEATABLE,
        StructuralRepeatabilityStatus.NOT_REPEATABLE,
        StructuralRepeatabilityStatus.INTEGRITY_FAILURE,
    )
    assert tuple(StructuralEvidenceCurrentness) == (
        StructuralEvidenceCurrentness.CURRENT,
        StructuralEvidenceCurrentness.STALE_RELATIVE_TO_CURRENT_STATE,
        StructuralEvidenceCurrentness.CURRENTNESS_UNAVAILABLE,
    )

    with pytest.raises(ValidationError):
        study.max_levels = 4

    with pytest.raises(ValidationError, match="response_semantics"):
        _study(response_semantics="signed")


def test_convergence_subject_requires_study_result(evidence_payload):
    with pytest.raises(ValidationError, match="convergence"):
        StructuralEvidencePayload.model_validate({
            **evidence_payload.model_dump(mode="json"),
            "subject": EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY,
            "semantic_hash": "pending",
        })


def _convergence_result(study: StructuralMeshConvergenceStudy) -> StructuralMeshConvergenceResult:
    return StructuralMeshConvergenceResult(
        study=study,
        status=StructuralMeshConvergenceStatus.CONVERGED,
        levels=tuple(
            StructuralMeshConvergenceLevel(
                level_index=index,
                evidence_id=f"EVD-{index}",
                evidence_hash=f"sha256:{str(index) * 64}",
                mesh_specification_hash=mesh_hash,
                node_count=10 + index,
                volume_element_count=index,
                response_value=1.0 + index / 100.0,
                previous_relative_change=0.01 if index > 1 else None,
            )
            for index, mesh_hash in enumerate(study.mesh_specification_hashes, start=1)
        ),
    )


def test_convergence_subject_accepts_only_convergence_bindings(evidence_payload):
    study = _study()
    convergence = _convergence_result(study)
    values = evidence_payload.model_dump(mode="python")
    values.update(
        {
            "subject": EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY,
            "request": None,
            "execution_manifest_artifact_id": None,
            "execution_manifest_artifact_hash": None,
            "execution_manifest": None,
            "result": None,
            "verification": None,
            "analytical_validation": None,
            "analytical_geometry_observation": None,
            "analytical_material_observation": None,
            "aggregate_provenance": None,
            "repeatability": None,
            "convergence": convergence,
            "mesh_convergence_status": StructuralMeshConvergenceStatus.CONVERGED,
            "semantic_hash": "pending",
        }
    )
    payload = StructuralEvidencePayload.model_validate(values)
    assert payload.convergence == convergence
    values["request"] = evidence_payload.request
    with pytest.raises(ValidationError, match="physical"):
        StructuralEvidencePayload.model_validate(values)


def test_convergence_result_rejects_partial_successful_level_sequence():
    study = _study(
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
    result_values = _convergence_result(study).model_dump(mode="json")
    result_values["levels"] = result_values["levels"][:3]
    result_values["result_hash"] = "pending"

    with pytest.raises(ValidationError, match="all declared"):
        StructuralMeshConvergenceResult.model_validate(result_values)

    result_values["status"] = StructuralMeshConvergenceStatus.NOT_EVALUABLE.value
    result_values["reason"] = "response_metric_unavailable"
    result_values["result_hash"] = "pending"
    with pytest.raises(ValidationError, match="all declared"):
        StructuralMeshConvergenceResult.model_validate(result_values)


def test_not_evaluable_convergence_requires_complete_typed_level_records():
    study = _study()
    result_values = _convergence_result(study).model_dump(mode="json")
    result_values["status"] = StructuralMeshConvergenceStatus.NOT_EVALUABLE.value
    result_values["reason"] = "response_metric_unavailable"
    result_values["levels"] = [
        {
            **level,
            "response_value": None,
            "previous_relative_change": None,
            "status": StructuralMeshConvergenceStatus.NOT_EVALUABLE.value,
            "reason": "response_metric_unavailable",
        }
        for level in result_values["levels"]
    ]
    result_values["result_hash"] = "pending"

    result = StructuralMeshConvergenceResult.model_validate(result_values)

    assert result.status is StructuralMeshConvergenceStatus.NOT_EVALUABLE
    assert len(result.levels) == len(study.mesh_specifications)
    assert all(level.response_value is None for level in result.levels)
    assert all(level.status is StructuralMeshConvergenceStatus.NOT_EVALUABLE for level in result.levels)

    with pytest.raises(ValidationError, match="all declared"):
        StructuralMeshConvergenceResult(
            study=study,
            status=StructuralMeshConvergenceStatus.NOT_EVALUABLE,
            reason="response_metric_unavailable",
        )

def test_convergence_levels_bind_to_the_study_mesh_specification_sequence():
    study = _study()
    convergence = _convergence_result(study)
    wrong_level = convergence.levels[1].model_copy(
        update={"mesh_specification_hash": "sha256:" + "x" * 64}
    )
    with pytest.raises(ValidationError, match="mesh specification"):
        StructuralMeshConvergenceResult(
            study=study,
            status=StructuralMeshConvergenceStatus.CONVERGED,
            levels=(convergence.levels[0], wrong_level, convergence.levels[2]),
        )


def test_repeatability_comparison_rejects_mesh_node_and_element_correspondence_ids():
    with pytest.raises(ValidationError, match="correspondence"):
        StructuralRepeatabilityComparison(
            field_id="mesh_node_ids",
            first_value=(1,),
            second_value=(2,),
            absolute_tolerance=0.0,
            relative_tolerance=0.0,
            within_tolerance=True,
        )


def test_structural_provenance_is_deeply_frozen(evidence_payload):
    with pytest.raises(ValidationError):
        evidence_payload.aggregate_provenance.solver_provenance.backend_name = "forged"
    with pytest.raises(ValidationError):
        evidence_payload.execution_manifest.solver_manifest.backend_provenance.backend_name = "forged"


def test_convergence_study_restricts_supported_domain_and_runtime_constraints():
    with pytest.raises(ValidationError, match="domain"):
        _study(response_domain="unsupported-domain")
    with pytest.raises(ValidationError, match="runtime"):
        _study(required_runtime_identities=())


def test_mesh_convergence_status_matches_subject_and_result(evidence_payload):
    ordinary = evidence_payload.model_dump(mode="python")
    ordinary["mesh_convergence_status"] = StructuralMeshConvergenceStatus.CONVERGED
    ordinary["semantic_hash"] = "pending"
    with pytest.raises(ValidationError, match="status"):
        StructuralEvidencePayload.model_validate(ordinary)

    study = _study()
    convergence = _convergence_result(study)
    values = evidence_payload.model_dump(mode="python")
    values.update(
        {
            "subject": EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY,
            "request": None,
            "execution_manifest_artifact_id": None,
            "execution_manifest_artifact_hash": None,
            "execution_manifest": None,
            "result": None,
            "verification": None,
            "analytical_validation": None,
            "analytical_geometry_observation": None,
            "analytical_material_observation": None,
            "aggregate_provenance": None,
            "repeatability": None,
            "convergence": convergence,
            "mesh_convergence_status": StructuralMeshConvergenceStatus.NOT_CONVERGED,
            "semantic_hash": "pending",
        }
    )
    with pytest.raises(ValidationError, match="status"):
        StructuralEvidencePayload.model_validate(values)


def test_repeatability_result_requires_policy_and_compared_evidence_ids():
    policy = StructuralRepeatabilityPolicy(
        policy_id="repeatability@1",
        source_project_id="project",
        source_definition_id="definition",
        source_definition_hash="sha256:" + "a" * 64,
        source_request_hash="sha256:" + "b" * 64,
        required_provider_identities=("provider@1",),
        required_runtime_identities=("runtime@1",),
        semantic_summary_fields=("free_end_transverse_displacement_mm",),
    )
    result = StructuralRepeatabilityResult(
        policy=policy,
        first_evidence_id="EVD-1",
        second_evidence_id="EVD-2",
        status=StructuralRepeatabilityStatus.REPEATABLE,
        comparisons=(StructuralRepeatabilityComparison(
            field_id="free_end_transverse_displacement_mm",
            first_value=1.0,
            second_value=1.0,
            absolute_tolerance=0.0,
            relative_tolerance=0.0,
            within_tolerance=True,
        ),),
    )
    assert result.policy_hash == policy.policy_hash
    with pytest.raises(ValidationError):
        StructuralRepeatabilityResult(
            policy=policy,
            first_evidence_id="EVD-1",
            second_evidence_id="EVD-1",
            status=StructuralRepeatabilityStatus.REPEATABLE,
            comparisons=(),
        )


def _convergence_payload() -> StructuralEvidencePayload:
    study = _study()
    return StructuralEvidencePayload(
        subject=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY,
        mesh_convergence_status=StructuralMeshConvergenceStatus.CONVERGED,
        convergence=_convergence_result(study),
    )


def test_legacy_evidence_round_trip_has_no_structural_payload():
    legacy = Evidence(
        id="EVD-1",
        kind="analysis.legacy",
        summary="legacy",
        revision=1,
        state_hash="sha256:state",
    )

    reloaded = Evidence.model_validate_json(legacy.model_dump_json())

    assert reloaded.subject is None
    assert reloaded.structural_evidence_payload is None
    serialized = json.loads(legacy.model_dump_json())
    assert "subject" not in serialized
    assert "structural_evidence_payload" not in serialized


def test_structural_evidence_discriminators_bind_kind_subject_and_payload(evidence_payload):
    ordinary = Evidence(
        id="EVD-ordinary",
        kind="analysis.structural",
        subject=EvidenceSubject.STRUCTURAL_ANALYSIS,
        summary="ordinary structural evidence",
        revision=1,
        state_hash="sha256:state",
        structural_evidence_payload=evidence_payload,
    )
    convergence_payload = _convergence_payload()
    convergence = Evidence(
        id="EVD-convergence",
        kind="analysis.structural.convergence",
        subject=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY,
        summary="structural convergence evidence",
        revision=1,
        state_hash="sha256:state",
        structural_evidence_payload=convergence_payload,
    )

    assert ordinary.subject is EvidenceSubject.STRUCTURAL_ANALYSIS
    assert ordinary.structural_evidence_payload is evidence_payload
    assert convergence.subject is EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY
    assert convergence.structural_evidence_payload is convergence_payload

    with pytest.raises(ValidationError, match="discriminator"):
        Evidence(
            id="EVD-mismatch",
            kind="analysis.structural.convergence",
            subject=EvidenceSubject.STRUCTURAL_ANALYSIS,
            summary="mismatched structural evidence",
            revision=1,
            state_hash="sha256:state",
            structural_evidence_payload=evidence_payload,
        )


def test_unsupported_structural_schema_version_fails_through_typed_payload(evidence_payload):
    with pytest.raises(ValidationError, match="schema"):
        Evidence.model_validate(
            {
                "id": "EVD-unsupported",
                "kind": "analysis.structural",
                "subject": EvidenceSubject.STRUCTURAL_ANALYSIS,
                "summary": "unsupported structural evidence",
                "revision": 1,
                "state_hash": "sha256:state",
                "structural_evidence_payload": {
                    **evidence_payload.model_dump(mode="json"),
                    "schema_version": "structural-evidence@999",
                    "semantic_hash": "pending",
                },
            }
        )


def test_generic_evidence_module_depends_only_on_structural_data_models():
    source = Path("src/mechcad_harness/models/evidence.py").read_text(encoding="utf-8")

    assert "structural.evidence_service" not in source
    assert "StructuralEvidenceVerifier" not in source
    assert "ArtifactStore" not in source
    assert "ProductionApplication" not in source
    assert "discover_" not in source


def test_analytical_vector_checks_preserve_tuple_semantics_after_json_round_trip():
    from mechcad_harness.structural.evidence_models import AnalyticalValidationCheck

    check = AnalyticalValidationCheck(
        check_id="geometry",
        expected_value=(1.0, 2.0, 3.0),
        observed_value=(1.0, 2.0, 3.0),
        absolute_error=0.0,
        relative_error=0.0,
        tolerance=0.01,
        status="pass",
    )

    reloaded = AnalyticalValidationCheck.model_validate_json(check.model_dump_json())

    assert reloaded.expected_value == check.expected_value
    assert isinstance(reloaded.expected_value, tuple)
    assert reloaded.observed_value == check.observed_value


def test_generic_evidence_import_does_not_load_structural_runtime_modules():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "from mechcad_harness.models.evidence import Evidence; "
                "print(sorted(name for name in sys.modules "
                "if name in {'mechcad_harness.structural.runtime', "
                "'mechcad_harness.structural.geometry', "
                "'mechcad_harness.structural.mesh', "
                "'mechcad_harness.structural.validation'}))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "[]"


def test_structural_evidence_import_does_not_load_structural_runtime_modules():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import mechcad_harness.structural.evidence; "
                "print(sorted(name for name in sys.modules "
                "if name in {'mechcad_harness.structural.runtime', "
                "'mechcad_harness.structural.geometry', "
                "'mechcad_harness.structural.mesh', "
                "'mechcad_harness.structural.validation'}))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "[]"


def test_structural_evidence_models_imports_cleanly_in_subprocess():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from mechcad_harness.structural.evidence_models import "
                "CantileverGeometryObservation; "
                "print(CantileverGeometryObservation.__name__)"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "CantileverGeometryObservation"


def test_evidence_store_round_trips_typed_structural_payload(tmp_path, evidence_payload):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-1", DesignState(id="DES-1", revision=1))
    graph = DependencyGraph(
        [],
        [
            DependencyEdge(
                source="analysis.structural",
                target="analysis.structural.convergence",
            )
        ],
    )
    store = EvidenceStore(tmp_path, manager, graph)
    current = manager._read_current("PRJ-1")
    evidence = Evidence(
        id="EVD-structural",
        kind="analysis.structural",
        subject=EvidenceSubject.STRUCTURAL_ANALYSIS,
        summary="typed structural evidence",
        revision=current["revision"],
        state_hash=current["state_hash"],
        structural_evidence_payload=evidence_payload,
    )

    store.write_evidence("PRJ-1", evidence)
    reloaded = store.load_evidence("PRJ-1", evidence.id)

    assert reloaded == evidence
    assert reloaded.structural_evidence_payload == evidence_payload


def test_convergence_result_requires_ordered_level_evidence_bindings():
    study = _study()
    with pytest.raises(ValidationError, match="level"):
        StructuralMeshConvergenceResult(
            study=study,
            status=StructuralMeshConvergenceStatus.CONVERGED,
            levels=(),
        )

    failed = StructuralMeshConvergenceResult(
        study=study,
        status=StructuralMeshConvergenceStatus.INTEGRITY_FAILURE,
        levels=(),
        reason="level_count_mismatch",
    )
    assert failed.levels == ()


def test_convergence_result_rejects_not_evaluated_status():
    with pytest.raises(ValidationError, match="NOT_EVALUATED"):
        StructuralMeshConvergenceResult(
            study=_study(),
            status=StructuralMeshConvergenceStatus.NOT_EVALUATED,
        )


def test_repeatability_summary_values_are_deeply_immutable_and_hash_stable():
    policy = StructuralRepeatabilityPolicy(
        policy_id="repeatability@1",
        source_project_id="project",
        source_definition_id="definition",
        source_definition_hash="sha256:" + "a" * 64,
        source_request_hash="sha256:" + "b" * 64,
        required_provider_identities=("provider@1",),
        required_runtime_identities=("runtime@1",),
        semantic_summary_fields=("criterion_results",),
    )
    comparison = StructuralRepeatabilityComparison(
        field_id="criterion_results",
        first_value={"criterion": {"status": "pass", "details": [1, 2]}},
        second_value={"criterion": {"status": "pass", "details": [1, 3]}},
        absolute_tolerance=0.0,
        relative_tolerance=0.0,
        within_tolerance=False,
    )
    result = StructuralRepeatabilityResult(
        policy=policy,
        first_evidence_id="EVD-1",
        second_evidence_id="EVD-2",
        status=StructuralRepeatabilityStatus.NOT_REPEATABLE,
        comparisons=(comparison,),
    )
    before_hash = result.result_hash

    with pytest.raises(TypeError):
        comparison.first_value[0][1][0][1] = (1, 3)

    assert result.result_hash == before_hash == structural_repeatability_result_hash(result)
