from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import ConfigDict, Field, StrictInt, StrictStr, field_validator, model_validator

from mechcad_harness.artifacts import ArtifactStore, ArtifactType, EngineeringArtifact
from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_compilation import MountingPlateDesignSpec, compile_mounting_plate
from mechcad_harness.cad_program import cad_program_hash
from mechcad_harness.generated_part_cad import compile_generated_part
from mechcad_harness.imported_component import (
    ImportedComponentError,
    ImportedCadComponent,
    imported_component_hash,
    resolve_imported_component,
)
from mechcad_harness.models.common import Model
from mechcad_harness.models.physical_mechanism import (
    CanonicalPlacement,
    CanonicalPlacementOrigin,
    CanonicalComponentPropertyAvailability,
    CanonicalGeometryFidelity,
    CanonicalPhysicalMechanism,
)
from mechcad_harness.models.generated_part import generated_geometry_definition_identities
from mechcad_harness.step_content_identity import step_content_identity_v1
from mechcad_harness.state.hashing import canonical_json
from mechcad_harness.candidates.dimensions import (
    LEGACY_PLATE_DIMENSION_ALIASES,
    DimensionInput,
    DimensionResolutionError,
    resolve_dimensions,
)

from .canonical_mechanism import (
    CanonicalMechanismReconstruction,
    ExactSourceArtifactResolver,
    ProjectArtifactResolver,
    TrustedSourceArtifact,
    validate_canonical_mechanism,
)
from .generated_authority import build_canonical_view
from .cad_realization import (
    SemanticSourceGeometryIdentity,
    semantic_assembly_hash,
    trusted_representation_identity,
)


_SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]+")


def _hash_model(value: Model, identity_field: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(identity_field, None)
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def _require_hash(value: str) -> str:
    if (
        len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError("must be a sha256 hash")
    return value


def _hash_or_pending(value: str) -> str:
    return value if value == "pending" else _require_hash(value)


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty or whitespace")
    return value


def _canonical_request_hash(
    project_id: str,
    revision: int,
    state_hash: str,
    mechanism_id: str,
    mechanism_hash: str,
    mappings: tuple["CanonicalPhysicalCadMapping", ...],
    compiler_identity: str,
    compiler_version: str,
) -> str:
    payload = {
        "project_id": project_id,
        "revision": revision,
        "state_hash": state_hash,
        "mechanism_id": mechanism_id,
        "mechanism_hash": mechanism_hash,
        "mappings": [mapping.model_dump(mode="json") for mapping in mappings],
        "compiler_identity": compiler_identity,
        "compiler_version": compiler_version,
    }
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


class CanonicalCadModel(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CanonicalPhysicalCadMapping(CanonicalCadModel):
    """Fresh CAD identity for one canonical physical component."""

    schema_version: Literal["canonical-physical-cad-mapping@1"] = (
        "canonical-physical-cad-mapping@1"
    )
    mechanism_hash: StrictStr
    physical_instance_id: StrictStr = Field(min_length=1)
    cad_instance_id: StrictStr = Field(min_length=1)
    component_hash: StrictStr
    specification_hash: StrictStr
    fidelity: CanonicalGeometryFidelity
    representation_identity: StrictStr
    source_geometry_identity: StrictStr | None = None
    geometry_definition_identities: tuple[StrictStr, ...] = Field(min_length=1)
    placement: CadRigidTransform
    placement_id: StrictStr | None = None
    placement_hash: StrictStr | None = None
    placement_input_identities: tuple[StrictStr, ...] = Field(min_length=1)
    placement_relation: StrictStr = Field(min_length=1)
    mapping_hash: StrictStr = "pending"

    _validate_hashes = field_validator(
        "mechanism_hash",
        "component_hash",
        "specification_hash",
        "representation_identity",
        "placement_hash",
    )(lambda value: None if value is None else _require_hash(value))
    _validate_mapping_hash = field_validator("mapping_hash")(_hash_or_pending)
    _validate_text = field_validator(
        "physical_instance_id",
        "cad_instance_id",
        "placement_id",
        "placement_relation",
    )(lambda value: None if value is None else _nonblank(value))

    @model_validator(mode="after")
    def validate_mapping(self) -> "CanonicalPhysicalCadMapping":
        if any(not value.strip() for value in self.geometry_definition_identities):
            raise ValueError("canonical geometry definition identities must not be empty")
        if any(not value.strip() for value in self.placement_input_identities):
            raise ValueError("canonical placement input identities must not be empty")
        if self.fidelity is CanonicalGeometryFidelity.TRUSTED_SOURCE_GEOMETRY:
            if self.source_geometry_identity is None:
                raise ValueError("trusted source geometry requires source geometry identity")
            _require_hash(self.source_geometry_identity)
            if len(self.geometry_definition_identities) != 1:
                raise ValueError("trusted source geometry must identify exactly one artifact")
        elif self.source_geometry_identity is not None:
            raise ValueError("bounded geometry cannot claim source geometry")
        if self.placement_id is None and self.placement_hash is not None:
            raise ValueError("unbound placement cannot claim a placement hash")
        if self.placement_id is not None and self.placement_hash is None:
            raise ValueError("canonical placement requires its placement hash")
        expected = _hash_model(self, "mapping_hash")
        if self.mapping_hash == "pending":
            object.__setattr__(self, "mapping_hash", expected)
        elif self.mapping_hash != expected:
            raise ValueError("canonical CAD mapping hash mismatch")
        return self


def validate_canonical_cad_compiler_literals(
    compiler_identity: str, compiler_version: str
) -> None:
    """Fail closed on non-contract compiler overrides for canonical CAD @2."""

    if (
        compiler_identity != "canonical-physical-cad-compiler"
        or compiler_version != "canonical-cad@1"
    ):
        raise ValueError(
            "canonical CAD semantic family requires canonical compiler literals"
        )


def _canonical_geometry_content_by_raw_identity(mechanism):
    content_by_raw: dict[str, str] = {}
    specifications = getattr(mechanism, "component_specifications", mechanism)
    for specification in specifications:
        reference = specification.geometry_source
        if reference is None:
            continue
        if (
            reference.content_identity in (None, "pending")
            or reference.content_identity_algorithm != "step-content-identity@1"
            or reference.semantic_reference_hash in (None, "pending")
        ):
            raise ValueError(
                "canonical CAD mapping@2 requires bound semantic geometry references"
            )
        for raw in (reference.artifact_id, reference.artifact_hash):
            previous = content_by_raw.setdefault(raw, reference.content_identity)
            if previous != reference.content_identity:
                raise ValueError("canonical raw geometry token maps to conflicting content")
    return content_by_raw


def _canonical_semantic_placement_inputs(input_identities, content_by_raw):
    transformed = []
    for identity in input_identities:
        if identity.startswith("ART-") and identity not in content_by_raw:
            raise ValueError("canonical placement source artifact identity is unbound")
        transformed.append(content_by_raw.get(identity, identity))
    transformed = tuple(transformed)
    if any(not isinstance(value, str) or not value.strip() for value in transformed):
        raise ValueError("canonical placement inputs must be non-empty identities")
    if len(set(transformed)) != len(transformed):
        raise ValueError("canonical semantic placement inputs must be unique")
    return tuple(sorted(transformed))


def semantic_canonical_placement_hash(
    *,
    placement: CanonicalPlacement | None,
    mapping_instance_id: str,
    geometry_identities,
    placement_id: str | None = None,
    placement_input_identities: tuple[str, ...] = (),
    placement_relation: str | None = None,
    transform: CadRigidTransform | None = None,
) -> str:
    """Pure §15 placement identity, resolved in the canonical @4 mechanism.

    Existing mechanism placement records preserve their distinct origin and
    relation. A component with no mechanism placement is represented by null
    placement id/origin and the mapping's default-home transform/inputs/relation.
    """

    if not isinstance(mapping_instance_id, str) or not mapping_instance_id.strip():
        raise ValueError("canonical placement mapping instance must be non-empty")
    content_by_raw = _canonical_geometry_content_by_raw_identity(geometry_identities)
    if placement is not None:
        if placement.instance_id != mapping_instance_id:
            raise ValueError("canonical placement instance does not match mapping instance")
        if placement_id is not None and placement_id != placement.placement_id:
            raise ValueError("canonical placement ID does not match mapping placement ID")
        payload = {
            "placement_id": placement.placement_id,
            "instance_id": placement.instance_id,
            "origin": placement.origin.value,
            "input_identities": list(
                _canonical_semantic_placement_inputs(
                    placement.input_identities, content_by_raw
                )
            ),
            "relation": placement.relation,
            "x_mm": placement.x_mm,
            "y_mm": placement.y_mm,
            "z_mm": placement.z_mm,
            "rotation_quaternion": list(placement.rotation_quaternion),
        }
    else:
        if placement_id is not None:
            raise ValueError("canonical placement ID requires a mechanism placement")
        if transform is None or placement_relation is None:
            raise ValueError("default canonical placement requires transform and relation")
        payload = {
            "placement_id": None,
            "instance_id": mapping_instance_id,
            "origin": None,
            "input_identities": list(
                _canonical_semantic_placement_inputs(
                    placement_input_identities, content_by_raw
                )
            ),
            "relation": placement_relation,
            "x_mm": transform.x_mm,
            "y_mm": transform.y_mm,
            "z_mm": transform.z_mm,
            "rotation_quaternion": list(transform.rotation_quaternion),
        }
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


class CanonicalPhysicalCadMappingV2(CanonicalCadModel):
    """Canonical physical-to-CAD semantic mapping introduced by P4."""

    schema_version: Literal["canonical-physical-cad-mapping@2"] = (
        "canonical-physical-cad-mapping@2"
    )
    mechanism_hash: StrictStr
    physical_instance_id: StrictStr = Field(min_length=1)
    cad_instance_id: StrictStr = Field(min_length=1)
    component_hash: StrictStr
    specification_hash: StrictStr
    fidelity: CanonicalGeometryFidelity
    representation_identity: StrictStr
    source_geometry_identity: SemanticSourceGeometryIdentity | None = None
    geometry_definition_identities: tuple[StrictStr, ...] = Field(min_length=1)
    placement: CadRigidTransform
    placement_id: StrictStr | None = None
    placement_input_identities: tuple[StrictStr, ...] = Field(min_length=1)
    placement_relation: StrictStr = Field(min_length=1)
    mapping_hash: StrictStr = "pending"

    _validate_hashes = field_validator(
        "mechanism_hash", "component_hash", "specification_hash", "representation_identity"
    )(_require_hash)
    _validate_mapping_hash = field_validator("mapping_hash")(_hash_or_pending)
    _validate_text = field_validator(
        "physical_instance_id", "cad_instance_id", "placement_id", "placement_relation"
    )(lambda value: None if value is None else _nonblank(value))

    @model_validator(mode="after")
    def validate_mapping_v2(self) -> "CanonicalPhysicalCadMappingV2":
        if any(not value.strip() for value in self.geometry_definition_identities):
            raise ValueError("canonical geometry definition identities must not be empty")
        if any(not value.strip() for value in self.placement_input_identities):
            raise ValueError("canonical placement input identities must not be empty")
        if len(set(self.geometry_definition_identities)) != len(
            self.geometry_definition_identities
        ):
            raise ValueError("canonical geometry definition identities must be unique")
        if self.placement_input_identities != tuple(sorted(self.placement_input_identities)):
            raise ValueError("canonical semantic placement inputs must be sorted")
        if len(set(self.placement_input_identities)) != len(
            self.placement_input_identities
        ):
            raise ValueError("canonical semantic placement inputs must be unique")
        if self.fidelity is CanonicalGeometryFidelity.TRUSTED_SOURCE_GEOMETRY:
            if self.source_geometry_identity is None:
                raise ValueError("trusted source geometry requires semantic source identity")
            if self.geometry_definition_identities != (
                self.source_geometry_identity.content_identity,
            ):
                raise ValueError("trusted geometry definition must be the content identity")
        elif self.source_geometry_identity is not None:
            raise ValueError("generated or bounded mapping cannot claim trusted source geometry")
        if self.mapping_hash != "pending":
            _require_hash(self.mapping_hash)
        return self


def canonical_physical_cad_mapping_hash_v2(
    mapping: CanonicalPhysicalCadMappingV2,
    mechanism: CanonicalPhysicalMechanism,
    *,
    expected_representation_identity: str | None = None,
    fallback_geometry_definition_identities: tuple[str, ...] | None = None,
) -> str:
    """Recompute a canonical mapping@2 hash with its bound mechanism context."""

    if mechanism.schema_version != "canonical-physical-mechanism@4":
        raise ValueError("canonical CAD mapping@2 requires mechanism@4")
    mechanism = CanonicalPhysicalMechanism.model_validate(
        mechanism.model_dump(mode="json")
    )
    if mapping.mechanism_hash != mechanism.mechanism_hash:
        raise ValueError("canonical CAD mapping mechanism hash mismatch")
    component = next(
        (item for item in mechanism.components if item.instance_id == mapping.physical_instance_id),
        None,
    )
    if component is None or component.component_hash != mapping.component_hash:
        raise ValueError("canonical CAD mapping physical component mismatch")
    specification = next(
        (
            item
            for item in mechanism.component_specifications
            if item.specification_hash == component.specification_hash
        ),
        None,
    )
    if specification is None or mapping.specification_hash != specification.specification_hash:
        raise ValueError("canonical CAD mapping specification mismatch")
    if specification.schema_version != "canonical-component-specification@4":
        raise ValueError("canonical CAD mapping@2 requires component specification@4")

    source = specification.geometry_source
    if mapping.fidelity is CanonicalGeometryFidelity.TRUSTED_SOURCE_GEOMETRY:
        if source is None or mapping.source_geometry_identity is None:
            raise ValueError("trusted canonical mapping requires bound source geometry")
        expected_source = {
            "content_identity": source.content_identity,
            "content_identity_algorithm": source.content_identity_algorithm,
        }
        if mapping.source_geometry_identity.model_dump(mode="json") != expected_source:
            raise ValueError("canonical semantic source geometry identity mismatch")
        expected_definitions = (source.content_identity,)
        expected_representation = trusted_representation_identity(
            slot=mapping.cad_instance_id,
            content_identity=source.content_identity,
            content_identity_algorithm=source.content_identity_algorithm,
        )
        if mapping.source_geometry_identity.content_identity_algorithm != "step-content-identity@1":
            raise ValueError("unsupported trusted source semantic identity algorithm")
    elif specification.generated_part is not None:
        if mapping.fidelity is not CanonicalGeometryFidelity.EXACT_GENERATED_GEOMETRY:
            raise ValueError("generated canonical specification requires exact generated fidelity")
        if fallback_geometry_definition_identities is not None:
            raise ValueError("generated part does not accept fallback definition identities")
        expected_definitions = generated_geometry_definition_identities(
            specification.generated_part
        )
        if expected_representation_identity is None:
            raise ValueError(
                "generated canonical mapping requires a recomputed CAD program identity"
            )
        expected_representation = expected_representation_identity
    else:
        if source is not None:
            raise ValueError("supplied canonical geometry requires trusted source fidelity")
        if specification.generated_part is not None:
            raise ValueError("generated canonical geometry requires exact generated fidelity")
        if mapping.fidelity is not CanonicalGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION:
            raise ValueError("canonical fallback geometry requires bounded fidelity")
        if fallback_geometry_definition_identities is None:
            raise ValueError("bounded canonical mapping requires resolved dimension identities")
        if expected_representation_identity is None:
            raise ValueError(
                "bounded canonical mapping requires a recomputed CAD program identity"
            )
        expected_definitions = fallback_geometry_definition_identities
        expected_representation = expected_representation_identity
    if tuple(mapping.geometry_definition_identities) != tuple(expected_definitions):
        raise ValueError("canonical semantic geometry definition identities mismatch")
    if expected_representation is not None and mapping.representation_identity != expected_representation:
        raise ValueError("canonical CAD semantic representation identity mismatch")

    owned_placements = tuple(
        item
        for item in mechanism.placements
        if item.instance_id == mapping.physical_instance_id
    )
    if len(owned_placements) > 1:
        raise ValueError("canonical mapping physical instance has ambiguous placements")
    owned_placement = owned_placements[0] if owned_placements else None
    if mapping.placement_id is None:
        if owned_placement is not None:
            raise ValueError("canonical mapping omitted its mechanism placement ID")
        placement = None
    else:
        placement = next(
            (
                item
                for item in mechanism.placements
                if item.placement_id == mapping.placement_id
            ),
            None,
        )
        if placement is None:
            raise ValueError("canonical mapping placement ID does not resolve in mechanism@4")
        if placement != owned_placement:
            raise ValueError("canonical mapping placement belongs to a different instance")
    content_by_raw = _canonical_geometry_content_by_raw_identity(mechanism)
    expected_inputs = _canonical_semantic_placement_inputs(
        placement.input_identities
        if placement is not None
        else mapping.placement_input_identities,
        content_by_raw,
    )
    if tuple(mapping.placement_input_identities) != expected_inputs:
        raise ValueError("canonical mapping semantic placement inputs mismatch")
    if placement is not None:
        expected_transform = CadRigidTransform(
            x_mm=placement.x_mm,
            y_mm=placement.y_mm,
            z_mm=placement.z_mm,
            rotation_quaternion=placement.rotation_quaternion,
        )
        if mapping.placement != expected_transform:
            raise ValueError("canonical mapping placement transform mismatch")
        if mapping.placement_relation != placement.relation:
            raise ValueError("canonical mapping placement relation mismatch")
        placement_hash = semantic_canonical_placement_hash(
            placement=placement,
            mapping_instance_id=mapping.physical_instance_id,
            geometry_identities=mechanism.component_specifications,
            placement_id=mapping.placement_id,
        )
    else:
        placement_hash = semantic_canonical_placement_hash(
            placement=None,
            mapping_instance_id=mapping.physical_instance_id,
            geometry_identities=mechanism.component_specifications,
            placement_id=None,
            placement_input_identities=mapping.placement_input_identities,
            placement_relation=mapping.placement_relation,
            transform=mapping.placement,
        )
    payload = {
        "schema_version": mapping.schema_version,
        "mechanism_hash": mapping.mechanism_hash,
        "physical_instance_id": mapping.physical_instance_id,
        "cad_instance_id": mapping.cad_instance_id,
        "component_hash": mapping.component_hash,
        "specification_hash": mapping.specification_hash,
        "fidelity": mapping.fidelity.value,
        "representation_identity": mapping.representation_identity,
        "source_geometry_identity": (
            None
            if mapping.source_geometry_identity is None
            else mapping.source_geometry_identity.model_dump(mode="json")
        ),
        "geometry_definition_identities": list(mapping.geometry_definition_identities),
        "placement": mapping.placement.model_dump(mode="json"),
        "placement_id": mapping.placement_id,
        "semantic_canonical_placement_hash": placement_hash,
        "placement_input_identities": list(mapping.placement_input_identities),
        "placement_relation": mapping.placement_relation,
    }
    digest = "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()
    if mapping.mapping_hash not in ("pending", digest):
        raise ValueError("canonical CAD mapping@2 hash mismatch")
    return digest


# The shorter name mirrors the candidate CAD model while retaining a canonical
# primary type for callers that describe the physical-to-CAD boundary.
CanonicalCadInstanceMapping = CanonicalPhysicalCadMapping


class CanonicalCadIntegrityError(ValueError):
    """Canonical CAD input or source verification failed closed."""


class CanonicalCadRealization(CanonicalCadModel):
    """A fresh CAD realization bound to one canonical state revision."""

    schema_version: Literal["canonical-cad-realization@1"] = "canonical-cad-realization@1"
    project_id: StrictStr = Field(min_length=1)
    revision: StrictInt = Field(gt=0)
    state_hash: StrictStr
    mechanism_id: StrictStr = Field(min_length=1)
    mechanism_hash: StrictStr
    request_hash: StrictStr
    mappings: tuple[CanonicalPhysicalCadMapping, ...] = Field(min_length=1)
    assembly: CadAssemblyProgram
    assembly_hash: StrictStr
    selected_source_artifact_ids: tuple[StrictStr, ...] = ()
    selected_source_content_identities: tuple[StrictStr, ...] = ()
    selected_source_provenance: tuple[TrustedSourceArtifact, ...] = ()
    compiler_identity: StrictStr = Field(min_length=1)
    compiler_version: StrictStr = Field(min_length=1)
    realization_hash: StrictStr = "pending"

    _validate_hashes = field_validator(
        "state_hash",
        "mechanism_hash",
        "request_hash",
        "assembly_hash",
    )(_require_hash)
    _validate_realization_hash = field_validator("realization_hash")(_hash_or_pending)
    _validate_text = field_validator(
        "project_id", "mechanism_id", "compiler_identity", "compiler_version"
    )(_nonblank)

    @model_validator(mode="after")
    def validate_realization(self) -> "CanonicalCadRealization":
        physical_ids = tuple(mapping.physical_instance_id for mapping in self.mappings)
        cad_ids = tuple(mapping.cad_instance_id for mapping in self.mappings)
        if len(set(physical_ids)) != len(physical_ids):
            raise ValueError("canonical physical CAD mappings must be unique")
        if len(set(cad_ids)) != len(cad_ids):
            raise ValueError("canonical CAD instance mappings must be unique")
        if any(mapping.mechanism_hash != self.mechanism_hash for mapping in self.mappings):
            raise ValueError("canonical CAD mapping mechanism binding mismatch")

        assembly_instances = {instance.instance_id: instance for instance in self.assembly.instances}
        if set(cad_ids) != set(assembly_instances):
            raise ValueError("canonical CAD assembly instances must match mappings")
        if any(
            assembly_instances[mapping.cad_instance_id].placement != mapping.placement
            for mapping in self.mappings
        ):
            raise ValueError("canonical CAD assembly placement must match mapping")
        if self.assembly_hash != assembly_hash(self.assembly):
            raise ValueError("canonical CAD assembly hash mismatch")

        parts = {part.part_id: part for part in self.assembly.parts}
        imported = {
            component.component_id: component
            for component in self.assembly.imported_components
        }

        source_ids = tuple(source.artifact_id for source in self.selected_source_provenance)
        if source_ids != self.selected_source_artifact_ids:
            raise ValueError("canonical selected source artifact identity mismatch")
        source_hashes = tuple(source.sha256 for source in self.selected_source_provenance)
        if source_hashes != self.selected_source_content_identities:
            raise ValueError("canonical selected source content identity mismatch")
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("canonical selected source artifacts must be unique")
        if any(
            source.project_id != self.project_id
            or source.artifact_type is not ArtifactType.STEP
            for source in self.selected_source_provenance
        ):
            raise ValueError("canonical selected source provenance is invalid")
        provenance_by_id = {
            source.artifact_id: source for source in self.selected_source_provenance
        }

        for mapping in self.mappings:
            instance = assembly_instances[mapping.cad_instance_id]
            if mapping.fidelity is CanonicalGeometryFidelity.TRUSTED_SOURCE_GEOMETRY:
                component = imported.get(instance.part_id)
                if component is None:
                    raise ValueError("canonical trusted mapping must reference its imported component")
                if mapping.geometry_definition_identities != (component.artifact_id,):
                    raise ValueError(
                        "canonical trusted mapping artifact identity mismatch"
                    )
                if (
                    mapping.source_geometry_identity != component.artifact_hash
                    or mapping.representation_identity != imported_component_hash(component)
                ):
                    raise ValueError("canonical source geometry identity mismatch")
                provenance = provenance_by_id.get(component.artifact_id)
                if provenance is None or provenance.sha256 != component.artifact_hash:
                    raise ValueError("canonical source provenance hash mismatch")
            else:
                part = parts.get(instance.part_id)
                if part is None or mapping.representation_identity != cad_program_hash(part):
                    raise ValueError("canonical bounded mapping must reference its CAD part")

        mapped_source_ids = tuple(
            mapping.geometry_definition_identities[0]
            for mapping in self.mappings
            if mapping.fidelity is CanonicalGeometryFidelity.TRUSTED_SOURCE_GEOMETRY
        )
        if set(mapped_source_ids) != set(source_ids):
            raise ValueError("canonical selected source set does not match CAD mappings")

        expected_request_hash = _canonical_request_hash(
            self.project_id,
            self.revision,
            self.state_hash,
            self.mechanism_id,
            self.mechanism_hash,
            self.mappings,
            self.compiler_identity,
            self.compiler_version,
        )
        if self.request_hash != expected_request_hash:
            raise ValueError("canonical CAD request hash mismatch")

        expected = _hash_model(self, "realization_hash")
        if self.realization_hash == "pending":
            object.__setattr__(self, "realization_hash", expected)
        elif self.realization_hash != expected:
            raise ValueError("canonical CAD realization hash mismatch")
        return self

    @property
    def verified_source_content_identities(self) -> tuple[str, ...]:
        return self.selected_source_content_identities

    def validated_canonical_copy(self) -> "CanonicalCadRealization":
        """Revalidate and defensively copy the complete realization before use."""
        try:
            return type(self).model_validate(self.model_dump(mode="json"))
        except Exception as exc:
            raise CanonicalCadIntegrityError(
                str(exc) or "canonical CAD realization integrity validation failed"
            ) from exc

    @property
    def validated_canonical_assembly(self) -> CadAssemblyProgram:
        """Return a validated defensive assembly copy for trusted consumers."""
        return self.validated_canonical_copy().assembly


def _semantic_canonical_cad_request_hash_from_hashes(
    project_id: str,
    revision: int,
    mechanism_id: str,
    mechanism_hash: str,
    mapping_hashes: tuple[str, ...],
    compiler_identity: str,
    compiler_version: str,
) -> str:
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("canonical CAD semantic request project ID must not be empty")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision <= 0:
        raise ValueError("canonical CAD semantic request revision must be positive")
    _require_hash(mechanism_hash)
    for mapping_hash in mapping_hashes:
        _require_hash(mapping_hash)
    if len(set(mapping_hashes)) != len(mapping_hashes):
        raise ValueError("canonical CAD mapping hashes must be unique")
    if compiler_identity != "canonical-physical-cad-compiler":
        raise ValueError("canonical CAD semantic request compiler identity is not admitted")
    if compiler_version != "canonical-cad@1":
        raise ValueError("canonical CAD semantic request compiler version is not admitted")
    payload = {
        "request_contract": "canonical-cad-request@2",
        "project_id": project_id,
        "revision": revision,
        "mechanism_id": mechanism_id,
        "mechanism_hash": mechanism_hash,
        "mapping_hashes": list(mapping_hashes),
        "compiler_identity": compiler_identity,
        "compiler_version": compiler_version,
    }
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def semantic_canonical_cad_request_hash(
    *,
    project_id: str,
    revision: int,
    mechanism: CanonicalPhysicalMechanism,
    mappings: tuple[CanonicalPhysicalCadMappingV2, ...],
    compiler_identity: str,
    compiler_version: str,
    expected_representation_identities: dict[str, str] | None = None,
    fallback_geometry_definition_identities: dict[str, tuple[str, ...]] | None = None,
) -> str:
    """Compute canonical-cad-request@2 from a bound @4 mechanism + @2 maps.

    Mapping self-hashes are recomputed with the mechanism placement/specification
    context before their cad-instance-sorted tuple is admitted. No state hash,
    full mapping object, or raw artifact identity enters the request payload.
    """

    if type(mechanism) is not CanonicalPhysicalMechanism:
        raise TypeError("canonical CAD request@2 requires a typed mechanism@4")
    mechanism = CanonicalPhysicalMechanism.model_validate(
        mechanism.model_dump(mode="json")
    )
    if mechanism.schema_version != "canonical-physical-mechanism@4":
        raise ValueError("canonical CAD request@2 requires mechanism@4")
    if mechanism.id is None or not mechanism.id.strip():
        raise ValueError("canonical CAD mechanism ID must not be empty")
    if len({mapping.cad_instance_id for mapping in mappings}) != len(mappings):
        raise ValueError("canonical CAD request mapping cad_instance_id values must be unique")
    if len({mapping.physical_instance_id for mapping in mappings}) != len(mappings):
        raise ValueError("canonical CAD request mapping physical IDs must be unique")
    ordered = tuple(sorted(mappings, key=lambda mapping: mapping.cad_instance_id))
    representation_by_instance = expected_representation_identities or {}
    definitions_by_instance = fallback_geometry_definition_identities or {}
    mapping_hashes = []
    for mapping in ordered:
        if type(mapping) is not CanonicalPhysicalCadMappingV2:
            raise ValueError("canonical CAD request@2 rejects canonical mapping@1")
        expected_hash = canonical_physical_cad_mapping_hash_v2(
            mapping,
            mechanism,
            expected_representation_identity=representation_by_instance.get(
                mapping.physical_instance_id
            ),
            fallback_geometry_definition_identities=definitions_by_instance.get(
                mapping.physical_instance_id
            ),
        )
        if mapping.mapping_hash != expected_hash:
            raise ValueError("canonical CAD request mapping@2 hash mismatch")
        mapping_hashes.append(expected_hash)
    return _semantic_canonical_cad_request_hash_from_hashes(
        project_id,
        revision,
        mechanism.id,
        mechanism.mechanism_hash,
        tuple(mapping_hashes),
        compiler_identity,
        compiler_version,
    )


def canonical_cad_realization_hash_v2(realization: "CanonicalCadRealizationV2") -> str:
    """Compute the semantic hash of canonical-cad-realization@2 (§9)."""

    if realization.schema_version != "canonical-cad-realization@2":
        raise ValueError("canonical_cad_realization_hash_v2 requires realization@2")
    mapping_hashes = tuple(
        mapping.mapping_hash
        for mapping in sorted(
            realization.mappings, key=lambda mapping: mapping.cad_instance_id
        )
    )
    request_hash = _semantic_canonical_cad_request_hash_from_hashes(
        realization.project_id,
        realization.revision,
        realization.mechanism_id,
        realization.mechanism_hash,
        mapping_hashes,
        realization.compiler_identity,
        realization.compiler_version,
    )
    if realization.request_hash != request_hash:
        raise ValueError("canonical CAD request identity mismatch")
    payload = {
        "schema_version": realization.schema_version,
        "project_id": realization.project_id,
        "revision": realization.revision,
        "mechanism_id": realization.mechanism_id,
        "mechanism_hash": realization.mechanism_hash,
        "request_hash": realization.request_hash,
        "mapping_hashes": list(mapping_hashes),
        "semantic_assembly_hash": semantic_assembly_hash(
            realization.assembly, realization.mappings
        ),
        "selected_source_content_identities": list(
            realization.selected_source_content_identities
        ),
        "compiler_identity": realization.compiler_identity,
        "compiler_version": realization.compiler_version,
    }
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


class CanonicalCadRealizationV2(CanonicalCadModel):
    """Revision-scoped canonical CAD realization with semantic mapping refs."""

    schema_version: Literal["canonical-cad-realization@2"] = (
        "canonical-cad-realization@2"
    )
    project_id: StrictStr = Field(min_length=1)
    revision: StrictInt = Field(gt=0)
    state_hash: StrictStr
    mechanism_id: StrictStr = Field(min_length=1)
    mechanism_hash: StrictStr
    request_hash: StrictStr
    mappings: tuple[CanonicalPhysicalCadMappingV2, ...] = Field(min_length=1)
    assembly: CadAssemblyProgram
    assembly_hash: StrictStr
    selected_source_artifact_ids: tuple[StrictStr, ...] = ()
    selected_source_content_identities: tuple[StrictStr, ...] = ()
    selected_source_provenance: tuple[TrustedSourceArtifact, ...] = ()
    compiler_identity: StrictStr
    compiler_version: StrictStr
    realization_hash: StrictStr = "pending"
    selected_source_artifact_hashes: tuple[StrictStr, ...] = ()

    _validate_hashes = field_validator(
        "state_hash", "mechanism_hash", "request_hash", "assembly_hash"
    )(_require_hash)
    _validate_semantic_content = field_validator("selected_source_content_identities")(
        lambda values: tuple(_require_hash(value) for value in values)
    )
    _validate_raw_artifact_hashes = field_validator("selected_source_artifact_hashes")(
        lambda values: tuple(_require_hash(value) for value in values)
    )
    _validate_realization_hash = field_validator("realization_hash")(_hash_or_pending)
    _validate_literals = field_validator("compiler_identity", "compiler_version")(
        _nonblank
    )

    @model_validator(mode="after")
    def validate_realization_v2(self) -> "CanonicalCadRealizationV2":
        validate_canonical_cad_compiler_literals(
            self.compiler_identity, self.compiler_version
        )
        physical_ids = tuple(mapping.physical_instance_id for mapping in self.mappings)
        cad_ids = tuple(mapping.cad_instance_id for mapping in self.mappings)
        if len(set(physical_ids)) != len(physical_ids):
            raise ValueError("canonical physical CAD mappings must be unique")
        if len(set(cad_ids)) != len(cad_ids):
            raise ValueError("canonical CAD instance mappings must be unique")
        if any(
            type(mapping) is not CanonicalPhysicalCadMappingV2
            or mapping.mechanism_hash != self.mechanism_hash
            for mapping in self.mappings
        ):
            raise ValueError("canonical CAD realization@2 requires mapping@2 for its mechanism")
        assembly_instances = {
            instance.instance_id: instance for instance in self.assembly.instances
        }
        if set(cad_ids) != set(assembly_instances):
            raise ValueError("canonical CAD assembly instances must match mappings")
        if any(
            assembly_instances[mapping.cad_instance_id].placement != mapping.placement
            for mapping in self.mappings
        ):
            raise ValueError("canonical CAD assembly placement must match mapping")
        if self.assembly_hash != assembly_hash(self.assembly):
            raise ValueError("canonical CAD assembly hash mismatch")
        provenance = tuple(
            sorted(self.selected_source_provenance, key=lambda source: source.artifact_id)
        )
        if provenance != self.selected_source_provenance:
            raise ValueError("canonical selected source provenance must be artifact-ID sorted")
        source_ids = tuple(source.artifact_id for source in provenance)
        source_hashes = tuple(source.sha256 for source in provenance)
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("canonical selected source artifact IDs must be unique")
        if self.selected_source_artifact_ids != source_ids:
            raise ValueError("canonical selected source artifact identity mismatch")
        if self.selected_source_artifact_hashes != source_hashes:
            raise ValueError("canonical selected source artifact hash mismatch")
        if any(
            source.project_id != self.project_id
            or source.artifact_type is not ArtifactType.STEP
            for source in provenance
        ):
            raise ValueError("canonical selected source provenance is invalid")
        imported = {
            component.component_id: component
            for component in self.assembly.imported_components
        }
        parts = {part.part_id: part for part in self.assembly.parts}
        trusted_contents = []
        for mapping in self.mappings:
            instance = assembly_instances[mapping.cad_instance_id]
            if mapping.fidelity is CanonicalGeometryFidelity.TRUSTED_SOURCE_GEOMETRY:
                component = imported.get(instance.part_id)
                if component is None:
                    raise ValueError("canonical trusted mapping must reference imported source geometry")
                source = mapping.source_geometry_identity
                assert source is not None
                if mapping.representation_identity != trusted_representation_identity(
                    slot=mapping.cad_instance_id,
                    content_identity=source.content_identity,
                    content_identity_algorithm=source.content_identity_algorithm,
                ):
                    raise ValueError("canonical trusted representation identity mismatch")
                source_snapshot = next(
                    (item for item in provenance if item.artifact_id == component.artifact_id),
                    None,
                )
                if source_snapshot is None or source_snapshot.sha256 != component.artifact_hash:
                    raise ValueError("canonical trusted source provenance mismatch")
                trusted_contents.append((mapping.cad_instance_id, source.content_identity))
            else:
                part = parts.get(instance.part_id)
                if part is None or mapping.representation_identity != cad_program_hash(part):
                    raise ValueError("canonical bounded mapping must reference its CAD part")
        expected_content_ids = tuple(
            dict.fromkeys(content for _, content in sorted(trusted_contents))
        )
        if self.selected_source_content_identities != expected_content_ids:
            raise ValueError("canonical selected semantic source content identities mismatch")
        expected_hash = canonical_cad_realization_hash_v2(self)
        if self.realization_hash == "pending":
            object.__setattr__(self, "realization_hash", expected_hash)
        elif self.realization_hash != expected_hash:
            raise ValueError("canonical CAD realization@2 hash mismatch")
        return self


def _validate_m13_3_body_universe(mechanism, mappings) -> None:
    if mechanism.schema_version not in {
        "canonical-physical-mechanism@3",
        "canonical-physical-mechanism@4",
    }:
        return

    mapped_ids = {mapping.physical_instance_id for mapping in mappings}
    owner_by_member: dict[str, str] = {}
    for body in mechanism.physical_rigid_body_bindings:
        for member_id in body.member_physical_instance_ids:
            if member_id in owner_by_member:
                raise CanonicalCadIntegrityError(
                    "canonical physical body member has multiple CAD owners"
                )
            owner_by_member[member_id] = body.physical_body_id
    if set(owner_by_member) != mapped_ids:
        raise CanonicalCadIntegrityError(
            "canonical physical body and fresh CAD mapping universes do not match"
        )


class CanonicalPhysicalCadCompiler:
    """Compile canonical physical semantics without candidate CAD inputs."""

    _GENERATED_COMPONENT_TYPES = frozenset({"fixture", "mount", "support-mount", "driven-body"})

    def __init__(
        self,
        artifact_store_factory: ArtifactStore | ProjectArtifactResolver,
        *,
        compiler_identity: str = "canonical-physical-cad-compiler",
        compiler_version: str = "canonical-cad@1",
    ) -> None:
        if not isinstance(artifact_store_factory, (ArtifactStore, ProjectArtifactResolver)) and not callable(artifact_store_factory):
            raise ValueError("canonical CAD requires a project artifact resolver")
        self.artifact_store_factory = artifact_store_factory
        self.compiler_identity = _nonblank(compiler_identity)
        self.compiler_version = _nonblank(compiler_version)

    def realize(
        self,
        reconstruction: CanonicalMechanismReconstruction,
        *,
        trusted_source_references: tuple[TrustedSourceArtifact, ...] | None = None,
    ) -> CanonicalCadRealization | CanonicalCadRealizationV2:
        try:
            if not isinstance(reconstruction, CanonicalMechanismReconstruction):
                raise TypeError("canonical CAD requires a canonical mechanism reconstruction")
            reconstruction = CanonicalMechanismReconstruction.model_validate(
                reconstruction.model_dump(mode="json")
            )
            mechanism = validate_canonical_mechanism(reconstruction.canonical_mechanism)
            semantic_v2 = (
                mechanism.schema_version == "canonical-physical-mechanism@4"
            )
            if semantic_v2:
                try:
                    validate_canonical_cad_compiler_literals(
                        self.compiler_identity, self.compiler_version
                    )
                except ValueError as exc:
                    raise CanonicalCadIntegrityError(str(exc)) from exc
            resolver = self._resolver(
                reconstruction.project_id,
                trusted_source_references=trusted_source_references,
            )
            sources = {
                source.artifact_id: self._resolve_source(resolver, reconstruction, source)
                for source in reconstruction.trusted_source_references
            }
            if semantic_v2:
                self._verify_semantic_source_content(
                    resolver, reconstruction, mechanism
                )
            specifications = {
                specification.specification_hash: specification
                for specification in mechanism.component_specifications
            }
            components_by_id = {component.instance_id: component for component in mechanism.components}
            placements_by_id = {}
            placements_by_instance = {}
            for placement in mechanism.placements:
                if placement.placement_id in placements_by_id:
                    raise CanonicalCadIntegrityError("canonical placement IDs must be unique")
                if placement.instance_id not in components_by_id:
                    raise CanonicalCadIntegrityError(
                        "canonical placement references an unknown component"
                    )
                if placement.instance_id in placements_by_instance:
                    raise CanonicalCadIntegrityError(
                        "canonical component cannot have duplicate placements"
                    )
                placements_by_id[placement.placement_id] = placement
                placements_by_instance[placement.instance_id] = placement
            declared_placement_ids = {
                component.placement_id
                for component in mechanism.components
                if component.placement_id is not None
            }
            if set(placements_by_id) != declared_placement_ids:
                raise CanonicalCadIntegrityError(
                    "canonical placements must be declared by their components"
                )

            mappings = []
            parts_by_id = {}
            imported_components = []
            semantic_program_hashes: dict[str, str] = {}
            for component in mechanism.components:
                specification = specifications[component.specification_hash]
                cad_id = self._cad_id(mechanism.id, component.instance_id)
                placement = (
                    None
                    if component.placement_id is None
                    else placements_by_id.get(component.placement_id)
                )
                if placement is not None and placement.instance_id != component.instance_id:
                    raise CanonicalCadIntegrityError(
                        "canonical placement does not belong to its component"
                    )
                if component.placement_id is not None and placement is None:
                    raise CanonicalCadIntegrityError(
                        "canonical component placement reference is missing"
                    )
                transform = CadRigidTransform(
                    **({}
                    if placement is None
                    else {
                        "x_mm": placement.x_mm,
                        "y_mm": placement.y_mm,
                        "z_mm": placement.z_mm,
                        "rotation_quaternion": placement.rotation_quaternion,
                    })
                )
                if specification.geometry_source is not None:
                    source = specification.geometry_source
                    imported = sources[source.artifact_id][0].model_copy(update={"component_id": cad_id})
                    imported_components.append(imported)
                    if semantic_v2:
                        semantic_source = SemanticSourceGeometryIdentity(
                            content_identity=source.content_identity,
                            content_identity_algorithm=source.content_identity_algorithm,
                        )
                        input_identities = _canonical_semantic_placement_inputs(
                            (component.component_hash,)
                            if placement is None
                            else placement.input_identities,
                            _canonical_geometry_content_by_raw_identity(mechanism),
                        )
                        mapping = CanonicalPhysicalCadMappingV2(
                            mechanism_hash=mechanism.mechanism_hash,
                            physical_instance_id=component.instance_id,
                            cad_instance_id=cad_id,
                            component_hash=component.component_hash,
                            specification_hash=component.specification_hash,
                            fidelity=CanonicalGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
                            representation_identity=trusted_representation_identity(
                                slot=cad_id,
                                content_identity=source.content_identity,
                                content_identity_algorithm=source.content_identity_algorithm,
                            ),
                            source_geometry_identity=semantic_source,
                            geometry_definition_identities=(source.content_identity,),
                            placement=transform,
                            placement_id=None if placement is None else placement.placement_id,
                            placement_input_identities=input_identities,
                            placement_relation=(
                                "canonical-default-home-placement@1"
                                if placement is None
                                else placement.relation
                            ),
                        )
                        mapping_hash = canonical_physical_cad_mapping_hash_v2(
                            mapping, mechanism
                        )
                        mappings.append(mapping.model_copy(update={"mapping_hash": mapping_hash}))
                    else:
                        mappings.append(
                            CanonicalPhysicalCadMapping(
                                mechanism_hash=mechanism.mechanism_hash,
                                physical_instance_id=component.instance_id,
                                cad_instance_id=cad_id,
                                component_hash=component.component_hash,
                                specification_hash=component.specification_hash,
                                fidelity=CanonicalGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
                                representation_identity=imported_component_hash(imported),
                                source_geometry_identity=source.artifact_hash,
                                geometry_definition_identities=(source.artifact_id,),
                                placement=transform,
                                placement_id=None if placement is None else placement.placement_id,
                                placement_hash=None if placement is None else placement.placement_hash,
                                placement_input_identities=(
                                    (component.component_hash,)
                                    if placement is None
                                    else placement.input_identities
                                ),
                                placement_relation=(
                                    "canonical-default-home-placement@1"
                                    if placement is None
                                    else placement.relation
                                ),
                            )
                        )
                else:
                    program, identities = self._compile_generated(
                        specification, component.instance_id, cad_id, mechanism
                    )
                    parts_by_id.setdefault(program.part_id, program)
                    if semantic_v2:
                        program_hash = cad_program_hash(program)
                        semantic_program_hashes[component.instance_id] = program_hash
                        fidelity = (
                            CanonicalGeometryFidelity.EXACT_GENERATED_GEOMETRY
                            if specification.generated_part is not None
                            else CanonicalGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION
                        )
                        input_identities = _canonical_semantic_placement_inputs(
                            (component.component_hash,)
                            if placement is None
                            else placement.input_identities,
                            _canonical_geometry_content_by_raw_identity(mechanism),
                        )
                        mapping = CanonicalPhysicalCadMappingV2(
                            mechanism_hash=mechanism.mechanism_hash,
                            physical_instance_id=component.instance_id,
                            cad_instance_id=cad_id,
                            component_hash=component.component_hash,
                            specification_hash=component.specification_hash,
                            fidelity=fidelity,
                            representation_identity=program_hash,
                            source_geometry_identity=None,
                            geometry_definition_identities=identities,
                            placement=transform,
                            placement_id=None if placement is None else placement.placement_id,
                            placement_input_identities=input_identities,
                            placement_relation=(
                                "canonical-default-home-placement@1"
                                if placement is None
                                else placement.relation
                            ),
                        )
                        fallback = (
                            identities
                            if specification.generated_part is None
                            else None
                        )
                        mapping_hash = canonical_physical_cad_mapping_hash_v2(
                            mapping,
                            mechanism,
                            expected_representation_identity=program_hash,
                            fallback_geometry_definition_identities=fallback,
                        )
                        mappings.append(mapping.model_copy(update={"mapping_hash": mapping_hash}))
                    else:
                        mappings.append(
                            CanonicalPhysicalCadMapping(
                                mechanism_hash=mechanism.mechanism_hash,
                                physical_instance_id=component.instance_id,
                                cad_instance_id=cad_id,
                                component_hash=component.component_hash,
                                specification_hash=component.specification_hash,
                                fidelity=(
                                    CanonicalGeometryFidelity.EXACT_GENERATED_GEOMETRY
                                    if specification.generated_part is not None
                                    else CanonicalGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION
                                ),
                                representation_identity=cad_program_hash(program),
                                geometry_definition_identities=identities,
                                placement=transform,
                                placement_id=None if placement is None else placement.placement_id,
                                placement_hash=None if placement is None else placement.placement_hash,
                                placement_input_identities=(
                                    (component.component_hash,)
                                    if placement is None
                                    else placement.input_identities
                                ),
                                placement_relation=(
                                    "canonical-default-home-placement@1"
                                    if placement is None
                                    else placement.relation
                                ),
                            )
                        )

            _validate_m13_3_body_universe(mechanism, mappings)
            if semantic_v2:
                mappings = sorted(mappings, key=lambda mapping: mapping.cad_instance_id)
                request_hash = semantic_canonical_cad_request_hash(
                    project_id=reconstruction.project_id,
                    revision=reconstruction.revision,
                    mechanism=mechanism,
                    mappings=tuple(mappings),
                    compiler_identity=self.compiler_identity,
                    compiler_version=self.compiler_version,
                    expected_representation_identities={
                        **semantic_program_hashes
                    },
                    fallback_geometry_definition_identities={
                        mapping.physical_instance_id: mapping.geometry_definition_identities
                        for mapping in mappings
                        if mapping.fidelity is CanonicalGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION
                    },
                )
            else:
                request_hash = self._request_hash(reconstruction, tuple(mappings))
            instances = tuple(
                CadComponentInstance(
                    instance_id=mapping.cad_instance_id,
                    part_id=(
                        mapping.cad_instance_id
                        if mapping.fidelity is CanonicalGeometryFidelity.TRUSTED_SOURCE_GEOMETRY
                        else next(
                            part.part_id
                            for part in parts_by_id.values()
                            if cad_program_hash(part) == mapping.representation_identity
                        )
                    ),
                    placement=mapping.placement.model_copy(deep=True),
                )
                for mapping in mappings
            )
            assembly = CadAssemblyProgram(
                assembly_id=f"canonical-assembly-{request_hash[7:23]}",
                parts=tuple(parts_by_id.values()),
                imported_components=tuple(imported_components),
                instances=instances,
            )
            provenance = tuple(
                sources[artifact_id][1]
                for artifact_id in sorted(sources)
            )
            if semantic_v2:
                ordered_mappings = tuple(
                    sorted(mappings, key=lambda mapping: mapping.physical_instance_id)
                )
                semantic_content_identities = tuple(
                    dict.fromkeys(
                        mapping.source_geometry_identity.content_identity
                        for mapping in sorted(
                            mappings, key=lambda mapping: mapping.cad_instance_id
                        )
                        if mapping.source_geometry_identity is not None
                    )
                )
                return CanonicalCadRealizationV2(
                    project_id=reconstruction.project_id,
                    revision=reconstruction.revision,
                    state_hash=reconstruction.state_hash,
                    mechanism_id=mechanism.id,
                    mechanism_hash=mechanism.mechanism_hash,
                    request_hash=request_hash,
                    mappings=ordered_mappings,
                    assembly=assembly,
                    assembly_hash=assembly_hash(assembly),
                    selected_source_artifact_ids=tuple(
                        source.artifact_id for source in provenance
                    ),
                    selected_source_content_identities=semantic_content_identities,
                    selected_source_provenance=provenance,
                    compiler_identity=self.compiler_identity,
                    compiler_version=self.compiler_version,
                    selected_source_artifact_hashes=tuple(
                        source.sha256 for source in provenance
                    ),
                )
            return CanonicalCadRealization(
                project_id=reconstruction.project_id,
                revision=reconstruction.revision,
                state_hash=reconstruction.state_hash,
                mechanism_id=mechanism.id,
                mechanism_hash=mechanism.mechanism_hash,
                request_hash=request_hash,
                mappings=tuple(mappings),
                assembly=assembly,
                assembly_hash=assembly_hash(assembly),
                selected_source_artifact_ids=tuple(source.artifact_id for source in provenance),
                selected_source_content_identities=tuple(source.sha256 for source in provenance),
                selected_source_provenance=provenance,
                compiler_identity=self.compiler_identity,
                compiler_version=self.compiler_version,
            )
        except CanonicalCadIntegrityError:
            raise
        except Exception as exc:
            raise CanonicalCadIntegrityError(str(exc) or "canonical CAD realization failed") from exc

    def _resolver(
        self,
        project_id: str,
        *,
        trusted_source_references: tuple[TrustedSourceArtifact, ...] | None = None,
    ) -> ProjectArtifactResolver:
        factory = self.artifact_store_factory
        if isinstance(factory, ArtifactStore):
            resolver = ProjectArtifactResolver(factory)
        elif isinstance(factory, ProjectArtifactResolver):
            resolver = factory
        else:
            try:
                resolver = factory(project_id)
            except TypeError as exc:
                raise CanonicalCadIntegrityError(
                    "canonical artifact resolver factory must accept project_id only"
                ) from exc
        if not isinstance(resolver, ProjectArtifactResolver):
            raise CanonicalCadIntegrityError("canonical CAD requires a ProjectArtifactResolver")
        if resolver.project_id != project_id:
            raise CanonicalCadIntegrityError("canonical artifact resolver project scope mismatch")
        if trusted_source_references:
            try:
                return ExactSourceArtifactResolver(
                    resolver.workspace,
                    project_id,
                    trusted_source_references,
                )
            except Exception as exc:
                raise CanonicalCadIntegrityError(
                    f"canonical exact source resolver is invalid: {exc}"
                ) from exc
        return resolver

    @staticmethod
    def _resolve_source(resolver, reconstruction, source):
        try:
            verified = resolver.read_verified_in_project(
                source.artifact_id,
                expected_type=ArtifactType.STEP,
                expected_hash=source.sha256,
            )
        except Exception as exc:
            raise CanonicalCadIntegrityError(f"canonical source verification failed: {exc}") from exc
        if verified is None:
            raise CanonicalCadIntegrityError("canonical selected source is missing or tampered")
        artifact, _ = verified
        if (
            artifact.project_id != reconstruction.project_id
            or artifact.artifact_id != source.artifact_id
            or artifact.artifact_type is not ArtifactType.STEP
            or artifact.sha256 != source.sha256
        ):
            raise CanonicalCadIntegrityError("canonical selected source binding mismatch")
        try:
            expected_snapshot = TrustedSourceArtifact.from_artifact(artifact)
            if expected_snapshot != source:
                raise CanonicalCadIntegrityError("canonical source provenance snapshot mismatch")
            source_store = ArtifactStore(
                resolver.workspace,
                project_id=reconstruction.project_id,
                run_id=artifact.run_id,
                task_id=artifact.task_id,
            )
            imported = resolve_imported_component(
                source.artifact_id,
                source.sha256,
                source_store,
                component_id="source-verification",
            )
        except CanonicalCadIntegrityError:
            raise
        except (ImportedComponentError, ValueError) as exc:
            raise CanonicalCadIntegrityError(f"canonical imported source verification failed: {exc}") from exc
        return imported, source

    @staticmethod
    def _verify_semantic_source_content(resolver, reconstruction, mechanism) -> None:
        """Dual-verify semantic STEP content from the exact raw-verified bytes."""

        for specification in mechanism.component_specifications:
            reference = specification.geometry_source
            if reference is None:
                continue
            verified = resolver.read_verified_in_project(
                reference.artifact_id,
                expected_type=ArtifactType.STEP,
                expected_hash=reference.artifact_hash,
            )
            if verified is None:
                raise CanonicalCadIntegrityError(
                    "canonical semantic STEP source is missing or ambiguous"
                )
            artifact, content = verified
            snapshot = next(
                (
                    item
                    for item in reconstruction.trusted_source_references
                    if item.artifact_id == reference.artifact_id
                ),
                None,
            )
            if (
                snapshot is None
                or artifact.project_id != reconstruction.project_id
                or artifact != EngineeringArtifact.model_validate(
                    snapshot.model_dump(mode="json", exclude={"schema_version"})
                )
            ):
                raise CanonicalCadIntegrityError(
                    "canonical semantic STEP raw source binding mismatch"
                )
            actual = step_content_identity_v1(content)
            if (
                actual.algorithm != reference.content_identity_algorithm
                or actual.content_hash != reference.content_identity
            ):
                raise CanonicalCadIntegrityError(
                    "canonical STEP semantic content identity mismatch"
                )

    @classmethod
    def _compile_generated(cls, specification, instance_id, cad_id, mechanism):
        if specification.generated_part is not None:
            try:
                compilation = compile_generated_part(
                    specification.generated_part,
                    build_canonical_view(mechanism, specification.specification_hash),
                    owning_instance_context=instance_id,
                )
            except Exception as exc:
                raise CanonicalCadIntegrityError(str(exc)) from exc
            return compilation.program, compilation.geometry_definition_identities
        if specification.component_type not in cls._GENERATED_COMPONENT_TYPES:
            raise CanonicalCadIntegrityError(
                f"canonical component type is not supported for generated CAD: {specification.component_type}"
            )
        inputs = []
        choice_semantics = {}
        for semantic_name, aliases in LEGACY_PLATE_DIMENSION_ALIASES.items():
            for alias in aliases:
                suffix = alias.removeprefix("geometry.")
                for key in (
                    f"{instance_id}.{alias}",
                    f"{instance_id}.geometry.{suffix}",
                    f"geometry.{instance_id}.{suffix}",
                ):
                    choice_semantics[key] = (semantic_name, alias)

        for choice in mechanism.accepted_design_choices:
            semantic = choice_semantics.get(choice.key)
            if semantic is None:
                continue
            semantic_name, alias = semantic
            inputs.append(
                DimensionInput(
                    component_instance_id=instance_id,
                    semantic_name=semantic_name,
                    alias=alias,
                    value=choice.value,
                    unit="mm",
                    identity=choice.choice_hash,
                )
            )

        for property_value in specification.properties:
            semantic_name = next(
                (
                    semantic_name
                    for semantic_name, aliases in LEGACY_PLATE_DIMENSION_ALIASES.items()
                    if property_value.key in aliases
                ),
                None,
            )
            if (
                semantic_name is None
                or property_value.availability
                is not CanonicalComponentPropertyAvailability.AVAILABLE
                or property_value.normalized_value is None
                or property_value.canonical_unit != "mm"
            ):
                continue
            inputs.append(
                DimensionInput(
                    component_instance_id=instance_id,
                    semantic_name=semantic_name,
                    alias=property_value.key,
                    value=property_value.normalized_value,
                    unit="mm",
                    identity=property_value.property_hash,
                )
            )

        try:
            resolved = resolve_dimensions(
                inputs,
                required_dimensions=tuple(LEGACY_PLATE_DIMENSION_ALIASES),
            )
        except DimensionResolutionError as exc:
            raise CanonicalCadIntegrityError(str(exc)) from exc
        if not resolved or any(
            (instance_id, semantic_name) not in resolved
            for semantic_name in LEGACY_PLATE_DIMENSION_ALIASES
        ):
            raise CanonicalCadIntegrityError(
                f"canonical geometry is unavailable for {instance_id}"
            )

        dimensions = {
            semantic_name: resolved[(instance_id, semantic_name)].value
            for semantic_name in LEGACY_PLATE_DIMENSION_ALIASES
        }
        identities = tuple(
            identity
            for semantic_name in LEGACY_PLATE_DIMENSION_ALIASES
            for identity in resolved[(instance_id, semantic_name)].identities
        )
        try:
            program = compile_mounting_plate(
                MountingPlateDesignSpec(
                    part_id=cad_id,
                    plate_length_mm=dimensions["length_mm"],
                    plate_width_mm=dimensions["width_mm"],
                    plate_thickness_mm=dimensions["thickness_mm"],
                )
            )
        except Exception as exc:
            raise CanonicalCadIntegrityError(str(exc)) from exc
        return program, tuple(identities)

    def _request_hash(self, reconstruction, mappings) -> str:
        return _canonical_request_hash(
            reconstruction.project_id,
            reconstruction.revision,
            reconstruction.state_hash,
            reconstruction.canonical_mechanism.id,
            reconstruction.canonical_mechanism.mechanism_hash,
            mappings,
            self.compiler_identity,
            self.compiler_version,
        )

    @staticmethod
    def _cad_id(mechanism_id: str, physical_instance_id: str) -> str:
        readable = _SAFE_ID.sub("-", f"canonical-{mechanism_id}-{physical_instance_id}").strip("-")
        if not readable or not readable[0].isalpha():
            readable = f"canonical-{readable}"
        digest = hashlib.sha256(f"{mechanism_id}:{physical_instance_id}".encode()).hexdigest()[:12]
        return f"{readable[:100]}-{digest}"


__all__ = [
    "CanonicalCadInstanceMapping",
    "CanonicalCadIntegrityError",
    "CanonicalCadModel",
    "CanonicalCadRealization",
    "CanonicalCadRealizationV2",
    "CanonicalPhysicalCadMappingV2",
    "CanonicalPhysicalCadCompiler",
    "CanonicalPhysicalCadMapping",
    "canonical_cad_realization_hash_v2",
    "canonical_physical_cad_mapping_hash_v2",
    "semantic_canonical_cad_request_hash",
    "semantic_canonical_placement_hash",
    "validate_canonical_cad_compiler_literals",
]
