from __future__ import annotations

from collections.abc import Mapping

from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
)
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.candidates.models import (
    PhysicalAxisOwnerEndpoint,
    PhysicalJointMotionMode,
    PhysicalRevoluteJointBinding,
    PhysicalRigidBodyBinding,
    SuppliedReferenceFrameAxisSource,
)
from mechcad_harness.candidates.multi_joint_m10_bridge import (
    compile_kinematic_model_v2,
    derive_body_member_offsets,
    lower_physical_axis_to_parent_body_reference,
)
from mechcad_harness.models.physical_mechanism import (
    CanonicalPhysicalRevoluteJointBinding,
    CanonicalPhysicalRigidBodyBinding,
    CanonicalSuppliedReferenceFrameAxisSource,
)
from mechcad_harness.multi_joint_kinematics import (
    JointConfiguration,
    MultiJointKinematicsService,
    rigid_transform_agrees,
    transform_apply,
    transform_compose,
    transform_inverse,
)


_HASH = "sha256:" + "a" * 64


def _body(body_id: str, *members: str) -> PhysicalRigidBodyBinding:
    return PhysicalRigidBodyBinding(
        physical_body_id=body_id,
        member_physical_instance_ids=members,
        reference_physical_instance_id=members[0],
    )


def _joint(
    *,
    joint_id: str = "joint-main",
    motion_mode: PhysicalJointMotionMode = PhysicalJointMotionMode.BOUNDED,
    min_angle_deg: float | None = -90.0,
    max_angle_deg: float | None = 90.0,
    axis_sign: int = 1,
    source_instance_id: str = "child-reference",
) -> PhysicalRevoluteJointBinding:
    return PhysicalRevoluteJointBinding(
        physical_joint_id=joint_id,
        parent_physical_body_id="body-root",
        child_physical_body_id="body-child",
        connection_id="connection-main",
        parent_physical_instance_id="root-reference",
        parent_interface_id="axis",
        child_physical_instance_id="child-reference",
        child_interface_id="axis",
        axis_source=SuppliedReferenceFrameAxisSource(
            source_physical_instance_id=source_instance_id,
            frame_id="frame-axis",
            frame_hash=_HASH,
            geometry_reference_hash=_HASH,
            specification_hash=_HASH,
        ),
        axis_owner_endpoint=PhysicalAxisOwnerEndpoint.PARENT,
        axis_sign=axis_sign,
        motion_mode=motion_mode,
        min_angle_deg=min_angle_deg,
        max_angle_deg=max_angle_deg,
        zero_reference_semantics="accepted-semantic-home@1",
    )


def _assembly(placements: Mapping[str, CadRigidTransform]) -> CadAssemblyProgram:
    parts = tuple(
        CadPartProgram(
            part_id=f"part-{instance_id}",
            operations=(
                BasePlateOperation(
                    operation_id=f"operation-{instance_id}",
                    length_mm=1.0,
                    width_mm=1.0,
                    thickness_mm=1.0,
                ),
            ),
        )
        for instance_id in placements
    )
    return CadAssemblyProgram(
        assembly_id="lowering-assembly",
        parts=parts,
        instances=tuple(
            CadComponentInstance(
                instance_id=f"cad-{instance_id}",
                part_id=f"part-{instance_id}",
                placement=placement,
            )
            for instance_id, placement in placements.items()
        ),
    )


def _fixture():
    root_home = CadRigidTransform(
        x_mm=17.25,
        y_mm=-8.5,
        z_mm=3.75,
        rotation_quaternion=(0.31, -0.42, 0.57, 0.63),
    )
    root_offset = CadRigidTransform(
        x_mm=2.0,
        y_mm=4.0,
        z_mm=-1.5,
        rotation_quaternion=(0.71, 0.11, -0.23, 0.65),
    )
    child_home = CadRigidTransform(
        x_mm=52.0,
        y_mm=10.0,
        z_mm=4.0,
        rotation_quaternion=(0.83, -0.19, 0.41, 0.33),
    )
    semantic_placements = {
        "root-reference": root_home,
        "root-member": transform_compose(root_home, root_offset),
        "child-reference": child_home,
    }
    physical_to_cad = {
        physical_id: f"cad-{physical_id}"
        for physical_id in semantic_placements
    }
    bodies = (
        _body("body-child", "child-reference"),
        _body("body-root", "root-reference", "root-member"),
    )
    axis_pose = {
        "joint-main": (
            (1.25, -2.0, 3.5),
            (0.0, 1.0, 0.0),
        )
    }
    return (
        semantic_placements,
        physical_to_cad,
        bodies,
        _joint(),
        axis_pose,
        _assembly(semantic_placements),
    )


def test_lower_axis_converts_source_local_frame_to_parent_reference_and_applies_sign():
    source_home = CadRigidTransform(x_mm=10.0, y_mm=4.0, z_mm=-2.0)
    parent_home = CadRigidTransform(x_mm=3.0, y_mm=1.0, z_mm=5.0)
    source_origin = (2.0, -1.0, 4.0)
    source_direction = (0.0, 1.0, 0.0)

    origin, positive_direction = lower_physical_axis_to_parent_body_reference(
        source_origin,
        source_direction,
        source_home,
        parent_home,
        axis_sign=1,
    )
    negative_origin, negative_direction = lower_physical_axis_to_parent_body_reference(
        source_origin,
        source_direction,
        source_home,
        parent_home,
        axis_sign=-1,
    )

    expected_origin = transform_apply(
        transform_inverse(parent_home),
        transform_apply(source_home, source_origin),
    )
    assert origin == expected_origin == negative_origin
    assert positive_direction == (0.0, 1.0, 0.0)
    assert negative_direction == (0.0, -1.0, 0.0)


def test_derive_body_member_offsets_uses_literal_reference_identity_and_full_precision_quaternions():
    semantic_placements, _, bodies, _, _, _ = _fixture()
    body = next(body for body in bodies if body.physical_body_id == "body-root")

    members = derive_body_member_offsets(body, semantic_placements)

    assert tuple(member.member_instance_id for member in members) == (
        "root-member",
        "root-reference",
    )
    reference = next(member for member in members if member.member_instance_id == "root-reference")
    member = next(member for member in members if member.member_instance_id == "root-member")
    assert reference.reference_to_member_home == CadRigidTransform()
    expected = transform_compose(
        transform_inverse(semantic_placements["root-reference"]),
        semantic_placements["root-member"],
    )
    assert member.reference_to_member_home.model_dump(mode="json") == expected.model_dump(mode="json")


def test_compile_emits_stable_physical_ids_revalidates_and_preserves_raw_multiturn_limits():
    semantic_placements, physical_to_cad, bodies, joint, axis_pose, semantic_assembly = _fixture()
    continuous_joint = _joint(
        motion_mode=PhysicalJointMotionMode.CONTINUOUS,
        min_angle_deg=None,
        max_angle_deg=None,
    )
    model = compile_kinematic_model_v2(
        assembly=_assembly(semantic_placements),
        body_bindings=bodies,
        joint_bindings=(continuous_joint,),
        semantic_placements=semantic_placements,
        physical_to_cad_instance_ids=physical_to_cad,
        semantic_axis_poses=axis_pose,
        model_id="stable-model",
    )

    assert tuple(body.body_id for body in model.bodies) == ("body-child", "body-root")
    assert tuple(joint.joint_id for joint in model.joints) == ("joint-main",)
    assert model.joints[0].parent_body_id == "body-root"
    assert model.joints[0].child_body_id == "body-child"
    assert model.joints[0].min_angle_deg is None
    assert model.joints[0].max_angle_deg is None
    assert {member.member_instance_id for body in model.bodies for member in body.members} == {
        "cad-child-reference",
        "cad-root-member",
        "cad-root-reference",
    }

    zero = MultiJointKinematicsService().evaluate(
        semantic_assembly,
        model,
        JointConfiguration(model_id=model.model_id, positions={"joint-main": 0.0}),
    )
    source = {instance.instance_id: instance.placement for instance in semantic_assembly.instances}
    for item in zero.instance_world_transforms:
        assert rigid_transform_agrees(source[item.instance_id], item.transform)


def test_compile_preserves_bounded_raw_multiturn_limits_without_wrapping():
    semantic_placements, physical_to_cad, bodies, joint, axis_pose, _ = _fixture()
    mult_turn_joint = _joint(min_angle_deg=0.0, max_angle_deg=1080.0)

    model = compile_kinematic_model_v2(
        assembly=_assembly(semantic_placements),
        body_bindings=bodies,
        joint_bindings=(mult_turn_joint,),
        semantic_placements=semantic_placements,
        physical_to_cad_instance_ids=physical_to_cad,
        semantic_axis_poses=axis_pose,
        model_id="stable-model",
    )

    assert (model.joints[0].min_angle_deg, model.joints[0].max_angle_deg) == (0.0, 1080.0)


def test_candidate_and_canonical_lowering_agree_at_zero_configuration():
    semantic_placements, physical_to_cad, candidate_bodies, candidate_joint, axis_pose, assembly = _fixture()
    canonical_bodies = tuple(
        CanonicalPhysicalRigidBodyBinding(
            physical_body_id=body.physical_body_id,
            member_physical_instance_ids=body.member_physical_instance_ids,
            reference_physical_instance_id=body.reference_physical_instance_id,
        )
        for body in candidate_bodies
    )
    canonical_joint = CanonicalPhysicalRevoluteJointBinding(
        physical_joint_id=candidate_joint.physical_joint_id,
        parent_physical_body_id=candidate_joint.parent_physical_body_id,
        child_physical_body_id=candidate_joint.child_physical_body_id,
        connection_id=candidate_joint.connection_id,
        parent_physical_instance_id=candidate_joint.parent_physical_instance_id,
        parent_interface_id=candidate_joint.parent_interface_id,
        child_physical_instance_id=candidate_joint.child_physical_instance_id,
        child_interface_id=candidate_joint.child_interface_id,
        axis_source=CanonicalSuppliedReferenceFrameAxisSource(
            source_physical_instance_id=candidate_joint.axis_source.source_physical_instance_id,
            frame_id=candidate_joint.axis_source.frame_id,
            frame_hash=candidate_joint.axis_source.frame_hash,
            geometry_reference_hash=candidate_joint.axis_source.geometry_reference_hash,
            specification_hash=candidate_joint.axis_source.specification_hash,
        ),
        axis_owner_endpoint="parent",
        axis_sign=candidate_joint.axis_sign,
        motion_mode="bounded",
        min_angle_deg=candidate_joint.min_angle_deg,
        max_angle_deg=candidate_joint.max_angle_deg,
        zero_reference_semantics=candidate_joint.zero_reference_semantics,
    )

    candidate_model = compile_kinematic_model_v2(
        assembly,
        candidate_bodies,
        (candidate_joint,),
        semantic_placements,
        physical_to_cad,
        axis_pose,
        "shared-model",
    )
    canonical_model = compile_kinematic_model_v2(
        assembly,
        canonical_bodies,
        (canonical_joint,),
        semantic_placements,
        physical_to_cad,
        axis_pose,
        "shared-model",
    )

    candidate_zero = MultiJointKinematicsService().evaluate(
        assembly,
        candidate_model,
        JointConfiguration(model_id="shared-model", positions={"joint-main": 0.0}),
    )
    canonical_zero = MultiJointKinematicsService().evaluate(
        assembly,
        canonical_model,
        JointConfiguration(model_id="shared-model", positions={"joint-main": 0.0}),
    )
    assert candidate_model.model_dump(mode="json") == canonical_model.model_dump(mode="json")
    for candidate, canonical in zip(
        candidate_zero.instance_world_transforms,
        canonical_zero.instance_world_transforms,
    ):
        assert candidate.instance_id == canonical.instance_id
        assert rigid_transform_agrees(candidate.transform, canonical.transform)
