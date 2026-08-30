from __future__ import annotations

import hashlib
import math
from enum import StrEnum
from typing import Any, Literal

from pydantic import (
    AliasChoices,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from mechcad_harness.changes.operations import ChangeOperation
from mechcad_harness.models import ChangeProposal
from mechcad_harness.models.common import Model
from mechcad_harness.models.physical_mechanism import (
    CanonicalAcceptedDesignChoice,
    CanonicalComponentPropertyAuthority,
    CanonicalComponentSpecification,
    CanonicalJointPhysicalBinding,
    CanonicalM10VerificationObligation,
    CanonicalMechanicalConnection,
    CanonicalPhysicalComponent,
    CanonicalPhysicalMechanism,
    CanonicalPlacement,
)
from mechcad_harness.revolute_drive import (
    DriveAdmissibility,
    InputProvenanceKind,
    RevoluteDriveAdmissibilityResult,
    admissibility_result_hash,
)
from mechcad_harness.state.hashing import canonical_json

from .cad_realization import CandidateGeometryFidelity
from .comparison import (
    CandidateComparisonRequest,
    CandidateComparisonResult,
    candidate_comparison_request_hash,
)
from .evaluation import CandidateEvaluation, CandidateEvaluationOutcome
from .models import (
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
    MechanicalDesignCandidate,
)
from .selection import CandidateSelection


def _hash(value: Model, identity_field: str | None = None) -> str:
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


def _optional_nonblank(value: str | None) -> str | None:
    return None if value is None else _nonblank(value)


def _nonblank_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    if any(not value.strip() for value in values):
        raise ValueError("identity values must not be empty")
    return values


class PromotionModel(Model):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
    )


class PromotionValueClassification(StrEnum):
    ACCEPTED_PHYSICAL_FACT = "accepted_physical_fact"
    ACCEPTED_DESIGN_CHOICE = "accepted_design_choice"
    CANONICAL_REDERIVATION_INPUT = "canonical_rederivation_input"
    PROVENANCE_ONLY = "provenance_only"
    DO_NOT_PROMOTE = "do_not_promote"


PromotionSourceValue = (
    StrictStr
    | StrictFloat
    | StrictInt
    | StrictBool
    | tuple[StrictFloat, StrictFloat]
)


class PromotionClassification(PromotionModel):
    """Explicit classification for one candidate-defining input."""

    source_identity: StrictStr = Field(min_length=1)
    source_provenance: InputProvenanceKind = InputProvenanceKind.SOURCE_AUTHORITY
    classification: PromotionValueClassification
    source_value: PromotionSourceValue | None = None
    classification_hash: StrictStr = "pending"

    _validate_source_identity = field_validator("source_identity")(_nonblank)
    _validate_hash = field_validator("classification_hash")(_hash_or_pending)

    @field_validator("source_value")
    @classmethod
    def validate_source_value(cls, value: Any) -> Any:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("classified source values must be finite")
        if isinstance(value, str) and not value.strip():
            raise ValueError("classified source values must not be empty")
        if isinstance(value, tuple):
            if len(value) != 2 or any(not math.isfinite(number) for number in value) or value[0] > value[1]:
                raise ValueError("classified source ranges must be finite and ordered")
        return value

    @model_validator(mode="after")
    def validate_classification(self) -> "PromotionClassification":
        expected = _hash(self, "classification_hash")
        if self.classification_hash == "pending":
            object.__setattr__(self, "classification_hash", expected)
        elif self.classification_hash != expected:
            raise ValueError("promotion classification hash mismatch")
        return self


class CandidatePromotionPolicy(PromotionModel):
    schema_version: Literal["candidate-promotion-policy@1"] = "candidate-promotion-policy@1"
    allowed_target_family: StrictStr = "canonical_physical_mechanism"
    mapping_schema_version: StrictStr = "candidate-canonical-mapping@1"
    compiler_version: StrictStr = "candidate-promotion@1"
    allowed_classifications: tuple[PromotionValueClassification, ...] = Field(
        default=tuple(PromotionValueClassification),
        validation_alias=AliasChoices(
            "allowed_classifications", "allowed_promotion_classifications"
        ),
    )
    required_property_authorities: tuple[CanonicalComponentPropertyAuthority, ...] = Field(
        default=(),
        validation_alias=AliasChoices(
            "required_property_authorities", "required_source_property_authorities"
        ),
    )
    publication_mode: Literal["decision_and_result_manifests"] = Field(
        default="decision_and_result_manifests",
        validation_alias=AliasChoices("publication_mode", "publication_behavior"),
    )
    policy_hash: StrictStr = "pending"

    _validate_text = field_validator(
        "allowed_target_family", "mapping_schema_version", "compiler_version"
    )(_nonblank)
    _validate_hash = field_validator("policy_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_policy(self) -> "CandidatePromotionPolicy":
        if not self.allowed_classifications:
            raise ValueError("promotion policy requires at least one classification")
        if len(set(self.allowed_classifications)) != len(self.allowed_classifications):
            raise ValueError("promotion policy classifications must be unique")
        if len(set(self.required_property_authorities)) != len(self.required_property_authorities):
            raise ValueError("promotion policy property authorities must be unique")
        expected = _hash(self, "policy_hash")
        if self.policy_hash == "pending":
            object.__setattr__(self, "policy_hash", expected)
        elif self.policy_hash != expected:
            raise ValueError("candidate promotion policy hash mismatch")
        return self


class PostPromotionM11TargetIntent(PromotionModel):
    schema_version: Literal["post-promotion-m11-target-intent@1"] = (
        "post-promotion-m11-target-intent@1"
    )
    assessment_requested: StrictBool = True
    target_scope: Literal["whole_mechanism", "single_component"] = "whole_mechanism"
    candidate_instance_id: StrictStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "candidate_instance_id", "candidate_physical_instance_id"
        ),
    )
    analysis_category: Literal["linear_static"] = Field(
        default="linear_static",
        validation_alias=AliasChoices("analysis_category", "requested_analysis_category"),
    )
    intent_hash: StrictStr = "pending"

    _validate_optional_id = field_validator("candidate_instance_id")(_optional_nonblank)
    _validate_category = field_validator("analysis_category")(_nonblank)
    _validate_hash = field_validator("intent_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_intent(self) -> "PostPromotionM11TargetIntent":
        if self.target_scope == "single_component" and self.candidate_instance_id is None:
            raise ValueError("single-component M11 intent requires a candidate instance")
        if self.target_scope == "whole_mechanism" and self.candidate_instance_id is not None:
            raise ValueError("whole-mechanism M11 intent cannot name a candidate instance")
        expected = _hash(self, "intent_hash")
        if self.intent_hash == "pending":
            object.__setattr__(self, "intent_hash", expected)
        elif self.intent_hash != expected:
            raise ValueError("post-promotion M11 intent hash mismatch")
        return self

    @property
    def candidate_physical_instance_id(self) -> str | None:
        return self.candidate_instance_id

    @property
    def requested_analysis_category(self) -> str:
        return self.analysis_category


class PromotionPhysicalPairRequirement(PromotionModel):
    requirement_key: StrictStr = Field(min_length=1)
    first_instance_id: StrictStr = Field(min_length=1)
    first_interface_id: StrictStr = Field(min_length=1)
    second_instance_id: StrictStr = Field(min_length=1)
    second_interface_id: StrictStr = Field(min_length=1)
    requires_home_exact_check: StrictBool = False
    requirement_hash: StrictStr = "pending"

    _validate_text = field_validator(
        "requirement_key",
        "first_instance_id",
        "first_interface_id",
        "second_instance_id",
        "second_interface_id",
    )(_nonblank)
    _validate_hash = field_validator("requirement_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_pair(self) -> "PromotionPhysicalPairRequirement":
        if self.first_instance_id == self.second_instance_id:
            raise ValueError("promotion physical pair must contain two instances")
        expected = _hash(self, "requirement_hash")
        if self.requirement_hash == "pending":
            object.__setattr__(self, "requirement_hash", expected)
        elif self.requirement_hash != expected:
            raise ValueError("promotion physical pair requirement hash mismatch")
        return self


class PrePromotionM10ScopeProjection(PromotionModel):
    schema_version: Literal["pre-promotion-m10-scope-projection@1"] = (
        "pre-promotion-m10-scope-projection@1"
    )
    joint_semantic_key: StrictStr = Field(min_length=1)
    angle_interval_deg: tuple[StrictFloat, StrictFloat]
    path_semantics: StrictStr = "single_axis_interval"
    required_clearance_mm: StrictFloat = Field(ge=0)
    physical_pair_requirements: tuple[PromotionPhysicalPairRequirement, ...] = Field(
        min_length=1
    )
    fidelity_requirements: tuple[tuple[StrictStr, CandidateGeometryFidelity], ...] = ()
    required_home_check_semantics: tuple[StrictStr, ...] = ()
    bounded_limitations: tuple[StrictStr, ...] = ()
    projection_hash: StrictStr = "pending"

    _validate_text = field_validator("joint_semantic_key", "path_semantics")(_nonblank)
    _validate_hash = field_validator("projection_hash")(_hash_or_pending)

    @field_validator("required_clearance_mm")
    @classmethod
    def validate_clearance(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("pre-promotion M10 clearance must be finite")
        return value

    @model_validator(mode="after")
    def validate_projection(self) -> "PrePromotionM10ScopeProjection":
        start, end = self.angle_interval_deg
        if not all(math.isfinite(value) for value in (start, end)) or start > end:
            raise ValueError("pre-promotion M10 interval must be finite and ordered")
        fidelity_keys = tuple(key for key, _ in self.fidelity_requirements)
        if any(not key.strip() for key in fidelity_keys) or len(set(fidelity_keys)) != len(fidelity_keys):
            raise ValueError("pre-promotion fidelity keys must be unique and non-empty")
        if any(not value.strip() for value in self.required_home_check_semantics + self.bounded_limitations):
            raise ValueError("pre-promotion M10 semantic text must not be empty")
        expected = _hash(self, "projection_hash")
        if self.projection_hash == "pending":
            object.__setattr__(self, "projection_hash", expected)
        elif self.projection_hash != expected:
            raise ValueError("pre-promotion M10 projection hash mismatch")
        return self


class CandidateCanonicalInstanceMapping(PromotionModel):
    candidate_instance_id: StrictStr = Field(min_length=1)
    canonical_instance_id: StrictStr = Field(min_length=1)
    canonical_path: StrictStr = Field(min_length=2)
    classification: PromotionValueClassification
    source_identity: StrictStr = Field(min_length=1)
    source_provenance: InputProvenanceKind = InputProvenanceKind.SOURCE_AUTHORITY
    source_value: PromotionSourceValue | None = None
    mapping_hash: StrictStr = "pending"

    _validate_text = field_validator(
        "candidate_instance_id", "canonical_instance_id", "canonical_path", "source_identity"
    )(_nonblank)
    _validate_hash = field_validator("mapping_hash")(_hash_or_pending)

    @field_validator("source_value")
    @classmethod
    def validate_source_value(cls, value: Any) -> Any:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("mapped source values must be finite")
        if isinstance(value, str) and not value.strip():
            raise ValueError("mapped source values must not be empty")
        if isinstance(value, tuple):
            if len(value) != 2 or any(not math.isfinite(number) for number in value) or value[0] > value[1]:
                raise ValueError("mapped source ranges must be finite and ordered")
        return value

    @model_validator(mode="after")
    def validate_mapping(self) -> "CandidateCanonicalInstanceMapping":
        if not self.canonical_path.startswith("/") or "//" in self.canonical_path or "~" in self.canonical_path:
            raise ValueError("canonical mapping path must be a literal path")
        expected = _hash(self, "mapping_hash")
        if self.mapping_hash == "pending":
            object.__setattr__(self, "mapping_hash", expected)
        elif self.mapping_hash != expected:
            raise ValueError("candidate canonical mapping hash mismatch")
        return self


class PromotionDecisionInputReference(PromotionModel):
    schema_version: Literal["promotion-decision-input-reference@1"] = (
        "promotion-decision-input-reference@1"
    )
    promotion_request_hash: StrictStr
    project_id: StrictStr = Field(min_length=1)
    base_revision: StrictInt = Field(gt=0)
    base_state_hash: StrictStr
    candidate_hash: StrictStr
    synthesis_request_hash: StrictStr
    synthesis_policy_hash: StrictStr
    m12_3_result_hash: StrictStr
    evaluation_hash: StrictStr
    selection_hash: StrictStr
    comparison_used: StrictBool = False
    comparison_result_hash: StrictStr | None = None
    comparison_request_hash: StrictStr | None = None
    promotion_policy_hash: StrictStr
    canonical_target_mechanism_id: StrictStr = Field(min_length=1)
    m11_target_intent: PostPromotionM11TargetIntent | None = None
    mapping_identities: tuple[StrictStr, ...] = ()
    classification_identities: tuple[StrictStr, ...] = ()
    reference_hash: StrictStr = "pending"

    _validate_hashes = field_validator(
        "promotion_request_hash",
        "base_state_hash",
        "candidate_hash",
        "synthesis_request_hash",
        "synthesis_policy_hash",
        "m12_3_result_hash",
        "evaluation_hash",
        "selection_hash",
        "promotion_policy_hash",
    )(_require_hash)
    _validate_optional_hashes = field_validator("comparison_result_hash", "comparison_request_hash")(
        lambda value: None if value is None else _require_hash(value)
    )
    _validate_reference_hash = field_validator("reference_hash")(_hash_or_pending)
    _validate_project = field_validator("project_id", "canonical_target_mechanism_id")(_nonblank)
    _validate_identities = field_validator("mapping_identities", "classification_identities")(
        _nonblank_tuple
    )

    @model_validator(mode="after")
    def validate_reference(self) -> "PromotionDecisionInputReference":
        if self.comparison_used != (self.comparison_result_hash is not None):
            raise ValueError("comparison result identity must match comparison usage")
        if self.comparison_used != (self.comparison_request_hash is not None):
            raise ValueError("comparison request identity must match comparison usage")
        expected = _hash(self, "reference_hash")
        if self.reference_hash == "pending":
            object.__setattr__(self, "reference_hash", expected)
        elif self.reference_hash != expected:
            raise ValueError("promotion decision input reference hash mismatch")
        return self


class CandidatePromotionRequest(PromotionModel):
    """Transient readiness input; it is never canonical authority."""

    schema_version: Literal["candidate-promotion-request@1"] = "candidate-promotion-request@1"
    project_id: StrictStr = Field(min_length=1)
    source_revision: StrictInt = Field(gt=0)
    source_state_hash: StrictStr
    candidate: MechanicalDesignCandidate
    synthesis_request: CandidateSynthesisRequest
    synthesis_policy: CandidateSynthesisPolicy
    m12_3_result: RevoluteDriveAdmissibilityResult
    evaluation: CandidateEvaluation
    selection: CandidateSelection
    comparison_used: StrictBool = False
    comparison: CandidateComparisonResult | None = None
    comparison_request: CandidateComparisonRequest | None = None
    comparison_entries: tuple[tuple[MechanicalDesignCandidate, CandidateEvaluation], ...] | None = None
    promotion_policy: CandidatePromotionPolicy
    canonical_target_mechanism_id: StrictStr = Field(min_length=1)
    classifications: tuple[PromotionClassification, ...] = ()
    m11_target_intent: PostPromotionM11TargetIntent | None = None
    request_hash: StrictStr = "pending"

    _validate_source_hash = field_validator("source_state_hash")(_require_hash)
    _validate_request_hash = field_validator("request_hash")(_hash_or_pending)
    _validate_text = field_validator("project_id", "canonical_target_mechanism_id")(_nonblank)

    @model_validator(mode="after")
    def validate_request(self) -> "CandidatePromotionRequest":
        candidate_source_binding_hash = _hash(self.candidate.source_binding)
        if self.candidate.source_binding.project_id != self.project_id:
            raise ValueError("promotion project binding mismatch")
        if self.candidate.source_binding.source_revision != self.source_revision or self.candidate.source_binding.source_state_hash != self.source_state_hash:
            raise ValueError("promotion source binding mismatch")
        if self.synthesis_request.request_hash != self.candidate.synthesis_request_hash:
            raise ValueError("promotion synthesis request binding mismatch")
        if self.synthesis_policy.policy_hash != self.candidate.synthesis_policy_hash:
            raise ValueError("promotion synthesis policy binding mismatch")
        if (
            self.m12_3_result.source_binding_hash != candidate_source_binding_hash
            or self.evaluation.source_binding_hash != candidate_source_binding_hash
        ):
            raise ValueError("promotion source binding hash mismatch")
        if self.evaluation.synthesis_request_hash != self.candidate.synthesis_request_hash:
            raise ValueError("promotion evaluation synthesis request binding mismatch")
        if self.evaluation.synthesis_policy_hash != self.candidate.synthesis_policy_hash:
            raise ValueError("promotion evaluation synthesis policy binding mismatch")
        if self.m12_3_result.candidate_hash != self.candidate.candidate_hash:
            raise ValueError("promotion M12-3 candidate binding mismatch")
        if admissibility_result_hash(self.m12_3_result) != self.evaluation.m12_3_result_hash:
            raise ValueError("promotion M12-3 result identity mismatch")
        if self.evaluation.candidate_hash != self.candidate.candidate_hash:
            raise ValueError("promotion evaluation candidate binding mismatch")
        if self.selection.candidate_hash != self.candidate.candidate_hash or self.selection.evaluation_hash != self.evaluation.evaluation_hash:
            raise ValueError("promotion selection binding mismatch")
        if self.selection.source_binding_hash != candidate_source_binding_hash:
            raise ValueError("selection source binding mismatch")
        if self.selection.evaluation_scope_hash != self.evaluation.evaluation_scope_hash:
            raise ValueError("selection evaluation scope mismatch")
        if self.comparison_used != (self.comparison is not None):
            raise ValueError("comparison result must match comparison usage")
        if self.comparison_used != (self.comparison_request is not None):
            raise ValueError("comparison request must match comparison usage")
        if self.comparison_used != (self.comparison_entries is not None):
            raise ValueError("comparison entries must match comparison usage")
        if self.comparison_used:
            assert self.comparison is not None
            assert self.comparison_request is not None
            assert self.comparison_entries is not None
            if (
                candidate_comparison_request_hash(self.comparison_request)
                != self.comparison_request.request_hash
            ):
                raise ValueError("comparison request identity is invalid")
            if self.comparison_request.request_hash != self.comparison.request_hash:
                raise ValueError("comparison request/result identity mismatch")
            selected_pair = (self.candidate.candidate_hash, self.evaluation.evaluation_hash)
            if selected_pair not in self.comparison_request.candidate_evaluation_pairs:
                raise ValueError("comparison request/result selected pair mismatch")
            if self.comparison_request.project_id != self.project_id or self.comparison.project_id != self.project_id:
                raise ValueError("comparison project binding mismatch")
            if (
                self.comparison_request.source_binding_hash != self.evaluation.source_binding_hash
                or self.comparison.source_binding_hash != self.evaluation.source_binding_hash
                or self.comparison_request.evaluation_scope_hash != self.evaluation.evaluation_scope_hash
                or self.comparison.evaluation_scope_hash != self.evaluation.evaluation_scope_hash
            ):
                raise ValueError("comparison source binding mismatch")
            if (
                self.comparison_request.candidate_evaluation_pairs
                != self.comparison.candidate_evaluation_pairs
            ):
                raise ValueError("comparison request/result membership mismatch")
            if not self.comparison_entries:
                raise ValueError("comparison entries must not be empty")
            entry_pairs = tuple(
                (candidate.candidate_hash, evaluation.evaluation_hash)
                for candidate, evaluation in self.comparison_entries
            )
            if any(
                evaluation.candidate_hash != candidate.candidate_hash
                for candidate, evaluation in self.comparison_entries
            ):
                raise ValueError("comparison entries contain inconsistent candidate bindings")
            for member_candidate, member_evaluation in self.comparison_entries:
                member_source_binding_hash = _hash(member_candidate.source_binding)
                if (
                    member_candidate.source_binding.project_id != self.project_id
                    or member_source_binding_hash
                    != self.comparison_request.source_binding_hash
                ):
                    raise ValueError("comparison entry source binding mismatch")
                if member_evaluation.source_binding_hash != member_source_binding_hash:
                    raise ValueError("comparison entry source binding mismatch")
                if (
                    member_evaluation.evaluation_scope_hash
                    != self.comparison_request.evaluation_scope_hash
                ):
                    raise ValueError("comparison entry evaluation scope mismatch")
            if len(set(entry_pairs)) != len(entry_pairs):
                raise ValueError("comparison entries must be unique")
            if entry_pairs != self.comparison_request.candidate_evaluation_pairs:
                raise ValueError("comparison membership does not match comparison entries")
            if not self.selection.comparison_used:
                raise ValueError("comparison use must match selection comparison usage")
            if self.selection.comparison_result_hash != self.comparison.result_hash:
                raise ValueError("comparison result must match selection comparison result")
        elif self.selection.comparison_used:
            raise ValueError("comparison use must match selection comparison usage")
        expected = _hash(self, "request_hash")
        if self.request_hash == "pending":
            object.__setattr__(self, "request_hash", expected)
        elif self.request_hash != expected:
            raise ValueError("candidate promotion request hash mismatch")
        return self


class PromotableMechanismProjection(PromotionModel):
    schema_version: Literal["promotable-mechanism-projection@1"] = (
        "promotable-mechanism-projection@1"
    )
    canonical_target_mechanism_id: StrictStr = Field(min_length=1)
    canonical_instance_ids: tuple[StrictStr, ...] = Field(min_length=1)
    component_specifications: tuple[CanonicalComponentSpecification, ...] = ()
    components: tuple[CanonicalPhysicalComponent, ...] = ()
    accepted_design_choices: tuple[CanonicalAcceptedDesignChoice, ...] = ()
    placements: tuple[CanonicalPlacement, ...] = ()
    connections: tuple[CanonicalMechanicalConnection, ...] = ()
    joint_bindings: tuple[CanonicalJointPhysicalBinding, ...] = ()
    m10_obligations: tuple[CanonicalM10VerificationObligation, ...] = ()
    mapping_identities: tuple[StrictStr, ...] = ()
    projection_hash: StrictStr = "pending"

    _validate_text = field_validator("canonical_target_mechanism_id")(_nonblank)
    _validate_hash = field_validator("projection_hash")(_hash_or_pending)
    _validate_ids = field_validator("canonical_instance_ids", "mapping_identities")(_nonblank_tuple)

    @model_validator(mode="after")
    def validate_projection(self) -> "PromotableMechanismProjection":
        if len(set(self.canonical_instance_ids)) != len(self.canonical_instance_ids):
            raise ValueError("canonical projection instance IDs must be unique")
        expected = _hash(self, "projection_hash")
        if self.projection_hash == "pending":
            object.__setattr__(self, "projection_hash", expected)
        elif self.projection_hash != expected:
            raise ValueError("promotable mechanism projection hash mismatch")
        return self


class CandidatePromotionCompilation(PromotionModel):
    schema_version: Literal["candidate-promotion-compilation@1"] = (
        "candidate-promotion-compilation@1"
    )
    canonical_mechanism: CanonicalPhysicalMechanism
    proposal: ChangeProposal
    promotion_proposal_hash: StrictStr
    mapping: tuple[CandidateCanonicalInstanceMapping, ...]
    projection: PromotableMechanismProjection
    compilation_hash: StrictStr = "pending"

    _validate_hashes = field_validator("promotion_proposal_hash")(_require_hash)
    _validate_compilation_hash = field_validator("compilation_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_compilation(self) -> "CandidatePromotionCompilation":
        if self.canonical_mechanism.id != self.projection.canonical_target_mechanism_id:
            raise ValueError("promotion compilation mechanism/projection mismatch")
        self.validated_proposal()
        expected = _hash(self, "compilation_hash")
        if self.compilation_hash == "pending":
            object.__setattr__(self, "compilation_hash", expected)
        elif self.compilation_hash != expected:
            raise ValueError("candidate promotion compilation hash mismatch")
        return self

    def validated_proposal(self) -> ChangeProposal:
        """Return the proposal only while its complete semantic payload is current."""

        expected = promotion_proposal_hash(
            self.proposal.base_revision,
            self.proposal.base_state_hash,
            tuple(self.proposal.operations),
        )
        if self.promotion_proposal_hash != expected:
            raise ValueError("promotion proposal semantic hash mismatch")
        return self.proposal


class PromotionApplicationStatus(StrEnum):
    PRE_APPLY_FAILURE = "pre_apply_failure"
    CHANGEENGINE_REJECTED = "changeengine_rejected"
    PROMOTION_APPLIED_BUT_RUN_TRANSITION_FAILED = "promotion_applied_but_run_transition_failed"
    PROMOTION_APPLIED_BUT_INVALIDATION_PERSISTENCE_FAILED = "promotion_applied_but_invalidation_persistence_failed"
    PROMOTION_APPLIED_BUT_INVALIDATION_VERIFICATION_FAILED = "promotion_applied_but_invalidation_verification_failed"
    PROMOTION_APPLIED_BUT_RESULT_PROVENANCE_FAILED = "promotion_applied_but_result_provenance_failed"
    PROMOTION_APPLIED = "promotion_applied"


class CandidatePromotionApplicationResult(PromotionModel):
    """Application receipt; later verification must not require this object."""

    schema_version: Literal["candidate-promotion-application-result@1"] = (
        "candidate-promotion-application-result@1"
    )
    request: CandidatePromotionRequest | None = None
    compilation: CandidatePromotionCompilation | None = None
    decision_artifact_id: StrictStr | None = None
    result_artifact_id: StrictStr | None = None
    applied_revision: StrictInt | None = Field(default=None, gt=0)
    applied_state_hash: StrictStr | None = None
    status: PromotionApplicationStatus
    error: StrictStr | None = None

    _validate_hash = field_validator("applied_state_hash")(
        lambda value: None if value is None else _require_hash(value)
    )
    _validate_ids = field_validator("decision_artifact_id", "result_artifact_id")(_optional_nonblank)
    _validate_error = field_validator("error")(_optional_nonblank)


class PromotedMechanismVerificationStatus(StrEnum):
    VERIFIED = "verified"
    ENGINEERING_VIOLATION = "engineering_violation"
    UNRESOLVED = "unresolved"
    INTEGRITY_FAILURE = "integrity_failure"
    OPERATIONAL_FAILURE = "operational_failure"


class PromotedMechanismVerificationResult(PromotionModel):
    """Durable post-promotion provenance, independent of transient candidates."""

    schema_version: Literal["promoted-mechanism-verification-result@1"] = (
        "promoted-mechanism-verification-result@1"
    )
    promotion_result_artifact_id: StrictStr | None = None
    promotion_result_hash: StrictStr | None = None
    promoted_revision: StrictInt | None = Field(default=None, gt=0)
    promoted_state_hash: StrictStr | None = None
    canonical_target_mechanism_id: StrictStr | None = None
    canonical_mechanism_hash: StrictStr | None = None
    projection_hash: StrictStr | None = None
    projection_equivalence_hash: StrictStr | None = None
    canonical_cad_request_hash: StrictStr | None = None
    canonical_cad_realization_hash: StrictStr | None = None
    canonical_m10_inventory_hash: StrictStr | None = None
    canonical_m10_outcome_hash: StrictStr | None = None
    canonical_m10_request_hashes: tuple[StrictStr, ...] = ()
    canonical_m10_result_hashes: tuple[StrictStr, ...] = ()
    scope_equivalence_hash: StrictStr | None = None
    m11_handoff_hash: StrictStr | None = None
    status: PromotedMechanismVerificationStatus
    error: StrictStr | None = None
    verification_hash: StrictStr = "pending"

    _validate_hashes = field_validator(
        "promotion_result_hash",
        "promoted_state_hash",
        "canonical_mechanism_hash",
        "projection_hash",
    )(lambda value: None if value is None else _require_hash(value))
    _validate_optional_hashes = field_validator(
        "projection_equivalence_hash",
        "canonical_cad_request_hash",
        "canonical_cad_realization_hash",
        "canonical_m10_inventory_hash",
        "canonical_m10_outcome_hash",
        "scope_equivalence_hash",
        "m11_handoff_hash",
    )(lambda value: None if value is None else _require_hash(value))
    _validate_sequence_hashes = field_validator(
        "canonical_m10_request_hashes", "canonical_m10_result_hashes"
    )(lambda values: tuple(_require_hash(value) for value in values))
    _validate_text = field_validator(
        "promotion_result_artifact_id", "canonical_target_mechanism_id"
    )(lambda value: None if value is None else _nonblank(value))
    _validate_optional_error = field_validator("error")(_optional_nonblank)
    _validate_verification_hash = field_validator("verification_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_result(self) -> "PromotedMechanismVerificationResult":
        if self.status in (
            PromotedMechanismVerificationStatus.VERIFIED,
            PromotedMechanismVerificationStatus.ENGINEERING_VIOLATION,
            PromotedMechanismVerificationStatus.UNRESOLVED,
        ):
            required = (
                self.promotion_result_artifact_id,
                self.promotion_result_hash,
                self.promoted_revision,
                self.promoted_state_hash,
                self.canonical_target_mechanism_id,
                self.canonical_mechanism_hash,
                self.projection_hash,
                self.projection_equivalence_hash,
                self.canonical_cad_request_hash,
                self.canonical_cad_realization_hash,
                self.canonical_m10_inventory_hash,
                self.canonical_m10_outcome_hash,
                self.scope_equivalence_hash,
            )
            if any(value is None for value in required):
                raise ValueError("post-promotion result is incomplete")
            if not self.canonical_m10_request_hashes or not self.canonical_m10_result_hashes:
                raise ValueError("post-promotion result requires canonical M10 identities")
        if len(self.canonical_m10_request_hashes) != len(self.canonical_m10_result_hashes):
            raise ValueError("canonical M10 request/result identity counts must match")
        expected = _hash(self, "verification_hash")
        if self.verification_hash == "pending":
            object.__setattr__(self, "verification_hash", expected)
        elif self.verification_hash != expected:
            raise ValueError("promoted mechanism verification hash mismatch")
        return self


def promotion_proposal_hash(
    base_revision: int,
    base_state_hash: str,
    operations: tuple[ChangeOperation, ...] | list[ChangeOperation],
) -> str:
    """Hash proposal semantics without operational proposal or run identities."""

    if base_revision <= 0:
        raise ValueError("base revision must be positive")
    _require_hash(base_state_hash)
    normalized_operations = tuple(ChangeOperation.model_validate(operation) for operation in operations)
    payload = {
        "base_revision": base_revision,
        "base_state_hash": base_state_hash,
        "operations": [operation.model_dump(mode="json") for operation in normalized_operations],
    }
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


__all__ = [
    "CandidateCanonicalInstanceMapping",
    "CandidatePromotionApplicationResult",
    "CandidatePromotionCompilation",
    "CandidatePromotionPolicy",
    "CandidatePromotionRequest",
    "PostPromotionM11TargetIntent",
    "PrePromotionM10ScopeProjection",
    "PromotionApplicationStatus",
    "PromotionClassification",
    "PromotionDecisionInputReference",
    "PromotionPhysicalPairRequirement",
    "PromotionValueClassification",
    "PromotionSourceValue",
    "PromotableMechanismProjection",
    "PromotedMechanismVerificationResult",
    "PromotedMechanismVerificationStatus",
    "promotion_proposal_hash",
]
