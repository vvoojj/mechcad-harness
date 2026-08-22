from __future__ import annotations

import math

import pytest

from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.multi_joint_continuous_path import (
    ARTICULATED_DESCENDANT_REACH_BOUND_VERSION,
    COMPONENT_LOCAL_GEOMETRY_EXTENT_VERSION,
    JointConfiguration,
    MultiJointContinuousPathRequest,
    MultiJointPath,
    TrustedLocalGeometryExtent,
    derive_reach_bounds,
)
from mechcad_harness.multi_joint_kinematics import (
    KinematicModel,
    RevoluteJointModel,
    joint_configuration_hash,
    kinematic_model_hash,
)


PART = CadPartProgram(
    part_id="part",
    operations=(BasePlateOperation(operation_id="plate", length_mm=10, width_mm=4, thickness_mm=2),),
)


def assembly() -> CadAssemblyProgram:
    return CadAssemblyProgram(
        assembly_id="path-assembly",
        parts=(PART,),
        instances=(
            CadComponentInstance(instance_id="base", part_id="part"),
            CadComponentInstance(instance_id="link-1", part_id="part", placement=CadRigidTransform(x_mm=20)),
            CadComponentInstance(instance_id="link-2", part_id="part", placement=CadRigidTransform(x_mm=50)),
        ),
    )


def model() -> KinematicModel:
    return KinematicModel(
        model_id="path-model",
        joints=(
            RevoluteJointModel(joint_id="j1", parent_instance_id="base", child_instance_id="link-1"),
            RevoluteJointModel(joint_id="j2", parent_instance_id="link-1", child_instance_id="link-2", axis_origin_x_mm=20),
        ),
    )


def config(model_id: str, **positions: float) -> JointConfiguration:
    return JointConfiguration(model_id=model_id, positions=positions)


def path() -> MultiJointPath:
    mdl = model()
    return MultiJointPath(
        model_id=mdl.model_id,
        waypoints=(
            config(mdl.model_id, j1=0, j2=0),
            config(mdl.model_id, j1=360, j2=720),
        ),
    )


def test_path_interpolates_raw_commands_and_preserves_order_semantics():
    requested = path()
    midpoint = requested.interpolate(0, 0.5)
    assert midpoint.positions == {"j1": 180.0, "j2": 360.0}
    assert requested.interpolate(0, 0).positions == {"j1": 0.0, "j2": 0.0}
    assert requested.interpolate(0, 1).positions == {"j1": 360.0, "j2": 720.0}

    reordered = MultiJointPath(
        model_id=requested.model_id,
        waypoints=tuple(reversed(requested.waypoints)),
    )
    assert reordered.path_hash != requested.path_hash

    mapping_reordered = JointConfiguration(
        model_id="path-model", positions={"j2": 0, "j1": 0}
    )
    assert joint_configuration_hash(mapping_reordered) == joint_configuration_hash(requested.waypoints[0])


def test_path_rejects_invalid_schema_and_non_finite_values():
    with pytest.raises(ValueError, match="at least 2"):
        MultiJointPath(model_id="path-model", waypoints=(config("path-model", j1=0, j2=0),))
    with pytest.raises(ValueError, match="model ID"):
        MultiJointPath(
            model_id="path-model",
            waypoints=(config("other", j1=0, j2=0), config("other", j1=1, j2=1)),
        )
    with pytest.raises(ValueError, match="finite"):
        JointConfiguration(model_id="path-model", positions={"j1": math.inf, "j2": 0})


def test_request_identity_contains_ordered_waypoints_and_resource_limits():
    mdl = model()
    requested = MultiJointContinuousPathRequest(
        source_assembly_id=assembly().assembly_id,
        source_assembly_hash=assembly_hash(assembly()),
        model=mdl,
        path=path(),
        moving_instance_ids=("link-1", "link-2"),
        stationary_instance_ids=("base",),
        max_exact_evaluations=3,
    )
    changed_budget = requested.model_copy(update={"max_exact_evaluations": 4, "request_hash": "pending"})
    assert requested.request_hash != changed_budget.request_hash
    assert requested.model_hash == kinematic_model_hash(mdl)


def test_reach_bounds_are_pure_and_include_chain_offsets_and_extent():
    mdl = model()
    source = assembly()
    extents = {
        "base": TrustedLocalGeometryExtent(instance_id="base", component_identity="part@1", local_radius_mm=3),
        "link-1": TrustedLocalGeometryExtent(instance_id="link-1", component_identity="part@1", local_radius_mm=3),
        "link-2": TrustedLocalGeometryExtent(instance_id="link-2", component_identity="part@1", local_radius_mm=4),
    }
    bounds = derive_reach_bounds(source, mdl, extents)
    assert bounds.algorithm_version == ARTICULATED_DESCENDANT_REACH_BOUND_VERSION
    assert bounds.extent_algorithm_version == COMPONENT_LOCAL_GEOMETRY_EXTENT_VERSION
    assert bounds.for_instance_joint("link-2", "j1").reach_bound_mm >= 34
    assert bounds.for_instance_joint("link-2", "j2").reach_bound_mm >= 14
    assert bounds.for_instance_joint("base", "j1") is None
    assert all(record.offset_lengths_mm for record in bounds.records if record.instance_id == "link-2")
