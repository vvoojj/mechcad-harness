import importlib.util
import math

import pytest

from mechcad_harness.azimuth_mount_plate import AzimuthMotorMountPlateSpec, XYPoint, compile_azimuth_motor_mount_plate, AzimuthDriveMountInterface, MountPointSpec, RequiredMatingHole, AzimuthMotorMountPlateDesignRequirements, PlateThicknessPolicy, M7B1B_TEST_FIXTURE_ONLY, synthesize_azimuth_motor_mount_plate, SynthesisStatus
from mechcad_harness.cad_service import CadGenerationService
from mechcad_harness.backends.freecad import FreeCADBackend
from mechcad_harness.cad_program import cad_program_hash
from mechcad_harness.models import DesignState
from mechcad_harness.state import StateManager


FREECAD_AVAILABLE = importlib.util.find_spec("mechcad_harness") is not None


def fixture_spec():
    return AzimuthMotorMountPlateSpec(
        part_id="azimuth_motor_mount_plate_test_fixture",
        plate_length_mm=120,
        plate_width_mm=100,
        plate_thickness_mm=10,
        motor_center_x_mm=60,
        motor_center_y_mm=50,
        motor_mount_hole_diameter_mm=8,
        motor_mount_hole_positions=(XYPoint(x_mm=40, y_mm=30), XYPoint(x_mm=80, y_mm=30), XYPoint(x_mm=80, y_mm=70), XYPoint(x_mm=40, y_mm=70)),
        central_clearance_hole_diameter_mm=30,
        frame_mount_hole_diameter_mm=6,
        frame_mount_hole_positions=(XYPoint(x_mm=10, y_mm=10), XYPoint(x_mm=110, y_mm=10), XYPoint(x_mm=110, y_mm=90), XYPoint(x_mm=10, y_mm=90)),
        provenance="M7B1_TEST_FIXTURE_ONLY",
    )


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD runtime unavailable")
def test_synthetic_domain_plate_runs_through_production_cad_path(tmp_path, monkeypatch):
    monkeypatch.setenv("MECHCAD_FREECADCMD", r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe")
    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-M7B1-TEST", DesignState(id="DES-M7B1-TEST", revision=1))
    program = compile_azimuth_motor_mount_plate(fixture_spec())
    result = CadGenerationService(manager, FreeCADBackend()).generate_program("PRJ-M7B1-TEST", "RUN-M7B1-TEST", 1, snapshot.state_hash, program, tmp_path)
    expected_volume = 120 * 100 * 10 - math.pi * (30 / 2) ** 2 * 10 - 4 * math.pi * (8 / 2) ** 2 * 10 - 4 * math.pi * (6 / 2) ** 2 * 10
    assert result.fcstd_verification.x_length_mm == pytest.approx(120, abs=1e-6)
    assert result.fcstd_verification.y_length_mm == pytest.approx(100, abs=1e-6)
    assert result.fcstd_verification.z_length_mm == pytest.approx(10, abs=1e-6)
    assert result.fcstd_verification.solid_count == 1
    assert result.fcstd_verification.volume_mm3 == pytest.approx(expected_volume, rel=1e-6)
    assert result.step_verification.volume_mm3 == pytest.approx(expected_volume, rel=1e-6)
    assert result.fcstd.input_hash == cad_program_hash(program)


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD runtime unavailable")
def test_synthesized_plate_runs_through_production_cad_path(tmp_path, monkeypatch):
    monkeypatch.setenv("MECHCAD_FREECADCMD", r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe")
    interface = AzimuthDriveMountInterface(component_id="drive-test", frame_reference_id="datum-x", mount_points=(MountPointSpec(hole_id="a", x_mm=-30, y_mm=-25, external_mating_requirement=RequiredMatingHole(diameter_mm=8)), MountPointSpec(hole_id="b", x_mm=30, y_mm=-20, external_mating_requirement=RequiredMatingHole(diameter_mm=8)), MountPointSpec(hole_id="c", x_mm=28, y_mm=25, external_mating_requirement=RequiredMatingHole(diameter_mm=8)), MountPointSpec(hole_id="d", x_mm=-25, y_mm=24, external_mating_requirement=RequiredMatingHole(diameter_mm=8))), central_keepout_diameter_mm=30, central_required_mating_opening_diameter_mm=34)
    requirements = AzimuthMotorMountPlateDesignRequirements(minimum_edge_margin_mm=10, minimum_hole_ligament_mm=5, plate_thickness_policy=PlateThicknessPolicy(allowed_thicknesses_mm=(6, 8, 10), minimum_thickness_mm=7), central_radial_clearance_mm=2, mounting_hole_radial_clearance_mm=1, provenance=M7B1B_TEST_FIXTURE_ONLY)
    synthesis = synthesize_azimuth_motor_mount_plate(interface, requirements)
    assert synthesis.status is SynthesisStatus.SUCCESS
    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-M7B1B-TEST", DesignState(id="DES-M7B1B-TEST", revision=1))
    result = CadGenerationService(manager, FreeCADBackend()).generate_program("PRJ-M7B1B-TEST", "RUN-M7B1B-TEST", 1, snapshot.state_hash, compile_azimuth_motor_mount_plate(synthesis.spec), tmp_path)
    expected_volume = synthesis.spec.plate_length_mm * synthesis.spec.plate_width_mm * synthesis.spec.plate_thickness_mm - math.pi * (34 / 2) ** 2 * synthesis.spec.plate_thickness_mm - 4 * math.pi * (8 / 2) ** 2 * synthesis.spec.plate_thickness_mm
    assert result.fcstd_verification.x_length_mm == pytest.approx(synthesis.spec.plate_length_mm, abs=1e-6)
    assert result.fcstd_verification.y_length_mm == pytest.approx(synthesis.spec.plate_width_mm, abs=1e-6)
    assert result.fcstd_verification.z_length_mm == pytest.approx(8, abs=1e-6)
    assert result.fcstd_verification.solid_count == 1
    assert result.fcstd_verification.volume_mm3 == pytest.approx(expected_volume, rel=1e-6)
    assert result.step_verification.volume_mm3 == pytest.approx(expected_volume, rel=1e-6)
