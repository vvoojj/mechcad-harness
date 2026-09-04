from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_serializer, model_validator

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
from mechcad_harness.models.quaternion import normalize_quaternion
from mechcad_harness.multi_joint_pair_scope import (
    ExactConstituentPair,
    canonical_exact_pair_scope,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MULTI_JOINT_FORWARD_KINEMATICS_VERSION = "multi-joint-forward-kinematics@1.0"
MULTI_JOINT_FORWARD_KINEMATICS_V2_VERSION = "multi-joint-forward-kinematics@2.0"
RIGID_TRANSFORM_AGREEMENT_VERSION = "rigid-transform-agreement@1.0"
RIGID_TRANSFORM_TRANSLATION_ABS_TOL_MM = 1e-9
RIGID_TRANSFORM_ORIENTATION_ABS_TOL_RAD = 1e-7


@dataclass(frozen=True)
class RigidTransformAgreementPolicy:
    version: str
    translation_metric: str
    translation_abs_tol_mm: float
    orientation_metric: str
    orientation_abs_tol_rad: float


RIGID_TRANSFORM_AGREEMENT_POLICY: RigidTransformAgreementPolicy = (
    RigidTransformAgreementPolicy(
        version=RIGID_TRANSFORM_AGREEMENT_VERSION,
        translation_metric="componentwise-max-absolute-mm",
        translation_abs_tol_mm=RIGID_TRANSFORM_TRANSLATION_ABS_TOL_MM,
        orientation_metric="sign-invariant-unit-quaternion-angle-rad",
        orientation_abs_tol_rad=RIGID_TRANSFORM_ORIENTATION_ABS_TOL_RAD,
    )
)


# ---------------------------------------------------------------------------
# Transform helpers
# ---------------------------------------------------------------------------


def rigid_transform_agrees(
    first: CadRigidTransform,
    second: CadRigidTransform,
    policy_version: str = RIGID_TRANSFORM_AGREEMENT_VERSION,
) -> bool:
    """Compare two rigid poses using the one frozen v2 agreement policy."""
    if policy_version != RIGID_TRANSFORM_AGREEMENT_VERSION:
        raise ValueError(
            f"unsupported rigid transform agreement version: {policy_version!r}"
        )

    raw_values = (
        first.x_mm,
        first.y_mm,
        first.z_mm,
        *first.rotation_quaternion,
        second.x_mm,
        second.y_mm,
        second.z_mm,
        *second.rotation_quaternion,
    )
    if any(not math.isfinite(value) for value in raw_values):
        return False

    first_q = normalize_quaternion(first.rotation_quaternion)
    second_q = normalize_quaternion(second.rotation_quaternion)
    translation_error_mm = max(
        abs(first.x_mm - second.x_mm),
        abs(first.y_mm - second.y_mm),
        abs(first.z_mm - second.z_mm),
    )
    dot = abs(
        first_q[0] * second_q[0]
        + first_q[1] * second_q[1]
        + first_q[2] * second_q[2]
        + first_q[3] * second_q[3]
    )
    clamped_dot = min(1.0, max(0.0, dot))
    orientation_error_rad = 2.0 * math.acos(clamped_dot)
    return (
        translation_error_mm <= RIGID_TRANSFORM_TRANSLATION_ABS_TOL_MM
        and orientation_error_rad <= RIGID_TRANSFORM_ORIENTATION_ABS_TOL_RAD
    )


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
# Rigid-body member records
# ---------------------------------------------------------------------------


def _require_nonblank_kinematic_id(value: str, label: str) -> str:
    if not value.strip():
        raise ValueError(f"{label} must not be blank")
    return value


class _ImmutableCadRigidTransform(CadRigidTransform):
    model_config = ConfigDict(frozen=True, extra="forbid")

    def __eq__(self, other) -> bool:
        if isinstance(other, CadRigidTransform):
            return self.model_dump() == other.model_dump()
        return NotImplemented


class KinematicRigidBodyMember(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    member_instance_id: str
    reference_to_member_home: CadRigidTransform

    @field_validator("member_instance_id")
    @classmethod
    def _validate_member_instance_id(cls, value: str) -> str:
        return _require_nonblank_kinematic_id(value, "member_instance_id")

    @model_validator(mode="after")
    def _freeze_reference_offset(self) -> "KinematicRigidBodyMember":
        object.__setattr__(
            self,
            "reference_to_member_home",
            _ImmutableCadRigidTransform.model_validate(
                self.reference_to_member_home
            ),
        )
        return self


def _kinematic_rigid_body_semantic_hash(body: "KinematicRigidBody") -> str:
    payload = {
        "schema_version": body.schema_version,
        "body_id": body.body_id,
        "reference_member_instance_id": body.reference_member_instance_id,
        "members": [
            {
                "member_instance_id": member.member_instance_id,
                "reference_to_member_home": member.reference_to_member_home.model_dump(
                    mode="json"
                ),
            }
            for member in sorted(
                body.members, key=lambda member: member.member_instance_id
            )
        ],
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


class KinematicRigidBody(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kinematic-rigid-body@1"] = "kinematic-rigid-body@1"
    body_id: str
    reference_member_instance_id: str
    members: tuple[KinematicRigidBodyMember, ...]
    body_hash: str = "pending"

    @field_validator("body_id")
    @classmethod
    def _validate_body_id(cls, value: str) -> str:
        return _require_nonblank_kinematic_id(value, "body_id")

    @field_validator("reference_member_instance_id")
    @classmethod
    def _validate_reference_member_instance_id(cls, value: str) -> str:
        return _require_nonblank_kinematic_id(
            value, "reference_member_instance_id"
        )

    @model_validator(mode="after")
    def _validate_members_and_hash(self) -> "KinematicRigidBody":
        if not self.members:
            raise ValueError("rigid body must contain at least one member")

        member_ids = [member.member_instance_id for member in self.members]
        if len(set(member_ids)) != len(member_ids):
            raise ValueError("duplicate member instance IDs in rigid body")

        reference_members = [
            member
            for member in self.members
            if member.member_instance_id == self.reference_member_instance_id
        ]
        if len(reference_members) != 1:
            raise ValueError(
                "reference member must occur exactly once in rigid body members"
            )
        if reference_members[0].reference_to_member_home != CadRigidTransform():
            raise ValueError("reference member offset must be literal identity")

        canonical_members = tuple(
            sorted(self.members, key=lambda member: member.member_instance_id)
        )
        object.__setattr__(self, "members", canonical_members)

        expected = _kinematic_rigid_body_semantic_hash(self)
        if self.body_hash == "pending":
            object.__setattr__(self, "body_hash", expected)
        elif self.body_hash != expected:
            raise ValueError("rigid body hash mismatch")
        return self


def kinematic_rigid_body_hash(body: KinematicRigidBody) -> str:
    if type(body) is not KinematicRigidBody:
        raise TypeError("rigid body must be a supported typed model")
    payload = body.model_dump(mode="json")
    if payload.get("body_hash") == "pending":
        raise ValueError("body hash must be finalized")
    validated = KinematicRigidBody.model_validate(payload)
    return _kinematic_rigid_body_semantic_hash(validated)


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

    schema_version: Literal["revolute-joint-model@1"] = "revolute-joint-model@1"
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

    @model_serializer(mode="wrap")
    def _serialize_legacy(self, handler):
        payload = handler(self)
        payload.pop("schema_version", None)
        return payload

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


class RevoluteJointModelV2(Model):
    """Versioned revolute joint using rigid-body endpoints."""

    schema_version: Literal["revolute-joint-model@2"] = "revolute-joint-model@2"
    joint_id: str = Field(min_length=1)
    joint_kind: KinematicJointKind
    parent_body_id: str = Field(min_length=1)
    child_body_id: str = Field(min_length=1)
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
                raise ValueError("joint min_angle_deg must be <= max_angle_deg")
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

    schema_version: Literal["kinematic-model@1"] = "kinematic-model@1"
    model_id: str = Field(min_length=1)
    joints: tuple[RevoluteJointModel, ...] = Field(default_factory=tuple)
    evaluator_version: Literal["multi-joint-forward-kinematics@1.0"] = (
        MULTI_JOINT_FORWARD_KINEMATICS_VERSION
    )

    @model_validator(mode="after")
    def _validate_unique_joint_ids(self):
        ids = [j.joint_id for j in self.joints]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate joint IDs in kinematic model")
        return self


    @model_serializer(mode="wrap")
    def _serialize_legacy(self, handler):
        payload = handler(self)
        payload.pop("schema_version", None)
        return payload


class KinematicModelV2(Model):
    schema_version: Literal["kinematic-model@2"] = "kinematic-model@2"
    model_id: str = Field(min_length=1)
    bodies: tuple[KinematicRigidBody, ...]
    joints: tuple[RevoluteJointModelV2, ...]
    evaluator_version: Literal["multi-joint-forward-kinematics@2.0"] = (
        "multi-joint-forward-kinematics@2.0"
    )
    transform_agreement_version: Literal["rigid-transform-agreement@1.0"] = (
        RIGID_TRANSFORM_AGREEMENT_VERSION
    )

    @model_validator(mode="after")
    def _canonicalize_v2_records(self):
        body_ids = [body.body_id for body in self.bodies]
        if len(set(body_ids)) != len(body_ids):
            raise ValueError("duplicate body IDs in kinematic model")
        joint_ids = [joint.joint_id for joint in self.joints]
        if len(set(joint_ids)) != len(joint_ids):
            raise ValueError("duplicate joint IDs in kinematic model")
        object.__setattr__(
            self,
            "bodies",
            tuple(sorted(self.bodies, key=lambda body: body.body_id)),
        )
        object.__setattr__(
            self,
            "joints",
            tuple(sorted(self.joints, key=lambda joint: joint.joint_id)),
        )
        return self


def revalidate_v2_kinematic_model(model: KinematicModelV2) -> KinematicModelV2:
    """Reconstruct every v2 record before trusting it at an execution boundary."""
    if type(model) is not KinematicModelV2:
        raise TypeError("kinematic model must be a v2 KinematicModelV2")
    payload = model.model_dump(mode="json")
    raw_bodies = payload.get("bodies", ())
    if isinstance(raw_bodies, (tuple, list)):
        body_ids = [
            body.get("body_id")
            for body in raw_bodies
            if isinstance(body, dict) and isinstance(body.get("body_id"), str)
        ]
        if any(
            isinstance(body, dict) and body.get("body_hash") == "pending"
            for body in raw_bodies
        ):
            raise ValueError("v2 rigid body hashes must be finalized")
        duplicate_body_ids = sorted(
            body_id for body_id in set(body_ids) if body_ids.count(body_id) > 1
        )
        if duplicate_body_ids:
            raise ValueError(f"duplicate body IDs: {duplicate_body_ids}")
    try:
        validated = KinematicModelV2.model_validate(payload)
    except Exception as exc:
        raise ValueError(f"v2 kinematic model integrity validation failed: {exc}") from exc

    if validated.schema_version != "kinematic-model@2":
        raise ValueError("v2 kinematic model schema version is not trusted")
    if validated.evaluator_version != MULTI_JOINT_FORWARD_KINEMATICS_V2_VERSION:
        raise ValueError("v2 kinematic model evaluator version is not trusted")
    if validated.transform_agreement_version != RIGID_TRANSFORM_AGREEMENT_VERSION:
        raise ValueError("v2 transform agreement version is not trusted")
    for body in validated.bodies:
        expected_body_hash = _kinematic_rigid_body_semantic_hash(body)
        if body.body_hash != expected_body_hash:
            raise ValueError(
                f"rigid body {body.body_id!r} hash does not match canonical semantics"
            )
    return validated


def body_by_member_id(model: KinematicModelV2) -> dict[str, KinematicRigidBody]:
    """Return the unique v2 body owning each declared assembly member."""
    model = revalidate_v2_kinematic_model(model)
    body_ids = [body.body_id for body in model.bodies]
    blank_body_ids = sorted(body_id for body_id in body_ids if not body_id.strip())
    if blank_body_ids:
        raise ValueError(f"body IDs must not be blank: {blank_body_ids}")

    duplicate_body_ids = sorted(
        body_id for body_id in set(body_ids) if body_ids.count(body_id) > 1
    )
    if duplicate_body_ids:
        raise ValueError(f"duplicate body IDs: {duplicate_body_ids}")

    member_to_body: dict[str, KinematicRigidBody] = {}
    for body in model.bodies:
        for member in body.members:
            previous = member_to_body.get(member.member_instance_id)
            if previous is not None:
                raise ValueError(
                    f"member {member.member_instance_id!r} belongs to multiple bodies: "
                    f"{sorted((previous.body_id, body.body_id))}"
                )
            member_to_body[member.member_instance_id] = body
    return member_to_body


def validate_v2_body_assembly_agreement(
    assembly: CadAssemblyProgram,
    model: KinematicModelV2,
) -> dict[str, KinematicRigidBody]:
    """Validate complete v2 membership and declared home-frame offsets."""
    model = revalidate_v2_kinematic_model(model)
    instance_by_id = {instance.instance_id: instance for instance in assembly.instances}
    member_to_body = body_by_member_id(model)

    declared_member_ids = set(member_to_body)
    source_member_ids = set(instance_by_id)
    unknown_member_ids = sorted(declared_member_ids - source_member_ids)
    missing_member_ids = sorted(source_member_ids - declared_member_ids)
    if unknown_member_ids or missing_member_ids:
        diagnostics = []
        if unknown_member_ids:
            diagnostics.append(f"unknown={unknown_member_ids}")
        if missing_member_ids:
            diagnostics.append(f"missing={missing_member_ids}")
        raise ValueError(
            "v2 body assembly membership mismatch: " + ", ".join(diagnostics)
        )

    for member_id, body in member_to_body.items():
        reference_instance = instance_by_id.get(body.reference_member_instance_id)
        if reference_instance is None:
            raise ValueError(
                f"body {body.body_id!r} reference member "
                f"{body.reference_member_instance_id!r} is not in assembly"
            )
        member = next(
            member
            for member in body.members
            if member.member_instance_id == member_id
        )
        recomposed = transform_compose(
            reference_instance.placement,
            member.reference_to_member_home,
        )
        if not rigid_transform_agrees(
            instance_by_id[member_id].placement,
            recomposed,
            RIGID_TRANSFORM_AGREEMENT_VERSION,
        ):
            raise ValueError(
                f"body {body.body_id!r} member {member_id!r} home placement "
                "disagrees with source assembly"
            )

    return member_to_body


def validate_v2_exact_pair_scope(
    assembly: CadAssemblyProgram,
    model: KinematicModelV2,
    exact_pair_scope: tuple[ExactConstituentPair, ...],
) -> tuple[ExactConstituentPair, ...]:
    """Validate canonical concrete pairs against v2 assembly membership."""
    model = revalidate_v2_kinematic_model(model)
    member_to_body = validate_v2_body_assembly_agreement(assembly, model)
    canonical = canonical_exact_pair_scope(exact_pair_scope)
    if exact_pair_scope != canonical:
        raise ValueError("exact pair scope must be canonical")

    source_instance_ids = {
        instance.instance_id for instance in assembly.instances
    }
    for pair in canonical:
        pair_instance_ids = {
            pair.first_instance_id,
            pair.second_instance_id,
        }
        missing_source_ids = sorted(pair_instance_ids - source_instance_ids)
        if missing_source_ids:
            raise ValueError(
                "exact pair instance IDs not in source assembly: "
                f"{missing_source_ids}"
            )

        missing_body_ids = sorted(set(pair_instance_ids) - set(member_to_body))
        if missing_body_ids:
            raise ValueError(
                "exact pair instance IDs missing from v2 body map: "
                f"{missing_body_ids}"
            )

        first_body = member_to_body[pair.first_instance_id]
        second_body = member_to_body[pair.second_instance_id]
        if first_body.body_id == second_body.body_id:
            raise ValueError(
                "exact pair members belong to the same rigid body: "
                f"{first_body.body_id!r}"
            )

    return canonical


KinematicModelInput = KinematicModel | KinematicModelV2
RevoluteJointModelInput = RevoluteJointModel | RevoluteJointModelV2


def parse_revolute_joint_model(
    value: Mapping[str, object] | RevoluteJointModelInput,
) -> RevoluteJointModelInput:
    if isinstance(value, RevoluteJointModel):
        if value.schema_version != "revolute-joint-model@1":
            raise ValueError("invalid revolute joint model v1 schema version")
        return value
    if isinstance(value, RevoluteJointModelV2):
        try:
            return RevoluteJointModelV2.model_validate(value.model_dump(mode="json"))
        except Exception as exc:
            raise ValueError(
                f"v2 revolute joint model integrity validation failed: {exc}"
            ) from exc
    if isinstance(value, Mapping):
        schema_version = value.get("schema_version")
        if schema_version is None or schema_version == "revolute-joint-model@1":
            return RevoluteJointModel.model_validate(value)
        if schema_version == "revolute-joint-model@2":
            return RevoluteJointModelV2.model_validate(value)
        raise ValueError(f"unsupported revolute joint model schema: {schema_version!r}")
    raise TypeError("revolute joint model must be a mapping or typed model")


def parse_kinematic_model(
    value: Mapping[str, object] | KinematicModelInput,
) -> KinematicModelInput:
    if isinstance(value, KinematicModel):
        if value.schema_version != "kinematic-model@1":
            raise ValueError("invalid kinematic model v1 schema version")
        return value
    if isinstance(value, KinematicModelV2):
        return revalidate_v2_kinematic_model(value)
    if isinstance(value, Mapping):
        schema_version = value.get("schema_version")
        if schema_version is None or schema_version == "kinematic-model@1":
            return KinematicModel.model_validate(value)
        if schema_version == "kinematic-model@2":
            return KinematicModelV2.model_validate(value)
        raise ValueError(f"unsupported kinematic model schema: {schema_version!r}")
    raise TypeError("kinematic model must be a mapping or typed model")


def kinematic_model_wire_payload(model: KinematicModelInput) -> dict[str, object]:
    if isinstance(model, KinematicModelV2):
        model = revalidate_v2_kinematic_model(model)
    return model.model_dump(mode="json")


def v2_revolute_joint_wire_payload(
    joint: RevoluteJointModelV2,
) -> dict[str, object]:
    joint = RevoluteJointModelV2.model_validate(joint.model_dump(mode="json"))
    return {
        "schema_version": joint.schema_version,
        "joint_id": joint.joint_id,
        "joint_kind": joint.joint_kind.value,
        "parent_body_id": joint.parent_body_id,
        "child_body_id": joint.child_body_id,
        "axis_origin_x_mm": joint.axis_origin_x_mm,
        "axis_origin_y_mm": joint.axis_origin_y_mm,
        "axis_origin_z_mm": joint.axis_origin_z_mm,
        "axis_direction_x": joint.axis_direction_x,
        "axis_direction_y": joint.axis_direction_y,
        "axis_direction_z": joint.axis_direction_z,
        "min_angle_deg": joint.min_angle_deg,
        "max_angle_deg": joint.max_angle_deg,
    }


def kinematic_model_hash(model: KinematicModelInput) -> str:
    """Deterministic SHA-256 over model semantic fields."""
    if isinstance(model, KinematicModel):
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
    elif isinstance(model, KinematicModelV2):
        model = revalidate_v2_kinematic_model(model)
        payload = {
            "schema_version": model.schema_version,
            "model_id": model.model_id,
            "evaluator_version": model.evaluator_version,
            "transform_agreement_version": model.transform_agreement_version,
            "bodies": [
                _kinematic_rigid_body_semantic_hash(body) for body in model.bodies
            ],
            "joints": [
                v2_revolute_joint_wire_payload(joint) for joint in model.joints
            ],
        }
    else:
        raise TypeError("kinematic model must be a supported typed model")
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


class _KinematicBodyTopology:
    """Validated topology of a v2 kinematic model against body IDs."""

    __slots__ = (
        "joint_by_child",
        "child_joints_of",
        "roots",
        "articulated_children",
        "evaluation_order",
    )

    def __init__(
        self,
        joint_by_child: dict[str, RevoluteJointModelV2],
        child_joints_of: dict[str, list[RevoluteJointModelV2]],
        roots: tuple[str, ...],
        articulated_children: frozenset[str],
        evaluation_order: tuple[RevoluteJointModelV2, ...],
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


def _build_v2_kinematic_topology(
    assembly: CadAssemblyProgram,
    model: KinematicModelV2,
) -> _KinematicBodyTopology:
    """Validate and build deterministic topology from v2 body IDs."""
    model = revalidate_v2_kinematic_model(model)
    body_ids = {body.body_id for body in model.bodies}
    if len(body_ids) != len(model.bodies):
        raise ValueError("duplicate body IDs")

    joint_ids = [joint.joint_id for joint in model.joints]
    if len(set(joint_ids)) != len(joint_ids):
        raise ValueError("duplicate joint IDs")

    for joint in model.joints:
        if joint.parent_body_id not in body_ids:
            raise ValueError(
                f"joint {joint.joint_id!r}: parent body "
                f"{joint.parent_body_id!r} not in model"
            )
        if joint.child_body_id not in body_ids:
            raise ValueError(
                f"joint {joint.joint_id!r}: child body "
                f"{joint.child_body_id!r} not in model"
            )
        if joint.parent_body_id == joint.child_body_id:
            raise ValueError(
                f"joint {joint.joint_id!r}: parent == child "
                f"({joint.parent_body_id!r})"
            )

    joint_by_child: dict[str, RevoluteJointModelV2] = {}
    for joint in model.joints:
        if joint.child_body_id in joint_by_child:
            existing = joint_by_child[joint.child_body_id]
            raise ValueError(
                f"child body {joint.child_body_id!r} has two parent joints: "
                f"{existing.joint_id!r} and {joint.joint_id!r}"
            )
        joint_by_child[joint.child_body_id] = joint

    _detect_v2_cycles(model)

    child_joints_of: dict[str, list[RevoluteJointModelV2]] = {}
    for joint in model.joints:
        child_joints_of.setdefault(joint.parent_body_id, []).append(joint)

    roots = tuple(
        sorted(body_id for body_id in body_ids if body_id not in joint_by_child)
    )
    articulated_children = frozenset(joint_by_child)
    evaluation_order: list[RevoluteJointModelV2] = []
    visited_nodes: set[str] = set()
    queue: deque[str] = deque(roots)

    while queue:
        node = queue.popleft()
        if node in visited_nodes:
            continue
        visited_nodes.add(node)
        for joint in sorted(
            child_joints_of.get(node, []), key=lambda joint: joint.joint_id
        ):
            evaluation_order.append(joint)
            queue.append(joint.child_body_id)

    unreachable = articulated_children - (visited_nodes & articulated_children)
    if unreachable:
        raise ValueError(
            "articulated bodies unreachable from roots: "
            f"{sorted(unreachable)}"
        )

    return _KinematicBodyTopology(
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


def _detect_v2_cycles(model: KinematicModelV2) -> None:
    """Detect cycles in the v2 body parent-child graph."""
    if not model.joints:
        return

    child_to_parent_joint: dict[str, RevoluteJointModelV2] = {}
    for joint in model.joints:
        child_to_parent_joint[joint.child_body_id] = joint

    for start_joint in model.joints:
        visited: set[str] = set()
        current = start_joint.child_body_id
        while current in child_to_parent_joint:
            if current in visited:
                raise ValueError("cycle detected in v2 kinematic topology")
            visited.add(current)
            current = child_to_parent_joint[current].parent_body_id


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
        model: KinematicModelInput,
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
        if not isinstance(model, (KinematicModel, KinematicModelV2)):
            raise TypeError("kinematic model must be a supported typed model")
        if isinstance(model, KinematicModelV2):
            model = revalidate_v2_kinematic_model(model)

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

        if isinstance(model, KinematicModelV2):
            return _evaluate_v2(assembly, model, configuration)
        return _evaluate_v1(assembly, model, configuration)


def _evaluate_v1(
    assembly: CadAssemblyProgram,
    model: KinematicModel,
    configuration: JointConfiguration,
) -> KinematicForwardKinematicsResult:
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


def _evaluate_v2(
    assembly: CadAssemblyProgram,
    model: KinematicModelV2,
    configuration: JointConfiguration,
) -> KinematicForwardKinematicsResult:
    model = revalidate_v2_kinematic_model(model)
    member_to_body = validate_v2_body_assembly_agreement(assembly, model)
    topology = _build_v2_kinematic_topology(assembly, model)
    instance_by_id = {
        instance.instance_id: instance for instance in assembly.instances
    }
    member_by_id = {
        member.member_instance_id: member
        for body in model.bodies
        for member in body.members
    }

    body_home = {
        body.body_id: instance_by_id[body.reference_member_instance_id].placement
        for body in model.bodies
    }
    world_body: dict[str, CadRigidTransform] = {
        body_id: body_home[body_id] for body_id in topology.roots
    }

    t_parent_child_home: dict[str, CadRigidTransform] = {}
    for joint in model.joints:
        t_parent_child_home[joint.joint_id] = transform_compose(
            transform_inverse(body_home[joint.parent_body_id]),
            body_home[joint.child_body_id],
        )

    joint_states: list[EvaluatedJointState] = []
    for joint in topology.evaluation_order:
        t_parent = world_body[joint.parent_body_id]
        angle = configuration.positions[joint.joint_id]
        t_joint = axis_rotation_transform(
            joint.axis_origin,
            joint.axis_direction,
            angle,
        )
        world_body[joint.child_body_id] = transform_compose(
            t_parent,
            transform_compose(
                t_joint,
                t_parent_child_home[joint.joint_id],
            ),
        )

        within_limits = True
        if joint.min_angle_deg is not None and angle < joint.min_angle_deg:
            within_limits = False
        if joint.max_angle_deg is not None and angle > joint.max_angle_deg:
            within_limits = False
        joint_states.append(
            EvaluatedJointState(
                joint_id=joint.joint_id,
                joint_position_deg=angle,
                within_limits=within_limits,
            )
        )

    projected: dict[str, CadRigidTransform] = {}
    instance_transforms: list[InstanceWorldTransform] = []
    for instance in assembly.instances:
        body = member_to_body[instance.instance_id]
        projected[instance.instance_id] = transform_compose(
            world_body[body.body_id],
            member_by_id[instance.instance_id].reference_to_member_home,
        )
        instance_transforms.append(
            InstanceWorldTransform(
                instance_id=instance.instance_id,
                is_articulated=body.body_id in topology.articulated_children,
                transform=projected[instance.instance_id],
            )
        )

    if all(angle == 0.0 for angle in configuration.positions.values()):
        for instance in assembly.instances:
            if not rigid_transform_agrees(
                projected[instance.instance_id],
                instance.placement,
                model.transform_agreement_version,
            ):
                raise ValueError(
                    f"v2 q=0 projected placement disagrees for "
                    f"instance {instance.instance_id!r}"
                )

    new_instances = tuple(
        CadComponentInstance(
            instance_id=instance.instance_id,
            part_id=instance.part_id,
            placement=projected[instance.instance_id],
        )
        for instance in assembly.instances
    )
    transformed_assembly = assembly.model_copy(update={"instances": new_instances})

    result = KinematicForwardKinematicsResult(
        evaluator_version=model.evaluator_version,
        source_assembly_hash=assembly_hash(assembly),
        model_hash=kinematic_model_hash(model),
        configuration_hash=joint_configuration_hash(configuration),
        transformed_assembly_hash=assembly_hash(transformed_assembly),
        model_id=model.model_id,
        ordered_joint_states=tuple(joint_states),
        instance_world_transforms=tuple(instance_transforms),
        transformed_assembly=transformed_assembly,
    )
    return result.model_copy(
        update={"result_hash": kinematic_forward_kinematics_result_hash(result)}
    )


__all__ = [
    "MULTI_JOINT_FORWARD_KINEMATICS_VERSION",
    "MULTI_JOINT_FORWARD_KINEMATICS_V2_VERSION",
    "RIGID_TRANSFORM_AGREEMENT_VERSION",
    "RIGID_TRANSFORM_TRANSLATION_ABS_TOL_MM",
    "RIGID_TRANSFORM_ORIENTATION_ABS_TOL_RAD",
    "RIGID_TRANSFORM_AGREEMENT_POLICY",
    "RigidTransformAgreementPolicy",
    "KinematicRigidBodyMember",
    "KinematicRigidBody",
    "KinematicJointKind",
    "RevoluteJointModel",
    "RevoluteJointModelV2",
    "KinematicModel",
    "KinematicModelV2",
    "JointConfiguration",
    "EvaluatedJointState",
    "InstanceWorldTransform",
    "KinematicForwardKinematicsResult",
    "MultiJointKinematicsService",
    "body_by_member_id",
    "validate_v2_body_assembly_agreement",
    "validate_v2_exact_pair_scope",
    "parse_revolute_joint_model",
    "parse_kinematic_model",
    "kinematic_model_wire_payload",
    "v2_revolute_joint_wire_payload",
    "kinematic_rigid_body_hash",
    "revalidate_v2_kinematic_model",
    "kinematic_model_hash",
    "joint_configuration_hash",
    "kinematic_forward_kinematics_result_hash",
    "rigid_transform_agrees",
    "transform_apply",
    "transform_compose",
    "transform_inverse",
    "axis_rotation_transform",
]
