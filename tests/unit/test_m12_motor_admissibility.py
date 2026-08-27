from __future__ import annotations

from mechcad_harness.candidates import (
    ComponentPropertyAvailability,
    ComponentPropertyAuthority,
    ComponentPropertySnapshot,
    ComponentSpecificationSnapshot,
)
from mechcad_harness.revolute_drive import (
    DriveArchitecture,
    EngineeringCheckStatus,
    InputProvenanceKind,
    RevoluteDriveEngineeringRequirements,
    SourceBoundScalar,
    StaticOutputShaftDesignLoadCase,
    evaluate_motor_checks,
)


def scalar(value: float, unit: str, path: str) -> SourceBoundScalar:
    return SourceBoundScalar(
        value=value,
        unit=unit,
        provenance=InputProvenanceKind.SOURCE_AUTHORITY,
        source_path=path,
    )


def prop(key: str, value: float, unit: str) -> ComponentPropertySnapshot:
    return ComponentPropertySnapshot(
        key=key,
        availability=ComponentPropertyAvailability.AVAILABLE,
        normalized_value=value,
        canonical_unit=unit,
        source_identity="datasheet:motor@1",
        authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
    )


def motor(*, continuous: float | None = 12.0, speed_min: float = 10.0, speed_max: float = 200.0, voltage: float | None = 24.0) -> ComponentSpecificationSnapshot:
    properties = [
        prop("motor.peak_torque_nm", 30.0, "N*m"),
        prop("motor.speed_min_rpm", speed_min, "rpm"),
        prop("motor.speed_max_rpm", speed_max, "rpm"),
    ]
    if voltage is not None:
        properties.append(prop("motor.rated_voltage_v", voltage, "V"))
    if continuous is not None:
        properties.insert(0, prop("motor.continuous_torque_nm", continuous, "N*m"))
    else:
        properties.insert(
            0,
            ComponentPropertySnapshot(
                key="motor.continuous_torque_nm",
                availability=ComponentPropertyAvailability.MISSING,
                source_identity="datasheet:motor@1",
                authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
            ),
        )
    return ComponentSpecificationSnapshot(
        component_type="motor",
        source_identity="datasheet:motor@1",
        properties=tuple(properties),
    )


def requirements(*, required_speed: float = 100.0, design_torque: float = 10.0, required_voltage: float = 24.0, required_peak: float | None = None) -> RevoluteDriveEngineeringRequirements:
    return RevoluteDriveEngineeringRequirements(
        required_output_speed=scalar(required_speed, "rpm", "/requirements/required_output_speed"),
        design_load_case=StaticOutputShaftDesignLoadCase(
            design_torque=scalar(design_torque, "N*m", "/requirements/design_load_case/design_torque"),
            transverse_force_y=scalar(0.0, "N", "/requirements/design_load_case/transverse_force_y"),
            transverse_force_z=scalar(0.0, "N", "/requirements/design_load_case/transverse_force_z"),
        ),
        required_voltage=scalar(required_voltage, "V", "/requirements/required_voltage"),
        required_peak_torque=None if required_peak is None else scalar(required_peak, "N*m", "/requirements/required_peak_torque"),
        trusted_source_scalar_bindings=(),
    )


def statuses(checks):
    return {check.check_id: check.status for check in checks}


def test_direct_motor_checks_use_continuous_torque_and_scalar_speed():
    checks = evaluate_motor_checks(requirements(), motor())

    assert statuses(checks) == {
        "motor-continuous-torque": EngineeringCheckStatus.SATISFIED,
        "motor-speed": EngineeringCheckStatus.SATISFIED,
        "motor-voltage": EngineeringCheckStatus.SATISFIED,
    }
    torque_check = checks[0]
    assert torque_check.consumed_requirement_paths == ("/requirements/design_load_case/design_torque",)
    assert torque_check.consumed_property_bindings[0].property_key == "motor.continuous_torque_nm"


def test_motor_checks_report_valid_torque_speed_and_voltage_violations():
    checks = evaluate_motor_checks(
        requirements(required_speed=250.0, design_torque=20.0, required_voltage=12.0),
        motor(continuous=12.0, voltage=24.0),
    )

    assert statuses(checks) == {
        "motor-continuous-torque": EngineeringCheckStatus.VIOLATED,
        "motor-speed": EngineeringCheckStatus.VIOLATED,
        "motor-voltage": EngineeringCheckStatus.VIOLATED,
    }


def test_missing_continuous_torque_is_unresolved_and_peak_is_not_substituted():
    checks = evaluate_motor_checks(requirements(design_torque=20.0), motor(continuous=None))

    assert checks[0].status is EngineeringCheckStatus.UNRESOLVED
    assert "continuous" in (checks[0].reason or "")


def test_spur_context_transfers_required_torque_through_ratio_and_efficiency():
    checks = evaluate_motor_checks(
        requirements(design_torque=30.0, required_peak=50.0),
        motor(continuous=12.0),
        architecture=DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
        ratio_magnitude=5.0,
        efficiency=0.8,
    )

    assert statuses(checks) == {
        "motor-continuous-torque": EngineeringCheckStatus.SATISFIED,
        "motor-peak-torque": EngineeringCheckStatus.SATISFIED,
        "motor-speed": EngineeringCheckStatus.SATISFIED,
        "motor-voltage": EngineeringCheckStatus.SATISFIED,
    }
    torque_check = next(check for check in checks if check.check_id == "motor-continuous-torque")
    assert "/requirements/efficiency" in torque_check.consumed_requirement_paths


def test_spur_context_reports_inadequate_motor_torque_as_violated():
    checks = evaluate_motor_checks(
        requirements(design_torque=30.0, required_peak=160.0),
        motor(continuous=6.0),
        architecture=DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
        ratio_magnitude=5.0,
        efficiency=0.8,
    )

    statuses_by_id = statuses(checks)
    assert statuses_by_id["motor-continuous-torque"] is EngineeringCheckStatus.VIOLATED
    assert statuses_by_id["motor-peak-torque"] is EngineeringCheckStatus.VIOLATED
    torque_check = next(check for check in checks if check.check_id == "motor-continuous-torque")
    assert "7.5" in (torque_check.reason or "")
    peak_check = next(check for check in checks if check.check_id == "motor-peak-torque")
    assert "40.0" in (peak_check.reason or "")


def test_missing_efficiency_is_unresolved_not_violated_and_kinematics_stay_evaluated():
    checks = evaluate_motor_checks(
        requirements(design_torque=30.0, required_peak=50.0),
        motor(continuous=12.0),
        architecture=DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
        ratio_magnitude=5.0,
        efficiency=None,
    )

    statuses_by_id = statuses(checks)
    assert statuses_by_id["motor-continuous-torque"] is EngineeringCheckStatus.UNRESOLVED
    assert statuses_by_id["motor-peak-torque"] is EngineeringCheckStatus.UNRESOLVED
    assert "efficiency" in (checks[0].reason or "")
    assert statuses_by_id["motor-speed"] is EngineeringCheckStatus.SATISFIED
    assert statuses_by_id["motor-voltage"] is EngineeringCheckStatus.SATISFIED


def test_speed_check_can_be_suppressed_when_spur_pair_owns_output_speed_check():
    checks = evaluate_motor_checks(
        requirements(),
        motor(),
        architecture=DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
        ratio_magnitude=5.0,
        efficiency=None,
        include_speed_check=False,
    )

    assert "motor-speed" not in statuses(checks)


def test_direct_drive_ignores_optional_drive_context():
    direct = evaluate_motor_checks(requirements(design_torque=20.0), motor(continuous=12.0))
    with_eta = evaluate_motor_checks(requirements(design_torque=20.0), motor(continuous=12.0), efficiency=0.5)

    assert [check.status for check in direct] == [check.status for check in with_eta]


def test_declared_peak_requirement_is_checked_satisfied_and_violated():
    satisfied = evaluate_motor_checks(requirements(required_peak=25.0), motor())
    violated = evaluate_motor_checks(requirements(required_peak=50.0), motor())

    assert statuses(satisfied)["motor-peak-torque"] is EngineeringCheckStatus.SATISFIED
    assert statuses(violated)["motor-peak-torque"] is EngineeringCheckStatus.VIOLATED
    peak_check = next(check for check in violated if check.check_id == "motor-peak-torque")
    assert "/requirements/required_peak_torque" in peak_check.consumed_requirement_paths


def test_missing_rated_voltage_property_is_unresolved_when_voltage_required():
    checks = evaluate_motor_checks(requirements(), motor(voltage=None))

    voltage_check = next(check for check in checks if check.check_id == "motor-voltage")
    assert voltage_check.status is EngineeringCheckStatus.UNRESOLVED
    assert "rated_voltage" in (voltage_check.reason or "")


def test_required_speed_below_minimum_or_above_maximum_is_violated():
    below = evaluate_motor_checks(requirements(required_speed=5.0), motor())
    above = evaluate_motor_checks(requirements(required_speed=300.0), motor())

    assert statuses(below)["motor-speed"] is EngineeringCheckStatus.VIOLATED
    assert statuses(above)["motor-speed"] is EngineeringCheckStatus.VIOLATED


def test_speed_check_retains_available_bound_binding_when_other_bound_is_missing():
    payload = motor().model_dump(mode="json")
    payload["properties"] = [
        property_value
        for property_value in payload["properties"]
        if property_value["key"] != "motor.speed_max_rpm"
    ]
    payload["specification_hash"] = "pending"
    incomplete_motor = type(motor()).model_validate(payload)

    speed_check = next(
        check
        for check in evaluate_motor_checks(requirements(), incomplete_motor)
        if check.check_id == "motor-speed"
    )

    assert speed_check.status is EngineeringCheckStatus.UNRESOLVED
    assert [binding.property_key for binding in speed_check.consumed_property_bindings] == [
        "motor.speed_min_rpm"
    ]


def test_negative_usable_speed_bound_is_not_accepted_as_a_speed_magnitude():
    checks = evaluate_motor_checks(requirements(required_speed=100.0), motor(speed_min=-1.0))

    speed_check = next(check for check in checks if check.check_id == "motor-speed")

    assert speed_check.status is EngineeringCheckStatus.VIOLATED
    assert "nonnegative" in (speed_check.reason or "")
