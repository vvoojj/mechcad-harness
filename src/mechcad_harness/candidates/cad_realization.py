from __future__ import annotations

import hashlib
import math
from enum import StrEnum
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from mechcad_harness.cad_assembly import CadAssemblyProgram, CadRigidTransform, assembly_hash
from mechcad_harness.cad_assembly import CadComponentInstance
from mechcad_harness.cad_compilation import MountingPlateDesignSpec, compile_mounting_plate
from mechcad_harness.cad_program import cad_program_hash
from mechcad_harness.candidates.models import (
    CandidateSourceBinding,
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
    ComponentPropertyAvailability,
    ComponentSpecificationSnapshot,
    MechanicalDesignCandidate,
)
from mechcad_harness.candidates.services import (
    CandidateCurrentness,
    CandidateCurrentnessService,
    CandidateIntegrityError,
    CandidateIntegrityVerifier,
)
from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.imported_component import (
    ImportedComponentError,
    ImportedCadComponent,
    imported_component_hash,
    resolve_imported_component,
)
from mechcad_harness.models.common import Model
from mechcad_harness.state.hashing import canonical_json


def _hash(value: object, identity_field: str | None = None) -> str:
    payload = value.model_dump(mode="json") if isinstance(value, Model) else value
    payload = dict(payload)
    if identity_field is not None:
        payload.pop(identity_field, None)
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def _require_hash(value: str) -> str:
    if len(value) != 71 or not value.startswith("sha256:"):
        raise ValueError("must be a sha256 hash")
    if any(character not in "0123456789abcdef" for character in value[7:]):
        raise ValueError("must be a sha256 hash")
    return value


def _require_hash_or_pending(value: str) -> str:
    return value if value == "pending" else _require_hash(value)


def _require_nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty or whitespace")
    return value


class CandidateCadIntegrityError(CandidateIntegrityError):
    """The candidate or one of its trusted CAD inputs failed closed."""


class CandidateCadRealizationService:
    """Realize a current candidate through existing generic CAD contracts."""

    _GENERATED_COMPONENT_TYPES = frozenset({"fixture", "mount", "support-mount", "driven-body"})
    _DIMENSION_ALIASES = {
        "length_mm": ("geometry.length_mm", "plate_length_mm", "length_mm"),
        "width_mm": ("geometry.width_mm", "plate_width_mm", "width_mm"),
        "thickness_mm": ("geometry.thickness_mm", "plate_thickness_mm", "thickness_mm"),
    }

    def __init__(self, workspace, project_id: str, state_manager, provider_identity: str = "candidate-cad-realization@1"):
        self.workspace = workspace
        self.project_id = project_id
        self.state_manager = state_manager
        self.provider_identity = provider_identity
        self._lookup_store = ArtifactStore(workspace, project_id=project_id, run_id="_candidate-cad")

    def realize(
        self,
        candidate: MechanicalDesignCandidate,
        synthesis_request: CandidateSynthesisRequest,
        synthesis_policy: CandidateSynthesisPolicy,
        request: "CandidateCadRealizationRequest",
    ) -> "CandidateCadStageOutcome":
        self._verify_candidate(candidate, synthesis_request, synthesis_policy, request)

        return self._realize_current(candidate, request)

    def validate_realization(self, candidate, request, realization) -> None:
        """Rebuild a candidate CAD result from current trusted inputs."""
        try:
            candidate = MechanicalDesignCandidate.model_validate(candidate.model_dump(mode="json"))
            request = CandidateCadRealizationRequest.model_validate(request.model_dump(mode="json"))
            realization = CandidateCadRealization.model_validate(realization.model_dump(mode="json"))
            if request.candidate_hash != candidate.candidate_hash:
                raise CandidateCadIntegrityError("CAD request candidate binding mismatch")
            if request.source_binding != candidate.source_binding:
                raise CandidateCadIntegrityError("CAD request source binding mismatch")
            if request.source_binding.project_id != self.project_id:
                raise CandidateCadIntegrityError("candidate source project does not match realization project")
            if realization.candidate_hash != candidate.candidate_hash:
                raise CandidateCadIntegrityError("CAD realization candidate binding mismatch")
            if realization.request_hash != request.request_hash:
                raise CandidateCadIntegrityError("CAD realization request identity mismatch")
            if realization.mappings != request.mappings:
                raise CandidateCadIntegrityError("CAD realization mapping manifest mismatch")
            self._validate_request_input_identities(candidate, request)
            expected = self._realize_current(candidate, request)
            if expected.status is not CandidateCadStageStatus.SUCCESS or expected.realization != realization:
                raise CandidateCadIntegrityError("candidate CAD realization replay mismatch")
        except CandidateCadIntegrityError:
            raise
        except Exception as exc:
            raise CandidateCadIntegrityError(str(exc) or "candidate CAD replay integrity failure") from exc

    def _realize_current(self, candidate, request):

        specifications = {
            specification.specification_hash: specification
            for specification in candidate.component_specifications
        }
        parts = []
        imported_components = []
        instances = []
        verified_sources = []
        unresolved_reasons: list[CandidateCadStageReason] = []

        for mapping in request.mappings:
            physical = next(
                component
                for component in candidate.realization.components
                if component.instance_id == mapping.physical_instance_id
            )
            specification = specifications[physical.specification_hash]
            placement_error = self._placement_error(candidate, mapping)
            if placement_error:
                return CandidateCadStageOutcome(
                    status=CandidateCadStageStatus.UNRESOLVED,
                    reasons=(CandidateCadStageReason.INVALID_PLACEMENT_PROVENANCE,),
                )

            if specification.geometry_source is not None:
                imported, reason = self._resolve_trusted_source(specification, mapping, candidate)
                if reason is not None:
                    unresolved_reasons.append(reason)
                    continue
                assert imported is not None
                imported_components.append(imported)
                verified_sources.append(imported.artifact_hash)
                expected_representation = imported_component_hash(imported)
                if mapping.representation_identity != expected_representation:
                    raise CandidateCadIntegrityError("trusted imported representation identity mismatch")
                instances.append(
                    CadComponentInstance(
                        instance_id=mapping.cad_instance_id,
                        part_id=mapping.cad_instance_id,
                        placement=mapping.placement,
                    )
                )
                continue

            if mapping.fidelity is not CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION:
                unresolved_reasons.append(CandidateCadStageReason.UNSUPPORTED_REPRESENTATION)
                continue
            generated, reason = self._compile_generated(specification, mapping, candidate)
            if reason is not None:
                unresolved_reasons.append(reason)
                continue
            assert generated is not None
            parts.append(generated)
            instances.append(
                CadComponentInstance(
                    instance_id=mapping.cad_instance_id,
                    part_id=generated.part_id,
                    placement=mapping.placement,
                )
            )

        if unresolved_reasons:
            return CandidateCadStageOutcome(
                status=CandidateCadStageStatus.UNRESOLVED,
                reasons=tuple(dict.fromkeys(unresolved_reasons)),
            )

        assembly = CadAssemblyProgram(
            assembly_id=f"candidate-cad-{candidate.candidate_hash[7:23]}",
            parts=tuple(parts),
            imported_components=tuple(imported_components),
            instances=tuple(instances),
        )
        realization = CandidateCadRealization(
            candidate_hash=candidate.candidate_hash,
            request_hash=request.request_hash,
            mappings=request.mappings,
            assembly=assembly,
            assembly_hash=assembly_hash(assembly),
            verified_source_content_identities=tuple(verified_sources),
            compiler_identity=request.compiler_identity,
            compiler_version=request.compiler_version,
            provider_identity=self.provider_identity,
        )
        return CandidateCadStageOutcome(
            status=CandidateCadStageStatus.SUCCESS,
            realization=realization,
        )

    def _verify_candidate(self, candidate, synthesis_request, synthesis_policy, request) -> None:
        try:
            CandidateIntegrityVerifier().verify(candidate, synthesis_request, synthesis_policy)
            CandidateCadRealizationRequest.model_validate(request.model_dump(mode="json"))
            if request.candidate_hash != candidate.candidate_hash:
                raise CandidateCadIntegrityError("CAD request is bound to a different candidate")
            if request.source_binding != candidate.source_binding:
                raise CandidateCadIntegrityError("CAD request source binding mismatch")
            if request.source_binding.project_id != self.project_id:
                raise CandidateCadIntegrityError("candidate source project does not match realization project")
            candidate_instance_ids = {
                component.instance_id for component in candidate.realization.components
            }
            if set(request.candidate_instance_ids) != candidate_instance_ids:
                raise CandidateCadIntegrityError("CAD request must map every candidate physical instance")
            self._validate_request_input_identities(candidate, request)
            currentness = CandidateCurrentnessService(self.state_manager).evaluate(
                candidate, synthesis_request, synthesis_policy
            )
            if currentness is not CandidateCurrentness.CURRENT:
                raise CandidateCadIntegrityError(
                    f"candidate is not current: {currentness.value}"
                )
        except CandidateCadIntegrityError:
            raise
        except CandidateIntegrityError as exc:
            raise CandidateCadIntegrityError(str(exc)) from exc
        except Exception as exc:
            raise CandidateCadIntegrityError(str(exc) or "candidate CAD integrity failure") from exc

    def _validate_request_input_identities(self, candidate, request) -> None:
        specifications = {
            specification.specification_hash: specification
            for specification in candidate.component_specifications
        }
        components = {
            component.instance_id: component
            for component in candidate.realization.components
        }
        candidate_design_variable_identities = {
            f"candidate:design-variable:{variable.name}"
            for variable in candidate.design_variables
        }
        candidate_interface_identities = {
            f"candidate:component-interface:{component.instance_id}:{interface}"
            for component in candidate.realization.components
            for interface in (
                set(component.interfaces)
                & set(specifications[component.specification_hash].interfaces)
            )
        }
        declared_inputs = {
            identity
            for mapping in request.mappings
            for identity in (
                mapping.geometry_definition_identities
                + mapping.placement_origin.input_identities
            )
        }
        requested_design_variable_identities = set(request.design_variable_identities)
        requested_interface_identities = set(request.component_interface_identities)

        for mapping in request.mappings:
            specification = specifications[components[mapping.physical_instance_id].specification_hash]
            if (
                mapping.fidelity is CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY
                and specification.geometry_source is not None
                and mapping.source_geometry_identity != specification.geometry_source.artifact_hash
            ):
                raise CandidateCadIntegrityError("candidate source geometry identity mismatch")
            if (
                mapping.fidelity is CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY
                and specification.geometry_source is not None
                and mapping.geometry_definition_identities
                != (specification.geometry_source.artifact_id,)
            ):
                raise CandidateCadIntegrityError("trusted geometry definition identities are not component-scoped")
            self._validate_placement_provenance(candidate, request, specifications, components)

        if not requested_design_variable_identities <= candidate_design_variable_identities:
            raise CandidateCadIntegrityError(
                "CAD request contains a foreign design variable identity"
            )
        if not requested_interface_identities <= candidate_interface_identities:
            raise CandidateCadIntegrityError(
                "CAD request contains a foreign component interface identity"
            )

        declared_design_variable_identities = (
            declared_inputs & candidate_design_variable_identities
        )
        declared_interface_identities = declared_inputs & candidate_interface_identities
        if requested_design_variable_identities != declared_design_variable_identities:
            raise CandidateCadIntegrityError(
                "CAD request design variable identities do not match declared realization inputs"
            )
        if requested_interface_identities != declared_interface_identities:
            raise CandidateCadIntegrityError(
                "CAD request component interface identities do not match declared realization inputs"
            )

    @staticmethod
    def _validate_placement_provenance(candidate, request, specifications, components) -> None:
        for mapping in request.mappings:
            component = components[mapping.physical_instance_id]
            specification = specifications[component.specification_hash]
            placement_variables = {
                f"candidate:design-variable:{variable.name}"
                for variable in candidate.design_variables
                if variable.name in {
                    f"{mapping.physical_instance_id}.placement.{axis}"
                    for axis in ("x_mm", "y_mm", "z_mm")
                }
                or variable.name in {
                    f"placement.{mapping.physical_instance_id}.{axis}"
                    for axis in ("x_mm", "y_mm", "z_mm")
                }
            }
            component_interfaces = {
                f"candidate:component-interface:{mapping.physical_instance_id}:{interface}"
                for interface in set(component.interfaces) & set(specification.interfaces)
            }
            source_authority_inputs = set()
            allowed = {
                f"candidate:/realization/components/{mapping.physical_instance_id}",
                f"candidate:placement:{mapping.physical_instance_id}",
                *placement_variables,
                *component_interfaces,
                f"candidate:policy:{request.representation_policy_version}",
            }
            if specification.geometry_source is not None:
                source_authority_inputs = {
                    specification.geometry_source.artifact_id,
                    specification.geometry_source.artifact_hash,
                    f"candidate:source-authority:{specification.geometry_source.source_identity}",
                }
                allowed.update(source_authority_inputs)
            identities = set(mapping.placement_origin.input_identities)
            if not identities <= allowed:
                raise CandidateCadIntegrityError(
                    "CAD mapping contains a foreign or irrelevant placement provenance identity"
                )
            authority_inputs = {
                "source_authority": identities & source_authority_inputs,
                "candidate_design_variable": identities & placement_variables,
                "candidate_interface": identities & component_interfaces,
                "explicit_policy_assumption": identities & {
                    f"candidate:policy:{request.representation_policy_version}"
                },
            }
            required = authority_inputs.get(mapping.placement_origin.authority)
            if required is not None and not required:
                raise CandidateCadIntegrityError(
                    "CAD placement provenance authority is not owned by its mapping"
                )

    def _resolve_trusted_source(self, specification, mapping, candidate):
        source = specification.geometry_source
        assert source is not None
        if mapping.fidelity is not CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY:
            return None, CandidateCadStageReason.UNSUPPORTED_REPRESENTATION
        if mapping.source_geometry_identity != source.artifact_hash:
            raise CandidateCadIntegrityError("candidate source geometry identity mismatch")
        if mapping.geometry_definition_identities != (source.artifact_id,):
            raise CandidateCadIntegrityError("trusted geometry definition identity mismatch")
        artifact = self._lookup_store.existing_in_project(source.artifact_id)
        if artifact is None:
            raise CandidateCadIntegrityError("trusted source artifact is missing or failed integrity verification")
        if artifact.artifact_type is not ArtifactType.STEP:
            raise CandidateCadIntegrityError("trusted source artifact is not a STEP")
        if artifact.sha256 != source.artifact_hash:
            raise CandidateCadIntegrityError("trusted source artifact hash mismatch")
        if (
            artifact.project_id != candidate.source_binding.project_id
            or artifact.bound_revision != candidate.source_binding.source_revision
            or artifact.bound_state_hash != candidate.source_binding.source_state_hash
        ):
            raise CandidateCadIntegrityError("trusted source artifact binding mismatch")
        try:
            store = ArtifactStore(self.workspace, project_id=self.project_id, run_id=artifact.run_id)
            imported = resolve_imported_component(
                source.artifact_id,
                source.artifact_hash,
                store,
                component_id=mapping.cad_instance_id,
            )
        except ImportedComponentError as exc:
            raise CandidateCadIntegrityError(str(exc)) from exc
        return imported, None

    def _compile_generated(self, specification, mapping, candidate):
        if specification.component_type not in self._GENERATED_COMPONENT_TYPES:
            return None, CandidateCadStageReason.UNSUPPORTED_REPRESENTATION
        dimensions = self._generated_dimensions(specification, mapping.physical_instance_id, candidate)
        if dimensions is None:
            return None, CandidateCadStageReason.GEOMETRY_UNAVAILABLE
        values, identities = dimensions
        if set(mapping.geometry_definition_identities) != set(identities):
            raise CandidateCadIntegrityError("generated geometry definition identities mismatch")
        try:
            spec = MountingPlateDesignSpec(
                part_id=mapping.cad_instance_id,
                plate_length_mm=values["length_mm"],
                plate_width_mm=values["width_mm"],
                plate_thickness_mm=values["thickness_mm"],
            )
            program = compile_mounting_plate(spec)
        except Exception as exc:
            raise CandidateCadIntegrityError(str(exc)) from exc
        if mapping.representation_identity != cad_program_hash(program):
            raise CandidateCadIntegrityError("generated CAD representation identity mismatch")
        return program, None

    def _generated_dimensions(self, specification, physical_instance_id, candidate):
        properties = {property.key: property for property in specification.properties}
        values = {}
        identities = []
        for dimension, aliases in self._DIMENSION_ALIASES.items():
            property = next((properties[alias] for alias in aliases if alias in properties), None)
            if property is not None:
                if (
                    property.availability is not ComponentPropertyAvailability.AVAILABLE
                    or property.normalized_value is None
                    or property.canonical_unit != "mm"
                    or not math.isfinite(property.normalized_value)
                    or property.normalized_value <= 0
                ):
                    return None
                values[dimension] = property.normalized_value
                identities.append(property.property_hash)
                continue
            variable = next(
                (
                    variable
                    for variable in candidate.design_variables
                    if variable.name in (
                        f"{physical_instance_id}.{dimension}",
                        f"{physical_instance_id}.geometry.{dimension}",
                        f"geometry.{physical_instance_id}.{dimension}",
                    )
                ),
                None,
            )
            if variable is None or isinstance(variable.value, bool):
                return None
            try:
                value = float(variable.value)
            except (TypeError, ValueError):
                return None
            if not math.isfinite(value) or value <= 0:
                return None
            values[dimension] = value
            identities.append(f"candidate:design-variable:{variable.name}")
        return values, tuple(identities)

    def _placement_error(self, candidate, mapping) -> bool:
        expected_values = {"x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0}
        provenance_identities = set(mapping.placement_origin.input_identities)
        for axis in expected_values:
            names = (
                f"{mapping.physical_instance_id}.placement.{axis}",
                f"placement.{mapping.physical_instance_id}.{axis}",
            )
            variables = [variable for variable in candidate.design_variables if variable.name in names]
            if variables:
                if len(variables) != 1 or isinstance(variables[0].value, bool):
                    return True
                try:
                    value = float(variables[0].value)
                except (TypeError, ValueError):
                    return True
                if not math.isfinite(value):
                    return True
                expected_values[axis] = value
                if f"candidate:design-variable:{variables[0].name}" not in provenance_identities:
                    return True
        expected = CadRigidTransform(**expected_values)
        return mapping.placement != expected or mapping.placement_origin.transform != expected


class CandidateCadModel(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CandidateGeometryFidelity(StrEnum):
    TRUSTED_SOURCE_GEOMETRY = "trusted_source_geometry"
    DECLARED_BOUNDED_COLLISION_REPRESENTATION = "declared_bounded_collision_representation"


class CandidatePlacementOrigin(CandidateCadModel):
    authority: Literal[
        "source_authority",
        "candidate_design_variable",
        "deterministic_derived_relation",
        "explicit_policy_assumption",
    ]
    input_identities: tuple[str, ...] = Field(min_length=1)
    derivation: str = Field(min_length=1)
    transform: CadRigidTransform
    origin_hash: str = "pending"

    _validate_hash = field_validator("origin_hash")(_require_hash_or_pending)
    _validate_derivation = field_validator("derivation")(_require_nonblank)

    @model_validator(mode="after")
    def validate_origin(self) -> "CandidatePlacementOrigin":
        if any(not value.strip() for value in self.input_identities):
            raise ValueError("placement provenance input identities must not be empty")
        expected = _hash(self, "origin_hash")
        if self.origin_hash == "pending":
            object.__setattr__(self, "origin_hash", expected)
        elif self.origin_hash != expected:
            raise ValueError("placement origin hash mismatch")
        return self


class CandidateCadInstanceMapping(CandidateCadModel):
    schema_version: Literal["candidate-cad-instance-mapping@1"] = "candidate-cad-instance-mapping@1"
    candidate_hash: str
    physical_instance_id: str = Field(min_length=1)
    cad_instance_id: str = Field(min_length=1)
    fidelity: CandidateGeometryFidelity
    representation_identity: str
    source_geometry_identity: str | None = None
    geometry_definition_identities: tuple[str, ...] = Field(min_length=1)
    placement: CadRigidTransform
    placement_origin: CandidatePlacementOrigin
    mapping_hash: str = "pending"

    _validate_hashes = field_validator("candidate_hash", "representation_identity")(_require_hash)
    _validate_mapping_hash = field_validator("mapping_hash")(_require_hash_or_pending)
    _validate_ids = field_validator("physical_instance_id", "cad_instance_id")(_require_nonblank)

    @model_validator(mode="after")
    def validate_mapping(self) -> "CandidateCadInstanceMapping":
        if any(not value.strip() for value in self.geometry_definition_identities):
            raise ValueError("geometry definition identities must not be empty")
        if self.placement != self.placement_origin.transform:
            raise ValueError("placement transform must match its provenance")
        if self.fidelity is CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY:
            if self.source_geometry_identity is None or not self.source_geometry_identity.strip():
                raise ValueError("trusted source geometry requires source geometry identity")
        elif self.source_geometry_identity is not None:
            raise ValueError("bounded collision representation cannot claim source geometry")
        expected = _hash(self, "mapping_hash")
        if self.mapping_hash == "pending":
            object.__setattr__(self, "mapping_hash", expected)
        elif self.mapping_hash != expected:
            raise ValueError("candidate CAD mapping hash mismatch")
        return self


class CandidateCadRealizationRequest(CandidateCadModel):
    schema_version: Literal["candidate-cad-realization-request@1"] = "candidate-cad-realization-request@1"
    candidate_hash: str
    source_binding: CandidateSourceBinding
    source_binding_hash: str = "pending"
    representation_policy_version: str = Field(min_length=1)
    compiler_identity: str = Field(min_length=1)
    compiler_version: str = Field(min_length=1)
    candidate_instance_ids: tuple[str, ...] = Field(min_length=1)
    mappings: tuple[CandidateCadInstanceMapping, ...] = Field(min_length=1)
    design_variable_identities: tuple[str, ...] = ()
    component_interface_identities: tuple[str, ...] = ()
    request_hash: str = "pending"

    _validate_hashes = field_validator("candidate_hash")(_require_hash)
    _validate_derived_hashes = field_validator("source_binding_hash", "request_hash")(_require_hash_or_pending)
    _validate_provenance = field_validator(
        "representation_policy_version", "compiler_identity", "compiler_version"
    )(_require_nonblank)

    @model_validator(mode="after")
    def validate_manifest_and_hash(self) -> "CandidateCadRealizationRequest":
        if any(not value.strip() for value in self.candidate_instance_ids):
            raise ValueError("candidate physical instance IDs must not be empty")
        if len(set(self.candidate_instance_ids)) != len(self.candidate_instance_ids):
            raise ValueError("candidate physical instance IDs must be unique")
        physical_ids = tuple(mapping.physical_instance_id for mapping in self.mappings)
        cad_ids = tuple(mapping.cad_instance_id for mapping in self.mappings)
        if len(set(physical_ids)) != len(physical_ids):
            raise ValueError("candidate physical instance mappings must be unique")
        if len(set(cad_ids)) != len(cad_ids):
            raise ValueError("CAD instance mappings must be unique")
        if set(physical_ids) != set(self.candidate_instance_ids):
            raise ValueError("mapping must cover every candidate physical instance")
        if any(mapping.candidate_hash != self.candidate_hash for mapping in self.mappings):
            raise ValueError("CAD mapping is bound to a different candidate")
        expected_source_hash = _hash(self.source_binding)
        if self.source_binding_hash == "pending":
            object.__setattr__(self, "source_binding_hash", expected_source_hash)
        elif self.source_binding_hash != expected_source_hash:
            raise ValueError("candidate source binding hash mismatch")
        expected = _hash(self, "request_hash")
        if self.request_hash == "pending":
            object.__setattr__(self, "request_hash", expected)
        elif self.request_hash != expected:
            raise ValueError("candidate CAD realization request hash mismatch")
        return self


class CandidateCadRealization(CandidateCadModel):
    schema_version: Literal["candidate-cad-realization@1"] = "candidate-cad-realization@1"
    candidate_hash: str
    request_hash: str
    mappings: tuple[CandidateCadInstanceMapping, ...] = Field(min_length=1)
    assembly: CadAssemblyProgram
    assembly_hash: str
    representation_identities: tuple[str, ...] = ()
    verified_source_content_identities: tuple[str, ...] = ()
    compiler_identity: str = Field(min_length=1)
    compiler_version: str = Field(min_length=1)
    provider_identity: str = Field(min_length=1)
    realization_hash: str = "pending"

    _validate_hashes = field_validator("candidate_hash", "request_hash", "assembly_hash")(_require_hash)
    _validate_realization_hash = field_validator("realization_hash")(_require_hash_or_pending)
    _validate_provenance = field_validator(
        "compiler_identity", "compiler_version", "provider_identity"
    )(_require_nonblank)

    @model_validator(mode="after")
    def validate_realization(self) -> "CandidateCadRealization":
        physical_ids = tuple(mapping.physical_instance_id for mapping in self.mappings)
        cad_ids = tuple(mapping.cad_instance_id for mapping in self.mappings)
        if len(set(physical_ids)) != len(physical_ids):
            raise ValueError("candidate physical instance mappings must be unique")
        if len(set(cad_ids)) != len(cad_ids):
            raise ValueError("CAD instance mappings must be unique")
        if any(mapping.candidate_hash != self.candidate_hash for mapping in self.mappings):
            raise ValueError("CAD mapping is bound to a different candidate")
        assembly_instances = {instance.instance_id: instance for instance in self.assembly.instances}
        if set(cad_ids) != set(assembly_instances):
            raise ValueError("candidate CAD assembly instances must match mappings")
        if any(
            assembly_instances[mapping.cad_instance_id].placement != mapping.placement
            for mapping in self.mappings
        ):
            raise ValueError("candidate CAD assembly placement must match mapping")
        parts_by_id = {part.part_id: part for part in self.assembly.parts}
        imported_by_id = {
            component.component_id: component
            for component in self.assembly.imported_components
        }
        for mapping in self.mappings:
            instance = assembly_instances[mapping.cad_instance_id]
            if mapping.fidelity is CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY:
                imported = imported_by_id.get(instance.part_id)
                if imported is None:
                    raise ValueError(
                        "trusted CAD mapping must reference an imported assembly component"
                    )
                if mapping.representation_identity != imported_component_hash(imported):
                    raise ValueError("candidate CAD imported representation identity mismatch")
            else:
                part = parts_by_id.get(instance.part_id)
                if part is None:
                    raise ValueError(
                        "bounded CAD mapping must reference a CadPartProgram assembly component"
                    )
                if mapping.representation_identity != cad_program_hash(part):
                    raise ValueError("candidate CAD part representation identity mismatch")
        if self.assembly_hash != assembly_hash(self.assembly):
            raise ValueError("candidate CAD assembly hash mismatch")
        if not self.representation_identities:
            object.__setattr__(
                self,
                "representation_identities",
                tuple(mapping.representation_identity for mapping in self.mappings),
            )
        if tuple(self.representation_identities) != tuple(mapping.representation_identity for mapping in self.mappings):
            raise ValueError("candidate CAD representation manifest mismatch")
        for value in self.verified_source_content_identities:
            _require_hash(value)
        trusted_source_geometry_identities = tuple(
            mapping.source_geometry_identity
            for mapping in self.mappings
            if mapping.fidelity is CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY
        )
        if any(identity is None for identity in trusted_source_geometry_identities):
            raise ValueError("trusted source geometry requires source geometry identity")
        trusted_source_geometry_identities = tuple(
            identity for identity in trusted_source_geometry_identities if identity is not None
        )
        if trusted_source_geometry_identities and not self.verified_source_content_identities:
            raise ValueError("trusted source geometry requires verified source content identity")
        if len(self.verified_source_content_identities) != len(trusted_source_geometry_identities):
            if trusted_source_geometry_identities:
                raise ValueError("trusted source geometry identities must bind one-to-one")
            raise ValueError("bounded CAD representation cannot claim verified source content")
        if len(set(trusted_source_geometry_identities)) != len(trusted_source_geometry_identities):
            raise ValueError("trusted source geometry identities must bind one-to-one")
        if tuple(self.verified_source_content_identities) != trusted_source_geometry_identities:
            if trusted_source_geometry_identities:
                raise ValueError("trusted source geometry identity must match verified source content identity")
            if self.verified_source_content_identities:
                raise ValueError("bounded CAD representation cannot claim verified source content")
        expected = _hash(self, "realization_hash")
        if self.realization_hash == "pending":
            object.__setattr__(self, "realization_hash", expected)
        elif self.realization_hash != expected:
            raise ValueError("candidate CAD realization hash mismatch")
        return self


class CandidateCadStageStatus(StrEnum):
    SUCCESS = "success"
    UNRESOLVED = "unresolved"
    NOT_REACHED = "not_reached"


class CandidateCadStageReason(StrEnum):
    GEOMETRY_UNAVAILABLE = "geometry_unavailable"
    UNSUPPORTED_REPRESENTATION = "unsupported_representation"
    INVALID_PLACEMENT_PROVENANCE = "invalid_placement_provenance"
    PRIOR_STAGE_FAILED = "prior_stage_failed"


class CandidateCadStageOutcome(CandidateCadModel):
    schema_version: Literal["candidate-cad-stage-outcome@1"] = "candidate-cad-stage-outcome@1"
    status: CandidateCadStageStatus
    realization: CandidateCadRealization | None = None
    realization_hash: str | None = None
    reasons: tuple[CandidateCadStageReason, ...] = ()
    outcome_hash: str = "pending"

    @field_validator("realization_hash")
    @classmethod
    def validate_realization_hash(cls, value: str | None) -> str | None:
        return None if value is None else _require_hash(value)

    @field_validator("outcome_hash")
    @classmethod
    def validate_outcome_hash(cls, value: str) -> str:
        return _require_hash_or_pending(value)

    @model_validator(mode="after")
    def validate_status_and_hash(self) -> "CandidateCadStageOutcome":
        if self.status is CandidateCadStageStatus.SUCCESS:
            if self.realization is None or self.reasons:
                raise ValueError("successful CAD stage requires exactly one realization")
            expected_realization_hash = self.realization.realization_hash
            if self.realization_hash is None:
                object.__setattr__(self, "realization_hash", expected_realization_hash)
            elif self.realization_hash != expected_realization_hash:
                raise ValueError("CAD stage realization identity mismatch")
        elif self.status is CandidateCadStageStatus.UNRESOLVED:
            if CandidateCadStageReason.PRIOR_STAGE_FAILED in self.reasons:
                raise ValueError("unresolved CAD stage cannot use prior stage reason")
            if self.realization is not None or self.realization_hash is not None:
                raise ValueError("unresolved or unreached CAD stage cannot carry a realization")
            if not self.reasons:
                raise ValueError("unresolved or unreached CAD stage requires a typed reason")
        else:
            if self.realization is not None or self.realization_hash is not None:
                raise ValueError("unresolved or unreached CAD stage cannot carry a realization")
            if self.reasons != (CandidateCadStageReason.PRIOR_STAGE_FAILED,):
                raise ValueError("not-reached CAD stage requires exactly the prior-stage reason")
        expected = _hash(self, "outcome_hash")
        if self.outcome_hash == "pending":
            object.__setattr__(self, "outcome_hash", expected)
        elif self.outcome_hash != expected:
            raise ValueError("candidate CAD stage outcome hash mismatch")
        return self
