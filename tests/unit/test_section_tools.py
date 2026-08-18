import importlib.util
import json

import pytest

SECTION_PROPERTIES_AVAILABLE = importlib.util.find_spec("sectionproperties") is not None


def _controller(tmp_path):
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore
    from mechcad_harness.models import Component, DesignState
    from mechcad_harness.runs import RunController, TaskDefinition
    from mechcad_harness.state import StateManager

    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-1", DesignState(id="DES-1", revision=1, components=[Component(id="PRT-1", name="Part")]))
    graph_path = tmp_path / "dependencies.json"
    graph_path.write_text(json.dumps({"rules": [{"when": ["/components/*/name"], "invalidates": ["analysis.structural"]}], "edges": []}), encoding="utf-8")
    evidence = EvidenceStore(tmp_path, manager, DependencyGraph.from_yaml(graph_path))
    controller = RunController(tmp_path, manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/components/*", "owner": "actor"}])), evidence)
    return controller, snapshot


@pytest.mark.skipif(not SECTION_PROPERTIES_AVAILABLE, reason="structural profile is not installed")
def test_section_toolbroker_success_persists_call_result_evidence_and_provenance(tmp_path):
    from mechcad_harness.runs import TaskDefinition
    from mechcad_harness.tools import SectionTools, ToolBroker, ToolRegistry, ToolResultStatus

    controller, snapshot = _controller(tmp_path)
    run = controller.create_run("PRJ-1")
    task = TaskDefinition(task_id="TASK-1", run_id=run.run_id, task_type="tool", objective="section", bound_revision=1, bound_state_hash=snapshot.state_hash, allowed_tools=("mechcad-calc-rectangle-section-properties@1.0",))
    controller.add_task(run.run_id, task)
    before = snapshot.state_hash
    result = ToolBroker(controller, ToolRegistry(SectionTools.registrations())).execute(
        run.run_id,
        task.task_id,
        "mechcad-calc-rectangle-section-properties",
        "1.0",
        {"width_mm": 50, "height_mm": 100, "mesh_size_mm2": 5},
        evidence_node="analysis.structural",
    )
    assert result.status is ToolResultStatus.SUCCEEDED
    assert result.backend_provenance.backend_name == "section-properties"
    assert result.output["centroid_x_mm"] == pytest.approx(25)
    assert controller.state_manager._read_snapshot("PRJ-1", 1).state_hash == before
    assert controller.evidence.load_evidence("PRJ-1", result.evidence_id).backend_provenance == result.backend_provenance
    assert list((tmp_path / "projects" / "PRJ-1" / "runs" / run.run_id / "tool_calls").glob("*.json"))


def test_section_toolbroker_rejects_missing_permission(tmp_path):
    from mechcad_harness.runs import TaskDefinition
    from mechcad_harness.tools import SectionTools, ToolBroker, ToolRegistry
    from mechcad_harness.tools.errors import ToolPermissionError

    controller, snapshot = _controller(tmp_path)
    run = controller.create_run("PRJ-1")
    task = TaskDefinition(task_id="TASK-1", run_id=run.run_id, task_type="tool", objective="section", bound_revision=1, bound_state_hash=snapshot.state_hash, allowed_tools=())
    controller.add_task(run.run_id, task)
    with pytest.raises(ToolPermissionError):
        ToolBroker(controller, ToolRegistry(SectionTools.registrations())).execute(run.run_id, task.task_id, "mechcad-calc-rectangle-section-properties", "1.0", {"width_mm": 50, "height_mm": 100, "mesh_size_mm2": 5})


def test_section_toolbroker_rejects_stale_task(tmp_path):
    from mechcad_harness.runs import TaskDefinition
    from mechcad_harness.tools import SectionTools, ToolBroker, ToolRegistry
    from mechcad_harness.tools.errors import ToolExecutionError

    controller, snapshot = _controller(tmp_path)
    run = controller.create_run("PRJ-1")
    task = TaskDefinition(task_id="TASK-1", run_id=run.run_id, task_type="tool", objective="section", bound_revision=1, bound_state_hash=snapshot.state_hash, allowed_tools=("mechcad-calc-rectangle-section-properties@1.0",))
    controller.add_task(run.run_id, task)
    task_path = tmp_path / "projects" / "PRJ-1" / "runs" / run.run_id / "tasks" / task.task_id / "definition.json"
    task_path.write_text(task.model_copy(update={"bound_revision": 2}).model_dump_json(), encoding="utf-8")
    with pytest.raises(ToolExecutionError, match="stale"):
        ToolBroker(controller, ToolRegistry(SectionTools.registrations())).execute(run.run_id, task.task_id, "mechcad-calc-rectangle-section-properties", "1.0", {"width_mm": 50, "height_mm": 100, "mesh_size_mm2": 5})
