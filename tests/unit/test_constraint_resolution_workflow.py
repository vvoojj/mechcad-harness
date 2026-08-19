from datetime import datetime, timezone

import pytest


def _setup(tmp_path):
    from mechcad_harness.agents.constraint_requests import ConstraintRequestLifecycle, ConstraintRequestRecord, ConstraintRequestStore
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionMaterializer, ConstraintResolutionStore, OutputAngularSpeedAnswer
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.models import Constraint, DesignState, Requirement, ConstraintRequest
    from mechcad_harness.state import StateManager

    manager = StateManager(tmp_path)
    manager.create_project("PRJ", DesignState(id="DES-1", revision=1, requirements=[Requirement(id="REQ-TRANSMISSION-OUTPUT-SPEED", name="Speed", description="Canonical")], constraints=[Constraint(id="CON-TRANSMISSION-OUTPUT-INTERFACE", name="Interface", expression="Canonical")]))
    requests = ConstraintRequestStore(tmp_path)
    request = ConstraintRequestRecord(request=ConstraintRequest(id="CRREQ-1", description="speed", revision=1, state_hash=manager._read_current("PRJ")["state_hash"]), project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1.0", source_invocation_id="INV", source_agent_result_id="RES", engineering_scope_id="transmission", key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, rationale="needed", lifecycle=ConstraintRequestLifecycle.DISCOVERED)
    requests.write(request)
    command = ConstraintResolutionBatchCommand(command_id="CMD-1", project_id="PRJ", engineering_scope_id="transmission", source_revision=1, source_state_hash=request.request.state_hash, answers=(ConstraintResolutionAnswer(request_id=request.request.id, answer=OutputAngularSpeedAnswer(value=6, unit="deg/s")),), resolver_type="user", resolver_id="u", received_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    materializer = ConstraintResolutionMaterializer(requests, ConstraintResolutionStore(tmp_path))
    application = ConstraintResolutionApplicationService(manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])), requests)
    return manager, requests, command, materializer, application


def test_workflow_runs_materialization_application_invalidation_satisfaction_and_completion(tmp_path):
    from mechcad_harness.agents.constraint_resolution_workflow import ConstraintResolutionWorkflow
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore

    manager, requests, command, materializer, application = _setup(tmp_path)
    evidence = EvidenceStore(tmp_path, manager, DependencyGraph([], []))
    workflow = ConstraintResolutionWorkflow(manager, materializer, application, evidence)
    result = workflow.run(command, run_id="RUN")
    assert result.outcome == "complete"
    assert result.new_revision == 2
    assert result.invalidated_node_ids == ()
    assert result.parameter_ids
    transitions = sorted(path.stem for path in (tmp_path / "projects" / "PRJ" / "runs" / "RUN" / "resolution_workflow").glob("*.json"))
    assert transitions == ["00_started", "10_command_materialized", "20_resolutions_materialized", "30_state_application", "40_state_revision", "50_invalidation", "60_satisfaction", "70_complete"]


def test_workflow_replay_is_no_change_and_does_not_write_second_invalidation(tmp_path):
    from mechcad_harness.agents.constraint_resolution_workflow import ConstraintResolutionWorkflow
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore

    manager, requests, command, materializer, application = _setup(tmp_path)
    evidence = EvidenceStore(tmp_path, manager, DependencyGraph([], []))
    workflow = ConstraintResolutionWorkflow(manager, materializer, application, evidence)
    first = workflow.run(command, run_id="RUN")
    second = workflow.run(command, run_id="RUN")
    assert first.workflow_id == second.workflow_id
    assert second.outcome == "complete"
    assert second.application_outcome == "no_change"
    assert manager._read_current("PRJ")["revision"] == 2
    assert len(list((tmp_path / "projects" / "PRJ" / "invalidations").glob("*.json"))) == 1


def test_workflow_requires_strict_satisfaction_after_application(tmp_path):
    from mechcad_harness.agents.constraint_resolution_workflow import ConstraintResolutionWorkflow
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore

    manager, requests, command, materializer, application = _setup(tmp_path)
    workflow = ConstraintResolutionWorkflow(manager, materializer, application, EvidenceStore(tmp_path, manager, DependencyGraph([], [])))
    result = workflow.run(command, run_id="RUN")
    assert result.satisfaction_proof_ids == result.resolution_ids
    parameter = manager.load_current_state("PRJ").authoritative_parameters[0]
    assert parameter.value.value_rad_s == pytest.approx(0.10471975511965977)


def test_workflow_identity_is_deterministic(tmp_path):
    from mechcad_harness.agents.constraint_resolution_workflow import workflow_id

    assert workflow_id("PRJ", "CMD-1") == workflow_id("PRJ", "CMD-1")
    assert workflow_id("PRJ", "CMD-1") != workflow_id("PRJ", "CMD-2")


def test_configured_dependency_graph_keeps_torque_evidence_current_for_resolution_path(tmp_path):
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore
    from mechcad_harness.models import DesignState
    from mechcad_harness.state import StateManager

    manager = StateManager(tmp_path)
    manager.create_project("PRJ", DesignState(id="DES-1", revision=1))
    config = tmp_path / "dependencies.yaml"
    config.write_text('{"rules": [{"when": ["/requirements/REQ-TORQUE-FORCE/description"], "invalidates": ["analysis.transmission.torque"]}, {"when": ["/requirements/REQ-TORQUE-ARM/description"], "invalidates": ["analysis.transmission.torque"]}, {"when": ["/requirements/REQ-TORQUE-SAFETY/description"], "invalidates": ["analysis.transmission.torque"]}], "edges": []}', encoding="utf-8")
    store = EvidenceStore(tmp_path, manager, DependencyGraph.from_yaml(config))
    assert store.get_change_impact(("/authoritative_parameters/PARAM-1",)).all_nodes == ()


@pytest.mark.parametrize("missing_transition", ["20_resolutions_materialized", "50_invalidation", "60_satisfaction"])
def test_workflow_recovery_reuses_durable_state_and_does_not_create_second_revision(tmp_path, missing_transition):
    from mechcad_harness.agents.constraint_resolution_workflow import ConstraintResolutionWorkflow
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore

    manager, requests, command, materializer, application = _setup(tmp_path)
    workflow = ConstraintResolutionWorkflow(manager, materializer, application, EvidenceStore(tmp_path, manager, DependencyGraph([], [])))
    first = workflow.run(command, run_id="RUN")
    transition = tmp_path / "projects" / "PRJ" / "runs" / "RUN" / "resolution_workflow" / f"{missing_transition}.json"
    transition.unlink()
    with pytest.raises(ValueError, match="WORKFLOW_INTEGRITY_FAILURE"):
        workflow.run(command, run_id="RUN")
    assert manager._read_current("PRJ")["revision"] == 2
    assert len(list((tmp_path / "projects" / "PRJ" / "invalidations").glob("*.json"))) == 1


@pytest.mark.parametrize("missing_transition", ["10_command_materialized", "20_resolutions_materialized", "50_invalidation", "60_satisfaction"])
def test_workflow_recovery_reconstructs_missing_transition_from_validated_artifacts(tmp_path, missing_transition):
    from mechcad_harness.agents.constraint_resolution_workflow import ConstraintResolutionWorkflow
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore

    manager, requests, command, materializer, application = _setup(tmp_path)
    workflow = ConstraintResolutionWorkflow(manager, materializer, application, EvidenceStore(tmp_path, manager, DependencyGraph([], [])))
    workflow.run(command, run_id="RUN")
    directory = tmp_path / "projects" / "PRJ" / "runs" / "RUN" / "resolution_workflow"
    (directory / f"{missing_transition}.json").unlink()
    with pytest.raises(ValueError, match="WORKFLOW_INTEGRITY_FAILURE"):
        workflow.run(command, run_id="RUN")
    assert manager._read_current("PRJ")["revision"] == 2
    assert len(list((tmp_path / "projects" / "PRJ" / "invalidations").glob("*.json"))) == 1


@pytest.mark.parametrize("missing_transition", ["30_state_application", "40_state_revision"])
def test_workflow_terminal_history_hole_fails_closed(tmp_path, missing_transition):
    from mechcad_harness.agents.constraint_resolution_workflow import ConstraintResolutionWorkflow
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore

    manager, requests, command, materializer, application = _setup(tmp_path)
    workflow = ConstraintResolutionWorkflow(manager, materializer, application, EvidenceStore(tmp_path, manager, DependencyGraph([], [])))
    workflow.run(command, run_id="RUN")
    directory = tmp_path / "projects" / "PRJ" / "runs" / "RUN" / "resolution_workflow"
    (directory / f"{missing_transition}.json").unlink()
    with pytest.raises(ValueError, match="WORKFLOW_INTEGRITY_FAILURE"):
        workflow.run(command, run_id="RUN")
    assert not (directory / f"{missing_transition}.json").exists()
    assert manager._read_current("PRJ")["revision"] == 2


def test_unanswered_revision_sibling_is_stale_without_carry_forward(tmp_path):
    from mechcad_harness.agents.constraint_requests import ConstraintRequestLifecycle, ConstraintRequestRecord, ConstraintRequestStore
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionAnswer, ConstraintResolutionBatchCommand, ConstraintResolutionMaterializer, ConstraintResolutionStore, OutputAngularSpeedAnswer, OutputInterfaceAnswer
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.agents.constraint_resolution_workflow import ConstraintResolutionWorkflow
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.models import ConstraintRequest

    manager, requests, command, materializer, application = _setup(tmp_path)
    requests.write(ConstraintRequestRecord(request=ConstraintRequest(id="CRREQ-2", description="interface", revision=1, state_hash=command.source_state_hash), project_id="PRJ", run_id="RUN", task_id="TASK", agent_name="agent", agent_version="1.0", source_invocation_id="INV", source_agent_result_id="RES", engineering_scope_id="transmission", key=SupportedConstraintKey.OUTPUT_INTERFACE, rationale="needed", lifecycle=ConstraintRequestLifecycle.DISCOVERED))
    evidence = EvidenceStore(tmp_path, manager, DependencyGraph([], []))
    workflow = ConstraintResolutionWorkflow(manager, materializer, application, evidence)
    workflow.run(command, run_id="RUN")
    sibling_command = command.model_copy(update={"command_id": "CMD-SIBLING", "answers": (ConstraintResolutionAnswer(request_id="CRREQ-2", answer=OutputInterfaceAnswer(interface_type="keyed", torque_transfer_description="shaft")),)})
    sibling_materialized = ConstraintResolutionMaterializer(requests, ConstraintResolutionStore(tmp_path)).materialize_batch(sibling_command, run_id="RUN")
    sibling_application = ConstraintResolutionApplicationService(manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])), requests)
    with pytest.raises(ValueError, match="stale"):
        sibling_application.apply_batch(sibling_materialized, run_id="RUN")
    assert manager._read_current("PRJ")["revision"] == 2
    assert all(record.source_resolution_id != sibling_materialized.resolution_ids[0] for record in manager.load_current_state("PRJ").authoritative_parameters)


def test_workflow_recovers_receipt_present_before_application_transition_without_reapplying(tmp_path):
    from mechcad_harness.agents.constraint_resolution_workflow import ConstraintResolutionWorkflow
    from mechcad_harness.changes.provenance import StateApplicationStore
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore

    manager, requests, command, materializer, application = _setup(tmp_path)
    workflow = ConstraintResolutionWorkflow(manager, materializer, application, EvidenceStore(tmp_path, manager, DependencyGraph([], [])))
    materialized = materializer.materialize_batch(command, run_id="RUN")
    applied = application.apply_batch(materialized, run_id="RUN")
    directory = tmp_path / "projects" / "PRJ" / "runs" / "RUN" / "resolution_workflow"
    from mechcad_harness.agents.constraint_resolution_workflow import WorkflowTransition, workflow_id

    base = dict(workflow_id=workflow_id("PRJ", command.command_id), project_id="PRJ", source_command_id=command.command_id, source_revision=command.source_revision, source_state_hash=command.source_state_hash)
    workflow._write_transition(directory, WorkflowTransition(transition="00_started", payload={}, **base))
    workflow._write_transition(directory, WorkflowTransition(transition="10_command_materialized", payload={"command_id": command.command_id}, **base))
    workflow._write_transition(directory, WorkflowTransition(transition="20_resolutions_materialized", payload={"resolution_ids": list(materialized.resolution_ids)}, **base))
    before = manager._read_current("PRJ").copy()
    recovered = workflow.run(command, run_id="RUN")
    assert recovered.new_revision == applied.new_revision
    assert manager._read_current("PRJ") == before
    assert StateApplicationStore(tmp_path).load_receipt("PRJ", "RUN", applied.application_id)


def test_workflow_rejects_mismatched_application_linkage(tmp_path):
    from mechcad_harness.agents.constraint_resolution_workflow import ConstraintResolutionWorkflow
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore

    manager, requests, command, materializer, application = _setup(tmp_path)
    workflow = ConstraintResolutionWorkflow(manager, materializer, application, EvidenceStore(tmp_path, manager, DependencyGraph([], [])))
    workflow.run(command, run_id="RUN")
    directory = tmp_path / "projects" / "PRJ" / "runs" / "RUN" / "resolution_workflow"
    path = directory / "30_state_application.json"
    transition = __import__("mechcad_harness.agents.constraint_resolution_workflow", fromlist=["WorkflowTransition"]).WorkflowTransition.model_validate_json(path.read_text(encoding="utf-8"))
    path.write_text(transition.model_copy(update={"payload": {**transition.payload, "proposal_id": "CP-CONFLICT"}}).model_dump_json(), encoding="utf-8")
    with pytest.raises(ValueError, match="WORKFLOW_INTEGRITY_FAILURE"):
        workflow.run(command, run_id="RUN")
