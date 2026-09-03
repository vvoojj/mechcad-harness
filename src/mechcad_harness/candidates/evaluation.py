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
    CandidateGeometryFidelity,
    CandidateCadRealizationService,
)
from mechcad_harness.candidates.m10_evaluation import (
    CandidateM10Binding,
    CandidateM10EvaluationRequest,
    CandidateM10EvaluationScope,
    CandidateM10PairClassification,
    CandidateM10StageOutcome,
    CandidateM10StageStatus,
    CandidateM10BodyDisposition,
    CandidateM10EvaluationService,
)
from mechcad_harness.candidates.models import (
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
    MechanicalDesignCandidate,
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
from mechcad_harness.cad_assembly import assembly_hash
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

    def evaluate(
        self,
        candidate: MechanicalDesignCandidate,
        synthesis_request: CandidateSynthesisRequest,
        synthesis_policy: CandidateSynthesisPolicy,
        m12_3_result: RevoluteDriveAdmissibilityResult,
        cad_stage_outcome: CandidateCadStageOutcome,
        m10_stage_outcome: CandidateM10StageOutcome,
        policy: CandidateEvaluationPolicy,
        *,
        cad_request: CandidateCadRealizationRequest | None = None,
        m10_request: CandidateM10EvaluationRequest | None = None,
        m10_scope: CandidateM10EvaluationScope | None = None,
        m10_binding: CandidateM10Binding | None = None,
    ) -> CandidateEvaluation:
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

    def verify_current(
        self,
        evaluation: CandidateEvaluation,
        candidate: MechanicalDesignCandidate,
        synthesis_request: CandidateSynthesisRequest | None = None,
        synthesis_policy: CandidateSynthesisPolicy | None = None,
        m12_3_result: RevoluteDriveAdmissibilityResult | None = None,
        cad_stage_outcome: CandidateCadStageOutcome | None = None,
        m10_stage_outcome: CandidateM10StageOutcome | None = None,
        policy: CandidateEvaluationPolicy | None = None,
        cad_request: CandidateCadRealizationRequest | None = None,
        m10_request: CandidateM10EvaluationRequest | None = None,
        m10_scope: CandidateM10EvaluationScope | None = None,
        m10_binding: CandidateM10Binding | None = None,
    ) -> bool:
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
        if synthesis_request is not None:
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
            if synthesis_request is not None
            else CandidateCurrentnessService(self.state_manager).evaluate_source_binding(candidate)
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
    "CandidateMetric",
    "CandidateMetricKey",
]
