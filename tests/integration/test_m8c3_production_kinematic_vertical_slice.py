from __future__ import annotations

import inspect
import json

import pytest

from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
from mechcad_harness.application import ProductionApplication
from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_compilation import MountingPlateDesignSpec
from mechcad_harness.imported_component import ImportedCadComponent
from mechcad_harness.kinematic_sweep import (
    CollisionClassification,
    RevoluteAxis,
    SweepAggregateClassification,
)
from mechcad_harness.models import Component, DesignState
from mechcad_harness.state import StateManager
from mechcad_harness.transient_assembly_analysis import TransientAssemblyAnalysisRequest
from mechcad_harness.transient_freecad_measurement import FreeCADTransientAssemblyMeasurementProvider


def _make_application(tmp_path, kinematic_measure=None):
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /components/*\n    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    dependencies.write_text(
        json.dumps({"rules": [{"when": ["/components/*"], "invalidates": ["analysis.kinematic_sweep"]}], "edges": []}),
        encoding="utf-8",
    )
    state = DesignState(
        id="DES-m8c3",
        revision=1,
        components=[Component(id="PRT-fixture", name="Fixture")],
    )
    StateManager(workspace).create_project("PRJ-m8c3", state)

    identity = AgentIdentity(
        agent_name="mechcad-transmission",
        agent_version="1.0",
        role="transmission_engineer",
        protocol_version="1.0",
    )
    adapter = FakeAgentAdapter(identity, scripted_responses=())
    return ProductionApplication.create(
        workspace,
        "PRJ-m8c3",
        adapter,
        ownership_path=ownership,
        dependency_path=dependencies,
        kinematic_measure=kinematic_measure,
    )


def _make_generic_fixture_plate(application):
    spec = MountingPlateDesignSpec(
        part_id="fixture_plate",
        plate_length_mm=120.0,
        plate_width_mm=100.0,
        plate_thickness_mm=10.0,
        mounting_holes=(
            MountingPlateDesignSpec.HoleSpec(hole_id="h1", x_mm=30.0, y_mm=25.0, diameter_mm=8.0),
            MountingPlateDesignSpec.HoleSpec(hole_id="h2", x_mm=90.0, y_mm=25.0, diameter_mm=8.0),
        ),
    )
    compiled = application.compile_design_spec(
        source_revision=1,
        source_state_hash=application.load_state().state_hash,
        spec=spec,
    )
    return compiled.program


def _make_imported_component():
    return ImportedCadComponent(
        component_id="imported_body",
        artifact_id="ART-m8c3-body",
        artifact_hash="sha256:" + "a" * 64,
        format="step",
        source_revision=1,
        source_state_hash="sha256:" + "b" * 64,
    )


def _make_fixture_assembly(plate_program, imported):
    return CadAssemblyProgram(
        assembly_id="m8c3-generic-fixture",
        parts=(plate_program,),
        imported_components=(imported,),
        instances=(
            CadComponentInstance(instance_id="inst_plate", part_id="fixture_plate", placement=CadRigidTransform(x_mm=-20, y_mm=0, z_mm=0)),
            CadComponentInstance(instance_id="inst_body", part_id="imported_body", placement=CadRigidTransform(x_mm=20, y_mm=0, z_mm=0)),
        ),
    )


def _deterministic_exact_measure(request: TransientAssemblyAnalysisRequest, program: CadAssemblyProgram):
    # Synthetic exact-geometry substitute injected ONLY at the external CAD
    # execution composition boundary (never supplied by an ordinary workflow
    # caller). Distinct per-angle outcomes exercise the reused classification.
    outcomes = {
        0.0: (0.0, 5.0),
        45.0: (0.0, 0.0),
        90.0: (1.0, 0.0),
    }
    volume, distance = outcomes.get(float(round(request.sample_angle_deg, 6)), (0.0, 1.0))
    return tuple(
        (moving, stationary, volume, distance)
        for moving, stationary in request.pairs
    )


class TestM8C3ProductionKinematicConnectivity:
    def test_production_entry_runs_real_sweep_through_internal_graph(self, tmp_path):
        # Deterministic provider injected at composition (external CAD boundary).
        application = _make_application(tmp_path, kinematic_measure=_deterministic_exact_measure)
        source = application.load_state()
        plate = _make_generic_fixture_plate(application)
        imported = _make_imported_component()
        assembly = _make_fixture_assembly(plate, imported)

        axis = RevoluteAxis(origin_x_mm=0, origin_y_mm=0, origin_z_mm=0, direction_x=0, direction_y=1, direction_z=0, frame_id="fixture_frame")

        # Ordinary call: no measurement callback argument.
        result = application.analyze_assembly_kinematics(
            source_revision=source.revision,
            source_state_hash=source.state_hash,
            assembly=assembly,
            axis=axis,
            moving_instance_ids=("inst_body",),
            stationary_instance_ids=("inst_plate",),
            sample_angles_deg=(0.0, 45.0, 90.0),
        )

        from mechcad_harness.kinematic_sweep import CadKinematicSweepResult
        assert isinstance(result, CadKinematicSweepResult)
        assert [sample.angle_deg for sample in result.samples] == [0.0, 45.0, 90.0]
        assert result.source_assembly_hash == assembly_hash(assembly)
        for sample in result.samples:
            assert [(p.moving_instance_id, p.stationary_instance_id) for p in sample.pair_results] == [("inst_body", "inst_plate")]
        assert result.samples[0].classification is CollisionClassification.POSITIVE_CLEARANCE
        assert result.samples[1].classification is CollisionClassification.TOUCHING
        assert result.samples[2].classification is CollisionClassification.INTERFERENCE
        assert result.aggregate_classification is SweepAggregateClassification.COLLISION_PRESENT
        # Deterministic connectivity proof: no public per-sample ArtifactStore artifacts.
        assert result.continuous_sweep_verified is False

    def test_production_result_is_deterministic(self, tmp_path):
        application = _make_application(tmp_path, kinematic_measure=_deterministic_exact_measure)
        source = application.load_state()
        plate = _make_generic_fixture_plate(application)
        assembly = _make_fixture_assembly(plate, _make_imported_component())
        axis = RevoluteAxis(origin_x_mm=0, origin_y_mm=0, origin_z_mm=0, direction_x=0, direction_y=1, direction_z=0, frame_id="fixture_frame")

        def run():
            return application.analyze_assembly_kinematics(
                source_revision=source.revision,
                source_state_hash=source.state_hash,
                assembly=assembly,
                axis=axis,
                moving_instance_ids=("inst_body",),
                stationary_instance_ids=("inst_plate",),
                sample_angles_deg=(0.0, 45.0, 90.0),
            )

        assert run().result_hash == run().result_hash

    def test_production_fails_closed_on_stale_source(self, tmp_path):
        application = _make_application(tmp_path, kinematic_measure=_deterministic_exact_measure)
        source = application.load_state()
        plate = _make_generic_fixture_plate(application)
        assembly = _make_fixture_assembly(plate, _make_imported_component())
        axis = RevoluteAxis(origin_x_mm=0, origin_y_mm=0, origin_z_mm=0, direction_x=0, direction_y=1, direction_z=0, frame_id="fixture_frame")

        from mechcad_harness.cad_service import CadSourceRevisionNotFoundError
        with pytest.raises(CadSourceRevisionNotFoundError):
            application.analyze_assembly_kinematics(
                source_revision=99,
                source_state_hash=source.state_hash,
                assembly=assembly,
                axis=axis,
                moving_instance_ids=("inst_body",),
                stationary_instance_ids=("inst_plate",),
                sample_angles_deg=(0.0,),
            )

    def test_production_fails_closed_on_overlapping_partition(self, tmp_path):
        application = _make_application(tmp_path, kinematic_measure=_deterministic_exact_measure)
        source = application.load_state()
        plate = _make_generic_fixture_plate(application)
        assembly = _make_fixture_assembly(plate, _make_imported_component())
        axis = RevoluteAxis(origin_x_mm=0, origin_y_mm=0, origin_z_mm=0, direction_x=0, direction_y=1, direction_z=0, frame_id="fixture_frame")

        with pytest.raises(ValueError):
            application.analyze_assembly_kinematics(
                source_revision=source.revision,
                source_state_hash=source.state_hash,
                assembly=assembly,
                axis=axis,
                moving_instance_ids=("inst_body", "inst_plate"),
                stationary_instance_ids=("inst_plate",),
                sample_angles_deg=(0.0,),
            )

    def test_production_fails_closed_on_unknown_instance(self, tmp_path):
        application = _make_application(tmp_path, kinematic_measure=_deterministic_exact_measure)
        source = application.load_state()
        plate = _make_generic_fixture_plate(application)
        assembly = _make_fixture_assembly(plate, _make_imported_component())
        axis = RevoluteAxis(origin_x_mm=0, origin_y_mm=0, origin_z_mm=0, direction_x=0, direction_y=1, direction_z=0, frame_id="fixture_frame")

        with pytest.raises(ValueError):
            application.analyze_assembly_kinematics(
                source_revision=source.revision,
                source_state_hash=source.state_hash,
                assembly=assembly,
                axis=axis,
                moving_instance_ids=("inst_ghost",),
                stationary_instance_ids=("inst_plate",),
                sample_angles_deg=(0.0,),
            )

    def test_production_fails_closed_on_invalid_axis(self, tmp_path):
        application = _make_application(tmp_path, kinematic_measure=_deterministic_exact_measure)
        source = application.load_state()
        plate = _make_generic_fixture_plate(application)
        assembly = _make_fixture_assembly(plate, _make_imported_component())

        with pytest.raises(ValueError):
            application.analyze_assembly_kinematics(
                source_revision=source.revision,
                source_state_hash=source.state_hash,
                assembly=assembly,
                axis=RevoluteAxis(origin_x_mm=0, origin_y_mm=0, origin_z_mm=0, direction_x=0, direction_y=0, direction_z=0, frame_id="fixture_frame"),
                moving_instance_ids=("inst_body",),
                stationary_instance_ids=("inst_plate",),
                sample_angles_deg=(0.0,),
            )

    def test_production_does_not_mutate_design_state(self, tmp_path):
        application = _make_application(tmp_path, kinematic_measure=_deterministic_exact_measure)
        before = application.load_state().state_hash
        source = application.load_state()
        plate = _make_generic_fixture_plate(application)
        assembly = _make_fixture_assembly(plate, _make_imported_component())
        axis = RevoluteAxis(origin_x_mm=0, origin_y_mm=0, origin_z_mm=0, direction_x=0, direction_y=1, direction_z=0, frame_id="fixture_frame")

        application.analyze_assembly_kinematics(
            source_revision=source.revision,
            source_state_hash=source.state_hash,
            assembly=assembly,
            axis=axis,
            moving_instance_ids=("inst_body",),
            stationary_instance_ids=("inst_plate",),
            sample_angles_deg=(0.0, 45.0, 90.0),
        )
        assert application.load_state().state_hash == before


class TestM8C3MeasurementTrustBoundary:
    def test_public_method_has_no_caller_controlled_measurement_argument(self):
        params = inspect.signature(ProductionApplication.analyze_assembly_kinematics).parameters
        assert "exact_measure" not in params
        assert "kinematic_measure" not in params

    def test_default_production_provider_is_trusted_freecad_provider(self, tmp_path):
        application = _make_application(tmp_path)
        assert isinstance(application._kinematic_measurement_provider, FreeCADTransientAssemblyMeasurementProvider)
        assert application.kinematic_measure.__func__ is FreeCADTransientAssemblyMeasurementProvider.exact_measure

    def test_injected_deterministic_provider_is_composition_only(self, tmp_path):
        application = _make_application(tmp_path, kinematic_measure=_deterministic_exact_measure)
        assert application._kinematic_measurement_provider is None
        assert application.kinematic_measure is _deterministic_exact_measure


class TestM8C3LiveFreeCADKinematicSweep:
    @pytest.mark.skipif(
        __import__("mechcad_harness.backends.freecad", fromlist=["discover_freecad"]).discover_freecad().available is False,
        reason="FreeCAD not available",
    )
    def test_live_production_kinematic_sweep_with_generated_assembly(self, tmp_path):
        # Uses the trusted production default provider (runtime-gated FreeCAD).
        application = _make_application(tmp_path)
        source = application.load_state()
        plate = _make_generic_fixture_plate(application)
        assembly = CadAssemblyProgram(
            assembly_id="m8c3-live",
            parts=(plate,),
            imported_components=(),
            instances=(
                CadComponentInstance(instance_id="inst_plate", part_id="fixture_plate", placement=CadRigidTransform(x_mm=-20)),
                CadComponentInstance(instance_id="inst_body", part_id="fixture_plate", placement=CadRigidTransform(x_mm=20)),
            ),
        )
        axis = RevoluteAxis(origin_x_mm=0, origin_y_mm=0, origin_z_mm=0, direction_x=0, direction_y=1, direction_z=0, frame_id="fixture_frame")
        result = application.analyze_assembly_kinematics(
            source_revision=source.revision,
            source_state_hash=source.state_hash,
            assembly=assembly,
            axis=axis,
            moving_instance_ids=("inst_body",),
            stationary_instance_ids=("inst_plate",),
            sample_angles_deg=(0.0, 90.0, 180.0),
        )
        assert [sample.angle_deg for sample in result.samples] == [0.0, 90.0, 180.0]
        assert result.continuous_sweep_verified is False
        assert result.source_assembly_hash == assembly_hash(assembly)
