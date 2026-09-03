from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping
from typing import Annotated, Literal, TypeAlias

from pydantic import ConfigDict, Field, field_validator, model_validator

from mechcad_harness.cad_assembly import CadRigidTransform

from .common import Model
from .generated_part import (
    GeneratedAttachmentFaceInterface,
    GeneratedAuthorityInput,
    GeneratedAuthorityRole,
    GeneratedAuthoritySourceKind,
    GeneratedAuthorityView,
    GeneratedReferenceFrame,
    GeneratedRotationalInterface,
    DesignSelectionLocator,
    resolve_generated_inputs,
    selection_hash,
    value_hash,
)
from .quaternion import (
    normalize_direction,
    normalize_quaternion,
    quaternion_compose,
    rotate_vector,
)


PLACEMENT_RULES = (
    "coaxial-generated-placement@1",
    "frame-generated-placement@1",
)

_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")


def _nonblank(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must not be empty or whitespace")
    return value


def _optional_nonblank(value: str | None) -> str | None:
    if value is None:
        return None
    return _nonblank(value)


def _safe_id(value: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID_RE.fullmatch(value):
        raise ValueError("must be a SAFE_ID")
    return value


def _require_hash(value: str) -> str:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise ValueError("must be a sha256 hash")
    return value


def _optional_hash(value: str | None) -> str | None:
    if value is None:
        return None
    return _require_hash(value)


def _hash_or_pending(value: str) -> str:
    if value == "pending":
        return value
    return _require_hash(value)


def _finite_float(value: object) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise ValueError("must be a finite float")
    return value


def _self_hash(model: Model, hash_field: str) -> str:
    from mechcad_harness.state.hashing import canonical_json

    payload = model.model_dump(mode="json")
    payload.pop(hash_field, None)
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


class GeneratedInterfaceRef(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    interface_id: str = Field(min_length=1)
    interface_hash: str

    _validate_id = field_validator("interface_id")(_nonblank)
    _validate_hash = field_validator("interface_hash")(_require_hash)


class GeneratedFrameRef(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    frame_id: str = Field(min_length=1)
    frame_hash: str

    _validate_id = field_validator("frame_id")(_nonblank)
    _validate_hash = field_validator("frame_hash")(_require_hash)


class DesignVariablePlacementRef(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["design_variable_placement"]


class DerivationPlacementRef(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["derivation"]
    derivation_id: str

    _validate_id = field_validator("derivation_id")(_safe_id)


SourcePlacementRef: TypeAlias = Annotated[
    DesignVariablePlacementRef | DerivationPlacementRef,
    Field(discriminator="kind"),
]


class GeneratedFrameAxisRef(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    frame_role: Literal["source", "target"]
    axis: Literal["+x", "+y", "+z", "-x", "-y", "-z"]


class GeneratedPlacementRotationInput(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rotation_id: str
    axis_ref: GeneratedFrameAxisRef
    angle_degrees: float
    provenance: DesignSelectionLocator
    value_hash: str
    input_hash: str = "pending"

    _validate_id = field_validator("rotation_id")(_safe_id)
    _validate_angle = field_validator("angle_degrees", mode="before")(_finite_float)
    _validate_hashes = field_validator("value_hash", "input_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_rotation(self) -> "GeneratedPlacementRotationInput":
        expected_value_hash = value_hash(self.angle_degrees)
        if self.value_hash != expected_value_hash:
            raise ValueError("generated placement rotation value hash mismatch")
        expected_selection_hash = selection_hash(
            self.provenance.name_form.value,
            self.provenance.selection_key,
            self.angle_degrees,
        )
        if self.provenance.selection_hash != expected_selection_hash:
            raise ValueError("generated placement rotation selection hash mismatch")
        expected = _self_hash(self, "input_hash")
        if self.input_hash == "pending":
            object.__setattr__(self, "input_hash", expected)
        elif self.input_hash != expected:
            raise ValueError("generated placement rotation input hash mismatch")
        return self


class GeneratedPlacementDerivation(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    derivation_id: str
    rule_id: Literal[
        "coaxial-generated-placement@1", "frame-generated-placement@1"
    ]
    source_physical_instance_id: str
    source_interface_ref: GeneratedInterfaceRef
    source_frame_ref: GeneratedFrameRef | None = None
    source_placement_ref: SourcePlacementRef
    target_physical_instance_id: str
    target_generated_interface_ref: GeneratedInterfaceRef | None = None
    target_generated_frame_ref: GeneratedFrameRef | None = None
    inputs: tuple[GeneratedAuthorityInput, ...] = ()
    rotation: GeneratedPlacementRotationInput | None = None
    derivation_hash: str = "pending"

    _validate_derivation_id = field_validator("derivation_id")(_safe_id)
    _validate_instance_ids = field_validator(
        "source_physical_instance_id", "target_physical_instance_id"
    )(_nonblank)
    _validate_hash = field_validator("derivation_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_derivation(self) -> "GeneratedPlacementDerivation":
        if len({item.input_id for item in self.inputs}) != len(self.inputs):
            raise ValueError("placement input IDs must be unique")
        if any(
            item.role is not GeneratedAuthorityRole.AXIAL_OFFSET
            or item.source_kind is not GeneratedAuthoritySourceKind.DESIGN_SELECTION
            for item in self.inputs
        ):
            raise ValueError("placement inputs must be DESIGN_SELECTION axial-offset inputs")

        if self.rule_id == "coaxial-generated-placement@1":
            if self.target_generated_interface_ref is None:
                raise ValueError("coaxial placement requires a target interface")
            if not _is_axisymmetric_target_interface(self.target_generated_interface_ref):
                raise ValueError("coaxial placement target is not axisymmetric")
            if (
                self.source_frame_ref is not None
                or self.target_generated_frame_ref is not None
                or self.rotation is not None
            ):
                raise ValueError("coaxial placement does not accept frame or rotation inputs")
        else:
            if self.source_frame_ref is None or self.target_generated_frame_ref is None:
                raise ValueError("frame placement requires source and target frames")
            if self.rotation is None:
                raise ValueError("frame placement requires exactly one rotation input")
            if self.target_generated_interface_ref is not None:
                raise ValueError("frame placement targets a generated frame, not an interface")
            frame = self.rotation.axis_ref.frame_role
            if frame == "source" and self.source_frame_ref is None:
                raise ValueError("rotation source axis frame is missing")
            if frame == "target" and self.target_generated_frame_ref is None:
                raise ValueError("rotation target axis frame is missing")

        expected = _self_hash(self, "derivation_hash")
        if self.derivation_hash == "pending":
            object.__setattr__(self, "derivation_hash", expected)
        elif self.derivation_hash != expected:
            raise ValueError("generated placement derivation hash mismatch")
        return self


class CanonicalGeneratedPlacementDerivation(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    derivation_id: str
    rule_id: Literal[
        "coaxial-generated-placement@1", "frame-generated-placement@1"
    ]
    source_canonical_instance_id: str
    source_interface_id: str
    source_interface_hash: str
    source_frame_id: str | None = None
    source_frame_hash: str | None = None
    source_placement_ref: SourcePlacementRef
    target_canonical_instance_id: str
    target_generated_interface_id: str | None = None
    target_generated_interface_hash: str | None = None
    target_generated_frame_id: str | None = None
    target_generated_frame_hash: str | None = None
    inputs: tuple[GeneratedAuthorityInput, ...]
    rotation: GeneratedPlacementRotationInput | None = None
    derivation_hash: str = "pending"

    _validate_derivation_id = field_validator("derivation_id")(_safe_id)
    _validate_ids = field_validator(
        "source_canonical_instance_id",
        "target_canonical_instance_id",
        "source_interface_id",
    )(_nonblank)
    _validate_optional_ids = field_validator(
        "source_frame_id", "target_generated_interface_id", "target_generated_frame_id"
    )(_optional_nonblank)
    _validate_hashes = field_validator("source_interface_hash")(_require_hash)
    _validate_optional_hashes = field_validator(
        "source_frame_hash", "target_generated_interface_hash", "target_generated_frame_hash"
    )(_optional_hash)
    _validate_hash = field_validator("derivation_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_derivation(self) -> "CanonicalGeneratedPlacementDerivation":
        if len({item.input_id for item in self.inputs}) != len(self.inputs):
            raise ValueError("placement input IDs must be unique")
        if any(
            item.role is not GeneratedAuthorityRole.AXIAL_OFFSET
            or item.source_kind is not GeneratedAuthoritySourceKind.DESIGN_SELECTION
            for item in self.inputs
        ):
            raise ValueError("placement inputs must be DESIGN_SELECTION axial-offset inputs")
        for identifier, digest, name in (
            (self.source_frame_id, self.source_frame_hash, "source frame"),
            (
                self.target_generated_interface_id,
                self.target_generated_interface_hash,
                "target generated interface",
            ),
            (
                self.target_generated_frame_id,
                self.target_generated_frame_hash,
                "target generated frame",
            ),
        ):
            if (identifier is None) != (digest is None):
                raise ValueError(f"{name} ID and hash must be jointly present")
        if self.rule_id == "coaxial-generated-placement@1":
            if not _is_axisymmetric_target_interface_id(self.target_generated_interface_id):
                raise ValueError("coaxial placement requires a target interface")
            if any(
                value is not None
                for value in (
                    self.source_frame_id,
                    self.source_frame_hash,
                    self.target_generated_frame_id,
                    self.target_generated_frame_hash,
                    self.rotation,
                )
            ):
                raise ValueError("coaxial placement does not accept frame or rotation inputs")
        else:
            if self.source_frame_id is None or self.source_frame_hash is None:
                raise ValueError("frame placement requires a source frame")
            if self.target_generated_frame_id is None or self.target_generated_frame_hash is None:
                raise ValueError("frame placement requires a target frame")
            if self.rotation is None:
                raise ValueError("frame placement requires exactly one rotation input")
            if self.target_generated_interface_id is not None:
                raise ValueError("frame placement targets a generated frame, not an interface")
        expected = _self_hash(self, "derivation_hash")
        if self.derivation_hash == "pending":
            object.__setattr__(self, "derivation_hash", expected)
        elif self.derivation_hash != expected:
            raise ValueError("canonical generated placement derivation hash mismatch")
        return self


def _is_axisymmetric_target_interface_id(interface_id: str | None) -> bool:
    if interface_id is None:
        return False
    return bool(
        re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*:shaft", interface_id)
        or re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_.-]*:bore:[A-Za-z][A-Za-z0-9_.-]*:(?:near|far)",
            interface_id,
        )
    )


def _is_axisymmetric_target_interface(interface: GeneratedInterfaceRef) -> bool:
    return _is_axisymmetric_target_interface_id(interface.interface_id)


def _validate_acyclic(derivations: tuple[object, ...]) -> None:
    ids = tuple(item.derivation_id for item in derivations)
    if len(set(ids)) != len(ids):
        raise ValueError("placement derivation IDs must be unique")
    by_id = {item.derivation_id: item for item in derivations}
    dependencies: dict[str, str] = {}
    for item in derivations:
        ref = item.source_placement_ref
        if getattr(ref, "kind", None) != "derivation":
            continue
        dependency = ref.derivation_id
        if dependency not in by_id:
            raise ValueError("placement derivation references an unknown derivation")
        dependency_target = getattr(by_id[dependency], "target_physical_instance_id", None)
        if dependency_target is None:
            dependency_target = getattr(by_id[dependency], "target_canonical_instance_id", None)
        current_source = getattr(item, "source_physical_instance_id", None)
        if current_source is None:
            current_source = getattr(item, "source_canonical_instance_id", None)
        if dependency_target != current_source:
            raise ValueError("placement derivation chain instance continuity mismatch")
        dependencies[item.derivation_id] = dependency

    remaining = set(ids)
    while remaining:
        ready = sorted(item_id for item_id in remaining if dependencies.get(item_id) not in remaining)
        if not ready:
            raise ValueError("placement derivation set must be acyclic")
        remaining.difference_update(ready)


def placement_derivations_hash(derivations) -> str:
    from mechcad_harness.state.hashing import canonical_json

    records = tuple(derivations)
    _validate_acyclic(records)
    payload = {
        "derivations": [
            record.model_dump(mode="json")
            for record in sorted(records, key=lambda item: item.derivation_id)
        ]
    }
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def _cross(first: tuple[float, float, float], second: tuple[float, float, float]):
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def _rotation_aligning(
    from_dir, to_dir
) -> tuple[float, float, float, float]:
    source = normalize_direction(from_dir)
    target = normalize_direction(to_dir)
    dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(source, target))))
    if dot >= 1.0 - 1e-12:
        return normalize_quaternion((1.0, 0.0, 0.0, 0.0))
    if dot <= -1.0 + 1e-12:
        axis = _cross(source, (1.0, 0.0, 0.0))
        if sum(value * value for value in axis) <= 1e-24:
            axis = _cross(source, (0.0, 1.0, 0.0))
        axis = normalize_direction(axis)
        return normalize_quaternion((0.0, axis[0], axis[1], axis[2]))
    axis = _cross(source, target)
    return normalize_quaternion((1.0 + dot, axis[0], axis[1], axis[2]))


def _reconstruct_rotation(axis: str, angle_degrees: float) -> tuple[float, float, float, float]:
    angle = _finite_float(angle_degrees)
    direction = {
        "+x": (1.0, 0.0, 0.0),
        "+y": (0.0, 1.0, 0.0),
        "+z": (0.0, 0.0, 1.0),
        "-x": (-1.0, 0.0, 0.0),
        "-y": (0.0, -1.0, 0.0),
        "-z": (0.0, 0.0, -1.0),
    }.get(axis)
    if direction is None:
        raise ValueError("unknown placement rotation axis")
    half_angle = math.radians(angle) / 2.0
    sine = math.sin(half_angle)
    return normalize_quaternion(
        (math.cos(half_angle), direction[0] * sine, direction[1] * sine, direction[2] * sine)
    )


def _resolve_frame_orientation(
    frame_ref: GeneratedFrameRef,
    view: GeneratedAuthorityView,
) -> tuple[float, float, float, float]:
    from .supplied_component_interface import SuppliedComponentReferenceFrame

    records = view.reference_frames
    candidates = tuple(records.values()) if isinstance(records, Mapping) else tuple(records)
    matches = []
    for candidate in candidates:
        if isinstance(candidate, GeneratedReferenceFrame):
            if candidate.frame_id == frame_ref.frame_id and candidate.frame_hash == frame_ref.frame_hash:
                matches.append(candidate.orientation)
        elif isinstance(candidate, SuppliedComponentReferenceFrame):
            if candidate.frame_id != frame_ref.frame_id or candidate.frame_hash != frame_ref.frame_hash:
                continue
            if candidate.orientation.accepted_evidence_id is None:
                continue
            evidence = next(
                (
                    record
                    for record in candidate.orientation.evidence
                    if record.evidence_id == candidate.orientation.accepted_evidence_id
                ),
                None,
            )
            if evidence is not None and evidence.availability.value == "available":
                matches.append(normalize_quaternion(evidence.value))
    if len(matches) != 1:
        raise ValueError("placement rotation axis frame cannot be resolved by exact ID and hash")
    return normalize_quaternion(matches[0])


def _target_instance_id(
    derivation: GeneratedPlacementDerivation | CanonicalGeneratedPlacementDerivation,
) -> str:
    target = getattr(derivation, "target_physical_instance_id", None)
    if target is None:
        target = derivation.target_canonical_instance_id
    return target


def _frame_ref_for_role(
    derivation: GeneratedPlacementDerivation | CanonicalGeneratedPlacementDerivation,
    frame_role: str,
) -> GeneratedFrameRef:
    if isinstance(derivation, GeneratedPlacementDerivation):
        frame_ref = (
            derivation.source_frame_ref
            if frame_role == "source"
            else derivation.target_generated_frame_ref
        )
        if frame_ref is None:
            raise ValueError("placement rotation axis frame is missing")
        return frame_ref

    if frame_role == "source":
        frame_id, frame_hash = derivation.source_frame_id, derivation.source_frame_hash
    else:
        frame_id, frame_hash = (
            derivation.target_generated_frame_id,
            derivation.target_generated_frame_hash,
        )
    if frame_id is None or frame_hash is None:
        raise ValueError("placement rotation axis frame is missing")
    return GeneratedFrameRef(frame_id=frame_id, frame_hash=frame_hash)


def _resolve_target_generated_interface(
    derivation: GeneratedPlacementDerivation | CanonicalGeneratedPlacementDerivation,
    view: GeneratedAuthorityView,
) -> GeneratedRotationalInterface:
    if isinstance(derivation, GeneratedPlacementDerivation):
        reference = derivation.target_generated_interface_ref
    else:
        if (
            derivation.target_generated_interface_id is None
            or derivation.target_generated_interface_hash is None
        ):
            raise ValueError("coaxial placement requires a target interface")
        reference = GeneratedInterfaceRef(
            interface_id=derivation.target_generated_interface_id,
            interface_hash=derivation.target_generated_interface_hash,
        )
    if reference is None:
        raise ValueError("coaxial placement requires a target interface")
    records = view.generated_interfaces
    candidates = tuple(records.values()) if isinstance(records, Mapping) else tuple(records)
    matches = tuple(
        record
        for record in candidates
        if isinstance(record, GeneratedRotationalInterface)
        and record.interface_id == reference.interface_id
        and record.interface_hash == reference.interface_hash
    )
    if len(matches) != 1:
        raise ValueError("target generated interface cannot be resolved by exact ID and hash")
    return matches[0]


def _resolve_rotation_input(
    derivation: GeneratedPlacementDerivation | CanonicalGeneratedPlacementDerivation,
    view: GeneratedAuthorityView,
) -> tuple[float, float, float, float]:
    rotation = derivation.rotation
    if rotation is None:
        raise ValueError("placement derivation has no rotation input")
    frame_ref = _frame_ref_for_role(derivation, rotation.axis_ref.frame_role)
    frame_orientation = _resolve_frame_orientation(frame_ref, view)
    # The synthetic input reuses the established selection resolver while the
    # derivation target supplies the only permitted instance context.
    resolved = resolve_generated_inputs(
        (
            GeneratedAuthorityInput(
                input_id=rotation.rotation_id,
                role=GeneratedAuthorityRole.CLOCKING_ANGLE,
                source_kind="design_selection",
                locator=rotation.provenance,
                value=rotation.angle_degrees,
                value_hash=rotation.value_hash,
            ),
        ),
        view,
            owning_instance_context=_target_instance_id(derivation),
    )
    local_rotation = _reconstruct_rotation(rotation.axis_ref.axis, resolved[rotation.rotation_id])
    inverse_frame_orientation = normalize_quaternion(
        (
            frame_orientation[0],
            -frame_orientation[1],
            -frame_orientation[2],
            -frame_orientation[3],
        )
    )
    return quaternion_compose(
        quaternion_compose(frame_orientation, local_rotation), inverse_frame_orientation
    )


def resolve_placement_inputs(
    derivation: GeneratedPlacementDerivation | CanonicalGeneratedPlacementDerivation,
    view: GeneratedAuthorityView | None = None,
) -> dict[str, float]:
    target_instance_id = getattr(derivation, "target_physical_instance_id", None)
    if target_instance_id is None:
        target_instance_id = derivation.target_canonical_instance_id
    if any(
        input_record.role is not GeneratedAuthorityRole.AXIAL_OFFSET
        or input_record.source_kind is not GeneratedAuthoritySourceKind.DESIGN_SELECTION
        for input_record in derivation.inputs
    ):
        raise ValueError("placement inputs must be DESIGN_SELECTION axial-offset inputs")
    if derivation.rule_id == "coaxial-generated-placement@1":
        _resolve_target_generated_interface(derivation, view or GeneratedAuthorityView())
    elif derivation.rotation is not None:
        _resolve_rotation_input(derivation, view or GeneratedAuthorityView())
    return resolve_generated_inputs(
        derivation.inputs,
        view,
        owning_instance_context=target_instance_id,
    )


def pose_from_interface(interface) -> CadRigidTransform:
    if isinstance(interface, GeneratedRotationalInterface):
        point = interface.axis_point
        orientation = _rotation_aligning(interface.axis_direction, (0.0, 0.0, 1.0))
    elif isinstance(interface, GeneratedAttachmentFaceInterface):
        point = interface.plane_point
        orientation = _rotation_aligning(interface.outward_normal, (0.0, 0.0, 1.0))
    elif isinstance(interface, GeneratedReferenceFrame):
        point = interface.origin
        orientation = interface.orientation
    else:
        raise TypeError("pose extraction requires a generated interface or reference frame")
    return CadRigidTransform(x_mm=point[0], y_mm=point[1], z_mm=point[2], rotation_quaternion=orientation)


def compose_poses(outer: CadRigidTransform, inner: CadRigidTransform) -> CadRigidTransform:
    rotated = rotate_vector((inner.x_mm, inner.y_mm, inner.z_mm), outer.rotation_quaternion)
    return CadRigidTransform(
        x_mm=outer.x_mm + rotated[0],
        y_mm=outer.y_mm + rotated[1],
        z_mm=outer.z_mm + rotated[2],
        rotation_quaternion=quaternion_compose(
            outer.rotation_quaternion, inner.rotation_quaternion
        ),
    )


def invert_pose(pose: CadRigidTransform) -> CadRigidTransform:
    inverse_rotation = normalize_quaternion(
        (
            pose.rotation_quaternion[0],
            -pose.rotation_quaternion[1],
            -pose.rotation_quaternion[2],
            -pose.rotation_quaternion[3],
        )
    )
    translated = rotate_vector(
        (-pose.x_mm, -pose.y_mm, -pose.z_mm), inverse_rotation
    )
    return CadRigidTransform(
        x_mm=translated[0],
        y_mm=translated[1],
        z_mm=translated[2],
        rotation_quaternion=inverse_rotation,
    )


def place_generated_target(
    rule_id: str,
    source_world_pose: CadRigidTransform,
    target_local_pose: CadRigidTransform,
    axial_offset: float | None,
    explicit_rotation: tuple[float, float, float, float] | None,
) -> CadRigidTransform:
    if rule_id not in PLACEMENT_RULES:
        raise ValueError("unknown generated placement rule")
    if axial_offset is not None:
        axial_offset = _finite_float(axial_offset)
    if rule_id == "coaxial-generated-placement@1" and explicit_rotation is not None:
        raise ValueError("coaxial placement does not accept rotation")
    if rule_id == "frame-generated-placement@1" and explicit_rotation is None:
        raise ValueError("frame placement requires rotation")

    offset_pose = CadRigidTransform(z_mm=0.0 if axial_offset is None else axial_offset)
    rotation_pose = CadRigidTransform(
        rotation_quaternion=(
            (1.0, 0.0, 0.0, 0.0)
            if explicit_rotation is None
            else normalize_quaternion(explicit_rotation)
        )
    )
    return compose_poses(
        compose_poses(
            compose_poses(source_world_pose, offset_pose),
            rotation_pose,
        ),
        invert_pose(target_local_pose),
    )


__all__ = [
    "PLACEMENT_RULES",
    "CanonicalGeneratedPlacementDerivation",
    "DerivationPlacementRef",
    "DesignVariablePlacementRef",
    "GeneratedFrameAxisRef",
    "GeneratedFrameRef",
    "GeneratedInterfaceRef",
    "GeneratedPlacementDerivation",
    "GeneratedPlacementRotationInput",
    "SourcePlacementRef",
    "compose_poses",
    "invert_pose",
    "place_generated_target",
    "placement_derivations_hash",
    "pose_from_interface",
    "resolve_placement_inputs",
]
