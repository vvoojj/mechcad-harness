from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from mechcad_harness.models import (
    CanonicalGeneratedReferenceFrameAxisSource,
    CanonicalGeneratedRotationalInterfaceAxisSource,
    CanonicalMultiJointVerificationObligation,
    CanonicalPhysicalMechanism,
    CanonicalPhysicalPairClassificationBinding,
    CanonicalPhysicalRigidBodyBinding,
    CanonicalPhysicalRevoluteJointBinding,
    CanonicalComponentSpecification,
    CanonicalPhysicalComponent,
    CanonicalMechanicalConnection,
    CanonicalMechanicalConnectionKind,
    CanonicalConnectionMeaning,
    CanonicalSuppliedReferenceFrameAxisSource,
    CanonicalSuppliedRotationalInterfaceAxisSource,
    PhysicalPairClassification,
    physical_kinematic_root_hash,
    physical_pair_classification_set_hash,
)
from mechcad_harness.multi_joint_kinematics import JointConfiguration, joint_configuration_hash
from mechcad_harness.models.multi_joint_verification import (
    MultiJointVerificationConfigurationSet,
    configuration_set_hash,
)


_SHA_A = "sha256:" + "a" * 64
_SHA_B = "sha256:" + "b" * 64


def _hash(payload: dict) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _source(source_kind: str, **updates):
    common = {"source_physical_instance_id": "canonical-instance-axis"}
    if source_kind == "supplied_rotational_interface":
        values = common | {
            "interface_id": "canonical-interface",
            "interface_hash": _SHA_A,
            "geometry_reference_hash": _SHA_B,
            "specification_hash": _SHA_A,
        }
        source_type = CanonicalSuppliedRotationalInterfaceAxisSource
    elif source_kind == "supplied_reference_frame":
        values = common | {
            "frame_id": "canonical-frame",
            "frame_hash": _SHA_A,
            "geometry_reference_hash": _SHA_B,
            "specification_hash": _SHA_A,
        }
        source_type = CanonicalSuppliedReferenceFrameAxisSource
    elif source_kind == "generated_rotational_interface":
        values = common | {
            "interface_id": "canonical-generated-interface",
            "interface_hash": _SHA_A,
            "generated_specification_hash": _SHA_B,
        }
        source_type = CanonicalGeneratedRotationalInterfaceAxisSource
    elif source_kind == "generated_reference_frame":
        values = common | {
            "frame_id": "canonical-generated-frame",
            "frame_hash": _SHA_A,
            "generated_specification_hash": _SHA_B,
        }
        source_type = CanonicalGeneratedReferenceFrameAxisSource
    else:
        raise AssertionError(source_kind)
    return source_type(**(values | updates))


@pytest.mark.parametrize(
    ("source_kind", "source_type"),
    [
        ("supplied_rotational_interface", CanonicalSuppliedRotationalInterfaceAxisSource),
        ("supplied_reference_frame", CanonicalSuppliedReferenceFrameAxisSource),
        ("generated_rotational_interface", CanonicalGeneratedRotationalInterfaceAxisSource),
        ("generated_reference_frame", CanonicalGeneratedReferenceFrameAxisSource),
    ],
)
def test_canonical_axis_sources_have_distinct_wire_shapes_and_independent_hashes(
    source_kind, source_type
):
    source = _source(source_kind)
    wire = source.model_dump(mode="json")

    expected_fields = {
        "supplied_rotational_interface": {
            "schema_version", "source_kind", "source_physical_instance_id", "interface_id",
            "interface_hash", "geometry_reference_hash", "specification_hash", "source_hash",
        },
        "supplied_reference_frame": {
            "schema_version", "source_kind", "source_physical_instance_id", "frame_id",
            "frame_hash", "geometry_reference_hash", "specification_hash", "source_hash",
        },
        "generated_rotational_interface": {
            "schema_version", "source_kind", "source_physical_instance_id", "interface_id",
            "interface_hash", "generated_specification_hash", "source_hash",
        },
        "generated_reference_frame": {
            "schema_version", "source_kind", "source_physical_instance_id", "frame_id",
            "frame_hash", "generated_specification_hash", "source_hash",
        },
    }[source_kind]
    assert set(wire) == expected_fields
    assert wire["schema_version"] == f"canonical-{source_kind.replace('_', '-')}-axis-source@1"
    assert wire["source_kind"] == source_kind
    assert source.source_hash == _hash(
        {key: value for key, value in wire.items() if key != "source_hash"}
    )
    assert "candidate" not in json.dumps(wire)


def test_canonical_body_and_pair_bindings_are_sorted_and_hash_bound_independently():
    body = CanonicalPhysicalRigidBodyBinding(
        physical_body_id="body-a",
        member_physical_instance_ids=("instance-z", "instance-a"),
        reference_physical_instance_id="instance-a",
    )
    assert body.member_physical_instance_ids == ("instance-a", "instance-z")
    assert body.binding_hash == _hash(
        {
            "schema_version": "canonical-physical-rigid-body-binding@1",
            "physical_body_id": "body-a",
            "member_physical_instance_ids": ["instance-a", "instance-z"],
            "reference_physical_instance_id": "instance-a",
        }
    )

    pair = CanonicalPhysicalPairClassificationBinding(
        first_physical_instance_id="instance-z",
        second_physical_instance_id="instance-a",
        classification=PhysicalPairClassification.CHECK_CLEARANCE,
        exclusion_reason=None,
    )
    assert (pair.first_physical_instance_id, pair.second_physical_instance_id) == (
        "instance-a",
        "instance-z",
    )
    assert pair.binding_hash == _hash(
        {
            "schema_version": "canonical-physical-pair-classification-binding@1",
            "first_physical_instance_id": "instance-a",
            "second_physical_instance_id": "instance-z",
            "classification": "check_clearance",
            "exclusion_reason": None,
        }
    )
    assert physical_pair_classification_set_hash((pair,)) != pair.binding_hash


def test_canonical_joint_recomputes_source_and_joint_hashes():
    source = _source("supplied_rotational_interface")
    joint = CanonicalPhysicalRevoluteJointBinding(
        physical_joint_id="joint-a",
        parent_physical_body_id="body-a",
        child_physical_body_id="body-b",
        connection_id="connection-a",
        parent_physical_instance_id="instance-parent",
        parent_interface_id="interface-parent",
        child_physical_instance_id="instance-child",
        child_interface_id="interface-child",
        axis_source=source,
        axis_owner_endpoint="parent",
        axis_sign=1,
        motion_mode="bounded",
        min_angle_deg=-10.0,
        max_angle_deg=20.0,
        zero_reference_semantics="accepted-semantic-home@1",
    )
    wire = joint.model_dump(mode="json")
    assert set(wire) == {
        "schema_version", "physical_joint_id", "parent_physical_body_id",
        "child_physical_body_id", "connection_id", "parent_physical_instance_id",
        "parent_interface_id", "child_physical_instance_id", "child_interface_id",
        "axis_source", "axis_owner_endpoint", "axis_sign", "motion_mode",
        "min_angle_deg", "max_angle_deg", "zero_reference_semantics", "binding_hash",
    }
    assert joint.binding_hash == _hash(
        {key: value for key, value in wire.items() if key != "binding_hash"}
    )
    assert joint.axis_source.source_hash != _SHA_A
    assert "candidate-instance" not in json.dumps(wire)


def _configuration_set() -> MultiJointVerificationConfigurationSet:
    configurations = (
        JointConfiguration(model_id="physical-to-m10-v2-model@1:abc", positions={"joint-a": 0.0}),
        JointConfiguration(model_id="physical-to-m10-v2-model@1:abc", positions={"joint-a": 720.0}),
    )
    return MultiJointVerificationConfigurationSet(configurations=configurations)


def _mechanism_v3(**updates) -> CanonicalPhysicalMechanism:
    parent_specification = CanonicalComponentSpecification(
        component_type="mount", source_identity="source:mount@1", interfaces=("axis",)
    )
    child_specification = CanonicalComponentSpecification(
        component_type="shaft", source_identity="source:shaft@1", interfaces=("axis",)
    )
    parent = CanonicalPhysicalComponent(
        instance_id="instance-parent",
        specification_hash=parent_specification.specification_hash,
        role="mount_or_support",
        interfaces=("axis",),
    )
    child = CanonicalPhysicalComponent(
        instance_id="instance-child",
        specification_hash=child_specification.specification_hash,
        role="shaft",
        interfaces=("axis",),
    )
    connection = CanonicalMechanicalConnection(
        connection_id="connection-a",
        kind=CanonicalMechanicalConnectionKind.ROTATIONAL_DRIVE,
        from_instance_id="instance-parent",
        from_interface_id="axis",
        to_instance_id="instance-child",
        to_interface_id="axis",
        meanings=(CanonicalConnectionMeaning.KINEMATIC_REALIZATION_INTENT,),
    )
    body_parent = CanonicalPhysicalRigidBodyBinding(
        physical_body_id="body-parent",
        member_physical_instance_ids=("instance-parent",),
        reference_physical_instance_id="instance-parent",
    )
    body_child = CanonicalPhysicalRigidBodyBinding(
        physical_body_id="body-child",
        member_physical_instance_ids=("instance-child",),
        reference_physical_instance_id="instance-child",
    )
    joint = CanonicalPhysicalRevoluteJointBinding(
        physical_joint_id="joint-a",
        parent_physical_body_id="body-parent",
        child_physical_body_id="body-child",
        connection_id=connection.connection_id,
        parent_physical_instance_id="instance-parent",
        parent_interface_id="axis",
        child_physical_instance_id="instance-child",
        child_interface_id="axis",
        axis_source=_source(
            "supplied_rotational_interface", source_physical_instance_id="instance-parent"
        ),
        axis_owner_endpoint="parent",
        axis_sign=1,
        motion_mode="bounded",
        min_angle_deg=-10.0,
        max_angle_deg=20.0,
        zero_reference_semantics="accepted-semantic-home@1",
    )
    pair = CanonicalPhysicalPairClassificationBinding(
        first_physical_instance_id="instance-parent",
        second_physical_instance_id="instance-child",
        classification=PhysicalPairClassification.CHECK_CLEARANCE,
        exclusion_reason=None,
    )
    values = {
        "schema_version": "canonical-physical-mechanism@3",
        "id": "mechanism-v3",
        "name": "mechanism v3",
        "component_specifications": (parent_specification, child_specification),
        "components": (parent, child),
        "connections": (connection,),
        "physical_rigid_body_bindings": (body_parent, body_child),
        "physical_revolute_joint_bindings": (joint,),
        "kinematic_root_physical_body_id": "body-parent",
        "kinematic_root_binding_hash": physical_kinematic_root_hash("body-parent"),
        "physical_pair_classification_bindings": (pair,),
        "multi_joint_verification_obligations": (
            CanonicalMultiJointVerificationObligation(
                configuration_set=_configuration_set(),
                volume_tolerance_mm3=0.001,
                distance_tolerance_mm=0.002,
            ),
        ),
    }
    values.update(updates)
    return CanonicalPhysicalMechanism(**values)


def test_configuration_set_preserves_order_and_hashes_actual_configurations():
    value = _configuration_set()
    assert value.configuration_hashes == tuple(joint_configuration_hash(item) for item in value.configurations)
    assert value.configuration_set_hash == configuration_set_hash(value)
    assert value.configuration_set_hash == _hash(
        {
            "schema_version": "multi-joint-verification-configuration-set@1",
            "configurations": [item.model_dump(mode="json") for item in value.configurations],
        }
    )
    assert MultiJointVerificationConfigurationSet.model_validate(
        value.model_dump(mode="json")
    ) == value


def test_canonical_obligation_has_exact_frozen_fields_and_hash():
    configuration_set = _configuration_set()
    obligation = CanonicalMultiJointVerificationObligation(
        configuration_set=configuration_set,
        volume_tolerance_mm3=0.001,
        distance_tolerance_mm=0.002,
    )
    wire = obligation.model_dump(mode="json")
    assert set(wire) == {
        "schema_version",
        "configuration_set",
        "volume_tolerance_mm3",
        "distance_tolerance_mm",
        "configuration_set_hash",
        "obligation_hash",
    }
    assert obligation.configuration_set_hash == configuration_set.configuration_set_hash
    assert obligation.obligation_hash == _hash(
        {key: value for key, value in wire.items() if key != "obligation_hash"}
    )
    assert CanonicalMultiJointVerificationObligation.model_validate(wire) == obligation


def test_canonical_mechanism_v3_round_trips_and_hashes_projected_authority():
    mechanism = _mechanism_v3()
    wire = mechanism.model_dump(mode="json")

    assert mechanism.physical_rigid_body_bindings == tuple(
        sorted(mechanism.physical_rigid_body_bindings, key=lambda item: item.physical_body_id)
    )
    assert mechanism.physical_revolute_joint_bindings[0].physical_joint_id == "joint-a"
    assert mechanism.multi_joint_verification_obligations[0].obligation_hash.startswith("sha256:")
    assert CanonicalPhysicalMechanism.model_validate(wire) == mechanism
    assert mechanism.mechanism_hash == _hash(
        {key: value for key, value in wire.items() if key != "mechanism_hash"}
    )


def test_canonical_mechanism_v3_requires_exactly_one_obligation_and_rejects_v3_fields_in_old_versions():
    mechanism = _mechanism_v3()
    legacy_payload = {
        key: value
        for key, value in mechanism.model_dump(mode="python").items()
        if key not in {
            "schema_version",
            "physical_rigid_body_bindings",
            "physical_revolute_joint_bindings",
            "kinematic_root_physical_body_id",
            "kinematic_root_binding_hash",
            "physical_pair_classification_bindings",
            "multi_joint_verification_obligations",
            "mechanism_hash",
        }
    }
    legacy_payload["mechanism_hash"] = "pending"
    with pytest.raises((ValidationError, ValueError)):
        CanonicalPhysicalMechanism.model_validate(
            legacy_payload
            | {
                "schema_version": "canonical-physical-mechanism@1",
                "multi_joint_verification_obligations": mechanism.multi_joint_verification_obligations,
            }
        )

    with pytest.raises((ValidationError, ValueError)):
        CanonicalPhysicalMechanism.model_validate(
            legacy_payload
            | {
                "schema_version": "canonical-physical-mechanism@2",
                "physical_rigid_body_bindings": mechanism.physical_rigid_body_bindings,
            }
        )


@pytest.mark.parametrize(
    "obligations",
    [(), (_configuration_set(),)],
)
def test_zero_or_non_obligation_canonical_v3_values_are_rejected(obligations):
    with pytest.raises((ValidationError, ValueError)):
        _mechanism_v3(multi_joint_verification_obligations=obligations)


def test_multiple_canonical_obligations_are_rejected_even_when_distinct():
    obligation = _mechanism_v3().multi_joint_verification_obligations[0]
    second = obligation.model_copy(
        update={"distance_tolerance_mm": 0.003, "obligation_hash": "pending"}
    )
    with pytest.raises((ValidationError, ValueError)):
        _mechanism_v3(multi_joint_verification_obligations=(obligation, second))
