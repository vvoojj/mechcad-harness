from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import AliasChoices, Field, StrictInt, StrictStr, field_validator, model_validator

from mechcad_harness.artifacts import ArtifactStore, ArtifactType, EngineeringArtifact
from mechcad_harness.state.hashing import canonical_json

from .promotion_models import (
    CandidateCanonicalInstanceMapping,
    PrePromotionM10ScopeProjection,
    PromotionDecisionInputReference,
    PromotionModel,
    PromotableMechanismProjection,
    _require_hash,
    promotion_proposal_hash as semantic_promotion_proposal_hash,
)


_DECISION_SCHEMA = "selected-candidate-decision-manifest@1"
_RESULT_SCHEMA = "candidate-promotion-result-manifest@1"


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


def result_manifest_hash(manifest: CandidatePromotionResultManifest) -> str:
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


class PromotionManifestService:
    """Publish and strictly resolve both promotion manifests in one run scope."""

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


def resolve_decision(store: ArtifactStore, artifact_id: str) -> SelectedCandidateDecisionManifest:
    return PromotionManifestService().resolve_decision(store, artifact_id)


def resolve_result(store: ArtifactStore, artifact_id: str) -> CandidatePromotionResultManifest:
    return PromotionManifestService().resolve_result(store, artifact_id)


__all__ = [
    "CandidatePromotionResultManifest",
    "decision_manifest_hash",
    "PromotionManifestIntegrityError",
    "PromotionManifestPostPublicationVerificationError",
    "PromotionManifestService",
    "SelectedCandidateDecisionManifest",
    "result_manifest_hash",
    "resolve_decision",
    "resolve_result",
]
