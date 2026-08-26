from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from mechcad_harness.artifacts.storage import ArtifactStore, ArtifactType
from mechcad_harness.dependency import DependencyGraph, EvidenceStore
from mechcad_harness.models.structural import (
    MaximumDisplacementCriterion,
    YieldSafetyFactorCriterion,
)
from mechcad_harness.state.manager import StateManager
from mechcad_harness.structural.evidence import (
    FREE_END_TRANSVERSE_DISPLACEMENT,
    EvidenceSubject,
    StructuralEvidenceCurrentness,
    StructuralMeshConvergenceStatus,
    StructuralMeshConvergenceStudy,
    StructuralRepeatabilityPolicy,
    StructuralRepeatabilityStatus,
    structural_mesh_convergence_study_hash,
    structural_mesh_specification_hash,
    structural_repeatability_policy_hash,
)
from mechcad_harness.structural.evidence_service import (
    StructuralEvidenceVerifier,
    StructuralMeshConvergenceService,
    StructuralRepeatabilityService,
)
from mechcad_harness.structural.models import (
    StructuralCriterionStatus,
    StructuralExecutionStatus,
    execution_manifest_hash,
    mesh_manifest_hash,
)
from mechcad_harness.structural.mesh import _parse_msh_v2
from mechcad_harness.structural.runtime import (
    CALCULIX_IDENTITY,
    FREECAD_IDENTITY,
    GMSH_IDENTITY,
    discover_calculix,
    discover_freecad,
    discover_gmsh,
)
from mechcad_harness.structural_request import MeshSpecification, StructuralAnalysisRequest
from mechcad_harness.structural.evidence_models import cantilever_validation_policy_hash

from test_m11_4_live_structural import (
    CANTILEVER_FAIL_LIMIT_MM,
    CANTILEVER_MESH_SPECIFICATION,
    CANTILEVER_PASS_LIMIT_MM,
    _cantilever_binding,
    _cantilever_definition,
    _cantilever_request,
    _prepare_cantilever,
    _publish_step,
    live_app,
)


PROJECT_ID = "PRJ-M11-3-live"
REQUIRED_RUNTIME_IDENTITIES = (
    f"{FREECAD_IDENTITY.library_name}@{FREECAD_IDENTITY.library_version}",
    f"{GMSH_IDENTITY.library_name}@{GMSH_IDENTITY.library_version}",
    f"{CALCULIX_IDENTITY.library_name}@{CALCULIX_IDENTITY.library_version}",
)


@pytest.fixture(scope="module", autouse=True)
def require_real_structural_runtimes():
    discoveries = (discover_freecad(), discover_gmsh(), discover_calculix())
    unavailable = tuple(
        f"{discovery.identity.library_name} {discovery.version or 'unavailable'}"
        for discovery in discoveries
        if not discovery.available
    )
    if unavailable:
        pytest.skip("required live structural runtimes unavailable: " + ", ".join(unavailable))


def _manifest_artifact(tmp_path: Path, execution, request: StructuralAnalysisRequest):
    artifact_id = "STRUCT-JSON-" + hashlib.sha256(
        f"{request.request_hash}|json".encode("utf-8")
    ).hexdigest()[:16]
    store = ArtifactStore(tmp_path, project_id=PROJECT_ID, run_id=execution.run_id)
    artifact = store.existing(artifact_id)
    assert artifact is not None
    assert artifact.artifact_type is ArtifactType.JSON
    assert artifact_id in execution.produced_artifact_ids
    return artifact


def _publish_execution(live_app, tmp_path: Path, execution, request, *, analytical_policy=None):
    manifest_artifact = _manifest_artifact(tmp_path, execution, request)
    return live_app.publish_structural_evidence(
        execution_manifest=execution.manifest,
        request=request,
        analytical_policy=analytical_policy,
        execution_manifest_artifact_id=manifest_artifact.artifact_id,
        execution_manifest_artifact_hash=manifest_artifact.sha256,
    )


def _execute_live_pass(live_app, tmp_path: Path, *, mesh_size_mm: float = 5.0):
    definition = _cantilever_definition(
        MaximumDisplacementCriterion(
            criterion_id="DISP-1",
            load_case_id="LC-1",
            assessment_region_id="free",
            maximum_allowed_displacement_mm=CANTILEVER_PASS_LIMIT_MM,
        )
    )
    request, policy, _mesh, _geometry, _material = _prepare_cantilever(
        live_app, definition, tmp_path
    )
    if mesh_size_mm != CANTILEVER_MESH_SPECIFICATION.global_target_size_mm:
        request, policy = _request_for_mesh_size(request, policy, mesh_size_mm)
    execution = live_app.execute_structural_analysis(request=request)
    assert execution.execution_status is StructuralExecutionStatus.SUCCEEDED, execution.error_detail
    assert execution.manifest is not None
    evidence = _publish_execution(
        live_app, tmp_path, execution, request, analytical_policy=policy
    )
    return execution, request, policy, evidence


def _execute_live_outcome(live_app, tmp_path: Path, definition):
    request, _policy, _mesh, _geometry, _material = _prepare_cantilever(
        live_app, definition, tmp_path
    )
    execution = live_app.execute_structural_analysis(request=request)
    assert execution.execution_status is StructuralExecutionStatus.SUCCEEDED, execution.error_detail
    assert execution.manifest is not None
    evidence = _publish_execution(live_app, tmp_path, execution, request)
    return execution, request, evidence


def _fresh_live_verifier(workspace: Path, project_id: str, evidence_id: str):
    manager = StateManager(workspace)
    graph = DependencyGraph.from_yaml(Path(__file__).parents[2] / "config" / "dependencies.yaml")
    evidence_store = EvidenceStore(workspace, manager, graph)
    durable_evidence = evidence_store.load_evidence(project_id, evidence_id)
    payload = durable_evidence.structural_evidence_payload
    assert payload is not None
    if payload.execution_manifest is not None:
        run_id = payload.execution_manifest.run_id
    else:
        assert payload.convergence is not None
        first_level = evidence_store.load_evidence(
            project_id, payload.convergence.levels[0].evidence_id
        )
        assert first_level.structural_evidence_payload is not None
        assert first_level.structural_evidence_payload.execution_manifest is not None
        run_id = first_level.structural_evidence_payload.execution_manifest.run_id
    return StructuralEvidenceVerifier(
        workspace=workspace,
        project_id=project_id,
        state_manager=manager,
        artifact_store=ArtifactStore(workspace, project_id=project_id, run_id=run_id),
        evidence_store=evidence_store,
    )


def _request_for_mesh_size(request, policy, mesh_size_mm: float):
    specification = MeshSpecification(
        global_target_size_mm=mesh_size_mm,
        quality_policy_id=CANTILEVER_MESH_SPECIFICATION.quality_policy_id,
        mesher_settings_version=CANTILEVER_MESH_SPECIFICATION.mesher_settings_version,
    )
    policy = policy.model_copy(
        update={
            "request_hash": None,
            "mesh_specification_hash": structural_mesh_specification_hash(specification),
        }
    )
    request_values = request.model_dump(mode="json")
    request_values["mesh_specification"] = specification.model_dump(mode="json")
    request_values["analytical_policy_hash"] = cantilever_validation_policy_hash(policy)
    request_values["request_hash"] = "pending"
    request = StructuralAnalysisRequest.model_validate(request_values)
    policy = policy.model_copy(update={"request_hash": request.request_hash})
    return request, policy


def _repeatability_policy(request: StructuralAnalysisRequest):
    fields = (
        "free_end_transverse_displacement_mm",
        "maximum_displacement_mm",
        "maximum_von_mises_stress_mpa",
        "total_reaction_force_n",
        "total_reaction_moment_n_mm",
        "criterion_results",
        "analytical_validation",
    )
    return StructuralRepeatabilityPolicy(
        policy_id="m11-5-live-repeatability@1",
        source_project_id=PROJECT_ID,
        source_definition_id=request.source_binding.definition_id,
        source_definition_hash=request.source_binding.definition_hash,
        source_request_hash=request.request_hash,
        required_provider_identities=("freecad", "gmsh", "calculix"),
        required_runtime_identities=REQUIRED_RUNTIME_IDENTITIES,
        semantic_summary_fields=fields,
        absolute_tolerances=tuple((field, 0.01) for field in fields),
        relative_tolerances=tuple((field, 0.01) for field in fields),
    )


def _convergence_study():
    specifications = tuple(
        MeshSpecification(
            global_target_size_mm=size,
            quality_policy_id=CANTILEVER_MESH_SPECIFICATION.quality_policy_id,
            mesher_settings_version=CANTILEVER_MESH_SPECIFICATION.mesher_settings_version,
        )
        for size in (10.0, 7.5, 5.0)
    )
    return StructuralMeshConvergenceStudy(
        policy_id="m11-5-live-convergence@1",
        mesh_specifications=specifications,
        load_case_id="LC-1",
        response_metric=FREE_END_TRANSVERSE_DISPLACEMENT,
        response_domain="free-end",
        response_semantics="magnitude",
        relative_change_threshold=0.05,
        epsilon=1e-12,
        max_levels=3,
        required_runtime_identities=REQUIRED_RUNTIME_IDENTITIES,
    )


def test_live_pass_evidence_fresh_reload(live_app, tmp_path: Path):
    execution, request, _policy, evidence = _execute_live_pass(live_app, tmp_path)

    durable = _fresh_live_verifier(tmp_path, PROJECT_ID, evidence.id).evidence_store.load_evidence(
        PROJECT_ID, evidence.id
    )
    payload = durable.structural_evidence_payload
    assert payload is not None
    manifest_artifact = _manifest_artifact(tmp_path, execution, request)
    assert payload.execution_manifest_artifact_id == manifest_artifact.artifact_id
    assert payload.execution_manifest_artifact_hash == manifest_artifact.sha256

    verified = _fresh_live_verifier(tmp_path, PROJECT_ID, evidence.id).verify(evidence.id)
    assert verified.valid
    assert verified.engineering_status is StructuralCriterionStatus.PASS
    assert verified.payload.verification.overall_status is StructuralCriterionStatus.PASS


def test_live_fail_and_not_evaluable_evidence_fresh_reload(live_app, tmp_path: Path):
    cases = (
        (
            _cantilever_definition(
                MaximumDisplacementCriterion(
                    criterion_id="DISP-FAIL",
                    load_case_id="LC-1",
                    assessment_region_id="free",
                    maximum_allowed_displacement_mm=CANTILEVER_FAIL_LIMIT_MM,
                )
            ),
            StructuralCriterionStatus.FAIL,
            "maximum_displacement_exceeded",
        ),
        (
            _cantilever_definition(
                YieldSafetyFactorCriterion(
                    criterion_id="YIELD-MISSING",
                    load_case_id="LC-1",
                    assessment_region_id="free",
                    stress_sampling="element_nodal_extrapolated",
                    minimum_yield_safety_factor=1.5,
                    zero_stress_tolerance_mpa=1e-9,
                )
            ),
            StructuralCriterionStatus.NOT_EVALUABLE,
            "missing_material_property",
        ),
    )
    for definition, expected_status, expected_reason in cases:
        _execution, _request, evidence = _execute_live_outcome(
            live_app, tmp_path, definition
        )
        verified = _fresh_live_verifier(tmp_path, PROJECT_ID, evidence.id).verify(evidence.id)
        criterion = verified.payload.verification.criterion_results[0]
        assert verified.valid
        assert verified.engineering_status is expected_status
        assert criterion.status is expected_status
        assert criterion.reason == expected_reason


def test_live_repeatability_policy_is_hashed_before_either_run(live_app, tmp_path: Path):
    definition = _cantilever_definition(
        MaximumDisplacementCriterion(
            criterion_id="DISP-REPEAT",
            load_case_id="LC-1",
            assessment_region_id="free",
            maximum_allowed_displacement_mm=CANTILEVER_PASS_LIMIT_MM,
        )
    )
    request, analytical_policy, _mesh, _geometry, _material = _prepare_cantilever(
        live_app, definition, tmp_path
    )
    policy = _repeatability_policy(request)
    policy_hash = structural_repeatability_policy_hash(policy)
    assert policy.policy_hash == policy_hash

    first_execution = live_app.execute_structural_analysis(request=request)
    assert first_execution.execution_status is StructuralExecutionStatus.SUCCEEDED, first_execution.error_detail
    first = _publish_execution(
        live_app, tmp_path, first_execution, request, analytical_policy=analytical_policy
    )
    second_execution = live_app.execute_structural_analysis(request=request)
    assert second_execution.execution_status is StructuralExecutionStatus.SUCCEEDED, second_execution.error_detail
    second = _publish_execution(
        live_app, tmp_path, second_execution, request, analytical_policy=analytical_policy
    )

    fresh_verifier = _fresh_live_verifier(tmp_path, PROJECT_ID, first.id)
    result = StructuralRepeatabilityService(fresh_verifier).compare(
        policy=policy,
        first_evidence_id=first.id,
        second_evidence_id=second.id,
    )
    assert first.id != second.id
    assert result.first_evidence_id == first.id
    assert result.second_evidence_id == second.id
    assert result.policy_hash == policy_hash
    assert result.status is StructuralRepeatabilityStatus.REPEATABLE


def test_live_three_level_convergence_publication_and_reload(live_app, tmp_path: Path):
    study = _convergence_study()
    study_hash = structural_mesh_convergence_study_hash(study)
    base_definition = _cantilever_definition(
        MaximumDisplacementCriterion(
            criterion_id="DISP-CONVERGENCE",
            load_case_id="LC-1",
            assessment_region_id="free",
            maximum_allowed_displacement_mm=CANTILEVER_PASS_LIMIT_MM,
        )
    )
    base_request, base_policy, _mesh, _geometry, _material = _prepare_cantilever(
        live_app, base_definition, tmp_path
    )

    level_ids = []
    level_snapshots = {}
    level_audit = []
    for mesh_size in (10.0, 7.5, 5.0):
        request, policy = _request_for_mesh_size(base_request, base_policy, mesh_size)
        execution = live_app.execute_structural_analysis(request=request)
        assert execution.execution_status is StructuralExecutionStatus.SUCCEEDED, execution.error_detail
        assert execution.run_id is not None
        assert execution.manifest is not None
        assert execution.manifest.mesh_manifest is not None
        evidence = _publish_execution(
            live_app, tmp_path, execution, request, analytical_policy=policy
        )
        assert execution.manifest is not None
        manifest = execution.manifest
        assert manifest.mesh_manifest is not None
        mesh_store = ArtifactStore(tmp_path, project_id=PROJECT_ID, run_id=execution.run_id)
        mesh_artifact, msh_bytes = mesh_store.read_verified_strict(
            manifest.mesh_artifact_id,
            expected_type=ArtifactType.MSH,
            expected_hash=manifest.mesh_artifact_hash,
        )
        nodes, surface_entities, volume_entities, _physical, _ = _parse_msh_v2(msh_bytes)
        msh_lines = msh_bytes.decode("utf-8", errors="replace").splitlines()
        in_elements = False
        c3d10_count = 0
        boundary_count = 0
        for line in msh_lines:
            if line == "$Elements":
                in_elements = True
                continue
            if line == "$EndElements":
                in_elements = False
                continue
            if not in_elements or not line or line.isdigit():
                continue
            parts = line.split()
            element_type = int(parts[1])
            if element_type == 11:
                c3d10_count += 1
            elif element_type in (2, 9):
                boundary_count += 1
        computed_mesh_manifest_hash = mesh_manifest_hash(manifest.mesh_manifest)
        response = next(
            check.observed_value
            for check in evidence.structural_evidence_payload.analytical_validation.checks
            if check.check_id == "tip_displacement"
        )
        level_audit.append({
            "target_mesh_size_mm": mesh_size,
            "evidence_id": evidence.id,
            "evidence_hash": evidence.structural_evidence_payload.semantic_hash,
            "mesh_specification_hash": structural_mesh_specification_hash(request.mesh_specification),
            "msh_artifact_id": mesh_artifact.artifact_id,
            "msh_sha256": hashlib.sha256(msh_bytes).hexdigest(),
            "node_count": len(nodes),
            "c3d10_volume_element_count": c3d10_count,
            "boundary_element_count": boundary_count,
            "mesh_semantic_hash": computed_mesh_manifest_hash,
            "mesh_manifest_hash": manifest.mesh_manifest_hash,
            "response_value": response,
            "run_id": execution.run_id,
            "request_hash": request.request_hash,
            "execution_manifest_hash": execution_manifest_hash(manifest),
            "execution_artifact_ids": tuple(execution.produced_artifact_ids),
        })
        assert mesh_artifact.run_id == execution.run_id
        assert mesh_artifact.sha256 == manifest.mesh_artifact_hash
        assert mesh_artifact.sha256 == "sha256:" + hashlib.sha256(msh_bytes).hexdigest()
        assert manifest.mesh_manifest.node_count == len(nodes)
        assert manifest.mesh_manifest.volume_element_count == c3d10_count
        assert manifest.mesh_manifest.boundary_element_count == boundary_count
        assert manifest.mesh_manifest_hash == computed_mesh_manifest_hash
        assert manifest.mesh_manifest.mesh_hash == mesh_artifact.sha256
        assert manifest.mesh_specification_hash == structural_mesh_specification_hash(request.mesh_specification)
        assert manifest.case_manifests[0].mesh_artifact_id == manifest.mesh_artifact_id
        assert manifest.case_manifests[0].mesh_artifact_hash == manifest.mesh_artifact_hash
        assert evidence.structural_evidence_payload is not None
        assert evidence.structural_evidence_payload.result.mesh_hash == manifest.mesh_artifact_hash
        assert evidence.structural_evidence_payload.result.load_case_results[0].mesh_hash == manifest.mesh_artifact_hash
        assert evidence.structural_evidence_payload.result.load_case_results[0].frd_artifact_hash == manifest.frd_artifact_hash
        assert evidence.structural_evidence_payload.result.load_case_results[0].dat_artifact_hash == manifest.dat_artifact_hash
        assert mesh_artifact.artifact_id in execution.produced_artifact_ids
        assert manifest.frd_artifact_id is not None
        assert manifest.dat_artifact_id is not None
        assert manifest.deck_artifact_id is not None
        deck_artifact = mesh_store.existing(manifest.deck_artifact_id)
        frd_artifact = mesh_store.existing(manifest.frd_artifact_id)
        dat_artifact = mesh_store.existing(manifest.dat_artifact_id)
        assert deck_artifact is not None and deck_artifact.input_hash == manifest.mesh_artifact_hash
        assert frd_artifact is not None and frd_artifact.input_hash == manifest.deck_artifact_hash
        assert dat_artifact is not None and dat_artifact.input_hash == manifest.deck_artifact_hash
        level_ids.append(evidence.id)
        level_snapshots[evidence.id] = live_app.evidence_store.load_evidence(PROJECT_ID, evidence.id)

    print("M11_5_CONVERGENCE_MESH_AUDIT=" + json.dumps(level_audit, sort_keys=True, separators=(",", ":")))
    assert len({item["mesh_specification_hash"] for item in level_audit}) == 3
    assert len({item["msh_artifact_id"] for item in level_audit}) == 3
    assert len({item["msh_sha256"] for item in level_audit}) == 3
    assert len({item["mesh_semantic_hash"] for item in level_audit}) == 3
    assert len({item["mesh_manifest_hash"] for item in level_audit}) == 3
    assert len({item["node_count"] for item in level_audit}) == 3
    assert len({item["c3d10_volume_element_count"] for item in level_audit}) == 3
    assert len({item["boundary_element_count"] for item in level_audit}) == 3
    assert len({item["run_id"] for item in level_audit}) == 3
    assert len({item["request_hash"] for item in level_audit}) == 3
    assert len({item["execution_manifest_hash"] for item in level_audit}) == 3
    artifact_sets = [set(item["execution_artifact_ids"]) for item in level_audit]
    assert all(left.isdisjoint(right) for index, left in enumerate(artifact_sets) for right in artifact_sets[index + 1:])

    level_ids = tuple(level_ids)
    fresh_verifier = _fresh_live_verifier(tmp_path, PROJECT_ID, level_ids[0])
    result = StructuralMeshConvergenceService(fresh_verifier).evaluate(
        study=study, level_evidence_ids=level_ids
    )
    assert result.study_hash == study_hash
    assert result.status in {
        StructuralMeshConvergenceStatus.CONVERGED,
        StructuralMeshConvergenceStatus.NOT_CONVERGED,
    }
    assert study.response_semantics == "magnitude"
    assert tuple(level.mesh_specification_hash for level in result.levels) == study.mesh_specification_hashes
    assert tuple(level.evidence_id for level in result.levels) == level_ids
    assert all(level.response_value > 0 for level in result.levels)

    publication_verifier = _fresh_live_verifier(tmp_path, PROJECT_ID, level_ids[0])
    convergence_evidence = StructuralMeshConvergenceService(publication_verifier).publish(
        study=study, level_evidence_ids=level_ids
    )
    convergence_verifier = _fresh_live_verifier(
        tmp_path, PROJECT_ID, convergence_evidence.id
    )
    reloaded = convergence_verifier.verify(convergence_evidence.id)
    assert reloaded.valid
    assert reloaded.payload.subject is EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY
    assert reloaded.payload.convergence == result
    for evidence_id, snapshot in level_snapshots.items():
        assert (
            convergence_verifier.evidence_store.load_evidence(PROJECT_ID, evidence_id)
            == snapshot
        )


def test_live_not_evaluable_convergence_publication_and_reload_without_analytical_metric(
    live_app, tmp_path: Path
):
    study = _convergence_study()
    base_definition = _cantilever_definition(
        MaximumDisplacementCriterion(
            criterion_id="DISP-CONVERGENCE-NO-METRIC",
            load_case_id="LC-1",
            assessment_region_id="free",
            maximum_allowed_displacement_mm=CANTILEVER_PASS_LIMIT_MM,
        )
    )
    revision, state_hash, step_artifact, program = _publish_step(
        live_app, base_definition, tmp_path
    )
    base_binding = _cantilever_binding(
        base_definition, revision, state_hash, step_artifact, program
    )
    base_request = _cantilever_request(base_binding)

    level_ids = []
    level_hashes = []
    level_snapshots = {}
    for mesh_size in (10.0, 7.5, 5.0):
        specification = MeshSpecification(
            global_target_size_mm=mesh_size,
            quality_policy_id=CANTILEVER_MESH_SPECIFICATION.quality_policy_id,
            mesher_settings_version=CANTILEVER_MESH_SPECIFICATION.mesher_settings_version,
        )
        request_values = base_request.model_dump(mode="json")
        request_values["mesh_specification"] = specification.model_dump(mode="json")
        request_values["analytical_policy_hash"] = None
        request_values["request_hash"] = "pending"
        request = StructuralAnalysisRequest.model_validate(request_values)
        execution = live_app.execute_structural_analysis(request=request)
        assert execution.execution_status is StructuralExecutionStatus.SUCCEEDED, execution.error_detail
        evidence = _publish_execution(
            live_app, tmp_path, execution, request, analytical_policy=None
        )
        level_ids.append(evidence.id)
        level_hashes.append(evidence.structural_evidence_payload.semantic_hash)
        level_snapshots[evidence.id] = _fresh_live_verifier(
            tmp_path, PROJECT_ID, evidence.id
        ).evidence_store.load_evidence(PROJECT_ID, evidence.id)

    level_ids = tuple(level_ids)
    level_hashes = tuple(level_hashes)
    evaluation_verifier = _fresh_live_verifier(tmp_path, PROJECT_ID, level_ids[0])
    result = StructuralMeshConvergenceService(evaluation_verifier).evaluate(
        study=study, level_evidence_ids=level_ids
    )

    assert result.status is StructuralMeshConvergenceStatus.NOT_EVALUABLE
    assert result.reason == "response_metric_unavailable"
    assert tuple(level.evidence_id for level in result.levels) == level_ids
    assert tuple(level.evidence_hash for level in result.levels) == level_hashes
    assert all(level.response_value is None for level in result.levels)

    publication_verifier = _fresh_live_verifier(tmp_path, PROJECT_ID, level_ids[0])
    convergence_evidence = StructuralMeshConvergenceService(publication_verifier).publish(
        study=study, level_evidence_ids=level_ids
    )
    reload_verifier = _fresh_live_verifier(
        tmp_path, PROJECT_ID, convergence_evidence.id
    )
    verified = reload_verifier.verify(convergence_evidence.id)

    assert verified.valid
    assert verified.payload.convergence is not None
    assert verified.payload.convergence.status is StructuralMeshConvergenceStatus.NOT_EVALUABLE
    assert tuple(level.evidence_id for level in verified.payload.convergence.levels) == level_ids
    assert tuple(level.evidence_hash for level in verified.payload.convergence.levels) == level_hashes
    for evidence_id, snapshot in level_snapshots.items():
        assert reload_verifier.evidence_store.load_evidence(PROJECT_ID, evidence_id) == snapshot


def test_live_historical_evidence_is_valid_stale_and_runtime_independent(
    live_app, tmp_path: Path, monkeypatch
):
    _execution, _request, _policy, evidence = _execute_live_pass(live_app, tmp_path)
    state_manager = StateManager(tmp_path)
    current_state = state_manager.load_current_state(PROJECT_ID)
    advanced = state_manager.create_revision(PROJECT_ID, current_state)
    assert advanced.revision == evidence.revision + 1

    def unavailable_runtime(*_args, **_kwargs):
        raise AssertionError("historical verification crossed a runtime boundary")

    monkeypatch.setattr("mechcad_harness.structural.runtime.discover_freecad", unavailable_runtime)
    monkeypatch.setattr("mechcad_harness.structural.runtime.discover_gmsh", unavailable_runtime)
    monkeypatch.setattr("mechcad_harness.structural.runtime.discover_calculix", unavailable_runtime)
    monkeypatch.setattr(subprocess, "run", unavailable_runtime)
    monkeypatch.setattr(
        "mechcad_harness.structural.geometry.StructuralFreeCADGeometryAdapter",
        unavailable_runtime,
    )
    monkeypatch.setattr(
        "mechcad_harness.structural.mesh.StructuralGmshMeshingProvider",
        unavailable_runtime,
    )
    monkeypatch.setattr(
        "mechcad_harness.structural.solver.StructuralCalculiXSolverProvider",
        unavailable_runtime,
    )

    verifier = _fresh_live_verifier(tmp_path, PROJECT_ID, evidence.id)
    verified = verifier.verify(evidence.id)
    assert verified.valid
    assert verified.engineering_status is StructuralCriterionStatus.PASS
    assert verifier.currentness(evidence.id) is StructuralEvidenceCurrentness.STALE_RELATIVE_TO_CURRENT_STATE
