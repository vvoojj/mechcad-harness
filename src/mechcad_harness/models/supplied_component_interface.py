from __future__ import annotations

import hashlib
import math
import re
from enum import StrEnum
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from .common import Model
from .component_property import ComponentPropertyAuthority, ComponentPropertyAvailability
from .geometry_identity import (
    GeometryArtifactIdentity,
    geometry_identity_hash,
    geometry_reference_hash as _geometry_reference_hash,
)
from .quaternion import (
    normalize_direction,
    normalize_quaternion,
    quaternion_compose,
    rotate_vector,
)


class SuppliedInterfaceEvidenceShape(StrEnum):
    SCALAR = "scalar"
    VECTOR3 = "vector3"
    QUATERNION = "quaternion"
    TEXT = "text"


class SuppliedInterfaceEvidenceOrigin(StrEnum):
    SOURCE_DOCUMENT = "source_document"
    GEOMETRY_INFERRED = "geometry_inferred"
    HUMAN_CONFIRMED_INTERPRETATION = "human_confirmed_interpretation"
    DERIVED_MATERIALIZATION = "derived_materialization"


class SuppliedInterfaceTransformRole(StrEnum):
    POINT_MM = "point_mm"
    LENGTH_MM = "length_mm"
    DISPLACEMENT_MM = "displacement_mm"
    DIRECTION_UNIT = "direction_unit"
    ORIENTATION = "orientation"
    TEXT = "text"


def _nonblank(value: str | None) -> str | None:
    if value is not None and not value.strip():
        raise ValueError("must not be empty or whitespace")
    return value


def _require_hash(value: str) -> str:
    if not value.startswith("sha256:") or len(value) != 71:
        raise ValueError("must be a sha256 hash")
    if any(character not in "0123456789abcdef" for character in value[7:]):
        raise ValueError("must be a sha256 hash")
    return value


def _hash_or_pending(value: str) -> str:
    if value == "pending":
        return value
    return _require_hash(value)


def _self_hash(model: Model, hash_field: str) -> str:
    from mechcad_harness.state.hashing import canonical_json

    payload = model.model_dump(mode="json")
    payload.pop(hash_field, None)
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def _shape_value_is_valid(
    shape: SuppliedInterfaceEvidenceShape, value: Any
) -> bool:
    if shape is SuppliedInterfaceEvidenceShape.SCALAR:
        return isinstance(value, float) and math.isfinite(value)
    if shape is SuppliedInterfaceEvidenceShape.VECTOR3:
        return (
            isinstance(value, tuple)
            and len(value) == 3
            and all(isinstance(component, float) and math.isfinite(component) for component in value)
        )
    if shape is SuppliedInterfaceEvidenceShape.QUATERNION:
        return (
            isinstance(value, tuple)
            and len(value) == 4
            and all(isinstance(component, float) and math.isfinite(component) for component in value)
        )
    return isinstance(value, str) and bool(value.strip())


def _validate_confirmation_geometry_bindings(
    records: dict[str, SuppliedInterfaceEvidence],
) -> None:
    def inferred_basis(
        evidence_id: str, visiting: set[str]
    ) -> tuple[SuppliedInterfaceEvidence, ...]:
        if evidence_id in visiting:
            raise ValueError("confirmation basis graph must be acyclic")
        record = records[evidence_id]
        if record.evidence_origin is SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED:
            return (record,)
        if record.evidence_origin is not SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION:
            return ()
        visiting.add(evidence_id)
        result = tuple(
            inferred
            for basis_id in record.basis_evidence_ids
            for inferred in inferred_basis(basis_id, visiting)
        )
        visiting.remove(evidence_id)
        return result

    for record in records.values():
        if record.evidence_origin is not SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION:
            continue
        geometry_inferred_basis = inferred_basis(record.evidence_id, set())
        if not geometry_inferred_basis:
            continue
        geometry_hashes = {
            evidence.geometry_reference_hash for evidence in geometry_inferred_basis
        }
        if (
            len(geometry_hashes) != 1
            or None in geometry_hashes
            or record.geometry_reference_hash != next(iter(geometry_hashes))
        ):
            raise ValueError(
                "human-confirmed interpretation geometry reference must match "
                "its geometry-inferred basis"
            )


class SuppliedInterfaceEvidence(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str = Field(min_length=1)
    shape: SuppliedInterfaceEvidenceShape
    value: float | tuple[float, float, float] | tuple[float, float, float, float] | str | None = None
    canonical_unit: str | None = None
    availability: ComponentPropertyAvailability
    authority: ComponentPropertyAuthority
    source_identity: str = Field(min_length=1)
    applicability_context: str | None = None
    conversion_provenance: str | None = None
    evidence_origin: SuppliedInterfaceEvidenceOrigin
    source_document_identity: str | None = None
    geometry_reference_hash: str | None = None
    basis_evidence_ids: tuple[str, ...] = ()
    evidence_hash: str = "pending"

    _validate_text = field_validator(
        "evidence_id",
        "source_identity",
        "canonical_unit",
        "applicability_context",
        "conversion_provenance",
        "source_document_identity",
        "geometry_reference_hash",
    )(_nonblank)
    _validate_hash = field_validator("evidence_hash")(_hash_or_pending)

    @field_validator("geometry_reference_hash")
    @classmethod
    def validate_geometry_hash(cls, value: str | None) -> str | None:
        return None if value is None else _require_hash(value)

    @field_validator("basis_evidence_ids")
    @classmethod
    def validate_basis_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("basis evidence IDs must not be empty")
        if len(set(values)) != len(values):
            raise ValueError("basis evidence IDs must be unique")
        return values

    @model_validator(mode="before")
    @classmethod
    def reject_boolean_numeric_values(cls, data: Any) -> Any:
        values = dict(data)
        shape = values.get("shape")
        value = values.get("value")
        if shape in (SuppliedInterfaceEvidenceShape.SCALAR, "scalar") and isinstance(value, bool):
            raise ValueError("numeric evidence values must not be boolean")
        if shape in (
            SuppliedInterfaceEvidenceShape.VECTOR3,
            SuppliedInterfaceEvidenceShape.QUATERNION,
            "vector3",
            "quaternion",
        ) and isinstance(value, (tuple, list)) and any(isinstance(component, bool) for component in value):
            raise ValueError("numeric evidence values must not be boolean")
        return data

    @model_validator(mode="after")
    def validate_evidence(self) -> "SuppliedInterfaceEvidence":
        if (
            self.evidence_origin is SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION
            and not self.basis_evidence_ids
        ):
            raise ValueError(
                "human-confirmed interpretation evidence requires basis evidence"
            )
        if (
            self.evidence_origin is SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED
            and self.geometry_reference_hash is None
        ):
            raise ValueError(
                "geometry-inferred evidence requires a geometry reference hash"
            )
        if self.shape is SuppliedInterfaceEvidenceShape.TEXT and self.canonical_unit is not None:
            raise ValueError("text evidence must not have a unit")
        if (
            self.shape in (
                SuppliedInterfaceEvidenceShape.SCALAR,
                SuppliedInterfaceEvidenceShape.VECTOR3,
                SuppliedInterfaceEvidenceShape.QUATERNION,
            )
            and self.canonical_unit is None
        ):
            raise ValueError("numeric evidence requires a canonical unit")
        if self.availability is ComponentPropertyAvailability.AVAILABLE:
            if self.value is None or not _shape_value_is_valid(self.shape, self.value):
                raise ValueError("available evidence value does not match its shape")
            if self.shape is SuppliedInterfaceEvidenceShape.QUATERNION:
                object.__setattr__(self, "value", normalize_quaternion(self.value))
        elif self.value is not None:
            raise ValueError("unavailable evidence must not contain a value")

        expected = _self_hash(self, "evidence_hash")
        if self.evidence_hash == "pending":
            object.__setattr__(self, "evidence_hash", expected)
        elif self.evidence_hash != expected:
            raise ValueError("supplied interface evidence hash mismatch")
        return self


class SuppliedInterfaceFact(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    fact_id: str = Field(min_length=1)
    expected_shape: SuppliedInterfaceEvidenceShape
    expected_unit: str | None
    transform_role: SuppliedInterfaceTransformRole
    evidence: tuple[SuppliedInterfaceEvidence, ...]
    accepted_evidence_id: str | None = None
    fact_hash: str = "pending"

    _validate_text = field_validator("fact_id", "expected_unit", "accepted_evidence_id")(_nonblank)
    _validate_hash = field_validator("fact_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_fact(self) -> "SuppliedInterfaceFact":
        evidence_ids = tuple(record.evidence_id for record in self.evidence)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("evidence IDs must be unique within a fact")
        ordered_evidence = tuple(sorted(self.evidence, key=lambda record: record.evidence_id))
        if self.transform_role is SuppliedInterfaceTransformRole.DIRECTION_UNIT:
            normalized_evidence = []
            for record in ordered_evidence:
                if record.availability is ComponentPropertyAvailability.AVAILABLE:
                    values = record.model_dump(mode="python")
                    values["value"] = normalize_direction(record.value)
                    values["evidence_hash"] = "pending"
                    record = SuppliedInterfaceEvidence.model_validate(values)
                normalized_evidence.append(record)
            ordered_evidence = tuple(normalized_evidence)
        object.__setattr__(self, "evidence", ordered_evidence)

        if self.expected_shape is SuppliedInterfaceEvidenceShape.TEXT:
            if self.expected_unit is not None:
                raise ValueError("text facts must not have a unit")
        elif self.expected_unit is None:
            raise ValueError("numeric facts require a canonical unit")

        for record in self.evidence:
            if record.shape is not self.expected_shape:
                raise ValueError("evidence shape does not match fact shape")
            if record.canonical_unit != self.expected_unit:
                raise ValueError("evidence unit does not match fact unit")

        expected_shape, expected_unit = {
            SuppliedInterfaceTransformRole.POINT_MM: (
                SuppliedInterfaceEvidenceShape.VECTOR3,
                "mm",
            ),
            SuppliedInterfaceTransformRole.LENGTH_MM: (
                SuppliedInterfaceEvidenceShape.SCALAR,
                "mm",
            ),
            SuppliedInterfaceTransformRole.DISPLACEMENT_MM: (
                SuppliedInterfaceEvidenceShape.VECTOR3,
                "mm",
            ),
            SuppliedInterfaceTransformRole.DIRECTION_UNIT: (
                SuppliedInterfaceEvidenceShape.VECTOR3,
                "1",
            ),
            SuppliedInterfaceTransformRole.ORIENTATION: (
                SuppliedInterfaceEvidenceShape.QUATERNION,
                "1",
            ),
            SuppliedInterfaceTransformRole.TEXT: (
                SuppliedInterfaceEvidenceShape.TEXT,
                None,
            ),
        }[self.transform_role]
        if (self.expected_shape, self.expected_unit) != (expected_shape, expected_unit):
            raise ValueError("fact shape and unit do not match its transform role")

        records = {record.evidence_id: record for record in self.evidence}
        for record in self.evidence:
            if record.evidence_origin is SuppliedInterfaceEvidenceOrigin.DERIVED_MATERIALIZATION:
                continue
            if any(basis_id not in records for basis_id in record.basis_evidence_ids):
                raise ValueError("confirmation basis evidence is not fact-local")
        _validate_confirmation_geometry_bindings(records)

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(evidence_id: str) -> None:
            if evidence_id in visiting:
                raise ValueError("confirmation basis graph must be acyclic")
            if evidence_id in visited:
                return
            visiting.add(evidence_id)
            record = records[evidence_id]
            if record.evidence_origin is not SuppliedInterfaceEvidenceOrigin.DERIVED_MATERIALIZATION:
                for basis_id in record.basis_evidence_ids:
                    visit(basis_id)
            visiting.remove(evidence_id)
            visited.add(evidence_id)

        for evidence_id in records:
            visit(evidence_id)

        if self.accepted_evidence_id is not None:
            accepted = records.get(self.accepted_evidence_id)
            if accepted is None:
                raise ValueError("accepted evidence ID is not present in the fact")
            if accepted.availability is not ComponentPropertyAvailability.AVAILABLE:
                raise ValueError("accepted evidence must be available")
            if accepted.evidence_origin is SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED:
                raise ValueError("inferred evidence cannot be accepted")

        expected = _self_hash(self, "fact_hash")
        if self.fact_hash == "pending":
            object.__setattr__(self, "fact_hash", expected)
        elif self.fact_hash != expected:
            raise ValueError("supplied interface fact hash mismatch")
        return self


def _require_fact_role(
    fact: SuppliedInterfaceFact,
    role: SuppliedInterfaceTransformRole,
    field_name: str,
) -> None:
    if fact.transform_role is not role:
        raise ValueError(f"{field_name} must have transform role {role.value}")


def _require_positive_available(fact: SuppliedInterfaceFact, field_name: str) -> None:
    for evidence in fact.evidence:
        if evidence.availability is ComponentPropertyAvailability.AVAILABLE:
            if not isinstance(evidence.value, float) or not math.isfinite(evidence.value):
                raise ValueError(f"{field_name} must be finite")
            if evidence.value <= 0.0:
                raise ValueError(f"{field_name} must be positive")


def _require_geometry_binding(
    geometry_reference_hash: str, geometry: GeometryArtifactIdentity
) -> None:
    _require_hash(geometry_reference_hash)
    if geometry_reference_hash != _geometry_reference_hash(geometry):
        raise ValueError("geometry reference hash does not match geometry identity projection")


def _interface_facts(
    interface: "RotationalShaftInterface | MountingFaceInterface",
) -> tuple[tuple[str, SuppliedInterfaceFact], ...]:
    if isinstance(interface, RotationalShaftInterface):
        facts: list[tuple[str, SuppliedInterfaceFact]] = [
            ("shaft axis point", interface.axis_point),
            ("shaft axis direction", interface.axis_direction),
            ("shaft nominal diameter", interface.nominal_shaft_diameter),
            ("shaft usable engagement length", interface.usable_axial_engagement_length),
        ]
        if interface.shoulder_reference_plane is not None:
            facts.extend((
                ("shaft shoulder point", interface.shoulder_reference_plane[0]),
                ("shaft shoulder normal", interface.shoulder_reference_plane[1]),
            ))
        if interface.d_flat_profile is not None:
            facts.extend((
                ("D-flat normal", interface.d_flat_profile.flat_normal_direction),
                ("D-flat across dimension", interface.d_flat_profile.flat_across_dimension),
                ("D-flat start", interface.d_flat_profile.start_from_shoulder),
                ("D-flat effective length", interface.d_flat_profile.effective_length),
            ))
        if interface.thread_designation is not None:
            facts.append(("shaft thread designation", interface.thread_designation))
        return tuple(facts)

    facts = [
        ("mount plane point", interface.plane_point),
        ("mount outward normal", interface.outward_normal),
    ]
    for hole in interface.holes:
        facts.extend((
            (f"hole {hole.hole_id} center", hole.center),
            (f"hole {hole.hole_id} axis", hole.axis),
            (f"hole {hole.hole_id} diameter", hole.nominal_diameter),
        ))
        if hole.thread_designation is not None:
            facts.append((f"hole {hole.hole_id} thread designation", hole.thread_designation))
    if interface.pilot_boss is not None:
        facts.extend((
            ("pilot point", interface.pilot_boss.point),
            ("pilot axis", interface.pilot_boss.axis),
            ("pilot diameter", interface.pilot_boss.diameter),
        ))
    return tuple(facts)


def _validate_fact_geometry_binding(
    fact: SuppliedInterfaceFact,
    geometry_reference_hashes: tuple[str, ...],
    fact_name: str,
) -> None:
    allowed = set(geometry_reference_hashes)
    for evidence in fact.evidence:
        if evidence.geometry_reference_hash is not None and evidence.geometry_reference_hash not in allowed:
            raise ValueError(f"{fact_name} evidence geometry reference does not match enclosing geometry")
        if (
            evidence.evidence_origin is SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED
            and evidence.geometry_reference_hash not in allowed
        ):
            raise ValueError(f"{fact_name} inferred evidence geometry reference does not match enclosing geometry")


def _reject_direct_derived_evidence(interface: "RotationalShaftInterface | MountingFaceInterface") -> None:
    for field_name, fact in _interface_facts(interface):
        if fact.accepted_evidence_id is None:
            continue
        selected = next(
            evidence for evidence in fact.evidence
            if evidence.evidence_id == fact.accepted_evidence_id
        )
        if selected.evidence_origin is SuppliedInterfaceEvidenceOrigin.DERIVED_MATERIALIZATION:
            raise ValueError(
                f"direct interface cannot select derived_materialization evidence for {field_name}"
            )


class SuppliedShaftProfileKind(StrEnum):
    ROUND = "round"
    D_FLAT = "d_flat"
    KEYWAY = "keyway"
    SPLINE = "spline"
    THREAD = "thread"
    OTHER = "other"


class SuppliedShaftDFlatProfile(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    flat_normal_direction: SuppliedInterfaceFact
    flat_across_dimension: SuppliedInterfaceFact
    start_from_shoulder: SuppliedInterfaceFact
    effective_length: SuppliedInterfaceFact

    @model_validator(mode="after")
    def validate_profile(self) -> "SuppliedShaftDFlatProfile":
        _require_fact_role(self.flat_normal_direction, SuppliedInterfaceTransformRole.DIRECTION_UNIT, "flat normal")
        for name, fact in (
            ("flat across dimension", self.flat_across_dimension),
            ("flat start from shoulder", self.start_from_shoulder),
            ("flat effective length", self.effective_length),
        ):
            _require_fact_role(fact, SuppliedInterfaceTransformRole.LENGTH_MM, name)
            _require_positive_available(fact, name)
        return self


class RotationalShaftInterface(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    interface_id: str
    geometry_reference_hash: str
    geometry: GeometryArtifactIdentity
    reference_frame_id: str | None = None
    axis_point: SuppliedInterfaceFact
    axis_direction: SuppliedInterfaceFact
    nominal_shaft_diameter: SuppliedInterfaceFact
    usable_axial_engagement_length: SuppliedInterfaceFact
    shoulder_reference_plane: tuple[SuppliedInterfaceFact, SuppliedInterfaceFact] | None = None
    shaft_profile: SuppliedShaftProfileKind | None = None
    d_flat_profile: SuppliedShaftDFlatProfile | None = None
    thread_designation: SuppliedInterfaceFact | None = None
    interface_hash: str = "pending"

    _validate_id = field_validator("interface_id", "reference_frame_id")(_nonblank)
    _validate_geometry_hash = field_validator("geometry_reference_hash")(_require_hash)
    _validate_hash = field_validator("interface_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_interface(self) -> "RotationalShaftInterface":
        _require_geometry_binding(self.geometry_reference_hash, self.geometry)
        _require_fact_role(self.axis_point, SuppliedInterfaceTransformRole.POINT_MM, "axis point")
        _require_fact_role(self.axis_direction, SuppliedInterfaceTransformRole.DIRECTION_UNIT, "axis direction")
        _require_fact_role(self.nominal_shaft_diameter, SuppliedInterfaceTransformRole.LENGTH_MM, "shaft diameter")
        _require_fact_role(self.usable_axial_engagement_length, SuppliedInterfaceTransformRole.LENGTH_MM, "shaft engagement")
        _require_positive_available(self.nominal_shaft_diameter, "shaft diameter")
        _require_positive_available(self.usable_axial_engagement_length, "shaft engagement")
        for field_name, fact in _interface_facts(self):
            _validate_fact_geometry_binding(fact, (self.geometry_reference_hash,), field_name)
        if self.shoulder_reference_plane is not None:
            _require_fact_role(self.shoulder_reference_plane[0], SuppliedInterfaceTransformRole.POINT_MM, "shoulder point")
            _require_fact_role(self.shoulder_reference_plane[1], SuppliedInterfaceTransformRole.DIRECTION_UNIT, "shoulder normal")
        if self.d_flat_profile is not None and self.shaft_profile is not SuppliedShaftProfileKind.D_FLAT:
            raise ValueError("D-flat profile requires a D_FLAT shaft profile")
        if self.thread_designation is not None:
            _require_fact_role(self.thread_designation, SuppliedInterfaceTransformRole.TEXT, "shaft thread designation")

        expected = _self_hash(self, "interface_hash")
        if self.interface_hash == "pending":
            object.__setattr__(self, "interface_hash", expected)
        elif self.interface_hash != expected:
            raise ValueError("rotational shaft interface hash mismatch")
        return self


class MountingHole(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    hole_id: str
    center: SuppliedInterfaceFact
    axis: SuppliedInterfaceFact
    nominal_diameter: SuppliedInterfaceFact
    thread_designation: SuppliedInterfaceFact | None = None

    _validate_id = field_validator("hole_id")(_nonblank)

    @model_validator(mode="after")
    def validate_hole(self) -> "MountingHole":
        _require_fact_role(self.center, SuppliedInterfaceTransformRole.POINT_MM, "hole center")
        _require_fact_role(self.axis, SuppliedInterfaceTransformRole.DIRECTION_UNIT, "hole axis")
        _require_fact_role(self.nominal_diameter, SuppliedInterfaceTransformRole.LENGTH_MM, "hole diameter")
        _require_positive_available(self.nominal_diameter, "hole diameter")
        if self.thread_designation is not None:
            _require_fact_role(self.thread_designation, SuppliedInterfaceTransformRole.TEXT, "hole thread designation")
        return self


class SuppliedPilotBossReference(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    point: SuppliedInterfaceFact
    axis: SuppliedInterfaceFact
    diameter: SuppliedInterfaceFact

    @model_validator(mode="after")
    def validate_pilot(self) -> "SuppliedPilotBossReference":
        _require_fact_role(self.point, SuppliedInterfaceTransformRole.POINT_MM, "pilot point")
        _require_fact_role(self.axis, SuppliedInterfaceTransformRole.DIRECTION_UNIT, "pilot axis")
        _require_fact_role(self.diameter, SuppliedInterfaceTransformRole.LENGTH_MM, "pilot diameter")
        _require_positive_available(self.diameter, "pilot diameter")
        return self


class MountingFaceInterface(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    interface_id: str
    geometry_reference_hash: str
    geometry: GeometryArtifactIdentity
    face_reference_id: str
    reference_frame_id: str
    plane_point: SuppliedInterfaceFact
    outward_normal: SuppliedInterfaceFact
    holes: tuple[MountingHole, ...] = ()
    pilot_boss: SuppliedPilotBossReference | None = None
    interface_hash: str = "pending"

    _validate_id = field_validator("interface_id", "face_reference_id", "reference_frame_id")(_nonblank)
    _validate_geometry_hash = field_validator("geometry_reference_hash")(_require_hash)
    _validate_hash = field_validator("interface_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_interface(self) -> "MountingFaceInterface":
        _require_geometry_binding(self.geometry_reference_hash, self.geometry)
        _require_fact_role(self.plane_point, SuppliedInterfaceTransformRole.POINT_MM, "plane point")
        _require_fact_role(self.outward_normal, SuppliedInterfaceTransformRole.DIRECTION_UNIT, "outward normal")
        for field_name, fact in _interface_facts(self):
            _validate_fact_geometry_binding(fact, (self.geometry_reference_hash,), field_name)
        hole_ids = tuple(hole.hole_id for hole in self.holes)
        if len(set(hole_ids)) != len(hole_ids):
            raise ValueError("mounting hole IDs must be unique")
        for index, hole in enumerate(self.holes):
            semantic_hole = hole.model_dump(mode="json")
            semantic_hole.pop("hole_id")
            for other in self.holes[index + 1:]:
                other_semantic_hole = other.model_dump(mode="json")
                other_semantic_hole.pop("hole_id")
                if semantic_hole == other_semantic_hole:
                    raise ValueError(
                        "distinct mounting hole IDs must not have identical complete semantics"
                    )
        object.__setattr__(self, "holes", tuple(sorted(self.holes, key=lambda hole: hole.hole_id)))

        expected = _self_hash(self, "interface_hash")
        if self.interface_hash == "pending":
            object.__setattr__(self, "interface_hash", expected)
        elif self.interface_hash != expected:
            raise ValueError("mounting face interface hash mismatch")
        return self


class SuppliedComponentInterfaceDefinition(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["direct", "materialized"] = "direct"
    interface_id: str
    geometry_reference_hash: str
    geometry: GeometryArtifactIdentity
    shaft: RotationalShaftInterface | None = None
    mounting_face: MountingFaceInterface | None = None
    derivation: "InterfaceDerivationProvenance | None" = None
    interface_hash: str = "pending"

    _validate_id = field_validator("interface_id")(_nonblank)
    _validate_geometry_hash = field_validator("geometry_reference_hash")(_require_hash)
    _validate_hash = field_validator("interface_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_definition(self) -> "SuppliedComponentInterfaceDefinition":
        variants = tuple(value for value in (self.shaft, self.mounting_face) if value is not None)
        if len(variants) != 1:
            raise ValueError("exactly one shaft or mounting face variant is required")
        variant = variants[0]
        if (
            variant.interface_id != self.interface_id
            or variant.geometry_reference_hash != self.geometry_reference_hash
            or variant.geometry.geometry_identity_hash != self.geometry.geometry_identity_hash
        ):
            raise ValueError("interface variant does not match definition binding")
        if self.kind == "direct":
            if self.derivation is not None:
                raise ValueError("direct interface must not have derivation provenance")
            _reject_direct_derived_evidence(variant)
        else:
            if self.derivation is None:
                raise ValueError("materialized interface requires complete derivation provenance")
            if (
                self.derivation.derived_geometry != self.geometry
                or self.derivation.derived_geometry_reference_hash != self.geometry_reference_hash
            ):
                raise ValueError("materialized interface geometry does not match derivation provenance")
            for field_name, fact in _interface_facts(variant):
                if fact.accepted_evidence_id is None:
                    raise ValueError(f"materialized interface {field_name} has no derived evidence")
                selected = next(
                    evidence for evidence in fact.evidence
                    if evidence.evidence_id == fact.accepted_evidence_id
                )
                if selected.evidence_origin is not SuppliedInterfaceEvidenceOrigin.DERIVED_MATERIALIZATION:
                    raise ValueError(f"materialized interface {field_name} is not derived")
        expected = _self_hash(self, "interface_hash")
        if self.interface_hash == "pending":
            object.__setattr__(self, "interface_hash", expected)
        elif self.interface_hash != expected:
            raise ValueError("supplied component interface definition hash mismatch")
        return self


def require_authoritatively_consumable_interface(
    definition: SuppliedComponentInterfaceDefinition,
    reference_frame: SuppliedComponentReferenceFrame | None = None,
) -> SuppliedComponentInterfaceDefinition:
    if definition.kind == "materialized":
        provenance = definition.derivation
        if provenance is None:
            raise ValueError("materialized interface requires complete derivation provenance")

        variant = definition.shaft if definition.shaft is not None else definition.mounting_face
        assert variant is not None
        prefix = "shaft" if definition.shaft is not None else "mounting_face"
        active_slots = dict(_variant_fact_slots(variant, prefix))
        for field_name, fact in active_slots.items():
            if fact.accepted_evidence_id is None:
                raise ValueError(f"materialized interface {field_name} has no derived evidence")
            selected = next(
                (
                    evidence
                    for evidence in fact.evidence
                    if evidence.evidence_id == fact.accepted_evidence_id
                ),
                None,
            )
            if selected is None:
                raise ValueError(f"materialized interface {field_name} selected evidence is missing")
            if selected.availability is not ComponentPropertyAvailability.AVAILABLE:
                raise ValueError(f"materialized interface {field_name} selected evidence is unavailable")
            if selected.evidence_origin is not SuppliedInterfaceEvidenceOrigin.DERIVED_MATERIALIZATION:
                raise ValueError(f"materialized interface {field_name} selected evidence is not derived")

        if not isinstance(provenance, InterfaceDerivationProvenance):
            raise ValueError("materialized interface requires complete derivation provenance")
        source = provenance.source_interface_snapshot
        if not isinstance(source, SuppliedComponentInterfaceDefinition) or source.kind != "direct":
            raise ValueError("materialized interface provenance requires a direct source snapshot")
        if source.interface_id != definition.interface_id:
            raise ValueError("materialized interface source interface identity does not match definition")
        if source.derivation is not None:
            raise ValueError("materialized interface source snapshot must not have derivation")
        if not provenance.fact_derivation_bindings:
            raise ValueError("materialized interface derivation bindings are required")

        source_frame = provenance.source_reference_frame_snapshot
        source_slots = dict(_fact_slots(source, source_frame))
        source_variant = source.shaft if source.shaft is not None else source.mounting_face
        assert source_variant is not None
        source_interface_slots = dict(
            _variant_fact_slots(source_variant, prefix)
        )
        for path, source_fact in source_slots.items():
            _validate_fact_geometry_binding(
                source_fact,
                (provenance.source_geometry_reference_hash,),
                path,
            )
        for path, active_fact in active_slots.items():
            _validate_fact_geometry_binding(
                active_fact,
                (provenance.derived_geometry_reference_hash,),
                path,
            )
        bindings = {}
        for binding in provenance.fact_derivation_bindings:
            if not isinstance(binding, InterfaceFactDerivationBinding):
                raise ValueError("materialized interface derivation binding is invalid")
            if not _is_closed_fact_path(binding.fact_path):
                raise ValueError("materialized interface derivation binding is not closed")
            if binding.fact_path in bindings:
                raise ValueError("materialized interface derivation binding paths must be unique")
            bindings[binding.fact_path] = binding
        if set(active_slots) != set(source_interface_slots):
            raise ValueError("materialized interface active fact slots are incomplete")
        if set(bindings) != set(source_slots):
            raise ValueError("materialized interface derivation bindings are incomplete")

        for path, source_fact in source_slots.items():
            source_evidence = require_authoritative_fact(source_fact, fact_name=path)
            binding = bindings[path]
            if (
                binding.source_fact_id != source_fact.fact_id
                or binding.source_evidence_id != source_evidence.evidence_id
                or binding.source_evidence_hash != source_evidence.evidence_hash
                or binding.transform_role is not source_fact.transform_role
            ):
                raise ValueError("materialized interface source derivation binding is incomplete")

            active_fact = active_slots.get(path)
            expected_derived_fact_id = (
                f"derived:{source_fact.fact_id}:{provenance.transform_id}"
            )
            if binding.derived_fact_id != expected_derived_fact_id:
                raise ValueError("materialized interface derived fact binding is incomplete")
            if active_fact is None:
                continue
            if (
                binding.derived_fact_id != active_fact.fact_id
                or binding.transform_role is not active_fact.transform_role
            ):
                raise ValueError("materialized interface derived fact binding is incomplete")
            if len(active_fact.evidence) != 1:
                raise ValueError(
                    "materialized interface fact does not have one deterministic evidence record"
                )
            selected = next(
                evidence
                for evidence in active_fact.evidence
                if evidence.evidence_id == active_fact.accepted_evidence_id
            )
            if (
                selected.evidence_id != expected_derived_fact_id
                or selected.basis_evidence_ids != (source_evidence.evidence_id,)
                or selected.conversion_provenance != provenance.transform_hash
                or selected.geometry_reference_hash != provenance.derived_geometry_reference_hash
            ):
                raise ValueError("materialized interface derived evidence binding is incomplete")

        _require_geometry_binding(definition.geometry_reference_hash, definition.geometry)
        if (
            provenance.derived_geometry != definition.geometry
            or provenance.derived_geometry_reference_hash != definition.geometry_reference_hash
        ):
            raise ValueError("materialized interface geometry does not match derivation provenance")
        _assert_interface_hashes(source)
        _assert_interface_hashes(definition)
        if provenance.source_interface_hash != source.interface_hash:
            raise ValueError("materialized interface source interface hash does not match snapshot")
        if provenance.source_geometry != source.geometry:
            raise ValueError("materialized interface source geometry does not match snapshot")
        if provenance.source_geometry_reference_hash != source.geometry_reference_hash:
            raise ValueError("materialized interface source geometry reference does not match snapshot")
        _require_geometry_binding(provenance.source_geometry_reference_hash, provenance.source_geometry)
        _require_geometry_binding(provenance.derived_geometry_reference_hash, provenance.derived_geometry)

        source_frame_id = _interface_reference_frame_id(source)
        active_frame_id = _interface_reference_frame_id(definition)
        if source_frame is None:
            if reference_frame is not None:
                raise ValueError("materialized interface has no active reference frame")
            if source_frame_id is not None or active_frame_id is not None:
                raise ValueError("materialized interface frame provenance is incomplete")
            if any(
                value is not None
                for value in (
                    provenance.source_reference_frame_hash,
                    provenance.derived_reference_frame_id,
                    provenance.derived_reference_frame_hash,
                )
            ):
                raise ValueError("materialized interface frame provenance is incomplete")
        else:
            _assert_frame_hashes(source_frame)
            if (
                source_frame_id != source_frame.frame_id
                or provenance.source_reference_frame_hash != source_frame.frame_hash
                or source_frame.geometry_reference_hash != provenance.source_geometry_reference_hash
                or active_frame_id != provenance.derived_reference_frame_id
                or provenance.derived_reference_frame_hash is None
            ):
                raise ValueError("materialized interface frame provenance is incomplete")
            _require_hash(provenance.derived_reference_frame_hash)
            if reference_frame is None:
                raise ValueError("materialized interface requires active frame")
            if (
                reference_frame.frame_id != active_frame_id
                or reference_frame.frame_id != provenance.derived_reference_frame_id
            ):
                raise ValueError("active reference frame ID does not match materialized interface")
            if reference_frame.frame_hash != provenance.derived_reference_frame_hash:
                raise ValueError("active reference frame hash does not match materialized interface")
            if reference_frame.geometry_reference_hash != provenance.derived_geometry_reference_hash:
                raise ValueError("active reference frame geometry does not match derived geometry")
            _validate_fact_geometry_binding(
                reference_frame.origin,
                (reference_frame.geometry_reference_hash,),
                "active reference frame origin",
            )
            _validate_fact_geometry_binding(
                reference_frame.orientation,
                (reference_frame.geometry_reference_hash,),
                "active reference frame orientation",
            )
            _assert_frame_hashes(reference_frame)
            _verify_derivation_bindings(
                provenance,
                MaterializedInterfaceResult(
                    interface=definition,
                    reference_frame=reference_frame,
                ),
            )

        _require_hash(provenance.transform_hash)
        _assert_hash_value(provenance, "provenance_hash")
        return definition
    variant = definition.shaft if definition.shaft is not None else definition.mounting_face
    assert variant is not None
    for field_name, fact in _interface_facts(variant):
        require_authoritative_fact(fact, fact_name=field_name)
    return definition


def require_authoritative_fact(
    fact: SuppliedInterfaceFact,
    *,
    fact_name: str,
) -> SuppliedInterfaceEvidence:
    if not fact_name.strip():
        raise ValueError("fact_name must not be empty or whitespace")
    if fact.accepted_evidence_id is None:
        raise ValueError(f"{fact_name} has no accepted evidence")
    records = {record.evidence_id: record for record in fact.evidence}
    evidence = records.get(fact.accepted_evidence_id)
    if evidence is None:
        raise ValueError(f"{fact_name} accepted evidence is missing")
    if evidence.availability is not ComponentPropertyAvailability.AVAILABLE:
        raise ValueError(f"{fact_name} accepted evidence is unavailable")
    if evidence.evidence_origin is SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED:
        raise ValueError(f"{fact_name} accepted evidence is inferred")
    if evidence.evidence_origin is SuppliedInterfaceEvidenceOrigin.DERIVED_MATERIALIZATION:
        raise ValueError(f"{fact_name} derived materialization requires provenance verification")
    return evidence


class GeometryDerivationStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"


class GeometryDerivationUnitConversion(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_unit: str
    derived_unit: str
    declaration: str

    _validate_text = field_validator("source_unit", "derived_unit", "declaration")(_nonblank)


class GeometryDerivationAuthorityRole(StrEnum):
    TRANSLATION_MM = "translation_mm"
    ROTATION = "rotation"
    UNIFORM_SCALE = "uniform_scale"


class GeometryDerivationAuthorityFact(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    authority_role: GeometryDerivationAuthorityRole
    expected_shape: SuppliedInterfaceEvidenceShape
    expected_unit: str
    evidence: tuple[SuppliedInterfaceEvidence, ...]
    accepted_evidence_id: str | None = None
    authority_fact_hash: str = "pending"

    _validate_text = field_validator("expected_unit", "accepted_evidence_id")(_nonblank)
    _validate_hash = field_validator("authority_fact_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_authority_fact(self) -> "GeometryDerivationAuthorityFact":
        expected_shape, expected_unit = {
            GeometryDerivationAuthorityRole.TRANSLATION_MM: (
                SuppliedInterfaceEvidenceShape.VECTOR3,
                "mm",
            ),
            GeometryDerivationAuthorityRole.ROTATION: (
                SuppliedInterfaceEvidenceShape.QUATERNION,
                "1",
            ),
            GeometryDerivationAuthorityRole.UNIFORM_SCALE: (
                SuppliedInterfaceEvidenceShape.SCALAR,
                "1",
            ),
        }[self.authority_role]
        if (self.expected_shape, self.expected_unit) != (expected_shape, expected_unit):
            raise ValueError("authority fact shape and unit do not match its authority role")

        evidence_ids = tuple(record.evidence_id for record in self.evidence)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("evidence IDs must be unique within an authority fact")
        ordered_evidence = tuple(sorted(self.evidence, key=lambda record: record.evidence_id))

        records = {record.evidence_id: record for record in ordered_evidence}
        for record in ordered_evidence:
            if record.shape is not expected_shape or record.canonical_unit != expected_unit:
                raise ValueError("evidence shape and unit do not match authority fact")
            if (
                self.authority_role is GeometryDerivationAuthorityRole.UNIFORM_SCALE
                and record.availability is ComponentPropertyAvailability.AVAILABLE
                and record.value <= 0.0
            ):
                raise ValueError("uniform scale evidence must be positive")
            if record.evidence_origin is SuppliedInterfaceEvidenceOrigin.DERIVED_MATERIALIZATION:
                continue
            if any(basis_id not in records for basis_id in record.basis_evidence_ids):
                raise ValueError("confirmation basis evidence is not fact-local")
        _validate_confirmation_geometry_bindings(records)

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(evidence_id: str) -> None:
            if evidence_id in visiting:
                raise ValueError("confirmation basis graph must be acyclic")
            if evidence_id in visited:
                return
            visiting.add(evidence_id)
            record = records[evidence_id]
            if record.evidence_origin is not SuppliedInterfaceEvidenceOrigin.DERIVED_MATERIALIZATION:
                for basis_id in record.basis_evidence_ids:
                    visit(basis_id)
            visiting.remove(evidence_id)
            visited.add(evidence_id)

        for evidence_id in records:
            visit(evidence_id)

        if self.accepted_evidence_id is not None:
            accepted = records.get(self.accepted_evidence_id)
            if accepted is None:
                raise ValueError("accepted evidence ID is not present in authority fact")
            if accepted.availability is not ComponentPropertyAvailability.AVAILABLE:
                raise ValueError("accepted evidence must be available")
            if accepted.evidence_origin is SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED:
                raise ValueError("inferred evidence cannot be accepted")

        object.__setattr__(self, "evidence", ordered_evidence)
        expected_hash = _self_hash(self, "authority_fact_hash")
        if self.authority_fact_hash == "pending":
            object.__setattr__(self, "authority_fact_hash", expected_hash)
        elif self.authority_fact_hash != expected_hash:
            raise ValueError("geometry derivation authority fact hash mismatch")
        return self


class GeometryDerivationTransform(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    transform_id: str
    source_geometry: GeometryArtifactIdentity
    derived_geometry: GeometryArtifactIdentity
    source_geometry_reference_hash: str
    derived_geometry_reference_hash: str
    translation_fact: GeometryDerivationAuthorityFact
    rotation_fact: GeometryDerivationAuthorityFact
    uniform_scale_fact: GeometryDerivationAuthorityFact
    unit_conversion: GeometryDerivationUnitConversion
    status: GeometryDerivationStatus
    transform_hash: str = "pending"

    _validate_text = field_validator("transform_id")(_nonblank)
    _validate_geometry_hashes = field_validator(
        "source_geometry_reference_hash", "derived_geometry_reference_hash"
    )(_require_hash)
    _validate_hash = field_validator("transform_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_transform(self) -> "GeometryDerivationTransform":
        if (
            self.source_geometry.geometry_identity_hash
            == self.derived_geometry.geometry_identity_hash
        ):
            raise ValueError("source and derived geometry must be distinct artifacts")
        if self.source_geometry_reference_hash != _geometry_reference_hash(self.source_geometry):
            raise ValueError("source geometry reference hash does not match geometry identity")
        if self.derived_geometry_reference_hash != _geometry_reference_hash(self.derived_geometry):
            raise ValueError("derived geometry reference hash does not match geometry identity")
        allowed_geometry_hashes = (
            self.source_geometry_reference_hash,
            self.derived_geometry_reference_hash,
        )
        for field_name, fact in (
            ("translation", self.translation_fact),
            ("rotation", self.rotation_fact),
            ("uniform scale", self.uniform_scale_fact),
        ):
            _validate_fact_geometry_binding(fact, allowed_geometry_hashes, field_name)
        if self.translation_fact.authority_role is not GeometryDerivationAuthorityRole.TRANSLATION_MM:
            raise ValueError("translation_fact has the wrong authority role")
        if self.rotation_fact.authority_role is not GeometryDerivationAuthorityRole.ROTATION:
            raise ValueError("rotation_fact has the wrong authority role")
        if self.uniform_scale_fact.authority_role is not GeometryDerivationAuthorityRole.UNIFORM_SCALE:
            raise ValueError("uniform_scale_fact has the wrong authority role")

        expected_hash = _geometry_derivation_transform_hash(self)
        if self.transform_hash == "pending":
            object.__setattr__(self, "transform_hash", expected_hash)
        elif self.transform_hash != expected_hash:
            raise ValueError("geometry derivation transform hash mismatch")
        return self

    @property
    def translation_mm(self) -> tuple[float, float, float]:
        value = _selected_authority_value(self.translation_fact, "translation")
        assert isinstance(value, tuple) and len(value) == 3
        return value

    @property
    def rotation_quaternion(self) -> tuple[float, float, float, float]:
        value = _selected_authority_value(self.rotation_fact, "rotation")
        assert isinstance(value, tuple) and len(value) == 4
        return normalize_quaternion(value)

    @property
    def scale(self) -> float:
        value = _selected_authority_value(self.uniform_scale_fact, "uniform scale")
        assert isinstance(value, float)
        if value <= 0.0:
            raise ValueError("uniform scale must be positive")
        return value


def _selected_authority_value(
    fact: GeometryDerivationAuthorityFact, fact_name: str
) -> Any:
    if fact.accepted_evidence_id is None:
        raise ValueError(f"{fact_name} has no selected authority evidence")
    records = {record.evidence_id: record for record in fact.evidence}
    evidence = records.get(fact.accepted_evidence_id)
    if evidence is None or evidence.availability is not ComponentPropertyAvailability.AVAILABLE:
        raise ValueError(f"{fact_name} selected authority evidence is unavailable")
    assert evidence.value is not None
    return evidence.value


def _optional_selected_authority_value(
    fact: GeometryDerivationAuthorityFact,
) -> Any | None:
    if fact.accepted_evidence_id is None:
        return None
    records = {record.evidence_id: record for record in fact.evidence}
    evidence = records.get(fact.accepted_evidence_id)
    if evidence is None or evidence.availability is not ComponentPropertyAvailability.AVAILABLE:
        return None
    return evidence.value


def _geometry_derivation_transform_hash(transform: GeometryDerivationTransform) -> str:
    from mechcad_harness.state.hashing import canonical_json

    payload = {
        "transform_id": transform.transform_id,
        "source_geometry": transform.source_geometry.model_dump(mode="json"),
        "derived_geometry": transform.derived_geometry.model_dump(mode="json"),
        "source_geometry_reference_hash": transform.source_geometry_reference_hash,
        "derived_geometry_reference_hash": transform.derived_geometry_reference_hash,
        "translation_fact": transform.translation_fact.model_dump(mode="json"),
        "rotation_fact": transform.rotation_fact.model_dump(mode="json"),
        "uniform_scale_fact": transform.uniform_scale_fact.model_dump(mode="json"),
        "effective_translation_mm": _optional_selected_authority_value(transform.translation_fact),
        "effective_rotation_quaternion": _optional_selected_authority_value(transform.rotation_fact),
        "effective_scale": _optional_selected_authority_value(transform.uniform_scale_fact),
        "unit_conversion": transform.unit_conversion.model_dump(mode="json"),
        "status": transform.status,
    }
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def require_authoritative_transform(
    transform: GeometryDerivationTransform,
) -> GeometryDerivationTransform:
    if transform.status is not GeometryDerivationStatus.ACCEPTED:
        raise ValueError("geometry derivation transform is not accepted")
    for fact_name, fact in (
        ("translation", transform.translation_fact),
        ("rotation", transform.rotation_fact),
        ("uniform scale", transform.uniform_scale_fact),
    ):
        _selected_authority_value(fact, fact_name)
        selected = next(
            record for record in fact.evidence if record.evidence_id == fact.accepted_evidence_id
        )
        if selected.evidence_origin not in (
            SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
            SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION,
        ):
            raise ValueError(f"{fact_name} authority evidence is not authoritative")
    return transform


def _require_runtime_role_value(role: SuppliedInterfaceTransformRole, value: Any) -> None:
    expected_shape = {
        SuppliedInterfaceTransformRole.POINT_MM: SuppliedInterfaceEvidenceShape.VECTOR3,
        SuppliedInterfaceTransformRole.LENGTH_MM: SuppliedInterfaceEvidenceShape.SCALAR,
        SuppliedInterfaceTransformRole.DISPLACEMENT_MM: SuppliedInterfaceEvidenceShape.VECTOR3,
        SuppliedInterfaceTransformRole.DIRECTION_UNIT: SuppliedInterfaceEvidenceShape.VECTOR3,
        SuppliedInterfaceTransformRole.ORIENTATION: SuppliedInterfaceEvidenceShape.QUATERNION,
        SuppliedInterfaceTransformRole.TEXT: SuppliedInterfaceEvidenceShape.TEXT,
    }[role]
    if not _shape_value_is_valid(expected_shape, value):
        raise ValueError(f"value does not match transform role {role.value}")


def apply_transform_role(
    role: SuppliedInterfaceTransformRole,
    value: Any,
    transform: GeometryDerivationTransform,
) -> Any:
    _require_runtime_role_value(role, value)
    if role is SuppliedInterfaceTransformRole.TEXT:
        return value
    if role is SuppliedInterfaceTransformRole.LENGTH_MM:
        return transform.scale * value
    if role is SuppliedInterfaceTransformRole.POINT_MM:
        rotated = rotate_vector(value, transform.rotation_quaternion)
        return tuple(
            transform.scale * component + offset
            for component, offset in zip(rotated, transform.translation_mm)
        )
    if role is SuppliedInterfaceTransformRole.DISPLACEMENT_MM:
        return tuple(
            transform.scale * component
            for component in rotate_vector(value, transform.rotation_quaternion)
        )
    if role is SuppliedInterfaceTransformRole.DIRECTION_UNIT:
        return normalize_direction(rotate_vector(value, transform.rotation_quaternion))
    return quaternion_compose(transform.rotation_quaternion, value)


def transform_fact(
    fact: SuppliedInterfaceFact,
    transform: GeometryDerivationTransform,
) -> SuppliedInterfaceEvidence:
    if not isinstance(fact, SuppliedInterfaceFact):
        raise TypeError("transform_fact requires a SuppliedInterfaceFact")
    require_authoritative_transform(transform)
    source = require_authoritative_fact(fact, fact_name=fact.fact_id)
    transformed_value = apply_transform_role(fact.transform_role, source.value, transform)
    values = source.model_dump(mode="python")
    values.update({
        "evidence_id": f"derived:{fact.fact_id}:{transform.transform_id}",
        "value": transformed_value,
        "authority": ComponentPropertyAuthority.DERIVED_NORMALIZATION,
        "source_identity": f"transform:{transform.transform_id}",
        "conversion_provenance": transform.transform_hash,
        "evidence_origin": SuppliedInterfaceEvidenceOrigin.DERIVED_MATERIALIZATION,
        "geometry_reference_hash": transform.derived_geometry_reference_hash,
        "basis_evidence_ids": (source.evidence_id,),
        "evidence_hash": "pending",
    })
    return SuppliedInterfaceEvidence.model_validate(values)


class SuppliedComponentReferenceFrame(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    frame_id: str = Field(min_length=1)
    geometry_reference_hash: str
    origin: SuppliedInterfaceFact
    orientation: SuppliedInterfaceFact
    frame_hash: str = "pending"

    _validate_text = field_validator("frame_id")(_nonblank)
    _validate_geometry_hash = field_validator("geometry_reference_hash")(_require_hash)
    _validate_hash = field_validator("frame_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_frame(self) -> "SuppliedComponentReferenceFrame":
        _validate_fact_geometry_binding(
            self.origin, (self.geometry_reference_hash,), "reference frame origin"
        )
        _validate_fact_geometry_binding(
            self.orientation, (self.geometry_reference_hash,), "reference frame orientation"
        )
        if (
            self.origin.expected_shape is not SuppliedInterfaceEvidenceShape.VECTOR3
            or self.origin.expected_unit != "mm"
            or self.origin.transform_role is not SuppliedInterfaceTransformRole.POINT_MM
        ):
            raise ValueError("frame origin must be a point fact in mm")
        if (
            self.orientation.expected_shape is not SuppliedInterfaceEvidenceShape.QUATERNION
            or self.orientation.expected_unit != "1"
            or self.orientation.transform_role is not SuppliedInterfaceTransformRole.ORIENTATION
        ):
            raise ValueError("frame orientation must be an orientation fact")

        expected = _self_hash(self, "frame_hash")
        if self.frame_hash == "pending":
            object.__setattr__(self, "frame_hash", expected)
        elif self.frame_hash != expected:
            raise ValueError("supplied component reference frame hash mismatch")
        return self


class MaterializationIntegrityError(ValueError):
    """Raised when a persisted materialization cannot be replayed exactly."""


def _require_optional_hash(value: str | None) -> str | None:
    return None if value is None else _require_hash(value)


def _is_closed_fact_path(path: str) -> bool:
    if path in {"reference_frame.origin", "reference_frame.orientation"}:
        return True
    if re.fullmatch(
        r"shaft\.(axis_point|axis_direction|nominal_shaft_diameter|"
        r"usable_axial_engagement_length|thread_designation)", path
    ):
        return True
    if re.fullmatch(r"shaft\.shoulder_reference_plane\.(point|normal)", path):
        return True
    if re.fullmatch(
        r"shaft\.d_flat_profile\.(flat_normal_direction|flat_across_dimension|"
        r"start_from_shoulder|effective_length)", path
    ):
        return True
    if path in {"mounting_face.plane_point", "mounting_face.outward_normal"}:
        return True
    hole_prefix = "mounting_face.holes["
    if path.startswith(hole_prefix):
        for field_name in ("center", "axis", "nominal_diameter", "thread_designation"):
            suffix = f"].{field_name}"
            if path.endswith(suffix):
                hole_id = path[len(hole_prefix):-len(suffix)]
                return bool(hole_id.strip())
    return path in {
        "mounting_face.pilot_boss.point",
        "mounting_face.pilot_boss.axis",
        "mounting_face.pilot_boss.diameter",
    }


class InterfaceFactDerivationBinding(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    fact_path: str
    source_fact_id: str
    derived_fact_id: str
    source_evidence_id: str
    source_evidence_hash: str
    transform_role: SuppliedInterfaceTransformRole

    _validate_text = field_validator(
        "fact_path", "source_fact_id", "derived_fact_id", "source_evidence_id"
    )(_nonblank)
    _validate_hash = field_validator("source_evidence_hash")(_require_hash)

    @model_validator(mode="after")
    def validate_slot(self) -> "InterfaceFactDerivationBinding":
        if not _is_closed_fact_path(self.fact_path):
            raise ValueError("fact_path is not an allowed materialization slot")
        return self


class InterfaceDerivationProvenance(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_interface_snapshot: SuppliedComponentInterfaceDefinition
    source_interface_hash: str
    source_reference_frame_snapshot: SuppliedComponentReferenceFrame | None = None
    source_reference_frame_hash: str | None = None
    derived_reference_frame_id: str | None = None
    derived_reference_frame_hash: str | None = None
    transform_id: str
    transform_hash: str
    source_geometry: GeometryArtifactIdentity
    derived_geometry: GeometryArtifactIdentity
    source_geometry_reference_hash: str
    derived_geometry_reference_hash: str
    fact_derivation_bindings: tuple[InterfaceFactDerivationBinding, ...]
    materialization_algorithm: Literal["supplied-interface-materialization@1"] = (
        "supplied-interface-materialization@1"
    )
    provenance_hash: str = "pending"

    _validate_text = field_validator("transform_id")(_nonblank)
    _validate_hashes = field_validator(
        "source_interface_hash",
        "transform_hash",
        "source_geometry_reference_hash",
        "derived_geometry_reference_hash",
        "derived_reference_frame_hash",
    )(_require_optional_hash)
    _validate_provenance_hash = field_validator("provenance_hash")(_hash_or_pending)
    _validate_frame_id = field_validator("derived_reference_frame_id")(_nonblank)

    @model_validator(mode="after")
    def validate_provenance(self) -> "InterfaceDerivationProvenance":
        source = self.source_interface_snapshot
        if source.kind != "direct":
            raise ValueError("provenance source interface snapshot must be direct")
        _assert_interface_hashes(source)
        if self.source_interface_hash != source.interface_hash:
            raise ValueError("source interface hash does not match its snapshot")
        if self.source_geometry != source.geometry:
            raise ValueError("provenance source geometry does not match source interface")
        _require_geometry_binding(self.source_geometry_reference_hash, self.source_geometry)
        _require_geometry_binding(self.derived_geometry_reference_hash, self.derived_geometry)
        if self.source_geometry_reference_hash != source.geometry_reference_hash:
            raise ValueError("provenance source geometry reference does not match source interface")

        source_frame = self.source_reference_frame_snapshot
        frame_id = _interface_reference_frame_id(source)
        if source_frame is None:
            if any(
                value is not None
                for value in (
                    self.source_reference_frame_hash,
                    self.derived_reference_frame_id,
                    self.derived_reference_frame_hash,
                )
            ):
                raise ValueError("frame provenance fields require a source frame snapshot")
            if frame_id is not None:
                raise ValueError("source interface frame reference has no frame snapshot")
        else:
            _assert_frame_hashes(source_frame)
            if self.source_reference_frame_hash != source_frame.frame_hash:
                raise ValueError("source reference frame hash does not match its snapshot")
            if frame_id != source_frame.frame_id:
                raise ValueError("source interface frame reference does not match its snapshot")
            if source_frame.geometry_reference_hash != self.source_geometry_reference_hash:
                raise ValueError("source reference frame geometry does not match source interface")
            if self.derived_reference_frame_id is None or self.derived_reference_frame_hash is None:
                raise ValueError("frame provenance must include the derived frame identity")

        paths = tuple(binding.fact_path for binding in self.fact_derivation_bindings)
        if not paths:
            raise ValueError("materialization fact derivation bindings are required")
        if len(set(paths)) != len(paths):
            raise ValueError("materialization fact paths must be unique")
        object.__setattr__(
            self,
            "fact_derivation_bindings",
            tuple(sorted(self.fact_derivation_bindings, key=lambda binding: binding.fact_path)),
        )
        expected = _self_hash(self, "provenance_hash")
        if self.provenance_hash == "pending":
            object.__setattr__(self, "provenance_hash", expected)
        elif self.provenance_hash != expected:
            raise ValueError("interface derivation provenance hash mismatch")
        return self


class DerivedInterfaceSemantics(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    interface_id: str
    geometry_reference_hash: str
    geometry: GeometryArtifactIdentity
    shaft: RotationalShaftInterface | None = None
    mounting_face: MountingFaceInterface | None = None

    _validate_id = field_validator("interface_id")(_nonblank)
    _validate_hash = field_validator("geometry_reference_hash")(_require_hash)

    @model_validator(mode="after")
    def validate_semantics(self) -> "DerivedInterfaceSemantics":
        _require_geometry_binding(self.geometry_reference_hash, self.geometry)
        variants = tuple(value for value in (self.shaft, self.mounting_face) if value is not None)
        if len(variants) != 1:
            raise ValueError("exactly one shaft or mounting face semantic is required")
        variant = variants[0]
        if (
            variant.interface_id != self.interface_id
            or variant.geometry_reference_hash != self.geometry_reference_hash
            or variant.geometry != self.geometry
        ):
            raise ValueError("derived interface semantic binding does not match")
        return self


class MaterializedInterfaceResult(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    interface: SuppliedComponentInterfaceDefinition
    reference_frame: SuppliedComponentReferenceFrame | None = None


def _interface_reference_frame_id(
    definition: SuppliedComponentInterfaceDefinition,
) -> str | None:
    variant = definition.shaft if definition.shaft is not None else definition.mounting_face
    assert variant is not None
    return variant.reference_frame_id


def _variant_fact_slots(
    variant: RotationalShaftInterface | MountingFaceInterface,
    prefix: str,
) -> tuple[tuple[str, SuppliedInterfaceFact], ...]:
    if isinstance(variant, RotationalShaftInterface):
        slots: list[tuple[str, SuppliedInterfaceFact]] = [
            (f"{prefix}.axis_point", variant.axis_point),
            (f"{prefix}.axis_direction", variant.axis_direction),
            (f"{prefix}.nominal_shaft_diameter", variant.nominal_shaft_diameter),
            (f"{prefix}.usable_axial_engagement_length", variant.usable_axial_engagement_length),
        ]
        if variant.shoulder_reference_plane is not None:
            slots.extend((
                (f"{prefix}.shoulder_reference_plane.point", variant.shoulder_reference_plane[0]),
                (f"{prefix}.shoulder_reference_plane.normal", variant.shoulder_reference_plane[1]),
            ))
        if variant.d_flat_profile is not None:
            slots.extend((
                (f"{prefix}.d_flat_profile.flat_normal_direction", variant.d_flat_profile.flat_normal_direction),
                (f"{prefix}.d_flat_profile.flat_across_dimension", variant.d_flat_profile.flat_across_dimension),
                (f"{prefix}.d_flat_profile.start_from_shoulder", variant.d_flat_profile.start_from_shoulder),
                (f"{prefix}.d_flat_profile.effective_length", variant.d_flat_profile.effective_length),
            ))
        if variant.thread_designation is not None:
            slots.append((f"{prefix}.thread_designation", variant.thread_designation))
        return tuple(slots)

    slots: list[tuple[str, SuppliedInterfaceFact]] = [
        (f"{prefix}.plane_point", variant.plane_point),
        (f"{prefix}.outward_normal", variant.outward_normal),
    ]
    for hole in variant.holes:
        slots.extend((
            (f"{prefix}.holes[{hole.hole_id}].center", hole.center),
            (f"{prefix}.holes[{hole.hole_id}].axis", hole.axis),
            (f"{prefix}.holes[{hole.hole_id}].nominal_diameter", hole.nominal_diameter),
        ))
        if hole.thread_designation is not None:
            slots.append((f"{prefix}.holes[{hole.hole_id}].thread_designation", hole.thread_designation))
    if variant.pilot_boss is not None:
        slots.extend((
            (f"{prefix}.pilot_boss.point", variant.pilot_boss.point),
            (f"{prefix}.pilot_boss.axis", variant.pilot_boss.axis),
            (f"{prefix}.pilot_boss.diameter", variant.pilot_boss.diameter),
        ))
    return tuple(slots)


def _fact_slots(
    definition: SuppliedComponentInterfaceDefinition,
    source_frame: SuppliedComponentReferenceFrame | None = None,
) -> tuple[tuple[str, SuppliedInterfaceFact], ...]:
    variant = definition.shaft if definition.shaft is not None else definition.mounting_face
    assert variant is not None
    slots: list[tuple[str, SuppliedInterfaceFact]] = []
    if source_frame is not None:
        slots.extend((
            ("reference_frame.origin", source_frame.origin),
            ("reference_frame.orientation", source_frame.orientation),
        ))
    slots.extend(_variant_fact_slots(
        variant, "shaft" if definition.shaft is not None else "mounting_face"
    ))
    return tuple(slots)


def _derived_fact(
    fact: SuppliedInterfaceFact,
    transform: GeometryDerivationTransform,
) -> SuppliedInterfaceFact:
    derived_evidence = transform_fact(fact, transform)
    return SuppliedInterfaceFact(
        fact_id=f"derived:{fact.fact_id}:{transform.transform_id}",
        expected_shape=fact.expected_shape,
        expected_unit=fact.expected_unit,
        transform_role=fact.transform_role,
        evidence=(derived_evidence,),
        accepted_evidence_id=derived_evidence.evidence_id,
    )


def _derive_variant(
    variant: RotationalShaftInterface | MountingFaceInterface,
    transform: GeometryDerivationTransform,
) -> RotationalShaftInterface | MountingFaceInterface:
    transform_one = lambda fact: _derived_fact(fact, transform)
    if isinstance(variant, RotationalShaftInterface):
        d_flat = None
        if variant.d_flat_profile is not None:
            d_flat = SuppliedShaftDFlatProfile(
                flat_normal_direction=transform_one(variant.d_flat_profile.flat_normal_direction),
                flat_across_dimension=transform_one(variant.d_flat_profile.flat_across_dimension),
                start_from_shoulder=transform_one(variant.d_flat_profile.start_from_shoulder),
                effective_length=transform_one(variant.d_flat_profile.effective_length),
            )
        shoulder = None if variant.shoulder_reference_plane is None else (
            transform_one(variant.shoulder_reference_plane[0]),
            transform_one(variant.shoulder_reference_plane[1]),
        )
        return RotationalShaftInterface(
            interface_id=variant.interface_id,
            geometry_reference_hash=transform.derived_geometry_reference_hash,
            geometry=transform.derived_geometry,
            reference_frame_id=variant.reference_frame_id,
            axis_point=transform_one(variant.axis_point),
            axis_direction=transform_one(variant.axis_direction),
            nominal_shaft_diameter=transform_one(variant.nominal_shaft_diameter),
            usable_axial_engagement_length=transform_one(variant.usable_axial_engagement_length),
            shoulder_reference_plane=shoulder,
            shaft_profile=variant.shaft_profile,
            d_flat_profile=d_flat,
            thread_designation=(
                None if variant.thread_designation is None else transform_one(variant.thread_designation)
            ),
        )

    holes = tuple(
        MountingHole(
            hole_id=hole.hole_id,
            center=transform_one(hole.center),
            axis=transform_one(hole.axis),
            nominal_diameter=transform_one(hole.nominal_diameter),
            thread_designation=(
                None if hole.thread_designation is None else transform_one(hole.thread_designation)
            ),
        )
        for hole in variant.holes
    )
    pilot = None if variant.pilot_boss is None else SuppliedPilotBossReference(
        point=transform_one(variant.pilot_boss.point),
        axis=transform_one(variant.pilot_boss.axis),
        diameter=transform_one(variant.pilot_boss.diameter),
    )
    return MountingFaceInterface(
        interface_id=variant.interface_id,
        geometry_reference_hash=transform.derived_geometry_reference_hash,
        geometry=transform.derived_geometry,
        face_reference_id=variant.face_reference_id,
        reference_frame_id=variant.reference_frame_id,
        plane_point=transform_one(variant.plane_point),
        outward_normal=transform_one(variant.outward_normal),
        holes=holes,
        pilot_boss=pilot,
    )


def _assert_geometry_transform_binding(
    source: SuppliedComponentInterfaceDefinition,
    transform: GeometryDerivationTransform,
) -> None:
    if source.geometry != transform.source_geometry:
        raise ValueError("source interface geometry does not match derivation source geometry")
    if source.geometry_reference_hash != transform.source_geometry_reference_hash:
        raise ValueError("source interface geometry reference does not match derivation")
    _require_geometry_binding(transform.source_geometry_reference_hash, transform.source_geometry)
    _require_geometry_binding(transform.derived_geometry_reference_hash, transform.derived_geometry)


def derive_reference_frame_semantics(
    source_frame: SuppliedComponentReferenceFrame,
    transform: GeometryDerivationTransform,
) -> SuppliedComponentReferenceFrame:
    require_authoritative_transform(transform)
    if source_frame.geometry_reference_hash != transform.source_geometry_reference_hash:
        raise ValueError("source reference frame geometry does not match derivation")
    _require_geometry_binding(transform.source_geometry_reference_hash, transform.source_geometry)
    _require_geometry_binding(transform.derived_geometry_reference_hash, transform.derived_geometry)
    return SuppliedComponentReferenceFrame(
        frame_id=source_frame.frame_id,
        geometry_reference_hash=transform.derived_geometry_reference_hash,
        origin=_derived_fact(source_frame.origin, transform),
        orientation=_derived_fact(source_frame.orientation, transform),
    )


def derive_interface_semantics(
    source: SuppliedComponentInterfaceDefinition,
    transform: GeometryDerivationTransform,
) -> DerivedInterfaceSemantics:
    if source.kind != "direct":
        raise ValueError("unresolved authority: materialized interfaces are not source inputs")
    try:
        require_authoritatively_consumable_interface(source)
        require_authoritative_transform(transform)
    except ValueError as exc:
        raise ValueError(f"unresolved authority: {exc}") from exc
    _assert_geometry_transform_binding(source, transform)
    variant = source.shaft if source.shaft is not None else source.mounting_face
    assert variant is not None
    derived = _derive_variant(variant, transform)
    return DerivedInterfaceSemantics(
        interface_id=source.interface_id,
        geometry_reference_hash=transform.derived_geometry_reference_hash,
        geometry=transform.derived_geometry,
        shaft=derived if isinstance(derived, RotationalShaftInterface) else None,
        mounting_face=derived if isinstance(derived, MountingFaceInterface) else None,
    )


def build_derivation_provenance(
    source: SuppliedComponentInterfaceDefinition,
    source_frame_or_none: SuppliedComponentReferenceFrame | None,
    transform: GeometryDerivationTransform,
) -> InterfaceDerivationProvenance:
    if source.kind != "direct":
        raise ValueError("provenance source interface must be direct")
    require_authoritatively_consumable_interface(source)
    require_authoritative_transform(transform)
    _assert_geometry_transform_binding(source, transform)
    frame_id = _interface_reference_frame_id(source)
    if (source_frame_or_none is None) != (frame_id is None):
        raise ValueError("source frame argument does not match interface frame reference")
    if source_frame_or_none is not None:
        if source_frame_or_none.frame_id != frame_id:
            raise ValueError("source frame ID does not match interface frame reference")
        if source_frame_or_none.geometry_reference_hash != source.geometry_reference_hash:
            raise ValueError("source frame geometry does not match source interface")
        frame_semantics = derive_reference_frame_semantics(source_frame_or_none, transform)
    else:
        frame_semantics = None

    derived_semantics = derive_interface_semantics(source, transform)
    derived_variant = derived_semantics.shaft or derived_semantics.mounting_face
    assert derived_variant is not None
    derived_slots: list[tuple[str, SuppliedInterfaceFact]] = []
    if frame_semantics is not None:
        derived_slots.extend((
            ("reference_frame.origin", frame_semantics.origin),
            ("reference_frame.orientation", frame_semantics.orientation),
        ))
    derived_slots.extend(_variant_fact_slots(
        derived_variant,
        "shaft" if derived_semantics.shaft is not None else "mounting_face",
    ))
    derived_by_path = dict(derived_slots)
    bindings = []
    for path, source_fact in _fact_slots(source, source_frame_or_none):
        source_evidence = require_authoritative_fact(source_fact, fact_name=path)
        derived_fact = derived_by_path.get(path)
        if derived_fact is None:
            raise ValueError(f"derived materialization slot is missing: {path}")
        bindings.append(InterfaceFactDerivationBinding(
            fact_path=path,
            source_fact_id=source_fact.fact_id,
            derived_fact_id=derived_fact.fact_id,
            source_evidence_id=source_evidence.evidence_id,
            source_evidence_hash=source_evidence.evidence_hash,
            transform_role=source_fact.transform_role,
        ))

    return InterfaceDerivationProvenance(
        source_interface_snapshot=source,
        source_interface_hash=source.interface_hash,
        source_reference_frame_snapshot=source_frame_or_none,
        source_reference_frame_hash=(
            None if source_frame_or_none is None else source_frame_or_none.frame_hash
        ),
        derived_reference_frame_id=(
            None if frame_semantics is None else frame_semantics.frame_id
        ),
        derived_reference_frame_hash=(
            None if frame_semantics is None else frame_semantics.frame_hash
        ),
        transform_id=transform.transform_id,
        transform_hash=transform.transform_hash,
        source_geometry=transform.source_geometry,
        derived_geometry=transform.derived_geometry,
        source_geometry_reference_hash=transform.source_geometry_reference_hash,
        derived_geometry_reference_hash=transform.derived_geometry_reference_hash,
        fact_derivation_bindings=tuple(bindings),
    )


def _derived_interface_from_semantics(
    semantics: DerivedInterfaceSemantics,
    provenance: InterfaceDerivationProvenance,
) -> SuppliedComponentInterfaceDefinition:
    return SuppliedComponentInterfaceDefinition(
        kind="materialized",
        interface_id=semantics.interface_id,
        geometry_reference_hash=semantics.geometry_reference_hash,
        geometry=semantics.geometry,
        shaft=semantics.shaft,
        mounting_face=semantics.mounting_face,
        derivation=provenance,
    )


def construct_materialized_result(
    interface_semantics: DerivedInterfaceSemantics,
    frame_semantics_or_none: SuppliedComponentReferenceFrame | None,
    provenance: InterfaceDerivationProvenance,
) -> MaterializedInterfaceResult:
    source = provenance.source_interface_snapshot
    if source.kind != "direct":
        raise ValueError("provenance source interface snapshot must be direct")
    if source.interface_id != interface_semantics.interface_id:
        raise ValueError("provenance source interface identity does not match derived semantics")
    if provenance.source_interface_hash != source.interface_hash:
        raise ValueError("provenance source interface hash does not match source snapshot")
    if provenance.source_geometry != source.geometry:
        raise ValueError("provenance source geometry does not match source snapshot")
    if provenance.source_geometry_reference_hash != source.geometry_reference_hash:
        raise ValueError("provenance source geometry reference does not match source snapshot")
    _require_geometry_binding(provenance.source_geometry_reference_hash, provenance.source_geometry)
    _require_geometry_binding(provenance.derived_geometry_reference_hash, provenance.derived_geometry)
    source_variant = source.shaft or source.mounting_face
    if interface_semantics.geometry != provenance.derived_geometry:
        raise ValueError("materialized interface geometry does not match provenance")
    if interface_semantics.geometry_reference_hash != provenance.derived_geometry_reference_hash:
        raise ValueError("materialized interface geometry reference does not match provenance")
    derived_variant = interface_semantics.shaft or interface_semantics.mounting_face
    assert derived_variant is not None
    if (source.shaft is None) != (interface_semantics.shaft is None):
        raise ValueError("provenance source variant does not match derived semantics")
    assert source_variant is not None
    source_frame = provenance.source_reference_frame_snapshot
    if source_frame is None:
        if _interface_reference_frame_id(source) is not None:
            raise ValueError("provenance source frame is missing")
    else:
        if source_frame.geometry_reference_hash != provenance.source_geometry_reference_hash:
            raise ValueError("provenance source frame geometry does not match source geometry")
        if source_frame.frame_id != _interface_reference_frame_id(source):
            raise ValueError("provenance source frame ID does not match source interface")
    if frame_semantics_or_none is None:
        if derived_variant.reference_frame_id is not None:
            raise ValueError("derived interface frame ID requires an active frame")
        if (
            provenance.derived_reference_frame_id is not None
            or provenance.derived_reference_frame_hash is not None
        ):
            raise ValueError("provenance requires an active derived frame")
        if _interface_reference_frame_id(provenance.source_interface_snapshot) is not None:
            raise ValueError("materialized interface is missing its derived frame")
    else:
        if frame_semantics_or_none.geometry_reference_hash != provenance.derived_geometry_reference_hash:
            raise ValueError("active frame geometry does not match derived geometry")
        if derived_variant.reference_frame_id != frame_semantics_or_none.frame_id:
            raise ValueError("derived interface frame ID does not match active frame")
        if (
            provenance.derived_reference_frame_id != frame_semantics_or_none.frame_id
            or provenance.derived_reference_frame_hash != frame_semantics_or_none.frame_hash
        ):
            raise ValueError("active derived frame does not match provenance")
        if (
            _interface_reference_frame_id(provenance.source_interface_snapshot)
            != frame_semantics_or_none.frame_id
        ):
            raise ValueError("active derived frame ID does not match source frame")
    return MaterializedInterfaceResult(
        interface=_derived_interface_from_semantics(interface_semantics, provenance),
        reference_frame=frame_semantics_or_none,
    )


def materialize_interface(
    source: SuppliedComponentInterfaceDefinition,
    source_frame_or_none: SuppliedComponentReferenceFrame | None,
    transform: GeometryDerivationTransform,
) -> MaterializedInterfaceResult:
    interface_semantics = derive_interface_semantics(source, transform)
    frame_semantics = (
        None
        if source_frame_or_none is None
        else derive_reference_frame_semantics(source_frame_or_none, transform)
    )
    return construct_materialized_result(
        interface_semantics,
        frame_semantics,
        build_derivation_provenance(source, source_frame_or_none, transform),
    )


def _assert_hash_value(model: Model, hash_field: str) -> None:
    actual = getattr(model, hash_field)
    if actual == "pending":
        raise ValueError(f"{hash_field} is pending")
    if actual != _self_hash(model, hash_field):
        raise ValueError(f"{hash_field} does not match its model")


def _assert_fact_hashes(fact: SuppliedInterfaceFact) -> None:
    for evidence in fact.evidence:
        _assert_hash_value(evidence, "evidence_hash")
    _assert_hash_value(fact, "fact_hash")


def _assert_variant_hashes(
    variant: RotationalShaftInterface | MountingFaceInterface,
) -> None:
    for _, fact in _variant_fact_slots(
        variant, "shaft" if isinstance(variant, RotationalShaftInterface) else "mounting_face"
    ):
        _assert_fact_hashes(fact)
    _assert_hash_value(variant, "interface_hash")


def _assert_interface_hashes(definition: SuppliedComponentInterfaceDefinition) -> None:
    variant = definition.shaft if definition.shaft is not None else definition.mounting_face
    assert variant is not None
    _assert_variant_hashes(variant)
    _assert_hash_value(definition, "interface_hash")
    if definition.geometry.geometry_identity_hash != geometry_identity_hash(definition.geometry):
        raise ValueError("interface geometry identity hash mismatch")


def _assert_frame_hashes(frame: SuppliedComponentReferenceFrame) -> None:
    _assert_fact_hashes(frame.origin)
    _assert_fact_hashes(frame.orientation)
    _assert_hash_value(frame, "frame_hash")


def _verify_derivation_bindings(
    provenance: InterfaceDerivationProvenance,
    expected: MaterializedInterfaceResult,
) -> None:
    source = provenance.source_interface_snapshot
    _assert_interface_hashes(source)
    source_frame = provenance.source_reference_frame_snapshot
    if source_frame is not None:
        _assert_frame_hashes(source_frame)
    source_slots = dict(_fact_slots(source, source_frame))
    expected_slots = dict(_fact_slots(expected.interface, expected.reference_frame))
    bindings = {binding.fact_path: binding for binding in provenance.fact_derivation_bindings}
    if set(bindings) != set(source_slots) or set(bindings) != set(expected_slots):
        raise ValueError("materialization fact derivation slots are incomplete")
    for path, source_fact in source_slots.items():
        binding = bindings[path]
        if binding.source_fact_id != source_fact.fact_id:
            raise ValueError("materialization binding source fact mismatch")
        source_evidence = require_authoritative_fact(source_fact, fact_name=path)
        if (
            binding.source_evidence_id != source_evidence.evidence_id
            or binding.source_evidence_hash != source_evidence.evidence_hash
            or source_evidence.evidence_hash != _self_hash(source_evidence, "evidence_hash")
        ):
            raise ValueError("materialization binding source evidence mismatch")
        derived_fact = expected_slots[path]
        if binding.derived_fact_id != derived_fact.fact_id:
            raise ValueError("materialization binding derived fact mismatch")
        if (
            binding.transform_role is not source_fact.transform_role
            or derived_fact.transform_role is not binding.transform_role
        ):
            raise ValueError("materialization binding transform role mismatch")
        _assert_fact_hashes(derived_fact)
        if derived_fact.accepted_evidence_id is None or len(derived_fact.evidence) != 1:
            raise ValueError("materialized fact does not have one deterministic evidence record")
        evidence = derived_fact.evidence[0]
        if (
            evidence.evidence_id != f"derived:{source_fact.fact_id}:{provenance.transform_id}"
            or evidence.evidence_origin is not SuppliedInterfaceEvidenceOrigin.DERIVED_MATERIALIZATION
            or evidence.basis_evidence_ids != (source_evidence.evidence_id,)
            or evidence.conversion_provenance != provenance.transform_hash
            or evidence.geometry_reference_hash != provenance.derived_geometry_reference_hash
            or derived_fact.accepted_evidence_id != evidence.evidence_id
        ):
            raise ValueError("materialized fact evidence correspondence mismatch")


class MaterializedInterfaceVerifier:
    @staticmethod
    def replay(
        provenance: InterfaceDerivationProvenance,
        transform: GeometryDerivationTransform,
    ) -> MaterializedInterfaceResult:
        try:
            _assert_hash_value(provenance, "provenance_hash")
            if provenance.materialization_algorithm != "supplied-interface-materialization@1":
                raise ValueError("unsupported materialization algorithm")
            source = provenance.source_interface_snapshot
            if source.kind != "direct":
                raise ValueError("provenance source interface snapshot must be direct")
            if provenance.source_interface_hash != source.interface_hash:
                raise ValueError("provenance source interface hash mismatch")
            if (
                transform.transform_id != provenance.transform_id
                or transform.transform_hash != provenance.transform_hash
            ):
                raise ValueError("provenance transform identity mismatch")
            if _geometry_derivation_transform_hash(transform) != transform.transform_hash:
                raise ValueError("transform hash mismatch")
            if (
                transform.source_geometry != provenance.source_geometry
                or transform.derived_geometry != provenance.derived_geometry
                or transform.source_geometry_reference_hash
                != provenance.source_geometry_reference_hash
                or transform.derived_geometry_reference_hash
                != provenance.derived_geometry_reference_hash
            ):
                raise ValueError("provenance geometry binding mismatch")
            require_authoritatively_consumable_interface(source)
            require_authoritative_transform(transform)
            _assert_geometry_transform_binding(source, transform)
            semantics = derive_interface_semantics(source, transform)
            source_frame = provenance.source_reference_frame_snapshot
            frame = (
                None
                if source_frame is None
                else derive_reference_frame_semantics(source_frame, transform)
            )
            expected = construct_materialized_result(semantics, frame, provenance)
            _verify_derivation_bindings(provenance, expected)
            return expected
        except MaterializationIntegrityError:
            raise
        except Exception as exc:
            raise MaterializationIntegrityError(
                f"materialization integrity failure: {exc}"
            ) from exc

    @staticmethod
    def verify(
        provenance: InterfaceDerivationProvenance,
        transform: GeometryDerivationTransform,
        persisted_active_interface: SuppliedComponentInterfaceDefinition,
        persisted_active_frame: SuppliedComponentReferenceFrame | None = None,
    ) -> None:
        try:
            expected = MaterializedInterfaceVerifier.replay(provenance, transform)
            if not isinstance(persisted_active_interface, SuppliedComponentInterfaceDefinition):
                raise ValueError("persisted active interface has the wrong type")
            if persisted_active_interface != expected.interface:
                raise ValueError("persisted active interface semantics differ from replay")
            _assert_hash_value(persisted_active_interface, "interface_hash")
            if persisted_active_frame != expected.reference_frame:
                raise ValueError("persisted active frame semantics differ from replay")
            if persisted_active_frame is not None:
                _assert_frame_hashes(persisted_active_frame)
        except MaterializationIntegrityError:
            raise
        except Exception as exc:
            raise MaterializationIntegrityError(
                f"materialization integrity failure: {exc}"
            ) from exc


SuppliedComponentInterfaceDefinition.model_rebuild(
    force=True,
    _types_namespace={"InterfaceDerivationProvenance": InterfaceDerivationProvenance},
)


__all__ = [
    "SuppliedComponentReferenceFrame",
    "MountingFaceInterface",
    "MountingHole",
    "RotationalShaftInterface",
    "SuppliedComponentInterfaceDefinition",
    "SuppliedInterfaceEvidence",
    "SuppliedInterfaceEvidenceOrigin",
    "SuppliedInterfaceEvidenceShape",
    "SuppliedInterfaceFact",
    "SuppliedInterfaceTransformRole",
    "SuppliedPilotBossReference",
    "SuppliedShaftDFlatProfile",
    "SuppliedShaftProfileKind",
    "GeometryDerivationAuthorityFact",
    "GeometryDerivationAuthorityRole",
    "GeometryDerivationStatus",
    "GeometryDerivationTransform",
    "GeometryDerivationUnitConversion",
    "InterfaceFactDerivationBinding",
    "InterfaceDerivationProvenance",
    "DerivedInterfaceSemantics",
    "MaterializedInterfaceResult",
    "MaterializedInterfaceVerifier",
    "MaterializationIntegrityError",
    "apply_transform_role",
    "build_derivation_provenance",
    "construct_materialized_result",
    "derive_interface_semantics",
    "derive_reference_frame_semantics",
    "materialize_interface",
    "require_authoritative_fact",
    "require_authoritative_transform",
    "require_authoritatively_consumable_interface",
    "transform_fact",
]
