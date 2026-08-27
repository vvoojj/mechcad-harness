from __future__ import annotations

import json
from enum import StrEnum

from pydantic import Field

from mechcad_harness.artifacts import ArtifactStore, ArtifactType, EngineeringArtifact
from mechcad_harness.models.common import Model
from mechcad_harness.state import StateManager

from .models import CandidateSynthesisPolicy, CandidateSynthesisRequest, MechanicalDesignCandidate, candidate_hash


class CandidateIntegrityError(ValueError):
    pass


class CandidateCurrentness(StrEnum):
    CURRENT = "current"
    STALE_RELATIVE_TO_CURRENT_STATE = "stale_relative_to_current_state"
    CURRENTNESS_UNAVAILABLE = "currentness_unavailable"


class CandidateIntegrityVerifier:
    def verify(self, candidate: MechanicalDesignCandidate, request: CandidateSynthesisRequest, policy: CandidateSynthesisPolicy) -> MechanicalDesignCandidate:
        try:
            if candidate.candidate_hash != candidate_hash(candidate):
                raise CandidateIntegrityError("candidate hash mismatch")
            if candidate.synthesis_request_hash != request.request_hash or candidate.synthesis_policy_hash != policy.policy_hash:
                raise CandidateIntegrityError("candidate request or policy hash mismatch")
            if candidate.source_binding != request.source_binding:
                raise CandidateIntegrityError("candidate and request source binding mismatch")
            bound_joint_ids = {binding.joint_id for binding in candidate.realization.joint_bindings}
            missing_required = set(request.required_joint_ids) - bound_joint_ids
            if missing_required:
                raise CandidateIntegrityError("required joint physical realization is unresolved")
            # Revalidation catches forged nested hashes produced via model_copy().
            MechanicalDesignCandidate.model_validate(candidate.model_dump(mode="json"))
            return candidate
        except CandidateIntegrityError:
            raise
        except Exception as exc:
            raise CandidateIntegrityError(str(exc) or "candidate integrity failure") from exc


class CandidateCurrentnessService:
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager

    def evaluate(self, candidate: MechanicalDesignCandidate, request: CandidateSynthesisRequest, policy: CandidateSynthesisPolicy) -> CandidateCurrentness:
        CandidateIntegrityVerifier().verify(candidate, request, policy)
        try:
            current = self.state_manager.load_current_state(candidate.source_binding.project_id)
        except Exception:
            return CandidateCurrentness.CURRENTNESS_UNAVAILABLE
        if current.revision == candidate.source_binding.source_revision:
            try:
                candidate.source_binding.validate_against(candidate.source_binding.project_id, current)
            except Exception as exc:
                raise CandidateIntegrityError("candidate source binding is invalid") from exc
            return CandidateCurrentness.CURRENT
        payload = current.model_dump(mode="json")
        try:
            for reference in candidate.source_binding.consumed_authority:
                from .models import _resolve_path, canonical_json
                import hashlib
                actual = "sha256:" + hashlib.sha256(canonical_json(_resolve_path(payload, reference.path))).hexdigest()
                if actual != reference.value_hash:
                    return CandidateCurrentness.STALE_RELATIVE_TO_CURRENT_STATE
            return CandidateCurrentness.CURRENT
        except Exception:
            return CandidateCurrentness.CURRENTNESS_UNAVAILABLE


class CandidatePublication(Model):
    model_config = {"frozen": True, "extra": "forbid"}
    artifact: EngineeringArtifact
    candidate: MechanicalDesignCandidate


class CandidatePublicationService:
    _RUN_ID = "PUBLISH"

    def __init__(self, workspace, project_id: str, state_manager: StateManager):
        self.project_id = project_id
        self.state_manager = state_manager
        self.store = ArtifactStore(workspace, project_id=project_id, run_id=self._RUN_ID)

    def publish(self, candidate: MechanicalDesignCandidate, request: CandidateSynthesisRequest, policy: CandidateSynthesisPolicy) -> CandidatePublication:
        CandidateIntegrityVerifier().verify(candidate, request, policy)
        candidate.source_binding.validate_against(self.project_id, self.state_manager.load_revision(self.project_id, candidate.source_binding.source_revision))
        payload = {
            "schema_version": "candidate-publication@1",
            "candidate": candidate.model_dump(mode="json"),
            "request": request.model_dump(mode="json"),
            "policy": policy.model_dump(mode="json"),
        }
        content = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        artifact = self.store.publish(
            artifact_id="CAND-" + candidate.candidate_hash[7:31], artifact_type=ArtifactType.JSON,
            filename="candidate.json", content=content, producer_tool_name="mechcad-candidate-publication",
            producer_tool_version="1", bound_revision=candidate.source_binding.source_revision,
            bound_state_hash=candidate.source_binding.source_state_hash, input_hash=candidate.candidate_hash,
        )
        return CandidatePublication(artifact=artifact, candidate=self.resolve(artifact.artifact_id).candidate)

    def resolve(self, artifact_id: str) -> CandidatePublication:
        try:
            verified = self.store.read_verified_strict(artifact_id, expected_type=ArtifactType.JSON)
            if verified is None:
                raise CandidateIntegrityError("candidate artifact is missing")
            artifact, content = verified
            payload = json.loads(content)
            if set(payload) != {"schema_version", "candidate", "request", "policy"} or payload["schema_version"] != "candidate-publication@1":
                raise CandidateIntegrityError("candidate publication manifest schema is invalid")
            candidate = MechanicalDesignCandidate.model_validate(payload["candidate"])
            request = CandidateSynthesisRequest.model_validate(payload["request"])
            policy = CandidateSynthesisPolicy.model_validate(payload["policy"])
            if artifact.project_id != self.project_id or artifact.input_hash != candidate.candidate_hash:
                raise CandidateIntegrityError("candidate publication artifact binding mismatch")
            if (artifact.bound_revision, artifact.bound_state_hash) != (candidate.source_binding.source_revision, candidate.source_binding.source_state_hash):
                raise CandidateIntegrityError("candidate publication source binding mismatch")
            CandidateIntegrityVerifier().verify(candidate, request, policy)
            candidate.source_binding.validate_against(self.project_id, self.state_manager.load_revision(self.project_id, candidate.source_binding.source_revision))
            return CandidatePublication(artifact=artifact, candidate=candidate)
        except CandidateIntegrityError:
            raise
        except Exception as exc:
            raise CandidateIntegrityError(str(exc) or "candidate publication integrity failure") from exc
