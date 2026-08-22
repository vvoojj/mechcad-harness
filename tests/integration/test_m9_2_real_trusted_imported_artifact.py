from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import tempfile
from pathlib import Path

import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.backends.freecad import FreeCADBackend, discover_freecad
from mechcad_harness.backends.gearworks_cad import build_spur_gear_cad
from mechcad_harness.cad import SpurGearCadInput
from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
from mechcad_harness.dependency import DependencyGraph, EvidenceStore
from mechcad_harness.imported_component import (
    ImportedArtifactIntegrityError,
    ImportedCadComponent,
    resolve_imported_component,
)
from mechcad_harness.models import Component, DesignState
from mechcad_harness.runs import RunController, TaskDefinition
from mechcad_harness.state import StateManager
from mechcad_harness.tools import GearworksTools, ToolBroker, ToolRegistry, ToolResultStatus

GEAR_AVAILABLE = importlib.util.find_spec("py_gearworks") is not None
BUILD123D_AVAILABLE = importlib.util.find_spec("build123d") is not None
PRODUCER_AVAILABLE = GEAR_AVAILABLE and BUILD123D_AVAILABLE

FREECAD_CANDIDATE = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"


def _freecad_available() -> bool:
    try:
        return discover_freecad().available
    except Exception:
        return False


def _make_run_binding(tmp_path: Path):
    manager = StateManager(tmp_path)
    snapshot = manager.create_project(
        "PRJ-M9-2",
        DesignState(id="DES-1", revision=1, components=[Component(id="PRT-1", name="Gear")]),
    )
    graph_path = tmp_path / "dependencies.json"
    graph_path.write_text(
        json.dumps({"rules": [{"when": ["/components/*/name"], "invalidates": ["artifact.gear"]}], "edges": []}),
        encoding="utf-8",
    )
    evidence = EvidenceStore(tmp_path, manager, DependencyGraph.from_yaml(graph_path))
    controller = RunController(
        tmp_path,
        manager,
        ChangeEngine(manager, OwnershipPolicy([{"path": "/components/*", "owner": "actor"}])),
        evidence,
    )
    return manager, snapshot, controller


def _gear_input() -> SpurGearCadInput:
    # Fixed acceptance fixture: a single spur gear. No engineering selection.
    return SpurGearCadInput(
        module_mm=2.0,
        teeth=12,
        face_width_mm=5.0,
        pressure_angle_deg=20.0,
        requested_formats=("step",),
    )


@pytest.mark.skipif(not PRODUCER_AVAILABLE, reason="gear + build123d extras are not installed")
class TestM9_2RealTrustedImportedArtifact:
    def test_real_producer_publishes_step_through_artifact_store(self, tmp_path):
        manager, snapshot, controller = _make_run_binding(tmp_path)
        run = controller.create_run("PRJ-M9-2")
        task = TaskDefinition(
            task_id="TASK-gear",
            run_id=run.run_id,
            task_type="tool",
            objective="cad",
            bound_revision=1,
            bound_state_hash=snapshot.state_hash,
            allowed_tools=("mechcad-build-spur-gear-cad@1.0",),
        )
        controller.add_task(run.run_id, task)
        broker = ToolBroker(controller, ToolRegistry(GearworksTools.registrations()))
        result = broker.execute(
            run.run_id,
            task.task_id,
            "mechcad-build-spur-gear-cad",
            "1.0",
            {
                "module_mm": 1,
                "teeth": 20,
                "face_width_mm": 5,
                "pressure_angle_deg": 20,
                "requested_formats": ["step"],
            },
            evidence_node="artifact.gear",
        )

        # A. real specialized production producer executes
        assert result.status is ToolResultStatus.SUCCEEDED
        assert result.backend_provenance.library_name == "py_gearworks"

        # B. real STEP bytes are generated; C. artifact published via ArtifactStore
        refs = result.output["artifact_references"]
        assert len(refs) == 1
        assert refs[0]["artifact_type"] == "step"
        artifact_path = tmp_path / refs[0]["relative_path"]
        content = artifact_path.read_bytes()
        assert len(content) > 0

        # D. actual bytes hash matches EngineeringArtifact.sha256
        recomputed = f"sha256:{hashlib.sha256(content).hexdigest()}"
        assert refs[0]["sha256"] == recomputed

        # E. ArtifactStore.existing succeeds
        store = ArtifactStore(tmp_path, project_id="PRJ-M9-2", run_id=run.run_id, task_id=task.task_id)
        existing = store.existing(refs[0]["artifact_id"])
        assert existing is not None
        assert existing.artifact_type is ArtifactType.STEP
        assert existing.sha256 == recomputed
        assert existing.size_bytes == len(content)
        assert f"sha256:{hashlib.sha256((tmp_path / existing.relative_path).read_bytes()).hexdigest()}" == existing.sha256

    def test_real_artifact_resolves_to_imported_component_with_trusted_provenance(self, tmp_path):
        manager, snapshot, controller = _make_run_binding(tmp_path)
        run = controller.create_run("PRJ-M9-2")
        task = TaskDefinition(
            task_id="TASK-gear",
            run_id=run.run_id,
            task_type="tool",
            objective="cad",
            bound_revision=1,
            bound_state_hash=snapshot.state_hash,
            allowed_tools=("mechcad-build-spur-gear-cad@1.0",),
        )
        controller.add_task(run.run_id, task)
        broker = ToolBroker(controller, ToolRegistry(GearworksTools.registrations()))
        result = broker.execute(
            run.run_id,
            task.task_id,
            "mechcad-build-spur-gear-cad",
            "1.0",
            {
                "module_mm": 2.0,
                "teeth": 12,
                "face_width_mm": 5,
                "pressure_angle_deg": 20,
                "requested_formats": ["step"],
            },
            evidence_node="artifact.gear",
        )
        artifact_id = result.output["artifact_references"][0]["artifact_id"]
        artifact_hash = result.output["artifact_references"][0]["sha256"]
        store = ArtifactStore(tmp_path, project_id="PRJ-M9-2", run_id=run.run_id, task_id=task.task_id)

        # F. real artifact resolves through resolve_imported_component
        component = resolve_imported_component(
            artifact_id=artifact_id,
            artifact_hash=artifact_hash,
            store=store,
            component_id="gear-1",
        )

        # G. source_revision / source_state_hash are derived from trusted artifact metadata
        assert isinstance(component, ImportedCadComponent)
        assert component.component_id == "gear-1"
        assert component.artifact_id == artifact_id
        assert component.artifact_hash == artifact_hash
        assert component.format == "step"
        # trusted source binding from the artifact record, not caller-authored
        assert component.source_revision == 1
        assert component.source_state_hash == snapshot.state_hash

        # H. caller cannot override provenance. resolve_imported_component exposes no
        # caller-controlled source fields; the artifact record is authoritative.
        artifact = store.existing(artifact_id)
        assert artifact.bound_revision == component.source_revision
        assert artifact.bound_state_hash == component.source_state_hash

    def test_resolver_rejects_forged_hash(self, tmp_path):
        manager, snapshot, controller = _make_run_binding(tmp_path)
        run = controller.create_run("PRJ-M9-2")
        task = TaskDefinition(
            task_id="TASK-gear",
            run_id=run.run_id,
            task_type="tool",
            objective="cad",
            bound_revision=1,
            bound_state_hash=snapshot.state_hash,
            allowed_tools=("mechcad-build-spur-gear-cad@1.0",),
        )
        controller.add_task(run.run_id, task)
        broker = ToolBroker(controller, ToolRegistry(GearworksTools.registrations()))
        result = broker.execute(
            run.run_id,
            task.task_id,
            "mechcad-build-spur-gear-cad",
            "1.0",
            {
                "module_mm": 2.0,
                "teeth": 12,
                "face_width_mm": 5,
                "pressure_angle_deg": 20,
                "requested_formats": ["step"],
            },
            evidence_node="artifact.gear",
        )
        artifact_id = result.output["artifact_references"][0]["artifact_id"]
        store = ArtifactStore(tmp_path, project_id="PRJ-M9-2", run_id=run.run_id, task_id=task.task_id)
        forged = "sha256:" + "0" * 64
        with pytest.raises(ImportedArtifactIntegrityError):
            resolve_imported_component(
                artifact_id=artifact_id,
                artifact_hash=forged,
                store=store,
                component_id="gear-1",
            )

    def test_no_designstate_mutation_or_change_artifacts(self, tmp_path):
        manager, snapshot, controller = _make_run_binding(tmp_path)
        before_revision = snapshot.revision
        before_hash = snapshot.state_hash
        run = controller.create_run("PRJ-M9-2")
        task = TaskDefinition(
            task_id="TASK-gear",
            run_id=run.run_id,
            task_type="tool",
            objective="cad",
            bound_revision=1,
            bound_state_hash=snapshot.state_hash,
            allowed_tools=("mechcad-build-spur-gear-cad@1.0",),
        )
        controller.add_task(run.run_id, task)
        broker = ToolBroker(controller, ToolRegistry(GearworksTools.registrations()))
        broker.execute(
            run.run_id,
            task.task_id,
            "mechcad-build-spur-gear-cad",
            "1.0",
            {
                "module_mm": 2.0,
                "teeth": 12,
                "face_width_mm": 5,
                "pressure_angle_deg": 20,
                "requested_formats": ["step"],
            },
            evidence_node="artifact.gear",
        )

        # J. no DesignState mutation
        after = manager.load_current_state("PRJ-M9-2")
        assert after.revision == before_revision
        assert manager._read_current("PRJ-M9-2")["state_hash"] == before_hash

        # K. no ChangeProposal / ChangeSet created anywhere in the workspace
        violations = list(tmp_path.rglob("*proposal*")) + list(tmp_path.rglob("*changeset*"))
        assert not violations

    def test_producer_is_byte_deterministic(self, tmp_path):
        inp = _gear_input()
        ws_a = tempfile.mkdtemp()
        ws_b = tempfile.mkdtemp()
        ra = build_spur_gear_cad(inp, ws_a, project_id="PRJ-M9-2", run_id="run-a", bound_revision=1, bound_state_hash="sha256:" + "a" * 64)
        rb = build_spur_gear_cad(inp, ws_b, project_id="PRJ-M9-2", run_id="run-b", bound_revision=1, bound_state_hash="sha256:" + "a" * 64)
        path_a = Path(ws_a) / ra.artifact_references[0].relative_path
        path_b = Path(ws_b) / rb.artifact_references[0].relative_path
        bytes_a = path_a.read_bytes()
        bytes_b = path_b.read_bytes()
        # same semantic input -> identical STEP bytes (fixed export timestamp)
        assert ra.artifact_references[0].sha256 == rb.artifact_references[0].sha256
        assert bytes_a == bytes_b


def _verify_step_with_freecad(step_path: Path) -> dict:
    discovery = discover_freecad().require_available()
    script = (
        "import FreeCAD, Part, json\n"
        "doc = FreeCAD.newDocument('M9_2Verify')\n"
        f"Part.insert({str(step_path.resolve())!r}, doc.Name)\n"
        "doc.recompute()\n"
        "objects = [obj for obj in doc.Objects if hasattr(obj, 'Shape') and not obj.Shape.isNull()]\n"
        "items = []\n"
        "for obj in objects:\n"
        "    shape = obj.Shape\n"
        "    items.append({'object_name': obj.Name, 'shape_valid': shape.isValid(), 'solid_count': len(shape.Solids)})\n"
        "print('M9_2_JSON=' + json.dumps({'objects': items, 'shape_valid': all(i['shape_valid'] for i in items), 'solid_count': sum(i['solid_count'] for i in items)}, sort_keys=True))\n"
        "FreeCAD.closeDocument(doc.Name)\n"
    )
    completed = FreeCADBackend._run(discovery.executable, script, cwd=step_path.parent)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout or "freecad step verification failed")
    line = next((ln for ln in completed.stdout.splitlines() if ln.startswith("M9_2_JSON=")), None)
    if line is None:
        raise RuntimeError("freecad structured verification missing")
    return json.loads(line.removeprefix("M9_2_JSON="))


@pytest.mark.skipif(not PRODUCER_AVAILABLE, reason="gear + build123d extras are not installed")
@pytest.mark.skipif(not _freecad_available(), reason="FreeCAD not available")
def test_live_freecad_imported_step_is_valid_solid(tmp_path, monkeypatch):
    monkeypatch.setenv("MECHCAD_FREECADCMD", FREECAD_CANDIDATE)
    manager, snapshot, controller = _make_run_binding(tmp_path)
    run = controller.create_run("PRJ-M9-2")
    task = TaskDefinition(
        task_id="TASK-gear",
        run_id=run.run_id,
        task_type="tool",
        objective="cad",
        bound_revision=1,
        bound_state_hash=snapshot.state_hash,
        allowed_tools=("mechcad-build-spur-gear-cad@1.0",),
    )
    controller.add_task(run.run_id, task)
    broker = ToolBroker(controller, ToolRegistry(GearworksTools.registrations()))
    result = broker.execute(
        run.run_id,
        task.task_id,
        "mechcad-build-spur-gear-cad",
        "1.0",
        {
            "module_mm": 2.0,
            "teeth": 12,
            "face_width_mm": 5,
            "pressure_angle_deg": 20,
            "requested_formats": ["step"],
        },
        evidence_node="artifact.gear",
    )
    step_path = tmp_path / result.output["artifact_references"][0]["relative_path"]
    verification = _verify_step_with_freecad(step_path)
    assert verification["shape_valid"] is True
    assert verification["solid_count"] >= 1


def test_generic_bridge_has_no_gear_semantics():
    # I. generic bridge must not contain specialized gear semantics.
    generic_modules = [
        Path(__file__).resolve().parents[2] / "src" / "mechcad_harness" / "imported_component.py",
        Path(__file__).resolve().parents[2] / "src" / "mechcad_harness" / "cad_assembly.py",
        Path(__file__).resolve().parents[2] / "src" / "mechcad_harness" / "assembly_service.py",
    ]
    forbidden = (
        "py_gearworks",
        "build123d",
        "SpurGear",
        "pressure_angle",
        "gear_ratio",
        "tooth",
        "module_mm",
    )
    for module_path in generic_modules:
        text = module_path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{module_path.name} references gear token: {token}"
