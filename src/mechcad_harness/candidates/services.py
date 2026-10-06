from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from pydantic import Field

from mechcad_harness.artifacts import ArtifactStore, ArtifactType, EngineeringArtifact
from mechcad_harness.core.canonical import canonical_json_bytes
from mechcad_harness.core.currentness import Currentness
from mechcad_harness.models.common import Model
from mechcad_harness.state import StateManager
from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity
from mechcad_harness.step_content_identity import step_content_identity_v1

from .semantic_authority import (
    semantic_source_binding_hash,
)

from .models import (
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
    MechanicalDesignCandidate,
    candidate_hash,
    candidate_hash_v2,
    candidate_synthesis_request_hash_v2,
    _resolve_path,
)
from mechcad_harness.models.semantic_component import semantic_component_specification_hash


class CandidateIntegrityError(ValueError):
    pass


CandidateCurrentness = Currentness


def compute_verified_semantic_binding(
    source_binding,
    *,
    state,
    store: ArtifactStore,
    project_id: str,
    exact_source_artifacts=None,
    required_source_identities=None,
):
    """Rebuild the verifier-local semantic binding from one exact state."""

    return _compute_semantic_binding(
        source_binding,
        state=state,
        store=store,
        project_id=project_id,
        validate_legacy_binding=True,
        exact_source_artifacts=exact_source_artifacts,
        required_source_identities=required_source_identities,
    )


def verify_candidate_semantic_binding(
    candidate: MechanicalDesignCandidate,
    request: CandidateSynthesisRequest,
    *,
    state_manager: StateManager,
    store: ArtifactStore,
    project_id: str,
    exact_source_artifacts=None,
) -> MechanicalDesignCandidate:
    """Verify a persisted candidate@2 without filling or repairing identity fields."""

    try:
        if candidate.schema_version != "mechanical-design-candidate@2":
            raise CandidateIntegrityError(
                "semantic candidate verification requires candidate@2"
            )
        if request.schema_version != "candidate-synthesis-request@2":
            raise CandidateIntegrityError("candidate@2 requires synthesis request@2")
        if request.source_binding != candidate.source_binding:
            raise CandidateIntegrityError("candidate and request source binding mismatch")
        state = state_manager.load_revision(
            candidate.source_binding.project_id,
            candidate.source_binding.source_revision,
        )
        required_source_identities = candidate_cad_required_raw_source_identities(
            candidate,
            state_manager=state_manager,
            project_id=project_id,
        )
        context, semantic_hash = compute_verified_semantic_binding(
            candidate.source_binding,
            state=state,
            store=store,
            project_id=project_id,
            exact_source_artifacts=exact_source_artifacts,
            required_source_identities=required_source_identities,
        )
        if request.semantic_source_binding_hash != semantic_hash:
            raise CandidateIntegrityError("request semantic source binding hash mismatch")
        if candidate.semantic_source_binding_hash != semantic_hash:
            raise CandidateIntegrityError("candidate semantic source binding hash mismatch")
        if candidate_synthesis_request_hash_v2(request) != request.request_hash:
            raise CandidateIntegrityError("request@2 hash mismatch")
        if candidate.synthesis_request_hash != request.request_hash:
            raise CandidateIntegrityError("candidate synthesis request hash mismatch")
        for specification in candidate.component_specifications:
            if specification.schema_version != "component-specification@4":
                raise CandidateIntegrityError("candidate@2 requires component-specification@4")
            if semantic_component_specification_hash(specification, context) != specification.specification_hash:
                raise CandidateIntegrityError("candidate component specification semantic hash mismatch")
        if candidate_hash_v2(candidate) != candidate.candidate_hash:
            raise CandidateIntegrityError("candidate@2 hash mismatch")
        return candidate
    except CandidateIntegrityError:
        raise
    except Exception as exc:
        raise CandidateIntegrityError(str(exc) or "candidate semantic binding failure") from exc


def bind_candidate_synthesis_request_semantic_identity(
    pending_request: CandidateSynthesisRequest,
    *,
    state_manager: StateManager,
    store: ArtifactStore,
    project_id: str,
) -> CandidateSynthesisRequest:
    """Bind a new request@2 once, before it crosses a trusted boundary."""

    try:
        if pending_request.schema_version != "candidate-synthesis-request@2":
            raise CandidateIntegrityError("request semantic binding requires request@2")
        state = state_manager.load_revision(
            pending_request.source_binding.project_id,
            pending_request.source_binding.source_revision,
        )
        _, semantic_hash = compute_verified_semantic_binding(
            pending_request.source_binding,
            state=state,
            store=store,
            project_id=project_id,
        )
        if pending_request.semantic_source_binding_hash not in ("pending", semantic_hash):
            raise CandidateIntegrityError("request semantic source binding hash mismatch")
        payload = pending_request.model_dump(mode="json")
        payload["semantic_source_binding_hash"] = semantic_hash
        return CandidateSynthesisRequest.model_validate(payload)
    except CandidateIntegrityError:
        raise
    except Exception as exc:
        raise CandidateIntegrityError(str(exc) or "request semantic binding failure") from exc


def _compute_semantic_binding(
    source_binding,
    *,
    state,
    store: ArtifactStore,
    project_id: str,
    validate_legacy_binding: bool,
    exact_source_artifacts=None,
    required_source_identities=None,
):
    if validate_legacy_binding:
        source_binding.validate_against(project_id, state)
    payload = state.model_dump(mode="json")
    resolved_values = {
        reference.path: _resolve_path(payload, reference.path)
        for reference in source_binding.consumed_authority
    }
    geometry_bindings = {}
    exact_by_id = None
    if exact_source_artifacts is not None:
        exact_by_id = {}
        for artifact in exact_source_artifacts:
            if artifact.artifact_id in exact_by_id:
                raise CandidateIntegrityError(
                    "candidate exact source artifact IDs must be unique"
                )
            exact_by_id[artifact.artifact_id] = artifact
    for identity in _iter_geometry_identities(tuple(resolved_values.values())):
        key = (
            identity.artifact_id,
            identity.artifact_hash,
            identity.source_identity,
            identity.format,
            identity.coordinate_system_id,
        )
        if exact_by_id is None:
            verified = store.read_verified_in_project(
                identity.artifact_id,
                expected_type=ArtifactType.STEP,
                expected_hash=identity.artifact_hash,
            )
        else:
            source = exact_by_id.get(identity.artifact_id)
            if (
                source is None
                or source.artifact_type is not ArtifactType.STEP
                or source.project_id != project_id
                or source.sha256 != identity.artifact_hash
            ):
                raise CandidateIntegrityError(
                    f"candidate exact geometry artifact binding mismatch: {identity.artifact_id}"
                )
            exact_store = ArtifactStore(
                store.workspace,
                project_id=source.project_id,
                run_id=source.run_id,
                task_id=source.task_id,
            )
            verified = exact_store.read_verified_strict(
                source.artifact_id,
                expected_type=ArtifactType.STEP,
                expected_hash=identity.artifact_hash,
            )
            if verified is not None and verified[0] != source:
                raise CandidateIntegrityError(
                    f"candidate exact geometry artifact snapshot mismatch: {identity.artifact_id}"
                )
        if verified is None:
            raise CandidateIntegrityError(
                f"candidate geometry artifact is missing or ambiguous: {identity.artifact_id}"
            )
        artifact, content = verified
        if artifact.project_id != project_id:
            raise CandidateIntegrityError(
                f"candidate geometry artifact belongs to a different project: {identity.artifact_id}"
            )
        if validate_legacy_binding and (
            artifact.bound_revision != source_binding.source_revision
            or artifact.bound_state_hash != source_binding.source_state_hash
        ):
            raise CandidateIntegrityError(
                f"candidate geometry artifact is bound to a different source: {identity.artifact_id}"
            )
        geometry_bindings[key] = step_content_identity_v1(content).model_dump(mode="json")
    if required_source_identities is not None:
        for identity in required_source_identities.values():
            key = (
                identity.artifact_id,
                identity.artifact_hash,
                identity.source_identity,
                identity.format,
                identity.coordinate_system_id,
            )
            if key in geometry_bindings:
                continue
            if exact_by_id is not None:
                source = exact_by_id.get(identity.artifact_id)
                if source is None:
                    raise CandidateIntegrityError(
                        "candidate required exact source artifact is missing: "
                        f"{identity.artifact_id}"
                    )
                if (
                    source.artifact_type is not ArtifactType.STEP
                    or source.project_id != project_id
                    or source.sha256 != identity.artifact_hash
                ):
                    raise CandidateIntegrityError(
                        "candidate required exact source artifact binding mismatch: "
                        f"{identity.artifact_id}"
                    )
                exact_store = ArtifactStore(
                    store.workspace,
                    project_id=source.project_id,
                    run_id=source.run_id,
                    task_id=source.task_id,
                )
                verified = exact_store.read_verified_strict(
                    source.artifact_id,
                    expected_type=ArtifactType.STEP,
                    expected_hash=identity.artifact_hash,
                )
                if verified is not None and verified[0] != source:
                    raise CandidateIntegrityError(
                        "candidate required exact source artifact snapshot mismatch: "
                        f"{identity.artifact_id}"
                    )
            else:
                verified = store.read_verified_in_project(
                    identity.artifact_id,
                    expected_type=ArtifactType.STEP,
                    expected_hash=identity.artifact_hash,
                )
            if verified is None:
                raise CandidateIntegrityError(
                    "candidate required geometry artifact is missing or ambiguous: "
                    f"{identity.artifact_id}"
                )
            artifact, content = verified
            if artifact.project_id != project_id:
                raise CandidateIntegrityError(
                    "candidate required geometry artifact belongs to a different project: "
                    f"{identity.artifact_id}"
                )
            if validate_legacy_binding and (
                artifact.bound_revision != source_binding.source_revision
                or artifact.bound_state_hash != source_binding.source_state_hash
            ):
                raise CandidateIntegrityError(
                    "candidate required geometry artifact is bound to a different source: "
                    f"{identity.artifact_id}"
                )
            geometry_bindings[key] = step_content_identity_v1(content).model_dump(
                mode="json"
            )
    return geometry_bindings, semantic_source_binding_hash(
        source_binding,
        resolved_values,
        geometry_bindings,
    )


def _iter_geometry_identities(value):
    if isinstance(value, Mapping):
        keys = set(value)
        if {"artifact_id", "artifact_hash", "source_identity", "format"} <= keys:
            try:
                yield GeometryArtifactIdentity.from_fields(
                    value["artifact_id"],
                    value["artifact_hash"],
                    value["source_identity"],
                    value["format"],
                    value.get("coordinate_system_id"),
                )
            except Exception as exc:
                raise CandidateIntegrityError("candidate geometry identity is invalid") from exc
        for item in value.values():
            yield from _iter_geometry_identities(item)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            yield from _iter_geometry_identities(item)


def candidate_cad_required_raw_source_identities(
    candidate: MechanicalDesignCandidate,
    *,
    state_manager: StateManager,
    project_id: str,
) -> dict[str, GeometryArtifactIdentity]:
    """Derive the exact raw source set shared by candidate publication/CAD provenance.

    The result is verifier-local, keyed by artifact ID, and carries no semantic
    identity. It includes the source-bound authority walk plus supplied and
    materialized component geometry required by the existing candidate
    publication resolver.
    """

    from mechcad_harness.models.supplied_component_interface import (
        GeometryDerivationStatus,
    )

    source_binding = candidate.source_binding
    if source_binding.project_id != project_id:
        raise CandidateIntegrityError("candidate source project does not match raw source resolver")
    state = state_manager.load_revision(
        source_binding.project_id, source_binding.source_revision
    )
    source_binding.validate_against(project_id, state)
    state_payload = state.model_dump(mode="json")
    authority_values = tuple(
        _resolve_path(state_payload, reference.path)
        for reference in source_binding.consumed_authority
    )
    required: dict[str, GeometryArtifactIdentity] = {}

    def include(identity: GeometryArtifactIdentity) -> None:
        prior = required.get(identity.artifact_id)
        if prior is not None and prior != identity:
            raise CandidateIntegrityError(
                "candidate CAD required raw identity has a conflicting artifact binding"
            )
        required[identity.artifact_id] = identity

    for identity in _iter_geometry_identities(authority_values):
        include(identity)

    for specification in candidate.component_specifications:
        if specification.geometry_source is not None:
            include(GeometryArtifactIdentity.from_candidate(specification.geometry_source))
        has_m13_payload = bool(
            specification.supplied_reference_frames
            or specification.supplied_interface_definitions
            or specification.geometry_derivation_transforms
        )
        if specification.schema_version not in {
            "component-specification@2",
            "component-specification@4",
        } or not has_m13_payload:
            continue
        transforms = {
            transform.transform_id: transform
            for transform in specification.geometry_derivation_transforms
        }
        for transform in specification.geometry_derivation_transforms:
            if transform.status is GeometryDerivationStatus.ACCEPTED:
                include(transform.source_geometry)
                include(transform.derived_geometry)
        for active_interface in specification.supplied_interface_definitions:
            if active_interface.kind != "materialized":
                continue
            provenance = active_interface.derivation
            if provenance is None:
                raise CandidateIntegrityError(
                    "candidate CAD materialized interface derivation is missing"
                )
            include(provenance.source_geometry)
            include(provenance.derived_geometry)
            transform = transforms.get(provenance.transform_id)
            if transform is None or transform.transform_hash != provenance.transform_hash:
                raise CandidateIntegrityError(
                    "candidate CAD materialized interface transform does not resolve"
                )
    return required


class CandidateIntegrityVerifier:
    def verify(self, candidate: MechanicalDesignCandidate, request: CandidateSynthesisRequest, policy: CandidateSynthesisPolicy) -> MechanicalDesignCandidate:
        try:
            candidate_is_v2 = candidate.schema_version == "mechanical-design-candidate@2"
            request_is_v2 = request.schema_version == "candidate-synthesis-request@2"
            if candidate_is_v2 != request_is_v2:
                raise CandidateIntegrityError(
                    "candidate and synthesis request families must match"
                )
            if candidate_is_v2:
                if request.schema_version != "candidate-synthesis-request@2":
                    raise CandidateIntegrityError("candidate@2 requires synthesis request@2")
                if request.request_hash == "pending" or candidate.synthesis_request_hash == "pending":
                    raise CandidateIntegrityError("candidate@2 request identity is pending")
                if candidate.semantic_source_binding_hash != request.semantic_source_binding_hash:
                    raise CandidateIntegrityError("candidate and request semantic binding mismatch")
                if candidate.synthesis_request_hash != request.request_hash:
                    raise CandidateIntegrityError("candidate and request hash mismatch")
                if candidate.candidate_hash != candidate_hash_v2(candidate):
                    raise CandidateIntegrityError("candidate@2 hash mismatch")
            elif candidate.candidate_hash != candidate_hash(candidate):
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

    def evaluate(
        self,
        candidate: MechanicalDesignCandidate,
        request: CandidateSynthesisRequest,
        policy: CandidateSynthesisPolicy,
        exact_source_artifacts=None,
    ) -> CandidateCurrentness:
        CandidateIntegrityVerifier().verify(candidate, request, policy)
        return self.evaluate_source_binding(
            candidate,
            synthesis_request=request,
            exact_source_artifacts=exact_source_artifacts,
        )

    def evaluate_source_binding(
        self,
        candidate: MechanicalDesignCandidate,
        *,
        synthesis_request: CandidateSynthesisRequest | None = None,
        exact_source_artifacts=None,
    ) -> CandidateCurrentness:
        if candidate.schema_version == "mechanical-design-candidate@2":
            if synthesis_request is None or synthesis_request.schema_version != "candidate-synthesis-request@2":
                raise CandidateIntegrityError("candidate@2 currentness requires synthesis request@2")
            store = ArtifactStore(
                self.state_manager.workspace,
                project_id=candidate.source_binding.project_id,
                run_id="CURRENTNESS",
            )
            verify_candidate_semantic_binding(
                candidate,
                synthesis_request,
                state_manager=self.state_manager,
                store=store,
                project_id=candidate.source_binding.project_id,
                exact_source_artifacts=exact_source_artifacts,
            )
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
        try:
            if candidate.schema_version == "mechanical-design-candidate@2":
                store = ArtifactStore(
                    self.state_manager.workspace,
                    project_id=candidate.source_binding.project_id,
                    run_id="CURRENTNESS",
                )
                _, current_semantic_hash = _compute_semantic_binding(
                    candidate.source_binding,
                    state=current,
                    store=store,
                    project_id=candidate.source_binding.project_id,
                    validate_legacy_binding=False,
                    exact_source_artifacts=exact_source_artifacts,
                )
                if current_semantic_hash == candidate.semantic_source_binding_hash:
                    return CandidateCurrentness.CURRENT
                return CandidateCurrentness.STALE_RELATIVE_TO_CURRENT_STATE
            payload = current.model_dump(mode="json")
            from .models import canonical_json
            import hashlib
            for reference in candidate.source_binding.consumed_authority:
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
        if candidate.schema_version == "mechanical-design-candidate@2":
            verify_candidate_semantic_binding(
                candidate,
                request,
                state_manager=self.state_manager,
                store=self.store,
                project_id=self.project_id,
            )
        candidate.source_binding.validate_against(self.project_id, self.state_manager.load_revision(self.project_id, candidate.source_binding.source_revision))
        payload = {
            "schema_version": "candidate-publication@1",
            "candidate": candidate.model_dump(mode="json"),
            "request": request.model_dump(mode="json"),
            "policy": policy.model_dump(mode="json"),
        }
        content = canonical_json_bytes(payload)
        artifact = self.store.publish(
            artifact_id="CAND-" + candidate.candidate_hash[7:31], artifact_type=ArtifactType.JSON,
            filename="candidate.json", content=content, producer_tool_name="mechcad-candidate-publication",
            producer_tool_version="1", bound_revision=candidate.source_binding.source_revision,
            bound_state_hash=candidate.source_binding.source_state_hash, input_hash=candidate.candidate_hash,
        )
        return CandidatePublication(artifact=artifact, candidate=self.resolve(artifact.artifact_id).candidate)

    def resolve(
        self,
        artifact_id: str,
        *,
        exact_source_artifacts=None,
        verify_semantic_binding: bool = True,
    ) -> CandidatePublication:
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
            if (
                candidate.schema_version == "mechanical-design-candidate@2"
                and verify_semantic_binding
            ):
                verify_candidate_semantic_binding(
                    candidate,
                    request,
                    state_manager=self.state_manager,
                    store=self.store,
                    project_id=self.project_id,
                    exact_source_artifacts=exact_source_artifacts,
                )
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
                    if exact_source_artifacts is None:
                        verified_source = self.store.read_verified_in_project(
                            identity.artifact_id,
                            expected_type=ArtifactType.STEP,
                            expected_hash=identity.artifact_hash,
                        )
                    else:
                        exact = {
                            item.artifact_id: item for item in exact_source_artifacts
                        }.get(identity.artifact_id)
                        if exact is None or exact.sha256 != identity.artifact_hash:
                            raise CandidateIntegrityError(
                                "candidate geometry artifact exact snapshot is missing"
                            )
                        verified_source = ArtifactStore(
                            self.store.workspace,
                            project_id=exact.project_id,
                            run_id=exact.run_id,
                            task_id=exact.task_id,
                        ).read_verified_strict(
                            exact.artifact_id,
                            expected_type=ArtifactType.STEP,
                            expected_hash=exact.sha256,
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
                if exact_source_artifacts is not None:
                    exact = next(
                        item
                        for item in exact_source_artifacts
                        if item.artifact_id == identity.artifact_id
                    )
                    if source_artifact != exact:
                        raise CandidateIntegrityError(
                            "candidate geometry artifact exact snapshot mismatch"
                        )
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
                if spec.schema_version not in {"component-specification@2", "component-specification@4"} or not has_m13_payload:
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
