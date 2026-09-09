from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import AliasChoices, Field, StrictInt, StrictStr, field_validator, model_validator

from mechcad_harness.artifacts import ArtifactStore, ArtifactType, EngineeringArtifact
from mechcad_harness.changes.engine import AppliedChangeResult
from mechcad_harness.dependency.models import InvalidationRecord
from mechcad_harness.models import ChangeProposal
from mechcad_harness.state.hashing import canonical_json, state_hash

from .promotion_models import (
    CandidateCanonicalInstanceMapping,
    CandidateMultiJointPromotionApplicationResult,
    CandidateMultiJointPromotionRequest,
    CandidatePromotionCompilation,
    MultiJointPromotionDecisionInputReference,
    PrePromotionM10ScopeProjection,
    PromotionDecisionInputReference,
    PromotionModel,
    PromotionApplicationStatus,
    PromotableMechanismProjection,
    _hash as _promotion_model_hash,
    _require_hash,
    promotion_proposal_hash as semantic_promotion_proposal_hash,
)
from mechcad_harness.runs import Run, RunStatus


_DECISION_SCHEMA = "selected-candidate-decision-manifest@1"
_RESULT_SCHEMA = "candidate-promotion-result-manifest@1"
_MULTI_JOINT_DECISION_SCHEMA = "selected-multi-joint-candidate-decision-manifest@1"
_MULTI_JOINT_RESULT_SCHEMA = "multi-joint-promotion-result-manifest@1"


class PromotionManifestIntegrityError(ValueError):
    """A promotion manifest or one of its trusted source bindings is invalid."""


class PromotionManifestPostPublicationVerificationError(PromotionManifestIntegrityError):
    """Publication succeeded, but fresh verification failed afterward."""

    def __init__(self, message: str, *, published_artifact: EngineeringArtifact):
        super().__init__(message)
        self.published_artifact = published_artifact


def _manifest_hash(value: PromotionModel, identity_field: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(identity_field, None)
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def _hash_or_pending(value: str) -> str:
    return value if value == "pending" else _require_hash(value)


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty or whitespace")
    return value


def _require_equal(label: str, *values: Any) -> Any:
    if any(value != values[0] for value in values[1:]):
        raise PromotionManifestIntegrityError(f"multi-joint {label} binding mismatch")
    return values[0]


def _build_multi_joint_decision_input_reference(
    request: CandidateMultiJointPromotionRequest,
    readiness: Any,
) -> MultiJointPromotionDecisionInputReference:
    from .promotion import MultiJointPromotionReadiness

    if type(request) is not CandidateMultiJointPromotionRequest:
        raise PromotionManifestIntegrityError("multi-joint promotion request must be a typed request")
    if type(readiness) is not MultiJointPromotionReadiness:
        raise PromotionManifestIntegrityError("multi-joint promotion readiness must be typed")
    try:
        request = CandidateMultiJointPromotionRequest.model_validate(
            request.model_dump(mode="json")
        )
        readiness = MultiJointPromotionReadiness.model_validate(
            readiness.model_dump(mode="json")
        )
    except Exception as exc:
        raise PromotionManifestIntegrityError(
            f"multi-joint decision input integrity failure: {exc}"
        ) from exc

    source_binding_hash = _promotion_model_hash(request.candidate.source_binding)
    multi_request = request.multi_joint_request
    evaluation = request.multi_joint_evaluation
    selection = request.multi_joint_selection
    classification_identities = tuple(
        sorted(item.classification_hash for item in request.classifications)
    )
    mapping_identities = tuple(item.mapping_hash for item in readiness.mapping)

    _require_equal("request/readiness", request.request_hash, readiness.request_hash)
    _require_equal("project", request.project_id, readiness.project_id)
    _require_equal("source revision", request.source_revision, readiness.source_revision)
    _require_equal("source state", request.source_state_hash, readiness.source_state_hash)
    _require_equal("source binding", source_binding_hash, readiness.source_binding_hash)
    _require_equal("candidate", request.candidate.candidate_hash, readiness.candidate_hash)
    _require_equal(
        "synthesis request",
        request.synthesis_request.request_hash,
        request.candidate.synthesis_request_hash,
        readiness.synthesis_request_hash,
    )
    _require_equal(
        "synthesis policy",
        request.synthesis_policy.policy_hash,
        request.candidate.synthesis_policy_hash,
        readiness.synthesis_policy_hash,
    )
    _require_equal("M12-3 result", request.m12_3_result.result_hash, readiness.m12_3_result_hash)
    _require_equal(
        "multi-joint evaluation request",
        multi_request.request_hash,
        evaluation.candidate_request_hash,
        selection.candidate_request_hash,
    )
    _require_equal(
        "multi-joint evaluation",
        evaluation.evaluation_hash,
        readiness.multi_joint_evaluation_hash,
    )
    _require_equal(
        "multi-joint selection",
        selection.selection_hash,
        readiness.multi_joint_selection_hash,
    )
    _require_equal("scope", multi_request.scope_hash, readiness.scope_hash)
    _require_equal(
        "configuration set",
        multi_request.configuration_set_hash,
        evaluation.configuration_set_hash,
        selection.configuration_set_hash,
        readiness.configuration_set_hash,
    )
    _require_equal(
        "placement derivation",
        request.placement_derivations_hash,
        multi_request.placement_derivations_hash,
    )
    _require_equal(
        "physical pair classification set",
        multi_request.physical_pair_classification_set_hash,
        evaluation.physical_pair_classification_set_hash,
        selection.physical_pair_classification_set_hash,
    )
    _require_equal(
        "M10 v2 request",
        multi_request.m10_v2_request_hash,
        evaluation.m10_v2_request_hash,
        selection.m10_v2_request_hash,
    )
    _require_equal(
        "M10 v2 result",
        evaluation.m10_v2_result_hash,
        selection.m10_v2_result_hash,
    )
    _require_equal(
        "promotion policy",
        request.promotion_policy.policy_hash,
        readiness.promotion_policy_hash,
    )
    _require_equal(
        "target mechanism",
        request.canonical_target_mechanism_id,
        readiness.canonical_target_mechanism_id,
    )
    _require_equal("classification identities", classification_identities, readiness.classification_identities)
    _require_equal(
        "mapping identities",
        mapping_identities,
        tuple(item.mapping_hash for item in readiness.mapping),
    )

    return MultiJointPromotionDecisionInputReference(
        promotion_request_hash=request.request_hash,
        readiness_hash=readiness.readiness_hash,
        project_id=request.project_id,
        source_revision=request.source_revision,
        source_state_hash=request.source_state_hash,
        source_binding_hash=source_binding_hash,
        candidate_hash=request.candidate.candidate_hash,
        synthesis_request_hash=request.synthesis_request.request_hash,
        synthesis_policy_hash=request.synthesis_policy.policy_hash,
        m12_3_result_hash=request.m12_3_result.result_hash,
        multi_joint_evaluation_request_hash=multi_request.request_hash,
        multi_joint_evaluation_hash=evaluation.evaluation_hash,
        multi_joint_selection_hash=selection.selection_hash,
        scope_hash=multi_request.scope_hash,
        configuration_set_hash=multi_request.configuration_set_hash,
        placement_derivations_hash=request.placement_derivations_hash,
        physical_pair_classification_set_hash=multi_request.physical_pair_classification_set_hash,
        m10_v2_request_hash=multi_request.m10_v2_request_hash,
        m10_v2_result_hash=evaluation.m10_v2_result_hash,
        promotion_policy_hash=request.promotion_policy.policy_hash,
        canonical_target_mechanism_id=request.canonical_target_mechanism_id,
        mapping_identities=mapping_identities,
        classification_identities=classification_identities,
    )


def _path(value: str) -> str:
    value = _nonblank(value)
    if not value.startswith("/") or "//" in value or "~" in value:
        raise ValueError("manifest path must be a literal absolute path")
    if any(part in {"", ".", ".."} for part in value.split("/")[1:]):
        raise ValueError("manifest path must be a literal absolute path")
    return value


def _paths(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(_path(value) for value in values)
    if len(set(normalized)) != len(normalized):
        raise ValueError("manifest changed paths must be unique")
    return normalized


class SelectedCandidateDecisionManifest(PromotionModel):
    """Compact, pre-application provenance for one selected promotion decision."""

    schema_version: Literal[_DECISION_SCHEMA] = _DECISION_SCHEMA
    input_reference: PromotionDecisionInputReference = Field(
        validation_alias=AliasChoices("input_reference", "decision_input_reference")
    )
    pre_promotion_scope_projection: PrePromotionM10ScopeProjection = Field(
        validation_alias=AliasChoices(
            "pre_promotion_scope_projection", "pre_promotion_m10_scope_projection", "scope_projection"
        )
    )
    promotion_policy_hash: StrictStr
    base_revision: StrictInt = Field(gt=0)
    base_state_hash: StrictStr
    compilation_hash: StrictStr
    promotion_proposal_hash: StrictStr
    projection_hash: StrictStr
    projection: PromotableMechanismProjection = Field(
        validation_alias=AliasChoices("projection", "promotable_projection")
    )
    mapping: tuple[CandidateCanonicalInstanceMapping, ...] = Field(min_length=1)
    decision_hash: StrictStr = "pending"

    _validate_hashes = field_validator(
        "promotion_policy_hash",
        "base_state_hash",
        "compilation_hash",
        "promotion_proposal_hash",
        "projection_hash",
    )(_require_hash)
    _validate_decision_hash = field_validator("decision_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_manifest(self) -> "SelectedCandidateDecisionManifest":
        reference = self.input_reference
        if (reference.base_revision, reference.base_state_hash) != (
            self.base_revision,
            self.base_state_hash,
        ):
            raise ValueError("decision base binding mismatch")
        if reference.promotion_policy_hash != self.promotion_policy_hash:
            raise ValueError("decision promotion policy binding mismatch")
        if reference.canonical_target_mechanism_id != self.projection.canonical_target_mechanism_id:
            raise ValueError("decision target mechanism binding mismatch")
        if self.projection_hash != self.projection.projection_hash:
            raise ValueError("decision projection hash mismatch")

        mapping_hashes = tuple(item.mapping_hash for item in self.mapping)
        canonical_ids = tuple(item.canonical_instance_id for item in self.mapping)
        if mapping_hashes != reference.mapping_identities:
            raise ValueError("decision mapping identity mismatch")
        if canonical_ids != self.projection.canonical_instance_ids:
            raise ValueError("decision projection mapping mismatch")
        if len(set(item.candidate_instance_id for item in self.mapping)) != len(self.mapping):
            raise ValueError("decision candidate mapping IDs must be unique")
        expected = _manifest_hash(self, "decision_hash")
        if self.decision_hash == "pending":
            object.__setattr__(self, "decision_hash", expected)
        elif self.decision_hash != expected:
            raise ValueError("decision manifest hash mismatch")
        return self

    @property
    def project_id(self) -> str:
        return self.input_reference.project_id

    @property
    def promotable_projection(self) -> PromotableMechanismProjection:
        return self.projection


class SelectedMultiJointCandidateDecisionManifest(PromotionModel):
    schema_version: Literal[_MULTI_JOINT_DECISION_SCHEMA] = _MULTI_JOINT_DECISION_SCHEMA
    input_reference: MultiJointPromotionDecisionInputReference
    promotion_policy_hash: StrictStr
    base_revision: StrictInt = Field(gt=0)
    base_state_hash: StrictStr
    compilation_hash: StrictStr
    promotion_proposal_hash: StrictStr
    projection_hash: StrictStr
    projection: PromotableMechanismProjection
    mapping: tuple[CandidateCanonicalInstanceMapping, ...] = Field(min_length=1)
    decision_hash: StrictStr = "pending"

    _validate_hashes = field_validator(
        "promotion_policy_hash",
        "base_state_hash",
        "compilation_hash",
        "promotion_proposal_hash",
        "projection_hash",
    )(_require_hash)
    _validate_decision_hash = field_validator("decision_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_manifest(self) -> "SelectedMultiJointCandidateDecisionManifest":
        reference = self.input_reference
        if (reference.source_revision, reference.source_state_hash) != (
            self.base_revision,
            self.base_state_hash,
        ):
            raise ValueError("multi-joint decision base binding mismatch")
        if reference.promotion_policy_hash != self.promotion_policy_hash:
            raise ValueError("multi-joint decision promotion policy binding mismatch")
        if reference.canonical_target_mechanism_id != self.projection.canonical_target_mechanism_id:
            raise ValueError("multi-joint decision target mechanism binding mismatch")
        if self.projection_hash != self.projection.projection_hash:
            raise ValueError("multi-joint decision projection hash mismatch")

        candidate_ids = tuple(item.candidate_instance_id for item in self.mapping)
        canonical_ids = tuple(item.canonical_instance_id for item in self.mapping)
        mapping_hashes = tuple(item.mapping_hash for item in self.mapping)
        if candidate_ids != tuple(sorted(candidate_ids)):
            raise ValueError("multi-joint decision mapping must be canonically sorted")
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("multi-joint decision candidate mapping IDs must be unique")
        if len(set(canonical_ids)) != len(canonical_ids):
            raise ValueError("multi-joint decision canonical mapping IDs must be unique")
        if mapping_hashes != reference.mapping_identities:
            raise ValueError("multi-joint decision mapping identity mismatch")
        projection_ids = self.projection.canonical_instance_ids
        if (
            any(not identifier.strip() for identifier in canonical_ids)
            or any(not identifier.strip() for identifier in projection_ids)
            or len(canonical_ids) != len(projection_ids)
            or set(canonical_ids) != set(projection_ids)
        ):
            raise ValueError("multi-joint decision projection mapping universe mismatch")

        expected = _manifest_hash(self, "decision_hash")
        if self.decision_hash == "pending":
            object.__setattr__(self, "decision_hash", expected)
        elif self.decision_hash != expected:
            raise ValueError("multi-joint decision manifest hash mismatch")
        return self

    @property
    def project_id(self) -> str:
        return self.input_reference.project_id

    @property
    def promotable_projection(self) -> PromotableMechanismProjection:
        return self.projection


class MultiJointPromotionResultManifest(PromotionModel):
    schema_version: Literal[_MULTI_JOINT_RESULT_SCHEMA] = _MULTI_JOINT_RESULT_SCHEMA
    decision_artifact_id: StrictStr = Field(min_length=1)
    decision_artifact_hash: StrictStr
    decision_hash: StrictStr
    promotion_proposal_hash: StrictStr
    proposal_id: StrictStr = Field(min_length=1)
    changeset_id: StrictStr = Field(min_length=1)
    changed_paths: tuple[StrictStr, ...] = Field(min_length=1)
    canonical_target_mechanism_id: StrictStr = Field(min_length=1)
    mechanism_path: StrictStr
    base_revision: StrictInt = Field(gt=0)
    base_state_hash: StrictStr
    resulting_revision: StrictInt = Field(gt=0)
    resulting_state_hash: StrictStr
    result_hash: StrictStr = "pending"

    _validate_hashes = field_validator(
        "decision_artifact_hash",
        "decision_hash",
        "promotion_proposal_hash",
        "base_state_hash",
        "resulting_state_hash",
    )(_require_hash)
    _validate_result_hash = field_validator("result_hash")(_hash_or_pending)
    _validate_ids = field_validator(
        "decision_artifact_id", "proposal_id", "changeset_id", "canonical_target_mechanism_id"
    )(_nonblank)
    _validate_paths = field_validator("changed_paths")(_paths)
    _validate_mechanism_path = field_validator("mechanism_path")(_path)

    @model_validator(mode="after")
    def validate_manifest(self) -> "MultiJointPromotionResultManifest":
        expected_mechanism_path = f"/physical_mechanisms/{self.canonical_target_mechanism_id}"
        if self.mechanism_path != expected_mechanism_path:
            raise ValueError("multi-joint result mechanism path mismatch")
        if self.mechanism_path not in self.changed_paths:
            raise ValueError("multi-joint result mechanism path must be changed")
        if self.resulting_revision != self.base_revision + 1:
            raise ValueError("multi-joint result revision must be base revision plus one")
        expected = _manifest_hash(self, "result_hash")
        if self.result_hash == "pending":
            object.__setattr__(self, "result_hash", expected)
        elif self.result_hash != expected:
            raise ValueError("multi-joint result manifest hash mismatch")
        return self


class CandidatePromotionResultManifest(PromotionModel):
    """Compact, post-application provenance bound to a verified decision artifact."""

    schema_version: Literal[_RESULT_SCHEMA] = _RESULT_SCHEMA
    decision_artifact_id: StrictStr = Field(min_length=1)
    decision_artifact_hash: StrictStr
    promotion_proposal_hash: StrictStr
    proposal_id: StrictStr | None = None
    changeset_id: StrictStr | None = None
    application_id: StrictStr | None = None
    changed_paths: tuple[StrictStr, ...] = Field(min_length=1)
    mechanism_path: StrictStr
    resulting_revision: StrictInt = Field(gt=0)
    resulting_state_hash: StrictStr
    result_hash: StrictStr = "pending"

    _validate_hashes = field_validator(
        "decision_artifact_hash", "promotion_proposal_hash", "resulting_state_hash"
    )(_require_hash)
    _validate_result_hash = field_validator("result_hash")(_hash_or_pending)
    _validate_ids = field_validator("decision_artifact_id", "proposal_id", "changeset_id", "application_id")(
        lambda value: None if value is None else _nonblank(value)
    )
    _validate_path_values = field_validator("changed_paths")(_paths)
    _validate_mechanism_path = field_validator("mechanism_path")(_path)

    @model_validator(mode="after")
    def validate_manifest(self) -> "CandidatePromotionResultManifest":
        if self.mechanism_path not in self.changed_paths:
            raise ValueError("result mechanism path must be one of the changed paths")
        expected = _manifest_hash(self, "result_hash")
        if self.result_hash == "pending":
            object.__setattr__(self, "result_hash", expected)
        elif self.result_hash != expected:
            raise ValueError("result manifest hash mismatch")
        return self


def _artifact_id(prefix: str, identity: str) -> str:
    return f"{prefix}-{identity[7:31]}"


def _content(manifest: PromotionModel) -> bytes:
    return canonical_json(manifest.model_dump(mode="json")) + b"\n"


def decision_manifest_hash(manifest: SelectedCandidateDecisionManifest) -> str:
    return _manifest_hash(manifest, "decision_hash")


def multi_joint_decision_manifest_hash(
    manifest: SelectedMultiJointCandidateDecisionManifest,
) -> str:
    return _manifest_hash(manifest, "decision_hash")


def result_manifest_hash(manifest: CandidatePromotionResultManifest) -> str:
    return _manifest_hash(manifest, "result_hash")


def multi_joint_result_manifest_hash(manifest: MultiJointPromotionResultManifest) -> str:
    return _manifest_hash(manifest, "result_hash")


def _load_json(store: ArtifactStore, artifact_id: str) -> tuple[EngineeringArtifact, bytes, dict[str, Any]]:
    try:
        verified = store.read_verified_strict(artifact_id, expected_type=ArtifactType.JSON)
        if verified is None:
            raise PromotionManifestIntegrityError("promotion manifest artifact is missing")
        artifact, content = verified
        payload = json.loads(content)
        if not isinstance(payload, dict):
            raise PromotionManifestIntegrityError("promotion manifest payload is not an object")
        return artifact, content, payload
    except PromotionManifestIntegrityError:
        raise
    except Exception as exc:
        raise PromotionManifestIntegrityError(f"promotion manifest artifact is invalid: {exc}") from exc


def _verify_selected_sources(store: ArtifactStore, manifest: SelectedCandidateDecisionManifest) -> None:
    source_references: dict[str, Any] = {}
    for specification in manifest.projection.component_specifications:
        source = specification.geometry_source
        if source is None:
            continue
        first_reference = source_references.get(source.artifact_id)
        if first_reference is not None:
            if source != first_reference:
                raise PromotionManifestIntegrityError(
                    "selected geometry source reference conflict"
                )
            continue
        source_references[source.artifact_id] = source
        try:
            verified = store.read_verified_in_project(
                source.artifact_id,
                expected_type=ArtifactType.STEP,
                expected_hash=source.artifact_hash,
            )
        except Exception as exc:
            raise PromotionManifestIntegrityError(
                f"selected geometry source verification failed: {exc}"
            ) from exc
        if verified is None:
            raise PromotionManifestIntegrityError("selected geometry source is missing or tampered")
        artifact, _ = verified
        if (
            artifact.project_id != manifest.project_id
            or artifact.artifact_type is not ArtifactType.STEP
            or artifact.sha256 != source.artifact_hash
            or artifact.bound_revision != manifest.base_revision
            or artifact.bound_state_hash != manifest.base_state_hash
        ):
            raise PromotionManifestIntegrityError("selected geometry source binding mismatch")


def _verify_multi_joint_selected_sources(
    store: ArtifactStore, manifest: SelectedMultiJointCandidateDecisionManifest
) -> None:
    _verify_selected_sources(store, manifest)


class PromotionManifestService:
    """Publish and strictly resolve both promotion manifests in one run scope."""

    def publish_multi_joint_decision(
        self,
        store: ArtifactStore,
        *,
        run: Run,
        request: CandidateMultiJointPromotionRequest,
        readiness: Any,
        compilation: CandidatePromotionCompilation,
    ) -> EngineeringArtifact:
        from .promotion import MultiJointPromotionReadiness

        if type(run) is not Run:
            raise PromotionManifestIntegrityError("multi-joint decision publication requires a typed Run")
        if type(request) is not CandidateMultiJointPromotionRequest:
            raise PromotionManifestIntegrityError(
                "multi-joint decision publication requires a typed request"
            )
        if type(readiness) is not MultiJointPromotionReadiness:
            raise PromotionManifestIntegrityError(
                "multi-joint decision publication requires typed readiness"
            )
        if type(compilation) is not CandidatePromotionCompilation:
            raise PromotionManifestIntegrityError(
                "multi-joint decision publication requires a typed compilation"
            )
        try:
            request = CandidateMultiJointPromotionRequest.model_validate(
                request.model_dump(mode="json")
            )
            readiness = MultiJointPromotionReadiness.model_validate(
                readiness.model_dump(mode="json")
            )
            compilation = CandidatePromotionCompilation.model_validate(
                compilation.model_dump(mode="json")
            )
            compilation.validated_proposal()
        except Exception as exc:
            raise PromotionManifestIntegrityError(
                f"multi-joint decision publication typed input integrity failure: {exc}"
            ) from exc

        if not _nonblank(run.run_id):
            raise PromotionManifestIntegrityError("multi-joint decision run ID must not be empty")
        if run.status is not RunStatus.CREATED:
            raise PromotionManifestIntegrityError("multi-joint decision run must be CREATED")
        if (
            run.project_id != request.project_id
            or request.project_id != readiness.project_id
            or store.project_id != run.project_id
            or store.run_id != run.run_id
        ):
            raise PromotionManifestIntegrityError("multi-joint decision run or store scope mismatch")
        if (
            run.initial_revision != run.active_revision
            or run.initial_revision != request.source_revision
            or request.source_revision != readiness.source_revision
            or compilation.proposal.base_revision != request.source_revision
            or run.initial_state_hash != run.active_state_hash
            or run.initial_state_hash != request.source_state_hash
            or request.source_state_hash != readiness.source_state_hash
            or compilation.proposal.base_state_hash != request.source_state_hash
        ):
            raise PromotionManifestIntegrityError("multi-joint decision run or base binding mismatch")

        try:
            reference = _build_multi_joint_decision_input_reference(request, readiness)
            manifest = SelectedMultiJointCandidateDecisionManifest(
                input_reference=reference,
                promotion_policy_hash=request.promotion_policy.policy_hash,
                base_revision=compilation.proposal.base_revision,
                base_state_hash=compilation.proposal.base_state_hash,
                compilation_hash=compilation.compilation_hash,
                promotion_proposal_hash=compilation.promotion_proposal_hash,
                projection_hash=compilation.projection.projection_hash,
                projection=compilation.projection,
                mapping=compilation.mapping,
            )
        except Exception as exc:
            raise PromotionManifestIntegrityError(
                f"multi-joint decision manifest is invalid: {exc}"
            ) from exc

        self._check_store_project(store, manifest.project_id)
        _verify_multi_joint_selected_sources(store, manifest)
        content = _content(manifest)
        artifact = store.publish(
            _artifact_id("MULTI-JOINT-PROMOTION-DECISION", manifest.decision_hash),
            ArtifactType.JSON,
            "multi_joint_decision.json",
            content,
            "mechcad-promotion-manifest",
            "1",
            manifest.base_revision,
            manifest.base_state_hash,
            input_hash=manifest.decision_hash,
        )
        self.resolve_multi_joint_decision(store, artifact.artifact_id)
        return artifact

    def publish_decision(
        self,
        store: ArtifactStore,
        *,
        input_reference: PromotionDecisionInputReference | None = None,
        pre_promotion_scope_projection: PrePromotionM10ScopeProjection | None = None,
        promotion_policy_hash: str | None = None,
        base_revision: int | None = None,
        base_state_hash: str | None = None,
        compilation_hash: str | None = None,
        promotion_proposal_hash: str | None = None,
        projection_hash: str | None = None,
        projection: PromotableMechanismProjection | None = None,
        mapping: tuple[CandidateCanonicalInstanceMapping, ...] | list[CandidateCanonicalInstanceMapping] | None = None,
        manifest: SelectedCandidateDecisionManifest | None = None,
        readiness: Any | None = None,
        compilation: Any | None = None,
        request: Any | None = None,
        **aliases: Any,
    ) -> EngineeringArtifact:
        if manifest is None:
            if readiness is not None:
                base_revision = base_revision if base_revision is not None else readiness.source_revision
                base_state_hash = base_state_hash or readiness.source_state_hash
                promotion_policy_hash = promotion_policy_hash or readiness.promotion_policy_hash
                mapping = mapping or readiness.mapping
                if input_reference is None and request is not None:
                    comparison = getattr(request, "comparison", None)
                    comparison_request = getattr(request, "comparison_request", None)
                    input_reference = PromotionDecisionInputReference(
                        promotion_request_hash=readiness.request_hash,
                        project_id=readiness.project_id,
                        base_revision=readiness.source_revision,
                        base_state_hash=readiness.source_state_hash,
                        candidate_hash=readiness.candidate_hash,
                        synthesis_request_hash=request.synthesis_request.request_hash,
                        synthesis_policy_hash=request.synthesis_policy.policy_hash,
                        m12_3_result_hash=readiness.m12_3_result_hash,
                        evaluation_hash=readiness.evaluation_hash,
                        selection_hash=readiness.selection_hash,
                        comparison_used=readiness.comparison_used,
                        comparison_result_hash=(
                            None if comparison is None else comparison.result_hash
                        ),
                        comparison_request_hash=(
                            None if comparison_request is None else comparison_request.request_hash
                        ),
                        promotion_policy_hash=readiness.promotion_policy_hash,
                        canonical_target_mechanism_id=readiness.canonical_target_mechanism_id,
                        m11_target_intent=getattr(request, "m11_target_intent", None),
                        mapping_identities=tuple(item.mapping_hash for item in readiness.mapping),
                        classification_identities=readiness.classification_identities,
                    )
            if compilation is not None:
                compilation_hash = compilation_hash or compilation.compilation_hash
                promotion_proposal_hash = promotion_proposal_hash or compilation.promotion_proposal_hash
                projection_hash = projection_hash or compilation.projection.projection_hash
                projection = projection or compilation.projection
                mapping = mapping or compilation.mapping
            input_reference = input_reference or aliases.get("decision_input_reference")
            pre_promotion_scope_projection = pre_promotion_scope_projection or aliases.get(
                "pre_promotion_m10_scope_projection", aliases.get("scope_projection")
            )
            projection = projection or aliases.get("promotable_projection")
            values = dict(
                input_reference=input_reference,
                pre_promotion_scope_projection=pre_promotion_scope_projection,
                promotion_policy_hash=promotion_policy_hash,
                base_revision=base_revision,
                base_state_hash=base_state_hash,
                compilation_hash=compilation_hash,
                promotion_proposal_hash=promotion_proposal_hash,
                projection_hash=projection_hash,
                projection=projection,
                mapping=mapping,
            )
            try:
                manifest = SelectedCandidateDecisionManifest.model_validate(values)
            except Exception as exc:
                raise PromotionManifestIntegrityError(f"decision manifest is invalid: {exc}") from exc
        else:
            try:
                manifest = SelectedCandidateDecisionManifest.model_validate(
                    manifest.model_dump(mode="json")
                )
            except Exception as exc:
                raise PromotionManifestIntegrityError(f"decision manifest is invalid: {exc}") from exc
        self._check_store_project(store, manifest.project_id)
        _verify_selected_sources(store, manifest)
        content = _content(manifest)
        artifact = store.publish(
            _artifact_id("PROMOTION-DECISION", manifest.decision_hash),
            ArtifactType.JSON,
            "decision.json",
            content,
            "mechcad-promotion-manifest",
            "1",
            manifest.base_revision,
            manifest.base_state_hash,
            input_hash=manifest.decision_hash,
        )
        self.resolve_decision(store, artifact.artifact_id)
        return artifact

    def resolve_decision(
        self, store: ArtifactStore, artifact_id: str
    ) -> SelectedCandidateDecisionManifest:
        artifact, content, payload = _load_json(store, artifact_id)
        try:
            manifest = SelectedCandidateDecisionManifest.model_validate(payload)
        except Exception as exc:
            raise PromotionManifestIntegrityError(f"decision manifest schema is invalid: {exc}") from exc
        self._check_store_project(store, manifest.project_id)
        if (
            artifact.artifact_id != _artifact_id("PROMOTION-DECISION", manifest.decision_hash)
            or artifact.input_hash != manifest.decision_hash
            or artifact.bound_revision != manifest.base_revision
            or artifact.bound_state_hash != manifest.base_state_hash
            or content != _content(manifest)
        ):
            raise PromotionManifestIntegrityError("decision manifest artifact binding mismatch")
        _verify_selected_sources(store, manifest)
        return manifest

    def resolve_multi_joint_decision(
        self, store: ArtifactStore, artifact_id: str
    ) -> SelectedMultiJointCandidateDecisionManifest:
        artifact, content, payload = _load_json(store, artifact_id)
        try:
            manifest = SelectedMultiJointCandidateDecisionManifest.model_validate(payload)
        except Exception as exc:
            raise PromotionManifestIntegrityError(
                f"multi-joint decision manifest schema is invalid: {exc}"
            ) from exc
        self._check_store_project(store, manifest.project_id)
        if (
            not _nonblank(artifact.run_id)
            or artifact.run_id != store.run_id
            or artifact.artifact_id
            != _artifact_id("MULTI-JOINT-PROMOTION-DECISION", manifest.decision_hash)
            or artifact.artifact_type is not ArtifactType.JSON
            or artifact.producer_tool_name != "mechcad-promotion-manifest"
            or artifact.producer_tool_version != "1"
            or artifact.relative_path.rsplit("/", 1)[-1] != "multi_joint_decision.json"
            or artifact.input_hash != manifest.decision_hash
            or artifact.bound_revision != manifest.base_revision
            or artifact.bound_state_hash != manifest.base_state_hash
            or content != _content(manifest)
        ):
            raise PromotionManifestIntegrityError(
                "multi-joint decision manifest artifact binding mismatch"
            )
        _verify_multi_joint_selected_sources(store, manifest)
        return manifest

    def publish_multi_joint_result(
        self,
        store: ArtifactStore,
        *,
        decision_artifact: EngineeringArtifact,
        compilation: CandidatePromotionCompilation,
        proposal: ChangeProposal,
        applied: AppliedChangeResult,
        invalidation: InvalidationRecord,
        final_run: Run,
    ) -> EngineeringArtifact:
        if type(decision_artifact) is not EngineeringArtifact:
            raise PromotionManifestIntegrityError(
                "multi-joint result publication requires a typed decision artifact"
            )
        if type(compilation) is not CandidatePromotionCompilation:
            raise PromotionManifestIntegrityError(
                "multi-joint result publication requires a typed compilation"
            )
        if type(proposal) is not ChangeProposal:
            raise PromotionManifestIntegrityError(
                "multi-joint result publication requires a typed proposal"
            )
        if type(applied) is not AppliedChangeResult:
            raise PromotionManifestIntegrityError(
                "multi-joint result publication requires an AppliedChangeResult"
            )
        if type(invalidation) is not InvalidationRecord:
            raise PromotionManifestIntegrityError(
                "multi-joint result publication requires an InvalidationRecord"
            )
        if type(final_run) is not Run:
            raise PromotionManifestIntegrityError(
                "multi-joint result publication requires a typed final Run"
            )
        try:
            compilation = CandidatePromotionCompilation.model_validate(
                compilation.model_dump(mode="json")
            )
            proposal = ChangeProposal.model_validate(proposal.model_dump(mode="json"))
            invalidation = InvalidationRecord.model_validate(
                invalidation.model_dump(mode="json")
            )
            final_run = Run.model_validate(final_run.model_dump(mode="json"))
            compilation.validated_proposal()
        except Exception as exc:
            raise PromotionManifestIntegrityError(
                f"multi-joint result publication typed input integrity failure: {exc}"
            ) from exc

        self._check_store_project(store, decision_artifact.project_id)
        try:
            decision = self.resolve_multi_joint_decision(
                store, decision_artifact.artifact_id
            )
            verified_decision = store.read_verified_strict(
                decision_artifact.artifact_id, expected_type=ArtifactType.JSON
            )
            if verified_decision is None or verified_decision[0] != decision_artifact:
                raise PromotionManifestIntegrityError(
                    "multi-joint decision artifact is not the trusted stored artifact"
                )
        except PromotionManifestIntegrityError:
            raise
        except Exception as exc:
            raise PromotionManifestIntegrityError(
                f"multi-joint decision resolution failed: {exc}"
            ) from exc

        expected_paths = tuple(
            dict.fromkeys(operation.path for operation in proposal.operations)
        )
        try:
            snapshot = applied.snapshot
            applied_revision = snapshot.revision
            applied_state_hash = _require_hash(snapshot.state_hash)
        except Exception as exc:
            raise PromotionManifestIntegrityError(
                f"multi-joint applied snapshot is invalid: {exc}"
            ) from exc
        if (
            proposal != compilation.proposal
            or compilation.promotion_proposal_hash != decision.promotion_proposal_hash
            or compilation.projection != decision.projection
            or compilation.mapping != decision.mapping
            or proposal.base_revision != decision.base_revision
            or proposal.base_state_hash != decision.base_state_hash
            or applied.changeset_id != invalidation.changeset_id
            or not invalidation.changeset_id
            or tuple(applied.changed_paths) != expected_paths
            or tuple(invalidation.changed_paths) != expected_paths
            or invalidation.project_id != store.project_id
            or invalidation.revision != applied_revision
            or invalidation.parent_revision != decision.base_revision
            or applied_revision != decision.base_revision + 1
            or final_run.project_id != store.project_id
            or final_run.run_id != store.run_id
            or final_run.status is not RunStatus.CREATED
            or final_run.initial_revision != decision.base_revision
            or final_run.initial_state_hash != decision.base_state_hash
            or final_run.active_revision != applied_revision
            or final_run.active_state_hash != applied_state_hash
            or decision_artifact.run_id != final_run.run_id
        ):
            raise PromotionManifestIntegrityError(
                "multi-joint result decision or lifecycle binding mismatch"
            )

        target_id = decision.projection.canonical_target_mechanism_id
        try:
            manifest = MultiJointPromotionResultManifest(
                decision_artifact_id=decision_artifact.artifact_id,
                decision_artifact_hash=decision_artifact.sha256,
                decision_hash=decision.decision_hash,
                promotion_proposal_hash=compilation.promotion_proposal_hash,
                proposal_id=proposal.id,
                changeset_id=invalidation.changeset_id,
                changed_paths=expected_paths,
                canonical_target_mechanism_id=target_id,
                mechanism_path=f"/physical_mechanisms/{target_id}",
                base_revision=decision.base_revision,
                base_state_hash=decision.base_state_hash,
                resulting_revision=applied_revision,
                resulting_state_hash=applied_state_hash,
            )
        except Exception as exc:
            raise PromotionManifestIntegrityError(
                f"multi-joint result manifest is invalid: {exc}"
            ) from exc
        content = _content(manifest)
        artifact = store.publish(
            _artifact_id("MULTI-JOINT-PROMOTION-RESULT", manifest.result_hash),
            ArtifactType.JSON,
            "multi_joint_result.json",
            content,
            "mechcad-promotion-manifest",
            "1",
            manifest.resulting_revision,
            manifest.resulting_state_hash,
            input_hash=decision_artifact.sha256,
        )
        try:
            self.resolve_multi_joint_result(store, artifact.artifact_id)
        except Exception as exc:
            raise PromotionManifestPostPublicationVerificationError(
                str(exc), published_artifact=artifact
            ) from exc
        return artifact

    def publish_result(
        self,
        store: ArtifactStore,
        *,
        decision_artifact_id: str | None = None,
        decision_artifact_hash: str | None = None,
        promotion_proposal_hash: str | None = None,
        proposal_id: str | None = None,
        changeset_id: str | None = None,
        application_id: str | None = None,
        changed_paths: tuple[str, ...] | list[str] | None = None,
        mechanism_path: str | None = None,
        resulting_revision: int | None = None,
        resulting_state_hash: str | None = None,
        decision_artifact: EngineeringArtifact | None = None,
        manifest: CandidatePromotionResultManifest | None = None,
        compilation: Any | None = None,
        proposal: Any | None = None,
        applied: Any | None = None,
        **aliases: Any,
    ) -> EngineeringArtifact:
        if compilation is not None:
            compilation_proposal_hash = compilation.promotion_proposal_hash
            compilation_proposal_id = compilation.proposal.id
            compilation_mechanism_path = (
                f"/physical_mechanisms/{compilation.projection.canonical_target_mechanism_id}"
            )
            self._require_matching_input("proposal ID", proposal_id, compilation_proposal_id)
            self._require_matching_input(
                "promotion proposal hash", promotion_proposal_hash, compilation_proposal_hash
            )
            self._require_matching_input("mechanism path", mechanism_path, compilation_mechanism_path)
            proposal_id = proposal_id or compilation_proposal_id
            promotion_proposal_hash = promotion_proposal_hash or compilation_proposal_hash
            mechanism_path = mechanism_path or compilation_mechanism_path
        if proposal is not None:
            proposal_proposal_hash = semantic_promotion_proposal_hash(
                proposal.base_revision,
                proposal.base_state_hash,
                tuple(proposal.operations),
            )
            self._require_matching_input("proposal ID", proposal_id, proposal.id)
            self._require_matching_input(
                "promotion proposal hash", promotion_proposal_hash, proposal_proposal_hash
            )
            if compilation is not None:
                self._require_matching_input("proposal ID", proposal.id, compilation.proposal.id)
            proposal_id = proposal_id or proposal.id
            promotion_proposal_hash = promotion_proposal_hash or proposal_proposal_hash
        if applied is not None:
            applied_changed_paths = tuple(applied.changed_paths)
            self._require_matching_input("ChangeSet ID", changeset_id, applied.changeset_id)
            self._require_matching_input(
                "changed paths",
                None if changed_paths is None else tuple(changed_paths),
                applied_changed_paths,
            )
            self._require_matching_input(
                "resulting revision", resulting_revision, applied.snapshot.revision
            )
            self._require_matching_input(
                "resulting state hash", resulting_state_hash, applied.snapshot.state_hash
            )
            changeset_id = changeset_id or applied.changeset_id
            changed_paths = changed_paths or applied_changed_paths
            resulting_revision = resulting_revision or applied.snapshot.revision
            resulting_state_hash = resulting_state_hash or applied.snapshot.state_hash
        if decision_artifact is not None:
            self._require_matching_input(
                "decision artifact ID", decision_artifact_id, decision_artifact.artifact_id
            )
            self._require_matching_input(
                "decision artifact hash", decision_artifact_hash, decision_artifact.sha256
            )
            decision_artifact_id = decision_artifact.artifact_id
            decision_artifact_hash = decision_artifact.sha256
        if manifest is None:
            if decision_artifact_id is None:
                decision_artifact_id = aliases.get("decision_id")
            if changed_paths is None:
                changed_paths = aliases.get("paths")
            try:
                decision = self.resolve_decision(store, decision_artifact_id)
                if decision_artifact_hash is None:
                    verified = store.read_verified_strict(
                        decision_artifact_id, expected_type=ArtifactType.JSON
                    )
                    if verified is None:
                        raise PromotionManifestIntegrityError("decision artifact is missing")
                    decision_artifact_hash = verified[0].sha256
                promotion_proposal_hash = promotion_proposal_hash or decision.promotion_proposal_hash
                mechanism_path = mechanism_path or f"/physical_mechanisms/{decision.projection.canonical_target_mechanism_id}"
                manifest = CandidatePromotionResultManifest(
                    decision_artifact_id=decision_artifact_id,
                    decision_artifact_hash=decision_artifact_hash,
                    promotion_proposal_hash=promotion_proposal_hash,
                    proposal_id=proposal_id,
                    changeset_id=changeset_id,
                    application_id=application_id,
                    changed_paths=changed_paths,
                    mechanism_path=mechanism_path,
                    resulting_revision=resulting_revision,
                    resulting_state_hash=resulting_state_hash,
                )
            except PromotionManifestIntegrityError:
                raise
            except Exception as exc:
                raise PromotionManifestIntegrityError(f"result manifest is invalid: {exc}") from exc
        else:
            try:
                manifest = CandidatePromotionResultManifest.model_validate(
                    manifest.model_dump(mode="json")
                )
            except Exception as exc:
                raise PromotionManifestIntegrityError(f"result manifest is invalid: {exc}") from exc
            for label, supplied, expected in (
                ("decision artifact ID", decision_artifact_id, manifest.decision_artifact_id),
                ("decision artifact hash", decision_artifact_hash, manifest.decision_artifact_hash),
                ("promotion proposal hash", promotion_proposal_hash, manifest.promotion_proposal_hash),
                ("proposal ID", proposal_id, manifest.proposal_id),
                ("ChangeSet ID", changeset_id, manifest.changeset_id),
                (
                    "changed paths",
                    None if changed_paths is None else tuple(changed_paths),
                    manifest.changed_paths,
                ),
                ("mechanism path", mechanism_path, manifest.mechanism_path),
                ("resulting revision", resulting_revision, manifest.resulting_revision),
                ("resulting state hash", resulting_state_hash, manifest.resulting_state_hash),
            ):
                self._require_matching_input(label, supplied, expected)
            decision = self.resolve_decision(store, manifest.decision_artifact_id)
            decision_artifact_hash = manifest.decision_artifact_hash

        decision = self.resolve_decision(store, manifest.decision_artifact_id)
        if (
            manifest.decision_artifact_hash
            != self._artifact_hash(store, manifest.decision_artifact_id)
            or manifest.promotion_proposal_hash != decision.promotion_proposal_hash
            or manifest.resulting_revision != decision.base_revision + 1
            or manifest.mechanism_path
            != f"/physical_mechanisms/{decision.projection.canonical_target_mechanism_id}"
        ):
            raise PromotionManifestIntegrityError("result manifest decision binding mismatch")
        content = _content(manifest)
        artifact = store.publish(
            _artifact_id("PROMOTION-RESULT", manifest.result_hash),
            ArtifactType.JSON,
            "result.json",
            content,
            "mechcad-promotion-manifest",
            "1",
            manifest.resulting_revision,
            manifest.resulting_state_hash,
            input_hash=manifest.decision_artifact_hash,
        )
        try:
            self.resolve_result(store, artifact.artifact_id)
        except Exception as exc:
            raise PromotionManifestPostPublicationVerificationError(
                str(exc), published_artifact=artifact
            ) from exc
        return artifact

    @staticmethod
    def _require_matching_input(label: str, supplied: Any, expected: Any) -> None:
        if supplied is not None and supplied != expected:
            raise PromotionManifestIntegrityError(f"{label} does not match supplied provenance")

    def resolve_result(
        self, store: ArtifactStore, artifact_id: str
    ) -> CandidatePromotionResultManifest:
        artifact, content, payload = _load_json(store, artifact_id)
        try:
            manifest = CandidatePromotionResultManifest.model_validate(payload)
        except Exception as exc:
            raise PromotionManifestIntegrityError(f"result manifest schema is invalid: {exc}") from exc
        decision = self.resolve_decision(store, manifest.decision_artifact_id)
        if (
            artifact.artifact_id != _artifact_id("PROMOTION-RESULT", manifest.result_hash)
            or artifact.input_hash != manifest.decision_artifact_hash
            or artifact.bound_revision != manifest.resulting_revision
            or artifact.bound_state_hash != manifest.resulting_state_hash
            or content != _content(manifest)
            or manifest.decision_artifact_hash != self._artifact_hash(store, manifest.decision_artifact_id)
            or manifest.promotion_proposal_hash != decision.promotion_proposal_hash
            or manifest.resulting_revision != decision.base_revision + 1
            or manifest.mechanism_path
            != f"/physical_mechanisms/{decision.projection.canonical_target_mechanism_id}"
        ):
            raise PromotionManifestIntegrityError("result manifest artifact binding mismatch")
        return manifest

    def resolve_multi_joint_result(
        self, store: ArtifactStore, artifact_id: str
    ) -> MultiJointPromotionResultManifest:
        artifact, content, payload = _load_json(store, artifact_id)
        try:
            manifest = MultiJointPromotionResultManifest.model_validate(payload)
        except Exception as exc:
            raise PromotionManifestIntegrityError(
                f"multi-joint result manifest schema is invalid: {exc}"
            ) from exc
        try:
            decision = self.resolve_multi_joint_decision(
                store, manifest.decision_artifact_id
            )
            decision_artifact = store.read_verified_strict(
                manifest.decision_artifact_id, expected_type=ArtifactType.JSON
            )
            if decision_artifact is None:
                raise PromotionManifestIntegrityError("multi-joint decision artifact is missing")
            decision_artifact_model = decision_artifact[0]
            self._check_store_project(store, decision.project_id)
        except PromotionManifestIntegrityError:
            raise
        except Exception as exc:
            raise PromotionManifestIntegrityError(
                f"multi-joint result decision resolution failed: {exc}"
            ) from exc
        if (
            not _nonblank(artifact.run_id)
            or artifact.run_id != store.run_id
            or artifact.run_id != decision_artifact_model.run_id
            or artifact.artifact_id
            != _artifact_id("MULTI-JOINT-PROMOTION-RESULT", manifest.result_hash)
            or artifact.artifact_type is not ArtifactType.JSON
            or artifact.producer_tool_name != "mechcad-promotion-manifest"
            or artifact.producer_tool_version != "1"
            or artifact.relative_path.rsplit("/", 1)[-1] != "multi_joint_result.json"
            or artifact.input_hash != manifest.decision_artifact_hash
            or artifact.bound_revision != manifest.resulting_revision
            or artifact.bound_state_hash != manifest.resulting_state_hash
            or manifest.decision_artifact_hash != decision_artifact_model.sha256
            or manifest.decision_hash != decision.decision_hash
            or manifest.promotion_proposal_hash != decision.promotion_proposal_hash
            or manifest.canonical_target_mechanism_id
            != decision.projection.canonical_target_mechanism_id
            or manifest.base_revision != decision.base_revision
            or manifest.base_state_hash != decision.base_state_hash
            or content != _content(manifest)
        ):
            raise PromotionManifestIntegrityError(
                "multi-joint result manifest artifact binding mismatch"
            )
        return manifest

    def _artifact_hash(self, store: ArtifactStore, artifact_id: str) -> str:
        verified = store.read_verified_strict(artifact_id, expected_type=ArtifactType.JSON)
        if verified is None:
            raise PromotionManifestIntegrityError("referenced decision artifact is missing")
        return verified[0].sha256

    @staticmethod
    def _check_store_project(store: ArtifactStore, project_id: str) -> None:
        if not isinstance(store, ArtifactStore):
            raise PromotionManifestIntegrityError("promotion manifests require an ArtifactStore")
        if store.project_id != project_id:
            raise PromotionManifestIntegrityError("manifest project does not match ArtifactStore scope")


def verify_multi_joint_promotion_decision(
    manifest: SelectedMultiJointCandidateDecisionManifest,
    *,
    request: CandidateMultiJointPromotionRequest,
    readiness: Any,
    compilation: CandidatePromotionCompilation,
) -> None:
    from .promotion import MultiJointPromotionReadiness

    if type(manifest) is not SelectedMultiJointCandidateDecisionManifest:
        raise PromotionManifestIntegrityError(
            "multi-joint decision verification requires a typed manifest"
        )
    if type(request) is not CandidateMultiJointPromotionRequest:
        raise PromotionManifestIntegrityError(
            "multi-joint decision verification requires a typed request"
        )
    if type(readiness) is not MultiJointPromotionReadiness:
        raise PromotionManifestIntegrityError(
            "multi-joint decision verification requires typed readiness"
        )
    if type(compilation) is not CandidatePromotionCompilation:
        raise PromotionManifestIntegrityError(
            "multi-joint decision verification requires a typed compilation"
        )
    try:
        manifest = SelectedMultiJointCandidateDecisionManifest.model_validate(
            manifest.model_dump(mode="json")
        )
        request = CandidateMultiJointPromotionRequest.model_validate(
            request.model_dump(mode="json")
        )
        readiness = MultiJointPromotionReadiness.model_validate(
            readiness.model_dump(mode="json")
        )
        compilation = CandidatePromotionCompilation.model_validate(
            compilation.model_dump(mode="json")
        )
        compilation.validated_proposal()
        reference = _build_multi_joint_decision_input_reference(request, readiness)
        expected = SelectedMultiJointCandidateDecisionManifest(
            input_reference=reference,
            promotion_policy_hash=request.promotion_policy.policy_hash,
            base_revision=compilation.proposal.base_revision,
            base_state_hash=compilation.proposal.base_state_hash,
            compilation_hash=compilation.compilation_hash,
            promotion_proposal_hash=compilation.promotion_proposal_hash,
            projection_hash=compilation.projection.projection_hash,
            projection=compilation.projection,
            mapping=compilation.mapping,
        )
    except Exception as exc:
        raise PromotionManifestIntegrityError(
            f"multi-joint decision verification integrity failure: {exc}"
        ) from exc
    if manifest.mapping != compilation.mapping:
        raise PromotionManifestIntegrityError(
            "multi-joint decision mapping does not match the original compilation"
        )

    mismatches = []
    reference_bindings = (
        ("project", "project_id"),
        ("source revision", "source_revision"),
        ("source state", "source_state_hash"),
        ("source binding", "source_binding_hash"),
        ("candidate", "candidate_hash"),
        ("synthesis request", "synthesis_request_hash"),
        ("synthesis policy", "synthesis_policy_hash"),
        ("M12-3 result", "m12_3_result_hash"),
        ("multi-joint evaluation request", "multi_joint_evaluation_request_hash"),
        ("multi-joint evaluation", "multi_joint_evaluation_hash"),
        ("multi-joint selection", "multi_joint_selection_hash"),
        ("scope", "scope_hash"),
        ("configuration set", "configuration_set_hash"),
        ("placement derivation", "placement_derivations_hash"),
        ("physical pair classification set", "physical_pair_classification_set_hash"),
        ("M10 v2 request", "m10_v2_request_hash"),
        ("M10 v2 result", "m10_v2_result_hash"),
        ("promotion policy", "promotion_policy_hash"),
        ("target mechanism", "canonical_target_mechanism_id"),
        ("classification identities", "classification_identities"),
        ("mapping identities", "mapping_identities"),
        ("promotion request", "promotion_request_hash"),
        ("readiness", "readiness_hash"),
    )
    mismatches.extend(
        label
        for label, field in reference_bindings
        if getattr(manifest.input_reference, field) != getattr(reference, field)
    )

    manifest_bindings = (
        ("promotion policy", "promotion_policy_hash"),
        ("base revision", "base_revision"),
        ("base state", "base_state_hash"),
        ("compilation", "compilation_hash"),
        ("promotion proposal", "promotion_proposal_hash"),
        ("projection", "projection_hash"),
    )
    mismatches.extend(
        label
        for label, field in manifest_bindings
        if getattr(manifest, field) != getattr(expected, field)
    )
    if mismatches:
        raise PromotionManifestIntegrityError(
            "multi-joint decision binding mismatch: " + ", ".join(mismatches)
        )


def verify_multi_joint_promotion_application_result(
    receipt: CandidateMultiJointPromotionApplicationResult,
    *,
    manifest_service: PromotionManifestService,
    manifest_store: ArtifactStore,
    state_manager: Any,
    evidence_store: Any,
    run_controller: Any,
) -> None:
    if type(receipt) is not CandidateMultiJointPromotionApplicationResult:
        raise PromotionManifestIntegrityError(
            "multi-joint application verification requires a typed receipt"
        )
    try:
        receipt = CandidateMultiJointPromotionApplicationResult(
            request=receipt.request,
            readiness=receipt.readiness,
            compilation=receipt.compilation,
            decision_artifact_id=receipt.decision_artifact_id,
            result_artifact_id=receipt.result_artifact_id,
            applied_revision=receipt.applied_revision,
            applied_state_hash=receipt.applied_state_hash,
            status=receipt.status,
            error=receipt.error,
        )
    except Exception as exc:
        raise PromotionManifestIntegrityError(
            f"multi-joint application receipt is invalid: {exc}"
        ) from exc

    if receipt.status in (
        PromotionApplicationStatus.PRE_APPLY_FAILURE,
        PromotionApplicationStatus.CHANGEENGINE_REJECTED,
    ):
        return
    if receipt.request is None or receipt.readiness is None or receipt.compilation is None:
        raise PromotionManifestIntegrityError("multi-joint application receipt is incomplete")
    if receipt.decision_artifact_id is None:
        raise PromotionManifestIntegrityError("multi-joint application decision artifact is missing")

    try:
        decision_artifact = manifest_store.read_verified_strict(
            receipt.decision_artifact_id, expected_type=ArtifactType.JSON
        )
        if decision_artifact is None:
            raise PromotionManifestIntegrityError("multi-joint decision artifact is missing")
        decision_artifact_model = decision_artifact[0]
        decision = manifest_service.resolve_multi_joint_decision(
            manifest_store, receipt.decision_artifact_id
        )
        verify_multi_joint_promotion_decision(
            decision,
            request=receipt.request,
            readiness=receipt.readiness,
            compilation=receipt.compilation,
        )
    except PromotionManifestIntegrityError:
        raise
    except Exception as exc:
        raise PromotionManifestIntegrityError(
            f"multi-joint application decision verification failed: {exc}"
        ) from exc

    if (
        manifest_store.project_id != decision.project_id
        or manifest_store.run_id != decision_artifact_model.run_id
        or decision_artifact_model.project_id != decision.project_id
        or decision_artifact_model.run_id != manifest_store.run_id
        or receipt.status
        is PromotionApplicationStatus.PROMOTION_APPLIED_BUT_RESULT_PROVENANCE_FAILED
        and receipt.result_artifact_id is not None
    ):
        raise PromotionManifestIntegrityError("multi-joint application decision run binding mismatch")

    if receipt.status is not PromotionApplicationStatus.PROMOTION_APPLIED:
        try:
            persisted_state = state_manager.load_revision(
                decision.input_reference.project_id, receipt.applied_revision
            )
            persisted_state_hash = state_hash(persisted_state)
        except Exception as exc:
            raise PromotionManifestIntegrityError(
                f"multi-joint partial application state verification failed: {exc}"
            ) from exc
        if (
            receipt.applied_revision != decision.base_revision + 1
            or persisted_state_hash != receipt.applied_state_hash
        ):
            raise PromotionManifestIntegrityError(
                "multi-joint partial application N-to-N+1 binding mismatch"
            )
        return
    if receipt.result_artifact_id is None:
        raise PromotionManifestIntegrityError("multi-joint application result artifact is missing")
    try:
        result = manifest_service.resolve_multi_joint_result(
            manifest_store, receipt.result_artifact_id
        )
        result_artifact = manifest_store.read_verified_strict(
            receipt.result_artifact_id, expected_type=ArtifactType.JSON
        )
        if result_artifact is None:
            raise PromotionManifestIntegrityError("multi-joint result artifact is missing")
        result_artifact_model = result_artifact[0]
        invalidation = evidence_store.load_invalidation(
            decision.project_id, result.resulting_revision
        )
        if type(invalidation) is not InvalidationRecord:
            raise PromotionManifestIntegrityError("multi-joint invalidation record is not typed")
        persisted_state = state_manager.load_revision(
            decision.project_id, result.resulting_revision
        )
        persisted_state_hash = state_hash(persisted_state)
        run = run_controller.get_run(
            decision_artifact_model.run_id, project_id=decision.project_id
        )
        if type(run) is not Run:
            raise PromotionManifestIntegrityError("multi-joint application run is not typed")
    except PromotionManifestIntegrityError:
        raise
    except Exception as exc:
        raise PromotionManifestIntegrityError(
            f"multi-joint application durable verification failed: {exc}"
        ) from exc

    expected_paths = tuple(
        dict.fromkeys(operation.path for operation in receipt.compilation.proposal.operations)
    )
    if (
        result_artifact_model.run_id != manifest_store.run_id
        or result_artifact_model.run_id != decision_artifact_model.run_id
        or result.decision_artifact_id != receipt.decision_artifact_id
        or result.decision_artifact_hash != decision_artifact_model.sha256
        or result.decision_hash != decision.decision_hash
        or result.promotion_proposal_hash != receipt.compilation.promotion_proposal_hash
        or result.proposal_id != receipt.compilation.proposal.id
        or result.changeset_id != invalidation.changeset_id
        or result.changed_paths != expected_paths
        or tuple(invalidation.changed_paths) != expected_paths
        or invalidation.project_id != decision.project_id
        or invalidation.revision != result.resulting_revision
        or invalidation.parent_revision != result.base_revision
        or result.base_revision != decision.base_revision
        or result.base_state_hash != decision.base_state_hash
        or result.resulting_revision != receipt.applied_revision
        or result.resulting_state_hash != receipt.applied_state_hash
        or result.resulting_revision != result.base_revision + 1
        or persisted_state_hash != result.resulting_state_hash
        or run.project_id != decision.project_id
        or run.run_id != manifest_store.run_id
        or run.status is not RunStatus.CREATED
        or run.initial_revision != result.base_revision
        or run.initial_state_hash != result.base_state_hash
        or run.active_revision != result.resulting_revision
        or run.active_state_hash != result.resulting_state_hash
    ):
        raise PromotionManifestIntegrityError(
            "multi-joint application result or N-to-N+1 binding mismatch"
        )


def resolve_decision(store: ArtifactStore, artifact_id: str) -> SelectedCandidateDecisionManifest:
    return PromotionManifestService().resolve_decision(store, artifact_id)


def resolve_multi_joint_decision(
    store: ArtifactStore, artifact_id: str
) -> SelectedMultiJointCandidateDecisionManifest:
    return PromotionManifestService().resolve_multi_joint_decision(store, artifact_id)


def resolve_multi_joint_result(
    store: ArtifactStore, artifact_id: str
) -> MultiJointPromotionResultManifest:
    return PromotionManifestService().resolve_multi_joint_result(store, artifact_id)


def resolve_result(store: ArtifactStore, artifact_id: str) -> CandidatePromotionResultManifest:
    return PromotionManifestService().resolve_result(store, artifact_id)


__all__ = [
    "CandidatePromotionResultManifest",
    "decision_manifest_hash",
    "multi_joint_decision_manifest_hash",
    "multi_joint_result_manifest_hash",
    "MultiJointPromotionResultManifest",
    "PromotionManifestIntegrityError",
    "PromotionManifestPostPublicationVerificationError",
    "PromotionManifestService",
    "SelectedCandidateDecisionManifest",
    "SelectedMultiJointCandidateDecisionManifest",
    "result_manifest_hash",
    "resolve_decision",
    "resolve_multi_joint_decision",
    "resolve_multi_joint_result",
    "resolve_result",
    "verify_multi_joint_promotion_application_result",
    "verify_multi_joint_promotion_decision",
]
