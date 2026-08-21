import pytest

from mechcad_harness.backends.freecad import discover_freecad
from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, CadRigidTransform, assembly_hash
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.kinematic_sweep import (
    CadKinematicSweepService,
    CollisionClassification,
    RevoluteAxis,
    SweepAggregateClassification,
    transformed_assembly_program,
)
from mechcad_harness.transient_assembly_analysis import TransientAssemblyAnalysisService
from mechcad_harness.transient_freecad_measurement import FreeCADTransientAssemblyMeasurementProvider
from mechcad_harness.yagi_el_reference import create_yagi_el_reference
from mechcad_harness.yagi_el_sweep import create_yagi_el_sweep_reference, create_yagi_el_sweep_request


pytestmark = pytest.mark.skipif(not discover_freecad().available, reason="FreeCADCmd is unavailable")


def _layout():
    from mechcad_harness.yagi_collision_layout import synthesize_yagi_collision_layout
    from tests.unit.test_m7b2c_collision_layout import _carrier, _requirements

    return synthesize_yagi_collision_layout(
        _requirements(),
        _carrier(),
        ("ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200"),
    ).spec


def test_live_yagi_el_sweep_uses_transient_freecad_measurement_without_canonical_side_effects(monkeypatch):
    import mechcad_harness.artifacts.storage

    def artifact_store_forbidden(*args, **kwargs):
        raise AssertionError("EL sweep must not create artifact store records")

    monkeypatch.setattr(mechcad_harness.artifacts.storage, "ArtifactStore", artifact_store_forbidden)
    layout = _layout()
    axis = RevoluteAxis(
        origin_x_mm=0,
        origin_y_mm=0,
        origin_z_mm=0,
        direction_x=0,
        direction_y=1,
        direction_z=0,
        frame_id="yagi_el_reference_fixture",
    )
    assembly = CadAssemblyProgram(
        assembly_id=layout.layout_id,
        parts=(
            CadPartProgram(part_id="moving", operations=(BasePlateOperation(operation_id="moving", length_mm=10, width_mm=10, thickness_mm=10),)),
            CadPartProgram(part_id="stationary", operations=(BasePlateOperation(operation_id="stationary", length_mm=10, width_mm=10, thickness_mm=10),)),
        ),
        instances=(
            CadComponentInstance(instance_id="moving", part_id="moving", placement=CadRigidTransform(x_mm=10, z_mm=-5)),
            CadComponentInstance(instance_id="stationary", part_id="stationary", placement=CadRigidTransform(x_mm=-15, z_mm=-10)),
        ),
    )
    adapter_reference = create_yagi_el_sweep_reference(
        layout,
        create_yagi_el_reference(layout),
        source_assembly_id=assembly.assembly_id,
        source_assembly_hash=assembly_hash(assembly),
        axis=axis,
        sample_angles_deg=(0, 90, 180),
        moving_instance_ids=("moving",),
        stationary_instance_ids=("stationary",),
    )
    request = create_yagi_el_sweep_request(
        layout,
        create_yagi_el_reference(layout),
        source_assembly_id=adapter_reference.source_assembly_id,
        source_assembly_hash=adapter_reference.source_assembly_hash,
        axis=adapter_reference.axis,
        sample_angles_deg=adapter_reference.sample_angles_deg,
        moving_instance_ids=adapter_reference.moving_instance_ids,
        stationary_instance_ids=adapter_reference.stationary_instance_ids,
    )
    service = CadKinematicSweepService(
        transient_analysis_service=TransientAssemblyAnalysisService(FreeCADTransientAssemblyMeasurementProvider().exact_measure)
    )

    result = service.execute(request, assembly)

    assert [sample.angle_deg for sample in result.samples] == [0, 90, 180]
    assert [sample.transformed_assembly_hash for sample in result.samples] == [
        assembly_hash(transformed_assembly_program(assembly, axis, angle, ("moving",), ("stationary",)))
        for angle in request.sample_angles_deg
    ]
    assert [
        (pair.moving_instance_id, pair.stationary_instance_id)
        for sample in result.samples
        for pair in sample.pair_results
    ] == [("moving", "stationary")] * 3
    assert [sample.classification for sample in result.samples] == [
        CollisionClassification.POSITIVE_CLEARANCE,
        CollisionClassification.TOUCHING,
        CollisionClassification.INTERFERENCE,
    ]
    measurements = [sample.pair_results[0] for sample in result.samples]
    assert measurements[0].interference_volume_mm3 == pytest.approx(0.0, abs=1e-7)
    assert measurements[0].exact_distance_mm > 0
    assert measurements[1].interference_volume_mm3 == pytest.approx(0.0, abs=1e-7)
    assert measurements[1].exact_distance_mm == pytest.approx(0.0, abs=1e-7)
    assert measurements[2].interference_volume_mm3 > 0
    assert measurements[2].exact_distance_mm == pytest.approx(0.0, abs=1e-7)
    assert result.aggregate_classification is SweepAggregateClassification.COLLISION_PRESENT
    assert result.continuous_sweep_verified is False
    assert result.result_hash == CadKinematicSweepService(
        transient_analysis_service=TransientAssemblyAnalysisService(FreeCADTransientAssemblyMeasurementProvider().exact_measure)
    ).execute(request, assembly).result_hash
