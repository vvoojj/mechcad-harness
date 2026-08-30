from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from mechcad_harness.artifacts import ArtifactStore
from mechcad_harness.candidates import (
    CandidateCanonicalInstanceMapping,
    CandidatePromotionApplicationService,
    CandidatePromotionCompilation,
    CandidatePromotionCompiler,
    CandidatePromotionRequest,
    PrePromotionM10ScopeProjection,
    PromotionManifestService,
    PromotionPhysicalPairRequirement,
    PromotionReadiness,
    PromotionValueClassification,
    PromotedMechanismVerificationStatus,
    verify_promoted_mechanism,
)
from mechcad_harness.changes import ChangeOperation
from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
from mechcad_harness.changes.errors import StaleProposalError
from mechcad_harness.dependency import DependencyGraph, EvidenceStore
from mechcad_harness.dependency.models import InvalidationRecord
from mechcad_harness.models import (
    CanonicalComponentSpecification,
    CanonicalPhysicalComponent,
    CanonicalPhysicalMechanism,
    ChangeProposal,
    DesignState,
    ProposalStatus,
)
from mechcad_harness.runs import (
    RunController,
    Run,
    RunStatus,
    SourceBinding,
)
from mechcad_harness.runs.convergence import ConvergenceTracker
from mechcad_harness.state import StateManager, state_hash


def _request_and_manager(tmp_path):
    from test_m12_promotion_compiler import _classifications, _inputs

    inputs, request_builder, state = _inputs()
    candidate, synthesis_request, synthesis_policy, m12, evaluation, selection = inputs
    base = request_builder(
        inputs=inputs,
        classifications=(),
    )
    request = request_builder(
        inputs=inputs,
        classifications=_classifications(base),
    )
    request = CandidatePromotionRequest.model_validate(request.model_dump(mode="json"))
    manager = StateManager(tmp_path)
    manager.create_project(request.project_id, state)
    return request, state, manager


def _compiled(request):
    specification = CanonicalComponentSpecification(
        component_type="fixture",
        source_identity="fixture:spec",
        interfaces=("frame",),
    )
    mechanism = CanonicalPhysicalMechanism(
        id=request.canonical_target_mechanism_id,
        name="fixture mechanism",
        component_specifications=(specification,),
        components=(
            CanonicalPhysicalComponent(
                instance_id="component-1",
                specification_hash=specification.specification_hash,
                role="mount_or_support",
                interfaces=("frame",),
            ),
        ),
    )
    projection = CandidatePromotionCompiler._projection(mechanism)
    mapping = CandidateCanonicalInstanceMapping(
        candidate_instance_id="shaft",
        canonical_instance_id="component-1",
        canonical_path=f"/physical_mechanisms/{request.canonical_target_mechanism_id}/components/component-1",
        classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
        source_identity="candidate:physical-instance:shaft",
    )
    operation = ChangeOperation(
        operation="add",
        path=f"/physical_mechanisms/{request.canonical_target_mechanism_id}",
        value=mechanism.model_dump(mode="json"),
    )
    proposal = ChangeProposal(
        id=f"promotion:{request.canonical_target_mechanism_id}",
        title="fixture promotion",
        status=ProposalStatus.DRAFT,
        base_revision=request.source_revision,
        base_state_hash=request.source_state_hash,
        actor="candidate-promotion",
        operations=[operation],
    )
    from mechcad_harness.candidates.promotion_models import promotion_proposal_hash

    compilation = CandidatePromotionCompilation(
        canonical_mechanism=mechanism,
        proposal=proposal,
        promotion_proposal_hash=promotion_proposal_hash(
            request.source_revision, request.source_state_hash, (operation,)
        ),
        mapping=(mapping,),
        projection=projection,
    )
    readiness = PromotionReadiness(
        project_id=request.project_id,
        source_revision=request.source_revision,
        source_state_hash=request.source_state_hash,
        source_binding_hash="sha256:" + "1" * 64,
        request_hash=request.request_hash,
        candidate_hash=request.candidate.candidate_hash,
        m12_3_result_hash=request.m12_3_result.result_hash,
        evaluation_hash=request.evaluation.evaluation_hash,
        selection_hash=request.selection.selection_hash,
        evaluation_scope_hash=request.evaluation.evaluation_scope_hash,
        promotion_policy_hash=request.promotion_policy.policy_hash,
        canonical_target_mechanism_id=request.canonical_target_mechanism_id,
        mapping=(mapping,),
        classification_identities=tuple(
            item.classification_hash for item in request.classifications
        ),
    )
    scope = PrePromotionM10ScopeProjection(
        joint_semantic_key="joint-output",
        angle_interval_deg=(0.0, 360.0),
        required_clearance_mm=1.0,
        physical_pair_requirements=(
            PromotionPhysicalPairRequirement(
                requirement_key="fixture-pair",
                first_instance_id="component-1",
                first_interface_id="frame",
                second_instance_id="component-2",
                second_interface_id="frame",
            ),
        ),
    )
    return readiness, compilation, scope


class _Evidence:
    def __init__(self, events, record):
        self.events = events
        self.record = record

    def load_invalidation(self, project_id, revision):
        self.events.append("invalidation_reload")
        if self.record is None:
            raise RuntimeError("missing invalidation")
        return self.record


class _Controller:
    def __init__(self, tmp_path, request, events, *, invalidation=None, apply_error=None):
        self.workspace = tmp_path
        self.events = events
        self.evidence = _Evidence(events, invalidation)
        self.request = request
        self.apply_error = apply_error
        self.run = None

    def create_run(self, project_id, *, expected_source):
        self.events.append("create_run")
        assert expected_source == SourceBinding(
            project_id=self.request.project_id,
            revision=self.request.source_revision,
            state_hash=self.request.source_state_hash,
        )
        self.run = Run(
            run_id="RUN-1",
            project_id=project_id,
            initial_revision=self.request.source_revision,
            initial_state_hash=self.request.source_state_hash,
            active_revision=self.request.source_revision,
            active_state_hash=self.request.source_state_hash,
        )
        return self.run

    def apply_approved_proposal(self, run_id, proposal):
        self.events.append("apply")
        if self.apply_error is not None:
            raise self.apply_error
        return self.run.model_copy(
            update={
                "active_revision": self.request.source_revision + 1,
                "active_state_hash": "sha256:" + "2" * 64,
            }
        )

    def fail_run(self, run_id, *, error):
        self.events.append("fail_run")
        self.run = self.run.model_copy(update={"status": RunStatus.FAILED})
        return self.run


class _Compiler:
    def __init__(self, manager, request, events, readiness, compilation):
        self.state_manager = manager
        self.request = request
        self.events = events
        self.readiness = readiness
        self.compilation = compilation

    def validate_readiness(self, request):
        self.events.append("readiness")
        return self.readiness

    def compile(self, state, request):
        self.events.append("compilation")
        assert state.revision == request.source_revision
        return self.compilation


class _ManifestRecorder:
    def __init__(self, events, *, failure=None):
        self.events = events
        self.service = PromotionManifestService()
        self.failure = failure

    def publish_decision(self, *args, **kwargs):
        self.events.append("decision_publish")
        if self.failure == "decision":
            raise RuntimeError("decision publication failed")
        return self.service.publish_decision(*args, **kwargs)

    def resolve_decision(self, *args, **kwargs):
        self.events.append("decision_reload")
        return self.service.resolve_decision(*args, **kwargs)

    def publish_result(self, *args, **kwargs):
        self.events.append("result_publish")
        if self.failure == "result":
            raise RuntimeError("result publication failed")
        return self.service.publish_result(*args, **kwargs)

    def resolve_result(self, *args, **kwargs):
        self.events.append("result_reload")
        return self.service.resolve_result(*args, **kwargs)


class _ResultFreshResolutionFailure(PromotionManifestService):
    def resolve_result(self, *args, **kwargs):
        raise RuntimeError("fresh result resolution failed")


def _service(
    tmp_path,
    *,
    manifest_failure=None,
    apply_error=None,
    invalidation=None,
    manifest_service=None,
):
    request, state, manager = _request_and_manager(tmp_path)
    readiness, compilation, scope = _compiled(request)
    events = []
    controller = _Controller(
        tmp_path,
        request,
        events,
        invalidation=invalidation
        or InvalidationRecord(
            project_id=request.project_id,
            revision=request.source_revision + 1,
            parent_revision=request.source_revision,
            changeset_id="CS-1",
            changed_paths=(f"/physical_mechanisms/{request.canonical_target_mechanism_id}",),
            directly_invalidated_nodes=(),
            transitively_invalidated_nodes=(),
            created_at="2026-01-01T00:00:00+00:00",
        ),
        apply_error=apply_error,
    )
    compiler = _Compiler(manager, request, events, readiness, compilation)
    manifest = manifest_service or _ManifestRecorder(events, failure=manifest_failure)
    service = CandidatePromotionApplicationService(
        compiler,
        controller,
        manifest_service=manifest,
    )
    service._scope_projection = lambda request: scope
    return service, request, state, manager, controller, events, scope


def _real_controller_service(
    tmp_path, *, manifest_failure=None, fail_invalidation=False, manifest_service=None
):
    request, state, manager = _request_and_manager(tmp_path)
    readiness, compilation, scope = _compiled(request)
    dependency_path = tmp_path / "dependencies.json"
    dependency_path.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "when": ["/physical_mechanisms/*"],
                        "invalidates": [
                            "analysis.continuous_clearance_proof",
                            "analysis.kinematic_sweep",
                        ],
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    evidence = EvidenceStore(
        tmp_path, manager, DependencyGraph.from_yaml(dependency_path)
    )
    if fail_invalidation:
        evidence.record_invalidation = lambda record: (_ for _ in ()).throw(
            RuntimeError("invalidation disk failure")
        )
    controller = RunController(
        tmp_path,
        manager,
        ChangeEngine(
            manager,
            OwnershipPolicy(
                [{"path": "/physical_mechanisms/*", "owner": "candidate-promotion"}]
            ),
        ),
        evidence,
    )
    events = []
    compiler = _Compiler(manager, request, events, readiness, compilation)
    manifest = manifest_service or _ManifestRecorder(events, failure=manifest_failure)
    service = CandidatePromotionApplicationService(
        compiler, controller, manifest_service=manifest
    )
    service._scope_projection = lambda request: scope
    return service, request, state, manager, controller, events


def _revision_fixture(manager, project_id, revision):
    path = manager._revision_path(project_id, revision)
    raw = path.read_bytes()
    return raw, json.loads(raw.decode("utf-8"))


def test_promotion_application_uses_one_run_scope_and_ordered_controller_lifecycle(tmp_path):
    service, request, state, manager, controller, events, _ = _service(tmp_path)

    result = service.promote_selected_candidate(request)

    assert result.status.value == "promotion_applied"
    assert result.decision_artifact_id
    assert result.result_artifact_id
    assert result.applied_revision == request.source_revision + 1
    assert events == [
        "readiness",
        "compilation",
        "create_run",
        "decision_publish",
        "decision_reload",
        "apply",
        "invalidation_reload",
        "result_publish",
        "result_reload",
    ]
    assert controller.run.status is RunStatus.CREATED
    assert manager.load_current_pointer(request.project_id)["revision"] == state.revision


def test_decision_publication_failure_fails_created_run_without_canonical_mutation(tmp_path):
    service, request, state, manager, controller, events, _ = _service(
        tmp_path, manifest_failure="decision"
    )
    before_pointer = manager.load_current_pointer(request.project_id)
    before_bytes, before_payload = _revision_fixture(
        manager, request.project_id, request.source_revision
    )

    result = service.promote_selected_candidate(request)

    assert result.status.value == "pre_apply_failure"
    assert controller.run.status is RunStatus.FAILED
    assert manager.load_current_pointer(request.project_id) == before_pointer
    after_bytes, after_payload = _revision_fixture(
        manager, request.project_id, request.source_revision
    )
    assert after_bytes == before_bytes
    assert after_payload == before_payload
    assert state_hash(manager.load_revision(request.project_id, request.source_revision)) == before_pointer[
        "state_hash"
    ]
    assert "apply" not in events
    assert events[-1] == "fail_run"


def test_semantically_tampered_reused_proposal_id_is_rejected_before_run_creation(tmp_path):
    service, request, state, manager, controller, events, _ = _service(tmp_path)
    before_pointer = manager.load_current_pointer(request.project_id)
    before_bytes, before_payload = _revision_fixture(
        manager, request.project_id, request.source_revision
    )
    service.compiler.compilation.proposal.operations.append(
        ChangeOperation(
            operation="remove",
            path=f"/physical_mechanisms/{request.canonical_target_mechanism_id}",
        )
    )

    result = service.promote_selected_candidate(request)

    assert result.status.value == "pre_apply_failure"
    assert "create_run" not in events
    assert manager.load_current_pointer(request.project_id) == before_pointer
    after_bytes, after_payload = _revision_fixture(
        manager, request.project_id, request.source_revision
    )
    assert after_bytes == before_bytes
    assert after_payload == before_payload
    assert state_hash(manager.load_revision(request.project_id, request.source_revision)) == before_pointer[
        "state_hash"
    ]
    assert controller.run is None


def test_change_engine_rejection_is_distinct_and_does_not_advance_revision(tmp_path):
    error = StaleProposalError("stale proposal")
    service, request, state, manager, controller, events, _ = _service(
        tmp_path, apply_error=error
    )
    before_pointer = manager.load_current_pointer(request.project_id)
    before_bytes, before_payload = _revision_fixture(
        manager, request.project_id, request.source_revision
    )

    result = service.promote_selected_candidate(request)

    assert result.status.value == "changeengine_rejected"
    assert controller.run.status is RunStatus.FAILED
    assert manager.load_current_pointer(request.project_id) == before_pointer
    after_bytes, after_payload = _revision_fixture(
        manager, request.project_id, request.source_revision
    )
    assert after_bytes == before_bytes
    assert after_payload == before_payload
    assert state_hash(manager.load_revision(request.project_id, request.source_revision)) == before_pointer[
        "state_hash"
    ]
    assert events[-1] == "fail_run"


def test_post_apply_run_transition_failure_is_not_change_engine_rejection(
    tmp_path, monkeypatch
):
    service, request, state, manager, controller, events = _real_controller_service(
        tmp_path
    )
    monkeypatch.setattr(
        ConvergenceTracker,
        "record_revision",
        staticmethod(
            lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError("convergence transition failed")
            )
        ),
    )

    result = service.promote_selected_candidate(request)

    assert result.status.value == "promotion_applied_but_run_transition_failed"
    assert result.applied_revision == request.source_revision + 1
    assert result.result_artifact_id is None
    assert manager.load_current_pointer(request.project_id)["revision"] == state.revision + 1
    fresh_manager = StateManager(tmp_path)
    fresh_pointer = fresh_manager.load_current_pointer(request.project_id)
    assert fresh_pointer["revision"] == request.source_revision + 1
    assert fresh_pointer["state_hash"] == result.applied_state_hash
    fresh_state = fresh_manager.load_revision(
        request.project_id, request.source_revision + 1
    )
    assert state_hash(fresh_state) == result.applied_state_hash
    decision_artifact = ArtifactStore(
        tmp_path, project_id=request.project_id, run_id="lookup"
    ).existing_in_project(result.decision_artifact_id)
    assert decision_artifact is not None
    fresh_run = controller.get_run(decision_artifact.run_id, request.project_id)
    assert (fresh_run.active_revision, fresh_run.active_state_hash) == (
        request.source_revision + 1,
        result.applied_state_hash,
    )
    assert fresh_run.status is RunStatus.BLOCKED
    assert verify_promoted_mechanism(result).status is not PromotedMechanismVerificationStatus.VERIFIED


def test_post_apply_invalidation_persistence_failure_preserves_applied_revision(tmp_path):
    service, request, state, manager, controller, events = _real_controller_service(
        tmp_path, fail_invalidation=True
    )

    result = service.promote_selected_candidate(request)

    assert result.status.value == "promotion_applied_but_invalidation_persistence_failed"
    assert result.applied_revision == request.source_revision + 1
    assert result.result_artifact_id is None
    assert "result_publish" not in events
    fresh_manager = StateManager(tmp_path)
    fresh_pointer = fresh_manager.load_current_pointer(request.project_id)
    assert fresh_pointer["revision"] == request.source_revision + 1
    assert fresh_pointer["state_hash"] == result.applied_state_hash
    fresh_state = fresh_manager.load_revision(
        request.project_id, request.source_revision + 1
    )
    assert fresh_state.revision == request.source_revision + 1
    assert state_hash(fresh_state) == result.applied_state_hash
    decision_artifact = ArtifactStore(
        tmp_path, project_id=request.project_id, run_id="lookup"
    ).existing_in_project(result.decision_artifact_id)
    assert decision_artifact is not None
    fresh_run = controller.get_run(decision_artifact.run_id, request.project_id)
    assert (fresh_run.active_revision, fresh_run.active_state_hash) == (
        request.source_revision + 1,
        result.applied_state_hash,
    )
    assert fresh_run.status is RunStatus.BLOCKED
    result_artifacts = tuple(
        (
            tmp_path
            / "projects"
            / request.project_id
            / "runs"
            / decision_artifact.run_id
            / "artifacts"
        ).glob("PROMOTION-RESULT-*")
    )
    assert result_artifacts == ()
    assert verify_promoted_mechanism(result).status is not PromotedMechanismVerificationStatus.VERIFIED


def test_invalidation_verification_failure_keeps_applied_revision_and_publishes_no_result(tmp_path):
    bad_record = InvalidationRecord(
        project_id="wrong-project",
        revision=2,
        parent_revision=1,
        changeset_id="CS-1",
        changed_paths=("/wrong",),
        directly_invalidated_nodes=(),
        transitively_invalidated_nodes=(),
        created_at="2026-01-01T00:00:00+00:00",
    )
    service, request, state, manager, controller, events = _real_controller_service(
        tmp_path
    )
    controller.evidence.load_invalidation = lambda project_id, revision: bad_record

    result = service.promote_selected_candidate(request)

    assert result.status.value == "promotion_applied_but_invalidation_verification_failed"
    assert result.applied_revision == request.source_revision + 1
    assert result.result_artifact_id is None
    fresh_manager = StateManager(tmp_path)
    fresh_pointer = fresh_manager.load_current_pointer(request.project_id)
    assert fresh_pointer["revision"] == request.source_revision + 1
    assert fresh_pointer["state_hash"] == result.applied_state_hash
    fresh_state = fresh_manager.load_revision(
        request.project_id, request.source_revision + 1
    )
    assert fresh_state.revision == request.source_revision + 1
    assert state_hash(fresh_state) == result.applied_state_hash
    decision_artifact = ArtifactStore(
        tmp_path, project_id=request.project_id, run_id="lookup"
    ).existing_in_project(result.decision_artifact_id)
    assert decision_artifact is not None
    fresh_run = controller.get_run(decision_artifact.run_id, request.project_id)
    assert (fresh_run.active_revision, fresh_run.active_state_hash) == (
        request.source_revision + 1,
        result.applied_state_hash,
    )
    assert fresh_run.status is RunStatus.CREATED
    result_artifacts = tuple(
        (
            tmp_path
            / "projects"
            / request.project_id
            / "runs"
            / decision_artifact.run_id
            / "artifacts"
        ).glob("PROMOTION-RESULT-*")
    )
    assert result_artifacts == ()
    assert verify_promoted_mechanism(result).status is not PromotedMechanismVerificationStatus.VERIFIED
    assert "result_publish" not in events


def test_result_provenance_failure_never_rolls_back_applied_revision(tmp_path):
    service, request, state, manager, controller, events = _real_controller_service(
        tmp_path, manifest_failure="result"
    )

    result = service.promote_selected_candidate(request)

    assert result.status.value == "promotion_applied_but_result_provenance_failed"
    assert result.applied_revision == request.source_revision + 1
    assert result.result_artifact_id is None
    fresh_manager = StateManager(tmp_path)
    fresh_pointer = fresh_manager.load_current_pointer(request.project_id)
    assert fresh_pointer["revision"] == request.source_revision + 1
    assert fresh_pointer["state_hash"] == result.applied_state_hash
    fresh_state = fresh_manager.load_revision(
        request.project_id, request.source_revision + 1
    )
    assert fresh_state.revision == request.source_revision + 1
    assert state_hash(fresh_state) == result.applied_state_hash
    decision_artifact = ArtifactStore(
        tmp_path, project_id=request.project_id, run_id="lookup"
    ).existing_in_project(result.decision_artifact_id)
    assert decision_artifact is not None
    fresh_run = controller.get_run(decision_artifact.run_id, request.project_id)
    assert (fresh_run.active_revision, fresh_run.active_state_hash) == (
        request.source_revision + 1,
        result.applied_state_hash,
    )
    assert fresh_run.status is RunStatus.CREATED
    result_artifacts = tuple(
        (
            tmp_path
            / "projects"
            / request.project_id
            / "runs"
            / decision_artifact.run_id
            / "artifacts"
        ).glob("PROMOTION-RESULT-*")
    )
    assert result_artifacts == ()
    assert verify_promoted_mechanism(result).status is not PromotedMechanismVerificationStatus.VERIFIED


def test_result_fresh_resolution_failure_preserves_published_artifact_id(tmp_path):
    manifest = _ResultFreshResolutionFailure()
    service, request, state, manager, controller, events = _real_controller_service(
        tmp_path, manifest_service=manifest
    )

    result = service.promote_selected_candidate(request)

    assert result.status.value == "promotion_applied_but_result_provenance_failed"
    assert result.result_artifact_id
    assert result.applied_revision == request.source_revision + 1
    assert manager.load_current_pointer(request.project_id)["revision"] == state.revision + 1
    fresh_manager = StateManager(tmp_path)
    fresh_pointer = fresh_manager.load_current_pointer(request.project_id)
    assert fresh_pointer["revision"] == request.source_revision + 1
    assert fresh_pointer["state_hash"] == result.applied_state_hash
    fresh_state = fresh_manager.load_revision(
        request.project_id, request.source_revision + 1
    )
    assert state_hash(fresh_state) == result.applied_state_hash
    decision_artifact = ArtifactStore(
        tmp_path, project_id=request.project_id, run_id="lookup"
    ).existing_in_project(result.decision_artifact_id)
    assert decision_artifact is not None
    fresh_run = controller.get_run(decision_artifact.run_id, request.project_id)
    assert (fresh_run.active_revision, fresh_run.active_state_hash) == (
        request.source_revision + 1,
        result.applied_state_hash,
    )
    assert fresh_run.status is RunStatus.CREATED
    assert verify_promoted_mechanism(result).status is not PromotedMechanismVerificationStatus.VERIFIED
