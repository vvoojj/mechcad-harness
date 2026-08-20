import pytest

from mechcad_harness.backends.freecad import discover_freecad
from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, CadRigidTransform, assembly_hash
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.kinematic_sweep import (
    CadKinematicSweepRequest,
    CadKinematicSweepService,
    CollisionClassification,
    RevoluteAxis,
    SweepAggregateClassification,
    transformed_assembly_program,
)
from mechcad_harness.transient_assembly_analysis import TransientAssemblyAnalysisService
from mechcad_harness.transient_freecad_measurement import FreeCADTransientAssemblyMeasurementProvider


pytestmark = pytest.mark.skipif(not discover_freecad().available, reason="FreeCADCmd is unavailable")


def test_live_kinematic_sweep_uses_transient_exact_measurement_without_canonical_side_effects(monkeypatch):
    import mechcad_harness.artifacts.storage

    def artifact_store_forbidden(*args, **kwargs):
        raise AssertionError("kinematic sweep must not create artifact store records")

    monkeypatch.setattr(mechcad_harness.artifacts.storage, "ArtifactStore", artifact_store_forbidden)
    assembly = CadAssemblyProgram(
        assembly_id="live-sweep",
        parts=(
            CadPartProgram(part_id="moving", operations=(BasePlateOperation(operation_id="moving", length_mm=10, width_mm=10, thickness_mm=10),)),
            CadPartProgram(part_id="stationary", operations=(BasePlateOperation(operation_id="stationary", length_mm=10, width_mm=10, thickness_mm=10),)),
        ),
        instances=(
            CadComponentInstance(instance_id="moving", part_id="moving", placement=CadRigidTransform(x_mm=10)),
            CadComponentInstance(instance_id="stationary", part_id="stationary", placement=CadRigidTransform(x_mm=-15)),
        ),
    )
    axis = RevoluteAxis(origin_x_mm=0, origin_y_mm=0, origin_z_mm=0, direction_x=0, direction_y=1, direction_z=0, frame_id="fixture")
    request = CadKinematicSweepRequest(
        source_assembly_id=assembly.assembly_id,
        source_assembly_hash=assembly_hash(assembly),
        axis=axis,
        sample_angles_deg=(0, 90, 180),
        moving_instance_ids=("moving",),
        stationary_instance_ids=("stationary",),
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
    # These are exact transformed-solid measurements, not distances between box centers.
    assert [(sample.pair_results[0].interference_volume_mm3, sample.pair_results[0].exact_distance_mm) for sample in result.samples] == [
        (0.0, 15.0),
        (0.0, pytest.approx(11.18033988749895, abs=1e-6)),
        (0.0, pytest.approx(0.0, abs=1e-7)),
    ]
    assert result.aggregate_classification is SweepAggregateClassification.TOUCHING_PRESENT
    assert result.samples[2].classification is CollisionClassification.TOUCHING
    assert result.continuous_sweep_verified is False
