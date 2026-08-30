from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Literal

from pydantic import ConfigDict, Field, StrictInt, StrictStr, field_validator, model_validator

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.models import (
    StructuralAnalysisKind,
    StructuralMaterialPropertyName,
    evaluate_material_authority_policy,
)
from mechcad_harness.state import state_hash as calculate_state_hash
from mechcad_harness.state.errors import RevisionNotFoundError, StateIntegrityError
from mechcad_harness.state.hashing import canonical_json
from .canonical_mechanism import (
    CanonicalMechanismReconstruction,
    _projection_from_mechanism,
)
from .promotion_artifacts import (
    CandidatePromotionResultManifest,
    PromotionManifestIntegrityError,
    PromotionManifestService,
    SelectedCandidateDecisionManifest,
)
from .promotion_models import (
    CandidateCanonicalInstanceMapping,
    CandidatePromotionApplicationResult,
    CandidatePromotionCompilation,
    PostPromotionM11TargetIntent,
    PromotionApplicationStatus,
    PromotionModel,
    _nonblank,
    _require_hash,
)


def _identity(value: PromotionModel, field: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(field, None)
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def _hash_or_pending(value: str) -> str:
    return value if value == "pending" else _require_hash(value)


class CanonicalM11HandoffStatus(StrEnum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    UNRESOLVED = "unresolved"
    INTEGRITY_FAILURE = "integrity_failure"
    OPERATIONAL_FAILURE = "operational_failure"


class CanonicalM11HandoffIntegrityError(ValueError):
    """A post-promotion M11 handoff failed a trust-boundary check."""


class CanonicalM11HandoffRequest(PromotionModel):
    """An explicit, post-promotion M11 eligibility request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["canonical-m11-handoff-request@1"] = (
        "canonical-m11-handoff-request@1"
    )
    project_id: StrictStr = Field(min_length=1)
    promoted_revision: StrictInt = Field(gt=0)
    promoted_state_hash: StrictStr
    canonical_mechanism_id: StrictStr = Field(min_length=1)
    canonical_mechanism_hash: StrictStr
    target_scope: Literal["whole_mechanism", "single_component"]
    target_instance_id: StrictStr = Field(min_length=1)
    target_geometry_artifact_id: StrictStr | None = None
    target_geometry_artifact_hash: StrictStr | None = None
    target_geometry_bound_revision: StrictInt | None = Field(default=None, gt=0)
    target_geometry_bound_state_hash: StrictStr | None = None
    analysis_category: Literal["linear_static"]
    eligibility_scope: Literal["single_solid_only"] = "single_solid_only"
    eligibility_scope_version: StrictStr = "m11-eligibility-only@1"
    intent: PostPromotionM11TargetIntent
    promotion_result_artifact_id: StrictStr = Field(min_length=1)
    promotion_result_hash: StrictStr
    decision_artifact_id: StrictStr = Field(min_length=1)
    decision_artifact_hash: StrictStr
    promotion_proposal_hash: StrictStr
    mapping_hashes: tuple[StrictStr, ...] = Field(min_length=1)
    mapping: tuple[CandidateCanonicalInstanceMapping, ...] = Field(min_length=1)
    request_hash: StrictStr = "pending"

    _validate_text = field_validator(
        "project_id",
        "canonical_mechanism_id",
        "target_instance_id",
        "eligibility_scope_version",
        "promotion_result_artifact_id",
        "decision_artifact_id",
    )(_nonblank)
    _validate_optional_geometry_id = field_validator("target_geometry_artifact_id")(
        lambda value: None if value is None else _nonblank(value)
    )
    @field_validator(
        "promoted_state_hash",
        "canonical_mechanism_hash",
        "promotion_result_hash",
        "decision_artifact_hash",
        "promotion_proposal_hash",
        "mapping_hashes",
    )
    @classmethod
    def _validate_hash_values(cls, value):
        if isinstance(value, tuple):
            return tuple(_require_hash(item) for item in value)
        return _require_hash(value)

    _validate_optional_geometry_hash = field_validator("target_geometry_artifact_hash")(
        lambda value: None if value is None else _require_hash(value)
    )
    _validate_optional_geometry_bound_hash = field_validator(
        "target_geometry_bound_state_hash"
    )(
        lambda value: None if value is None else _require_hash(value)
    )

    _validate_request_hash = field_validator("request_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_request(self) -> "CanonicalM11HandoffRequest":
        if self.intent.target_scope != self.target_scope:
            raise ValueError("M11 handoff target scope does not match intent")
        if self.intent.analysis_category != self.analysis_category:
            raise ValueError("M11 handoff analysis category does not match intent")
        if (self.target_geometry_artifact_id is None) != (
            self.target_geometry_artifact_hash is None
        ):
            raise ValueError("M11 target geometry artifact identity must be complete")
        if (self.target_geometry_bound_revision is None) != (
            self.target_geometry_bound_state_hash is None
        ):
            raise ValueError("M11 target geometry source binding must be complete")
        if (self.target_geometry_artifact_id is None) != (
            self.target_geometry_bound_revision is None
        ):
            raise ValueError("M11 target geometry source identity must be complete")
        if self.target_scope == "whole_mechanism" and (
            self.target_instance_id != self.canonical_mechanism_id
            or self.target_geometry_artifact_id is not None
            or self.target_geometry_artifact_hash is not None
            or self.target_geometry_bound_revision is not None
            or self.target_geometry_bound_state_hash is not None
        ):
            raise ValueError(
                "whole-mechanism M11 handoff must target the mechanism and cannot bind component geometry"
            )
        mapping_hashes = tuple(item.mapping_hash for item in self.mapping)
        candidate_ids = tuple(item.candidate_instance_id for item in self.mapping)
        canonical_ids = tuple(item.canonical_instance_id for item in self.mapping)
        if mapping_hashes != self.mapping_hashes:
            raise ValueError("M11 handoff mapping identities do not match mapping records")
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("M11 handoff candidate mapping IDs must be unique")
        if len(set(canonical_ids)) != len(canonical_ids):
            raise ValueError("M11 handoff canonical mapping IDs must be unique")
        if any(
            item.canonical_path
            != f"/physical_mechanisms/{self.canonical_mechanism_id}/components/{item.canonical_instance_id}"
            for item in self.mapping
        ):
            raise ValueError("M11 handoff mapping path does not match the canonical mechanism")
        expected = _identity(self, "request_hash")
        if self.request_hash == "pending":
            object.__setattr__(self, "request_hash", expected)
        elif self.request_hash != expected:
            raise ValueError("M11 handoff request hash mismatch")
        return self

    @property
    def revision(self) -> int:
        return self.promoted_revision

    @property
    def state_hash(self) -> str:
        return self.promoted_state_hash

    @property
    def mechanism_id(self) -> str:
        return self.canonical_mechanism_id

    @property
    def mechanism_hash(self) -> str:
        return self.canonical_mechanism_hash


class CanonicalM11HandoffResult(PromotionModel):
    """The non-executing eligibility decision for one explicit target."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["canonical-m11-handoff-result@1"] = "canonical-m11-handoff-result@1"
    status: CanonicalM11HandoffStatus
    reason: StrictStr | None = None
    missing_authority: tuple[StrictStr, ...] = ()
    result_hash: StrictStr = "pending"

    _validate_reason = field_validator("reason")(
        lambda value: None if value is None else _nonblank(value)
    )
    _validate_missing = field_validator("missing_authority")(
        lambda values: tuple(_nonblank(value) for value in values)
    )
    _validate_hash = field_validator("result_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_result(self) -> "CanonicalM11HandoffResult":
        if len(set(self.missing_authority)) != len(self.missing_authority):
            raise ValueError("M11 handoff authority gaps must be unique")
        expected = _identity(self, "result_hash")
        if self.result_hash == "pending":
            object.__setattr__(self, "result_hash", expected)
        elif self.result_hash != expected:
            raise ValueError("M11 handoff result hash mismatch")
        return self


class CanonicalM11Handoff(PromotionModel):
    """A durable-shaped, non-executing M11 eligibility assessment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["canonical-m11-handoff@1"] = "canonical-m11-handoff@1"
    project_id: StrictStr = Field(min_length=1)
    promoted_revision: StrictInt = Field(gt=0)
    promoted_state_hash: StrictStr
    canonical_mechanism_id: StrictStr = Field(min_length=1)
    canonical_mechanism_hash: StrictStr
    target_scope: Literal["whole_mechanism", "single_component"]
    target_instance_id: StrictStr = Field(min_length=1)
    analysis_category: Literal["linear_static"]
    intent_hash: StrictStr
    request: CanonicalM11HandoffRequest
    result: CanonicalM11HandoffResult
    status: CanonicalM11HandoffStatus
    result_hash: StrictStr
    handoff_hash: StrictStr = "pending"

    _validate_text = field_validator(
        "project_id", "canonical_mechanism_id", "target_instance_id"
    )(_nonblank)
    _validate_hashes = field_validator(
        "promoted_state_hash", "canonical_mechanism_hash", "intent_hash", "result_hash"
    )(_require_hash)
    _validate_handoff_hash = field_validator("handoff_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_handoff(self) -> "CanonicalM11Handoff":
        expected_fields = (
            (self.project_id, self.request.project_id),
            (self.promoted_revision, self.request.promoted_revision),
            (self.promoted_state_hash, self.request.promoted_state_hash),
            (self.canonical_mechanism_id, self.request.canonical_mechanism_id),
            (self.canonical_mechanism_hash, self.request.canonical_mechanism_hash),
            (self.target_scope, self.request.target_scope),
            (self.target_instance_id, self.request.target_instance_id),
            (self.analysis_category, self.request.analysis_category),
            (self.intent_hash, self.request.intent.intent_hash),
            (self.status, self.result.status),
            (self.result_hash, self.result.result_hash),
        )
        if any(actual != expected for actual, expected in expected_fields):
            raise ValueError("M11 handoff binding mismatch")
        expected_hash = _identity(self, "handoff_hash")
        if self.handoff_hash == "pending":
            object.__setattr__(self, "handoff_hash", expected_hash)
        elif self.handoff_hash != expected_hash:
            raise ValueError("M11 handoff hash mismatch")
        return self

    @property
    def revision(self) -> int:
        return self.promoted_revision

    @property
    def state_hash(self) -> str:
        return self.promoted_state_hash

    @property
    def mechanism_id(self) -> str:
        return self.canonical_mechanism_id

    @property
    def mechanism_hash(self) -> str:
        return self.canonical_mechanism_hash

    @property
    def target_id(self) -> str:
        return self.target_instance_id


def _strict(value, expected_type, label):
    if not isinstance(value, expected_type):
        raise CanonicalM11HandoffIntegrityError(f"{label} has the wrong type")
    try:
        return expected_type.model_validate(value.model_dump(mode="json"))
    except Exception as exc:
        raise CanonicalM11HandoffIntegrityError(f"{label} integrity validation failed: {exc}") from exc


def _promotion_context(promotion_result):
    return getattr(promotion_result, "verification_context", promotion_result)


def _verified_manifests(
    context,
    receipt: CandidatePromotionApplicationResult,
    *,
    expected_project_id: str | None = None,
    expected_intent: PostPromotionM11TargetIntent | None = None,
) -> tuple[SelectedCandidateDecisionManifest, CandidatePromotionResultManifest]:
    service = getattr(context, "manifest_service", None)
    store = getattr(context, "manifest_store", None)
    if not isinstance(service, PromotionManifestService) or not isinstance(store, ArtifactStore):
        raise CanonicalM11HandoffIntegrityError(
            "durable promotion manifest verification services are required"
        )
    if not receipt.decision_artifact_id or not receipt.result_artifact_id:
        raise CanonicalM11HandoffIntegrityError(
            "applied promotion must bind decision and result artifacts"
        )
    try:
        raw_decision = service.resolve_decision(store, receipt.decision_artifact_id)
    except PromotionManifestIntegrityError as exc:
        raise CanonicalM11HandoffIntegrityError(
            f"decision manifest verification failed: {exc}"
        ) from exc
    except Exception as exc:
        raise CanonicalM11HandoffIntegrityError(
            f"decision manifest verification failed: {exc}"
        ) from exc
    try:
        raw_result = service.resolve_result(store, receipt.result_artifact_id)
        decision_artifact = store.read_verified_strict(
            receipt.decision_artifact_id, expected_type=ArtifactType.JSON
        )
        if decision_artifact is None:
            raise CanonicalM11HandoffIntegrityError("decision artifact is missing")
    except CanonicalM11HandoffIntegrityError:
        raise
    except PromotionManifestIntegrityError as exc:
        raise CanonicalM11HandoffIntegrityError(
            f"result manifest verification failed: {exc}"
        ) from exc
    except Exception as exc:
        raise CanonicalM11HandoffIntegrityError(
            f"result manifest verification failed: {exc}"
        ) from exc
    decision = _strict(raw_decision, SelectedCandidateDecisionManifest, "decision manifest")
    result = _strict(raw_result, CandidatePromotionResultManifest, "result manifest")
    if expected_project_id is not None and decision.project_id != expected_project_id:
        raise CanonicalM11HandoffIntegrityError(
            "promotion decision project binding mismatch"
        )
    if expected_intent is not None and decision.input_reference.m11_target_intent != expected_intent:
        raise CanonicalM11HandoffIntegrityError(
            "promotion decision intent binding mismatch"
        )
    if (
        result.decision_artifact_id != receipt.decision_artifact_id
        or result.decision_artifact_hash != decision_artifact[0].sha256
    ):
        raise CanonicalM11HandoffIntegrityError(
            "promotion decision/result artifact binding mismatch"
        )
    return decision, result


def _verified_manifests_for_request(
    state_manager, request: CanonicalM11HandoffRequest
) -> tuple[SelectedCandidateDecisionManifest, CandidatePromotionResultManifest]:
    try:
        lookup = ArtifactStore(
            state_manager.workspace,
            project_id=request.project_id,
            run_id="M11-HANDOFF-LOOKUP",
        )
        decision_artifact = lookup.existing_in_project(request.decision_artifact_id)
        result_artifact = lookup.existing_in_project(request.promotion_result_artifact_id)
    except (TypeError, ValueError, AttributeError) as exc:
        raise CanonicalM11HandoffIntegrityError(
            f"promotion manifest storage scope is invalid: {exc}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"promotion manifest storage unavailable: {exc}") from exc
    if decision_artifact is None or result_artifact is None:
        raise CanonicalM11HandoffIntegrityError(
            "promoted request manifests are missing or unverified"
        )
    if (
        decision_artifact.project_id != request.project_id
        or result_artifact.project_id != request.project_id
        or decision_artifact.run_id != result_artifact.run_id
    ):
        raise CanonicalM11HandoffIntegrityError(
            "promotion manifest project or run binding mismatch"
        )
    try:
        store = ArtifactStore(
            state_manager.workspace,
            project_id=request.project_id,
            run_id=decision_artifact.run_id,
        )
    except (TypeError, ValueError, AttributeError) as exc:
        raise CanonicalM11HandoffIntegrityError(
            f"promotion manifest storage scope is invalid: {exc}"
        ) from exc
    service = PromotionManifestService()
    try:
        decision = service.resolve_decision(store, request.decision_artifact_id)
        result = service.resolve_result(store, request.promotion_result_artifact_id)
    except PromotionManifestIntegrityError as exc:
        raise CanonicalM11HandoffIntegrityError(
            f"promotion manifest verification failed: {exc}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"promotion manifest storage unavailable: {exc}") from exc
    except Exception as exc:
        raise CanonicalM11HandoffIntegrityError(
            f"promotion manifest verification failed: {exc}"
        ) from exc
    decision = _strict(decision, SelectedCandidateDecisionManifest, "decision manifest")
    result = _strict(result, CandidatePromotionResultManifest, "result manifest")
    if (
        decision.project_id != request.project_id
        or decision.base_revision >= request.promoted_revision
        or decision.base_state_hash == request.promoted_state_hash
        or decision_artifact.sha256 != request.decision_artifact_hash
        or result_artifact.artifact_id != request.promotion_result_artifact_id
        or result.decision_artifact_id != request.decision_artifact_id
        or result.decision_artifact_hash != decision_artifact.sha256
        or result.resulting_revision != request.promoted_revision
        or result.resulting_state_hash != request.promoted_state_hash
        or result.result_hash != request.promotion_result_hash
        or result.promotion_proposal_hash != request.promotion_proposal_hash
        or decision.promotion_proposal_hash != request.promotion_proposal_hash
        or decision.projection.canonical_target_mechanism_id
        != request.canonical_mechanism_id
        or tuple(item.mapping_hash for item in decision.mapping)
        != request.mapping_hashes
        or decision.mapping != request.mapping
        or result.mechanism_path
        != f"/physical_mechanisms/{request.canonical_mechanism_id}"
    ):
        raise CanonicalM11HandoffIntegrityError(
            "promoted request manifest binding mismatch"
        )
    durable_intent = decision.input_reference.m11_target_intent
    if durable_intent is None or durable_intent != request.intent:
        raise CanonicalM11HandoffIntegrityError(
            "promotion decision intent binding mismatch"
        )
    try:
        promoted_state = state_manager.load_revision(
            request.project_id, request.promoted_revision
        )
    except (StateIntegrityError, RevisionNotFoundError, TypeError, ValueError, KeyError) as exc:
        raise CanonicalM11HandoffIntegrityError(
            f"promoted canonical state verification failed: {exc}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"promoted canonical state unavailable: {exc}") from exc
    except Exception as exc:
        raise CanonicalM11HandoffIntegrityError(
            f"promoted canonical state verification failed: {exc}"
        ) from exc
    if (
        promoted_state.revision != request.promoted_revision
        or calculate_state_hash(promoted_state) != request.promoted_state_hash
    ):
        raise CanonicalM11HandoffIntegrityError(
            "promoted canonical state binding mismatch"
        )
    mechanisms = tuple(
        mechanism
        for mechanism in promoted_state.physical_mechanisms
        if mechanism.id == request.canonical_mechanism_id
    )
    if len(mechanisms) != 1:
        raise CanonicalM11HandoffIntegrityError(
            "promoted canonical mechanism is missing or ambiguous"
        )
    mechanism = mechanisms[0]
    if mechanism.mechanism_hash != request.canonical_mechanism_hash:
        raise CanonicalM11HandoffIntegrityError(
            "promoted canonical mechanism hash mismatch"
        )
    if decision.projection != _projection_from_mechanism(mechanism):
        raise CanonicalM11HandoffIntegrityError(
            "promotion mapping projection does not match the promoted canonical mechanism"
        )

    mapping = decision.mapping
    candidate_ids = tuple(item.candidate_instance_id for item in mapping)
    canonical_ids = tuple(item.canonical_instance_id for item in mapping)
    expected_canonical_ids = tuple(item.instance_id for item in mechanism.components)
    expected_paths = tuple(
        f"/physical_mechanisms/{mechanism.id}/components/{instance_id}"
        for instance_id in expected_canonical_ids
    )
    if (
        not mapping
        or len(set(candidate_ids)) != len(candidate_ids)
        or len(set(canonical_ids)) != len(canonical_ids)
        or canonical_ids != expected_canonical_ids
        or tuple(item.canonical_path for item in mapping) != expected_paths
    ):
        raise CanonicalM11HandoffIntegrityError(
            "promotion mapping records do not exactly cover the promoted canonical mechanism"
        )
    return decision, result


def build_handoff_request(
    intent: PostPromotionM11TargetIntent | None,
    promotion_result,
    reconstruction: CanonicalMechanismReconstruction,
) -> CanonicalM11HandoffRequest | None:
    """Bind an explicit pre-promotion intent to verified N+1 canonical facts."""

    if intent is None or not getattr(intent, "assessment_requested", False):
        return None
    intent = _strict(intent, PostPromotionM11TargetIntent, "M11 target intent")
    context = _promotion_context(promotion_result)
    receipt = _strict(
        getattr(context, "application_result", context),
        CandidatePromotionApplicationResult,
        "promotion application result",
    )
    if receipt.status is not PromotionApplicationStatus.PROMOTION_APPLIED:
        raise CanonicalM11HandoffIntegrityError("promotion result is not an applied promotion")
    if receipt.compilation is None or receipt.applied_revision is None or receipt.applied_state_hash is None:
        raise CanonicalM11HandoffIntegrityError("promotion result lacks applied binding")
    compilation = _strict(receipt.compilation, CandidatePromotionCompilation, "promotion compilation")
    try:
        compilation.validated_proposal()
    except Exception as exc:
        raise CanonicalM11HandoffIntegrityError(f"promotion compilation is invalid: {exc}") from exc
    reconstruction = _strict(
        reconstruction, CanonicalMechanismReconstruction, "canonical reconstruction"
    )
    decision, manifest = _verified_manifests(
        context,
        receipt,
        expected_project_id=reconstruction.project_id,
        expected_intent=intent,
    )
    expected_paths = tuple(dict.fromkeys(operation.path for operation in compilation.proposal.operations))
    if (
        manifest.resulting_revision != receipt.applied_revision
        or manifest.resulting_state_hash != receipt.applied_state_hash
        or manifest.promotion_proposal_hash != compilation.promotion_proposal_hash
        or manifest.proposal_id != compilation.proposal.id
        or manifest.changed_paths != expected_paths
        or manifest.resulting_revision != compilation.proposal.base_revision + 1
        or manifest.mechanism_path
        != f"/physical_mechanisms/{compilation.projection.canonical_target_mechanism_id}"
    ):
        raise CanonicalM11HandoffIntegrityError("promotion result manifest binding mismatch")
    if decision.mapping != compilation.mapping:
        raise CanonicalM11HandoffIntegrityError("promotion decision mapping binding mismatch")
    if (
        decision.base_revision != compilation.proposal.base_revision
        or decision.base_state_hash != compilation.proposal.base_state_hash
        or decision.compilation_hash != compilation.compilation_hash
        or decision.promotion_proposal_hash != compilation.promotion_proposal_hash
        or decision.projection != compilation.projection
    ):
        raise CanonicalM11HandoffIntegrityError("promotion decision manifest binding mismatch")
    mechanism = reconstruction.mechanism
    if (
        reconstruction.revision != receipt.applied_revision
        or reconstruction.state_hash != receipt.applied_state_hash
        or mechanism.id != compilation.projection.canonical_target_mechanism_id
        or mechanism.mechanism_hash != compilation.canonical_mechanism.mechanism_hash
    ):
        raise CanonicalM11HandoffIntegrityError("canonical reconstruction binding mismatch")
    mappings = compilation.mapping
    candidate_ids = [item.candidate_instance_id for item in mappings]
    canonical_ids = [item.canonical_instance_id for item in mappings]
    if len(set(candidate_ids)) != len(candidate_ids) or len(set(canonical_ids)) != len(canonical_ids):
        raise CanonicalM11HandoffIntegrityError("promotion target mapping is ambiguous")
    mechanism_instance_ids = {component.instance_id for component in mechanism.components}
    if set(canonical_ids) != mechanism_instance_ids:
        raise CanonicalM11HandoffIntegrityError("promotion target mapping is foreign")
    if any(
        item.canonical_path
        != f"/physical_mechanisms/{mechanism.id}/components/{item.canonical_instance_id}"
        for item in mappings
    ):
        raise CanonicalM11HandoffIntegrityError("promotion target mapping path is foreign")
    if intent.target_scope == "whole_mechanism":
        target_instance_id = mechanism.id
    else:
        matches = [
            item.canonical_instance_id
            for item in mappings
            if item.candidate_instance_id == intent.candidate_instance_id
        ]
        if len(matches) != 1:
            raise CanonicalM11HandoffIntegrityError("promotion target mapping is missing or ambiguous")
        target_instance_id = matches[0]
    if intent.target_scope == "whole_mechanism" and target_instance_id != mechanism.id:
        raise CanonicalM11HandoffIntegrityError(
            "whole-mechanism M11 handoff target must equal the canonical mechanism"
        )
    target_geometry_artifact_id = None
    target_geometry_artifact_hash = None
    target_geometry_bound_revision = None
    target_geometry_bound_state_hash = None
    if intent.target_scope == "single_component":
        component = next(
            item for item in mechanism.components if item.instance_id == target_instance_id
        )
        specifications = [
            item
            for item in mechanism.component_specifications
            if item.specification_hash == component.specification_hash
        ]
        if len(specifications) != 1:
            raise CanonicalM11HandoffIntegrityError(
                "M11 target component specification is missing or ambiguous"
            )
        source = specifications[0].geometry_source
        if source is not None:
            trusted = [
                item
                for item in reconstruction.trusted_source_references
                if item.artifact_id == source.artifact_id
            ]
            if len(trusted) != 1 or trusted[0].sha256 != source.artifact_hash:
                raise CanonicalM11HandoffIntegrityError(
                    "M11 target geometry source trust binding mismatch"
                )
            target_geometry_artifact_id = source.artifact_id
            target_geometry_artifact_hash = source.artifact_hash
            target_geometry_bound_revision = trusted[0].bound_revision
            target_geometry_bound_state_hash = trusted[0].bound_state_hash
    return CanonicalM11HandoffRequest(
        project_id=reconstruction.project_id,
        promoted_revision=reconstruction.revision,
        promoted_state_hash=reconstruction.state_hash,
        canonical_mechanism_id=mechanism.id,
        canonical_mechanism_hash=mechanism.mechanism_hash,
        target_scope=intent.target_scope,
        target_instance_id=target_instance_id,
        target_geometry_artifact_id=target_geometry_artifact_id,
        target_geometry_artifact_hash=target_geometry_artifact_hash,
        target_geometry_bound_revision=target_geometry_bound_revision,
        target_geometry_bound_state_hash=target_geometry_bound_state_hash,
        analysis_category=intent.analysis_category,
        intent=intent,
        promotion_result_artifact_id=receipt.result_artifact_id,
        promotion_result_hash=manifest.result_hash,
        decision_artifact_id=manifest.decision_artifact_id,
        decision_artifact_hash=manifest.decision_artifact_hash,
        promotion_proposal_hash=manifest.promotion_proposal_hash,
        mapping_hashes=tuple(item.mapping_hash for item in mappings),
        mapping=mappings,
    )


class CanonicalM11HandoffService:
    """Assess M11 eligibility without creating or executing structural inputs."""

    def __init__(self, state_manager=None, *, structural_service=None, geometry_adapter=None) -> None:
        self.state_manager = state_manager
        self.structural_service = structural_service
        self.geometry_adapter = geometry_adapter

    def assess(self, request: CanonicalM11HandoffRequest) -> CanonicalM11Handoff:
        if (
            isinstance(request, CanonicalM11HandoffRequest)
            and request.target_scope == "whole_mechanism"
            and request.target_instance_id != request.canonical_mechanism_id
        ):
            return self._assessment(
                request,
                CanonicalM11HandoffStatus.INTEGRITY_FAILURE,
                "whole-mechanism M11 handoff target must equal the canonical mechanism",
            )
        request = _strict(request, CanonicalM11HandoffRequest, "M11 handoff request")
        if self.state_manager is None:
            return self._assessment(request, CanonicalM11HandoffStatus.OPERATIONAL_FAILURE, "state manager unavailable")
        try:
            decision, _result_manifest = _verified_manifests_for_request(
                self.state_manager, request
            )
        except CanonicalM11HandoffIntegrityError as exc:
            return self._assessment(request, CanonicalM11HandoffStatus.INTEGRITY_FAILURE, str(exc))
        except RuntimeError as exc:
            return self._assessment(request, CanonicalM11HandoffStatus.OPERATIONAL_FAILURE, str(exc))
        except (TypeError, ValueError, AttributeError) as exc:
            return self._assessment(request, CanonicalM11HandoffStatus.INTEGRITY_FAILURE, str(exc))
        except OSError as exc:
            return self._assessment(request, CanonicalM11HandoffStatus.OPERATIONAL_FAILURE, str(exc))
        if request.intent.assessment_requested is not True:
            return self._assessment(
                request,
                CanonicalM11HandoffStatus.INTEGRITY_FAILURE,
                "M11 assessment was not requested",
            )
        if (
            request.eligibility_scope != "single_solid_only"
            or request.eligibility_scope_version != "m11-eligibility-only@1"
        ):
            return self._assessment(
                request,
                CanonicalM11HandoffStatus.INTEGRITY_FAILURE,
                "unsupported M11 eligibility scope",
            )
        try:
            current = self.state_manager.load_current_pointer(request.project_id)
        except (StateIntegrityError, RevisionNotFoundError, TypeError, ValueError, KeyError) as exc:
            return self._assessment(request, CanonicalM11HandoffStatus.INTEGRITY_FAILURE, str(exc))
        except OSError as exc:
            return self._assessment(request, CanonicalM11HandoffStatus.OPERATIONAL_FAILURE, str(exc))
        except Exception as exc:
            return self._assessment(request, CanonicalM11HandoffStatus.OPERATIONAL_FAILURE, str(exc))
        if (
            current["revision"] != request.promoted_revision
            or current["state_hash"] != request.promoted_state_hash
        ):
            return self._assessment(
                request,
                CanonicalM11HandoffStatus.INTEGRITY_FAILURE,
                "promoted revision is not the project current revision",
            )
        try:
            state = self.state_manager.load_revision(request.project_id, request.promoted_revision)
        except (StateIntegrityError, RevisionNotFoundError) as exc:
            return self._assessment(request, CanonicalM11HandoffStatus.INTEGRITY_FAILURE, str(exc))
        except Exception as exc:
            return self._assessment(request, CanonicalM11HandoffStatus.OPERATIONAL_FAILURE, str(exc))
        if (
            state.revision != request.promoted_revision
            or calculate_state_hash(state) != request.promoted_state_hash
        ):
            return self._assessment(request, CanonicalM11HandoffStatus.INTEGRITY_FAILURE, "promoted state binding mismatch")
        mechanisms = [item for item in state.physical_mechanisms if item.id == request.canonical_mechanism_id]
        if len(mechanisms) != 1 or mechanisms[0].mechanism_hash != request.canonical_mechanism_hash:
            return self._assessment(request, CanonicalM11HandoffStatus.INTEGRITY_FAILURE, "canonical mechanism binding mismatch")
        mechanism = mechanisms[0]
        if request.target_scope == "whole_mechanism":
            return self._assessment(request, CanonicalM11HandoffStatus.NOT_ELIGIBLE, "whole_mechanism_target")
        if request.analysis_category != "linear_static":
            return self._assessment(request, CanonicalM11HandoffStatus.NOT_ELIGIBLE, "unsupported_analysis_category")
        if request.target_instance_id not in {item.instance_id for item in mechanism.components}:
            return self._assessment(request, CanonicalM11HandoffStatus.INTEGRITY_FAILURE, "target is not a canonical component")
        mapped_targets = [
            item.canonical_instance_id
            for item in decision.mapping
            if item.candidate_instance_id == request.intent.candidate_instance_id
        ]
        if len(mapped_targets) != 1 or mapped_targets[0] != request.target_instance_id:
            return self._assessment(
                request,
                CanonicalM11HandoffStatus.INTEGRITY_FAILURE,
                "target does not match the durable candidate mapping",
            )
        definitions = [
            definition
            for definition in state.structural_analysis_definitions
            if definition.target_body_id == request.target_instance_id
        ]
        if not definitions:
            return self._assessment(
                request,
                CanonicalM11HandoffStatus.UNRESOLVED,
                "missing canonical structural definition",
                ("structural_definition",),
            )
        if len(definitions) != 1:
            return self._assessment(request, CanonicalM11HandoffStatus.INTEGRITY_FAILURE, "ambiguous structural definition")
        definition = definitions[0]
        if (
            definition.analysis_kind is not StructuralAnalysisKind.LINEAR_STATIC_SOLID
            or definition.physical_assumptions.body_scope != "single_solid_body"
        ):
            return self._assessment(request, CanonicalM11HandoffStatus.NOT_ELIGIBLE, "unsupported structural target")
        component = next(
            item for item in mechanism.components if item.instance_id == request.target_instance_id
        )
        specifications = [
            item
            for item in mechanism.component_specifications
            if item.specification_hash == component.specification_hash
        ]
        if len(specifications) != 1:
            return self._assessment(
                request,
                CanonicalM11HandoffStatus.INTEGRITY_FAILURE,
                "canonical target specification is missing or ambiguous",
            )
        source = specifications[0].geometry_source
        if source is None:
            return self._assessment(
                request,
                CanonicalM11HandoffStatus.UNRESOLVED,
                "canonical geometry source is missing",
                ("geometry_source",),
            )
        if (
            request.target_geometry_artifact_id != source.artifact_id
            or request.target_geometry_artifact_hash != source.artifact_hash
        ):
            return self._assessment(
                request,
                CanonicalM11HandoffStatus.INTEGRITY_FAILURE,
                "canonical geometry source binding mismatch",
            )
        geometry_status = self._inspect_geometry(request, source)
        if geometry_status is not None:
            return self._assessment(request, *geometry_status)
        missing = self._missing_authority(definition)
        if missing:
            return self._assessment(request, CanonicalM11HandoffStatus.UNRESOLVED, "structural authority is incomplete", missing)
        return self._assessment(request, CanonicalM11HandoffStatus.ELIGIBLE, None)

    def _inspect_geometry(self, request, source):
        if self.geometry_adapter is None:
            return (
                CanonicalM11HandoffStatus.OPERATIONAL_FAILURE,
                "geometry inspection service unavailable",
                (),
            )
        try:
            store = ArtifactStore(
                self.state_manager.workspace,
                project_id=request.project_id,
                run_id="M11-HANDOFF-LOOKUP",
            )
            unbound = store.read_verified_in_project(
                source.artifact_id, expected_type=ArtifactType.STEP
            )
            if unbound is None:
                return (
                    CanonicalM11HandoffStatus.INTEGRITY_FAILURE,
                    "canonical geometry source artifact is missing or invalid",
                    (),
                )
            artifact = unbound[0]
            try:
                bound_state_hash = _require_hash(artifact.bound_state_hash)
            except ValueError:
                return (
                    CanonicalM11HandoffStatus.INTEGRITY_FAILURE,
                    "canonical geometry source binding is malformed",
                    (),
                )
            if (
                artifact.project_id != request.project_id
                or artifact.artifact_id != source.artifact_id
                or artifact.artifact_type is not ArtifactType.STEP
                or artifact.bound_revision <= 0
                or not bound_state_hash
                or artifact.bound_revision != request.target_geometry_bound_revision
                or bound_state_hash != request.target_geometry_bound_state_hash
                or artifact.sha256 != source.artifact_hash
            ):
                return (
                    CanonicalM11HandoffStatus.INTEGRITY_FAILURE,
                    "canonical geometry source binding mismatch",
                    (),
                )
            verified = store.read_verified_in_project(
                source.artifact_id,
                expected_type=ArtifactType.STEP,
                expected_hash=source.artifact_hash,
            )
            if verified is None:
                return (
                    CanonicalM11HandoffStatus.INTEGRITY_FAILURE,
                    "canonical geometry source verification failed",
                    (),
                )
            path = store.path_for_in_project(verified[0])
            if path is None:
                return (
                    CanonicalM11HandoffStatus.INTEGRITY_FAILURE,
                    "canonical geometry source path is untrusted",
                    (),
                )
            realization = self.geometry_adapter.realize_geometry(path)
        except Exception as exc:
            return (
                CanonicalM11HandoffStatus.OPERATIONAL_FAILURE,
                f"canonical geometry inspection failed: {exc}",
                (),
            )
        solid_count = getattr(realization, "solid_count", None)
        if (
            getattr(realization, "shape_valid", False) is not True
            or not isinstance(solid_count, int)
            or isinstance(solid_count, bool)
            or solid_count < 0
        ):
            return (
                CanonicalM11HandoffStatus.INTEGRITY_FAILURE,
                "canonical geometry realization is malformed",
                (),
            )
        if solid_count != 1:
            return (
                CanonicalM11HandoffStatus.NOT_ELIGIBLE,
                "multibody_target" if solid_count > 1 else "unsupported_geometry",
                (),
            )
        return None

    @staticmethod
    def _missing_authority(definition) -> tuple[str, ...]:
        missing: list[str] = []
        if not definition.regions:
            missing.append("regions")
        if not definition.load_cases or not any(case.active and case.loads for case in definition.load_cases):
            missing.append("loads")
        if not definition.boundary_conditions:
            missing.append("supports")
        assignment = definition.material_assignment
        snapshots = {snapshot.property_name for snapshot in assignment.property_snapshot}
        required = {
            StructuralMaterialPropertyName.ELASTIC_MODULUS,
            StructuralMaterialPropertyName.POISSON_RATIO,
        }
        if not required <= snapshots:
            missing.append("material_properties")
        rules = {
            rule.property_name: rule
            for rule in definition.material_authority_policy.allowed_authorities_by_property
        }
        if not required <= set(rules):
            missing.append("material_authority")
        else:
            by_name = {snapshot.property_name: snapshot for snapshot in assignment.property_snapshot}
            if any(by_name[name].authority not in rules[name].allowed_authorities for name in required):
                missing.append("material_authority")
        for criterion in definition.acceptance_criteria:
            policy_decision = evaluate_material_authority_policy(
                criterion,
                assignment,
                definition.material_authority_policy,
            )
            if policy_decision.status != "eligible":
                missing.append("material_authority")
                break
        return tuple(missing)

    @staticmethod
    def _assessment(request, status, reason, missing=()) -> CanonicalM11Handoff:
        missing = tuple(dict.fromkeys(missing))
        result = CanonicalM11HandoffResult(
            status=status,
            reason=reason,
            missing_authority=tuple(missing),
        )
        return CanonicalM11Handoff(
            project_id=request.project_id,
            promoted_revision=request.promoted_revision,
            promoted_state_hash=request.promoted_state_hash,
            canonical_mechanism_id=request.canonical_mechanism_id,
            canonical_mechanism_hash=request.canonical_mechanism_hash,
            target_scope=request.target_scope,
            target_instance_id=request.target_instance_id,
            analysis_category=request.analysis_category,
            intent_hash=request.intent.intent_hash,
            request=request,
            result=result,
            status=status,
            result_hash=result.result_hash,
        )


__all__ = [
    "CanonicalM11Handoff",
    "CanonicalM11HandoffIntegrityError",
    "CanonicalM11HandoffRequest",
    "CanonicalM11HandoffResult",
    "CanonicalM11HandoffService",
    "CanonicalM11HandoffStatus",
    "build_handoff_request",
]
