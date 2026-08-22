"""M9-4: trusted analysis / backend provenance for kinematic sweeps.

These tests prove that durable evidence can distinguish a real FreeCAD exact
execution from a deterministic/test execution, and that the provenance is bound
to the exact analysis request/result identity. They also prove an ordinary
workflow caller cannot spoof trusted execution provenance.
"""

import json

import importlib.util
import pytest

from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
from mechcad_harness.application import ProductionApplication
from mechcad_harness.artifacts import ArtifactStore
from mechcad_harness.backends.freecad import discover_freecad
from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_compilation import MountingPlateDesignSpec
from mechcad_harness.imported_component import ImportedCadComponent, resolve_imported_component
from mechcad_harness.kinematic_sweep import RevoluteAxis
from mechcad_harness.models import Component, DesignState
from mechcad_harness.runs import TaskDefinition
from mechcad_harness.state import StateManager
from mechcad_harness.tools import GearworksTools
from mechcad_harness.transient_assembly_analysis import TransientAssemblyAnalysisRequest
from mechcad_harness.transient_freecad_measurement import FreeCADTransientAssemblyMeasurementProvider


FREECAD_AVAILABLE = discover_freecad().available
GEAR_AVAILABLE = importlib.util.find_spec("py_gearworks") is not None and importlib.util.find_spec("build123d") is not None


def _make_application(tmp_path, kinematic_measure=None):
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /components/*\n    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    dependencies.write_text(
        json.dumps({"rules": [{"when": ["/components/*"], "invalidates": ["artifact.gear", "analysis.kinematic_sweep"]}], "edges": []}),
        encoding="utf-8",
    )
    state = DesignState(
        id="DES-m9-4",
        revision=1,
        components=[Component(id="PRT-fixture", name="Fixture")],
    )
    StateManager(workspace).create_project("PRJ-m9-4", state)

    identity = AgentIdentity(
        agent_name="mechcad-transmission",
        agent_version="1.0",
        role="transmission_engineer",
        protocol_version="1.0",
    )
    adapter = FakeAgentAdapter(identity, scripted_responses=())
    return ProductionApplication.create(
        workspace,
        "PRJ-m9-4",
        adapter,
        ownership_path=ownership,
        dependency_path=dependencies,
        additional_tool_registrations=GearworksTools.registrations(),
        kinematic_measure=kinematic_measure,
    )


def _produce_real_imported(tmp_path, application):
    """Produce a real trusted STEP artifact via the production producer and
    resolve it through the production ArtifactStore path.

    The transient FreeCAD measurement provider fails closed when the resolved
    imported artifact is not genuinely present in the workspace, so the live
    provenance tests must exercise the real artifact path (mirroring M9-3).
    """
    import os

    os.environ.setdefault("MECHCAD_FREECADCMD", r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe")
    source = application.load_state()
    run = application.create_run().run
    task = TaskDefinition(
        task_id="TASK-gear",
        run_id=run.run_id,
        task_type="tool",
        objective="cad",
        bound_revision=source.revision,
        bound_state_hash=source.state_hash,
        allowed_tools=("mechcad-build-spur-gear-cad@1.0",),
    )
    application.run_controller.add_task(run.run_id, task)
    gear_input = {
        "module_mm": 2.0,
        "teeth": 12,
        "face_width_mm": 5.0,
        "pressure_angle_deg": 20.0,
        "requested_formats": ["step"],
    }
    result = application.tool_broker.execute(
        run.run_id,
        task.task_id,
        "mechcad-build-spur-gear-cad",
        "1.0",
        gear_input,
        evidence_node="artifact.gear",
    )
    assert result.status.value == "succeeded"
    refs = result.output["artifact_references"]
    artifact_id = refs[0]["artifact_id"]
    artifact_hash = refs[0]["sha256"]
    store = ArtifactStore(
        application.state_manager.workspace,
        project_id="PRJ-m9-4",
        run_id=run.run_id,
        task_id=task.task_id,
    )
    return resolve_imported_component(
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        store=store,
        component_id="imported_body",
    )


def _deterministic_exact_measure(request: TransientAssemblyAnalysisRequest, program: CadAssemblyProgram):
    outcomes = {0.0: (0.0, 5.0), 45.0: (0.0, 0.0), 90.0: (1.0, 0.0)}
    volume, distance = outcomes.get(float(round(request.sample_angle_deg, 6)), (0.0, 1.0))
    return tuple((moving, stationary, volume, distance) for moving, stationary in request.pairs)


def _assembly(application, imported=None):
    spec = MountingPlateDesignSpec(
        part_id="fixture_plate",
        plate_length_mm=120.0,
        plate_width_mm=100.0,
        plate_thickness_mm=10.0,
        mounting_holes=(MountingPlateDesignSpec.HoleSpec(hole_id="h1", x_mm=30.0, y_mm=25.0, diameter_mm=8.0),),
    )
    program = application.compile_design_spec(
        source_revision=1,
        source_state_hash=application.load_state().state_hash,
        spec=spec,
    ).program
    if imported is None:
        imported = ImportedCadComponent(
            component_id="imported_body",
            artifact_id="ART-m9-4-body",
            artifact_hash="sha256:" + "a" * 64,
            format="step",
            source_revision=1,
            source_state_hash="sha256:" + "b" * 64,
        )
    return CadAssemblyProgram(
        assembly_id="m9-4-fixture",
        parts=(program,),
        imported_components=(imported,),
        instances=(
            CadComponentInstance(instance_id="inst_plate", part_id="fixture_plate", placement=CadRigidTransform(x_mm=-20, y_mm=0, z_mm=0)),
            CadComponentInstance(instance_id="inst_body", part_id="imported_body", placement=CadRigidTransform(x_mm=20, y_mm=0, z_mm=0)),
        ),
    )


def _run_sweep(application, assembly, angles=(0.0, 45.0, 90.0)):
    source = application.load_state()
    axis = RevoluteAxis(origin_x_mm=0, origin_y_mm=0, origin_z_mm=0, direction_x=0, direction_y=1, direction_z=0, frame_id="fixture_frame")
    return application.analyze_assembly_kinematics(
        source_revision=source.revision,
        source_state_hash=source.state_hash,
        assembly=assembly,
        axis=axis,
        moving_instance_ids=("inst_body",),
        stationary_instance_ids=("inst_plate",),
        sample_angles_deg=angles,
    )


# C. Caller cannot spoof trusted provenance through public inputs.


def test_public_analysis_call_accepts_no_trusted_provenance_override():
    import inspect

    params = inspect.signature(ProductionApplication.analyze_assembly_kinematics).parameters
    for forbidden in ("provider_name", "provider_version", "backend_name", "runtime_version", "provenance", "backend_provenance"):
        assert forbidden not in params


# B. Deterministic provider differentiation (no FreeCAD identity).


def test_deterministic_provider_yields_deterministic_provenance(tmp_path):
    application = _make_application(tmp_path, kinematic_measure=_deterministic_exact_measure)
    assembly = _assembly(application)
    sweep = _run_sweep(application, assembly)

    evidence = application.get_kinematic_sweep_evidence(sweep.result_hash)
    assert evidence is not None
    prov = evidence.analysis_execution_provenance
    assert prov is not None
    assert prov.provider_name == "deterministic-test-provider"
    assert prov.provider_version == "deterministic-test@1.0"
    assert prov.execution_mode == "deterministic-injected"
    assert prov.backend_provenance is None
    assert evidence.backend_provenance is None


def test_deterministic_provider_is_not_freecad_provider(tmp_path):
    application = _make_application(tmp_path, kinematic_measure=_deterministic_exact_measure)
    assembly = _assembly(application)
    sweep = _run_sweep(application, assembly)
    prov = application.get_kinematic_sweep_evidence(sweep.result_hash).analysis_execution_provenance
    assert prov.provider_name != "freecad-transient-exact"
    assert prov.backend_provenance is None


# D. Result binding.


def test_provenance_binds_request_result_and_assembly_hashes(tmp_path):
    application = _make_application(tmp_path, kinematic_measure=_deterministic_exact_measure)
    assembly = _assembly(application)
    sweep = _run_sweep(application, assembly)
    prov = application.get_kinematic_sweep_evidence(sweep.result_hash).analysis_execution_provenance
    assert prov.request_hash == sweep.request_hash
    assert prov.result_hash == sweep.result_hash
    assert prov.source_assembly_hash == sweep.source_assembly_hash
    assert prov.sweep_version == sweep.sweep_version
    assert prov.source_assembly_hash == assembly_hash(assembly)


# G. No result-hash corruption.


def test_result_hash_stable_when_provenance_stored_separately(tmp_path):
    application = _make_application(tmp_path, kinematic_measure=_deterministic_exact_measure)
    assembly = _assembly(application)
    first = _run_sweep(application, assembly)
    second = _run_sweep(application, assembly)
    assert first.result_hash == second.result_hash


# F. Stable identity.


def test_deterministic_provenance_identity_is_stable(tmp_path):
    application = _make_application(tmp_path, kinematic_measure=_deterministic_exact_measure)
    assembly = _assembly(application)
    first = _run_sweep(application, assembly)
    second = _run_sweep(application, assembly)
    p1 = application.get_kinematic_sweep_evidence(first.result_hash).analysis_execution_provenance
    p2 = application.get_kinematic_sweep_evidence(second.result_hash).analysis_execution_provenance
    assert p1.provider_name == p2.provider_name
    assert p1.provider_version == p2.provider_version
    assert p1.execution_mode == p2.execution_mode
    assert p1.backend_provenance == p2.backend_provenance


# H. No state mutation.


def test_analysis_does_not_mutate_design_state(tmp_path):
    application = _make_application(tmp_path, kinematic_measure=_deterministic_exact_measure)
    before = application.load_state().state_hash
    assembly = _assembly(application)
    _run_sweep(application, assembly)
    assert application.load_state().state_hash == before


# A / E / I. Live FreeCAD provider provenance (requires real FreeCAD).


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD runtime not configured")
@pytest.mark.skipif(not GEAR_AVAILABLE, reason="gear + build123d extras are not installed")
class TestM9_4LiveFreeCADProvenance:
    def test_default_live_provider_uses_freecad_provenance(self, tmp_path):
        import os

        candidate = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"
        os.environ["MECHCAD_FREECADCMD"] = os.environ.get("MECHCAD_FREECADCMD") or candidate
        application = _make_application(tmp_path)
        imported = _produce_real_imported(tmp_path, application)
        assembly = _assembly(application, imported)
        sweep = _run_sweep(application, assembly)

        evidence = application.get_kinematic_sweep_evidence(sweep.result_hash)
        assert evidence is not None
        prov = evidence.analysis_execution_provenance
        assert prov.provider_name == "freecad-transient-exact"
        assert prov.provider_version == "mechcad-freecad-transient@1.0"
        assert prov.backend_provenance is not None
        assert prov.backend_provenance.backend_name == "freecad"
        assert prov.backend_provenance.backend_adapter_version == "mechcad-freecad@2.1"
        assert prov.backend_provenance.library_name == "FreeCAD"
        assert prov.backend_provenance.library_version and prov.backend_provenance.library_version != "unknown"
        assert prov.execution_mode == "freecadcmd-subprocess"

    def test_live_provenance_records_actual_runtime_identity(self, tmp_path):
        import os

        candidate = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"
        os.environ["MECHCAD_FREECADCMD"] = os.environ.get("MECHCAD_FREECADCMD") or candidate
        application = _make_application(tmp_path)
        imported = _produce_real_imported(tmp_path, application)
        assembly = _assembly(application, imported)
        sweep = _run_sweep(application, assembly)
        prov = application.get_kinematic_sweep_evidence(sweep.result_hash).analysis_execution_provenance

        backend = FreeCADTransientAssemblyMeasurementProvider().provenance()
        assert prov.backend_provenance == backend
        assert prov.backend_provenance.library_source is not None

    def test_live_provenance_identity_is_stable_across_runs(self, tmp_path):
        import os

        candidate = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"
        os.environ["MECHCAD_FREECADCMD"] = os.environ.get("MECHCAD_FREECADCMD") or candidate
        application = _make_application(tmp_path)
        imported = _produce_real_imported(tmp_path, application)
        assembly = _assembly(application, imported)
        first = _run_sweep(application, assembly)
        second = _run_sweep(application, assembly)
        p1 = application.get_kinematic_sweep_evidence(first.result_hash).analysis_execution_provenance
        p2 = application.get_kinematic_sweep_evidence(second.result_hash).analysis_execution_provenance
        assert p1.backend_provenance == p2.backend_provenance
        assert p1.provider_name == p2.provider_name
        assert p1.execution_mode == p2.execution_mode
