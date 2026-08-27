from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
from mechcad_harness.application import ProductionApplication
from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.backends.freecad import FreeCADBackend, discover_freecad
from mechcad_harness.backends.freecad_assembly import FreeCADAssemblyBackend
from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.imported_component import ImportedCadComponent
from mechcad_harness.kinematic_sweep import CollisionClassification
from mechcad_harness.models import Component, DesignState
from mechcad_harness.state import StateManager
from mechcad_harness.multi_joint_continuous_clearance import MultiJointContinuousProofStatus
from mechcad_harness.multi_joint_continuous_path import MultiJointPath
from mechcad_harness.multi_joint_kinematics import (
    JointConfiguration,
    KinematicModel,
    RevoluteJointModel,
)
from mechcad_harness.transient_assembly_analysis import TransientAssemblyAnalysisRequest
from mechcad_harness.transient_freecad_measurement import (
    FreeCADTransientAssemblyMeasurementProvider,
)


CANDIDATE = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"
if not os.environ.get("MECHCAD_FREECADCMD") and os.path.isfile(CANDIDATE):
    os.environ["MECHCAD_FREECADCMD"] = CANDIDATE

FREECAD_AVAILABLE = discover_freecad().available
pytestmark = pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCADCmd is unavailable")


class _RadialAxis:
    origin_x_mm = 0.0
    origin_y_mm = 0.0
    origin_z_mm = 0.0
    direction_x = 0.0
    direction_y = 0.0
    direction_z = 1.0


def _make_multishape_step_bytes() -> bytes:
    """Real trusted STEP with two separate top-level solids: A near x=0, B near x=100."""
    backend = FreeCADBackend()
    disc = discover_freecad().require_available()
    wd = Path(tempfile.mkdtemp())
    step = wd / "ms.step"
    script = (
        "import FreeCAD, Part\n"
        "doc=FreeCAD.newDocument('MS')\n"
        "a=doc.addObject('Part::Box','A'); a.Length=20;a.Width=20;a.Height=20; a.Placement.Base=FreeCAD.Vector(0,0,0)\n"
        "b=doc.addObject('Part::Box','B'); b.Length=20;b.Width=20;b.Height=20; b.Placement.Base=FreeCAD.Vector(100,0,0)\n"
        "doc.recompute()\n"
        "Part.export([a,b], r'" + str(step) + "')\n"
        "FreeCAD.closeDocument(doc.Name)\n"
    )
    result = backend._run(disc.executable, script, cwd=wd)
    if result.returncode != 0 or not step.is_file():
        raise RuntimeError(result.stderr or result.stdout or "multi-shape STEP generation failed")
    return step.read_bytes()


def _publish_imported(workspace, project_id, run_id, artifact_id, content):
    store = ArtifactStore(workspace, project_id=project_id, run_id=run_id)
    artifact = store.publish(
        artifact_id,
        ArtifactType.STEP,
        artifact_id + ".step",
        content,
        "test-producer",
        "1.0",
        1,
        "sha256:" + "b" * 64,
    )
    return artifact, artifact.sha256


def _imported(component_id, artifact_id, artifact_hash):
    return ImportedCadComponent(
        component_id=component_id,
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        format="step",
        source_revision=1,
        source_state_hash="sha256:" + "b" * 64,
    )


def _freecad_run(script: str) -> dict:
    backend = FreeCADBackend()
    disc = discover_freecad().require_available()
    with tempfile.TemporaryDirectory(prefix="mechcad-int-") as directory:
        result = backend._run(disc.executable, script, cwd=Path(directory))
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "FreeCAD script failed")
    line = next((l for l in result.stdout.splitlines() if l.startswith("INV=")), None)
    if line is None:
        raise RuntimeError("FreeCAD script produced no INV payload: " + result.stdout)
    return json.loads(line.removeprefix("INV="))


def _transient_imported_invariants(artifact_path: Path) -> dict:
    script = (
        "import FreeCAD, Part, json\n"
        "doc=FreeCAD.newDocument('T')\n"
        "Part.insert(r'" + str(artifact_path) + "', doc.Name)\n"
        "objs=[o for o in doc.Objects if hasattr(o,'Shape') and not o.Shape.isNull()]\n"
        "shape=Part.makeCompound([o.Shape.copy() for o in objs])\n"
        "b=shape.BoundBox\n"
        "print('INV='+json.dumps({'volume':shape.Volume,'xmin':b.XMin,'xmax':b.XMax,'ymin':b.YMin,'ymax':b.YMax,'zmin':b.ZMin,'zmax':b.ZMax}))\n"
        "FreeCAD.closeDocument(doc.Name)\n"
    )
    return _freecad_run(script)


def _persisted_imported_invariants(assembly_fcstd_path: Path) -> dict:
    script = (
        "import FreeCAD, Part, json\n"
        "doc=FreeCAD.openDocument(r'" + str(assembly_fcstd_path) + "')\n"
        "objs=[o for o in doc.Objects if hasattr(o,'Shape') and not o.Shape.isNull()]\n"
        "best=None\n"
        "for o in objs:\n"
        "    v=o.Shape.Volume\n"
        "    if best is None or v>best[0]: best=(v,o.Shape.copy())\n"
        "sh=best[1]\n"
        "b=sh.BoundBox\n"
        "print('INV='+json.dumps({'volume':best[0],'xmin':b.XMin,'xmax':b.XMax,'ymin':b.YMin,'ymax':b.YMax,'zmin':b.ZMin,'zmax':b.ZMax}))\n"
        "FreeCAD.closeDocument(doc.Name)\n"
    )
    return _freecad_run(script)


def _obstacle_program(imported, placement_x_mm: float = 110.0) -> CadAssemblyProgram:
    return CadAssemblyProgram(
        assembly_id="multi-shape-transient",
        parts=(
            CadPartProgram(
                part_id="obs",
                operations=(BasePlateOperation(operation_id="obs", length_mm=20, width_mm=20, thickness_mm=20),),
            ),
        ),
        imported_components=(imported,),
        instances=(
            CadComponentInstance(instance_id="imp_inst", part_id="IMP"),
            CadComponentInstance(
                instance_id="obs_inst",
                part_id="obs",
                placement=CadRigidTransform(x_mm=placement_x_mm),
            ),
        ),
    )


def test_real_multishape_step_detects_collision_against_second_shape(tmp_path):
    content = _make_multishape_step_bytes()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    artifact, sha = _publish_imported(workspace, "PRJ", "RUN-1", "ART-multi", content)
    imported = _imported("IMP", artifact.artifact_id, sha)
    program = _obstacle_program(imported)

    provider = FreeCADTransientAssemblyMeasurementProvider(workspace=workspace, project_id="PRJ")
    identity = assembly_hash(program)
    request = TransientAssemblyAnalysisRequest(
        source_assembly_hash=identity,
        transformed_assembly_hash=identity,
        sweep_request_hash="sha256:request",
        sample_angle_deg=0,
        pairs=(("imp_inst", "obs_inst"),),
    )
    measurements = provider.exact_measure(request, program)
    moving, stationary, volume, distance = measurements[0]
    assert (moving, stationary) == ("imp_inst", "obs_inst")
    # Obstacle intersects only the second imported solid; the complete-artifact
    # realization must detect it.
    assert volume > 0


def test_old_first_candidate_only_misses_second_shape(tmp_path):
    content = _make_multishape_step_bytes()
    artifact_path = tmp_path / "ms.step"
    artifact_path.write_bytes(content)
    obstacle_path = tmp_path / "obs.step"
    backend = FreeCADBackend()
    disc = discover_freecad().require_available()
    with tempfile.TemporaryDirectory(prefix="mechcad-old-") as directory:
        # Build the obstacle as its own STEP so we can reuse the provider geometry.
        build = (
            "import FreeCAD, Part\n"
            "doc=FreeCAD.newDocument('OBS')\n"
            "o=doc.addObject('Part::Box','obs'); o.Length=20;o.Width=20;o.Height=20; o.Placement.Base=FreeCAD.Vector(110,0,0)\n"
            "doc.recompute()\n"
            "Part.export([o], r'" + str(obstacle_path) + "')\n"
            "FreeCAD.closeDocument(doc.Name)\n"
        )
        r0 = backend._run(disc.executable, build, cwd=Path(directory))
        assert r0.returncode == 0 and obstacle_path.is_file()

        script = (
            "import FreeCAD, Part, json\n"
            "doc=FreeCAD.newDocument('PROBE')\n"
            "Part.insert(r'" + str(obstacle_path) + "', doc.Name)\n"
            "obs_shape=[o.Shape.copy() for o in doc.Objects if hasattr(o,'Shape') and not o.Shape.isNull()][0]\n"
            "Part.insert(r'" + str(artifact_path) + "', doc.Name)\n"
            "cands=[o for o in doc.Objects if hasattr(o,'Shape') and not o.Shape.isNull() and o.Name!='obs']\n"
            "comp=Part.makeCompound([c.Shape.copy() for c in cands])\n"
            "first=cands[0].Shape.copy()\n"
            # emulate legacy first-candidate realization
            "v_first=first.common(obs_shape).Volume\n"
            "v_comp=comp.common(obs_shape).Volume\n"
            "print('PROBE='+json.dumps({'num':len(cands),'first':v_first,'compound':v_comp}))\n"
            "FreeCAD.closeDocument(doc.Name)\n"
        )
        r = backend._run(disc.executable, script, cwd=Path(directory))
    assert r.returncode == 0, r.stderr or r.stdout
    line = next(l for l in r.stdout.splitlines() if l.startswith("PROBE="))
    probe = json.loads(line.removeprefix("PROBE="))
    assert probe["num"] == 2
    # Legacy realization (first top-level shape only) misses the second solid.
    assert probe["first"] == pytest.approx(0.0, abs=1e-6)
    # Correct realization (all top-level shapes) detects the collision.
    assert probe["compound"] > 0


def test_persisted_vs_transient_geometry_consistency(tmp_path):
    content = _make_multishape_step_bytes()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    artifact, sha = _publish_imported(workspace, "PRJ", "RUN-2", "ART-multi", content)
    imported = _imported("IMP", artifact.artifact_id, sha)
    program = _obstacle_program(imported, placement_x_mm=0.0)

    backend = FreeCADAssemblyBackend()
    gen = backend.generate_assembly(
        program, workspace, project_id="PRJ", run_id="RUN-2", revision=1, state_hash="sha256:" + "b" * 64
    )
    persisted_fcstd = workspace / gen.fcstd.relative_path

    transient = _transient_imported_invariants(workspace / artifact.relative_path)
    persisted = _persisted_imported_invariants(persisted_fcstd)

    # Both realizations must represent the same complete imported geometry:
    # two solids totalling ~16000 mm3 spanning x in [0, 120].
    assert transient["volume"] == pytest.approx(16000.0, rel=1e-6)
    assert persisted["volume"] == pytest.approx(16000.0, rel=1e-6)
    assert transient["volume"] == pytest.approx(persisted["volume"], rel=1e-6)
    assert transient["xmax"] == pytest.approx(120.0, abs=1e-4)
    assert persisted["xmax"] == pytest.approx(120.0, abs=1e-4)
    assert transient["xmax"] == pytest.approx(persisted["xmax"], abs=1e-4)
    assert transient["xmin"] == pytest.approx(persisted["xmin"], abs=1e-4)


def test_imported_local_extent_includes_all_shapes(tmp_path):
    content = _make_multishape_step_bytes()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    artifact, sha = _publish_imported(workspace, "PRJ", "RUN-1", "ART-multi", content)
    imported = _imported("IMP", artifact.artifact_id, sha)
    program = _obstacle_program(imported, placement_x_mm=0.0)

    provider = FreeCADTransientAssemblyMeasurementProvider(workspace=workspace, project_id="PRJ")
    extents = provider.trusted_local_geometry_extents(program, ("imp_inst",))
    radius = extents["imp_inst"].local_radius_mm
    # The second solid sits near x=120; first-shape-only logic would yield ~34 mm.
    assert radius > 100.0


def test_imported_radial_bounds_include_all_shapes(tmp_path):
    content = _make_multishape_step_bytes()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    artifact, sha = _publish_imported(workspace, "PRJ", "RUN-1", "ART-multi", content)
    imported = _imported("IMP", artifact.artifact_id, sha)
    program = _obstacle_program(imported, placement_x_mm=0.0)

    provider = FreeCADTransientAssemblyMeasurementProvider(workspace=workspace, project_id="PRJ")
    radii = provider.geometry_radial_bounds(program, _RadialAxis(), ("imp_inst",))
    # The second solid extends to x=120; a first-shape-only bound would be ~28 mm.
    assert radii["imp_inst"] > 100.0


def _make_app(tmp_path, content):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    ownership = workspace / "ownership.yaml"
    dependencies = workspace / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /components/*\n    owner: engineer\n",
        encoding="utf-8",
    )
    dependencies.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "when": ["/components/*"],
                        "invalidates": [
                            "analysis.multi_joint_collision_sweep",
                            "analysis.continuous_multi_joint_clearance_proof",
                        ],
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    StateManager(workspace).create_project(
        "PRJ",
        DesignState(id="D", revision=1, components=[Component(id="x", name="X")]),
    )
    artifact, sha = _publish_imported(workspace, "PRJ", "RUN-1", "ART-multi", content)
    imported = _imported("IMP", artifact.artifact_id, sha)
    identity = AgentIdentity(
        agent_name="t", agent_version="1.0", role="engineer", protocol_version="1.0"
    )
    app = ProductionApplication.create(
        workspace,
        "PRJ",
        FakeAgentAdapter(identity, scripted_responses=()),
        ownership_path=ownership,
        dependency_path=dependencies,
    )
    source = app.load_state()
    return app, imported, source.revision, source.state_hash


def _chain_program(imported) -> CadAssemblyProgram:
    return CadAssemblyProgram(
        assembly_id="m10-multi-chain",
        parts=(
            CadPartProgram(
                part_id="base",
                operations=(BasePlateOperation(operation_id="base", length_mm=20, width_mm=20, thickness_mm=20),),
            ),
            CadPartProgram(
                part_id="link",
                operations=(BasePlateOperation(operation_id="link", length_mm=20, width_mm=20, thickness_mm=20),),
            ),
            CadPartProgram(
                part_id="obs",
                operations=(BasePlateOperation(operation_id="obs", length_mm=20, width_mm=20, thickness_mm=20),),
            ),
        ),
        imported_components=(imported,),
        instances=(
            CadComponentInstance(
                instance_id="base", part_id="base", placement=CadRigidTransform(x_mm=0, y_mm=0, z_mm=-200)
            ),
            CadComponentInstance(
                instance_id="link", part_id="link", placement=CadRigidTransform(x_mm=0, y_mm=0, z_mm=-100)
            ),
            CadComponentInstance(instance_id="imp_inst", part_id="IMP"),
            CadComponentInstance(
                instance_id="obs_inst", part_id="obs", placement=CadRigidTransform(x_mm=110)
            ),
        ),
    )


def _chain_model() -> KinematicModel:
    return KinematicModel(
        model_id="m",
        joints=(
            RevoluteJointModel(
                joint_id="j1",
                parent_instance_id="base",
                child_instance_id="link",
                axis_origin_x_mm=0,
                axis_origin_y_mm=0,
                axis_origin_z_mm=0,
                axis_direction_x=0,
                axis_direction_y=0,
                axis_direction_z=1,
                min_angle_deg=-10,
                max_angle_deg=10,
            ),
            RevoluteJointModel(
                joint_id="j2",
                parent_instance_id="link",
                child_instance_id="imp_inst",
                axis_origin_x_mm=0,
                axis_origin_y_mm=0,
                axis_origin_z_mm=0,
                axis_direction_x=0,
                axis_direction_y=0,
                axis_direction_z=1,
                min_angle_deg=-10,
                max_angle_deg=10,
            ),
        ),
    )


def test_m10_3_collision_through_exact_sweep_detects_second_shape(tmp_path):
    content = _make_multishape_step_bytes()
    app, imported, revision, state_hash = _make_app(tmp_path, content)
    program = _chain_program(imported)
    model = _chain_model()
    configs = (
        JointConfiguration(model_id="m", positions={"j1": 0.0, "j2": 0.0}),
        JointConfiguration(model_id="m", positions={"j1": 10.0, "j2": 0.0}),
    )
    result = app.analyze_multi_joint_collision_sweep(
        source_revision=revision,
        source_state_hash=state_hash,
        assembly=program,
        model=model,
        configurations=configs,
        moving_instance_ids=("link", "imp_inst"),
        stationary_instance_ids=("base", "obs_inst"),
    )
    for cr in result.configuration_results:
        pair = next(
            p
            for p in cr.pair_results
            if p.moving_instance_id == "imp_inst" and p.stationary_instance_id == "obs_inst"
        )
        # Collision occurs only against the second imported solid.
        assert pair.interference_volume_mm3 > 0
        assert pair.classification is CollisionClassification.INTERFERENCE


def test_m10_4_proof_uses_complete_imported_extent(tmp_path):
    content = _make_multishape_step_bytes()
    app, imported, revision, state_hash = _make_app(tmp_path, content)
    program = _chain_program(imported)
    model = _chain_model()
    path = MultiJointPath(
        model_id="m",
        waypoints=(
            JointConfiguration(model_id="m", positions={"j1": 0.0, "j2": 0.0}),
            JointConfiguration(model_id="m", positions={"j1": 10.0, "j2": 0.0}),
        ),
    )
    result = app.prove_continuous_multi_joint_path_clearance(
        source_revision=revision,
        source_state_hash=state_hash,
        assembly=program,
        model=model,
        path=path,
        moving_instance_ids=("link", "imp_inst"),
        stationary_instance_ids=("base", "obs_inst"),
    )
    # The imported second solid collides with the obstacle; the complete-artifact
    # realization must surface it rather than reporting verified clearance.
    assert result.status is MultiJointContinuousProofStatus.COLLISION_WITNESS
