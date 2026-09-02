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
        return self.evaluate_source_binding(candidate)

    def evaluate_source_binding(self, candidate: MechanicalDesignCandidate) -> CandidateCurrentness:
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

            from mechcad_harness.models.supplied_component_interface import (
                MaterializedInterfaceVerifier,
                GeometryDerivationStatus,
            )
            from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity

            verified_geometry = {}

            def verify_geometry(identity):
                prior = verified_geometry.get(identity.artifact_id)
                if prior is not None:
                    if prior[0] != identity:
                        raise CandidateIntegrityError("candidate geometry artifact binding mismatch")
                    return prior[1]
                try:
                    verified_source = self.store.read_verified_in_project(
                        identity.artifact_id,
                        expected_type=ArtifactType.STEP,
                        expected_hash=identity.artifact_hash,
                    )
                except Exception as exc:
                    raise CandidateIntegrityError(
                        f"candidate geometry artifact verification failed: {exc}"
                    ) from exc
                if verified_source is None:
                    raise CandidateIntegrityError("candidate geometry artifact is missing or tampered")
                source_artifact, _ = verified_source
                if (
                    source_artifact.project_id != self.project_id
                    or source_artifact.artifact_id != identity.artifact_id
                    or source_artifact.artifact_type is not ArtifactType.STEP
                    or source_artifact.sha256 != identity.artifact_hash
                ):
                    raise CandidateIntegrityError("candidate geometry artifact binding mismatch")
                verified_geometry[identity.artifact_id] = (identity, source_artifact)
                return source_artifact

            for spec in candidate.component_specifications:
                if spec.geometry_source is not None:
                    verify_geometry(
                        GeometryArtifactIdentity.from_candidate(spec.geometry_source)
                    )
                has_m13_payload = (
                    bool(spec.supplied_reference_frames)
                    or bool(spec.supplied_interface_definitions)
                    or bool(spec.geometry_derivation_transforms)
                )
                if spec.schema_version != "component-specification@2" or not has_m13_payload:
                    continue
                transforms = {
                    transform.transform_id: transform
                    for transform in spec.geometry_derivation_transforms
                }
                for transform in spec.geometry_derivation_transforms:
                    if transform.status is GeometryDerivationStatus.ACCEPTED:
                        verify_geometry(transform.source_geometry)
                        verify_geometry(transform.derived_geometry)
                for active_interface in spec.supplied_interface_definitions:
                    if active_interface.kind != "materialized":
                        continue
                    provenance = active_interface.derivation
                    assert provenance is not None
                    verify_geometry(provenance.source_geometry)
                    verify_geometry(provenance.derived_geometry)
                    transform = transforms.get(provenance.transform_id)
                    if transform is None or transform.transform_hash != provenance.transform_hash:
                        raise CandidateIntegrityError(
                            "candidate materialized interface transform does not resolve"
                        )
                    active_frame = None
                    if provenance.derived_reference_frame_id is not None:
                        active_frame = next(
                            (
                                frame
                                for frame in spec.supplied_reference_frames
                                if frame.frame_id == provenance.derived_reference_frame_id
                                and frame.frame_hash == provenance.derived_reference_frame_hash
                            ),
                            None,
                        )
                        if active_frame is None:
                            raise CandidateIntegrityError(
                                "candidate materialized interface frame does not resolve"
                            )
                    try:
                        MaterializedInterfaceVerifier.verify(
                            provenance, transform, active_interface, active_frame
                        )
                    except Exception as exc:
                        raise CandidateIntegrityError(
                            f"candidate materialized interface integrity failure: {exc}"
                        ) from exc
            return CandidatePublication(artifact=artifact, candidate=candidate)
        except CandidateIntegrityError:
            raise
        except Exception as exc:
            raise CandidateIntegrityError(str(exc) or "candidate publication integrity failure") from exc
