from datetime import datetime, timezone
import threading

import pytest


def _state(with_parameter=None):
    from mechcad_harness.models import Constraint, DesignState, Requirement

    return DesignState(
        id="DES-1",
        revision=1,
        requirements=[Requirement(id="REQ-TRANSMISSION-OUTPUT-SPEED", name="Output speed", description="Canonical")],
        constraints=[Constraint(id="CON-TRANSMISSION-OUTPUT-INTERFACE", name="Interface", expression="Canonical")],
        authoritative_parameters=[] if with_parameter is None else [with_parameter],
    )


def _setup(tmp_path, *, state=None):
    from mechcad_harness.agents.constraint_requests import ConstraintRequestLifecycle, ConstraintRequestRecord, ConstraintRequestStore
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionMaterializer, ConstraintResolutionStore, OutputAngularSpeedAnswer
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.models import ConstraintRequest
    from mechcad_harness.state import StateManager

    manager = StateManager(tmp_path)
    manager.create_project("PRJ", state or _state())
    requests = ConstraintRequestStore(tmp_path)
    requests.write(ConstraintRequestRecord(request=ConstraintRequest(id="CRREQ-1", description="speed", revision=1, state_hash=manager._read_current("PRJ")["state_hash"]), project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1.0", source_invocation_id="INV", source_agent_result_id="RES", engineering_scope_id="transmission", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, rationale="needed", lifecycle=ConstraintRequestLifecycle.DISCOVERED))
    command = ConstraintResolutionBatchCommand(command_id="CMD-1", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash=manager._read_current("PRJ")["state_hash"], answers=(ConstraintResolutionAnswer(request_id="CRREQ-1", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s")),), resolver_type="user", resolver_id="u", received_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    materialized = ConstraintResolutionMaterializer(requests, ConstraintResolutionStore(tmp_path)).materialize_batch(command, run_id="RUN")
    return manager, requests, command, materialized


def test_application_service_applies_one_persisted_resolution_to_one_new_revision(tmp_path):
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.state import StateManager, state_hash

    manager, requests, command, materialized = _setup(tmp_path)
    service = ConstraintResolutionApplicationService(manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])), requests)
    result = service.apply_batch(materialized, run_id="RUN")
    state = manager.load_current_state("PRJ")
    assert result.outcome == "applied"
    assert result.old_revision == 1
    assert result.new_revision == 2
    assert result.new_state_hash == state_hash(state)
    assert state.authoritative_parameters[0].source_resolution_id == materialized.resolution_ids[0]
    assert result.parameter_ids == (state.authoritative_parameters[0].id,)
    assert result.proposal_id
    assert result.changeset_id


def test_application_no_change_replay_does_not_create_revision(tmp_path):
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy

    manager, requests, command, materialized = _setup(tmp_path)
    service = ConstraintResolutionApplicationService(manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])), requests)
    first = service.apply_batch(materialized, run_id="RUN")
    second = service.apply_batch(materialized, run_id="RUN")
    assert first.new_revision == 2
    assert second.outcome == "no_change"
    assert second.new_revision == 2
    assert manager._read_current("PRJ")["revision"] == 2


def test_application_rejects_stale_resolution_binding_before_mutation(tmp_path):
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.models import Component

    manager, requests, command, materialized = _setup(tmp_path)
    manager.create_revision("PRJ", manager.load_current_state("PRJ").model_copy(update={"components": [Component(id="P", name="advanced")] }))
    service = ConstraintResolutionApplicationService(manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])), requests)
    with pytest.raises(Exception, match="stale"):
        service.apply_batch(materialized, run_id="RUN")
    assert manager._read_current("PRJ")["revision"] == 2


def test_application_holds_project_lock_from_preparation_through_atomic_commit(tmp_path, monkeypatch):
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy, StaleProposalError
    from mechcad_harness.models import ChangeProposal, ProposalStatus

    manager, requests, command, materialized = _setup(tmp_path)
    service = ConstraintResolutionApplicationService(
        manager,
        ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])),
        requests,
    )
    preparation_started = threading.Event()
    release_application = threading.Event()
    competing_state_loaded = threading.Event()
    competing_finished = threading.Event()
    errors = {}
    original_prepare = service.change_engine.prepare_proposal

    def prepare(project_id, proposal, **kwargs):
        result = original_prepare(project_id, proposal, **kwargs)
        preparation_started.set()
        assert release_application.wait(timeout=5)
        return result

    monkeypatch.setattr(service.change_engine, "prepare_proposal", prepare)
    record = service.resolution_store.load_resolution("PRJ", "RUN", materialized.resolution_ids[0])
    competing_operations, _ = service._plan_operations(
        command,
        manager.load_current_state("PRJ"),
        [(record, requests.load("PRJ", "RUN", record.source_constraint_request_id))],
    )
    competing = ChangeProposal(
        id="CP-COMPETING",
        title="competing",
        status=ProposalStatus.DRAFT,
        base_revision=command.source_revision,
        base_state_hash=command.source_state_hash,
        actor="mechcad-resolution",
        operations=competing_operations,
    )

    def apply_resolution():
        try:
            service.apply_batch(materialized, run_id="RUN")
        except BaseException as exc:
            errors["application"] = exc

    def compete_with_stale_snapshot():
        competing_state_loaded.set()
        try:
            service.change_engine.apply_proposal("PRJ", competing)
        except BaseException as exc:
            errors["competing"] = exc
        finally:
            competing_finished.set()

    application_thread = threading.Thread(target=apply_resolution)
    competing_thread = threading.Thread(target=compete_with_stale_snapshot)
    application_thread.start()
    assert preparation_started.wait(timeout=5)
    competing_thread.start()
    assert competing_state_loaded.wait(timeout=5)
    assert not competing_finished.wait(timeout=0.1)
    release_application.set()
    application_thread.join(timeout=5)
    competing_thread.join(timeout=5)

    assert not application_thread.is_alive()
    assert not competing_thread.is_alive()
    assert "application" not in errors
    assert isinstance(errors["competing"], StaleProposalError)
    assert manager._read_current("PRJ")["revision"] == 2
    assert len(manager.load_current_state("PRJ").authoritative_parameters) == 1


def test_ownership_allows_resolution_only_on_authoritative_parameters(tmp_path):
    from mechcad_harness.changes import OwnershipPolicy, OwnershipViolationError

    policy = OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])
    policy.check("/authoritative_parameters/PARAM-1", "mechcad-resolution")
    with pytest.raises(OwnershipViolationError):
        policy.check("/authoritative_parameters/PARAM-1", "other")
    with pytest.raises(OwnershipViolationError):
        policy.check("/requirements/REQ-1", "mechcad-resolution")


def test_repository_ownership_config_limits_resolution_actor_to_authoritative_parameters():
    from mechcad_harness.changes import OwnershipPolicy, OwnershipViolationError

    policy = OwnershipPolicy.from_file("config/ownership.yaml")
    policy.check("/authoritative_parameters/PARAM-1", "mechcad-resolution")
    with pytest.raises(OwnershipViolationError):
        policy.check("/requirements/REQ-1", "mechcad-resolution")
    with pytest.raises(OwnershipViolationError):
        policy.check("/authoritative_parameters/PARAM-1", "mechcad-requirements")


def test_application_replaces_existing_parameter_and_preserves_single_identity(tmp_path):
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.agents.constraint_resolution import parameter_id
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.models.design import AuthoritativeAnchor, AuthoritativeParameter, OutputAngularSpeedValue

    existing = AuthoritativeParameter(id=parameter_id(project_id="PRJ", scope_id="transmission", anchor_kind="requirement", anchor_id="REQ-TRANSMISSION-OUTPUT-SPEED", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED), anchor=AuthoritativeAnchor(kind="requirement", id="REQ-TRANSMISSION-OUTPUT-SPEED"), scope_id="transmission", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, value=OutputAngularSpeedValue(kind=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED.value, value_rad_s=0.2), source_resolution_id="CRRES-OLD")
    manager, requests, command, materialized = _setup(tmp_path, state=_state(with_parameter=existing))
    service = ConstraintResolutionApplicationService(manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])), requests)
    result = service.apply_batch(materialized, run_id="RUN")
    parameters = manager.load_current_state("PRJ").authoritative_parameters
    assert result.outcome == "applied"
    assert result.new_revision == 2
    assert len(parameters) == 1
    assert parameters[0].value.value_rad_s == pytest.approx(0.10471975511965977)
    assert parameters[0].source_resolution_id == materialized.resolution_ids[0]


def test_invalid_batch_member_prevents_any_revision(tmp_path):
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionMaterializer, ConstraintResolutionStore, OutputAngularSpeedAnswer, OutputInterfaceAnswer
    from mechcad_harness.agents.constraint_requests import ConstraintRequestLifecycle, ConstraintRequestRecord, ConstraintRequestStore
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.models import ConstraintRequest

    manager, requests, command, materialized = _setup(tmp_path)
    requests.write(ConstraintRequestRecord(request=ConstraintRequest(id="CRREQ-2", description="interface", revision=1, state_hash=command.source_state_hash), project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1.0", source_invocation_id="INV", source_agent_result_id="RES", engineering_scope_id="transmission", key=SupportedConstraintKey.OUTPUT_INTERFACE, rationale="needed", lifecycle=ConstraintRequestLifecycle.DISCOVERED))
    invalid_command = command.model_copy(update={"command_id": "CMD-2", "answers": (ConstraintResolutionAnswer(request_id="CRREQ-1", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s")), ConstraintResolutionAnswer(request_id="CRREQ-2", answer=OutputInterfaceAnswer(interface_type="keyed", torque_transfer_description="shaft")))})
    materialized = ConstraintResolutionMaterializer(requests, ConstraintResolutionStore(tmp_path)).materialize_batch(invalid_command, run_id="RUN")
    service = ConstraintResolutionApplicationService(manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])), requests)
    with pytest.raises(ValueError):
        service.apply_batch(materialized, run_id="RUN")
    assert manager._read_current("PRJ")["revision"] == 1
    assert manager.load_current_state("PRJ").authoritative_parameters == []


def test_multi_answer_batch_creates_one_proposal_one_changeset_and_one_revision(tmp_path):
    from mechcad_harness.agents.constraint_requests import ConstraintRequestLifecycle, ConstraintRequestRecord, ConstraintRequestStore
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionMaterializer, ConstraintResolutionStore, OutputAngularSpeedAnswer, OutputInterfaceAnswer
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.models import ConstraintRequest

    manager, requests, command, _ = _setup(tmp_path)
    requests.write(ConstraintRequestRecord(request=ConstraintRequest(id="CRREQ-2", description="interface", revision=1, state_hash=command.source_state_hash), project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1.0", source_invocation_id="INV", source_agent_result_id="RES", engineering_scope_id="transmission", key=SupportedConstraintKey.OUTPUT_INTERFACE, rationale="needed", lifecycle=ConstraintRequestLifecycle.DISCOVERED))
    batch = command.model_copy(update={"command_id": "CMD-MULTI", "answers": (ConstraintResolutionAnswer(request_id="CRREQ-2", answer=OutputInterfaceAnswer(interface_type="keyed", torque_transfer_description="shaft")), ConstraintResolutionAnswer(request_id="CRREQ-1", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s")))})
    resolution_store = ConstraintResolutionStore(tmp_path)
    old_resolution_id = ConstraintResolutionMaterializer(requests, resolution_store).materialize_batch(command, run_id="RUN").resolution_ids[0]
    old_path = resolution_store._path("PRJ", "RUN", "constraint_resolutions", old_resolution_id)
    old_path.unlink()
    materialized = ConstraintResolutionMaterializer(requests, resolution_store).materialize_batch(batch, run_id="RUN")
    result = ConstraintResolutionApplicationService(manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])), requests).apply_batch(materialized, run_id="RUN")
    assert result.outcome == "applied"
    assert result.new_revision == 2
    assert len(result.parameter_ids) == 2
    assert manager.load_current_state("PRJ").revision == 2
    assert len(manager.load_current_state("PRJ").authoritative_parameters) == 2


def test_application_rejects_nonaccepted_or_wrong_command_resolution(tmp_path):
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionRecord, ResolutionStatus
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy

    manager, requests, command, materialized = _setup(tmp_path)
    store = ConstraintResolutionApplicationService(manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])), requests).resolution_store
    record = store.load_resolution("PRJ", "RUN", materialized.resolution_ids[0])
    path = store._path("PRJ", "RUN", "constraint_resolutions", record.resolution_id)
    path.write_text(record.model_copy(update={"status": ResolutionStatus.REJECTED}).model_dump_json(), encoding="utf-8")
    service = ConstraintResolutionApplicationService(manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])), requests)
    with pytest.raises(ValueError):
        service.apply_batch(materialized, run_id="RUN")
    assert manager._read_current("PRJ")["revision"] == 1


def test_application_rejects_missing_exact_anchor(tmp_path):
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.models import DesignState

    manager, requests, command, materialized = _setup(tmp_path, state=DesignState(id="DES-1", revision=1))
    service = ConstraintResolutionApplicationService(manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])), requests)
    with pytest.raises(ValueError):
        service.apply_batch(materialized, run_id="RUN")
    assert manager._read_current("PRJ")["revision"] == 1
