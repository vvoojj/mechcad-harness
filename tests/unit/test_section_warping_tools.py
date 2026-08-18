import importlib.util
import json

import pytest

SECTION_PROPERTIES_AVAILABLE = importlib.util.find_spec("sectionproperties") is not None


def _controller(tmp_path):
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore
    from mechcad_harness.models import Component, DesignState
    from mechcad_harness.runs import RunController
    from mechcad_harness.state import StateManager

    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-1", DesignState(id="DES-1", revision=1, components=[Component(id="PRT-1", name="Part")]))
    graph_path = tmp_path / "dependencies.json"
    graph_path.write_text(json.dumps({"rules": [{"when": ["/components/*/name"], "invalidates": ["analysis.structural"]}], "edges": []}), encoding="utf-8")
    evidence = EvidenceStore(tmp_path, manager, DependencyGraph.from_yaml(graph_path))
    return RunController(tmp_path, manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/components/*", "owner": "actor"}])), evidence), snapshot


@pytest.mark.skipif(not SECTION_PROPERTIES_AVAILABLE, reason="structural profile is not installed")
def test_warping_tool_success_persists_evidence_provenance_and_leaves_design_state_unchanged(tmp_path):
    from mechcad_harness.runs import TaskDefinition
    from mechcad_harness.tools import SectionTools, ToolBroker, ToolRegistry, ToolResultStatus

    controller, snapshot = _controller(tmp_path)
    run = controller.create_run("PRJ-1")
    task = TaskDefinition(task_id="TASK-1", run_id=run.run_id, task_type="tool", objective="warping", bound_revision=1, bound_state_hash=snapshot.state_hash, allowed_tools=("mechcad-calc-circle-section-warping@1.0",))
    controller.add_task(run.run_id, task)
    result = ToolBroker(controller, ToolRegistry(SectionTools.registrations())).execute(
        run.run_id,
        task.task_id,
        "mechcad-calc-circle-section-warping",
        "1.0",
        {"diameter_mm": 50, "discretization_points": 128, "mesh_size_mm2": 20},
        evidence_node="analysis.structural",
    )
    assert result.status is ToolResultStatus.SUCCEEDED
    assert result.backend_provenance.backend_adapter_version == "0.2.0"
    assert result.output["convergence_metadata"]["converged"] is True
    assert controller.evidence.load_evidence("PRJ-1", result.evidence_id).backend_provenance == result.backend_provenance
    assert controller.state_manager._read_snapshot("PRJ-1", 1).state_hash == snapshot.state_hash


def test_warping_tool_permission_is_enforced(tmp_path):
    from mechcad_harness.runs import TaskDefinition
    from mechcad_harness.tools import SectionTools, ToolBroker, ToolRegistry
    from mechcad_harness.tools.errors import ToolPermissionError

    controller, snapshot = _controller(tmp_path)
    run = controller.create_run("PRJ-1")
    task = TaskDefinition(task_id="TASK-1", run_id=run.run_id, task_type="tool", objective="warping", bound_revision=1, bound_state_hash=snapshot.state_hash, allowed_tools=())
    controller.add_task(run.run_id, task)
    with pytest.raises(ToolPermissionError):
        ToolBroker(controller, ToolRegistry(SectionTools.registrations())).execute(run.run_id, task.task_id, "mechcad-calc-circle-section-warping", "1.0", {"diameter_mm": 50, "discretization_points": 128, "mesh_size_mm2": 20})
