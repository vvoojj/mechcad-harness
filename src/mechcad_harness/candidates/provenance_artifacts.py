from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from mechcad_harness.artifacts import ArtifactStore, ArtifactType, EngineeringArtifact
from mechcad_harness.core.canonical import canonical_json_bytes
from mechcad_harness.dependency import DependencyGraph, EvidenceStore
from mechcad_harness.models.common import Model
from mechcad_harness.models.evidence import Evidence
from mechcad_harness.state import StateManager, state_hash

from .cad_realization import (
    CandidateCadRealization,
    CandidateCadRealizationRequest,
    CandidateCadStageOutcome,
    CandidateCadStageStatus,
    CandidateCadRealizationRequestV3,
    CandidateCadRealizationV2,
    trusted_representation_identity,
)
from .canonical_cad import CanonicalCadRealization, CanonicalPhysicalCadCompiler
from .canonical_m10 import (
    CanonicalM10VerificationOutcome,
    canonical_m10_aggregate_summary,
)
from .canonical_mechanism import (
    CanonicalMechanismReconstruction,
    CanonicalPhysicalMechanismCompiler,
    ExactSourceArtifactResolver,
    ProjectArtifactResolver,
    TrustedSourceArtifact,
    validate_canonical_mechanism,
)
from .comparison import (
    CandidateComparisonRequest,
    CandidateComparisonRequestV2,
    CandidateComparisonResult,
    CandidateComparisonResultV2,
    CandidateComparisonService,
    candidate_comparison_result_hash_v2,
)
from .evaluation import (
    CandidateEvaluation,
    CandidateEvaluationV2,
    CandidateEvaluationCurrentnessService,
    _validate_cad_inputs_v2,
    _validate_cad_inputs,
    _verify_candidate_cad_trusted_slot_raw_bindings,
)
from .models import (
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
    MechanicalDesignCandidate,
)
from .selection import (
    CandidateSelection,
    CandidateSelectionV2,
    CandidateSelectionService,
)
from .services import (
    CandidateIntegrityVerifier,
    CandidatePublication,
    CandidatePublicationService,
    candidate_cad_required_raw_source_identities,
    verify_candidate_semantic_binding,
)
from mechcad_harness.step_content_identity import step_content_identity_v1

_PRODUCER_NAME = "mechcad-candidate-provenance"
_PRODUCER_VERSION = "1"
_CANDIDATE_PUBLICATION_PRODUCER_NAME = "mechcad-candidate-publication"
_CANDIDATE_PUBLICATION_PRODUCER_VERSION = "1"
_CANDIDATE_PUBLICATION_FILENAME = "candidate.json"
_CANDIDATE_PUBLICATION_RUN_ID = CandidatePublicationService._RUN_ID
_CANONICAL_PROVENANCE_RUN_ID = "CANONICAL"
_CANONICAL_CAD_FILENAME = "canonical_cad_provenance.json"
_CANONICAL_M10_FILENAME = "canonical_m10_provenance.json"
_CHAIN_LOCATOR_SCHEMA = "promotion-chain-locator@1"
_CHAIN_LOCATOR_FILENAME = "promotion_chain_locator.json"
_CHAIN_LOCATOR_PREFIX = "PROMOTION-CHAIN-LOCATOR-"


class CandidateProvenanceIntegrityError(ValueError):
    """A durable candidate provenance record has inconsistent bindings."""


def _artifact_failure_message(label: str, exc: Exception, fallback: str) -> str:
    reason = str(exc)
    if "type mismatch" in reason:
        return f"{label} verification failed: artifact type mismatch"
    if "byte/hash mismatch" in reason:
        return f"{label} verification failed: artifact byte/hash mismatch"
    if "identity mismatch" in reason:
        return f"{label} verification failed: artifact project/identity mismatch"
    if "missing" in reason:
        return f"{label} verification failed: artifact is missing"
    return fallback


class ArtifactReference(Model):
    """An immutable, execution-scoped snapshot of a JSON artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact: EngineeringArtifact
    artifact_id: str | None = None
    project_id: str | None = None
    run_id: str | None = None
    task_id: str | None = None
    artifact_type: ArtifactType | None = None
    sha256: str | None = None
    bound_revision: int | None = None
    bound_state_hash: str | None = None

    @model_validator(mode="after")
    def validate_artifact(self) -> ArtifactReference:
        artifact = self.artifact
        if artifact.artifact_type is not ArtifactType.JSON:
            raise ValueError("provenance reference requires a JSON artifact")
        for field in (
            "artifact_id",
            "project_id",
            "run_id",
            "task_id",
            "artifact_type",
            "sha256",
            "bound_revision",
            "bound_state_hash",
        ):
            value = getattr(self, field)
            expected = getattr(artifact, field)
            if value is None:
                object.__setattr__(self, field, expected)
            elif value != expected:
                raise ValueError(f"artifact reference {field} does not match snapshot")
        return self


def _content(value: Model) -> bytes:
    return canonical_json_bytes(value.model_dump(mode="json"))


def _artifact_id(prefix: str, identity: str) -> str:
    return f"{prefix}{identity[7:31]}"


def _reparse(model_type: type[Model], value: Model) -> Model:
    return model_type.model_validate(value.model_dump(mode="json"))


def _canonical_source_bindings(values) -> tuple:
    """Normalize source snapshots by artifact identity without weakening equality."""
    by_artifact_id = {}
    for value in values:
        artifact_id = value.artifact_id
        if artifact_id in by_artifact_id:
            raise CandidateProvenanceIntegrityError(
                "canonical source provenance identities must be unique"
            )
        by_artifact_id[artifact_id] = value
    return tuple(by_artifact_id[artifact_id] for artifact_id in sorted(by_artifact_id))


def _reference_artifacts(
    *references: ArtifactReference | None,
) -> tuple[EngineeringArtifact, ...]:
    return tuple(
        _reparse(EngineeringArtifact, reference.artifact)
        for reference in references
        if reference is not None
    )


def _reopen_verified_artifact(
    workspace,
    artifact: EngineeringArtifact,
    *,
    expected_type: ArtifactType,
    label: str,
    return_content: bool = False,
) -> EngineeringArtifact | tuple[EngineeringArtifact, bytes]:
    """Require persisted artifact bytes and metadata to equal the recorded snapshot."""
    artifact = _reparse(EngineeringArtifact, artifact)
    try:
        verified, content = ArtifactStore(
            workspace,
            project_id=artifact.project_id,
            run_id=artifact.run_id,
            task_id=artifact.task_id,
        ).read_verified_strict(
            artifact.artifact_id,
            expected_type=expected_type,
            expected_hash=artifact.sha256,
        )
    except Exception as exc:
        raise CandidateProvenanceIntegrityError(
            _artifact_failure_message(label, exc, f"{label} verification failed")
        ) from exc
    if verified != artifact:
        if verified.project_id != artifact.project_id:
            message = f"{label} artifact project mismatch"
        elif verified.artifact_type is not artifact.artifact_type:
            message = f"{label} artifact type mismatch"
        elif (verified.bound_revision, verified.bound_state_hash) != (
            artifact.bound_revision,
            artifact.bound_state_hash,
        ):
            message = f"{label} source revision/state binding mismatch"
        else:
            message = f"{label} snapshot mismatch"
        raise CandidateProvenanceIntegrityError(message)
    return (verified, content) if return_content else verified


def _parse_verified_candidate_publication(
    artifact: EngineeringArtifact,
    content: bytes,
    realization: CandidateCadRealization,
    cad_request: CandidateCadRealizationRequest,
) -> CandidatePublication:
    """Authenticate the Task 1 publication snapshot and its candidate semantics."""
    try:
        payload = json.loads(content)
        if (
            not isinstance(payload, dict)
            or set(payload) != {"schema_version", "candidate", "request", "policy"}
            or payload["schema_version"] != "candidate-publication@1"
        ):
            raise ValueError("candidate publication manifest schema is invalid")
        candidate = MechanicalDesignCandidate.model_validate(payload["candidate"])
        request = CandidateSynthesisRequest.model_validate(payload["request"])
        policy = CandidateSynthesisPolicy.model_validate(payload["policy"])
        expected_id = "CAND-" + candidate.candidate_hash[7:31]
        expected_path = (
            PurePosixPath("projects")
            / candidate.source_binding.project_id
            / "runs"
            / _CANDIDATE_PUBLICATION_RUN_ID
            / "artifacts"
            / expected_id
            / _CANDIDATE_PUBLICATION_FILENAME
        ).as_posix()
        if (
            artifact.artifact_type is not ArtifactType.JSON
            or artifact.project_id != candidate.source_binding.project_id
            or artifact.run_id != _CANDIDATE_PUBLICATION_RUN_ID
            or artifact.task_id is not None
            or artifact.producer_tool_name != _CANDIDATE_PUBLICATION_PRODUCER_NAME
            or artifact.producer_tool_version != _CANDIDATE_PUBLICATION_PRODUCER_VERSION
            or artifact.relative_path != expected_path
            or artifact.artifact_id != expected_id
            or artifact.input_hash != candidate.candidate_hash
            or (artifact.bound_revision, artifact.bound_state_hash)
            != (
                candidate.source_binding.source_revision,
                candidate.source_binding.source_state_hash,
            )
        ):
            raise ValueError("candidate publication artifact metadata binding mismatch")
        publication = CandidatePublication(artifact=artifact, candidate=candidate)
        CandidateIntegrityVerifier().verify(candidate, request, policy)
        if (
            candidate.candidate_hash != realization.candidate_hash
            or candidate.candidate_hash != cad_request.candidate_hash
            or candidate.source_binding != cad_request.source_binding
            or request.source_binding != cad_request.source_binding
            or realization.request_hash != cad_request.request_hash
        ):
            raise ValueError("candidate publication/CAD realization binding mismatch")
        return publication
    except Exception as exc:
        raise CandidateProvenanceIntegrityError(
            "candidate publication integrity validation failed"
        ) from exc


def _require_shared_artifact_binding(
    *artifacts: EngineeringArtifact,
) -> tuple[str, int, str]:
    if not artifacts:
        raise ValueError("provenance requires at least one artifact reference")
    binding = (
        artifacts[0].project_id,
        artifacts[0].bound_revision,
        artifacts[0].bound_state_hash,
    )
    if any(
        (artifact.project_id, artifact.bound_revision, artifact.bound_state_hash)
        != binding
        for artifact in artifacts[1:]
    ):
        raise ValueError("provenance artifact project/revision/state binding mismatch")
    return binding


def _require_evidence_binding(
    evidence: tuple[Evidence, ...], revision: int, state_hash: str
) -> None:
    for value in evidence:
        value = _reparse(Evidence, value)
        if (value.revision, value.state_hash) != (revision, state_hash):
            raise ValueError("provenance evidence revision/state binding mismatch")


class CandidateCadProvenance(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["candidate-cad-provenance@1"] = "candidate-cad-provenance@1"
    realization: CandidateCadRealization
    request: CandidateCadRealizationRequest
    candidate_artifact: ArtifactReference
    source_step_artifacts: tuple[EngineeringArtifact, ...]

    @model_validator(mode="after")
    def validate_envelope(self) -> CandidateCadProvenance:
        realization = _reparse(CandidateCadRealization, self.realization)
        request = _reparse(CandidateCadRealizationRequest, self.request)
        publication = _reparse(EngineeringArtifact, self.candidate_artifact.artifact)
        if publication.project_id != request.source_binding.project_id:
            raise ValueError(
                "candidate CAD publication/source-binding project mismatch"
            )
        if (
            realization.candidate_hash != request.candidate_hash
            or realization.request_hash != request.request_hash
            or publication.input_hash != realization.candidate_hash
            or (publication.bound_revision, publication.bound_state_hash)
            != (
                request.source_binding.source_revision,
                request.source_binding.source_state_hash,
            )
        ):
            raise ValueError("candidate CAD provenance binding mismatch")
        sources = tuple(
            _reparse(EngineeringArtifact, source)
            for source in self.source_step_artifacts
        )
        for source in sources:
            if (
                source.artifact_type is not ArtifactType.STEP
                or source.project_id != publication.project_id
                or (source.bound_revision, source.bound_state_hash)
                != (
                    request.source_binding.source_revision,
                    request.source_binding.source_state_hash,
                )
            ):
                raise ValueError("candidate CAD source STEP binding mismatch")
        expected_source_artifact_ids = tuple(
            dict.fromkeys(
                mapping.geometry_definition_identities[0]
                for mapping in realization.mappings
                if mapping.source_geometry_identity is not None
            )
        )
        if tuple(source.artifact_id for source in sources) != expected_source_artifact_ids:
            raise ValueError("candidate CAD source STEP identity mismatch")
        if (
            tuple(dict.fromkeys(source.sha256 for source in sources))
            != realization.verified_source_content_identities
        ):
            raise ValueError("candidate CAD source STEP identity mismatch")
        return self


class CandidateEvaluationProvenance(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["candidate-evaluation-provenance@1"] = (
        "candidate-evaluation-provenance@1"
    )
    evaluation: CandidateEvaluation
    candidate_cad: ArtifactReference
    candidate_artifact: ArtifactReference
    proof_evidence: tuple[Evidence, ...] = ()
    home_evidence: tuple[Evidence, ...] = ()

    @model_validator(mode="after")
    def validate_envelope(self) -> CandidateEvaluationProvenance:
        evaluation = _reparse(CandidateEvaluation, self.evaluation)
        cad, candidate = _reference_artifacts(
            self.candidate_cad, self.candidate_artifact
        )
        _, revision, state_hash = _require_shared_artifact_binding(cad, candidate)
        if (
            candidate.input_hash != evaluation.candidate_hash
            or evaluation.cad_stage_outcome.realization_hash is None
            or cad.input_hash != evaluation.cad_stage_outcome.realization_hash
        ):
            raise ValueError("candidate evaluation artifact identity binding mismatch")
        _require_evidence_binding(
            self.proof_evidence + self.home_evidence, revision, state_hash
        )
        return self


class CandidateComparisonProvenance(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["candidate-comparison-provenance@1"] = (
        "candidate-comparison-provenance@1"
    )
    request: CandidateComparisonRequest
    result: CandidateComparisonResult
    candidate_cad_artifacts: tuple[ArtifactReference, ...] = Field(min_length=1)
    candidate_evaluation_artifacts: tuple[ArtifactReference, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_envelope(self) -> CandidateComparisonProvenance:
        request = _reparse(CandidateComparisonRequest, self.request)
        result = _reparse(CandidateComparisonResult, self.result)
        if request.request_hash != result.request_hash:
            raise ValueError("candidate comparison request binding mismatch")
        cad_artifacts = _reference_artifacts(*self.candidate_cad_artifacts)
        evaluation_artifacts = _reference_artifacts(
            *self.candidate_evaluation_artifacts
        )
        project_id, _, _ = _require_shared_artifact_binding(
            *cad_artifacts, *evaluation_artifacts
        )
        if project_id != result.project_id or len(cad_artifacts) != len(
            evaluation_artifacts
        ):
            raise ValueError("candidate comparison artifact binding mismatch")
        return self


class CandidateSelectionProvenance(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["candidate-selection-provenance@1"] = (
        "candidate-selection-provenance@1"
    )
    selection: CandidateSelection
    candidate_cad: ArtifactReference
    evaluation: ArtifactReference
    comparison: ArtifactReference | None = None

    @model_validator(mode="after")
    def validate_envelope(self) -> CandidateSelectionProvenance:
        selection = _reparse(CandidateSelection, self.selection)
        if selection.comparison_used != (self.comparison is not None):
            raise ValueError("candidate selection comparison binding mismatch")
        cad, evaluation, *comparison = _reference_artifacts(
            self.candidate_cad, self.evaluation, self.comparison
        )
        _require_shared_artifact_binding(cad, evaluation, *comparison)
        if evaluation.input_hash != selection.evaluation_hash:
            raise ValueError(
                "candidate selection evaluation artifact identity mismatch"
            )
        if comparison and comparison[0].input_hash != selection.comparison_result_hash:
            raise ValueError(
                "candidate selection comparison artifact identity mismatch"
            )
        return self


class CanonicalCadProvenance(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["canonical-cad-provenance@1"] = "canonical-cad-provenance@1"
    realization: CanonicalCadRealization
    source_step_artifacts: tuple[EngineeringArtifact, ...] = ()

    @model_validator(mode="after")
    def validate_envelope(self) -> CanonicalCadProvenance:
        realization = _reparse(CanonicalCadRealization, self.realization)
        sources = tuple(
            _reparse(EngineeringArtifact, source)
            for source in self.source_step_artifacts
        )
        expected_sources = tuple(
            EngineeringArtifact.model_validate(
                source.model_dump(mode="json", exclude={"schema_version"})
            )
            for source in realization.selected_source_provenance
        )
        if _canonical_source_bindings(sources) != _canonical_source_bindings(
            expected_sources
        ):
            raise ValueError("canonical CAD source artifact identity mismatch")
        return self


class CanonicalM10Provenance(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["canonical-m10-provenance@1"] = "canonical-m10-provenance@1"
    outcome: CanonicalM10VerificationOutcome
    canonical_cad: ArtifactReference
    proof_evidence: tuple[Evidence, ...] = ()
    home_evidence: tuple[Evidence, ...] = ()

    @model_validator(mode="after")
    def validate_envelope(self) -> CanonicalM10Provenance:
        outcome = _reparse(CanonicalM10VerificationOutcome, self.outcome)
        (cad,) = _reference_artifacts(self.canonical_cad)
        if (cad.project_id, cad.bound_revision, cad.bound_state_hash) != (
            outcome.project_id,
            outcome.revision,
            outcome.state_hash,
        ) or cad.input_hash != outcome.cad_realization_hash:
            raise ValueError("canonical M10 CAD artifact binding mismatch")
        _require_evidence_binding(
            self.proof_evidence + self.home_evidence,
            outcome.revision,
            outcome.state_hash,
        )
        return self


class CandidateCadProvenancePublication(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact: EngineeringArtifact
    payload: Any

    @model_validator(mode="after")
    def validate_payload_type(self) -> "CandidateCadProvenancePublication":
        schema_version = (
            self.payload.get("schema_version")
            if isinstance(self.payload, dict)
            else getattr(self.payload, "schema_version", None)
        )
        if schema_version == "candidate-cad-provenance@1":
            payload = CandidateCadProvenance.model_validate(
                self.payload.model_dump(mode="json")
                if isinstance(self.payload, Model)
                else self.payload
            )
        elif schema_version == "candidate-cad-provenance@2":
            payload = CandidateCadProvenanceV2.model_validate(
                self.payload.model_dump(mode="json")
                if isinstance(self.payload, Model)
                else self.payload
            )
        else:
            raise ValueError("candidate CAD publication requires an exact provenance envelope")
        object.__setattr__(self, "payload", payload)
        return self


class CandidateEvaluationProvenancePublication(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact: EngineeringArtifact
    payload: Any

    @model_validator(mode="after")
    def validate_payload_type(self) -> "CandidateEvaluationProvenancePublication":
        schema_version = (
            self.payload.get("schema_version")
            if isinstance(self.payload, dict)
            else getattr(self.payload, "schema_version", None)
        )
        raw = (
            self.payload.model_dump(mode="json")
            if isinstance(self.payload, Model)
            else self.payload
        )
        if schema_version == "candidate-evaluation-provenance@1":
            payload = CandidateEvaluationProvenance.model_validate(raw)
        elif schema_version == "candidate-evaluation-provenance@2":
            payload = CandidateEvaluationProvenanceV2.model_validate(raw)
        else:
            raise ValueError(
                "candidate evaluation publication requires an exact provenance envelope"
            )
        object.__setattr__(self, "payload", payload)
        return self


class CandidateComparisonProvenancePublication(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact: EngineeringArtifact
    payload: Any

    @model_validator(mode="after")
    def validate_payload_type(self) -> "CandidateComparisonProvenancePublication":
        version = (
            self.payload.get("schema_version")
            if isinstance(self.payload, dict)
            else getattr(self.payload, "schema_version", None)
        )
        raw = self.payload.model_dump(mode="json") if isinstance(self.payload, Model) else self.payload
        if version == "candidate-comparison-provenance@1":
            payload = CandidateComparisonProvenance.model_validate(raw)
        elif version == "candidate-comparison-provenance@2":
            payload = CandidateComparisonProvenanceV2.model_validate(raw)
        else:
            raise ValueError("comparison publication requires an exact provenance envelope")
        object.__setattr__(self, "payload", payload)
        return self


class CandidateSelectionProvenancePublication(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact: EngineeringArtifact
    payload: Any

    @model_validator(mode="after")
    def validate_payload_type(self) -> "CandidateSelectionProvenancePublication":
        version = (
            self.payload.get("schema_version")
            if isinstance(self.payload, dict)
            else getattr(self.payload, "schema_version", None)
        )
        raw = self.payload.model_dump(mode="json") if isinstance(self.payload, Model) else self.payload
        if version == "candidate-selection-provenance@1":
            payload = CandidateSelectionProvenance.model_validate(raw)
        elif version == "candidate-selection-provenance@2":
            payload = CandidateSelectionProvenanceV2.model_validate(raw)
        else:
            raise ValueError("selection publication requires an exact provenance envelope")
        object.__setattr__(self, "payload", payload)
        return self


class CanonicalCadProvenancePublication(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact: EngineeringArtifact
    payload: Any

    @model_validator(mode="after")
    def validate_payload_type(self):
        version = (
            self.payload.get("schema_version")
            if isinstance(self.payload, dict)
            else getattr(self.payload, "schema_version", None)
        )
        raw = self.payload.model_dump(mode="json") if isinstance(self.payload, Model) else self.payload
        if version == "canonical-cad-provenance@1":
            payload = CanonicalCadProvenance.model_validate(raw)
        elif version == "canonical-cad-provenance@2":
            payload = CanonicalCadProvenanceV2.model_validate(raw)
        else:
            raise ValueError("canonical CAD publication requires exact provenance envelope")
        object.__setattr__(self, "payload", payload)
        return self


class CanonicalM10ProvenancePublication(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact: EngineeringArtifact
    payload: Any

    @model_validator(mode="after")
    def validate_payload_type(self):
        version = (
            self.payload.get("schema_version")
            if isinstance(self.payload, dict)
            else getattr(self.payload, "schema_version", None)
        )
        raw = self.payload.model_dump(mode="json") if isinstance(self.payload, Model) else self.payload
        if version == "canonical-m10-provenance@1":
            payload = CanonicalM10Provenance.model_validate(raw)
        elif version == "canonical-m10-provenance@2":
            payload = CanonicalM10ProvenanceV2.model_validate(raw)
        else:
            raise ValueError("canonical M10 publication requires exact provenance envelope")
        object.__setattr__(self, "payload", payload)
        return self


def _locator_hash(value: str) -> str:
    if (
        len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError("must be a sha256 hash")
    return value


def _locator_id(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty or whitespace")
    return value


class PromotionChainLocator(Model):
    """Production-owned durable root for scalar-only promotion chain restart.

    Published once into the promotion run scope, after the complete
    candidate-to-canonical-M10 chain validates with a VERIFIED outcome. It
    owns the full scalar locator bundle; no protected promotion manifest is
    modified to carry it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["promotion-chain-locator@1"] = "promotion-chain-locator@1"
    project_id: str = Field(min_length=1)
    base_revision: int = Field(gt=0)
    base_state_hash: str
    resulting_revision: int = Field(gt=0)
    resulting_state_hash: str
    canonical_target_mechanism_id: str = Field(min_length=1)
    decision_artifact_id: str = Field(min_length=1)
    decision_artifact_hash: str
    result_artifact_id: str = Field(min_length=1)
    result_artifact_hash: str
    result_hash: str
    selection_artifact_id: str = Field(min_length=1)
    selection_artifact_hash: str
    selection_hash: str
    comparison_artifact_id: str | None = None
    comparison_artifact_hash: str | None = None
    comparison_result_hash: str | None = None
    evaluation_artifact_id: str = Field(min_length=1)
    evaluation_artifact_hash: str
    evaluation_hash: str
    candidate_cad_artifact_id: str = Field(min_length=1)
    candidate_cad_artifact_hash: str
    candidate_cad_realization_hash: str
    canonical_cad_artifact_id: str = Field(min_length=1)
    canonical_cad_artifact_hash: str
    canonical_cad_realization_hash: str
    canonical_m10_artifact_id: str = Field(min_length=1)
    canonical_m10_artifact_hash: str
    canonical_m10_outcome_hash: str
    verification_hash: str
    status: Literal["verified"] = "verified"
    locator_hash: str = "pending"

    _validate_hashes = field_validator(
        "base_state_hash",
        "resulting_state_hash",
        "decision_artifact_hash",
        "result_artifact_hash",
        "result_hash",
        "selection_artifact_hash",
        "selection_hash",
        "evaluation_artifact_hash",
        "evaluation_hash",
        "candidate_cad_artifact_hash",
        "candidate_cad_realization_hash",
        "canonical_cad_artifact_hash",
        "canonical_cad_realization_hash",
        "canonical_m10_artifact_hash",
        "canonical_m10_outcome_hash",
        "verification_hash",
    )(_locator_hash)
    _validate_optional_hashes = field_validator(
        "comparison_artifact_hash",
        "comparison_result_hash",
    )(lambda value: None if value is None else _locator_hash(value))
    _validate_ids = field_validator(
        "project_id",
        "canonical_target_mechanism_id",
        "decision_artifact_id",
        "result_artifact_id",
        "selection_artifact_id",
        "evaluation_artifact_id",
        "candidate_cad_artifact_id",
        "canonical_cad_artifact_id",
        "canonical_m10_artifact_id",
    )(_locator_id)
    _validate_optional_ids = field_validator("comparison_artifact_id")(
        lambda value: None if value is None else _locator_id(value)
    )
    _validate_locator_hash = field_validator("locator_hash")(
        lambda value: "pending" if value == "pending" else _locator_hash(value)
    )

    @model_validator(mode="after")
    def validate_locator(self) -> PromotionChainLocator:
        if self.resulting_revision != self.base_revision + 1:
            raise ValueError("chain locator revision must be base revision plus one")
        prefixes = (
            ("decision_artifact_id", "PROMOTION-DECISION-"),
            ("result_artifact_id", "PROMOTION-RESULT-"),
            ("selection_artifact_id", "CANDIDATE-SELECTION-"),
            ("evaluation_artifact_id", "CANDIDATE-EVALUATION-"),
            ("candidate_cad_artifact_id", "CANDIDATE-CAD-"),
            ("canonical_cad_artifact_id", "CANONICAL-CAD-"),
            ("canonical_m10_artifact_id", "CANONICAL-M10-"),
        )
        for field, prefix in prefixes:
            if not getattr(self, field).startswith(prefix):
                raise ValueError(f"chain locator {field} has the wrong artifact prefix")
        if self.comparison_artifact_id is not None and not self.comparison_artifact_id.startswith(
            "CANDIDATE-COMPARISON-"
        ):
            raise ValueError("chain locator comparison artifact has the wrong prefix")
        comparison_triple = (
            self.comparison_artifact_id,
            self.comparison_artifact_hash,
            self.comparison_result_hash,
        )
        if any(value is None for value in comparison_triple) and not all(
            value is None for value in comparison_triple
        ):
            raise ValueError("chain locator comparison bundle is incomplete")
        if self.selection_artifact_id != _artifact_id(
            "CANDIDATE-SELECTION-", self.selection_hash
        ):
            raise ValueError("chain locator selection artifact identity mismatch")
        if self.canonical_m10_artifact_id != _artifact_id(
            "CANONICAL-M10-", self.canonical_m10_outcome_hash
        ):
            raise ValueError("chain locator canonical M10 artifact identity mismatch")
        expected = "sha256:" + hashlib.sha256(
            canonical_json_bytes(
                self.model_dump(mode="json", exclude={"locator_hash"})
            )
        ).hexdigest()
        if self.locator_hash == "pending":
            object.__setattr__(self, "locator_hash", expected)
        elif self.locator_hash != expected:
            raise ValueError("chain locator hash mismatch")
        return self


class PromotionChainLocatorPublication(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact: EngineeringArtifact
    payload: PromotionChainLocator


class CandidateProvenanceArtifactService:
    """Publish deterministic candidate provenance envelopes without changing domain identity."""

    def __init__(
        self,
        workspace,
        project_id: str,
        state_manager: StateManager,
        *,
        evidence_store: EvidenceStore | None = None,
        candidate_publication_service: CandidatePublicationService | None = None,
        cad_replay_verifier=None,
    ):
        self.workspace = workspace
        self.project_id = project_id
        self.state_manager = state_manager
        self.evidence_store = (
            evidence_store
            if evidence_store is not None
            else EvidenceStore(workspace, state_manager, DependencyGraph([], []))
        )
        self.candidate_publication_service = (
            candidate_publication_service
            if candidate_publication_service is not None
            else CandidatePublicationService(workspace, project_id, state_manager)
        )
        self.cad_replay_verifier = cad_replay_verifier

    def _resolve_top_level(self, artifact: EngineeringArtifact | str, *, label: str):
        if isinstance(artifact, str):
            verified = ArtifactStore(
                self.workspace, project_id=self.project_id, run_id="LOOKUP"
            ).read_verified_in_project(artifact, expected_type=ArtifactType.JSON)
            if verified is None:
                raise CandidateProvenanceIntegrityError(
                    f"{label} artifact is missing or ambiguous"
                )
            return verified
        artifact = _reparse(EngineeringArtifact, artifact)
        if artifact.project_id != self.project_id:
            raise CandidateProvenanceIntegrityError(
                f"{label} artifact project mismatch"
            )
        return _reopen_verified_artifact(
            self.workspace,
            artifact,
            expected_type=ArtifactType.JSON,
            label=f"{label} artifact",
            return_content=True,
        )

    def _resolve_reference(
        self,
        reference: ArtifactReference,
        *,
        expected_input_hash: str,
        expected_scope: tuple[str, str, str | None] | None = None,
        label: str = "artifact reference",
    ):
        artifact = reference.artifact
        if artifact.project_id != self.project_id:
            raise CandidateProvenanceIntegrityError(
                "artifact reference project mismatch"
            )
        if expected_scope is not None and (
            artifact.project_id,
            artifact.run_id,
            artifact.task_id,
        ) != expected_scope:
            raise CandidateProvenanceIntegrityError(
                f"{label} scope mismatch"
            )
        verified, content = _reopen_verified_artifact(
            self.workspace,
            artifact,
            expected_type=ArtifactType.JSON,
            label=label,
            return_content=True,
        )
        if verified != artifact or artifact.input_hash != expected_input_hash:
            raise CandidateProvenanceIntegrityError(
                "artifact reference binding mismatch"
            )
        return verified, content

    def _evidence(
        self,
        *,
        kind: str,
        request_hash: str,
        result_hash: str,
        revision: int,
        state_hash: str,
    ) -> Evidence:
        prefix = (
            "EVD-CPROOF-"
            if kind == "analysis.continuous_clearance_proof"
            else "EVD-KSWEEP-"
        )
        evidence_id = (
            prefix
            + hashlib.sha256((request_hash + result_hash).encode()).hexdigest()[:24]
        )
        try:
            evidence = self.evidence_store.load_evidence(self.project_id, evidence_id)
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "required M10 evidence is missing"
            ) from exc
        if (
            evidence.id != evidence_id
            or evidence.kind != kind
            or (evidence.revision, evidence.state_hash) != (revision, state_hash)
            or evidence.producer_result_id != result_hash
            or evidence.input_hash != request_hash
            or evidence.output_hash != result_hash
        ):
            raise CandidateProvenanceIntegrityError("M10 evidence binding mismatch")
        return _reparse(Evidence, evidence)

    def _candidate_cad_required_raw_pairs(
        self, candidate: MechanicalDesignCandidate
    ) -> dict[str, str]:
        """Derive the complete raw source set from verified authority records."""
        try:
            identities = candidate_cad_required_raw_source_identities(
                candidate,
                state_manager=self.state_manager,
                project_id=self.project_id,
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate CAD required raw source binding is invalid"
            ) from exc
        return {
            artifact_id: identity.artifact_hash
            for artifact_id, identity in identities.items()
        }

    def _verify_candidate_cad_raw_artifacts(
        self,
        required_raw_pairs: dict[str, str],
        source_step_artifacts: tuple[EngineeringArtifact, ...] | None,
        *,
        source_binding,
    ) -> tuple[tuple[EngineeringArtifact, ...], dict[tuple[str, str], bytes]]:
        if source_step_artifacts is None:
            lookup = ArtifactStore(
                self.workspace, project_id=self.project_id, run_id="LOOKUP"
            )
            supplied = []
            for artifact_id, artifact_hash in sorted(required_raw_pairs.items()):
                verified = lookup.read_verified_in_project(
                    artifact_id,
                    expected_type=ArtifactType.STEP,
                    expected_hash=artifact_hash,
                )
                if verified is None:
                    raise CandidateProvenanceIntegrityError(
                        "candidate CAD required raw source artifact is missing or ambiguous"
                    )
                supplied.append(verified[0])
            source_step_artifacts = tuple(supplied)

        by_id: dict[str, EngineeringArtifact] = {}
        for value in source_step_artifacts:
            artifact = _reparse(EngineeringArtifact, value)
            if artifact.artifact_id in by_id:
                raise CandidateProvenanceIntegrityError(
                    "candidate CAD source artifact IDs must be unique"
                )
            by_id[artifact.artifact_id] = artifact
        supplied_pairs = {
            artifact_id: artifact.sha256 for artifact_id, artifact in by_id.items()
        }
        if supplied_pairs != required_raw_pairs:
            raise CandidateProvenanceIntegrityError(
                "candidate CAD source artifacts do not exactly match the complete required raw set"
            )

        ordered_artifacts = tuple(by_id[key] for key in sorted(by_id))
        verified_bytes: dict[tuple[str, str], bytes] = {}
        for artifact in ordered_artifacts:
            if (
                artifact.project_id != self.project_id
                or artifact.artifact_type is not ArtifactType.STEP
                or artifact.sha256 != required_raw_pairs[artifact.artifact_id]
                or (artifact.bound_revision, artifact.bound_state_hash)
                != (source_binding.source_revision, source_binding.source_state_hash)
            ):
                raise CandidateProvenanceIntegrityError(
                    "candidate CAD raw source artifact binding mismatch"
                )
            try:
                verified, content = _reopen_verified_artifact(
                    self.workspace,
                    artifact,
                    expected_type=ArtifactType.STEP,
                    label="source STEP artifact",
                    return_content=True,
                )
            except Exception as exc:
                raise CandidateProvenanceIntegrityError(
                    f"candidate CAD source STEP byte verification failed: {exc}"
                ) from exc
            if verified != artifact:
                raise CandidateProvenanceIntegrityError(
                    "candidate CAD source STEP artifact snapshot mismatch"
                )
            verified_bytes[(artifact.artifact_id, artifact.sha256)] = content
        return ordered_artifacts, verified_bytes

    def _candidate_cad_v2_context(
        self,
        candidate: MechanicalDesignCandidate,
        synthesis_request: CandidateSynthesisRequest,
        synthesis_policy: CandidateSynthesisPolicy,
        request: CandidateCadRealizationRequestV3,
        realization: CandidateCadRealizationV2,
        source_step_artifacts: tuple[EngineeringArtifact, ...] | None,
        *,
        candidate_publication_artifact: EngineeringArtifact | None = None,
    ):
        candidate = _reparse(MechanicalDesignCandidate, candidate)
        synthesis_request = _reparse(CandidateSynthesisRequest, synthesis_request)
        synthesis_policy = _reparse(CandidateSynthesisPolicy, synthesis_policy)
        request = CandidateCadRealizationRequestV3.model_validate(
            request.model_dump(mode="json")
        )
        realization = CandidateCadRealizationV2.model_validate(
            realization.model_dump(mode="json")
        )
        if (
            candidate.schema_version != "mechanical-design-candidate@2"
            or synthesis_request.schema_version != "candidate-synthesis-request@2"
            or request.schema_version != "candidate-cad-realization-request@3"
            or realization.schema_version != "candidate-cad-realization@2"
        ):
            raise CandidateProvenanceIntegrityError(
                "candidate CAD provenance requires the homogeneous @2/@3 family"
            )
        if (
            candidate.source_binding != synthesis_request.source_binding
            or candidate.semantic_source_binding_hash
            != synthesis_request.semantic_source_binding_hash
            or candidate.synthesis_request_hash != synthesis_request.request_hash
            or request.candidate_hash != candidate.candidate_hash
            or request.source_binding != candidate.source_binding
            or request.semantic_source_binding_hash
            != candidate.semantic_source_binding_hash
            or realization.candidate_hash != candidate.candidate_hash
            or realization.request_hash != request.request_hash
            or realization.mappings != request.mappings
        ):
            raise CandidateProvenanceIntegrityError(
                "candidate CAD request/candidate/realization binding mismatch"
            )
        try:
            CandidateIntegrityVerifier().verify(
                candidate, synthesis_request, synthesis_policy
            )
            candidate.source_binding.validate_against(
                self.project_id,
                self.state_manager.load_revision(
                    candidate.source_binding.project_id,
                    candidate.source_binding.source_revision,
                ),
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate CAD typed authority verification failed"
            ) from exc

        required_raw_pairs = self._candidate_cad_required_raw_pairs(candidate)
        verified_sources, verified_bytes = self._verify_candidate_cad_raw_artifacts(
            required_raw_pairs,
            source_step_artifacts,
            source_binding=candidate.source_binding,
        )
        if candidate_publication_artifact is not None:
            try:
                resolved_candidate = self.candidate_publication_service.resolve(
                    candidate_publication_artifact.artifact_id,
                    exact_source_artifacts=verified_sources,
                    verify_semantic_binding=False,
                )
            except Exception as exc:
                raise CandidateProvenanceIntegrityError(
                    "candidate publication raw-authority resolution failed"
                ) from exc
            if (
                resolved_candidate.artifact != candidate_publication_artifact
                or resolved_candidate.candidate != candidate
            ):
                raise CandidateProvenanceIntegrityError(
                    "candidate publication snapshot mismatch"
                )
        required_pairs = {
            (artifact_id, artifact_hash)
            for artifact_id, artifact_hash in required_raw_pairs.items()
        }
        try:
            expected_raw_binding_by_slot = (
                _verify_candidate_cad_trusted_slot_raw_bindings(
                    candidate,
                    realization,
                    required_raw_pairs=required_pairs,
                )
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                f"candidate CAD trusted per-slot raw verification failed: {exc}"
            ) from exc

        content_identity_by_slot: dict[tuple[str, str], str] = {}
        mapping_by_slot = {
            (mapping.physical_instance_id, mapping.cad_instance_id): mapping
            for mapping in realization.mappings
        }
        for slot, raw_pair in expected_raw_binding_by_slot.items():
            content = verified_bytes[raw_pair]
            content_identity = step_content_identity_v1(content).content_hash
            mapping = mapping_by_slot[slot]
            semantic_source = mapping.source_geometry_identity
            if (
                semantic_source is None
                or semantic_source.content_identity != content_identity
                or semantic_source.content_identity_algorithm
                != "step-content-identity@1"
                or mapping.geometry_definition_identities != (content_identity,)
                or mapping.representation_identity
                != trusted_representation_identity(
                    slot=mapping.cad_instance_id,
                    content_identity=content_identity,
                )
            ):
                raise CandidateProvenanceIntegrityError(
                    "candidate CAD trusted semantic identity does not match its slot raw bytes"
                )
            content_identity_by_slot[slot] = content_identity

        try:
            from .cad_realization import CandidateCadStageOutcomeV2

            _validate_cad_inputs_v2(
                candidate,
                request,
                CandidateCadStageOutcomeV2(
                    status=CandidateCadStageStatus.SUCCESS,
                    realization=realization,
                ),
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                f"candidate CAD semantic mapping verification failed: {exc}"
            ) from exc

        if Counter(realization.verified_source_artifact_hashes) != Counter(
            artifact.sha256 for artifact in verified_sources
        ):
            raise CandidateProvenanceIntegrityError(
                "candidate CAD raw SHA multiset does not match the required raw artifacts"
            )
        deduped_semantic_content = tuple(
            dict.fromkeys(
                content_identity_by_slot[
                    (mapping.physical_instance_id, mapping.cad_instance_id)
                ]
                for mapping in realization.mappings
                if mapping.fidelity.value == "trusted_source_geometry"
            )
        )
        if deduped_semantic_content != realization.verified_source_content_identities:
            raise CandidateProvenanceIntegrityError(
                "candidate CAD semantic content collection does not match verified slot bytes"
            )
        return (
            candidate,
            synthesis_request,
            synthesis_policy,
            request,
            realization,
            verified_sources,
            verified_bytes,
        )

    def _publish_candidate_cad_v2(
        self,
        candidate: MechanicalDesignCandidate,
        synthesis_request: CandidateSynthesisRequest,
        synthesis_policy: CandidateSynthesisPolicy,
        request: CandidateCadRealizationRequestV3,
        realization: CandidateCadRealizationV2,
        *,
        source_step_artifacts: tuple[EngineeringArtifact, ...] | None,
    ) -> CandidateCadProvenancePublication:
        (
            candidate,
            synthesis_request,
            synthesis_policy,
            request,
            realization,
            source_step_artifacts,
            _,
        ) = self._candidate_cad_v2_context(
            candidate,
            synthesis_request,
            synthesis_policy,
            request,
            realization,
            source_step_artifacts,
        )
        try:
            candidate_publication = self.candidate_publication_service.publish(
                candidate, synthesis_request, synthesis_policy
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate publication integrity validation failed"
            ) from exc
        if candidate_publication.artifact.project_id != self.project_id:
            raise CandidateProvenanceIntegrityError(
                "candidate publication project mismatch"
            )
        candidate_artifact, _ = _reopen_verified_artifact(
            self.workspace,
            candidate_publication.artifact,
            expected_type=ArtifactType.JSON,
            label="candidate artifact",
            return_content=True,
        )
        payload = CandidateCadProvenanceV2(
            realization=realization,
            request=request,
            candidate_artifact=ArtifactReference(artifact=candidate_artifact),
            source_step_artifacts=source_step_artifacts,
        )
        artifact = ArtifactStore(
            self.workspace,
            project_id=self.project_id,
            run_id=candidate_publication.artifact.run_id,
            task_id=candidate_publication.artifact.task_id,
        ).publish(
            _artifact_id("CANDIDATE-CAD-", realization.realization_hash),
            ArtifactType.JSON,
            "candidate_cad_provenance.json",
            _content(payload),
            _PRODUCER_NAME,
            _PRODUCER_VERSION,
            request.source_binding.source_revision,
            request.source_binding.source_state_hash,
            input_hash=realization.realization_hash,
        )
        return CandidateCadProvenancePublication(artifact=artifact, payload=payload)

    def _parse_candidate_publication_v2(
        self,
        cad_artifact: EngineeringArtifact,
        payload: "CandidateCadProvenanceV2",
    ):
        candidate_artifact, content = self._resolve_reference(
            payload.candidate_artifact,
            expected_input_hash=payload.realization.candidate_hash,
            expected_scope=(
                cad_artifact.project_id,
                cad_artifact.run_id,
                cad_artifact.task_id,
            ),
            label="candidate publication reference",
        )
        try:
            raw = json.loads(content)
            if (
                set(raw) != {"schema_version", "candidate", "request", "policy"}
                or raw["schema_version"] != "candidate-publication@1"
            ):
                raise ValueError("candidate publication manifest schema is invalid")
            candidate = MechanicalDesignCandidate.model_validate(raw["candidate"])
            synthesis_request = CandidateSynthesisRequest.model_validate(raw["request"])
            synthesis_policy = CandidateSynthesisPolicy.model_validate(raw["policy"])
            if (
                candidate.schema_version != "mechanical-design-candidate@2"
                or synthesis_request.schema_version != "candidate-synthesis-request@2"
                or candidate.source_binding != synthesis_request.source_binding
                or candidate.candidate_hash != payload.realization.candidate_hash
                or candidate.synthesis_request_hash != synthesis_request.request_hash
                or candidate_artifact.input_hash != candidate.candidate_hash
                or candidate_artifact.artifact_id
                != "CAND-" + candidate.candidate_hash[7:31]
                or candidate_artifact.producer_tool_name
                != _CANDIDATE_PUBLICATION_PRODUCER_NAME
                or candidate_artifact.producer_tool_version
                != _CANDIDATE_PUBLICATION_PRODUCER_VERSION
                or PurePosixPath(candidate_artifact.relative_path).name
                != _CANDIDATE_PUBLICATION_FILENAME
                or (
                    candidate_artifact.bound_revision,
                    candidate_artifact.bound_state_hash,
                )
                != (
                    candidate.source_binding.source_revision,
                    candidate.source_binding.source_state_hash,
                )
            ):
                raise ValueError("candidate publication typed parent mismatch")
            CandidateIntegrityVerifier().verify(
                candidate, synthesis_request, synthesis_policy
            )
            candidate.source_binding.validate_against(
                self.project_id,
                self.state_manager.load_revision(
                    candidate.source_binding.project_id,
                    candidate.source_binding.source_revision,
                ),
            )
            return (
                candidate_artifact,
                content,
                candidate,
                synthesis_request,
                synthesis_policy,
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate publication typed authority is invalid"
            ) from exc

    def _resolve_candidate_cad_v2(
        self,
        artifact: EngineeringArtifact,
        content: bytes,
    ) -> CandidateCadProvenancePublication:
        try:
            payload = CandidateCadProvenanceV2.model_validate_json(content)
            if content != _content(payload):
                raise CandidateProvenanceIntegrityError(
                    "candidate CAD envelope bytes are not canonical"
                )
            expected_id = _artifact_id(
                "CANDIDATE-CAD-", payload.realization.realization_hash
            )
            expected_binding = (
                payload.request.source_binding.source_revision,
                payload.request.source_binding.source_state_hash,
            )
            if (
                artifact.producer_tool_name != _PRODUCER_NAME
                or artifact.producer_tool_version != _PRODUCER_VERSION
                or PurePosixPath(artifact.relative_path).name
                != "candidate_cad_provenance.json"
                or artifact.artifact_id != expected_id
                or artifact.input_hash != payload.realization.realization_hash
                or (artifact.bound_revision, artifact.bound_state_hash)
                != expected_binding
            ):
                raise CandidateProvenanceIntegrityError(
                    "candidate CAD artifact metadata binding mismatch"
                )

            (
                candidate_artifact,
                _,
                candidate,
                synthesis_request,
                synthesis_policy,
            ) = self._parse_candidate_publication_v2(artifact, payload)
            (
                _,
                _,
                _,
                _,
                _,
                verified_sources,
                _,
            ) = self._candidate_cad_v2_context(
                candidate,
                synthesis_request,
                synthesis_policy,
                payload.request,
                payload.realization,
                payload.source_step_artifacts,
                candidate_publication_artifact=candidate_artifact,
            )
            try:
                fully_resolved = self.candidate_publication_service.resolve(
                    candidate_artifact.artifact_id,
                    exact_source_artifacts=verified_sources,
                )
            except Exception as exc:
                raise CandidateProvenanceIntegrityError(
                    "candidate publication semantic authority re-verification failed"
                ) from exc
            if (
                fully_resolved.artifact != candidate_artifact
                or fully_resolved.candidate != candidate
            ):
                raise CandidateProvenanceIntegrityError(
                    "candidate publication semantic snapshot mismatch"
                )
            return CandidateCadProvenancePublication(
                artifact=artifact, payload=payload
            )
        except CandidateProvenanceIntegrityError:
            raise
        except Exception as exc:
            failure = _artifact_failure_message(
                "candidate CAD",
                exc,
                "candidate CAD artifact identity/binding verification failed",
            )
            if failure == "candidate CAD artifact identity/binding verification failed":
                failure = f"{failure}: {exc}"
            raise CandidateProvenanceIntegrityError(
                failure
            ) from exc

    def _validate_candidate_cad_realization(
        self,
        candidate: MechanicalDesignCandidate,
        request: CandidateCadRealizationRequest,
        realization: CandidateCadRealization,
    ) -> None:
        try:
            _validate_cad_inputs(
                candidate,
                request,
                CandidateCadStageOutcome(
                    status=CandidateCadStageStatus.SUCCESS,
                    realization=realization,
                ),
                self.cad_replay_verifier,
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate CAD mapping/currentness validation failed"
            ) from exc

    def _candidate_from_cad(self, cad: CandidateCadProvenancePublication):
        publication, request, policy = self._candidate_publication_context(cad)
        return publication.candidate, request, policy

    def _candidate_publication_context(self, cad: CandidateCadProvenancePublication):
        artifact, content = self._resolve_reference(
            cad.payload.candidate_artifact,
            expected_input_hash=cad.payload.realization.candidate_hash,
            expected_scope=(
                cad.artifact.project_id,
                cad.artifact.run_id,
                cad.artifact.task_id,
            ),
            label="candidate publication reference",
        )
        publication = self._resolve_candidate_publication(
            artifact,
            content,
            cad.payload.realization,
            cad.payload.request,
            source_step_artifacts=cad.payload.source_step_artifacts,
        )
        try:
            raw = json.loads(content)
            return (
                publication,
                CandidateSynthesisRequest.model_validate(raw["request"]),
                CandidateSynthesisPolicy.model_validate(raw["policy"]),
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate publication context is invalid"
            ) from exc

    def _resolve_candidate_publication(
        self,
        artifact: EngineeringArtifact,
        content: bytes,
        realization: CandidateCadRealization,
        cad_request: CandidateCadRealizationRequest,
        source_step_artifacts: tuple[EngineeringArtifact, ...] = (),
    ) -> CandidatePublication:
        parsed = _parse_verified_candidate_publication(
            artifact, content, realization, cad_request
        )
        try:
            resolved = self.candidate_publication_service.resolve(
                artifact.artifact_id,
                exact_source_artifacts=source_step_artifacts or None,
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate publication persisted resolution failed"
            ) from exc
        if resolved.artifact != artifact or resolved.candidate != parsed.candidate:
            raise CandidateProvenanceIntegrityError(
                "candidate publication snapshot mismatch"
            )
        return resolved

    @staticmethod
    def _require_envelope_metadata(
        artifact: EngineeringArtifact,
        *,
        artifact_id: str,
        filename: str,
        input_hash: str,
        revision: int,
        state_hash: str,
    ) -> None:
        if (
            artifact.producer_tool_name != _PRODUCER_NAME
            or artifact.producer_tool_version != _PRODUCER_VERSION
            or PurePosixPath(artifact.relative_path).name != filename
            or artifact.artifact_id != artifact_id
            or artifact.input_hash != input_hash
            or (artifact.bound_revision, artifact.bound_state_hash)
            != (revision, state_hash)
        ):
            raise CandidateProvenanceIntegrityError(
                "provenance artifact metadata binding mismatch"
            )

    def publish_candidate_cad(
        self,
        candidate: MechanicalDesignCandidate,
        synthesis_request: CandidateSynthesisRequest,
        synthesis_policy: CandidateSynthesisPolicy,
        request: CandidateCadRealizationRequest | CandidateCadRealizationRequestV3,
        realization: CandidateCadRealization | CandidateCadRealizationV2,
        *,
        source_step_artifacts: tuple[EngineeringArtifact, ...] | None,
    ) -> CandidateCadProvenancePublication:
        if (
            candidate.schema_version == "mechanical-design-candidate@2"
            or request.schema_version == "candidate-cad-realization-request@3"
            or realization.schema_version == "candidate-cad-realization@2"
        ):
            return self._publish_candidate_cad_v2(
                candidate,
                synthesis_request,
                synthesis_policy,
                request,
                realization,
                source_step_artifacts=source_step_artifacts,
            )
        candidate = _reparse(MechanicalDesignCandidate, candidate)
        synthesis_request = _reparse(CandidateSynthesisRequest, synthesis_request)
        synthesis_policy = _reparse(CandidateSynthesisPolicy, synthesis_policy)
        request = _reparse(CandidateCadRealizationRequest, request)
        realization = _reparse(CandidateCadRealization, realization)
        try:
            candidate_publication = self.candidate_publication_service.publish(
                candidate, synthesis_request, synthesis_policy
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate publication integrity validation failed"
            ) from exc
        if (
            candidate_publication.artifact.project_id
            != request.source_binding.project_id
        ):
            raise CandidateProvenanceIntegrityError(
                "candidate publication/source-binding project mismatch"
            )
        if candidate_publication.artifact.project_id != self.project_id:
            raise CandidateProvenanceIntegrityError(
                "candidate publication project mismatch"
            )
        candidate_artifact, candidate_content = _reopen_verified_artifact(
            self.workspace,
            candidate_publication.artifact,
            expected_type=ArtifactType.JSON,
            label="candidate artifact",
            return_content=True,
        )
        self._resolve_candidate_publication(
            candidate_artifact,
            candidate_content,
            realization,
            request,
            source_step_artifacts=source_step_artifacts,
        )
        self._validate_candidate_cad_realization(candidate, request, realization)
        source_step_artifacts = tuple(
            _reopen_verified_artifact(
                self.workspace,
                source,
                expected_type=ArtifactType.STEP,
                label="source STEP artifact",
            )
            for source in source_step_artifacts
        )
        payload = CandidateCadProvenance(
            realization=realization,
            request=request,
            candidate_artifact=ArtifactReference(artifact=candidate_artifact),
            source_step_artifacts=source_step_artifacts,
        )
        artifact = ArtifactStore(
            self.workspace,
            project_id=self.project_id,
            run_id=candidate_publication.artifact.run_id,
            task_id=candidate_publication.artifact.task_id,
        ).publish(
            _artifact_id("CANDIDATE-CAD-", realization.realization_hash),
            ArtifactType.JSON,
            "candidate_cad_provenance.json",
            _content(payload),
            _PRODUCER_NAME,
            _PRODUCER_VERSION,
            request.source_binding.source_revision,
            request.source_binding.source_state_hash,
            input_hash=realization.realization_hash,
        )
        return CandidateCadProvenancePublication(artifact=artifact, payload=payload)

    def resolve_candidate_cad(
        self, artifact: EngineeringArtifact | str
    ) -> CandidateCadProvenancePublication:
        if isinstance(artifact, str):
            verified, content = self._resolve_top_level(artifact, label="candidate CAD")
            artifact = verified
        else:
            artifact = _reparse(EngineeringArtifact, artifact)
            if artifact.project_id != self.project_id:
                raise CandidateProvenanceIntegrityError(
                    "candidate CAD artifact project mismatch"
                )
        try:
            verified, content = ArtifactStore(
                self.workspace,
                project_id=artifact.project_id,
                run_id=artifact.run_id,
                task_id=artifact.task_id,
            ).read_verified_strict(
                artifact.artifact_id,
                expected_type=ArtifactType.JSON,
                expected_hash=artifact.sha256,
            )
            if verified != artifact:
                if verified.project_id != artifact.project_id:
                    message = "candidate CAD artifact project mismatch"
                elif verified.artifact_type is not artifact.artifact_type:
                    message = "candidate CAD artifact type mismatch"
                elif (verified.bound_revision, verified.bound_state_hash) != (
                    artifact.bound_revision,
                    artifact.bound_state_hash,
                ):
                    message = "candidate CAD source revision/state binding mismatch"
                else:
                    message = "candidate CAD artifact snapshot mismatch"
                raise CandidateProvenanceIntegrityError(
                    message
                )
            if json.loads(content).get("schema_version") == "candidate-cad-provenance@2":
                return self._resolve_candidate_cad_v2(verified, content)
            payload = CandidateCadProvenance.model_validate_json(content)
        except CandidateProvenanceIntegrityError:
            raise
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                _artifact_failure_message(
                    "candidate CAD",
                    exc,
                    "candidate CAD artifact identity/binding verification failed",
                )
            ) from exc

        expected_id = _artifact_id(
            "CANDIDATE-CAD-", payload.realization.realization_hash
        )
        expected_binding = (
            payload.request.source_binding.source_revision,
            payload.request.source_binding.source_state_hash,
        )
        if (
            content != _content(payload)
            or verified.producer_tool_name != _PRODUCER_NAME
            or verified.producer_tool_version != _PRODUCER_VERSION
            or PurePosixPath(verified.relative_path).name
            != "candidate_cad_provenance.json"
            or verified.artifact_id != expected_id
            or verified.input_hash != payload.realization.realization_hash
            or (verified.bound_revision, verified.bound_state_hash) != expected_binding
        ):
            raise CandidateProvenanceIntegrityError(
                "candidate CAD artifact metadata binding mismatch"
            )
        candidate_artifact, candidate_content = self._resolve_reference(
            payload.candidate_artifact,
            expected_input_hash=payload.realization.candidate_hash,
            expected_scope=(verified.project_id, verified.run_id, verified.task_id),
            label="candidate artifact",
        )
        for source in payload.source_step_artifacts:
            _reopen_verified_artifact(
                self.workspace,
                source,
                expected_type=ArtifactType.STEP,
                label="source STEP artifact",
            )
        publication = self._resolve_candidate_publication(
            candidate_artifact,
            candidate_content,
            payload.realization,
            payload.request,
            source_step_artifacts=payload.source_step_artifacts,
        )
        self._validate_candidate_cad_realization(
            publication.candidate,
            payload.request,
            payload.realization,
        )
        return CandidateCadProvenancePublication(artifact=verified, payload=payload)

    def publish_candidate_evaluation(
        self,
        candidate_cad: EngineeringArtifact | CandidateCadProvenancePublication,
        evaluation: CandidateEvaluation | CandidateEvaluationV2,
    ) -> CandidateEvaluationProvenancePublication:
        if evaluation.schema_version == "candidate-evaluation@2":
            return self._publish_candidate_evaluation_v2(candidate_cad, evaluation)
        cad = self.resolve_candidate_cad(
            candidate_cad.artifact
            if isinstance(candidate_cad, CandidateCadProvenancePublication)
            else candidate_cad
        )
        candidate, request, policy = self._candidate_from_cad(cad)
        evaluation = _reparse(CandidateEvaluation, evaluation)
        if (
            evaluation.candidate_hash != candidate.candidate_hash
            or evaluation.cad_realization_hash
            != cad.payload.realization.realization_hash
        ):
            raise CandidateProvenanceIntegrityError(
                "candidate evaluation/CAD binding mismatch"
            )
        try:
            CandidateEvaluationCurrentnessService(
                self.state_manager, cad_replay_verifier=self.cad_replay_verifier
            ).verify_current(
                evaluation,
                candidate,
                request,
                policy,
                exact_source_artifacts=cad.payload.source_step_artifacts,
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate evaluation currentness validation failed"
            ) from exc
        revision = candidate.source_binding.source_revision
        state_hash = candidate.source_binding.source_state_hash
        proofs = tuple(
            self._evidence(
                kind="analysis.continuous_clearance_proof",
                request_hash=proof.request_hash,
                result_hash=proof.result_hash,
                revision=revision,
                state_hash=state_hash,
            )
            for proof in evaluation.m10_stage_outcome.pair_proofs
        )
        homes = tuple(
            self._evidence(
                kind="analysis.kinematic_sweep",
                request_hash=check.request_hash,
                result_hash=check.result_hash,
                revision=revision,
                state_hash=state_hash,
            )
            for check in evaluation.m10_stage_outcome.home_exact_checks
        )
        payload = CandidateEvaluationProvenance(
            evaluation=evaluation,
            candidate_cad=ArtifactReference(artifact=cad.artifact),
            candidate_artifact=cad.payload.candidate_artifact,
            proof_evidence=proofs,
            home_evidence=homes,
        )
        artifact = ArtifactStore(
            self.workspace,
            project_id=self.project_id,
            run_id=cad.artifact.run_id,
            task_id=cad.artifact.task_id,
        ).publish(
            _artifact_id("CANDIDATE-EVALUATION-", evaluation.evaluation_hash),
            ArtifactType.JSON,
            "candidate_evaluation_provenance.json",
            _content(payload),
            _PRODUCER_NAME,
            _PRODUCER_VERSION,
            revision,
            state_hash,
            input_hash=evaluation.evaluation_hash,
        )
        return CandidateEvaluationProvenancePublication(
            artifact=artifact, payload=payload
        )

    def _publish_candidate_evaluation_v2(
        self,
        candidate_cad: EngineeringArtifact | CandidateCadProvenancePublication,
        evaluation,
    ) -> CandidateEvaluationProvenancePublication:
        from .evaluation import CandidateEvaluationV2, CandidateEvaluationCurrentnessService

        cad = self.resolve_candidate_cad(
            candidate_cad.artifact
            if isinstance(candidate_cad, CandidateCadProvenancePublication)
            else candidate_cad
        )
        if cad.payload.schema_version != "candidate-cad-provenance@2":
            raise CandidateProvenanceIntegrityError(
                "candidate evaluation@2 requires candidate CAD provenance@2"
            )
        evaluation = _reparse_exact(CandidateEvaluationV2, evaluation)
        candidate_artifact, _, candidate, request, policy = (
            self._parse_candidate_publication_v2(cad.artifact, cad.payload)
        )
        if (
            candidate.schema_version != "mechanical-design-candidate@2"
            or request.schema_version != "candidate-synthesis-request@2"
            or evaluation.candidate_hash != candidate.candidate_hash
            or evaluation.cad_realization_hash != cad.payload.realization.realization_hash
        ):
            raise CandidateProvenanceIntegrityError(
                "candidate evaluation@2/CAD typed parent mismatch"
            )
        try:
            CandidateEvaluationCurrentnessService(
                self.state_manager, cad_replay_verifier=self.cad_replay_verifier
            ).verify_current(
                evaluation,
                candidate,
                request,
                policy,
                exact_source_artifacts=cad.payload.source_step_artifacts,
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate evaluation@2 currentness validation failed"
            ) from exc
        revision = candidate.source_binding.source_revision
        state_hash = candidate.source_binding.source_state_hash
        proofs = tuple(
            self._evidence(
                kind="analysis.continuous_clearance_proof",
                request_hash=proof.request_hash,
                result_hash=proof.result_hash,
                revision=revision,
                state_hash=state_hash,
            )
            for proof in evaluation.m10_stage_outcome.pair_proofs
        )
        homes = tuple(
            self._evidence(
                kind="analysis.kinematic_sweep",
                request_hash=check.request_hash,
                result_hash=check.result_hash,
                revision=revision,
                state_hash=state_hash,
            )
            for check in evaluation.m10_stage_outcome.home_exact_checks
        )
        payload = CandidateEvaluationProvenanceV2(
            evaluation=evaluation,
            candidate_cad=ArtifactReference(artifact=cad.artifact),
            candidate_artifact=ArtifactReference(artifact=candidate_artifact),
            proof_evidence=proofs,
            home_evidence=homes,
        )
        artifact = ArtifactStore(
            self.workspace,
            project_id=self.project_id,
            run_id=cad.artifact.run_id,
            task_id=cad.artifact.task_id,
        ).publish(
            _artifact_id("CANDIDATE-EVALUATION-", evaluation.evaluation_hash),
            ArtifactType.JSON,
            "candidate_evaluation_provenance.json",
            _content(payload),
            _PRODUCER_NAME,
            _PRODUCER_VERSION,
            revision,
            state_hash,
            input_hash=evaluation.evaluation_hash,
        )
        return CandidateEvaluationProvenancePublication(
            artifact=artifact, payload=payload
        )

    def resolve_candidate_evaluation(
        self, artifact: EngineeringArtifact | str
    ) -> CandidateEvaluationProvenancePublication:
        verified, content = self._resolve_top_level(
            artifact, label="candidate evaluation"
        )
        try:
            if json.loads(content).get("schema_version") == "candidate-evaluation-provenance@2":
                return self._resolve_candidate_evaluation_v2(verified, content)
        except CandidateProvenanceIntegrityError:
            raise
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate evaluation artifact identity/binding verification failed"
            ) from exc
        try:
            payload = CandidateEvaluationProvenance.model_validate_json(content)
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate evaluation artifact identity/binding verification failed"
            ) from exc
        if content != _content(payload):
            raise CandidateProvenanceIntegrityError(
                "candidate evaluation artifact metadata binding mismatch"
            )
        self._require_envelope_metadata(
            verified,
            artifact_id=_artifact_id(
                "CANDIDATE-EVALUATION-", payload.evaluation.evaluation_hash
            ),
            filename="candidate_evaluation_provenance.json",
            input_hash=payload.evaluation.evaluation_hash,
            revision=payload.candidate_cad.artifact.bound_revision,
            state_hash=payload.candidate_cad.artifact.bound_state_hash,
        )
        evaluation_scope = (verified.project_id, verified.run_id, verified.task_id)
        for label, reference in (
            ("candidate CAD reference", payload.candidate_cad),
            ("candidate publication reference", payload.candidate_artifact),
        ):
            if (
                reference.artifact.project_id,
                reference.artifact.run_id,
                reference.artifact.task_id,
            ) != evaluation_scope:
                raise CandidateProvenanceIntegrityError(f"{label} scope mismatch")
        cad = self.resolve_candidate_cad(payload.candidate_cad.artifact)
        candidate, request, policy = self._candidate_from_cad(cad)
        if (
            payload.candidate_artifact != cad.payload.candidate_artifact
            or payload.evaluation.candidate_hash != candidate.candidate_hash
            or payload.evaluation.cad_realization_hash
            != cad.payload.realization.realization_hash
        ):
            raise CandidateProvenanceIntegrityError(
                "candidate evaluation dependency mismatch"
            )
        revision, state_hash = (
            candidate.source_binding.source_revision,
            candidate.source_binding.source_state_hash,
        )
        proofs = tuple(
            self._evidence(
                kind="analysis.continuous_clearance_proof",
                request_hash=p.request_hash,
                result_hash=p.result_hash,
                revision=revision,
                state_hash=state_hash,
            )
            for p in payload.evaluation.m10_stage_outcome.pair_proofs
        )
        homes = tuple(
            self._evidence(
                kind="analysis.kinematic_sweep",
                request_hash=p.request_hash,
                result_hash=p.result_hash,
                revision=revision,
                state_hash=state_hash,
            )
            for p in payload.evaluation.m10_stage_outcome.home_exact_checks
        )
        if (payload.proof_evidence, payload.home_evidence) != (proofs, homes):
            raise CandidateProvenanceIntegrityError(
                "candidate evaluation evidence coverage mismatch"
            )
        try:
            CandidateEvaluationCurrentnessService(
                self.state_manager, cad_replay_verifier=self.cad_replay_verifier
            ).verify_current(payload.evaluation, candidate, request, policy)
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate evaluation currentness validation failed"
            ) from exc
        return CandidateEvaluationProvenancePublication(
            artifact=verified, payload=payload
        )

    def _resolve_candidate_evaluation_v2(
        self, artifact: EngineeringArtifact, content: bytes
    ) -> CandidateEvaluationProvenancePublication:
        from .evaluation import CandidateEvaluationCurrentnessService

        try:
            payload = CandidateEvaluationProvenanceV2.model_validate_json(content)
            if content != _content(payload):
                raise CandidateProvenanceIntegrityError(
                    "candidate evaluation@2 envelope bytes are not canonical"
                )
            self._require_envelope_metadata(
                artifact,
                artifact_id=_artifact_id(
                    "CANDIDATE-EVALUATION-", payload.evaluation.evaluation_hash
                ),
                filename="candidate_evaluation_provenance.json",
                input_hash=payload.evaluation.evaluation_hash,
                revision=payload.candidate_cad.artifact.bound_revision,
                state_hash=payload.candidate_cad.artifact.bound_state_hash,
            )
            scope = (artifact.project_id, artifact.run_id, artifact.task_id)
            for label, reference in (
                ("candidate CAD reference", payload.candidate_cad),
                ("candidate publication reference", payload.candidate_artifact),
            ):
                if (
                    reference.artifact.project_id,
                    reference.artifact.run_id,
                    reference.artifact.task_id,
                ) != scope:
                    raise CandidateProvenanceIntegrityError(f"{label} scope mismatch")
            cad = self.resolve_candidate_cad(payload.candidate_cad.artifact)
            if cad.payload.schema_version != "candidate-cad-provenance@2":
                raise CandidateProvenanceIntegrityError(
                    "candidate evaluation@2 requires candidate CAD provenance@2"
                )
            candidate_artifact, _, candidate, request, policy = (
                self._parse_candidate_publication_v2(cad.artifact, cad.payload)
            )
            evaluation = payload.evaluation
            if (
                payload.candidate_artifact.artifact != candidate_artifact
                or evaluation.candidate_hash != candidate.candidate_hash
                or evaluation.cad_realization_hash != cad.payload.realization.realization_hash
            ):
                raise CandidateProvenanceIntegrityError(
                    "candidate evaluation@2 dependency mismatch"
                )
            revision = candidate.source_binding.source_revision
            state_hash = candidate.source_binding.source_state_hash
            proofs = tuple(
                self._evidence(
                    kind="analysis.continuous_clearance_proof",
                    request_hash=item.request_hash,
                    result_hash=item.result_hash,
                    revision=revision,
                    state_hash=state_hash,
                )
                for item in evaluation.m10_stage_outcome.pair_proofs
            )
            homes = tuple(
                self._evidence(
                    kind="analysis.kinematic_sweep",
                    request_hash=item.request_hash,
                    result_hash=item.result_hash,
                    revision=revision,
                    state_hash=state_hash,
                )
                for item in evaluation.m10_stage_outcome.home_exact_checks
            )
            if (payload.proof_evidence, payload.home_evidence) != (proofs, homes):
                raise CandidateProvenanceIntegrityError(
                    "candidate evaluation@2 evidence coverage mismatch"
                )
            CandidateEvaluationCurrentnessService(
                self.state_manager, cad_replay_verifier=self.cad_replay_verifier
            ).verify_current(
                evaluation,
                candidate,
                request,
                policy,
                exact_source_artifacts=cad.payload.source_step_artifacts,
            )
            return CandidateEvaluationProvenancePublication(
                artifact=artifact, payload=payload
            )
        except CandidateProvenanceIntegrityError:
            raise
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate evaluation@2 typed parent verification failed"
            ) from exc

    def publish_candidate_comparison(
        self,
        request: CandidateComparisonRequest | CandidateComparisonRequestV2,
        result: CandidateComparisonResult | CandidateComparisonResultV2,
        candidate_evaluation_artifacts: tuple[EngineeringArtifact, ...],
    ) -> CandidateComparisonProvenancePublication:
        if (
            request.schema_version == "candidate-comparison-request@2"
            or result.schema_version == "candidate-comparison-result@2"
        ):
            if (
                type(request) is not CandidateComparisonRequestV2
                or type(result) is not CandidateComparisonResultV2
            ):
                raise CandidateProvenanceIntegrityError(
                    "comparison provenance rejects mixed @1/@2 parents"
                )
            return self._publish_candidate_comparison_v2(
                request, result, candidate_evaluation_artifacts
            )
        request, result = (
            _reparse(CandidateComparisonRequest, request),
            _reparse(CandidateComparisonResult, result),
        )
        evaluations = tuple(
            self.resolve_candidate_evaluation(item)
            for item in candidate_evaluation_artifacts
        )
        candidate_cads = tuple(
            self.resolve_candidate_cad(item.payload.candidate_cad.artifact)
            for item in evaluations
        )
        self._validate_comparison(request, result, candidate_cads, evaluations)
        payload = CandidateComparisonProvenance(
            request=request,
            result=result,
            candidate_cad_artifacts=tuple(
                ArtifactReference(artifact=item.artifact) for item in candidate_cads
            ),
            candidate_evaluation_artifacts=tuple(
                ArtifactReference(artifact=item.artifact) for item in evaluations
            ),
        )
        first = evaluations[0].artifact
        artifact = ArtifactStore(
            self.workspace,
            project_id=self.project_id,
            run_id=first.run_id,
            task_id=first.task_id,
        ).publish(
            _artifact_id("CANDIDATE-COMPARISON-", result.result_hash),
            ArtifactType.JSON,
            "candidate_comparison_provenance.json",
            _content(payload),
            _PRODUCER_NAME,
            _PRODUCER_VERSION,
            first.bound_revision,
            first.bound_state_hash,
            input_hash=result.result_hash,
        )
        return CandidateComparisonProvenancePublication(
            artifact=artifact, payload=payload
        )

    def _publish_candidate_comparison_v2(
        self,
        request: CandidateComparisonRequestV2,
        result: CandidateComparisonResultV2,
        candidate_evaluation_artifacts: tuple[EngineeringArtifact, ...],
    ) -> CandidateComparisonProvenancePublication:
        request = CandidateComparisonRequestV2.model_validate(
            request.model_dump(mode="json")
        )
        result = CandidateComparisonResultV2.model_validate(
            result.model_dump(mode="json")
        )
        evaluations = tuple(
            self.resolve_candidate_evaluation(item)
            for item in candidate_evaluation_artifacts
        )
        candidate_cads = tuple(
            self.resolve_candidate_cad(item.payload.candidate_cad.artifact)
            for item in evaluations
        )
        self._validate_comparison_v2(request, result, candidate_cads, evaluations)
        payload = CandidateComparisonProvenanceV2(
            request=request,
            result=result,
            candidate_cad_artifacts=tuple(
                ArtifactReference(artifact=item.artifact) for item in candidate_cads
            ),
            candidate_evaluation_artifacts=tuple(
                ArtifactReference(artifact=item.artifact) for item in evaluations
            ),
        )
        first = evaluations[0].artifact
        artifact = ArtifactStore(
            self.workspace,
            project_id=self.project_id,
            run_id=first.run_id,
            task_id=first.task_id,
        ).publish(
            _artifact_id("CANDIDATE-COMPARISON-", result.result_hash),
            ArtifactType.JSON,
            "candidate_comparison_provenance.json",
            _content(payload),
            _PRODUCER_NAME,
            _PRODUCER_VERSION,
            first.bound_revision,
            first.bound_state_hash,
            input_hash=result.result_hash,
        )
        return CandidateComparisonProvenancePublication(
            artifact=artifact, payload=payload
        )

    def _validate_comparison_v2(
        self,
        request: CandidateComparisonRequestV2,
        result: CandidateComparisonResultV2,
        candidate_cads: tuple[CandidateCadProvenancePublication, ...],
        evaluations: tuple[CandidateEvaluationProvenancePublication, ...],
    ) -> None:
        if type(request) is not CandidateComparisonRequestV2 or type(
            result
        ) is not CandidateComparisonResultV2:
            raise CandidateProvenanceIntegrityError(
                "comparison provenance requires request@2/result@2"
            )
        if tuple(
            (
                item.payload.evaluation.candidate_hash,
                item.payload.evaluation.evaluation_hash,
            )
            for item in evaluations
        ) != request.candidate_evaluation_pairs:
            raise CandidateProvenanceIntegrityError(
                "comparison@2 candidate/evaluation pair binding mismatch"
            )
        if len(candidate_cads) != len(evaluations) or any(
            cad.artifact != evaluation.payload.candidate_cad.artifact
            for cad, evaluation in zip(candidate_cads, evaluations)
        ):
            raise CandidateProvenanceIntegrityError(
                "comparison@2 CAD/evaluation binding mismatch"
            )
        try:
            project_id, _, _ = _require_shared_artifact_binding(
                *(item.artifact for item in candidate_cads),
                *(item.artifact for item in evaluations),
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "comparison@2 artifact project/revision/state binding mismatch"
            ) from exc
        if project_id != self.project_id or request.project_id != project_id:
            raise CandidateProvenanceIntegrityError(
                "comparison@2 project binding mismatch"
            )
        comparison_scope = (
            evaluations[0].artifact.project_id,
            evaluations[0].artifact.run_id,
            evaluations[0].artifact.task_id,
        )
        if any(
            (item.artifact.project_id, item.artifact.run_id, item.artifact.task_id)
            != comparison_scope
            for item in (*candidate_cads, *evaluations)
        ):
            raise CandidateProvenanceIntegrityError(
                "comparison@2 artifact scope mismatch"
            )
        candidates = []
        synthesis_requests = {}
        for cad in candidate_cads:
            candidate, synthesis_request, _ = self._candidate_from_cad(cad)
            if (
                candidate.schema_version != "mechanical-design-candidate@2"
                or synthesis_request.schema_version != "candidate-synthesis-request@2"
            ):
                raise CandidateProvenanceIntegrityError(
                    "comparison@2 requires homogeneous candidate/request@2 parents"
                )
            candidates.append(candidate)
            synthesis_requests[candidate.candidate_hash] = synthesis_request
        try:
            replay = CandidateEvaluationCurrentnessService(
                self.state_manager, cad_replay_verifier=self.cad_replay_verifier
            )
            recomputed = CandidateComparisonService(
                result.policy,
                project_id=self.project_id,
                currentness_verifier=replay,
            ).compare(
                request,
                tuple(
                    (candidate, evaluation.payload.evaluation)
                    for candidate, evaluation in zip(candidates, evaluations)
                ),
                synthesis_requests_by_candidate_hash=synthesis_requests,
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate comparison@2 validation failed"
            ) from exc
        if recomputed != result or result.result_hash != candidate_comparison_result_hash_v2(
            result
        ):
            raise CandidateProvenanceIntegrityError(
                "candidate comparison@2 result mismatch"
            )

    def _validate_comparison(
        self,
        request: CandidateComparisonRequest,
        result: CandidateComparisonResult,
        candidate_cads: tuple[CandidateCadProvenancePublication, ...],
        evaluations: tuple[CandidateEvaluationProvenancePublication, ...],
    ) -> None:
        if (
            tuple(
                (
                    item.payload.evaluation.candidate_hash,
                    item.payload.evaluation.evaluation_hash,
                )
                for item in evaluations
            )
            != request.candidate_evaluation_pairs
        ):
            raise CandidateProvenanceIntegrityError(
                "candidate comparison pair order mismatch"
            )
        if len(candidate_cads) != len(evaluations) or any(
            cad.artifact != evaluation.payload.candidate_cad.artifact
            for cad, evaluation in zip(candidate_cads, evaluations)
        ):
            raise CandidateProvenanceIntegrityError(
                "candidate comparison CAD/evaluation binding mismatch"
            )
        candidates = tuple(self._candidate_from_cad(item)[0] for item in candidate_cads)
        try:
            replay = CandidateEvaluationCurrentnessService(
                self.state_manager, cad_replay_verifier=self.cad_replay_verifier
            )
            recomputed = CandidateComparisonService(
                result.policy, project_id=self.project_id, currentness_verifier=replay
            ).compare(
                request,
                tuple(
                    zip(candidates, (item.payload.evaluation for item in evaluations))
                ),
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate comparison validation failed"
            ) from exc
        if recomputed != result:
            raise CandidateProvenanceIntegrityError(
                "candidate comparison result mismatch"
            )

    def resolve_candidate_comparison(
        self, artifact: EngineeringArtifact | str
    ) -> CandidateComparisonProvenancePublication:
        verified, content = self._resolve_top_level(
            artifact, label="candidate comparison"
        )
        try:
            raw = json.loads(content)
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate comparison artifact identity/binding verification failed"
            ) from exc
        if raw.get("schema_version") == "candidate-comparison-provenance@2":
            return self._resolve_candidate_comparison_v2(verified, content)
        try:
            payload = CandidateComparisonProvenance.model_validate_json(content)
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate comparison artifact identity/binding verification failed"
            ) from exc
        if content != _content(payload):
            raise CandidateProvenanceIntegrityError(
                "candidate comparison artifact metadata binding mismatch"
            )
        first = payload.candidate_evaluation_artifacts[0].artifact
        self._require_envelope_metadata(
            verified,
            artifact_id=_artifact_id(
                "CANDIDATE-COMPARISON-", payload.result.result_hash
            ),
            filename="candidate_comparison_provenance.json",
            input_hash=payload.result.result_hash,
            revision=first.bound_revision,
            state_hash=first.bound_state_hash,
        )
        comparison_scope = (verified.project_id, verified.run_id, verified.task_id)
        for label, references in (
            ("candidate CAD reference", payload.candidate_cad_artifacts),
            ("candidate evaluation reference", payload.candidate_evaluation_artifacts),
        ):
            if any(
                (reference.artifact.project_id, reference.artifact.run_id, reference.artifact.task_id)
                != comparison_scope
                for reference in references
            ):
                raise CandidateProvenanceIntegrityError(f"{label} scope mismatch")
        evaluations = tuple(
            self.resolve_candidate_evaluation(item.artifact)
            for item in payload.candidate_evaluation_artifacts
        )
        candidate_cads = tuple(
            self.resolve_candidate_cad(item.artifact)
            for item in payload.candidate_cad_artifacts
        )
        self._validate_comparison(
            payload.request, payload.result, candidate_cads, evaluations
        )
        return CandidateComparisonProvenancePublication(
            artifact=verified, payload=payload
        )

    def _resolve_candidate_comparison_v2(
        self, verified: EngineeringArtifact, content: bytes
    ) -> CandidateComparisonProvenancePublication:
        try:
            payload = CandidateComparisonProvenanceV2.model_validate_json(content)
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate comparison@2 artifact identity/binding verification failed"
            ) from exc
        if content != _content(payload):
            raise CandidateProvenanceIntegrityError(
                "candidate comparison@2 artifact metadata binding mismatch"
            )
        first = payload.candidate_evaluation_artifacts[0].artifact
        self._require_envelope_metadata(
            verified,
            artifact_id=_artifact_id(
                "CANDIDATE-COMPARISON-", payload.result.result_hash
            ),
            filename="candidate_comparison_provenance.json",
            input_hash=payload.result.result_hash,
            revision=first.bound_revision,
            state_hash=first.bound_state_hash,
        )
        comparison_scope = (verified.project_id, verified.run_id, verified.task_id)
        for label, references in (
            ("candidate CAD reference", payload.candidate_cad_artifacts),
            ("candidate evaluation reference", payload.candidate_evaluation_artifacts),
        ):
            if any(
                (
                    reference.artifact.project_id,
                    reference.artifact.run_id,
                    reference.artifact.task_id,
                )
                != comparison_scope
                for reference in references
            ):
                raise CandidateProvenanceIntegrityError(
                    f"{label} scope mismatch"
                )
        evaluations = tuple(
            self.resolve_candidate_evaluation(reference.artifact)
            for reference in payload.candidate_evaluation_artifacts
        )
        candidate_cads = tuple(
            self.resolve_candidate_cad(reference.artifact)
            for reference in payload.candidate_cad_artifacts
        )
        self._validate_comparison_v2(
            payload.request, payload.result, candidate_cads, evaluations
        )
        return CandidateComparisonProvenancePublication(
            artifact=verified, payload=payload
        )

    def publish_candidate_selection(
        self,
        selection: CandidateSelection | CandidateSelectionV2,
        candidate_cad: EngineeringArtifact,
        evaluation: EngineeringArtifact,
        comparison: EngineeringArtifact | None = None,
    ) -> CandidateSelectionProvenancePublication:
        if selection.schema_version == "candidate-selection@2":
            if type(selection) is not CandidateSelectionV2:
                raise CandidateProvenanceIntegrityError(
                    "selection provenance requires the exact selection@2 record"
                )
            return self._publish_candidate_selection_v2(
                selection, candidate_cad, evaluation, comparison
            )
        selection = _reparse(CandidateSelection, selection)
        cad, evaluated = (
            self.resolve_candidate_cad(candidate_cad),
            self.resolve_candidate_evaluation(evaluation),
        )
        comparison_publication = (
            self.resolve_candidate_comparison(comparison)
            if comparison is not None
            else None
        )
        self._validate_selection(selection, cad, evaluated, comparison_publication)
        payload = CandidateSelectionProvenance(
            selection=selection,
            candidate_cad=ArtifactReference(artifact=cad.artifact),
            evaluation=ArtifactReference(artifact=evaluated.artifact),
            comparison=None
            if comparison_publication is None
            else ArtifactReference(artifact=comparison_publication.artifact),
        )
        artifact = ArtifactStore(
            self.workspace,
            project_id=self.project_id,
            run_id=cad.artifact.run_id,
            task_id=cad.artifact.task_id,
        ).publish(
            _artifact_id("CANDIDATE-SELECTION-", selection.selection_hash),
            ArtifactType.JSON,
            "candidate_selection_provenance.json",
            _content(payload),
            _PRODUCER_NAME,
            _PRODUCER_VERSION,
            cad.artifact.bound_revision,
            cad.artifact.bound_state_hash,
            input_hash=selection.selection_hash,
        )
        return CandidateSelectionProvenancePublication(
            artifact=artifact, payload=payload
        )

    def _publish_candidate_selection_v2(
        self,
        selection: CandidateSelectionV2,
        candidate_cad: EngineeringArtifact,
        evaluation: EngineeringArtifact,
        comparison: EngineeringArtifact | None,
    ) -> CandidateSelectionProvenancePublication:
        selection = CandidateSelectionV2.model_validate(
            selection.model_dump(mode="json")
        )
        cad = self.resolve_candidate_cad(candidate_cad)
        evaluated = self.resolve_candidate_evaluation(evaluation)
        comparison_publication = (
            self.resolve_candidate_comparison(comparison)
            if comparison is not None
            else None
        )
        self._validate_selection_v2(
            selection, cad, evaluated, comparison_publication
        )
        payload = CandidateSelectionProvenanceV2(
            selection=selection,
            candidate_cad=ArtifactReference(artifact=cad.artifact),
            evaluation=ArtifactReference(artifact=evaluated.artifact),
            comparison=(
                None
                if comparison_publication is None
                else ArtifactReference(artifact=comparison_publication.artifact)
            ),
        )
        artifact = ArtifactStore(
            self.workspace,
            project_id=self.project_id,
            run_id=cad.artifact.run_id,
            task_id=cad.artifact.task_id,
        ).publish(
            _artifact_id("CANDIDATE-SELECTION-", selection.selection_hash),
            ArtifactType.JSON,
            "candidate_selection_provenance.json",
            _content(payload),
            _PRODUCER_NAME,
            _PRODUCER_VERSION,
            cad.artifact.bound_revision,
            cad.artifact.bound_state_hash,
            input_hash=selection.selection_hash,
        )
        return CandidateSelectionProvenancePublication(
            artifact=artifact, payload=payload
        )

    def _validate_selection_v2(
        self,
        selection: CandidateSelectionV2,
        cad: CandidateCadProvenancePublication,
        evaluated: CandidateEvaluationProvenancePublication,
        comparison_publication: CandidateComparisonProvenancePublication | None,
    ) -> None:
        if type(selection) is not CandidateSelectionV2:
            raise CandidateProvenanceIntegrityError(
                "selection provenance requires selection@2"
            )
        if cad.artifact != evaluated.payload.candidate_cad.artifact:
            raise CandidateProvenanceIntegrityError(
                "selection@2 CAD/evaluation binding mismatch"
            )
        candidate, synthesis_request, _ = self._candidate_from_cad(cad)
        if (
            candidate.schema_version != "mechanical-design-candidate@2"
            or synthesis_request.schema_version != "candidate-synthesis-request@2"
            or evaluated.payload.evaluation.schema_version != "candidate-evaluation@2"
        ):
            raise CandidateProvenanceIntegrityError(
                "selection@2 requires homogeneous candidate/evaluation/request@2 parents"
            )
        if selection.comparison_used != (comparison_publication is not None):
            raise CandidateProvenanceIntegrityError(
                "selection@2 comparison binding mismatch"
            )

        comparison_result = None
        comparison_entries = None
        synthesis_requests = None
        exact_source_artifacts_by_candidate_hash = {
            candidate.candidate_hash: cad.payload.source_step_artifacts
        }
        if comparison_publication is not None:
            if comparison_publication.payload.schema_version != "candidate-comparison-provenance@2":
                raise CandidateProvenanceIntegrityError(
                    "selection@2 requires comparison provenance@2"
                )
            comparison_result = comparison_publication.payload.result
            comparison_entries_list = []
            synthesis_requests = {}
            for reference in comparison_publication.payload.candidate_evaluation_artifacts:
                member_evaluation = self.resolve_candidate_evaluation(
                    reference.artifact
                )
                member_cad = self.resolve_candidate_cad(
                    member_evaluation.payload.candidate_cad.artifact
                )
                member_candidate, member_request, _ = self._candidate_from_cad(
                    member_cad
                )
                if (
                    member_candidate.schema_version
                    != "mechanical-design-candidate@2"
                    or member_request.schema_version
                    != "candidate-synthesis-request@2"
                    or member_evaluation.payload.evaluation.schema_version
                    != "candidate-evaluation@2"
                ):
                    raise CandidateProvenanceIntegrityError(
                        "selection@2 comparison parent contains a mixed family"
                    )
                comparison_entries_list.append(
                    (member_candidate, member_evaluation.payload.evaluation)
                )
                synthesis_requests[member_candidate.candidate_hash] = member_request
                exact_source_artifacts_by_candidate_hash[
                    member_candidate.candidate_hash
                ] = member_cad.payload.source_step_artifacts
            comparison_entries = tuple(comparison_entries_list)

        try:
            replay = CandidateEvaluationCurrentnessService(
                self.state_manager, cad_replay_verifier=self.cad_replay_verifier
            )
            expected = CandidateSelectionService(
                project_id=self.project_id,
                currentness_verifier=replay,
            ).select(
                candidate,
                evaluated.payload.evaluation,
                selection.selector_identity,
                selection.rationale,
                comparison=comparison_result,
                comparison_entries=comparison_entries,
                synthesis_request=synthesis_request,
                synthesis_requests_by_candidate_hash=synthesis_requests,
                exact_source_artifacts=cad.payload.source_step_artifacts,
                exact_source_artifacts_by_candidate_hash=(
                    exact_source_artifacts_by_candidate_hash
                ),
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate selection@2 validation failed"
            ) from exc
        if expected != selection:
            raise CandidateProvenanceIntegrityError(
                "candidate selection@2 mismatch"
            )

    def _validate_selection(
        self,
        selection: CandidateSelection,
        cad: CandidateCadProvenancePublication,
        evaluated: CandidateEvaluationProvenancePublication,
        comparison_publication: CandidateComparisonProvenancePublication | None,
    ) -> None:
        if cad.artifact != evaluated.payload.candidate_cad.artifact:
            raise CandidateProvenanceIntegrityError(
                "candidate selection CAD/evaluation binding mismatch"
            )
        candidate, _, _ = self._candidate_from_cad(cad)
        if selection.comparison_used != (comparison_publication is not None):
            raise CandidateProvenanceIntegrityError(
                "candidate selection comparison binding mismatch"
            )
        entries = None
        result = None
        if comparison_publication is not None:
            result = comparison_publication.payload.result
            entries = tuple(
                (
                    self._candidate_from_cad(
                        self.resolve_candidate_cad(
                            self.resolve_candidate_evaluation(
                                ref.artifact
                            ).payload.candidate_cad.artifact
                        )
                    )[0],
                    self.resolve_candidate_evaluation(ref.artifact).payload.evaluation,
                )
                for ref in comparison_publication.payload.candidate_evaluation_artifacts
            )
        try:
            replay = CandidateEvaluationCurrentnessService(
                self.state_manager, cad_replay_verifier=self.cad_replay_verifier
            )
            expected = CandidateSelectionService(
                project_id=self.project_id, currentness_verifier=replay
            ).select(
                candidate,
                evaluated.payload.evaluation,
                selection.selector_identity,
                selection.rationale,
                result,
                entries,
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate selection validation failed"
            ) from exc
        if expected != selection:
            raise CandidateProvenanceIntegrityError("candidate selection mismatch")

    def resolve_candidate_selection(
        self, artifact: EngineeringArtifact | str
    ) -> CandidateSelectionProvenancePublication:
        verified, content = self._resolve_top_level(
            artifact, label="candidate selection"
        )
        try:
            raw = json.loads(content)
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate selection artifact identity/binding verification failed"
            ) from exc
        if raw.get("schema_version") == "candidate-selection-provenance@2":
            return self._resolve_candidate_selection_v2(verified, content)
        try:
            payload = CandidateSelectionProvenance.model_validate_json(content)
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate selection artifact identity/binding verification failed"
            ) from exc
        if content != _content(payload):
            raise CandidateProvenanceIntegrityError(
                "candidate selection artifact metadata binding mismatch"
            )
        self._require_envelope_metadata(
            verified,
            artifact_id=_artifact_id(
                "CANDIDATE-SELECTION-", payload.selection.selection_hash
            ),
            filename="candidate_selection_provenance.json",
            input_hash=payload.selection.selection_hash,
            revision=payload.candidate_cad.artifact.bound_revision,
            state_hash=payload.candidate_cad.artifact.bound_state_hash,
        )
        selection_scope = (verified.project_id, verified.run_id, verified.task_id)
        for label, reference in (
            ("candidate CAD reference", payload.candidate_cad),
            ("candidate evaluation reference", payload.evaluation),
            ("candidate comparison reference", payload.comparison),
        ):
            if reference is not None and (
                reference.artifact.project_id,
                reference.artifact.run_id,
                reference.artifact.task_id,
            ) != selection_scope:
                raise CandidateProvenanceIntegrityError(f"{label} scope mismatch")
        cad = self.resolve_candidate_cad(payload.candidate_cad.artifact)
        evaluated = self.resolve_candidate_evaluation(payload.evaluation.artifact)
        comparison = (
            self.resolve_candidate_comparison(payload.comparison.artifact)
            if payload.comparison is not None
            else None
        )
        self._validate_selection(payload.selection, cad, evaluated, comparison)
        return CandidateSelectionProvenancePublication(
            artifact=verified, payload=payload
        )

    def _resolve_candidate_selection_v2(
        self, verified: EngineeringArtifact, content: bytes
    ) -> CandidateSelectionProvenancePublication:
        try:
            payload = CandidateSelectionProvenanceV2.model_validate_json(content)
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate selection@2 artifact identity/binding verification failed"
            ) from exc
        if content != _content(payload):
            raise CandidateProvenanceIntegrityError(
                "candidate selection@2 artifact metadata binding mismatch"
            )
        self._require_envelope_metadata(
            verified,
            artifact_id=_artifact_id(
                "CANDIDATE-SELECTION-", payload.selection.selection_hash
            ),
            filename="candidate_selection_provenance.json",
            input_hash=payload.selection.selection_hash,
            revision=payload.candidate_cad.artifact.bound_revision,
            state_hash=payload.candidate_cad.artifact.bound_state_hash,
        )
        selection_scope = (verified.project_id, verified.run_id, verified.task_id)
        for label, reference in (
            ("candidate CAD reference", payload.candidate_cad),
            ("candidate evaluation reference", payload.evaluation),
            ("candidate comparison reference", payload.comparison),
        ):
            if reference is not None and (
                reference.artifact.project_id,
                reference.artifact.run_id,
                reference.artifact.task_id,
            ) != selection_scope:
                raise CandidateProvenanceIntegrityError(
                    f"{label} scope mismatch"
                )
        cad = self.resolve_candidate_cad(payload.candidate_cad.artifact)
        evaluated = self.resolve_candidate_evaluation(payload.evaluation.artifact)
        comparison = (
            self.resolve_candidate_comparison(payload.comparison.artifact)
            if payload.comparison is not None
            else None
        )
        self._validate_selection_v2(payload.selection, cad, evaluated, comparison)
        return CandidateSelectionProvenancePublication(
            artifact=verified, payload=payload
        )

    def validate_selection_for_promotion(
        self, request
    ) -> CandidateSelectionProvenancePublication:
        """Resolve the durable selected-candidate chain before promotion mutates state."""
        from .promotion_models import CandidatePromotionRequest, CandidatePromotionRequestV2, _hash

        if type(request) is CandidatePromotionRequestV2:
            return self.validate_selection_for_promotion_v2(request)

        if type(request) is not CandidatePromotionRequest:
            raise CandidateProvenanceIntegrityError(
                "promotion provenance preflight requires the exact typed request"
            )
        selection = self.resolve_candidate_selection(
            _artifact_id("CANDIDATE-SELECTION-", request.selection.selection_hash)
        )
        selected = selection.payload.selection
        if (
            selection.artifact.project_id != request.project_id
            or selection.artifact.bound_revision != request.source_revision
            or selection.artifact.bound_state_hash != request.source_state_hash
            or selected.selection_hash != request.selection.selection_hash
            or selected.candidate_hash != request.candidate.candidate_hash
            or selected.evaluation_hash != request.evaluation.evaluation_hash
            or selected.source_binding_hash
            != _hash(request.candidate.source_binding)
            or selected.comparison_used != request.comparison_used
            or selected.comparison_result_hash
            != (
                None
                if request.comparison is None
                else request.comparison.result_hash
            )
        ):
            raise CandidateProvenanceIntegrityError(
                "durable candidate selection does not match promotion request"
            )
        return selection

    def validate_selection_for_promotion_v2(
        self, request
    ) -> CandidateSelectionProvenancePublication:
        """Resolve and revalidate the typed @2 candidate/evaluation/selection parent chain."""
        from .promotion_models import CandidatePromotionRequestV2

        if type(request) is not CandidatePromotionRequestV2:
            raise CandidateProvenanceIntegrityError(
                "promotion@2 provenance preflight requires exact request@2"
            )
        try:
            request = CandidatePromotionRequestV2.model_validate(
                request.model_dump(mode="json")
            )
            selection_publication = self.resolve_candidate_selection(
                _artifact_id("CANDIDATE-SELECTION-", request.selection_hash)
            )
            if (
                type(selection_publication.payload)
                is not CandidateSelectionProvenanceV2
            ):
                raise CandidateProvenanceIntegrityError(
                    "promotion@2 requires selection provenance@2"
                )
            selection = selection_publication.payload.selection
            cad = self.resolve_candidate_cad(
                selection_publication.payload.candidate_cad.artifact
            )
            evaluation_publication = self.resolve_candidate_evaluation(
                selection_publication.payload.evaluation.artifact
            )
            if type(evaluation_publication.payload) is not CandidateEvaluationProvenanceV2:
                raise CandidateProvenanceIntegrityError(
                    "promotion@2 requires evaluation provenance@2"
                )
            candidate, synthesis_request, synthesis_policy = self._candidate_from_cad(
                cad
            )
            if (
                candidate.schema_version != "mechanical-design-candidate@2"
                or synthesis_request.schema_version != "candidate-synthesis-request@2"
                or candidate.source_binding != synthesis_request.source_binding
                or candidate.semantic_source_binding_hash
                != synthesis_request.semantic_source_binding_hash
                or candidate.synthesis_request_hash != synthesis_request.request_hash
            ):
                raise CandidateProvenanceIntegrityError(
                    "promotion@2 candidate/request typed parent mismatch"
                )
            try:
                resolved_candidate = self.candidate_publication_service.resolve(
                    cad.payload.candidate_artifact.artifact.artifact_id,
                    exact_source_artifacts=cad.payload.source_step_artifacts,
                )
                verify_candidate_semantic_binding(
                    resolved_candidate.candidate,
                    synthesis_request,
                    state_manager=self.state_manager,
                    store=self.candidate_publication_service.store,
                    project_id=self.project_id,
                    exact_source_artifacts=cad.payload.source_step_artifacts,
                )
            except Exception as exc:
                raise CandidateProvenanceIntegrityError(
                    "promotion@2 candidate semantic restart verification failed"
                ) from exc
            evaluation = evaluation_publication.payload.evaluation
            if (
                request.project_id != self.project_id
                or request.source_revision != candidate.source_binding.source_revision
                or request.source_state_hash != candidate.source_binding.source_state_hash
                or request.candidate_hash != candidate.candidate_hash
                or request.synthesis_request_hash != synthesis_request.request_hash
                or request.synthesis_policy_hash != synthesis_policy.policy_hash
                or request.m12_3_result_hash != evaluation.m12_3_result_hash
                or request.evaluation_hash != evaluation.evaluation_hash
                or request.selection_hash != selection.selection_hash
                or selection.candidate_hash != candidate.candidate_hash
                or selection.evaluation_hash != evaluation.evaluation_hash
                or selection.source_binding_hash
                != candidate.semantic_source_binding_hash
                or selection.evaluation_scope_hash != evaluation.evaluation_scope_hash
                or selection.comparison_used != request.comparison_used
                or selection.comparison_result_hash != request.comparison_result_hash
            ):
                raise CandidateProvenanceIntegrityError(
                    "promotion@2 request does not match the resolved typed parent chain"
                )
            if request.comparison_used:
                comparison_reference = selection_publication.payload.comparison
                if comparison_reference is None:
                    raise CandidateProvenanceIntegrityError(
                        "promotion@2 comparison parent is missing"
                    )
                comparison_publication = self.resolve_candidate_comparison(
                    comparison_reference.artifact
                )
                if type(comparison_publication.payload) is not CandidateComparisonProvenanceV2:
                    raise CandidateProvenanceIntegrityError(
                        "promotion@2 requires comparison provenance@2"
                    )
                comparison = comparison_publication.payload
                expected_entries = tuple(
                    sorted(comparison.request.candidate_evaluation_pairs)
                )
                if (
                    comparison.request.request_hash != request.comparison_request_hash
                    or comparison.result.result_hash != request.comparison_result_hash
                    or tuple(sorted(request.comparison_entry_hashes))
                    != expected_entries
                ):
                    raise CandidateProvenanceIntegrityError(
                        "promotion@2 comparison request/result identity mismatch"
                    )
            elif any(
                value is not None
                for value in (
                    selection_publication.payload.comparison,
                    request.comparison_request_hash,
                    request.comparison_result_hash,
                )
            ):
                raise CandidateProvenanceIntegrityError(
                    "promotion@2 unused comparison has a persisted parent"
                )
            return selection_publication
        except CandidateProvenanceIntegrityError:
            raise
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "promotion@2 typed parent preflight failed"
            ) from exc

    def resolve_selection_for_promotion(
        self, *, decision, result_manifest
    ) -> CandidateSelectionProvenancePublication:
        """Resolve the exact selected-candidate chain referenced by promotion."""
        from .promotion_artifacts import (
            CandidatePromotionResultManifest,
            SelectedCandidateDecisionManifest,
        )

        if type(decision) is not SelectedCandidateDecisionManifest:
            raise CandidateProvenanceIntegrityError(
                "promotion decision must be the exact typed manifest"
            )
        if type(result_manifest) is not CandidatePromotionResultManifest:
            raise CandidateProvenanceIntegrityError(
                "promotion result must be the exact typed manifest"
            )
        reference = decision.input_reference
        if reference.project_id != self.project_id:
            raise CandidateProvenanceIntegrityError(
                "promotion selection project binding mismatch"
            )
        expected_id = _artifact_id(
            "CANDIDATE-SELECTION-", reference.selection_hash
        )
        verified, _ = self._resolve_top_level(expected_id, label="promotion selection")
        if (
            verified.artifact_id != expected_id
            or verified.project_id != reference.project_id
            or verified.input_hash != reference.selection_hash
            or (verified.bound_revision, verified.bound_state_hash)
            != (reference.base_revision, reference.base_state_hash)
        ):
            raise CandidateProvenanceIntegrityError(
                "promotion selection artifact binding mismatch"
            )
        publication = self.resolve_candidate_selection(verified)
        selection = publication.payload.selection
        if (
            selection.selection_hash != reference.selection_hash
            or selection.candidate_hash != reference.candidate_hash
            or selection.evaluation_hash != reference.evaluation_hash
            or selection.comparison_used != reference.comparison_used
            or selection.comparison_result_hash != reference.comparison_result_hash
        ):
            raise CandidateProvenanceIntegrityError(
                "promotion selection semantic binding mismatch"
            )
        dependencies = (
            publication.payload.candidate_cad.artifact,
            publication.payload.evaluation.artifact,
        ) + (
            (publication.payload.comparison.artifact,)
            if publication.payload.comparison is not None
            else ()
        )
        if any(
            (dependency.project_id, dependency.run_id, dependency.task_id)
            != (verified.project_id, verified.run_id, verified.task_id)
            for dependency in dependencies
        ):
            raise CandidateProvenanceIntegrityError(
                "promotion selection execution scope mismatch"
            )
        return publication

    def resolve_promoted_candidate_chain(
        self, *, decision, result_manifest
    ) -> CandidateSelectionProvenancePublication:
        """Resolve the durable selected-candidate chain for promotion verification."""
        return self.resolve_selection_for_promotion(
            decision=decision, result_manifest=result_manifest
        )

    def resolve_promotion_chain(
        self,
        *,
        decision_artifact_id: str,
        decision_artifact_hash: str,
        result_artifact_id: str,
        result_artifact_hash: str,
        selection_artifact_id: str,
        selection_artifact_hash: str,
        canonical_m10_artifact_id: str,
        canonical_m10_artifact_hash: str,
    ):
        """Reconstruct the durable promotion chain from scalar artifact locators."""
        from types import SimpleNamespace

        from .promotion_artifacts import PromotionManifestService

        def resolve_locator(artifact_id: str, artifact_hash: str, label: str):
            try:
                artifact = ArtifactStore(
                    self.workspace,
                    project_id=self.project_id,
                    run_id="LOOKUP",
                ).read_verified_in_project(
                    artifact_id,
                    expected_type=ArtifactType.JSON,
                    expected_hash=artifact_hash,
                )
            except Exception as exc:
                raise CandidateProvenanceIntegrityError(
                    f"{label} artifact is missing or ambiguous"
                ) from exc
            if artifact is None:
                raise CandidateProvenanceIntegrityError(
                    f"{label} artifact is missing or ambiguous"
                )
            verified, _content = artifact
            return verified

        decision_artifact = resolve_locator(
            decision_artifact_id, decision_artifact_hash, "promotion decision"
        )
        decision_store = ArtifactStore(
            self.workspace,
            project_id=self.project_id,
            run_id=decision_artifact.run_id,
            task_id=decision_artifact.task_id,
        )
        try:
            decision = PromotionManifestService().resolve_decision(
                decision_store, decision_artifact.artifact_id
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "promotion decision artifact verification failed"
            ) from exc
        if decision.project_id != self.project_id:
            raise CandidateProvenanceIntegrityError(
                "promotion decision project mismatch"
            )

        result_artifact = resolve_locator(
            result_artifact_id, result_artifact_hash, "promotion result"
        )
        result_store = ArtifactStore(
            self.workspace,
            project_id=self.project_id,
            run_id=result_artifact.run_id,
            task_id=result_artifact.task_id,
        )
        try:
            result_manifest = PromotionManifestService().resolve_result(
                result_store, result_artifact.artifact_id
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "promotion result artifact verification failed"
            ) from exc
        if (
            result_manifest.decision_artifact_id != decision_artifact.artifact_id
            or result_manifest.decision_artifact_hash != decision_artifact.sha256
            or result_manifest.promotion_proposal_hash != decision.promotion_proposal_hash
            or result_manifest.mechanism_path
            != f"/physical_mechanisms/{decision.projection.canonical_target_mechanism_id}"
        ):
            raise CandidateProvenanceIntegrityError(
                "promotion result semantic binding mismatch"
            )

        selection_artifact = resolve_locator(
            selection_artifact_id, selection_artifact_hash, "promotion selection"
        )
        selection = self.resolve_candidate_selection(selection_artifact)
        if (
            (selection_artifact.bound_revision, selection_artifact.bound_state_hash)
            != (decision.base_revision, decision.base_state_hash)
            or selection.payload.selection.selection_hash
            != decision.input_reference.selection_hash
            or selection.payload.selection.candidate_hash
            != decision.input_reference.candidate_hash
            or selection.payload.selection.evaluation_hash
            != decision.input_reference.evaluation_hash
            or selection.payload.selection.comparison_used
            != decision.input_reference.comparison_used
            or selection.payload.selection.comparison_result_hash
            != decision.input_reference.comparison_result_hash
        ):
            raise CandidateProvenanceIntegrityError(
                "promotion selection semantic binding mismatch"
            )

        canonical_m10_artifact = resolve_locator(
            canonical_m10_artifact_id,
            canonical_m10_artifact_hash,
            "canonical M10",
        )
        canonical_m10 = self.resolve_canonical_m10(canonical_m10_artifact)
        if (
            canonical_m10.payload.outcome.project_id != decision.project_id
            or canonical_m10.payload.outcome.mechanism_id
            != decision.projection.canonical_target_mechanism_id
            or (
                canonical_m10.payload.outcome.revision,
                canonical_m10.payload.outcome.state_hash,
            )
            != (
                result_manifest.resulting_revision,
                result_manifest.resulting_state_hash,
            )
        ):
            raise CandidateProvenanceIntegrityError(
                "canonical M10 promotion binding mismatch"
            )
        candidate_cad = self.resolve_candidate_cad(
            selection.payload.candidate_cad.artifact
        )
        evaluation = self.resolve_candidate_evaluation(
            selection.payload.evaluation.artifact
        )
        comparison = (
            self.resolve_candidate_comparison(selection.payload.comparison.artifact)
            if selection.payload.comparison is not None
            else None
        )
        candidate_publication, _, _ = self._candidate_publication_context(candidate_cad)
        canonical_cad = self.resolve_canonical_cad(
            canonical_m10.payload.canonical_cad.artifact
        )
        return SimpleNamespace(
            decision=decision,
            decision_artifact=decision_artifact,
            result_artifact=result_artifact,
            result_manifest=result_manifest,
            selection=selection,
            comparison=comparison,
            evaluation=evaluation,
            candidate_cad=candidate_cad,
            candidate_publication=candidate_publication,
            canonical_cad=canonical_cad,
            canonical_m10=canonical_m10,
        )

    def publish_promotion_chain_locator(
        self,
        store: ArtifactStore,
        *,
        decision_artifact_id: str,
        result_artifact_id: str,
        selection: CandidateSelectionProvenancePublication,
        candidate_cad: CandidateCadProvenancePublication,
        canonical_cad: CanonicalCadProvenancePublication,
        canonical_m10: CanonicalM10ProvenancePublication,
        verification_hash: str,
    ) -> PromotionChainLocatorPublication:
        """Publish the production-owned restart root after VERIFIED validation.

        The locator lives in the promotion run scope alongside the protected
        decision/result manifests. Protected manifest bytes and semantic hashes
        are never modified; the locator carries its own identity.
        """
        from .promotion_artifacts import PromotionManifestService

        if store.project_id != self.project_id:
            raise CandidateProvenanceIntegrityError(
                "chain locator store project mismatch"
            )
        try:
            decision = PromotionManifestService().resolve_decision(
                store, decision_artifact_id
            )
            result_manifest = PromotionManifestService().resolve_result(
                store, result_artifact_id
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "chain locator manifest resolution failed"
            ) from exc
        try:
            decision_artifact, _ = store.read_verified_strict(
                decision_artifact_id, expected_type=ArtifactType.JSON
            )
            result_artifact, _ = store.read_verified_strict(
                result_artifact_id, expected_type=ArtifactType.JSON
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "chain locator manifest artifact verification failed"
            ) from exc
        if (
            result_manifest.decision_artifact_id != decision_artifact.artifact_id
            or result_manifest.decision_artifact_hash != decision_artifact.sha256
            or (store.run_id, decision_artifact.run_id, result_artifact.run_id)
            != (store.run_id, store.run_id, store.run_id)
        ):
            raise CandidateProvenanceIntegrityError(
                "chain locator manifest binding mismatch"
            )
        selection = _reparse(CandidateSelectionProvenancePublication, selection)
        if selection.artifact.project_id != self.project_id:
            raise CandidateProvenanceIntegrityError(
                "chain locator selection project mismatch"
            )
        reference = decision.input_reference
        selected = selection.payload.selection
        if (
            selection.artifact.input_hash != selected.selection_hash
            or selected.selection_hash != reference.selection_hash
            or selected.candidate_hash != reference.candidate_hash
            or selected.evaluation_hash != reference.evaluation_hash
            or selected.comparison_used != reference.comparison_used
            or selected.comparison_result_hash != reference.comparison_result_hash
            or (selection.artifact.bound_revision, selection.artifact.bound_state_hash)
            != (decision.base_revision, decision.base_state_hash)
        ):
            raise CandidateProvenanceIntegrityError(
                "chain locator selection binding mismatch"
            )
        comparison_reference = selection.payload.comparison
        if (comparison_reference is None) != (reference.comparison_used is False):
            raise CandidateProvenanceIntegrityError(
                "chain locator comparison binding mismatch"
            )
        canonical_m10 = _reparse(CanonicalM10ProvenancePublication, canonical_m10)
        if (
            canonical_m10.payload.outcome.project_id != self.project_id
            or canonical_m10.payload.outcome.mechanism_id
            != decision.projection.canonical_target_mechanism_id
            or (
                canonical_m10.payload.outcome.revision,
                canonical_m10.payload.outcome.state_hash,
            )
            != (
                result_manifest.resulting_revision,
                result_manifest.resulting_state_hash,
            )
        ):
            raise CandidateProvenanceIntegrityError(
                "chain locator canonical M10 promotion binding mismatch"
            )
        canonical_cad = _reparse(CanonicalCadProvenancePublication, canonical_cad)
        if canonical_cad.artifact != canonical_m10.payload.canonical_cad.artifact:
            raise CandidateProvenanceIntegrityError(
                "chain locator canonical CAD binding mismatch"
            )
        candidate_cad = _reparse(CandidateCadProvenancePublication, candidate_cad)
        if candidate_cad.artifact != selection.payload.candidate_cad.artifact:
            raise CandidateProvenanceIntegrityError(
                "chain locator candidate CAD binding mismatch"
            )
        evaluation_reference = selection.payload.evaluation.artifact
        payload = PromotionChainLocator(
            project_id=self.project_id,
            base_revision=decision.base_revision,
            base_state_hash=decision.base_state_hash,
            resulting_revision=result_manifest.resulting_revision,
            resulting_state_hash=result_manifest.resulting_state_hash,
            canonical_target_mechanism_id=decision.projection.canonical_target_mechanism_id,
            decision_artifact_id=decision_artifact.artifact_id,
            decision_artifact_hash=decision_artifact.sha256,
            result_artifact_id=result_artifact.artifact_id,
            result_artifact_hash=result_artifact.sha256,
            result_hash=result_manifest.result_hash,
            selection_artifact_id=selection.artifact.artifact_id,
            selection_artifact_hash=selection.artifact.sha256,
            selection_hash=selected.selection_hash,
            comparison_artifact_id=(
                None
                if comparison_reference is None
                else comparison_reference.artifact.artifact_id
            ),
            comparison_artifact_hash=(
                None
                if comparison_reference is None
                else comparison_reference.artifact.sha256
            ),
            comparison_result_hash=selected.comparison_result_hash,
            evaluation_artifact_id=evaluation_reference.artifact_id,
            evaluation_artifact_hash=evaluation_reference.sha256,
            evaluation_hash=selected.evaluation_hash,
            candidate_cad_artifact_id=candidate_cad.artifact.artifact_id,
            candidate_cad_artifact_hash=candidate_cad.artifact.sha256,
            candidate_cad_realization_hash=candidate_cad.payload.realization.realization_hash,
            canonical_cad_artifact_id=canonical_cad.artifact.artifact_id,
            canonical_cad_artifact_hash=canonical_cad.artifact.sha256,
            canonical_cad_realization_hash=canonical_cad.payload.realization.realization_hash,
            canonical_m10_artifact_id=canonical_m10.artifact.artifact_id,
            canonical_m10_artifact_hash=canonical_m10.artifact.sha256,
            canonical_m10_outcome_hash=canonical_m10.payload.outcome.outcome_hash,
            verification_hash=_locator_hash(verification_hash),
        )
        artifact = store.publish(
            _artifact_id(_CHAIN_LOCATOR_PREFIX, payload.result_hash),
            ArtifactType.JSON,
            _CHAIN_LOCATOR_FILENAME,
            _content(payload),
            _PRODUCER_NAME,
            _PRODUCER_VERSION,
            payload.resulting_revision,
            payload.resulting_state_hash,
            input_hash=payload.locator_hash,
        )
        return self.resolve_root_locator(artifact)

    def resolve_root_locator(
        self, artifact: EngineeringArtifact | str
    ) -> PromotionChainLocatorPublication:
        """Strictly reload one production-owned chain locator."""
        verified, content = self._resolve_top_level(artifact, label="chain locator")
        try:
            payload = PromotionChainLocator.model_validate_json(content)
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "chain locator artifact identity/binding verification failed"
            ) from exc
        if content != _content(payload):
            raise CandidateProvenanceIntegrityError(
                "chain locator artifact metadata binding mismatch"
            )
        if verified.project_id != self.project_id or payload.project_id != self.project_id:
            raise CandidateProvenanceIntegrityError("chain locator project mismatch")
        if payload.status != "verified":
            raise CandidateProvenanceIntegrityError(
                "chain locator is not a verified completeness record"
            )
        self._require_envelope_metadata(
            verified,
            artifact_id=_artifact_id(_CHAIN_LOCATOR_PREFIX, payload.result_hash),
            filename=_CHAIN_LOCATOR_FILENAME,
            input_hash=payload.locator_hash,
            revision=payload.resulting_revision,
            state_hash=payload.resulting_state_hash,
        )
        return PromotionChainLocatorPublication(artifact=verified, payload=payload)

    def locate_published_chain_locator(
        self, result_artifact_id: str
    ) -> PromotionChainLocatorPublication:
        """Find the production-owned locator for one promotion result artifact."""
        try:
            located = ArtifactStore(
                self.workspace,
                project_id=self.project_id,
                run_id="LOOKUP",
            ).read_verified_in_project(
                result_artifact_id, expected_type=ArtifactType.JSON
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "promotion result artifact is missing or ambiguous"
            ) from exc
        if located is None:
            raise CandidateProvenanceIntegrityError(
                "promotion result artifact is missing or ambiguous"
            )
        result_artifact, _ = located
        result_store = ArtifactStore(
            self.workspace,
            project_id=self.project_id,
            run_id=result_artifact.run_id,
            task_id=result_artifact.task_id,
        )
        try:
            from .promotion_artifacts import PromotionManifestService

            result_manifest = PromotionManifestService().resolve_result(
                result_store, result_artifact.artifact_id
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "promotion result artifact verification failed"
            ) from exc
        root_id = _artifact_id(_CHAIN_LOCATOR_PREFIX, result_manifest.result_hash)
        try:
            located_root = ArtifactStore(
                self.workspace,
                project_id=self.project_id,
                run_id="LOOKUP",
            ).read_verified_in_project(root_id, expected_type=ArtifactType.JSON)
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "chain locator artifact is missing or ambiguous"
            ) from exc
        if located_root is None:
            raise CandidateProvenanceIntegrityError(
                "chain locator artifact is missing or ambiguous"
            )
        publication = self.resolve_root_locator(located_root[0])
        if (
            publication.payload.result_artifact_id != result_artifact.artifact_id
            or publication.payload.result_artifact_hash != result_artifact.sha256
            or publication.payload.result_hash != result_manifest.result_hash
        ):
            raise CandidateProvenanceIntegrityError(
                "chain locator result binding mismatch"
            )
        return publication

    def resolve_promotion_chain_from_root(
        self, root_artifact_id: str, root_artifact_hash: str
    ):
        """Reconstruct the full chain from the production-owned root only."""
        try:
            located = ArtifactStore(
                self.workspace,
                project_id=self.project_id,
                run_id="LOOKUP",
            ).read_verified_in_project(
                root_artifact_id,
                expected_type=ArtifactType.JSON,
                expected_hash=root_artifact_hash,
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "chain locator artifact is missing or ambiguous"
            ) from exc
        if located is None:
            raise CandidateProvenanceIntegrityError(
                "chain locator artifact is missing or ambiguous"
            )
        root = self.resolve_root_locator(located[0])
        locator = root.payload
        if (
            root.artifact.artifact_id != root_artifact_id
            or root.artifact.sha256 != root_artifact_hash
        ):
            raise CandidateProvenanceIntegrityError(
                "chain locator artifact binding mismatch"
            )
        chain = self.resolve_promotion_chain(
            decision_artifact_id=locator.decision_artifact_id,
            decision_artifact_hash=locator.decision_artifact_hash,
            result_artifact_id=locator.result_artifact_id,
            result_artifact_hash=locator.result_artifact_hash,
            selection_artifact_id=locator.selection_artifact_id,
            selection_artifact_hash=locator.selection_artifact_hash,
            canonical_m10_artifact_id=locator.canonical_m10_artifact_id,
            canonical_m10_artifact_hash=locator.canonical_m10_artifact_hash,
        )
        if (
            chain.decision.input_reference.selection_hash != locator.selection_hash
            or chain.selection.payload.selection.selection_hash != locator.selection_hash
            or chain.evaluation.payload.evaluation.evaluation_hash != locator.evaluation_hash
            or chain.evaluation.artifact.artifact_id != locator.evaluation_artifact_id
            or chain.evaluation.artifact.sha256 != locator.evaluation_artifact_hash
            or chain.candidate_cad.artifact.artifact_id != locator.candidate_cad_artifact_id
            or chain.candidate_cad.artifact.sha256 != locator.candidate_cad_artifact_hash
            or chain.candidate_cad.payload.realization.realization_hash
            != locator.candidate_cad_realization_hash
            or chain.canonical_cad.artifact.artifact_id != locator.canonical_cad_artifact_id
            or chain.canonical_cad.artifact.sha256 != locator.canonical_cad_artifact_hash
            or chain.canonical_cad.payload.realization.realization_hash
            != locator.canonical_cad_realization_hash
            or chain.canonical_m10.artifact.artifact_id != locator.canonical_m10_artifact_id
            or chain.canonical_m10.artifact.sha256 != locator.canonical_m10_artifact_hash
            or chain.canonical_m10.payload.outcome.outcome_hash
            != locator.canonical_m10_outcome_hash
        ):
            raise CandidateProvenanceIntegrityError(
                "chain locator semantic binding mismatch"
            )
        if (chain.comparison is None) != (locator.comparison_artifact_id is None):
            raise CandidateProvenanceIntegrityError(
                "chain locator comparison presence mismatch"
            )
        if chain.comparison is not None and (
            chain.comparison.payload.result.result_hash != locator.comparison_result_hash
            or chain.comparison.artifact.artifact_id != locator.comparison_artifact_id
            or chain.comparison.artifact.sha256 != locator.comparison_artifact_hash
        ):
            raise CandidateProvenanceIntegrityError(
                "chain locator comparison binding mismatch"
            )
        return chain

    def _validate_canonical_state(
        self, project_id: str, revision: int, expected_state_hash: str, label: str
    ) -> None:
        try:
            state = self.state_manager.load_revision(project_id, revision)
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                f"{label} source state is missing"
            ) from exc
        if state.revision != revision or state_hash(state) != expected_state_hash:
            raise CandidateProvenanceIntegrityError(f"{label} source state mismatch")

    def _require_canonical_mechanism_identity(
        self,
        cad: CanonicalCadRealization,
        reconstruction: CanonicalMechanismReconstruction | None = None,
    ) -> None:
        if reconstruction is not None:
            try:
                reconstruction = CanonicalMechanismReconstruction.model_validate(
                    reconstruction.model_dump(mode="json")
                )
                mechanism = validate_canonical_mechanism(
                    reconstruction.canonical_mechanism
                )
                state = self.state_manager.load_revision(
                    reconstruction.project_id, reconstruction.revision
                )
                if (
                    state.revision != reconstruction.revision
                    or state_hash(state) != reconstruction.state_hash
                ):
                    raise ValueError("canonical reconstruction source state mismatch")
                mechanisms = tuple(
                    candidate
                    for candidate in state.physical_mechanisms
                    if candidate.id == mechanism.id
                )
                if len(mechanisms) != 1:
                    raise ValueError("canonical reconstruction mechanism is missing or ambiguous")
                bound_mechanism = validate_canonical_mechanism(mechanisms[0])
                if (
                    bound_mechanism.id != mechanism.id
                    or bound_mechanism.mechanism_hash != mechanism.mechanism_hash
                    or bound_mechanism != mechanism
                ):
                    raise ValueError("canonical reconstruction mechanism identity mismatch")
            except Exception as exc:
                raise CandidateProvenanceIntegrityError(
                    "canonical CAD reconstruction binding mismatch"
                ) from exc
            if (
                reconstruction.project_id != cad.project_id
                or reconstruction.revision != cad.revision
                or reconstruction.state_hash != cad.state_hash
            ):
                raise CandidateProvenanceIntegrityError(
                    "canonical CAD reconstruction binding mismatch"
                )
        else:
            try:
                state = self.state_manager.load_revision(cad.project_id, cad.revision)
                mechanisms = tuple(
                    mechanism
                    for mechanism in state.physical_mechanisms
                    if mechanism.id == cad.mechanism_id
                )
                if len(mechanisms) != 1:
                    raise ValueError("canonical mechanism is missing or ambiguous")
                mechanism = validate_canonical_mechanism(mechanisms[0])
            except Exception as exc:
                raise CandidateProvenanceIntegrityError(
                    "canonical CAD bound mechanism is missing or invalid"
                ) from exc

        if (
            mechanism.id != cad.mechanism_id
            or mechanism.mechanism_hash != cad.mechanism_hash
        ):
            raise CandidateProvenanceIntegrityError(
                "canonical CAD mechanism hash/identity mismatch"
            )

    def _canonical_source_artifacts(
        self,
        cad: CanonicalCadRealization,
        trusted_source_references: tuple[TrustedSourceArtifact, ...] | None = None,
    ) -> tuple[EngineeringArtifact, ...]:
        canonical_provenance = tuple(cad.selected_source_provenance)
        if trusted_source_references is None:
            expected_provenance = canonical_provenance
        else:
            trusted_source_references = tuple(trusted_source_references)
            if _canonical_source_bindings(trusted_source_references) != _canonical_source_bindings(
                canonical_provenance
            ):
                raise CandidateProvenanceIntegrityError(
                    "canonical source provenance does not match exact promotion snapshots"
                )
            trusted_by_id = {
                source.artifact_id: source for source in trusted_source_references
            }
            expected_provenance = tuple(
                trusted_by_id[source.artifact_id] for source in canonical_provenance
            )
        sources = tuple(
            EngineeringArtifact.model_validate(
                source.model_dump(mode="json", exclude={"schema_version"})
            )
            for source in expected_provenance
        )
        if (
            tuple(source.artifact_id for source in sources)
            != cad.selected_source_artifact_ids
        ):
            raise CandidateProvenanceIntegrityError(
                "canonical CAD selected source identity mismatch"
            )
        verified_sources = []
        for expected, source in zip(expected_provenance, sources):
            try:
                verified = _reopen_verified_artifact(
                    self.workspace,
                    source,
                    expected_type=ArtifactType.STEP,
                    label="canonical source STEP artifact",
                )
                if (
                    TrustedSourceArtifact.from_artifact(verified) != expected
                    or verified.sha256 != expected.sha256
                ):
                    raise CandidateProvenanceIntegrityError(
                        "canonical source STEP provenance snapshot mismatch"
                    )
            except CandidateProvenanceIntegrityError:
                raise
            except Exception as exc:
                raise CandidateProvenanceIntegrityError(
                    "canonical source STEP provenance verification failed"
                ) from exc
            verified_sources.append(verified)
        return tuple(verified_sources)

    def _canonical_resolver(
        self,
        project_id: str,
        source_references: tuple[TrustedSourceArtifact, ...] = (),
    ) -> ProjectArtifactResolver:
        if source_references:
            return ExactSourceArtifactResolver(
                self.workspace, project_id, source_references
            )
        return ProjectArtifactResolver(
            ArtifactStore(self.workspace, project_id=project_id, run_id="LOOKUP")
        )

    def _reconstruct_canonical_cad_source(
        self,
        cad: CanonicalCadRealization,
        trusted_source_references: tuple[TrustedSourceArtifact, ...] | None = None,
    ) -> CanonicalMechanismReconstruction:
        source_references = tuple(
            cad.selected_source_provenance
            if trusted_source_references is None
            else trusted_source_references
        )
        try:
            return CanonicalPhysicalMechanismCompiler(
                self.state_manager,
                self._canonical_resolver(
                    cad.project_id, source_references
                ),
            ).reconstruct(
                cad.project_id,
                cad.revision,
                cad.state_hash,
                cad.mechanism_id,
                trusted_source_references=source_references,
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "canonical CAD reconstruction verification failed"
            ) from exc

    def _require_fresh_canonical_cad(
        self,
        cad: CanonicalCadRealization,
        reconstruction: CanonicalMechanismReconstruction,
        trusted_source_references: tuple[TrustedSourceArtifact, ...] | None = None,
    ) -> None:
        source_references = tuple(
            cad.selected_source_provenance
            if trusted_source_references is None
            else trusted_source_references
        )
        try:
            fresh = CanonicalPhysicalCadCompiler(
                self._canonical_resolver(
                    reconstruction.project_id,
                    source_references,
                )
            ).realize(
                reconstruction,
                trusted_source_references=source_references,
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "canonical CAD fresh realization failed"
            ) from exc
        if fresh != cad:
            raise CandidateProvenanceIntegrityError(
                "canonical CAD realization does not match fresh canonical reconstruction"
            )

    def publish_canonical_cad(
        self,
        reconstruction_or_cad,
        canonical_cad: CanonicalCadRealization | None = None,
        *,
        trusted_source_references: tuple[TrustedSourceArtifact, ...] | None = None,
    ) -> CanonicalCadProvenancePublication:
        selected_cad = reconstruction_or_cad if canonical_cad is None else canonical_cad
        if getattr(selected_cad, "schema_version", None) == "canonical-cad-realization@2":
            reconstruction = None if canonical_cad is None else reconstruction_or_cad
            return self._publish_canonical_cad_v2(
                reconstruction,
                selected_cad,
                trusted_source_references=trusted_source_references,
            )
        reconstruction = None if canonical_cad is None else reconstruction_or_cad
        canonical_cad = reconstruction_or_cad if canonical_cad is None else canonical_cad
        try:
            cad = CanonicalCadRealization.model_validate(
                canonical_cad.model_dump(mode="json")
            ).validated_canonical_copy()
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "canonical CAD realization integrity validation failed"
            ) from exc
        if cad.project_id != self.project_id:
            raise CandidateProvenanceIntegrityError(
                "canonical CAD artifact project mismatch"
            )
        if trusted_source_references is not None:
            trusted_source_references = tuple(trusted_source_references)
            if _canonical_source_bindings(trusted_source_references) != _canonical_source_bindings(
                cad.selected_source_provenance
            ):
                raise CandidateProvenanceIntegrityError(
                    "canonical source provenance does not match exact promotion snapshots"
                )
        self._validate_canonical_state(
            cad.project_id, cad.revision, cad.state_hash, "canonical CAD"
        )
        if reconstruction is not None:
            try:
                reconstruction = CanonicalMechanismReconstruction.model_validate(
                    reconstruction.model_dump(mode="json")
                )
            except Exception as exc:
                raise CandidateProvenanceIntegrityError(
                    "canonical CAD reconstruction binding mismatch"
                ) from exc
            if (
                reconstruction.project_id != cad.project_id
                or reconstruction.revision != cad.revision
                or reconstruction.state_hash != cad.state_hash
                or reconstruction.mechanism.id != cad.mechanism_id
            ):
                raise CandidateProvenanceIntegrityError(
                    "canonical CAD reconstruction binding mismatch"
                )
            self._require_canonical_mechanism_identity(cad, reconstruction)
        else:
            self._require_canonical_mechanism_identity(cad)
            reconstruction = self._reconstruct_canonical_cad_source(cad)
        sources = self._canonical_source_artifacts(
            cad, trusted_source_references=trusted_source_references
        )
        self._require_fresh_canonical_cad(
            cad,
            reconstruction,
            trusted_source_references=trusted_source_references,
        )
        payload = CanonicalCadProvenance(
            realization=cad,
            source_step_artifacts=sources,
        )
        artifact = ArtifactStore(
            self.workspace,
            project_id=self.project_id,
            run_id=_CANONICAL_PROVENANCE_RUN_ID,
        ).publish(
            _artifact_id("CANONICAL-CAD-", cad.realization_hash),
            ArtifactType.JSON,
            _CANONICAL_CAD_FILENAME,
            _content(payload),
            _PRODUCER_NAME,
            _PRODUCER_VERSION,
            cad.revision,
            cad.state_hash,
            input_hash=cad.realization_hash,
        )
        if (artifact.project_id, artifact.run_id, artifact.task_id) != (
            self.project_id,
            _CANONICAL_PROVENANCE_RUN_ID,
            None,
        ):
            raise CandidateProvenanceIntegrityError(
                "canonical CAD publication scope mismatch"
            )
        return CanonicalCadProvenancePublication(artifact=artifact, payload=payload)

    def _publish_canonical_cad_v2(
        self,
        reconstruction,
        canonical_cad,
        *,
        trusted_source_references=None,
    ):
        from .canonical_cad import CanonicalCadRealizationV2

        try:
            cad = CanonicalCadRealizationV2.model_validate(
                canonical_cad.model_dump(mode="json")
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "canonical CAD@2 realization integrity validation failed"
            ) from exc
        if cad.project_id != self.project_id:
            raise CandidateProvenanceIntegrityError(
                "canonical CAD@2 artifact project mismatch"
            )
        self._validate_canonical_state(cad.project_id, cad.revision, cad.state_hash, "canonical CAD@2")
        if reconstruction is not None:
            try:
                reconstruction = CanonicalMechanismReconstruction.model_validate(
                    reconstruction.model_dump(mode="json")
                )
            except Exception as exc:
                raise CandidateProvenanceIntegrityError(
                    "canonical CAD@2 reconstruction binding mismatch"
                ) from exc
            if (
                reconstruction.project_id != cad.project_id
                or reconstruction.revision != cad.revision
                or reconstruction.state_hash != cad.state_hash
                or reconstruction.mechanism.id != cad.mechanism_id
            ):
                raise CandidateProvenanceIntegrityError(
                    "canonical CAD@2 reconstruction binding mismatch"
                )
            self._require_canonical_mechanism_identity(cad, reconstruction)
        else:
            self._require_canonical_mechanism_identity(cad)
            reconstruction = self._reconstruct_canonical_cad_source(cad)
        sources = self._canonical_source_artifacts(
            cad, trusted_source_references=trusted_source_references
        )
        self._require_fresh_canonical_cad(
            cad,
            reconstruction,
            trusted_source_references=trusted_source_references,
        )
        payload = CanonicalCadProvenanceV2(
            realization=cad,
            source_step_artifacts=sources,
        )
        artifact = ArtifactStore(
            self.workspace,
            project_id=self.project_id,
            run_id=_CANONICAL_PROVENANCE_RUN_ID,
        ).publish(
            _artifact_id("CANONICAL-CAD-V2", cad.realization_hash),
            ArtifactType.JSON,
            "canonical_cad_provenance_v2.json",
            _content(payload),
            _PRODUCER_NAME,
            _PRODUCER_VERSION,
            cad.revision,
            cad.state_hash,
            input_hash=cad.realization_hash,
        )
        return CanonicalCadProvenancePublication(artifact=artifact, payload=payload)

    def resolve_canonical_cad(
        self, artifact: EngineeringArtifact | str
    ) -> CanonicalCadProvenancePublication:
        verified, content = self._resolve_top_level(artifact, label="canonical CAD")
        try:
            if json.loads(content).get("schema_version") == "canonical-cad-provenance@2":
                return self._resolve_canonical_cad_v2(verified, content)
        except CandidateProvenanceIntegrityError:
            raise
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "canonical CAD artifact identity/binding verification failed"
            ) from exc
        try:
            payload = CanonicalCadProvenance.model_validate_json(content)
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "canonical CAD artifact identity/binding verification failed"
            ) from exc
        if content != _content(payload):
            raise CandidateProvenanceIntegrityError(
                "canonical CAD artifact metadata binding mismatch"
            )
        cad = payload.realization
        if cad.project_id != self.project_id:
            raise CandidateProvenanceIntegrityError(
                "canonical CAD artifact project mismatch"
            )
        if (verified.project_id, verified.run_id, verified.task_id) != (
            self.project_id,
            _CANONICAL_PROVENANCE_RUN_ID,
            None,
        ):
            raise CandidateProvenanceIntegrityError(
                "canonical CAD artifact scope mismatch"
            )
        self._require_envelope_metadata(
            verified,
            artifact_id=_artifact_id("CANONICAL-CAD-", cad.realization_hash),
            filename=_CANONICAL_CAD_FILENAME,
            input_hash=cad.realization_hash,
            revision=cad.revision,
            state_hash=cad.state_hash,
        )
        self._validate_canonical_state(
            cad.project_id, cad.revision, cad.state_hash, "canonical CAD"
        )
        self._require_canonical_mechanism_identity(cad)
        self._canonical_source_artifacts(cad)
        reconstruction = self._reconstruct_canonical_cad_source(cad)
        try:
            cad.validated_canonical_copy()
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "canonical CAD realization integrity validation failed"
            ) from exc
        self._require_fresh_canonical_cad(cad, reconstruction)
        return CanonicalCadProvenancePublication(artifact=verified, payload=payload)

    def _resolve_canonical_cad_v2(self, verified, content):
        try:
            payload = CanonicalCadProvenanceV2.model_validate_json(content)
            cad = payload.realization
            if content != _content(payload):
                raise ValueError("canonical CAD@2 canonical bytes mismatch")
            if cad.project_id != self.project_id:
                raise ValueError("canonical CAD@2 project mismatch")
            if (verified.project_id, verified.run_id, verified.task_id) != (
                self.project_id,
                _CANONICAL_PROVENANCE_RUN_ID,
                None,
            ):
                raise ValueError("canonical CAD@2 artifact scope mismatch")
            self._require_envelope_metadata(
                verified,
                artifact_id=_artifact_id("CANONICAL-CAD-V2", cad.realization_hash),
                filename="canonical_cad_provenance_v2.json",
                input_hash=cad.realization_hash,
                revision=cad.revision,
                state_hash=cad.state_hash,
            )
            self._validate_canonical_state(
                cad.project_id, cad.revision, cad.state_hash, "canonical CAD@2"
            )
            self._require_canonical_mechanism_identity(cad)
            sources = self._canonical_source_artifacts(cad)
            if sources != payload.source_step_artifacts:
                raise ValueError("canonical CAD@2 source artifact tuple mismatch")
            reconstruction = self._reconstruct_canonical_cad_source(cad)
            self._require_fresh_canonical_cad(cad, reconstruction)
            return CanonicalCadProvenancePublication(artifact=verified, payload=payload)
        except CandidateProvenanceIntegrityError:
            raise
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "canonical CAD@2 artifact identity/binding verification failed"
            ) from exc

    def publish_canonical_m10(
        self,
        canonical_cad: CanonicalCadProvenancePublication | EngineeringArtifact | str,
        outcome: CanonicalM10VerificationOutcome,
    ) -> CanonicalM10ProvenancePublication:
        if getattr(outcome, "schema_version", None) == "canonical-m10-verification-outcome@2":
            return self._publish_canonical_m10_v2(canonical_cad, outcome)
        cad = self.resolve_canonical_cad(
            canonical_cad.artifact
            if isinstance(canonical_cad, CanonicalCadProvenancePublication)
            else canonical_cad
        )
        try:
            outcome = _reparse(CanonicalM10VerificationOutcome, outcome)
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "canonical M10 outcome integrity validation failed"
            ) from exc
        if outcome.project_id != self.project_id:
            raise CandidateProvenanceIntegrityError(
                "canonical M10 artifact project mismatch"
            )
        if outcome.cad_realization_hash != cad.payload.realization.realization_hash:
            raise CandidateProvenanceIntegrityError(
                "canonical M10 CAD identity mismatch"
            )
        if (
            outcome.mechanism_id != cad.payload.realization.mechanism_id
            or outcome.mechanism_hash != cad.payload.realization.mechanism_hash
        ):
            raise CandidateProvenanceIntegrityError(
                "canonical M10 mechanism identity mismatch"
            )
        cad_binding = (
            cad.payload.realization.revision,
            cad.payload.realization.state_hash,
        )
        if (
            cad_binding
            != (cad.artifact.bound_revision, cad.artifact.bound_state_hash)
            or (outcome.revision, outcome.state_hash) != cad_binding
        ):
            raise CandidateProvenanceIntegrityError(
                "canonical M10 CAD revision/state binding mismatch"
            )
        self._validate_canonical_state(
            outcome.project_id, outcome.revision, outcome.state_hash, "canonical M10"
        )
        try:
            canonical_m10_aggregate_summary(outcome)
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "canonical M10 aggregate proof validation failed"
            ) from exc
        proofs = tuple(
            self._evidence(
                kind="analysis.continuous_clearance_proof",
                request_hash=proof.request_hash,
                result_hash=proof.result_hash,
                revision=outcome.revision,
                state_hash=outcome.state_hash,
            )
            for proof in outcome.pair_proofs
        )
        homes = tuple(
            self._evidence(
                kind="analysis.kinematic_sweep",
                request_hash=check.request_hash,
                result_hash=check.result_hash,
                revision=outcome.revision,
                state_hash=outcome.state_hash,
            )
            for check in outcome.home_exact_checks
        )
        payload = CanonicalM10Provenance(
            outcome=outcome,
            canonical_cad=ArtifactReference(artifact=cad.artifact),
            proof_evidence=proofs,
            home_evidence=homes,
        )
        artifact = ArtifactStore(
            self.workspace,
            project_id=self.project_id,
            run_id=_CANONICAL_PROVENANCE_RUN_ID,
        ).publish(
            _artifact_id("CANONICAL-M10-", outcome.outcome_hash),
            ArtifactType.JSON,
            _CANONICAL_M10_FILENAME,
            _content(payload),
            _PRODUCER_NAME,
            _PRODUCER_VERSION,
            outcome.revision,
            outcome.state_hash,
            input_hash=outcome.outcome_hash,
        )
        if (artifact.project_id, artifact.run_id, artifact.task_id) != (
            self.project_id,
            _CANONICAL_PROVENANCE_RUN_ID,
            None,
        ):
            raise CandidateProvenanceIntegrityError(
                "canonical M10 publication scope mismatch"
            )
        return CanonicalM10ProvenancePublication(artifact=artifact, payload=payload)

    def _publish_canonical_m10_v2(self, canonical_cad, outcome):
        from .canonical_m10 import CanonicalM10VerificationOutcomeV2

        cad = self.resolve_canonical_cad(
            canonical_cad.artifact
            if isinstance(canonical_cad, CanonicalCadProvenancePublication)
            else canonical_cad
        )
        try:
            outcome = CanonicalM10VerificationOutcomeV2.model_validate(
                outcome.model_dump(mode="json")
            )
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "canonical M10@2 outcome integrity validation failed"
            ) from exc
        if type(cad.payload) is not CanonicalCadProvenanceV2:
            raise CandidateProvenanceIntegrityError(
                "canonical M10@2 requires canonical CAD provenance@2"
            )
        cad_realization = cad.payload.realization
        if (
            outcome.project_id != self.project_id
            or outcome.cad_realization_hash != cad_realization.realization_hash
            or outcome.mechanism_hash != cad_realization.mechanism_hash
            or (outcome.revision, outcome.state_hash)
            != (cad_realization.revision, cad_realization.state_hash)
        ):
            raise CandidateProvenanceIntegrityError(
                "canonical M10@2 source binding mismatch"
            )
        self._validate_canonical_state(
            outcome.project_id, outcome.revision, outcome.state_hash, "canonical M10@2"
        )
        proofs = tuple(
            self._evidence(
                kind="analysis.continuous_clearance_proof",
                request_hash=proof.request_hash,
                result_hash=proof.result_hash,
                revision=outcome.revision,
                state_hash=outcome.state_hash,
            )
            for proof in outcome.pair_proofs
        )
        homes = tuple(
            self._evidence(
                kind="analysis.kinematic_sweep",
                request_hash=check.request_hash,
                result_hash=check.result_hash,
                revision=outcome.revision,
                state_hash=outcome.state_hash,
            )
            for check in outcome.home_exact_checks
        )
        payload = CanonicalM10ProvenanceV2(
            outcome=outcome,
            canonical_cad=ArtifactReference(artifact=cad.artifact),
            proof_evidence=proofs,
            home_evidence=homes,
        )
        artifact = ArtifactStore(
            self.workspace,
            project_id=self.project_id,
            run_id=_CANONICAL_PROVENANCE_RUN_ID,
        ).publish(
            _artifact_id("CANONICAL-M10-V2", outcome.outcome_hash),
            ArtifactType.JSON,
            "canonical_m10_provenance_v2.json",
            _content(payload),
            _PRODUCER_NAME,
            _PRODUCER_VERSION,
            outcome.revision,
            outcome.state_hash,
            input_hash=outcome.outcome_hash,
        )
        return CanonicalM10ProvenancePublication(artifact=artifact, payload=payload)

    def resolve_canonical_m10(
        self, artifact: EngineeringArtifact | str
    ) -> CanonicalM10ProvenancePublication:
        verified, content = self._resolve_top_level(artifact, label="canonical M10")
        try:
            if json.loads(content).get("schema_version") == "canonical-m10-provenance@2":
                return self._resolve_canonical_m10_v2(verified, content)
        except CandidateProvenanceIntegrityError:
            raise
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "canonical M10 artifact verification failed"
            ) from exc
        try:
            payload = CanonicalM10Provenance.model_validate_json(content)
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "canonical M10 artifact verification failed: identity/binding mismatch"
            ) from exc
        if content != _content(payload):
            raise CandidateProvenanceIntegrityError(
                "canonical M10 artifact metadata binding mismatch"
            )
        outcome = payload.outcome
        if outcome.project_id != self.project_id:
            raise CandidateProvenanceIntegrityError(
                "canonical M10 artifact project mismatch"
            )
        m10_scope = (verified.project_id, verified.run_id, verified.task_id)
        if m10_scope != (self.project_id, _CANONICAL_PROVENANCE_RUN_ID, None):
            raise CandidateProvenanceIntegrityError(
                "canonical M10 artifact scope mismatch"
            )
        if (
            payload.canonical_cad.artifact.project_id,
            payload.canonical_cad.artifact.run_id,
            payload.canonical_cad.artifact.task_id,
        ) != m10_scope:
            raise CandidateProvenanceIntegrityError(
                "canonical M10 nested CAD reference scope mismatch"
            )
        self._require_envelope_metadata(
            verified,
            artifact_id=_artifact_id("CANONICAL-M10-", outcome.outcome_hash),
            filename=_CANONICAL_M10_FILENAME,
            input_hash=outcome.outcome_hash,
            revision=outcome.revision,
            state_hash=outcome.state_hash,
        )
        self._validate_canonical_state(
            outcome.project_id, outcome.revision, outcome.state_hash, "canonical M10"
        )
        cad = self.resolve_canonical_cad(payload.canonical_cad.artifact)
        if outcome.cad_realization_hash != cad.payload.realization.realization_hash:
            raise CandidateProvenanceIntegrityError(
                "canonical M10 CAD identity mismatch"
            )
        if (
            outcome.mechanism_id != cad.payload.realization.mechanism_id
            or outcome.mechanism_hash != cad.payload.realization.mechanism_hash
        ):
            raise CandidateProvenanceIntegrityError(
                "canonical M10 mechanism identity mismatch"
            )
        cad_binding = (
            cad.payload.realization.revision,
            cad.payload.realization.state_hash,
        )
        if (
            cad_binding
            != (cad.artifact.bound_revision, cad.artifact.bound_state_hash)
            or (outcome.revision, outcome.state_hash) != cad_binding
        ):
            raise CandidateProvenanceIntegrityError(
                "canonical M10 CAD revision/state binding mismatch"
            )
        proofs = tuple(
            self._evidence(
                kind="analysis.continuous_clearance_proof",
                request_hash=proof.request_hash,
                result_hash=proof.result_hash,
                revision=outcome.revision,
                state_hash=outcome.state_hash,
            )
            for proof in outcome.pair_proofs
        )
        homes = tuple(
            self._evidence(
                kind="analysis.kinematic_sweep",
                request_hash=check.request_hash,
                result_hash=check.result_hash,
                revision=outcome.revision,
                state_hash=outcome.state_hash,
            )
            for check in outcome.home_exact_checks
        )
        if (payload.proof_evidence, payload.home_evidence) != (proofs, homes):
            raise CandidateProvenanceIntegrityError(
                "canonical M10 evidence coverage mismatch"
            )
        try:
            canonical_m10_aggregate_summary(outcome)
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "canonical M10 aggregate proof validation failed"
            ) from exc
        return CanonicalM10ProvenancePublication(artifact=verified, payload=payload)

    def _resolve_canonical_m10_v2(self, verified, content):
        try:
            payload = CanonicalM10ProvenanceV2.model_validate_json(content)
            outcome = payload.outcome
            if content != _content(payload):
                raise ValueError("canonical M10@2 canonical bytes mismatch")
            if (verified.project_id, verified.run_id, verified.task_id) != (
                self.project_id,
                _CANONICAL_PROVENANCE_RUN_ID,
                None,
            ):
                raise ValueError("canonical M10@2 artifact scope mismatch")
            self._require_envelope_metadata(
                verified,
                artifact_id=_artifact_id("CANONICAL-M10-V2", outcome.outcome_hash),
                filename="canonical_m10_provenance_v2.json",
                input_hash=outcome.outcome_hash,
                revision=outcome.revision,
                state_hash=outcome.state_hash,
            )
            self._validate_canonical_state(
                outcome.project_id, outcome.revision, outcome.state_hash, "canonical M10@2"
            )
            cad = self.resolve_canonical_cad(payload.canonical_cad.artifact)
            if type(cad.payload) is not CanonicalCadProvenanceV2:
                raise ValueError("canonical M10@2 CAD parent must be provenance@2")
            cad_realization = cad.payload.realization
            if (
                outcome.project_id != self.project_id
                or outcome.project_id != cad_realization.project_id
                or outcome.revision != cad_realization.revision
                or outcome.state_hash != cad_realization.state_hash
            ):
                raise ValueError(
                    "canonical M10@2 CAD parent coordinate binding mismatch"
                )
            if (
                cad_realization.realization_hash != outcome.cad_realization_hash
                or cad_realization.mechanism_hash != outcome.mechanism_hash
            ):
                raise ValueError("canonical M10@2 CAD parent binding mismatch")
            expected_proofs = tuple(
                self._evidence(
                    kind="analysis.continuous_clearance_proof",
                    request_hash=proof.request_hash,
                    result_hash=proof.result_hash,
                    revision=outcome.revision,
                    state_hash=outcome.state_hash,
                )
                for proof in outcome.pair_proofs
            )
            expected_homes = tuple(
                self._evidence(
                    kind="analysis.kinematic_sweep",
                    request_hash=check.request_hash,
                    result_hash=check.result_hash,
                    revision=outcome.revision,
                    state_hash=outcome.state_hash,
                )
                for check in outcome.home_exact_checks
            )
            if (payload.proof_evidence, payload.home_evidence) != (
                expected_proofs,
                expected_homes,
            ):
                raise ValueError("canonical M10@2 evidence coverage mismatch")
            return CanonicalM10ProvenancePublication(artifact=verified, payload=payload)
        except CandidateProvenanceIntegrityError:
            raise
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "canonical M10@2 artifact identity/binding verification failed"
            ) from exc

    def publish_candidate_multi_joint_m10(
        self,
        *,
        request,
        evaluation,
        selection,
        m10_v2_result,
        candidate_cad,
    ):
        """Publish §18B typed MJ parents through the existing candidate artifact scope."""
        from .multi_joint_m10_evaluation import (
            CandidateMultiJointM10EvaluationRequestV2,
            CandidateMultiJointM10EvaluationV2,
        )
        from .multi_joint_selection import CandidateMultiJointSelectionV2

        request = _reparse_exact(CandidateMultiJointM10EvaluationRequestV2, request)
        evaluation = _reparse_exact(CandidateMultiJointM10EvaluationV2, evaluation)
        selection = _reparse_exact(CandidateMultiJointSelectionV2, selection)
        candidate_cad_artifact = (
            candidate_cad.artifact
            if isinstance(candidate_cad, CandidateCadProvenancePublication)
            else candidate_cad
        )
        cad_publication = self.resolve_candidate_cad(candidate_cad_artifact)
        if type(cad_publication.payload) is not CandidateCadProvenanceV2:
            raise CandidateProvenanceIntegrityError(
                "§18B requires candidate CAD provenance@2"
            )
        candidate_reference = cad_publication.payload.candidate_artifact
        payload = CandidateMultiJointM10Provenance(
            request=request,
            evaluation=evaluation,
            selection=selection,
            m10_v2_result=m10_v2_result,
            candidate_publication=candidate_reference,
            candidate_cad=ArtifactReference(artifact=cad_publication.artifact),
        )
        self._verify_candidate_multi_joint_m10_semantics(payload, cad_publication)
        store = ArtifactStore(
            self.workspace,
            project_id=self.project_id,
            run_id=cad_publication.artifact.run_id,
            task_id=cad_publication.artifact.task_id,
        )
        artifact = store.publish(
            candidate_multi_joint_m10_provenance_artifact_id(selection.selection_hash),
            ArtifactType.JSON,
            "candidate_multi_joint_m10_provenance.json",
            _content(payload),
            _PRODUCER_NAME,
            _PRODUCER_VERSION,
            request.source_revision,
            request.source_state_hash,
            input_hash=selection.selection_hash,
        )
        return self.resolve_candidate_multi_joint_m10(
            artifact, expected_selection_hash=selection.selection_hash
        )

    def resolve_candidate_multi_joint_m10(
        self,
        artifact: EngineeringArtifact | str,
        *,
        expected_selection_hash: str,
    ):
        """Strictly resolve §18B only after its typed parent establishes the selection hash."""
        from .promotion_models import _require_hash
        from .multi_joint_m10_evaluation import CandidateMultiJointM10EvaluationRequestV2

        _require_hash(expected_selection_hash)
        verified, content = self._resolve_top_level(
            artifact, label="candidate multi-joint M10"
        )
        try:
            payload = CandidateMultiJointM10Provenance.model_validate_json(content)
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                "candidate multi-joint M10 artifact identity/binding verification failed"
            ) from exc
        request = _reparse_exact(CandidateMultiJointM10EvaluationRequestV2, payload.request)
        selection_hash = payload.selection.selection_hash
        expected_id = candidate_multi_joint_m10_provenance_artifact_id(
            expected_selection_hash
        )
        reference_scope = (self.project_id, verified.run_id, verified.task_id)
        if (
            selection_hash != expected_selection_hash
            or verified.artifact_id != expected_id
            or verified.input_hash != expected_selection_hash
            or verified.relative_path.rsplit("/", 1)[-1]
            != "candidate_multi_joint_m10_provenance.json"
            or verified.bound_revision != request.source_revision
            or verified.bound_state_hash != request.source_state_hash
            or verified.run_id != payload.candidate_cad.artifact.run_id
            or verified.task_id != payload.candidate_cad.artifact.task_id
        ):
            raise CandidateProvenanceIntegrityError(
                "candidate multi-joint M10 artifact scope or identity mismatch"
            )
        try:
            candidate_artifact, _ = self._resolve_reference(
                payload.candidate_publication,
                expected_input_hash=request.candidate_hash,
                expected_scope=reference_scope,
                label="candidate publication reference",
            )
            cad_artifact, _ = self._resolve_reference(
                payload.candidate_cad,
                expected_input_hash=payload.evaluation.cad_realization_hash,
                expected_scope=reference_scope,
                label="candidate CAD reference",
            )
            cad_publication = self.resolve_candidate_cad(cad_artifact)
            if (
                candidate_artifact
                != cad_publication.payload.candidate_artifact.artifact
            ):
                raise CandidateProvenanceIntegrityError(
                    "§18B candidate publication conflicts with candidate CAD parent"
                )
            self._verify_candidate_multi_joint_m10_semantics(payload, cad_publication)
        except CandidateProvenanceIntegrityError:
            raise
        except Exception as exc:
            raise CandidateProvenanceIntegrityError(
                f"candidate multi-joint M10 parent verification failed: {exc}"
            ) from exc
        if content != _content(payload):
            raise CandidateProvenanceIntegrityError(
                "candidate multi-joint M10 canonical bytes mismatch"
            )
        self._require_envelope_metadata(
            verified,
            artifact_id=expected_id,
            filename="candidate_multi_joint_m10_provenance.json",
            input_hash=expected_selection_hash,
            revision=request.source_revision,
            state_hash=request.source_state_hash,
        )
        return CandidateMultiJointM10ProvenancePublication(
            artifact=verified, payload=payload
        )

    def _verify_candidate_multi_joint_m10_semantics(self, envelope, cad_publication):
        from mechcad_harness.cad_assembly import assembly_hash
        from mechcad_harness.multi_joint_collision_sweep import (
            MultiJointCollisionSweepResultV2,
            multi_joint_collision_sweep_result_v2_hash,
        )
        from mechcad_harness.semantic_m10_kinematics import (
            semantic_m10_v2_request_hash,
            semantic_m10_v2_result_hash,
        )

        from .multi_joint_m10_bridge import (
            PhysicalToM10V2BridgeCompiler,
            validate_physical_to_m10_v2_bridge_v2,
        )
        from .multi_joint_m10_evaluation import (
            CandidateMultiJointM10EvaluationService,
            CandidateMultiJointM10EvaluationRequestV2,
            CandidateMultiJointM10EvaluationV2,
        )
        from .multi_joint_selection import CandidateMultiJointSelectionV2

        envelope = CandidateMultiJointM10Provenance.model_validate(
            envelope.model_dump(mode="json")
        )
        request = _reparse_exact(
            CandidateMultiJointM10EvaluationRequestV2, envelope.request
        )
        evaluation = _reparse_exact(CandidateMultiJointM10EvaluationV2, envelope.evaluation)
        selection = _reparse_exact(CandidateMultiJointSelectionV2, envelope.selection)
        result = _reparse_exact(MultiJointCollisionSweepResultV2, envelope.m10_v2_result)
        cad_publication = _reparse(CandidateCadProvenancePublication, cad_publication)
        if type(cad_publication.payload) is not CandidateCadProvenanceV2:
            raise ValueError("§18B requires candidate CAD provenance@2")
        candidate, synthesis_request, _policy = self._candidate_from_cad(cad_publication)
        if (
            candidate.schema_version != "mechanical-design-candidate@2"
            or synthesis_request.schema_version != "candidate-synthesis-request@2"
            or candidate.candidate_hash != request.candidate_hash
            or candidate.source_binding.project_id != self.project_id
            or candidate.source_binding.source_revision != request.source_revision
            or candidate.source_binding.source_state_hash != request.source_state_hash
            or candidate.semantic_source_binding_hash != request.semantic_source_binding_hash
            or candidate.synthesis_request_hash != synthesis_request.request_hash
        ):
            raise ValueError("§18B candidate semantic parent mismatch")
        verify_candidate_semantic_binding(
            candidate,
            synthesis_request,
            state_manager=self.state_manager,
            store=self.candidate_publication_service.store,
            project_id=self.project_id,
            exact_source_artifacts=cad_publication.payload.source_step_artifacts,
        )
        realization = cad_publication.payload.realization
        bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
            candidate,
            realization,
            cad_publication.payload.request.placement_derivations,
        )
        validate_physical_to_m10_v2_bridge_v2(
            bridge,
            candidate=candidate,
            cad_realization=realization,
            placement_derivations=cad_publication.payload.request.placement_derivations,
        )
        if bridge.physical_to_m10_bridge_hash != request.physical_to_m10_bridge_hash:
            raise ValueError("§18B P5 bridge identity mismatch")
        low_request = CandidateMultiJointM10EvaluationService._reconstruct_m10_request_v2(
            bridge, realization, request.scope
        )
        semantic_request = semantic_m10_v2_request_hash(
            low_request, realization.assembly, realization.mappings
        )
        if (
            semantic_request != request.semantic_m10_v2_request_hash
            or result.request_hash != low_request.request_hash
            or result.source_assembly_hash != assembly_hash(realization.assembly)
            or result.model_hash != low_request.model_hash
            or result.evaluator_version != low_request.evaluator_version
            or result.result_hash != multi_joint_collision_sweep_result_v2_hash(result)
        ):
            raise ValueError("§18B P5/P6 raw replay binding mismatch")
        semantic_result = semantic_m10_v2_result_hash(
            result, low_request, realization.assembly, realization.mappings
        )
        if (
            semantic_result != evaluation.semantic_m10_v2_result_hash
            or selection.semantic_m10_v2_result_hash != semantic_result
            or selection.semantic_m10_v2_request_hash != semantic_request
            or selection.evaluation_hash != evaluation.evaluation_hash
            or selection.candidate_request_hash != request.request_hash
        ):
            raise ValueError("§18B P5/P6 semantic replay binding mismatch")


# ---------------------------------------------------------------------------
# P7 §18A provenance @2 envelopes (Spec §18A). No self-hash, typed substitution,
# same declared counts as @1. Legacy @1 frozen.
# candidate-cad-provenance@2 is T-P3.4-owned; its envelope declaration was
# minimally introduced during the original T-P7.2 session to unblock §18B.
# T-P3.4 now owns the first-positive publish/resolve verifier above; T-P7.2
# consumes and regression-verifies that completed predecessor without a second
# verifier or redefinition.
# Remaining five are T-P7.2-owned first-positive implementations.
# ---------------------------------------------------------------------------


def _reparse_exact(expected_type: type, value: object) -> object:
    # Accept exact instances or dicts that validate to the exact expected type
    # (required for model_dump->model_validate roundtrips). Reject @1/mixed
    # via schema_version check inside the typed model itself.
    if isinstance(value, dict):
        try:
            parsed = expected_type.model_validate(value)
        except Exception as exc:
            raise ValueError(f"provenance typed reparse failed: {exc}") from exc
        # Ensure no silent upgrade: dict must carry the exact expected literal.
        expected_literal = expected_type.model_fields["schema_version"].default
        if parsed.schema_version != expected_literal:
            raise ValueError(
                f"provenance requires exact {expected_type.__name__}, got {parsed.schema_version}"
            )
        return parsed
    if type(value) is not expected_type:
        raise ValueError(
            f"provenance requires exact {expected_type.__name__}, got {type(value).__name__}"
        )
    try:
        return expected_type.model_validate(value.model_dump(mode="json"))
    except Exception as exc:
        raise ValueError(f"provenance typed reparse failed: {exc}") from exc


class CandidateCadProvenanceV2(Model):
    """candidate-cad-provenance@2: 5 declared, V2 realization/request (T-P3.4-owned)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["candidate-cad-provenance@2"] = "candidate-cad-provenance@2"
    realization: CandidateCadRealizationV2
    request: CandidateCadRealizationRequestV3
    candidate_artifact: ArtifactReference
    source_step_artifacts: tuple[EngineeringArtifact, ...]

    @field_validator("realization", mode="before")
    @classmethod
    def _validate_realization(cls, value):
        from .cad_realization import CandidateCadRealizationV2

        return _reparse_exact(CandidateCadRealizationV2, value)

    @field_validator("request", mode="before")
    @classmethod
    def _validate_request(cls, value):
        from .cad_realization import CandidateCadRealizationRequestV3

        return _reparse_exact(CandidateCadRealizationRequestV3, value)

    @model_validator(mode="after")
    def validate_envelope_v2(self) -> "CandidateCadProvenanceV2":
        from .cad_realization import CandidateCadRealizationV2

        realization = _reparse_exact(CandidateCadRealizationV2, self.realization)
        request = _reparse_exact(CandidateCadRealizationRequestV3, self.request)
        publication = self.candidate_artifact.artifact
        if (
            publication.project_id != request.source_binding.project_id
            or realization.candidate_hash != request.candidate_hash
            or realization.request_hash != request.request_hash
            or realization.mappings != request.mappings
            or publication.input_hash != realization.candidate_hash
            or (
                publication.bound_revision,
                publication.bound_state_hash,
            )
            != (
                request.source_binding.source_revision,
                request.source_binding.source_state_hash,
            )
        ):
            raise ValueError("candidate CAD provenance @2 typed binding mismatch")
        source_ids = tuple(item.artifact_id for item in self.source_step_artifacts)
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("candidate CAD source STEP artifact IDs must be unique")
        for source in self.source_step_artifacts:
            if (
                source.artifact_type is not ArtifactType.STEP
                or source.project_id != publication.project_id
                or (
                    source.bound_revision,
                    source.bound_state_hash,
                )
                != (
                    request.source_binding.source_revision,
                    request.source_binding.source_state_hash,
                )
            ):
                raise ValueError("candidate CAD source STEP provenance binding mismatch")
        return self


class CandidateEvaluationProvenanceV2(Model):
    """candidate-evaluation-provenance@2: 6 declared, evaluation V2."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["candidate-evaluation-provenance@2"] = (
        "candidate-evaluation-provenance@2"
    )
    evaluation: Any = Field()
    candidate_cad: ArtifactReference
    candidate_artifact: ArtifactReference
    proof_evidence: tuple[Evidence, ...] = ()
    home_evidence: tuple[Evidence, ...] = ()

    @field_validator("evaluation", mode="before")
    @classmethod
    def _validate_evaluation(cls, value):
        from .evaluation import CandidateEvaluationV2

        return _reparse_exact(CandidateEvaluationV2, value)

    @model_validator(mode="after")
    def validate_envelope_v2(self) -> "CandidateEvaluationProvenanceV2":
        from .evaluation import CandidateEvaluationV2

        evaluation = _reparse_exact(CandidateEvaluationV2, self.evaluation)
        cad, candidate = _reference_artifacts(self.candidate_cad, self.candidate_artifact)
        _, revision, state_hash = _require_shared_artifact_binding(cad, candidate)
        if candidate.input_hash != evaluation.candidate_hash:
            raise ValueError("evaluation@2 artifact identity binding mismatch")
        _require_evidence_binding(self.proof_evidence + self.home_evidence, revision, state_hash)
        return self


class CandidateComparisonProvenanceV2(Model):
    """candidate-comparison-provenance@2: 5 declared, request/result V2."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["candidate-comparison-provenance@2"] = (
        "candidate-comparison-provenance@2"
    )
    request: Any = Field()
    result: Any = Field()
    candidate_cad_artifacts: tuple[ArtifactReference, ...] = Field(min_length=1)
    candidate_evaluation_artifacts: tuple[ArtifactReference, ...] = Field(min_length=1)

    @field_validator("request", mode="before")
    @classmethod
    def _validate_request(cls, value):
        from .comparison import CandidateComparisonRequestV2

        return _reparse_exact(CandidateComparisonRequestV2, value)

    @field_validator("result", mode="before")
    @classmethod
    def _validate_result(cls, value):
        from .comparison import CandidateComparisonResultV2

        return _reparse_exact(CandidateComparisonResultV2, value)

    @model_validator(mode="after")
    def validate_envelope_v2(self) -> "CandidateComparisonProvenanceV2":
        from .comparison import CandidateComparisonRequestV2, CandidateComparisonResultV2

        request = _reparse_exact(CandidateComparisonRequestV2, self.request)
        result = _reparse_exact(CandidateComparisonResultV2, self.result)
        if request.request_hash != result.request_hash:
            raise ValueError("comparison@2 request binding mismatch")
        return self


class CandidateSelectionProvenanceV2(Model):
    """candidate-selection-provenance@2: 5 declared, selection V2."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["candidate-selection-provenance@2"] = (
        "candidate-selection-provenance@2"
    )
    selection: Any = Field()
    candidate_cad: ArtifactReference
    evaluation: ArtifactReference
    comparison: ArtifactReference | None = None

    @field_validator("selection", mode="before")
    @classmethod
    def _validate_selection(cls, value):
        from .selection import CandidateSelectionV2

        return _reparse_exact(CandidateSelectionV2, value)

    @model_validator(mode="after")
    def validate_envelope_v2(self) -> "CandidateSelectionProvenanceV2":
        from .selection import CandidateSelectionV2

        selection = _reparse_exact(CandidateSelectionV2, self.selection)
        if selection.comparison_used != (self.comparison is not None):
            raise ValueError("selection@2 comparison binding mismatch")
        cad, evaluation, *comparison = _reference_artifacts(
            self.candidate_cad, self.evaluation, self.comparison
        )
        _require_shared_artifact_binding(cad, evaluation, *comparison)
        if evaluation.input_hash != selection.evaluation_hash:
            raise ValueError("selection@2 evaluation artifact mismatch")
        return self


class CanonicalCadProvenanceV2(Model):
    """canonical-cad-provenance@2: 3 declared, canonical realization V2."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["canonical-cad-provenance@2"] = "canonical-cad-provenance@2"
    realization: Any = Field()
    source_step_artifacts: tuple[EngineeringArtifact, ...] = ()

    @field_validator("realization", mode="before")
    @classmethod
    def _validate_realization(cls, value):
        from .canonical_cad import CanonicalCadRealizationV2

        return _reparse_exact(CanonicalCadRealizationV2, value)


class CanonicalM10ProvenanceV2(Model):
    """canonical-m10-provenance@2: 5 declared, outcome V2."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["canonical-m10-provenance@2"] = "canonical-m10-provenance@2"
    outcome: Any = Field()
    canonical_cad: ArtifactReference
    proof_evidence: tuple[Evidence, ...] = ()
    home_evidence: tuple[Evidence, ...] = ()

    @field_validator("outcome", mode="before")
    @classmethod
    def _validate_outcome(cls, value):
        from .canonical_m10 import CanonicalM10VerificationOutcomeV2

        return _reparse_exact(CanonicalM10VerificationOutcomeV2, value)

    @model_validator(mode="after")
    def validate_envelope_v2(self) -> "CanonicalM10ProvenanceV2":
        from .canonical_m10 import CanonicalM10VerificationOutcomeV2

        outcome = _reparse_exact(CanonicalM10VerificationOutcomeV2, self.outcome)
        (cad,) = _reference_artifacts(self.canonical_cad)
        if cad.input_hash != outcome.cad_realization_hash:
            raise ValueError("canonical M10@2 CAD artifact binding mismatch")
        return self


# ---------------------------------------------------------------------------
# P7 §18B MJ typed-parent provenance (Spec §18B). T-P7.2-owned first-positive.
# EXACTLY 7 declared fields, no self-hash, no @2 envelope version, no locator@2.
# Reuses existing ArtifactStore + CandidateProvenanceArtifactService patterns.
# ---------------------------------------------------------------------------

_MJ_PROVENANCE_SCHEMA = "candidate-multi-joint-m10-provenance@1"
_MJ_PROVENANCE_PREFIX = "CANDIDATE-MULTI-JOINT-M10-"


def candidate_multi_joint_m10_provenance_artifact_id(selection_hash: str) -> str:
    from .promotion_models import _require_hash as _rh

    _rh(selection_hash)
    return f"{_MJ_PROVENANCE_PREFIX}{selection_hash[7:31]}"


class CandidateMultiJointM10Provenance(Model):
    """MJ typed-parent provenance @1: 7 declared, no self-hash."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["candidate-multi-joint-m10-provenance@1"] = (
        "candidate-multi-joint-m10-provenance@1"
    )
    request: Any = Field()
    evaluation: Any = Field()
    selection: Any = Field()
    m10_v2_result: Any = Field()
    candidate_publication: ArtifactReference
    candidate_cad: ArtifactReference

    @field_validator("request", mode="before")
    @classmethod
    def _validate_request(cls, value):
        from .multi_joint_m10_evaluation import CandidateMultiJointM10EvaluationRequestV2

        return _reparse_exact(CandidateMultiJointM10EvaluationRequestV2, value)

    @field_validator("evaluation", mode="before")
    @classmethod
    def _validate_evaluation(cls, value):
        from .multi_joint_m10_evaluation import CandidateMultiJointM10EvaluationV2

        return _reparse_exact(CandidateMultiJointM10EvaluationV2, value)

    @field_validator("selection", mode="before")
    @classmethod
    def _validate_selection(cls, value):
        from .multi_joint_selection import CandidateMultiJointSelectionV2

        return _reparse_exact(CandidateMultiJointSelectionV2, value)

    @field_validator("m10_v2_result", mode="before")
    @classmethod
    def _validate_result(cls, value):
        from mechcad_harness.multi_joint_collision_sweep import (
            MultiJointCollisionSweepResultV2,
        )

        if isinstance(value, dict):
            parsed = MultiJointCollisionSweepResultV2.model_validate(value)
            if parsed.schema_version != "multi-joint-collision-sweep-result@2":
                raise ValueError("§18B requires exact M10 result@2")
            return parsed
        if type(value) is not MultiJointCollisionSweepResultV2:
            raise ValueError("§18B requires exact M10 result@2")
        return MultiJointCollisionSweepResultV2.model_validate(
            value.model_dump(mode="json")
        )

    @model_validator(mode="after")
    def validate_envelope(self) -> "CandidateMultiJointM10Provenance":
        from mechcad_harness.multi_joint_collision_sweep import (
            MultiJointCollisionSweepResultV2,
        )
        from .multi_joint_m10_evaluation import (
            CandidateMultiJointM10EvaluationRequestV2,
            CandidateMultiJointM10EvaluationV2,
        )
        from .multi_joint_selection import CandidateMultiJointSelectionV2

        request = _reparse_exact(CandidateMultiJointM10EvaluationRequestV2, self.request)
        evaluation = _reparse_exact(CandidateMultiJointM10EvaluationV2, self.evaluation)
        selection = _reparse_exact(CandidateMultiJointSelectionV2, self.selection)
        if selection.evaluation_hash != evaluation.evaluation_hash:
            raise ValueError("MJ provenance selection/evaluation binding mismatch")
        if evaluation.candidate_request_hash != request.request_hash:
            raise ValueError("MJ provenance evaluation/request binding mismatch")
        if not (
            request.candidate_hash == evaluation.candidate_hash == selection.candidate_hash
        ):
            raise ValueError("MJ provenance candidate binding mismatch")
        result = self.m10_v2_result
        if type(result) is not MultiJointCollisionSweepResultV2:
            raise ValueError("MJ provenance requires persisted typed P6 result@2")
        if selection.semantic_m10_v2_result_hash != evaluation.semantic_m10_v2_result_hash:
            raise ValueError("MJ provenance P6 semantic result binding mismatch")
        candidate_artifact = self.candidate_publication.artifact
        cad_artifact = self.candidate_cad.artifact
        if (
            candidate_artifact.input_hash != request.candidate_hash
            or cad_artifact.input_hash != evaluation.cad_realization_hash
            or (candidate_artifact.project_id, candidate_artifact.bound_revision,
                candidate_artifact.bound_state_hash)
            != (request.project_id, request.source_revision, request.source_state_hash)
            or (cad_artifact.project_id, cad_artifact.bound_revision,
                cad_artifact.bound_state_hash)
            != (request.project_id, request.source_revision, request.source_state_hash)
        ):
            raise ValueError("MJ provenance artifact parent binding mismatch")
        return self


class CandidateMultiJointM10ProvenancePublication(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact: EngineeringArtifact
    payload: CandidateMultiJointM10Provenance


def validate_candidate_multi_joint_m10_provenance_chain(
    envelope: CandidateMultiJointM10Provenance,
    *,
    candidate_hash: str,
    project_id: str,
) -> tuple[str, str, str]:
    """Validate MJ chain equalities and return expected (req, eval, sel) tuple."""
    from .multi_joint_m10_evaluation import (
        CandidateMultiJointM10EvaluationRequestV2,
        CandidateMultiJointM10EvaluationV2,
    )
    from .multi_joint_selection import CandidateMultiJointSelectionV2

    if type(envelope) is not CandidateMultiJointM10Provenance:
        raise ValueError("MJ provenance must be the exact typed envelope")
    envelope = CandidateMultiJointM10Provenance.model_validate(envelope.model_dump(mode="json"))
    request = CandidateMultiJointM10EvaluationRequestV2.model_validate(
        envelope.request.model_dump(mode="json")
    )
    evaluation = CandidateMultiJointM10EvaluationV2.model_validate(
        envelope.evaluation.model_dump(mode="json")
    )
    selection = CandidateMultiJointSelectionV2.model_validate(
        envelope.selection.model_dump(mode="json")
    )
    if request.candidate_hash != candidate_hash:
        raise ValueError("MJ provenance candidate/publication binding mismatch")
    if request.project_id != project_id:
        raise ValueError("MJ provenance project binding mismatch")
    if request.semantic_source_binding_hash != getattr(request, "semantic_source_binding_hash", None):
        raise ValueError("MJ provenance semantic binding missing")
    return (request.request_hash, evaluation.evaluation_hash, selection.selection_hash)


def resolve_mj_provenance_expected_tuple_from_promotion_request(
    promotion_request: Any,
) -> tuple[str, str, str]:
    """Root A: verified entry context only (not durable fresh-process storage)."""
    from .promotion_models import CandidateMultiJointPromotionRequestV2

    if type(promotion_request) is not CandidateMultiJointPromotionRequestV2:
        raise ValueError("Root A requires exact MJ promotion request@2")
    promotion_request = CandidateMultiJointPromotionRequestV2.model_validate(
        promotion_request.model_dump(mode="json")
    )
    return (
        promotion_request.multi_joint_request_hash,
        promotion_request.multi_joint_evaluation_hash,
        promotion_request.multi_joint_selection_hash,
    )


def resolve_mj_provenance_expected_tuple_from_decision_manifest(
    decision_manifest: Any,
) -> tuple[str, str, str]:
    """Root B: durable restart from MJ decision manifest@2 via input-reference@2."""
    from .promotion_artifacts import SelectedMultiJointCandidateDecisionManifestV2

    if type(decision_manifest) is not SelectedMultiJointCandidateDecisionManifestV2:
        raise ValueError("Root B requires exact MJ decision manifest@2")
    decision_manifest = SelectedMultiJointCandidateDecisionManifestV2.model_validate(
        decision_manifest.model_dump(mode="json")
    )
    ref = decision_manifest.input_reference
    return (
        ref.multi_joint_evaluation_request_hash,
        ref.multi_joint_evaluation_hash,
        ref.multi_joint_selection_hash,
    )


def resolve_mj_provenance_expected_tuple_from_result_manifest(
    result_manifest: Any,
    *,
    decision_artifact_bytes: bytes,
    decision_artifact_hash: str,
) -> tuple[str, str, str]:
    """Root C: durable restart from MJ result manifest@2 via byte-verified decision artifact."""
    import hashlib as _hl

    from .promotion_artifacts import (
        MultiJointPromotionResultManifestV2,
        SelectedMultiJointCandidateDecisionManifestV2,
        multi_joint_decision_manifest_hash_v2,
    )

    if type(result_manifest) is not MultiJointPromotionResultManifestV2:
        raise ValueError("Root C requires exact MJ result manifest@2")
    result_manifest = MultiJointPromotionResultManifestV2.model_validate(
        result_manifest.model_dump(mode="json")
    )
    computed = "sha256:" + _hl.sha256(decision_artifact_bytes).hexdigest()
    if computed != decision_artifact_hash or computed != result_manifest.decision_artifact_hash:
        raise ValueError("Root C decision artifact byte mismatch")
    import json as _json

    manifest = SelectedMultiJointCandidateDecisionManifestV2.model_validate_json(
        decision_artifact_bytes.decode("utf-8")
    )
    recomputed = multi_joint_decision_manifest_hash_v2(manifest)
    if recomputed != manifest.decision_hash or recomputed != result_manifest.decision_hash:
        raise ValueError("Root C decision_hash mismatch")
    return resolve_mj_provenance_expected_tuple_from_decision_manifest(manifest)


__all__ = [
    "ArtifactReference",
    "CandidateCadProvenance",
    "CandidateCadProvenancePublication",
    "CandidateCadProvenanceV2",
    "CandidateComparisonProvenance",
    "CandidateComparisonProvenancePublication",
    "CandidateComparisonProvenanceV2",
    "CandidateEvaluationProvenance",
    "CandidateEvaluationProvenancePublication",
    "CandidateEvaluationProvenanceV2",
    "CandidateMultiJointM10Provenance",
    "CandidateMultiJointM10ProvenancePublication",
    "CandidateProvenanceArtifactService",
    "CandidateProvenanceIntegrityError",
    "CandidateSelectionProvenance",
    "CandidateSelectionProvenancePublication",
    "CandidateSelectionProvenanceV2",
    "CanonicalCadProvenance",
    "CanonicalCadProvenancePublication",
    "CanonicalCadProvenanceV2",
    "CanonicalM10Provenance",
    "CanonicalM10ProvenancePublication",
    "CanonicalM10ProvenanceV2",
    "PromotionChainLocator",
    "PromotionChainLocatorPublication",
    "candidate_multi_joint_m10_provenance_artifact_id",
    "resolve_mj_provenance_expected_tuple_from_decision_manifest",
    "resolve_mj_provenance_expected_tuple_from_promotion_request",
    "resolve_mj_provenance_expected_tuple_from_result_manifest",
    "validate_candidate_multi_joint_m10_provenance_chain",
]
