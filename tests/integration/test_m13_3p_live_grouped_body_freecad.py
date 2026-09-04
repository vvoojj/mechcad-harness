from __future__ import annotations

import json
import math
import os

import pytest

from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
from mechcad_harness.application import ProductionApplication
from mechcad_harness.backends.freecad import FreeCADBackend, discover_freecad
from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.kinematic_sweep import CollisionClassification
from mechcad_harness.models import DesignState
from mechcad_harness.multi_joint_continuous_clearance import (
    ContinuousExactEvaluationV2,
    ContinuousExactPairResultV2,
    ContinuousIntervalCertificateV2,
    ContinuousPairCertificateV2,
    ContinuousSegmentResultV2,
    MultiJointContinuousClearanceProofResultV2,
    MultiJointContinuousCollisionWitnessV2,
    MultiJointContinuousProofStatus,
)
from mechcad_harness.multi_joint_continuous_path import (
    BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION,
    MultiJointPath,
)
from mechcad_harness.multi_joint_kinematics import (
    JointConfiguration,
    KinematicModelV2,
    KinematicRigidBody,
    KinematicRigidBodyMember,
    KinematicJointKind,
    RevoluteJointModelV2,
    rigid_transform_agrees,
    transform_compose,
    transform_inverse,
)
from mechcad_harness.multi_joint_pair_scope import ExactConstituentPair
from mechcad_harness.multi_joint_collision_sweep import (
    MULTI_JOINT_EXACT_COLLISION_SWEEP_V2_VERSION,
    ExactConstituentPairResultV2,
    MultiJointCollisionConfigurationResultV2,
    MultiJointCollisionSweepResultV2,
)
from mechcad_harness.state import StateManager
from mechcad_harness.transient_freecad_measurement import (
    FreeCADTransientAssemblyMeasurementProvider,
)


FREECAD_CANDIDATE = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"
FREECAD_AVAILABLE = discover_freecad().available or os.path.isfile(FREECAD_CANDIDATE)
PROJECT_ID = "PRJ-M13-3P-T14"


def _application(tmp_path):
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /components/*\n    owner: m13-3p-test\n",
        encoding="utf-8",
    )
    dependencies.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "when": ["/components/*"],
                        "invalidates": [
                            "analysis.multi_joint_kinematics",
                            "analysis.multi_joint_collision_sweep",
                            "analysis.continuous_multi_joint_clearance_proof",
                        ],
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    StateManager(workspace).create_project(
        PROJECT_ID,
        DesignState(id="DES-M13-3P-T14", revision=1),
    )
    identity = AgentIdentity(
        agent_name="m13-3p-test-agent",
        agent_version="1.0",
        role="m13-3p-test",
        protocol_version="1.0",
    )
    return ProductionApplication.create(
        workspace,
        PROJECT_ID,
        FakeAgentAdapter(identity, scripted_responses=()),
        ownership_path=ownership,
        dependency_path=dependencies,
    )


def _fixture():
    plate = CadPartProgram(
        part_id="grouped-plate",
        operations=(
            BasePlateOperation(
                operation_id="base",
                length_mm=10.0,
                width_mm=10.0,
                thickness_mm=2.0,
            ),
        ),
    )
    root_home = CadRigidTransform(
        x_mm=100.0,
        y_mm=-50.0,
        z_mm=5.0,
        rotation_quaternion=(0.91, 0.12, -0.27, 0.29),
    )
    root_to_a = CadRigidTransform(x_mm=30.0)
    a_to_b = CadRigidTransform(x_mm=30.0)
    member_offset = CadRigidTransform(x_mm=0.0, y_mm=22.0)
    a_home = transform_compose(root_home, root_to_a)
    b_home = transform_compose(root_home, transform_compose(root_to_a, a_to_b))
    assembly = CadAssemblyProgram(
        assembly_id="m13-3p-grouped-body-live",
        parts=(plate,),
        instances=(
            CadComponentInstance(instance_id="R1", part_id=plate.part_id, placement=root_home),
            CadComponentInstance(
                instance_id="R2",
                part_id=plate.part_id,
                placement=transform_compose(root_home, member_offset),
            ),
            CadComponentInstance(instance_id="A1", part_id=plate.part_id, placement=a_home),
            CadComponentInstance(
                instance_id="A2",
                part_id=plate.part_id,
                placement=transform_compose(
                    root_home, transform_compose(root_to_a, member_offset)
                ),
            ),
            CadComponentInstance(instance_id="B1", part_id=plate.part_id, placement=b_home),
            CadComponentInstance(
                instance_id="B2",
                part_id=plate.part_id,
                placement=transform_compose(
                    root_home,
                    transform_compose(transform_compose(root_to_a, a_to_b), member_offset),
                ),
            ),
        ),
    )
    model = KinematicModelV2(
        model_id="m13-3p-grouped-body-live-model",
        bodies=(
            KinematicRigidBody(
                body_id="R",
                reference_member_instance_id="R1",
                members=(
                    KinematicRigidBodyMember(
                        member_instance_id="R1",
                        reference_to_member_home=CadRigidTransform(),
                    ),
                    KinematicRigidBodyMember(
                        member_instance_id="R2",
                        reference_to_member_home=member_offset,
                    ),
                ),
            ),
            KinematicRigidBody(
                body_id="A",
                reference_member_instance_id="A1",
                members=(
                    KinematicRigidBodyMember(
                        member_instance_id="A1",
                        reference_to_member_home=CadRigidTransform(),
                    ),
                    KinematicRigidBodyMember(
                        member_instance_id="A2",
                        reference_to_member_home=member_offset,
                    ),
                ),
            ),
            KinematicRigidBody(
                body_id="B",
                reference_member_instance_id="B1",
                members=(
                    KinematicRigidBodyMember(
                        member_instance_id="B1",
                        reference_to_member_home=CadRigidTransform(),
                    ),
                    KinematicRigidBodyMember(
                        member_instance_id="B2",
                        reference_to_member_home=member_offset,
                    ),
                ),
            ),
        ),
        joints=(
            RevoluteJointModelV2(
                joint_id="J1",
                joint_kind=KinematicJointKind.REVOLUTE,
                parent_body_id="R",
                child_body_id="A",
            ),
            RevoluteJointModelV2(
                joint_id="J2",
                joint_kind=KinematicJointKind.REVOLUTE,
                parent_body_id="A",
                child_body_id="B",
            ),
        ),
    )
    return assembly, model


def _configuration(model, j1, j2):
    return JointConfiguration(
        model_id=model.model_id,
        positions={"J1": float(j1), "J2": float(j2)},
    )


def _transform_map(result):
    return {
        item.instance_id: item.transform for item in result.instance_world_transforms
    }


def _relative(first, second):
    return transform_compose(transform_inverse(first), second)


def _assert_neutral_pair_payload(record, schema_version):
    payload = record.model_dump(mode="json")
    assert payload["schema_version"] == schema_version
    assert "moving_instance_id" not in payload
    assert "stationary_instance_id" not in payload


@pytest.mark.skipif(
    not FREECAD_AVAILABLE,
    reason="FreeCAD not available through the repository discovery gate",
)
def test_live_grouped_body_freecad_acceptance(tmp_path, monkeypatch):
    discovery = discover_freecad()
    executable = (
        discovery.executable
        or os.environ.get("MECHCAD_FREECADCMD")
        or FREECAD_CANDIDATE
    )
    monkeypatch.setenv("MECHCAD_FREECADCMD", executable)
    runtime = discover_freecad().require_available()
    app = _application(tmp_path)
    source = app.load_state()
    assembly, model = _fixture()
    source_hash = assembly_hash(assembly)
    source_placements = {
        instance.instance_id: instance.placement for instance in assembly.instances
    }
    source_snapshot = tuple(
        (instance_id, placement.model_dump(mode="json"))
        for instance_id, placement in source_placements.items()
    )

    provider = app._kinematic_measurement_provider
    assert type(provider) is FreeCADTransientAssemblyMeasurementProvider
    assert provider.execute is None
    assert provider.execute_in_workspace is None
    assert type(provider.backend) is FreeCADBackend
    assert app.kinematic_measure.__func__ is FreeCADTransientAssemblyMeasurementProvider.exact_measure
    assert app._v2_kinematic_provider_snapshot().real_freecad is True
    backend_provenance = provider.provenance()
    assert backend_provenance.backend_name == "freecad"
    assert backend_provenance.library_name == "FreeCAD"
    assert backend_provenance.library_version == "1.1.3"

    q0 = _configuration(model, 0.0, 0.0)
    j1_only = _configuration(model, 15.0, 0.0)
    j2_only = _configuration(model, 0.0, 15.0)
    combined = _configuration(model, 15.0, 90.0)
    configurations = (q0, j1_only, j2_only, combined)
    fk_results = tuple(
        app.evaluate_multi_joint_configuration(
            source_revision=source.revision,
            source_state_hash=source.state_hash,
            assembly=assembly,
            model=model,
            configuration=configuration,
        )
        for configuration in configurations
    )

    q0_transforms = _transform_map(fk_results[0])
    assert set(q0_transforms) == {"R1", "R2", "A1", "A2", "B1", "B2"}
    assert all(
        rigid_transform_agrees(source_placements[instance_id], q0_transforms[instance_id])
        for instance_id in source_placements
    )
    assert any(
        source_placements[instance_id] != q0_transforms[instance_id]
        for instance_id in source_placements
    )
    assert fk_results[0].source_assembly_hash == source_hash
    assert fk_results[0].transformed_assembly_hash != source_hash

    transform_maps = tuple(_transform_map(result) for result in fk_results)
    zero, q1, q2, q12 = transform_maps
    for instance_id in ("R1", "R2"):
        assert rigid_transform_agrees(q1[instance_id], zero[instance_id])
        assert rigid_transform_agrees(q2[instance_id], zero[instance_id])
        assert rigid_transform_agrees(q12[instance_id], zero[instance_id])
    for instance_id in ("A1", "A2", "B1", "B2"):
        assert not rigid_transform_agrees(q1[instance_id], zero[instance_id])
    for instance_id in ("A1", "A2"):
        assert rigid_transform_agrees(q2[instance_id], zero[instance_id])
    for instance_id in ("B1", "B2"):
        assert not rigid_transform_agrees(q2[instance_id], zero[instance_id])
        assert not rigid_transform_agrees(q12[instance_id], zero[instance_id])
    for transforms in transform_maps:
        for first, second in (("R1", "R2"), ("A1", "A2"), ("B1", "B2")):
            assert rigid_transform_agrees(
                _relative(source_placements[first], source_placements[second]),
                _relative(transforms[first], transforms[second]),
            )

    exact_pair_scope = (
        ExactConstituentPair(first_instance_id="R1", second_instance_id="A1"),
        ExactConstituentPair(first_instance_id="A2", second_instance_id="B1"),
    )
    discrete = app.analyze_multi_joint_collision_sweep_v2(
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        assembly=assembly,
        model=model,
        configurations=configurations,
        exact_pair_scope=exact_pair_scope,
    )
    assert isinstance(discrete, MultiJointCollisionSweepResultV2)
    assert discrete.schema_version == "multi-joint-collision-sweep-result@2"
    assert discrete.evaluator_version == MULTI_JOINT_EXACT_COLLISION_SWEEP_V2_VERSION
    assert discrete.continuous_path_verified is False
    assert "moving_instance_id" not in discrete.model_dump(mode="json")
    assert "stationary_instance_id" not in discrete.model_dump(mode="json")
    expected_pairs = (("A1", "R1"), ("A2", "B1"))
    assert [item.configuration_index for item in discrete.configuration_results] == [0, 1, 2, 3]
    for configuration_result in discrete.configuration_results:
        assert isinstance(configuration_result, MultiJointCollisionConfigurationResultV2)
        assert configuration_result.schema_version == (
            "multi-joint-collision-configuration-result@2"
        )
        assert "moving_instance_id" not in configuration_result.model_dump(mode="json")
        assert "stationary_instance_id" not in configuration_result.model_dump(mode="json")
        assert tuple(
            (pair.first_instance_id, pair.second_instance_id)
            for pair in configuration_result.pair_results
        ) == expected_pairs
        assert len(configuration_result.pair_results) == 2
        assert all(
            math.isfinite(pair.interference_volume_mm3)
            and math.isfinite(pair.exact_distance_mm)
            for pair in configuration_result.pair_results
        )
        assert all(
            isinstance(pair, ExactConstituentPairResultV2)
            and pair.schema_version == "exact-constituent-pair-result@2"
            and "moving_instance_id" not in pair.model_dump(mode="json")
            and "stationary_instance_id" not in pair.model_dump(mode="json")
            for pair in configuration_result.pair_results
        )
    assert any(
        (pair.first_instance_id, pair.second_instance_id) == ("A2", "B1")
        for configuration_result in discrete.configuration_results
        for pair in configuration_result.pair_results
    )
    combined_a2_b1 = next(
        pair
        for pair in discrete.configuration_results[-1].pair_results
        if (pair.first_instance_id, pair.second_instance_id) == ("A2", "B1")
    )
    assert combined_a2_b1.classification in {
        CollisionClassification.INTERFERENCE,
        CollisionClassification.TOUCHING,
    }
    discrete_evidence = app.get_multi_joint_collision_sweep_evidence(discrete.result_hash)
    assert discrete_evidence is not None
    assert discrete_evidence.analysis_execution_provenance.provider_name == "freecad-transient-exact"
    assert discrete_evidence.analysis_execution_provenance.backend_provenance.backend_name == "freecad"

    clear_path = MultiJointPath(
        model_id=model.model_id,
        waypoints=(q0, _configuration(model, 1.0, 1.0)),
    )
    clear = app.prove_continuous_multi_joint_path_clearance_v2(
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        assembly=assembly,
        model=model,
        path=clear_path,
        exact_pair_scope=exact_pair_scope,
        max_depth=0,
        max_exact_evaluations=10,
    )
    assert isinstance(clear, MultiJointContinuousClearanceProofResultV2)
    assert clear.status is MultiJointContinuousProofStatus.VERIFIED_CLEAR
    assert clear.continuous_path_verified is True
    assert clear.schema_version == "multi-joint-continuous-clearance-proof-result@2"
    assert clear.proof_algorithm_version == "conservative-multi-joint-path-clearance-proof@1.0"
    assert clear.reach_bound_algorithm_version == BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION
    assert "moving_instance_id" not in clear.model_dump(mode="json")
    assert "stationary_instance_id" not in clear.model_dump(mode="json")
    assert all(isinstance(item, ContinuousSegmentResultV2) for item in clear.segment_results)
    assert all(
        item.schema_version == "continuous-segment-result@2"
        for item in clear.segment_results
    )
    assert all(
        isinstance(evaluation, ContinuousExactEvaluationV2)
        and evaluation.schema_version == "continuous-exact-evaluation@2"
        for evaluation in clear.exact_evaluations
    )
    assert all(
        isinstance(pair, ContinuousExactPairResultV2)
        for evaluation in clear.exact_evaluations
        for pair in evaluation.pair_results
    )
    for evaluation in clear.exact_evaluations:
        for pair in evaluation.pair_results:
            _assert_neutral_pair_payload(pair, "continuous-exact-pair-result@2")
    for interval in clear.certified_leaf_certificates:
        assert isinstance(interval, ContinuousIntervalCertificateV2)
        assert interval.schema_version == "continuous-interval-certificate@2"
        assert interval.reach_bound_algorithm_version == BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION
        for pair in interval.pair_certificates:
            assert isinstance(pair, ContinuousPairCertificateV2)
            _assert_neutral_pair_payload(pair, "continuous-pair-certificate@2")
    assert all(
        tuple((pair.first_instance_id, pair.second_instance_id) for pair in evaluation.pair_results)
        == expected_pairs
        for evaluation in clear.exact_evaluations
    )

    witness_path = MultiJointPath(
        model_id=model.model_id,
        waypoints=(q0, _configuration(model, 15.0, 90.0)),
    )
    witness = app.prove_continuous_multi_joint_path_clearance_v2(
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        assembly=assembly,
        model=model,
        path=witness_path,
        exact_pair_scope=exact_pair_scope,
        max_depth=0,
        max_exact_evaluations=10,
    )
    assert isinstance(witness, MultiJointContinuousClearanceProofResultV2)
    assert witness.status is MultiJointContinuousProofStatus.COLLISION_WITNESS
    assert witness.continuous_path_verified is False
    assert witness.schema_version == "multi-joint-continuous-clearance-proof-result@2"
    assert witness.proof_algorithm_version == clear.proof_algorithm_version
    assert witness.reach_bound_algorithm_version == clear.reach_bound_algorithm_version
    assert witness.collision_witness is not None
    assert isinstance(witness.collision_witness, MultiJointContinuousCollisionWitnessV2)
    assert witness.collision_witness.schema_version == (
        "multi-joint-continuous-collision-witness@2"
    )
    assert "moving_instance_id" not in witness.model_dump(mode="json")
    assert "stationary_instance_id" not in witness.model_dump(mode="json")
    _assert_neutral_pair_payload(
        witness.collision_witness,
        "multi-joint-continuous-collision-witness@2",
    )
    assert all(isinstance(item, ContinuousSegmentResultV2) for item in witness.segment_results)
    assert all(
        isinstance(evaluation, ContinuousExactEvaluationV2)
        and evaluation.schema_version == "continuous-exact-evaluation@2"
        for evaluation in witness.exact_evaluations
    )
    for evaluation in witness.exact_evaluations:
        for pair in evaluation.pair_results:
            _assert_neutral_pair_payload(pair, "continuous-exact-pair-result@2")
    assert witness.collision_witness.first_instance_id == "A2"
    assert witness.collision_witness.second_instance_id == "B1"
    assert witness.collision_witness.classification in {
        CollisionClassification.INTERFERENCE,
        CollisionClassification.TOUCHING,
    }
    witness_evidence = app.get_multi_joint_continuous_proof_evidence(witness.result_hash)
    assert witness_evidence is not None
    assert witness_evidence.continuous_proof_execution_provenance.provider_name == "freecad-transient-exact"
    assert witness_evidence.continuous_proof_execution_provenance.backend_provenance.backend_name == "freecad"

    assert assembly_hash(assembly) == source_hash
    assert source_snapshot == tuple(
        (instance_id, placement.model_dump(mode="json"))
        for instance_id, placement in source_placements.items()
    )
    state_after = app.load_state()
    assert state_after.revision == source.revision
    assert state_after.state_hash == source.state_hash
    print(
        "M13_3P_T14_LIVE="
        + json.dumps(
            {
                "runtime": {
                    "executable": runtime.executable,
                    "version": runtime.version,
                    "backend_version": backend_provenance.library_version,
                    "execution_mode": runtime.execution_boundary,
                },
                "source_assembly_hash": source_hash,
                "model_id": model.model_id,
                "discrete_result_hash": discrete.result_hash,
                "clear_result_hash": clear.result_hash,
                "witness_result_hash": witness.result_hash,
                "witness_pair": [
                    witness.collision_witness.first_instance_id,
                    witness.collision_witness.second_instance_id,
                ],
            },
            sort_keys=True,
        )
    )
