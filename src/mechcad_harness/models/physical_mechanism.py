from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_serializer, model_validator

from .common import Model
from .component_property import (
    ComponentPropertyAuthority as CanonicalComponentPropertyAuthority,
    ComponentPropertyAvailability as CanonicalComponentPropertyAvailability,
)
from .geometry_identity import (
    GeometryArtifactIdentity,
    canonical_geometry_reference_payload,
)
from .quaternion import rotate_vector
from .supplied_component_interface import (
    GeometryDerivationStatus,
    GeometryDerivationTransform,
    MaterializedInterfaceVerifier,
    MountingFaceInterface,
    SuppliedComponentInterfaceDefinition,
    SuppliedComponentReferenceFrame,
)


def _canonical_hash(value: Model, identity_field: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(identity_field, None)
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _hash_or_pending(value: str) -> str:
    if value == "pending":
        return value
    if len(value) != 71 or not value.startswith("sha256:"):
        raise ValueError("must be a sha256 hash")
    if any(character not in "0123456789abcdef" for character in value[7:]):
        raise ValueError("must be a sha256 hash")
    return value


def _require_hash(value: str) -> str:
    if value == "pending":
        raise ValueError("must be a sha256 hash")
    return _hash_or_pending(value)


def _nonblank(value: str | None) -> str | None:
    if value is None:
        return value
    if not value.strip():
        raise ValueError("must not be empty or whitespace")
    return value


def _nonblank_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_nonblank(value) for value in values)


class CanonicalModel(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CanonicalPhysicalComponentRole(StrEnum):
    ACTUATOR = "actuator"
    TRANSMISSION = "transmission"
    ROTATING_MEMBER = "rotating_member"
    SHAFT = "shaft"
    BEARING = "bearing"
    HUB_OR_COUPLING = "hub_or_coupling"
    MOUNT_OR_SUPPORT = "mount_or_support"
    DRIVEN_BODY = "driven_body"
    PAYLOAD_OR_FRAME_ATTACHMENT = "payload_or_frame_attachment"


class CanonicalMechanicalConnectionKind(StrEnum):
    FIXED_ATTACHMENT = "fixed_attachment"
    ROTATIONAL_DRIVE = "rotational_drive"
    COAXIAL_CONNECTION = "coaxial_connection"
    SHAFT_JOURNAL = "shaft_journal"
    BEARING_SUPPORT = "bearing_support"
    GEAR_MESH = "gear_mesh"
    COUPLING = "coupling"
    MOTOR_MOUNT = "motor_mount"
    PAYLOAD_ATTACHMENT = "payload_attachment"
    STRUCTURAL_SUPPORT_DECLARATION = "structural_support_declaration"


class CanonicalConnectionMeaning(StrEnum):
    KINEMATIC_REALIZATION_INTENT = "kinematic_realization_intent"
    TORQUE_LOAD_PATH_INTENT = "torque_load_path_intent"
    CAD_PLACEMENT_MATING_INTENT = "cad_placement_mating_intent"
    STRUCTURAL_RELEVANCE = "structural_relevance"


class CanonicalDesignChoiceOrigin(StrEnum):
    CANDIDATE_LOCAL_CHOICE = "candidate_local_choice"
    EXPLICIT_POLICY_ASSUMPTION = "explicit_policy_assumption"
    SOURCE_BACKED_FIXED_VALUE = "source_backed_fixed_value"
    DETERMINISTIC_RELATION = "deterministic_relation"


class CanonicalPlacementOrigin(StrEnum):
    ACCEPTED_DESIGN_CHOICE = "accepted_design_choice"
    ACCEPTED_INTERFACE = "accepted_interface"
    SELECTED_SOURCE_GEOMETRY = "selected_source_geometry"
    DETERMINISTIC_RELATION = "deterministic_relation"
    EXPLICIT_POLICY_ASSUMPTION = "explicit_policy_assumption"


class CanonicalGeometryFidelity(StrEnum):
    TRUSTED_SOURCE_GEOMETRY = "trusted_source_geometry"
    DECLARED_BOUNDED_COLLISION_REPRESENTATION = (
        "declared_bounded_collision_representation"
    )


class CanonicalComponentProperty(CanonicalModel):
    schema_version: Literal["canonical-component-property@1"] = (
        "canonical-component-property@1"
    )
    key: str = Field(min_length=1)
    availability: CanonicalComponentPropertyAvailability
    normalized_value: float | None = None
    normalized_range: tuple[float, float] | None = None
    canonical_unit: str | None = None
    source_identity: str = Field(min_length=1)
    authority: CanonicalComponentPropertyAuthority
    applicability_context: str | None = None
    conversion_provenance: str | None = None
    property_hash: str = "pending"

    _validate_key = field_validator(
        "key",
        "source_identity",
        "canonical_unit",
        "applicability_context",
        "conversion_provenance",
    )(_nonblank)
    _validate_hash = field_validator("property_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_property(self) -> "CanonicalComponentProperty":
        if self.availability is CanonicalComponentPropertyAvailability.AVAILABLE:
            if self.canonical_unit is None or (
                self.normalized_value is None
            ) == (self.normalized_range is None):
                raise ValueError(
                    "available component property requires exactly one normalized value or range and a unit"
                )
        elif any(
            value is not None
            for value in (
                self.normalized_value,
                self.normalized_range,
                self.canonical_unit,
            )
        ):
            raise ValueError("unavailable component property cannot contain a value or unit")
        numbers = (() if self.normalized_value is None else (self.normalized_value,)) + (
            self.normalized_range or ()
        )
        if any(not math.isfinite(number) for number in numbers):
            raise ValueError("component property values must be finite")
        if self.normalized_range is not None and self.normalized_range[0] > self.normalized_range[1]:
            raise ValueError("component property range is invalid")
        expected = _canonical_hash(self, "property_hash")
        if self.property_hash == "pending":
            object.__setattr__(self, "property_hash", expected)
        elif self.property_hash != expected:
            raise ValueError("component property hash mismatch")
        return self


class CanonicalGeometrySourceReference(CanonicalModel):
    artifact_id: str = Field(min_length=1)
    artifact_hash: str
    source_identity: str = Field(min_length=1)
    format: Literal["step"] = "step"
    coordinate_system_id: str | None = None
    reference_hash: str = "pending"

    _validate_text = field_validator("artifact_id", "source_identity")(_nonblank)
    _validate_artifact_hash = field_validator("artifact_hash")(_require_hash)
    _validate_reference_hash = field_validator("reference_hash")(_hash_or_pending)
    _validate_coordinate_system = field_validator("coordinate_system_id")(_nonblank)

    @model_serializer(mode="wrap")
    def serialize_reference(self, handler):
        from .geometry_identity import canonical_geometry_reference_payload

        del handler
        return canonical_geometry_reference_payload(
            self, m13=self.coordinate_system_id is not None
        )

    @model_validator(mode="after")
    def validate_reference(self) -> "CanonicalGeometrySourceReference":
        from .geometry_identity import reference_hash_payload

        payload = reference_hash_payload(self.model_dump(mode="json"))
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        expected = f"sha256:{hashlib.sha256(encoded).hexdigest()}"
        if self.reference_hash == "pending":
            object.__setattr__(self, "reference_hash", expected)
        elif self.reference_hash != expected:
            raise ValueError("geometry source reference hash mismatch")
        return self


def _canonical_interface_reference_frame_id(
    definition: SuppliedComponentInterfaceDefinition,
) -> str | None:
    variant = definition.shaft if definition.shaft is not None else definition.mounting_face
    assert variant is not None
    return variant.reference_frame_id


def _canonical_accepted_fact_value(fact) -> Any | None:
    if fact.accepted_evidence_id is None:
        return None
    evidence = next(
        (record for record in fact.evidence if record.evidence_id == fact.accepted_evidence_id),
        None,
    )
    if evidence is None or evidence.value is None:
        return None
    return evidence.value


def _validate_canonical_mounting_face_frame(
    interface: MountingFaceInterface,
    frame: SuppliedComponentReferenceFrame,
) -> None:
    outward_normal = _canonical_accepted_fact_value(interface.outward_normal)
    orientation = _canonical_accepted_fact_value(frame.orientation)
    if outward_normal is None or orientation is None:
        return
    frame_z = rotate_vector((0.0, 0.0, 1.0), orientation)
    dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(outward_normal, frame_z))))
    if math.acos(dot) > 1e-9:
        raise ValueError("mounting face outward normal does not match frame +Z")


class CanonicalComponentSpecification(CanonicalModel):
    schema_version: Literal[
        "canonical-component-specification@1", "canonical-component-specification@2"
    ] = "canonical-component-specification@1"
    component_type: str = Field(min_length=1)
    manufacturer: str | None = None
    part_number: str | None = None
    source_identity: str = Field(min_length=1)
    properties: tuple[CanonicalComponentProperty, ...] = ()
    geometry_source: CanonicalGeometrySourceReference | None = None
    interfaces: tuple[str, ...] = ()
    compatibility_declarations: tuple[str, ...] = ()
    supplied_reference_frames: tuple[SuppliedComponentReferenceFrame, ...] = ()
    supplied_interface_definitions: tuple[SuppliedComponentInterfaceDefinition, ...] = ()
    geometry_derivation_transforms: tuple[GeometryDerivationTransform, ...] = ()
    specification_hash: str = "pending"

    _validate_text = field_validator(
        "component_type", "source_identity", "manufacturer", "part_number"
    )(_nonblank)
    _validate_hash = field_validator("specification_hash")(_hash_or_pending)

    def _specification_payload_for_schema(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "component_type": self.component_type,
            "manufacturer": self.manufacturer,
            "part_number": self.part_number,
            "source_identity": self.source_identity,
            "properties": [property.model_dump(mode="json") for property in self.properties],
            "geometry_source": (
                None
                if self.geometry_source is None
                else canonical_geometry_reference_payload(
                    self.geometry_source, m13=self.schema_version.endswith("@2")
                )
            ),
            "interfaces": list(self.interfaces),
            "compatibility_declarations": list(self.compatibility_declarations),
        }
        if self.schema_version.endswith("@2"):
            payload.update({
                "supplied_reference_frames": [
                    frame.model_dump(mode="json") for frame in self.supplied_reference_frames
                ],
                "supplied_interface_definitions": [
                    definition.model_dump(mode="json")
                    for definition in self.supplied_interface_definitions
                ],
                "geometry_derivation_transforms": [
                    transform.model_dump(mode="json")
                    for transform in self.geometry_derivation_transforms
                ],
            })
        payload["specification_hash"] = self.specification_hash
        return payload

    def _specification_hash_payload(self) -> dict[str, Any]:
        payload = self._specification_payload_for_schema()
        payload.pop("specification_hash")
        return payload

    @model_serializer(mode="wrap")
    def serialize_specification(self, handler):
        del handler
        return self._specification_payload_for_schema()

    @model_validator(mode="after")
    def validate_specification(self) -> "CanonicalComponentSpecification":
        keys = tuple(property.key for property in self.properties)
        if len(set(keys)) != len(keys):
            raise ValueError("component property keys must be unique")
        declarations = self.interfaces + self.compatibility_declarations
        if any(not value.strip() for value in declarations):
            raise ValueError("component declarations must not be empty")
        if self.schema_version.endswith("@1"):
            if any((
                self.supplied_reference_frames,
                self.supplied_interface_definitions,
                self.geometry_derivation_transforms,
            )):
                raise ValueError("canonical-component-specification@1 must not contain M13 records")
            if self.geometry_source is not None and self.geometry_source.coordinate_system_id is not None:
                raise ValueError("canonical-component-specification@1 requires no coordinate system")
        elif any((
            self.supplied_reference_frames,
            self.supplied_interface_definitions,
            self.geometry_derivation_transforms,
        )) and (
            self.geometry_source is None
            or self.geometry_source.coordinate_system_id is None
        ):
            raise ValueError("canonical-component-specification@2 M13 records require a coordinate system")

        frames = tuple(sorted(self.supplied_reference_frames, key=lambda frame: frame.frame_id))
        definitions = tuple(sorted(
            self.supplied_interface_definitions, key=lambda definition: definition.interface_id
        ))
        transforms = tuple(sorted(
            self.geometry_derivation_transforms, key=lambda transform: transform.transform_id
        ))
        if len({frame.frame_id for frame in frames}) != len(frames):
            raise ValueError("reference frame IDs must be unique")
        if len({definition.interface_id for definition in definitions}) != len(definitions):
            raise ValueError("interface IDs must be unique")
        if len({transform.transform_id for transform in transforms}) != len(transforms):
            raise ValueError("transform IDs must be unique")
        object.__setattr__(self, "supplied_reference_frames", frames)
        object.__setattr__(self, "supplied_interface_definitions", definitions)
        object.__setattr__(self, "geometry_derivation_transforms", transforms)

        selected_geometry = (
            None
            if self.geometry_source is None
            else GeometryArtifactIdentity.from_canonical(self.geometry_source)
        )
        frame_by_id = {frame.frame_id: frame for frame in frames}
        transform_by_id = {transform.transform_id: transform for transform in transforms}
        for frame in frames:
            if selected_geometry is None or frame.geometry_reference_hash != self.geometry_source.reference_hash:
                raise ValueError("reference frame geometry does not match selected geometry")
        for definition in definitions:
            if self.interfaces.count(definition.interface_id) != 1:
                raise ValueError("typed interface IDs must appear exactly once in interfaces")
            if selected_geometry is None or (
                definition.geometry != selected_geometry
                or definition.geometry_reference_hash != self.geometry_source.reference_hash
            ):
                raise ValueError("interface geometry does not match selected geometry")
            frame_id = _canonical_interface_reference_frame_id(definition)
            frame = None if frame_id is None else frame_by_id.get(frame_id)
            if frame_id is not None and frame is None:
                raise ValueError("interface reference frame does not resolve in this specification")
            if definition.kind == "materialized":
                provenance = definition.derivation
                assert provenance is not None
                transform = transform_by_id.get(provenance.transform_id)
                if transform is None or transform.transform_hash != provenance.transform_hash:
                    raise ValueError("materialized interface transform does not resolve")
                if transform.status is not GeometryDerivationStatus.ACCEPTED:
                    raise ValueError("materialized interface transform is not accepted")
                try:
                    MaterializedInterfaceVerifier.verify(
                        provenance, transform, definition, frame
                    )
                except Exception as exc:
                    raise ValueError(f"materialized interface integrity failure: {exc}") from exc
            if isinstance(definition.mounting_face, MountingFaceInterface) and frame is not None:
                _validate_canonical_mounting_face_frame(definition.mounting_face, frame)

        encoded = json.dumps(
            self._specification_hash_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        expected = f"sha256:{hashlib.sha256(encoded).hexdigest()}"
        if self.specification_hash == "pending":
            object.__setattr__(self, "specification_hash", expected)
        elif self.specification_hash != expected:
            raise ValueError("component specification hash mismatch")
        return self


class CanonicalPhysicalComponent(CanonicalModel):
    instance_id: str = Field(min_length=1)
    specification_hash: str
    role: CanonicalPhysicalComponentRole
    interfaces: tuple[str, ...] = ()
    placement_id: str | None = None
    component_hash: str = "pending"

    _validate_text = field_validator("instance_id", "placement_id")(_nonblank)
    _validate_specification_hash = field_validator("specification_hash")(_require_hash)
    _validate_hash = field_validator("component_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_component(self) -> "CanonicalPhysicalComponent":
        if any(not value.strip() for value in self.interfaces):
            raise ValueError("component interface IDs must not be empty")
        expected = _canonical_hash(self, "component_hash")
        if self.component_hash == "pending":
            object.__setattr__(self, "component_hash", expected)
        elif self.component_hash != expected:
            raise ValueError("physical component hash mismatch")
        return self


class CanonicalAcceptedDesignChoice(CanonicalModel):
    key: str = Field(min_length=1)
    value: str | float | int | bool
    origin: CanonicalDesignChoiceOrigin
    provenance: str = Field(min_length=1)
    source_identities: tuple[str, ...] = ()
    choice_hash: str = "pending"

    _validate_text = field_validator("key", "provenance")(_nonblank)
    _validate_hash = field_validator("choice_hash")(_hash_or_pending)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: Any) -> Any:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("design choice values must be finite")
        if isinstance(value, str) and not value.strip():
            raise ValueError("design choice values must not be empty")
        return value

    @model_validator(mode="after")
    def validate_choice(self) -> "CanonicalAcceptedDesignChoice":
        if any(not value.strip() for value in self.source_identities):
            raise ValueError("design choice source identities must not be empty")
        if (
            self.origin is CanonicalDesignChoiceOrigin.EXPLICIT_POLICY_ASSUMPTION
            and not self.provenance.strip()
        ):
            raise ValueError("policy-origin design choice requires explicit provenance")
        expected = _canonical_hash(self, "choice_hash")
        if self.choice_hash == "pending":
            object.__setattr__(self, "choice_hash", expected)
        elif self.choice_hash != expected:
            raise ValueError("accepted design choice hash mismatch")
        return self


class CanonicalPlacement(CanonicalModel):
    placement_id: str = Field(min_length=1)
    instance_id: str = Field(min_length=1)
    origin: CanonicalPlacementOrigin
    input_identities: tuple[str, ...] = Field(min_length=1)
    relation: str = Field(min_length=1)
    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: float = 0.0
    rotation_quaternion: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)
    placement_hash: str = "pending"

    _validate_text = field_validator(
        "placement_id", "instance_id", "relation"
    )(_nonblank)
    _validate_hash = field_validator("placement_hash")(_hash_or_pending)

    @model_validator(mode="before")
    @classmethod
    def normalize_transform(cls, data: Any) -> Any:
        data = dict(data)
        values = tuple(
            float(data.get(name, 0.0))
            for name in ("x_mm", "y_mm", "z_mm")
        ) + tuple(float(value) for value in data.get("rotation_quaternion", (1.0, 0.0, 0.0, 0.0)))
        if any(not math.isfinite(value) for value in values):
            raise ValueError("placement values must be finite")
        quaternion = values[3:]
        norm = math.sqrt(sum(value * value for value in quaternion))
        if norm <= 1e-12:
            raise ValueError("rotation quaternion must have non-zero norm")
        normalized = tuple(value / norm for value in quaternion)
        first_nonzero = next((value for value in normalized if abs(value) > 1e-12), 1.0)
        data["rotation_quaternion"] = (
            tuple(-value for value in normalized)
            if first_nonzero < 0
            else normalized
        )
        return data

    @model_validator(mode="after")
    def validate_placement(self) -> "CanonicalPlacement":
        if any(not value.strip() for value in self.input_identities):
            raise ValueError("placement input identities must not be empty")
        expected = _canonical_hash(self, "placement_hash")
        if self.placement_hash == "pending":
            object.__setattr__(self, "placement_hash", expected)
        elif self.placement_hash != expected:
            raise ValueError("canonical placement hash mismatch")
        return self


class CanonicalMechanicalConnection(CanonicalModel):
    connection_id: str = Field(min_length=1)
    kind: CanonicalMechanicalConnectionKind
    from_instance_id: str = Field(min_length=1)
    from_interface_id: str = Field(min_length=1)
    to_instance_id: str = Field(min_length=1)
    to_interface_id: str = Field(min_length=1)
    meanings: tuple[CanonicalConnectionMeaning, ...] = ()
    connection_hash: str = "pending"

    _validate_text = field_validator(
        "connection_id",
        "from_instance_id",
        "from_interface_id",
        "to_instance_id",
        "to_interface_id",
    )(_nonblank)
    _validate_hash = field_validator("connection_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_connection(self) -> "CanonicalMechanicalConnection":
        if (self.from_instance_id, self.from_interface_id) == (
            self.to_instance_id,
            self.to_interface_id,
        ):
            raise ValueError("connection endpoints must differ")
        if len(set(self.meanings)) != len(self.meanings):
            raise ValueError("connection meanings must be unique")
        expected = _canonical_hash(self, "connection_hash")
        if self.connection_hash == "pending":
            object.__setattr__(self, "connection_hash", expected)
        elif self.connection_hash != expected:
            raise ValueError("mechanical connection hash mismatch")
        return self


class CanonicalJointPhysicalBinding(CanonicalModel):
    joint_id: str = Field(min_length=1)
    expected_parent_instance_id: str = Field(min_length=1)
    expected_child_instance_id: str = Field(min_length=1)
    axis_origin_x_mm: float = 0.0
    axis_origin_y_mm: float = 0.0
    axis_origin_z_mm: float = 0.0
    axis_direction_x: float = 0.0
    axis_direction_y: float = 0.0
    axis_direction_z: float = 1.0
    axis_frame_reference: str = Field(min_length=1)
    semantic_hash: str
    semantic_version: str = Field(min_length=1)
    binding_hash: str = "pending"

    _validate_text = field_validator(
        "joint_id",
        "expected_parent_instance_id",
        "expected_child_instance_id",
        "axis_frame_reference",
        "semantic_version",
    )(_nonblank)
    _validate_semantic_hash = field_validator("semantic_hash")(_require_hash)
    _validate_binding_hash = field_validator("binding_hash")(_hash_or_pending)

    @model_validator(mode="before")
    @classmethod
    def normalize_axis(cls, data: Any) -> Any:
        data = dict(data)
        names = (
            "axis_origin_x_mm",
            "axis_origin_y_mm",
            "axis_origin_z_mm",
            "axis_direction_x",
            "axis_direction_y",
            "axis_direction_z",
        )
        values = tuple(float(data.get(name, 0.0 if name.endswith("_mm") else 0.0)) for name in names)
        if "axis_direction_z" not in data:
            values = values[:5] + (1.0,)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("joint axis values must be finite")
        direction = values[3:]
        norm = math.sqrt(sum(value * value for value in direction))
        if norm <= 1e-12:
            raise ValueError("joint axis direction must be non-zero")
        data.update(
            axis_direction_x=direction[0] / norm,
            axis_direction_y=direction[1] / norm,
            axis_direction_z=direction[2] / norm,
        )
        return data

    @model_validator(mode="after")
    def validate_binding(self) -> "CanonicalJointPhysicalBinding":
        if self.expected_parent_instance_id == self.expected_child_instance_id:
            raise ValueError("joint parent and child instances must differ")
        expected = _canonical_hash(self, "binding_hash")
        if self.binding_hash == "pending":
            object.__setattr__(self, "binding_hash", expected)
        elif self.binding_hash != expected:
            raise ValueError("joint physical binding hash mismatch")
        return self


class CanonicalPhysicalPairRequirement(CanonicalModel):
    requirement_key: str = Field(min_length=1)
    first_instance_id: str = Field(min_length=1)
    first_interface_id: str = Field(min_length=1)
    second_instance_id: str = Field(min_length=1)
    second_interface_id: str = Field(min_length=1)
    requires_home_exact_check: bool = False
    requirement_hash: str = "pending"

    _validate_text = field_validator(
        "requirement_key",
        "first_instance_id",
        "first_interface_id",
        "second_instance_id",
        "second_interface_id",
    )(_nonblank)
    _validate_hash = field_validator("requirement_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_pair(self) -> "CanonicalPhysicalPairRequirement":
        if self.first_instance_id == self.second_instance_id:
            raise ValueError("physical pair requirement must contain two instances")
        expected = _canonical_hash(self, "requirement_hash")
        if self.requirement_hash == "pending":
            object.__setattr__(self, "requirement_hash", expected)
        elif self.requirement_hash != expected:
            raise ValueError("physical pair requirement hash mismatch")
        return self


class CanonicalM10VerificationObligation(CanonicalModel):
    joint_semantic_key: str = Field(min_length=1)
    angle_interval_deg: tuple[float, float]
    required_clearance_mm: float = Field(ge=0)
    physical_pair_requirements: tuple[CanonicalPhysicalPairRequirement, ...] = Field(
        min_length=1
    )
    fidelity_requirements: tuple[tuple[str, CanonicalGeometryFidelity], ...] = ()
    required_home_check_semantics: tuple[str, ...] = ()
    bounded_limitations: tuple[str, ...] = ()
    obligation_hash: str = "pending"

    _validate_text = field_validator("joint_semantic_key")(_nonblank)
    _validate_hash = field_validator("obligation_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_obligation(self) -> "CanonicalM10VerificationObligation":
        start, end = self.angle_interval_deg
        if not all(math.isfinite(value) for value in (start, end)) or start > end:
            raise ValueError("M10 angle interval must be finite and ordered")
        if not math.isfinite(self.required_clearance_mm):
            raise ValueError("M10 required clearance must be finite")
        fidelity_keys = tuple(key for key, _ in self.fidelity_requirements)
        if any(not key.strip() for key in fidelity_keys) or len(set(fidelity_keys)) != len(fidelity_keys):
            raise ValueError("M10 fidelity requirement keys must be unique and non-empty")
        semantic_text = self.required_home_check_semantics + self.bounded_limitations
        if any(not value.strip() for value in semantic_text):
            raise ValueError("M10 obligation semantic text must not be empty")
        expected = _canonical_hash(self, "obligation_hash")
        if self.obligation_hash == "pending":
            object.__setattr__(self, "obligation_hash", expected)
        elif self.obligation_hash != expected:
            raise ValueError("M10 verification obligation hash mismatch")
        return self


class CanonicalPhysicalMechanism(CanonicalModel):
    schema_version: Literal["canonical-physical-mechanism@1"] = (
        "canonical-physical-mechanism@1"
    )
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    component_specifications: tuple[CanonicalComponentSpecification, ...] = Field(
        min_length=1
    )
    components: tuple[CanonicalPhysicalComponent, ...] = Field(min_length=1)
    accepted_design_choices: tuple[CanonicalAcceptedDesignChoice, ...] = ()
    placements: tuple[CanonicalPlacement, ...] = ()
    connections: tuple[CanonicalMechanicalConnection, ...] = ()
    joint_bindings: tuple[CanonicalJointPhysicalBinding, ...] = ()
    m10_obligations: tuple[CanonicalM10VerificationObligation, ...] = ()
    promotion_provenance: tuple[str, ...] = ()
    mechanism_hash: str = "pending"

    _validate_text = field_validator("id", "name")(_nonblank)
    _validate_hash = field_validator("mechanism_hash")(_hash_or_pending)
    _validate_provenance = field_validator("promotion_provenance")(_nonblank_tuple)

    @model_validator(mode="after")
    def validate_mechanism(self) -> "CanonicalPhysicalMechanism":
        component_ids = tuple(component.instance_id for component in self.components)
        if len(set(component_ids)) != len(component_ids):
            raise ValueError("component IDs must be unique")
        specifications = {
            specification.specification_hash: specification
            for specification in self.component_specifications
        }
        if len(specifications) != len(self.component_specifications):
            raise ValueError("component specification hashes must be unique")
        if any(
            component.specification_hash not in specifications for component in self.components
        ):
            raise ValueError("physical component references a missing specification")
        placements = tuple(placement.placement_id for placement in self.placements)
        if len(set(placements)) != len(placements):
            raise ValueError("placement IDs must be unique")
        if any(
            placement.instance_id not in component_ids for placement in self.placements
        ):
            raise ValueError("placement references a missing component")
        placement_ids = set(placements)
        if any(
            component.placement_id is not None
            and component.placement_id not in placement_ids
            for component in self.components
        ):
            raise ValueError("component placement reference is missing")
        connection_ids = tuple(connection.connection_id for connection in self.connections)
        if len(set(connection_ids)) != len(connection_ids):
            raise ValueError("connection IDs must be unique")
        component_interfaces = {
            component.instance_id: set(component.interfaces)
            for component in self.components
        }
        for connection in self.connections:
            if connection.from_instance_id not in component_ids or connection.to_instance_id not in component_ids:
                raise ValueError("connection references a missing component")
            if (
                connection.from_interface_id
                not in component_interfaces[connection.from_instance_id]
                or connection.to_interface_id
                not in component_interfaces[connection.to_instance_id]
            ):
                raise ValueError("connection interface reference is missing")
        joint_ids = tuple(binding.joint_id for binding in self.joint_bindings)
        if len(set(joint_ids)) != len(joint_ids):
            raise ValueError("joint IDs must be unique")
        for binding in self.joint_bindings:
            if not {
                binding.expected_parent_instance_id,
                binding.expected_child_instance_id,
            } <= set(component_ids):
                raise ValueError("joint binding references a missing component")
        joint_id_set = set(joint_ids)
        for obligation in self.m10_obligations:
            if obligation.joint_semantic_key not in joint_id_set:
                raise ValueError("obligation joint semantic key is missing")
            for pair in obligation.physical_pair_requirements:
                for instance_id, interface_id in (
                    (pair.first_instance_id, pair.first_interface_id),
                    (pair.second_instance_id, pair.second_interface_id),
                ):
                    if (
                        instance_id not in component_interfaces
                        or interface_id not in component_interfaces[instance_id]
                    ):
                        raise ValueError(
                            "obligation pair requirement reference is missing"
                        )
            if any(
                component_id not in component_interfaces
                for component_id, _ in obligation.fidelity_requirements
            ):
                raise ValueError("obligation fidelity requirement reference is missing")
        obligation_keys = tuple(obligation.joint_semantic_key for obligation in self.m10_obligations)
        if len(set(obligation_keys)) != len(obligation_keys):
            raise ValueError("M10 obligation joint keys must be unique")
        expected = _canonical_hash(self, "mechanism_hash")
        if self.mechanism_hash == "pending":
            object.__setattr__(self, "mechanism_hash", expected)
        elif self.mechanism_hash != expected:
            raise ValueError("canonical physical mechanism hash mismatch")
        return self


__all__ = [name for name in globals() if name.startswith("Canonical")]
