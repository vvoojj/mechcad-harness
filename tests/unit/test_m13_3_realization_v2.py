from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from mechcad_harness.candidates import (
    PhysicalComponentInstance,
    PhysicalComponentRole,
    PhysicalMechanismRealization,
    PhysicalRevoluteJointBinding,
    PhysicalRigidBodyBinding,
    SuppliedReferenceFrameAxisSource,
    candidate_hash,
    physical_kinematic_root_hash,
)
from mechcad_harness.candidates.models import (
    ConnectionMeaning,
    MechanicalConnection,
    MechanicalConnectionKind,
    PhysicalJointMotionMode,
    PhysicalAxisOwnerEndpoint,
)
from mechcad_harness.models import PhysicalPairClassification, PhysicalPairClassificationBinding


_SPEC_HASH = "sha256:" + "a" * 64
_AUTHORITY_HASH = "sha256:" + "b" * 64


def _hash(payload: dict) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _components() -> tuple[PhysicalComponentInstance, ...]:
    return (
        PhysicalComponentInstance(
            instance_id="instance-a",
            specification_hash=_SPEC_HASH,
            role=PhysicalComponentRole.ROTATING_MEMBER,
            interfaces=("axis",),
        ),
        PhysicalComponentInstance(
            instance_id="instance-b",
            specification_hash=_SPEC_HASH,
            role=PhysicalComponentRole.DRIVEN_BODY,
            interfaces=("axis",),
        ),
        PhysicalComponentInstance(
            instance_id="instance-unassigned",
            specification_hash=_SPEC_HASH,
            role=PhysicalComponentRole.PAYLOAD_OR_FRAME_ATTACHMENT,
            interfaces=("payload",),
        ),
    )


def _connection() -> MechanicalConnection:
    return MechanicalConnection(
        connection_id="connection-main",
        kind=MechanicalConnectionKind.ROTATIONAL_DRIVE,
        from_instance_id="instance-a",
        from_interface_id="axis",
        to_instance_id="instance-b",
        to_interface_id="axis",
        meanings=(ConnectionMeaning.KINEMATIC_REALIZATION_INTENT,),
    )


def _source() -> SuppliedReferenceFrameAxisSource:
    return SuppliedReferenceFrameAxisSource(
        source_physical_instance_id="instance-a",
        frame_id="frame-axis",
        frame_hash=_AUTHORITY_HASH,
        geometry_reference_hash=_SPEC_HASH,
        specification_hash=_AUTHORITY_HASH,
    )


def _joint(joint_id: str = "joint-main") -> PhysicalRevoluteJointBinding:
    return PhysicalRevoluteJointBinding(
        physical_joint_id=joint_id,
        parent_physical_body_id="body-parent",
        child_physical_body_id="body-child",
        connection_id="connection-main",
        parent_physical_instance_id="instance-a",
        parent_interface_id="axis",
        child_physical_instance_id="instance-b",
        child_interface_id="axis",
        axis_source=_source(),
        axis_owner_endpoint=PhysicalAxisOwnerEndpoint.PARENT,
        axis_sign=1,
        motion_mode=PhysicalJointMotionMode.BOUNDED,
        min_angle_deg=-90.0,
        max_angle_deg=90.0,
        zero_reference_semantics="accepted-semantic-home@1",
    )


def _body(body_id: str, member: str) -> PhysicalRigidBodyBinding:
    return PhysicalRigidBodyBinding(
        physical_body_id=body_id,
        member_physical_instance_ids=(member,),
        reference_physical_instance_id=member,
    )


def _pair(first: str, second: str) -> PhysicalPairClassificationBinding:
    return PhysicalPairClassificationBinding(
        first_physical_instance_id=first,
        second_physical_instance_id=second,
        classification=PhysicalPairClassification.CHECK_CLEARANCE,
        exclusion_reason=None,
    )


def _realization_v2(**overrides) -> PhysicalMechanismRealization:
    values = {
        "schema_version": "physical-mechanism-realization@2",
        "components": _components(),
        "connections": (_connection(),),
        "joint_bindings": (),
        "physical_rigid_body_bindings": (_body("body-child", "instance-b"), _body("body-parent", "instance-a")),
        "physical_revolute_joint_bindings": (_joint(),),
        "kinematic_root_physical_body_id": "body-parent",
        "kinematic_root_binding_hash": physical_kinematic_root_hash("body-parent"),
        "physical_pair_classification_bindings": (_pair("instance-b", "instance-a"),),
    }
    return PhysicalMechanismRealization(**(values | overrides))


def test_realization_v1_wire_and_hash_remain_historically_literal():
    component = _components()[0]
    realization = PhysicalMechanismRealization(components=(component,))
    expected_without_hash = {
        "schema_version": "physical-mechanism-realization@1",
        "components": [component.model_dump(mode="json")],
        "connections": [],
        "joint_bindings": [],
    }
    expected = expected_without_hash | {
        "realization_hash": _hash(expected_without_hash),
    }

    assert realization.model_dump(mode="json") == expected
    assert realization.model_dump_json() == json.dumps(expected, separators=(",", ":"))
    assert realization.realization_hash == _hash(expected_without_hash)


def test_realization_v2_has_exact_sorted_wire_payload_and_hash():
    realization = _realization_v2()
    wire = realization.model_dump(mode="json")

    assert list(wire) == [
        "schema_version",
        "components",
        "connections",
        "joint_bindings",
        "physical_rigid_body_bindings",
        "physical_revolute_joint_bindings",
        "kinematic_root_physical_body_id",
        "kinematic_root_binding_hash",
        "physical_pair_classification_bindings",
        "realization_hash",
    ]
    assert [item["physical_body_id"] for item in wire["physical_rigid_body_bindings"]] == [
        "body-child",
        "body-parent",
    ]
    assert [item["physical_joint_id"] for item in wire["physical_revolute_joint_bindings"]] == [
        "joint-main",
    ]
    assert [(item["first_physical_instance_id"], item["second_physical_instance_id"]) for item in wire["physical_pair_classification_bindings"]] == [
        ("instance-a", "instance-b"),
    ]
    expected_payload = dict(wire)
    expected_payload.pop("realization_hash")
    assert realization.realization_hash == _hash(expected_payload)


def test_realization_v2_requires_all_versioned_fields_but_allows_partial_universe():
    values = {
        "schema_version": "physical-mechanism-realization@2",
        "components": _components(),
        "physical_rigid_body_bindings": (_body("body-parent", "instance-a"),),
        "physical_revolute_joint_bindings": (),
        "kinematic_root_physical_body_id": "body-parent",
        "kinematic_root_binding_hash": physical_kinematic_root_hash("body-parent"),
        "physical_pair_classification_bindings": (),
    }
    realization = PhysicalMechanismRealization(**values)

    assert realization.physical_rigid_body_bindings[0].physical_body_id == "body-parent"
    assert "instance-unassigned" in {component.instance_id for component in realization.components}

    for field in (
        "physical_rigid_body_bindings",
        "physical_revolute_joint_bindings",
        "kinematic_root_physical_body_id",
        "kinematic_root_binding_hash",
        "physical_pair_classification_bindings",
    ):
        missing = values.copy()
        missing.pop(field)
        with pytest.raises((ValueError, ValidationError)):
            PhysicalMechanismRealization(**missing)


@pytest.mark.parametrize(
    "field,value",
    [
        ("physical_rigid_body_bindings", (_body("body-parent", "instance-a"),)),
        ("physical_revolute_joint_bindings", (_joint(),)),
        ("kinematic_root_physical_body_id", "body-parent"),
        ("kinematic_root_binding_hash", physical_kinematic_root_hash("body-parent")),
        ("physical_pair_classification_bindings", (_pair("instance-a", "instance-b"),)),
    ],
)
def test_realization_v1_rejects_every_m13_3_field(field, value):
    with pytest.raises((ValueError, ValidationError)):
        PhysicalMechanismRealization(
            schema_version="physical-mechanism-realization@1",
            components=(_components()[0],),
            **{field: value},
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"kinematic_root_binding_hash": _AUTHORITY_HASH},
        {"kinematic_root_physical_body_id": "body-missing"},
        {"physical_rigid_body_bindings": (_body("body-parent", "instance-missing"),)},
        {"physical_revolute_joint_bindings": (_joint(joint_id="joint-main"), _joint(joint_id="joint-main"))},
        {"physical_pair_classification_bindings": (_pair("instance-a", "instance-b"), _pair("instance-b", "instance-a"))},
        {"physical_pair_classification_bindings": (_pair("instance-a", "instance-missing"),)},
    ],
)
def test_realization_v2_rejects_bad_root_uniqueness_and_basic_references(kwargs):
    with pytest.raises((ValueError, ValidationError)):
        _realization_v2(**kwargs)


def test_mechanical_design_candidate_stays_v1_and_binds_versioned_realization():
    from test_m12_candidate_foundation import _candidate

    candidate, _, _ = _candidate()
    assert candidate.schema_version == "mechanical-design-candidate@1"
    assert candidate.realization.schema_version == "physical-mechanism-realization@1"
    assert candidate.candidate_hash == candidate_hash(candidate)

    versioned_realization = PhysicalMechanismRealization(
        schema_version="physical-mechanism-realization@2",
        components=candidate.realization.components,
        connections=candidate.realization.connections,
        joint_bindings=candidate.realization.joint_bindings,
        physical_rigid_body_bindings=(_body("body-parent", "motor"),),
        physical_revolute_joint_bindings=(),
        kinematic_root_physical_body_id="body-parent",
        kinematic_root_binding_hash=physical_kinematic_root_hash("body-parent"),
        physical_pair_classification_bindings=(),
    )
    versioned_candidate = candidate.model_copy(
        update={"realization": versioned_realization, "candidate_hash": "pending"}
    )
    assert candidate_hash(versioned_candidate) != candidate.candidate_hash
