from __future__ import annotations

import hashlib
import math
from enum import StrEnum
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from mechcad_harness.candidates.cad_realization import (
    CandidateCadRealization,
    CandidateCadRealizationRequest,
    CandidateCadStageOutcome,
    CandidateCadStageStatus,
    CandidateCadRealizationRequestV3,
    CandidateCadRealizationV2,
    CandidateCadStageOutcomeV2,
    CandidateGeometryFidelity,
    CandidateCadRealizationService,
    candidate_cad_stage_outcome_hash_v2,
    candidate_realization_hash_v2,
    candidate_request_hash_v3,
    semantic_declared_inputs,
    trusted_representation_identity,
)
from mechcad_harness.candidates.m10_evaluation import (
    CandidateM10Binding,
    CandidateM10BindingV2,
    CandidateM10EvaluationRequest,
    CandidateM10EvaluationRequestV2,
    CandidateM10EvaluationScope,
    CandidateM10PairClassification,
    CandidateM10StageOutcome,
    CandidateM10StageOutcomeV2,
    CandidateM10StageStatus,
    CandidateM10BodyDisposition,
    CandidateM10EvaluationService,
    candidate_m10_binding_hash_v2,
    candidate_m10_stage_outcome_hash_v2,
)
from mechcad_harness.candidates.models import (
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
    MechanicalDesignCandidate,
    candidate_hash_v2,
    candidate_synthesis_request_hash_v2,
)
from mechcad_harness.candidates.services import (
    CandidateCurrentness,
    CandidateCurrentnessService,
    CandidateIntegrityError,
    CandidateIntegrityVerifier,
)
from mechcad_harness.continuous_proof import ContinuousSingleAxisProofStatus
from mechcad_harness.continuous_proof import ContinuousSingleAxisProofRequest
from mechcad_harness.kinematic_sweep import CadKinematicSweepRequest, SweepAggregateClassification
from mechcad_harness.cad_assembly import _require_semantic_fields, assembly_hash
from mechcad_harness.models.common import Model
from mechcad_harness.models.generated_part import generated_geometry_definition_identities
from mechcad_harness.revolute_drive import (
    DriveAdmissibility,
    RevoluteDriveAdmissibilityResult,
    admissibility_result_hash,
)
from mechcad_harness.state.hashing import canonical_json


def _hash(value: object, identity_field: str | None = None) -> str:
    payload = value.model_dump(mode="json") if isinstance(value, Model) else value
    payload = dict(payload)
    if identity_field is not None:
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


class CandidateEvaluationModel(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CandidateEvaluationOutcome(StrEnum):
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    UNRESOLVED = "unresolved"


_SUPPORTED_CHECKS = frozenset(
    {
        "m12_3_admissibility",
        "candidate_cad_realization",
        "m10_continuous_clearance",
    }
)


class CandidateEvaluationPolicy(CandidateEvaluationModel):
    """The fixed required-check inventory for one candidate evaluation."""

    schema_version: Literal["candidate-evaluation-policy@1"] = "candidate-evaluation-policy@1"
    required_check_keys: tuple[str, ...] = (
        "m12_3_admissibility",
        "candidate_cad_realization",
        "m10_continuous_clearance",
    )
    policy_version: str = "candidate-evaluation@1"
    policy_hash: str = "pending"

    @field_validator("policy_version")
    @classmethod
    def _nonblank_version(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("evaluation policy version must not be empty")
        return value

    @field_validator("policy_hash")
    @classmethod
    def _valid_policy_hash(cls, value: str) -> str:
        return value if value == "pending" else _require_hash(value)

    @model_validator(mode="after")
    def _validate_policy(self) -> "CandidateEvaluationPolicy":
        if not self.required_check_keys:
            raise ValueError("evaluation policy requires at least one check")
        if any(not key.strip() for key in self.required_check_keys):
            raise ValueError("evaluation policy check keys must not be empty")
        if len(set(self.required_check_keys)) != len(self.required_check_keys):
            raise ValueError("evaluation policy check keys must be unique")
        unknown = set(self.required_check_keys) - _SUPPORTED_CHECKS
        if unknown:
            raise ValueError(f"unsupported candidate evaluation check: {sorted(unknown)[0]}")
        expected = _hash(self, "policy_hash")
        if self.policy_hash == "pending":
            object.__setattr__(self, "policy_hash", expected)
        elif self.policy_hash != expected:
            raise ValueError("candidate evaluation policy hash mismatch")
        return self

    @property
    def required_checks(self) -> tuple[str, ...]:
        return self.required_check_keys


class CandidateMetricKey(StrEnum):
    VERIFIED_CLEARANCE_LOWER_BOUND_MM = "verified_clearance_lower_bound_mm"


class CandidateMetric(CandidateEvaluationModel):
    schema_version: Literal["candidate-metric@1"] = "candidate-metric@1"
    key: CandidateMetricKey
    value: float
    unit: Literal["mm"]
    source_result_hashes: tuple[str, ...] = Field(min_length=1)
    derivation: Literal["minimum_certified_lower_clearance_mm"] = (
        "minimum_certified_lower_clearance_mm"
    )
    metric_hash: str = "pending"

    @field_validator("value")
    @classmethod
    def _finite_value(cls, value: float) -> float:
        if not math.isfinite(value) or value < 0:
            raise ValueError("candidate metric value must be finite and non-negative")
        return value

    @field_validator("source_result_hashes")
    @classmethod
    def _valid_sources(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(_require_hash(source) != source for source in value):
            raise ValueError("candidate metric source result identity is invalid")
        if len(set(value)) != len(value):
            raise ValueError("candidate metric source result identities must be unique")
        return value

    @field_validator("metric_hash")
    @classmethod
    def _valid_metric_hash(cls, value: str) -> str:
        return value if value == "pending" else _require_hash(value)

    @model_validator(mode="after")
    def _validate_metric(self) -> "CandidateMetric":
        if self.key is not CandidateMetricKey.VERIFIED_CLEARANCE_LOWER_BOUND_MM:
            raise ValueError("unsupported candidate metric key")
        expected = _hash(self, "metric_hash")
        if self.metric_hash == "pending":
            object.__setattr__(self, "metric_hash", expected)
        elif self.metric_hash != expected:
            raise ValueError("candidate metric hash mismatch")
        return self

    @property
    def source_result_hash(self) -> str:
        if len(self.source_result_hashes) != 1:
            raise ValueError("metric has multiple source result identities")
        return self.source_result_hashes[0]


def _stage_outcome_hash(outcome: Model) -> str:
    field = "outcome_hash"
    return _hash(outcome, field)


def _expected_outcome(
    m12_result: RevoluteDriveAdmissibilityResult,
    cad_stage: CandidateCadStageOutcome,
    m10_stage: CandidateM10StageOutcome,
    required_checks: tuple[str, ...],
    m10_request: CandidateM10EvaluationRequest | None = None,
) -> tuple[CandidateEvaluationOutcome, tuple[str, ...], tuple[str, ...]]:
    hard: list[str] = []
    unresolved: list[str] = []

    if m12_result.status is DriveAdmissibility.INADMISSIBLE:
        hard.append("m12_3_admissibility")
    elif m12_result.status is DriveAdmissibility.UNRESOLVED:
        unresolved.append("m12_3_admissibility")

    if "candidate_cad_realization" in required_checks:
        if cad_stage.status is not CandidateCadStageStatus.SUCCESS:
            unresolved.append("candidate_cad_realization")

    if "m10_continuous_clearance" in required_checks:
        if m10_stage.status is not CandidateM10StageStatus.SUCCESS:
            unresolved.append("m10_continuous_clearance")
        elif not m10_stage.pair_proofs:
            unresolved.append("m10_continuous_clearance")
        else:
            for proof in m10_stage.pair_proofs:
                status = proof.result.status
                if status is ContinuousSingleAxisProofStatus.COLLISION_WITNESS:
                    hard.append(f"m10_collision:{proof.result_hash}")
                elif status is ContinuousSingleAxisProofStatus.NOT_PROVEN:
                    unresolved.append(f"m10_not_proven:{proof.result_hash}")

    for check in m10_stage.home_exact_checks:
        if check.result.aggregate_classification in (
            SweepAggregateClassification.COLLISION_PRESENT,
            SweepAggregateClassification.TOUCHING_PRESENT,
        ):
            hard.append(f"m10_home_collision:{check.result_hash}")

    if m10_request is not None:
        required_home_pairs = {
            item.pair
            for item in m10_request.inventory.classifications
            if item.requires_home_exact_check
        }
        checked_home_pairs = {check.pair for check in m10_stage.home_exact_checks}
        if required_home_pairs & checked_home_pairs:
            unresolved.append("m10_internal_motion_unmodeled")

    if hard:
        return CandidateEvaluationOutcome.INFEASIBLE, tuple(hard), tuple(unresolved)
    if unresolved:
        return CandidateEvaluationOutcome.UNRESOLVED, (), tuple(unresolved)
    return CandidateEvaluationOutcome.FEASIBLE, (), ()


def _expected_outcome_v2(
    m12_result: RevoluteDriveAdmissibilityResult,
    cad_stage: CandidateCadStageOutcomeV2,
    m10_stage: CandidateM10StageOutcomeV2,
    required_checks: tuple[str, ...],
    m10_request: CandidateM10EvaluationRequestV2 | None = None,
) -> tuple[CandidateEvaluationOutcome, tuple[str, ...], tuple[str, ...]]:
    hard: list[str] = []
    unresolved: list[str] = []

    if m12_result.status is DriveAdmissibility.INADMISSIBLE:
        hard.append("m12_3_admissibility")
    elif m12_result.status is DriveAdmissibility.UNRESOLVED:
        unresolved.append("m12_3_admissibility")

    if "candidate_cad_realization" in required_checks:
        if cad_stage.status is not CandidateCadStageStatus.SUCCESS:
            unresolved.append("candidate_cad_realization")

    if "m10_continuous_clearance" in required_checks:
        if m10_stage.status is not CandidateM10StageStatus.SUCCESS:
            unresolved.append("m10_continuous_clearance")
        elif not m10_stage.pair_proofs:
            unresolved.append("m10_continuous_clearance")
        else:
            for proof in m10_stage.pair_proofs:
                if proof.result.status is ContinuousSingleAxisProofStatus.COLLISION_WITNESS:
                    hard.append(f"m10_collision:{proof.proof_hash}")
                elif proof.result.status is ContinuousSingleAxisProofStatus.NOT_PROVEN:
                    unresolved.append(f"m10_not_proven:{proof.proof_hash}")

    for check in m10_stage.home_exact_checks:
        if check.result.aggregate_classification in (
            SweepAggregateClassification.COLLISION_PRESENT,
            SweepAggregateClassification.TOUCHING_PRESENT,
        ):
            hard.append(f"m10_home_collision:{check.check_hash}")

    if m10_request is not None:
        required_home_pairs = {
            item.pair
            for item in m10_request.inventory.classifications
            if item.requires_home_exact_check
        }
        checked_home_pairs = {check.pair for check in m10_stage.home_exact_checks}
        if required_home_pairs & checked_home_pairs:
            unresolved.append("m10_internal_motion_unmodeled")

    if hard:
        return CandidateEvaluationOutcome.INFEASIBLE, tuple(hard), tuple(unresolved)
    if unresolved:
        return CandidateEvaluationOutcome.UNRESOLVED, (), tuple(unresolved)
    return CandidateEvaluationOutcome.FEASIBLE, (), ()


def _metric_from_stage(m10_stage: CandidateM10StageOutcome) -> CandidateMetric | None:
    if m10_stage.status is not CandidateM10StageStatus.SUCCESS or not m10_stage.pair_proofs:
        return None
    values: list[float] = []
    source_hashes: list[str] = []
    for proof in m10_stage.pair_proofs:
        if proof.result.status is not ContinuousSingleAxisProofStatus.VERIFIED_CLEAR:
            return None
        if not proof.result.certified_leaf_certificates:
            raise ValueError("verified-clear M10 result requires certificates")
        for certificate in proof.result.certified_leaf_certificates:
            if not certificate.pair_certificates:
                raise ValueError("M10 interval certificate cannot be empty")
            pair_values = tuple(pair.certified_lower_clearance_mm for pair in certificate.pair_certificates)
            if not all(math.isfinite(value) and value >= 0 for value in pair_values):
                raise ValueError("M10 certificate clearance values must be finite and non-negative")
            expected = min(pair_values)
            if certificate.minimum_certified_lower_clearance_mm != expected:
                raise ValueError("M10 interval certificate minimum is inconsistent")
            if any(
                value <= proof.result.required_clearance_mm + proof.result.proof_guard_mm
                for value in pair_values
            ):
                raise ValueError(
                    "M10 verified-clear lower bound does not exceed required clearance and proof guard"
                )
            values.append(certificate.minimum_certified_lower_clearance_mm)
        source_hashes.append(proof.result_hash)
    if not values:
        raise ValueError("verified-clear M10 result requires certificates")
    return CandidateMetric(
        key=CandidateMetricKey.VERIFIED_CLEARANCE_LOWER_BOUND_MM,
        value=min(values),
        unit="mm",
        source_result_hashes=tuple(source_hashes),
    )


def _metric_from_stage_v2(m10_stage: CandidateM10StageOutcomeV2) -> CandidateMetric | None:
    if m10_stage.status is not CandidateM10StageStatus.SUCCESS or not m10_stage.pair_proofs:
        return None
    values: list[float] = []
    semantic_proof_hashes: list[str] = []
    for proof in m10_stage.pair_proofs:
        if proof.result.status is not ContinuousSingleAxisProofStatus.VERIFIED_CLEAR:
            return None
        if not proof.result.certified_leaf_certificates:
            raise ValueError("verified-clear M10 @2 result requires certificates")
        for certificate in proof.result.certified_leaf_certificates:
            if not certificate.pair_certificates:
                raise ValueError("M10 @2 interval certificate cannot be empty")
            pair_values = tuple(
                pair.certified_lower_clearance_mm
                for pair in certificate.pair_certificates
            )
            if not all(math.isfinite(value) and value >= 0 for value in pair_values):
                raise ValueError("M10 @2 certificate clearances must be finite and non-negative")
            minimum = min(pair_values)
            if certificate.minimum_certified_lower_clearance_mm != minimum:
                raise ValueError("M10 @2 interval certificate minimum is inconsistent")
            if any(
                value <= proof.result.required_clearance_mm + proof.result.proof_guard_mm
                for value in pair_values
            ):
                raise ValueError(
                    "M10 @2 lower bound does not exceed required clearance and proof guard"
                )
            values.append(minimum)
        # The @1 metric record remains unchanged; its source references in the
        # @2 evaluation are the semantic proof certificates, not raw result hashes.
        semantic_proof_hashes.append(proof.proof_hash)
    if not values:
        raise ValueError("verified-clear M10 @2 result requires certificates")
    return CandidateMetric(
        key=CandidateMetricKey.VERIFIED_CLEARANCE_LOWER_BOUND_MM,
        value=min(values),
        unit="mm",
        source_result_hashes=tuple(semantic_proof_hashes),
    )


def _validate_cad_inputs(
    candidate: MechanicalDesignCandidate,
    request: CandidateCadRealizationRequest,
    stage: CandidateCadStageOutcome,
    cad_replay_verifier=None,
) -> None:
    request = CandidateCadRealizationRequest.model_validate(request.model_dump(mode="json"))
    stage = CandidateCadStageOutcome.model_validate(stage.model_dump(mode="json"))
    if stage.status is not CandidateCadStageStatus.SUCCESS or stage.realization is None:
        raise ValueError("exact CAD inputs require a successful CAD stage")
    realization = CandidateCadRealization.model_validate(stage.realization.model_dump(mode="json"))
    if request.candidate_hash != candidate.candidate_hash:
        raise ValueError("CAD request candidate identity mismatch")
    if request.source_binding != candidate.source_binding:
        raise ValueError("CAD request source binding mismatch")
    if request.source_binding_hash != _hash(candidate.source_binding):
        raise ValueError("CAD request source binding identity mismatch")
    expected_physical_ids = {component.instance_id for component in candidate.realization.components}
    if set(request.candidate_instance_ids) != expected_physical_ids:
        raise ValueError("CAD request candidate instance inventory mismatch")
    if realization.request_hash != request.request_hash:
        raise ValueError("CAD realization request identity mismatch")
    if realization.placement_derivations_hash != request.placement_derivations_hash:
        raise ValueError("CAD realization placement derivations identity mismatch")
    if realization.candidate_hash != candidate.candidate_hash:
        raise ValueError("CAD realization candidate identity mismatch")
    if realization.mappings != request.mappings:
        raise ValueError("CAD realization mapping manifest mismatch")

    specifications = {
        specification.specification_hash: specification
        for specification in candidate.component_specifications
    }
    components = {component.instance_id: component for component in candidate.realization.components}
    for mapping in request.mappings:
        component = components.get(mapping.physical_instance_id)
        if component is None:
            raise ValueError("CAD mapping references an unknown candidate physical instance")
        specification = specifications.get(component.specification_hash)
        if specification is None:
            raise ValueError("CAD mapping references a missing candidate specification")
        if mapping.candidate_hash != candidate.candidate_hash:
            raise ValueError("CAD mapping candidate identity mismatch")
        if (
            specification.geometry_source is not None
            and mapping.fidelity is not CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY
        ):
            raise ValueError("source-backed specification requires trusted source geometry")
        if mapping.fidelity is CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY:
            source = specification.geometry_source
            if source is None or mapping.source_geometry_identity != source.artifact_hash:
                raise ValueError("CAD mapping trusted source identity mismatch")
            if mapping.geometry_definition_identities != (source.artifact_id,):
                raise ValueError("CAD mapping trusted source definition mismatch")
        elif specification.generated_part is not None:
            if mapping.fidelity is not CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY:
                raise ValueError("generated CAD mapping requires exact generated fidelity")
            if mapping.geometry_definition_identities != generated_geometry_definition_identities(
                specification.generated_part
            ):
                raise ValueError("CAD mapping generated definition mismatch")
        elif mapping.source_geometry_identity is not None:
            raise ValueError("CAD bounded mapping cannot carry a source identity")
        candidate_design_inputs = {
            f"candidate:design-variable:{variable.name}" for variable in candidate.design_variables
        }
        candidate_interface_inputs = {
            f"candidate:component-interface:{component.instance_id}:{interface}"
            for component in candidate.realization.components
            for interface in component.interfaces
        }
        allowed_geometry_inputs = (
            {property.property_hash for property in specification.properties}
            | candidate_design_inputs
            | {f"candidate:geometry:{mapping.physical_instance_id}"}
        )
        if specification.geometry_source is not None:
            allowed_geometry_inputs.add(specification.geometry_source.artifact_id)
        if specification.generated_part is not None:
            allowed_geometry_inputs.update(
                generated_geometry_definition_identities(specification.generated_part)
            )
        if any(
            identity not in allowed_geometry_inputs
            for identity in mapping.geometry_definition_identities
        ):
            raise ValueError("CAD mapping contains a foreign geometry input identity")
    CandidateCadRealizationService._validate_placement_provenance(
        candidate,
        request,
        specifications,
        components,
    )

    requested_design_inputs = set(request.design_variable_identities)
    requested_interface_inputs = set(request.component_interface_identities)
    candidate_design_inputs = {
        f"candidate:design-variable:{variable.name}" for variable in candidate.design_variables
    }
    candidate_interface_inputs = {
        f"candidate:component-interface:{component.instance_id}:{interface}"
        for component in candidate.realization.components
        for interface in component.interfaces
    }
    if not requested_design_inputs <= candidate_design_inputs:
        raise ValueError("CAD request contains a foreign design variable identity")
    if not requested_interface_inputs <= candidate_interface_inputs:
        raise ValueError("CAD request contains a foreign component interface identity")
    declared_inputs = {
        identity
        for mapping in request.mappings
        for identity in mapping.geometry_definition_identities + mapping.placement_origin.input_identities
    }
    if requested_design_inputs != declared_inputs & candidate_design_inputs:
        raise ValueError("CAD request design variable inputs do not match mappings")
    if requested_interface_inputs != declared_inputs & candidate_interface_inputs:
        raise ValueError("CAD request component interface inputs do not match mappings")
    if cad_replay_verifier is not None:
        cad_replay_verifier(candidate, request, realization)


def _validate_cad_inputs_v2(
    candidate: MechanicalDesignCandidate,
    request: CandidateCadRealizationRequestV3,
    stage: CandidateCadStageOutcomeV2,
) -> CandidateCadRealizationV2:
    """Revalidate the accepted CAD@2/request@3 records from their typed inputs.

    The persisted @2 realization carries enough semantic mapping and assembly
    material to re-derive its identity without calling a CAD provider. Raw source
    authority is independently rechecked through typed request currentness.
    """

    request = CandidateCadRealizationRequestV3.model_validate(
        request.model_dump(mode="json")
    )
    stage = CandidateCadStageOutcomeV2.model_validate(stage.model_dump(mode="json"))
    if stage.status is not CandidateCadStageStatus.SUCCESS or stage.realization is None:
        raise ValueError("exact CAD @2 inputs require a successful CAD stage")
    realization = CandidateCadRealizationV2.model_validate(
        stage.realization.model_dump(mode="json")
    )
    if (
        request.candidate_hash != candidate.candidate_hash
        or request.source_binding != candidate.source_binding
        or request.source_binding_hash != _hash(candidate.source_binding)
        or request.semantic_source_binding_hash != candidate.semantic_source_binding_hash
    ):
        raise ValueError("CAD request@3 candidate/source binding mismatch")
    if (
        stage.realization_hash != realization.realization_hash
        or realization.candidate_hash != candidate.candidate_hash
        or realization.request_hash != request.request_hash
        or realization.mappings != request.mappings
        or request.request_hash != candidate_request_hash_v3(request)
        or realization.realization_hash != candidate_realization_hash_v2(realization)
    ):
        raise ValueError("CAD realization@2/request@3 semantic identity mismatch")

    components = {item.instance_id: item for item in candidate.realization.components}
    specifications = {
        item.specification_hash: item for item in candidate.component_specifications
    }
    if set(request.candidate_instance_ids) != set(components):
        raise ValueError("CAD request@3 physical instance inventory mismatch")
    if {item.physical_instance_id for item in request.mappings} != set(components):
        raise ValueError("CAD request@3 mappings do not cover candidate instances")

    design_inputs = {
        f"candidate:design-variable:{variable.name}"
        for variable in candidate.design_variables
    }
    interface_inputs = {
        f"candidate:component-interface:{component.instance_id}:{interface}"
        for component in candidate.realization.components
        for interface in component.interfaces
    }
    declared_inputs = semantic_declared_inputs(request.mappings)
    if set(request.design_variable_identities) != declared_inputs & design_inputs:
        raise ValueError("CAD request@3 design variable identities mismatch")
    if set(request.component_interface_identities) != declared_inputs & interface_inputs:
        raise ValueError("CAD request@3 component interface identities mismatch")

    for mapping in request.mappings:
        component = components.get(mapping.physical_instance_id)
        if component is None or mapping.candidate_hash != candidate.candidate_hash:
            raise ValueError("CAD mapping@2 candidate binding mismatch")
        specification = specifications.get(component.specification_hash)
        if specification is None or specification.schema_version != "component-specification@4":
            raise ValueError("candidate CAD @2 requires component-specification@4")
        source = specification.geometry_source
        if source is not None:
            semantic_source = mapping.source_geometry_identity
            if (
                mapping.fidelity is not CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY
                or semantic_source is None
                or semantic_source.content_identity != source.content_identity
                or semantic_source.content_identity_algorithm
                != source.content_identity_algorithm
                or mapping.geometry_definition_identities != (source.content_identity,)
                or mapping.representation_identity
                != trusted_representation_identity(
                    slot=mapping.cad_instance_id,
                    content_identity=source.content_identity,
                    content_identity_algorithm=source.content_identity_algorithm,
                )
            ):
                raise ValueError("CAD mapping@2 semantic source identity mismatch")
        elif specification.generated_part is not None:
            if (
                mapping.fidelity is not CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY
                or mapping.geometry_definition_identities
                != generated_geometry_definition_identities(specification.generated_part)
                or mapping.source_geometry_identity is not None
            ):
                raise ValueError("CAD mapping@2 generated specification mismatch")
        elif mapping.source_geometry_identity is not None:
            raise ValueError("bounded CAD mapping@2 cannot carry source geometry identity")
    return realization


def _verify_candidate_cad_trusted_slot_raw_bindings(
    candidate: MechanicalDesignCandidate,
    realization: CandidateCadRealizationV2,
    *,
    required_raw_pairs: set[tuple[str, str]],
) -> dict[tuple[str, str], tuple[str, str]]:
    """Verify verifier-local physical-slot to imported-raw-source bindings.

    Raw artifact identities deliberately remain outside candidate CAD mapping
    records and their semantic hashes. ``required_raw_pairs`` contains only
    artifact pairs that have already been byte-verified by the provenance
    boundary.
    """

    if candidate.schema_version != "mechanical-design-candidate@2":
        raise ValueError("trusted slot raw verification requires candidate@2")
    if type(realization) is not CandidateCadRealizationV2:
        raise TypeError("trusted slot raw verification requires realization@2")

    components_by_id = {}
    for component in candidate.realization.components:
        if component.instance_id in components_by_id:
            raise ValueError("trusted slot raw verification found duplicate physical instances")
        components_by_id[component.instance_id] = component
    specifications_by_hash = {}
    for specification in candidate.component_specifications:
        if specification.specification_hash in specifications_by_hash:
            raise ValueError("trusted slot raw verification found duplicate specifications")
        specifications_by_hash[specification.specification_hash] = specification

    assembly_instances = {}
    for instance in realization.assembly.instances:
        if instance.instance_id in assembly_instances:
            raise ValueError("trusted slot raw verification found duplicate CAD instances")
        assembly_instances[instance.instance_id] = instance
    imported_components = {}
    for imported in realization.assembly.imported_components:
        if imported.component_id in imported_components:
            raise ValueError("trusted slot raw verification found duplicate imported components")
        imported_components[imported.component_id] = imported

    verified_pairs = set(required_raw_pairs)
    expected_raw_binding_by_slot: dict[
        tuple[str, str], tuple[str, str]
    ] = {}
    for mapping in realization.mappings:
        if mapping.fidelity is not CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY:
            continue

        slot = (mapping.physical_instance_id, mapping.cad_instance_id)
        if slot in expected_raw_binding_by_slot:
            raise ValueError("trusted slot raw verification found a duplicate slot")
        component = components_by_id.get(mapping.physical_instance_id)
        if component is None:
            raise ValueError("trusted slot raw verification cannot resolve physical instance")
        specification = specifications_by_hash.get(component.specification_hash)
        if specification is None or specification.geometry_source is None:
            raise ValueError(
                "trusted slot raw verification requires one authoritative GeometrySourceReference"
            )
        source = specification.geometry_source
        expected_pair = (source.artifact_id, source.artifact_hash)

        instance = assembly_instances.get(mapping.cad_instance_id)
        if instance is None:
            raise ValueError("trusted slot raw verification cannot resolve CAD instance")
        imported = imported_components.get(instance.part_id)
        if imported is None:
            raise ValueError(
                "trusted slot raw verification cannot resolve one imported component"
            )
        actual_pair = (imported.artifact_id, imported.artifact_hash)
        if expected_pair != actual_pair:
            raise ValueError(
                "trusted slot raw binding mismatch: expected and actual artifact pairs differ"
            )
        if actual_pair not in verified_pairs:
            raise ValueError(
                "trusted slot raw binding is outside the byte-verified required set"
            )
        expected_raw_binding_by_slot[slot] = expected_pair

    return expected_raw_binding_by_slot


def _expected_m10_pairs(request: CandidateM10EvaluationRequest):
    return {
        item.pair
        for item in request.inventory.classifications
        if item.classification is CandidateM10PairClassification.CHECK_CLEARANCE
    }, {
        item.pair
        for item in request.inventory.classifications
        if item.requires_home_exact_check
    }


def _validate_m10_proofs(
    stage: CandidateM10StageOutcome,
    request: CandidateM10EvaluationRequest,
    scope: CandidateM10EvaluationScope,
    binding: CandidateM10Binding,
    realization: CandidateCadRealization,
) -> None:
    expected_continuous, expected_home = _expected_m10_pairs(request)
    actual_continuous = {proof.pair for proof in stage.pair_proofs}
    actual_home = {check.pair for check in stage.home_exact_checks}
    if actual_continuous != expected_continuous:
        raise ValueError("M10 stage continuous pair proofs are incomplete")
    if actual_home != expected_home:
        raise ValueError("M10 stage home pair proofs are incomplete")

    dispositions = {
        entry.cad_instance_id: entry for entry in binding.constituent_dispositions
    }
    for proof in stage.pair_proofs:
        first, second = (dispositions[proof.pair[0]], dispositions[proof.pair[1]])
        moving = next(
            entry.cad_instance_id
            for entry in (first, second)
            if entry.disposition is CandidateM10BodyDisposition.OUTPUT_RIGID
        )
        stationary = next(
            entry.cad_instance_id
            for entry in (first, second)
            if entry.disposition is CandidateM10BodyDisposition.FIXED
        )
        pair_assembly = CandidateM10EvaluationService._induced_pair_assembly(
            realization.assembly, moving, stationary
        )
        expected_request = ContinuousSingleAxisProofRequest(
            source_assembly_id=pair_assembly.assembly_id,
            source_assembly_hash=assembly_hash(pair_assembly),
            axis=binding.output_axis,
            start_angle_deg=scope.angle_interval_deg[0],
            end_angle_deg=scope.angle_interval_deg[1],
            moving_instance_ids=(moving,),
            stationary_instance_ids=(stationary,),
            required_clearance_mm=scope.required_clearance_mm,
            proof_guard_mm=proof.request.proof_guard_mm,
            max_depth=proof.request.max_depth,
            minimum_interval_deg=proof.request.minimum_interval_deg,
            max_exact_evaluations=proof.request.max_exact_evaluations,
        )
        if proof.request != expected_request:
            raise ValueError("M10 continuous proof request does not match exact scope")
        CandidateM10EvaluationService._validate_continuous_result(
            proof.request, proof.result, pair_assembly
        )
        if proof.result.status is ContinuousSingleAxisProofStatus.VERIFIED_CLEAR:
            threshold = proof.request.required_clearance_mm + proof.request.proof_guard_mm
            for certificate in proof.result.certified_leaf_certificates:
                if any(pair.certified_lower_clearance_mm <= threshold for pair in certificate.pair_certificates):
                    raise ValueError("M10 verified-clear lower bound does not exceed proof threshold")

    for check in stage.home_exact_checks:
        first, second = (dispositions[check.pair[0]], dispositions[check.pair[1]])
        moving = next(
            entry.cad_instance_id
            for entry in (first, second)
            if entry.disposition is CandidateM10BodyDisposition.INTERNAL_MOTION_UNMODELED
        )
        stationary = second.cad_instance_id if moving == first.cad_instance_id else first.cad_instance_id
        pair_assembly = CandidateM10EvaluationService._induced_pair_assembly(
            realization.assembly, moving, stationary
        )
        expected_request = CadKinematicSweepRequest(
            source_assembly_id=pair_assembly.assembly_id,
            source_assembly_hash=assembly_hash(pair_assembly),
            axis=binding.output_axis,
            sample_angles_deg=(0.0,),
            moving_instance_ids=(moving,),
            stationary_instance_ids=(stationary,),
        )
        if check.request != expected_request:
            raise ValueError("M10 home proof request does not match exact scope")
        CandidateM10EvaluationService._validate_home_result(
            check.request, check.result, pair_assembly
        )


def _validate_stored_stage_context(
    candidate_hash: str,
    cad_stage: CandidateCadStageOutcome,
    m10_stage: CandidateM10StageOutcome,
    cad_request: CandidateCadRealizationRequest | None,
    m10_request: CandidateM10EvaluationRequest | None,
    m10_scope: CandidateM10EvaluationScope | None,
    m10_binding: CandidateM10Binding | None,
) -> None:
    contexts = (cad_request, m10_request, m10_scope, m10_binding)
    if not any(value is not None for value in contexts):
        return
    if any(value is None for value in contexts):
        raise ValueError("candidate evaluation stage context is incomplete")
    cad_request = CandidateCadRealizationRequest.model_validate(cad_request.model_dump(mode="json"))
    m10_request = CandidateM10EvaluationRequest.model_validate(m10_request.model_dump(mode="json"))
    m10_scope = CandidateM10EvaluationScope.model_validate(m10_scope.model_dump(mode="json"))
    m10_binding = CandidateM10Binding.model_validate(m10_binding.model_dump(mode="json"))
    if cad_stage.status is not CandidateCadStageStatus.SUCCESS or cad_stage.realization is None:
        raise ValueError("exact stage context requires successful CAD realization")
    realization = CandidateCadRealization.model_validate(cad_stage.realization.model_dump(mode="json"))
    if cad_request.candidate_hash != candidate_hash or realization.candidate_hash != candidate_hash:
        raise ValueError("candidate evaluation CAD identity mismatch")
    if cad_request.request_hash != realization.request_hash:
        raise ValueError("candidate evaluation CAD request identity mismatch")
    if realization.placement_derivations_hash != cad_request.placement_derivations_hash:
        raise ValueError("candidate evaluation placement derivations identity mismatch")
    if m10_binding.candidate_hash != candidate_hash:
        raise ValueError("candidate evaluation M10 candidate identity mismatch")
    if m10_request.candidate_hash != candidate_hash:
        raise ValueError("candidate evaluation M10 request candidate identity mismatch")
    m10_binding.validate_against(realization)
    m10_request.validate_against(realization, m10_binding, m10_scope)
    comparisons = (
        (m10_stage.cad_realization_hash, realization.realization_hash, "CAD realization"),
        (m10_stage.binding_hash, m10_binding.binding_hash, "binding"),
        (m10_stage.scope_hash, m10_scope.scope_hash, "scope"),
        (m10_stage.evaluation_request_hash, m10_request.request_hash, "request"),
    )
    for actual, expected, label in comparisons:
        if actual != expected:
            raise ValueError(f"candidate evaluation M10 {label} identity mismatch")
    _validate_m10_proofs(m10_stage, m10_request, m10_scope, m10_binding, realization)


def _validate_stored_stage_context_v2(
    candidate: MechanicalDesignCandidate,
    synthesis_request: CandidateSynthesisRequest,
    evaluation: "CandidateEvaluationV2",
) -> None:
    if candidate.schema_version != "mechanical-design-candidate@2":
        raise ValueError("candidate evaluation@2 requires candidate@2")
    if synthesis_request.schema_version != "candidate-synthesis-request@2":
        raise ValueError("candidate evaluation@2 requires request@2")
    if (
        candidate.source_binding != synthesis_request.source_binding
        or candidate.semantic_source_binding_hash
        != synthesis_request.semantic_source_binding_hash
        or candidate.synthesis_request_hash != synthesis_request.request_hash
        or evaluation.candidate_hash != candidate.candidate_hash
        or evaluation.source_binding_hash != candidate.semantic_source_binding_hash
        or evaluation.synthesis_request_hash != synthesis_request.request_hash
        or evaluation.synthesis_policy_hash != candidate.synthesis_policy_hash
    ):
        raise ValueError("candidate evaluation@2 request/candidate semantic binding mismatch")
    if evaluation.m12_3_result.schema_version != "revolute-drive-admissibility@2":
        raise ValueError("candidate evaluation@2 requires admissibility@2")
    if (
        evaluation.m12_3_result.candidate_hash != candidate.candidate_hash
        or evaluation.m12_3_result.source_binding_hash
        != candidate.semantic_source_binding_hash
        or evaluation.m12_3_result.synthesis_request_hash != synthesis_request.request_hash
        or evaluation.m12_3_result.synthesis_policy_hash != candidate.synthesis_policy_hash
    ):
        raise ValueError("candidate evaluation@2 M12-3 parent mismatch")

    if evaluation.cad_stage_outcome.status is CandidateCadStageStatus.SUCCESS:
        if evaluation.cad_request is None:
            raise ValueError("candidate evaluation@2 is missing request@3")
        _validate_cad_inputs_v2(candidate, evaluation.cad_request, evaluation.cad_stage_outcome)
    else:
        if evaluation.cad_request is not None:
            raise ValueError("candidate evaluation@2 contains request@3 without successful CAD")
    _validate_m10_inputs_v2(
        candidate,
        synthesis_request,
        evaluation.m12_3_result,
        evaluation.cad_stage_outcome,
        evaluation.m10_stage_outcome,
        evaluation.cad_request,
        evaluation.m10_request,
        evaluation.m10_scope,
        evaluation.m10_binding,
    )


def _validate_m10_inputs(
    candidate: MechanicalDesignCandidate,
    cad_stage: CandidateCadStageOutcome,
    stage: CandidateM10StageOutcome,
    request: CandidateM10EvaluationRequest,
    scope: CandidateM10EvaluationScope,
    binding: CandidateM10Binding,
) -> None:
    request = CandidateM10EvaluationRequest.model_validate(request.model_dump(mode="json"))
    scope = CandidateM10EvaluationScope.model_validate(scope.model_dump(mode="json"))
    binding = CandidateM10Binding.model_validate(binding.model_dump(mode="json"))
    if cad_stage.realization is None:
        raise ValueError("M10 evaluation requires a CAD realization")
    realization = CandidateCadRealization.model_validate(cad_stage.realization.model_dump(mode="json"))
    if stage.candidate_hash != candidate.candidate_hash:
        raise ValueError("M10 stage candidate identity mismatch")
    if stage.cad_realization_hash != realization.realization_hash:
        raise ValueError("M10 stage CAD realization identity mismatch")
    if stage.binding_hash != binding.binding_hash:
        raise ValueError("M10 stage binding identity mismatch")
    if stage.scope_hash != scope.scope_hash:
        raise ValueError("M10 stage scope identity mismatch")
    if stage.evaluation_request_hash != request.request_hash:
        raise ValueError("M10 stage request identity mismatch")
    if stage.source_revision != candidate.source_binding.source_revision:
        raise ValueError("M10 stage source revision mismatch")
    if stage.source_state_hash != candidate.source_binding.source_state_hash:
        raise ValueError("M10 stage source state identity mismatch")
    if request.candidate_hash != candidate.candidate_hash:
        raise ValueError("M10 request candidate identity mismatch")
    binding.validate_against(realization, candidate.realization)
    request.validate_against(realization, binding, scope)
    _validate_m10_proofs(stage, request, scope, binding, realization)


def _validate_m10_inputs_v2(
    candidate: MechanicalDesignCandidate,
    synthesis_request: CandidateSynthesisRequest,
    admissibility_result: RevoluteDriveAdmissibilityResult,
    cad_stage: CandidateCadStageOutcomeV2,
    stage: CandidateM10StageOutcomeV2,
    cad_request: CandidateCadRealizationRequestV3 | None,
    m10_request: CandidateM10EvaluationRequestV2 | None,
    scope: CandidateM10EvaluationScope | None,
    binding: CandidateM10BindingV2 | None,
) -> None:
    if (
        candidate.schema_version != "mechanical-design-candidate@2"
        or synthesis_request.schema_version != "candidate-synthesis-request@2"
        or admissibility_result.schema_version != "revolute-drive-admissibility@2"
    ):
        raise ValueError("candidate evaluation@2 requires a homogeneous request/candidate/M12 chain")
    if (
        candidate.source_binding != synthesis_request.source_binding
        or candidate.semantic_source_binding_hash
        != synthesis_request.semantic_source_binding_hash
        or candidate.synthesis_request_hash != synthesis_request.request_hash
        or admissibility_result.candidate_hash != candidate.candidate_hash
        or admissibility_result.source_binding_hash
        != synthesis_request.semantic_source_binding_hash
        or admissibility_result.synthesis_request_hash != synthesis_request.request_hash
        or admissibility_result.synthesis_policy_hash != candidate.synthesis_policy_hash
        or admissibility_result.result_hash != admissibility_result_hash(admissibility_result)
    ):
        raise ValueError("candidate evaluation@2 typed request or M12 parent mismatch")
    if (
        stage.candidate_hash != candidate.candidate_hash
        or stage.source_revision != candidate.source_binding.source_revision
        or stage.source_state_hash != candidate.source_binding.source_state_hash
    ):
        raise ValueError("candidate evaluation@2 M10 candidate/source coordinates mismatch")
    if stage.status is CandidateM10StageStatus.NOT_REACHED:
        if any(value is not None for value in (m10_request, scope, binding)):
            raise ValueError("not-reached M10 @2 evaluation cannot retain M10 context")
        if any(
            value is not None
            for value in (stage.cad_realization_hash, stage.binding_hash, stage.scope_hash,
                          stage.evaluation_request_hash)
        ):
            raise ValueError("not-reached M10 @2 evaluation must be reason-only")
        return
    if cad_stage.status is not CandidateCadStageStatus.SUCCESS or cad_stage.realization is None:
        raise ValueError("completed M10 @2 evaluation requires successful CAD @2")
    if any(value is None for value in (cad_request, m10_request, scope, binding)):
        raise ValueError("completed M10 @2 evaluation requires exact CAD/M10 contexts")
    realization = _validate_cad_inputs_v2(candidate, cad_request, cad_stage)
    binding = CandidateM10BindingV2.model_validate(binding.model_dump(mode="json"))
    m10_request = CandidateM10EvaluationRequestV2.model_validate(
        m10_request.model_dump(mode="json")
    )
    scope = CandidateM10EvaluationScope.model_validate(scope.model_dump(mode="json"))
    stage.validate_against(
        candidate,
        synthesis_request,
        admissibility_result,
        realization,
        binding,
        m10_request,
        scope,
    )


class CandidateEvaluation(CandidateEvaluationModel):
    schema_version: Literal["candidate-evaluation@1"] = "candidate-evaluation@1"
    candidate_hash: str
    source_binding_hash: str
    synthesis_request_hash: str
    synthesis_policy_hash: str
    policy: CandidateEvaluationPolicy
    policy_hash: str
    evaluation_scope_hash: str | None = None
    required_check_keys: tuple[str, ...] = Field(min_length=1)
    m12_3_result: RevoluteDriveAdmissibilityResult
    m12_3_result_hash: str
    cad_stage_outcome: CandidateCadStageOutcome
    cad_stage_outcome_hash: str
    m10_stage_outcome: CandidateM10StageOutcome
    m10_stage_outcome_hash: str
    cad_request: CandidateCadRealizationRequest | None = None
    m10_request: CandidateM10EvaluationRequest | None = None
    m10_scope: CandidateM10EvaluationScope | None = None
    m10_binding: CandidateM10Binding | None = None
    metrics: tuple[CandidateMetric, ...] = ()
    hard_witnesses: tuple[str, ...] = ()
    unresolved_findings: tuple[str, ...] = ()
    outcome: CandidateEvaluationOutcome
    evaluator_identity: str = "candidate-evaluation"
    evaluator_version: str = "1"
    evaluation_hash: str = "pending"

    _validate_hashes = field_validator(
        "candidate_hash",
        "source_binding_hash",
        "synthesis_request_hash",
        "synthesis_policy_hash",
        "policy_hash",
        "m12_3_result_hash",
        "cad_stage_outcome_hash",
        "m10_stage_outcome_hash",
    )(_require_hash)

    @field_validator("evaluation_scope_hash")
    @classmethod
    def _valid_evaluation_scope_hash(cls, value: str | None) -> str | None:
        return None if value is None else _require_hash(value)

    @field_validator("evaluation_hash")
    @classmethod
    def _valid_evaluation_hash(cls, value: str) -> str:
        return value if value == "pending" else _require_hash(value)

    @model_validator(mode="after")
    def _validate_evaluation(self) -> "CandidateEvaluation":
        if self.policy_hash != self.policy.policy_hash:
            raise ValueError("candidate evaluation policy binding mismatch")
        if self.required_check_keys != self.policy.required_check_keys:
            raise ValueError("candidate evaluation required-check binding mismatch")
        if self.m12_3_result.candidate_hash != self.candidate_hash:
            raise ValueError("candidate evaluation M12-3 candidate binding mismatch")
        if self.m12_3_result.source_binding_hash != self.source_binding_hash:
            raise ValueError("candidate evaluation M12-3 source binding mismatch")
        if self.m12_3_result.synthesis_request_hash != self.synthesis_request_hash:
            raise ValueError("candidate evaluation M12-3 request binding mismatch")
        if self.m12_3_result.synthesis_policy_hash != self.synthesis_policy_hash:
            raise ValueError("candidate evaluation M12-3 synthesis policy binding mismatch")
        if self.m12_3_result_hash != admissibility_result_hash(self.m12_3_result):
            raise ValueError("candidate evaluation M12-3 result identity mismatch")
        if self.cad_stage_outcome_hash != _stage_outcome_hash(self.cad_stage_outcome):
            raise ValueError("candidate evaluation CAD stage identity mismatch")
        if self.m10_stage_outcome_hash != _stage_outcome_hash(self.m10_stage_outcome):
            raise ValueError("candidate evaluation M10 stage identity mismatch")
        if self.cad_stage_outcome.status is CandidateCadStageStatus.SUCCESS:
            assert self.cad_stage_outcome.realization is not None
            if self.cad_stage_outcome.realization.candidate_hash != self.candidate_hash:
                raise ValueError("candidate evaluation CAD candidate binding mismatch")
            if self.m10_stage_outcome.cad_realization_hash != self.cad_stage_outcome.realization_hash:
                raise ValueError("candidate evaluation M10/CAD realization binding mismatch")
        if self.m10_stage_outcome.candidate_hash != self.candidate_hash:
            raise ValueError("candidate evaluation M10 candidate binding mismatch")
        if self.m10_stage_outcome.status is CandidateM10StageStatus.NOT_REACHED:
            if self.evaluation_scope_hash is not None:
                raise ValueError("not-reached candidate evaluation cannot retain an M10 scope identity")
            if any(value is not None for value in (
                self.m10_stage_outcome.binding_hash,
                self.m10_stage_outcome.scope_hash,
                self.m10_stage_outcome.evaluation_request_hash,
            )):
                raise ValueError("not-reached candidate evaluation cannot retain M10 identities")
            if any(value is not None for value in (
                self.m10_request,
                self.m10_scope,
                self.m10_binding,
            )):
                raise ValueError("not-reached candidate evaluation cannot retain M10 context")
        elif self.evaluation_scope_hash != self.m10_stage_outcome.scope_hash:
            raise ValueError("candidate evaluation scope binding mismatch")
        if (
            self.m12_3_result.status is DriveAdmissibility.INADMISSIBLE
            and self.cad_stage_outcome.status is not CandidateCadStageStatus.NOT_REACHED
        ):
            raise ValueError("inadmissible M12-3 result requires CAD stage not reached")
        if (
            self.cad_stage_outcome.status is not CandidateCadStageStatus.SUCCESS
            and self.m10_stage_outcome.status is not CandidateM10StageStatus.NOT_REACHED
        ):
            raise ValueError("uncompleted CAD stage requires M10 stage not reached")
        if self.cad_stage_outcome.status is CandidateCadStageStatus.SUCCESS and self.cad_request is None:
            raise ValueError("successful CAD evaluation requires the exact CAD request")
        _validate_stored_stage_context(
            self.candidate_hash,
            self.cad_stage_outcome,
            self.m10_stage_outcome,
            self.cad_request,
            self.m10_request,
            self.m10_scope,
            self.m10_binding,
        )
        for proof in self.m10_stage_outcome.pair_proofs:
            CandidateM10EvaluationService._validate_continuous_result(
                proof.request, proof.result
            )
        for check in self.m10_stage_outcome.home_exact_checks:
            CandidateM10EvaluationService._validate_home_result(check.request, check.result)
        expected_outcome, hard, unresolved = _expected_outcome(
            self.m12_3_result,
            self.cad_stage_outcome,
            self.m10_stage_outcome,
            self.required_check_keys,
            self.m10_request,
        )
        if self.outcome is not expected_outcome:
            raise ValueError("candidate evaluation outcome does not match referenced results")
        if self.hard_witnesses != hard or self.unresolved_findings != unresolved:
            raise ValueError("candidate evaluation findings do not match referenced results")
        expected_metric = (
            _metric_from_stage(self.m10_stage_outcome)
            if "m10_continuous_clearance" in self.required_check_keys
            else None
        )
        if expected_metric is None:
            if self.metrics:
                raise ValueError("candidate metric requires verified-clear M10 results")
        elif self.metrics != (expected_metric,):
            raise ValueError("candidate metric does not match trusted M10 certificates")
        expected = _hash(self, "evaluation_hash")
        if self.evaluation_hash == "pending":
            object.__setattr__(self, "evaluation_hash", expected)
        elif self.evaluation_hash != expected:
            raise ValueError("candidate evaluation hash mismatch")
        return self

    @property
    def cad_realization_hash(self) -> str | None:
        return self.cad_stage_outcome.realization_hash

    @property
    def m10_request_hashes(self) -> tuple[str, ...]:
        return self.m10_stage_outcome.m10_request_hashes

    @property
    def m10_result_hashes(self) -> tuple[str, ...]:
        return self.m10_stage_outcome.m10_result_hashes


class CandidateEvaluationV2(CandidateEvaluationModel):
    """Semantic candidate evaluation over verified candidate@2 dependencies."""

    schema_version: Literal["candidate-evaluation@2"] = "candidate-evaluation@2"
    candidate_hash: str
    source_binding_hash: str
    synthesis_request_hash: str
    synthesis_policy_hash: str
    policy: CandidateEvaluationPolicy
    policy_hash: str
    evaluation_scope_hash: str | None = None
    required_check_keys: tuple[str, ...] = Field(min_length=1)
    m12_3_result: RevoluteDriveAdmissibilityResult
    m12_3_result_hash: str
    cad_stage_outcome: CandidateCadStageOutcomeV2
    cad_stage_outcome_hash: str
    m10_stage_outcome: CandidateM10StageOutcomeV2
    m10_stage_outcome_hash: str
    cad_request: CandidateCadRealizationRequestV3 | None = None
    m10_request: CandidateM10EvaluationRequestV2 | None = None
    m10_scope: CandidateM10EvaluationScope | None = None
    m10_binding: CandidateM10BindingV2 | None = None
    metrics: tuple[CandidateMetric, ...] = ()
    hard_witnesses: tuple[str, ...] = ()
    unresolved_findings: tuple[str, ...] = ()
    outcome: CandidateEvaluationOutcome
    evaluator_identity: str = "candidate-evaluation"
    evaluator_version: str = "1"
    evaluation_hash: str = "pending"

    _validate_hashes = field_validator(
        "candidate_hash", "source_binding_hash", "synthesis_request_hash",
        "synthesis_policy_hash", "policy_hash", "m12_3_result_hash",
        "cad_stage_outcome_hash", "m10_stage_outcome_hash",
    )(_require_hash)
    _validate_scope_hash = field_validator("evaluation_scope_hash")(
        lambda value: None if value is None else _require_hash(value)
    )
    _validate_evaluation_hash = field_validator("evaluation_hash")(
        lambda value: value if value == "pending" else _require_hash(value)
    )

    @model_validator(mode="after")
    def validate_evaluation_v2(self) -> "CandidateEvaluationV2":
        policy = CandidateEvaluationPolicy.model_validate(self.policy.model_dump(mode="json"))
        m12_result = RevoluteDriveAdmissibilityResult.model_validate(
            self.m12_3_result.model_dump(mode="json")
        )
        cad_stage = CandidateCadStageOutcomeV2.model_validate(
            self.cad_stage_outcome.model_dump(mode="json")
        )
        m10_stage = CandidateM10StageOutcomeV2.model_validate(
            self.m10_stage_outcome.model_dump(mode="json")
        )
        object.__setattr__(self, "policy", policy)
        object.__setattr__(self, "m12_3_result", m12_result)
        object.__setattr__(self, "cad_stage_outcome", cad_stage)
        object.__setattr__(self, "m10_stage_outcome", m10_stage)
        if self.policy_hash != policy.policy_hash:
            raise ValueError("candidate evaluation@2 policy binding mismatch")
        if self.required_check_keys != policy.required_check_keys:
            raise ValueError("candidate evaluation@2 required-check binding mismatch")
        if (
            m12_result.schema_version != "revolute-drive-admissibility@2"
            or m12_result.candidate_hash != self.candidate_hash
            or m12_result.source_binding_hash != self.source_binding_hash
            or m12_result.synthesis_request_hash != self.synthesis_request_hash
            or m12_result.synthesis_policy_hash != self.synthesis_policy_hash
            or self.m12_3_result_hash != admissibility_result_hash(m12_result)
        ):
            raise ValueError("candidate evaluation@2 M12-3 parent mismatch")
        if self.cad_stage_outcome_hash != candidate_cad_stage_outcome_hash_v2(cad_stage):
            raise ValueError("candidate evaluation@2 CAD stage identity mismatch")
        if self.m10_stage_outcome_hash != candidate_m10_stage_outcome_hash_v2(m10_stage):
            raise ValueError("candidate evaluation@2 M10 stage identity mismatch")
        if m10_stage.candidate_hash != self.candidate_hash:
            raise ValueError("candidate evaluation@2 M10 candidate binding mismatch")
        if cad_stage.status is CandidateCadStageStatus.SUCCESS:
            assert cad_stage.realization is not None
            if cad_stage.realization.candidate_hash != self.candidate_hash:
                raise ValueError("candidate evaluation@2 CAD candidate binding mismatch")
            if m10_stage.cad_realization_hash != cad_stage.realization_hash:
                raise ValueError("candidate evaluation@2 M10/CAD identity mismatch")
            if self.cad_request is None:
                raise ValueError("successful candidate CAD @2 evaluation requires request@3")
            cad_request = CandidateCadRealizationRequestV3.model_validate(
                self.cad_request.model_dump(mode="json")
            )
            if (
                cad_request.candidate_hash != self.candidate_hash
                or cad_request.request_hash != cad_stage.realization.request_hash
            ):
                raise ValueError("candidate evaluation@2 CAD request binding mismatch")
            object.__setattr__(self, "cad_request", cad_request)
        elif self.cad_request is not None:
            raise ValueError("uncompleted candidate CAD stage cannot retain request@3")

        if m10_stage.status is CandidateM10StageStatus.NOT_REACHED:
            if self.evaluation_scope_hash is not None:
                raise ValueError("not-reached candidate evaluation@2 cannot retain M10 scope")
            if any(value is not None for value in (
                m10_stage.binding_hash, m10_stage.scope_hash,
                m10_stage.evaluation_request_hash, self.m10_request,
                self.m10_scope, self.m10_binding,
            )):
                raise ValueError("not-reached candidate evaluation@2 cannot retain M10 context")
        else:
            if any(value is None for value in (
                self.m10_request, self.m10_scope, self.m10_binding,
            )):
                raise ValueError("completed candidate evaluation@2 requires M10 context")
            request = CandidateM10EvaluationRequestV2.model_validate(
                self.m10_request.model_dump(mode="json")
            )
            scope = CandidateM10EvaluationScope.model_validate(
                self.m10_scope.model_dump(mode="json")
            )
            binding = CandidateM10BindingV2.model_validate(
                self.m10_binding.model_dump(mode="json")
            )
            if (
                request.candidate_hash != self.candidate_hash
                or binding.candidate_hash != self.candidate_hash
                or request.binding_hash != binding.binding_hash
                or request.scope_hash != scope.scope_hash
                or self.evaluation_scope_hash != scope.scope_hash
                or m10_stage.evaluation_request_hash != request.request_hash
                or m10_stage.binding_hash != binding.binding_hash
                or m10_stage.scope_hash != scope.scope_hash
            ):
                raise ValueError("candidate evaluation@2 M10 semantic references mismatch")
            object.__setattr__(self, "m10_request", request)
            object.__setattr__(self, "m10_scope", scope)
            object.__setattr__(self, "m10_binding", binding)

        expected_outcome, hard, unresolved = _expected_outcome_v2(
            m12_result, cad_stage, m10_stage, self.required_check_keys, self.m10_request
        )
        if self.outcome is not expected_outcome:
            raise ValueError("candidate evaluation@2 outcome does not match referenced results")
        if self.hard_witnesses != hard or self.unresolved_findings != unresolved:
            raise ValueError("candidate evaluation@2 findings do not match referenced results")
        expected_metric = (
            _metric_from_stage_v2(m10_stage)
            if "m10_continuous_clearance" in self.required_check_keys
            else None
        )
        if expected_metric is None:
            if self.metrics:
                raise ValueError("candidate metric requires verified-clear M10 results")
        elif self.metrics != (expected_metric,):
            raise ValueError("candidate evaluation@2 metric does not match trusted M10 certificates")
        expected_hash = candidate_evaluation_hash_v2(self)
        if self.evaluation_hash == "pending":
            object.__setattr__(self, "evaluation_hash", expected_hash)
        elif self.evaluation_hash != expected_hash:
            raise ValueError("candidate evaluation@2 hash mismatch")
        return self

    @property
    def cad_realization_hash(self) -> str | None:
        return self.cad_stage_outcome.realization_hash

    @property
    def m10_request_hashes(self) -> tuple[str, ...]:
        return self.m10_stage_outcome.m10_request_hashes

    @property
    def m10_result_hashes(self) -> tuple[str, ...]:
        return self.m10_stage_outcome.m10_result_hashes


def candidate_evaluation_hash_v2(evaluation: CandidateEvaluationV2) -> str:
    _require_semantic_fields(
        evaluation,
        CandidateEvaluationV2,
        {
            "schema_version", "candidate_hash", "source_binding_hash",
            "synthesis_request_hash", "synthesis_policy_hash", "policy", "policy_hash",
            "evaluation_scope_hash", "required_check_keys", "m12_3_result",
            "m12_3_result_hash", "cad_stage_outcome", "cad_stage_outcome_hash",
            "m10_stage_outcome", "m10_stage_outcome_hash", "cad_request", "m10_request",
            "m10_scope", "m10_binding", "metrics", "hard_witnesses",
            "unresolved_findings", "outcome", "evaluator_identity", "evaluator_version",
            "evaluation_hash",
        },
        "CandidateEvaluationV2",
    )
    return _hash(
        {
            "schema_version": evaluation.schema_version,
            "candidate_hash": evaluation.candidate_hash,
            "source_binding_hash": evaluation.source_binding_hash,
            "synthesis_request_hash": evaluation.synthesis_request_hash,
            "synthesis_policy_hash": evaluation.synthesis_policy_hash,
            "policy": evaluation.policy.model_dump(mode="json"),
            "policy_hash": evaluation.policy_hash,
            "evaluation_scope_hash": evaluation.evaluation_scope_hash,
            "required_check_keys": list(evaluation.required_check_keys),
            "m12_3_result_hash": admissibility_result_hash(evaluation.m12_3_result),
            "cad_stage_outcome_hash": candidate_cad_stage_outcome_hash_v2(
                evaluation.cad_stage_outcome
            ),
            "m10_stage_outcome_hash": candidate_m10_stage_outcome_hash_v2(
                evaluation.m10_stage_outcome
            ),
            "cad_request_hash": (
                None
                if evaluation.cad_request is None
                else candidate_request_hash_v3(evaluation.cad_request)
            ),
            "m10_request_hash": (
                None if evaluation.m10_request is None else evaluation.m10_request.request_hash
            ),
            "m10_scope_hash": (
                None if evaluation.m10_scope is None else evaluation.m10_scope.scope_hash
            ),
            "m10_binding_hash": (
                None if evaluation.m10_binding is None else evaluation.m10_binding.binding_hash
            ),
            "metrics": [metric.model_dump(mode="json") for metric in evaluation.metrics],
            "hard_witnesses": list(evaluation.hard_witnesses),
            "unresolved_findings": list(evaluation.unresolved_findings),
            "outcome": evaluation.outcome.value,
        }
    )


class CandidateEvaluationService:
    def __init__(self, state_manager=None, *, currentness_verifier=None, cad_replay_verifier=None):
        if state_manager is None and currentness_verifier is None:
            raise CandidateIntegrityError(
                "candidate evaluation requires a currentness verifier or state manager"
            )
        if state_manager is not None and currentness_verifier is not None:
            raise ValueError("candidate evaluation accepts either a currentness verifier or state manager")
        self.currentness_verifier = currentness_verifier or CandidateCurrentnessService(state_manager)
        self.cad_replay_verifier = cad_replay_verifier

    def _evaluate_v2(
        self,
        candidate: MechanicalDesignCandidate,
        synthesis_request: CandidateSynthesisRequest,
        synthesis_policy: CandidateSynthesisPolicy,
        m12_3_result: RevoluteDriveAdmissibilityResult,
        cad_stage_outcome: CandidateCadStageOutcomeV2,
        m10_stage_outcome: CandidateM10StageOutcomeV2,
        policy: CandidateEvaluationPolicy,
        *,
        cad_request: CandidateCadRealizationRequestV3 | None,
        m10_request: CandidateM10EvaluationRequestV2 | None,
        m10_scope: CandidateM10EvaluationScope | None,
        m10_binding: CandidateM10BindingV2 | None,
    ) -> CandidateEvaluationV2:
        candidate = MechanicalDesignCandidate.model_validate(
            candidate.model_dump(mode="json")
        )
        if (
            candidate.schema_version != "mechanical-design-candidate@2"
            or synthesis_request.schema_version != "candidate-synthesis-request@2"
        ):
            raise CandidateIntegrityError(
                "candidate evaluation@2 requires candidate@2 and typed request@2"
            )
        synthesis_request = CandidateSynthesisRequest.model_validate(
            synthesis_request.model_dump(mode="json")
        )
        synthesis_policy = CandidateSynthesisPolicy.model_validate(
            synthesis_policy.model_dump(mode="json")
        )
        CandidateIntegrityVerifier().verify(candidate, synthesis_request, synthesis_policy)
        currentness = self.currentness_verifier.evaluate(
            candidate, synthesis_request, synthesis_policy
        )
        if currentness is not CandidateCurrentness.CURRENT:
            raise CandidateIntegrityError(f"candidate is not current: {currentness.value}")

        m12_3_result = RevoluteDriveAdmissibilityResult.model_validate(
            m12_3_result.model_dump(mode="json")
        )
        if m12_3_result.schema_version != "revolute-drive-admissibility@2":
            raise CandidateIntegrityError(
                "candidate evaluation@2 requires admissibility@2"
            )
        if (
            m12_3_result.candidate_hash != candidate.candidate_hash
            or m12_3_result.source_binding_hash != candidate.semantic_source_binding_hash
            or m12_3_result.synthesis_request_hash != synthesis_request.request_hash
            or m12_3_result.synthesis_policy_hash != synthesis_policy.policy_hash
        ):
            raise CandidateIntegrityError("candidate evaluation@2 M12-3 parent mismatch")
        if m12_3_result.result_hash != admissibility_result_hash(m12_3_result):
            raise CandidateIntegrityError("candidate evaluation@2 M12-3 result hash mismatch")

        cad_stage_outcome = CandidateCadStageOutcomeV2.model_validate(
            cad_stage_outcome.model_dump(mode="json")
        )
        m10_stage_outcome = CandidateM10StageOutcomeV2.model_validate(
            m10_stage_outcome.model_dump(mode="json")
        )
        policy = CandidateEvaluationPolicy.model_validate(policy.model_dump(mode="json"))
        if cad_stage_outcome.status is CandidateCadStageStatus.SUCCESS:
            if cad_request is None:
                raise ValueError("successful CAD @2 evaluation requires request@3")
            realization = _validate_cad_inputs_v2(
                candidate, cad_request, cad_stage_outcome
            )
        else:
            realization = None
            if cad_request is not None:
                raise ValueError("uncompleted CAD @2 evaluation cannot retain request@3")

        if m10_stage_outcome.status is CandidateM10StageStatus.NOT_REACHED:
            if any(value is not None for value in (m10_request, m10_scope, m10_binding)):
                raise ValueError("not-reached M10 @2 evaluation cannot retain M10 context")
        else:
            if realization is None or any(
                value is None for value in (m10_request, m10_scope, m10_binding)
            ):
                raise ValueError("completed M10 @2 evaluation requires exact stage inputs")
            _validate_m10_inputs_v2(
                candidate,
                synthesis_request,
                m12_3_result,
                cad_stage_outcome,
                m10_stage_outcome,
                cad_request,
                m10_request,
                m10_scope,
                m10_binding,
            )

        outcome, hard, unresolved = _expected_outcome_v2(
            m12_3_result,
            cad_stage_outcome,
            m10_stage_outcome,
            policy.required_check_keys,
            m10_request,
        )
        metric = (
            _metric_from_stage_v2(m10_stage_outcome)
            if "m10_continuous_clearance" in policy.required_check_keys
            else None
        )
        return CandidateEvaluationV2(
            candidate_hash=candidate.candidate_hash,
            source_binding_hash=candidate.semantic_source_binding_hash,
            synthesis_request_hash=synthesis_request.request_hash,
            synthesis_policy_hash=synthesis_policy.policy_hash,
            policy=policy,
            policy_hash=policy.policy_hash,
            evaluation_scope_hash=(
                None
                if m10_stage_outcome.status is CandidateM10StageStatus.NOT_REACHED
                else m10_stage_outcome.scope_hash
            ),
            required_check_keys=policy.required_check_keys,
            m12_3_result=m12_3_result,
            m12_3_result_hash=admissibility_result_hash(m12_3_result),
            cad_stage_outcome=cad_stage_outcome,
            cad_stage_outcome_hash=candidate_cad_stage_outcome_hash_v2(cad_stage_outcome),
            m10_stage_outcome=m10_stage_outcome,
            m10_stage_outcome_hash=candidate_m10_stage_outcome_hash_v2(m10_stage_outcome),
            cad_request=cad_request,
            m10_request=m10_request,
            m10_scope=m10_scope,
            m10_binding=m10_binding,
            metrics=() if metric is None else (metric,),
            hard_witnesses=hard,
            unresolved_findings=unresolved,
            outcome=outcome,
        )

    def evaluate(
        self,
        candidate: MechanicalDesignCandidate,
        synthesis_request: CandidateSynthesisRequest,
        synthesis_policy: CandidateSynthesisPolicy,
        m12_3_result: RevoluteDriveAdmissibilityResult,
        cad_stage_outcome: CandidateCadStageOutcome | CandidateCadStageOutcomeV2,
        m10_stage_outcome: CandidateM10StageOutcome | CandidateM10StageOutcomeV2,
        policy: CandidateEvaluationPolicy,
        *,
        cad_request: CandidateCadRealizationRequest | CandidateCadRealizationRequestV3 | None = None,
        m10_request: CandidateM10EvaluationRequest | CandidateM10EvaluationRequestV2 | None = None,
        m10_scope: CandidateM10EvaluationScope | None = None,
        m10_binding: CandidateM10Binding | CandidateM10BindingV2 | None = None,
    ) -> CandidateEvaluation | CandidateEvaluationV2:
        if candidate.schema_version == "mechanical-design-candidate@2":
            return self._evaluate_v2(
                candidate,
                synthesis_request,
                synthesis_policy,
                m12_3_result,
                cad_stage_outcome,
                m10_stage_outcome,
                policy,
                cad_request=cad_request,
                m10_request=m10_request,
                m10_scope=m10_scope,
                m10_binding=m10_binding,
            )
        synthesis_request = CandidateSynthesisRequest.model_validate(
            synthesis_request.model_dump(mode="json")
        )
        synthesis_policy = CandidateSynthesisPolicy.model_validate(
            synthesis_policy.model_dump(mode="json")
        )
        CandidateIntegrityVerifier().verify(candidate, synthesis_request, synthesis_policy)
        currentness = self.currentness_verifier.evaluate(
            candidate, synthesis_request, synthesis_policy
        )
        if currentness is not CandidateCurrentness.CURRENT:
            raise CandidateIntegrityError(f"candidate is not current: {currentness.value}")
        m12_3_result = RevoluteDriveAdmissibilityResult.model_validate(
            m12_3_result.model_dump(mode="json")
        )
        cad_stage_outcome = CandidateCadStageOutcome.model_validate(
            cad_stage_outcome.model_dump(mode="json")
        )
        m10_stage_outcome = CandidateM10StageOutcome.model_validate(
            m10_stage_outcome.model_dump(mode="json")
        )
        policy = CandidateEvaluationPolicy.model_validate(policy.model_dump(mode="json"))
        source_binding_hash = _hash(candidate.source_binding)
        if m12_3_result.candidate_hash != candidate.candidate_hash:
            raise ValueError("M12-3 result is bound to a different candidate")
        if m12_3_result.source_binding_hash != source_binding_hash:
            raise ValueError("M12-3 result is bound to a different source")
        if m12_3_result.synthesis_request_hash != synthesis_request.request_hash:
            raise ValueError("M12-3 result synthesis request binding mismatch")
        if m12_3_result.synthesis_policy_hash != synthesis_policy.policy_hash:
            raise ValueError("M12-3 result synthesis policy binding mismatch")
        if cad_stage_outcome.status is CandidateCadStageStatus.SUCCESS:
            assert cad_stage_outcome.realization is not None
            if cad_stage_outcome.realization.candidate_hash != candidate.candidate_hash:
                raise ValueError("CAD stage is bound to a different candidate")
        if m10_stage_outcome.candidate_hash != candidate.candidate_hash:
            raise ValueError("M10 stage is bound to a different candidate")
        if m10_stage_outcome.source_revision != candidate.source_binding.source_revision:
            raise ValueError("M10 stage source revision mismatch")
        if m10_stage_outcome.source_state_hash != candidate.source_binding.source_state_hash:
            raise ValueError("M10 stage source state hash mismatch")
        if cad_stage_outcome.status is CandidateCadStageStatus.SUCCESS:
            if cad_request is None:
                raise ValueError("successful CAD evaluation requires the exact CAD request")
            _validate_cad_inputs(
                candidate,
                cad_request,
                cad_stage_outcome,
                self.cad_replay_verifier,
            )
        if m10_stage_outcome.status is not CandidateM10StageStatus.NOT_REACHED:
            if any(value is None for value in (m10_request, m10_scope, m10_binding)):
                raise ValueError("completed M10 evaluation requires request, scope, and binding")
            _validate_m10_inputs(
                candidate,
                cad_stage_outcome,
                m10_stage_outcome,
                m10_request,
                m10_scope,
                m10_binding,
            )
        else:
            if any(value is not None for value in (m10_stage_outcome.binding_hash, m10_stage_outcome.scope_hash, m10_stage_outcome.evaluation_request_hash)):
                raise ValueError("not-reached M10 stage must be a reason-only record")
            if any(value is not None for value in (m10_request, m10_scope, m10_binding)):
                raise ValueError("not-reached M10 evaluation cannot retain M10 context")
        outcome, hard, unresolved = _expected_outcome(
            m12_3_result,
            cad_stage_outcome,
            m10_stage_outcome,
            policy.required_check_keys,
            m10_request,
        )
        metric = (
            _metric_from_stage(m10_stage_outcome)
            if "m10_continuous_clearance" in policy.required_check_keys
            and m10_stage_outcome.status is CandidateM10StageStatus.SUCCESS
            else None
        )
        return CandidateEvaluation(
            candidate_hash=candidate.candidate_hash,
            source_binding_hash=source_binding_hash,
            synthesis_request_hash=synthesis_request.request_hash,
            synthesis_policy_hash=synthesis_policy.policy_hash,
            policy=policy,
            policy_hash=policy.policy_hash,
            evaluation_scope_hash=m10_stage_outcome.scope_hash,
            required_check_keys=policy.required_check_keys,
            m12_3_result=m12_3_result,
            m12_3_result_hash=admissibility_result_hash(m12_3_result),
            cad_stage_outcome=cad_stage_outcome,
            cad_stage_outcome_hash=_stage_outcome_hash(cad_stage_outcome),
            m10_stage_outcome=m10_stage_outcome,
            m10_stage_outcome_hash=_stage_outcome_hash(m10_stage_outcome),
            cad_request=cad_request,
            m10_request=m10_request,
            m10_scope=m10_scope,
            m10_binding=m10_binding,
            metrics=() if metric is None else (metric,),
            hard_witnesses=hard,
            unresolved_findings=unresolved,
            outcome=outcome,
        )


class CandidateEvaluationCurrentnessService:
    def __init__(self, state_manager, *, cad_replay_verifier=None):
        if not callable(cad_replay_verifier):
            raise CandidateIntegrityError(
                "candidate evaluation currentness requires a CAD replay verifier"
            )
        self.state_manager = state_manager
        self.cad_replay_verifier = cad_replay_verifier

    def _verify_current_v2(
        self,
        evaluation: CandidateEvaluationV2,
        candidate: MechanicalDesignCandidate,
        synthesis_request: CandidateSynthesisRequest | None,
        synthesis_policy: CandidateSynthesisPolicy | None,
        m12_3_result: RevoluteDriveAdmissibilityResult | None,
        cad_stage_outcome: CandidateCadStageOutcomeV2 | None,
        m10_stage_outcome: CandidateM10StageOutcomeV2 | None,
        policy: CandidateEvaluationPolicy | None,
        cad_request: CandidateCadRealizationRequestV3 | None,
        m10_request: CandidateM10EvaluationRequestV2 | None,
        m10_scope: CandidateM10EvaluationScope | None,
        m10_binding: CandidateM10BindingV2 | None,
        exact_source_artifacts=None,
    ) -> bool:
        candidate = MechanicalDesignCandidate.model_validate(
            candidate.model_dump(mode="json")
        )
        evaluation = CandidateEvaluationV2.model_validate(
            evaluation.model_dump(mode="json")
        )
        if candidate.schema_version != "mechanical-design-candidate@2":
            raise CandidateIntegrityError(
                "candidate-evaluation@2 cannot use a legacy candidate"
            )
        if synthesis_request is None:
            raise CandidateIntegrityError(
                "candidate@2 evaluation currentness requires typed request@2"
            )
        synthesis_request = CandidateSynthesisRequest.model_validate(
            synthesis_request.model_dump(mode="json")
        )
        if synthesis_request.schema_version != "candidate-synthesis-request@2":
            raise CandidateIntegrityError(
                "candidate@2 evaluation currentness requires typed request@2"
            )
        if evaluation.schema_version != "candidate-evaluation@2":
            raise CandidateIntegrityError(
                "candidate@2 currentness requires evaluation@2"
            )
        if (
            candidate.source_binding != synthesis_request.source_binding
            or candidate.semantic_source_binding_hash
            != synthesis_request.semantic_source_binding_hash
            or candidate.synthesis_request_hash != synthesis_request.request_hash
        ):
            raise CandidateIntegrityError(
                "candidate evaluation request/candidate semantic binding mismatch"
            )
        if (
            evaluation.candidate_hash != candidate.candidate_hash
            or evaluation.source_binding_hash != candidate.semantic_source_binding_hash
            or evaluation.synthesis_request_hash != synthesis_request.request_hash
            or evaluation.synthesis_policy_hash != candidate.synthesis_policy_hash
        ):
            raise CandidateIntegrityError(
                "candidate evaluation@2 typed request parent mismatch"
            )
        if synthesis_policy is not None:
            synthesis_policy = CandidateSynthesisPolicy.model_validate(
                synthesis_policy.model_dump(mode="json")
            )
            try:
                CandidateIntegrityVerifier().verify(
                    candidate, synthesis_request, synthesis_policy
                )
            except Exception as exc:
                raise CandidateIntegrityError(
                    f"candidate evaluation@2 integrity verification failed: {exc}"
                ) from exc
        if m12_3_result is not None:
            m12_3_result = RevoluteDriveAdmissibilityResult.model_validate(
                m12_3_result.model_dump(mode="json")
            )
            if admissibility_result_hash(m12_3_result) != evaluation.m12_3_result_hash:
                raise CandidateIntegrityError("candidate evaluation@2 M12-3 result is stale")
        if cad_stage_outcome is not None:
            cad_stage_outcome = CandidateCadStageOutcomeV2.model_validate(
                cad_stage_outcome.model_dump(mode="json")
            )
            if candidate_cad_stage_outcome_hash_v2(cad_stage_outcome) != (
                evaluation.cad_stage_outcome_hash
            ):
                raise CandidateIntegrityError("candidate evaluation@2 CAD stage is stale")
        if m10_stage_outcome is not None:
            m10_stage_outcome = CandidateM10StageOutcomeV2.model_validate(
                m10_stage_outcome.model_dump(mode="json")
            )
            if candidate_m10_stage_outcome_hash_v2(m10_stage_outcome) != (
                evaluation.m10_stage_outcome_hash
            ):
                raise CandidateIntegrityError("candidate evaluation@2 M10 stage is stale")
        if policy is not None:
            policy = CandidateEvaluationPolicy.model_validate(policy.model_dump(mode="json"))
            if policy.policy_hash != evaluation.policy_hash:
                raise CandidateIntegrityError("candidate evaluation@2 policy is stale")

        effective_cad_request = cad_request or evaluation.cad_request
        effective_m10_request = m10_request or evaluation.m10_request
        effective_m10_scope = m10_scope or evaluation.m10_scope
        effective_m10_binding = m10_binding or evaluation.m10_binding
        try:
            _validate_stored_stage_context_v2(
                candidate, synthesis_request, evaluation
            )
            if evaluation.cad_stage_outcome.status is CandidateCadStageStatus.SUCCESS:
                if effective_cad_request is None:
                    raise ValueError("candidate evaluation@2 is missing request@3")
                if effective_cad_request != evaluation.cad_request:
                    raise ValueError("candidate evaluation@2 CAD request context mismatch")
            elif effective_cad_request is not None:
                raise ValueError("candidate evaluation@2 contains a request without successful CAD")
            if evaluation.m10_stage_outcome.status is CandidateM10StageStatus.NOT_REACHED:
                if any(
                    value is not None
                    for value in (
                        effective_m10_request,
                        effective_m10_scope,
                        effective_m10_binding,
                    )
                ):
                    raise ValueError(
                        "not-reached candidate evaluation@2 contains M10 context"
                    )
            else:
                if any(
                    value is None
                    for value in (
                        effective_cad_request,
                        effective_m10_request,
                        effective_m10_scope,
                        effective_m10_binding,
                    )
                ):
                    raise ValueError("candidate evaluation@2 is missing exact stage inputs")
                if (
                    effective_m10_request != evaluation.m10_request
                    or effective_m10_scope != evaluation.m10_scope
                    or effective_m10_binding != evaluation.m10_binding
                ):
                    raise ValueError("candidate evaluation@2 M10 context mismatch")
        except Exception as exc:
            raise CandidateIntegrityError(
                f"candidate evaluation@2 stage verification failed: {exc}"
            ) from exc

        currentness = CandidateCurrentnessService(self.state_manager).evaluate_source_binding(
            candidate,
            synthesis_request=synthesis_request,
            exact_source_artifacts=exact_source_artifacts,
        )
        if currentness is not CandidateCurrentness.CURRENT:
            raise CandidateIntegrityError(
                f"candidate evaluation is not current: {currentness.value}"
            )
        return True

    def verify_current(
        self,
        evaluation: CandidateEvaluation | CandidateEvaluationV2,
        candidate: MechanicalDesignCandidate,
        synthesis_request: CandidateSynthesisRequest | None = None,
        synthesis_policy: CandidateSynthesisPolicy | None = None,
        m12_3_result: RevoluteDriveAdmissibilityResult | None = None,
        cad_stage_outcome: CandidateCadStageOutcome | CandidateCadStageOutcomeV2 | None = None,
        m10_stage_outcome: CandidateM10StageOutcome | CandidateM10StageOutcomeV2 | None = None,
        policy: CandidateEvaluationPolicy | None = None,
        cad_request: CandidateCadRealizationRequest | CandidateCadRealizationRequestV3 | None = None,
        m10_request: CandidateM10EvaluationRequest | CandidateM10EvaluationRequestV2 | None = None,
        m10_scope: CandidateM10EvaluationScope | None = None,
        m10_binding: CandidateM10Binding | CandidateM10BindingV2 | None = None,
        exact_source_artifacts=None,
    ) -> bool:
        if (
            candidate.schema_version == "mechanical-design-candidate@2"
            or evaluation.schema_version == "candidate-evaluation@2"
        ):
            if not isinstance(evaluation, CandidateEvaluationV2):
                raise CandidateIntegrityError(
                    "candidate@2 currentness requires evaluation@2"
                )
            return self._verify_current_v2(
                evaluation,
                candidate,
                synthesis_request,
                synthesis_policy,
                m12_3_result,
                cad_stage_outcome,
                m10_stage_outcome,
                policy,
                cad_request,
                m10_request,
                m10_scope,
                m10_binding,
                exact_source_artifacts,
            )
        evaluation = CandidateEvaluation.model_validate(evaluation.model_dump(mode="json"))
        candidate = MechanicalDesignCandidate.model_validate(candidate.model_dump(mode="json"))
        synthesis_request = (
            CandidateSynthesisRequest.model_validate(synthesis_request.model_dump(mode="json"))
            if synthesis_request is not None
            else None
        )
        synthesis_policy = CandidateSynthesisPolicy.model_validate(
            synthesis_policy.model_dump(mode="json")
        ) if synthesis_policy is not None else None
        if (synthesis_request is None) != (synthesis_policy is None):
            raise CandidateIntegrityError("candidate evaluation currentness context is incomplete")
        if candidate.schema_version == "mechanical-design-candidate@2" and synthesis_request is None:
            raise CandidateIntegrityError(
                "candidate@2 evaluation currentness requires synthesis request@2"
            )
        if (
            candidate.schema_version == "mechanical-design-candidate@2"
            and evaluation.schema_version != "candidate-evaluation@2"
        ):
            raise CandidateIntegrityError(
                "candidate@2 evaluation currentness requires evaluation@2"
            )
        if (
            candidate.schema_version != "mechanical-design-candidate@2"
            and synthesis_request is not None
            and synthesis_request.schema_version == "candidate-synthesis-request@2"
        ):
            raise CandidateIntegrityError(
                "legacy candidate evaluation cannot carry synthesis request@2"
            )
        if synthesis_request is not None and synthesis_policy is not None:
            CandidateIntegrityVerifier().verify(candidate, synthesis_request, synthesis_policy)
        elif (
            evaluation.synthesis_request_hash != candidate.synthesis_request_hash
            or evaluation.synthesis_policy_hash != candidate.synthesis_policy_hash
        ):
            raise CandidateIntegrityError("candidate evaluation synthesis binding mismatch")
        if m12_3_result is not None:
            m12_3_result = RevoluteDriveAdmissibilityResult.model_validate(
                m12_3_result.model_dump(mode="json")
            )
        if cad_stage_outcome is not None:
            cad_stage_outcome = CandidateCadStageOutcome.model_validate(
                cad_stage_outcome.model_dump(mode="json")
            )
        if m10_stage_outcome is not None:
            m10_stage_outcome = CandidateM10StageOutcome.model_validate(
                m10_stage_outcome.model_dump(mode="json")
            )
        if policy is not None:
            policy = CandidateEvaluationPolicy.model_validate(policy.model_dump(mode="json"))
        if evaluation.candidate_hash != candidate.candidate_hash:
            raise CandidateIntegrityError("candidate evaluation candidate binding mismatch")
        if evaluation.source_binding_hash != _hash(candidate.source_binding):
            raise CandidateIntegrityError("candidate evaluation source binding mismatch")
        expected_synthesis_request_hash = (
            synthesis_request.request_hash
            if synthesis_request is not None
            else candidate.synthesis_request_hash
        )
        expected_synthesis_policy_hash = (
            synthesis_policy.policy_hash
            if synthesis_policy is not None
            else candidate.synthesis_policy_hash
        )
        if evaluation.synthesis_request_hash != expected_synthesis_request_hash:
            raise CandidateIntegrityError("candidate evaluation request binding mismatch")
        if evaluation.synthesis_policy_hash != expected_synthesis_policy_hash:
            raise CandidateIntegrityError("candidate evaluation synthesis policy binding mismatch")
        if evaluation.m10_stage_outcome.candidate_hash != candidate.candidate_hash:
            raise CandidateIntegrityError("candidate evaluation M10 candidate binding mismatch")
        if evaluation.m10_stage_outcome.source_revision != candidate.source_binding.source_revision:
            raise CandidateIntegrityError("candidate evaluation M10 source revision mismatch")
        if evaluation.m10_stage_outcome.source_state_hash != candidate.source_binding.source_state_hash:
            raise CandidateIntegrityError("candidate evaluation M10 source state hash mismatch")
        if m12_3_result is not None and evaluation.m12_3_result_hash != admissibility_result_hash(m12_3_result):
            raise CandidateIntegrityError("candidate evaluation M12-3 result is stale")
        if cad_stage_outcome is not None and evaluation.cad_stage_outcome_hash != _stage_outcome_hash(cad_stage_outcome):
            raise CandidateIntegrityError("candidate evaluation CAD stage is stale")
        if m10_stage_outcome is not None and evaluation.m10_stage_outcome_hash != _stage_outcome_hash(m10_stage_outcome):
            raise CandidateIntegrityError("candidate evaluation M10 stage is stale")
        if policy is not None and evaluation.policy_hash != policy.policy_hash:
            raise CandidateIntegrityError("candidate evaluation policy is stale")
        effective_cad_request = cad_request or evaluation.cad_request
        effective_m10_request = m10_request or evaluation.m10_request
        effective_m10_scope = m10_scope or evaluation.m10_scope
        effective_m10_binding = m10_binding or evaluation.m10_binding
        if evaluation.cad_stage_outcome.status is CandidateCadStageStatus.SUCCESS:
            if effective_cad_request is None:
                raise CandidateIntegrityError("candidate evaluation is missing the exact CAD request")
            try:
                _validate_cad_inputs(
                    candidate,
                    effective_cad_request,
                    evaluation.cad_stage_outcome,
                    self.cad_replay_verifier,
                )
            except ValueError as exc:
                raise CandidateIntegrityError(str(exc)) from exc

        if evaluation.m10_stage_outcome.status is not CandidateM10StageStatus.NOT_REACHED:
            if any(
                value is None
                for value in (
                    effective_cad_request,
                    effective_m10_request,
                    effective_m10_scope,
                    effective_m10_binding,
                )
            ):
                raise CandidateIntegrityError("candidate evaluation is missing exact stage inputs")
            try:
                _validate_m10_inputs(
                    candidate,
                    evaluation.cad_stage_outcome,
                    evaluation.m10_stage_outcome,
                    effective_m10_request,
                    effective_m10_scope,
                    effective_m10_binding,
                )
            except ValueError as exc:
                raise CandidateIntegrityError(str(exc)) from exc
        else:
            if any(value is not None for value in (
                evaluation.m10_stage_outcome.binding_hash,
                evaluation.m10_stage_outcome.scope_hash,
                evaluation.m10_stage_outcome.evaluation_request_hash,
                evaluation.evaluation_scope_hash,
                effective_cad_request,
                effective_m10_request,
                effective_m10_scope,
                effective_m10_binding,
            )):
                raise CandidateIntegrityError("not-reached candidate evaluation contains M10 context")
        currentness = (
            CandidateCurrentnessService(self.state_manager).evaluate(
                candidate, synthesis_request, synthesis_policy
            )
            if synthesis_request is not None and synthesis_policy is not None
            else CandidateCurrentnessService(self.state_manager).evaluate_source_binding(
                candidate, synthesis_request=synthesis_request
            )
        )
        if currentness is not CandidateCurrentness.CURRENT:
            raise CandidateIntegrityError(f"candidate evaluation is not current: {currentness.value}")
        return True


__all__ = [
    "CandidateEvaluationCurrentnessService",
    "CandidateEvaluationOutcome",
    "CandidateEvaluationPolicy",
    "CandidateEvaluationService",
    "CandidateEvaluation",
    "CandidateEvaluationV2",
    "CandidateMetric",
    "CandidateMetricKey",
    "candidate_evaluation_hash_v2",
]
