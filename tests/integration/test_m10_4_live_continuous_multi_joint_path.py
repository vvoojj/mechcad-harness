from __future__ import annotations

import importlib.util
import json
import os

import pytest

from mechcad_harness.backends.freecad import discover_freecad
from mechcad_harness.kinematic_sweep import CollisionClassification
from mechcad_harness.multi_joint_continuous_clearance import (
    MultiJointContinuousClearanceProofResult,
    MultiJointContinuousProofStatus,
)
from mechcad_harness.multi_joint_continuous_path import MultiJointPath
from mechcad_harness.multi_joint_kinematics import JointConfiguration


FREECAD_CANDIDATE = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"
FREECAD_AVAILABLE = discover_freecad().available or os.path.isfile(FREECAD_CANDIDATE)
GEAR_AVAILABLE = importlib.util.find_spec("py_gearworks") is not None and importlib.util.find_spec("build123d") is not None


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD not available through discovery")
@pytest.mark.skipif(not GEAR_AVAILABLE, reason="gear + build123d extras are not installed")
def test_live_m10_4_path_clear_witness_and_not_proven(tmp_path, monkeypatch):
    from tests.integration.test_m10_3_live_multi_joint_collision import _gear_input
    from tests.integration.test_m10_3_live_multi_joint_collision import _make_application as make_m10_3_application
    from mechcad_harness.artifacts import ArtifactStore, ArtifactType
    from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, CadRigidTransform
    from mechcad_harness.cad_compilation import MountingPlateDesignSpec
    from mechcad_harness.imported_component import resolve_imported_component
    from mechcad_harness.multi_joint_kinematics import KinematicModel, RevoluteJointModel
    from mechcad_harness.runs import TaskDefinition

    executable = discover_freecad().executable or os.environ.get("MECHCAD_FREECADCMD") or FREECAD_CANDIDATE
    monkeypatch.setenv("MECHCAD_FREECADCMD", executable)
    app = make_m10_3_application(tmp_path)
    source = app.load_state()
    run = app.create_run().run
    task = TaskDefinition(
        task_id="TASK-gear-m10-4",
        run_id=run.run_id,
        task_type="tool",
        objective="cad",
        bound_revision=source.revision,
        bound_state_hash=source.state_hash,
        allowed_tools=("mechcad-build-spur-gear-cad@1.0",),
    )
    app.run_controller.add_task(run.run_id, task)
    tool_result = app.tool_broker.execute(run.run_id, task.task_id, "mechcad-build-spur-gear-cad", "1.0", _gear_input(), evidence_node="artifact.gear")
    reference = tool_result.output["artifact_references"][0]
    store = ArtifactStore(app.state_manager.workspace, project_id=app.project_id, run_id=run.run_id, task_id=task.task_id)
    imported = resolve_imported_component(artifact_id=reference["artifact_id"], artifact_hash=reference["sha256"], store=store, component_id="link-2-gear")
    plate = app.compile_design_spec(
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        spec=MountingPlateDesignSpec(part_id="generated_link_plate", plate_length_mm=40, plate_width_mm=30, plate_thickness_mm=10),
    ).program
    assembly = CadAssemblyProgram(
        assembly_id="m10-4-live-chain",
        parts=(plate,), imported_components=(imported,),
        instances=(
            CadComponentInstance(instance_id="base", part_id=plate.part_id),
            CadComponentInstance(instance_id="link-1", part_id=plate.part_id, placement=CadRigidTransform(x_mm=20, y_mm=20, z_mm=20)),
            CadComponentInstance(instance_id="link-2", part_id=imported.component_id, placement=CadRigidTransform(x_mm=70, y_mm=20, z_mm=20)),
        ),
    )
    model = KinematicModel(
        model_id="m10-4-live-model",
        joints=(
            RevoluteJointModel(joint_id="joint-1", parent_instance_id="base", child_instance_id="link-1", min_angle_deg=-45, max_angle_deg=45),
            RevoluteJointModel(joint_id="joint-2", parent_instance_id="link-1", child_instance_id="link-2", axis_origin_x_mm=50, min_angle_deg=-45, max_angle_deg=45),
        ),
    )
    clear_path = MultiJointPath(
        model_id=model.model_id,
        waypoints=(
            JointConfiguration(model_id=model.model_id, positions={"joint-1": 0, "joint-2": 0}),
            JointConfiguration(model_id=model.model_id, positions={"joint-1": 20, "joint-2": 20}),
        ),
    )
    clear = app.prove_continuous_multi_joint_path_clearance(
        source_revision=source.revision, source_state_hash=source.state_hash,
        assembly=assembly, model=model, path=clear_path,
        moving_instance_ids=("link-1", "link-2"), stationary_instance_ids=("base",),
        max_depth=8, max_exact_evaluations=100,
    )
    clear_evidence = app.get_multi_joint_continuous_proof_evidence(clear.result_hash)
    assert clear_evidence is not None
    durable_clear = MultiJointContinuousClearanceProofResult.model_validate(
        clear_evidence.continuous_multi_joint_clearance_proof_result_payload
    )
    assert app.get_multi_joint_continuous_proof_result(clear.result_hash) == clear
    assert clear_evidence.output_hash == clear.result_hash
    assert clear_evidence.continuous_proof_execution_provenance.result_hash == clear.result_hash
    assert clear_evidence.continuous_proof_execution_provenance.path_hash == clear_path.path_hash
    assert durable_clear == clear
    assert durable_clear.status is MultiJointContinuousProofStatus.VERIFIED_CLEAR
    assert durable_clear.continuous_path_verified is True
    assert durable_clear.exact_evaluations_count == 5
    assert [item.evaluation_index for item in durable_clear.exact_evaluations] == [0, 1, 2, 3, 4]
    assert [item.location.waypoint_index for item in durable_clear.exact_evaluations[:2]] == [0, 1]
    assert [item.location.t for item in durable_clear.exact_evaluations[2:]] == [0.5, 0.25, 0.75]
    assert all(item.pair_results for item in durable_clear.exact_evaluations)
    assert durable_clear.certified_leaf_certificates

    witness_path = MultiJointPath(
        model_id=model.model_id,
        waypoints=(
            JointConfiguration(model_id=model.model_id, positions={"joint-1": 0, "joint-2": 0}),
            JointConfiguration(model_id=model.model_id, positions={"joint-1": 30, "joint-2": 30}),
        ),
    )
    witness = app.prove_continuous_multi_joint_path_clearance(
        source_revision=source.revision, source_state_hash=source.state_hash,
        assembly=assembly, model=model, path=witness_path,
        moving_instance_ids=("link-1", "link-2"), stationary_instance_ids=("base",),
        required_clearance_mm=1000, max_depth=1, max_exact_evaluations=10,
    )
    witness_evidence = app.get_multi_joint_continuous_proof_evidence(witness.result_hash)
    assert witness_evidence is not None
    durable_witness = MultiJointContinuousClearanceProofResult.model_validate(
        witness_evidence.continuous_multi_joint_clearance_proof_result_payload
    )
    assert app.get_multi_joint_continuous_proof_result(witness.result_hash) == witness
    assert witness_evidence.output_hash == witness.result_hash
    assert witness_evidence.continuous_proof_execution_provenance.result_hash == witness.result_hash
    assert witness_evidence.continuous_proof_execution_provenance.path_hash == witness_path.path_hash
    assert durable_witness == witness
    assert durable_witness.status is MultiJointContinuousProofStatus.COLLISION_WITNESS
    assert durable_witness.collision_witness is not None
    assert durable_witness.collision_witness.classification in set(CollisionClassification)
    assert durable_witness.collision_witness.location.waypoint_index == 0
    assert durable_witness.collision_witness.exact_distance_mm <= 1000

    not_proven = app.prove_continuous_multi_joint_path_clearance(
        source_revision=source.revision, source_state_hash=source.state_hash,
        assembly=assembly, model=model, path=clear_path,
        moving_instance_ids=("link-1", "link-2"), stationary_instance_ids=("base",),
        max_depth=8, max_exact_evaluations=3,
    )
    not_proven_evidence = app.get_multi_joint_continuous_proof_evidence(not_proven.result_hash)
    assert not_proven_evidence is not None
    durable_not_proven = MultiJointContinuousClearanceProofResult.model_validate(
        not_proven_evidence.continuous_multi_joint_clearance_proof_result_payload
    )
    assert app.get_multi_joint_continuous_proof_result(not_proven.result_hash) == not_proven
    assert not_proven_evidence.output_hash == not_proven.result_hash
    assert not_proven_evidence.continuous_proof_execution_provenance.result_hash == not_proven.result_hash
    assert not_proven_evidence.continuous_proof_execution_provenance.path_hash == clear_path.path_hash
    assert durable_not_proven == not_proven
    assert durable_not_proven.exact_evaluations_count == 3
    assert len(durable_not_proven.exact_evaluations) == 3
    assert durable_not_proven.status is MultiJointContinuousProofStatus.NOT_PROVEN
    assert durable_not_proven.unresolved_intervals
    assert durable_not_proven.continuous_path_verified is False
    assert all(not item.produced_requested_clearance_witness for item in durable_not_proven.exact_evaluations)
    print("M10_4_LIVE=" + json.dumps({
        "clear": durable_clear.model_dump(mode="json"),
        "witness": durable_witness.model_dump(mode="json"),
        "not_proven": durable_not_proven.model_dump(mode="json"),
    }, sort_keys=True))
