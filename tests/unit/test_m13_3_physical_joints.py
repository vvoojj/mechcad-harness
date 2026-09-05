from __future__ import annotations

import hashlib
import json
import math

import pytest
from pydantic import ValidationError

from mechcad_harness.candidates import (
    GeneratedReferenceFrameAxisSource as ExportedGeneratedReferenceFrameAxisSource,
    GeneratedRotationalInterfaceAxisSource as ExportedGeneratedRotationalInterfaceAxisSource,
    PhysicalAxisOwnerEndpoint as ExportedPhysicalAxisOwnerEndpoint,
    PhysicalJointMotionMode as ExportedPhysicalJointMotionMode,
    PhysicalRevoluteJointBinding as ExportedPhysicalRevoluteJointBinding,
    SuppliedReferenceFrameAxisSource as ExportedSuppliedReferenceFrameAxisSource,
    SuppliedRotationalInterfaceAxisSource as ExportedSuppliedRotationalInterfaceAxisSource,
)
from mechcad_harness.candidates.models import (
    GeneratedReferenceFrameAxisSource,
    GeneratedRotationalInterfaceAxisSource,
    PhysicalAxisOwnerEndpoint,
    PhysicalJointMotionMode,
    PhysicalRevoluteJointBinding,
    SuppliedReferenceFrameAxisSource,
    SuppliedRotationalInterfaceAxisSource,
)


_SHA = "sha256:" + "a" * 64
_SHA_B = "sha256:" + "b" * 64


def _hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _source_kwargs(source_kind: str) -> dict:
    common = {
        "source_physical_instance_id": "instance-axis",
    }
    if source_kind == "supplied_rotational_interface":
        return common | {
            "interface_id": "supplied-interface",
            "interface_hash": _SHA,
            "geometry_reference_hash": _SHA_B,
            "specification_hash": _SHA,
        }
    if source_kind == "supplied_reference_frame":
        return common | {
            "frame_id": "supplied-frame",
            "frame_hash": _SHA,
            "geometry_reference_hash": _SHA_B,
            "specification_hash": _SHA,
        }
    if source_kind == "generated_rotational_interface":
        return common | {
            "interface_id": "generated-interface",
            "interface_hash": _SHA,
            "generated_specification_hash": _SHA_B,
        }
    if source_kind == "generated_reference_frame":
        return common | {
            "frame_id": "generated-frame",
            "frame_hash": _SHA,
            "generated_specification_hash": _SHA_B,
        }
    raise AssertionError(source_kind)


@pytest.mark.parametrize(
    ("source_kind", "source_type", "fields"),
    [
        (
            "supplied_rotational_interface",
            SuppliedRotationalInterfaceAxisSource,
            {
                "schema_version",
                "source_kind",
                "source_physical_instance_id",
                "interface_id",
                "interface_hash",
                "geometry_reference_hash",
                "specification_hash",
                "source_hash",
            },
        ),
        (
            "supplied_reference_frame",
            SuppliedReferenceFrameAxisSource,
            {
                "schema_version",
                "source_kind",
                "source_physical_instance_id",
                "frame_id",
                "frame_hash",
                "geometry_reference_hash",
                "specification_hash",
                "source_hash",
            },
        ),
        (
            "generated_rotational_interface",
            GeneratedRotationalInterfaceAxisSource,
            {
                "schema_version",
                "source_kind",
                "source_physical_instance_id",
                "interface_id",
                "interface_hash",
                "generated_specification_hash",
                "source_hash",
            },
        ),
        (
            "generated_reference_frame",
            GeneratedReferenceFrameAxisSource,
            {
                "schema_version",
                "source_kind",
                "source_physical_instance_id",
                "frame_id",
                "frame_hash",
                "generated_specification_hash",
                "source_hash",
            },
        ),
    ],
)
def test_each_axis_source_has_exact_wire_shape_and_self_hash(
    source_kind: str, source_type: type, fields: set[str]
):
    source = source_type(**_source_kwargs(source_kind))
    wire = source.model_dump(mode="json")

    assert set(wire) == fields
    assert wire["schema_version"] == f"{source_kind.replace('_', '-')}-axis-source@1"
    assert wire["source_kind"] == source_kind
    assert source.source_hash == _hash({key: value for key, value in wire.items() if key != "source_hash"})


def test_axis_sources_are_discriminated_when_revalidated_from_wire():
    source = GeneratedReferenceFrameAxisSource(**_source_kwargs("generated_reference_frame"))
    binding = _joint(axis_source=source)
    restored = PhysicalRevoluteJointBinding.model_validate(binding.model_dump(mode="json"))

    assert type(restored.axis_source) is GeneratedReferenceFrameAxisSource
    assert restored.axis_source.source_kind == "generated_reference_frame"


def test_axis_source_and_joint_symbols_are_publicly_exported():
    assert ExportedSuppliedRotationalInterfaceAxisSource is SuppliedRotationalInterfaceAxisSource
    assert ExportedSuppliedReferenceFrameAxisSource is SuppliedReferenceFrameAxisSource
    assert ExportedGeneratedRotationalInterfaceAxisSource is GeneratedRotationalInterfaceAxisSource
    assert ExportedGeneratedReferenceFrameAxisSource is GeneratedReferenceFrameAxisSource
    assert ExportedPhysicalAxisOwnerEndpoint is PhysicalAxisOwnerEndpoint
    assert ExportedPhysicalJointMotionMode is PhysicalJointMotionMode
    assert ExportedPhysicalRevoluteJointBinding is PhysicalRevoluteJointBinding
    assert [member.value for member in PhysicalAxisOwnerEndpoint] == ["parent", "child"]
    assert [member.value for member in PhysicalJointMotionMode] == ["bounded", "continuous"]


def _joint(**overrides) -> PhysicalRevoluteJointBinding:
    values = {
        "physical_joint_id": "joint-main",
        "parent_physical_body_id": "body-parent",
        "child_physical_body_id": "body-child",
        "connection_id": "connection-main",
        "parent_physical_instance_id": "instance-parent",
        "parent_interface_id": "interface-parent",
        "child_physical_instance_id": "instance-child",
        "child_interface_id": "interface-child",
        "axis_source": SuppliedRotationalInterfaceAxisSource(**_source_kwargs("supplied_rotational_interface")),
        "axis_owner_endpoint": PhysicalAxisOwnerEndpoint.PARENT,
        "axis_sign": 1,
        "motion_mode": PhysicalJointMotionMode.BOUNDED,
        "min_angle_deg": -720.0,
        "max_angle_deg": 1080.0,
        "zero_reference_semantics": "accepted-semantic-home@1",
    }
    return PhysicalRevoluteJointBinding(**(values | overrides))


def test_joint_has_exact_fields_and_hashes_all_semantic_fields():
    joint = _joint()
    wire = joint.model_dump(mode="json")

    assert set(wire) == {
        "schema_version",
        "physical_joint_id",
        "parent_physical_body_id",
        "child_physical_body_id",
        "connection_id",
        "parent_physical_instance_id",
        "parent_interface_id",
        "child_physical_instance_id",
        "child_interface_id",
        "axis_source",
        "axis_owner_endpoint",
        "axis_sign",
        "motion_mode",
        "min_angle_deg",
        "max_angle_deg",
        "zero_reference_semantics",
        "binding_hash",
    }
    assert joint.binding_hash == _hash({key: value for key, value in wire.items() if key != "binding_hash"})

    changed_owner = _joint(axis_owner_endpoint=PhysicalAxisOwnerEndpoint.CHILD)
    changed_sign = _joint(axis_sign=-1)
    changed_source_identity = _joint(
        axis_source=SuppliedRotationalInterfaceAxisSource(
            **(_source_kwargs("supplied_rotational_interface") | {"interface_id": "other-interface"})
        )
    )
    assert changed_owner.binding_hash != joint.binding_hash
    assert changed_sign.binding_hash != joint.binding_hash
    assert changed_source_identity.binding_hash != joint.binding_hash
    assert changed_source_identity.axis_source.source_hash != joint.axis_source.source_hash


def test_bounded_joint_preserves_finite_multi_turn_limits():
    joint = _joint(min_angle_deg=-1440.0, max_angle_deg=2160.0)

    assert joint.motion_mode is PhysicalJointMotionMode.BOUNDED
    assert joint.min_angle_deg == -1440.0
    assert joint.max_angle_deg == 2160.0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("min_angle_deg", True),
        ("max_angle_deg", False),
        ("min_angle_deg", "not-a-number"),
        ("max_angle_deg", "not-a-number"),
    ],
)
def test_joint_rejects_raw_bool_or_nonnumeric_string_angle_limits(field, value):
    with pytest.raises((ValueError, ValidationError)):
        _joint(**{field: value})


def test_continuous_joint_requires_both_limits_to_be_none():
    joint = _joint(
        motion_mode=PhysicalJointMotionMode.CONTINUOUS,
        min_angle_deg=None,
        max_angle_deg=None,
    )

    assert joint.min_angle_deg is None
    assert joint.max_angle_deg is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"axis_owner_endpoint": "other"},
        {"axis_sign": True},
        {"axis_sign": 0},
        {"axis_sign": 2},
        {"zero_reference_semantics": "home"},
        {"motion_mode": PhysicalJointMotionMode.BOUNDED, "min_angle_deg": None},
        {"motion_mode": PhysicalJointMotionMode.BOUNDED, "max_angle_deg": None},
        {"motion_mode": PhysicalJointMotionMode.BOUNDED, "min_angle_deg": 1.0, "max_angle_deg": 1.0},
        {"motion_mode": PhysicalJointMotionMode.BOUNDED, "min_angle_deg": 2.0, "max_angle_deg": 1.0},
        {"motion_mode": PhysicalJointMotionMode.BOUNDED, "min_angle_deg": math.inf},
        {"motion_mode": PhysicalJointMotionMode.BOUNDED, "max_angle_deg": math.nan},
        {"motion_mode": PhysicalJointMotionMode.CONTINUOUS, "min_angle_deg": 0.0},
        {"motion_mode": PhysicalJointMotionMode.CONTINUOUS, "max_angle_deg": 1.0},
    ],
)
def test_joint_rejects_invalid_owner_sign_zero_semantics_or_limits(overrides):
    with pytest.raises((ValueError, ValidationError)):
        _joint(**overrides)


@pytest.mark.parametrize(
    "source_type",
    [
        SuppliedRotationalInterfaceAxisSource,
        SuppliedReferenceFrameAxisSource,
        GeneratedRotationalInterfaceAxisSource,
        GeneratedReferenceFrameAxisSource,
    ],
)
def test_axis_source_rejects_blank_identity_or_hash_mismatch(source_type):
    source_kind = {
        SuppliedRotationalInterfaceAxisSource: "supplied_rotational_interface",
        SuppliedReferenceFrameAxisSource: "supplied_reference_frame",
        GeneratedRotationalInterfaceAxisSource: "generated_rotational_interface",
        GeneratedReferenceFrameAxisSource: "generated_reference_frame",
    }[source_type]
    values = _source_kwargs(source_kind)
    identity_field = "interface_id" if "interface" in source_kind else "frame_id"

    with pytest.raises((ValueError, ValidationError)):
        source_type(**(values | {"source_physical_instance_id": " "}))
    with pytest.raises((ValueError, ValidationError)):
        source_type(**(values | {identity_field: "\t"}))
    with pytest.raises((ValueError, ValidationError)):
        source_type(**(values | {"source_hash": _SHA_B}))


def test_joint_rejects_stale_binding_hash_and_unknown_fields():
    joint = _joint()

    with pytest.raises((ValueError, ValidationError)):
        PhysicalRevoluteJointBinding.model_validate(
            joint.model_dump(mode="json") | {"binding_hash": _SHA_B}
        )
    with pytest.raises((ValueError, ValidationError)):
        PhysicalRevoluteJointBinding.model_validate(
            joint.model_dump(mode="json") | {"unrelated": "not-allowed"}
        )
