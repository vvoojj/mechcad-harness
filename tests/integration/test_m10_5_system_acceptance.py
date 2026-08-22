from __future__ import annotations

import hashlib
import importlib.util
import json
import os

import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.backends.freecad import discover_freecad
from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_compilation import MountingPlateDesignSpec
from mechcad_harness.cad_program import cad_program_hash
from mechcad_harness.dependency import DependencyGraph, EvidenceStore
from mechcad_harness.imported_component import resolve_imported_component
from mechcad_harness.kinematic_sweep import CollisionClassification
from mechcad_harness.multi_joint_continuous_clearance import (
    MultiJointContinuousClearanceProofResult,
    MultiJointContinuousProofStatus,
    continuous_clearance_result_hash,
)
from mechcad_harness.multi_joint_continuous_path import MultiJointPath
from mechcad_harness.multi_joint_kinematics import (
    JointConfiguration,
    KinematicModel,
    RevoluteJointModel,
    joint_configuration_hash,
    kinematic_model_hash,
)
from mechcad_harness.runs import TaskDefinition
from mechcad_harness.state import StateManager


FREECAD_CANDIDATE = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"
FREECAD_AVAILABLE = discover_freecad().available or os.path.isfile(FREECAD_CANDIDATE)
GEAR_AVAILABLE = (
    importlib.util.find_spec("py_gearworks") is not None
    and importlib.util.find_spec("build123d") is not None
)


def _pair_map(pair_results):
    return {
        (item.moving_instance_id, item.stationary_instance_id): item
        for item in pair_results
    }


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD not available through discovery")
@pytest.mark.skipif(not GEAR_AVAILABLE, reason="gear + build123d extras are not installed")
def test_m10_5_capstone_proves_shared_configuration_across_motion_stack(
    tmp_path, monkeypatch
):
    from tests.integration.test_m10_3_live_multi_joint_collision import (
        _gear_input,
        _make_application,
    )

    executable = (
        discover_freecad().executable
        or os.environ.get("MECHCAD_FREECADCMD")
        or FREECAD_CANDIDATE
    )
    monkeypatch.setenv("MECHCAD_FREECADCMD", executable)
    runtime = discover_freecad().require_available()
    app = _make_application(tmp_path)
    live_backend_provenance = app._kinematic_measurement_provider.provenance()
    assert live_backend_provenance.library_version not in ("", "unknown")
    source = app.load_state()

    run = app.create_run().run
    task = TaskDefinition(
        task_id="TASK-gear-m10-5",
        run_id=run.run_id,
        task_type="tool",
        objective="capstone imported CAD",
        bound_revision=source.revision,
        bound_state_hash=source.state_hash,
        allowed_tools=("mechcad-build-spur-gear-cad@1.0",),
    )
    app.run_controller.add_task(run.run_id, task)
    tool_result = app.tool_broker.execute(
        run.run_id,
        task.task_id,
        "mechcad-build-spur-gear-cad",
        "1.0",
        _gear_input(),
        evidence_node="artifact.gear",
    )
    reference = tool_result.output["artifact_references"][0]
    store = ArtifactStore(
        app.state_manager.workspace,
        project_id=app.project_id,
        run_id=run.run_id,
        task_id=task.task_id,
    )
    artifact = store.existing(reference["artifact_id"])
    assert artifact is not None
    assert artifact.artifact_type is ArtifactType.STEP
    artifact_path = app.state_manager.workspace / artifact.relative_path
    assert reference["sha256"] == "sha256:" + hashlib.sha256(
        artifact_path.read_bytes()
    ).hexdigest()
    imported = resolve_imported_component(
        artifact_id=reference["artifact_id"],
        artifact_hash=reference["sha256"],
        store=store,
        component_id="link-2-gear",
    )

    compiled = app.compile_design_spec(
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        spec=MountingPlateDesignSpec(
            part_id="generated_link_plate",
            plate_length_mm=40.0,
            plate_width_mm=30.0,
            plate_thickness_mm=10.0,
        ),
    )
    plate = compiled.program
    assembly = CadAssemblyProgram(
        assembly_id="m10-5-live-mixed-chain",
        parts=(plate,),
        imported_components=(imported,),
        instances=(
            CadComponentInstance(instance_id="base", part_id=plate.part_id),
            CadComponentInstance(
                instance_id="link-1",
                part_id=plate.part_id,
                placement=CadRigidTransform(x_mm=20.0, y_mm=20.0, z_mm=20.0),
            ),
            CadComponentInstance(
                instance_id="link-2",
                part_id=imported.component_id,
                placement=CadRigidTransform(x_mm=70.0, y_mm=20.0, z_mm=20.0),
            ),
        ),
    )
    model = KinematicModel(
        model_id="m10-5-live-chain-model",
        joints=(
            RevoluteJointModel(
                joint_id="joint-1",
                parent_instance_id="base",
                child_instance_id="link-1",
                min_angle_deg=-45.0,
                max_angle_deg=45.0,
            ),
            RevoluteJointModel(
                joint_id="joint-2",
                parent_instance_id="link-1",
                child_instance_id="link-2",
                axis_origin_x_mm=50.0,
                min_angle_deg=-45.0,
                max_angle_deg=45.0,
            ),
        ),
    )
    q0 = JointConfiguration(
        model_id=model.model_id,
        positions={"joint-1": 0.0, "joint-2": 0.0},
    )
    q1 = JointConfiguration(
        model_id=model.model_id,
        positions={"joint-1": 20.0, "joint-2": 20.0},
    )
    configurations = (q0, q1)
    path = MultiJointPath(model_id=model.model_id, waypoints=configurations)

    source_hash = assembly_hash(assembly)
    source_instances = tuple(
        (item.instance_id, item.placement.model_dump(mode="json"))
        for item in assembly.instances
    )
    state_before = app.load_state()
    artifacts_before = tuple(
        sorted(
            path.relative_to(app.state_manager.workspace).as_posix()
            for path in app.state_manager.workspace.glob(
                "projects/*/runs/*/artifacts/*/metadata.json"
            )
        )
    )

    discrete = app.analyze_multi_joint_collision_sweep(
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        assembly=assembly,
        model=model,
        configurations=configurations,
        moving_instance_ids=("link-1", "link-2"),
        stationary_instance_ids=("base",),
    )
    fk = app.evaluate_multi_joint_configuration(
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        assembly=assembly,
        model=model,
        configuration=q1,
    )
    continuous = app.prove_continuous_multi_joint_path_clearance(
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        assembly=assembly,
        model=model,
        path=path,
        moving_instance_ids=("link-1", "link-2"),
        stationary_instance_ids=("base",),
        max_depth=8,
        max_exact_evaluations=100,
    )
    discrete_repeat = app.analyze_multi_joint_collision_sweep(
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        assembly=assembly,
        model=model,
        configurations=configurations,
        moving_instance_ids=("link-1", "link-2"),
        stationary_instance_ids=("base",),
    )
    continuous_repeat = app.prove_continuous_multi_joint_path_clearance(
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        assembly=assembly,
        model=model,
        path=path,
        moving_instance_ids=("link-1", "link-2"),
        stationary_instance_ids=("base",),
        max_depth=8,
        max_exact_evaluations=100,
    )

    assert discrete.continuous_path_verified is False
    assert continuous.status is MultiJointContinuousProofStatus.VERIFIED_CLEAR
    assert continuous.continuous_path_verified is True
    assert discrete_repeat.request_hash == discrete.request_hash
    assert discrete_repeat.result_hash == discrete.result_hash
    assert continuous_repeat.request_hash == continuous.request_hash
    assert continuous_repeat.result_hash == continuous.result_hash
    assert discrete.model_hash == kinematic_model_hash(model)
    assert fk.model_hash == discrete.model_hash
    assert fk.transformed_assembly_hash == discrete.configuration_results[1].transformed_assembly_hash

    discrete_by_configuration = {
        item.configuration_hash: item for item in discrete.configuration_results
    }
    continuous_by_configuration = {
        item.configuration_hash: item for item in continuous.exact_evaluations
    }
    q1_hash = joint_configuration_hash(q1)
    assert tuple(
        (item.moving_instance_id, item.stationary_instance_id)
        for item in discrete.configuration_results[1].pair_results
    ) == (("link-1", "base"), ("link-2", "base"))
    for configuration in configurations:
        configuration_hash = joint_configuration_hash(configuration)
        discrete_result = discrete_by_configuration[configuration_hash]
        continuous_result = continuous_by_configuration[configuration_hash]
        assert discrete_result.transformed_assembly_hash == continuous_result.transformed_assembly_hash
        if configuration_hash == q1_hash:
            assert discrete_result.transformed_assembly_hash == fk.transformed_assembly_hash
        discrete_pairs = _pair_map(discrete_result.pair_results)
        continuous_pairs = _pair_map(continuous_result.pair_results)
        assert tuple(discrete_pairs) == tuple(continuous_pairs)
        for pair in discrete_pairs:
            assert discrete_pairs[pair].interference_volume_mm3 == pytest.approx(
                continuous_pairs[pair].interference_volume_mm3
            )
            assert discrete_pairs[pair].exact_distance_mm == pytest.approx(
                continuous_pairs[pair].exact_distance_mm
            )
            assert discrete_pairs[pair].classification is continuous_pairs[pair].classification

    discrete_evidence = app.get_multi_joint_collision_sweep_evidence(discrete.result_hash)
    continuous_evidence = app.get_multi_joint_continuous_proof_evidence(continuous.result_hash)
    assert discrete_evidence is not None
    assert continuous_evidence is not None
    assert discrete_evidence.analysis_execution_provenance.result_hash == discrete.result_hash
    assert continuous_evidence.continuous_proof_execution_provenance.result_hash == continuous.result_hash
    assert continuous_evidence.continuous_proof_execution_provenance.path_hash == path.path_hash

    reloaded_state_manager = StateManager(app.state_manager.workspace)
    reloaded_store = EvidenceStore(
        app.state_manager.workspace,
        reloaded_state_manager,
        DependencyGraph.from_yaml(tmp_path / "dependencies.yaml"),
    )
    reloaded_discrete_evidence = reloaded_store.load_evidence(
        app.project_id, discrete_evidence.id
    )
    reloaded_continuous_evidence = reloaded_store.load_evidence(
        app.project_id, continuous_evidence.id
    )
    restored_continuous = MultiJointContinuousClearanceProofResult.model_validate(
        reloaded_continuous_evidence.continuous_multi_joint_clearance_proof_result_payload
    )
    assert reloaded_discrete_evidence.analysis_execution_provenance.result_hash == discrete.result_hash
    assert restored_continuous.result_hash == continuous.result_hash
    assert restored_continuous.result_hash == continuous_clearance_result_hash(restored_continuous)
    assert restored_continuous.exact_evaluations == continuous.exact_evaluations
    assert restored_continuous.certified_leaf_certificates == continuous.certified_leaf_certificates
    assert restored_continuous.reach_bounds == continuous.reach_bounds
    assert restored_continuous.unresolved_intervals == continuous.unresolved_intervals

    assert assembly_hash(assembly) == source_hash
    assert source_instances == tuple(
        (item.instance_id, item.placement.model_dump(mode="json"))
        for item in assembly.instances
    )
    state_after = app.load_state()
    assert state_after.revision == state_before.revision == source.revision
    assert state_after.state_hash == state_before.state_hash == source.state_hash
    assert artifacts_before == tuple(
        sorted(
            path.relative_to(app.state_manager.workspace).as_posix()
            for path in app.state_manager.workspace.glob(
                "projects/*/runs/*/artifacts/*/metadata.json"
            )
        )
    )

    print(
        "M10_5_CAPSTONE="
        + json.dumps(
            {
                "runtime": {
                    "executable": runtime.executable,
                    "version": live_backend_provenance.library_version,
                    "execution_mode": runtime.execution_boundary,
                },
                "source_assembly_hash": source_hash,
                "source_revision": source.revision,
                "source_state_hash": source.state_hash,
                "generated_program_hash": cad_program_hash(plate),
                "generated_spec_hash": compiled.spec_hash,
                "generated_compiler_version": compiled.compiler_version,
                "imported_artifact_id": imported.artifact_id,
                "imported_artifact_hash": imported.artifact_hash,
                "imported_source_revision": imported.source_revision,
                "imported_source_state_hash": imported.source_state_hash,
                "imported_producer_backend": tool_result.backend_provenance.model_dump(mode="json"),
                "model_hash": discrete.model_hash,
                "path_hash": path.path_hash,
                "m10_3_request_hash": discrete.request_hash,
                "m10_3_result_hash": discrete.result_hash,
                "m10_3_evidence_id": discrete_evidence.id,
                "m10_4_request_hash": continuous.request_hash,
                "m10_4_result_hash": continuous.result_hash,
                "m10_4_evidence_id": continuous_evidence.id,
                "provider": {
                    "name": continuous_evidence.continuous_proof_execution_provenance.provider_name,
                    "version": continuous_evidence.continuous_proof_execution_provenance.provider_version,
                    "backend": continuous_evidence.continuous_proof_execution_provenance.backend_provenance.model_dump(mode="json"),
                    "execution_mode": continuous_evidence.continuous_proof_execution_provenance.execution_mode,
                },
                "proof_algorithm_version": continuous.proof_algorithm_version,
                "reach_bound_algorithm_version": continuous.reach_bound_algorithm_version,
                "waypoints": [q0.positions, q1.positions],
                "exact_evaluations": continuous.exact_evaluations_count,
                "certified_leaves": len(continuous.certified_leaf_certificates),
                "certified_leaf_payload": [
                    item.model_dump(mode="json")
                    for item in continuous.certified_leaf_certificates
                ],
                "unresolved_intervals": [
                    item.model_dump(mode="json")
                    for item in continuous.unresolved_intervals
                ],
                "reach_bounds": [
                    item.model_dump(mode="json")
                    for item in continuous.reach_bounds.records
                ],
                "minimum_certified_lower_clearance_mm": continuous.minimum_certified_lower_clearance_mm,
                "shared_pairs": [
                    {
                        "configuration_hash": item.configuration_hash,
                        "transformed_assembly_hash": item.transformed_assembly_hash,
                        "pairs": [pair.model_dump(mode="json") for pair in item.pair_results],
                    }
                    for item in discrete.configuration_results
                ],
            },
            sort_keys=True,
        )
    )
