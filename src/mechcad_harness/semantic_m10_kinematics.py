from __future__ import annotations

import hashlib
import json

from mechcad_harness.cad_assembly import (
    M10_EXECUTION_SEMANTICS_VERSION,
    CadAssemblyProgram,
    CadRigidTransform,
    _require_semantic_fields,
    verified_semantic_assembly_hash,
)
from mechcad_harness.multi_joint_collision_sweep import (
    ExactConstituentPairResultV2,
    EvaluatedJointState,
    InstanceWorldTransform,
    JointConfiguration,
    MultiJointCollisionConfigurationResultV2,
    MultiJointCollisionSweepRequestV2,
    MultiJointCollisionSweepResultV2,
    _digest,
)
from mechcad_harness.multi_joint_kinematics import (
    KinematicModel,
    KinematicModelV2,
    KinematicRigidBody,
    KinematicRigidBodyMember,
    MULTI_JOINT_FORWARD_KINEMATICS_VERSION,
    MULTI_JOINT_FORWARD_KINEMATICS_V2_VERSION,
    RIGID_TRANSFORM_AGREEMENT_VERSION,
    RevoluteJointModel,
    RevoluteJointModelV2,
    joint_configuration_hash,
    v2_revolute_joint_wire_payload,
)
from mechcad_harness.multi_joint_pair_scope import (
    EXACT_CONSTITUENT_PAIR_SCOPE_VERSION,
    ExactConstituentPair,
    canonical_exact_pair_scope,
    exact_pair_scope_hash,
)


def semantic_kinematic_model_hash(model: KinematicModelV2) -> str:
    """Hash the exact F1 semantic KinematicModelV2 projection (evaluator-free)."""
    _require_semantic_fields(
        model,
        KinematicModelV2,
        {
            "schema_version", "model_id", "bodies", "joints",
            "evaluator_version", "transform_agreement_version",
        },
        "KinematicModelV2",
    )
    body_fields = {
        "schema_version", "body_id", "reference_member_instance_id", "members",
        "body_hash",
    }
    member_fields = {"member_instance_id", "reference_to_member_home"}
    transform_fields = {"x_mm", "y_mm", "z_mm", "rotation_quaternion"}
    joint_fields = {
        "schema_version", "joint_id", "joint_kind", "parent_body_id",
        "child_body_id", "axis_origin_x_mm", "axis_origin_y_mm",
        "axis_origin_z_mm", "axis_direction_x", "axis_direction_y",
        "axis_direction_z", "min_angle_deg", "max_angle_deg",
    }

    raw = model.model_dump(mode="json")
    # Evaluator versions are validated at the execution boundary, but are not
    # an input to the semantic model identity. Normalize only that excluded
    # replay/provenance field before integrity reconstruction.
    raw["evaluator_version"] = MULTI_JOINT_FORWARD_KINEMATICS_V2_VERSION
    validated = KinematicModelV2.model_validate(raw)
    if validated.schema_version != "kinematic-model@2":
        raise ValueError("unsupported semantic kinematic model schema")
    if validated.transform_agreement_version != RIGID_TRANSFORM_AGREEMENT_VERSION:
        raise ValueError("unsupported transform agreement contract")

    bodies = []
    for body in validated.bodies:
        _require_semantic_fields(body, KinematicRigidBody, body_fields, "KinematicRigidBody")
        members = []
        for member in body.members:
            _require_semantic_fields(
                member, KinematicRigidBodyMember, member_fields,
                "KinematicRigidBodyMember",
            )
            transform = member.reference_to_member_home
            _require_semantic_fields(
                transform, CadRigidTransform, transform_fields, "CadRigidTransform"
            )
            members.append(
                {
                    "member_instance_id": member.member_instance_id,
                    "reference_to_member_home": transform.model_dump(mode="json"),
                }
            )
        bodies.append(
            {
                "schema_version": body.schema_version,
                "body_id": body.body_id,
                "reference_member_instance_id": body.reference_member_instance_id,
                "members": members,
            }
        )
    joints = []
    for joint in validated.joints:
        _require_semantic_fields(
            joint, RevoluteJointModelV2, joint_fields, "RevoluteJointModelV2"
        )
        joints.append(v2_revolute_joint_wire_payload(joint))
    payload = {
        "semantic_projection_version": M10_EXECUTION_SEMANTICS_VERSION,
        "model_contract": "kinematic-model@2",
        "model_id": validated.model_id,
        "bodies": bodies,
        "joints": joints,
        "transform_agreement_version": validated.transform_agreement_version,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def semantic_single_joint_kinematic_model_hash(model: KinematicModel) -> str:
    """Hash the exact F3 single-joint model projection, excluding evaluator ID."""
    _require_semantic_fields(
        model,
        KinematicModel,
        {"schema_version", "model_id", "joints", "evaluator_version"},
        "KinematicModel",
    )
    if model.schema_version != "kinematic-model@1":
        raise ValueError("unsupported semantic single-joint model schema")
    raw = model.model_dump(mode="json")
    raw["evaluator_version"] = MULTI_JOINT_FORWARD_KINEMATICS_VERSION
    validated = KinematicModel.model_validate(raw)
    joint_fields = {
        "schema_version", "joint_id", "joint_kind", "parent_instance_id",
        "child_instance_id", "axis_origin_x_mm", "axis_origin_y_mm",
        "axis_origin_z_mm", "axis_direction_x", "axis_direction_y",
        "axis_direction_z", "min_angle_deg", "max_angle_deg",
    }
    joints = []
    for joint in sorted(validated.joints, key=lambda item: item.joint_id):
        _require_semantic_fields(
            joint, RevoluteJointModel, joint_fields, "RevoluteJointModel"
        )
        joints.append(
            {
                "schema_version": joint.schema_version,
                "joint_id": joint.joint_id,
                "joint_kind": joint.joint_kind.value,
                "parent_instance_id": joint.parent_instance_id,
                "child_instance_id": joint.child_instance_id,
                "axis_origin_x_mm": joint.axis_origin_x_mm,
                "axis_origin_y_mm": joint.axis_origin_y_mm,
                "axis_origin_z_mm": joint.axis_origin_z_mm,
                "axis_direction_x": joint.axis_direction_x,
                "axis_direction_y": joint.axis_direction_y,
                "axis_direction_z": joint.axis_direction_z,
                "min_angle_deg": joint.min_angle_deg,
                "max_angle_deg": joint.max_angle_deg,
            }
        )
    payload = {
        "semantic_projection_version": M10_EXECUTION_SEMANTICS_VERSION,
        "model_contract": "kinematic-model@1",
        "model_id": validated.model_id,
        "joints": joints,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def semantic_m10_v2_request_hash(
    request: MultiJointCollisionSweepRequestV2,
    assembly: CadAssemblyProgram,
    mappings,
) -> str:
    """Project P5 using only semantic model, ordered configuration and scope IDs."""
    _require_semantic_fields(
        request,
        MultiJointCollisionSweepRequestV2,
        {
            "schema_version", "source_assembly_id", "source_assembly_hash",
            "model", "configurations", "exact_pair_scope",
            "volume_tolerance_mm3", "distance_tolerance_mm",
            "evaluator_version", "model_hash", "request_hash",
        },
        "MultiJointCollisionSweepRequestV2",
    )
    if request.schema_version != "multi-joint-collision-sweep-request@2":
        raise ValueError("unsupported semantic M10 request contract")
    if request.source_assembly_id != assembly.assembly_id:
        raise ValueError("M10 request source assembly ID mismatch")
    semantic_assembly = verified_semantic_assembly_hash(
        assembly, mappings, request.source_assembly_hash
    )
    model_hash = semantic_kinematic_model_hash(request.model)
    configurations = []
    for configuration in request.configurations:
        _require_semantic_fields(
            configuration,
            JointConfiguration,
            {"model_id", "positions"},
            "JointConfiguration",
        )
        validated = JointConfiguration.model_validate(
            configuration.model_dump(mode="json")
        )
        if validated.model_id != request.model.model_id:
            raise ValueError("M10 configuration model identity mismatch")
        configurations.append(joint_configuration_hash(validated))
    if not configurations:
        raise ValueError("semantic M10 request requires configurations")
    scope = canonical_exact_pair_scope(request.exact_pair_scope)
    for pair in scope:
        _require_semantic_fields(
            pair,
            ExactConstituentPair,
            {"schema_version", "first_instance_id", "second_instance_id"},
            "ExactConstituentPair",
        )
    if scope != request.exact_pair_scope:
        raise ValueError("M10 exact pair scope is not canonical")
    payload = {
        "semantic_projection_version": M10_EXECUTION_SEMANTICS_VERSION,
        "request_contract": "multi-joint-collision-sweep-request@2",
        "semantic_kinematic_model_hash": model_hash,
        "configuration_hashes": configurations,
        "exact_pair_scope_hash": exact_pair_scope_hash(scope),
        "exact_pair_scope_version": EXACT_CONSTITUENT_PAIR_SCOPE_VERSION,
        "volume_tolerance_mm3": request.volume_tolerance_mm3,
        "distance_tolerance_mm": request.distance_tolerance_mm,
        "semantic_assembly_hash": semantic_assembly,
    }
    return _digest(payload)


def semantic_m10_v2_result_hash(
    result: MultiJointCollisionSweepResultV2,
    request: MultiJointCollisionSweepRequestV2,
    assembly: CadAssemblyProgram,
    mappings,
) -> str:
    """Project P6 measurements, retaining configuration order and excluding raw hashes."""
    _require_semantic_fields(
        result,
        MultiJointCollisionSweepResultV2,
        {
            "schema_version", "evaluator_version", "source_assembly_hash",
            "model_hash", "request_hash", "configuration_results",
            "any_interference", "any_touching", "all_positive_clearance",
            "collision_configuration_indices", "minimum_exact_distance_mm",
            "minimum_distance_configuration_index", "continuous_path_verified",
            "result_hash",
        },
        "MultiJointCollisionSweepResultV2",
    )
    semantic_request = semantic_m10_v2_request_hash(request, assembly, mappings)
    semantic_assembly = verified_semantic_assembly_hash(
        assembly, mappings, result.source_assembly_hash
    )
    if result.schema_version != "multi-joint-collision-sweep-result@2":
        raise ValueError("unsupported semantic M10 result contract")
    if (
        result.request_hash != request.request_hash
        or result.source_assembly_hash != request.source_assembly_hash
        or result.model_hash != request.model_hash
    ):
        raise ValueError("M10 result does not bind its legacy request replay identities")
    if result.continuous_path_verified is not False:
        raise ValueError("discrete M10 result cannot verify a continuous path")
    if len(result.configuration_results) != len(request.configurations):
        raise ValueError("M10 result configuration cardinality mismatch")

    config_fields = {
        "schema_version", "configuration_index", "configuration_hash",
        "transformed_assembly_hash", "ordered_joint_states",
        "instance_world_transforms", "pair_results", "classification",
        "any_interference", "any_touching", "all_positive_clearance",
        "minimum_exact_distance_mm",
    }
    joint_state_fields = {"joint_id", "joint_position_deg", "within_limits"}
    transform_result_fields = {"instance_id", "is_articulated", "transform"}
    transform_fields = {"x_mm", "y_mm", "z_mm", "rotation_quaternion"}
    pair_fields = {
        "schema_version", "first_instance_id", "second_instance_id",
        "interference_volume_mm3", "exact_distance_mm", "classification",
    }
    configuration_results = []
    for index, (configuration, item) in enumerate(
        zip(request.configurations, result.configuration_results, strict=True)
    ):
        _require_semantic_fields(
            item, MultiJointCollisionConfigurationResultV2, config_fields,
            "MultiJointCollisionConfigurationResultV2",
        )
        configuration_hash = joint_configuration_hash(configuration)
        if item.configuration_index != index or item.configuration_hash != configuration_hash:
            raise ValueError("M10 result configuration order or identity mismatch")
        joint_states = []
        for state in item.ordered_joint_states:
            _require_semantic_fields(
                state, EvaluatedJointState, joint_state_fields, "EvaluatedJointState"
            )
            joint_states.append(state.model_dump(mode="json"))
        world_transforms = []
        for transform in item.instance_world_transforms:
            _require_semantic_fields(
                transform, InstanceWorldTransform, transform_result_fields,
                "InstanceWorldTransform",
            )
            _require_semantic_fields(
                transform.transform, CadRigidTransform, transform_fields,
                "CadRigidTransform",
            )
            world_transforms.append(transform.model_dump(mode="json"))
        pair_results = []
        for pair in item.pair_results:
            _require_semantic_fields(
                pair, ExactConstituentPairResultV2, pair_fields,
                "ExactConstituentPairResultV2",
            )
            pair_results.append(pair.model_dump(mode="json"))
        configuration_results.append(
            {
                "schema_version": item.schema_version,
                "configuration_index": item.configuration_index,
                "configuration_hash": item.configuration_hash,
                "ordered_joint_states": joint_states,
                "instance_world_transforms": world_transforms,
                "pair_results": pair_results,
                "classification": item.classification.value,
                "any_interference": item.any_interference,
                "any_touching": item.any_touching,
                "all_positive_clearance": item.all_positive_clearance,
                "minimum_exact_distance_mm": item.minimum_exact_distance_mm,
            }
        )
    payload = {
        "semantic_projection_version": M10_EXECUTION_SEMANTICS_VERSION,
        "result_contract": "multi-joint-collision-sweep-result@2",
        "semantic_m10_v2_request_hash": semantic_request,
        "semantic_kinematic_model_hash": semantic_kinematic_model_hash(request.model),
        "configuration_semantic_results": configuration_results,
        "any_interference": result.any_interference,
        "any_touching": result.any_touching,
        "all_positive_clearance": result.all_positive_clearance,
        "collision_configuration_indices": list(result.collision_configuration_indices),
        "minimum_exact_distance_mm": result.minimum_exact_distance_mm,
        "minimum_distance_configuration_index": result.minimum_distance_configuration_index,
        "continuous_path_verified": False,
        "semantic_assembly_hash": semantic_assembly,
    }
    return _digest(payload)
