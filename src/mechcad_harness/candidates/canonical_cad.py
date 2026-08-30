from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import ConfigDict, Field, StrictInt, StrictStr, field_validator, model_validator

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_compilation import MountingPlateDesignSpec, compile_mounting_plate
from mechcad_harness.cad_program import cad_program_hash
from mechcad_harness.imported_component import (
    ImportedComponentError,
    ImportedCadComponent,
    imported_component_hash,
    resolve_imported_component,
)
from mechcad_harness.models.common import Model
from mechcad_harness.models.physical_mechanism import (
    CanonicalComponentPropertyAvailability,
    CanonicalGeometryFidelity,
)
from mechcad_harness.state.hashing import canonical_json

from .canonical_mechanism import (
    CanonicalMechanismReconstruction,
    ProjectArtifactResolver,
    TrustedSourceArtifact,
)


_SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]+")
_DIMENSION_ALIASES = {
    "length_mm": ("length_mm", "geometry.length_mm", "plate_length_mm"),
    "width_mm": ("width_mm", "geometry.width_mm", "plate_width_mm"),
    "thickness_mm": ("thickness_mm", "geometry.thickness_mm", "plate_thickness_mm"),
}


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

    def realize(self, reconstruction: CanonicalMechanismReconstruction) -> CanonicalCadRealization:
        try:
            if not isinstance(reconstruction, CanonicalMechanismReconstruction):
                raise TypeError("canonical CAD requires a canonical mechanism reconstruction")
            reconstruction = CanonicalMechanismReconstruction.model_validate(
                reconstruction.model_dump(mode="json")
            )
            mechanism = reconstruction.canonical_mechanism
            resolver = self._resolver(reconstruction.project_id)
            sources = {
                source.artifact_id: self._resolve_source(resolver, reconstruction, source)
                for source in reconstruction.trusted_source_references
            }
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
            assemblies = []
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
                    assemblies.append(("imported", imported, transform))
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
                    assemblies.append(("part", program, transform))
                    mappings.append(
                        CanonicalPhysicalCadMapping(
                            mechanism_hash=mechanism.mechanism_hash,
                            physical_instance_id=component.instance_id,
                            cad_instance_id=cad_id,
                            component_hash=component.component_hash,
                            specification_hash=component.specification_hash,
                            fidelity=CanonicalGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
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

            request_hash = self._request_hash(reconstruction, tuple(mappings))
            parts = tuple(value for kind, value, _ in assemblies if kind == "part")
            imported_components = tuple(value for kind, value, _ in assemblies if kind == "imported")
            instances = tuple(
                CadComponentInstance(
                    instance_id=mapping.cad_instance_id,
                    part_id=mapping.cad_instance_id,
                    placement=mapping.placement.model_copy(deep=True),
                )
                for mapping in mappings
            )
            assembly = CadAssemblyProgram(
                assembly_id=f"canonical-assembly-{request_hash[7:23]}",
                parts=parts,
                imported_components=imported_components,
                instances=instances,
            )
            provenance = tuple(
                sources[artifact_id][1]
                for artifact_id in sorted(sources)
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

    def _resolver(self, project_id: str) -> ProjectArtifactResolver:
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

    def _compile_generated(self, specification, instance_id, cad_id, mechanism):
        if specification.component_type not in self._GENERATED_COMPONENT_TYPES:
            raise CanonicalCadIntegrityError(
                f"canonical component type is not supported for generated CAD: {specification.component_type}"
            )
        dimensions = {}
        identities = []
        choices = {choice.key: choice for choice in mechanism.accepted_design_choices}
        properties = {property.key: property for property in specification.properties}
        for dimension, aliases in _DIMENSION_ALIASES.items():
            choice = next(
                (
                    choices[key]
                    for alias in aliases
                    for key in (
                        f"{instance_id}.{alias}",
                        f"{instance_id}.geometry.{alias.removeprefix('geometry.')}",
                        f"geometry.{instance_id}.{alias.removeprefix('geometry.')}",
                    )
                    if key in choices
                ),
                None,
            )
            if choice is not None:
                value = choice.value
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise CanonicalCadIntegrityError("canonical geometry choice must be numeric")
                if value <= 0:
                    raise CanonicalCadIntegrityError("canonical geometry choice must be positive")
                dimensions[dimension] = float(value)
                identities.append(choice.choice_hash)
                continue

            property_value = next(
                (properties[alias] for alias in aliases if alias in properties), None
            )
            if (
                property_value is None
                or property_value.availability is not CanonicalComponentPropertyAvailability.AVAILABLE
                or property_value.normalized_value is None
                or property_value.canonical_unit != "mm"
                or property_value.normalized_value <= 0
            ):
                raise CanonicalCadIntegrityError(
                    f"canonical geometry is unavailable for {instance_id}.{dimension}"
                )
            dimensions[dimension] = property_value.normalized_value
            identities.append(property_value.property_hash)
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
    "CanonicalPhysicalCadCompiler",
    "CanonicalPhysicalCadMapping",
]
