from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.kinematic_sweep import CollisionClassification
from mechcad_harness.models.quaternion import normalize_quaternion
from mechcad_harness.multi_joint_collision_sweep import (
    MULTI_JOINT_EXACT_COLLISION_SWEEP_V2_VERSION,
    MultiJointCollisionSweepRequestV2,
    MultiJointDiscreteCollisionSweepService,
    multi_joint_collision_sweep_result_v2_hash,
)
from mechcad_harness.multi_joint_pair_scope import (
    EXACT_CONSTITUENT_PAIR_SCOPE_VERSION,
    ExactConstituentPair,
    canonical_exact_pair_scope,
    exact_pair_scope_hash,
)
from mechcad_harness.multi_joint_kinematics import (
    KinematicRigidBody,
    KinematicRigidBodyMember,
    KinematicModelV2,
    KinematicJointKind,
    JointConfiguration,
    MultiJointKinematicsService,
    RevoluteJointModelV2,
    RIGID_TRANSFORM_AGREEMENT_POLICY,
    RIGID_TRANSFORM_AGREEMENT_VERSION,
    RIGID_TRANSFORM_ORIENTATION_ABS_TOL_RAD,
    RIGID_TRANSFORM_TRANSLATION_ABS_TOL_MM,
    kinematic_rigid_body_hash,
    kinematic_model_hash,
    kinematic_model_wire_payload,
    parse_kinematic_model,
    parse_revolute_joint_model,
    rigid_transform_agrees,
    transform_compose,
    transform_inverse,
    body_by_member_id,
    validate_v2_body_assembly_agreement,
    validate_v2_exact_pair_scope,
    _build_v2_kinematic_topology,
)
from mechcad_harness.transient_assembly_analysis import TransientAssemblyAnalysisService


def _orientation_metric(first: CadRigidTransform, second: CadRigidTransform) -> float:
    first_q = normalize_quaternion(first.rotation_quaternion)
    second_q = normalize_quaternion(second.rotation_quaternion)
    dot = abs(sum(a * b for a, b in zip(first_q, second_q)))
    clamped_dot = min(1.0, max(0.0, dot))
    return 2.0 * math.acos(clamped_dot)


def _orientation_boundary_transforms() -> tuple[CadRigidTransform, CadRigidTransform]:
    first = CadRigidTransform()
    low = 0.0
    high = 2.0e-7
    for _ in range(256):
        midpoint = (low + high) / 2.0
        candidate = CadRigidTransform(
            rotation_quaternion=(
                math.cos(midpoint / 2.0),
                math.sin(midpoint / 2.0),
                0.0,
                0.0,
            )
        )
        if _orientation_metric(first, candidate) <= RIGID_TRANSFORM_ORIENTATION_ABS_TOL_RAD:
            low = midpoint
        else:
            high = midpoint

    for _ in range(1024):
        next_theta = math.nextafter(low, math.inf)
        low_transform = CadRigidTransform(
            rotation_quaternion=(
                math.cos(low / 2.0),
                math.sin(low / 2.0),
                0.0,
                0.0,
            )
        )
        high_transform = CadRigidTransform(
            rotation_quaternion=(
                math.cos(next_theta / 2.0),
                math.sin(next_theta / 2.0),
                0.0,
                0.0,
            )
        )
        low_metric = _orientation_metric(first, low_transform)
        high_metric = _orientation_metric(first, high_transform)
        if (
            low_metric <= RIGID_TRANSFORM_ORIENTATION_ABS_TOL_RAD
            and high_metric > RIGID_TRANSFORM_ORIENTATION_ABS_TOL_RAD
        ):
            return low_transform, high_transform
        low = next_theta

    raise AssertionError("bounded nextafter search did not find orientation boundary")


def test_transform_agreement_accepts_literal_identity():
    assert rigid_transform_agrees(CadRigidTransform(), CadRigidTransform())


def test_transform_agreement_accepts_arbitrary_normalized_quaternion_round_trip():
    transform = CadRigidTransform(
        x_mm=17.25,
        y_mm=-8.5,
        z_mm=3.75,
        rotation_quaternion=(0.31, -0.42, 0.57, 0.63),
    )
    identity = transform_compose(transform, transform_inverse(transform))

    assert rigid_transform_agrees(identity, CadRigidTransform())


def test_transform_agreement_accepts_observed_floating_reconstruction():
    parent = CadRigidTransform(
        x_mm=13.7,
        y_mm=-4.2,
        z_mm=9.1,
        rotation_quaternion=(0.91, 0.12, -0.27, 0.29),
    )
    child = CadRigidTransform(
        x_mm=44.3,
        y_mm=18.4,
        z_mm=-2.6,
        rotation_quaternion=(0.83, -0.19, 0.41, 0.33),
    )
    reconstructed = transform_compose(
        parent,
        transform_compose(transform_inverse(parent), child),
    )

    assert reconstructed != child
    assert rigid_transform_agrees(child, reconstructed)


def test_transform_agreement_accepts_quaternion_sign_equivalence():
    quaternion = (0.31, -0.42, 0.57, 0.63)
    first = CadRigidTransform.model_construct(rotation_quaternion=quaternion)
    second = CadRigidTransform.model_construct(
        rotation_quaternion=tuple(-value for value in quaternion)
    )

    assert rigid_transform_agrees(first, second)


def test_transform_agreement_rejects_nonfinite_model_constructed_input():
    nonfinite = CadRigidTransform.model_construct(x_mm=math.nan)

    assert not rigid_transform_agrees(CadRigidTransform(), nonfinite)


def test_transform_agreement_rejects_materially_incorrect_placement():
    first = CadRigidTransform(x_mm=10.0)
    second = CadRigidTransform(x_mm=10.01)

    assert not rigid_transform_agrees(first, second)


def test_transform_agreement_translation_tolerance_is_inclusive():
    first = CadRigidTransform()
    at_boundary = CadRigidTransform(x_mm=RIGID_TRANSFORM_TRANSLATION_ABS_TOL_MM)
    beyond_boundary = CadRigidTransform(
        x_mm=math.nextafter(RIGID_TRANSFORM_TRANSLATION_ABS_TOL_MM, math.inf)
    )

    assert rigid_transform_agrees(first, at_boundary)
    assert not rigid_transform_agrees(first, beyond_boundary)


def test_transform_agreement_orientation_tolerance_is_inclusive():
    first = CadRigidTransform()
    at_boundary, beyond_boundary = _orientation_boundary_transforms()

    assert _orientation_metric(first, at_boundary) <= RIGID_TRANSFORM_ORIENTATION_ABS_TOL_RAD
    assert _orientation_metric(first, beyond_boundary) > RIGID_TRANSFORM_ORIENTATION_ABS_TOL_RAD
    assert rigid_transform_agrees(first, at_boundary)
    assert not rigid_transform_agrees(first, beyond_boundary)


def test_transform_agreement_policy_is_frozen_and_constant_backed():
    assert RIGID_TRANSFORM_AGREEMENT_POLICY == type(RIGID_TRANSFORM_AGREEMENT_POLICY)(
        version=RIGID_TRANSFORM_AGREEMENT_VERSION,
        translation_metric="componentwise-max-absolute-mm",
        translation_abs_tol_mm=RIGID_TRANSFORM_TRANSLATION_ABS_TOL_MM,
        orientation_metric="sign-invariant-unit-quaternion-angle-rad",
        orientation_abs_tol_rad=RIGID_TRANSFORM_ORIENTATION_ABS_TOL_RAD,
    )
    with pytest.raises((TypeError, AttributeError)):
        RIGID_TRANSFORM_AGREEMENT_POLICY.version = "changed"


def test_transform_agreement_rejects_unknown_policy_version():
    with pytest.raises(ValueError, match="unsupported rigid transform agreement version"):
        rigid_transform_agrees(
            CadRigidTransform(),
            CadRigidTransform(),
            policy_version="unknown@1.0",
        )


def _body_members(*, second_offset: CadRigidTransform | None = None):
    return (
        KinematicRigidBodyMember(
            member_instance_id="member-a",
            reference_to_member_home=CadRigidTransform(),
        ),
        KinematicRigidBodyMember(
            member_instance_id="member-b",
            reference_to_member_home=second_offset or CadRigidTransform(x_mm=12.5),
        ),
    )


def _body(
    *,
    body_id="body-1",
    reference_member_instance_id="member-a",
    members=None,
    body_hash="pending",
):
    return KinematicRigidBody(
        body_id=body_id,
        reference_member_instance_id=reference_member_instance_id,
        members=_body_members() if members is None else members,
        body_hash=body_hash,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("body_id", ""),
        ("body_id", "   "),
        ("reference_member_instance_id", ""),
        ("reference_member_instance_id", "\t"),
    ),
)
def test_rigid_body_rejects_blank_body_and_reference_ids(field, value):
    kwargs = {field: value}

    with pytest.raises(ValueError):
        _body(**kwargs)


def test_rigid_body_member_rejects_blank_member_id():
    with pytest.raises(ValueError):
        KinematicRigidBodyMember(
            member_instance_id="  ",
            reference_to_member_home=CadRigidTransform(),
        )


def test_rigid_body_rejects_empty_members():
    with pytest.raises(ValueError, match="at least one member"):
        _body(members=())


def test_rigid_body_rejects_duplicate_members_before_canonicalization():
    members = _body_members() + (
        KinematicRigidBodyMember(
            member_instance_id="member-a",
            reference_to_member_home=CadRigidTransform(),
        ),
    )

    with pytest.raises(ValueError, match="duplicate member"):
        _body(members=members)


def test_rigid_body_rejects_missing_reference_member():
    with pytest.raises(ValueError, match="reference member"):
        _body(reference_member_instance_id="missing")


def test_rigid_body_rejects_reference_member_occurring_more_than_once():
    members = (
        KinematicRigidBodyMember(
            member_instance_id="member-a",
            reference_to_member_home=CadRigidTransform(),
        ),
        KinematicRigidBodyMember(
            member_instance_id="member-a",
            reference_to_member_home=CadRigidTransform(),
        ),
    )

    with pytest.raises(ValueError, match="duplicate member"):
        _body(members=members)


def test_rigid_body_requires_literal_identity_reference_offset():
    members = (
        KinematicRigidBodyMember(
            member_instance_id="member-a",
            reference_to_member_home=CadRigidTransform(x_mm=1e-12),
        ),
        KinematicRigidBodyMember(
            member_instance_id="member-b",
            reference_to_member_home=CadRigidTransform(x_mm=12.5),
        ),
    )

    with pytest.raises(ValueError, match="reference member offset"):
        _body(members=members)


def test_rigid_body_canonicalizes_members_by_instance_id():
    members = tuple(reversed(_body_members()))

    body = _body(members=members)

    assert tuple(member.member_instance_id for member in body.members) == (
        "member-a",
        "member-b",
    )
    assert body == _body()
    assert body.body_hash == kinematic_rigid_body_hash(body)


def test_rigid_body_hash_changes_for_body_id():
    assert _body().body_hash != _body(body_id="body-2").body_hash


def test_rigid_body_hash_changes_for_reference_member():
    members = (
        KinematicRigidBodyMember(
            member_instance_id="member-a",
            reference_to_member_home=CadRigidTransform(),
        ),
        KinematicRigidBodyMember(
            member_instance_id="member-b",
            reference_to_member_home=CadRigidTransform(),
        ),
    )

    assert _body(members=members).body_hash != _body(
        reference_member_instance_id="member-b", members=members
    ).body_hash


def test_rigid_body_hash_changes_for_member_membership():
    assert _body().body_hash != _body(
        members=(
            KinematicRigidBodyMember(
                member_instance_id="member-a",
                reference_to_member_home=CadRigidTransform(),
            ),
        )
    ).body_hash


def test_rigid_body_hash_changes_for_exact_offset_value():
    assert _body().body_hash != _body(
        members=_body_members(
            second_offset=CadRigidTransform(x_mm=math.nextafter(12.5, math.inf))
        )
    ).body_hash


def test_rigid_body_rejects_supplied_hash_mismatch():
    with pytest.raises(ValueError, match="body hash mismatch"):
        _body(body_hash="sha256:" + "0" * 64)


def test_rigid_body_member_mutation_cannot_change_its_identity_or_offset():
    offset = CadRigidTransform(x_mm=12.5)
    member = KinematicRigidBodyMember(
        member_instance_id="member-b",
        reference_to_member_home=offset,
    )
    original = member.model_dump(mode="json")

    with pytest.raises((TypeError, ValidationError)):
        member.member_instance_id = "changed"
    with pytest.raises((TypeError, ValidationError)):
        member.reference_to_member_home = CadRigidTransform()
    with pytest.raises((TypeError, ValidationError)):
        member.reference_to_member_home.x_mm = 99.0

    offset.x_mm = 99.0

    assert member.model_dump(mode="json") == original
    assert member.member_instance_id == "member-b"
    assert member.reference_to_member_home == CadRigidTransform(x_mm=12.5)


def test_rigid_body_mutation_cannot_change_membership_reference_or_body_hash():
    body = _body()
    original = body.model_dump(mode="json")
    original_hash = body.body_hash

    with pytest.raises((TypeError, ValidationError)):
        body.body_id = "changed"
    with pytest.raises((TypeError, ValidationError)):
        body.reference_member_instance_id = "member-b"
    with pytest.raises((TypeError, ValidationError)):
        body.members = tuple(reversed(body.members))
    with pytest.raises((TypeError, ValidationError)):
        body.body_hash = "sha256:" + "0" * 64
    with pytest.raises((TypeError, ValidationError)):
        body.members[0].member_instance_id = "changed"
    with pytest.raises((TypeError, ValidationError)):
        body.members[1].reference_to_member_home.x_mm = 99.0

    assert body.model_dump(mode="json") == original
    assert body.body_hash == original_hash == kinematic_rigid_body_hash(body)
    assert tuple(member.member_instance_id for member in body.members) == (
        "member-a",
        "member-b",
    )
    assert body.members[0].reference_to_member_home == CadRigidTransform()


def _v2_joint(*, joint_id="J1", parent_body_id="body-1", child_body_id="body-2"):
    return RevoluteJointModelV2(
        joint_id=joint_id,
        joint_kind=KinematicJointKind.REVOLUTE,
        parent_body_id=parent_body_id,
        child_body_id=child_body_id,
    )


def _v2_model(*, bodies=None, joints=None, **joint_kwargs):
    if bodies is None:
        bodies = (_body(body_id="body-1"), _body(body_id="body-2"))
    if joints is None:
        joints = (_v2_joint(**joint_kwargs),)
    return KinematicModelV2(model_id="model-v2", bodies=tuple(bodies), joints=tuple(joints))


_VALIDATION_PART = CadPartProgram(
    part_id="validation-part",
    operations=(
        BasePlateOperation(
            operation_id="base", length_mm=1, width_mm=1, thickness_mm=1
        ),
    ),
)


def _validation_assembly(*instances):
    return CadAssemblyProgram(
        assembly_id="validation-assembly",
        parts=(_VALIDATION_PART,),
        instances=tuple(
            CadComponentInstance(instance_id=instance_id, part_id="validation-part", placement=placement)
            for instance_id, placement in instances
        ),
    )


def _validation_body(
    *,
    body_id="body-1",
    reference_member_instance_id="member-a",
    members=None,
    second_offset=None,
):
    return KinematicRigidBody(
        body_id=body_id,
        reference_member_instance_id=reference_member_instance_id,
        members=tuple(
            members
            or _body_members(
                second_offset=second_offset
                if second_offset is not None
                else CadRigidTransform(x_mm=12.5)
            )
        ),
    )


def _validation_model(*bodies):
    return KinematicModelV2(model_id="validation-model", bodies=tuple(bodies), joints=())


def test_v2_body_assembly_agreement_rejects_unknown_member_with_sorted_diagnostic():
    assembly = _validation_assembly(("member-a", CadRigidTransform()))
    body = _validation_body(
        members=(
            KinematicRigidBodyMember(
                member_instance_id="member-a",
                reference_to_member_home=CadRigidTransform(),
            ),
            KinematicRigidBodyMember(
                member_instance_id="unknown-member",
                reference_to_member_home=CadRigidTransform(x_mm=1),
            ),
        )
    )

    with pytest.raises(ValueError, match=r"unknown=\['unknown-member'\]"):
        validate_v2_body_assembly_agreement(assembly, _validation_model(body))


def test_v2_body_assembly_agreement_rejects_extra_and_missing_members_sorted():
    assembly = _validation_assembly(
        ("assembly-2", CadRigidTransform()),
        ("assembly-1", CadRigidTransform(x_mm=1)),
    )
    body = _validation_body(
        reference_member_instance_id="declared-1",
        members=(
            KinematicRigidBodyMember(
                member_instance_id="declared-2",
                reference_to_member_home=CadRigidTransform(x_mm=1),
            ),
            KinematicRigidBodyMember(
                member_instance_id="declared-1",
                reference_to_member_home=CadRigidTransform(),
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match=r"unknown=\['declared-1', 'declared-2'\].*missing=\['assembly-1', 'assembly-2'\]",
    ):
        validate_v2_body_assembly_agreement(assembly, _validation_model(body))


def test_v2_body_assembly_agreement_rejects_duplicate_membership_across_bodies():
    assembly = _validation_assembly(
        ("member-a", CadRigidTransform()),
        ("member-b", CadRigidTransform(x_mm=1)),
    )
    body_one = _validation_body(
        body_id="body-1",
        members=(
            KinematicRigidBodyMember(
                member_instance_id="member-a",
                reference_to_member_home=CadRigidTransform(),
            ),
        ),
    )
    body_two = _validation_body(
        body_id="body-2",
        members=(
            KinematicRigidBodyMember(
                member_instance_id="member-a",
                reference_to_member_home=CadRigidTransform(),
            ),
        ),
    )

    with pytest.raises(ValueError, match="multiple bodies"):
        validate_v2_body_assembly_agreement(assembly, _validation_model(body_one, body_two))


def test_v2_body_assembly_agreement_rejects_duplicate_body_ids_even_if_model_is_unvalidated():
    assembly = _validation_assembly(("member-a", CadRigidTransform()))
    body = _validation_body(
        members=(
            KinematicRigidBodyMember(
                member_instance_id="member-a",
                reference_to_member_home=CadRigidTransform(),
            ),
        )
    )
    model = KinematicModelV2.model_construct(
        model_id="validation-model",
        bodies=(body, body.model_copy(update={"body_id": "body-1"})),
        joints=(),
        evaluator_version="multi-joint-forward-kinematics@2.0",
        transform_agreement_version=RIGID_TRANSFORM_AGREEMENT_VERSION,
    )

    with pytest.raises(ValueError, match=r"duplicate body IDs.*body-1"):
        validate_v2_body_assembly_agreement(assembly, model)


def test_v2_body_assembly_agreement_rejects_reference_offset_mismatch():
    assembly = _validation_assembly(("member-a", CadRigidTransform()))
    reference = KinematicRigidBodyMember(
        member_instance_id="member-a",
        reference_to_member_home=CadRigidTransform(x_mm=1),
    )
    body = KinematicRigidBody.model_construct(
        schema_version="kinematic-rigid-body@1",
        body_id="body-1",
        reference_member_instance_id="member-a",
        members=(reference,),
        body_hash="pending",
    )
    model = KinematicModelV2.model_construct(
        model_id="validation-model",
        bodies=(body,),
        joints=(),
        evaluator_version="multi-joint-forward-kinematics@2.0",
        transform_agreement_version=RIGID_TRANSFORM_AGREEMENT_VERSION,
    )

    with pytest.raises(ValueError, match="rigid body hashes must be finalized"):
        validate_v2_body_assembly_agreement(assembly, model)


def test_v2_body_assembly_agreement_rejects_meaningful_non_reference_offset_mismatch():
    assembly = _validation_assembly(
        ("member-a", CadRigidTransform()),
        ("member-b", CadRigidTransform(x_mm=99)),
    )
    body = _validation_body(second_offset=CadRigidTransform(x_mm=12.5))

    with pytest.raises(ValueError, match="home placement disagrees"):
        validate_v2_body_assembly_agreement(assembly, _validation_model(body))


def test_v2_body_assembly_agreement_accepts_arbitrary_quaternion_composed_offset():
    reference_placement = CadRigidTransform(
        x_mm=17.25,
        y_mm=-8.5,
        z_mm=3.75,
        rotation_quaternion=(0.31, -0.42, 0.57, 0.63),
    )
    member_offset = CadRigidTransform(
        x_mm=12.5,
        y_mm=-4.0,
        z_mm=2.25,
        rotation_quaternion=(0.71, 0.11, -0.23, 0.65),
    )
    member_placement = transform_compose(reference_placement, member_offset)
    assembly = _validation_assembly(
        ("member-a", reference_placement),
        ("member-b", member_placement),
    )
    body = _validation_body(second_offset=member_offset)

    result = validate_v2_body_assembly_agreement(assembly, _validation_model(body))

    assert result == {"member-a": body, "member-b": body}
    assert body_by_member_id(_validation_model(body)) == result


def test_v2_model_canonicalizes_body_and_joint_tuples():
    model = _v2_model(
        bodies=(_body(body_id="body-2"), _body(body_id="body-1")),
        joints=(_v2_joint(joint_id="J2"), _v2_joint(joint_id="J1")),
    )

    assert tuple(body.body_id for body in model.bodies) == ("body-1", "body-2")
    assert tuple(joint.joint_id for joint in model.joints) == ("J1", "J2")


def test_v2_model_rejects_duplicate_body_and_joint_ids_before_sorting():
    with pytest.raises(ValueError, match="duplicate body IDs"):
        _v2_model(bodies=(_body(body_id="body-1"), _body(body_id="body-1")))
    with pytest.raises(ValueError, match="duplicate joint IDs"):
        _v2_model(joints=(_v2_joint(), _v2_joint()))


def test_v2_model_wire_dump_and_hash_ignore_body_member_and_joint_order():
    body_one = _body(body_id="body-1")
    body_two = _body(body_id="body-2")
    model = _v2_model(
        bodies=(body_two, body_one),
        joints=(_v2_joint(joint_id="J2"), _v2_joint(joint_id="J1")),
    )
    reordered = _v2_model(
        bodies=(
            KinematicRigidBody(
                body_id="body-1",
                reference_member_instance_id="member-a",
                members=tuple(reversed(body_one.members)),
            ),
            body_two,
        ),
        joints=(_v2_joint(joint_id="J1"), _v2_joint(joint_id="J2")),
    )

    assert model.model_dump(mode="json") == reordered.model_dump(mode="json")
    assert kinematic_model_wire_payload(model) == kinematic_model_wire_payload(reordered)
    assert kinematic_model_hash(model) == kinematic_model_hash(reordered)


@pytest.mark.parametrize(
    ("change", "expected_different"),
    (
        ("body", True),
        ("member", True),
        ("endpoint", True),
        ("axis", True),
        ("limit", True),
    ),
)
def test_v2_model_hash_changes_for_each_semantic_change(change, expected_different):
    baseline = _v2_model()
    if change == "body":
        changed = _v2_model(bodies=(_body(body_id="body-1"), _body(body_id="body-X")))
    elif change == "member":
        changed_body = _body(
            body_id="body-1",
            members=(
                KinematicRigidBodyMember(
                    member_instance_id="member-a",
                    reference_to_member_home=CadRigidTransform(),
                ),
                KinematicRigidBodyMember(
                    member_instance_id="member-X",
                    reference_to_member_home=CadRigidTransform(x_mm=12.5),
                ),
            ),
        )
        changed = _v2_model(bodies=(changed_body, _body(body_id="body-2")))
    elif change == "endpoint":
        changed = _v2_model(child_body_id="body-X")
    elif change == "axis":
        changed_joint = _v2_joint()
        changed_joint = changed_joint.model_copy(update={"axis_direction_x": 1.0})
        changed = _v2_model(joints=(changed_joint,))
    else:
        changed_joint = _v2_joint()
        changed_joint = changed_joint.model_copy(update={"min_angle_deg": -10.0})
        changed = _v2_model(joints=(changed_joint,))

    assert (kinematic_model_hash(baseline) != kinematic_model_hash(changed)) is expected_different


def test_v2_model_hash_changes_for_joint_id():
    assert kinematic_model_hash(_v2_model(joint_id="J1")) != kinematic_model_hash(
        _v2_model(joint_id="JX")
    )


def test_v2_model_hash_changes_for_agreement_version():
    baseline = _v2_model()
    changed = baseline.model_copy(
        update={"transform_agreement_version": "rigid-transform-agreement@2.0"}
    )

    with pytest.raises(ValueError):
        kinematic_model_hash(changed)


def test_explicit_joint_parser_rejects_unknown_schema_version():
    payload = _v2_joint().model_dump(mode="json")
    payload["schema_version"] = "revolute-joint-model@999"

    with pytest.raises(ValueError, match="unsupported revolute joint model schema"):
        parse_revolute_joint_model(payload)


def test_explicit_kinematic_model_parser_rejects_unknown_schema_version():
    payload = _v2_model().model_dump(mode="json")
    payload["schema_version"] = "kinematic-model@999"

    with pytest.raises(ValueError, match="unsupported kinematic model schema"):
        parse_kinematic_model(payload)


def _grouped_fk_fixture(*, branching: bool = False):
    root_home = CadRigidTransform(
        x_mm=17.25,
        y_mm=-8.5,
        z_mm=3.75,
        rotation_quaternion=(0.31, -0.42, 0.57, 0.63),
    )
    root_second_offset = CadRigidTransform(
        x_mm=2.0,
        y_mm=4.0,
        rotation_quaternion=(0.71, 0.11, -0.23, 0.65),
    )
    articulated_home = CadRigidTransform(x_mm=30.0)
    articulated_second_offset = CadRigidTransform(
        x_mm=1.5,
        y_mm=3.0,
        rotation_quaternion=(0.83, -0.19, 0.41, 0.33),
    )
    output_home = CadRigidTransform(x_mm=80.0)
    output_second_offset = CadRigidTransform(
        x_mm=-2.0,
        y_mm=2.5,
        rotation_quaternion=(0.91, 0.12, -0.27, 0.29),
    )

    def member(instance_id, reference_to_home):
        return KinematicRigidBodyMember(
            member_instance_id=instance_id,
            reference_to_member_home=reference_to_home,
        )

    bodies = (
        KinematicRigidBody(
            body_id="R",
            reference_member_instance_id="R1",
            members=(member("R1", CadRigidTransform()), member("R2", root_second_offset)),
        ),
        KinematicRigidBody(
            body_id="A",
            reference_member_instance_id="A1",
            members=(
                member("A1", CadRigidTransform()),
                member("A2", articulated_second_offset),
            ),
        ),
        KinematicRigidBody(
            body_id="B",
            reference_member_instance_id="B1",
            members=(member("B1", CadRigidTransform()), member("B2", output_second_offset)),
        ),
    )
    instances = (
        ("B2", transform_compose(root_home, transform_compose(output_home, output_second_offset))),
        ("R2", transform_compose(root_home, root_second_offset)),
        ("A1", transform_compose(root_home, articulated_home)),
        ("B1", transform_compose(root_home, output_home)),
        ("R1", root_home),
        ("A2", transform_compose(root_home, transform_compose(articulated_home, articulated_second_offset))),
    )
    assembly = _validation_assembly(*instances)
    joints = (
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
    )
    if branching:
        joints = (
            RevoluteJointModelV2(
                joint_id="J2",
                joint_kind=KinematicJointKind.REVOLUTE,
                parent_body_id="R",
                child_body_id="B",
            ),
            RevoluteJointModelV2(
                joint_id="J1",
                joint_kind=KinematicJointKind.REVOLUTE,
                parent_body_id="R",
                child_body_id="A",
            ),
        )
    return assembly, KinematicModelV2(model_id="grouped-model", bodies=bodies, joints=joints)


def _grouped_fk_result(assembly, model, **positions):
    return MultiJointKinematicsService().evaluate(
        assembly,
        model,
        JointConfiguration(model_id=model.model_id, positions=positions),
    )


def test_v2_fk_projects_serial_body_members_in_source_order_and_propagates_joints():
    assembly, model = _grouped_fk_fixture()
    zero = _grouped_fk_result(assembly, model, J1=0.0, J2=0.0)
    j1_only = _grouped_fk_result(assembly, model, J1=90.0, J2=0.0)
    j2_only = _grouped_fk_result(assembly, model, J1=0.0, J2=90.0)
    combined = _grouped_fk_result(assembly, model, J1=30.0, J2=45.0)

    expected_order = tuple(instance.instance_id for instance in assembly.instances)
    assert tuple(item.instance_id for item in zero.instance_world_transforms) == expected_order
    assert tuple(instance.instance_id for instance in zero.transformed_assembly.instances) == expected_order

    zero_transforms = {item.instance_id: item.transform for item in zero.instance_world_transforms}
    j1_transforms = {item.instance_id: item.transform for item in j1_only.instance_world_transforms}
    j2_transforms = {item.instance_id: item.transform for item in j2_only.instance_world_transforms}
    combined_transforms = {item.instance_id: item.transform for item in combined.instance_world_transforms}

    for instance_id in ("R1", "R2"):
        assert rigid_transform_agrees(j1_transforms[instance_id], zero_transforms[instance_id])
        assert rigid_transform_agrees(j2_transforms[instance_id], zero_transforms[instance_id])
        assert rigid_transform_agrees(combined_transforms[instance_id], zero_transforms[instance_id])

    for instance_id in ("A1", "A2", "B1", "B2"):
        assert not rigid_transform_agrees(j1_transforms[instance_id], zero_transforms[instance_id])
    for instance_id in ("A1", "A2"):
        assert rigid_transform_agrees(j2_transforms[instance_id], zero_transforms[instance_id])
    for instance_id in ("B1", "B2"):
        assert not rigid_transform_agrees(j2_transforms[instance_id], zero_transforms[instance_id])
        assert not rigid_transform_agrees(combined_transforms[instance_id], zero_transforms[instance_id])

    assert all(item.is_articulated is False for item in zero.instance_world_transforms if item.instance_id in ("R1", "R2"))
    assert all(item.is_articulated is True for item in zero.instance_world_transforms if item.instance_id not in ("R1", "R2"))


def test_v2_fk_preserves_relative_member_poses_under_serial_motion():
    assembly, model = _grouped_fk_fixture()
    source = {instance.instance_id: instance.placement for instance in assembly.instances}

    for result in (
        _grouped_fk_result(assembly, model, J1=0.0, J2=0.0),
        _grouped_fk_result(assembly, model, J1=30.0, J2=45.0),
    ):
        transforms = {item.instance_id: item.transform for item in result.instance_world_transforms}
        for first, second in (("R1", "R2"), ("A1", "A2"), ("B1", "B2")):
            source_relative = transform_compose(transform_inverse(source[first]), source[second])
            result_relative = transform_compose(
                transform_inverse(transforms[first]), transforms[second]
            )
            assert rigid_transform_agrees(source_relative, result_relative)


def test_v2_fk_q0_accepts_arbitrary_quaternion_round_trip_without_hash_substitution():
    assembly, model = _grouped_fk_fixture()

    result = _grouped_fk_result(assembly, model, J1=0.0, J2=0.0)

    assert result.source_assembly_hash != result.transformed_assembly_hash
    source = {instance.instance_id: instance.placement for instance in assembly.instances}
    for item in result.instance_world_transforms:
        assert rigid_transform_agrees(source[item.instance_id], item.transform)


def test_v2_body_topology_uses_sorted_roots_and_breadth_first_joint_order():
    assembly, model = _grouped_fk_fixture(branching=True)

    topology = _build_v2_kinematic_topology(assembly, model)

    assert topology.roots == ("R",)
    assert tuple(joint.joint_id for joint in topology.evaluation_order) == ("J1", "J2")
    assert topology.articulated_children == frozenset({"A", "B"})


def _forest_fk_fixture():
    def member(instance_id, reference_to_home):
        return KinematicRigidBodyMember(
            member_instance_id=instance_id,
            reference_to_member_home=reference_to_home,
        )

    root_a_home = CadRigidTransform(
        x_mm=12.0,
        y_mm=5.0,
        z_mm=1.0,
        rotation_quaternion=(0.91, 0.12, -0.27, 0.29),
    )
    root_a_second_offset = CadRigidTransform(
        x_mm=2.0,
        y_mm=-3.0,
        rotation_quaternion=(0.83, -0.19, 0.41, 0.33),
    )
    arm_a_home = CadRigidTransform(
        x_mm=45.0,
        y_mm=10.0,
        z_mm=2.0,
        rotation_quaternion=(0.71, 0.11, -0.23, 0.65),
    )
    arm_a_second_offset = CadRigidTransform(x_mm=1.5, y_mm=4.0)
    root_z_home = CadRigidTransform(
        x_mm=-18.0,
        y_mm=42.0,
        z_mm=-2.0,
        rotation_quaternion=(0.89, -0.21, 0.17, 0.34),
    )
    root_z_second_offset = CadRigidTransform(x_mm=-2.5, y_mm=2.0)
    arm_z_home = CadRigidTransform(
        x_mm=-18.0,
        y_mm=78.0,
        z_mm=-1.0,
        rotation_quaternion=(0.78, 0.18, 0.44, 0.39),
    )
    arm_z_second_offset = CadRigidTransform(x_mm=3.0, y_mm=-1.0)

    bodies = (
        KinematicRigidBody(
            body_id="root-z",
            reference_member_instance_id="root-z-1",
            members=(
                member("root-z-1", CadRigidTransform()),
                member("root-z-2", root_z_second_offset),
            ),
        ),
        KinematicRigidBody(
            body_id="arm-a",
            reference_member_instance_id="arm-a-1",
            members=(
                member("arm-a-1", CadRigidTransform()),
                member("arm-a-2", arm_a_second_offset),
            ),
        ),
        KinematicRigidBody(
            body_id="root-a",
            reference_member_instance_id="root-a-1",
            members=(
                member("root-a-1", CadRigidTransform()),
                member("root-a-2", root_a_second_offset),
            ),
        ),
        KinematicRigidBody(
            body_id="arm-z",
            reference_member_instance_id="arm-z-1",
            members=(
                member("arm-z-1", CadRigidTransform()),
                member("arm-z-2", arm_z_second_offset),
            ),
        ),
    )
    instances = (
        ("arm-z-2", transform_compose(arm_z_home, arm_z_second_offset)),
        ("root-a-2", transform_compose(root_a_home, root_a_second_offset)),
        ("arm-a-1", arm_a_home),
        ("root-z-1", root_z_home),
        ("arm-a-2", transform_compose(arm_a_home, arm_a_second_offset)),
        ("root-z-2", transform_compose(root_z_home, root_z_second_offset)),
        ("root-a-1", root_a_home),
        ("arm-z-1", arm_z_home),
    )
    assembly = _validation_assembly(*instances)
    model = KinematicModelV2(
        model_id="forest-model",
        bodies=bodies,
        joints=(
            RevoluteJointModelV2(
                joint_id="joint-z",
                joint_kind=KinematicJointKind.REVOLUTE,
                parent_body_id="root-z",
                child_body_id="arm-z",
            ),
            RevoluteJointModelV2(
                joint_id="joint-a",
                joint_kind=KinematicJointKind.REVOLUTE,
                parent_body_id="root-a",
                child_body_id="arm-a",
            ),
        ),
    )
    return assembly, model


def test_v2_fk_forest_has_deterministic_roots_independent_motion_and_matching_placements():
    assembly, model = _forest_fk_fixture()
    topology = _build_v2_kinematic_topology(assembly, model)

    assert topology.roots == ("root-a", "root-z")
    assert tuple(joint.joint_id for joint in topology.evaluation_order) == (
        "joint-a",
        "joint-z",
    )

    zero = _grouped_fk_result(assembly, model, **{"joint-a": 0.0, "joint-z": 0.0})
    a_only = _grouped_fk_result(assembly, model, **{"joint-a": 45.0, "joint-z": 0.0})
    z_only = _grouped_fk_result(assembly, model, **{"joint-a": 0.0, "joint-z": -30.0})

    expected_order = tuple(instance.instance_id for instance in assembly.instances)
    for result in (zero, a_only, z_only):
        assert tuple(item.instance_id for item in result.instance_world_transforms) == expected_order
        assert tuple(instance.instance_id for instance in result.transformed_assembly.instances) == expected_order
        for instance, world_transform in zip(
            result.transformed_assembly.instances,
            result.instance_world_transforms,
        ):
            assert instance.instance_id == world_transform.instance_id
            assert rigid_transform_agrees(instance.placement, world_transform.transform)

    zero_transforms = {item.instance_id: item.transform for item in zero.instance_world_transforms}
    a_transforms = {item.instance_id: item.transform for item in a_only.instance_world_transforms}
    z_transforms = {item.instance_id: item.transform for item in z_only.instance_world_transforms}

    for instance_id in ("root-a-1", "root-a-2", "root-z-1", "root-z-2"):
        assert rigid_transform_agrees(a_transforms[instance_id], zero_transforms[instance_id])
        assert rigid_transform_agrees(z_transforms[instance_id], zero_transforms[instance_id])
    for instance_id in ("arm-a-1", "arm-a-2"):
        assert not rigid_transform_agrees(a_transforms[instance_id], zero_transforms[instance_id])
        assert rigid_transform_agrees(z_transforms[instance_id], zero_transforms[instance_id])
    for instance_id in ("arm-z-1", "arm-z-2"):
        assert rigid_transform_agrees(a_transforms[instance_id], zero_transforms[instance_id])
        assert not rigid_transform_agrees(z_transforms[instance_id], zero_transforms[instance_id])


@pytest.mark.parametrize(
    ("change", "match"),
    (
        ("missing-parent", "parent body"),
        ("missing-child", "child body"),
        ("same-body", "parent == child"),
        ("two-parents", "two parent joints"),
        ("cycle", "cycle"),
    ),
)
def test_v2_body_topology_rejects_invalid_graphs(change, match):
    assembly, model = _grouped_fk_fixture()
    if change == "missing-parent":
        joint = model.joints[0].model_copy(update={"parent_body_id": "missing"})
        model = model.model_copy(update={"joints": (joint, model.joints[1])})
    elif change == "missing-child":
        joint = model.joints[0].model_copy(update={"child_body_id": "missing"})
        model = model.model_copy(update={"joints": (joint, model.joints[1])})
    elif change == "same-body":
        joint = model.joints[0].model_copy(update={"child_body_id": "R"})
        model = model.model_copy(update={"joints": (joint, model.joints[1])})
    elif change == "two-parents":
        joint = model.joints[1].model_copy(update={"parent_body_id": "B", "child_body_id": "A"})
        model = model.model_copy(update={"joints": (model.joints[0], joint)})
    else:
        model = model.model_copy(
            update={
                "joints": (
                    model.joints[0].model_copy(update={"parent_body_id": "B", "child_body_id": "A"}),
                    model.joints[1].model_copy(update={"parent_body_id": "A", "child_body_id": "B"}),
                )
            }
        )

    with pytest.raises(ValueError, match=match):
        _build_v2_kinematic_topology(assembly, model)


def test_exact_pair_normalizes_reversed_operands_before_validation():
    pair = ExactConstituentPair(
        first_instance_id="member-b",
        second_instance_id="member-a",
    )

    assert pair.first_instance_id == "member-a"
    assert pair.second_instance_id == "member-b"
    assert pair.schema_version == "exact-constituent-pair@1"
    assert EXACT_CONSTITUENT_PAIR_SCOPE_VERSION == "exact-constituent-pair-scope@1.0"


def test_exact_pair_scope_canonicalization_makes_caller_tuple_reorder_equivalent():
    first = ExactConstituentPair(first_instance_id="z", second_instance_id="a")
    second = ExactConstituentPair(first_instance_id="d", second_instance_id="b")
    original = (first, second)
    reordered = (second, first)

    assert canonical_exact_pair_scope(original) == (first, second)
    assert canonical_exact_pair_scope(original) == canonical_exact_pair_scope(reordered)
    assert exact_pair_scope_hash(original) == exact_pair_scope_hash(reordered)


def test_exact_pair_scope_is_sorted_by_lexical_pair_key():
    scope = canonical_exact_pair_scope(
        (
            ExactConstituentPair(first_instance_id="z", second_instance_id="y"),
            ExactConstituentPair(first_instance_id="b", second_instance_id="c"),
            ExactConstituentPair(first_instance_id="a", second_instance_id="d"),
        )
    )

    assert tuple(
        (pair.first_instance_id, pair.second_instance_id) for pair in scope
    ) == (("a", "d"), ("b", "c"), ("y", "z"))


def test_exact_pair_rejects_self_pair():
    with pytest.raises(ValueError, match="strictly ordered"):
        ExactConstituentPair(first_instance_id="same", second_instance_id="same")


def test_exact_pair_rejects_post_construction_mutation():
    pair = ExactConstituentPair(first_instance_id="a", second_instance_id="b")

    with pytest.raises(ValidationError):
        pair.first_instance_id = ""


@pytest.mark.parametrize(
    ("update", "match"),
    (
        ({"first_instance_id": ""}, "must not be blank"),
        ({"first_instance_id": "b"}, "strictly ordered"),
    ),
)
def test_exact_pair_scope_revalidates_forged_model_copy(update, match):
    pair = ExactConstituentPair(first_instance_id="a", second_instance_id="b")
    forged = pair.model_copy(update=update)

    with pytest.raises(ValueError, match=match):
        canonical_exact_pair_scope((forged,))


def test_exact_pair_scope_revalidates_adversarial_post_construction_mutation():
    pair = ExactConstituentPair(first_instance_id="a", second_instance_id="b")
    object.__setattr__(pair, "first_instance_id", "")

    with pytest.raises(ValueError, match="must not be blank"):
        canonical_exact_pair_scope((pair,))


@pytest.mark.parametrize("value", ("", "   ", "\t"))
def test_exact_pair_rejects_blank_or_whitespace_instance_ids(value):
    with pytest.raises(ValueError, match="must not be blank"):
        ExactConstituentPair(first_instance_id=value, second_instance_id="other")


def test_exact_pair_scope_rejects_duplicate_unordered_pairs():
    with pytest.raises(ValueError, match="duplicate exact constituent pair"):
        canonical_exact_pair_scope(
            (
                ExactConstituentPair(first_instance_id="a", second_instance_id="b"),
                ExactConstituentPair(first_instance_id="b", second_instance_id="a"),
            )
        )


def test_exact_pair_scope_rejects_empty_scope():
    with pytest.raises(ValueError, match="must not be empty"):
        canonical_exact_pair_scope(())


def _recording_v2_pair_provider(assembly, model, scope, calls):
    validated = validate_v2_exact_pair_scope(assembly, model, scope)
    calls.append(validated)
    return validated


@pytest.mark.parametrize(
    ("pair_ids", "match"),
    (
        (("missing", "R1"), "not in source assembly"),
        (("R1", "missing"), "not in source assembly"),
        (("R1", "R2"), "same rigid body"),
    ),
)
def test_v2_pair_validator_rejects_invalid_scope_before_recording_provider(
    pair_ids, match
):
    assembly, model = _grouped_fk_fixture()
    calls = []
    scope = (ExactConstituentPair(first_instance_id=pair_ids[0], second_instance_id=pair_ids[1]),)

    with pytest.raises(ValueError, match=match):
        _recording_v2_pair_provider(assembly, model, scope, calls)

    assert calls == []


def test_v2_pair_validator_rejects_noncanonical_caller_tuple_order():
    assembly, model = _grouped_fk_fixture()
    first = ExactConstituentPair(first_instance_id="R1", second_instance_id="A1")
    second = ExactConstituentPair(first_instance_id="B1", second_instance_id="A2")

    with pytest.raises(ValueError, match="must be canonical"):
        validate_v2_exact_pair_scope(assembly, model, (second, first))


@pytest.mark.parametrize(
    ("fixture_kwargs", "pair_ids"),
    (
        ({}, ("A2", "B1")),
        ({"branching": True}, ("A1", "B1")),
        ({}, ("A1", "B1")),
    ),
)
def test_v2_pair_validator_allows_cross_body_categories_before_recording_provider(
    fixture_kwargs, pair_ids
):
    assembly, model = _grouped_fk_fixture(**fixture_kwargs)
    calls = []
    pair = ExactConstituentPair(
        first_instance_id=pair_ids[0], second_instance_id=pair_ids[1]
    )

    result = _recording_v2_pair_provider(assembly, model, (pair,), calls)

    assert result == (pair,)
    assert calls == [(pair,)]


def _v2_collision_request(assembly, model, scope, *, configurations=None):
    return MultiJointCollisionSweepRequestV2(
        schema_version="multi-joint-collision-sweep-request@2",
        source_assembly_id=assembly.assembly_id,
        source_assembly_hash=assembly_hash(assembly),
        model=model,
        configurations=configurations
        or (
            JointConfiguration(
                model_id=model.model_id,
                positions={joint.joint_id: 0.0 for joint in model.joints},
            ),
        ),
        exact_pair_scope=scope,
        evaluator_version=MULTI_JOINT_EXACT_COLLISION_SWEEP_V2_VERSION,
    )


def test_v2_collision_request_canonicalizes_scope_and_binds_scope_identity():
    assembly, model = _grouped_fk_fixture()
    first = ExactConstituentPair(first_instance_id="A1", second_instance_id="B1")
    second = ExactConstituentPair(first_instance_id="R1", second_instance_id="A1")

    request = _v2_collision_request(assembly, model, (second, first))
    equivalent = _v2_collision_request(assembly, model, (first, second))
    changed = _v2_collision_request(
        assembly,
        model,
        (ExactConstituentPair(first_instance_id="A2", second_instance_id="B1"),),
    )

    assert request.exact_pair_scope == (first, second)
    assert request.request_hash == equivalent.request_hash
    assert request.request_hash != changed.request_hash
    assert request.model_hash == kinematic_model_hash(model)


def test_v2_collision_scope_rejects_before_fk_or_provider_and_does_not_require_full_scope():
    assembly, model = _grouped_fk_fixture()
    request = _v2_collision_request(
        assembly,
        model,
        (ExactConstituentPair(first_instance_id="R1", second_instance_id="R2"),),
    )
    fk_calls = []
    provider_calls = []

    class RecordingKinematics:
        def evaluate(self, *args):
            fk_calls.append(args)
            return MultiJointKinematicsService().evaluate(*args)

    def exact_measure(received_request, transformed):
        provider_calls.append(received_request)
        return tuple(
            (first_id, second_id, 0.0, 1.0)
            for first_id, second_id in received_request.pairs
        )

    service = MultiJointDiscreteCollisionSweepService(
        TransientAssemblyAnalysisService(exact_measure),
        kinematics_service=RecordingKinematics(),
    )

    with pytest.raises(ValueError, match="same rigid body"):
        service.execute(request, assembly)

    assert fk_calls == []
    assert provider_calls == []


def test_v2_collision_unknown_scope_id_rejects_before_fk_or_provider():
    assembly, model = _grouped_fk_fixture()
    request = _v2_collision_request(
        assembly,
        model,
        (ExactConstituentPair(first_instance_id="A1", second_instance_id="unknown"),),
    )
    fk_calls = []
    provider_calls = []

    class RecordingKinematics:
        def evaluate(self, *args):
            fk_calls.append(args)
            return MultiJointKinematicsService().evaluate(*args)

    def exact_measure(received_request, transformed):
        provider_calls.append(received_request)
        return ()

    service = MultiJointDiscreteCollisionSweepService(
        TransientAssemblyAnalysisService(exact_measure),
        kinematics_service=RecordingKinematics(),
    )

    with pytest.raises(ValueError, match="not in source assembly"):
        service.execute(request, assembly)

    assert fk_calls == []
    assert provider_calls == []


def test_v2_collision_dispatches_canonical_concrete_pairs_and_serializes_neutral_results():
    assembly, model = _grouped_fk_fixture()
    pair = ExactConstituentPair(first_instance_id="A1", second_instance_id="B1")
    request = _v2_collision_request(assembly, model, (pair,))
    observed_pairs = []

    def exact_measure(received_request, transformed):
        observed_pairs.append(received_request.pairs)
        return tuple(
            (first_id, second_id, 0.0, 2.5)
            for first_id, second_id in received_request.pairs
        )

    result = MultiJointDiscreteCollisionSweepService(
        TransientAssemblyAnalysisService(exact_measure)
    ).execute(request, assembly)
    configuration = result.configuration_results[0]
    pair_result = configuration.pair_results[0]

    assert observed_pairs == [(('A1', 'B1'),)]
    assert (pair_result.first_instance_id, pair_result.second_instance_id) == (
        "A1",
        "B1",
    )
    assert "moving_instance_id" not in pair_result.model_dump(mode="json")
    assert "stationary_instance_id" not in pair_result.model_dump(mode="json")
    assert "result_hash" not in configuration.model_dump(mode="json")
    assert result.result_hash == multi_joint_collision_sweep_result_v2_hash(result)


def test_v2_collision_acceptance_records_articulated_articulated_pair_and_fk_placements():
    assembly, model = _grouped_fk_fixture()
    configurations = (
        JointConfiguration(model_id=model.model_id, positions={"J1": 0.0, "J2": 0.0}),
        JointConfiguration(model_id=model.model_id, positions={"J1": 90.0, "J2": 0.0}),
        JointConfiguration(model_id=model.model_id, positions={"J1": 0.0, "J2": 90.0}),
        JointConfiguration(model_id=model.model_id, positions={"J1": 30.0, "J2": 45.0}),
    )
    scope = (
        ExactConstituentPair(first_instance_id="A2", second_instance_id="B1"),
        ExactConstituentPair(first_instance_id="R1", second_instance_id="A1"),
    )
    request = _v2_collision_request(
        assembly, model, scope, configurations=configurations
    )
    expected_fk_results = tuple(
        MultiJointKinematicsService().evaluate(assembly, model, configuration)
        for configuration in configurations
    )
    expected_fk = {
        result.configuration_hash: result for result in expected_fk_results
    }
    interference_sample_id = expected_fk_results[-1].configuration_hash
    j1_only_sample_id = expected_fk_results[1].configuration_hash
    j2_only_sample_id = expected_fk_results[2].configuration_hash
    source_placements = {
        instance.instance_id: instance.placement for instance in assembly.instances
    }
    quarter_turn = CadRigidTransform(
        rotation_quaternion=(math.sqrt(0.5), 0.0, 0.0, math.sqrt(0.5))
    )
    expected_a2_after_j1 = transform_compose(
        source_placements["R1"],
        transform_compose(
            quarter_turn,
            transform_compose(
                transform_inverse(source_placements["R1"]),
                source_placements["A2"],
            ),
        ),
    )
    expected_b1_after_j2 = transform_compose(
        source_placements["A1"],
        transform_compose(
            quarter_turn,
            transform_compose(
                transform_inverse(source_placements["A1"]),
                source_placements["B1"],
            ),
        ),
    )
    expected_instance_ids = {"R1", "R2", "A1", "A2", "B1", "B2"}
    assert not rigid_transform_agrees(
        expected_a2_after_j1, source_placements["A2"]
    )
    assert not rigid_transform_agrees(
        expected_b1_after_j2, source_placements["B1"]
    )
    observed_pairs = []

    def exact_measure(received_request, transformed):
        observed_pairs.append(received_request.pairs)
        transformed_ids = tuple(
            instance.instance_id for instance in transformed.instances
        )
        assert len(transformed_ids) == 6
        assert set(transformed_ids) == expected_instance_ids
        assert ("A2", "B1") in received_request.pairs
        assert all(
            endpoint in transformed_ids
            for pair in received_request.pairs
            for endpoint in pair
        )
        expected = expected_fk[received_request.sample_id]
        expected_transforms = {
            item.instance_id: item.transform
            for item in expected.instance_world_transforms
        }
        transformed_placements = {
            item.instance_id: item.placement
            for item in transformed.instances
        }
        for instance_id in ("A2", "B1"):
            assert rigid_transform_agrees(
                transformed_placements[instance_id],
                expected_transforms[instance_id],
            )

        if received_request.sample_id == j1_only_sample_id:
            assert rigid_transform_agrees(
                transformed_placements["A2"], expected_a2_after_j1
            )
        if received_request.sample_id == j2_only_sample_id:
            assert rigid_transform_agrees(
                transformed_placements["B1"], expected_b1_after_j2
            )

        interference = received_request.sample_id == interference_sample_id
        return tuple(
            (
                first_id,
                second_id,
                1.0 if interference and (first_id, second_id) == ("A2", "B1") else 0.0,
                0.0 if interference and (first_id, second_id) == ("A2", "B1") else 2.5,
            )
            for first_id, second_id in received_request.pairs
        )

    result = MultiJointDiscreteCollisionSweepService(
        TransientAssemblyAnalysisService(exact_measure)
    ).execute(request, assembly)

    assert observed_pairs == [
        (("A1", "R1"), ("A2", "B1")),
        (("A1", "R1"), ("A2", "B1")),
        (("A1", "R1"), ("A2", "B1")),
        (("A1", "R1"), ("A2", "B1")),
    ]
    assert request.exact_pair_scope == (
        ExactConstituentPair(first_instance_id="A1", second_instance_id="R1"),
        ExactConstituentPair(first_instance_id="A2", second_instance_id="B1"),
    )
    assert result.configuration_results[0].classification is CollisionClassification.POSITIVE_CLEARANCE
    assert result.configuration_results[-1].classification is CollisionClassification.INTERFERENCE

    transforms = [
        {
            item.instance_id: item.transform
            for item in configuration.instance_world_transforms
        }
        for configuration in result.configuration_results
    ]
    for instance_id in ("R1", "R2"):
        assert rigid_transform_agrees(transforms[1][instance_id], transforms[0][instance_id])
        assert rigid_transform_agrees(transforms[2][instance_id], transforms[0][instance_id])
    for instance_id in ("A1", "A2", "B1", "B2"):
        assert not rigid_transform_agrees(transforms[1][instance_id], transforms[0][instance_id])
    for instance_id in ("A1", "A2"):
        assert rigid_transform_agrees(transforms[2][instance_id], transforms[0][instance_id])
    for instance_id in ("B1", "B2"):
        assert not rigid_transform_agrees(transforms[2][instance_id], transforms[0][instance_id])

    articulated_pair_result = next(
        pair
        for pair in result.configuration_results[-1].pair_results
        if (pair.first_instance_id, pair.second_instance_id) == ("A2", "B1")
    )
    assert (
        articulated_pair_result.first_instance_id,
        articulated_pair_result.second_instance_id,
    ) == ("A2", "B1")


def test_v2_collision_result_hash_binds_nested_transforms_and_pair_results():
    assembly, model = _grouped_fk_fixture()
    pair = ExactConstituentPair(first_instance_id="A1", second_instance_id="B1")
    request = _v2_collision_request(assembly, model, (pair,))

    result = MultiJointDiscreteCollisionSweepService(
        TransientAssemblyAnalysisService(
            lambda received_request, transformed: tuple(
                (first_id, second_id, 0.0, 2.5)
                for first_id, second_id in received_request.pairs
            )
        )
    ).execute(request, assembly)
    configuration = result.configuration_results[0]
    changed_pair = configuration.pair_results[0].model_copy(
        update={"exact_distance_mm": 3.5}
    )
    changed_configuration = configuration.model_copy(
        update={"pair_results": (changed_pair,)}
    )
    changed_transform = configuration.model_copy(
        update={"transformed_assembly_hash": "sha256:changed-transform"}
    )
    changed = result.model_copy(
        update={"configuration_results": (changed_configuration,)}
    )
    changed_with_transform = result.model_copy(
        update={"configuration_results": (changed_transform,)}
    )

    assert multi_joint_collision_sweep_result_v2_hash(changed) != result.result_hash
    assert (
        multi_joint_collision_sweep_result_v2_hash(changed_with_transform)
        != result.result_hash
    )


def test_v2_continuous_request_is_neutral_and_scope_order_invariant():
    from mechcad_harness.multi_joint_continuous_path import (
        BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION,
        MultiJointContinuousPathRequestV2,
        MultiJointPath,
    )

    assembly, model = _grouped_fk_fixture()
    path = MultiJointPath(
        model_id=model.model_id,
        waypoints=(
            JointConfiguration(model_id=model.model_id, positions={"J1": 0.0, "J2": 0.0}),
            JointConfiguration(model_id=model.model_id, positions={"J1": 10.0, "J2": 20.0}),
        ),
    )
    first = ExactConstituentPair(first_instance_id="A2", second_instance_id="B1")
    second = ExactConstituentPair(first_instance_id="R1", second_instance_id="A1")

    request = MultiJointContinuousPathRequestV2(
        schema_version="multi-joint-continuous-path-request@2",
        source_assembly_id=assembly.assembly_id,
        source_assembly_hash=assembly_hash(assembly),
        model=model,
        path=path,
        exact_pair_scope=(second, first),
    )
    equivalent = MultiJointContinuousPathRequestV2.model_validate(
        request.model_dump(mode="json")
        | {
            "exact_pair_scope": [first.model_dump(mode="json"), second.model_dump(mode="json")],
            "request_hash": "pending",
        }
    )

    assert request.exact_pair_scope == (second, first)
    assert request.pairs == (("A1", "R1"), ("A2", "B1"))
    assert request.request_hash == equivalent.request_hash
    assert request.model_hash == kinematic_model_hash(model)
    assert request.schema_version == "multi-joint-continuous-path-request@2"
    assert BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION == "body-member-reach-bound-plumbing@2.0"
    assert "moving_instance_ids" not in request.model_dump(mode="json")
    assert "stationary_instance_ids" not in request.model_dump(mode="json")


def _v2_continuous_request(assembly, model, scope):
    from mechcad_harness.multi_joint_continuous_path import (
        MultiJointContinuousPathRequestV2,
        MultiJointPath,
    )

    path = MultiJointPath(
        model_id=model.model_id,
        waypoints=(
            JointConfiguration(model_id=model.model_id, positions={"J1": 0.0, "J2": 0.0}),
            JointConfiguration(model_id=model.model_id, positions={"J1": 10.0, "J2": 20.0}),
        ),
    )
    return MultiJointContinuousPathRequestV2(
        schema_version="multi-joint-continuous-path-request@2",
        source_assembly_id=assembly.assembly_id,
        source_assembly_hash=assembly_hash(assembly),
        model=model,
        path=path,
        exact_pair_scope=scope,
        max_depth=0,
    )


def test_v2_continuous_scope_rejects_before_extent_and_exact_providers():
    from mechcad_harness.multi_joint_continuous_clearance import (
        MultiJointContinuousClearanceProofService,
    )

    assembly, model = _grouped_fk_fixture()
    request = _v2_continuous_request(
        assembly,
        model,
        (ExactConstituentPair(first_instance_id="R1", second_instance_id="R2"),),
    )
    extent_calls = []
    exact_calls = []
    service = MultiJointContinuousClearanceProofService(
        exact_measure=lambda *args: exact_calls.append(args),
        extent_provider=lambda *args: extent_calls.append(args),
    )

    with pytest.raises(ValueError, match="same rigid body"):
        service.execute(request, assembly)

    assert extent_calls == []
    assert exact_calls == []


@pytest.mark.parametrize(
    "pair",
    (
        ExactConstituentPair(first_instance_id="unknown", second_instance_id="A1"),
        ExactConstituentPair(first_instance_id="A1", second_instance_id="unknown"),
    ),
)
def test_v2_continuous_unknown_scope_ids_reject_before_extent_provider(pair):
    from mechcad_harness.multi_joint_continuous_clearance import (
        MultiJointContinuousClearanceProofService,
    )

    assembly, model = _grouped_fk_fixture()
    request = _v2_continuous_request(assembly, model, (pair,))
    extent_calls = []
    service = MultiJointContinuousClearanceProofService(
        exact_measure=lambda *args: (),
        extent_provider=lambda *args: extent_calls.append(args),
    )

    with pytest.raises(ValueError, match="not in source assembly"):
        service.execute(request, assembly)

    assert extent_calls == []


def test_v2_continuous_proof_emits_neutral_records_and_outer_result_hash():
    from mechcad_harness.multi_joint_continuous_clearance import (
        MultiJointContinuousClearanceProofService,
        MultiJointContinuousClearanceProofResultV2,
        MultiJointContinuousProofStatus,
        multi_joint_continuous_clearance_proof_result_v2_hash,
    )
    from mechcad_harness.multi_joint_continuous_path import TrustedLocalGeometryExtent

    assembly, model = _grouped_fk_fixture()
    pair = ExactConstituentPair(first_instance_id="A2", second_instance_id="B1")
    request = _v2_continuous_request(assembly, model, (pair,))
    extents = {
        instance.instance_id: TrustedLocalGeometryExtent(
            instance_id=instance.instance_id,
            component_identity="grouped-part@1",
            local_radius_mm=1.0,
        )
        for instance in assembly.instances
    }

    def measure(received_request, transformed):
        return tuple(
            (first, second, 0.0, 100.0)
            for first, second in received_request.pairs
        )

    result = MultiJointContinuousClearanceProofService(
        exact_measure=measure,
        extent_provider=lambda source, source_model, instance_ids: {
            instance_id: extents[instance_id] for instance_id in instance_ids
        },
    ).execute(request, assembly)

    assert isinstance(result, MultiJointContinuousClearanceProofResultV2)
    assert result.status is MultiJointContinuousProofStatus.VERIFIED_CLEAR
    assert result.collision_witness is None
    pair_result = result.exact_evaluations[0].pair_results[0]
    assert (pair_result.first_instance_id, pair_result.second_instance_id) == ("A2", "B1")
    certificate = result.certified_leaf_certificates[0]
    assert certificate.reach_bound_algorithm_version == "body-member-reach-bound-plumbing@2.0"
    certificate_pair = certificate.pair_certificates[0]
    assert (certificate_pair.first_instance_id, certificate_pair.second_instance_id) == ("A2", "B1")
    assert "moving_instance_id" not in pair_result.model_dump(mode="json")
    assert "stationary_instance_id" not in pair_result.model_dump(mode="json")
    assert "result_hash" not in pair_result.model_dump(mode="json")
    assert result.result_hash == multi_joint_continuous_clearance_proof_result_v2_hash(result)
    assert "moving_instance_id" not in str(result.model_dump(mode="json"))
    assert "stationary_instance_id" not in str(result.model_dump(mode="json"))

    changed_evaluation = result.exact_evaluations[0].model_copy(
        update={"transformed_assembly_hash": "sha256:changed"}
    )
    changed = result.model_copy(
        update={"exact_evaluations": (changed_evaluation,)}
    )
    assert multi_joint_continuous_clearance_proof_result_v2_hash(changed) != result.result_hash


def test_v2_continuous_result_parser_dispatches_v1_without_schema_and_v2_explicitly():
    from mechcad_harness.multi_joint_continuous_clearance import (
        MultiJointContinuousClearanceProofService,
        MultiJointContinuousClearanceProofResult,
        MultiJointContinuousClearanceProofResultV2,
        parse_multi_joint_continuous_result,
    )
    from mechcad_harness.multi_joint_continuous_path import TrustedLocalGeometryExtent

    assembly, model = _grouped_fk_fixture()
    pair = ExactConstituentPair(first_instance_id="A2", second_instance_id="B1")
    request = _v2_continuous_request(assembly, model, (pair,))
    extents = {
        instance.instance_id: TrustedLocalGeometryExtent(
            instance_id=instance.instance_id,
            component_identity="grouped-part@1",
            local_radius_mm=1.0,
        )
        for instance in assembly.instances
    }
    result = MultiJointContinuousClearanceProofService(
        exact_measure=lambda received, transformed: tuple(
            (first, second, 0.0, 100.0) for first, second in received.pairs
        ),
        extent_provider=lambda source, source_model, instance_ids: {
            instance_id: extents[instance_id] for instance_id in instance_ids
        },
    ).execute(request, assembly)

    payload = result.model_dump(mode="json")
    assert isinstance(parse_multi_joint_continuous_result(payload), MultiJointContinuousClearanceProofResultV2)

    from tests.unit.test_multi_joint_continuous_clearance import ASSEMBLY, request, service

    v1_result = service(
        lambda received, transformed: tuple(
            (first, second, 0.0, 100.0) for first, second in received.pairs
        )
    ).execute(request(max_depth=0), ASSEMBLY)
    assert isinstance(
        parse_multi_joint_continuous_result(v1_result.model_dump(mode="json")),
        MultiJointContinuousClearanceProofResult,
    )


@pytest.mark.parametrize("missing_field", ("certified_intervals", "unresolved_intervals"))
def test_v2_continuous_segment_requires_both_interval_fields(missing_field):
    from mechcad_harness.multi_joint_continuous_clearance import (
        MultiJointContinuousClearanceProofService,
        MultiJointContinuousClearanceProofResultV2,
        parse_multi_joint_continuous_result,
    )
    from mechcad_harness.multi_joint_continuous_path import TrustedLocalGeometryExtent

    assembly, model = _grouped_fk_fixture()
    request = _v2_continuous_request(
        assembly,
        model,
        (ExactConstituentPair(first_instance_id="A2", second_instance_id="B1"),),
    )
    extents = {
        instance.instance_id: TrustedLocalGeometryExtent(
            instance_id=instance.instance_id,
            component_identity="grouped-part@1",
            local_radius_mm=1.0,
        )
        for instance in assembly.instances
    }
    result = MultiJointContinuousClearanceProofService(
        exact_measure=lambda received, transformed: tuple(
            (first, second, 0.0, 100.0) for first, second in received.pairs
        ),
        extent_provider=lambda source, source_model, instance_ids: {
            instance_id: extents[instance_id] for instance_id in instance_ids
        },
    ).execute(request, assembly)

    assert isinstance(result, MultiJointContinuousClearanceProofResultV2)
    payload = result.model_dump(mode="json")
    payload["segment_results"][0].pop(missing_field)

    with pytest.raises(ValidationError, match=missing_field):
        parse_multi_joint_continuous_result(payload)


@pytest.mark.parametrize("schema_version", (None, "multi-joint-continuous-clearance-proof-result@999"))
def test_v2_continuous_result_parser_rejects_explicit_null_or_unknown_discriminator(schema_version):
    from mechcad_harness.multi_joint_continuous_clearance import (
        MultiJointContinuousClearanceProofService,
        parse_multi_joint_continuous_result,
    )
    from mechcad_harness.multi_joint_continuous_path import TrustedLocalGeometryExtent

    assembly, model = _grouped_fk_fixture()
    request = _v2_continuous_request(
        assembly,
        model,
        (ExactConstituentPair(first_instance_id="A2", second_instance_id="B1"),),
    )
    extents = {
        instance.instance_id: TrustedLocalGeometryExtent(
            instance_id=instance.instance_id,
            component_identity="grouped-part@1",
            local_radius_mm=1.0,
        )
        for instance in assembly.instances
    }
    result = MultiJointContinuousClearanceProofService(
        exact_measure=lambda received, transformed: tuple(
            (first, second, 0.0, 100.0) for first, second in received.pairs
        ),
        extent_provider=lambda source, source_model, instance_ids: {
            instance_id: extents[instance_id] for instance_id in instance_ids
        },
    ).execute(request, assembly)
    payload = result.model_dump(mode="json")
    payload["schema_version"] = schema_version

    with pytest.raises(ValueError, match="unsupported continuous clearance result schema"):
        parse_multi_joint_continuous_result(payload)


def test_v2_continuous_witness_has_neutral_pair_and_no_nested_hashes():
    from mechcad_harness.multi_joint_continuous_clearance import (
        MultiJointContinuousClearanceProofService,
        MultiJointContinuousClearanceProofResultV2,
    )
    from mechcad_harness.multi_joint_continuous_path import TrustedLocalGeometryExtent

    assembly, model = _grouped_fk_fixture()
    request = _v2_continuous_request(
        assembly,
        model,
        (ExactConstituentPair(first_instance_id="A2", second_instance_id="B1"),),
    )
    extents = {
        instance.instance_id: TrustedLocalGeometryExtent(
            instance_id=instance.instance_id,
            component_identity="grouped-part@1",
            local_radius_mm=1.0,
        )
        for instance in assembly.instances
    }
    result = MultiJointContinuousClearanceProofService(
        exact_measure=lambda received, transformed: tuple(
            (first, second, 1.0, 0.0) for first, second in received.pairs
        ),
        extent_provider=lambda source, source_model, instance_ids: {
            instance_id: extents[instance_id] for instance_id in instance_ids
        },
    ).execute(request, assembly)

    assert isinstance(result, MultiJointContinuousClearanceProofResultV2)
    assert result.collision_witness is not None
    witness = result.collision_witness
    assert (witness.first_instance_id, witness.second_instance_id) == ("A2", "B1")
    assert "moving_instance_id" not in witness.model_dump(mode="json")
    assert "stationary_instance_id" not in witness.model_dump(mode="json")
    assert "result_hash" not in witness.model_dump(mode="json")
    assert "result_hash" not in result.exact_evaluations[0].model_dump(mode="json")


def test_v2_continuous_result_hash_has_approved_sensitivity_and_reorder_invariance():
    from mechcad_harness.multi_joint_continuous_clearance import (
        MultiJointContinuousClearanceProofService,
        MultiJointContinuousClearanceProofResultV2,
        multi_joint_continuous_clearance_proof_result_v2_hash,
    )
    from mechcad_harness.multi_joint_continuous_path import TrustedLocalGeometryExtent

    assembly, model = _grouped_fk_fixture()
    first = ExactConstituentPair(first_instance_id="A2", second_instance_id="B1")
    second = ExactConstituentPair(first_instance_id="R1", second_instance_id="A1")
    request = _v2_continuous_request(assembly, model, (second, first))
    extents = {
        instance.instance_id: TrustedLocalGeometryExtent(
            instance_id=instance.instance_id,
            component_identity="grouped-part@1",
            local_radius_mm=1.0,
        )
        for instance in assembly.instances
    }

    def clear_measure(received, transformed):
        return tuple(
            (first_id, second_id, 0.0, 100.0)
            for first_id, second_id in received.pairs
        )

    def execute(proof_request, proof_assembly):
        return MultiJointContinuousClearanceProofService(
            exact_measure=clear_measure,
            extent_provider=lambda source, source_model, instance_ids: {
                instance_id: extents[instance_id] for instance_id in instance_ids
            },
        ).execute(proof_request, proof_assembly)

    result = execute(request, assembly)
    assert isinstance(result, MultiJointContinuousClearanceProofResultV2)
    baseline_hash = multi_joint_continuous_clearance_proof_result_v2_hash(result)

    pair_result = result.exact_evaluations[0].pair_results[0].model_copy(
        update={"second_instance_id": "B1"}
    )
    changed_evaluation = result.exact_evaluations[0].model_copy(
        update={"pair_results": (pair_result, *result.exact_evaluations[0].pair_results[1:])}
    )
    assert multi_joint_continuous_clearance_proof_result_v2_hash(
        result.model_copy(update={"exact_evaluations": (changed_evaluation, *result.exact_evaluations[1:])})
    ) != baseline_hash

    changed_evaluation_transform = result.exact_evaluations[0].model_copy(
        update={"transformed_assembly_hash": "sha256:changed-evaluation"}
    )
    assert multi_joint_continuous_clearance_proof_result_v2_hash(
        result.model_copy(
            update={
                "exact_evaluations": (
                    changed_evaluation_transform,
                    *result.exact_evaluations[1:],
                )
            }
        )
    ) != baseline_hash

    changed_certificate = result.certified_leaf_certificates[0].model_copy(
        update={"transformed_assembly_hash": "sha256:changed-certificate"}
    )
    assert multi_joint_continuous_clearance_proof_result_v2_hash(
        result.model_copy(update={"certified_leaf_certificates": (changed_certificate, *result.certified_leaf_certificates[1:])})
    ) != baseline_hash

    assert multi_joint_continuous_clearance_proof_result_v2_hash(
        result.model_copy(update={"reach_bound_algorithm_version": "body-member-reach-bound-plumbing@2.1"})
    ) != baseline_hash

    collision_result = MultiJointContinuousClearanceProofService(
        exact_measure=lambda received, transformed: tuple(
            (first_id, second_id, 1.0, 0.0)
            for first_id, second_id in received.pairs
        ),
        extent_provider=lambda source, source_model, instance_ids: {
            instance_id: extents[instance_id] for instance_id in instance_ids
        },
    ).execute(_v2_continuous_request(assembly, model, (first,)), assembly)
    assert collision_result.collision_witness is not None
    changed_witness = collision_result.collision_witness.model_copy(
        update={"second_instance_id": "B2"}
    )
    assert multi_joint_continuous_clearance_proof_result_v2_hash(
        collision_result.model_copy(update={"collision_witness": changed_witness})
    ) != collision_result.result_hash
    changed_witness_transform = collision_result.collision_witness.model_copy(
        update={"transformed_assembly_hash": "sha256:changed-witness"}
    )
    assert multi_joint_continuous_clearance_proof_result_v2_hash(
        collision_result.model_copy(update={"collision_witness": changed_witness_transform})
    ) != collision_result.result_hash

    reordered_model = KinematicModelV2.model_validate(
        model.model_dump(mode="python")
        | {
            "bodies": list(reversed(model.bodies)),
            "joints": list(reversed(model.joints)),
        }
    )
    reordered_assembly = CadAssemblyProgram.model_validate(
        assembly.model_dump(mode="python")
        | {"instances": list(reversed(assembly.instances))}
    )
    reordered_result = execute(
        _v2_continuous_request(reordered_assembly, reordered_model, (first, second)),
        reordered_assembly,
    )
    assert reordered_result.result_hash == result.result_hash


def _v2_continuous_request_for_pair(assembly, model, pair):
    from mechcad_harness.multi_joint_continuous_path import (
        MultiJointContinuousPathRequestV2,
        MultiJointPath,
    )

    path = MultiJointPath(
        model_id=model.model_id,
        waypoints=(
            JointConfiguration(
                model_id=model.model_id,
                positions={joint.joint_id: 0.0 for joint in model.joints},
            ),
            JointConfiguration(
                model_id=model.model_id,
                positions={joint.joint_id: 10.0 for joint in model.joints},
            ),
        ),
    )
    return MultiJointContinuousPathRequestV2(
        schema_version="multi-joint-continuous-path-request@2",
        source_assembly_id=assembly.assembly_id,
        source_assembly_hash=assembly_hash(assembly),
        model=model,
        path=path,
        exact_pair_scope=(pair,),
        max_depth=0,
    )


def _v2_extents_for(assembly):
    from mechcad_harness.multi_joint_continuous_path import TrustedLocalGeometryExtent

    return {
        instance.instance_id: TrustedLocalGeometryExtent(
            instance_id=instance.instance_id,
            component_identity="grouped-part@1",
            local_radius_mm=1.0,
        )
        for instance in assembly.instances
    }


@pytest.mark.parametrize(
    ("fixture_name", "pair_ids"),
    (
        ("serial", ("R1", "A1")),
        ("ancestor-descendant", ("A1", "B1")),
        ("sibling", ("A1", "B1")),
        ("separate-branches", ("arm-a-1", "arm-z-1")),
    ),
)
def test_v2_reach_bounds_cover_each_member_for_all_pair_topologies(fixture_name, pair_ids):
    if fixture_name == "serial":
        assembly, model = _grouped_fk_fixture()
    elif fixture_name == "ancestor-descendant":
        assembly, model = _grouped_fk_fixture()
    elif fixture_name == "sibling":
        assembly, model = _grouped_fk_fixture(branching=True)
    else:
        assembly, model = _forest_fk_fixture()

    from mechcad_harness.multi_joint_continuous_path import (
        BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION,
        ReachBoundTableV2,
        _v2_body_parent_chain,
        derive_reach_bounds,
    )
    from mechcad_harness.multi_joint_kinematics import body_by_member_id

    bounds = derive_reach_bounds(assembly, model, _v2_extents_for(assembly))

    assert isinstance(bounds, ReachBoundTableV2)
    assert bounds.algorithm_version == BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION
    assert bounds.extent_algorithm_version == "component-local-geometry-extent@1.0"
    owners = body_by_member_id(model)
    assert {record.instance_id for record in bounds.records} == {
        member_id
        for member_id, body in owners.items()
        if _v2_body_parent_chain(model, body.body_id)
    }
    assert all(
        record.algorithm_version == BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION
        and record.instance_id in owners
        and record.chain_body_ids
        for record in bounds.records
    )


def test_v2_reach_bound_appends_declared_terminal_member_distance_without_rounding():
    from mechcad_harness.multi_joint_continuous_path import derive_reach_bounds
    from mechcad_harness.multi_joint_kinematics import body_by_member_id, transform_apply

    assembly, model = _grouped_fk_fixture()
    bounds = derive_reach_bounds(assembly, model, _v2_extents_for(assembly))
    record = bounds.for_instance_joint("A2", "J1")
    member = next(
        member
        for member in body_by_member_id(model)["A2"].members
        if member.member_instance_id == "A2"
    )
    terminal_origin = transform_apply(member.reference_to_member_home, (0.0, 0.0, 0.0))
    terminal_distance = math.sqrt(sum(value * value for value in terminal_origin))

    assert record is not None
    assert record.offset_lengths_mm[-1] == terminal_distance
    assert record.reach_bound_mm == pytest.approx(
        record.local_geometry_radius_mm
        + sum(record.offset_lengths_mm)
        + 1e-9,
        rel=0.0,
        abs=0.0,
    )


@pytest.mark.parametrize(
    ("fixture_name", "pair_ids", "expected_positive"),
    (
        ("serial", ("R1", "A1"), (True, False)),
        ("ancestor-descendant", ("A1", "B1"), (True, True)),
        ("sibling", ("A1", "B1"), (True, True)),
        ("separate-branches", ("arm-a-1", "arm-z-1"), (True, True)),
    ),
)
def test_v2_continuous_proof_sums_independent_endpoint_bounds(fixture_name, pair_ids, expected_positive):
    from mechcad_harness.multi_joint_continuous_clearance import (
        MultiJointContinuousClearanceProofService,
        MultiJointContinuousProofStatus,
    )

    if fixture_name == "serial":
        assembly, model = _grouped_fk_fixture()
    elif fixture_name == "ancestor-descendant":
        assembly, model = _grouped_fk_fixture()
    elif fixture_name == "sibling":
        assembly, model = _grouped_fk_fixture(branching=True)
    else:
        assembly, model = _forest_fk_fixture()

    pair = ExactConstituentPair(
        first_instance_id=pair_ids[0], second_instance_id=pair_ids[1]
    )
    request = _v2_continuous_request_for_pair(assembly, model, pair)
    extents = _v2_extents_for(assembly)
    result = MultiJointContinuousClearanceProofService(
        exact_measure=lambda received, transformed: tuple(
            (first, second, 0.0, 1000.0) for first, second in received.pairs
        ),
        extent_provider=lambda source, source_model, instance_ids: {
            instance_id: extents[instance_id] for instance_id in instance_ids
        },
    ).execute(request, assembly)

    assert result.status is MultiJointContinuousProofStatus.VERIFIED_CLEAR
    pair_certificate = result.certified_leaf_certificates[0].pair_certificates[0]
    assert (pair_certificate.motion_bound_A_mm > 0, pair_certificate.motion_bound_B_mm > 0) == expected_positive
    assert pair_certificate.pair_motion_bound_mm == (
        pair_certificate.motion_bound_A_mm + pair_certificate.motion_bound_B_mm
    )


def test_v2_continuous_clear_acceptance_keeps_articulated_pair_neutral_across_samples():
    from mechcad_harness.multi_joint_continuous_clearance import (
        MultiJointContinuousClearanceProofResultV2,
        MultiJointContinuousClearanceProofService,
        MultiJointContinuousProofStatus,
        ProofWitnessLocation,
    )
    from mechcad_harness.multi_joint_kinematics import body_by_member_id

    assembly, model = _grouped_fk_fixture()
    pair = ExactConstituentPair(first_instance_id="A2", second_instance_id="B1")
    request = _v2_continuous_request_for_pair(assembly, model, pair)
    extents = _v2_extents_for(assembly)
    topology = _build_v2_kinematic_topology(assembly, model)
    owners = body_by_member_id(model)
    assert all(owners[instance_id].body_id in topology.articulated_children for instance_id in ("A2", "B1"))
    observed = []

    def measure(received_request, transformed):
        observed.append((received_request.sample_id, received_request.pairs))
        assert received_request.pairs == (("A2", "B1"),)
        assert {instance.instance_id for instance in transformed.instances} == {
            "R1", "R2", "A1", "A2", "B1", "B2"
        }
        return (("A2", "B1", 0.0, 100.0),)

    result = MultiJointContinuousClearanceProofService(
        exact_measure=measure,
        extent_provider=lambda source, source_model, instance_ids: {
            instance_id: extents[instance_id] for instance_id in instance_ids
        },
    ).execute(request, assembly)

    assert isinstance(result, MultiJointContinuousClearanceProofResultV2)
    assert result.status is MultiJointContinuousProofStatus.VERIFIED_CLEAR
    assert len(observed) == 3
    assert len(result.exact_evaluations) == len(observed)
    assert result.exact_evaluations[0].location.waypoint_index == 0
    assert result.exact_evaluations[1].location.waypoint_index == 1
    assert result.exact_evaluations[2].location == ProofWitnessLocation(segment_index=0, t=0.5)
    assert all(
        (pair_result.first_instance_id, pair_result.second_instance_id) == ("A2", "B1")
        for evaluation in result.exact_evaluations
        for pair_result in evaluation.pair_results
    )
    certificate_pair = result.certified_leaf_certificates[0].pair_certificates[0]
    assert (certificate_pair.first_instance_id, certificate_pair.second_instance_id) == ("A2", "B1")
    assert certificate_pair.motion_bound_A_mm > 0
    assert certificate_pair.motion_bound_B_mm > 0
    assert certificate_pair.pair_motion_bound_mm == (
        certificate_pair.motion_bound_A_mm + certificate_pair.motion_bound_B_mm
    )
    assert "moving_instance_id" not in str(result.model_dump(mode="json"))
    assert "stationary_instance_id" not in str(result.model_dump(mode="json"))


def test_v2_continuous_required_clearance_witness_retains_articulated_pair_identity():
    from mechcad_harness.multi_joint_continuous_clearance import (
        MultiJointContinuousClearanceProofResultV2,
        MultiJointContinuousClearanceProofService,
        MultiJointContinuousProofStatus,
    )
    from mechcad_harness.multi_joint_kinematics import body_by_member_id

    assembly, model = _grouped_fk_fixture()
    pair = ExactConstituentPair(first_instance_id="A2", second_instance_id="B1")
    request = _v2_continuous_request_for_pair(assembly, model, pair).model_copy(
        update={"required_clearance_mm": 10.0, "request_hash": "pending"}
    )
    extents = _v2_extents_for(assembly)
    topology = _build_v2_kinematic_topology(assembly, model)
    owners = body_by_member_id(model)
    assert all(owners[instance_id].body_id in topology.articulated_children for instance_id in ("A2", "B1"))
    observed_pairs = []

    def measure(received_request, transformed):
        observed_pairs.append(received_request.pairs)
        assert received_request.pairs == (("A2", "B1"),)
        return (("A2", "B1", 0.0, 5.0),)

    result = MultiJointContinuousClearanceProofService(
        exact_measure=measure,
        extent_provider=lambda source, source_model, instance_ids: {
            instance_id: extents[instance_id] for instance_id in instance_ids
        },
    ).execute(request, assembly)

    assert isinstance(result, MultiJointContinuousClearanceProofResultV2)
    assert result.status is MultiJointContinuousProofStatus.COLLISION_WITNESS
    assert observed_pairs == [(("A2", "B1"),)]
    assert result.collision_witness is not None
    witness = result.collision_witness
    assert (witness.first_instance_id, witness.second_instance_id) == ("A2", "B1")
    assert witness.exact_distance_mm == 5.0
    assert "moving_instance_id" not in str(result.model_dump(mode="json"))
    assert "stationary_instance_id" not in str(result.model_dump(mode="json"))


def test_continuous_proof_provenance_omits_optional_v2_plumbing_for_v1_and_serializes_it_for_v2():
    from mechcad_harness.analysis_provenance import ContinuousProofExecutionProvenance
    from mechcad_harness.multi_joint_continuous_path import BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION

    common = {
        "request_hash": "sha256:req",
        "result_hash": "sha256:result",
        "source_assembly_hash": "sha256:assembly",
        "proof_algorithm_version": "proof@1.0",
        "provider_name": "provider",
        "provider_version": "provider@1.0",
        "execution_mode": "test",
    }
    v1 = ContinuousProofExecutionProvenance(**common)
    v2 = ContinuousProofExecutionProvenance(
        **common,
        reach_bound_plumbing_version=BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION,
    )

    assert "reach_bound_plumbing_version" not in v1.model_dump(mode="json")
    assert v2.model_dump(mode="json")["reach_bound_plumbing_version"] == BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION


def test_v2_public_types_are_exported_by_domain_modules_not_package_root():
    import mechcad_harness
    import mechcad_harness.multi_joint_collision_sweep as collision_module
    import mechcad_harness.multi_joint_kinematics as kinematics_module

    assert {
        "MultiJointCollisionSweepRequestV2",
        "MultiJointCollisionSweepResultV2",
    } <= set(collision_module.__all__)
    assert {
        "KinematicModelV2",
        "RevoluteJointModelV2",
    } <= set(kinematics_module.__all__)
    assert not hasattr(mechcad_harness, "KinematicModelV2")


def test_m13_3p_generic_production_modules_have_no_forbidden_authority_imports():
    production_modules = (
        "multi_joint_kinematics.py",
        "multi_joint_pair_scope.py",
        "multi_joint_collision_sweep.py",
        "multi_joint_continuous_path.py",
        "multi_joint_continuous_clearance.py",
    )
    forbidden_prefixes = (
        "mechcad_harness.candidates",
        "mechcad_harness.models.physical_mechanism",
        "mechcad_harness.supplied_component",
        "mechcad_harness.generated_part",
        "mechcad_harness.models.supplied_component_interface",
        "mechcad_harness.models.generated_part",
    )
    source_root = Path(__file__).parents[2] / "src" / "mechcad_harness"

    forbidden_imports = []
    for module_name in production_modules:
        tree = ast.parse((source_root / module_name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported_modules = [node.module or ""]
            else:
                continue
            forbidden_imports.extend(
                (module_name, node.lineno, imported_module)
                for imported_module in imported_modules
                if imported_module.startswith(forbidden_prefixes)
            )

    assert forbidden_imports == []


def test_m12_output_group_metadata_cannot_construct_generic_v2_bodies():
    from tests.unit.test_m12_candidate_m10_binding import _binding, _realization

    realization = _realization()
    first_binding = _binding(realization)
    second_binding = _binding(realization)

    assert first_binding.model_dump(mode="json") == second_binding.model_dump(mode="json")
    output_rigid = tuple(
        entry
        for entry in first_binding.constituent_dispositions
        if entry.disposition.value == "output_rigid"
    )
    assert output_rigid
    assert {entry.output_transform_group for entry in output_rigid} == {"output-joint"}
    with pytest.raises(ValueError, match="missing"):
        validate_v2_body_assembly_agreement(
            realization.assembly,
            KinematicModelV2(model_id="explicit-v2", bodies=(), joints=()),
        )

    bodies = tuple(
        KinematicRigidBody(
            body_id=f"body-{instance.instance_id}",
            reference_member_instance_id=instance.instance_id,
            members=(
                KinematicRigidBodyMember(
                    member_instance_id=instance.instance_id,
                    reference_to_member_home=CadRigidTransform(),
                ),
            ),
        )
        for instance in realization.assembly.instances
    )
    model = KinematicModelV2(model_id="explicit-v2", bodies=bodies, joints=())

    assert set(validate_v2_body_assembly_agreement(realization.assembly, model)) == {
        instance.instance_id for instance in realization.assembly.instances
    }


def test_v2_model_hash_rejects_stale_body_hash_after_object_setattr_alteration():
    _, model = _grouped_fk_fixture()
    member = model.bodies[0].members[1]
    object.__setattr__(member, "reference_to_member_home", CadRigidTransform(x_mm=999.0))

    with pytest.raises(ValueError, match="rigid body hash mismatch"):
        kinematic_model_hash(model)


def test_v2_model_hash_rejects_stale_body_hash_from_model_copy():
    _, model = _grouped_fk_fixture()
    forged_body = model.bodies[0].model_copy(update={"body_id": "forged-root"})
    forged_model = model.model_copy(
        update={"bodies": (forged_body, *model.bodies[1:])}
    )

    with pytest.raises(ValueError, match="rigid body hash mismatch"):
        kinematic_model_hash(forged_model)


def test_v2_body_hash_rejects_pending_hash_from_model_copy():
    _, model = _grouped_fk_fixture()
    forged_body = model.bodies[0].model_copy(update={"body_hash": "pending"})

    with pytest.raises(ValueError, match="body hash must be finalized"):
        kinematic_rigid_body_hash(forged_body)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("schema_version", "kinematic-model@999"),
        ("evaluator_version", "multi-joint-forward-kinematics@999"),
        ("transform_agreement_version", "rigid-transform-agreement@999"),
    ),
)
def test_v2_model_hash_rejects_forged_model_versions(field, value):
    _, model = _grouped_fk_fixture()
    forged_model = model.model_copy(update={field: value})

    with pytest.raises(ValueError):
        kinematic_model_hash(forged_model)


def test_v2_nonzero_fk_rejects_forged_joint_schema():
    assembly, model = _grouped_fk_fixture()
    forged_joint = model.joints[0].model_copy(
        update={"schema_version": "revolute-joint-model@999"}
    )
    forged_model = model.model_copy(
        update={"joints": (forged_joint, model.joints[1])}
    )

    with pytest.raises(ValueError):
        MultiJointKinematicsService().evaluate(
            assembly,
            forged_model,
            JointConfiguration(
                model_id=forged_model.model_id,
                positions={"J1": 30.0, "J2": 45.0},
            ),
        )


def test_v2_nonzero_collision_rejects_forged_joint_schema_before_provider():
    assembly, model = _grouped_fk_fixture()
    forged_joint = model.joints[0].model_copy(
        update={"schema_version": "revolute-joint-model@999"}
    )
    forged_model = model.model_copy(
        update={"joints": (forged_joint, model.joints[1])}
    )
    request = _v2_collision_request(
        assembly,
        model,
        (ExactConstituentPair(first_instance_id="A1", second_instance_id="B1"),),
        configurations=(
            JointConfiguration(
                model_id=forged_model.model_id,
                positions={"J1": 30.0, "J2": 45.0},
            ),
        ),
    ).model_copy(
        update={"model": forged_model, "model_hash": "pending", "request_hash": "pending"}
    )
    provider_calls = []

    def exact_measure(received_request, transformed):
        provider_calls.append(received_request)
        return tuple(
            (first, second, 0.0, 100.0)
            for first, second in received_request.pairs
        )

    service = MultiJointDiscreteCollisionSweepService(
        TransientAssemblyAnalysisService(exact_measure)
    )

    with pytest.raises(ValueError):
        service.execute(request, assembly)

    assert provider_calls == []


def test_v2_continuous_request_rejects_forged_model_before_extent_provider():
    from mechcad_harness.multi_joint_continuous_clearance import (
        MultiJointContinuousClearanceProofService,
    )

    assembly, model = _grouped_fk_fixture()
    pair = ExactConstituentPair(first_instance_id="A1", second_instance_id="B1")
    valid_request = _v2_continuous_request_for_pair(assembly, model, pair)
    forged_joint = model.joints[0].model_copy(
        update={"schema_version": "revolute-joint-model@999"}
    )
    forged_model = model.model_copy(
        update={"joints": (forged_joint, model.joints[1])}
    )
    forged_request = valid_request.model_copy(
        update={"model": forged_model, "model_hash": "pending", "request_hash": "pending"}
    )
    extent_calls = []

    def extent_provider(source, requested_model, instance_ids):
        extent_calls.append((source, requested_model, instance_ids))
        return _v2_extents_for(source)

    with pytest.raises(ValueError):
        MultiJointContinuousClearanceProofService(
            exact_measure=lambda received, transformed: (),
            extent_provider=extent_provider,
        ).execute(forged_request, assembly)

    assert extent_calls == []
