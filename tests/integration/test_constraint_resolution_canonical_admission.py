def test_production_application_exposes_only_batch_constraint_resolution_admission_api():
    from mechcad_harness.application import ProductionApplication

    assert hasattr(ProductionApplication, "admit_constraint_resolution_batch")
    assert not hasattr(ProductionApplication, "admit_constraint_resolution")


def test_production_application_admits_bound_batch_reload_and_exact_replay(tmp_path):
    import json
    from datetime import datetime, timezone

    from mechcad_harness.agents.constraint_requests import (
        ConstraintRequestLifecycle,
        ConstraintRequestRecord,
        ConstraintRequestStore,
    )
    from mechcad_harness.agents.constraint_resolution import (
        ConstraintResolutionAnswer,
        ConstraintResolutionBatchCommand,
        ConstraintResolutionMaterializer,
        ConstraintResolutionStore,
        MotorCharacteristicsAnswer,
        OutputAngularSpeedAnswer,
    )
    from mechcad_harness.application import ProductionApplication
    from mechcad_harness.changes.constraint_resolution_admission import (
        ConstraintResolutionAdmissionPolicy,
        ConstraintResolutionAdmissionRule,
    )
    from mechcad_harness.engineering.keys import SupportedConstraintKey
    from mechcad_harness.models import Constraint, ConstraintRequest, DesignState, Evidence, Requirement
    from mechcad_harness.runs import TaskDefinition
    from mechcad_harness.state import StateManager

    class Adapter:
        identity = object()

        def invoke(self, request):
            raise AssertionError("not called")

    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    ownership.write_text(
        "ownership:\n  - path: /authoritative_parameters/*\n    owner: mechcad-authority-admission\n",
        encoding="utf-8",
    )
    dependencies = tmp_path / "dependencies.yaml"
    dependencies.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "when": ["/requirements/REQ-TORQUE-FORCE/description"],
                        "invalidates": ["analysis.transmission.torque"],
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    project_id = "PRJ-canonical"
    manager = StateManager(workspace)
    manager.create_project(
        project_id,
        DesignState(
            id="DES-canonical",
            revision=1,
            requirements=[
                Requirement(id="REQ-TRANSMISSION-OUTPUT-SPEED", name="speed", description="speed"),
                Requirement(id="REQ-TRANSMISSION-MOTOR-CHARACTERISTICS", name="motor", description="motor"),
            ],
            constraints=[Constraint(id="CON-TRANSMISSION-OUTPUT-INTERFACE", name="interface", expression="interface")],
        ),
    )
    source = manager._read_current(project_id)
    policy = ConstraintResolutionAdmissionPolicy(
        project_id=project_id,
        rules=(
            ConstraintResolutionAdmissionRule(
                resolver_type="synthetic",
                resolver_id="resolver-1",
                engineering_scope_id="transmission",
                allowed_keys=tuple(SupportedConstraintKey),
            ),
        ),
    )
    app = ProductionApplication.create(
        workspace,
        project_id,
        Adapter(),
        ownership_path=ownership,
        dependency_path=dependencies,
        constraint_resolution_policy=policy,
    )
    torque_evidence = Evidence(
        id="EVD-TORQUE",
        kind="analysis.transmission.torque",
        summary="current torque evidence",
        revision=1,
        state_hash=source["state_hash"],
    )
    app.evidence_store.write_evidence(project_id, torque_evidence)
    run = app.create_run().run
    request_store = ConstraintRequestStore(workspace)
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    request_store.write(
        ConstraintRequestRecord(
            request=ConstraintRequest(id="CRREQ-S", description="speed", revision=1, state_hash=source["state_hash"]),
            project_id=project_id,
            run_id=run.run_id,
            task_id="TASK-S",
            agent_name="agent",
            agent_version="1.0",
            source_invocation_id="INV-S",
            source_agent_result_id="RES-S",
            engineering_scope_id="transmission",
            key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED,
            rationale="needed",
            lifecycle=ConstraintRequestLifecycle.DISCOVERED,
            created_at=timestamp,
        )
    )
    request_store.write(
        ConstraintRequestRecord(
            request=ConstraintRequest(id="CRREQ-M", description="motor", revision=1, state_hash=source["state_hash"]),
            project_id=project_id,
            run_id=run.run_id,
            task_id="TASK-M",
            agent_name="agent",
            agent_version="1.0",
            source_invocation_id="INV-M",
            source_agent_result_id="RES-M",
            engineering_scope_id="transmission",
            key=SupportedConstraintKey.MOTOR_CHARACTERISTICS,
            rationale="needed",
            lifecycle=ConstraintRequestLifecycle.DISCOVERED,
            created_at=timestamp,
        )
    )
    for task_id in ("TASK-S", "TASK-M"):
        app.run_controller.add_task(
            run.run_id,
            TaskDefinition(
                task_id=task_id,
                run_id=run.run_id,
                task_type="agent",
                objective="resolve",
                bound_revision=1,
                bound_state_hash=source["state_hash"],
            ),
        )
    command = ConstraintResolutionBatchCommand(
        command_id="CMD-canonical",
        project_id=project_id,
        engineering_scope_id="transmission",
        source_revision=1,
        source_state_hash=source["state_hash"],
        answers=(
            ConstraintResolutionAnswer(request_id="CRREQ-S", answer=OutputAngularSpeedAnswer(value=6, unit="deg/s")),
            ConstraintResolutionAnswer(request_id="CRREQ-M", answer=MotorCharacteristicsAnswer(motor_id="M-1", speed_min_rpm=0, speed_max_rpm=100, continuous_torque_nm=2, peak_torque_nm=3)),
        ),
        resolver_type="synthetic",
        resolver_id="resolver-1",
        received_at=timestamp,
    )
    ConstraintResolutionMaterializer(request_store, ConstraintResolutionStore(workspace)).materialize_batch(command, run_id=run.run_id)

    first = app.admit_constraint_resolution_batch(run.run_id, command.command_id)
    assert first.replayed is False
    assert first.revision == 2
    state = app.state_manager.load_current_state(project_id)
    assert state.revision == 2
    assert {parameter.key for parameter in state.authoritative_parameters} == {
        SupportedConstraintKey.OUTPUT_ANGULAR_SPEED,
        SupportedConstraintKey.MOTOR_CHARACTERISTICS,
    }
    assert {parameter.source_resolution_id for parameter in state.authoritative_parameters} == set(first.resolution_ids)
    invalidation = app.evidence_store.load_invalidation(project_id, 2)
    assert invalidation.directly_invalidated_nodes == ()
    assert invalidation.transitively_invalidated_nodes == ()
    assert app.evidence_store.get_evidence_freshness(project_id, torque_evidence.id).value == "current"

    fresh = ProductionApplication.create(
        workspace,
        project_id,
        Adapter(),
        ownership_path=ownership,
        dependency_path=dependencies,
        constraint_resolution_policy=policy,
    )
    replay = fresh.admit_constraint_resolution_batch(run.run_id, command.command_id)
    assert replay.replayed is True
    assert fresh.state_manager._read_current(project_id)["revision"] == 2


def test_production_batch_api_fails_closed_for_missing_source_run_without_mutation(tmp_path):
    import pytest

    from mechcad_harness.application import ProductionApplication
    from mechcad_harness.models import DesignState
    from mechcad_harness.state import StateManager

    class Adapter:
        identity = object()

        def invoke(self, request):
            raise AssertionError("not called")

    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    ownership.write_text(
        "ownership:\n  - path: /authoritative_parameters/*\n    owner: mechcad-authority-admission\n",
        encoding="utf-8",
    )
    dependencies = tmp_path / "dependencies.yaml"
    dependencies.write_text("rules: []\nedges: []\n", encoding="utf-8")
    project_id = "PRJ-missing-run"
    manager = StateManager(workspace)
    manager.create_project(project_id, DesignState(id="DES-missing-run", revision=1))
    app = ProductionApplication.create(
        workspace,
        project_id,
        Adapter(),
        ownership_path=ownership,
        dependency_path=dependencies,
    )

    with pytest.raises(Exception, match="missing run record"):
        app.admit_constraint_resolution_batch("RUN-missing", "CMD-missing")
    assert app.state_manager._read_current(project_id)["revision"] == 1
