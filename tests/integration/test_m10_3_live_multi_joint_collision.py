from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os

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
from mechcad_harness.imported_component import ImportedCadComponent, resolve_imported_component
from mechcad_harness.kinematic_sweep import CollisionClassification
from mechcad_harness.models import Component, DesignState
from mechcad_harness.multi_joint_kinematics import (
    JointConfiguration,
    KinematicModel,
    RevoluteJointModel,
    joint_configuration_hash,
    kinematic_model_hash,
)
from mechcad_harness.runs import TaskDefinition
from mechcad_harness.state import StateManager
from mechcad_harness.tools import GearworksTools
from mechcad_harness.transient_freecad_measurement import FreeCADTransientAssemblyMeasurementProvider


GEAR_AVAILABLE = (
    importlib.util.find_spec("py_gearworks") is not None
    and importlib.util.find_spec("build123d") is not None
)
FREECAD_CANDIDATE = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"


def _freecad_available_for_test() -> bool:
    if os.environ.get("MECHCAD_FREECADCMD"):
        return discover_freecad().available
    if os.path.isfile(FREECAD_CANDIDATE):
        return True
    return discover_freecad().available


FREECAD_AVAILABLE = _freecad_available_for_test()


def _make_application(tmp_path):
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /components/*\n    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    dependencies.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "when": ["/components/*"],
                        "invalidates": [
                            "artifact.gear",
                            "analysis.multi_joint_kinematics",
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
        "PRJ-M10-3-live",
        DesignState(
            id="DES-M10-3-live",
            revision=1,
            components=[Component(id="fixture", name="Fixture")],
        ),
    )
    identity = AgentIdentity(
        agent_name="mechcad-transmission",
        agent_version="1.0",
        role="transmission_engineer",
        protocol_version="1.0",
    )
    return ProductionApplication.create(
        workspace,
        "PRJ-M10-3-live",
        FakeAgentAdapter(identity, scripted_responses=()),
        ownership_path=ownership,
        dependency_path=dependencies,
        additional_tool_registrations=GearworksTools.registrations(),
    )


def _public_artifact_metadata(workspace):
    return tuple(
        sorted(
            path.relative_to(workspace).as_posix()
            for path in workspace.glob("projects/*/runs/*/artifacts/*/metadata.json")
        )
    )


def _transform_map(configuration_result):
    return {
        item.instance_id: item.transform
        for item in configuration_result.instance_world_transforms
    }


def _transform_tuple(transform):
    return (
        transform.x_mm,
        transform.y_mm,
        transform.z_mm,
        *transform.rotation_quaternion,
    )


def _gear_input():
    return {
        "module_mm": 2.0,
        "teeth": 12,
        "face_width_mm": 5.0,
        "pressure_angle_deg": 20.0,
        "requested_formats": ["step"],
    }


def test_test_discovery_considers_documented_fallback_when_env_is_unset(
    monkeypatch,
):
    monkeypatch.delenv("MECHCAD_FREECADCMD", raising=False)
    monkeypatch.setattr(
        os.path,
        "isfile",
        lambda path: path == FREECAD_CANDIDATE,
    )

    assert _freecad_available_for_test()


@pytest.mark.skipif(not GEAR_AVAILABLE, reason="gear + build123d extras are not installed")
@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD not available through discovery")
def test_live_multi_joint_collision_uses_real_freecad_and_preserves_source(
    tmp_path, monkeypatch
):
    discovered = discover_freecad()
    executable = discovered.executable or os.environ.get("MECHCAD_FREECADCMD") or FREECAD_CANDIDATE
    monkeypatch.setenv("MECHCAD_FREECADCMD", executable)
    runtime = discover_freecad().require_available()
    print(
        "M10_3_RUNTIME="
        + json.dumps(
            {
                "available": runtime.available,
                "executable": runtime.executable,
                "version": runtime.version,
                "importable": runtime.importable,
                "execution_boundary": runtime.execution_boundary,
                "gear_available": GEAR_AVAILABLE,
            },
            sort_keys=True,
        )
    )

    app = _make_application(tmp_path)
    source = app.load_state()
    source_revision = source.revision
    source_state_hash = source.state_hash

    # Produce the imported component only through the trusted production tool path.
    run = app.create_run().run
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
    tool_result = app.tool_broker.execute(
        run.run_id,
        task.task_id,
        "mechcad-build-spur-gear-cad",
        "1.0",
        _gear_input(),
        evidence_node="artifact.gear",
    )
    assert tool_result.status.value == "succeeded"
    assert tool_result.backend_provenance is not None
    assert tool_result.backend_provenance.library_name == "py_gearworks"
    reference = tool_result.output["artifact_references"][0]
    artifact_id = reference["artifact_id"]
    artifact_hash = reference["sha256"]
    store = ArtifactStore(
        app.state_manager.workspace,
        project_id=app.project_id,
        run_id=run.run_id,
        task_id=task.task_id,
    )
    artifact = store.existing(artifact_id)
    assert artifact is not None
    assert artifact.artifact_type is ArtifactType.STEP
    artifact_path = app.state_manager.workspace / artifact.relative_path
    assert artifact_hash == f"sha256:{hashlib.sha256(artifact_path.read_bytes()).hexdigest()}"
    imported = resolve_imported_component(
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        store=store,
        component_id="link-2-gear",
    )
    assert isinstance(imported, ImportedCadComponent)
    assert imported.source_revision == source_revision
    assert imported.source_state_hash == source_state_hash

    # Compile a source-bound generated component and use it with the trusted import.
    compiled = app.compile_design_spec(
        source_revision=source_revision,
        source_state_hash=source_state_hash,
        spec=MountingPlateDesignSpec(
            part_id="generated_link_plate",
            plate_length_mm=40.0,
            plate_width_mm=30.0,
            plate_thickness_mm=10.0,
            mounting_holes=(
                MountingPlateDesignSpec.HoleSpec(
                    hole_id="mount",
                    x_mm=10.0,
                    y_mm=10.0,
                    diameter_mm=6.0,
                ),
            ),
        ),
    )
    assert compiled.source_revision == source_revision
    assert compiled.source_state_hash == source_state_hash
    plate = compiled.program

    assembly = CadAssemblyProgram(
        assembly_id="m10-3-live-mixed-chain",
        parts=(plate,),
        imported_components=(imported,),
        instances=(
            CadComponentInstance(
                instance_id="base",
                part_id=plate.part_id,
                placement=CadRigidTransform(x_mm=0.0, y_mm=0.0, z_mm=0.0),
            ),
            CadComponentInstance(
                instance_id="link-1",
                part_id=plate.part_id,
                placement=CadRigidTransform(x_mm=20.0, y_mm=20.0, z_mm=20.0),
            ),
            CadComponentInstance(
                instance_id="link-2",
                part_id=imported.component_id,
                placement=CadRigidTransform(x_mm=70.0, y_mm=20.0, z_mm=20.0),
            ),
        ),
    )
    model = KinematicModel(
        model_id="m10-3-live-chain-model",
        joints=(
            RevoluteJointModel(
                joint_id="joint-1",
                parent_instance_id="base",
                child_instance_id="link-1",
                axis_origin_x_mm=0.0,
                axis_origin_y_mm=0.0,
                axis_origin_z_mm=0.0,
                axis_direction_x=0.0,
                axis_direction_y=0.0,
                axis_direction_z=1.0,
                min_angle_deg=-45.0,
                max_angle_deg=45.0,
            ),
            RevoluteJointModel(
                joint_id="joint-2",
                parent_instance_id="link-1",
                child_instance_id="link-2",
                axis_origin_x_mm=50.0,
                axis_origin_y_mm=0.0,
                axis_origin_z_mm=0.0,
                axis_direction_x=0.0,
                axis_direction_y=0.0,
                axis_direction_z=1.0,
                min_angle_deg=-45.0,
                max_angle_deg=45.0,
            ),
        ),
    )
    configurations = (
        JointConfiguration(
            model_id=model.model_id,
            positions={"joint-1": 0.0, "joint-2": 0.0},
        ),
        JointConfiguration(
            model_id=model.model_id,
            positions={"joint-1": 30.0, "joint-2": 0.0},
        ),
        JointConfiguration(
            model_id=model.model_id,
            positions={"joint-1": 0.0, "joint-2": 30.0},
        ),
        JointConfiguration(
            model_id=model.model_id,
            positions={"joint-1": 30.0, "joint-2": 30.0},
        ),
    )

    source_assembly_hash = assembly_hash(assembly)
    source_instances = tuple(
        (item.instance_id, item.placement.model_dump(mode="json"))
        for item in assembly.instances
    )
    state_before = app.load_state()
    artifacts_before = _public_artifact_metadata(app.state_manager.workspace)
    assert artifacts_before == (
        f"projects/{app.project_id}/runs/{run.run_id}/artifacts/{artifact_id}/metadata.json",
    )
    artifact_bytes_before = artifact_path.read_bytes()

    provider = app._kinematic_measurement_provider
    assert isinstance(provider, FreeCADTransientAssemblyMeasurementProvider)
    assert provider.execute is None
    assert provider.execute_in_workspace is None
    assert app.kinematic_measure.__func__ is FreeCADTransientAssemblyMeasurementProvider.exact_measure

    result = app.analyze_multi_joint_collision_sweep(
        source_revision=source_revision,
        source_state_hash=source_state_hash,
        assembly=assembly,
        model=model,
        configurations=configurations,
        moving_instance_ids=("link-1", "link-2"),
        stationary_instance_ids=("base",),
    )

    assert [item.configuration_index for item in result.configuration_results] == [0, 1, 2, 3]
    assert result.source_assembly_hash == source_assembly_hash
    assert result.model_hash == kinematic_model_hash(model)
    assert result.request_hash.startswith("sha256:")
    assert result.result_hash.startswith("sha256:")
    assert result.continuous_path_verified is False

    transform_maps = [_transform_map(item) for item in result.configuration_results]
    home, q1_only, q2_only, q1_q2 = transform_maps
    assert _transform_tuple(home["base"]) == pytest.approx(_transform_tuple(q1_only["base"]))
    assert _transform_tuple(home["base"]) == pytest.approx(_transform_tuple(q2_only["base"]))
    assert _transform_tuple(home["base"]) == pytest.approx(_transform_tuple(q1_q2["base"]))
    assert _transform_tuple(home["link-1"]) != pytest.approx(_transform_tuple(q1_only["link-1"]))
    assert _transform_tuple(home["link-2"]) != pytest.approx(_transform_tuple(q1_only["link-2"]))
    assert _transform_tuple(home["link-1"]) == pytest.approx(_transform_tuple(q2_only["link-1"]))
    assert _transform_tuple(home["link-2"]) != pytest.approx(_transform_tuple(q2_only["link-2"]))
    assert _transform_tuple(home["link-2"]) != pytest.approx(_transform_tuple(q1_q2["link-2"]))

    independent_q2 = app.evaluate_multi_joint_configuration(
        source_revision=source_revision,
        source_state_hash=source_state_hash,
        assembly=assembly,
        model=model,
        configuration=configurations[2],
    )
    assert independent_q2.transformed_assembly_hash == result.configuration_results[2].transformed_assembly_hash
    independent_q2_transforms = {
        item.instance_id: item.transform
        for item in independent_q2.instance_world_transforms
    }
    assert _transform_map(result.configuration_results[2])["link-2"] == independent_q2_transforms["link-2"]
    assert assembly_hash(assembly) == source_assembly_hash

    expected_pairs = (("link-1", "base"), ("link-2", "base"))
    for configuration, configuration_result in zip(
        configurations, result.configuration_results, strict=True
    ):
        assert configuration_result.configuration_hash == joint_configuration_hash(configuration)
        assert configuration_result.transformed_assembly_hash.startswith("sha256:")
        assert tuple(
            (pair.moving_instance_id, pair.stationary_instance_id)
            for pair in configuration_result.pair_results
        ) == expected_pairs
        assert configuration_result.classification is CollisionClassification.POSITIVE_CLEARANCE
        for pair in configuration_result.pair_results:
            assert math.isfinite(pair.interference_volume_mm3)
            assert math.isfinite(pair.exact_distance_mm)
            assert pair.interference_volume_mm3 >= 0.0
            assert pair.exact_distance_mm >= 0.0
            assert pair.classification is CollisionClassification.POSITIVE_CLEARANCE
        print(
            "M10_3_CONFIGURATION="
            + json.dumps(
                {
                    "index": configuration_result.configuration_index,
                    "positions": configuration.positions,
                    "configuration_hash": configuration_result.configuration_hash,
                    "transformed_assembly_hash": configuration_result.transformed_assembly_hash,
                    "transforms": {
                        instance_id: _transform_tuple(transform)
                        for instance_id, transform in _transform_map(configuration_result).items()
                    },
                    "pairs": [pair.model_dump(mode="json") for pair in configuration_result.pair_results],
                },
                sort_keys=True,
            )
        )

    evidence = app.get_multi_joint_collision_sweep_evidence(result.result_hash)
    assert evidence is not None
    provenance = evidence.analysis_execution_provenance
    assert provenance is not None
    assert provenance.provider_name == "freecad-transient-exact"
    assert provenance.provider_version == "mechcad-freecad-transient@1.0"
    assert provenance.backend_provenance is not None
    assert provenance.backend_provenance.backend_name == "freecad"
    assert provenance.backend_provenance.library_name == "FreeCAD"
    assert provenance.backend_provenance.library_version
    assert provenance.backend_provenance.library_version != "unknown"
    assert provenance.execution_mode == "freecadcmd-subprocess"
    assert provenance.model_hash == result.model_hash
    assert provenance.request_hash == result.request_hash
    assert provenance.result_hash == result.result_hash
    print("M10_3_PROVENANCE=" + json.dumps(provenance.model_dump(mode="json"), sort_keys=True))

    assert assembly_hash(assembly) == source_assembly_hash
    assert source_instances == tuple(
        (item.instance_id, item.placement.model_dump(mode="json"))
        for item in assembly.instances
    )
    state_after = app.load_state()
    assert state_after.revision == state_before.revision == source_revision
    assert state_after.state_hash == state_before.state_hash == source_state_hash
    assert artifact_path.read_bytes() == artifact_bytes_before
    assert _public_artifact_metadata(app.state_manager.workspace) == artifacts_before
