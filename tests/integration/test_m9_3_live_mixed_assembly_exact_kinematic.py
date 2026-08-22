from __future__ import annotations

import hashlib
import importlib.util
import json
import math

import pytest

from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
from mechcad_harness.application import ProductionApplication
from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.backends.freecad import FreeCADBackend, discover_freecad
from mechcad_harness.cad_assembly import instance_object_name
from mechcad_harness.cad_compilation import MountingPlateDesignSpec
from mechcad_harness.imported_component import ImportedCadComponent, resolve_imported_component
from mechcad_harness.kinematic_sweep import CollisionClassification, RevoluteAxis
from mechcad_harness.models import Component, DesignState
from mechcad_harness.state import StateManager
from mechcad_harness.tools import GearworksTools
from mechcad_harness.transient_freecad_measurement import FreeCADTransientAssemblyMeasurementProvider


GEAR_AVAILABLE = importlib.util.find_spec("py_gearworks") is not None and importlib.util.find_spec("build123d") is not None
FREECAD_CANDIDATE = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"


def _freecad_available() -> bool:
    try:
        return discover_freecad().available
    except Exception:
        return False


def _make_application(workspace, project_id):
    workspace.mkdir(parents=True, exist_ok=True)
    ownership = workspace / "ownership.yaml"
    dependencies = workspace / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /components/*\n    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    dependencies.write_text(
        json.dumps({"rules": [{"when": ["/components/*/name"], "invalidates": ["artifact.gear", "analysis.kinematic_sweep"]}], "edges": []}),
        encoding="utf-8",
    )
    state = DesignState(
        id="DES-m9-3",
        revision=1,
        components=[Component(id="PRT-fixture", name="Fixture")],
    )
    StateManager(workspace).create_project(project_id, state)
    identity = AgentIdentity(
        agent_name="mechcad-transmission",
        agent_version="1.0",
        role="transmission_engineer",
        protocol_version="1.0",
    )
    adapter = FakeAgentAdapter(identity, scripted_responses=())
    return ProductionApplication.create(
        workspace,
        project_id,
        adapter,
        ownership_path=ownership,
        dependency_path=dependencies,
        additional_tool_registrations=GearworksTools.registrations(),
    )


def _gear_input():
    return {
        "module_mm": 2.0,
        "teeth": 12,
        "face_width_mm": 5.0,
        "pressure_angle_deg": 20.0,
        "requested_formats": ["step"],
    }


def _read_assembly_placements(fcstd_path):
    discovery = discover_freecad().require_available()
    script = (
        "import FreeCAD, json\n"
        f"doc = FreeCAD.openDocument({str(fcstd_path.resolve())!r})\n"
        "items = []\n"
        "for obj in doc.Objects:\n"
        "    if hasattr(obj, 'Shape') and not obj.Shape.isNull():\n"
        "        items.append({'name': obj.Name, 'base': [obj.Placement.Base.x, obj.Placement.Base.y, obj.Placement.Base.z], 'quat': list(obj.Placement.Rotation.Q)})\n"
        "print('M9_3_PLACEMENT=' + json.dumps(items, sort_keys=True))\n"
        "FreeCAD.closeDocument(doc.Name)\n"
    )
    completed = FreeCADBackend._run(discovery.executable, script, cwd=fcstd_path.parent)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout or "freecad placement read failed")
    line = next((ln for ln in completed.stdout.splitlines() if ln.startswith("M9_3_PLACEMENT=")), None)
    if line is None:
        raise RuntimeError("freecad placement output missing")
    return json.loads(line.removeprefix("M9_3_PLACEMENT="))


@pytest.mark.skipif(not GEAR_AVAILABLE, reason="gear + build123d extras are not installed")
@pytest.mark.skipif(not _freecad_available(), reason="FreeCAD not available")
class TestM9_3LiveMixedAssemblyExactKinematic:
    def test_full_live_vertical_slice(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MECHCAD_FREECADCMD", FREECAD_CANDIDATE)
        project_id = "PRJ-M9-3"
        workspace = tmp_path / "workspace"
        app = _make_application(workspace, project_id)

        source = app.load_state()
        source_revision = source.revision
        source_state_hash = source.state_hash

        # --- Production run + tool binding for the real producer -----------------
        run_binding = app.create_run()
        run = run_binding.run
        from mechcad_harness.runs import TaskDefinition

        task = TaskDefinition(
            task_id="TASK-gear",
            run_id=run.run_id,
            task_type="tool",
            objective="cad",
            bound_revision=source_revision,
            bound_state_hash=source_state_hash,
            allowed_tools=("mechcad-build-spur-gear-cad@1.0",),
        )
        app.run_controller.add_task(run.run_id, task)

        result = app.tool_broker.execute(
            run.run_id,
            task.task_id,
            "mechcad-build-spur-gear-cad",
            "1.0",
            _gear_input(),
            evidence_node="artifact.gear",
        )
        assert result.status.value == "succeeded"
        assert result.backend_provenance is not None
        assert result.backend_provenance.library_name == "py_gearworks"

        refs = result.output["artifact_references"]
        assert len(refs) == 1
        artifact_id = refs[0]["artifact_id"]
        artifact_hash = refs[0]["sha256"]
        artifact_path = workspace / refs[0]["relative_path"]
        content = artifact_path.read_bytes()
        assert len(content) > 0
        assert f"sha256:{hashlib.sha256(content).hexdigest()}" == artifact_hash

        store = ArtifactStore(workspace, project_id=project_id, run_id=run.run_id, task_id=task.task_id)
        existing = store.existing(artifact_id)
        assert existing is not None
        assert existing.artifact_type is ArtifactType.STEP
        assert existing.sha256 == artifact_hash
        assert f"sha256:{hashlib.sha256((workspace / existing.relative_path).read_bytes()).hexdigest()}" == existing.sha256

        # C. real trusted resolution through production resolver
        imported = resolve_imported_component(
            artifact_id=artifact_id,
            artifact_hash=artifact_hash,
            store=store,
            component_id="gear-1",
        )
        assert isinstance(imported, ImportedCadComponent)
        assert imported.artifact_id == artifact_id
        assert imported.artifact_hash == artifact_hash
        assert imported.source_revision == source_revision
        assert imported.source_state_hash == source_state_hash

        # A. M8C-1 generated part from source-bound design spec
        plate_spec = MountingPlateDesignSpec(
            part_id="plate",
            plate_length_mm=40.0,
            plate_width_mm=40.0,
            plate_thickness_mm=10.0,
            mounting_holes=(MountingPlateDesignSpec.HoleSpec(hole_id="h1", x_mm=10.0, y_mm=10.0, diameter_mm=6.0),),
        )
        compiled = app.compile_design_spec(
            source_revision=source_revision,
            source_state_hash=source_state_hash,
            spec=plate_spec,
        )
        plate_program = compiled.program
        assert compiled.source_revision == source_revision
        assert compiled.source_state_hash == source_state_hash
        plate_program_hash = compiled.program_hash

        # D. mixed CadAssemblyProgram
        from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, CadRigidTransform

        assembly = CadAssemblyProgram(
            assembly_id="m9-3-mixed-fixture",
            parts=(plate_program,),
            imported_components=(imported,),
            instances=(
                CadComponentInstance(
                    instance_id="plate-inst",
                    part_id="plate",
                    placement=CadRigidTransform(x_mm=0.0, y_mm=-60.0, z_mm=0.0),
                ),
                CadComponentInstance(
                    instance_id="gear-inst",
                    part_id="gear-1",
                    placement=CadRigidTransform(x_mm=20.0, y_mm=0.0, z_mm=5.0),
                ),
            ),
        )

        # E/F. real FreeCAD mixed assembly generation + persistence
        generation = app.build_assembly_with_imported_components(
            source_revision=source_revision,
            source_state_hash=source_state_hash,
            assembly_id="m9-3-mixed-fixture",
            generated_parts=(plate_program,),
            imported_components=(imported,),
            instances=assembly.instances,
            run_id=run.run_id,
        )
        assert generation.fcstd_verification.shape_valid
        assert generation.step_verification.shape_valid
        assert generation.fcstd_verification.solid_count == len(assembly.instances)
        assert generation.step_verification.solid_count == len(assembly.instances)

        # G. both generated + imported canonical objects exist (FCStd is authoritative;
        # STEP re-import is verified by solid count per the assembly backend contract)
        imported_name = instance_object_name("gear-inst")
        plate_name = instance_object_name("plate-inst")
        fcstd_objects = {item.object_name for item in generation.fcstd_verification.instances}
        assert plate_name in fcstd_objects and imported_name in fcstd_objects
        assert generation.step_verification.solid_count == len(assembly.instances)

        # H. imported placement survives fresh reload (explicit reopen)
        fcstd_path = workspace / generation.fcstd.relative_path
        placements = _read_assembly_placements(fcstd_path)
        by_name = {item["name"]: item for item in placements}
        assert imported_name in by_name
        assert plate_name in by_name
        imp = by_name[imported_name]
        assert imp["base"] == pytest.approx([20.0, 0.0, 5.0], abs=1e-6)
        assert len(placements) == len(assembly.instances)  # I. no duplicate temporary objects

        # --- K. real production kinematic entry; provider is real --------------
        assert isinstance(app._kinematic_measurement_provider, FreeCADTransientAssemblyMeasurementProvider)
        assert app.kinematic_measure.__func__ is FreeCADTransientAssemblyMeasurementProvider.exact_measure

        axis = RevoluteAxis(origin_x_mm=0, origin_y_mm=0, origin_z_mm=0, direction_x=0, direction_y=0, direction_z=1, frame_id="fixture_frame")

        # O/P. no per-angle public artifacts created during the sweep
        artifacts_before = sorted(workspace.glob("projects/*/runs/*/artifacts/*/metadata.json"))

        sweep = app.analyze_assembly_kinematics(
            source_revision=source_revision,
            source_state_hash=source_state_hash,
            assembly=assembly,
            axis=axis,
            moving_instance_ids=("gear-inst",),
            stationary_instance_ids=("plate-inst",),
            sample_angles_deg=(0.0, 90.0, 180.0, 270.0),
        )

        artifacts_after = sorted(workspace.glob("projects/*/runs/*/artifacts/*/metadata.json"))
        assert artifacts_before == artifacts_after

        # M. ordered angle samples returned; L. exact measurement executed
        assert [sample.angle_deg for sample in sweep.samples] == [0.0, 90.0, 180.0, 270.0]
        assert sweep.request_hash.startswith("sha256:")
        assert sweep.source_assembly_hash.startswith("sha256:")
        assert sweep.sweep_version.startswith("rigid-body-collision-sweep@")

        transformed_hashes = [sample.transformed_assembly_hash for sample in sweep.samples]
        assert all(h.startswith("sha256:") for h in transformed_hashes)
        assert transformed_hashes[0] != transformed_hashes[1]  # motion really changed transforms

        # N. result identity
        assert sweep.result_hash.startswith("sha256:")

        # Exact measurement evidence per sample
        for sample in sweep.samples:
            assert len(sample.pair_results) == 1
            pair = sample.pair_results[0]
            assert pair.moving_instance_id == "gear-inst"
            assert pair.stationary_instance_id == "plate-inst"
            assert pair.interference_volume_mm3 >= 0.0
            assert pair.exact_distance_mm >= 0.0
            assert math.isfinite(pair.interference_volume_mm3)
            assert math.isfinite(pair.exact_distance_mm)
            assert isinstance(pair.classification, CollisionClassification)

        # The moving gear orbits; world position changes -> distances differ
        distances = [sample.pair_results[0].exact_distance_mm for sample in sweep.samples]
        assert len(set(round(d, 6) for d in distances)) > 1

        # Q. continuous sweep never claimed
        assert sweep.continuous_sweep_verified is False

        # O. no DesignState mutation
        after = app.load_state()
        assert after.revision == source_revision
        assert after.state_hash == source_state_hash

        # Determinism: re-run the live sweep and compare measurements
        sweep2 = app.analyze_assembly_kinematics(
            source_revision=source_revision,
            source_state_hash=source_state_hash,
            assembly=assembly,
            axis=axis,
            moving_instance_ids=("gear-inst",),
            stationary_instance_ids=("plate-inst",),
            sample_angles_deg=(0.0, 90.0, 180.0, 270.0),
        )
        for a, b in zip(sweep.samples, sweep2.samples):
            pa, pb = a.pair_results[0], b.pair_results[0]
            assert pa.interference_volume_mm3 == pytest.approx(pb.interference_volume_mm3, abs=1e-6)
            assert pa.exact_distance_mm == pytest.approx(pb.exact_distance_mm, abs=1e-6)

        # --- M9-4: trusted execution provenance is durable and FreeCAD-bound ---
        evidence = app.get_kinematic_sweep_evidence(sweep.result_hash)
        assert evidence is not None
        assert evidence.kind == "analysis.kinematic_sweep"
        assert evidence.producer_result_id == sweep.result_hash
        assert evidence.input_hash == sweep.request_hash
        prov = evidence.analysis_execution_provenance
        assert prov is not None
        # Bindings to the exact analysis identity.
        assert prov.request_hash == sweep.request_hash
        assert prov.result_hash == sweep.result_hash
        assert prov.source_assembly_hash == sweep.source_assembly_hash
        assert prov.sweep_version == sweep.sweep_version
        # Live FreeCAD provider / backend identity.
        assert prov.provider_name == "freecad-transient-exact"
        assert prov.provider_version == "mechcad-freecad-transient@1.0"
        assert prov.backend_provenance is not None
        assert prov.backend_provenance.backend_name == "freecad"
        assert prov.backend_provenance.backend_adapter_version == "mechcad-freecad@2.1"
        assert prov.backend_provenance.library_name == "FreeCAD"
        assert prov.backend_provenance.library_version and prov.backend_provenance.library_version != "unknown"
        assert prov.execution_mode == "freecadcmd-subprocess"
