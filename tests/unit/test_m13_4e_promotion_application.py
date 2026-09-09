from __future__ import annotations

import pytest

from mechcad_harness.artifacts import ArtifactStore
from mechcad_harness.candidates import (
    CandidateMultiJointPromotionApplicationResult,
    CandidatePromotionApplicationService,
    PromotionApplicationStatus,
    PromotionManifestService,
    verify_multi_joint_promotion_application_result,
)
from mechcad_harness.changes.engine import AppliedChangeResult
from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
from mechcad_harness.changes.errors import StaleProposalError
from mechcad_harness.dependency import DependencyGraph, EvidenceStore
from mechcad_harness.runs import RunController, RunStatus
from mechcad_harness.state import RevisionSnapshot, state_hash
from mechcad_harness.candidates import promotion as promotion_module

from test_m13_3_promotion import _promotion_chain


def _route_inputs(tmp_path):
    _, _, _, _, _, request, manager, compiler = _promotion_chain(tmp_path)
    dependency_path = tmp_path / "dependencies.json"
    dependency_path.write_text('{"rules": [], "edges": []}', encoding="utf-8")
    evidence_store = EvidenceStore(
        tmp_path, manager, DependencyGraph.from_yaml(dependency_path)
    )
    controller = RunController(
        tmp_path,
        manager,
        ChangeEngine(
            manager,
            OwnershipPolicy(
                [{"path": "/physical_mechanisms/*", "owner": "mechcad-physical-mechanism"}]
            ),
        ),
        evidence_store,
    )
    service = CandidatePromotionApplicationService(compiler, controller)
    return service, request, manager, controller


def _stored_decision(tmp_path, request, receipt):
    lookup_store = ArtifactStore(
        tmp_path, project_id=request.project_id, run_id="promotion-lookup"
    )
    artifact = lookup_store.existing_in_project(receipt.decision_artifact_id)
    assert artifact is not None
    return artifact, ArtifactStore(
        tmp_path, project_id=request.project_id, run_id=artifact.run_id
    )


def test_full_verifier_proves_durable_decision_result_and_n_plus_one(tmp_path):
    service, request, state_manager, controller = _route_inputs(tmp_path)

    receipt = service._promote_multi_joint_route(request)

    assert receipt.status is PromotionApplicationStatus.PROMOTION_APPLIED
    decision_artifact, store = _stored_decision(tmp_path, request, receipt)
    verify_multi_joint_promotion_application_result(
        receipt,
        manifest_service=service.manifest_service,
        manifest_store=store,
        state_manager=state_manager,
        evidence_store=controller.evidence,
        run_controller=controller,
    )
    assert decision_artifact.artifact_id == receipt.decision_artifact_id
    assert receipt.result_artifact_id
    assert state_manager.load_revision(request.project_id, receipt.applied_revision).revision == (
        request.source_revision + 1
    )


def test_result_publication_receives_the_durable_applied_revision_snapshot(
    tmp_path, monkeypatch
):
    service, request, state_manager, _ = _route_inputs(tmp_path)
    published = []
    original_publish = service.manifest_service.publish_multi_joint_result

    def capture_publish(*args, **kwargs):
        published.append(kwargs["applied"])
        return original_publish(*args, **kwargs)

    monkeypatch.setattr(
        service.manifest_service, "publish_multi_joint_result", capture_publish
    )

    receipt = service._promote_multi_joint_route(request)

    assert receipt.status is PromotionApplicationStatus.PROMOTION_APPLIED
    assert len(published) == 1
    assert type(published[0]) is AppliedChangeResult
    assert type(published[0].snapshot) is RevisionSnapshot
    assert published[0].snapshot.project_id == request.project_id
    assert published[0].snapshot.revision == receipt.applied_revision
    assert published[0].snapshot.state_hash == receipt.applied_state_hash
    assert state_manager.load_revision(request.project_id, receipt.applied_revision) == (
        published[0].snapshot.state
    )


def test_full_verifier_rejects_result_artifact_substitution(tmp_path):
    service, request, state_manager, controller = _route_inputs(tmp_path)
    receipt = service._promote_multi_joint_route(request)
    _, store = _stored_decision(tmp_path, request, receipt)
    forged = receipt.model_copy(
        update={"result_artifact_id": "MULTI-JOINT-PROMOTION-RESULT-forged"}
    )

    with pytest.raises(ValueError, match="artifact|result|binding|missing"):
        verify_multi_joint_promotion_application_result(
            forged,
            manifest_service=service.manifest_service,
            manifest_store=store,
            state_manager=state_manager,
            evidence_store=controller.evidence,
            run_controller=controller,
        )


def test_route_order_uses_private_multi_joint_handoff_and_persists_both_artifacts(tmp_path):
    service, request, manager, controller = _route_inputs(tmp_path)

    receipt = service._promote_multi_joint_route(request)

    assert isinstance(receipt, CandidateMultiJointPromotionApplicationResult)
    assert receipt.status is PromotionApplicationStatus.PROMOTION_APPLIED
    assert receipt.decision_artifact_id
    assert receipt.result_artifact_id
    assert receipt.applied_revision == request.source_revision + 1
    decision_artifact, _ = _stored_decision(tmp_path, request, receipt)
    run = controller.get_run(decision_artifact.run_id, project_id=request.project_id)
    assert run.active_revision == receipt.applied_revision
    assert run.active_state_hash == receipt.applied_state_hash
    assert manager.load_revision(request.project_id, receipt.applied_revision).revision == (
        request.source_revision + 1
    )


def test_original_compilation_projection_identity_is_retained_in_receipt_and_manifest(
    tmp_path, monkeypatch
):
    service, request, _, _ = _route_inputs(tmp_path)
    original_compile = service.compiler.compile_multi_joint
    compiled = []

    def capture_compile(state, promotion_request):
        result = original_compile(state, promotion_request)
        compiled.append(result)
        return result

    monkeypatch.setattr(service.compiler, "compile_multi_joint", capture_compile)

    receipt = service._promote_multi_joint_route(request)
    _, store = _stored_decision(tmp_path, request, receipt)
    manifest = PromotionManifestService().resolve_multi_joint_decision(
        store, receipt.decision_artifact_id
    )

    assert receipt.compilation == compiled[0]
    assert receipt.compilation.compilation_hash == compiled[0].compilation_hash
    assert manifest.compilation_hash == compiled[0].compilation_hash
    assert manifest.projection_hash == compiled[0].projection.projection_hash
    assert manifest.projection == compiled[0].projection
    assert manifest.mapping == compiled[0].mapping


def test_route_context_has_only_exact_typed_route_fields_and_is_used(tmp_path, monkeypatch):
    service, request, _, _ = _route_inputs(tmp_path)
    original_context = promotion_module._MultiJointPromotionRouteContext
    captured = []

    def capture_context(**values):
        captured.append(values)
        return original_context(**values)

    monkeypatch.setattr(
        "mechcad_harness.candidates.promotion._MultiJointPromotionRouteContext",
        capture_context,
    )

    receipt = service._promote_multi_joint_route(request)

    assert receipt.status is PromotionApplicationStatus.PROMOTION_APPLIED
    assert captured
    assert set(captured[0]) == {
        "request",
        "readiness",
        "compilation",
        "run",
        "store",
        "decision_artifact",
    }
    assert set(original_context.__dataclass_fields__) == set(captured[0])


def test_failure_matrix_reports_pre_apply_and_changeengine_without_applied_identity(
    tmp_path, monkeypatch
):
    service, request, _, _ = _route_inputs(tmp_path / "readiness")

    def fail_readiness(_request):
        raise ValueError("readiness failed")

    monkeypatch.setattr(service.compiler, "validate_multi_joint_readiness", fail_readiness)
    receipt = service._promote_multi_joint_route(request)
    assert receipt.status is PromotionApplicationStatus.PRE_APPLY_FAILURE
    assert receipt.decision_artifact_id is None
    assert receipt.result_artifact_id is None
    assert receipt.applied_revision is None
    assert not list((tmp_path / "readiness").glob("projects/*/runs/*/manifest.json"))

    service, request, _, _ = _route_inputs(tmp_path / "decision")

    def fail_decision(*_args, **_kwargs):
        raise RuntimeError("decision publication failed")

    monkeypatch.setattr(service.manifest_service, "publish_multi_joint_decision", fail_decision)
    receipt = service._promote_multi_joint_route(request)
    assert receipt.status is PromotionApplicationStatus.PRE_APPLY_FAILURE
    assert receipt.decision_artifact_id is None
    assert receipt.result_artifact_id is None
    assert list((tmp_path / "decision").glob("projects/*/runs/*/manifest.json"))

    service, request, _, controller = _route_inputs(tmp_path / "changeengine")

    def fail_change_engine(*_args, **_kwargs):
        raise StaleProposalError("stale proposal")

    monkeypatch.setattr(controller.change_engine, "apply_proposal", fail_change_engine)
    receipt = service._promote_multi_joint_route(request)
    assert receipt.status is PromotionApplicationStatus.CHANGEENGINE_REJECTED
    assert receipt.decision_artifact_id
    assert receipt.result_artifact_id is None
    assert receipt.applied_revision is None


def _raise_generic_after_real_application(service, monkeypatch):
    original_validate = service._validate_applied_multi_joint_run

    def raise_after_real_application(applied_run):
        original_validate(applied_run)
        raise RuntimeError("unexpected post-apply controller failure")

    monkeypatch.setattr(
        service, "_validate_applied_multi_joint_run", raise_after_real_application
    )


def test_generic_post_apply_exception_verifies_real_durable_n_plus_one(tmp_path, monkeypatch):
    service, request, state_manager, _ = _route_inputs(tmp_path)
    _raise_generic_after_real_application(service, monkeypatch)
    original_load = state_manager.load_revision
    durable_loads = []

    def record_durable_load(project_id, revision):
        snapshot = original_load(project_id, revision)
        if revision == request.source_revision + 1:
            durable_loads.append(snapshot)
        return snapshot

    monkeypatch.setattr(state_manager, "load_revision", record_durable_load)

    receipt = service._promote_multi_joint_route(request)

    assert receipt.status is PromotionApplicationStatus.PROMOTION_APPLIED_BUT_RUN_TRANSITION_FAILED
    assert receipt.applied_revision == request.source_revision + 1
    assert durable_loads
    assert receipt.applied_state_hash == state_hash(durable_loads[-1])
    assert receipt.result_artifact_id is None


@pytest.mark.parametrize(
    ("error_type", "message"),
    [
        (FileNotFoundError, "N+1 snapshot is missing"),
        (OSError, "N+1 snapshot cannot be read"),
    ],
)
def test_generic_post_apply_exception_fails_closed_when_durable_n_plus_one_cannot_load(
    tmp_path, monkeypatch, error_type, message
):
    service, request, state_manager, _ = _route_inputs(tmp_path)
    _raise_generic_after_real_application(service, monkeypatch)
    original_load = state_manager.load_revision

    def reject_n_plus_one(project_id, revision):
        if revision == request.source_revision + 1:
            raise error_type(message)
        return original_load(project_id, revision)

    monkeypatch.setattr(state_manager, "load_revision", reject_n_plus_one)

    receipt = service._promote_multi_joint_route(request)

    assert receipt.status is PromotionApplicationStatus.PRE_APPLY_FAILURE
    assert receipt.applied_revision is None
    assert receipt.applied_state_hash is None
    assert receipt.result_artifact_id is None


@pytest.mark.parametrize("field", ["active_revision", "active_state_hash"])
def test_generic_post_apply_exception_fails_closed_when_run_disagrees_with_durable_state(
    tmp_path, monkeypatch, field
):
    service, request, _, controller = _route_inputs(tmp_path)
    _raise_generic_after_real_application(service, monkeypatch)
    original_get_run = controller.get_run
    calls = 0

    def mismatched_post_apply_run(run_id, project_id=None):
        nonlocal calls
        calls += 1
        current = original_get_run(run_id, project_id=project_id)
        if calls == 3:
            if field == "active_revision":
                return current.model_copy(update={field: current.active_revision + 1})
            return current.model_copy(update={field: "sha256:" + "f" * 64})
        return current

    monkeypatch.setattr(controller, "get_run", mismatched_post_apply_run)

    receipt = service._promote_multi_joint_route(request)

    assert receipt.status is PromotionApplicationStatus.PRE_APPLY_FAILURE
    assert receipt.applied_revision is None
    assert receipt.applied_state_hash is None
    assert receipt.result_artifact_id is None


def test_real_post_apply_run_transition_failure_preserves_persisted_n_plus_one(
    tmp_path, monkeypatch
):
    service, request, state_manager, _ = _route_inputs(tmp_path)
    base_revision = request.source_revision

    def fail_run_state_persistence(_run):
        raise OSError("run state disk failure")

    monkeypatch.setattr(service.run_controller, "_save", fail_run_state_persistence)

    receipt = service._promote_multi_joint_route(request)

    assert receipt.status is PromotionApplicationStatus.PROMOTION_APPLIED_BUT_RUN_TRANSITION_FAILED
    loaded_state = state_manager.load_revision(request.project_id, receipt.applied_revision)
    assert receipt.applied_revision == base_revision + 1
    assert loaded_state.revision == base_revision + 1
    assert state_hash(loaded_state) == receipt.applied_state_hash
    assert receipt.result_artifact_id is None


def test_real_post_apply_invalidation_persistence_failure_preserves_persisted_n_plus_one(
    tmp_path, monkeypatch
):
    service, request, state_manager, controller = _route_inputs(tmp_path)
    base_revision = request.source_revision

    def fail_invalidation_persistence(_record):
        raise OSError("invalidation disk failure")

    monkeypatch.setattr(
        controller.evidence, "record_invalidation", fail_invalidation_persistence
    )

    receipt = service._promote_multi_joint_route(request)

    assert receipt.status is (
        PromotionApplicationStatus.PROMOTION_APPLIED_BUT_INVALIDATION_PERSISTENCE_FAILED
    )
    loaded_state = state_manager.load_revision(request.project_id, receipt.applied_revision)
    assert receipt.applied_revision == base_revision + 1
    assert loaded_state.revision == base_revision + 1
    assert state_hash(loaded_state) == receipt.applied_state_hash
    assert receipt.result_artifact_id is None
    decision_artifact, _ = _stored_decision(tmp_path, request, receipt)
    blocked_run = controller.get_run(decision_artifact.run_id, project_id=request.project_id)
    assert blocked_run.status is RunStatus.BLOCKED
    assert blocked_run.active_revision == receipt.applied_revision


def test_real_post_apply_invalidation_reload_failure_occurs_after_durable_write(
    tmp_path, monkeypatch
):
    service, request, state_manager, controller = _route_inputs(tmp_path)
    base_revision = request.source_revision
    original_load = controller.evidence.load_invalidation
    persisted = []

    def fail_invalidation_reload(project_id, revision):
        persisted.append(original_load(project_id, revision))
        raise OSError("invalidation reload failed")

    monkeypatch.setattr(
        controller.evidence, "load_invalidation", fail_invalidation_reload
    )

    receipt = service._promote_multi_joint_route(request)

    assert receipt.status is (
        PromotionApplicationStatus.PROMOTION_APPLIED_BUT_INVALIDATION_VERIFICATION_FAILED
    )
    assert persisted and persisted[0].revision == receipt.applied_revision
    loaded_state = state_manager.load_revision(request.project_id, receipt.applied_revision)
    assert receipt.applied_revision == base_revision + 1
    assert loaded_state.revision == base_revision + 1
    assert state_hash(loaded_state) == receipt.applied_state_hash
    assert receipt.result_artifact_id is None


def test_real_post_apply_invalidation_verification_failure_occurs_after_durable_write(
    tmp_path, monkeypatch
):
    service, request, state_manager, controller = _route_inputs(tmp_path)
    base_revision = request.source_revision
    original_verify = service._verify_invalidation
    verified = []

    def fail_invalidation_verification(invalidation, initial_run, applied_run, proposal):
        original_verify(invalidation, initial_run, applied_run, proposal)
        verified.append(invalidation)
        raise ValueError("invalidation verification failed")

    monkeypatch.setattr(service, "_verify_invalidation", fail_invalidation_verification)

    receipt = service._promote_multi_joint_route(request)

    assert receipt.status is (
        PromotionApplicationStatus.PROMOTION_APPLIED_BUT_INVALIDATION_VERIFICATION_FAILED
    )
    assert verified and verified[0].revision == receipt.applied_revision
    loaded_state = state_manager.load_revision(request.project_id, receipt.applied_revision)
    assert receipt.applied_revision == base_revision + 1
    assert loaded_state.revision == base_revision + 1
    assert state_hash(loaded_state) == receipt.applied_state_hash
    assert receipt.result_artifact_id is None


def test_real_post_apply_result_publication_failure_follows_complete_lifecycle(
    tmp_path, monkeypatch
):
    service, request, state_manager, controller = _route_inputs(tmp_path)
    base_revision = request.source_revision

    original_publish = ArtifactStore.publish

    def fail_result_publication(store, artifact_id, artifact_type, filename, *args, **kwargs):
        if filename == "multi_joint_result.json":
            raise OSError("result publication failed")
        return original_publish(
            store, artifact_id, artifact_type, filename, *args, **kwargs
        )

    monkeypatch.setattr(ArtifactStore, "publish", fail_result_publication)

    receipt = service._promote_multi_joint_route(request)

    assert receipt.status is PromotionApplicationStatus.PROMOTION_APPLIED_BUT_RESULT_PROVENANCE_FAILED
    loaded_state = state_manager.load_revision(request.project_id, receipt.applied_revision)
    assert receipt.applied_revision == base_revision + 1
    assert loaded_state.revision == base_revision + 1
    assert state_hash(loaded_state) == receipt.applied_state_hash
    assert receipt.result_artifact_id is None
    decision_artifact, _ = _stored_decision(tmp_path, request, receipt)
    final_run = controller.get_run(decision_artifact.run_id, project_id=request.project_id)
    assert final_run.active_revision == receipt.applied_revision
    invalidation = controller.evidence.load_invalidation(
        request.project_id, receipt.applied_revision
    )
    assert invalidation.revision == receipt.applied_revision


def test_real_post_apply_result_resolution_failure_keeps_written_bytes_untrusted(
    tmp_path, monkeypatch
):
    service, request, state_manager, _ = _route_inputs(tmp_path)
    base_revision = request.source_revision

    def fail_result_resolution(_store, _artifact_id):
        raise OSError("fresh result resolution failed")

    monkeypatch.setattr(
        service.manifest_service, "resolve_multi_joint_result", fail_result_resolution
    )

    receipt = service._promote_multi_joint_route(request)

    assert receipt.status is PromotionApplicationStatus.PROMOTION_APPLIED_BUT_RESULT_PROVENANCE_FAILED
    result_paths = list(
        (tmp_path / "projects" / request.project_id / "runs").glob(
            "*/artifacts/*/multi_joint_result.json"
        )
    )
    assert len(result_paths) == 1
    assert result_paths[0].is_file()
    assert result_paths[0].read_bytes()
    loaded_state = state_manager.load_revision(request.project_id, receipt.applied_revision)
    assert receipt.applied_revision == base_revision + 1
    assert loaded_state.revision == base_revision + 1
    assert state_hash(loaded_state) == receipt.applied_state_hash
    assert receipt.result_artifact_id is None
