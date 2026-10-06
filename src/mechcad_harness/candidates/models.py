from __future__ import annotations

import hashlib
import math
from enum import StrEnum
from numbers import Real
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import ConfigDict, Field, field_validator, model_serializer, model_validator

from mechcad_harness.models.common import Model
from mechcad_harness.models.component_property import (
    ComponentPropertyAuthority,
    ComponentPropertyAvailability,
)
from mechcad_harness.models.geometry_identity import (
    GeometryArtifactIdentity,
    candidate_geometry_reference_payload,
    candidate_geometry_reference_wire_payload,
    reference_hash_payload,
    semantic_reference_hash,
)
from mechcad_harness.models.supplied_component_interface import (
    MaterializedInterfaceVerifier,
    MountingFaceInterface,
    SuppliedComponentInterfaceDefinition,
    SuppliedComponentReferenceFrame,
    GeometryDerivationStatus,
    GeometryDerivationTransform,
)
from mechcad_harness.models.generated_part import (
    GeneratedPartSpecification,
    validate_generated_interface_registry,
)
from mechcad_harness.candidates.dimensions import (
    LEGACY_PLATE_DIMENSION_ALIASES,
    DimensionInput,
    DimensionResolutionError,
    resolve_dimensions,
)
from mechcad_harness.models.physical_pair_policy import PhysicalPairClassificationBinding
from mechcad_harness.models.physical_mechanism import physical_kinematic_root_hash
from mechcad_harness.models.quaternion import rotate_vector
from mechcad_harness.state.hashing import canonical_json, state_hash


def _hash(value: Any, identity_field: str) -> str:
    if isinstance(value, Model):
        payload = value.model_dump(mode="json")
    else:
        payload = value
    payload = dict(payload)
    payload.pop(identity_field, None)
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def _require_hash(value: str) -> str:
    if len(value) != 71 or not value.startswith("sha256:") or any(char not in "0123456789abcdef" for char in value[7:]):
        raise ValueError("must be a sha256 hash")
    return value


def _hash_payload(payload: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def _require_nonblank_physical_identity(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("physical identity must not be empty or whitespace")
    return value


def _require_path(value: str) -> str:
    if not value.startswith("/") or value == "/" or "//" in value or "~" in value:
        raise ValueError("must be a literal non-root canonical path")
    return value


def _resolve_path(payload: Any, path: str) -> Any:
    value = payload
    for segment in path[1:].split("/"):
        if isinstance(value, dict) and segment in value:
            value = value[segment]
        elif isinstance(value, list) and segment.isdecimal() and int(segment) < len(value):
            value = value[int(segment)]
        else:
            raise ValueError(f"consumed authority path is missing: {path}")
    return value


class CandidateModel(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CandidateSourceAuthority(StrEnum):
    CANONICAL_REQUIREMENT = "canonical_requirement"
    CANONICAL_CONSTRAINT = "canonical_constraint"
    CANONICAL_INTERFACE = "canonical_interface"
    CANONICAL_PARAMETER = "canonical_parameter"
    CANONICAL_COMPONENT_FACT = "canonical_component_fact"
    CANONICAL_MATERIAL_FACT = "canonical_material_fact"


class CandidateSourceReference(CandidateModel):
    path: str
    value_hash: str
    authority: CandidateSourceAuthority

    _validate_path = field_validator("path")(_require_path)

    @field_validator("value_hash")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return value if value == "pending" else _require_hash(value)

class CandidateSourceBinding(CandidateModel):
    project_id: str = Field(min_length=1)
    source_revision: int = Field(gt=0)
    source_state_hash: str
    consumed_authority: tuple[CandidateSourceReference, ...] = Field(min_length=1)

    _validate_state_hash = field_validator("source_state_hash")(_require_hash)

    @model_validator(mode="after")
    def validate_unique_paths(self):
        paths = tuple(reference.path for reference in self.consumed_authority)
        if len(set(paths)) != len(paths):
            raise ValueError("consumed authority paths must be unique")
        return self

    def bound_to(self, state) -> "CandidateSourceBinding":
        payload = state.model_dump(mode="json")
        references = tuple(
            reference.model_copy(update={"value_hash": "sha256:" + hashlib.sha256(canonical_json(_resolve_path(payload, reference.path))).hexdigest()})
            for reference in self.consumed_authority
        )
        return self.model_copy(update={"source_revision": state.revision, "source_state_hash": state_hash(state), "consumed_authority": references})

    def validate_against(self, project_id: str, state) -> None:
        if project_id != self.project_id or state.revision != self.source_revision or state_hash(state) != self.source_state_hash:
            raise ValueError("candidate source project, revision, or state hash mismatch")
        payload = state.model_dump(mode="json")
        for reference in self.consumed_authority:
            if reference.value_hash == "pending":
                raise ValueError("candidate source authority reference is unbound")
            actual = "sha256:" + hashlib.sha256(canonical_json(_resolve_path(payload, reference.path))).hexdigest()
            if actual != reference.value_hash:
                raise ValueError(f"candidate source authority value mismatch: {reference.path}")


class ComponentPropertySnapshot(CandidateModel):
    schema_version: Literal["component-property@1"] = "component-property@1"
    key: str = Field(min_length=1)
    availability: ComponentPropertyAvailability
    normalized_value: float | None = None
    normalized_range: tuple[float, float] | None = None
    canonical_unit: str | None = None
    source_identity: str = Field(min_length=1)
    authority: ComponentPropertyAuthority
    applicability_context: str | None = None
    conversion_provenance: str | None = None
    property_hash: str = "pending"

    @model_validator(mode="after")
    def validate_value_and_hash(self):
        if self.availability is ComponentPropertyAvailability.AVAILABLE:
            if self.canonical_unit is None or (self.normalized_value is None) == (self.normalized_range is None):
                raise ValueError("available component property requires exactly one normalized value or range and a unit")
        elif any(value is not None for value in (self.normalized_value, self.normalized_range, self.canonical_unit)):
            raise ValueError("unavailable component property cannot contain a value or unit")
        numbers = (() if self.normalized_value is None else (self.normalized_value,)) + (self.normalized_range or ())
        if any(not math.isfinite(number) for number in numbers):
            raise ValueError("component property values must be finite")
        if self.normalized_range is not None and self.normalized_range[0] > self.normalized_range[1]:
            raise ValueError("component property range is invalid")
        expected = _hash(self, "property_hash")
        if self.property_hash == "pending":
            object.__setattr__(self, "property_hash", expected)
        elif self.property_hash != expected:
            raise ValueError("component property hash mismatch")
        return self


class GeometrySourceReference(CandidateModel):
    artifact_id: str = Field(min_length=1)
    artifact_hash: str
    source_identity: str = Field(min_length=1)
    format: Literal["step"] = "step"
    coordinate_system_id: str | None = None
    reference_hash: str = "pending"
    content_identity: str | None = None
    content_identity_algorithm: Literal["step-content-identity@1"] | None = None
    semantic_reference_hash: str | None = None

    _validate_artifact_hash = field_validator("artifact_hash")(_require_hash)
    _validate_reference_hash = field_validator("reference_hash")(
        lambda value: value if value == "pending" else _require_hash(value)
    )
    _validate_content_identity = field_validator("content_identity")(
        lambda value: value if value in (None, "pending") else _require_hash(value)
    )
    _validate_semantic_reference_hash = field_validator("semantic_reference_hash")(
        lambda value: value if value in (None, "pending") else _require_hash(value)
    )

    @field_validator("coordinate_system_id")
    @classmethod
    def validate_coordinate_system(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("coordinate_system_id must not be empty")
        return value

    @model_serializer(mode="wrap")
    def serialize_reference(self, handler):
        from mechcad_harness.models.geometry_identity import candidate_geometry_reference_wire_payload

        del handler
        return candidate_geometry_reference_wire_payload(
            self, m13=self.coordinate_system_id is not None
        )

    @model_validator(mode="after")
    def validate_reference(self):
        trio = (
            self.content_identity,
            self.content_identity_algorithm,
            self.semantic_reference_hash,
        )
        if self.content_identity is not None and self.content_identity_algorithm is None:
            raise ValueError("semantic geometry reference fields must be all present or absent")
        if self.content_identity is None and any(value is not None for value in trio[1:]):
            raise ValueError("semantic geometry reference fields must be all present or absent")
        pending_content_identity = self.content_identity == "pending"
        if pending_content_identity:
            if self.semantic_reference_hash not in (None, "pending"):
                raise ValueError("pending semantic geometry content cannot have a concrete reference hash")
            object.__setattr__(self, "semantic_reference_hash", "pending")
        expected = _hash_payload(
            reference_hash_payload(
                candidate_geometry_reference_payload(
                    self, m13=self.coordinate_system_id is not None
                )
            )
        )
        if self.reference_hash == "pending":
            object.__setattr__(self, "reference_hash", expected)
        elif self.reference_hash != expected:
            raise ValueError("geometry source reference hash mismatch")
        if self.content_identity is not None and self.semantic_reference_hash is None:
            object.__setattr__(self, "semantic_reference_hash", "pending")
        if self.content_identity is not None and not pending_content_identity:
            expected_semantic = semantic_reference_hash(self)
            if self.semantic_reference_hash == "pending":
                object.__setattr__(self, "semantic_reference_hash", expected_semantic)
            elif self.semantic_reference_hash != expected_semantic:
                raise ValueError("semantic geometry reference hash mismatch")
        return self


def _candidate_interface_reference_frame_id(
    definition: SuppliedComponentInterfaceDefinition,
) -> str | None:
    variant = definition.shaft if definition.shaft is not None else definition.mounting_face
    assert variant is not None
    return variant.reference_frame_id


def _accepted_fact_value(fact) -> Any | None:
    if fact.accepted_evidence_id is None:
        return None
    evidence = next(
        (record for record in fact.evidence if record.evidence_id == fact.accepted_evidence_id),
        None,
    )
    if evidence is None or evidence.value is None:
        return None
    return evidence.value


def _validate_mounting_face_frame(
    interface: MountingFaceInterface,
    frame: SuppliedComponentReferenceFrame,
) -> None:
    outward_normal = _accepted_fact_value(interface.outward_normal)
    orientation = _accepted_fact_value(frame.orientation)
    if outward_normal is None or orientation is None:
        return
    frame_z = rotate_vector((0.0, 0.0, 1.0), orientation)
    dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(outward_normal, frame_z))))
    if math.acos(dot) > 1e-9:
        raise ValueError("mounting face outward normal does not match frame +Z")


class ComponentSpecificationSnapshot(CandidateModel):
    schema_version: Literal[
        "component-specification@1",
        "component-specification@2",
        "component-specification@3",
        "component-specification@4",
    ] = "component-specification@1"
    component_type: str = Field(min_length=1)
    manufacturer: str | None = None
    part_number: str | None = None
    source_identity: str = Field(min_length=1)
    properties: tuple[ComponentPropertySnapshot, ...] = ()
    geometry_source: GeometrySourceReference | None = None
    generated_part: GeneratedPartSpecification | None = None
    interfaces: tuple[str, ...] = ()
    compatibility_declarations: tuple[str, ...] = ()
    supplied_reference_frames: tuple[SuppliedComponentReferenceFrame, ...] = ()
    supplied_interface_definitions: tuple[SuppliedComponentInterfaceDefinition, ...] = ()
    geometry_derivation_transforms: tuple[GeometryDerivationTransform, ...] = ()
    specification_hash: str = "pending"

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
                else (
                    candidate_geometry_reference_wire_payload(
                        self.geometry_source,
                        m13=True,
                    )
                    if self.schema_version == "component-specification@4"
                    else candidate_geometry_reference_payload(
                        self.geometry_source,
                        m13=self.schema_version == "component-specification@2",
                    )
                )
            ),
            "interfaces": list(self.interfaces),
            "compatibility_declarations": list(self.compatibility_declarations),
        }
        if self.schema_version == "component-specification@3":
            payload["generated_part"] = (
                None
                if self.generated_part is None
                else self.generated_part.model_dump(mode="json")
            )
        if self.schema_version in {
            "component-specification@2",
            "component-specification@4",
        }:
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
        if self.schema_version == "component-specification@4" and self.generated_part is not None:
            payload["generated_part"] = self.generated_part.model_dump(mode="json")
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
    def validate_specification(self):
        if self.schema_version != "component-specification@4" and self.geometry_source is not None:
            if any(
                value is not None
                for value in (
                    self.geometry_source.content_identity,
                    self.geometry_source.content_identity_algorithm,
                    self.geometry_source.semantic_reference_hash,
                )
            ):
                raise ValueError("legacy component specifications must not contain semantic geometry fields")
        keys = tuple(property.key for property in self.properties)
        if len(set(keys)) != len(keys):
            raise ValueError("component property keys must be unique")
        if any(not value.strip() for value in self.interfaces + self.compatibility_declarations):
            raise ValueError("component interface declarations must not be empty")
        if self.schema_version == "component-specification@1":
            if self.generated_part is not None:
                raise ValueError("component-specification@1 must not contain generated_part")
            if any((
                self.supplied_reference_frames,
                self.supplied_interface_definitions,
                self.geometry_derivation_transforms,
            )):
                raise ValueError("component-specification@1 must not contain M13 records")
            if self.geometry_source is not None and self.geometry_source.coordinate_system_id is not None:
                raise ValueError("component-specification@1 requires no coordinate system")
        elif self.schema_version == "component-specification@2":
            if self.generated_part is not None:
                raise ValueError("component-specification@2 must not contain generated_part")
            if any(
                (
                    self.supplied_reference_frames,
                    self.supplied_interface_definitions,
                    self.geometry_derivation_transforms,
                )
            ) and (
                self.geometry_source is None
                or self.geometry_source.coordinate_system_id is None
            ):
                raise ValueError("component-specification@2 M13 records require a coordinate system")
        elif self.schema_version == "component-specification@3":
            if self.generated_part is None:
                raise ValueError("component-specification@3 requires generated_part")
            if self.geometry_source is not None or any((
                self.supplied_reference_frames,
                self.supplied_interface_definitions,
                self.geometry_derivation_transforms,
            )):
                raise ValueError(
                    "component-specification@3 generated representation is exclusive"
                )
            validate_generated_interface_registry(self.generated_part, self.interfaces)
        else:
            has_m13 = any((
                self.supplied_reference_frames,
                self.supplied_interface_definitions,
                self.geometry_derivation_transforms,
            ))
            if self.generated_part is not None:
                if self.geometry_source is not None or has_m13:
                    raise ValueError("component-specification@4 generated representation is exclusive")
                validate_generated_interface_registry(self.generated_part, self.interfaces)
            else:
                if self.geometry_source is None:
                    raise ValueError("component-specification@4 supplied representation requires geometry_source")
                if has_m13 and self.geometry_source.coordinate_system_id is None:
                    raise ValueError("component-specification@4 M13 records require a coordinate system")

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
            else GeometryArtifactIdentity.from_candidate(self.geometry_source)
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
            frame_id = _candidate_interface_reference_frame_id(definition)
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
                _validate_mounting_face_frame(definition.mounting_face, frame)

        if self.schema_version == "component-specification@4":
            if self.specification_hash != "pending":
                _require_hash(self.specification_hash)
        else:
            expected = _hash_payload(self._specification_hash_payload())
            if self.specification_hash == "pending":
                object.__setattr__(self, "specification_hash", expected)
            elif self.specification_hash != expected:
                raise ValueError("component specification hash mismatch")
        return self


class PhysicalComponentRole(StrEnum):
    ACTUATOR = "actuator"
    TRANSMISSION = "transmission"
    ROTATING_MEMBER = "rotating_member"
    SHAFT = "shaft"
    BEARING = "bearing"
    HUB_OR_COUPLING = "hub_or_coupling"
    MOUNT_OR_SUPPORT = "mount_or_support"
    DRIVEN_BODY = "driven_body"
    PAYLOAD_OR_FRAME_ATTACHMENT = "payload_or_frame_attachment"


class PhysicalComponentInstance(CandidateModel):
    instance_id: str = Field(min_length=1)
    specification_hash: str
    role: PhysicalComponentRole
    interfaces: tuple[str, ...] = ()

    _validate_specification_hash = field_validator("specification_hash")(_require_hash)


class MechanicalConnectionKind(StrEnum):
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


class ConnectionMeaning(StrEnum):
    KINEMATIC_REALIZATION_INTENT = "kinematic_realization_intent"
    TORQUE_LOAD_PATH_INTENT = "torque_load_path_intent"
    CAD_PLACEMENT_MATING_INTENT = "cad_placement_mating_intent"
    STRUCTURAL_RELEVANCE = "structural_relevance"


class MechanicalConnection(CandidateModel):
    connection_id: str = Field(min_length=1)
    kind: MechanicalConnectionKind
    from_instance_id: str = Field(min_length=1)
    from_interface_id: str = Field(min_length=1)
    to_instance_id: str = Field(min_length=1)
    to_interface_id: str = Field(min_length=1)
    meanings: tuple[ConnectionMeaning, ...] = ()

    @model_validator(mode="after")
    def validate_endpoints(self):
        if (self.from_instance_id, self.from_interface_id) == (self.to_instance_id, self.to_interface_id):
            raise ValueError("connection endpoints must differ")
        if len(set(self.meanings)) != len(self.meanings):
            raise ValueError("connection meanings must be unique")
        return self


class PhysicalRigidBodyBinding(CandidateModel):
    schema_version: Literal["physical-rigid-body-binding@1"] = "physical-rigid-body-binding@1"
    physical_body_id: str = Field(min_length=1)
    member_physical_instance_ids: tuple[str, ...] = Field(min_length=1)
    reference_physical_instance_id: str = Field(min_length=1)
    binding_hash: str = "pending"

    @field_validator(
        "physical_body_id", "member_physical_instance_ids", "reference_physical_instance_id"
    )
    @classmethod
    def validate_nonblank(cls, value):
        if isinstance(value, tuple):
            if any(not member.strip() for member in value):
                raise ValueError("physical body member IDs must not be empty or whitespace")
        elif not value.strip():
            raise ValueError("physical body IDs must not be empty or whitespace")
        return value

    _validate_binding_hash = field_validator("binding_hash")(
        lambda value: value if value == "pending" else _require_hash(value)
    )

    @model_validator(mode="after")
    def validate_membership_and_hash(self):
        members = self.member_physical_instance_ids
        if len(set(members)) != len(members):
            raise ValueError("physical body member IDs must be unique")
        canonical_members = tuple(sorted(members))
        if members != canonical_members:
            object.__setattr__(self, "member_physical_instance_ids", canonical_members)
        if self.reference_physical_instance_id not in canonical_members:
            raise ValueError("physical body reference must be a member")
        expected = _hash(self, "binding_hash")
        if self.binding_hash == "pending":
            object.__setattr__(self, "binding_hash", expected)
        elif self.binding_hash != expected:
            raise ValueError("physical rigid body binding hash mismatch")
        return self


class PhysicalAxisOwnerEndpoint(StrEnum):
    PARENT = "parent"
    CHILD = "child"


class PhysicalJointMotionMode(StrEnum):
    BOUNDED = "bounded"
    CONTINUOUS = "continuous"


class SuppliedRotationalInterfaceAxisSource(CandidateModel):
    schema_version: Literal["supplied-rotational-interface-axis-source@1"] = (
        "supplied-rotational-interface-axis-source@1"
    )
    source_kind: Literal["supplied_rotational_interface"] = "supplied_rotational_interface"
    source_physical_instance_id: str = Field(min_length=1)
    interface_id: str = Field(min_length=1)
    interface_hash: str
    geometry_reference_hash: str
    specification_hash: str
    source_hash: str = "pending"

    _validate_source_instance_id = field_validator("source_physical_instance_id")(
        _require_nonblank_physical_identity
    )
    _validate_interface_id = field_validator("interface_id")(_require_nonblank_physical_identity)
    _validate_interface_hash = field_validator("interface_hash")(_require_hash)
    _validate_geometry_reference_hash = field_validator("geometry_reference_hash")(_require_hash)
    _validate_specification_hash = field_validator("specification_hash")(_require_hash)
    _validate_source_hash = field_validator("source_hash")(
        lambda value: value if value == "pending" else _require_hash(value)
    )

    @model_validator(mode="after")
    def validate_source_hash(self):
        expected = _hash(self, "source_hash")
        if self.source_hash == "pending":
            object.__setattr__(self, "source_hash", expected)
        elif self.source_hash != expected:
            raise ValueError("supplied rotational interface axis source hash mismatch")
        return self


class SuppliedReferenceFrameAxisSource(CandidateModel):
    schema_version: Literal["supplied-reference-frame-axis-source@1"] = (
        "supplied-reference-frame-axis-source@1"
    )
    source_kind: Literal["supplied_reference_frame"] = "supplied_reference_frame"
    source_physical_instance_id: str = Field(min_length=1)
    frame_id: str = Field(min_length=1)
    frame_hash: str
    geometry_reference_hash: str
    specification_hash: str
    source_hash: str = "pending"

    _validate_source_instance_id = field_validator("source_physical_instance_id")(
        _require_nonblank_physical_identity
    )
    _validate_frame_id = field_validator("frame_id")(_require_nonblank_physical_identity)
    _validate_frame_hash = field_validator("frame_hash")(_require_hash)
    _validate_geometry_reference_hash = field_validator("geometry_reference_hash")(_require_hash)
    _validate_specification_hash = field_validator("specification_hash")(_require_hash)
    _validate_source_hash = field_validator("source_hash")(
        lambda value: value if value == "pending" else _require_hash(value)
    )

    @model_validator(mode="after")
    def validate_source_hash(self):
        expected = _hash(self, "source_hash")
        if self.source_hash == "pending":
            object.__setattr__(self, "source_hash", expected)
        elif self.source_hash != expected:
            raise ValueError("supplied reference frame axis source hash mismatch")
        return self


class GeneratedRotationalInterfaceAxisSource(CandidateModel):
    schema_version: Literal["generated-rotational-interface-axis-source@1"] = (
        "generated-rotational-interface-axis-source@1"
    )
    source_kind: Literal["generated_rotational_interface"] = "generated_rotational_interface"
    source_physical_instance_id: str = Field(min_length=1)
    interface_id: str = Field(min_length=1)
    interface_hash: str
    generated_specification_hash: str
    source_hash: str = "pending"

    _validate_source_instance_id = field_validator("source_physical_instance_id")(
        _require_nonblank_physical_identity
    )
    _validate_interface_id = field_validator("interface_id")(_require_nonblank_physical_identity)
    _validate_interface_hash = field_validator("interface_hash")(_require_hash)
    _validate_generated_specification_hash = field_validator("generated_specification_hash")(
        _require_hash
    )
    _validate_source_hash = field_validator("source_hash")(
        lambda value: value if value == "pending" else _require_hash(value)
    )

    @model_validator(mode="after")
    def validate_source_hash(self):
        expected = _hash(self, "source_hash")
        if self.source_hash == "pending":
            object.__setattr__(self, "source_hash", expected)
        elif self.source_hash != expected:
            raise ValueError("generated rotational interface axis source hash mismatch")
        return self


class GeneratedReferenceFrameAxisSource(CandidateModel):
    schema_version: Literal["generated-reference-frame-axis-source@1"] = (
        "generated-reference-frame-axis-source@1"
    )
    source_kind: Literal["generated_reference_frame"] = "generated_reference_frame"
    source_physical_instance_id: str = Field(min_length=1)
    frame_id: str = Field(min_length=1)
    frame_hash: str
    generated_specification_hash: str
    source_hash: str = "pending"

    _validate_source_instance_id = field_validator("source_physical_instance_id")(
        _require_nonblank_physical_identity
    )
    _validate_frame_id = field_validator("frame_id")(_require_nonblank_physical_identity)
    _validate_frame_hash = field_validator("frame_hash")(_require_hash)
    _validate_generated_specification_hash = field_validator("generated_specification_hash")(
        _require_hash
    )
    _validate_source_hash = field_validator("source_hash")(
        lambda value: value if value == "pending" else _require_hash(value)
    )

    @model_validator(mode="after")
    def validate_source_hash(self):
        expected = _hash(self, "source_hash")
        if self.source_hash == "pending":
            object.__setattr__(self, "source_hash", expected)
        elif self.source_hash != expected:
            raise ValueError("generated reference frame axis source hash mismatch")
        return self


PhysicalAxisSource: TypeAlias = Annotated[
    SuppliedRotationalInterfaceAxisSource
    | SuppliedReferenceFrameAxisSource
    | GeneratedRotationalInterfaceAxisSource
    | GeneratedReferenceFrameAxisSource,
    Field(discriminator="source_kind"),
]


class PhysicalRevoluteJointBinding(CandidateModel):
    schema_version: Literal["physical-revolute-joint-binding@1"] = "physical-revolute-joint-binding@1"
    physical_joint_id: str = Field(min_length=1)
    parent_physical_body_id: str = Field(min_length=1)
    child_physical_body_id: str = Field(min_length=1)
    connection_id: str = Field(min_length=1)
    parent_physical_instance_id: str = Field(min_length=1)
    parent_interface_id: str = Field(min_length=1)
    child_physical_instance_id: str = Field(min_length=1)
    child_interface_id: str = Field(min_length=1)
    axis_source: PhysicalAxisSource
    axis_owner_endpoint: PhysicalAxisOwnerEndpoint
    axis_sign: Literal[1, -1]
    motion_mode: PhysicalJointMotionMode
    min_angle_deg: float | None
    max_angle_deg: float | None
    zero_reference_semantics: Literal["accepted-semantic-home@1"]
    binding_hash: str = "pending"

    _validate_identity = field_validator(
        "physical_joint_id",
        "parent_physical_body_id",
        "child_physical_body_id",
        "connection_id",
        "parent_physical_instance_id",
        "parent_interface_id",
        "child_physical_instance_id",
        "child_interface_id",
    )(_require_nonblank_physical_identity)
    @field_validator("axis_sign", mode="before")
    @classmethod
    def validate_axis_sign(cls, value):
        if type(value) is not int or value not in (1, -1):
            raise ValueError("physical joint axis sign must be exactly 1 or -1")
        return value

    @field_validator("min_angle_deg", "max_angle_deg", mode="before")
    @classmethod
    def validate_angle_limit_input(cls, value):
        if value is None:
            return value
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("physical joint angle limits must be finite numbers")
        return value

    _validate_binding_hash = field_validator("binding_hash")(
        lambda value: value if value == "pending" else _require_hash(value)
    )

    @model_validator(mode="after")
    def validate_motion_and_hash(self):
        if self.motion_mode is PhysicalJointMotionMode.BOUNDED:
            if self.min_angle_deg is None or self.max_angle_deg is None:
                raise ValueError("bounded physical joint requires both angle limits")
            if (
                not math.isfinite(self.min_angle_deg)
                or not math.isfinite(self.max_angle_deg)
                or self.min_angle_deg >= self.max_angle_deg
            ):
                raise ValueError("bounded physical joint limits must be finite and ordered")
        elif self.min_angle_deg is not None or self.max_angle_deg is not None:
            raise ValueError("continuous physical joint must have no angle limits")

        expected = _hash(self, "binding_hash")
        if self.binding_hash == "pending":
            object.__setattr__(self, "binding_hash", expected)
        elif self.binding_hash != expected:
            raise ValueError("physical revolute joint binding hash mismatch")
        return self


class JointPhysicalRealizationBinding(CandidateModel):
    joint_id: str = Field(min_length=1)
    driven_instance_id: str = Field(min_length=1)
    realization_component_ids: tuple[str, ...] = Field(min_length=1)
    actuator_path_connection_ids: tuple[str, ...] = ()
    transmission_path_connection_ids: tuple[str, ...] = ()
    support_instance_ids: tuple[str, ...] = ()
    hub_or_coupling_instance_id: str | None = None
    mount_or_support_instance_ids: tuple[str, ...] = ()
    axis_frame_reference: str = Field(min_length=1)
    load_path_metadata_available: bool


class PhysicalMechanismRealization(CandidateModel):
    schema_version: Literal[
        "physical-mechanism-realization@1",
        "physical-mechanism-realization@2",
    ] = "physical-mechanism-realization@1"
    components: tuple[PhysicalComponentInstance, ...] = Field(min_length=1)
    connections: tuple[MechanicalConnection, ...] = ()
    joint_bindings: tuple[JointPhysicalRealizationBinding, ...] = ()
    physical_rigid_body_bindings: tuple[PhysicalRigidBodyBinding, ...] = ()
    physical_revolute_joint_bindings: tuple[PhysicalRevoluteJointBinding, ...] = ()
    kinematic_root_physical_body_id: str | None = None
    kinematic_root_binding_hash: str | None = None
    physical_pair_classification_bindings: tuple[PhysicalPairClassificationBinding, ...] = ()
    realization_hash: str = "pending"

    _validate_root_id = field_validator("kinematic_root_physical_body_id")(
        lambda value: None
        if value is None
        else _require_nonblank_physical_identity(value)
    )
    _validate_root_hash = field_validator("kinematic_root_binding_hash")(
        lambda value: None if value is None else _require_hash(value)
    )

    def _realization_payload(self, *, include_hash: bool) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "components": [component.model_dump(mode="json") for component in self.components],
            "connections": [connection.model_dump(mode="json") for connection in self.connections],
            "joint_bindings": [binding.model_dump(mode="json") for binding in self.joint_bindings],
        }
        if self.schema_version == "physical-mechanism-realization@2":
            payload.update(
                {
                    "physical_rigid_body_bindings": [
                        binding.model_dump(mode="json")
                        for binding in self.physical_rigid_body_bindings
                    ],
                    "physical_revolute_joint_bindings": [
                        binding.model_dump(mode="json")
                        for binding in self.physical_revolute_joint_bindings
                    ],
                    "kinematic_root_physical_body_id": self.kinematic_root_physical_body_id,
                    "kinematic_root_binding_hash": self.kinematic_root_binding_hash,
                    "physical_pair_classification_bindings": [
                        binding.model_dump(mode="json")
                        for binding in self.physical_pair_classification_bindings
                    ],
                }
            )
        if include_hash:
            payload["realization_hash"] = self.realization_hash
        return payload

    @model_serializer(mode="wrap")
    def serialize_realization(self, handler):
        payload = handler(self)
        if self.schema_version == "physical-mechanism-realization@1":
            for field_name in (
                "physical_rigid_body_bindings",
                "physical_revolute_joint_bindings",
                "kinematic_root_physical_body_id",
                "kinematic_root_binding_hash",
                "physical_pair_classification_bindings",
            ):
                payload.pop(field_name, None)
        return payload

    @model_validator(mode="after")
    def validate_graph_and_hash(self):
        component_ids = {component.instance_id: component for component in self.components}
        if len(component_ids) != len(self.components):
            raise ValueError("physical component IDs must be unique")
        connection_ids = {connection.connection_id for connection in self.connections}
        if len(connection_ids) != len(self.connections):
            raise ValueError("mechanical connection IDs must be unique")
        for connection in self.connections:
            for instance_id, interface_id in ((connection.from_instance_id, connection.from_interface_id), (connection.to_instance_id, connection.to_interface_id)):
                if instance_id not in component_ids or interface_id not in component_ids[instance_id].interfaces:
                    raise ValueError("mechanical connection endpoint is missing")
        joint_ids = {binding.joint_id for binding in self.joint_bindings}
        if len(joint_ids) != len(self.joint_bindings):
            raise ValueError("joint physical realization bindings must be unique")
        for binding in self.joint_bindings:
            referenced_components = set(binding.realization_component_ids) | {binding.driven_instance_id} | set(binding.support_instance_ids) | set(binding.mount_or_support_instance_ids)
            if binding.hub_or_coupling_instance_id is not None:
                referenced_components.add(binding.hub_or_coupling_instance_id)
            if not referenced_components <= component_ids.keys():
                raise ValueError("joint physical realization component is missing")
            if not (set(binding.actuator_path_connection_ids) | set(binding.transmission_path_connection_ids)) <= connection_ids:
                raise ValueError("joint physical realization connection is missing")

        m13_fields = {
            "physical_rigid_body_bindings",
            "physical_revolute_joint_bindings",
            "kinematic_root_physical_body_id",
            "kinematic_root_binding_hash",
            "physical_pair_classification_bindings",
        }
        supplied_m13_fields = self.model_fields_set & m13_fields
        if self.schema_version == "physical-mechanism-realization@1":
            if supplied_m13_fields:
                raise ValueError("physical-mechanism-realization@1 must not contain M13-3 fields")
        else:
            if supplied_m13_fields != m13_fields:
                raise ValueError("physical-mechanism-realization@2 requires all M13-3 fields")
            if self.kinematic_root_physical_body_id is None or self.kinematic_root_binding_hash is None:
                raise ValueError("physical-mechanism-realization@2 requires a kinematic root")

            body_ids = tuple(binding.physical_body_id for binding in self.physical_rigid_body_bindings)
            if len(set(body_ids)) != len(body_ids):
                raise ValueError("physical rigid body IDs must be unique")
            ordered_bodies = tuple(
                sorted(self.physical_rigid_body_bindings, key=lambda binding: binding.physical_body_id)
            )
            object.__setattr__(self, "physical_rigid_body_bindings", ordered_bodies)
            body_ids = {binding.physical_body_id for binding in ordered_bodies}
            if self.kinematic_root_physical_body_id not in body_ids:
                raise ValueError("kinematic root physical body is missing")
            if self.kinematic_root_binding_hash != physical_kinematic_root_hash(
                self.kinematic_root_physical_body_id
            ):
                raise ValueError("kinematic root binding hash mismatch")

            member_owner: dict[str, str] = {}
            for binding in ordered_bodies:
                for instance_id in binding.member_physical_instance_ids:
                    if instance_id not in component_ids:
                        raise ValueError("physical rigid body member is missing")
                    previous_owner = member_owner.setdefault(instance_id, binding.physical_body_id)
                    if previous_owner != binding.physical_body_id:
                        raise ValueError("physical component belongs to multiple physical bodies")

            joint_ids = tuple(
                binding.physical_joint_id for binding in self.physical_revolute_joint_bindings
            )
            if len(set(joint_ids)) != len(joint_ids):
                raise ValueError("physical revolute joint IDs must be unique")
            ordered_joints = tuple(
                sorted(
                    self.physical_revolute_joint_bindings,
                    key=lambda binding: binding.physical_joint_id,
                )
            )
            object.__setattr__(self, "physical_revolute_joint_bindings", ordered_joints)
            for binding in ordered_joints:
                if binding.parent_physical_body_id not in body_ids or binding.child_physical_body_id not in body_ids:
                    raise ValueError("physical revolute joint body is missing")
                if binding.parent_physical_body_id == binding.child_physical_body_id:
                    raise ValueError("physical revolute joint endpoints must use different bodies")
                for instance_id, interface_id in (
                    (binding.parent_physical_instance_id, binding.parent_interface_id),
                    (binding.child_physical_instance_id, binding.child_interface_id),
                ):
                    component = component_ids.get(instance_id)
                    if component is None or interface_id not in component.interfaces:
                        raise ValueError("physical revolute joint endpoint is missing")
                if binding.axis_source.source_physical_instance_id not in component_ids:
                    raise ValueError("physical revolute joint axis source instance is missing")
                if binding.connection_id not in connection_ids:
                    raise ValueError("physical revolute joint connection is missing")

            pair_keys = tuple(
                (
                    binding.first_physical_instance_id,
                    binding.second_physical_instance_id,
                )
                for binding in self.physical_pair_classification_bindings
            )
            if len(set(pair_keys)) != len(pair_keys):
                raise ValueError("physical pair classification bindings must contain unique pairs")
            ordered_pairs = tuple(
                sorted(
                    self.physical_pair_classification_bindings,
                    key=lambda binding: (
                        binding.first_physical_instance_id,
                        binding.second_physical_instance_id,
                    ),
                )
            )
            object.__setattr__(self, "physical_pair_classification_bindings", ordered_pairs)
            if any(
                instance_id not in component_ids
                for binding in ordered_pairs
                for instance_id in (
                    binding.first_physical_instance_id,
                    binding.second_physical_instance_id,
                )
            ):
                raise ValueError("physical pair classification instance is missing")

        expected = (
            _hash(self, "realization_hash")
            if self.schema_version == "physical-mechanism-realization@1"
            else _hash_payload(self._realization_payload(include_hash=False))
        )
        if self.realization_hash == "pending":
            object.__setattr__(self, "realization_hash", expected)
        elif self.realization_hash != expected:
            raise ValueError("physical mechanism realization hash mismatch")
        return self


class UnresolvedCandidateReason(StrEnum):
    REQUIRED_AUTHORITY_MISSING = "required_authority_missing"
    PROPERTY_UNAVAILABLE = "property_unavailable"
    JOINT_REALIZATION_INCOMPLETE = "joint_realization_incomplete"
    GEOMETRY_UNAVAILABLE = "geometry_unavailable"
    UNSUPPORTED_SCOPE = "unsupported_scope"


class UnresolvedCandidateItem(CandidateModel):
    subject_path: str
    required_information: str = Field(min_length=1)
    reason: UnresolvedCandidateReason
    source_context: str | None = None

    _validate_subject_path = field_validator("subject_path")(_require_path)


class CandidateSynthesisRequest(CandidateModel):
    schema_version: Literal[
        "candidate-synthesis-request@1",
        "candidate-synthesis-request@2",
    ] = "candidate-synthesis-request@1"
    source_binding: CandidateSourceBinding
    semantic_source_binding_hash: str = "pending"
    requested_joint_ids: tuple[str, ...] = ()
    required_joint_ids: tuple[str, ...] = ()
    out_of_scope_joint_ids: tuple[str, ...] = ()
    requested_evaluation_categories: tuple[str, ...] = ()
    request_hash: str = "pending"

    @field_validator("semantic_source_binding_hash")
    @classmethod
    def validate_semantic_source_binding_hash(cls, value: str) -> str:
        return value if value == "pending" else _require_hash(value)

    @model_validator(mode="before")
    @classmethod
    def reject_legacy_semantic_field(cls, value):
        if isinstance(value, dict) and value.get("schema_version", "candidate-synthesis-request@1") == "candidate-synthesis-request@1":
            if "semantic_source_binding_hash" in value:
                raise ValueError("candidate-synthesis-request@1 cannot contain semantic binding")
        return value

    @model_serializer(mode="wrap")
    def serialize_request(self, handler):
        del handler
        payload = {
            "schema_version": self.schema_version,
            "source_binding": self.source_binding.model_dump(mode="json"),
            "requested_joint_ids": list(self.requested_joint_ids),
            "required_joint_ids": list(self.required_joint_ids),
            "out_of_scope_joint_ids": list(self.out_of_scope_joint_ids),
            "requested_evaluation_categories": list(self.requested_evaluation_categories),
            "request_hash": self.request_hash,
        }
        if self.schema_version == "candidate-synthesis-request@2":
            payload["semantic_source_binding_hash"] = self.semantic_source_binding_hash
        return payload

    @model_validator(mode="after")
    def validate_scope_and_hash(self):
        requested = set(self.requested_joint_ids)
        required = set(self.required_joint_ids)
        out_of_scope = set(self.out_of_scope_joint_ids)
        if len(requested) != len(self.requested_joint_ids) or not required <= requested or out_of_scope & required or not out_of_scope <= requested:
            raise ValueError("candidate synthesis joint scope is invalid")
        if self.schema_version == "candidate-synthesis-request@2" and self.semantic_source_binding_hash == "pending":
            if self.request_hash != "pending":
                raise ValueError("unbound candidate-synthesis-request@2 cannot have a request hash")
        else:
            expected = (
                candidate_synthesis_request_hash_v2(self)
                if self.schema_version == "candidate-synthesis-request@2"
                else _hash(self, "request_hash")
            )
            if self.request_hash == "pending":
                object.__setattr__(self, "request_hash", expected)
            elif self.request_hash != expected:
                raise ValueError("candidate synthesis request hash mismatch")
        return self


def candidate_synthesis_request_hash_v2(request: CandidateSynthesisRequest) -> str:
    if request.schema_version != "candidate-synthesis-request@2":
        raise ValueError("candidate_synthesis_request_hash_v2 requires request@2")
    if request.semantic_source_binding_hash == "pending":
        raise ValueError("candidate synthesis semantic source binding is pending")
    return _hash_payload(
        {
            "schema_version": request.schema_version,
            "semantic_source_binding_hash": request.semantic_source_binding_hash,
            "requested_joint_ids": list(request.requested_joint_ids),
            "required_joint_ids": list(request.required_joint_ids),
            "out_of_scope_joint_ids": list(request.out_of_scope_joint_ids),
            "requested_evaluation_categories": list(request.requested_evaluation_categories),
        }
    )


class PolicyEntrySemantics(StrEnum):
    HARD_ADMISSIBILITY = "hard_admissibility"
    PREFERENCE = "preference"
    EXECUTION_LIMIT = "execution_limit"


class CandidateSynthesisPolicy(CandidateModel):
    schema_version: Literal["candidate-synthesis-policy@1"] = "candidate-synthesis-policy@1"
    entries: tuple[tuple[str, str, PolicyEntrySemantics], ...] = ()
    policy_hash: str = "pending"

    @model_validator(mode="after")
    def validate_entries_and_hash(self):
        keys = tuple(entry[0] for entry in self.entries)
        if len(set(keys)) != len(keys) or any(not key.strip() or not value.strip() for key, value, _ in self.entries):
            raise ValueError("candidate synthesis policy entries are invalid")
        expected = _hash(self, "policy_hash")
        if self.policy_hash == "pending":
            object.__setattr__(self, "policy_hash", expected)
        elif self.policy_hash != expected:
            raise ValueError("candidate synthesis policy hash mismatch")
        return self


class CandidateDesignVariable(CandidateModel):
    """A candidate-local choice, never a replacement for canonical authority."""

    name: str = Field(min_length=1)
    value: str | float | int | bool
    canonical_path: str | None = None

    @field_validator("canonical_path")
    @classmethod
    def validate_canonical_path(cls, value: str | None) -> str | None:
        return None if value is None else _require_path(value)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("candidate design variable values must be finite")
        if isinstance(value, str) and not value.strip():
            raise ValueError("candidate design variable values must not be empty")
        return value


_LEGACY_PLATE_COMPONENT_TYPES = frozenset({"fixture", "mount", "support-mount", "driven-body"})
_SCOPED_DIMENSION_SPELLINGS = (
    "{instance}.{dimension}",
    "{instance}.geometry.{dimension}",
    "geometry.{instance}.{dimension}",
)


def _candidate_dimension_inputs(
    specification: ComponentSpecificationSnapshot,
    physical_instance_id: str,
    design_variables: tuple[CandidateDesignVariable, ...],
) -> tuple[DimensionInput, ...]:
    inputs = []
    for property in specification.properties:
        semantic_name = next(
            (
                semantic_name
                for semantic_name, aliases in LEGACY_PLATE_DIMENSION_ALIASES.items()
                if property.key in aliases
            ),
            None,
        )
        if (
            semantic_name is not None
            and property.availability is ComponentPropertyAvailability.AVAILABLE
            and property.normalized_value is not None
            and property.canonical_unit == "mm"
        ):
            inputs.append(
                DimensionInput(
                    component_instance_id=physical_instance_id,
                    semantic_name=semantic_name,
                    alias=property.key,
                    value=property.normalized_value,
                    unit="mm",
                    identity=property.property_hash,
                )
            )

    scoped_names = {
        spelling.format(instance=physical_instance_id, dimension=dimension): dimension
        for dimension in LEGACY_PLATE_DIMENSION_ALIASES
        for spelling in _SCOPED_DIMENSION_SPELLINGS
    }
    for variable in design_variables:
        semantic_name = scoped_names.get(variable.name)
        if semantic_name is None:
            continue
        if isinstance(variable.value, bool) or not isinstance(variable.value, Real):
            raise ValueError("dimension value must be a real number")
        inputs.append(
            DimensionInput(
                component_instance_id=physical_instance_id,
                semantic_name=semantic_name,
                alias=semantic_name,
                value=variable.value,
                unit="mm",
                identity=f"candidate:design-variable:{variable.name}",
            )
        )
    return tuple(inputs)


class MechanicalDesignCandidate(CandidateModel):
    schema_version: Literal[
        "mechanical-design-candidate@1",
        "mechanical-design-candidate@2",
    ] = "mechanical-design-candidate@1"
    source_binding: CandidateSourceBinding
    semantic_source_binding_hash: str = "pending"
    synthesis_request_hash: str
    synthesis_policy_hash: str
    component_specifications: tuple[ComponentSpecificationSnapshot, ...] = Field(min_length=1)
    realization: PhysicalMechanismRealization
    design_variables: tuple[CandidateDesignVariable, ...] = ()
    unresolved_items: tuple[UnresolvedCandidateItem, ...] = ()
    generator_identity: str = Field(min_length=1)
    generator_version: str = Field(min_length=1)
    parent_candidate_hash: str | None = None
    derivation_kind: str | None = None
    generation_ordinal: int | None = Field(default=None, ge=0)
    candidate_hash: str = "pending"

    _validate_request_hash = field_validator("synthesis_request_hash", "synthesis_policy_hash")(_require_hash)
    _validate_semantic_source_binding_hash = field_validator("semantic_source_binding_hash")(
        lambda value: value if value == "pending" else _require_hash(value)
    )
    @field_validator("parent_candidate_hash")
    @classmethod
    def validate_parent_hash(cls, value: str | None) -> str | None:
        return None if value is None else _require_hash(value)

    @model_serializer(mode="wrap")
    def serialize_candidate(self, handler):
        payload = handler(self)
        if self.schema_version == "mechanical-design-candidate@1":
            payload.pop("semantic_source_binding_hash", None)
        return payload

    @model_validator(mode="after")
    def validate_candidate(self):
        if self.schema_version == "mechanical-design-candidate@2":
            if any(
                specification.schema_version != "component-specification@4"
                for specification in self.component_specifications
            ):
                raise ValueError("mechanical-design-candidate@2 requires component-specification@4")
        else:
            if self.semantic_source_binding_hash != "pending":
                raise ValueError("mechanical-design-candidate@1 cannot contain semantic binding")
            if any(
                specification.schema_version == "component-specification@4"
                for specification in self.component_specifications
            ):
                raise ValueError("mechanical-design-candidate@1 cannot contain component-specification@4")
        specifications = {specification.specification_hash for specification in self.component_specifications}
        if len(specifications) != len(self.component_specifications):
            raise ValueError("component specification hashes must be unique")
        if any(component.specification_hash not in specifications for component in self.realization.components):
            raise ValueError("physical component references a missing specification")
        if any(variable.canonical_path is not None for variable in self.design_variables):
            raise ValueError("candidate design variables cannot override canonical authority")
        names = tuple(variable.name for variable in self.design_variables)
        if len(set(names)) != len(names):
            raise ValueError("candidate design variable names must be unique")
        specifications_by_hash = {
            specification.specification_hash: specification
            for specification in self.component_specifications
        }
        for component in self.realization.components:
            specification = specifications_by_hash[component.specification_hash]
            if (
                specification.generated_part is not None
                or specification.geometry_source is not None
                or specification.component_type not in _LEGACY_PLATE_COMPONENT_TYPES
            ):
                continue
            inputs = _candidate_dimension_inputs(
                specification,
                component.instance_id,
                self.design_variables,
            )
            if not inputs:
                continue
            try:
                resolve_dimensions(
                    inputs,
                    required_dimensions=tuple(LEGACY_PLATE_DIMENSION_ALIASES),
                )
            except DimensionResolutionError as exc:
                raise ValueError(str(exc)) from exc
        if (self.parent_candidate_hash is None) != (self.derivation_kind is None):
            raise ValueError("candidate lineage must include parent hash and derivation kind together")
        if self.schema_version == "mechanical-design-candidate@2":
            if self.semantic_source_binding_hash == "pending" or any(
                specification.specification_hash == "pending"
                for specification in self.component_specifications
            ):
                if self.candidate_hash != "pending":
                    raise ValueError("unbound mechanical-design-candidate@2 cannot have a candidate hash")
            else:
                expected = candidate_hash_v2(self)
                if self.candidate_hash == "pending":
                    object.__setattr__(self, "candidate_hash", expected)
                elif self.candidate_hash != expected:
                    raise ValueError("mechanical design candidate hash mismatch")
        else:
            expected = candidate_hash(self)
            if self.candidate_hash == "pending":
                object.__setattr__(self, "candidate_hash", expected)
            elif self.candidate_hash != expected:
                raise ValueError("mechanical design candidate hash mismatch")
        return self


def candidate_hash(candidate: MechanicalDesignCandidate) -> str:
    return _hash(candidate, "candidate_hash")


def candidate_hash_v2(candidate: MechanicalDesignCandidate) -> str:
    if candidate.schema_version != "mechanical-design-candidate@2":
        raise ValueError("candidate_hash_v2 requires mechanical-design-candidate@2")
    if candidate.semantic_source_binding_hash == "pending":
        raise ValueError("candidate semantic source binding is pending")
    for specification in candidate.component_specifications:
        if specification.schema_version != "component-specification@4":
            raise ValueError("candidate@2 requires component-specification@4")
        if specification.specification_hash == "pending":
            raise ValueError("candidate component specification hash is pending")
        geometry_source = specification.geometry_source
        if geometry_source is not None and (
            geometry_source.content_identity in (None, "pending")
            or geometry_source.content_identity_algorithm != "step-content-identity@1"
            or geometry_source.semantic_reference_hash in (None, "pending")
        ):
            raise ValueError("candidate component specification semantic geometry is pending")
    specification_hashes = tuple(
        specification.specification_hash for specification in candidate.component_specifications
    )
    if len(set(specification_hashes)) != len(specification_hashes):
        raise ValueError("candidate component specification hashes must be unique")
    unresolved_records = tuple(candidate.unresolved_items)
    for item in unresolved_records:
        _require_projection_model_fields(
            item,
            {"subject_path", "required_information", "reason", "source_context"},
            "UnresolvedCandidateItem",
        )
    return _hash_payload(
        {
            "schema_version": candidate.schema_version,
            "semantic_source_binding_hash": candidate.semantic_source_binding_hash,
            "synthesis_request_hash": candidate.synthesis_request_hash,
            "synthesis_policy_hash": candidate.synthesis_policy_hash,
            "component_specifications": [
                specification_hash
                for specification_hash in sorted(specification_hashes)
            ],
            "realization": semantic_candidate_realization_payload(candidate.realization),
            "design_variables": semantic_candidate_design_variable_records(
                candidate.design_variables
            ),
            "unresolved_items": [
                item.model_dump(mode="json")
                for item in sorted(
                    unresolved_records,
                    key=lambda item: (
                        item.subject_path,
                        item.required_information,
                        item.reason.value,
                        (0, "") if item.source_context is None else (1, item.source_context),
                    ),
                )
            ],
            "generator_identity": candidate.generator_identity,
            "generator_version": candidate.generator_version,
            "parent_candidate_hash": candidate.parent_candidate_hash,
            "derivation_kind": candidate.derivation_kind,
            "generation_ordinal": candidate.generation_ordinal,
        }
    )


def _require_projection_model_fields(
    value: Model, expected_fields: set[str], model_name: str
) -> dict[str, Any]:
    if type(value).model_fields.keys() != expected_fields:
        raise ValueError(f"{model_name} declared fields differ from the semantic projection")
    payload = value.model_dump(mode="json")
    if payload.keys() != expected_fields:
        raise ValueError(f"{model_name} serialized fields differ from the semantic projection")
    return payload


def semantic_candidate_design_variable_records(
    variables: tuple[CandidateDesignVariable, ...],
) -> list[dict[str, Any]]:
    """Return the complete candidate design-variable records in semantic name order."""
    records = tuple(variables)
    names = tuple(variable.name for variable in records)
    if len(set(names)) != len(names):
        raise ValueError("candidate design variable names must be unique")
    payloads = []
    for variable in records:
        payloads.append(
            _require_projection_model_fields(
                variable,
                {"name", "value", "canonical_path"},
                "CandidateDesignVariable",
            )
        )
    return [record for _, record in sorted(zip(names, payloads, strict=True))]


def semantic_candidate_axis_source_payload(source: PhysicalAxisSource) -> dict[str, str]:
    """Project a candidate axis source without consuming raw M13 references or hashes."""
    source_fields = {
        SuppliedRotationalInterfaceAxisSource: {
            "schema_version", "source_kind", "source_physical_instance_id",
            "interface_id", "interface_hash", "geometry_reference_hash",
            "specification_hash", "source_hash",
        },
        SuppliedReferenceFrameAxisSource: {
            "schema_version", "source_kind", "source_physical_instance_id",
            "frame_id", "frame_hash", "geometry_reference_hash",
            "specification_hash", "source_hash",
        },
        GeneratedRotationalInterfaceAxisSource: {
            "schema_version", "source_kind", "source_physical_instance_id",
            "interface_id", "interface_hash", "generated_specification_hash",
            "source_hash",
        },
        GeneratedReferenceFrameAxisSource: {
            "schema_version", "source_kind", "source_physical_instance_id",
            "frame_id", "frame_hash", "generated_specification_hash", "source_hash",
        },
    }
    expected_fields = source_fields.get(type(source))
    if expected_fields is None:
        raise TypeError("candidate axis source has an unsupported semantic type")
    payload = _require_projection_model_fields(
        source, expected_fields, type(source).__name__
    )
    projected = {
        "schema_version": payload["schema_version"],
        "source_kind": payload["source_kind"],
        "source_physical_instance_id": payload["source_physical_instance_id"],
    }
    if "interface_id" in payload:
        projected["interface_id"] = payload["interface_id"]
    else:
        projected["frame_id"] = payload["frame_id"]
    projected["specification_hash"] = payload.get(
        "specification_hash", payload.get("generated_specification_hash")
    )
    return projected


def semantic_candidate_realization_payload(
    realization: PhysicalMechanismRealization,
) -> dict[str, Any]:
    """Project candidate realization@1/@2 into its canonical semantic payload."""
    if type(realization) is not PhysicalMechanismRealization:
        raise TypeError("candidate realization projection requires PhysicalMechanismRealization")
    if realization.schema_version not in {
        "physical-mechanism-realization@1",
        "physical-mechanism-realization@2",
    }:
        raise ValueError("unsupported physical mechanism realization schema")
    declared_fields = {
        "schema_version", "components", "connections", "joint_bindings",
        "physical_rigid_body_bindings", "physical_revolute_joint_bindings",
        "kinematic_root_physical_body_id", "kinematic_root_binding_hash",
        "physical_pair_classification_bindings", "realization_hash",
    }
    if PhysicalMechanismRealization.model_fields.keys() != declared_fields:
        raise ValueError("PhysicalMechanismRealization declared fields differ from the semantic projection")

    expected_serialized_fields = {
        "schema_version", "components", "connections", "joint_bindings", "realization_hash"
    }
    if realization.schema_version == "physical-mechanism-realization@2":
        expected_serialized_fields.update(
            {
                "physical_rigid_body_bindings", "physical_revolute_joint_bindings",
                "kinematic_root_physical_body_id", "kinematic_root_binding_hash",
                "physical_pair_classification_bindings",
            }
        )
    serialized = realization.model_dump(mode="json")
    if serialized.keys() != expected_serialized_fields:
        raise ValueError("PhysicalMechanismRealization serialized fields differ from its schema")

    component_fields = {"instance_id", "specification_hash", "role", "interfaces"}
    components = []
    component_ids = []
    for component in realization.components:
        item = _require_projection_model_fields(
            component, component_fields, "PhysicalComponentInstance"
        )
        interfaces = tuple(item["interfaces"])
        if len(set(interfaces)) != len(interfaces):
            raise ValueError("physical component interface IDs must be unique")
        item["interfaces"] = sorted(interfaces)
        components.append(item)
        component_ids.append(item["instance_id"])
    if len(set(component_ids)) != len(component_ids):
        raise ValueError("physical component IDs must be unique")
    components.sort(key=lambda item: item["instance_id"])

    connection_fields = {
        "connection_id", "kind", "from_instance_id", "from_interface_id",
        "to_instance_id", "to_interface_id", "meanings",
    }
    connections = []
    connection_ids = []
    for connection in realization.connections:
        item = _require_projection_model_fields(
            connection, connection_fields, "MechanicalConnection"
        )
        meanings = tuple(item["meanings"])
        if len(set(meanings)) != len(meanings):
            raise ValueError("mechanical connection meanings must be unique")
        item["meanings"] = sorted(meanings)
        connections.append(item)
        connection_ids.append(item["connection_id"])
    if len(set(connection_ids)) != len(connection_ids):
        raise ValueError("mechanical connection IDs must be unique")
    connections.sort(key=lambda item: item["connection_id"])

    joint_fields = {
        "joint_id", "driven_instance_id", "realization_component_ids",
        "actuator_path_connection_ids", "transmission_path_connection_ids",
        "support_instance_ids", "hub_or_coupling_instance_id",
        "mount_or_support_instance_ids", "axis_frame_reference",
        "load_path_metadata_available",
    }
    set_semantic_joint_fields = (
        "realization_component_ids", "actuator_path_connection_ids",
        "transmission_path_connection_ids", "mount_or_support_instance_ids",
    )
    joint_bindings = []
    joint_ids = []
    for binding in realization.joint_bindings:
        item = _require_projection_model_fields(
            binding, joint_fields, "JointPhysicalRealizationBinding"
        )
        for field_name in set_semantic_joint_fields:
            values = tuple(item[field_name])
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must contain unique IDs")
            item[field_name] = sorted(values)
        support_ids = tuple(item["support_instance_ids"])
        if len(set(support_ids)) != len(support_ids):
            raise ValueError("support_instance_ids must contain unique IDs")
        joint_bindings.append(item)
        joint_ids.append(item["joint_id"])
    if len(set(joint_ids)) != len(joint_ids):
        raise ValueError("joint physical realization binding IDs must be unique")
    joint_bindings.sort(key=lambda item: item["joint_id"])

    payload: dict[str, Any] = {
        "schema_version": realization.schema_version,
        "components": components,
        "connections": connections,
        "joint_bindings": joint_bindings,
    }
    if realization.schema_version == "physical-mechanism-realization@2":
        body_fields = {
            "schema_version", "physical_body_id", "member_physical_instance_ids",
            "reference_physical_instance_id", "binding_hash",
        }
        bodies = []
        body_ids = []
        for binding in realization.physical_rigid_body_bindings:
            item = _require_projection_model_fields(
                binding, body_fields, "PhysicalRigidBodyBinding"
            )
            members = tuple(item["member_physical_instance_ids"])
            if len(set(members)) != len(members):
                raise ValueError("physical rigid body member IDs must be unique")
            item.pop("binding_hash")
            item["member_physical_instance_ids"] = sorted(members)
            bodies.append(item)
            body_ids.append(item["physical_body_id"])
        if len(set(body_ids)) != len(body_ids):
            raise ValueError("physical rigid body IDs must be unique")
        bodies.sort(key=lambda item: item["physical_body_id"])

        revolute_fields = {
            "schema_version", "physical_joint_id", "parent_physical_body_id",
            "child_physical_body_id", "connection_id", "parent_physical_instance_id",
            "parent_interface_id", "child_physical_instance_id", "child_interface_id",
            "axis_source", "axis_owner_endpoint", "axis_sign", "motion_mode",
            "min_angle_deg", "max_angle_deg", "zero_reference_semantics", "binding_hash",
        }
        revolute_joints = []
        physical_joint_ids = []
        for binding in realization.physical_revolute_joint_bindings:
            item = _require_projection_model_fields(
                binding, revolute_fields, "PhysicalRevoluteJointBinding"
            )
            item.pop("binding_hash")
            item["axis_source"] = semantic_candidate_axis_source_payload(binding.axis_source)
            revolute_joints.append(item)
            physical_joint_ids.append(item["physical_joint_id"])
        if len(set(physical_joint_ids)) != len(physical_joint_ids):
            raise ValueError("physical revolute joint IDs must be unique")
        revolute_joints.sort(key=lambda item: item["physical_joint_id"])

        pair_fields = {
            "schema_version", "first_physical_instance_id", "second_physical_instance_id",
            "classification", "exclusion_reason", "binding_hash",
        }
        pairs = []
        pair_keys = []
        for binding in realization.physical_pair_classification_bindings:
            item = _require_projection_model_fields(
                binding, pair_fields, "PhysicalPairClassificationBinding"
            )
            item.pop("binding_hash")
            key = (item["first_physical_instance_id"], item["second_physical_instance_id"])
            pair_keys.append(key)
            pairs.append(item)
        if len(set(pair_keys)) != len(pair_keys):
            raise ValueError("physical pair classification bindings must contain unique pairs")
        pairs.sort(key=lambda item: (
            item["first_physical_instance_id"], item["second_physical_instance_id"]
        ))
        payload.update(
            {
                "physical_rigid_body_bindings": bodies,
                "physical_revolute_joint_bindings": revolute_joints,
                "kinematic_root_physical_body_id": realization.kinematic_root_physical_body_id,
                "kinematic_root_binding_hash": realization.kinematic_root_binding_hash,
                "physical_pair_classification_bindings": pairs,
            }
        )
    return payload


def semantic_candidate_mechanism_hash(
    realization: PhysicalMechanismRealization,
) -> str:
    """Return the restart-recomputable semantic identity for candidate realization@2."""
    if type(realization) is not PhysicalMechanismRealization:
        raise TypeError("candidate mechanism identity requires PhysicalMechanismRealization")
    if realization.schema_version != "physical-mechanism-realization@2":
        raise ValueError("semantic_candidate_mechanism_hash requires realization@2")
    validated = PhysicalMechanismRealization.model_validate(
        realization.model_dump(mode="json")
    )
    return _hash_payload(
        {
            "mechanism_contract": "candidate-mechanism-semantic@1",
            "realization_semantics": semantic_candidate_realization_payload(validated),
        }
    )
