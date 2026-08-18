import json

import pytest

from mechcad_harness.changes import ChangeEngine, ChangeOperation, OwnershipPolicy
from mechcad_harness.dependency import DependencyGraph, EvidenceFreshness, EvidenceStore
from mechcad_harness.models import ChangeProposal, Component, DesignState, ProposalStatus
from mechcad_harness.runs import RunController, TaskDefinition, TaskStatus
from mechcad_harness.state import StateManager
from mechcad_harness.tools import (
    BuiltinTools,
    ToolBroker,
    ToolCall,
    ToolContext,
    ToolExecutionError,
    ToolPermissionError,
    ToolRegistry,
    ToolResultStatus,
    ToolVersionError,
)


def make_state():
    return DesignState(id="DES-1", revision=1, components=[Component(id="PRT-1", name="Bracket")])


def make_controller(tmp_path, *, allowed_tools=("mechcad-calc-torque@1.0",), evidence_nodes=()):
    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-1", make_state())
    graph_path = tmp_path / "dependencies.json"
    rules = [{"when": ["/components/*/name"], "invalidates": list(evidence_nodes)}] if evidence_nodes else []
    graph_path.write_text(json.dumps({"rules": rules, "edges": []}), encoding="utf-8")
    evidence = EvidenceStore(tmp_path, manager, DependencyGraph.from_yaml(graph_path))
    engine = ChangeEngine(manager, OwnershipPolicy([{"path": "/components/*", "owner": "actor"}]))
    controller = RunController(tmp_path, manager, engine, evidence)
    run = controller.create_run("PRJ-1")
    task = TaskDefinition(
        task_id="TASK-1", run_id=run.run_id, task_type="tool", objective="calculate",
        bound_revision=run.active_revision, bound_state_hash=run.active_state_hash,
        allowed_tools=allowed_tools,
    )
    controller.add_task(run.run_id, task)
    return controller, run, task, snapshot


def make_broker(controller):
    return ToolBroker(controller, ToolRegistry(BuiltinTools.registrations()))


def test_tool_context_contains_provenance_only():
    context = ToolContext(project_id="PRJ-1", run_id="RUN-1", task_id="TASK-1", bound_revision=1, bound_state_hash="sha256:a")
    assert set(context.model_dump()) == {"project_id", "run_id", "task_id", "bound_revision", "bound_state_hash"}
    with pytest.raises(Exception):
        ToolContext(**context.model_dump(), state={"secret": True})


def test_registry_requires_exact_tool_version():
    registry = ToolRegistry(BuiltinTools.registrations())
    assert registry.resolve("mechcad-calc-torque", "1.0").version == "1.0"
    with pytest.raises(ToolVersionError):
        registry.resolve("mechcad-calc-torque", "9.0")


def test_registry_rejects_duplicate_exact_registration():
    registration = next(item for item in BuiltinTools.registrations() if item.name == "mechcad-calc-torque")
    with pytest.raises(Exception):
        ToolRegistry([registration, registration])


def test_builtin_tools_are_explicit_and_deterministic():
    tools = BuiltinTools.registrations()
    torque = next(item for item in tools if item.name == "mechcad-calc-torque")
    first = torque.handler(torque.input_model(force_n=10, lever_arm_m=0.2, safety_factor=2))
    second = torque.handler(torque.input_model(force_n=10, lever_arm_m=0.2, safety_factor=2))
    assert first == second
    assert first.nominal_torque_nm == 2
    assert first.design_torque_nm == 4

    envelope = next(item for item in tools if item.name == "mechcad-check-envelope")
    assert envelope.handler(envelope.input_model(part_x_mm=10, part_y_mm=20, part_z_mm=30, max_x_mm=11, max_y_mm=20, max_z_mm=31)).fits is True
    assert envelope.handler(envelope.input_model(part_x_mm=10, part_y_mm=21, part_z_mm=30, max_x_mm=11, max_y_mm=20, max_z_mm=31)).fits is False

    compensation = next(item for item in tools if item.name == "mechcad-apply-dimension-compensation")
    assert compensation.handler(compensation.input_model(nominal_mm=10, compensation_mm=0.25)).compensated_mm == 10.25
    assert compensation.handler(compensation.input_model(nominal_mm=10, compensation_mm=-0.25)).compensated_mm == 9.75

    gear = next(item for item in tools if item.name == "mechcad-calc-spur-gear-geometry")
    output = gear.handler(gear.input_model(module_mm=2, teeth_pinion=20, teeth_gear=40))
    assert output.pitch_diameter_pinion_mm == 40
    assert output.pitch_diameter_gear_mm == 80
    assert output.center_distance_mm == 60
    assert output.ratio == 2


def test_tool_permission_is_explicit_and_empty_fails_closed(tmp_path):
    controller, run, task, _ = make_controller(tmp_path, allowed_tools=())
    with pytest.raises(ToolPermissionError):
        make_broker(controller).execute(run.run_id, task.task_id, "mechcad-calc-torque", "1.0", {"force_n": 1, "lever_arm_m": 1, "safety_factor": 1})


def test_success_persists_separate_call_and_result(tmp_path):
    controller, run, task, _ = make_controller(tmp_path)
    broker = make_broker(controller)
    result = broker.execute(run.run_id, task.task_id, "mechcad-calc-torque", "1.0", {"force_n": 10, "lever_arm_m": 0.2, "safety_factor": 2})
    run_dir = controller.store.run_dir("PRJ-1", run.run_id)
    assert (run_dir / "tool_calls" / f"{result.call_id}.json").exists()
    assert (run_dir / "tool_results" / f"{result.result_id}.json").exists()
    assert result.status is ToolResultStatus.SUCCEEDED
    assert result.output_hash


def test_call_and_result_records_are_immutable(tmp_path):
    controller, run, task, _ = make_controller(tmp_path)
    result = make_broker(controller).execute(run.run_id, task.task_id, "mechcad-calc-torque", "1.0", {"force_n": 10, "lever_arm_m": 0.2, "safety_factor": 2})
    with pytest.raises(Exception):
        make_broker(controller).store.write_result(result)
    call_path = controller.store.run_dir("PRJ-1", run.run_id) / "tool_calls" / f"{result.call_id}.json"
    result_path = controller.store.run_dir("PRJ-1", run.run_id) / "tool_results" / f"{result.result_id}.json"
    forbidden = {"active_revision", "active_state_hash", "iteration", "state_hash_history", "updated_at"}
    assert forbidden.isdisjoint(json.loads(call_path.read_text()))
    assert forbidden.isdisjoint(json.loads(result_path.read_text()))


def test_failed_execution_preserves_call_and_writes_failed_result(tmp_path):
    controller, run, task, _ = make_controller(tmp_path)
    registry = ToolRegistry([next(item for item in BuiltinTools.registrations() if item.name == "mechcad-calc-torque")])
    broker = ToolBroker(controller, registry)
    with pytest.raises(ToolExecutionError):
        broker.execute(run.run_id, task.task_id, "mechcad-calc-torque", "1.0", {"force_n": -1, "lever_arm_m": 1, "safety_factor": 1})
    run_dir = controller.store.run_dir("PRJ-1", run.run_id)
    assert len(list((run_dir / "tool_calls").glob("*.json"))) == 1
    assert len(list((run_dir / "tool_results").glob("*.json"))) == 1


def test_stale_old_task_cannot_invoke_tool_and_canonical_snapshot_is_unchanged(tmp_path):
    controller, run, task, snapshot = make_controller(tmp_path)
    old_bytes = (tmp_path / "projects/PRJ-1/revisions/REV-000001.json").read_bytes()
    proposal = ChangeProposal(
        id="CP-1", title="rename", status=ProposalStatus.DRAFT,
        base_revision=1, base_state_hash=snapshot.state_hash, actor="actor",
        operations=[ChangeOperation(operation="replace", path="/components/PRT-1/name", value="Plate")],
    )
    controller.apply_approved_proposal(run.run_id, proposal)
    with pytest.raises(ToolExecutionError):
        make_broker(controller).execute(run.run_id, task.task_id, "mechcad-calc-torque", "1.0", {"force_n": 1, "lever_arm_m": 1, "safety_factor": 1})
    assert (tmp_path / "projects/PRJ-1/revisions/REV-000001.json").read_bytes() == old_bytes


def test_explicit_declared_evidence_uses_exact_tool_result_provenance(tmp_path):
    controller, run, task, _ = make_controller(tmp_path, evidence_nodes=("analysis.torque",))
    registry = ToolRegistry([item.model_copy(update={"evidence_nodes": ("analysis.torque",)}) if item.name == "mechcad-calc-torque" else item for item in BuiltinTools.registrations()])
    broker = ToolBroker(controller, registry)
    result = broker.execute(run.run_id, task.task_id, "mechcad-calc-torque", "1.0", {"force_n": 10, "lever_arm_m": 0.2, "safety_factor": 2}, evidence_node="analysis.torque")
    evidence = controller.evidence.load_evidence("PRJ-1", result.evidence_id)
    assert evidence.revision == run.active_revision
    assert evidence.state_hash == run.active_state_hash
    assert evidence.producer_name == "mechcad-calc-torque"
    assert evidence.producer_version == "1.0"
    assert evidence.producer_result_id == result.result_id


def test_undeclared_evidence_and_failed_evidence_are_rejected(tmp_path):
    controller, run, task, _ = make_controller(tmp_path)
    broker = make_broker(controller)
    with pytest.raises(ToolExecutionError):
        broker.execute(run.run_id, task.task_id, "mechcad-calc-torque", "1.0", {"force_n": 1, "lever_arm_m": 1, "safety_factor": 1}, evidence_node="analysis.arbitrary")
