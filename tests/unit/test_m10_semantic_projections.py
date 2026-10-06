from __future__ import annotations

import pytest

import mechcad_harness.cad_assembly as cad_assembly
import mechcad_harness.continuous_proof as continuous_proof
import mechcad_harness.kinematic_sweep as kinematic_sweep
from mechcad_harness.candidates.multi_joint_m10_bridge import (
    MultiJointCollisionPairEntry,
    multi_joint_collision_pair_inventory_hash_v2,
)
from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.continuous_proof import (
    ContinuousIntervalCertificate,
    ContinuousPairCertificate,
    ContinuousSingleAxisProofRequest,
    ContinuousSingleAxisProofResult,
    ContinuousSingleAxisProofStatus,
)
from mechcad_harness.kinematic_sweep import (
    CadKinematicCollisionPairResult,
    CadKinematicSweepRequest,
    CadKinematicSweepResult,
    CadKinematicSweepSample,
    CollisionClassification,
    SweepAggregateClassification,
    RevoluteAxis,
)
from mechcad_harness.multi_joint_collision_sweep import (
    ExactConstituentPairResultV2,
    MultiJointCollisionConfigurationResultV2,
    MultiJointCollisionSweepRequestV2,
    MultiJointCollisionSweepResultV2,
    multi_joint_collision_sweep_result_v2_hash,
)
from mechcad_harness.multi_joint_kinematics import (
    EvaluatedJointState,
    InstanceWorldTransform,
    JointConfiguration,
    KinematicModel,
    KinematicModelV2,
    KinematicRigidBody,
    KinematicRigidBodyMember,
    KinematicJointKind,
    RevoluteJointModel,
    RevoluteJointModelV2,
    joint_configuration_hash,
    kinematic_model_hash,
)
from mechcad_harness.multi_joint_pair_scope import ExactConstituentPair
from mechcad_harness.models.physical_pair_policy import PhysicalPairClassification
from mechcad_harness.semantic_m10_kinematics import (
    semantic_kinematic_model_hash,
    semantic_m10_v2_request_hash,
    semantic_m10_v2_result_hash,
    semantic_single_joint_kinematic_model_hash,
)


_PART = CadPartProgram(
    part_id="link",
    operations=(
        BasePlateOperation(
            operation_id="plate", length_mm=10, width_mm=10, thickness_mm=2
        ),
    ),
)


def _assembly(assembly_id: str = "assembly-a") -> CadAssemblyProgram:
    return CadAssemblyProgram(
        assembly_id=assembly_id,
        parts=(_PART,),
        instances=(
            CadComponentInstance(instance_id="base", part_id="link"),
            CadComponentInstance(
                instance_id="moving", part_id="link", placement=CadRigidTransform(x_mm=20)
            ),
        ),
    )


def _axis(**changes) -> RevoluteAxis:
    values = dict(
        origin_x_mm=0.0,
        origin_y_mm=0.0,
        origin_z_mm=0.0,
        direction_x=0.0,
        direction_y=0.0,
        direction_z=1.0,
        frame_id="world",
    )
    values.update(changes)
    return RevoluteAxis(**values)


def _proof_request(assembly: CadAssemblyProgram, **changes):
    values = dict(
        source_assembly_id=assembly.assembly_id,
        source_assembly_hash=assembly_hash(assembly),
        axis=_axis(),
        start_angle_deg=0.0,
        end_angle_deg=90.0,
        moving_instance_ids=("moving",),
        stationary_instance_ids=("base",),
        required_clearance_mm=1.0,
    )
    values.update(changes)
    return ContinuousSingleAxisProofRequest(**values)


def _proof_result(request: ContinuousSingleAxisProofRequest):
    interval = ContinuousIntervalCertificate(
        interval_start_deg=request.start_angle_deg,
        interval_end_deg=request.end_angle_deg,
        reference_angle_deg=45.0,
        pair_certificates=(
            ContinuousPairCertificate(
                moving_instance_id="moving",
                stationary_instance_id="base",
                exact_distance_mm=5.0,
                radial_bound_mm=20.0,
                angular_motion_bound_mm=1.0,
                certified_lower_clearance_mm=4.0,
            ),
        ),
        minimum_certified_lower_clearance_mm=4.0,
    )
    return ContinuousSingleAxisProofResult(
        request_hash=request.request_hash,
        source_assembly_hash=request.source_assembly_hash,
        proof_algorithm_version="conservative-single-axis-clearance-proof@1.0",
        axis=request.axis,
        start_angle_deg=request.start_angle_deg,
        end_angle_deg=request.end_angle_deg,
        moving_instance_ids=request.moving_instance_ids,
        stationary_instance_ids=request.stationary_instance_ids,
        required_clearance_mm=request.required_clearance_mm,
        proof_guard_mm=request.proof_guard_mm,
        status=ContinuousSingleAxisProofStatus.VERIFIED_CLEAR,
        certified_leaf_certificates=(interval,),
        exact_evaluations_count=1,
        maximum_depth_reached=0,
        result_hash="sha256:legacy-proof-hash",
    )


def _sweep_request(assembly: CadAssemblyProgram, **changes):
    values = dict(
        source_assembly_id=assembly.assembly_id,
        source_assembly_hash=assembly_hash(assembly),
        axis=_axis(),
        sample_angles_deg=(0.0, 45.0, 90.0),
        moving_instance_ids=("moving",),
        stationary_instance_ids=("base",),
    )
    values.update(changes)
    return CadKinematicSweepRequest(**values)


def _sweep_result(request: CadKinematicSweepRequest, *, transformed_hash="sha256:transformed-a"):
    pair = CadKinematicCollisionPairResult(
        moving_instance_id="moving",
        stationary_instance_id="base",
        interference_volume_mm3=0.0,
        exact_distance_mm=3.0,
        classification=CollisionClassification.POSITIVE_CLEARANCE,
    )
    samples = tuple(
        CadKinematicSweepSample(
            angle_deg=angle,
            transformed_assembly_hash=f"{transformed_hash}:{angle}",
            pair_results=(pair,),
            maximum_interference_volume_mm3=0.0,
            minimum_exact_distance_mm=3.0,
            classification=CollisionClassification.POSITIVE_CLEARANCE,
        )
        for angle in request.sample_angles_deg
    )
    return CadKinematicSweepResult(
        request_hash=request.request_hash,
        source_assembly_hash=request.source_assembly_hash,
        samples=samples,
        aggregate_classification=SweepAggregateClassification.COLLISION_FREE,
        worst_interference_volume_mm3=0.0,
        minimum_clearance_angle_deg=0.0,
        minimum_clearance_mm=3.0,
        result_hash="sha256:legacy-sweep-hash",
    )


def _v2_model(*, axis_direction=(0.0, 0.0, 1.0), evaluator_version="multi-joint-forward-kinematics@2.0"):
    return KinematicModelV2(
        model_id="model-v2",
        evaluator_version=evaluator_version,
        bodies=(
            KinematicRigidBody(
                body_id="base-body",
                reference_member_instance_id="base",
                members=(
                    KinematicRigidBodyMember(
                        member_instance_id="base",
                        reference_to_member_home=CadRigidTransform(),
                    ),
                ),
            ),
            KinematicRigidBody(
                body_id="moving-body",
                reference_member_instance_id="moving",
                members=(
                    KinematicRigidBodyMember(
                        member_instance_id="moving",
                        reference_to_member_home=CadRigidTransform(),
                    ),
                ),
            ),
        ),
        joints=(
            RevoluteJointModelV2(
                joint_id="joint",
                joint_kind=KinematicJointKind.REVOLUTE,
                parent_body_id="base-body",
                child_body_id="moving-body",
                axis_direction_x=axis_direction[0],
                axis_direction_y=axis_direction[1],
                axis_direction_z=axis_direction[2],
            ),
        ),
    )


def _v2_request(assembly: CadAssemblyProgram, *, model=None, configurations=None, evaluator_version="multi-joint-exact-collision-sweep@2.0"):
    model = model or _v2_model()
    values = dict(
        schema_version="multi-joint-collision-sweep-request@2",
        source_assembly_id=assembly.assembly_id,
        source_assembly_hash=assembly_hash(assembly),
        model=model,
        configurations=configurations or (
            JointConfiguration(model_id=model.model_id, positions={"joint": 0.0}),
            JointConfiguration(model_id=model.model_id, positions={"joint": 45.0}),
        ),
        exact_pair_scope=(ExactConstituentPair(first_instance_id="moving", second_instance_id="base"),),
        evaluator_version=evaluator_version,
    )
    return MultiJointCollisionSweepRequestV2(**values)


def _v2_result(request: MultiJointCollisionSweepRequestV2, *, transformed_hash="sha256:transformed-a"):
    configuration_results = tuple(
        MultiJointCollisionConfigurationResultV2(
            schema_version="multi-joint-collision-configuration-result@2",
            configuration_index=index,
            configuration_hash=joint_configuration_hash(request.configurations[index]),
            transformed_assembly_hash=f"{transformed_hash}:{index}",
            ordered_joint_states=(
                EvaluatedJointState(
                    joint_id="joint", joint_position_deg=float(index), within_limits=True
                ),
            ),
            instance_world_transforms=(
                InstanceWorldTransform(
                    instance_id="moving",
                    is_articulated=True,
                    transform=CadRigidTransform(x_mm=20),
                ),
            ),
            pair_results=(
                ExactConstituentPairResultV2(
                    schema_version="exact-constituent-pair-result@2",
                    first_instance_id="base",
                    second_instance_id="moving",
                    interference_volume_mm3=0.0,
                    exact_distance_mm=3.0,
                    classification=CollisionClassification.POSITIVE_CLEARANCE,
                ),
            ),
            classification=CollisionClassification.POSITIVE_CLEARANCE,
            any_interference=False,
            any_touching=False,
            all_positive_clearance=True,
            minimum_exact_distance_mm=3.0,
        )
        for index, _ in enumerate(request.configurations)
    )
    result = MultiJointCollisionSweepResultV2(
        schema_version="multi-joint-collision-sweep-result@2",
        evaluator_version="multi-joint-exact-collision-sweep@2.0",
        source_assembly_hash=request.source_assembly_hash,
        model_hash=request.model_hash,
        request_hash=request.request_hash,
        configuration_results=configuration_results,
        any_interference=False,
        any_touching=False,
        all_positive_clearance=True,
        collision_configuration_indices=(),
        minimum_exact_distance_mm=3.0,
        minimum_distance_configuration_index=0,
    )
    return result.model_copy(
        update={"result_hash": multi_joint_collision_sweep_result_v2_hash(result)}
    )


def test_semantic_assembly_projection_reconstructs_and_dual_checks_raw_hash():
    assembly = _assembly()
    assert cad_assembly.verified_semantic_assembly_hash(
        assembly, (), assembly_hash(assembly)
    ).startswith("sha256:")
    with pytest.raises(ValueError, match="source assembly hash"):
        cad_assembly.verified_semantic_assembly_hash(assembly, (), "sha256:wrong")


def test_p1_p2_are_invariant_to_raw_assembly_identity_but_keep_engineering_inputs():
    first, second = _assembly("assembly-a"), _assembly("assembly-b")
    first_request, second_request = _proof_request(first), _proof_request(second)
    assert first_request.request_hash != second_request.request_hash
    first_assembly_hash = cad_assembly.verified_semantic_assembly_hash(first, (), first_request.source_assembly_hash)
    second_assembly_hash = cad_assembly.verified_semantic_assembly_hash(second, (), second_request.source_assembly_hash)
    assert first_assembly_hash == second_assembly_hash
    assert continuous_proof.semantic_proof_request_hash(first_request, first, ()) == continuous_proof.semantic_proof_request_hash(second_request, second, ())
    assert continuous_proof.semantic_proof_request_hash(
        _proof_request(first, required_clearance_mm=2.0), first, ()
    ) != continuous_proof.semantic_proof_request_hash(first_request, first, ())

    first_result, second_result = _proof_result(first_request), _proof_result(second_request)
    assert continuous_proof.semantic_proof_result_hash(first_result, first_request, first, ()) == continuous_proof.semantic_proof_result_hash(
        second_result, second_request, second, ()
    )
    assert continuous_proof.semantic_proof_result_hash(
        first_result.model_copy(update={"result_hash": "sha256:changed-self-hash"}),
        first_request,
        first,
        (),
    ) == continuous_proof.semantic_proof_result_hash(first_result, first_request, first, ())


def test_p3_p4_project_ordered_samples_and_exclude_transformed_hashes():
    first, second = _assembly("assembly-a"), _assembly("assembly-b")
    first_request, second_request = _sweep_request(first), _sweep_request(second)
    assert first_request.request_hash != second_request.request_hash
    assert kinematic_sweep.semantic_sweep_request_hash(first_request, first, ()) == kinematic_sweep.semantic_sweep_request_hash(
        second_request, second, ()
    )
    assert kinematic_sweep.semantic_sweep_request_hash(
        _sweep_request(first, sample_angles_deg=(0.0, 90.0, 45.0)), first, ()
    ) != kinematic_sweep.semantic_sweep_request_hash(first_request, first, ())

    first_result = _sweep_result(first_request)
    second_result = _sweep_result(second_request, transformed_hash="sha256:transformed-b")
    assert kinematic_sweep.semantic_sweep_result_hash(first_result, first_request, first, ()) == kinematic_sweep.semantic_sweep_result_hash(
        second_result, second_request, second, ()
    )
    changed = first_result.model_copy(
        update={"result_hash": "sha256:changed-self-hash"}
    )
    assert kinematic_sweep.semantic_sweep_result_hash(changed, first_request, first, ()) == kinematic_sweep.semantic_sweep_result_hash(
        first_result, first_request, first, ()
    )


def test_f1_and_f3_model_hashes_exclude_evaluator_but_include_engineering_fields():
    legacy = KinematicModel(
        model_id="single",
        joints=(
            RevoluteJointModel(
                joint_id="joint",
                parent_instance_id="base",
                child_instance_id="moving",
            ),
        ),
    )
    legacy_other_evaluator = legacy.model_copy(
        update={"evaluator_version": "multi-joint-forward-kinematics@other"}
    )
    assert kinematic_model_hash(legacy) != kinematic_model_hash(legacy_other_evaluator)
    assert semantic_single_joint_kinematic_model_hash(legacy) == semantic_single_joint_kinematic_model_hash(
        legacy_other_evaluator
    )
    changed_joint = legacy.model_copy(
        update={"joints": (legacy.joints[0].model_copy(update={"axis_direction_x": 1.0}),)}
    )
    assert semantic_single_joint_kinematic_model_hash(changed_joint) != semantic_single_joint_kinematic_model_hash(legacy)

    model = _v2_model()
    other_evaluator = model.model_copy(
        update={"evaluator_version": "multi-joint-forward-kinematics@other"}
    )
    assert semantic_kinematic_model_hash(model) == semantic_kinematic_model_hash(other_evaluator)
    changed_axis = _v2_model(axis_direction=(1.0, 0.0, 0.0))
    assert semantic_kinematic_model_hash(changed_axis) != semantic_kinematic_model_hash(model)


def test_p5_p6_are_semantic_and_preserve_configuration_order():
    first, second = _assembly("assembly-a"), _assembly("assembly-b")
    first_request, second_request = _v2_request(first), _v2_request(second)
    assert first_request.request_hash != second_request.request_hash
    assert semantic_m10_v2_request_hash(first_request, first, ()) == semantic_m10_v2_request_hash(
        second_request, second, ()
    )
    reversed_request = _v2_request(
        first,
        configurations=tuple(reversed(first_request.configurations)),
    )
    assert semantic_m10_v2_request_hash(reversed_request, first, ()) != semantic_m10_v2_request_hash(
        first_request, first, ()
    )
    changed_model = _v2_model(axis_direction=(1.0, 0.0, 0.0))
    assert semantic_m10_v2_request_hash(
        _v2_request(first, model=changed_model), first, ()
    ) != semantic_m10_v2_request_hash(first_request, first, ())

    first_result = _v2_result(first_request)
    second_result = _v2_result(second_request, transformed_hash="sha256:other-transform")
    assert semantic_m10_v2_result_hash(first_result, first_request, first, ()) == semantic_m10_v2_result_hash(
        second_result, second_request, second, ()
    )
    tampered_transform = first_result.model_copy(
        update={
            "configuration_results": tuple(
                item.model_copy(update={"transformed_assembly_hash": "sha256:tampered"})
                for item in first_result.configuration_results
            )
        }
    )
    assert semantic_m10_v2_result_hash(tampered_transform, first_request, first, ()) == semantic_m10_v2_result_hash(
        first_result, first_request, first, ()
    )

    evaluator_request = first_request.model_copy(
        update={"evaluator_version": "multi-joint-exact-collision-sweep@other"}
    )
    assert semantic_m10_v2_request_hash(
        evaluator_request, first, ()
    ) == semantic_m10_v2_request_hash(first_request, first, ())
    evaluator_result = first_result.model_copy(
        update={"evaluator_version": "multi-joint-exact-collision-sweep@other"}
    )
    assert semantic_m10_v2_result_hash(
        evaluator_result, first_request, first, ()
    ) == semantic_m10_v2_result_hash(first_result, first_request, first, ())


def test_semantic_projections_fail_closed_on_wrong_source_replay_binding():
    assembly = _assembly()
    proof_request = _proof_request(assembly)
    proof_result = _proof_result(proof_request)
    sweep_request = _sweep_request(assembly)
    sweep_result = _sweep_result(sweep_request)
    m10_request = _v2_request(assembly)
    m10_result = _v2_result(m10_request)
    with pytest.raises(ValueError, match="source assembly hash"):
        continuous_proof.semantic_proof_request_hash(
            proof_request.model_copy(update={"source_assembly_hash": "sha256:wrong"}),
            assembly,
            (),
        )
    with pytest.raises(ValueError, match="source assembly hash"):
        continuous_proof.semantic_proof_result_hash(
            proof_result.model_copy(update={"source_assembly_hash": "sha256:wrong"}),
            proof_request,
            assembly,
            (),
        )
    with pytest.raises(ValueError, match="source assembly hash"):
        kinematic_sweep.semantic_sweep_request_hash(
            sweep_request.model_copy(update={"source_assembly_hash": "sha256:wrong"}),
            assembly,
            (),
        )
    with pytest.raises(ValueError, match="source assembly hash"):
        kinematic_sweep.semantic_sweep_result_hash(
            sweep_result.model_copy(update={"source_assembly_hash": "sha256:wrong"}),
            sweep_request,
            assembly,
            (),
        )
    with pytest.raises(ValueError, match="source assembly hash"):
        semantic_m10_v2_request_hash(
            m10_request.model_copy(update={"source_assembly_hash": "sha256:wrong"}),
            assembly,
            (),
        )
    with pytest.raises(ValueError, match="source assembly hash"):
        semantic_m10_v2_result_hash(
            m10_result.model_copy(update={"source_assembly_hash": "sha256:wrong"}),
            m10_request,
            assembly,
            (),
        )


def test_f6_inventory_projection_uses_semantic_model_reference_and_exact_entries():
    entry = MultiJointCollisionPairEntry(
        first_instance_id="base",
        second_instance_id="moving",
        classification=PhysicalPairClassification.CHECK_CLEARANCE,
    )
    common = dict(
        physical_mechanism_hash="sha256:" + "1" * 64,
        physical_body_binding_hashes=("sha256:" + "2" * 64,),
        cad_realization_hash="sha256:" + "3" * 64,
        complete_concrete_instance_ids=("base", "moving"),
        expected_pair_universe=(("base", "moving"),),
        entries=(entry,),
    )
    first = multi_joint_collision_pair_inventory_hash_v2(
        **common, semantic_kinematic_model_hash="sha256:" + "4" * 64
    )
    same = multi_joint_collision_pair_inventory_hash_v2(
        **common, semantic_kinematic_model_hash="sha256:" + "4" * 64
    )
    changed_model = multi_joint_collision_pair_inventory_hash_v2(
        **common, semantic_kinematic_model_hash="sha256:" + "5" * 64
    )
    assert first == same
    assert first != changed_model
    with pytest.raises(ValueError, match="pair universe"):
        multi_joint_collision_pair_inventory_hash_v2(
            **(common | {"expected_pair_universe": ()}),
            semantic_kinematic_model_hash="sha256:" + "4" * 64,
        )


def test_semantic_projections_reject_unknown_declared_fields():
    class ExtendedSweepRequest(CadKinematicSweepRequest):
        unclassified_value: str

    assembly = _assembly()
    request = ExtendedSweepRequest(
        **_sweep_request(assembly).model_dump(exclude={"request_hash"}),
        unclassified_value="not-classified",
    )
    with pytest.raises((TypeError, ValueError), match="field|schema|type|unclassified"):
        kinematic_sweep.semantic_sweep_request_hash(request, assembly, ())


def test_m10_projection_declared_field_counts_are_pinned():
    assembly = _assembly()
    assert set(ContinuousSingleAxisProofRequest.model_fields) == {
        "source_assembly_id", "source_assembly_hash", "axis", "start_angle_deg",
        "end_angle_deg", "moving_instance_ids", "stationary_instance_ids",
        "required_clearance_mm", "volume_tolerance_mm3", "distance_tolerance_mm",
        "proof_guard_mm", "max_depth", "minimum_interval_deg",
        "max_exact_evaluations", "sweep_version", "request_hash",
    }
    assert set(ContinuousSingleAxisProofResult.model_fields) == {
        "request_hash", "source_assembly_hash", "proof_algorithm_version", "axis",
        "start_angle_deg", "end_angle_deg", "moving_instance_ids",
        "stationary_instance_ids", "required_clearance_mm", "proof_guard_mm",
        "status", "certified_leaf_certificates", "unresolved_intervals",
        "collision_witness", "exact_evaluations_count", "maximum_depth_reached",
        "result_hash",
    }
    assert set(CadKinematicSweepRequest.model_fields) == {
        "source_assembly_id", "source_assembly_hash", "axis", "sample_angles_deg",
        "moving_instance_ids", "stationary_instance_ids", "volume_tolerance_mm3",
        "distance_tolerance_mm", "sweep_version", "request_hash",
    }
    assert set(CadKinematicSweepResult.model_fields) == {
        "request_hash", "source_assembly_hash", "sweep_version", "samples",
        "aggregate_classification", "first_collision_angle_deg",
        "worst_interference_angle_deg", "worst_interference_volume_mm3",
        "minimum_clearance_angle_deg", "minimum_clearance_mm",
        "continuous_sweep_verified", "result_hash",
    }
    assert set(MultiJointCollisionSweepRequestV2.model_fields) == {
        "schema_version", "source_assembly_id", "source_assembly_hash", "model",
        "configurations", "exact_pair_scope", "volume_tolerance_mm3",
        "distance_tolerance_mm", "evaluator_version", "model_hash", "request_hash",
    }
    assert set(MultiJointCollisionSweepResultV2.model_fields) == {
        "schema_version", "evaluator_version", "source_assembly_hash", "model_hash",
        "request_hash", "configuration_results", "any_interference", "any_touching",
        "all_positive_clearance", "collision_configuration_indices",
        "minimum_exact_distance_mm", "minimum_distance_configuration_index",
        "continuous_path_verified", "result_hash",
    }
    assert len(ContinuousSingleAxisProofRequest.model_fields) == 16
    assert len(ContinuousSingleAxisProofResult.model_fields) == 17
    assert len(CadKinematicSweepRequest.model_fields) == 10
    assert len(CadKinematicSweepResult.model_fields) == 12
    assert len(MultiJointCollisionSweepRequestV2.model_fields) == 11
    assert len(MultiJointCollisionSweepResultV2.model_fields) == 14
    assert len(MultiJointCollisionConfigurationResultV2.model_fields) == 12
    assert len(ExactConstituentPairResultV2.model_fields) == 6
    assert len(KinematicModelV2.model_fields) == 6
    assert len(KinematicModel.model_fields) == 4
    assert len(KinematicRigidBody.model_fields) == 5
    assert len(KinematicRigidBodyMember.model_fields) == 2
    assert len(CadRigidTransform.model_fields) == 4
    assert len(RevoluteJointModelV2.model_fields) == 13
    assert len(RevoluteJointModel.model_fields) == 13
    assert len(ExactConstituentPair.model_fields) == 3
    assert len(CadKinematicSweepSample.model_fields) == 6
    assert len(CadKinematicCollisionPairResult.model_fields) == 5
    assert len(EvaluatedJointState.model_fields) == 3
    assert len(InstanceWorldTransform.model_fields) == 3
    assert len(MultiJointCollisionPairEntry.model_fields) == 5
    assert assembly_hash(assembly).startswith("sha256:")
