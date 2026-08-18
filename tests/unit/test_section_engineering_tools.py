import json

import pytest

from mechcad_harness.section_engineering import PreliminarySectionEngineeringToolInput


def test_public_tool_input_accepts_ids_not_inline_results():
    with pytest.raises(Exception):
        PreliminarySectionEngineeringToolInput(material={})


def test_public_tool_input_requires_material_and_geometry_ids():
    with pytest.raises(Exception):
        PreliminarySectionEngineeringToolInput()


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


def test_unknown_source_result_id_is_rejected(tmp_path):
    from mechcad_harness.tools.section_engineering import resolve_source_result

    controller, snapshot = _controller(tmp_path)
    with pytest.raises(Exception, match="not found"):
        resolve_source_result(controller, "PRJ-1", "RUN-unknown", "TOOLRES-unknown", ("tool",), 1, snapshot.state_hash, object)


def _write_result(tmp_path, controller, run, result_id, tool_name, output, *, task_id="SOURCE-TASK", output_hash=None, revision=1, state_hash=None, status="succeeded"):
    from mechcad_harness.tools.models import ToolResult
    from mechcad_harness.tools.broker import payload_hash

    result = ToolResult(result_id=result_id, call_id=f"CALL-{result_id}", tool_name=tool_name, tool_version="1.0", project_id="PRJ-1", run_id=run.run_id, task_id=task_id, bound_revision=revision, bound_state_hash=state_hash or run.active_state_hash, status=status, input_hash="sha256:input", output=output, output_hash=output_hash or payload_hash(output))
    path = tmp_path / "projects" / "PRJ-1" / "runs" / run.run_id / "tool_results" / f"{result_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(), encoding="utf-8")
    return result


def test_source_output_hash_mismatch_is_rejected(tmp_path):
    from mechcad_harness.runs import TaskDefinition
    from mechcad_harness.tools.section_engineering import resolve_source_result
    from mechcad_harness.materials import TypicalMaterialPropertiesResult

    controller, snapshot = _controller(tmp_path)
    run = controller.create_run("PRJ-1")
    output = {"bad": True}
    _write_result(tmp_path, controller, run, "TOOLRES-1", "mechcad-material-typical-properties", output, output_hash="sha256:wrong")
    with pytest.raises(Exception, match="hash"):
        resolve_source_result(controller, "PRJ-1", run.run_id, "TOOLRES-1", (("mechcad-material-typical-properties", "1.0"),), 1, snapshot.state_hash, TypicalMaterialPropertiesResult)


def _source_outputs(*, modulus=True, density=True):
    from mechcad_harness.testsupport import material_output, geometry_output

    return material_output(modulus=modulus, density=density), geometry_output()


def test_persisted_source_task_id_is_preserved(tmp_path):
    from mechcad_harness.materials import TypicalMaterialPropertiesResult
    from mechcad_harness.tools.section_engineering import resolve_source_result

    controller, snapshot = _controller(tmp_path)
    run = controller.create_run("PRJ-1")
    material, _ = _source_outputs()
    result = _write_result(tmp_path, controller, run, "TOOLRES-M", "mechcad-material-typical-properties", material, task_id="ORIGINAL-MATERIAL-TASK")
    _, _, source = resolve_source_result(controller, "PRJ-1", run.run_id, result.result_id, (("mechcad-material-typical-properties", "1.0"),), 1, snapshot.state_hash, TypicalMaterialPropertiesResult)
    assert source.task_id == "ORIGINAL-MATERIAL-TASK"


def test_complete_stiffness_result_creates_evidence_but_partial_result_does_not(tmp_path):
    from mechcad_harness.runs import TaskDefinition
    from mechcad_harness.tools import SectionEngineeringTools, ToolBroker, ToolRegistry, ToolResultStatus
    from mechcad_harness.tools.broker import payload_hash

    controller, snapshot = _controller(tmp_path)
    run = controller.create_run("PRJ-1")
    material, geometry = _source_outputs()
    material_id = "TOOLRES-M"
    geometry_id = "TOOLRES-G"
    _write_result(tmp_path, controller, run, material_id, "mechcad-material-typical-properties", material)
    _write_result(tmp_path, controller, run, geometry_id, "mechcad-calc-rectangle-section-properties", geometry)
    task = TaskDefinition(task_id="TASK-INTEGRATION", run_id=run.run_id, task_type="tool", objective="integration", bound_revision=1, bound_state_hash=snapshot.state_hash, allowed_tools=("mechcad-calc-preliminary-section-engineering-properties@1.0",))
    controller.add_task(run.run_id, task)
    broker = ToolBroker(controller, ToolRegistry(SectionEngineeringTools.registrations()))
    result = broker.execute(run.run_id, task.task_id, "mechcad-calc-preliminary-section-engineering-properties", "1.0", {"material_result_id": material_id, "section_geometry_result_id": geometry_id}, evidence_node="analysis.structural")
    assert result.status is ToolResultStatus.SUCCEEDED
    assert result.evidence_id is not None
    assert result.backend_provenance is None
    assert result.output["source_records"][0]["task_id"] == "SOURCE-TASK"

    partial_material, _ = _source_outputs(modulus=False)
    partial_id = "TOOLRES-M-PARTIAL"
    _write_result(tmp_path, controller, run, partial_id, "mechcad-material-typical-properties", partial_material)
    partial_task = TaskDefinition(task_id="TASK-INTEGRATION-PARTIAL", run_id=run.run_id, task_type="tool", objective="integration", bound_revision=1, bound_state_hash=snapshot.state_hash, allowed_tools=("mechcad-calc-preliminary-section-engineering-properties@1.0",))
    controller.add_task(run.run_id, partial_task)
    partial = broker.execute(run.run_id, partial_task.task_id, "mechcad-calc-preliminary-section-engineering-properties", "1.0", {"material_result_id": partial_id, "section_geometry_result_id": geometry_id}, evidence_node="analysis.structural")
    assert partial.status is ToolResultStatus.SUCCEEDED
    assert partial.output["axial_rigidity_ea"]["status"] == "unavailable"
    assert partial.evidence_id is None
