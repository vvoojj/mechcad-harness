from __future__ import annotations

import hashlib
import math
from dataclasses import replace
from enum import StrEnum
from numbers import Real
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_serializer, model_validator

from mechcad_harness.cad_assembly import CadAssemblyProgram, CadRigidTransform, assembly_hash
from mechcad_harness.cad_assembly import CadComponentInstance
from mechcad_harness.cad_compilation import MountingPlateDesignSpec, compile_mounting_plate
from mechcad_harness.cad_program import cad_program_hash
from mechcad_harness.generated_part_cad import compile_generated_part
from mechcad_harness.candidates.dimensions import (
    LEGACY_PLATE_DIMENSION_ALIASES,
    DimensionConflictError,
    DimensionInput,
    DimensionResolutionError,
    resolve_dimensions,
)
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
    candidate_cad_required_raw_source_identities,
)
from mechcad_harness.candidates.generated_authority import (
    build_candidate_view,
    candidate_placement_design_variables,
    m13_local_pose,
)
from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.imported_component import (
    ImportedComponentError,
    ImportedCadComponent,
    imported_component_hash,
    resolve_imported_component,
)
from mechcad_harness.models.common import Model
from mechcad_harness.models.generated_part import (
    GeneratedAuthorityView,
    GeneratedAttachmentFaceInterface,
    GeneratedRotationalInterface,
    generated_geometry_definition_identities,
)
from mechcad_harness.models.generated_placement import (
    GeneratedPlacementDerivation,
    _rotation_aligning,
    _resolve_rotation_input,
    compose_poses,
    place_generated_target,
    pose_from_interface,
    placement_derivations_hash,
    resolve_placement_inputs,
)
from mechcad_harness.models.supplied_component_interface import (
    require_authoritatively_consumable_interface,
)
from mechcad_harness.step_content_identity import step_content_identity_v1
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


def _require_optional_hash(value: str | None) -> str | None:
    if value is None:
        return None
    return _require_hash(value)


def _require_nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty or whitespace")
    return value


class CandidateCadIntegrityError(CandidateIntegrityError):
    """The candidate or one of its trusted CAD inputs failed closed."""


class CandidateCadRealizationService:
    """Realize a current candidate through existing generic CAD contracts."""

    _GENERATED_COMPONENT_TYPES = frozenset({"fixture", "mount", "support-mount", "driven-body"})

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
        request: "CandidateCadRealizationRequest | CandidateCadRealizationRequestV3",
    ) -> "CandidateCadStageOutcome | CandidateCadStageOutcomeV2":
        self._verify_candidate(candidate, synthesis_request, synthesis_policy, request)
        return self._realize_current(candidate, request)

    def validate_realization(self, candidate, request, realization) -> None:
        """Rebuild a candidate CAD result from current trusted inputs."""
        try:
            candidate = MechanicalDesignCandidate.model_validate(candidate.model_dump(mode="json"))
            semantic_family = (
                request.schema_version == "candidate-cad-realization-request@3"
            )
            if semantic_family:
                if candidate.schema_version != "mechanical-design-candidate@2":
                    raise CandidateCadIntegrityError(
                        "request@3 CAD replay requires candidate@2"
                    )
                request = CandidateCadRealizationRequestV3.model_validate(
                    request.model_dump(mode="json")
                )
                realization = CandidateCadRealizationV2.model_validate(
                    realization.model_dump(mode="json")
                )
            else:
                if candidate.schema_version == "mechanical-design-candidate@2":
                    raise CandidateCadIntegrityError(
                        "candidate@2 CAD replay requires request@3"
                    )
                request = CandidateCadRealizationRequest.model_validate(
                    request.model_dump(mode="json")
                )
                realization = CandidateCadRealization.model_validate(
                    realization.model_dump(mode="json")
                )
            if request.candidate_hash != candidate.candidate_hash:
                raise CandidateCadIntegrityError("CAD request candidate binding mismatch")
            if request.source_binding != candidate.source_binding:
                raise CandidateCadIntegrityError("CAD request source binding mismatch")
            if semantic_family and (
                request.semantic_source_binding_hash
                != candidate.semantic_source_binding_hash
            ):
                raise CandidateCadIntegrityError(
                    "CAD request semantic source binding mismatch"
                )
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
        semantic_family = (
            request.schema_version == "candidate-cad-realization-request@3"
        )
        specifications = {
            specification.specification_hash: specification
            for specification in candidate.component_specifications
        }
        parts = []
        generated_part_ids = set()
        imported_components = []
        instances = []
        verified_sources = []
        verified_source_contents = []
        verified_source_artifact_hashes: dict[str, str] = {}
        unresolved_reasons: list[CandidateCadStageReason] = []

        for mapping in request.mappings:
            physical = next(
                component
                for component in candidate.realization.components
                if component.instance_id == mapping.physical_instance_id
            )
            specification = specifications[physical.specification_hash]
            derivation = next(
                (
                    item
                    for item in request.placement_derivations
                    if item.target_physical_instance_id == mapping.physical_instance_id
                ),
                None,
            )
            if (
                request.schema_version.endswith("@2")
                or semantic_family
            ) and (
                specification.generated_part is not None
                and derivation is None
            ):
                return self._stage_outcome(
                    request,
                    CandidateCadStageStatus.UNRESOLVED,
                    reasons=(CandidateCadStageReason.INVALID_PLACEMENT_PROVENANCE,),
                )
            if derivation is not None:
                try:
                    self._derived_placement(request, mapping, specifications, candidate)
                except CandidateCadIntegrityError:
                    return self._stage_outcome(
                        request,
                        CandidateCadStageStatus.UNRESOLVED,
                        reasons=(CandidateCadStageReason.INVALID_PLACEMENT_PROVENANCE,),
                    )
                except Exception:
                    unresolved_reasons.append(CandidateCadStageReason.GEOMETRY_UNAVAILABLE)
                    continue
            elif self._placement_error(candidate, mapping):
                return self._stage_outcome(
                    request,
                    CandidateCadStageStatus.UNRESOLVED,
                    reasons=(CandidateCadStageReason.INVALID_PLACEMENT_PROVENANCE,),
                )

            if specification.geometry_source is not None:
                if semantic_family:
                    imported, reason, content_identity, source_artifact_id = (
                        self._resolve_trusted_source_v2(
                            specification, mapping, candidate
                        )
                    )
                    if reason is None:
                        verified_source_contents.append(content_identity)
                        verified_source_artifact_hashes[source_artifact_id] = (
                            imported.artifact_hash
                        )
                else:
                    imported, reason = self._resolve_trusted_source(
                        specification, mapping, candidate
                    )
                if reason is not None:
                    unresolved_reasons.append(reason)
                    continue
                assert imported is not None
                imported_components.append(imported)
                if not semantic_family:
                    verified_sources.append(imported.artifact_hash)
                expected_representation = (
                    trusted_representation_identity(
                        slot=mapping.cad_instance_id,
                        content_identity=content_identity,
                    )
                    if semantic_family
                    else imported_component_hash(imported)
                )
                if mapping.representation_identity != expected_representation:
                    raise CandidateCadIntegrityError(
                        "trusted imported representation identity mismatch"
                    )
                instances.append(
                    CadComponentInstance(
                        instance_id=mapping.cad_instance_id,
                        part_id=mapping.cad_instance_id,
                        placement=mapping.placement,
                    )
                )
                continue

            if (
                specification.generated_part is None
                and mapping.fidelity
                is not CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION
            ):
                unresolved_reasons.append(CandidateCadStageReason.UNSUPPORTED_REPRESENTATION)
                continue
            generated, reason = self._compile_generated(specification, mapping, candidate)
            if reason is not None:
                unresolved_reasons.append(reason)
                continue
            assert generated is not None
            if specification.generated_part is None or generated.part_id not in generated_part_ids:
                parts.append(generated)
                if specification.generated_part is not None:
                    generated_part_ids.add(generated.part_id)
            instances.append(
                CadComponentInstance(
                    instance_id=mapping.cad_instance_id,
                    part_id=generated.part_id,
                    placement=mapping.placement,
                )
            )

        if unresolved_reasons:
            return self._stage_outcome(
                request,
                CandidateCadStageStatus.UNRESOLVED,
                reasons=tuple(dict.fromkeys(unresolved_reasons)),
            )

        if semantic_family:
            required_raw_sources = candidate_cad_required_raw_source_identities(
                candidate,
                state_manager=self.state_manager,
                project_id=self.project_id,
            )
            verified_raw_hashes = {}
            for artifact_id, identity in sorted(required_raw_sources.items()):
                if identity.format != "step":
                    raise CandidateCadIntegrityError(
                        "candidate CAD raw source is not a STEP artifact"
                    )
                try:
                    verified = self._lookup_store.read_verified_in_project(
                        artifact_id,
                        expected_type=ArtifactType.STEP,
                        expected_hash=identity.artifact_hash,
                    )
                except Exception as exc:
                    raise CandidateCadIntegrityError(
                        f"candidate CAD required raw source verification failed: {exc}"
                    ) from exc
                if verified is None:
                    raise CandidateCadIntegrityError(
                        "candidate CAD required raw source is missing or ambiguous"
                    )
                artifact, _ = verified
                if (
                    artifact.project_id != candidate.source_binding.project_id
                    or artifact.artifact_id != artifact_id
                    or artifact.artifact_type is not ArtifactType.STEP
                    or artifact.sha256 != identity.artifact_hash
                    or artifact.bound_revision
                    != candidate.source_binding.source_revision
                    or artifact.bound_state_hash
                    != candidate.source_binding.source_state_hash
                ):
                    raise CandidateCadIntegrityError(
                        "candidate CAD required raw source binding mismatch"
                    )
                verified_raw_hashes[artifact_id] = artifact.sha256
            verified_source_artifact_hashes = verified_raw_hashes

        assembly = CadAssemblyProgram(
            assembly_id=f"candidate-cad-{candidate.candidate_hash[7:23]}",
            parts=tuple(parts),
            imported_components=tuple(imported_components),
            instances=tuple(instances),
        )
        if semantic_family:
            ordered_mappings = tuple(
                sorted(request.mappings, key=lambda item: item.physical_instance_id)
            )
            realization = CandidateCadRealizationV2(
                candidate_hash=candidate.candidate_hash,
                request_hash=request.request_hash,
                mappings=ordered_mappings,
                assembly=assembly,
                assembly_hash=assembly_hash(assembly),
                representation_identities=tuple(
                    mapping.representation_identity for mapping in ordered_mappings
                ),
                semantic_placement_derivations_hash=(
                    request.semantic_placement_derivations_hash
                ),
                verified_source_content_identities=tuple(
                    dict.fromkeys(verified_source_contents)
                ),
                verified_source_artifact_hashes=tuple(
                    verified_source_artifact_hashes.values()
                ),
                compiler_identity=request.compiler_identity,
                compiler_version=request.compiler_version,
                provider_identity=self.provider_identity,
            )
        else:
            realization = CandidateCadRealization(
                candidate_hash=candidate.candidate_hash,
                request_hash=request.request_hash,
                mappings=request.mappings,
                assembly=assembly,
                assembly_hash=assembly_hash(assembly),
                placement_derivations_hash=request.placement_derivations_hash,
                verified_source_content_identities=tuple(dict.fromkeys(verified_sources)),
                compiler_identity=request.compiler_identity,
                compiler_version=request.compiler_version,
                provider_identity=self.provider_identity,
            )
        return self._stage_outcome(
            request,
            CandidateCadStageStatus.SUCCESS,
            realization=realization,
        )

    @staticmethod
    def _stage_outcome(request, status, *, realization=None, reasons=()):
        if request.schema_version == "candidate-cad-realization-request@3":
            return CandidateCadStageOutcomeV2(
                status=status, realization=realization, reasons=reasons
            )
        return CandidateCadStageOutcome(
            status=status, realization=realization, reasons=reasons
        )

    def _derived_placement(self, request, mapping, specifications, candidate):
        derivations = {
            item.derivation_id: item for item in request.placement_derivations
        }
        target_derivation = next(
            (
                item
                for item in request.placement_derivations
                if item.target_physical_instance_id == mapping.physical_instance_id
            ),
            None,
        )
        if target_derivation is None:
            raise ValueError("generated placement derivation target is missing")
        components = {
            component.instance_id: component
            for component in candidate.realization.components
        }
        def design_variable_placement(instance_id):
            if instance_id not in components:
                raise ValueError("source physical instance cannot be resolved")
            return CadRigidTransform(**candidate_placement_design_variables(candidate, instance_id))

        def supplied_frame(specification, frame_ref):
            frames = tuple(specification.supplied_reference_frames)
            matches = tuple(
                frame
                for frame in frames
                if frame.frame_id == frame_ref.frame_id
                and frame.frame_hash == frame_ref.frame_hash
            )
            if len(matches) != 1:
                raise ValueError("source supplied frame cannot be resolved by exact ID and hash")
            return matches[0]

        def supplied_interface(specification, reference):
            definitions = tuple(specification.supplied_interface_definitions)
            matches = tuple(
                definition
                for definition in definitions
                if definition.interface_id == reference.interface_id
                and definition.interface_hash == reference.interface_hash
            )
            if len(matches) != 1:
                raise ValueError("source supplied interface cannot be resolved by exact ID and hash")
            definition = matches[0]
            variant = definition.shaft or definition.mounting_face
            if variant is None:
                raise ValueError("source supplied interface has no variant")
            active_frame_id = getattr(variant, "reference_frame_id", None)
            active_frame = None
            if active_frame_id is not None:
                active_frame = next(
                    (
                        frame
                        for frame in specification.supplied_reference_frames
                        if frame.frame_id == active_frame_id
                    ),
                    None,
                )
                if active_frame is None:
                    raise ValueError("source supplied interface frame cannot be resolved")
            require_authoritatively_consumable_interface(definition, active_frame)
            return definition, variant, active_frame

        def source_local_pose(specification, derivation):
            definition = None
            variant = None
            if specification.generated_part is not None:
                interfaces = tuple(specification.generated_part.interfaces)
                matches = tuple(
                    interface
                    for interface in interfaces
                    if interface.interface_id == derivation.source_interface_ref.interface_id
                    and interface.interface_hash == derivation.source_interface_ref.interface_hash
                )
                if len(matches) != 1:
                    raise ValueError("source generated interface cannot be resolved by exact ID and hash")
                interface = matches[0]
            else:
                definition, variant, active_frame = supplied_interface(
                    specification, derivation.source_interface_ref
                )
                interface = variant

            if derivation.rule_id == "frame-generated-placement@1":
                frame_ref = derivation.source_frame_ref
                if frame_ref is None:
                    raise ValueError("source frame is missing")
                if specification.generated_part is not None:
                    frames = tuple(specification.generated_part.reference_frames)
                    matches = tuple(
                        frame
                        for frame in frames
                        if frame.frame_id == frame_ref.frame_id
                        and frame.frame_hash == frame_ref.frame_hash
                    )
                    if len(matches) != 1:
                        raise ValueError("source generated frame cannot be resolved by exact ID and hash")
                    return pose_from_interface(matches[0])
                if definition is None or variant is None:
                    raise ValueError("source frame interface is missing")
                if getattr(variant, "reference_frame_id", None) != frame_ref.frame_id:
                    raise ValueError("source frame is not owned by the source interface")
                frame = supplied_frame(specification, frame_ref)
                require_authoritatively_consumable_interface(definition, frame)
                return m13_local_pose(frame)

            if isinstance(interface, GeneratedRotationalInterface):
                return pose_from_interface(interface)
            if isinstance(interface, GeneratedAttachmentFaceInterface):
                return pose_from_interface(interface)
            return m13_local_pose(definition, active_frame)

        def target_local_pose(specification, derivation, view):
            generated = specification.generated_part
            if generated is None:
                raise ValueError("derived placement target is not generated")
            if derivation.rule_id == "coaxial-generated-placement@1":
                reference = derivation.target_generated_interface_ref
                records = tuple(generated.interfaces)
            else:
                reference = derivation.target_generated_frame_ref
                records = tuple(generated.reference_frames)
            if reference is None:
                raise ValueError("generated placement target reference is missing")
            id_name = "interface_id" if derivation.rule_id == "coaxial-generated-placement@1" else "frame_id"
            hash_name = "interface_hash" if derivation.rule_id == "coaxial-generated-placement@1" else "frame_hash"
            matches = tuple(
                record
                for record in records
                if getattr(record, id_name) == getattr(reference, id_name)
                and getattr(record, hash_name) == getattr(reference, hash_name)
            )
            if len(matches) != 1:
                raise ValueError("target generated reference cannot be resolved by exact ID and hash")
            return pose_from_interface(matches[0])

        def resolve_source_placement(instance_id, reference, stack=()):
            if reference.kind == "design_variable_placement":
                return design_variable_placement(instance_id)
            if reference.derivation_id in stack:
                raise ValueError("placement derivation set must be acyclic")
            derivation = derivations.get(reference.derivation_id)
            if derivation is None or derivation.target_physical_instance_id != instance_id:
                raise ValueError("source instance and placement reference do not resolve as a pair")
            return derive(derivation, stack + (reference.derivation_id,))

        def derive(derivation, stack=()):
            source_id = derivation.source_physical_instance_id
            component = components.get(source_id)
            if component is None:
                raise ValueError("source physical instance cannot be resolved")
            source_specification = specifications[component.specification_hash]
            source_placement = resolve_source_placement(
                source_id, derivation.source_placement_ref, stack
            )
            source_pose = compose_poses(
                source_placement, source_local_pose(source_specification, derivation)
            )
            target_component = components.get(derivation.target_physical_instance_id)
            if target_component is None:
                raise ValueError("target physical instance cannot be resolved")
            target_specification = specifications[target_component.specification_hash]
            view = build_candidate_view(candidate, target_specification.specification_hash)
            reference_frames = list(view.reference_frames)
            known_frames = {
                (frame.frame_id, frame.frame_hash) for frame in reference_frames
            }
            if source_specification.generated_part is not None:
                for frame in source_specification.generated_part.reference_frames:
                    if (frame.frame_id, frame.frame_hash) not in known_frames:
                        reference_frames.append(frame)
                        known_frames.add((frame.frame_id, frame.frame_hash))
            view = replace(view, reference_frames=tuple(reference_frames))
            inputs = resolve_placement_inputs(derivation, view)
            if len(inputs) > 1:
                raise ValueError("generated placement has more than one axial offset")
            rotation = (
                _resolve_rotation_input(derivation, view)
                if derivation.rotation is not None
                else None
            )
            return place_generated_target(
                derivation.rule_id,
                source_pose,
                target_local_pose(target_specification, derivation, view),
                next(iter(inputs.values()), None),
                rotation,
            )

        result = derive(target_derivation)
        target_hash = (
            target_derivation.target_generated_interface_ref.interface_hash
            if target_derivation.target_generated_interface_ref is not None
            else target_derivation.target_generated_frame_ref.frame_hash
        )
        origin_model = (
            SemanticPlacementOrigin
            if type(mapping.placement_origin) is SemanticPlacementOrigin
            else CandidatePlacementOrigin
        )
        expected_origin = origin_model(
            authority="deterministic_derived_relation",
            input_identities=(
                f"candidate:generated-placement:{target_derivation.derivation_id}",
                target_derivation.source_interface_ref.interface_hash,
                target_hash,
                *sorted(item.input_hash for item in target_derivation.inputs),
                *(() if target_derivation.rotation is None else (target_derivation.rotation.input_hash,)),
            ),
            derivation=target_derivation.rule_id,
            transform=result,
        )
        if mapping.placement != result or mapping.placement_origin != expected_origin:
            raise CandidateCadIntegrityError(
                "candidate CAD placement does not match semantic derivation"
            )
        return result

    def _verify_candidate(self, candidate, synthesis_request, synthesis_policy, request) -> None:
        try:
            CandidateIntegrityVerifier().verify(candidate, synthesis_request, synthesis_policy)
            if (
                candidate.schema_version == "mechanical-design-candidate@2"
                and request.schema_version != "candidate-cad-realization-request@3"
            ):
                raise CandidateCadIntegrityError(
                    "candidate@2 CAD realization requires request@3"
                )
            if (
                request.schema_version == "candidate-cad-realization-request@3"
                and candidate.schema_version != "mechanical-design-candidate@2"
            ):
                raise CandidateCadIntegrityError(
                    "request@3 CAD realization requires candidate@2"
                )
            if request.schema_version == "candidate-cad-realization-request@3":
                CandidateCadRealizationRequestV3.model_validate(
                    request.model_dump(mode="json")
                )
                if (
                    request.semantic_source_binding_hash
                    != candidate.semantic_source_binding_hash
                ):
                    raise CandidateCadIntegrityError(
                        "CAD request semantic source binding mismatch"
                    )
            else:
                CandidateCadRealizationRequest.model_validate(
                    request.model_dump(mode="json")
                )
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
        if request.schema_version == "candidate-cad-realization-request@3":
            self._validate_request_input_identities_v2(candidate, request)
            return
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
            if specification.generated_part is not None and (
                mapping.fidelity is CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY
                and mapping.geometry_definition_identities
                != generated_geometry_definition_identities(specification.generated_part)
            ):
                raise CandidateCadIntegrityError(
                    "generated geometry definition identities mismatch"
                )
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

    def _validate_request_input_identities_v2(self, candidate, request) -> None:
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
        declared_inputs = semantic_declared_inputs(request.mappings)

        for mapping in request.mappings:
            component = components[mapping.physical_instance_id]
            specification = specifications[component.specification_hash]
            source = specification.geometry_source
            if mapping.fidelity is CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY:
                if source is None or mapping.source_geometry_identity is None:
                    raise CandidateCadIntegrityError(
                        "trusted CAD mapping has no authoritative semantic source"
                    )
                if (
                    source.content_identity in (None, "pending")
                    or source.content_identity_algorithm != "step-content-identity@1"
                    or source.semantic_reference_hash in (None, "pending")
                    or mapping.source_geometry_identity.content_identity
                    != source.content_identity
                    or mapping.source_geometry_identity.content_identity_algorithm
                    != source.content_identity_algorithm
                    or mapping.geometry_definition_identities
                    != (source.content_identity,)
                ):
                    raise CandidateCadIntegrityError(
                        "trusted CAD mapping semantic source does not match its component specification"
                    )
            elif mapping.source_geometry_identity is not None:
                raise CandidateCadIntegrityError(
                    "non-source CAD mapping cannot claim semantic source geometry"
                )

            if (
                specification.generated_part is not None
                and mapping.fidelity is CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY
                and mapping.geometry_definition_identities
                != generated_geometry_definition_identities(specification.generated_part)
            ):
                raise CandidateCadIntegrityError(
                    "generated geometry definition identities mismatch"
                )

            origin = mapping.placement_origin
            if mapping.placement != origin.transform:
                raise CandidateCadIntegrityError(
                    "CAD placement transform does not match semantic placement provenance"
                )
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
            if source is not None:
                source_authority_inputs = {
                    source.content_identity,
                    f"candidate:source-authority:{source.source_identity}",
                }
            allowed = {
                f"candidate:/realization/components/{mapping.physical_instance_id}",
                f"candidate:placement:{mapping.physical_instance_id}",
                *placement_variables,
                *component_interfaces,
                f"candidate:policy:{request.representation_policy_version}",
                *source_authority_inputs,
            }
            derivation = next(
                (
                    item
                    for item in request.placement_derivations
                    if item.target_physical_instance_id == mapping.physical_instance_id
                ),
                None,
            )
            if derivation is not None:
                target_hash = (
                    derivation.target_generated_interface_ref.interface_hash
                    if derivation.target_generated_interface_ref is not None
                    else derivation.target_generated_frame_ref.frame_hash
                )
                expected_inputs = {
                    f"candidate:generated-placement:{derivation.derivation_id}",
                    derivation.source_interface_ref.interface_hash,
                    target_hash,
                    *(item.input_hash for item in derivation.inputs),
                    *(() if derivation.rotation is None else (derivation.rotation.input_hash,)),
                }
                if (
                    origin.authority != "deterministic_derived_relation"
                    or origin.derivation != derivation.rule_id
                    or set(origin.input_identities) != expected_inputs
                    or len(origin.input_identities) != len(expected_inputs)
                ):
                    raise CandidateCadIntegrityError(
                        "CAD mapping contains foreign semantic placement provenance"
                    )
            else:
                identities = set(origin.input_identities)
                if not identities <= allowed:
                    raise CandidateCadIntegrityError(
                        "CAD mapping contains foreign semantic placement provenance"
                    )
                authority_inputs = {
                    "source_authority": identities & source_authority_inputs,
                    "candidate_design_variable": identities & placement_variables,
                    "candidate_interface": identities & component_interfaces,
                    "explicit_policy_assumption": identities
                    & {f"candidate:policy:{request.representation_policy_version}"},
                }
                required = authority_inputs.get(origin.authority)
                if required is not None and not required:
                    raise CandidateCadIntegrityError(
                        "CAD placement authority is not owned by its semantic mapping"
                    )

        requested_design_variable_identities = set(request.design_variable_identities)
        requested_interface_identities = set(request.component_interface_identities)
        if not requested_design_variable_identities <= candidate_design_variable_identities:
            raise CandidateCadIntegrityError(
                "CAD request contains a foreign design variable identity"
            )
        if not requested_interface_identities <= candidate_interface_identities:
            raise CandidateCadIntegrityError(
                "CAD request contains a foreign component interface identity"
            )
        if requested_design_variable_identities != (
            declared_inputs & candidate_design_variable_identities
        ):
            raise CandidateCadIntegrityError(
                "CAD request design variable identities do not match declared inputs"
            )
        if requested_interface_identities != (
            declared_inputs & candidate_interface_identities
        ):
            raise CandidateCadIntegrityError(
                "CAD request component interface identities do not match declared inputs"
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
            derivation = next(
                (
                    item
                    for item in request.placement_derivations
                    if item.target_physical_instance_id == mapping.physical_instance_id
                ),
                None,
            )
            if derivation is not None:
                target_hash = (
                    derivation.target_generated_interface_ref.interface_hash
                    if derivation.target_generated_interface_ref is not None
                    else derivation.target_generated_frame_ref.frame_hash
                )
                expected = (
                    f"candidate:generated-placement:{derivation.derivation_id}",
                    derivation.source_interface_ref.interface_hash,
                    target_hash,
                    *(sorted(item.input_hash for item in derivation.inputs)),
                    *(() if derivation.rotation is None else (derivation.rotation.input_hash,)),
                )
                if (
                    mapping.placement_origin.authority != "deterministic_derived_relation"
                    or mapping.placement_origin.derivation != derivation.rule_id
                    or mapping.placement_origin.input_identities != expected
                ):
                    raise CandidateCadIntegrityError(
                        "CAD mapping contains a foreign or irrelevant placement provenance identity"
                    )
                continue
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

    def _resolve_trusted_source_v2(self, specification, mapping, candidate):
        source = specification.geometry_source
        assert source is not None
        if mapping.fidelity is not CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY:
            return None, CandidateCadStageReason.UNSUPPORTED_REPRESENTATION, None, None
        if (
            source.content_identity in (None, "pending")
            or source.content_identity_algorithm != "step-content-identity@1"
            or source.semantic_reference_hash in (None, "pending")
        ):
            raise CandidateCadIntegrityError(
                "candidate source geometry semantic identity is unbound"
            )
        try:
            verified = self._lookup_store.read_verified_in_project(
                source.artifact_id,
                expected_type=ArtifactType.STEP,
                expected_hash=source.artifact_hash,
            )
        except Exception as exc:
            raise CandidateCadIntegrityError(
                f"trusted source artifact verification failed: {exc}"
            ) from exc
        if verified is None:
            raise CandidateCadIntegrityError(
                "trusted source artifact is missing or failed integrity verification"
            )
        artifact, raw_bytes = verified
        if (
            artifact.project_id != candidate.source_binding.project_id
            or artifact.artifact_id != source.artifact_id
            or artifact.artifact_type is not ArtifactType.STEP
            or artifact.sha256 != source.artifact_hash
            or artifact.bound_revision != candidate.source_binding.source_revision
            or artifact.bound_state_hash != candidate.source_binding.source_state_hash
        ):
            raise CandidateCadIntegrityError("trusted source artifact binding mismatch")

        content_identity = step_content_identity_v1(raw_bytes).content_hash
        if content_identity != source.content_identity:
            raise CandidateCadIntegrityError(
                "trusted source semantic content identity mismatch"
            )
        expected_semantic_source = SemanticSourceGeometryIdentity(
            content_identity=content_identity,
            content_identity_algorithm="step-content-identity@1",
        )
        if (
            mapping.source_geometry_identity != expected_semantic_source
            or mapping.geometry_definition_identities != (content_identity,)
        ):
            raise CandidateCadIntegrityError(
                "candidate CAD mapping semantic source identity mismatch"
            )
        try:
            store = ArtifactStore(
                self.workspace,
                project_id=artifact.project_id,
                run_id=artifact.run_id,
                task_id=artifact.task_id,
            )
            imported = resolve_imported_component(
                source.artifact_id,
                source.artifact_hash,
                store,
                component_id=mapping.cad_instance_id,
            )
        except ImportedComponentError as exc:
            raise CandidateCadIntegrityError(str(exc)) from exc
        return imported, None, content_identity, artifact.artifact_id

    def _compile_generated(self, specification, mapping, candidate):
        if specification.generated_part is not None:
            if mapping.fidelity is not CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY:
                return None, CandidateCadStageReason.UNSUPPORTED_REPRESENTATION
            try:
                compilation = compile_generated_part(
                    specification.generated_part,
                    build_candidate_view(candidate, specification.specification_hash),
                    owning_instance_context=mapping.physical_instance_id,
                )
            except Exception as exc:
                raise CandidateCadIntegrityError(str(exc)) from exc
            if mapping.source_geometry_identity is not None:
                raise CandidateCadIntegrityError(
                    "exact generated geometry cannot claim source geometry"
                )
            if mapping.geometry_definition_identities != compilation.geometry_definition_identities:
                raise CandidateCadIntegrityError("generated geometry definition identities mismatch")
            if mapping.representation_identity != compilation.program_hash:
                raise CandidateCadIntegrityError("generated CAD representation identity mismatch")
            return compilation.program, None
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

    @staticmethod
    def _candidate_authority_view(candidate, specification) -> GeneratedAuthorityView:
        return build_candidate_view(candidate, specification.specification_hash)

    def _generated_dimensions(self, specification, physical_instance_id, candidate):
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
            if semantic_name is None:
                continue
            if (
                property.availability is not ComponentPropertyAvailability.AVAILABLE
                or property.normalized_value is None
                or property.canonical_unit != "mm"
                or not math.isfinite(property.normalized_value)
                or property.normalized_value <= 0
            ):
                return None
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
            for spelling in (
                "{instance}.{dimension}",
                "{instance}.geometry.{dimension}",
                "geometry.{instance}.{dimension}",
            )
        }
        for variable in candidate.design_variables:
            semantic_name = scoped_names.get(variable.name)
            if semantic_name is None:
                continue
            if isinstance(variable.value, bool) or not isinstance(variable.value, Real):
                return None
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

        if not inputs:
            return None
        try:
            resolved = resolve_dimensions(
                inputs,
                required_dimensions=tuple(LEGACY_PLATE_DIMENSION_ALIASES),
            )
        except DimensionConflictError as exc:
            raise CandidateCadIntegrityError(str(exc)) from exc
        except DimensionResolutionError:
            return None

        values = {}
        identities = []
        for semantic_name in LEGACY_PLATE_DIMENSION_ALIASES:
            dimension = resolved[(physical_instance_id, semantic_name)]
            values[semantic_name] = dimension.value
            identities.extend(dimension.identities)
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
    EXACT_GENERATED_GEOMETRY = "exact_generated_geometry"


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
    schema_version: Literal[
        "candidate-cad-realization-request@1",
        "candidate-cad-realization-request@2",
    ] = "candidate-cad-realization-request@1"
    candidate_hash: str
    source_binding: CandidateSourceBinding
    source_binding_hash: str = "pending"
    representation_policy_version: str = Field(min_length=1)
    compiler_identity: str = Field(min_length=1)
    compiler_version: str = Field(min_length=1)
    candidate_instance_ids: tuple[str, ...] = Field(min_length=1)
    mappings: tuple[CandidateCadInstanceMapping, ...] = Field(min_length=1)
    placement_derivations: tuple[GeneratedPlacementDerivation, ...] = ()
    placement_derivations_hash: str | None = None
    design_variable_identities: tuple[str, ...] = ()
    component_interface_identities: tuple[str, ...] = ()
    request_hash: str = "pending"

    _validate_hashes = field_validator("candidate_hash")(_require_hash)
    _validate_derived_hashes = field_validator("source_binding_hash", "request_hash")(_require_hash_or_pending)
    _validate_placement_derivations_hash = field_validator(
        "placement_derivations_hash"
    )(_require_optional_hash)
    _validate_provenance = field_validator(
        "representation_policy_version", "compiler_identity", "compiler_version"
    )(_require_nonblank)

    @model_serializer(mode="wrap")
    def serialize_request(self, handler):
        payload = handler(self)
        if self.schema_version.endswith("@1"):
            payload.pop("placement_derivations", None)
            payload.pop("placement_derivations_hash", None)
        return payload

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
        if self.schema_version.endswith("@1"):
            if self.placement_derivations:
                raise ValueError("candidate-cad-realization-request@1 forbids placement derivations")
            if self.placement_derivations_hash is not None:
                raise ValueError(
                    "candidate-cad-realization-request@1 forbids placement derivations hash"
                )
        else:
            derivation_ids = tuple(item.derivation_id for item in self.placement_derivations)
            target_instance_ids = tuple(
                item.target_physical_instance_id for item in self.placement_derivations
            )
            if len(set(derivation_ids)) != len(derivation_ids):
                raise ValueError("placement derivation IDs must be unique")
            if len(set(target_instance_ids)) != len(target_instance_ids):
                raise ValueError("placement derivation targets must be unique per instance")
            if self.placement_derivations_hash is None:
                raise ValueError("candidate-cad-realization-request@2 requires placement derivations hash")
            expected_derivations_hash = placement_derivations_hash(self.placement_derivations)
            if self.placement_derivations_hash != expected_derivations_hash:
                raise ValueError("placement derivations hash mismatch")
            candidate_instance_ids = set(self.candidate_instance_ids)
            mappings_by_physical_id = {
                mapping.physical_instance_id: mapping for mapping in self.mappings
            }
            for derivation in self.placement_derivations:
                if derivation.source_physical_instance_id not in candidate_instance_ids:
                    raise ValueError(
                        "placement derivation source is not in candidate instance IDs"
                    )
                if derivation.target_physical_instance_id not in candidate_instance_ids:
                    raise ValueError(
                        "placement derivation target is not in candidate instance IDs"
                    )
                target_mapping = mappings_by_physical_id.get(
                    derivation.target_physical_instance_id
                )
                if target_mapping is None:
                    raise ValueError(
                        "placement derivation target is not a mapped physical instance"
                    )
                if target_mapping.fidelity is not CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY:
                    raise ValueError("placement derivation target must be a generated mapping")
            for mapping in self.mappings:
                if mapping.fidelity is CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY:
                    matches = tuple(
                        item
                        for item in self.placement_derivations
                        if item.target_physical_instance_id == mapping.physical_instance_id
                    )
                    if len(matches) != 1:
                        raise ValueError(
                            "generated mapping requires exactly one placement derivation target"
                        )
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
    placement_derivations_hash: str | None = None
    verified_source_content_identities: tuple[str, ...] = ()
    compiler_identity: str = Field(min_length=1)
    compiler_version: str = Field(min_length=1)
    provider_identity: str = Field(min_length=1)
    realization_hash: str = "pending"

    _validate_hashes = field_validator("candidate_hash", "request_hash", "assembly_hash")(_require_hash)
    _validate_placement_derivations_hash = field_validator(
        "placement_derivations_hash"
    )(_require_optional_hash)
    _validate_realization_hash = field_validator("realization_hash")(_require_hash_or_pending)
    _validate_provenance = field_validator(
        "compiler_identity", "compiler_version", "provider_identity"
    )(_require_nonblank)

    @model_serializer(mode="wrap")
    def serialize_realization(self, handler):
        payload = handler(self)
        if self.placement_derivations_hash is None:
            payload.pop("placement_derivations_hash", None)
        return payload

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
        if len(set(self.verified_source_content_identities)) != len(
            self.verified_source_content_identities
        ):
            raise ValueError(
                "verified source content identities must be unique and bind one-to-one"
            )
        unique_trusted_source_geometry_identities = tuple(
            dict.fromkeys(trusted_source_geometry_identities)
        )
        if tuple(self.verified_source_content_identities) != unique_trusted_source_geometry_identities:
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


# ---- Deterministic STEP content identity: candidate CAD @2/@3 family (P3) ----
#
# New semantic records are additive and dispatched from the typed request@3
# through the shared realization lowering. Every legacy @1/@2 record, hash
# payload, and validator above remains frozen for replay.

_SEMANTIC_CONTENT_IDENTITY_ALGORITHM = "step-content-identity@1"
_TRUSTED_REPRESENTATION_CONTRACT = "trusted-source-geometry@1"


def trusted_representation_identity(
    *,
    slot: str,
    content_identity: str,
    content_identity_algorithm: str = _SEMANTIC_CONTENT_IDENTITY_ALGORITHM,
) -> str:
    """Compute the exact trusted representation identity (Spec §8).

    Pure semantic projection over already-bound values. No raw artifact ID or
    SHA, no revision/state, no imported-component hash, no path, and no
    run/task identity enters.
    """

    if not isinstance(slot, str) or not slot.strip():
        raise ValueError("trusted representation slot must not be empty")
    _require_hash(content_identity)
    if content_identity_algorithm != _SEMANTIC_CONTENT_IDENTITY_ALGORITHM:
        raise ValueError("unsupported semantic geometry identity algorithm")
    payload = {
        "representation_contract": _TRUSTED_REPRESENTATION_CONTRACT,
        "slot": slot,
        "content_identity": content_identity,
        "content_identity_algorithm": content_identity_algorithm,
    }
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def collapse_placement_origin_inputs(
    authority: str,
    input_identities: tuple[str, ...] | list[str],
    *,
    content_by_artifact,
) -> tuple[str, ...]:
    """Collapse legacy placement provenance tokens to semantic tokens (Spec §8).

    For `source_authority` origins, raw artifact IDs/hashes resolve through the
    caller-supplied bound content map to the same single content token (which
    deduplicates); `candidate:`-scoped tokens are retained as-is; anything
    else fails closed. Other authorities retain their tokens unchanged.
    Output is lexicographically sorted with post-transformation duplicates
    removed by construction.
    """

    tokens: list[str] = []
    for token in tuple(input_identities):
        if not isinstance(token, str) or not token.strip():
            raise ValueError("placement provenance input identities must not be empty")
        if authority == "source_authority" and not token.startswith("candidate:"):
            content = content_by_artifact.get(token)
            if content is None:
                raise ValueError(
                    f"placement origin input does not resolve to bound content: {token}"
                )
            tokens.append(_require_hash(content))
        else:
            tokens.append(token)
    return tuple(sorted(set(tokens)))


def semantic_placement_origin_payload(
    *,
    authority: str,
    input_identities,
    derivation: str,
    transform: CadRigidTransform,
) -> dict:
    return {
        "authority": authority,
        "input_identities": list(input_identities),
        "derivation": derivation,
        "transform": transform.model_dump(mode="json"),
    }


def semantic_placement_origin_hash(
    *,
    authority: str,
    input_identities,
    derivation: str,
    transform: CadRigidTransform,
) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_json(
            semantic_placement_origin_payload(
                authority=authority,
                input_identities=input_identities,
                derivation=derivation,
                transform=transform,
            )
        )
    ).hexdigest()


def bind_semantic_placement_origin(
    authority: str,
    legacy_input_identities,
    derivation: str,
    transform: CadRigidTransform,
    *,
    content_by_artifact,
) -> "SemanticPlacementOrigin":
    """Build a semantic placement origin from legacy provenance tokens."""

    return SemanticPlacementOrigin(
        authority=authority,
        input_identities=collapse_placement_origin_inputs(
            authority, legacy_input_identities, content_by_artifact=content_by_artifact
        ),
        derivation=derivation,
        transform=transform,
    )


class SemanticSourceGeometryIdentity(CandidateCadModel):
    content_identity: str
    content_identity_algorithm: Literal["step-content-identity@1"] = (
        "step-content-identity@1"
    )

    _validate_content = field_validator("content_identity")(_require_hash)


class SemanticPlacementOrigin(CandidateCadModel):
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

    @model_validator(mode="after")
    def validate_semantic_origin(self) -> "SemanticPlacementOrigin":
        if any(not value.strip() for value in self.input_identities):
            raise ValueError("placement provenance input identities must not be empty")
        if len(set(self.input_identities)) != len(self.input_identities):
            raise ValueError("semantic placement origin input identities must be unique")
        object.__setattr__(
            self, "input_identities", tuple(sorted(self.input_identities))
        )
        if not self.derivation.strip():
            raise ValueError("placement origin derivation must not be empty")
        expected = semantic_placement_origin_hash(
            authority=self.authority,
            input_identities=self.input_identities,
            derivation=self.derivation,
            transform=self.transform,
        )
        if self.origin_hash == "pending":
            object.__setattr__(self, "origin_hash", expected)
        elif self.origin_hash != expected:
            raise ValueError("semantic placement origin hash mismatch")
        return self


def candidate_mapping_hash_v2(mapping: "CandidateCadInstanceMappingV2") -> str:
    """Compute the exact `candidate-cad-instance-mapping@2` hash (Spec §8)."""

    source = mapping.source_geometry_identity
    payload = {
        "schema_version": mapping.schema_version,
        "candidate_hash": mapping.candidate_hash,
        "physical_instance_id": mapping.physical_instance_id,
        "cad_instance_id": mapping.cad_instance_id,
        "fidelity": mapping.fidelity.value,
        "representation_identity": mapping.representation_identity,
        "source_geometry_identity": (
            None
            if source is None
            else {
                "content_identity": source.content_identity,
                "content_identity_algorithm": source.content_identity_algorithm,
            }
        ),
        "geometry_definition_identities": list(mapping.geometry_definition_identities),
        "placement": mapping.placement.model_dump(mode="json"),
        "placement_origin": semantic_placement_origin_payload(
            authority=mapping.placement_origin.authority,
            input_identities=mapping.placement_origin.input_identities,
            derivation=mapping.placement_origin.derivation,
            transform=mapping.placement_origin.transform,
        ),
    }
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


class CandidateCadInstanceMappingV2(CandidateCadModel):
    schema_version: Literal["candidate-cad-instance-mapping@2"] = (
        "candidate-cad-instance-mapping@2"
    )
    candidate_hash: str
    physical_instance_id: str = Field(min_length=1)
    cad_instance_id: str = Field(min_length=1)
    fidelity: CandidateGeometryFidelity
    representation_identity: str
    source_geometry_identity: SemanticSourceGeometryIdentity | None = None
    geometry_definition_identities: tuple[str, ...] = Field(min_length=1)
    placement: CadRigidTransform
    placement_origin: SemanticPlacementOrigin
    mapping_hash: str = "pending"

    _validate_hashes = field_validator("candidate_hash", "representation_identity")(
        _require_hash
    )
    _validate_mapping_hash = field_validator("mapping_hash")(_require_hash_or_pending)
    _validate_ids = field_validator("physical_instance_id", "cad_instance_id")(
        _require_nonblank
    )

    @model_validator(mode="after")
    def validate_mapping_v2(self) -> "CandidateCadInstanceMappingV2":
        if any(not value.strip() for value in self.geometry_definition_identities):
            raise ValueError("geometry definition identities must not be empty")
        if type(self.placement_origin) is not SemanticPlacementOrigin:
            raise ValueError("candidate-cad-instance-mapping@2 requires a semantic origin")
        if self.placement != self.placement_origin.transform:
            raise ValueError("placement transform must match its provenance")
        source = self.source_geometry_identity
        if self.fidelity is CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY:
            if source is None:
                raise ValueError("trusted source geometry requires source geometry identity")
            if self.geometry_definition_identities != (source.content_identity,):
                raise ValueError(
                    "trusted source geometry requires the singular content tuple"
                )
            expected_representation = trusted_representation_identity(
                slot=self.cad_instance_id,
                content_identity=source.content_identity,
                content_identity_algorithm=source.content_identity_algorithm,
            )
            if self.representation_identity != expected_representation:
                raise ValueError("trusted representation identity mismatch")
        else:
            if source is not None:
                raise ValueError("non-source fidelity cannot claim source geometry")
            if self.fidelity is CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY:
                if len(set(self.geometry_definition_identities)) != len(
                    self.geometry_definition_identities
                ):
                    raise ValueError("generated geometry definition identities must be unique")
                object.__setattr__(
                    self,
                    "geometry_definition_identities",
                    tuple(sorted(self.geometry_definition_identities)),
                )
        expected = candidate_mapping_hash_v2(self)
        if self.mapping_hash == "pending":
            object.__setattr__(self, "mapping_hash", expected)
        elif self.mapping_hash != expected:
            raise ValueError("candidate CAD mapping@2 hash mismatch")
        return self


def semantic_derivation_projection(derivation: GeneratedPlacementDerivation) -> dict:
    """Project one placement derivation to its semantic closure (Spec §7).

    Listed fields only; the legacy `derivation_hash` self-hash is excluded;
    inputs commit by recomputed `input_hash` sorted by `input_id`; rotation
    commits by `input_hash` or null. No projection version is embedded: the
    subprojection is versioned by the containing request contract.
    """

    def _interface_ref(reference):
        if reference is None:
            return None
        return {
            "interface_id": reference.interface_id,
            "interface_hash": reference.interface_hash,
        }

    def _frame_ref(reference):
        if reference is None:
            return None
        return {
            "frame_id": reference.frame_id,
            "frame_hash": reference.frame_hash,
        }

    placement_ref = derivation.source_placement_ref
    placement_payload: dict = {"kind": placement_ref.kind}
    if placement_ref.kind == "derivation":
        placement_payload["derivation_id"] = placement_ref.derivation_id
    rotation = derivation.rotation
    return {
        "derivation_id": derivation.derivation_id,
        "rule_id": derivation.rule_id,
        "source_physical_instance_id": derivation.source_physical_instance_id,
        "source_interface_ref": _interface_ref(derivation.source_interface_ref),
        "source_frame_ref": _frame_ref(derivation.source_frame_ref),
        "source_placement_ref": placement_payload,
        "target_physical_instance_id": derivation.target_physical_instance_id,
        "target_generated_interface_ref": _interface_ref(
            derivation.target_generated_interface_ref
        ),
        "target_generated_frame_ref": _frame_ref(
            derivation.target_generated_frame_ref
        ),
        "inputs": [
            item.input_hash
            for item in sorted(derivation.inputs, key=lambda item: item.input_id)
        ],
        "rotation": None if rotation is None else rotation.input_hash,
    }


def semantic_placement_derivations_hash(
    derivations: tuple[GeneratedPlacementDerivation, ...] | list[GeneratedPlacementDerivation],
) -> str:
    """Hash the `derivation_id`-sorted semantic derivation closure (Spec §7).

    Required even for the empty tuple (hash of the empty canonical tuple).
    """

    from mechcad_harness.models.generated_placement import _validate_acyclic

    records = tuple(derivations)
    _validate_acyclic(records)
    projections = sorted(
        (semantic_derivation_projection(item) for item in records),
        key=lambda projection: projection["derivation_id"],
    )
    return "sha256:" + hashlib.sha256(canonical_json(projections)).hexdigest()


def semantic_declared_inputs(
    mappings,
) -> set[str]:
    """Union semantic geometry-definition and placement-origin inputs (Spec §7)."""

    declared: set[str] = set()
    for mapping in mappings:
        declared.update(mapping.geometry_definition_identities)
        declared.update(mapping.placement_origin.input_identities)
    return declared


def candidate_request_hash_v3(request: "CandidateCadRealizationRequestV3") -> str:
    """Compute the exact `candidate-cad-realization-request@3` hash (Spec §7)."""

    if request.schema_version != "candidate-cad-realization-request@3":
        raise ValueError("candidate_request_hash_v3 requires request@3")
    if request.semantic_source_binding_hash == "pending":
        raise ValueError("candidate CAD semantic source binding is pending")
    ordered = sorted(request.mappings, key=lambda item: item.physical_instance_id)
    payload = {
        "schema_version": request.schema_version,
        "candidate_hash": request.candidate_hash,
        "semantic_source_binding_hash": request.semantic_source_binding_hash,
        "representation_policy_version": request.representation_policy_version,
        "compiler_identity": request.compiler_identity,
        "compiler_version": request.compiler_version,
        "candidate_instance_ids": list(request.candidate_instance_ids),
        "mappings": [mapping.mapping_hash for mapping in ordered],
        "semantic_placement_derivations_hash": request.semantic_placement_derivations_hash,
        "design_variable_identities": list(request.design_variable_identities),
        "component_interface_identities": list(request.component_interface_identities),
    }
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


class CandidateCadRealizationRequestV3(CandidateCadModel):
    schema_version: Literal["candidate-cad-realization-request@3"] = (
        "candidate-cad-realization-request@3"
    )
    candidate_hash: str
    source_binding: CandidateSourceBinding
    source_binding_hash: str = "pending"
    semantic_source_binding_hash: str = "pending"
    representation_policy_version: str = Field(min_length=1)
    compiler_identity: str = Field(min_length=1)
    compiler_version: str = Field(min_length=1)
    candidate_instance_ids: tuple[str, ...] = Field(min_length=1)
    mappings: tuple[CandidateCadInstanceMappingV2, ...] = Field(min_length=1)
    placement_derivations: tuple[GeneratedPlacementDerivation, ...] = ()
    semantic_placement_derivations_hash: str = "pending"
    design_variable_identities: tuple[str, ...] = ()
    component_interface_identities: tuple[str, ...] = ()
    request_hash: str = "pending"

    _validate_hashes = field_validator("candidate_hash")(_require_hash)
    _validate_derived_hashes = field_validator(
        "source_binding_hash", "semantic_source_binding_hash", "request_hash"
    )(_require_hash_or_pending)
    _validate_semantic_derivations_hash = field_validator(
        "semantic_placement_derivations_hash"
    )(_require_hash_or_pending)
    _validate_provenance = field_validator(
        "representation_policy_version", "compiler_identity", "compiler_version"
    )(_require_nonblank)

    @model_validator(mode="after")
    def validate_manifest_and_hash_v3(self) -> "CandidateCadRealizationRequestV3":
        if self.representation_policy_version != "candidate-cad-policy@1":
            raise ValueError("candidate-cad-realization-request@3 requires policy@1")
        if (
            self.compiler_identity != "candidate-cad-compiler"
            or self.compiler_version != "1"
        ):
            raise ValueError("candidate-cad-realization-request@3 requires compiler@1")
        if any(not value.strip() for value in self.candidate_instance_ids):
            raise ValueError("candidate physical instance IDs must not be empty")
        if len(set(self.candidate_instance_ids)) != len(self.candidate_instance_ids):
            raise ValueError("candidate physical instance IDs must be unique")
        object.__setattr__(
            self, "candidate_instance_ids", tuple(sorted(self.candidate_instance_ids))
        )
        physical_ids = tuple(mapping.physical_instance_id for mapping in self.mappings)
        if len(set(physical_ids)) != len(physical_ids):
            raise ValueError("candidate physical instance mappings must be unique")
        cad_ids = tuple(mapping.cad_instance_id for mapping in self.mappings)
        if len(set(cad_ids)) != len(cad_ids):
            raise ValueError("CAD instance mappings must be unique")
        if set(physical_ids) != set(self.candidate_instance_ids):
            raise ValueError("mapping must cover every candidate physical instance")
        if any(mapping.candidate_hash != self.candidate_hash for mapping in self.mappings):
            raise ValueError("CAD mapping is bound to a different candidate")
        object.__setattr__(
            self,
            "mappings",
            tuple(sorted(self.mappings, key=lambda item: item.physical_instance_id)),
        )
        expected_source_hash = _hash(self.source_binding)
        if self.source_binding_hash == "pending":
            object.__setattr__(self, "source_binding_hash", expected_source_hash)
        elif self.source_binding_hash != expected_source_hash:
            raise ValueError("candidate source binding hash mismatch")
        derivation_ids = tuple(item.derivation_id for item in self.placement_derivations)
        if len(set(derivation_ids)) != len(derivation_ids):
            raise ValueError("placement derivation IDs must be unique")
        object.__setattr__(
            self,
            "placement_derivations",
            tuple(sorted(self.placement_derivations, key=lambda item: item.derivation_id)),
        )
        expected_derivations_hash = semantic_placement_derivations_hash(
            self.placement_derivations
        )
        if self.semantic_placement_derivations_hash == "pending":
            object.__setattr__(
                self,
                "semantic_placement_derivations_hash",
                expected_derivations_hash,
            )
        elif self.semantic_placement_derivations_hash != expected_derivations_hash:
            raise ValueError("semantic placement derivations hash mismatch")
        declared = semantic_declared_inputs(self.mappings)
        for field_name, universe in (
            ("design_variable_identities", "candidate:design-variable:"),
            ("component_interface_identities", "candidate:component-interface:"),
        ):
            values = getattr(self, field_name)
            if any(not value.strip() for value in values):
                raise ValueError("candidate realization input identities must not be empty")
            if len(set(values)) != len(values):
                raise ValueError("candidate realization input identities must be unique")
            object.__setattr__(self, field_name, tuple(sorted(values)))
            expected_identities = tuple(
                sorted(value for value in declared if value.startswith(universe))
            )
            if tuple(getattr(self, field_name)) != expected_identities:
                raise ValueError(
                    "candidate realization input identities do not match declared inputs"
                )
        if self.semantic_source_binding_hash == "pending":
            if self.request_hash != "pending":
                raise ValueError("unbound candidate-cad-realization-request@3 cannot have a request hash")
        else:
            expected = candidate_request_hash_v3(self)
            if self.request_hash == "pending":
                object.__setattr__(self, "request_hash", expected)
            elif self.request_hash != expected:
                raise ValueError("candidate CAD realization request@3 hash mismatch")
        return self


def semantic_assembly_hash(assembly: CadAssemblyProgram, mappings) -> str:
    """Compute the §10 semantic assembly identity (option A).

    Parts commit by program hash (sorted by `part_id`); trusted sources commit
    by bound content identity (sorted by the mapping slot key); instances
    commit by placement (sorted by `instance_id`). Raw artifact IDs/hashes,
    revisions, state hashes, paths, and the legacy raw `assembly_hash` never
    enter. Duplicate keys are rejected by `CadAssemblyProgram` validation.
    """

    trusted_sources = []
    for mapping in sorted(mappings, key=lambda item: item.cad_instance_id):
        source = mapping.source_geometry_identity
        if source is None:
            continue
        trusted_sources.append(
            {
                "slot": mapping.cad_instance_id,
                "content_identity": source.content_identity,
                "content_identity_algorithm": source.content_identity_algorithm,
            }
        )
    payload = {
        "parts": [
            {"part_id": part.part_id, "program_hash": cad_program_hash(part)}
            for part in sorted(assembly.parts, key=lambda part: part.part_id)
        ],
        "trusted_sources": trusted_sources,
        "instances": [
            {
                "instance_id": instance.instance_id,
                "part_slot_ref": instance.part_id,
                "placement": instance.placement.model_dump(mode="json"),
            }
            for instance in sorted(assembly.instances, key=lambda item: item.instance_id)
        ],
    }
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def candidate_realization_hash_v2(realization: "CandidateCadRealizationV2") -> str:
    """Compute the exact `candidate-cad-realization@2` hash (Spec §9)."""

    if realization.schema_version != "candidate-cad-realization@2":
        raise ValueError("candidate_realization_hash_v2 requires realization@2")
    ordered = sorted(realization.mappings, key=lambda item: item.physical_instance_id)
    payload = {
        "schema_version": realization.schema_version,
        "candidate_hash": realization.candidate_hash,
        "request_hash": realization.request_hash,
        "mapping_hashes": [mapping.mapping_hash for mapping in ordered],
        "semantic_assembly_hash": semantic_assembly_hash(
            realization.assembly, realization.mappings
        ),
        "verified_source_content_identities": list(
            realization.verified_source_content_identities
        ),
        "representation_identities": list(realization.representation_identities),
        "semantic_placement_derivations_hash": (
            realization.semantic_placement_derivations_hash
        ),
        "compiler_identity": realization.compiler_identity,
        "compiler_version": realization.compiler_version,
    }
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


class CandidateCadRealizationV2(CandidateCadModel):
    schema_version: Literal["candidate-cad-realization@2"] = (
        "candidate-cad-realization@2"
    )
    candidate_hash: str
    request_hash: str
    mappings: tuple[CandidateCadInstanceMappingV2, ...] = Field(min_length=1)
    assembly: CadAssemblyProgram
    assembly_hash: str
    representation_identities: tuple[str, ...] = ()
    semantic_placement_derivations_hash: str = "pending"
    verified_source_content_identities: tuple[str, ...] = ()
    verified_source_artifact_hashes: tuple[str, ...] = ()
    compiler_identity: str = Field(min_length=1)
    compiler_version: str = Field(min_length=1)
    provider_identity: str = Field(min_length=1)
    realization_hash: str = "pending"

    _validate_hashes = field_validator(
        "candidate_hash", "request_hash", "assembly_hash"
    )(_require_hash)
    _validate_derivations_hash = field_validator("semantic_placement_derivations_hash")(
        _require_hash_or_pending
    )
    _validate_content_identities = field_validator("verified_source_content_identities")(
        lambda values: tuple(_require_hash(value) for value in values)
    )
    _validate_artifact_hashes = field_validator("verified_source_artifact_hashes")(
        lambda values: tuple(_require_hash(value) for value in values)
    )
    _validate_realization_hash = field_validator("realization_hash")(
        _require_hash_or_pending
    )
    _validate_provenance = field_validator(
        "compiler_identity", "compiler_version", "provider_identity"
    )(_require_nonblank)

    @model_validator(mode="after")
    def validate_realization_v2(self) -> "CandidateCadRealizationV2":
        if self.compiler_identity != "candidate-cad-compiler":
            raise ValueError("candidate-cad-realization@2 requires compiler@1")
        if self.compiler_version != "1":
            raise ValueError("candidate-cad-realization@2 requires compiler@1")
        for mapping in self.mappings:
            if type(mapping) is not CandidateCadInstanceMappingV2:
                raise ValueError(
                    "candidate-cad-realization@2 requires mapping@2 records"
                )
        physical_ids = tuple(mapping.physical_instance_id for mapping in self.mappings)
        cad_ids = tuple(mapping.cad_instance_id for mapping in self.mappings)
        if len(set(physical_ids)) != len(physical_ids):
            raise ValueError("candidate physical instance mappings must be unique")
        if len(set(cad_ids)) != len(cad_ids):
            raise ValueError("CAD instance mappings must be unique")
        if any(mapping.candidate_hash != self.candidate_hash for mapping in self.mappings):
            raise ValueError("CAD mapping is bound to a different candidate")
        object.__setattr__(
            self,
            "mappings",
            tuple(sorted(self.mappings, key=lambda item: item.physical_instance_id)),
        )
        assembly_instances = {
            instance.instance_id: instance for instance in self.assembly.instances
        }
        if set(cad_ids) != set(assembly_instances):
            raise ValueError("candidate CAD assembly instances must match mappings")
        if any(
            assembly_instances[mapping.cad_instance_id].placement != mapping.placement
            for mapping in self.mappings
        ):
            raise ValueError("candidate CAD assembly placement must match mapping")
        parts_by_id = {part.part_id for part in self.assembly.parts}
        imported_by_id = {
            component.component_id for component in self.assembly.imported_components
        }
        for mapping in self.mappings:
            instance = assembly_instances[mapping.cad_instance_id]
            if mapping.fidelity is CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY:
                if instance.part_id not in imported_by_id:
                    raise ValueError(
                        "trusted CAD mapping must reference an imported assembly component"
                    )
                source = mapping.source_geometry_identity
                assert source is not None
                expected_representation = trusted_representation_identity(
                    slot=mapping.cad_instance_id,
                    content_identity=source.content_identity,
                    content_identity_algorithm=source.content_identity_algorithm,
                )
                if mapping.representation_identity != expected_representation:
                    raise ValueError("candidate CAD trusted representation identity mismatch")
            elif instance.part_id not in parts_by_id:
                raise ValueError(
                    "non-source CAD mapping must reference a CadPartProgram assembly component"
                )
        if self.assembly_hash != assembly_hash(self.assembly):
            raise ValueError("candidate CAD assembly hash mismatch")
        if tuple(self.representation_identities) != tuple(
            mapping.representation_identity for mapping in self.mappings
        ):
            raise ValueError("candidate CAD representation manifest mismatch")
        trusted_contents = tuple(
            mapping.source_geometry_identity.content_identity
            for mapping in self.mappings
            if mapping.fidelity is CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY
        )
        for value in self.verified_source_content_identities:
            _require_hash(value)
        if tuple(dict.fromkeys(trusted_contents)) != tuple(
            self.verified_source_content_identities
        ):
            if trusted_contents:
                raise ValueError(
                    "trusted source geometry identity must match verified source content identity"
                )
            if self.verified_source_content_identities:
                raise ValueError("non-source CAD realization cannot claim verified source content")
        expected = candidate_realization_hash_v2(self)
        if self.realization_hash == "pending":
            object.__setattr__(self, "realization_hash", expected)
        elif self.realization_hash != expected:
            raise ValueError("candidate CAD realization@2 hash mismatch")
        return self


def candidate_cad_stage_outcome_hash_v2(outcome: "CandidateCadStageOutcomeV2") -> str:
    """Compute the exact `candidate-cad-stage-outcome@2` hash (Spec §9)."""

    if outcome.schema_version != "candidate-cad-stage-outcome@2":
        raise ValueError("candidate_cad_stage_outcome_hash_v2 requires outcome@2")
    payload = {
        "schema_version": outcome.schema_version,
        "status": outcome.status.value,
        "realization_hash": outcome.realization_hash,
        "reasons": [reason.value for reason in outcome.reasons],
    }
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


class CandidateCadStageOutcomeV2(CandidateCadModel):
    schema_version: Literal["candidate-cad-stage-outcome@2"] = (
        "candidate-cad-stage-outcome@2"
    )
    status: CandidateCadStageStatus
    realization: CandidateCadRealizationV2 | None = None
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
    def validate_status_and_hash_v2(self) -> "CandidateCadStageOutcomeV2":
        if self.status is CandidateCadStageStatus.SUCCESS:
            if self.realization is None or self.reasons:
                raise ValueError("successful CAD stage requires exactly one realization")
            if type(self.realization) is not CandidateCadRealizationV2:
                raise ValueError("candidate-cad-stage-outcome@2 requires realization@2")
            expected_realization_hash = candidate_realization_hash_v2(self.realization)
            if self.realization.realization_hash != expected_realization_hash:
                raise ValueError("CAD stage realization identity mismatch")
            if self.realization_hash is None:
                object.__setattr__(
                    self, "realization_hash", expected_realization_hash
                )
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
        expected = candidate_cad_stage_outcome_hash_v2(self)
        if self.outcome_hash == "pending":
            object.__setattr__(self, "outcome_hash", expected)
        elif self.outcome_hash != expected:
            raise ValueError("candidate CAD stage outcome@2 hash mismatch")
        return self
