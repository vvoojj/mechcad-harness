import pytest

from mechcad_harness.backends.freecad import discover_freecad
from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, CadRigidTransform, assembly_hash
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.transient_assembly_analysis import TransientAssemblyAnalysisRequest, TransientAssemblyAnalysisService
from mechcad_harness.transient_freecad_measurement import FreeCADTransientAssemblyMeasurementProvider


pytestmark = pytest.mark.skipif(not discover_freecad().available, reason="FreeCADCmd is unavailable")


def _assembly(stationary_x_mm: float) -> CadAssemblyProgram:
    return CadAssemblyProgram(
        assembly_id=f"transient-live-{stationary_x_mm:g}",
        parts=(
            CadPartProgram(part_id="moving", operations=(BasePlateOperation(operation_id="moving", length_mm=10, width_mm=10, thickness_mm=10),)),
            CadPartProgram(part_id="stationary", operations=(BasePlateOperation(operation_id="stationary", length_mm=10, width_mm=10, thickness_mm=10),)),
        ),
        instances=(
            CadComponentInstance(instance_id="moving", part_id="moving"),
            CadComponentInstance(instance_id="stationary", part_id="stationary", placement=CadRigidTransform(x_mm=stationary_x_mm)),
        ),
    )


@pytest.mark.parametrize(
    ("stationary_x_mm", "expected_volume", "expect_positive_distance"),
    ((15.0, 0.0, True), (10.0, 0.0, False), (5.0, 500.0, False)),
    ids=("positive-clearance", "touching", "interference"),
)
def test_transient_provider_measures_exact_box_relationships(stationary_x_mm, expected_volume, expect_positive_distance):
    program = _assembly(stationary_x_mm)
    identity = assembly_hash(program)
    request = TransientAssemblyAnalysisRequest(
        source_assembly_hash=identity,
        transformed_assembly_hash=identity,
        sweep_request_hash="sha256:live",
        sample_angle_deg=0,
        pairs=(("moving", "stationary"),),
    )
    service = TransientAssemblyAnalysisService(FreeCADTransientAssemblyMeasurementProvider().exact_measure)

    result = service.analyze(request, program)

    assert result.measurements[0][:2] == ("moving", "stationary")
    _, _, common_volume_mm3, exact_distance_mm = result.measurements[0]
    assert common_volume_mm3 == pytest.approx(expected_volume, abs=1e-7)
    if expect_positive_distance:
        assert exact_distance_mm > 0
    else:
        assert exact_distance_mm == pytest.approx(0.0, abs=1e-7)
