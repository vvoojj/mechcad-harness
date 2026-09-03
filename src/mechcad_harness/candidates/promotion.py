from __future__ import annotations

import hashlib
import inspect
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.models.common import Model
from mechcad_harness.state.hashing import state_hash

from .comparison import (
    CandidateComparisonService,
    candidate_comparison_policy_hash,
    candidate_comparison_request_hash,
    candidate_comparison_result_hash,
)
from .evaluation import (
    CandidateEvaluationCurrentnessService,
    CandidateEvaluationOutcome,
    _validate_cad_inputs,
    _validate_m10_inputs,
)
from .cad_realization import CandidateCadRealizationService
from .generated_authority import build_candidate_view
from .models import (
    ComponentPropertyAvailability,
    GeometrySourceReference,
    MechanicalDesignCandidate,
    candidate_hash,
)
from .promotion_models import (
    CandidateCanonicalInstanceMapping,
    CandidatePromotionApplicationResult,
    CandidatePromotionCompilation,
    CandidatePromotionPolicy,
    CandidatePromotionRequest,
    PrePromotionM10ScopeProjection,
    PromotableMechanismProjection,
    PromotionClassification,
    PromotionApplicationStatus,
    PromotionPhysicalPairRequirement,
    PromotionSourceValue,
    PromotionValueClassification,
    _hash,
    _nonblank,
    _require_hash,
    promotion_proposal_hash,
)
from .promotion_artifacts import PromotionManifestService
from .selection import CandidateSelectionService, candidate_selection_hash
from .services import (
    CandidateCurrentness,
    CandidateCurrentnessService,
    CandidateIntegrityVerifier,
)
from mechcad_harness.revolute_drive import (
    DriveAdmissibility,
    InputProvenanceKind,
    admissibility_result_hash,
)
from mechcad_harness.changes.operations import ChangeOperation
from mechcad_harness.changes.errors import ChangeError
from mechcad_harness.models import ChangeProposal, ProposalStatus
from mechcad_harness.runs import PostApplyInvalidationError, PostApplyRunTransitionError, SourceBinding
from mechcad_harness.models.physical_mechanism import (
    CanonicalAcceptedDesignChoice,
    CanonicalComponentProperty,
    CanonicalComponentPropertyAvailability,
    CanonicalComponentSpecification,
    CanonicalConnectionMeaning,
    CanonicalDesignChoiceOrigin,
    CanonicalGeometrySourceReference,
    CanonicalJointPhysicalBinding,
    CanonicalM10VerificationObligation,
    CanonicalMechanicalConnection,
    CanonicalMechanicalConnectionKind,
    CanonicalPhysicalComponent,
    CanonicalPhysicalComponentRole,
    CanonicalPhysicalPairRequirement,
    CanonicalPlacement,
    CanonicalPlacementOrigin,
    CanonicalGeometryFidelity,
    CanonicalPhysicalMechanism,
)
from mechcad_harness.models.geometry_identity import (
    GeometryArtifactIdentity,
    geometry_reference_hash,
)
from mechcad_harness.models.supplied_component_interface import (
    GeometryDerivationStatus,
    MaterializedInterfaceVerifier,
)
from mechcad_harness.models.generated_part import (
    GeneratedAuthorityView,
    resolve_generated_inputs,
)
from mechcad_harness.models.generated_placement import placement_derivations_hash
from mechcad_harness.models.generated_placement import CanonicalGeneratedPlacementDerivation
from mechcad_harness.generated_part_cad import verify_generated_part
from mechcad_harness.state.hashing import canonical_json


_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")


@dataclass(frozen=True)
class _ExpectedClassification:
    has_source_value: bool
    source_value: PromotionSourceValue | None = None
    required_classification: PromotionValueClassification | None = None


def _strict_hash(value: str) -> str:
    return _require_hash(value)


def _strict_hashes(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_require_hash(value) for value in values)


def _strict_nonblank_values(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_nonblank(value) for value in values)


class PromotionReadiness(Model):
    """Immutable proof that a request may enter a later promotion compiler."""

    model_config = {"frozen": True, "extra": "forbid"}

    schema_version: Literal["candidate-promotion-readiness@1"] = (
        "candidate-promotion-readiness@1"
    )
    project_id: StrictStr = Field(min_length=1)
    source_revision: StrictInt = Field(gt=0)
    source_state_hash: StrictStr
    source_binding_hash: StrictStr
    request_hash: StrictStr
    candidate_hash: StrictStr
    m12_3_result_hash: StrictStr
    evaluation_hash: StrictStr
    selection_hash: StrictStr
    evaluation_scope_hash: StrictStr
    comparison_used: StrictBool = False
    comparison_result_hash: StrictStr | None = None
    promotion_policy_hash: StrictStr
    canonical_target_mechanism_id: StrictStr = Field(min_length=1)
    mapping: tuple[CandidateCanonicalInstanceMapping, ...] = Field(min_length=1)
    classification_identities: tuple[StrictStr, ...] = Field(min_length=1)
    trusted_geometry_artifact_ids: tuple[StrictStr, ...] = ()
    readiness_hash: StrictStr = "pending"

    _validate_hashes = field_validator(
        "source_state_hash",
        "source_binding_hash",
        "request_hash",
        "candidate_hash",
        "m12_3_result_hash",
        "evaluation_hash",
        "selection_hash",
        "evaluation_scope_hash",
        "promotion_policy_hash",
    )(_strict_hash)
    _validate_optional_hash = field_validator("comparison_result_hash")(
        lambda value: None if value is None else _require_hash(value)
    )
    _validate_readiness_hash = field_validator("readiness_hash")(
        lambda value: value if value == "pending" else _require_hash(value)
    )
    _validate_text = field_validator("project_id", "canonical_target_mechanism_id")(_nonblank)
    _validate_identities = field_validator(
        "classification_identities"
    )(_strict_hashes)
    _validate_artifact_ids = field_validator("trusted_geometry_artifact_ids")(
        _strict_nonblank_values
    )

    @model_validator(mode="after")
    def validate_readiness(self) -> "PromotionReadiness":
        if self.comparison_used != (self.comparison_result_hash is not None):
            raise ValueError("readiness comparison identity must match comparison usage")
        candidate_ids = tuple(item.candidate_instance_id for item in self.mapping)
        canonical_ids = tuple(item.canonical_instance_id for item in self.mapping)
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("readiness candidate mapping IDs must be unique")
        if len(set(canonical_ids)) != len(canonical_ids):
            raise ValueError("readiness canonical mapping IDs must be unique")
        expected = _hash(self, "readiness_hash")
        if self.readiness_hash == "pending":
            object.__setattr__(self, "readiness_hash", expected)
        elif self.readiness_hash != expected:
            raise ValueError("promotion readiness hash mismatch")
        return self


class CandidatePromotionCompiler:
    """Perform the non-mutating, pre-application promotion trust boundary."""

    def __init__(
        self,
        state_manager,
        artifact_store_factory,
        *,
        evaluation_currentness_verifier=None,
        evaluation_currentness_service=None,
        cad_replay_verifier=None,
        candidate_integrity_verifier=None,
        candidate_currentness_service=None,
    ) -> None:
        if not callable(artifact_store_factory) and not isinstance(artifact_store_factory, ArtifactStore):
            raise ValueError("promotion requires an artifact store factory")
        self.state_manager = state_manager
        self.artifact_store_factory = artifact_store_factory
        self.candidate_integrity_verifier = candidate_integrity_verifier or CandidateIntegrityVerifier()
        self.candidate_currentness_service = candidate_currentness_service or CandidateCurrentnessService(
            state_manager
        )
        if evaluation_currentness_verifier is not None and evaluation_currentness_service is not None:
            raise ValueError("promotion accepts one evaluation currentness verifier")
        if evaluation_currentness_service is not None:
            self.evaluation_currentness_verifier = evaluation_currentness_service
        elif evaluation_currentness_verifier is not None:
            self.evaluation_currentness_verifier = evaluation_currentness_verifier
        else:
            if not callable(cad_replay_verifier):
                raise ValueError("promotion requires an evaluation currentness verifier or CAD replay verifier")
            self.evaluation_currentness_verifier = CandidateEvaluationCurrentnessService(
                state_manager, cad_replay_verifier=cad_replay_verifier
            )

    def validate_readiness(self, request: CandidatePromotionRequest) -> PromotionReadiness:
        request = self._revalidate_request(request)
        current = self.state_manager.load_current_state(request.project_id)
        current_hash = state_hash(current)
        if (request.source_revision, request.source_state_hash) != (
            current.revision,
            current_hash,
        ):
            raise ValueError("promotion source revision or state hash is stale")

        candidate = request.candidate
        self._verify_candidate(candidate, request)
        self._verify_m12_result(request)
        self._verify_evaluation(request)
        self._verify_selection(request)
        self._verify_comparison(request)
        self._verify_policy(request.promotion_policy, candidate)
        if any(
            mechanism.id == request.canonical_target_mechanism_id
            for mechanism in current.physical_mechanisms
        ):
            raise ValueError("promotion target mechanism path already exists")
        trusted_geometry_ids = self._verify_geometry_sources(request)
        mapping = self.map_instances(request)
        self._verify_generated_authority_survival(request, mapping)
        self._verify_placement_derivation_binding(request)

        return PromotionReadiness(
            project_id=request.project_id,
            source_revision=request.source_revision,
            source_state_hash=request.source_state_hash,
            source_binding_hash=_hash(candidate.source_binding),
            request_hash=request.request_hash,
            candidate_hash=candidate.candidate_hash,
            m12_3_result_hash=request.m12_3_result.result_hash,
            evaluation_hash=request.evaluation.evaluation_hash,
            selection_hash=request.selection.selection_hash,
            evaluation_scope_hash=request.evaluation.evaluation_scope_hash,
            comparison_used=request.comparison_used,
            comparison_result_hash=(
                None if request.comparison is None else request.comparison.result_hash
            ),
            promotion_policy_hash=request.promotion_policy.policy_hash,
            canonical_target_mechanism_id=request.canonical_target_mechanism_id,
            mapping=mapping,
            classification_identities=tuple(
                classification.classification_hash for classification in request.classifications
            ),
            trusted_geometry_artifact_ids=trusted_geometry_ids,
        )

    def map_instances(
        self, request: CandidatePromotionRequest
    ) -> tuple[CandidateCanonicalInstanceMapping, ...]:
        request = self._revalidate_request(request)
        self._validate_identifier(request.canonical_target_mechanism_id, "canonical mechanism ID")
        expected = self._expected_classifications(request)
        classifications = self._classifications_by_identity(request, expected)
        mappings = []
        for component in request.candidate.realization.components:
            self._validate_identifier(component.instance_id, "candidate instance ID")
            identity = f"candidate:physical-instance:{component.instance_id}"
            classification = classifications[identity]
            if classification.classification in (
                PromotionValueClassification.DO_NOT_PROMOTE,
                PromotionValueClassification.PROVENANCE_ONLY,
            ):
                raise ValueError("physical instance classification is not promotable")
            canonical_id = f"{request.canonical_target_mechanism_id}:{component.instance_id}"
            mappings.append(
                CandidateCanonicalInstanceMapping(
                    candidate_instance_id=component.instance_id,
                    canonical_instance_id=canonical_id,
                    canonical_path=(
                        f"/physical_mechanisms/{request.canonical_target_mechanism_id}"
                        f"/components/{canonical_id}"
                    ),
                    classification=classification.classification,
                    source_identity=classification.source_identity,
                    source_provenance=classification.source_provenance,
                    source_value=classification.source_value,
                )
            )
        if len({item.canonical_path for item in mappings}) != len(mappings):
            raise ValueError("promotion canonical mapping path collision")
        return tuple(mappings)

    def compile(self, state, request: CandidatePromotionRequest) -> CandidatePromotionCompilation:
        """Compile a ready candidate into one immutable canonical add proposal.

        The candidate and its execution records are read only at this boundary.  The
        returned mechanism contains reconstructed physical semantics, never the
        candidate's CAD, M10, evaluation, comparison, or runtime payloads.
        """

        request = self._revalidate_request(request)
        current = self.state_manager.load_current_state(request.project_id)
        current_hash = state_hash(current)
        supplied_hash = state_hash(state)
        if (state.revision, supplied_hash) != (current.revision, current_hash):
            raise ValueError("promotion compile state is not the current canonical state")
        if (request.source_revision, request.source_state_hash) != (state.revision, supplied_hash):
            raise ValueError("promotion compile request is not bound to the supplied state")

        readiness = self.validate_readiness(request)
        mapping = readiness.mapping
        mechanism = self._compile_mechanism(request, mapping)
        projection = self._projection(mechanism)
        operation = ChangeOperation(
            operation="add",
            path=f"/physical_mechanisms/{mechanism.id}",
            value=mechanism.model_dump(mode="json"),
        )
        proposal = ChangeProposal(
            id=f"promotion:{mechanism.id}",
            title=f"Promote {mechanism.id}",
            status=ProposalStatus.DRAFT,
            base_revision=state.revision,
            base_state_hash=supplied_hash,
            actor="mechcad-physical-mechanism",
            operations=[operation],
        )
        return CandidatePromotionCompilation(
            canonical_mechanism=mechanism,
            proposal=proposal,
            promotion_proposal_hash=promotion_proposal_hash(
                state.revision, supplied_hash, (operation,)
            ),
            mapping=mapping,
            projection=projection,
        )

    def promote_selected_candidate(
        self, request: CandidatePromotionRequest, run_controller, *, manifest_service=None
    ) -> CandidatePromotionApplicationResult:
        return CandidatePromotionApplicationService(
            self, run_controller, manifest_service=manifest_service
        ).promote_selected_candidate(request)

    @staticmethod
    def _projection(
        mechanism: CanonicalPhysicalMechanism,
    ) -> PromotableMechanismProjection:
        return PromotableMechanismProjection(
            canonical_target_mechanism_id=mechanism.id,
            canonical_instance_ids=tuple(component.instance_id for component in mechanism.components),
            component_specifications=mechanism.component_specifications,
            components=mechanism.components,
            accepted_design_choices=mechanism.accepted_design_choices,
            placements=mechanism.placements,
            connections=mechanism.connections,
            joint_bindings=mechanism.joint_bindings,
            m10_obligations=mechanism.m10_obligations,
            generated_placement_derivations=mechanism.generated_placement_derivations,
            mapping_identities=tuple(component.instance_id for component in mechanism.components),
        )

    def _compile_mechanism(
        self,
        request: CandidatePromotionRequest,
        mapping: tuple[CandidateCanonicalInstanceMapping, ...],
    ) -> CanonicalPhysicalMechanism:
        candidate = request.candidate
        canonical_by_candidate = {
            item.candidate_instance_id: item.canonical_instance_id for item in mapping
        }
        classifications = {
            item.source_identity: item for item in request.classifications
        }

        canonical_specs_by_candidate_hash = {
            specification.specification_hash: self._canonical_specification(specification)
            for specification in candidate.component_specifications
        }
        specifications = tuple(canonical_specs_by_candidate_hash.values())
        choices = tuple(
            self._canonical_choice(variable, classifications, canonical_by_candidate)
            for variable in candidate.design_variables
        )
        generated_derivations = self._canonical_generated_placement_derivations(
            request, canonical_by_candidate
        )
        placements = self._canonical_placements(
            candidate,
            classifications,
            canonical_by_candidate,
            request=request,
            generated_derivations=generated_derivations,
        )
        placement_ids = {placement.instance_id: placement.placement_id for placement in placements}
        components = tuple(
            CanonicalPhysicalComponent(
                instance_id=canonical_by_candidate[component.instance_id],
                specification_hash=canonical_specs_by_candidate_hash[
                    component.specification_hash
                ].specification_hash,
                role=CanonicalPhysicalComponentRole(component.role.value),
                interfaces=component.interfaces,
                placement_id=placement_ids.get(canonical_by_candidate[component.instance_id]),
            )
            for component in candidate.realization.components
        )
        connections = tuple(
            CanonicalMechanicalConnection(
                connection_id=connection.connection_id,
                kind=CanonicalMechanicalConnectionKind(connection.kind.value),
                from_instance_id=canonical_by_candidate[connection.from_instance_id],
                from_interface_id=connection.from_interface_id,
                to_instance_id=canonical_by_candidate[connection.to_instance_id],
                to_interface_id=connection.to_interface_id,
                meanings=tuple(CanonicalConnectionMeaning(meaning.value) for meaning in connection.meanings),
            )
            for connection in candidate.realization.connections
        )
        joint_bindings, obligations = self._canonical_motion_semantics(
            request, canonical_by_candidate
        )
        return CanonicalPhysicalMechanism(
            schema_version=(
                "canonical-physical-mechanism@2"
                if generated_derivations
                else "canonical-physical-mechanism@1"
            ),
            id=request.canonical_target_mechanism_id,
            name=f"Promoted mechanism {request.canonical_target_mechanism_id}",
            component_specifications=specifications,
            components=components,
            accepted_design_choices=choices,
            placements=placements,
            connections=connections,
            joint_bindings=joint_bindings,
            m10_obligations=obligations,
            generated_placement_derivations=generated_derivations,
            promotion_provenance=(
                f"candidate:{candidate.candidate_hash}",
                f"request:{request.request_hash}",
            ),
        )

    @staticmethod
    def _canonical_specification(specification) -> CanonicalComponentSpecification:
        geometry = specification.geometry_source
        return CanonicalComponentSpecification(
            schema_version=(
                "canonical-component-specification@3"
                if specification.schema_version == "component-specification@3"
                else "canonical-component-specification@2"
                if specification.schema_version == "component-specification@2"
                else "canonical-component-specification@1"
            ),
            component_type=specification.component_type,
            manufacturer=specification.manufacturer,
            part_number=specification.part_number,
            source_identity=specification.source_identity,
            properties=tuple(
                CanonicalComponentProperty(
                    key=prop.key,
                    availability=CanonicalComponentPropertyAvailability(prop.availability.value),
                    normalized_value=prop.normalized_value,
                    normalized_range=prop.normalized_range,
                    canonical_unit=prop.canonical_unit,
                    source_identity=prop.source_identity,
                    authority=prop.authority.value,
                    applicability_context=prop.applicability_context,
                    conversion_provenance=prop.conversion_provenance,
                )
                for prop in specification.properties
            ),
            geometry_source=(
                None
                if geometry is None
                else CanonicalGeometrySourceReference(
                    artifact_id=geometry.artifact_id,
                    artifact_hash=geometry.artifact_hash,
                    source_identity=geometry.source_identity,
                    coordinate_system_id=geometry.coordinate_system_id,
                )
            ),
            generated_part=(
                specification.generated_part
                if specification.schema_version == "component-specification@3"
                else None
            ),
            interfaces=specification.interfaces,
            compatibility_declarations=specification.compatibility_declarations,
            supplied_reference_frames=specification.supplied_reference_frames,
            supplied_interface_definitions=specification.supplied_interface_definitions,
            geometry_derivation_transforms=specification.geometry_derivation_transforms,
            specification_hash="pending",
        )

    @staticmethod
    def _canonical_choice(variable, classifications, canonical_by_candidate):
        identity = f"candidate:design-variable:{variable.name}"
        classification = classifications[identity]
        if classification.source_provenance is InputProvenanceKind.POLICY_ASSUMPTION:
            origin = CanonicalDesignChoiceOrigin.EXPLICIT_POLICY_ASSUMPTION
            provenance = f"explicit-policy-assumption:{identity}"
        else:
            origin = CanonicalDesignChoiceOrigin.CANDIDATE_LOCAL_CHOICE
            provenance = f"candidate-local-choice:{identity}"
        choice_key = variable.name
        prefix, separator, suffix = variable.name.partition(".")
        if separator and prefix in canonical_by_candidate:
            choice_key = f"{canonical_by_candidate[prefix]}.{suffix}"
        return CanonicalAcceptedDesignChoice(
            key=choice_key,
            value=variable.value,
            origin=origin,
            provenance=provenance,
            source_identities=(identity,),
        )

    @staticmethod
    def _canonical_placements(
        candidate,
        classifications,
        canonical_by_candidate,
        *,
        request=None,
        generated_derivations=(),
    ):
        variables = {variable.name: variable for variable in candidate.design_variables}
        derivations_by_target = {
            derivation.target_canonical_instance_id: derivation
            for derivation in generated_derivations
        }
        placements = []
        for component in candidate.realization.components:
            generated_derivation = derivations_by_target.get(
                canonical_by_candidate[component.instance_id]
            )
            if generated_derivation is not None:
                target_mapping = next(
                    (
                        mapping
                        for mapping in request.evaluation.cad_request.mappings
                        if mapping.physical_instance_id == component.instance_id
                    ),
                    None,
                )
                if target_mapping is None:
                    raise ValueError("canonical generated placement mapping is missing")
                specifications = {
                    specification.specification_hash: specification
                    for specification in candidate.component_specifications
                }
                transform = CandidateCadRealizationService._derived_placement(
                    None,
                    request.evaluation.cad_request,
                    target_mapping,
                    specifications,
                    candidate,
                )
                target_hash = (
                    generated_derivation.target_generated_interface_hash
                    if generated_derivation.target_generated_interface_hash is not None
                    else generated_derivation.target_generated_frame_hash
                )
                assert target_hash is not None
                placements.append(
                    CanonicalPlacement(
                        placement_id=f"{canonical_by_candidate[component.instance_id]}:placement",
                        instance_id=canonical_by_candidate[component.instance_id],
                        origin=CanonicalPlacementOrigin.DETERMINISTIC_RELATION,
                        input_identities=(
                            generated_derivation.source_interface_hash,
                            target_hash,
                            *sorted(item.input_hash for item in generated_derivation.inputs),
                            *(() if generated_derivation.rotation is None else (
                                generated_derivation.rotation.input_hash,
                            )),
                        ),
                        relation=generated_derivation.rule_id,
                        x_mm=transform.x_mm,
                        y_mm=transform.y_mm,
                        z_mm=transform.z_mm,
                        rotation_quaternion=transform.rotation_quaternion,
                    )
                )
                continue
            names = tuple(
                f"{component.instance_id}.placement.{axis}" for axis in ("x_mm", "y_mm", "z_mm")
            )
            present = tuple(name in variables for name in names)
            if not any(present):
                continue
            if not all(present):
                raise ValueError(
                    f"placement inputs are incomplete for candidate instance {component.instance_id}"
                )
            identities = tuple(f"candidate:design-variable:{name}" for name in names)
            if any(identity not in classifications for identity in identities):
                raise ValueError("placement input is not explicitly classified")
            values = tuple(variables[name].value for name in names)
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
                raise ValueError("placement design variables must be numeric")
            placement = CanonicalPlacement(
                placement_id=f"{canonical_by_candidate[component.instance_id]}:placement",
                instance_id=canonical_by_candidate[component.instance_id],
                origin=CanonicalPlacementOrigin.ACCEPTED_DESIGN_CHOICE,
                input_identities=identities,
                relation="accepted-design-variable-placement@1",
                x_mm=float(values[0]),
                y_mm=float(values[1]),
                z_mm=float(values[2]),
            )
            placements.append(placement)
        return tuple(placements)

    @staticmethod
    def _canonical_generated_placement_derivations(request, canonical_by_candidate):
        cad_request = getattr(getattr(request, "evaluation", None), "cad_request", None)
        if cad_request is None:
            return ()
        result = []
        for derivation in getattr(cad_request, "placement_derivations", ()):
            try:
                source_id = canonical_by_candidate[derivation.source_physical_instance_id]
                target_id = canonical_by_candidate[derivation.target_physical_instance_id]
            except KeyError as exc:
                raise ValueError("canonical generated placement references an unknown instance") from exc
            source_frame = derivation.source_frame_ref
            target_frame = derivation.target_generated_frame_ref
            target_interface = derivation.target_generated_interface_ref
            result.append(
                CanonicalGeneratedPlacementDerivation(
                    derivation_id=derivation.derivation_id,
                    rule_id=derivation.rule_id,
                    source_canonical_instance_id=source_id,
                    source_interface_id=derivation.source_interface_ref.interface_id,
                    source_interface_hash=derivation.source_interface_ref.interface_hash,
                    source_frame_id=None if source_frame is None else source_frame.frame_id,
                    source_frame_hash=None if source_frame is None else source_frame.frame_hash,
                    source_placement_ref=derivation.source_placement_ref,
                    target_canonical_instance_id=target_id,
                    target_generated_interface_id=(
                        None if target_interface is None else target_interface.interface_id
                    ),
                    target_generated_interface_hash=(
                        None if target_interface is None else target_interface.interface_hash
                    ),
                    target_generated_frame_id=None if target_frame is None else target_frame.frame_id,
                    target_generated_frame_hash=None if target_frame is None else target_frame.frame_hash,
                    inputs=derivation.inputs,
                    rotation=derivation.rotation,
                )
            )
        return tuple(result)

    def _canonical_motion_semantics(self, request, canonical_by_candidate):
        evaluation = request.evaluation
        scope = evaluation.m10_scope
        binding = evaluation.m10_binding
        if scope is None or binding is None:
            if scope is not None or binding is not None:
                raise ValueError("canonical M10 semantics require both scope and binding")
            return (), ()

        dispositions = {
            entry.constituent_key: entry.physical_instance_id
            for entry in binding.constituent_dispositions
        }
        cad_to_physical = {
            entry.cad_instance_id: entry.physical_instance_id
            for entry in binding.constituent_dispositions
        }

        def physical_id(constituent_key: str) -> str:
            candidate_id = dispositions.get(constituent_key, constituent_key)
            if candidate_id not in canonical_by_candidate:
                raise ValueError(f"canonical M10 semantic references unknown instance: {constituent_key}")
            return canonical_by_candidate[candidate_id]

        model_joints = tuple(binding.model.joints)
        if not model_joints:
            raise ValueError("canonical M10 semantics require a joint model")
        selected_joint = next(
            (joint for joint in model_joints if joint.joint_id == binding.output_joint_id),
            None,
        )
        if selected_joint is None:
            raise ValueError(
                "canonical M10 binding output joint is missing from the selected joint model"
            )
        parent_candidate = cad_to_physical.get(
            selected_joint.parent_instance_id, selected_joint.parent_instance_id
        )
        child_candidate = cad_to_physical.get(
            selected_joint.child_instance_id, selected_joint.child_instance_id
        )
        if parent_candidate not in canonical_by_candidate or child_candidate not in canonical_by_candidate:
            raise ValueError("canonical M10 joint references an unknown instance")
        physical_binding = next(
            (
                item
                for item in request.candidate.realization.joint_bindings
                if item.joint_id == selected_joint.joint_id
            ),
            None,
        )
        if physical_binding is None:
            raise ValueError(
                "canonical M10 joint has no exact candidate physical joint binding correspondence"
            )
        if physical_binding.driven_instance_id != child_candidate:
            raise ValueError(
                "canonical M10 joint physical binding child does not match the selected joint"
            )
        canonical_joint_id = scope.output_joint_semantic_key
        joint_binding = CanonicalJointPhysicalBinding(
            joint_id=canonical_joint_id,
            expected_parent_instance_id=canonical_by_candidate[parent_candidate],
            expected_child_instance_id=canonical_by_candidate[child_candidate],
            axis_origin_x_mm=selected_joint.axis_origin_x_mm,
            axis_origin_y_mm=selected_joint.axis_origin_y_mm,
            axis_origin_z_mm=selected_joint.axis_origin_z_mm,
            axis_direction_x=selected_joint.axis_direction_x,
            axis_direction_y=selected_joint.axis_direction_y,
            axis_direction_z=selected_joint.axis_direction_z,
            axis_frame_reference=(
                physical_binding.axis_frame_reference
            ),
            semantic_hash=self._canonical_joint_semantic_hash(
                canonical_joint_id,
                canonical_by_candidate[parent_candidate],
                canonical_by_candidate[child_candidate],
                selected_joint,
                binding.model.evaluator_version,
            ),
            semantic_version=binding.model.evaluator_version,
        )

        if scope.policy_assumptions:
            raise ValueError(
                "canonical M10 obligation cannot represent candidate scope policy assumptions"
            )
        pair_requirements = []
        for requirement in scope.pair_scope_requirements:
            if requirement.required_classification.value != "check_clearance":
                raise ValueError(
                    "canonical M10 obligation cannot represent non-clearance scope classifications"
                )
            first_candidate_id = dispositions.get(
                requirement.first_constituent_key, requirement.first_constituent_key
            )
            second_candidate_id = dispositions.get(
                requirement.second_constituent_key, requirement.second_constituent_key
            )
            pair_requirements.append(
                CanonicalPhysicalPairRequirement(
                    requirement_key=requirement.requirement_key,
                    first_instance_id=physical_id(requirement.first_constituent_key),
                    first_interface_id=self._interface_for(
                        request,
                        first_candidate_id,
                        second_candidate_id,
                        requirement.first_constituent_key,
                    ),
                    second_instance_id=physical_id(requirement.second_constituent_key),
                    second_interface_id=self._interface_for(
                        request,
                        second_candidate_id,
                        first_candidate_id,
                        requirement.second_constituent_key,
                    ),
                    requires_home_exact_check=requirement.requires_home_exact_check,
                )
            )
        if not pair_requirements:
            raise ValueError(
                "canonical M10 obligation requires at least one supported clearance pair"
            )
        obligations = (
            CanonicalM10VerificationObligation(
                joint_semantic_key=canonical_joint_id,
                angle_interval_deg=scope.angle_interval_deg,
                required_clearance_mm=scope.required_clearance_mm,
                physical_pair_requirements=tuple(pair_requirements),
                fidelity_requirements=tuple(
                    (
                        physical_id(constituent_key),
                        CanonicalGeometryFidelity(fidelity.value),
                    )
                    for constituent_key, fidelity in scope.fidelity_requirements
                ),
                required_home_check_semantics=scope.required_home_check_semantics,
            ),
        )
        return (joint_binding,), obligations

    @staticmethod
    def _canonical_joint_semantic_hash(
        joint_id: str,
        parent_instance_id: str,
        child_instance_id: str,
        joint,
        semantic_version: str,
    ) -> str:
        payload = {
            "joint_id": joint_id,
            "joint_kind": joint.joint_kind.value,
            "parent_instance_id": parent_instance_id,
            "child_instance_id": child_instance_id,
            "axis_origin": [
                joint.axis_origin_x_mm,
                joint.axis_origin_y_mm,
                joint.axis_origin_z_mm,
            ],
            "axis_direction": [
                joint.axis_direction_x,
                joint.axis_direction_y,
                joint.axis_direction_z,
            ],
            "semantic_version": semantic_version,
        }
        return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()

    @staticmethod
    def _interface_for(
        request,
        candidate_instance_id: str,
        other_instance_id: str,
        constituent_key: str,
    ) -> str:
        component = next(
            (
                component
                for component in request.candidate.realization.components
                if component.instance_id == candidate_instance_id
            ),
            None,
        )
        if component is None or not component.interfaces:
            raise ValueError(f"canonical M10 pair lacks an interface for {constituent_key}")
        declared = set(component.interfaces)
        candidates = set()
        for connection in request.candidate.realization.connections:
            if (
                connection.from_instance_id == candidate_instance_id
                and connection.to_instance_id == other_instance_id
            ):
                candidates.add(connection.from_interface_id)
            elif (
                connection.to_instance_id == candidate_instance_id
                and connection.from_instance_id == other_instance_id
            ):
                candidates.add(connection.to_interface_id)
        if candidates and not candidates <= declared:
            raise ValueError(f"canonical M10 pair interface is not declared for {constituent_key}")
        if len(candidates) > 1:
            raise ValueError(f"canonical M10 pair interface is ambiguous for {constituent_key}")
        if len(candidates) == 1:
            return next(iter(candidates))
        if len(declared) == 1:
            return next(iter(declared))
        raise ValueError(f"canonical M10 pair interface is ambiguous for {constituent_key}")

    def _revalidate_request(self, request: CandidatePromotionRequest) -> CandidatePromotionRequest:
        try:
            return CandidatePromotionRequest.model_validate(request.model_dump(mode="json"))
        except Exception as exc:
            raise ValueError(f"promotion request integrity failure: {exc}") from exc

    def _verify_candidate(self, candidate: MechanicalDesignCandidate, request) -> None:
        try:
            self.candidate_integrity_verifier.verify(
                candidate, request.synthesis_request, request.synthesis_policy
            )
            currentness = self.candidate_currentness_service.evaluate(
                candidate, request.synthesis_request, request.synthesis_policy
            )
        except Exception as exc:
            raise ValueError(f"promotion candidate integrity/currentness failure: {exc}") from exc
        if currentness is not CandidateCurrentness.CURRENT:
            raise ValueError(f"promotion candidate is not current: {currentness.value}")
        if candidate.candidate_hash != candidate_hash(candidate):
            raise ValueError("promotion candidate hash mismatch")
        if candidate.unresolved_items:
            raise ValueError("promotion candidate contains unresolved items")

    def _verify_m12_result(self, request: CandidatePromotionRequest) -> None:
        result = request.m12_3_result
        candidate = request.candidate
        source_binding_hash = _hash(candidate.source_binding)
        try:
            result = type(result).model_validate(result.model_dump(mode="json"))
        except Exception as exc:
            raise ValueError(f"promotion M12-3 result integrity failure: {exc}") from exc
        if result.result_hash != admissibility_result_hash(result):
            raise ValueError("promotion M12-3 result identity is stale")
        if result.status is not DriveAdmissibility.ADMISSIBLE:
            raise ValueError("promotion requires an ADMISSIBLE M12-3 result")
        if (
            result.candidate_hash != candidate.candidate_hash
            or result.source_binding_hash != source_binding_hash
            or result.synthesis_request_hash != request.synthesis_request.request_hash
            or result.synthesis_policy_hash != request.synthesis_policy.policy_hash
        ):
            raise ValueError("promotion M12-3 result binding mismatch")
        if result.result_hash != request.evaluation.m12_3_result_hash:
            raise ValueError("promotion M12-3 result identity does not match evaluation")
        if result.design_variables != candidate.design_variables:
            raise ValueError("promotion M12-3 design variable substitution")

        specifications = {
            specification.specification_hash: specification
            for specification in candidate.component_specifications
        }
        components = {
            component.instance_id: component for component in candidate.realization.components
        }
        properties = {
            (component.instance_id, prop.key): (component, specifications[component.specification_hash], prop)
            for component in candidate.realization.components
            for prop in specifications[component.specification_hash].properties
        }
        for binding in result.consumed_property_bindings:
            actual = properties.get((binding.component_instance_id, binding.property_key))
            if actual is None:
                raise ValueError("promotion M12-3 consumed property substitution")
            component, specification, prop = actual
            if (
                binding.specification_hash != specification.specification_hash
                or binding.property_hash != prop.property_hash
                or binding.source_identity != prop.source_identity
                or binding.authority.value != prop.authority.value
            ):
                raise ValueError("promotion M12-3 consumed property binding substitution")
        if any(
            binding.component_instance_id not in components
            for binding in result.consumed_property_bindings
        ):
            raise ValueError("promotion M12-3 consumed property references an unknown instance")

    def _verify_evaluation(self, request: CandidatePromotionRequest) -> None:
        evaluation = request.evaluation
        if evaluation.outcome is not CandidateEvaluationOutcome.FEASIBLE:
            raise ValueError("promotion requires a FEASIBLE candidate evaluation")
        if evaluation.unresolved_findings:
            raise ValueError("promotion cannot use an evaluation with unresolved findings")
        if evaluation.evaluation_hash != _hash(evaluation, "evaluation_hash"):
            raise ValueError("promotion candidate evaluation identity is stale")
        if evaluation.cad_stage_outcome.status.value == "success":
            if evaluation.cad_request is None:
                raise ValueError("promotion evaluation is missing the exact CAD request")
            try:
                _validate_cad_inputs(
                    request.candidate,
                    evaluation.cad_request,
                    evaluation.cad_stage_outcome,
                )
            except Exception as exc:
                raise ValueError(f"promotion candidate CAD integrity failure: {exc}") from exc
        if evaluation.m10_stage_outcome.status.value != "not_reached":
            if any(
                value is None
                for value in (
                    evaluation.m10_request,
                    evaluation.m10_scope,
                    evaluation.m10_binding,
                )
            ):
                raise ValueError("promotion evaluation is missing exact M10 inputs")
            try:
                _validate_m10_inputs(
                    request.candidate,
                    evaluation.cad_stage_outcome,
                    evaluation.m10_stage_outcome,
                    evaluation.m10_request,
                    evaluation.m10_scope,
                    evaluation.m10_binding,
                )
            except Exception as exc:
                raise ValueError(f"promotion candidate M10 integrity failure: {exc}") from exc
        try:
            current = self.evaluation_currentness_verifier.verify_current(
                evaluation,
                request.candidate,
                request.synthesis_request,
                request.synthesis_policy,
                m12_3_result=request.m12_3_result,
                cad_stage_outcome=evaluation.cad_stage_outcome,
                m10_stage_outcome=evaluation.m10_stage_outcome,
                policy=evaluation.policy,
                cad_request=evaluation.cad_request,
                m10_request=evaluation.m10_request,
                m10_scope=evaluation.m10_scope,
                m10_binding=evaluation.m10_binding,
            )
        except Exception as exc:
            raise ValueError(f"promotion evaluation currentness verification failed: {exc}") from exc
        if current is not True:
            raise ValueError("promotion candidate evaluation is not current")

    def _verify_selection(self, request: CandidatePromotionRequest) -> None:
        selection = request.selection
        if selection.selection_hash != candidate_selection_hash(selection):
            raise ValueError("promotion selection identity is stale")
        try:
            candidate, evaluation, source_binding_hash = CandidateSelectionService._validate_candidate_evaluation(
                request.candidate, request.evaluation
            )
        except Exception as exc:
            raise ValueError(f"promotion selection validation failed: {exc}") from exc
        if (
            selection.candidate_hash != candidate.candidate_hash
            or selection.evaluation_hash != evaluation.evaluation_hash
            or selection.source_binding_hash != source_binding_hash
            or selection.evaluation_scope_hash != evaluation.evaluation_scope_hash
        ):
            raise ValueError("promotion selection candidate/evaluation binding mismatch")

    def _verify_comparison(self, request: CandidatePromotionRequest) -> None:
        if request.selection.comparison_used != request.comparison_used:
            raise ValueError("promotion comparison flag does not match selection")
        if not request.comparison_used:
            if any(
                value is not None
                for value in (request.comparison, request.comparison_request, request.comparison_entries)
            ):
                raise ValueError("promotion comparison flag does not match supplied records")
            if request.selection.comparison_used:
                raise ValueError("promotion comparison flag does not match selection")
            return
        if request.comparison is None or request.comparison_request is None or request.comparison_entries is None:
            raise ValueError("promotion comparison records are incomplete")
        comparison = request.comparison
        comparison_request = request.comparison_request
        if (
            candidate_comparison_policy_hash(comparison.policy) != comparison.policy_hash
            or candidate_comparison_request_hash(comparison_request) != comparison_request.request_hash
            or candidate_comparison_result_hash(comparison) != comparison.result_hash
        ):
            raise ValueError("promotion comparison identity is stale")
        if comparison_request.request_hash != comparison.request_hash:
            raise ValueError("promotion comparison request/result identity mismatch")
        if request.selection.comparison_result_hash != comparison.result_hash:
            raise ValueError("promotion selection comparison binding mismatch")
        try:
            rebuilt = CandidateComparisonService(
                comparison.policy,
                project_id=request.project_id,
                currentness_verifier=self.evaluation_currentness_verifier,
            ).compare(comparison_request, request.comparison_entries)
        except Exception as exc:
            raise ValueError(f"promotion comparison validation failed: {exc}") from exc
        if rebuilt != comparison:
            raise ValueError("promotion comparison result does not match exact entries")

    def _verify_policy(self, policy: CandidatePromotionPolicy, candidate) -> None:
        if policy.allowed_target_family != "canonical_physical_mechanism":
            raise ValueError("promotion target family is not supported")
        has_v2_or_v3_specification = any(
            specification.schema_version in {
                "component-specification@2",
                "component-specification@3",
            }
            for specification in candidate.component_specifications
        )
        expected_mapping_schema = (
            "candidate-canonical-mapping@2"
            if has_v2_or_v3_specification
            else "candidate-canonical-mapping@1"
        )
        if policy.mapping_schema_version != expected_mapping_schema:
            raise ValueError("promotion mapping schema is not supported for candidate specification schemas")
        if policy.compiler_version != "candidate-promotion@1":
            raise ValueError("promotion compiler version is not supported")
        expected_authorities = set(policy.required_property_authorities)
        actual_authorities = {
            prop.authority.value
            for specification in candidate.component_specifications
            for prop in specification.properties
        }
        if not {authority.value for authority in expected_authorities} <= actual_authorities:
            raise ValueError("promotion required property authority is missing")

    def _verify_generated_authority_survival(self, request, mapping=()):
        """Verify generated inputs and relation bindings on both projection layers."""
        candidate = request.candidate
        generated_specifications = tuple(
            specification
            for specification in candidate.component_specifications
            if specification.schema_version == "component-specification@3"
        )
        if not generated_specifications:
            return

        expected = self._expected_classifications(request)
        classifications = self._classifications_by_identity(request, expected)
        canonical_by_candidate = {
            item.candidate_instance_id: item.canonical_instance_id for item in mapping
        }
        canonical_specifications = tuple(
            self._canonical_specification(specification)
            for specification in candidate.component_specifications
        )
        canonical_by_candidate_hash = {
            candidate_specification.specification_hash: canonical_specification
            for candidate_specification, canonical_specification in zip(
                candidate.component_specifications, canonical_specifications
            )
        }
        canonical_choices = tuple(
            self._canonical_choice(variable, classifications, canonical_by_candidate)
            for variable in candidate.design_variables
        )
        canonical_interfaces = tuple(
            interface
            for specification in canonical_specifications
            for interface in specification.supplied_interface_definitions
        )
        canonical_frames = tuple(
            frame
            for specification in canonical_specifications
            for frame in specification.supplied_reference_frames
        )
        components_by_specification = {
            specification.specification_hash: tuple(
                component
                for component in candidate.realization.components
                if component.specification_hash == specification.specification_hash
            )
            for specification in generated_specifications
        }

        for specification in generated_specifications:
            generated = specification.generated_part
            assert generated is not None
            canonical = canonical_by_candidate_hash.get(specification.specification_hash)
            if canonical is None or canonical.generated_part is None:
                raise ValueError("generated specification did not survive canonical projection")
            if generated.model_dump(mode="json") != canonical.generated_part.model_dump(mode="json"):
                raise ValueError("generated specification semantic substitution")
            generated_identity = (
                f"candidate:generated-part:{specification.specification_hash}:"
                f"{generated.generated_part_id}"
            )
            if (
                classifications[generated_identity].classification
                is not PromotionValueClassification.ACCEPTED_PHYSICAL_FACT
                or classifications[generated_identity].source_value != generated.generated_part_hash
            ):
                raise ValueError("generated part classification is incorrect")

            candidate_view = build_candidate_view(candidate, specification.specification_hash)
            canonical_view = GeneratedAuthorityView(
                component_properties=canonical.properties,
                design_selections={choice.key: choice for choice in canonical_choices},
                interface_definitions=canonical_interfaces,
                supplied_interfaces=canonical_interfaces,
                reference_frames=canonical_frames
                + tuple(canonical.generated_part.reference_frames),
                generated_interfaces=tuple(canonical.generated_part.interfaces),
            )
            canonical_instances = components_by_specification.get(
                specification.specification_hash, ()
            )
            if not canonical_instances:
                raise ValueError("generated specification is not bound to a physical instance")
            for component in canonical_instances:
                canonical_instance_id = canonical_by_candidate.get(component.instance_id)
                if canonical_instance_id is None:
                    raise ValueError("generated specification instance mapping is missing")
                try:
                    candidate_values = resolve_generated_inputs(
                        generated.inputs,
                        candidate_view,
                        owning_instance_context=component.instance_id,
                    )
                    canonical_values = resolve_generated_inputs(
                        canonical.generated_part.inputs,
                        canonical_view,
                        owning_instance_context=canonical_instance_id,
                    )
                    verify_generated_part(
                        generated,
                        candidate_view,
                        owning_instance_context=component.instance_id,
                    )
                    verify_generated_part(
                        canonical.generated_part,
                        canonical_view,
                        owning_instance_context=canonical_instance_id,
                    )
                except Exception as exc:
                    raise ValueError(
                        "generated authority input or binding did not survive promotion"
                    ) from exc
                if candidate_values != canonical_values:
                    raise ValueError("generated authority input value substitution")

    def _verify_placement_derivation_binding(self, request):
        candidate = request.candidate
        generated_specifications = tuple(
            specification
            for specification in candidate.component_specifications
            if specification.schema_version == "component-specification@3"
        )
        if not generated_specifications:
            return
        evaluation = request.evaluation
        cad_request = evaluation.cad_request
        if (
            cad_request is None
            or cad_request.schema_version != "candidate-cad-realization-request@2"
            or not cad_request.placement_derivations
        ):
            raise ValueError("generated promotion requires a non-empty candidate CAD derivation set")
        expected_hash = placement_derivations_hash(cad_request.placement_derivations)
        if cad_request.placement_derivations_hash != expected_hash:
            raise ValueError("promotion placement derivation set hash mismatch")
        stage = evaluation.cad_stage_outcome
        realization = stage.realization
        if realization is None or realization.placement_derivations_hash != expected_hash:
            raise ValueError("promotion CAD realization derivation set binding mismatch")
        if realization.request_hash != cad_request.request_hash:
            raise ValueError("promotion CAD request derivation set substitution")
        if evaluation.m10_stage_outcome.cad_realization_hash != realization.realization_hash:
            raise ValueError("promotion selected M10 realization derivation set mismatch")

        specifications = {
            specification.specification_hash: specification
            for specification in candidate.component_specifications
        }
        generated_targets = {
            component.instance_id
            for component in candidate.realization.components
            if specifications[component.specification_hash].schema_version
            == "component-specification@3"
        }
        derivation_targets = {
            derivation.target_physical_instance_id
            for derivation in cad_request.placement_derivations
        }
        if derivation_targets != generated_targets:
            raise ValueError("promotion derivation set does not cover generated targets")

        mappings = {
            mapping.physical_instance_id: mapping for mapping in cad_request.mappings
        }
        for derivation in cad_request.placement_derivations:
            mapping = mappings.get(derivation.target_physical_instance_id)
            if mapping is None:
                raise ValueError("promotion generated placement mapping is missing")
            try:
                CandidateCadRealizationService._derived_placement(
                    None,
                    cad_request,
                    mapping,
                    specifications,
                    candidate,
                )
            except Exception as exc:
                raise ValueError(
                    "promotion candidate CAD placement does not match semantic derivation"
                ) from exc

    def _verify_geometry_sources(self, request: CandidatePromotionRequest) -> tuple[str, ...]:
        sources = []
        for specification in request.candidate.component_specifications:
            if specification.geometry_source is not None:
                sources.append(specification.geometry_source)
            for transform in getattr(specification, "geometry_derivation_transforms", ()):
                if transform.status is GeometryDerivationStatus.ACCEPTED:
                    sources.extend((transform.source_geometry, transform.derived_geometry))

        if not sources:
            return ()
        store = self._artifact_store(request.project_id)
        identities = []
        verified_identities = {}
        for source in sources:
            identity = GeometryArtifactIdentity.from_candidate(source)
            prior = verified_identities.get(source.artifact_id)
            if prior is not None:
                if prior != identity:
                    raise ValueError("promotion trusted geometry source identity is ambiguous")
                continue
            try:
                verified = store.read_verified_in_project(
                    source.artifact_id,
                    expected_type=ArtifactType.STEP,
                    expected_hash=source.artifact_hash,
                )
            except Exception as exc:
                raise ValueError(f"promotion trusted geometry verification failed: {exc}") from exc
            if verified is None:
                raise ValueError("promotion trusted geometry source is missing or tampered")
            artifact, _ = verified
            if (
                artifact.project_id != request.project_id
                or artifact.artifact_type is not ArtifactType.STEP
                or artifact.sha256 != source.artifact_hash
                or artifact.bound_revision != request.source_revision
                or artifact.bound_state_hash != request.source_state_hash
            ):
                raise ValueError("promotion trusted geometry source binding mismatch")
            verified_identities[source.artifact_id] = identity
            identities.append(source.artifact_id)

        for specification in request.candidate.component_specifications:
            selected_geometry = getattr(specification, "geometry_source", None)
            transforms = {
                transform.transform_id: transform
                for transform in getattr(specification, "geometry_derivation_transforms", ())
            }
            if selected_geometry is not None:
                for transform in transforms.values():
                    if transform.status is not GeometryDerivationStatus.ACCEPTED:
                        continue
                    for role, geometry, reference_hash in (
                        (
                            "source",
                            transform.source_geometry,
                            transform.source_geometry_reference_hash,
                        ),
                        (
                            "derived",
                            transform.derived_geometry,
                            transform.derived_geometry_reference_hash,
                        ),
                    ):
                        expected_reference_hash = geometry_reference_hash(geometry)
                        if reference_hash != expected_reference_hash:
                            raise ValueError(
                                f"promotion {role} geometry reference hash mismatch"
                            )
                        if (
                            geometry.artifact_id == selected_geometry.artifact_id
                            and geometry.artifact_hash == selected_geometry.artifact_hash
                            and reference_hash != selected_geometry.reference_hash
                        ):
                            raise ValueError(
                                f"promotion {role} geometry reference does not match selected geometry"
                            )
            for active_interface in getattr(specification, "supplied_interface_definitions", ()):
                if active_interface.kind != "materialized":
                    continue
                provenance = active_interface.derivation
                assert provenance is not None
                transform = transforms.get(provenance.transform_id)
                if transform is None or transform.transform_hash != provenance.transform_hash:
                    raise ValueError(
                        "promotion materialized interface transform does not resolve"
                    )
                if transform.status is not GeometryDerivationStatus.ACCEPTED:
                    raise ValueError(
                        "promotion materialized interface transform is not accepted"
                    )
                active_frame = None
                if provenance.derived_reference_frame_id is not None:
                    active_frame = next(
                        (
                            frame
                            for frame in specification.supplied_reference_frames
                            if frame.frame_id == provenance.derived_reference_frame_id
                            and frame.frame_hash == provenance.derived_reference_frame_hash
                        ),
                        None,
                    )
                    if active_frame is None:
                        raise ValueError(
                            "promotion materialized interface frame does not resolve"
                        )
                try:
                    MaterializedInterfaceVerifier.verify(
                        provenance, transform, active_interface, active_frame
                    )
                except Exception as exc:
                    raise ValueError(
                        f"promotion materialized interface integrity failure: {exc}"
                    ) from exc
        return tuple(identities)

    def _artifact_store(self, project_id: str):
        factory = self.artifact_store_factory
        if isinstance(factory, ArtifactStore):
            return factory
        try:
            parameters = inspect.signature(factory).parameters
        except (TypeError, ValueError):
            parameters = {}
        if "project_id" in parameters:
            kwargs = {"project_id": project_id}
            if "run_id" in parameters:
                kwargs["run_id"] = "promotion-lookup"
            store = factory(**kwargs)
        elif len(parameters) == 0:
            store = factory()
        elif len(parameters) == 2:
            store = factory(project_id, "promotion-lookup")
        else:
            store = factory(project_id)
        if not hasattr(store, "read_verified_in_project"):
            raise ValueError("promotion artifact store lacks project-scoped verification")
        return store

    @classmethod
    def _expected_classifications(cls, request: CandidatePromotionRequest):
        candidate = request.candidate
        expected = {}

        def add_expected(identity, value):
            prior = expected.get(identity)
            if prior is not None:
                if prior != value:
                    raise ValueError(f"promotion classification identity collision: {identity}")
                return
            expected[identity] = value

        for specification in candidate.component_specifications:
            for prop in specification.properties:
                key = f"candidate:property:{specification.source_identity}:{prop.key}"
                if prop.availability is ComponentPropertyAvailability.AVAILABLE:
                    if prop.normalized_value is not None:
                        add_expected(key, _ExpectedClassification(True, prop.normalized_value))
                    else:
                        add_expected(key, _ExpectedClassification(True, tuple(prop.normalized_range)))
                else:
                    add_expected(key, _ExpectedClassification(False))
            if specification.geometry_source is not None:
                source = specification.geometry_source
                key = f"candidate:geometry-source:{source.artifact_id}"
                add_expected(key, _ExpectedClassification(True, source.artifact_hash))
            for frame in getattr(specification, "supplied_reference_frames", ()):
                add_expected(
                    f"candidate:supplied-frame:{specification.specification_hash}:{frame.frame_id}",
                    _ExpectedClassification(
                        True,
                        frame.frame_hash,
                        PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
                    ),
                )
            for interface in getattr(specification, "supplied_interface_definitions", ()):
                add_expected(
                    f"candidate:supplied-interface:{specification.specification_hash}:{interface.interface_id}",
                    _ExpectedClassification(
                        True,
                        interface.interface_hash,
                        PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
                    ),
                )
            for transform in getattr(specification, "geometry_derivation_transforms", ()):
                add_expected(
                    f"candidate:geometry-derivation:{specification.specification_hash}:{transform.transform_id}",
                    _ExpectedClassification(
                        True,
                        transform.transform_hash,
                        PromotionValueClassification.CANONICAL_REDERIVATION_INPUT,
                    ),
                )
            generated_part = getattr(specification, "generated_part", None)
            if generated_part is not None:
                add_expected(
                    f"candidate:generated-part:{specification.specification_hash}:"
                    f"{generated_part.generated_part_id}",
                    _ExpectedClassification(
                        True,
                        generated_part.generated_part_hash,
                        PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
                    ),
                )
        cad_request = getattr(getattr(request, "evaluation", None), "cad_request", None)
        for derivation in getattr(cad_request, "placement_derivations", ()):
            add_expected(
                f"candidate:generated-placement:{derivation.derivation_id}",
                _ExpectedClassification(
                    True,
                    derivation.derivation_hash,
                    PromotionValueClassification.CANONICAL_REDERIVATION_INPUT,
                ),
            )
        for variable in candidate.design_variables:
            key = f"candidate:design-variable:{variable.name}"
            add_expected(key, _ExpectedClassification(True, variable.value))
        for component in candidate.realization.components:
            key = f"candidate:physical-instance:{component.instance_id}"
            if key in expected:
                raise ValueError(f"promotion classification identity collision: {key}")
            expected[key] = _ExpectedClassification(False)
        for connection in candidate.realization.connections:
            key = f"candidate:connection:{connection.connection_id}"
            if key in expected:
                raise ValueError(f"promotion classification identity collision: {key}")
            expected[key] = _ExpectedClassification(False)
        for binding in candidate.realization.joint_bindings:
            key = f"candidate:joint-binding:{binding.joint_id}"
            if key in expected:
                raise ValueError(f"promotion classification identity collision: {key}")
            expected[key] = _ExpectedClassification(False)
        return expected

    @classmethod
    def _classifications_by_identity(cls, request, expected):
        classifications = tuple(request.classifications)
        by_identity = {}
        for classification in classifications:
            cls._validate_classification(classification, request.promotion_policy)
            if classification.source_identity in by_identity:
                raise ValueError("promotion classifications must classify each input exactly once")
            by_identity[classification.source_identity] = classification

        expected_identities = set(expected)
        for identity, expected_value in expected.items():
            classification = by_identity.get(identity)
            if classification is None:
                raise ValueError(f"promotion classification is missing: {identity}")
            if classification.classification in (
                PromotionValueClassification.DO_NOT_PROMOTE,
                PromotionValueClassification.PROVENANCE_ONLY,
            ):
                raise ValueError(f"promotion classification omits canonical input: {identity}")
            if (
                expected_value.required_classification is not None
                and classification.classification is not expected_value.required_classification
            ):
                raise ValueError(f"promotion classification is incorrect for canonical input: {identity}")
            if expected_value.has_source_value:
                if classification.source_value is None or not cls._same_typed_value(
                    classification.source_value, expected_value.source_value
                ):
                    raise ValueError(f"promotion classification value substitution: {identity}")
            elif classification.source_value is not None:
                raise ValueError(f"promotion classification has an unexpected source value: {identity}")
            if classification.source_provenance is InputProvenanceKind.POLICY_ASSUMPTION:
                if not identity.startswith("candidate:design-variable:") or classification.classification is not PromotionValueClassification.ACCEPTED_DESIGN_CHOICE:
                    raise ValueError("policy assumption requires an explicit accepted design choice")

        for identity, classification in by_identity.items():
            if identity in expected_identities:
                continue
            if not cls._is_derived_identity(identity, request):
                raise ValueError(f"promotion classification is unknown or unclassified: {identity}")
            if classification.classification is not PromotionValueClassification.DO_NOT_PROMOTE:
                raise ValueError(f"derived candidate authority cannot be promoted: {identity}")
        return by_identity

    @staticmethod
    def _validate_classification(classification: PromotionClassification, policy) -> None:
        if classification.classification not in policy.allowed_classifications:
            raise ValueError("promotion classification is not allowed by policy")
        if classification.source_provenance is InputProvenanceKind.POLICY_ASSUMPTION and classification.source_value is None:
            raise ValueError("policy assumption classification must retain an explicit value")

    @staticmethod
    def _is_derived_identity(identity: str, request: CandidatePromotionRequest) -> bool:
        exact = {
            request.m12_3_result.result_hash,
            request.evaluation.evaluation_hash,
            request.selection.selection_hash,
        }
        exact.update(request.evaluation.m10_stage_outcome.m10_request_hashes)
        exact.update(request.evaluation.m10_stage_outcome.m10_result_hashes)
        if request.evaluation.cad_realization_hash is not None:
            exact.add(request.evaluation.cad_realization_hash)
        if request.comparison is not None:
            exact.add(request.comparison.result_hash)
        if request.comparison_request is not None:
            exact.add(request.comparison_request.request_hash)
        return identity in exact

    @staticmethod
    def _same_typed_value(actual: object, expected: object) -> bool:
        return type(actual) is type(expected) and actual == expected

    @staticmethod
    def _validate_identifier(value: str, label: str) -> None:
        if not _IDENTIFIER.fullmatch(value) or ":" in value:
            raise ValueError(f"{label} is not a valid delimiter-free identifier")


class CandidatePromotionApplicationService:
    """Apply one compiled promotion through the normal run lifecycle."""

    def __init__(self, compiler: CandidatePromotionCompiler, run_controller, *, manifest_service=None):
        if compiler is None or run_controller is None:
            raise ValueError("promotion application requires a compiler and RunController")
        self.compiler = compiler
        self.run_controller = run_controller
        self.manifest_service = manifest_service or PromotionManifestService()

    def promote_selected_candidate(
        self, request: CandidatePromotionRequest
    ) -> CandidatePromotionApplicationResult:
        readiness = None
        compilation = None
        try:
            state = self.compiler.state_manager.load_current_state(request.project_id)
            readiness = self.compiler.validate_readiness(request)
            compilation = self.compiler.compile(state, request)
            proposal = compilation.validated_proposal()
            scope = self._scope_projection(request)
        except Exception as exc:
            return self._result(
                request=request,
                compilation=compilation,
                status=PromotionApplicationStatus.PRE_APPLY_FAILURE,
                error=exc,
            )

        run = None
        decision_artifact = None
        store = None
        try:
            run = self.run_controller.create_run(
                request.project_id,
                expected_source=SourceBinding(
                    project_id=request.project_id,
                    revision=request.source_revision,
                    state_hash=request.source_state_hash,
                ),
            )
            if (
                run.project_id != request.project_id
                or run.initial_revision != request.source_revision
                or run.initial_state_hash != request.source_state_hash
                or run.active_revision != request.source_revision
                or run.active_state_hash != request.source_state_hash
            ):
                raise ValueError("promotion run source binding mismatch")
            store = ArtifactStore(
                self.run_controller.workspace,
                project_id=request.project_id,
                run_id=run.run_id,
            )
            decision_artifact = self.manifest_service.publish_decision(
                store,
                readiness=readiness,
                compilation=compilation,
                request=request,
                pre_promotion_scope_projection=scope,
            )
            self.manifest_service.resolve_decision(store, decision_artifact.artifact_id)
        except Exception as exc:
            self._fail_created_run(run, exc)
            return self._result(
                request=request,
                compilation=compilation,
                decision_artifact_id=(
                    None if decision_artifact is None else decision_artifact.artifact_id
                ),
                status=PromotionApplicationStatus.PRE_APPLY_FAILURE,
                error=exc,
            )

        try:
            applied_run = self.run_controller.apply_approved_proposal(run.run_id, proposal)
        except PostApplyInvalidationError as exc:
            applied = exc.applied
            return self._result(
                request=request,
                compilation=compilation,
                decision_artifact_id=decision_artifact.artifact_id,
                applied_revision=applied.snapshot.revision,
                applied_state_hash=applied.snapshot.state_hash,
                status=PromotionApplicationStatus.PROMOTION_APPLIED_BUT_INVALIDATION_PERSISTENCE_FAILED,
                error=exc,
            )
        except PostApplyRunTransitionError as exc:
            applied = exc.applied
            return self._result(
                request=request,
                compilation=compilation,
                decision_artifact_id=decision_artifact.artifact_id,
                applied_revision=applied.snapshot.revision,
                applied_state_hash=applied.snapshot.state_hash,
                status=PromotionApplicationStatus.PROMOTION_APPLIED_BUT_RUN_TRANSITION_FAILED,
                error=exc,
            )
        except ChangeError as exc:
            self._fail_created_run(run, exc)
            return self._result(
                request=request,
                compilation=compilation,
                decision_artifact_id=decision_artifact.artifact_id,
                status=PromotionApplicationStatus.CHANGEENGINE_REJECTED,
                error=exc,
            )
        except Exception as exc:
            current = None
            try:
                current = self.run_controller.get_run(run.run_id)
            except Exception:
                pass
            if current is not None and current.active_revision > run.initial_revision:
                return self._result(
                    request=request,
                    compilation=compilation,
                    decision_artifact_id=decision_artifact.artifact_id,
                    applied_revision=current.active_revision,
                    applied_state_hash=current.active_state_hash,
                    status=PromotionApplicationStatus.PROMOTION_APPLIED_BUT_RUN_TRANSITION_FAILED,
                    error=exc,
                )
            self._fail_created_run(run, exc)
            return self._result(
                request=request,
                compilation=compilation,
                decision_artifact_id=decision_artifact.artifact_id,
                status=PromotionApplicationStatus.PRE_APPLY_FAILURE,
                error=exc,
            )

        applied_revision = getattr(applied_run, "active_revision", None)
        applied_state_hash = getattr(applied_run, "active_state_hash", None)
        try:
            invalidation = self.run_controller.evidence.load_invalidation(
                request.project_id, applied_revision
            )
            self._verify_invalidation(invalidation, run, applied_run, proposal)
        except Exception as exc:
            return self._result(
                request=request,
                compilation=compilation,
                decision_artifact_id=decision_artifact.artifact_id,
                applied_revision=applied_revision,
                applied_state_hash=applied_state_hash,
                status=PromotionApplicationStatus.PROMOTION_APPLIED_BUT_INVALIDATION_VERIFICATION_FAILED,
                error=exc,
            )

        result_artifact = None
        try:
            result_artifact = self.manifest_service.publish_result(
                store,
                decision_artifact=decision_artifact,
                compilation=compilation,
                proposal=proposal,
                changeset_id=invalidation.changeset_id,
                changed_paths=tuple(invalidation.changed_paths),
                resulting_revision=invalidation.revision,
                resulting_state_hash=applied_state_hash,
            )
            self.manifest_service.resolve_result(store, result_artifact.artifact_id)
        except Exception as exc:
            published_artifact = getattr(exc, "published_artifact", None)
            return self._result(
                request=request,
                compilation=compilation,
                decision_artifact_id=decision_artifact.artifact_id,
                result_artifact_id=(
                    None
                    if result_artifact is None and published_artifact is None
                    else (result_artifact or published_artifact).artifact_id
                ),
                applied_revision=applied_revision,
                applied_state_hash=applied_state_hash,
                status=PromotionApplicationStatus.PROMOTION_APPLIED_BUT_RESULT_PROVENANCE_FAILED,
                error=exc,
            )

        return self._result(
            request=request,
            compilation=compilation,
            decision_artifact_id=decision_artifact.artifact_id,
            result_artifact_id=result_artifact.artifact_id,
            applied_revision=applied_revision,
            applied_state_hash=applied_state_hash,
            status=PromotionApplicationStatus.PROMOTION_APPLIED,
        )

    def _fail_created_run(self, run, error: Exception) -> None:
        if run is None:
            return
        self.run_controller.fail_run(run.run_id, error=str(error) or type(error).__name__)

    @staticmethod
    def _result(
        *,
        request,
        compilation,
        status,
        error=None,
        decision_artifact_id=None,
        result_artifact_id=None,
        applied_revision=None,
        applied_state_hash=None,
    ) -> CandidatePromotionApplicationResult:
        values = dict(
            request=request,
            compilation=compilation,
            decision_artifact_id=decision_artifact_id,
            result_artifact_id=result_artifact_id,
            applied_revision=applied_revision,
            applied_state_hash=applied_state_hash,
            status=status,
            error=None if error is None else str(error) or type(error).__name__,
        )
        try:
            return CandidatePromotionApplicationResult(**values)
        except Exception:
            # Do not return an invalid transient receipt when a caller tampered
            # with the compiled proposal before the application boundary.
            values["compilation"] = None
            return CandidatePromotionApplicationResult(**values)

    @staticmethod
    def _scope_projection(request: CandidatePromotionRequest) -> PrePromotionM10ScopeProjection:
        scope = request.evaluation.m10_scope
        binding = request.evaluation.m10_binding
        if scope is None or binding is None:
            raise ValueError("promotion requires an exact pre-promotion M10 scope and binding")
        dispositions = {
            entry.constituent_key: entry.physical_instance_id
            for entry in binding.constituent_dispositions
        }
        requirements = []
        limitations = list(scope.policy_assumptions)
        for requirement in scope.pair_scope_requirements:
            if requirement.required_classification.value != "check_clearance":
                limitations.append(
                    f"{requirement.requirement_key}:{requirement.required_classification.value}"
                )
                continue
            first = dispositions.get(requirement.first_constituent_key)
            second = dispositions.get(requirement.second_constituent_key)
            if first is None or second is None:
                raise ValueError("pre-promotion scope references an unknown constituent")
            requirements.append(
                PromotionPhysicalPairRequirement(
                    requirement_key=requirement.requirement_key,
                    first_instance_id=first,
                    first_interface_id=CandidatePromotionCompiler._interface_for(
                        request, first, second, requirement.first_constituent_key
                    ),
                    second_instance_id=second,
                    second_interface_id=CandidatePromotionCompiler._interface_for(
                        request, second, first, requirement.second_constituent_key
                    ),
                    requires_home_exact_check=requirement.requires_home_exact_check,
                )
            )
        return PrePromotionM10ScopeProjection(
            joint_semantic_key=scope.output_joint_semantic_key,
            angle_interval_deg=scope.angle_interval_deg,
            required_clearance_mm=scope.required_clearance_mm,
            physical_pair_requirements=tuple(requirements),
            fidelity_requirements=tuple(
                (dispositions.get(key, key), fidelity)
                for key, fidelity in scope.fidelity_requirements
            ),
            required_home_check_semantics=scope.required_home_check_semantics,
            bounded_limitations=tuple(limitations),
        )

    @staticmethod
    def _verify_invalidation(invalidation, initial_run, applied_run, proposal) -> None:
        expected_paths = tuple(
            dict.fromkeys(operation.path for operation in proposal.operations)
        )
        if invalidation.project_id != initial_run.project_id:
            raise ValueError("invalidation project binding mismatch")
        if (
            applied_run.project_id != initial_run.project_id
            or applied_run.active_revision != initial_run.initial_revision + 1
            or applied_run.active_state_hash == initial_run.initial_state_hash
        ):
            raise ValueError("applied run revision binding mismatch")
        if invalidation.revision != applied_run.active_revision:
            raise ValueError("invalidation revision binding mismatch")
        if invalidation.parent_revision != initial_run.initial_revision:
            raise ValueError("invalidation parent revision binding mismatch")
        if tuple(invalidation.changed_paths) != expected_paths:
            raise ValueError("invalidation changed paths binding mismatch")
        if not invalidation.changeset_id or not invalidation.changeset_id.strip():
            raise ValueError("invalidation ChangeSet ID is missing")


class PromotedMechanismVerificationIntegrityError(ValueError):
    """A promoted verification record failed a trust-boundary check."""


class PromotedMechanismVerificationOperationalError(RuntimeError):
    """A post-application verifier dependency failed operationally."""


def verify_promoted_mechanism(application_result) -> "PromotedMechanismVerificationResult":
    """Verify one applied promotion without mutating canonical state."""
    from .canonical_cad import CanonicalCadIntegrityError, CanonicalCadRealization
    from .canonical_mechanism import CanonicalMechanismReconstruction, normalized_projection
    from .canonical_m10 import (
        CanonicalM10ScopeEquivalenceResult,
        CanonicalM10ScopeEquivalenceService,
        CanonicalM10VerificationOutcome,
        CanonicalM10VerificationStatus,
    )
    from .promotion_artifacts import (
        CandidatePromotionResultManifest,
        PromotionManifestIntegrityError,
        SelectedCandidateDecisionManifest,
    )
    from .promotion_models import (
        CandidatePromotionApplicationResult,
        CandidatePromotionCompilation,
        CandidatePromotionRequest,
        PrePromotionM10ScopeProjection,
        PromotableMechanismProjection,
        PromotedMechanismVerificationResult,
        PromotedMechanismVerificationStatus,
    )
    from mechcad_harness.backends.freecad import FreeCADBackendError

    context = getattr(application_result, "verification_context", application_result)
    raw_receipt = getattr(context, "application_result", None) or context
    receipt = raw_receipt
    compilation = getattr(receipt, "compilation", None)
    request = getattr(receipt, "request", None)
    raw_applied_revision = getattr(receipt, "applied_revision", None)
    raw_applied_state_hash = getattr(receipt, "applied_state_hash", None)

    def _safe_revision(value):
        return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None

    def _safe_hash(value):
        if not isinstance(value, str):
            return None
        try:
            return _require_hash(value)
        except (TypeError, ValueError):
            return None

    def _safe_id(value):
        return value if isinstance(value, str) and value.strip() else None

    applied_revision = _safe_revision(raw_applied_revision)
    applied_state_hash = _safe_hash(raw_applied_state_hash)
    raw_target_id = getattr(
        getattr(compilation, "projection", None), "canonical_target_mechanism_id", None
    )
    raw_target_id = raw_target_id or getattr(request, "canonical_target_mechanism_id", None)
    target_id = _safe_id(raw_target_id)
    canonical_mechanism_hash = None
    projection_hash = None
    promotion_result_hash = None
    canonical_cad_request_hash = None
    canonical_cad_realization_hash = None
    canonical_m10_inventory_hash = None
    canonical_m10_outcome_hash = None
    m10_request_hashes: tuple[str, ...] = ()
    m10_result_hashes: tuple[str, ...] = ()
    projection_equivalence_hash = None
    scope_equivalence_hash = None
    m11_handoff_hash = None
    status = PromotedMechanismVerificationStatus.OPERATIONAL_FAILURE
    error = None

    def _value(source, name, default=None):
        return getattr(source, name, default) if source is not None else default

    def _typed(value, expected_type, label):
        if not isinstance(value, expected_type):
            raise PromotedMechanismVerificationIntegrityError(
                f"{label} has the wrong type"
            )
        try:
            return expected_type.model_validate(value.model_dump(mode="json"))
        except Exception as exc:
            raise PromotedMechanismVerificationIntegrityError(
                f"{label} integrity validation failed: {exc}"
            ) from exc

    def _result() -> PromotedMechanismVerificationResult:
        return PromotedMechanismVerificationResult(
            promotion_result_artifact_id=_safe_id(
                getattr(receipt, "result_artifact_id", None)
            ),
            promotion_result_hash=promotion_result_hash,
            promoted_revision=applied_revision,
            promoted_state_hash=applied_state_hash,
            canonical_target_mechanism_id=target_id,
            canonical_mechanism_hash=canonical_mechanism_hash,
            projection_hash=projection_hash,
            projection_equivalence_hash=projection_equivalence_hash,
            canonical_cad_request_hash=canonical_cad_request_hash,
            canonical_cad_realization_hash=canonical_cad_realization_hash,
            canonical_m10_inventory_hash=canonical_m10_inventory_hash,
            canonical_m10_outcome_hash=canonical_m10_outcome_hash,
            canonical_m10_request_hashes=m10_request_hashes,
            canonical_m10_result_hashes=m10_result_hashes,
            scope_equivalence_hash=scope_equivalence_hash,
            m11_handoff_hash=m11_handoff_hash,
            status=status,
            error=error,
        )

    try:
        receipt = _typed(receipt, CandidatePromotionApplicationResult, "application result")
        if receipt.status is not PromotionApplicationStatus.PROMOTION_APPLIED:
            if receipt.applied_revision is not None and receipt.applied_state_hash is not None:
                status = PromotedMechanismVerificationStatus.OPERATIONAL_FAILURE
                error = receipt.error or f"promotion application did not complete: {receipt.status.value}"
                applied_revision = receipt.applied_revision
                applied_state_hash = receipt.applied_state_hash
                return _result()
            raise PromotedMechanismVerificationIntegrityError(
                "promoted verification requires a completed promotion application"
            )
        applied_revision = receipt.applied_revision
        applied_state_hash = receipt.applied_state_hash
        request = _typed(receipt.request, CandidatePromotionRequest, "promotion request")
        compilation = _typed(receipt.compilation, CandidatePromotionCompilation, "promotion compilation")
        target_id = compilation.projection.canonical_target_mechanism_id
        compilation.validated_proposal()
        if applied_revision is None or applied_state_hash is None:
            raise PromotedMechanismVerificationIntegrityError(
                "promoted verification requires an applied revision and state hash"
            )
        if not receipt.decision_artifact_id or not receipt.result_artifact_id:
            raise PromotedMechanismVerificationIntegrityError(
                "promoted verification requires both manifests"
            )

        manifest_service = getattr(context, "manifest_service", None)
        manifest_store = getattr(context, "manifest_store", None)
        if manifest_service is None or manifest_store is None:
            raise PromotedMechanismVerificationIntegrityError(
                "promoted verification manifest services are missing"
            )
        try:
            raw_decision = manifest_service.resolve_decision(
                manifest_store, receipt.decision_artifact_id
            )
            raw_result = manifest_service.resolve_result(
                manifest_store, receipt.result_artifact_id
            )
        except (PromotionManifestIntegrityError, ValueError):
            raise
        except Exception as exc:
            raise PromotedMechanismVerificationOperationalError(
                f"promotion manifest resolution failed: {exc}"
            ) from exc
        decision = _typed(raw_decision, SelectedCandidateDecisionManifest, "decision manifest")
        result_manifest = _typed(raw_result, CandidatePromotionResultManifest, "result manifest")
        proposal = compilation.proposal
        expected_paths = tuple(dict.fromkeys(operation.path for operation in proposal.operations))
        if (
            result_manifest.decision_artifact_id != receipt.decision_artifact_id
            or result_manifest.resulting_revision != applied_revision
            or result_manifest.resulting_state_hash != applied_state_hash
            or result_manifest.promotion_proposal_hash != compilation.promotion_proposal_hash
            or result_manifest.proposal_id != proposal.id
            or result_manifest.changed_paths != expected_paths
            or result_manifest.mechanism_path != f"/physical_mechanisms/{target_id}"
        ):
            raise PromotedMechanismVerificationIntegrityError(
                "promotion result manifest binding mismatch"
            )
        if (
            decision.project_id != request.project_id
            or decision.base_revision != proposal.base_revision
            or decision.base_state_hash != proposal.base_state_hash
            or decision.base_revision != request.source_revision
            or decision.base_state_hash != request.source_state_hash
            or decision.compilation_hash != compilation.compilation_hash
            or decision.promotion_proposal_hash != compilation.promotion_proposal_hash
            or decision.projection_hash != compilation.projection.projection_hash
            or decision.projection != compilation.projection
            or decision.mapping != compilation.mapping
        ):
            raise PromotedMechanismVerificationIntegrityError(
                "promotion decision manifest binding mismatch"
            )
        reference = decision.input_reference
        expected_reference = {
            "promotion_request_hash": request.request_hash,
            "project_id": request.project_id,
            "base_revision": request.source_revision,
            "base_state_hash": request.source_state_hash,
            "candidate_hash": request.candidate.candidate_hash,
            "synthesis_request_hash": request.synthesis_request.request_hash,
            "synthesis_policy_hash": request.synthesis_policy.policy_hash,
            "m12_3_result_hash": request.m12_3_result.result_hash,
            "evaluation_hash": request.evaluation.evaluation_hash,
            "selection_hash": request.selection.selection_hash,
            "comparison_used": request.comparison_used,
            "promotion_policy_hash": request.promotion_policy.policy_hash,
            "canonical_target_mechanism_id": target_id,
            "m11_target_intent": request.m11_target_intent,
            "mapping_identities": tuple(item.mapping_hash for item in compilation.mapping),
            "classification_identities": tuple(
                item.classification_hash for item in request.classifications
            ),
        }
        for name, expected in expected_reference.items():
            if getattr(reference, name) != expected:
                raise PromotedMechanismVerificationIntegrityError(
                    f"promotion decision input reference binding mismatch: {name}"
                )
        if (
            reference.comparison_result_hash
            != (None if request.comparison is None else request.comparison.result_hash)
            or reference.comparison_request_hash
            != (None if request.comparison_request is None else request.comparison_request.request_hash)
        ):
            raise PromotedMechanismVerificationIntegrityError(
                "promotion decision comparison identity mismatch"
            )
        try:
            request_scope = CandidatePromotionApplicationService._scope_projection(request)
        except Exception as exc:
            raise PromotedMechanismVerificationIntegrityError(
                f"pre-promotion request scope reconstruction failed: {exc}"
            ) from exc
        if request_scope != decision.pre_promotion_scope_projection:
            raise PromotedMechanismVerificationIntegrityError(
                "decision pre-promotion scope does not match the promotion request"
            )
        promotion_result_hash = result_manifest.result_hash

        mechanism_compiler = getattr(context, "canonical_mechanism_compiler", None)
        cad_compiler = getattr(context, "canonical_cad_compiler", None)
        m10_service = getattr(context, "canonical_m10_service", None)
        if mechanism_compiler is None or cad_compiler is None or m10_service is None:
            raise PromotedMechanismVerificationIntegrityError(
                "canonical verification services are missing"
            )
        try:
            raw_reconstruction = mechanism_compiler.reconstruct(
                request.project_id, applied_revision, applied_state_hash, target_id
            )
        except ValueError:
            raise
        except Exception as exc:
            raise PromotedMechanismVerificationOperationalError(
                f"canonical reconstruction failed: {exc}"
            ) from exc
        reconstruction = _typed(
            raw_reconstruction, CanonicalMechanismReconstruction, "canonical reconstruction"
        )
        if (
            reconstruction.project_id != request.project_id
            or reconstruction.revision != applied_revision
            or reconstruction.state_hash != applied_state_hash
            or reconstruction.mechanism.id != target_id
        ):
            raise PromotedMechanismVerificationIntegrityError(
                "canonical reconstruction binding mismatch"
            )
        canonical_mechanism_hash = reconstruction.mechanism.mechanism_hash
        projection_fn = getattr(context, "normalized_projection", None) or normalized_projection
        try:
            reconstructed_projection = projection_fn(reconstruction)
        except Exception as exc:
            raise PromotedMechanismVerificationIntegrityError(
                f"canonical projection reconstruction failed: {exc}"
            ) from exc
        reconstructed_projection = _typed(
            reconstructed_projection, PromotableMechanismProjection, "canonical projection"
        )
        projection_hash = reconstructed_projection.projection_hash
        if reconstructed_projection != decision.projection:
            raise PromotedMechanismVerificationIntegrityError(
                "canonical projection does not match decision projection"
            )
        projection_equivalence_hash = _hash_identity(
            {"decision": decision.projection_hash, "reconstructed": projection_hash}
        )

        try:
            raw_cad = cad_compiler.realize(reconstruction)
        except CanonicalCadIntegrityError as exc:
            if isinstance(exc.__cause__, (FreeCADBackendError, RuntimeError)):
                raise PromotedMechanismVerificationOperationalError(
                    f"canonical CAD backend failed: {exc.__cause__}"
                ) from exc
            raise
        except ValueError:
            raise
        except Exception as exc:
            raise PromotedMechanismVerificationOperationalError(
                f"canonical CAD realization failed: {exc}"
            ) from exc
        cad = _typed(raw_cad, CanonicalCadRealization, "canonical CAD realization")
        try:
            cad = cad.validated_canonical_copy()
        except (CanonicalCadIntegrityError, ValueError):
            raise
        except Exception as exc:
            raise PromotedMechanismVerificationOperationalError(
                f"canonical CAD validation failed: {exc}"
            ) from exc
        if (
            cad.project_id != request.project_id
            or cad.revision != applied_revision
            or cad.state_hash != applied_state_hash
            or cad.mechanism_id != target_id
            or cad.mechanism_hash != canonical_mechanism_hash
        ):
            raise PromotedMechanismVerificationIntegrityError("canonical CAD binding mismatch")
        source_by_id = {
            source.artifact_id: source
            for source in reconstruction.trusted_source_references
        }
        geometry_by_id = {
            specification.geometry_source.artifact_id: specification.geometry_source
            for specification in reconstruction.mechanism.component_specifications
            if specification.geometry_source is not None
        }
        expected_source_ids = tuple(sorted(source_by_id))
        expected_source_hashes = tuple(source_by_id[source_id].sha256 for source_id in expected_source_ids)
        expected_source_provenance = tuple(
            reconstruction.trusted_source_references[
                tuple(source.artifact_id for source in reconstruction.trusted_source_references).index(source_id)
            ]
            for source_id in expected_source_ids
        )
        if (
            set(source_by_id) != set(geometry_by_id)
            or cad.selected_source_artifact_ids != expected_source_ids
            or cad.selected_source_content_identities != expected_source_hashes
            or cad.selected_source_provenance != expected_source_provenance
            or any(
                geometry_by_id[source_id].artifact_hash != source_by_id[source_id].sha256
                for source_id in expected_source_ids
            )
        ):
            raise PromotedMechanismVerificationIntegrityError(
                "canonical CAD selected source binding mismatch"
            )
        canonical_cad_request_hash = cad.request_hash
        canonical_cad_realization_hash = cad.realization_hash

        try:
            raw_m10 = m10_service.execute(reconstruction, cad)
        except ValueError:
            raise
        except Exception as exc:
            raise PromotedMechanismVerificationOperationalError(
                f"canonical M10 execution failed: {exc}"
            ) from exc
        m10 = _typed(raw_m10, CanonicalM10VerificationOutcome, "canonical M10 outcome")
        if (
            m10.project_id != request.project_id
            or m10.revision != applied_revision
            or m10.state_hash != applied_state_hash
            or m10.mechanism_id != target_id
            or m10.mechanism_hash != canonical_mechanism_hash
            or m10.cad_realization_hash != cad.realization_hash
            or m10.request.cad_realization_hash != cad.realization_hash
            or m10.inventory.cad_realization_hash != cad.realization_hash
        ):
            raise PromotedMechanismVerificationIntegrityError(
                "canonical M10 CAD realization binding mismatch"
            )
        m10_request_hashes = (m10.request.request_hash,)
        m10_result_hashes = tuple(
            proof.result.result_hash for proof in m10.pair_proofs
        ) + tuple(check.result.result_hash for check in m10.home_exact_checks)
        if not m10_result_hashes:
            raise PromotedMechanismVerificationIntegrityError(
                "canonical M10 produced no result identity"
            )
        canonical_m10_inventory_hash = m10.inventory.inventory_hash
        canonical_m10_outcome_hash = m10.outcome_hash

        scope_service = getattr(context, "scope_equivalence_service", None)
        scope_service = scope_service or CanonicalM10ScopeEquivalenceService()
        try:
            raw_scope_result = scope_service.compare(
                decision.pre_promotion_scope_projection, m10.scope
            )
        except ValueError:
            raise
        except Exception as exc:
            raise PromotedMechanismVerificationOperationalError(
                f"canonical M10 scope comparison failed: {exc}"
            ) from exc
        scope_result = _typed(
            raw_scope_result,
            CanonicalM10ScopeEquivalenceResult,
            "canonical M10 scope equivalence result",
        )
        if (
            scope_result.project_id != request.project_id
            or scope_result.revision != applied_revision
            or scope_result.state_hash != applied_state_hash
            or scope_result.frozen_projection_hash
            != decision.pre_promotion_scope_projection.projection_hash
            or scope_result.derived_scope_hash != m10.scope.scope_hash
        ):
            raise PromotedMechanismVerificationIntegrityError(
                "canonical M10 scope equivalence binding mismatch"
            )
        scope_equivalence_hash = scope_result.result_hash
        if not scope_result.equivalent:
            raise _ScopeMismatch(
                "canonical M10 scope is not equivalent: "
                + ", ".join(scope_result.differences)
            )
        if m10.status is CanonicalM10VerificationStatus.COLLISION_WITNESS:
            status = PromotedMechanismVerificationStatus.ENGINEERING_VIOLATION
        elif m10.status is CanonicalM10VerificationStatus.NOT_PROVEN:
            status = PromotedMechanismVerificationStatus.UNRESOLVED
        elif m10.status is CanonicalM10VerificationStatus.VERIFIED_CLEAR:
            status = PromotedMechanismVerificationStatus.VERIFIED
        else:
            raise PromotedMechanismVerificationIntegrityError(
                "unknown canonical M10 verification status"
            )

        m11_handoff = getattr(context, "m11_handoff", None)
        if m11_handoff is not None:
            try:
                from pydantic import BaseModel

                from .m11_handoff import CanonicalM11Handoff, CanonicalM11HandoffRequest
            except (ImportError, AttributeError) as exc:
                raise PromotedMechanismVerificationIntegrityError(
                    "strict M11 assessment types are unavailable"
                ) from exc
            if not isinstance(CanonicalM11Handoff, type) or not issubclass(
                CanonicalM11Handoff, BaseModel
            ):
                raise PromotedMechanismVerificationIntegrityError(
                    "M11 assessment type is not a strict model"
                )
            if not isinstance(CanonicalM11HandoffRequest, type) or not issubclass(
                CanonicalM11HandoffRequest, BaseModel
            ):
                raise PromotedMechanismVerificationIntegrityError(
                    "M11 request type is not a strict model"
                )
            assessment = _typed(m11_handoff, CanonicalM11Handoff, "M11 assessment")
            handoff_payload = assessment.model_dump(mode="json")
            raw_request = getattr(assessment, "request", None)
            handoff_request = _typed(
                raw_request, CanonicalM11HandoffRequest, "M11 handoff request"
            )
            request_payload = handoff_request.model_dump(mode="json")
            raw_intents = [
                getattr(handoff_request, name, None)
                for name in ("intent", "target_intent")
                if getattr(handoff_request, name, None) is not None
            ]
            if len(raw_intents) != 1:
                raise PromotedMechanismVerificationIntegrityError(
                    "M11 handoff request requires exactly one strict intent"
                )
            intent = _typed(raw_intents[0], type(raw_intents[0]), "M11 handoff intent")
            if not isinstance(intent, BaseModel):
                raise PromotedMechanismVerificationIntegrityError(
                    "M11 handoff intent is not a strict model"
                )
            intent_payload = intent.model_dump(mode="json")
            nested_result = getattr(assessment, "result", None)
            if not isinstance(nested_result, BaseModel):
                raise PromotedMechanismVerificationIntegrityError(
                    "M11 assessment result is not a strict model"
                )
            result_record = _typed(
                nested_result, type(nested_result), "M11 assessment result"
            )
            result_payload = result_record.model_dump(mode="json")

            def _consistent_binding(label, names, *payloads):
                values = []
                for payload in payloads:
                    present = [payload[name] for name in names if name in payload]
                    if len(set(map(repr, present))) > 1:
                        raise PromotedMechanismVerificationIntegrityError(
                            f"M11 {label} has conflicting aliases"
                        )
                    values.extend(present)
                if not values or any(value != values[0] for value in values[1:]):
                    raise PromotedMechanismVerificationIntegrityError(
                        f"M11 {label} binding mismatch"
                    )
                return values[0]

            promotion_intent = request.m11_target_intent
            if promotion_intent is None:
                raise PromotedMechanismVerificationIntegrityError(
                    "M11 assessment requires a bound target intent"
                )
            target_instance_id = (
                target_id
                if promotion_intent.target_scope == "whole_mechanism"
                else next(
                    (
                        item.canonical_instance_id
                        for item in decision.mapping
                        if item.candidate_instance_id
                        == promotion_intent.candidate_instance_id
                    ),
                    None,
                )
            )
            if target_instance_id is None:
                raise PromotedMechanismVerificationIntegrityError(
                    "M11 assessment target is not present in the promotion mapping"
                )
            expected_bindings = (
                ("project", ("project_id",), request.project_id),
                ("promoted revision", ("promoted_revision", "revision"), applied_revision),
                (
                    "promoted state",
                    ("promoted_state_hash", "state_hash"),
                    applied_state_hash,
                ),
                ("mechanism ID", ("canonical_mechanism_id", "mechanism_id"), target_id),
                (
                    "mechanism hash",
                    ("canonical_mechanism_hash", "mechanism_hash"),
                    canonical_mechanism_hash,
                ),
                ("target ID", ("target_instance_id", "canonical_target_instance_id", "target_id"), target_instance_id),
                ("target scope", ("target_scope",), promotion_intent.target_scope),
                ("analysis category", ("analysis_category",), promotion_intent.analysis_category),
                ("intent hash", ("intent_hash",), promotion_intent.intent_hash),
            )
            for label, names, expected in expected_bindings:
                _consistent_binding(label, names, handoff_payload, request_payload, result_payload)
                if _consistent_binding(label, names, request_payload, intent_payload) != expected:
                    raise PromotedMechanismVerificationIntegrityError(
                        f"M11 {label} binding mismatch"
                    )
            result_hash = result_payload.get("result_hash")
            if not isinstance(result_hash, str) or _hash_identity(
                {key: value for key, value in result_payload.items() if key != "result_hash"}
            ) != result_hash:
                raise PromotedMechanismVerificationIntegrityError(
                    "M11 assessment result hash mismatch"
                )
            m11_handoff_hash = result_hash
    except _ScopeMismatch as exc:
        status = PromotedMechanismVerificationStatus.UNRESOLVED
        error = str(exc)
    except (
        PromotedMechanismVerificationIntegrityError,
        PromotionManifestIntegrityError,
        CanonicalCadIntegrityError,
        ValueError,
    ) as exc:
        status = PromotedMechanismVerificationStatus.INTEGRITY_FAILURE
        error = str(exc) or type(exc).__name__
    except PromotedMechanismVerificationOperationalError as exc:
        status = PromotedMechanismVerificationStatus.OPERATIONAL_FAILURE
        error = str(exc) or type(exc).__name__
    except Exception as exc:
        status = PromotedMechanismVerificationStatus.OPERATIONAL_FAILURE
        error = str(exc) or type(exc).__name__

    return _result()


class _ScopeMismatch(ValueError):
    pass


def _hash_identity(payload: object) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


__all__ = [
    "CandidatePromotionApplicationService",
    "CandidatePromotionCompiler",
    "PromotionReadiness",
    "PromotedMechanismVerificationIntegrityError",
    "PromotedMechanismVerificationOperationalError",
    "verify_promoted_mechanism",
]
