from __future__ import annotations

import hashlib
import importlib.util
import json
import math

import pytest

from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
from mechcad_harness.application import ProductionApplication
from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.backends.freecad import discover_freecad
from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_compilation import MountingPlateDesignSpec
from mechcad_harness.continuous_proof import (
    CONTINUOUS_PROOF_ALGORITHM_VERSION,
    ContinuousSingleAxisProofStatus,
    ContinuousSingleAxisProofResult,
)
from mechcad_harness.imported_component import ImportedCadComponent, resolve_imported_component
from mechcad_harness.kinematic_sweep import CollisionClassification, RevoluteAxis
from mechcad_harness.models import Component, DesignState
from mechcad_harness.state import StateManager
from mechcad_harness.tools import GearworksTools


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
        json.dumps({"rules": [{"when": ["/components/*/name"], "invalidates": ["artifact.gear", "analysis.kinematic_sweep", "analysis.continuous_clearance_proof"]}], "edges": []}),
        encoding="utf-8",
    )
    state = DesignState(
        id="DES-m10-1",
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


@pytest.mark.skipif(not GEAR_AVAILABLE, reason="gear + build123d extras not installed")
@pytest.mark.skipif(not _freecad_available(), reason="FreeCAD not available")
class TestM10_1LiveContinuousProof:
    def test_live_verified_clear_interval(self, tmp_path, monkeypatch):
        """M10-1: a real continuous interval certified VERIFIED_CLEAR."""
        monkeypatch.setenv("MECHCAD_FREECADCMD", FREECAD_CANDIDATE)
        project_id = "PRJ-M10-1"
        workspace = tmp_path / "workspace"
        app = _make_application(workspace, project_id)
        source = app.load_state()

        # Produce real gear STEP via ToolBroker
        run_binding = app.create_run()
        run = run_binding.run
        from mechcad_harness.runs import TaskDefinition
        task = TaskDefinition(
            task_id="TASK-gear",
            run_id=run.run_id,
            task_type="tool",
            objective="cad",
            bound_revision=source.revision,
            bound_state_hash=source.state_hash,
            allowed_tools=("mechcad-build-spur-gear-cad@1.0",),
        )
        app.run_controller.add_task(run.run_id, task)
        result = app.tool_broker.execute(
            run.run_id, task.task_id,
            "mechcad-build-spur-gear-cad", "1.0",
            _gear_input(), evidence_node="artifact.gear",
        )
        assert result.status.value == "succeeded"
        refs = result.output["artifact_references"]
        assert len(refs) == 1
        artifact_id = refs[0]["artifact_id"]
        artifact_hash = refs[0]["sha256"]

        store = ArtifactStore(workspace, project_id=project_id, run_id=run.run_id, task_id=task.task_id)
        imported = resolve_imported_component(
            artifact_id=artifact_id, artifact_hash=artifact_hash,
            store=store, component_id="gear-1",
        )

        # Source-bound plate
        plate_spec = MountingPlateDesignSpec(
            part_id="plate",
            plate_length_mm=40.0,
            plate_width_mm=40.0,
            plate_thickness_mm=10.0,
            mounting_holes=(MountingPlateDesignSpec.HoleSpec(hole_id="h1", x_mm=10.0, y_mm=10.0, diameter_mm=6.0),),
        )
        compiled = app.compile_design_spec(
            source_revision=source.revision,
            source_state_hash=source.state_hash,
            spec=plate_spec,
        )
        plate_program = compiled.program

        assembly = CadAssemblyProgram(
            assembly_id="m10-1-fixture",
            parts=(plate_program,),
            imported_components=(imported,),
            instances=(
                CadComponentInstance(
                    instance_id="plate-inst", part_id="plate",
                    placement=CadRigidTransform(x_mm=0.0, y_mm=-60.0, z_mm=0.0),
                ),
                CadComponentInstance(
                    instance_id="gear-inst", part_id="gear-1",
                    placement=CadRigidTransform(x_mm=20.0, y_mm=0.0, z_mm=5.0),
                ),
            ),
        )

        # Build assembly
        generation = app.build_assembly_with_imported_components(
            source_revision=source.revision,
            source_state_hash=source.state_hash,
            assembly_id="m10-1-fixture",
            generated_parts=(plate_program,),
            imported_components=(imported,),
            instances=assembly.instances,
            run_id=run.run_id,
        )
        assert generation.fcstd_verification.shape_valid

        # Axis: world-Z through origin
        axis = RevoluteAxis(
            origin_x_mm=0, origin_y_mm=0, origin_z_mm=0,
            direction_x=0, direction_y=0, direction_z=1,
            frame_id="fixture_frame",
        )

        # === LIVE POSITIVE PROOF: narrow interval around 90 deg ===
        # At 90 deg the gear is ~26mm from plate; with R~37mm,
        # a narrow interval (85..95) should certify.
        positive_result = app.prove_continuous_single_axis_clearance(
            source_revision=source.revision,
            source_state_hash=source.state_hash,
            assembly=assembly,
            axis=axis,
            moving_instance_ids=("gear-inst",),
            stationary_instance_ids=("plate-inst",),
            start_angle_deg=85.0,
            end_angle_deg=95.0,
        )

        assert isinstance(positive_result, ContinuousSingleAxisProofResult)
        assert positive_result.status is ContinuousSingleAxisProofStatus.VERIFIED_CLEAR
        assert len(positive_result.certified_leaf_certificates) >= 1
        assert positive_result.exact_evaluations_count >= 1
        assert positive_result.collision_witness is None
        assert positive_result.proof_algorithm_version == CONTINUOUS_PROOF_ALGORITHM_VERSION
        assert positive_result.result_hash.startswith("sha256:")

        # Verify certificate coverage
        leaves = sorted(positive_result.certified_leaf_certificates, key=lambda c: c.interval_start_deg)
        assert leaves[0].interval_start_deg == pytest.approx(85.0)
        assert leaves[-1].interval_end_deg == pytest.approx(95.0)
        for cert in positive_result.certified_leaf_certificates:
            assert cert.minimum_certified_lower_clearance_mm > 0

        # === LIVE COLLISION WITNESS: interval containing 270 deg ===
        collision_result = app.prove_continuous_single_axis_clearance(
            source_revision=source.revision,
            source_state_hash=source.state_hash,
            assembly=assembly,
            axis=axis,
            moving_instance_ids=("gear-inst",),
            stationary_instance_ids=("plate-inst",),
            start_angle_deg=260.0,
            end_angle_deg=280.0,
        )
        assert collision_result.status is ContinuousSingleAxisProofStatus.COLLISION_WITNESS
        assert collision_result.collision_witness is not None
        assert collision_result.collision_witness.moving_instance_id == "gear-inst"
        assert collision_result.collision_witness.stationary_instance_id == "plate-inst"
        assert collision_result.collision_witness.interference_volume_mm3 > 0
        assert collision_result.collision_witness.classification is CollisionClassification.INTERFERENCE

        # === NOT PROVEN: resource-limited interval ===
        not_proven_result = app.prove_continuous_single_axis_clearance(
            source_revision=source.revision,
            source_state_hash=source.state_hash,
            assembly=assembly,
            axis=axis,
            moving_instance_ids=("gear-inst",),
            stationary_instance_ids=("plate-inst",),
            start_angle_deg=0.0,
            end_angle_deg=360.0,
            max_exact_evaluations=2,
            max_depth=1,
        )
        assert not_proven_result.status is ContinuousSingleAxisProofStatus.NOT_PROVEN
        assert not_proven_result.exact_evaluations_count <= 2

        # === Ordinary discrete sweep still says continuous_sweep_verified=False ===
        sweep = app.analyze_assembly_kinematics(
            source_revision=source.revision,
            source_state_hash=source.state_hash,
            assembly=assembly,
            axis=axis,
            moving_instance_ids=("gear-inst",),
            stationary_instance_ids=("plate-inst",),
            sample_angles_deg=(0.0, 90.0, 180.0, 270.0),
        )
        assert sweep.continuous_sweep_verified is False

        # === DETERMINISM: same inputs -> same result hash ===
        repeat = app.prove_continuous_single_axis_clearance(
            source_revision=source.revision,
            source_state_hash=source.state_hash,
            assembly=assembly,
            axis=axis,
            moving_instance_ids=("gear-inst",),
            stationary_instance_ids=("plate-inst",),
            start_angle_deg=85.0,
            end_angle_deg=95.0,
        )
        assert repeat.result_hash == positive_result.result_hash

        # === PROVENANCE: durable evidence is recorded ===
        evidence = app.get_continuous_proof_evidence(positive_result.result_hash)
        assert evidence is not None
        assert evidence.kind == "analysis.continuous_clearance_proof"
        assert evidence.producer_result_id == positive_result.result_hash
        assert evidence.input_hash == positive_result.request_hash
        prov = evidence.continuous_proof_execution_provenance
        assert prov is not None
        assert prov.request_hash == positive_result.request_hash
        assert prov.result_hash == positive_result.result_hash
        assert prov.source_assembly_hash == positive_result.source_assembly_hash
        assert prov.proof_algorithm_version == CONTINUOUS_PROOF_ALGORITHM_VERSION
        assert prov.provider_name == "freecad-transient-exact"
        assert prov.backend_provenance is not None
        assert prov.backend_provenance.backend_name == "freecad"
        assert prov.execution_mode == "freecadcmd-subprocess"

        # === NO STATE MUTATION ===
        after = app.load_state()
        assert after.revision == source.revision
        assert after.state_hash == source.state_hash

        # === NO PER-SUBDIVISION ARTIFACTS ===
        artifacts = sorted(workspace.glob("projects/*/runs/*/artifacts/*/metadata.json"))
        # Only the gear artifact should exist, no per-evaluation artifacts
        gear_artifacts = [a for a in artifacts if "gear" in a.read_text().lower() or "STEP" in a.read_text()]
        # At least the gear artifact exists but no proof-evaluation artifacts
        for a in artifacts:
            text = a.read_text()
            assert "radial" not in text.lower()
            assert "continuous_proof" not in text.lower()
