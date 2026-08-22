from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from enum import StrEnum

from pydantic import Field, model_validator

from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.kinematic_sweep import (
    _quaternion_multiply,
    _rotation_quaternion,
    _rotate_vector,
)
from mechcad_harness.models.common import Model


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MULTI_JOINT_FORWARD_KINEMATICS_VERSION = "multi-joint-forward-kinematics@1.0"


# ---------------------------------------------------------------------------
# Transform helpers
# ---------------------------------------------------------------------------


def transform_apply(
    T: CadRigidTransform, p: tuple[float, float, float]
) -> tuple[float, float, float]:
    """Apply rigid transform to a point: rot(q, p) + t."""
    rotated = _rotate_vector(p, T.rotation_quaternion)
    return (T.x_mm + rotated[0], T.y_mm + rotated[1], T.z_mm + rotated[2])


def transform_compose(
    first: CadRigidTransform,
    second: CadRigidTransform,
) -> CadRigidTransform:
    """Compose rigid transforms: result = first . second (apply second then first).

    Composed rotation:    first.q * second.q   (quaternion multiply)
    Composed translation: first.t + rot(first.q, second.t)
    """
    q = _quaternion_multiply(first.rotation_quaternion, second.rotation_quaternion)
    t = _rotate_vector(
        (second.x_mm, second.y_mm, second.z_mm),
        first.rotation_quaternion,
    )
    return CadRigidTransform(
        x_mm=first.x_mm + t[0],
        y_mm=first.y_mm + t[1],
        z_mm=first.z_mm + t[2],
        rotation_quaternion=q,
    )


def transform_inverse(T: CadRigidTransform) -> CadRigidTransform:
    """Inverse of a rigid transform.

    For T(p) = rot(q, p) + t, the inverse is inv(p) = rot(conj(q), p - t).
    """
    q = T.rotation_quaternion
    conj = (q[0], -q[1], -q[2], -q[3])
    neg_t = (-T.x_mm, -T.y_mm, -T.z_mm)
    rotated = _rotate_vector(neg_t, conj)
    return CadRigidTransform(
        x_mm=rotated[0],
        y_mm=rotated[1],
        z_mm=rotated[2],
        rotation_quaternion=conj,
    )


class _FakeAxis:
    """Minimal axis-like object for reusing _rotation_quaternion."""

    __slots__ = ("direction_x", "direction_y", "direction_z")

    def __init__(self, dx: float, dy: float, dz: float):
        self.direction_x = dx
        self.direction_y = dy
        self.direction_z = dz


def axis_rotation_transform(
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
    angle_deg: float,
) -> CadRigidTransform:
    """Joint rotation about axis in parent-local frame.

    For parent-local axis point p = origin and unit direction u = direction,
    returns a rigid transform equivalent to:

        T_joint(q) = Translate(p) . Rotate(u, q) . Translate(-p)

    This rotates about the arbitrary axis point p (not the parent origin
    unless p == (0, 0, 0)).

    The translation component is p - rot(q, p).
    The rotation quaternion is from the existing _rotation_quaternion helper.
    """
    q = _rotation_quaternion(
        _FakeAxis(direction[0], direction[1], direction[2]),
        angle_deg,
    )
    rotated_origin = _rotate_vector(origin, q)
    return CadRigidTransform(
        x_mm=origin[0] - rotated_origin[0],
        y_mm=origin[1] - rotated_origin[1],
        z_mm=origin[2] - rotated_origin[2],
        rotation_quaternion=q,
    )


# ---------------------------------------------------------------------------
# Joint kind
# ---------------------------------------------------------------------------


class KinematicJointKind(StrEnum):
    REVOLUTE = "revolute"


# ---------------------------------------------------------------------------
# Joint model
# ---------------------------------------------------------------------------


class RevoluteJointModel(Model):
    """Revolute joint in a kinematic model.

    Axis origin and direction are expressed in the PARENT INSTANCE LOCAL FRAME.
    """

    joint_id: str = Field(min_length=1)
    joint_kind: KinematicJointKind = KinematicJointKind.REVOLUTE
    parent_instance_id: str = Field(min_length=1)
    child_instance_id: str = Field(min_length=1)
    axis_origin_x_mm: float = 0.0
    axis_origin_y_mm: float = 0.0
    axis_origin_z_mm: float = 0.0
    axis_direction_x: float = 0.0
    axis_direction_y: float = 0.0
    axis_direction_z: float = 1.0
    min_angle_deg: float | None = None
    max_angle_deg: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_axis(cls, data):
        data = dict(data)
        defaults = {
            "axis_origin_x_mm": 0.0,
            "axis_origin_y_mm": 0.0,
            "axis_origin_z_mm": 0.0,
            "axis_direction_x": 0.0,
            "axis_direction_y": 0.0,
            "axis_direction_z": 1.0,
        }
        values = tuple(
            float(data.get(name, defaults[name]))
            for name in (
                "axis_origin_x_mm",
                "axis_origin_y_mm",
                "axis_origin_z_mm",
                "axis_direction_x",
                "axis_direction_y",
                "axis_direction_z",
            )
        )
        if any(not math.isfinite(v) for v in values):
            raise ValueError("joint axis values must be finite")
        direction = values[3:]
        norm = math.sqrt(sum(v * v for v in direction))
        if norm <= 1e-12:
            raise ValueError("joint axis direction must be non-zero")
        data["axis_direction_x"] = direction[0] / norm
        data["axis_direction_y"] = direction[1] / norm
        data["axis_direction_z"] = direction[2] / norm
        return data

    @model_validator(mode="after")
    def _validate_limits(self):
        if self.min_angle_deg is not None and self.max_angle_deg is not None:
            if self.min_angle_deg > self.max_angle_deg:
                raise ValueError(
                    "joint min_angle_deg must be <= max_angle_deg"
                )
        return self

    @property
    def axis_origin(self) -> tuple[float, float, float]:
        return (self.axis_origin_x_mm, self.axis_origin_y_mm, self.axis_origin_z_mm)

    @property
    def axis_direction(self) -> tuple[float, float, float]:
        return (self.axis_direction_x, self.axis_direction_y, self.axis_direction_z)


# ---------------------------------------------------------------------------
# Kinematic model
# ---------------------------------------------------------------------------


class KinematicModel(Model):
    """Generic multi-joint kinematic model.

    Contains the topology (joints connecting parent/child instances) and
    evaluator version. The model itself has deterministic identity via
    kinematic_model_hash().
    """

    model_id: str = Field(min_length=1)
    joints: tuple[RevoluteJointModel, ...] = Field(default_factory=tuple)
    evaluator_version: str = MULTI_JOINT_FORWARD_KINEMATICS_VERSION

    @model_validator(mode="after")
    def _validate_unique_joint_ids(self):
        ids = [j.joint_id for j in self.joints]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate joint IDs in kinematic model")
        return self


def kinematic_model_hash(model: KinematicModel) -> str:
    """Deterministic SHA-256 over model semantic fields."""
    payload = {
        "model_id": model.model_id,
        "evaluator_version": model.evaluator_version,
        "joints": [
            {
                "joint_id": j.joint_id,
                "joint_kind": j.joint_kind.value,
                "parent_instance_id": j.parent_instance_id,
                "child_instance_id": j.child_instance_id,
                "axis_origin": [
                    j.axis_origin_x_mm,
                    j.axis_origin_y_mm,
                    j.axis_origin_z_mm,
                ],
                "axis_direction": [
                    j.axis_direction_x,
                    j.axis_direction_y,
                    j.axis_direction_z,
                ],
                "min_angle_deg": j.min_angle_deg,
                "max_angle_deg": j.max_angle_deg,
            }
            for j in sorted(model.joints, key=lambda j: j.joint_id)
        ],
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


# ---------------------------------------------------------------------------
# Joint configuration
# ---------------------------------------------------------------------------


class JointConfiguration(Model):
    """Explicit multi-joint configuration.

    positions maps joint_id -> angle_deg. The exact commanded angle is
    preserved (0, 360, 720 are distinct configurations).
    """

    model_id: str = Field(min_length=1)
    positions: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_positions(self):
        for joint_id, angle in self.positions.items():
            if not isinstance(angle, (int, float)) or not math.isfinite(
                float(angle)
            ):
                raise ValueError(
                    f"joint position for {joint_id!r} must be finite"
                )
        return self


def joint_configuration_hash(configuration: JointConfiguration) -> str:
    """Deterministic SHA-256 over model_id and sorted positions."""
    payload = {
        "model_id": configuration.model_id,
        "positions": tuple(sorted(configuration.positions.items())),
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


# ---------------------------------------------------------------------------
# Forward-kinematics result types
# ---------------------------------------------------------------------------


class EvaluatedJointState(Model):
    """Per-joint evaluation state in a kinematic configuration result."""

    joint_id: str = Field(min_length=1)
    joint_position_deg: float
    within_limits: bool


class InstanceWorldTransform(Model):
    """World transform for one instance after forward-kinematics evaluation."""

    instance_id: str = Field(min_length=1)
    is_articulated: bool
    transform: CadRigidTransform


class KinematicForwardKinematicsResult(Model):
    """Deterministic result of multi-joint forward-kinematics evaluation.

    Represents ONE explicit multi-joint configuration. Does NOT contain
    collision classification, clearance, or continuous verification.
    """

    evaluator_version: str = Field(min_length=1)
    source_assembly_hash: str = Field(min_length=1)
    model_hash: str = Field(min_length=1)
    configuration_hash: str = Field(min_length=1)
    transformed_assembly_hash: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    ordered_joint_states: tuple[EvaluatedJointState, ...] = Field(
        default_factory=tuple
    )
    instance_world_transforms: tuple[InstanceWorldTransform, ...] = Field(
        default_factory=tuple
    )
    transformed_assembly: CadAssemblyProgram
    result_hash: str = "pending"


def kinematic_forward_kinematics_result_hash(
    result: KinematicForwardKinematicsResult,
) -> str:
    """Return the canonical identity for one FK result payload."""
    payload = result.model_dump(
        mode="json", exclude={"result_hash", "transformed_assembly"}
    )
    return f"sha256:{hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}"


# ---------------------------------------------------------------------------
# Topology validation and traversal
# ---------------------------------------------------------------------------


class _KinematicTopology:
    """Validated topology of a kinematic model against an assembly."""

    __slots__ = (
        "joint_by_child",
        "child_joints_of",
        "roots",
        "articulated_children",
        "evaluation_order",
    )

    def __init__(
        self,
        joint_by_child: dict[str, RevoluteJointModel],
        child_joints_of: dict[str, list[RevoluteJointModel]],
        roots: tuple[str, ...],
        articulated_children: frozenset[str],
        evaluation_order: tuple[RevoluteJointModel, ...],
    ):
        self.joint_by_child = joint_by_child
        self.child_joints_of = child_joints_of
        self.roots = roots
        self.articulated_children = articulated_children
        self.evaluation_order = evaluation_order


def _build_kinematic_topology(
    assembly: CadAssemblyProgram,
    model: KinematicModel,
) -> _KinematicTopology:
    """Validate and build deterministic topology from model + assembly.

    Raises ValueError on invalid topology (fail closed).
    """
    instance_ids = {inst.instance_id for inst in assembly.instances}

    joint_ids = [j.joint_id for j in model.joints]
    if len(set(joint_ids)) != len(joint_ids):
        raise ValueError("duplicate joint IDs")

    for joint in model.joints:
        if joint.parent_instance_id not in instance_ids:
            raise ValueError(
                f"joint {joint.joint_id!r}: parent "
                f"{joint.parent_instance_id!r} not in assembly"
            )
        if joint.child_instance_id not in instance_ids:
            raise ValueError(
                f"joint {joint.joint_id!r}: child "
                f"{joint.child_instance_id!r} not in assembly"
            )
        if joint.parent_instance_id == joint.child_instance_id:
            raise ValueError(
                f"joint {joint.joint_id!r}: parent == child "
                f"({joint.parent_instance_id!r})"
            )

    joint_by_child: dict[str, RevoluteJointModel] = {}
    for joint in model.joints:
        if joint.child_instance_id in joint_by_child:
            existing = joint_by_child[joint.child_instance_id]
            raise ValueError(
                f"child {joint.child_instance_id!r} has two parent joints: "
                f"{existing.joint_id!r} and {joint.joint_id!r}"
            )
        joint_by_child[joint.child_instance_id] = joint

    _detect_cycles(model)

    child_joints_of: dict[str, list[RevoluteJointModel]] = {}
    for joint in model.joints:
        child_joints_of.setdefault(joint.parent_instance_id, []).append(joint)

    roots = tuple(
        sorted(
            inst_id
            for inst_id in instance_ids
            if inst_id not in joint_by_child
        )
    )

    articulated_children = frozenset(joint_by_child.keys())
    evaluation_order: list[RevoluteJointModel] = []
    visited_nodes: set[str] = set()
    queue: deque[str] = deque(sorted(roots))

    while queue:
        node = queue.popleft()
        if node in visited_nodes:
            continue
        visited_nodes.add(node)
        for joint in sorted(
            child_joints_of.get(node, []), key=lambda j: j.joint_id
        ):
            evaluation_order.append(joint)
            queue.append(joint.child_instance_id)

    reachable_articulated = visited_nodes & articulated_children
    unreachable = articulated_children - reachable_articulated
    if unreachable:
        raise ValueError(
            "articulated instances unreachable from roots: "
            f"{sorted(unreachable)}"
        )

    return _KinematicTopology(
        joint_by_child=joint_by_child,
        child_joints_of=child_joints_of,
        roots=roots,
        articulated_children=articulated_children,
        evaluation_order=tuple(evaluation_order),
    )


def _detect_cycles(model: KinematicModel) -> None:
    """Detect cycles in the parent-child graph."""
    if not model.joints:
        return

    child_to_parent_joint: dict[str, RevoluteJointModel] = {}
    for joint in model.joints:
        child_to_parent_joint[joint.child_instance_id] = joint

    for start_joint in model.joints:
        visited: set[str] = set()
        current = start_joint.child_instance_id
        while current in child_to_parent_joint:
            if current in visited:
                raise ValueError("cycle detected in kinematic topology")
            visited.add(current)
            current = child_to_parent_joint[current].parent_instance_id


# ---------------------------------------------------------------------------
# Forward-kinematics service
# ---------------------------------------------------------------------------


class MultiJointKinematicsService:
    """Deterministic multi-joint forward-kinematics evaluator.

    Produces a transformed CadAssemblyProgram from a source assembly,
    kinematic model, and joint configuration. No FreeCAD dependency.
    """

    def evaluate(
        self,
        assembly: CadAssemblyProgram,
        model: KinematicModel,
        configuration: JointConfiguration,
    ) -> KinematicForwardKinematicsResult:
        """Evaluate forward kinematics for one explicit configuration.

        Args:
            assembly: Source CadAssemblyProgram (home configuration).
            model: Kinematic model defining joints and topology.
            configuration: Joint positions (one per required joint).

        Returns:
            Deterministic result with transformed assembly and world transforms.
        """
        model_joint_ids = {j.joint_id for j in model.joints}
        config_joint_ids = set(configuration.positions.keys())
        if config_joint_ids != model_joint_ids:
            missing = sorted(model_joint_ids - config_joint_ids)
            extra = sorted(config_joint_ids - model_joint_ids)
            raise ValueError(
                f"configuration mismatch: missing={missing}, extra={extra}"
            )

        for joint_id, angle in configuration.positions.items():
            if not math.isfinite(angle):
                raise ValueError(
                    f"joint angle for {joint_id!r} must be finite"
                )

        joint_by_id = {j.joint_id: j for j in model.joints}
        for joint_id, angle in configuration.positions.items():
            joint = joint_by_id[joint_id]
            if joint.min_angle_deg is not None and angle < joint.min_angle_deg:
                raise ValueError(
                    f"joint {joint_id!r}: angle {angle} "
                    f"below min {joint.min_angle_deg}"
                )
            if joint.max_angle_deg is not None and angle > joint.max_angle_deg:
                raise ValueError(
                    f"joint {joint_id!r}: angle {angle} "
                    f"above max {joint.max_angle_deg}"
                )

        topology = _build_kinematic_topology(assembly, model)

        home_world: dict[str, CadRigidTransform] = {
            inst.instance_id: inst.placement for inst in assembly.instances
        }

        t_parent_child_home: dict[str, CadRigidTransform] = {}
        for joint in model.joints:
            t_parent = home_world[joint.parent_instance_id]
            t_child = home_world[joint.child_instance_id]
            t_parent_child_home[joint.joint_id] = transform_compose(
                transform_inverse(t_parent),
                t_child,
            )

        world: dict[str, CadRigidTransform] = {}
        for root_id in topology.roots:
            world[root_id] = home_world[root_id]

        joint_states: list[EvaluatedJointState] = []
        instance_transforms: list[InstanceWorldTransform] = []

        for joint in topology.evaluation_order:
            t_parent = world[joint.parent_instance_id]
            angle = configuration.positions[joint.joint_id]

            t_joint = axis_rotation_transform(
                joint.axis_origin,
                joint.axis_direction,
                angle,
            )

            t_child = transform_compose(
                t_parent,
                transform_compose(
                    t_joint,
                    t_parent_child_home[joint.joint_id],
                ),
            )
            world[joint.child_instance_id] = t_child

            within_limits = True
            if joint.min_angle_deg is not None and angle < joint.min_angle_deg:
                within_limits = False
            if joint.max_angle_deg is not None and angle > joint.max_angle_deg:
                within_limits = False

            joint_states.append(EvaluatedJointState(
                joint_id=joint.joint_id,
                joint_position_deg=angle,
                within_limits=within_limits,
            ))

        for inst in assembly.instances:
            is_articulated = inst.instance_id in topology.articulated_children
            instance_transforms.append(InstanceWorldTransform(
                instance_id=inst.instance_id,
                is_articulated=is_articulated,
                transform=world[inst.instance_id],
            ))

        new_instances = tuple(
            CadComponentInstance(
                instance_id=inst.instance_id,
                part_id=inst.part_id,
                placement=world[inst.instance_id],
            )
            for inst in assembly.instances
        )

        transformed_assembly = assembly.model_copy(
            update={"instances": new_instances}
        )

        src_hash = assembly_hash(assembly)
        mdl_hash = kinematic_model_hash(model)
        cfg_hash = joint_configuration_hash(configuration)
        tfm_hash = assembly_hash(transformed_assembly)

        result = KinematicForwardKinematicsResult(
            evaluator_version=MULTI_JOINT_FORWARD_KINEMATICS_VERSION,
            source_assembly_hash=src_hash,
            model_hash=mdl_hash,
            configuration_hash=cfg_hash,
            transformed_assembly_hash=tfm_hash,
            model_id=model.model_id,
            ordered_joint_states=tuple(joint_states),
            instance_world_transforms=tuple(instance_transforms),
            transformed_assembly=transformed_assembly,
        )

        return result.model_copy(
            update={"result_hash": kinematic_forward_kinematics_result_hash(result)}
        )
