from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.candidates import (
    PromotionManifestService,
    SelectedMultiJointCandidateDecisionManifest,
    MultiJointPromotionResultManifest,
    verify_multi_joint_promotion_application_result,
)
from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
from mechcad_harness.dependency import DependencyGraph, EvidenceStore
from mechcad_harness.runs import RunController
from mechcad_harness.state import StateManager

unit_path = str(Path(__file__).parents[1] / "unit")
if unit_path not in sys.path:
    sys.path.insert(0, unit_path)

from test_m13_4e_promotion_application import _route_inputs


def _strict_project_artifact(tmp_path, project_id, artifact_id):
    lookup_store = ArtifactStore(
        tmp_path, project_id=project_id, run_id="r8-project-lookup"
    )
    verified = lookup_store.read_verified_in_project(
        artifact_id, expected_type=ArtifactType.JSON
    )
    assert verified is not None
    return verified[0]


def _fresh_runtime(tmp_path, decision_artifact, *, store=None):
    fresh_store = store or ArtifactStore(
        tmp_path,
        project_id=decision_artifact.project_id,
        run_id=decision_artifact.run_id,
    )
    fresh_service = PromotionManifestService()
    fresh_manager = StateManager(tmp_path)
    dependency_path = tmp_path / "dependencies.json"
    fresh_evidence = EvidenceStore(
        tmp_path, fresh_manager, DependencyGraph.from_yaml(dependency_path)
    )
    fresh_controller = RunController(
        tmp_path,
        fresh_manager,
        ChangeEngine(
            fresh_manager,
            OwnershipPolicy(
                [{"path": "/physical_mechanisms/*", "owner": "mechcad-physical-mechanism"}]
            ),
        ),
        fresh_evidence,
    )
    return fresh_service, fresh_store, fresh_manager, fresh_evidence, fresh_controller


def _fresh_runtime_for_receipt(tmp_path, receipt):
    decision_artifact = _strict_project_artifact(
        tmp_path, receipt.request.project_id, receipt.decision_artifact_id
    )
    return decision_artifact, _fresh_runtime(tmp_path, decision_artifact)


def _rewrite_artifact_metadata(tmp_path, artifact, updates):
    metadata_path = (tmp_path / artifact.relative_path).parent / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    for key, value in updates.items():
        if value is _MISSING:
            metadata.pop(key, None)
        else:
            metadata[key] = value
    metadata_path.write_text(
        json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _relocate_artifacts(tmp_path, artifacts, target_run_id):
    for artifact in artifacts:
        source_dir = (tmp_path / artifact.relative_path).parent
        target_dir = (
            tmp_path
            / "projects"
            / artifact.project_id
            / "runs"
            / target_run_id
            / "artifacts"
            / artifact.artifact_id
        )
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        source_dir.rename(target_dir)
        metadata_path = target_dir / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["run_id"] = target_run_id
        metadata["relative_path"] = target_dir.joinpath(
            metadata["relative_path"].rsplit("/", 1)[-1]
        ).relative_to(tmp_path).as_posix()
        metadata_path.write_text(
            json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )


class _MissingMetadata:
    pass


_MISSING = _MissingMetadata()


def test_multi_joint_promotion_evidence_survives_fresh_serialized_reload(tmp_path):
    service, request, manager, controller = _route_inputs(tmp_path)
    receipt = service._promote_multi_joint_route(request)

    decision_artifact = _strict_project_artifact(
        tmp_path, receipt.request.project_id, receipt.decision_artifact_id
    )
    del service, manager, controller

    fresh_store = ArtifactStore(
        tmp_path,
        project_id=decision_artifact.project_id,
        run_id=decision_artifact.run_id,
    )
    fresh_service = PromotionManifestService()
    fresh_manager = StateManager(tmp_path)
    dependency_path = tmp_path / "dependencies.json"
    fresh_evidence = EvidenceStore(
        tmp_path, fresh_manager, DependencyGraph.from_yaml(dependency_path)
    )
    fresh_controller = RunController(
        tmp_path,
        fresh_manager,
        ChangeEngine(
            fresh_manager,
            OwnershipPolicy(
                [{"path": "/physical_mechanisms/*", "owner": "mechcad-physical-mechanism"}]
            ),
        ),
        fresh_evidence,
    )
    reloaded_decision_artifact, _ = fresh_store.read_verified_strict(
        receipt.decision_artifact_id, expected_type=ArtifactType.JSON
    )
    assert reloaded_decision_artifact.run_id == decision_artifact.run_id
    assert fresh_controller.get_run(
        reloaded_decision_artifact.run_id,
        project_id=reloaded_decision_artifact.project_id,
    ).run_id == reloaded_decision_artifact.run_id

    result_artifact, _ = fresh_store.read_verified_strict(
        receipt.result_artifact_id, expected_type=ArtifactType.JSON
    )
    assert result_artifact is not None
    decision_payload = json.loads(
        (tmp_path / reloaded_decision_artifact.relative_path).read_text(encoding="utf-8")
    )
    result_payload = json.loads(
        (tmp_path / result_artifact.relative_path).read_text(encoding="utf-8")
    )
    assert SelectedMultiJointCandidateDecisionManifest.model_validate(decision_payload)
    assert MultiJointPromotionResultManifest.model_validate(result_payload)
    decision = fresh_service.resolve_multi_joint_decision(
        fresh_store, receipt.decision_artifact_id
    )
    result = fresh_service.resolve_multi_joint_result(
        fresh_store, receipt.result_artifact_id
    )
    assert reloaded_decision_artifact.run_id == result_artifact.run_id
    assert result.resulting_revision == receipt.applied_revision

    verify_multi_joint_promotion_application_result(
        receipt,
        manifest_service=fresh_service,
        manifest_store=fresh_store,
        state_manager=fresh_manager,
        evidence_store=fresh_evidence,
        run_controller=fresh_controller,
    )

    fresh_manager.create_revision(
        request.project_id, fresh_manager.load_current_state(request.project_id)
    )
    assert fresh_manager.load_current_pointer(request.project_id)["revision"] == (
        receipt.applied_revision + 1
    )
    verify_multi_joint_promotion_application_result(
        receipt,
        manifest_service=fresh_service,
        manifest_store=fresh_store,
        state_manager=fresh_manager,
        evidence_store=fresh_evidence,
        run_controller=fresh_controller,
    )


@pytest.mark.parametrize(
    ("tamper", "value"),
    (("blank", ""), ("missing", _MISSING), ("corrupt", {"run": "id"})),
)
def test_restart_rejects_untrusted_decision_artifact_run_id(tmp_path, tamper, value):
    service, request, manager, controller = _route_inputs(tmp_path)
    receipt = service._promote_multi_joint_route(request)
    decision_artifact = _strict_project_artifact(
        tmp_path, receipt.request.project_id, receipt.decision_artifact_id
    )
    del service, manager, controller

    _rewrite_artifact_metadata(tmp_path, decision_artifact, {"run_id": value})

    lookup_store = ArtifactStore(
        tmp_path, project_id=request.project_id, run_id="r8-run-id-reload"
    )
    assert (
        lookup_store.read_verified_in_project(
            receipt.decision_artifact_id, expected_type=ArtifactType.JSON
        )
        is None
    ), tamper
    fresh_service, fresh_store, _, _, _ = _fresh_runtime(tmp_path, decision_artifact)
    with pytest.raises(ValueError, match="artifact metadata or bytes are unreadable"):
        fresh_service.resolve_multi_joint_decision(
            fresh_store, receipt.decision_artifact_id
        )


def test_restart_rejects_scoped_store_run_id_mismatch(tmp_path, monkeypatch):
    service, request, manager, controller = _route_inputs(tmp_path)
    receipt = service._promote_multi_joint_route(request)
    decision_artifact = _strict_project_artifact(
        tmp_path, receipt.request.project_id, receipt.decision_artifact_id
    )
    del service, manager, controller

    wrong_store = ArtifactStore(
        tmp_path,
        project_id=decision_artifact.project_id,
        run_id="RUN-R8-SCOPED-MISMATCH",
    )
    fresh_service, fresh_store, fresh_manager, fresh_evidence, fresh_controller = (
        _fresh_runtime(tmp_path, decision_artifact, store=wrong_store)
    )

    def unexpected_run_lookup(*_args, **_kwargs):
        raise AssertionError("run lookup must follow trusted artifact scope")

    monkeypatch.setattr(fresh_controller, "get_run", unexpected_run_lookup)
    with pytest.raises(ValueError, match="artifact|missing|scope|binding"):
        verify_multi_joint_promotion_application_result(
            receipt,
            manifest_service=fresh_service,
            manifest_store=fresh_store,
            state_manager=fresh_manager,
            evidence_store=fresh_evidence,
            run_controller=fresh_controller,
        )


def test_restart_rejects_decision_artifacts_naming_nonexistent_durable_run(
    tmp_path, monkeypatch
):
    service, request, manager, controller = _route_inputs(tmp_path)
    receipt = service._promote_multi_joint_route(request)
    decision_artifact = _strict_project_artifact(
        tmp_path, receipt.request.project_id, receipt.decision_artifact_id
    )
    result_artifact = _strict_project_artifact(
        tmp_path, receipt.request.project_id, receipt.result_artifact_id
    )
    del service, manager, controller

    _relocate_artifacts(
        tmp_path,
        (decision_artifact, result_artifact),
        "RUN-R8-NONEXISTENT",
    )
    persisted_decision = _strict_project_artifact(
        tmp_path, request.project_id, receipt.decision_artifact_id
    )
    assert persisted_decision.run_id == "RUN-R8-NONEXISTENT"
    fresh_service, fresh_store, fresh_manager, fresh_evidence, fresh_controller = (
        _fresh_runtime(tmp_path, persisted_decision)
    )
    looked_up = []
    original_get_run = fresh_controller.get_run

    def record_run_lookup(run_id, project_id=None):
        looked_up.append((run_id, project_id))
        return original_get_run(run_id, project_id=project_id)

    monkeypatch.setattr(fresh_controller, "get_run", record_run_lookup)
    with pytest.raises(ValueError, match="run|durable|verification|missing"):
        verify_multi_joint_promotion_application_result(
            receipt,
            manifest_service=fresh_service,
            manifest_store=fresh_store,
            state_manager=fresh_manager,
            evidence_store=fresh_evidence,
            run_controller=fresh_controller,
        )
    assert looked_up == [(persisted_decision.run_id, persisted_decision.project_id)]


def test_restart_rejects_durable_run_from_wrong_project(tmp_path, monkeypatch):
    service, request, manager, controller = _route_inputs(tmp_path)
    receipt = service._promote_multi_joint_route(request)
    decision_artifact = _strict_project_artifact(
        tmp_path, receipt.request.project_id, receipt.decision_artifact_id
    )
    del service, manager, controller

    state_path = (
        tmp_path
        / "projects"
        / decision_artifact.project_id
        / "runs"
        / decision_artifact.run_id
        / "state.json"
    )
    state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    state_payload["project_id"] = "PRJ-R8-WRONG"
    state_path.write_text(
        json.dumps(state_payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    _, runtime = _fresh_runtime_for_receipt(tmp_path, receipt)
    fresh_service, fresh_store, fresh_manager, fresh_evidence, fresh_controller = runtime
    looked_up = []
    original_get_run = fresh_controller.get_run

    def record_run_lookup(run_id, project_id=None):
        looked_up.append((run_id, project_id))
        return original_get_run(run_id, project_id=project_id)

    monkeypatch.setattr(fresh_controller, "get_run", record_run_lookup)
    with pytest.raises(
        ValueError, match=r"multi-joint application result or N-to-N\+1 binding mismatch"
    ):
        verify_multi_joint_promotion_application_result(
            receipt,
            manifest_service=fresh_service,
            manifest_store=fresh_store,
            state_manager=fresh_manager,
            evidence_store=fresh_evidence,
            run_controller=fresh_controller,
        )
    assert looked_up == [(decision_artifact.run_id, decision_artifact.project_id)]


def test_restart_rejects_durable_run_with_wrong_base_binding(tmp_path, monkeypatch):
    service, request, manager, controller = _route_inputs(tmp_path)
    receipt = service._promote_multi_joint_route(request)
    decision_artifact = _strict_project_artifact(
        tmp_path, receipt.request.project_id, receipt.decision_artifact_id
    )
    del service, manager, controller

    state_path = (
        tmp_path
        / "projects"
        / decision_artifact.project_id
        / "runs"
        / decision_artifact.run_id
        / "state.json"
    )
    state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    state_payload["initial_revision"] = receipt.request.source_revision + 99
    state_payload["initial_state_hash"] = "sha256:" + ("0" * 64)
    state_path.write_text(
        json.dumps(state_payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    _, runtime = _fresh_runtime_for_receipt(tmp_path, receipt)
    fresh_service, fresh_store, fresh_manager, fresh_evidence, fresh_controller = runtime
    looked_up = []
    original_get_run = fresh_controller.get_run

    def record_run_lookup(run_id, project_id=None):
        looked_up.append((run_id, project_id))
        return original_get_run(run_id, project_id=project_id)

    monkeypatch.setattr(fresh_controller, "get_run", record_run_lookup)
    with pytest.raises(
        ValueError, match=r"multi-joint application result or N-to-N\+1 binding mismatch"
    ):
        verify_multi_joint_promotion_application_result(
            receipt,
            manifest_service=fresh_service,
            manifest_store=fresh_store,
            state_manager=fresh_manager,
            evidence_store=fresh_evidence,
            run_controller=fresh_controller,
        )
    assert looked_up == [(decision_artifact.run_id, decision_artifact.project_id)]


def test_restart_rejects_result_artifact_from_different_run_with_matching_transition(
    tmp_path, monkeypatch,
):
    service, request, manager, controller = _route_inputs(tmp_path)
    receipt = service._promote_multi_joint_route(request)
    decision_artifact = _strict_project_artifact(
        tmp_path, receipt.request.project_id, receipt.decision_artifact_id
    )
    result_artifact = _strict_project_artifact(
        tmp_path, receipt.request.project_id, receipt.result_artifact_id
    )
    del service, manager, controller

    result_payload = json.loads(
        (tmp_path / result_artifact.relative_path).read_text(encoding="utf-8")
    )
    assert result_payload["base_revision"] == request.source_revision
    assert result_payload["resulting_revision"] == receipt.applied_revision
    _rewrite_artifact_metadata(
        tmp_path, result_artifact, {"run_id": "RUN-R8-RESULT-OTHER"}
    )

    fresh_service, fresh_store, fresh_manager, fresh_evidence, fresh_controller = (
        _fresh_runtime(tmp_path, decision_artifact)
    )
    looked_up = []

    def unexpected_run_lookup(run_id, project_id=None):
        looked_up.append((run_id, project_id))
        raise AssertionError("durable run lookup must follow strict result resolution")

    monkeypatch.setattr(fresh_controller, "get_run", unexpected_run_lookup)
    with pytest.raises(
        ValueError, match="promotion manifest artifact is invalid: artifact identity mismatch"
    ):
        fresh_service.resolve_multi_joint_result(
            fresh_store, receipt.result_artifact_id
        )
    with pytest.raises(
        ValueError, match="promotion manifest artifact is invalid: artifact identity mismatch"
    ):
        verify_multi_joint_promotion_application_result(
            receipt,
            manifest_service=fresh_service,
            manifest_store=fresh_store,
            state_manager=fresh_manager,
            evidence_store=fresh_evidence,
            run_controller=fresh_controller,
        )
    assert looked_up == []


def test_restart_rejects_wrong_run_with_identical_state_transition(tmp_path, monkeypatch):
    service, request, manager, controller = _route_inputs(tmp_path)
    receipt = service._promote_multi_joint_route(request)
    decision_artifact = _strict_project_artifact(
        tmp_path, receipt.request.project_id, receipt.decision_artifact_id
    )
    del service, manager, controller

    state_path = (
        tmp_path
        / "projects"
        / decision_artifact.project_id
        / "runs"
        / decision_artifact.run_id
        / "state.json"
    )
    state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    original_transition = (
        state_payload["initial_revision"],
        state_payload["initial_state_hash"],
        state_payload["active_revision"],
        state_payload["active_state_hash"],
    )
    state_payload["run_id"] = "RUN-R8-WRONG-IDENTITY"
    state_path.write_text(
        json.dumps(state_payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    _, runtime = _fresh_runtime_for_receipt(tmp_path, receipt)
    fresh_service, fresh_store, fresh_manager, fresh_evidence, fresh_controller = runtime
    looked_up = []
    original_get_run = fresh_controller.get_run

    def record_run_lookup(run_id, project_id=None):
        looked_up.append((run_id, project_id))
        return original_get_run(run_id, project_id=project_id)

    monkeypatch.setattr(fresh_controller, "get_run", record_run_lookup)
    with pytest.raises(
        ValueError, match=r"multi-joint application result or N-to-N\+1 binding mismatch"
    ):
        verify_multi_joint_promotion_application_result(
            receipt,
            manifest_service=fresh_service,
            manifest_store=fresh_store,
            state_manager=fresh_manager,
            evidence_store=fresh_evidence,
            run_controller=fresh_controller,
        )
    assert looked_up == [(decision_artifact.run_id, decision_artifact.project_id)]
    reloaded_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert (
        reloaded_state["initial_revision"],
        reloaded_state["initial_state_hash"],
        reloaded_state["active_revision"],
        reloaded_state["active_state_hash"],
    ) == original_transition
