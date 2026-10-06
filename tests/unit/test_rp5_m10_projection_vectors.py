from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from test_m10_semantic_projections import (
    _assembly,
    _v2_model,
    _v2_request,
    _v2_result,
)
from mechcad_harness.cad_assembly import CadRigidTransform, assembly_hash
from mechcad_harness.candidates.cad_realization import semantic_assembly_hash
from mechcad_harness.multi_joint_collision_sweep import (
    CadKinematicCollisionPairResult,
    EvaluatedJointState,
    ExactConstituentPairResultV2,
    InstanceWorldTransform,
    JointConfiguration,
    MultiJointCollisionConfigurationResultV2,
    MultiJointCollisionConfigurationResult,
    MultiJointCollisionSweepRequest,
    MultiJointCollisionSweepResult,
    MultiJointCollisionSweepRequestV2,
    MultiJointCollisionSweepResultV2,
)
from mechcad_harness.multi_joint_kinematics import (
    KinematicJointKind,
    KinematicModel,
    KinematicModelV2,
    KinematicRigidBody,
    KinematicRigidBodyMember,
    RevoluteJointModel,
    RevoluteJointModelV2,
    joint_configuration_hash,
)
from mechcad_harness.multi_joint_pair_scope import ExactConstituentPair
from mechcad_harness.kinematic_sweep import CollisionClassification
from mechcad_harness.semantic_m10_kinematics import (
    semantic_kinematic_model_hash,
    semantic_m10_v2_request_hash,
    semantic_m10_v2_result_hash,
    semantic_single_joint_kinematic_model_hash,
)


# These payloads are hand-expanded from accepted Spec DE17C360 §§10, 12A/F1,
# 12A/F3, and 12B/P5/P6. Their literal digests below were derived by applying
# the accepted canonical-JSON/SHA-256 rule to these payloads, without calling
# any of the four projection functions under test.
_IDENTITY = {
    "x_mm": 0.0,
    "y_mm": 0.0,
    "z_mm": 0.0,
    "rotation_quaternion": [1.0, 0.0, 0.0, 0.0],
}
_F1_PAYLOAD = {
    "semantic_projection_version": "m10-execution-semantics@1",
    "model_contract": "kinematic-model@2",
    "model_id": "model-v2",
    "bodies": [
        {
            "schema_version": "kinematic-rigid-body@1",
            "body_id": "base-body",
            "reference_member_instance_id": "base",
            "members": [
                {
                    "member_instance_id": "base",
                    "reference_to_member_home": _IDENTITY,
                }
            ],
        },
        {
            "schema_version": "kinematic-rigid-body@1",
            "body_id": "moving-body",
            "reference_member_instance_id": "moving",
            "members": [
                {
                    "member_instance_id": "moving",
                    "reference_to_member_home": _IDENTITY,
                }
            ],
        },
    ],
    "joints": [
        {
            "schema_version": "revolute-joint-model@2",
            "joint_id": "joint",
            "joint_kind": "revolute",
            "parent_body_id": "base-body",
            "child_body_id": "moving-body",
            "axis_origin_x_mm": 0.0,
            "axis_origin_y_mm": 0.0,
            "axis_origin_z_mm": 0.0,
            "axis_direction_x": 0.0,
            "axis_direction_y": 0.0,
            "axis_direction_z": 1.0,
            "min_angle_deg": None,
            "max_angle_deg": None,
        }
    ],
    "transform_agreement_version": "rigid-transform-agreement@1.0",
}
_F1_DIGEST = "sha256:05e4fe064b4458ee096fa0758fdd4d2b45b75b609525955aacdb559fb1b41a78"

_F3_PAYLOAD = {
    "semantic_projection_version": "m10-execution-semantics@1",
    "model_contract": "kinematic-model@1",
    "model_id": "single",
    "joints": [
        {
            "schema_version": "revolute-joint-model@1",
            "joint_id": "joint",
            "joint_kind": "revolute",
            "parent_instance_id": "base",
            "child_instance_id": "moving",
            "axis_origin_x_mm": 0.0,
            "axis_origin_y_mm": 0.0,
            "axis_origin_z_mm": 0.0,
            "axis_direction_x": 0.0,
            "axis_direction_y": 0.0,
            "axis_direction_z": 1.0,
            "min_angle_deg": None,
            "max_angle_deg": None,
        }
    ],
}
_F3_DIGEST = "sha256:0db39969b526ec6cac7531f328bc1c5b6782a901689ea2df878efb00b335bd76"

_PART_PROGRAM_PAYLOAD = {
    "part_id": "link",
    "operations": [
        {
            "operation_id": "plate",
            "operation_type": "base_plate",
            "length_mm": 10.0,
            "width_mm": 10.0,
            "thickness_mm": 2.0,
        }
    ],
    "coordinate_system": "lower-left-bottom; +X length, +Y width, +Z thickness",
}
_PART_PROGRAM_DIGEST = "sha256:ad0945dd5893d884a8a91426484de65b8d3ff6fa392489f5e588895099759f8a"
_SEMANTIC_ASSEMBLY_PAYLOAD = {
    "parts": [{"part_id": "link", "program_hash": _PART_PROGRAM_DIGEST}],
    "trusted_sources": [],
    "instances": [
        {"instance_id": "base", "part_slot_ref": "link", "placement": _IDENTITY},
        {
            "instance_id": "moving",
            "part_slot_ref": "link",
            "placement": {
                "x_mm": 20.0,
                "y_mm": 0.0,
                "z_mm": 0.0,
                "rotation_quaternion": [1.0, 0.0, 0.0, 0.0],
            },
        },
    ],
}
_SEMANTIC_ASSEMBLY_DIGEST = "sha256:1a0e2d6ab4dc49597b46b23bffdc269426e43eac12b4f8c2f627ea722314c8d5"

_CONFIGURATION_PAYLOADS = [
    {"model_id": "model-v2", "positions": [["joint", 0.0]]},
    {"model_id": "model-v2", "positions": [["joint", 45.0]]},
]
_CONFIGURATION_DIGESTS = [
    "sha256:90033cfd665cb11cb21ae79f18147c0c124dba7a4fcb638350fc260d85d88901",
    "sha256:f56ca341850ee5fbd596b21b2fd4c824c83318911b9ea52537a33571118ffd80",
]
_PAIR_SCOPE_PAYLOAD = {
    "exact_pair_scope_version": "exact-constituent-pair-scope@1.0",
    "pairs": [
        {
            "schema_version": "exact-constituent-pair@1",
            "first_instance_id": "base",
            "second_instance_id": "moving",
        }
    ],
}
_PAIR_SCOPE_DIGEST = "sha256:213a2984bc3ca06c9e6c707938a774b18f6b4ba604847c3b092c0398b5558007"
_P5_PAYLOAD = {
    "semantic_projection_version": "m10-execution-semantics@1",
    "request_contract": "multi-joint-collision-sweep-request@2",
    "semantic_kinematic_model_hash": _F1_DIGEST,
    "configuration_hashes": _CONFIGURATION_DIGESTS,
    "exact_pair_scope_hash": _PAIR_SCOPE_DIGEST,
    "exact_pair_scope_version": "exact-constituent-pair-scope@1.0",
    "volume_tolerance_mm3": 1e-9,
    "distance_tolerance_mm": 1e-7,
    "semantic_assembly_hash": _SEMANTIC_ASSEMBLY_DIGEST,
}
_P5_DIGEST = "sha256:2eefb88398c7a3e5e0b4f841a3df8e68e332b71ac04982c438cd8067af6c40fb"
_P6_PAYLOAD = {
    "semantic_projection_version": "m10-execution-semantics@1",
    "result_contract": "multi-joint-collision-sweep-result@2",
    "semantic_m10_v2_request_hash": _P5_DIGEST,
    "semantic_kinematic_model_hash": _F1_DIGEST,
    "configuration_semantic_results": [
        {
            "schema_version": "multi-joint-collision-configuration-result@2",
            "configuration_index": 0,
            "configuration_hash": _CONFIGURATION_DIGESTS[0],
            "ordered_joint_states": [
                {"joint_id": "joint", "joint_position_deg": 0.0, "within_limits": True}
            ],
            "instance_world_transforms": [
                {
                    "instance_id": "moving",
                    "is_articulated": True,
                    "transform": {
                        "x_mm": 20.0,
                        "y_mm": 0.0,
                        "z_mm": 0.0,
                        "rotation_quaternion": [1.0, 0.0, 0.0, 0.0],
                    },
                }
            ],
            "pair_results": [
                {
                    "schema_version": "exact-constituent-pair-result@2",
                    "first_instance_id": "base",
                    "second_instance_id": "moving",
                    "interference_volume_mm3": 0.0,
                    "exact_distance_mm": 3.0,
                    "classification": "positive_clearance",
                }
            ],
            "classification": "positive_clearance",
            "any_interference": False,
            "any_touching": False,
            "all_positive_clearance": True,
            "minimum_exact_distance_mm": 3.0,
        },
        {
            "schema_version": "multi-joint-collision-configuration-result@2",
            "configuration_index": 1,
            "configuration_hash": _CONFIGURATION_DIGESTS[1],
            "ordered_joint_states": [
                {"joint_id": "joint", "joint_position_deg": 1.0, "within_limits": True}
            ],
            "instance_world_transforms": [
                {
                    "instance_id": "moving",
                    "is_articulated": True,
                    "transform": {
                        "x_mm": 20.0,
                        "y_mm": 0.0,
                        "z_mm": 0.0,
                        "rotation_quaternion": [1.0, 0.0, 0.0, 0.0],
                    },
                }
            ],
            "pair_results": [
                {
                    "schema_version": "exact-constituent-pair-result@2",
                    "first_instance_id": "base",
                    "second_instance_id": "moving",
                    "interference_volume_mm3": 0.0,
                    "exact_distance_mm": 3.0,
                    "classification": "positive_clearance",
                }
            ],
            "classification": "positive_clearance",
            "any_interference": False,
            "any_touching": False,
            "all_positive_clearance": True,
            "minimum_exact_distance_mm": 3.0,
        },
    ],
    "any_interference": False,
    "any_touching": False,
    "all_positive_clearance": True,
    "collision_configuration_indices": [],
    "minimum_exact_distance_mm": 3.0,
    "minimum_distance_configuration_index": 0,
    "continuous_path_verified": False,
    "semantic_assembly_hash": _SEMANTIC_ASSEMBLY_DIGEST,
}
_P6_DIGEST = "sha256:47ef3529ace390837138a5f6573a0250cef8775fdac5fa35cc61f6c41472a78b"


def _independent_digest(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _single_joint_model() -> KinematicModel:
    return KinematicModel(
        model_id="single",
        joints=(
            RevoluteJointModel(
                joint_id="joint",
                parent_instance_id="base",
                child_instance_id="moving",
            ),
        ),
    )


def _legacy_m10_request(assembly, model: KinematicModel) -> MultiJointCollisionSweepRequest:
    return MultiJointCollisionSweepRequest(
        source_assembly_id=assembly.assembly_id,
        source_assembly_hash=assembly_hash(assembly),
        model=model,
        configurations=(
            JointConfiguration(model_id=model.model_id, positions={"joint": 0.0}),
        ),
        moving_instance_ids=("moving",),
        stationary_instance_ids=("base",),
    )


def _legacy_m10_result(
    request: MultiJointCollisionSweepRequest,
) -> MultiJointCollisionSweepResult:
    configuration = MultiJointCollisionConfigurationResult(
        configuration_index=0,
        configuration_hash=joint_configuration_hash(request.configurations[0]),
        transformed_assembly_hash=request.source_assembly_hash,
        ordered_joint_states=(),
        instance_world_transforms=(
            InstanceWorldTransform(
                instance_id="moving",
                is_articulated=True,
                transform=CadRigidTransform(x_mm=20.0),
            ),
        ),
        pair_results=(
            CadKinematicCollisionPairResult(
                moving_instance_id="moving",
                stationary_instance_id="base",
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
    return MultiJointCollisionSweepResult(
        evaluator_version="multi-joint-exact-collision-sweep@1.0",
        source_assembly_hash=request.source_assembly_hash,
        model_hash=request.model_hash,
        request_hash=request.request_hash,
        configuration_results=(configuration,),
        any_interference=False,
        any_touching=False,
        all_positive_clearance=True,
        collision_configuration_indices=(),
        minimum_exact_distance_mm=3.0,
        minimum_distance_configuration_index=0,
    )


def test_hand_derived_expected_payloads_have_pinned_digests():
    assert _independent_digest(_PART_PROGRAM_PAYLOAD) == _PART_PROGRAM_DIGEST
    assert _independent_digest(_SEMANTIC_ASSEMBLY_PAYLOAD) == _SEMANTIC_ASSEMBLY_DIGEST
    assert [_independent_digest(item) for item in _CONFIGURATION_PAYLOADS] == (
        _CONFIGURATION_DIGESTS
    )
    assert _independent_digest(_PAIR_SCOPE_PAYLOAD) == _PAIR_SCOPE_DIGEST
    assert _independent_digest(_F1_PAYLOAD) == _F1_DIGEST
    assert _independent_digest(_F3_PAYLOAD) == _F3_DIGEST
    assert _independent_digest(_P5_PAYLOAD) == _P5_DIGEST
    assert _independent_digest(_P6_PAYLOAD) == _P6_DIGEST


def test_four_relocated_projections_match_independent_spec_vectors():
    assembly = _assembly()
    model = _v2_model()
    request = _v2_request(assembly, model=model)
    result = _v2_result(request)

    # §10 is independently expanded above; do not use the result of P5/P6 or
    # the projection under test to construct either expected assembly input.
    assert semantic_assembly_hash(assembly, ()) == _SEMANTIC_ASSEMBLY_DIGEST
    assert semantic_kinematic_model_hash(model) == _F1_DIGEST
    assert semantic_single_joint_kinematic_model_hash(_single_joint_model()) == _F3_DIGEST
    assert semantic_m10_v2_request_hash(request, assembly, ()) == _P5_DIGEST
    assert semantic_m10_v2_result_hash(result, request, assembly, ()) == _P6_DIGEST


def test_declared_field_sets_match_the_accepted_projection_tables():
    assert set(KinematicModelV2.model_fields) == {
        "schema_version", "model_id", "bodies", "joints", "evaluator_version",
        "transform_agreement_version",
    }
    assert set(KinematicRigidBody.model_fields) == {
        "schema_version", "body_id", "reference_member_instance_id", "members",
        "body_hash",
    }
    assert set(KinematicRigidBodyMember.model_fields) == {
        "member_instance_id", "reference_to_member_home",
    }
    assert set(CadRigidTransform.model_fields) == {
        "x_mm", "y_mm", "z_mm", "rotation_quaternion",
    }
    assert set(RevoluteJointModelV2.model_fields) == {
        "schema_version", "joint_id", "joint_kind", "parent_body_id",
        "child_body_id", "axis_origin_x_mm", "axis_origin_y_mm",
        "axis_origin_z_mm", "axis_direction_x", "axis_direction_y",
        "axis_direction_z", "min_angle_deg", "max_angle_deg",
    }
    assert set(KinematicModel.model_fields) == {
        "schema_version", "model_id", "joints", "evaluator_version",
    }
    assert set(RevoluteJointModel.model_fields) == {
        "schema_version", "joint_id", "joint_kind", "parent_instance_id",
        "child_instance_id", "axis_origin_x_mm", "axis_origin_y_mm",
        "axis_origin_z_mm", "axis_direction_x", "axis_direction_y",
        "axis_direction_z", "min_angle_deg", "max_angle_deg",
    }
    assert set(MultiJointCollisionSweepRequestV2.model_fields) == {
        "schema_version", "source_assembly_id", "source_assembly_hash", "model",
        "configurations", "exact_pair_scope", "volume_tolerance_mm3",
        "distance_tolerance_mm", "evaluator_version", "model_hash", "request_hash",
    }
    assert set(JointConfiguration.model_fields) == {"model_id", "positions"}
    assert set(ExactConstituentPair.model_fields) == {
        "schema_version", "first_instance_id", "second_instance_id",
    }
    assert set(MultiJointCollisionSweepResultV2.model_fields) == {
        "schema_version", "evaluator_version", "source_assembly_hash", "model_hash",
        "request_hash", "configuration_results", "any_interference", "any_touching",
        "all_positive_clearance", "collision_configuration_indices",
        "minimum_exact_distance_mm", "minimum_distance_configuration_index",
        "continuous_path_verified", "result_hash",
    }
    assert set(MultiJointCollisionConfigurationResultV2.model_fields) == {
        "schema_version", "configuration_index", "configuration_hash",
        "transformed_assembly_hash", "ordered_joint_states", "instance_world_transforms",
        "pair_results", "classification", "any_interference", "any_touching",
        "all_positive_clearance", "minimum_exact_distance_mm",
    }
    assert set(EvaluatedJointState.model_fields) == {
        "joint_id", "joint_position_deg", "within_limits",
    }
    assert set(InstanceWorldTransform.model_fields) == {
        "instance_id", "is_articulated", "transform",
    }
    assert set(ExactConstituentPairResultV2.model_fields) == {
        "schema_version", "first_instance_id", "second_instance_id",
        "interference_volume_mm3", "exact_distance_mm", "classification",
    }


def test_f1_f3_exclude_evaluator_and_preserve_semantic_order_rules():
    model = _v2_model()
    other_evaluator = model.model_copy(
        update={"evaluator_version": "multi-joint-forward-kinematics@other"}
    )
    assert semantic_kinematic_model_hash(model) == _F1_DIGEST
    assert semantic_kinematic_model_hash(other_evaluator) == _F1_DIGEST
    reordered_model = KinematicModelV2(
        model_id=model.model_id,
        bodies=tuple(reversed(model.bodies)),
        joints=model.joints,
    )
    assert semantic_kinematic_model_hash(reordered_model) == _F1_DIGEST
    assert semantic_kinematic_model_hash(
        _v2_model(axis_direction=(1.0, 0.0, 0.0))
    ) != _F1_DIGEST
    reference_member = KinematicRigidBodyMember(
        member_instance_id="anchor", reference_to_member_home=CadRigidTransform()
    )
    offset_member = KinematicRigidBodyMember(
        member_instance_id="offset",
        reference_to_member_home=CadRigidTransform(x_mm=4.0),
    )
    body_members_forward = KinematicRigidBody(
        body_id="group",
        reference_member_instance_id="anchor",
        members=(reference_member, offset_member),
    )
    body_members_reversed = KinematicRigidBody(
        body_id="group",
        reference_member_instance_id="anchor",
        members=(offset_member, reference_member),
    )
    member_model_forward = KinematicModelV2(
        model_id="members", bodies=(body_members_forward,), joints=()
    )
    member_model_reversed = KinematicModelV2(
        model_id="members", bodies=(body_members_reversed,), joints=()
    )
    assert semantic_kinematic_model_hash(member_model_forward) == (
        semantic_kinematic_model_hash(member_model_reversed)
    )
    with pytest.raises(ValueError, match="duplicate body IDs"):
        KinematicModelV2(
            model_id="duplicates",
            bodies=(model.bodies[0], model.bodies[0]),
            joints=(),
        )

    single = _single_joint_model()
    alternate = single.model_copy(
        update={"evaluator_version": "multi-joint-forward-kinematics@other"}
    )
    assert semantic_single_joint_kinematic_model_hash(single) == _F3_DIGEST
    assert semantic_single_joint_kinematic_model_hash(alternate) == _F3_DIGEST
    two_joints = KinematicModel(
        model_id="single",
        joints=(
            RevoluteJointModel(
                joint_id="joint-z", parent_instance_id="base", child_instance_id="moving-z"
            ),
            RevoluteJointModel(
                joint_id="joint-a", parent_instance_id="base", child_instance_id="moving-a"
            ),
        ),
    )
    reversed_joints = KinematicModel(
        model_id="single", joints=tuple(reversed(two_joints.joints))
    )
    assert semantic_single_joint_kinematic_model_hash(two_joints) == (
        semantic_single_joint_kinematic_model_hash(reversed_joints)
    )
    with pytest.raises(ValueError, match="duplicate joint IDs"):
        KinematicModel(model_id="duplicate", joints=(single.joints[0], single.joints[0]))
    changed_joint = single.model_copy(
        update={
            "joints": (
                single.joints[0].model_copy(update={"axis_direction_x": 1.0}),
            )
        }
    )
    assert semantic_single_joint_kinematic_model_hash(changed_joint) != _F3_DIGEST


def test_p5_is_semantic_but_keeps_configuration_order_and_replay_binding():
    assembly = _assembly()
    request = _v2_request(assembly)
    assert semantic_m10_v2_request_hash(request, assembly, ()) == _P5_DIGEST
    assert semantic_m10_v2_request_hash(
        request.model_copy(update={"request_hash": "sha256:" + "f" * 64}),
        assembly,
        (),
    ) == _P5_DIGEST
    assert semantic_m10_v2_request_hash(
        request.model_copy(update={"model_hash": "sha256:" + "e" * 64}),
        assembly,
        (),
    ) == _P5_DIGEST

    renamed_assembly = _assembly("assembly-b")
    renamed_request = _v2_request(renamed_assembly)
    assert semantic_m10_v2_request_hash(renamed_request, renamed_assembly, ()) == _P5_DIGEST

    reversed_request = _v2_request(
        assembly, configurations=tuple(reversed(request.configurations))
    )
    assert semantic_m10_v2_request_hash(reversed_request, assembly, ()) != _P5_DIGEST
    pair_a = ExactConstituentPair(first_instance_id="base", second_instance_id="moving")
    pair_b = ExactConstituentPair(first_instance_id="base", second_instance_id="other")
    common = {
        "schema_version": request.schema_version,
        "source_assembly_id": request.source_assembly_id,
        "source_assembly_hash": request.source_assembly_hash,
        "model": request.model,
        "configurations": request.configurations,
        "evaluator_version": request.evaluator_version,
    }
    scope_forward = MultiJointCollisionSweepRequestV2(
        **common, exact_pair_scope=(pair_a, pair_b)
    )
    scope_reversed = MultiJointCollisionSweepRequestV2(
        **common, exact_pair_scope=(pair_b, pair_a)
    )
    assert semantic_m10_v2_request_hash(scope_forward, assembly, ()) == (
        semantic_m10_v2_request_hash(scope_reversed, assembly, ())
    )
    with pytest.raises(ValueError, match="duplicate exact constituent pair"):
        MultiJointCollisionSweepRequestV2(
            **common, exact_pair_scope=(pair_a, pair_a)
        )
    changed_tolerance = request.model_copy(
        update={"distance_tolerance_mm": 2e-7}
    )
    assert semantic_m10_v2_request_hash(changed_tolerance, assembly, ()) != _P5_DIGEST
    with pytest.raises(ValueError, match="source assembly ID"):
        semantic_m10_v2_request_hash(
            request.model_copy(update={"source_assembly_id": "wrong"}), assembly, ()
        )
    with pytest.raises(ValueError, match="source assembly hash"):
        semantic_m10_v2_request_hash(
            request.model_copy(update={"source_assembly_hash": "sha256:" + "0" * 64}),
            assembly,
            (),
        )


def test_p6_excludes_transient_identity_and_binds_ordered_measurements():
    assembly = _assembly()
    request = _v2_request(assembly)
    result = _v2_result(request)
    assert semantic_m10_v2_result_hash(result, request, assembly, ()) == _P6_DIGEST
    assert semantic_m10_v2_result_hash(
        result.model_copy(update={"result_hash": "sha256:" + "f" * 64}),
        request,
        assembly,
        (),
    ) == _P6_DIGEST

    rotated_transient = _v2_result(request, transformed_hash="sha256:transformed-b")
    assert semantic_m10_v2_result_hash(rotated_transient, request, assembly, ()) == _P6_DIGEST
    reversed_request = _v2_request(
        assembly, configurations=tuple(reversed(request.configurations))
    )
    reversed_result = _v2_result(reversed_request)
    assert semantic_m10_v2_result_hash(
        reversed_result, reversed_request, assembly, ()
    ) != _P6_DIGEST
    other_evaluator = result.model_copy(
        update={"evaluator_version": "multi-joint-exact-collision-sweep@other"}
    )
    assert semantic_m10_v2_result_hash(other_evaluator, request, assembly, ()) == _P6_DIGEST
    replay_hash = "sha256:" + "d" * 64
    replay_request = request.model_copy(
        update={"model_hash": replay_hash, "request_hash": replay_hash}
    )
    replay_result = result.model_copy(
        update={"model_hash": replay_hash, "request_hash": replay_hash}
    )
    assert semantic_m10_v2_result_hash(
        replay_result, replay_request, assembly, ()
    ) == _P6_DIGEST
    renamed_assembly = _assembly("assembly-b")
    renamed_request = _v2_request(renamed_assembly)
    renamed_result = _v2_result(renamed_request)
    assert semantic_m10_v2_result_hash(
        renamed_result, renamed_request, renamed_assembly, ()
    ) == _P6_DIGEST

    changed_measurement = result.model_copy(
        update={"minimum_exact_distance_mm": 4.0}
    )
    assert semantic_m10_v2_result_hash(changed_measurement, request, assembly, ()) != _P6_DIGEST
    with pytest.raises(ValueError, match="continuous path"):
        semantic_m10_v2_result_hash(
            result.model_copy(update={"continuous_path_verified": True}), request, assembly, ()
        )
    with pytest.raises(ValueError, match="cardinality"):
        semantic_m10_v2_result_hash(
            result.model_copy(update={"configuration_results": result.configuration_results[:1]}),
            request,
            assembly,
            (),
        )
    with pytest.raises(ValueError, match="source assembly hash"):
        semantic_m10_v2_result_hash(
            result.model_copy(update={"source_assembly_hash": "sha256:" + "1" * 64}),
            request,
            assembly,
            (),
        )


def test_wrong_semantic_families_and_unknown_declared_fields_fail_closed():
    assembly = _assembly()
    request = _v2_request(assembly)
    result = _v2_result(request)
    legacy_model = _single_joint_model()
    legacy_request = _legacy_m10_request(assembly, legacy_model)
    legacy_result = _legacy_m10_result(legacy_request)
    with pytest.raises(TypeError, match="KinematicModelV2"):
        semantic_kinematic_model_hash(legacy_model)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="KinematicModel"):
        semantic_single_joint_kinematic_model_hash(_v2_model())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="MultiJointCollisionSweepRequestV2"):
        semantic_m10_v2_request_hash(legacy_request, assembly, ())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="MultiJointCollisionSweepResultV2"):
        semantic_m10_v2_result_hash(
            legacy_result,
            request,
            assembly,
            (),
        )
    with pytest.raises(ValueError):
        KinematicModelV2.model_validate(
            _v2_model().model_dump(mode="json") | {"unclassified_field": "reject"}
        )
    with pytest.raises(ValueError):
        MultiJointCollisionSweepRequestV2.model_validate(
            request.model_dump(mode="json") | {"unclassified_field": "reject"}
        )
    with pytest.raises(ValueError):
        MultiJointCollisionSweepResultV2.model_validate(
            result.model_dump(mode="json") | {"unclassified_field": "reject"}
        )


def test_production_owner_definitions_imports_and_dependency_direction():
    root = Path(__file__).resolve().parents[2] / "src" / "mechcad_harness"
    owner_path = root / "semantic_m10_kinematics.py"
    owner_module = "mechcad_harness.semantic_m10_kinematics"
    names = {
        "semantic_kinematic_model_hash",
        "semantic_single_joint_kinematic_model_hash",
        "semantic_m10_v2_request_hash",
        "semantic_m10_v2_result_hash",
    }
    modules = {}
    definitions = {}
    imports = {}
    module_imports = {}
    exports = {}
    for path in root.rglob("*.py"):
        relative = path.relative_to(root).with_suffix("")
        parts = list(relative.parts)
        if parts[-1] == "__init__":
            parts.pop()
        module = "mechcad_harness" + ("." + ".".join(parts) if parts else "")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules[module] = tree
        local_defs = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in names
        }
        if local_defs:
            definitions[module] = local_defs
        imported_names = set()
        imported_modules = set()
        top_level_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
                    base = "." * node.level + (node.module or "")
                    resolved = importlib.util.resolve_name(base, package)
                else:
                    resolved = node.module or ""
                if resolved.startswith("mechcad_harness"):
                    imported_modules.add(resolved)
                if resolved == owner_module:
                    imported_names.update(alias.name for alias in node.names)
                    assert not any(alias.name == "*" for alias in node.names)
            elif isinstance(node, ast.Import):
                imported_modules.update(
                    alias.name for alias in node.names
                    if alias.name.startswith("mechcad_harness")
                )
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
                    base = "." * node.level + (node.module or "")
                    resolved = importlib.util.resolve_name(base, package)
                else:
                    resolved = node.module or ""
                if resolved.startswith("mechcad_harness"):
                    top_level_modules.add(resolved)
            elif isinstance(node, ast.Import):
                top_level_modules.update(
                    alias.name for alias in node.names
                    if alias.name.startswith("mechcad_harness")
                )
        declared_exports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            ) and isinstance(node.value, (ast.List, ast.Tuple)):
                declared_exports.update(
                    item.value for item in node.value.elts
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                )
        exports[module] = declared_exports
        imports[module] = (imported_names, imported_modules)
        module_imports[module] = top_level_modules

    assert definitions == {owner_module: names}
    callers = {
        module: imported & names
        for module, (imported, _) in imports.items()
        if imported & names
    }
    assert callers
    assert set.union(*callers.values()) == names
    for module, (imported, _) in imports.items():
        if module == owner_module:
            continue
        references = {
            node.id
            for node in ast.walk(modules[module])
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in names
        }
        assert references <= imported, (module, references - imported)
        assert not (exports[module] & names), (module, exports[module] & names)
    for module, (_, dependencies) in imports.items():
        if module != owner_module:
            assert not (dependencies & {owner_module}) or module in callers
    assert not any(
        module in {
            "mechcad_harness.multi_joint_kinematics",
            "mechcad_harness.multi_joint_collision_sweep",
            "mechcad_harness.multi_joint_pair_scope",
            "mechcad_harness.multi_joint_continuous_path",
            "mechcad_harness.multi_joint_continuous_clearance",
        }
        and owner_module in dependencies
        for module, (_, dependencies) in imports.items()
    )

    owner_dependencies = module_imports[owner_module]
    assert not any(module.startswith("mechcad_harness.candidates") for module in owner_dependencies)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(module: str) -> None:
        if module in visiting:
            raise AssertionError(f"static import cycle at {module}")
        if module in visited or module not in module_imports:
            return
        visiting.add(module)
        for dependency in module_imports[module]:
            visit(dependency)
        visiting.remove(module)
        visited.add(module)

    for dependency in owner_dependencies:
        visit(dependency)
        assert dependency not in callers, dependency
