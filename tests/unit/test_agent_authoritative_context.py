import json

import pytest


def _setup(tmp_path):
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore
    from mechcad_harness.models import Component, Constraint, DesignState, Evidence, Requirement
    from mechcad_harness.runs import RunController, TaskDefinition
    from mechcad_harness.state import StateManager

    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-1", DesignState(id="DES-1", revision=1, requirements=[Requirement(id="REQ-1", name="Requirement", description="Canonical requirement")], constraints=[Constraint(id="CON-1", name="Constraint", expression="x > 0")], components=[Component(id="P-1", name="Part")]))
    graph = tmp_path / "dependencies.json"
    graph.write_text(json.dumps({"rules": [{"when": ["/components/*/name"], "invalidates": ["analysis.structural"]}], "edges": []}), encoding="utf-8")
    evidence_store = EvidenceStore(tmp_path, manager, DependencyGraph.from_yaml(graph))
    controller = RunController(tmp_path, manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/components/*", "owner": "actor"}])), evidence_store)
    run = controller.create_run("PRJ-1")
    task = TaskDefinition(task_id="TASK-1", run_id=run.run_id, task_type="agent", objective="inspect", bound_revision=1, bound_state_hash=snapshot.state_hash)
    controller.add_task(run.run_id, task)
    evidence = Evidence(id="EVD-1", kind="analysis.structural", summary="Persisted authoritative summary", revision=1, state_hash=snapshot.state_hash, producer_type="tool", producer_name="tool", producer_version="1.0")
    evidence_store.write_evidence("PRJ-1", evidence)
    return controller, run, task, snapshot, evidence


def test_arbitrary_summary_text_is_not_accepted(tmp_path):
    from mechcad_harness.agents.context import ContextBuilder

    controller, run, task, snapshot, evidence = _setup(tmp_path)
    with pytest.raises(TypeError):
        ContextBuilder(controller).build(run.run_id, task.task_id, evidence_summaries=("fabricated",))


def test_persisted_evidence_id_is_resolved_into_summary(tmp_path):
    from mechcad_harness.agents.context import ContextBuilder

    controller, run, task, snapshot, evidence = _setup(tmp_path)
    context = ContextBuilder(controller).build(run.run_id, task.task_id, selected_evidence_ids=(evidence.id,))
    assert context.evidence_summaries[0].evidence_id == evidence.id
    assert context.evidence_summaries[0].summary == "Persisted authoritative summary"


def test_unknown_or_wrong_binding_evidence_is_rejected(tmp_path):
    from mechcad_harness.agents.context import ContextBuilder
    from mechcad_harness.models import Evidence

    controller, run, task, snapshot, evidence = _setup(tmp_path)
    with pytest.raises(Exception, match="not found"):
        ContextBuilder(controller).build(run.run_id, task.task_id, selected_evidence_ids=("EVD-UNKNOWN",))
    wrong = evidence.model_copy(update={"id": "EVD-WRONG", "state_hash": "sha256:wrong"})
    controller.evidence.write_evidence("PRJ-1", wrong)
    with pytest.raises(Exception, match="binding"):
        ContextBuilder(controller).build(run.run_id, task.task_id, selected_evidence_ids=(wrong.id,))


def test_requirement_and_constraint_ids_resolve_from_bound_state(tmp_path):
    from mechcad_harness.agents.context import ContextBuilder

    controller, run, task, snapshot, evidence = _setup(tmp_path)
    context = ContextBuilder(controller).build(run.run_id, task.task_id, selected_requirement_ids=("REQ-1",), selected_constraint_ids=("CON-1",))
    assert context.requirements == ("Canonical requirement",)
    assert context.constraints == ("x > 0",)
    with pytest.raises(Exception, match="requirement"):
        ContextBuilder(controller).build(run.run_id, task.task_id, selected_requirement_ids=("REQ-UNKNOWN",))
    with pytest.raises(Exception, match="constraint"):
        ContextBuilder(controller).build(run.run_id, task.task_id, selected_constraint_ids=("CON-UNKNOWN",))
