import importlib.util
import json

import pytest

from mechcad_harness.backends import BackendHealthStatus
from mechcad_harness.backends.adapters import PyGearworksAdapter
from mechcad_harness.gear import SpurGearGeometryInput, SpurGearPairInput
from mechcad_harness.tools import GearworksTools, ToolBroker, ToolRegistry, ToolResultStatus
from mechcad_harness.tools.builtins import calc_spur_gear
from mechcad_harness.tools.models import ToolRegistration
from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
from mechcad_harness.dependency import DependencyGraph, EvidenceStore
from mechcad_harness.models import Component, DesignState
from mechcad_harness.runs import RunController, TaskDefinition
from mechcad_harness.state import StateManager


GEAR_AVAILABLE = importlib.util.find_spec("py_gearworks") is not None


def test_gear_optional_dependency_profile_is_declared():
    pyproject = open("pyproject.toml", encoding="utf-8").read()
    assert "gear = [" in pyproject
    assert "numpy>=2,<2.4" in pyproject
    assert "2fc2a13d82a9997a65f30c870498f0bb3be62318" in pyproject


def test_base_harness_does_not_require_gear_imports():
    assert importlib.util.find_spec("mechcad_harness") is not None


def test_adapter_identity_and_capabilities():
    identity = PyGearworksAdapter.identity
    assert identity.name == "py-gearworks"
    assert identity.adapter_version == "0.1.0"
    assert identity.library_revision == "2fc2a13d82a9997a65f30c870498f0bb3be62318"
    assert identity.capabilities == ("gear.geometry.spur", "gear.geometry.pair")


def test_spur_and_pair_input_validation():
    with pytest.raises(Exception):
        SpurGearGeometryInput(module_mm=0, teeth=20, face_width_mm=5, pressure_angle_deg=20)
    with pytest.raises(Exception):
        SpurGearGeometryInput(module_mm=float("nan"), teeth=20, face_width_mm=5, pressure_angle_deg=20)
    with pytest.raises(Exception):
        SpurGearPairInput(module_mm=1, pinion_teeth=0, gear_teeth=60, face_width_mm=5, pressure_angle_deg=20)


@pytest.mark.skipif(not GEAR_AVAILABLE, reason="gear extra is not installed")
def test_adapter_health_and_normalized_calculations():
    adapter = PyGearworksAdapter()
    assert adapter.healthcheck().status is BackendHealthStatus.AVAILABLE
    result = adapter.spur_geometry(SpurGearGeometryInput(module_mm=1, teeth=20, face_width_mm=5, pressure_angle_deg=20))
    assert 2 * result[0].pitch_radius == pytest.approx(20)
    assert result[1]["base_radius_mm"] > 0


@pytest.mark.skipif(not GEAR_AVAILABLE, reason="gear extra is not installed")
def test_gearworks_tool_registration_and_pair_result():
    registration = next(item for item in GearworksTools.registrations() if item.name.endswith("pair-gearworks"))
    output = registration.handler(SpurGearPairInput(module_mm=1, pinion_teeth=20, gear_teeth=60, face_width_mm=5, pressure_angle_deg=20))
    assert output.gear_ratio == pytest.approx(3)
    assert output.pinion_pitch_diameter_mm == pytest.approx(20)
    assert output.gear_pitch_diameter_mm == pytest.approx(60)
    assert output.nominal_center_distance_mm == pytest.approx(40)
    assert output.actual_center_distance_mm == pytest.approx(40)


@pytest.mark.skipif(not GEAR_AVAILABLE, reason="gear extra is not installed")
def test_native_and_backend_basic_cross_validation():
    native = calc_spur_gear(type("Input", (), {"module_mm": 1, "teeth_pinion": 20, "teeth_gear": 60})())
    backend = next(item for item in GearworksTools.registrations() if item.name.endswith("pair-gearworks")).handler(SpurGearPairInput(module_mm=1, pinion_teeth=20, gear_teeth=60, face_width_mm=5, pressure_angle_deg=20))
    assert backend.pinion_pitch_diameter_mm == pytest.approx(native.pitch_diameter_pinion_mm)
    assert backend.gear_pitch_diameter_mm == pytest.approx(native.pitch_diameter_gear_mm)
    assert backend.nominal_center_distance_mm == pytest.approx(native.center_distance_mm)
    assert backend.gear_ratio == pytest.approx(native.ratio)


def test_unavailable_backend_fails_closed(monkeypatch):
    adapter = PyGearworksAdapter()
    monkeypatch.setattr(adapter, "healthcheck", lambda: type("Health", (), {"status": BackendHealthStatus.UNAVAILABLE, "message": "missing"})())
    with pytest.raises(Exception, match="missing"):
        adapter.provenance()


@pytest.mark.skipif(not GEAR_AVAILABLE, reason="gear extra is not installed")
def test_backend_toolbroker_result_and_evidence_provenance(tmp_path):
    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-1", DesignState(id="DES-1", revision=1, components=[Component(id="PRT-1", name="Gear")]))
    graph_path = tmp_path / "dependencies.json"
    graph_path.write_text(json.dumps({"rules": [{"when": ["/components/*/name"], "invalidates": ["analysis.transmission"]}], "edges": []}), encoding="utf-8")
    evidence = EvidenceStore(tmp_path, manager, DependencyGraph.from_yaml(graph_path))
    controller = RunController(tmp_path, manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/components/*", "owner": "actor"}])), evidence)
    run = controller.create_run("PRJ-1")
    task = TaskDefinition(task_id="TASK-1", run_id=run.run_id, task_type="tool", objective="gear", bound_revision=1, bound_state_hash=snapshot.state_hash, allowed_tools=("mechcad-calc-spur-gear-pair-gearworks@1.0",))
    controller.add_task(run.run_id, task)
    result = ToolBroker(controller, ToolRegistry(GearworksTools.registrations())).execute(run.run_id, task.task_id, "mechcad-calc-spur-gear-pair-gearworks", "1.0", {"module_mm": 1, "pinion_teeth": 20, "gear_teeth": 60, "face_width_mm": 5, "pressure_angle_deg": 20}, evidence_node="analysis.transmission")
    assert result.status is ToolResultStatus.SUCCEEDED
    assert result.backend_provenance.library_revision == "2fc2a13d82a9997a65f30c870498f0bb3be62318"
    saved = controller.evidence.load_evidence("PRJ-1", result.evidence_id)
    assert saved.backend_provenance == result.backend_provenance
    assert (controller.store.run_dir("PRJ-1", run.run_id) / "tool_calls" / f"{result.call_id}.json").exists()


@pytest.mark.skipif(not GEAR_AVAILABLE, reason="gear extra is not installed")
def test_backend_objects_are_not_in_normalized_result():
    registration = next(item for item in GearworksTools.registrations() if item.name.endswith("geometry-gearworks"))
    result = registration.handler(SpurGearGeometryInput(module_mm=1, teeth=20, face_width_mm=5, pressure_angle_deg=20))
    payload = result.model_dump(mode="json")
    assert "SpurGear" not in json.dumps(payload)
