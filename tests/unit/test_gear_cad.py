import hashlib
import importlib.util
import json

import pytest

from mechcad_harness.artifacts import ArtifactType
from mechcad_harness.backends.gearworks_cad import build_spur_gear_cad
from mechcad_harness.cad import SpurGearCadInput, SpurGearPairCadInput
from mechcad_harness.backends.gearworks_cad import build_spur_gear_pair_cad
from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
from mechcad_harness.dependency import DependencyGraph, EvidenceStore
from mechcad_harness.models import Component, DesignState
from mechcad_harness.runs import RunController, TaskDefinition
from mechcad_harness.state import StateManager
from mechcad_harness.tools import GearworksTools, ToolBroker, ToolRegistry, ToolResultStatus


GEAR_AVAILABLE = importlib.util.find_spec("py_gearworks") is not None
BUILD123D_AVAILABLE = importlib.util.find_spec("build123d") is not None


def test_cad_input_validation():
    with pytest.raises(Exception):
        SpurGearCadInput(module_mm=1, teeth=20, face_width_mm=5, pressure_angle_deg=20, requested_formats=("obj",))
    with pytest.raises(Exception):
        SpurGearCadInput(module_mm=1, teeth=20, face_width_mm=5, pressure_angle_deg=20, bore_diameter_mm=0)


@pytest.mark.skipif(not GEAR_AVAILABLE, reason="gear extra is not installed")
def test_golden_spur_cad_exports_step_stl_and_validates_geometry(tmp_path):
    result = build_spur_gear_cad(SpurGearCadInput(module_mm=1, teeth=20, face_width_mm=5, pressure_angle_deg=20, bore_diameter_mm=5), tmp_path, project_id="PRJ-1", run_id="RUN-1", task_id="TASK-1")
    assert result.geometry_summary["pitch_diameter_mm"] == pytest.approx(20)
    assert result.geometry_summary["outside_diameter_mm"] == pytest.approx(22)
    assert result.volume_mm3 > 0
    assert result.bounding_box_mm[2] == pytest.approx(5, abs=0.1)
    assert len(result.artifact_references) == 2
    for reference in result.artifact_references:
        path = tmp_path / reference.relative_path
        content = path.read_bytes()
        assert content
        assert reference.size_bytes == len(content)
        assert reference.sha256 == f"sha256:{hashlib.sha256(content).hexdigest()}"
        metadata = json.loads(path.parent.joinpath("metadata.json").read_text())
        assert metadata["backend_provenance"]["library_revision"] == "2fc2a13d82a9997a65f30c870498f0bb3be62318"


@pytest.mark.skipif(not (GEAR_AVAILABLE and BUILD123D_AVAILABLE), reason="gear and build123d extras are not installed")
def test_specialized_gear_records_actual_build123d_provenance(tmp_path):
    import importlib.metadata

    result = build_spur_gear_cad(SpurGearCadInput(module_mm=1, teeth=20, face_width_mm=5, pressure_angle_deg=20, requested_formats=("step",)), tmp_path, project_id="PRJ-1", run_id="RUN-1", task_id="TASK-1")
    expected_version = importlib.metadata.version("build123d")
    assert result.build123d_provenance.library_name == "build123d"
    assert result.build123d_provenance.library_version == expected_version
    assert result.backend_provenance.library_name == "py_gearworks"
    metadata = json.loads((tmp_path / result.artifact_references[0].relative_path).parent.joinpath("metadata.json").read_text())
    assert metadata["backend_provenance"]["library_name"] == "py_gearworks"
    assert metadata["backend_provenance"]["library_revision"] == "2fc2a13d82a9997a65f30c870498f0bb3be62318"
    assert metadata["build123d_provenance"]["library_name"] == "build123d"
    assert metadata["build123d_provenance"]["library_version"] == expected_version
    assert metadata["build123d_provenance"]["library_version"] == expected_version


@pytest.mark.skipif(not GEAR_AVAILABLE, reason="gear extra is not installed")
def test_step_reimport_has_expected_volume(tmp_path):
    result = build_spur_gear_cad(SpurGearCadInput(module_mm=1, teeth=20, face_width_mm=5, pressure_angle_deg=20, bore_diameter_mm=5, requested_formats=("step",)), tmp_path, project_id="PRJ-1", run_id="RUN-1", task_id="TASK-1")
    step = tmp_path / result.artifact_references[0].relative_path
    from build123d import import_step

    imported = import_step(step)
    assert imported.volume == pytest.approx(result.volume_mm3, rel=0.02)


@pytest.mark.skipif(not GEAR_AVAILABLE, reason="gear extra is not installed")
def test_cad_toolbroker_persists_call_and_provenance(tmp_path):
    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-1", DesignState(id="DES-1", revision=1, components=[Component(id="PRT-1", name="Gear")]))
    graph_path = tmp_path / "dependencies.json"
    graph_path.write_text(json.dumps({"rules": [{"when": ["/components/*/name"], "invalidates": ["artifact.gear"]}], "edges": []}), encoding="utf-8")
    evidence = EvidenceStore(tmp_path, manager, DependencyGraph.from_yaml(graph_path))
    controller = RunController(tmp_path, manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/components/*", "owner": "actor"}])), evidence)
    run = controller.create_run("PRJ-1")
    task = TaskDefinition(task_id="TASK-1", run_id=run.run_id, task_type="tool", objective="cad", bound_revision=1, bound_state_hash=snapshot.state_hash, allowed_tools=("mechcad-build-spur-gear-cad@1.0",))
    controller.add_task(run.run_id, task)
    broker = ToolBroker(controller, ToolRegistry(GearworksTools.registrations()))
    result = broker.execute(run.run_id, task.task_id, "mechcad-build-spur-gear-cad", "1.0", {"module_mm": 1, "teeth": 20, "face_width_mm": 5, "pressure_angle_deg": 20, "bore_diameter_mm": 5, "requested_formats": ["step"]}, evidence_node="artifact.gear")
    assert result.status is ToolResultStatus.SUCCEEDED
    assert result.backend_provenance.library_revision == "2fc2a13d82a9997a65f30c870498f0bb3be62318"
    assert result.output["artifact_references"][0]["relative_path"].startswith(f"projects/PRJ-1/runs/{run.run_id}/artifacts/")
    assert (controller.store.run_dir("PRJ-1", run.run_id) / "tool_calls" / f"{result.call_id}.json").exists()
    artifact_path = tmp_path / result.output["artifact_references"][0]["relative_path"]
    metadata = json.loads(artifact_path.parent.joinpath("metadata.json").read_text())
    assert metadata["project_id"] == "PRJ-1"
    assert metadata["run_id"] == run.run_id
    assert metadata["task_id"] == "TASK-1"
    assert metadata["bound_revision"] == 1
    assert metadata["bound_state_hash"] == snapshot.state_hash
    assert metadata["input_hash"] == json.loads((controller.store.run_dir("PRJ-1", run.run_id) / "tool_calls" / f"{result.call_id}.json").read_text())["input_hash"]


@pytest.mark.skipif(not GEAR_AVAILABLE, reason="gear extra is not installed")
def test_pair_cad_returns_two_artifacts_and_nominal_transform(tmp_path):
    input_value = SpurGearPairCadInput(
        pinion=SpurGearCadInput(module_mm=1, teeth=20, face_width_mm=5, pressure_angle_deg=20, bore_diameter_mm=5, requested_formats=("step",)),
        gear=SpurGearCadInput(module_mm=1, teeth=60, face_width_mm=5, pressure_angle_deg=20, bore_diameter_mm=5, requested_formats=("step",)),
    )
    result = build_spur_gear_pair_cad(input_value, tmp_path, project_id="PRJ-1", run_id="RUN-1", task_id="TASK-1")
    assert result.nominal_center_distance_mm == pytest.approx(40)
    assert result.relative_transform == pytest.approx((40, 0, 0))
    assert result.pinion.artifact_references[0].artifact_type == "step"
    assert result.gear.artifact_references[0].artifact_type == "step"
