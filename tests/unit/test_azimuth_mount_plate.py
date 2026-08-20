import math

import pytest
from pydantic import ValidationError

from mechcad_harness.azimuth_mount_plate import (
    M7B1_TEST_FIXTURE_ONLY,
    AzimuthMotorMountPlateSpec,
    XYPoint,
    compile_azimuth_motor_mount_plate,
    hole_edge_margin_mm,
    hole_ligament_mm,
    missing_authoritative_inputs,
    mount_plate_measurements,
    mount_plate_spec_hash,
)
from mechcad_harness.cad_program import BasePlateOperation, ThroughHoleOperation, cad_program_hash


def fixture_spec():
    return AzimuthMotorMountPlateSpec(
        part_id="azimuth_motor_mount_plate",
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


def test_valid_domain_spec_and_deterministic_compilation():
    spec = fixture_spec()
    program = compile_azimuth_motor_mount_plate(spec)
    assert M7B1_TEST_FIXTURE_ONLY == "M7B1_TEST_FIXTURE_ONLY"
    assert isinstance(program.operations[0], BasePlateOperation)
    assert [operation.operation_id for operation in program.operations] == ["base", "central_clearance", "motor_mount_1", "motor_mount_2", "motor_mount_3", "motor_mount_4", "frame_mount_1", "frame_mount_2", "frame_mount_3", "frame_mount_4"]
    assert isinstance(program.operations[1], ThroughHoleOperation)
    assert cad_program_hash(program) == cad_program_hash(compile_azimuth_motor_mount_plate(spec))


def test_invalid_geometry_is_rejected_before_cad_compilation():
    def replace(**updates):
        return AzimuthMotorMountPlateSpec.model_validate(fixture_spec().model_dump(mode="json") | updates)

    with pytest.raises(ValidationError):
        replace(plate_length_mm=0)
    with pytest.raises(ValidationError):
        replace(motor_mount_hole_positions=({"x_mm": 2, "y_mm": 2},))
    with pytest.raises(ValidationError):
        replace(central_clearance_hole_diameter_mm=math.nan)
    with pytest.raises(ValueError, match="duplicate"):
        replace(frame_mount_hole_positions=({"x_mm": 10, "y_mm": 10}, {"x_mm": 10, "y_mm": 10}))


def test_edge_margin_and_hole_ligament_are_deterministic():
    spec = fixture_spec()
    assert hole_edge_margin_mm(XYPoint(x_mm=10, y_mm=10), 6, spec.plate_length_mm, spec.plate_width_mm) == pytest.approx(7)
    assert hole_ligament_mm(XYPoint(x_mm=40, y_mm=30), 8, XYPoint(x_mm=80, y_mm=30), 8) == pytest.approx(32)
    measurements = mount_plate_measurements(spec)
    assert measurements["edge_margins_mm"]["motor_mount_1"] == pytest.approx(26)
    assert measurements["hole_ligaments_mm"]


def test_missing_authority_is_reported_without_defaults():
    from mechcad_harness.models import DesignState

    missing = missing_authoritative_inputs(DesignState(id="D", revision=1))
    assert len(missing) == 10
    assert all(item["blocking"] for item in missing)


def test_spec_hash_changes_with_semantic_geometry():
    first = mount_plate_spec_hash(fixture_spec())
    second = mount_plate_spec_hash(fixture_spec().model_copy(update={"plate_thickness_mm": 11}))
    assert first != second


def test_real_hardware_provenance_is_required_for_non_fixture_spec():
    with pytest.raises(ValidationError):
        AzimuthMotorMountPlateSpec.model_validate(fixture_spec().model_dump(mode="json") | {"provenance": ""})
