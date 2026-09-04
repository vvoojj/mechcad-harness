from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Literal

from pydantic import Field, model_validator

from mechcad_harness.cad_assembly import CadAssemblyProgram
from mechcad_harness.models.common import Model
from mechcad_harness.multi_joint_kinematics import (
    JointConfiguration,
    KinematicModel,
    KinematicModelV2,
    MultiJointKinematicsService,
    transform_apply,
    transform_compose,
    transform_inverse,
    joint_configuration_hash,
    kinematic_model_hash,
    revalidate_v2_kinematic_model,
)
from mechcad_harness.multi_joint_pair_scope import (
    EXACT_CONSTITUENT_PAIR_SCOPE_VERSION,
    ExactConstituentPair,
    canonical_exact_pair_scope,
    exact_pair_scope_hash,
)


MULTI_JOINT_PATH_INTERPOLATION_VERSION = "piecewise-linear-joint-command-path@1.0"
ARTICULATED_DESCENDANT_REACH_BOUND_VERSION = "articulated-descendant-reach-bound@1.0"
COMPONENT_LOCAL_GEOMETRY_EXTENT_VERSION = "component-local-geometry-extent@1.0"
MULTI_JOINT_CONTINUOUS_PATH_PROOF_VERSION = "conservative-multi-joint-path-clearance-proof@1.0"
BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION = "body-member-reach-bound-plumbing@2.0"
_BOUND_PADDING_MM = 1e-9


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


class MultiJointPath(Model):
    model_id: str = Field(min_length=1)
    waypoints: tuple[JointConfiguration, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_path(self):
        if any(waypoint.model_id != self.model_id for waypoint in self.waypoints):
            raise ValueError("waypoint model ID does not match path model ID")
        schemas = [frozenset(waypoint.positions) for waypoint in self.waypoints]
        if any(schema != schemas[0] for schema in schemas[1:]):
            raise ValueError("waypoint joint schemas must match")
        return self

    @property
    def path_hash(self) -> str:
        return _digest({
            "model_id": self.model_id,
            "interpolation_version": MULTI_JOINT_PATH_INTERPOLATION_VERSION,
            "waypoint_hashes": [joint_configuration_hash(waypoint) for waypoint in self.waypoints],
        })

    def interpolate(self, segment_index: int, t: float) -> JointConfiguration:
        if not 0 <= segment_index < len(self.waypoints) - 1:
            raise ValueError("segment index out of range")
        if not math.isfinite(t) or not 0 <= t <= 1:
            raise ValueError("path parameter must be finite and within [0, 1]")
        first, second = self.waypoints[segment_index : segment_index + 2]
        return JointConfiguration(
            model_id=self.model_id,
            positions={
                joint_id: first.positions[joint_id]
                + t * (second.positions[joint_id] - first.positions[joint_id])
                for joint_id in sorted(first.positions)
            },
        )


class TrustedLocalGeometryExtent(Model):
    """Trusted geometry boundary output; no geometry access is performed here."""

    instance_id: str = Field(min_length=1)
    component_identity: str = Field(min_length=1)
    local_radius_mm: float = Field(ge=0)
    extent_algorithm_version: str = COMPONENT_LOCAL_GEOMETRY_EXTENT_VERSION


class ReachBoundRecord(Model):
    instance_id: str = Field(min_length=1)
    influencing_joint_id: str = Field(min_length=1)
    component_identity: str = Field(min_length=1)
    local_geometry_radius_mm: float = Field(ge=0)
    offset_lengths_mm: tuple[float, ...]
    reach_bound_mm: float = Field(ge=0)
    chain_instance_ids: tuple[str, ...] = Field(min_length=1)
    algorithm_version: str = ARTICULATED_DESCENDANT_REACH_BOUND_VERSION


class ReachBoundTable(Model):
    algorithm_version: str = ARTICULATED_DESCENDANT_REACH_BOUND_VERSION
    extent_algorithm_version: str = COMPONENT_LOCAL_GEOMETRY_EXTENT_VERSION
    records: tuple[ReachBoundRecord, ...]

    def for_instance_joint(self, instance_id: str, joint_id: str) -> ReachBoundRecord | None:
        return next(
            (record for record in self.records
             if record.instance_id == instance_id and record.influencing_joint_id == joint_id),
            None,
        )


class ReachBoundRecordV2(Model):
    instance_id: str = Field(min_length=1)
    influencing_joint_id: str = Field(min_length=1)
    component_identity: str = Field(min_length=1)
    local_geometry_radius_mm: float = Field(ge=0)
    offset_lengths_mm: tuple[float, ...]
    reach_bound_mm: float = Field(ge=0)
    chain_body_ids: tuple[str, ...] = Field(min_length=1)
    algorithm_version: Literal["body-member-reach-bound-plumbing@2.0"]


class ReachBoundTableV2(Model):
    algorithm_version: Literal["body-member-reach-bound-plumbing@2.0"]
    extent_algorithm_version: str = Field(min_length=1)
    records: tuple[ReachBoundRecordV2, ...]

    def for_instance_joint(
        self, instance_id: str, joint_id: str
    ) -> ReachBoundRecordV2 | None:
        return next(
            (
                record
                for record in self.records
                if record.instance_id == instance_id
                and record.influencing_joint_id == joint_id
            ),
            None,
        )


def _parent_chain(model: KinematicModel, instance_id: str) -> list:
    by_child = {joint.child_instance_id: joint for joint in model.joints}
    chain = []
    current = instance_id
    while current in by_child:
        joint = by_child[current]
        chain.append(joint)
        current = joint.parent_instance_id
    chain.reverse()
    return chain


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt(sum((left - right) ** 2 for left, right in zip(a, b)))


def derive_reach_bounds(
    assembly: CadAssemblyProgram,
    model: KinematicModel | KinematicModelV2,
    extents: Mapping[str, TrustedLocalGeometryExtent],
) -> ReachBoundTable | ReachBoundTableV2:
    """Pure topology calculation over trusted local geometry extents."""
    if isinstance(model, KinematicModelV2):
        model = revalidate_v2_kinematic_model(model)
        return _derive_v2_reach_bounds(assembly, model, extents)

    MultiJointKinematicsService().evaluate(
        assembly,
        model,
        JointConfiguration(
            model_id=model.model_id,
            positions={joint.joint_id: 0.0 for joint in model.joints},
        ),
    )
    instance_by_id = {instance.instance_id: instance for instance in assembly.instances}
    records = []
    for instance_id, instance in instance_by_id.items():
        extent = extents.get(instance_id)
        if extent is None:
            raise ValueError(f"missing trusted local geometry extent for {instance_id}")
        if extent.instance_id != instance_id:
            raise ValueError(f"geometry extent instance mismatch for {instance_id}")
        chain = _parent_chain(model, instance_id)
        for influencing in chain:
            start = next(index for index, joint in enumerate(chain) if joint.joint_id == influencing.joint_id)
            relevant = chain[start:]
            offsets = []
            home_world = {
                item.instance_id: item.placement for item in assembly.instances
            }
            first = relevant[0]
            first_parent = home_world[first.parent_instance_id]
            first_child = transform_compose(
                transform_inverse(first_parent), home_world[first.child_instance_id]
            )
            offsets.append(_distance(first.axis_origin, transform_apply(first_child, (0.0, 0.0, 0.0))))
            for joint in relevant[1:]:
                parent_to_child = transform_compose(
                    transform_inverse(home_world[joint.parent_instance_id]),
                    home_world[joint.child_instance_id],
                )
                offsets.append(_distance((0.0, 0.0, 0.0), joint.axis_origin))
                child_in_parent = transform_apply(parent_to_child, (0.0, 0.0, 0.0))
                offsets.append(_distance(joint.axis_origin, child_in_parent))
            records.append(ReachBoundRecord(
                instance_id=instance_id,
                influencing_joint_id=influencing.joint_id,
                component_identity=extent.component_identity,
                local_geometry_radius_mm=extent.local_radius_mm,
                offset_lengths_mm=tuple(offsets),
                reach_bound_mm=extent.local_radius_mm + sum(offsets) + _BOUND_PADDING_MM,
                chain_instance_ids=tuple(
                    [influencing.parent_instance_id]
                    + [joint.child_instance_id for joint in relevant]
                ),
            ))
    return ReachBoundTable(records=tuple(records))


def _v2_body_parent_chain(model: KinematicModelV2, body_id: str) -> list:
    by_child = {joint.child_body_id: joint for joint in model.joints}
    chain = []
    current = body_id
    while current in by_child:
        joint = by_child[current]
        chain.append(joint)
        current = joint.parent_body_id
    chain.reverse()
    return chain


def _derive_v2_reach_bounds(
    assembly: CadAssemblyProgram,
    model: KinematicModelV2,
    extents: Mapping[str, TrustedLocalGeometryExtent],
) -> ReachBoundTableV2:
    """Derive the same telescoping bound inputs for grouped body members."""
    model = revalidate_v2_kinematic_model(model)
    MultiJointKinematicsService().evaluate(
        assembly,
        model,
        JointConfiguration(
            model_id=model.model_id,
            positions={joint.joint_id: 0.0 for joint in model.joints},
        ),
    )
    instance_by_id = {instance.instance_id: instance for instance in assembly.instances}
    member_by_id = {
        member.member_instance_id: (body, member)
        for body in model.bodies
        for member in body.members
    }
    body_home = {
        body.body_id: instance_by_id[body.reference_member_instance_id].placement
        for body in model.bodies
    }
    records = []
    for instance_id, (body, member) in member_by_id.items():
        extent = extents.get(instance_id)
        if extent is None:
            raise ValueError(f"missing trusted local geometry extent for {instance_id}")
        if extent.instance_id != instance_id:
            raise ValueError(f"geometry extent instance mismatch for {instance_id}")
        chain = _v2_body_parent_chain(model, body.body_id)
        for influencing in chain:
            start = next(
                index
                for index, joint in enumerate(chain)
                if joint.joint_id == influencing.joint_id
            )
            relevant = chain[start:]
            offsets = []
            first = relevant[0]
            first_parent = body_home[first.parent_body_id]
            first_child = transform_compose(
                transform_inverse(first_parent), body_home[first.child_body_id]
            )
            offsets.append(
                _distance(
                    first.axis_origin,
                    transform_apply(first_child, (0.0, 0.0, 0.0)),
                )
            )
            for joint in relevant[1:]:
                parent_to_child = transform_compose(
                    transform_inverse(body_home[joint.parent_body_id]),
                    body_home[joint.child_body_id],
                )
                offsets.append(_distance((0.0, 0.0, 0.0), joint.axis_origin))
                child_in_parent = transform_apply(parent_to_child, (0.0, 0.0, 0.0))
                offsets.append(_distance(joint.axis_origin, child_in_parent))
            offsets.append(
                _distance(
                    (0.0, 0.0, 0.0),
                    transform_apply(member.reference_to_member_home, (0.0, 0.0, 0.0)),
                )
            )
            records.append(
                ReachBoundRecordV2(
                    instance_id=instance_id,
                    influencing_joint_id=influencing.joint_id,
                    component_identity=extent.component_identity,
                    local_geometry_radius_mm=extent.local_radius_mm,
                    offset_lengths_mm=tuple(offsets),
                    reach_bound_mm=extent.local_radius_mm
                    + sum(offsets)
                    + _BOUND_PADDING_MM,
                    chain_body_ids=tuple(
                        [influencing.parent_body_id]
                        + [joint.child_body_id for joint in relevant]
                    ),
                    algorithm_version=BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION,
                )
            )
    return ReachBoundTableV2(
        algorithm_version=BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION,
        extent_algorithm_version=COMPONENT_LOCAL_GEOMETRY_EXTENT_VERSION,
        records=tuple(records),
    )


class MultiJointContinuousPathRequest(Model):
    source_assembly_id: str = Field(min_length=1)
    source_assembly_hash: str = Field(min_length=1)
    model: KinematicModel
    path: MultiJointPath
    moving_instance_ids: tuple[str, ...] = Field(min_length=1)
    stationary_instance_ids: tuple[str, ...] = Field(min_length=1)
    required_clearance_mm: float = Field(default=0, ge=0)
    proof_guard_mm: float = Field(default=1e-6, ge=0)
    volume_tolerance_mm3: float = Field(default=1e-9, ge=0)
    distance_tolerance_mm: float = Field(default=1e-7, ge=0)
    max_depth: int = Field(default=16, ge=0)
    minimum_path_interval: float = Field(default=1e-6, gt=0)
    max_exact_evaluations: int = Field(default=4096, ge=1)
    model_hash: str = "pending"
    request_hash: str = "pending"

    @model_validator(mode="after")
    def validate_request(self):
        if self.path.model_id != self.model.model_id:
            raise ValueError("path model ID does not match request model")
        joint_by_id = {joint.joint_id: joint for joint in self.model.joints}
        expected_joint_ids = set(joint_by_id)
        if frozenset(self.path.waypoints[0].positions) != expected_joint_ids:
            raise ValueError("path joint schema does not match model")
        for waypoint in self.path.waypoints:
            for joint_id, angle in waypoint.positions.items():
                joint = joint_by_id[joint_id]
                if joint.min_angle_deg is not None and angle < joint.min_angle_deg:
                    raise ValueError(f"joint {joint_id!r} waypoint is below its minimum limit")
                if joint.max_angle_deg is not None and angle > joint.max_angle_deg:
                    raise ValueError(f"joint {joint_id!r} waypoint is above its maximum limit")
        expected_model_hash = kinematic_model_hash(self.model)
        if self.model_hash == "pending":
            self.model_hash = expected_model_hash
        elif self.model_hash != expected_model_hash:
            raise ValueError("model hash mismatch")
        if set(self.moving_instance_ids) & set(self.stationary_instance_ids):
            raise ValueError("moving and stationary instance IDs overlap")
        payload = {
            "source_assembly_id": self.source_assembly_id,
            "source_assembly_hash": self.source_assembly_hash,
            "model_hash": self.model_hash,
            "path_hash": self.path.path_hash,
            "moving_instance_ids": self.moving_instance_ids,
            "stationary_instance_ids": self.stationary_instance_ids,
            "required_clearance_mm": self.required_clearance_mm,
            "proof_guard_mm": self.proof_guard_mm,
            "volume_tolerance_mm3": self.volume_tolerance_mm3,
            "distance_tolerance_mm": self.distance_tolerance_mm,
            "max_depth": self.max_depth,
            "minimum_path_interval": self.minimum_path_interval,
            "max_exact_evaluations": self.max_exact_evaluations,
            "proof_algorithm_version": MULTI_JOINT_CONTINUOUS_PATH_PROOF_VERSION,
            "reach_bound_algorithm_version": ARTICULATED_DESCENDANT_REACH_BOUND_VERSION,
        }
        expected_request_hash = _digest(payload)
        if self.request_hash == "pending":
            self.request_hash = expected_request_hash
        elif self.request_hash != expected_request_hash:
            raise ValueError("request hash mismatch")
        return self

    @property
    def pairs(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (moving, stationary)
            for moving in self.moving_instance_ids
            for stationary in self.stationary_instance_ids
        )


class MultiJointContinuousPathRequestV2(Model):
    schema_version: Literal["multi-joint-continuous-path-request@2"]
    source_assembly_id: str = Field(min_length=1)
    source_assembly_hash: str = Field(min_length=1)
    model: KinematicModelV2
    path: MultiJointPath
    exact_pair_scope: tuple[ExactConstituentPair, ...]
    required_clearance_mm: float = 0.0
    proof_guard_mm: float = 1e-6
    volume_tolerance_mm3: float = 1e-9
    distance_tolerance_mm: float = 1e-7
    max_depth: int = 16
    minimum_path_interval: float = 1e-6
    max_exact_evaluations: int = 4096
    model_hash: str = "pending"
    request_hash: str = "pending"

    @model_validator(mode="after")
    def validate_request(self):
        object.__setattr__(self, "model", revalidate_v2_kinematic_model(self.model))
        if self.schema_version != "multi-joint-continuous-path-request@2":
            raise ValueError("continuous path request schema version is not v2")
        if not self.source_assembly_hash.startswith("sha256:"):
            raise ValueError("source assembly hash must be a sha256 identity")
        if self.model.evaluator_version != "multi-joint-forward-kinematics@2.0":
            raise ValueError("kinematic model evaluator version is not trusted v2")
        if self.path.model_id != self.model.model_id:
            raise ValueError("path model ID does not match request model")
        joint_by_id = {joint.joint_id: joint for joint in self.model.joints}
        expected_joint_ids = set(joint_by_id)
        for waypoint in self.path.waypoints:
            if set(waypoint.positions) != expected_joint_ids:
                raise ValueError("path joint schema does not match model")
            for joint_id, angle in waypoint.positions.items():
                joint = joint_by_id[joint_id]
                if joint.min_angle_deg is not None and angle < joint.min_angle_deg:
                    raise ValueError(f"joint {joint_id!r} waypoint is below its minimum limit")
                if joint.max_angle_deg is not None and angle > joint.max_angle_deg:
                    raise ValueError(f"joint {joint_id!r} waypoint is above its maximum limit")
        if not all(
            math.isfinite(value) and value >= 0
            for value in (
                self.required_clearance_mm,
                self.proof_guard_mm,
                self.volume_tolerance_mm3,
                self.distance_tolerance_mm,
            )
        ):
            raise ValueError("continuous proof tolerances must be finite and non-negative")
        if self.max_depth < 0:
            raise ValueError("max depth must be non-negative")
        if not math.isfinite(self.minimum_path_interval) or self.minimum_path_interval <= 0:
            raise ValueError("minimum path interval must be finite and positive")
        if self.max_exact_evaluations < 1:
            raise ValueError("maximum exact evaluations must be positive")

        canonical_scope = canonical_exact_pair_scope(self.exact_pair_scope)
        object.__setattr__(self, "exact_pair_scope", canonical_scope)

        expected_model_hash = kinematic_model_hash(self.model)
        if self.model_hash == "pending":
            self.model_hash = expected_model_hash
        elif self.model_hash != expected_model_hash:
            raise ValueError("model hash mismatch")
        payload = {
            "schema_version": self.schema_version,
            "source_assembly_id": self.source_assembly_id,
            "source_assembly_hash": self.source_assembly_hash,
            "model_hash": self.model_hash,
            "path_hash": self.path.path_hash,
            "exact_pair_scope_hash": exact_pair_scope_hash(canonical_scope),
            "exact_pair_scope_version": EXACT_CONSTITUENT_PAIR_SCOPE_VERSION,
            "required_clearance_mm": self.required_clearance_mm,
            "proof_guard_mm": self.proof_guard_mm,
            "volume_tolerance_mm3": self.volume_tolerance_mm3,
            "distance_tolerance_mm": self.distance_tolerance_mm,
            "max_depth": self.max_depth,
            "minimum_path_interval": self.minimum_path_interval,
            "max_exact_evaluations": self.max_exact_evaluations,
            "proof_algorithm_version": MULTI_JOINT_CONTINUOUS_PATH_PROOF_VERSION,
            "reach_bound_algorithm_version": BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION,
        }
        expected_request_hash = _digest(payload)
        if self.request_hash == "pending":
            self.request_hash = expected_request_hash
        elif self.request_hash != expected_request_hash:
            raise ValueError("request hash mismatch")
        return self

    @property
    def pairs(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (pair.first_instance_id, pair.second_instance_id)
            for pair in self.exact_pair_scope
        )


__all__ = [
    "ARTICULATED_DESCENDANT_REACH_BOUND_VERSION",
    "BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION",
    "COMPONENT_LOCAL_GEOMETRY_EXTENT_VERSION",
    "JointConfiguration",
    "MultiJointContinuousPathRequest",
    "MultiJointContinuousPathRequestV2",
    "MultiJointPath",
    "ReachBoundRecord",
    "ReachBoundRecordV2",
    "ReachBoundTable",
    "ReachBoundTableV2",
    "TrustedLocalGeometryExtent",
    "derive_reach_bounds",
]
