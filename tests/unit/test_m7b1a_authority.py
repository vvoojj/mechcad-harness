import math

import pytest
from pydantic import ValidationError

from mechcad_harness.azimuth_mount_plate import (
    AzimuthDriveMountInterface,
    AzimuthDriveMountInterfaceValue,
    AzimuthMotorMountPlateSpec,
    MountPointSpec,
    RequiredMatingHole,
    XYPoint,
    compile_azimuth_motor_mount_plate,
)
from mechcad_harness.agents.constraint_requests import ConstraintRequestMaterializer, SupportedConstraintKey


def interface():
    return AzimuthDriveMountInterfaceValue(
        component_id="drive-test",
        mount_points=(MountPointSpec(hole_id="a", x_mm=-20, y_mm=-20, external_mating_requirement=RequiredMatingHole(diameter_mm=8)), MountPointSpec(hole_id="b", x_mm=20, y_mm=-20, external_mating_requirement=RequiredMatingHole(diameter_mm=8))),
        central_required_mating_opening_diameter_mm=30,
        frame_reference_id="datum-x",
    )


def test_hardware_interface_is_local_and_per_hole_typed():
    value = interface()
    assert value.coordinate_convention == "interface-center; mounting plane XY; +Z housing-to-mating-plate; +X source-defined reference; +Y right-handed"
    assert value.mount_points[0].external_mating_requirement.diameter_mm == 8
    with pytest.raises(ValidationError):
        MountPointSpec(hole_id="a", x_mm=math.nan, y_mm=0, external_mating_requirement=RequiredMatingHole(diameter_mm=8))


def test_hardware_interface_rejects_duplicate_holes():
    with pytest.raises(ValidationError):
        AzimuthDriveMountInterfaceValue(component_id="x", mount_points=({"hole_id": "a", "x_mm": 0, "y_mm": 0}, {"hole_id": "a", "x_mm": 1, "y_mm": 1}), central_required_mating_opening_diameter_mm=10, frame_reference_id="datum-x")


def test_supported_key_and_anchor_are_exact():
    assert SupportedConstraintKey.AZIMUTH_DRIVE_MOUNT_INTERFACE.value == "azimuth.drive_mount_interface"
    assert ConstraintRequestMaterializer.anchor_for(SupportedConstraintKey.AZIMUTH_DRIVE_MOUNT_INTERFACE) == ("constraint", "CON-AZIMUTH-DRIVE-MOUNT-INTERFACE")


def test_hardware_interface_translates_to_plate_local_coordinates():
    spec = AzimuthMotorMountPlateSpec(
        part_id="plate",
        plate_length_mm=120,
        plate_width_mm=100,
        plate_thickness_mm=10,
        motor_center_x_mm=60,
        motor_center_y_mm=50,
        drive_mount_interface=interface(),
        frame_mount_hole_diameter_mm=None,
        frame_mount_hole_positions=(),
        provenance="M7B1_TEST_FIXTURE_ONLY",
    )
    program = compile_azimuth_motor_mount_plate(spec)
    assert (program.operations[2].x_mm, program.operations[2].y_mm) == (40, 30)
    assert (program.operations[2].diameter_mm, program.operations[3].diameter_mm) == (8, 8)


def test_new_interface_value_is_excluded_from_design_variables():
    spec = AzimuthMotorMountPlateSpec(
        part_id="plate",
        plate_length_mm=120,
        plate_width_mm=100,
        plate_thickness_mm=10,
        motor_center_x_mm=60,
        motor_center_y_mm=50,
        drive_mount_interface=interface(),
        provenance="M7B1_TEST_FIXTURE_ONLY",
    )
    assert spec.drive_mount_interface is not None
    assert "plate_length_mm" not in AzimuthDriveMountInterface.model_fields
