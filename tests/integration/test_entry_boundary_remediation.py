from __future__ import annotations

from pathlib import Path

import pytest

from mechcad_harness.candidates import CandidateIntegrityError
from mechcad_harness.candidates.models import (
    CandidateSourceBinding,
    CandidateSourceReference,
    CandidateSynthesisRequest,
)
from mechcad_harness.revolute_drive import DriveArchitecture
from mechcad_harness.state import state_hash

from test_m12_revolute_drive_production import (
    _ALL_CONSUMED_PATHS,
    PROJECT_ID,
    bearing_specification,
    body_specification,
    build_application,
    hub_specification,
    motor_specification,
    mount_specification,
    policy_for,
    requirements,
    shaft_specification,
    template,
    workspace_snapshot,
)


def _make_at1_request(application) -> CandidateSynthesisRequest:
    state = application.state_manager.load_current_state(application.project_id)
    binding = CandidateSourceBinding(
        project_id=application.project_id,
        source_revision=state.revision,
        source_state_hash=state_hash(state),
        consumed_authority=(
            CandidateSourceReference(
                path=path,
                value_hash="pending",
                authority=authority,
            )
            for path, authority in _ALL_CONSUMED_PATHS
        ),
    ).bound_to(state)
    return CandidateSynthesisRequest(
        schema_version="candidate-synthesis-request@1",
        source_binding=binding,
        required_joint_ids=("J-1",),
        requested_joint_ids=("J-1",),
    )


def _legacy_template():
    return template(
        DriveArchitecture.DIRECT_DRIVE,
        motor_specification=motor_specification(),
        shaft_specification=shaft_specification(),
        bearing_a_specification=bearing_specification(),
        bearing_b_specification=bearing_specification(),
        hub_specification=hub_specification(),
        mount_specification=mount_specification(),
        driven_body_specification=body_specification(),
    )


def _make_at2_request_with_wrong_semantic_hash(application) -> CandidateSynthesisRequest:
    state = application.state_manager.load_current_state(application.project_id)
    binding = CandidateSourceBinding(
        project_id=application.project_id,
        source_revision=state.revision,
        source_state_hash=state_hash(state),
        consumed_authority=(
            CandidateSourceReference(
                path=path,
                value_hash="pending",
                authority=authority,
            )
            for path, authority in _ALL_CONSUMED_PATHS
        ),
    ).bound_to(state)
    return CandidateSynthesisRequest(
        schema_version="candidate-synthesis-request@2",
        source_binding=binding,
        semantic_source_binding_hash="sha256:" + "0" * 64,
        required_joint_ids=("J-1",),
        requested_joint_ids=("J-1",),
    )


def test_final_entry_rejects_at1_before_any_production_operation(tmp_path, monkeypatch):
    application = build_application(tmp_path)
    at1_request = _make_at1_request(application)
    before = workspace_snapshot(application.state_manager.workspace)

    invoked: list[str] = []

    def refuse(name):
        def _spy(*args, **kwargs):
            invoked.append(name)
            raise AssertionError(f"{name} must not be invoked for @1 request")
        return _spy

    monkeypatch.setattr(application.state_manager, "load_current_state", refuse("load_current_state"))
    monkeypatch.setattr(application.revolute_drive_service, "construct_candidate", refuse("construct_candidate"))
    monkeypatch.setattr(application.revolute_drive_service, "evaluate", refuse("evaluate"))
    monkeypatch.setattr(application.candidate_integrity_verifier, "verify", refuse("verify"))
    monkeypatch.setattr(application.candidate_currentness_service, "evaluate", refuse("currentness_evaluate"))
    monkeypatch.setattr(application.candidate_publication_service, "publish", refuse("publish"))
    monkeypatch.setattr(application.candidate_publication_service.store, "publish", refuse("artifact_publish"))
    monkeypatch.setattr(application, "create_run", refuse("create_run"))
    monkeypatch.setattr(application.candidate_cad_realization_service, "realize", refuse("cad_realize"))
    monkeypatch.setattr(application.candidate_m10_evaluation_service, "evaluate", refuse("m10_evaluate"))
    monkeypatch.setattr(application.candidate_provenance_artifact_service, "publish_candidate_cad", refuse("cad_publication"))
    monkeypatch.setattr(application.candidate_provenance_artifact_service, "publish_candidate_evaluation", refuse("evaluation_publication"))

    with pytest.raises(CandidateIntegrityError, match="candidate-synthesis-request@2"):
        application.realize_and_evaluate_revolute_drive(
            request=at1_request,
            policy=policy_for(DriveArchitecture.DIRECT_DRIVE),
            template_input=template(DriveArchitecture.DIRECT_DRIVE),
            requirements=requirements(),
        )

    assert invoked == []
    assert workspace_snapshot(application.state_manager.workspace) == before


def test_final_entry_rejects_forged_request_semantic_binding_before_construction(
    tmp_path, monkeypatch
):
    application = build_application(tmp_path)
    mixed_request = _make_at2_request_with_wrong_semantic_hash(application)

    invoked: list[str] = []

    def refuse(name):
        def _spy(*args, **kwargs):
            invoked.append(name)
            raise AssertionError(f"{name} must not be invoked for mixed-family request")
        return _spy

    monkeypatch.setattr(application.revolute_drive_service, "construct_candidate", refuse("construct_candidate"))
    monkeypatch.setattr(application.revolute_drive_service, "evaluate", refuse("evaluate"))
    monkeypatch.setattr(application.candidate_publication_service, "publish", refuse("publish"))

    with pytest.raises(CandidateIntegrityError):
        application.realize_and_evaluate_revolute_drive(
            request=mixed_request,
            policy=policy_for(DriveArchitecture.DIRECT_DRIVE),
            template_input=template(DriveArchitecture.DIRECT_DRIVE),
            requirements=requirements(),
        )

    assert invoked == []


def test_historical_replay_resolves_at1_publication_without_new_production(tmp_path, monkeypatch):
    application = build_application(tmp_path)

    at1_request = _make_at1_request(application)
    policy = policy_for(DriveArchitecture.DIRECT_DRIVE)
    construction = application.revolute_drive_service.construct_candidate(
        at1_request,
        policy,
        _legacy_template(),
    )
    assert construction.candidate is not None
    assert construction.candidate.schema_version == "mechanical-design-candidate@1"

    publication = application.candidate_publication_service.publish(
        construction.candidate,
        at1_request,
        policy,
    )
    before_replay = workspace_snapshot(application.state_manager.workspace)

    invoked: list[str] = []

    def refuse(name):
        def _spy(*args, **kwargs):
            invoked.append(name)
            raise AssertionError(f"{name} must not be invoked during historical replay")
        return _spy

    monkeypatch.setattr(application.revolute_drive_service, "construct_candidate", refuse("construct_candidate"))
    monkeypatch.setattr(application.revolute_drive_service, "evaluate", refuse("evaluate"))
    monkeypatch.setattr(application.candidate_publication_service, "publish", refuse("publish"))

    resolved = application.candidate_publication_service.resolve(
        artifact_id=publication.artifact.artifact_id,
    )

    assert resolved.candidate.schema_version == "mechanical-design-candidate@1"
    assert resolved.candidate.candidate_hash == construction.candidate.candidate_hash
    assert invoked == []
    assert workspace_snapshot(application.state_manager.workspace) == before_replay

def test_historical_replay_rejects_tampered_publication(tmp_path):
    application = build_application(tmp_path)

    at1_request = _make_at1_request(application)
    policy = policy_for(DriveArchitecture.DIRECT_DRIVE)
    construction = application.revolute_drive_service.construct_candidate(
        at1_request,
        policy,
        _legacy_template(),
    )
    assert construction.candidate is not None

    publication = application.candidate_publication_service.publish(
        construction.candidate,
        at1_request,
        policy,
    )

    store = application.candidate_publication_service.store
    artifact = store.read_verified_strict(
        publication.artifact.artifact_id,
        expected_type=__import__("mechcad_harness.artifacts", fromlist=["ArtifactType"]).ArtifactType.JSON,
    )
    assert artifact is not None
    original_artifact, original_content = artifact

    import json

    payload = json.loads(original_content)
    payload["candidate"]["component_specifications"] = []
    tampered_content = json.dumps(payload).encode()

    tampered_artifact = store.publish(
        artifact_id="CAND-TAMPERED",
        artifact_type=__import__("mechcad_harness.artifacts", fromlist=["ArtifactType"]).ArtifactType.JSON,
        filename="candidate.json",
        content=tampered_content,
        producer_tool_name="tampered",
        producer_tool_version="1",
        bound_revision=original_artifact.bound_revision,
        bound_state_hash=original_artifact.bound_state_hash,
        input_hash=original_artifact.input_hash,
    )

    with pytest.raises(CandidateIntegrityError):
        application.candidate_publication_service.resolve(
            artifact_id=tampered_artifact.artifact_id,
        )
