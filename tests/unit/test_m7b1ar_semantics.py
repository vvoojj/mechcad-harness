import pytest
from pydantic import ValidationError

from mechcad_harness.azimuth_mount_plate import (
    AzimuthDriveMountInterface,
    AzimuthMotorMountPlateSpec,
    MountHoleSpec,
    MountPointSpec,
    RequiredMatingHole,
    ThreadedMountHole,
    ThroughMountHole,
    XYPoint,
    compile_azimuth_motor_mount_plate,
    azimuth_mount_plate_design_readiness,
    mount_plate_spec_hash,
)


def base_spec(interface):
    return AzimuthMotorMountPlateSpec(
        part_id="plate",
        plate_length_mm=120,
        plate_width_mm=100,
        plate_thickness_mm=10,
        motor_center_x_mm=60,
        motor_center_y_mm=50,
        drive_mount_interface=interface,
        provenance="M7B1_TEST_FIXTURE_ONLY",
    )


def test_threaded_hardware_does_not_become_plate_hole_without_requirement():
    interface = AzimuthDriveMountInterface(component_id="drive", mount_points=(MountPointSpec(hole_id="a", x_mm=-20, y_mm=-20, physical_interface=ThreadedMountHole(nominal_thread_diameter_mm=8)),), central_required_mating_opening_diameter_mm=42, frame_reference_id="datum-x")
    with pytest.raises(ValueError, match="mating"):
        compile_azimuth_motor_mount_plate(base_spec(interface))


def test_physical_keepout_plus_radial_clearance_derives_plate_opening():
    interface = AzimuthDriveMountInterface(component_id="drive", mount_points=(MountPointSpec(hole_id="a", x_mm=-20, y_mm=-20, physical_interface=ThroughMountHole(physical_hole_diameter_mm=8), external_mating_requirement=RequiredMatingHole(diameter_mm=8)),), central_keepout_diameter_mm=40, manufacturer_required_central_radial_clearance_mm=1, frame_reference_id="datum-x")
    program = compile_azimuth_motor_mount_plate(base_spec(interface))
    assert program.operations[1].diameter_mm == 42


def test_explicit_mating_requirement_drives_plate_hole_without_invented_clearance():
    interface = AzimuthDriveMountInterface(component_id="drive", mount_points=(MountPointSpec(hole_id="a", x_mm=-20, y_mm=-20, external_mating_requirement=RequiredMatingHole(diameter_mm=10)),), central_required_mating_opening_diameter_mm=42, frame_reference_id="datum-x")
    program = compile_azimuth_motor_mount_plate(base_spec(interface))
    assert program.operations[1].diameter_mm == 42


def test_coordinate_frame_is_explicit_and_right_handed():
    interface = AzimuthDriveMountInterface(component_id="drive", mount_points=(MountPointSpec(hole_id="a", x_mm=-20, y_mm=-20, physical_interface=ThroughMountHole(physical_hole_diameter_mm=8), external_mating_requirement=RequiredMatingHole(diameter_mm=8)),), central_keepout_diameter_mm=40, manufacturer_required_central_radial_clearance_mm=1, frame_reference_id="datum-x")
    assert interface.coordinate_convention == "interface-center; mounting plane XY; +Z housing-to-mating-plate; +X source-defined reference; +Y right-handed"
    assert interface.in_plane_alignment == "aligned-with-plate-axes"
    assert interface.frame_reference_id == "datum-x"


def test_keepout_without_external_or_design_clearance_fails_closed():
    with pytest.raises(ValidationError, match="central"):
        AzimuthDriveMountInterface(component_id="drive", mount_points=(MountPointSpec(hole_id="a", x_mm=0, y_mm=0),), central_keepout_diameter_mm=40, frame_reference_id="datum-x")


def test_explicit_external_opening_takes_precedence_over_manufacturer_clearance():
    interface = AzimuthDriveMountInterface(component_id="drive", mount_points=(MountPointSpec(hole_id="a", x_mm=0, y_mm=0),), central_keepout_diameter_mm=40, central_required_mating_opening_diameter_mm=42, manufacturer_required_central_radial_clearance_mm=2, frame_reference_id="datum-x")
    assert interface.external_minimum_central_opening_diameter_mm() == 42


def test_mount_point_ids_are_the_correlation_key():
    point = MountPointSpec(hole_id="motor-1", x_mm=-20, y_mm=-20, physical_interface=ThreadedMountHole(nominal_thread_diameter_mm=6), external_mating_requirement=RequiredMatingHole(diameter_mm=6.6))
    interface = AzimuthDriveMountInterface(component_id="drive", mount_points=(point,), central_required_mating_opening_diameter_mm=42, frame_reference_id="datum-x")
    program = compile_azimuth_motor_mount_plate(base_spec(interface))
    assert program.operations[2].diameter_mm == 6.6
    assert program.operations[2].diameter_mm != 6


def test_duplicate_mount_point_ids_are_rejected():
    with pytest.raises(ValidationError, match="unique"):
        AzimuthDriveMountInterface(component_id="drive", mount_points=(MountPointSpec(hole_id="a", x_mm=0, y_mm=0), MountPointSpec(hole_id="a", x_mm=1, y_mm=1)), central_required_mating_opening_diameter_mm=42, frame_reference_id="datum-x")


def test_through_physical_diameter_does_not_become_plate_diameter():
    interface = AzimuthDriveMountInterface(component_id="drive", mount_points=(MountPointSpec(hole_id="through-1", x_mm=-20, y_mm=-20, physical_interface=ThroughMountHole(physical_hole_diameter_mm=8), external_mating_requirement=RequiredMatingHole(diameter_mm=9)),), central_required_mating_opening_diameter_mm=42, frame_reference_id="datum-x")
    assert compile_azimuth_motor_mount_plate(base_spec(interface)).operations[2].diameter_mm == 9


def test_requirement_only_point_has_no_physical_fact():
    point = MountPointSpec(hole_id="req-1", x_mm=-20, y_mm=-20, external_mating_requirement=RequiredMatingHole(diameter_mm=9))
    assert point.physical_interface is None


def test_frame_reference_identity_changes_interface_hash():
    left = AzimuthDriveMountInterface(component_id="drive", mount_points=(MountPointSpec(hole_id="a", x_mm=-20, y_mm=-20, external_mating_requirement=RequiredMatingHole(diameter_mm=9)),), central_required_mating_opening_diameter_mm=42, frame_reference_id="datum-x")
    right = left.model_copy(update={"frame_reference_id": "datum-y"})
    assert mount_plate_spec_hash(base_spec(left)) != mount_plate_spec_hash(base_spec(right))


def test_hardware_authority_can_be_complete_while_plate_design_is_not_ready():
    interface = AzimuthDriveMountInterface(component_id="drive", mount_points=(MountPointSpec(hole_id="a", x_mm=-20, y_mm=-20, external_mating_requirement=RequiredMatingHole(diameter_mm=9)),), central_required_mating_opening_diameter_mm=42, frame_reference_id="datum-x")
    assert AzimuthDriveMountInterface.model_fields
    assert not azimuth_mount_plate_design_readiness(interface)
