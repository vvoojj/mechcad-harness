from __future__ import annotations

import math

import pytest

from mechcad_harness.candidates import (
    ComponentPropertyAvailability,
    ComponentPropertyAuthority,
    ComponentPropertySnapshot,
    ComponentSpecificationSnapshot,
)
from mechcad_harness.revolute_drive import (
    EngineeringCheckStatus,
    InputProvenanceKind,
    RevoluteDriveEngineeringRequirements,
    SourceBoundScalar,
    StaticOutputShaftDesignLoadCase,
    calculate_spur_loads,
    evaluate_spur_pair,
)


def scalar(value: float, unit: str, path: str) -> SourceBoundScalar:
    return SourceBoundScalar(value=value, unit=unit, provenance=InputProvenanceKind.SOURCE_AUTHORITY, source_path=path)


def prop(key: str, value: float, unit: str) -> ComponentPropertySnapshot:
    return ComponentPropertySnapshot(
        key=key,
        availability=ComponentPropertyAvailability.AVAILABLE,
        normalized_value=value if isinstance(value, float) else None,
        canonical_unit=unit,
        source_identity="fixture:gear@1",
        authority=ComponentPropertyAuthority.USER_DECLARED,
    )


def gear(*, module: float = 2.0, teeth: int = 20, pressure_angle: float = 20.0, kind: str = "external_spur") -> ComponentSpecificationSnapshot:
    return ComponentSpecificationSnapshot(
        component_type="gear",
        source_identity=f"fixture:gear:{teeth}@1",
        properties=(
            prop("gear.module_mm", module, "mm"),
            prop("gear.tooth_count", float(teeth), "1"),
            prop("gear.pressure_angle_deg", pressure_angle, "deg"),
            prop("gear.face_width_mm", 10.0, "mm"),
            prop("gear.bore_diameter_mm", 12.0, "mm"),
        ),
        compatibility_declarations=(kind,),
    )


def motor() -> ComponentSpecificationSnapshot:
    return ComponentSpecificationSnapshot(
        component_type="motor",
        source_identity="fixture:motor@1",
        properties=(
            prop("motor.continuous_torque_nm", 10.0, "N*m"),
            prop("motor.peak_torque_nm", 20.0, "N*m"),
            prop("motor.speed_min_rpm", 10.0, "rpm"),
            prop("motor.speed_max_rpm", 500.0, "rpm"),
        ),
    )


def requirements(*, efficiency: float | None = 0.8) -> RevoluteDriveEngineeringRequirements:
    return RevoluteDriveEngineeringRequirements(
        required_output_speed=scalar(20.0, "rpm", "/requirements/required_output_speed"),
        design_load_case=StaticOutputShaftDesignLoadCase(
            design_torque=scalar(30.0, "N*m", "/requirements/design_load_case/design_torque"),
            transverse_force_y=scalar(0.0, "N", "/requirements/design_load_case/transverse_force_y"),
            transverse_force_z=scalar(0.0, "N", "/requirements/design_load_case/transverse_force_z"),
        ),
        efficiency=None if efficiency is None else SourceBoundScalar(value=efficiency, unit="1", provenance=InputProvenanceKind.POLICY_ASSUMPTION),
        trusted_source_scalar_bindings=(),
    )


def test_spur_pair_uses_explicit_driver_driven_ratio_and_efficiency_torque():
    result = evaluate_spur_pair(
        requirements(),
        motor(),
        gear(teeth=20),
        gear(teeth=100),
        motor_speed_rpm=100.0,
    )

    assert result.ratio_magnitude == 5.0
    assert result.pitch_diameter_driver_mm == 40.0
    assert result.pitch_diameter_driven_mm == 200.0
    assert result.center_distance_mm == 120.0
    assert result.output_speed_rpm == 20.0
    assert result.output_continuous_torque_nm == 40.0
    assert result.speed_check.status is EngineeringCheckStatus.SATISFIED
    assert result.torque_check.status is EngineeringCheckStatus.SATISFIED


def test_spur_pair_rejects_negative_motor_speed_magnitude():
    with pytest.raises(ValueError, match="motor_speed_rpm"):
        evaluate_spur_pair(
            requirements(),
            motor(),
            gear(teeth=20),
            gear(teeth=100),
            motor_speed_rpm=-1.0,
        )


def test_incompatible_spur_properties_are_violated_and_missing_efficiency_is_unresolved():
    result = evaluate_spur_pair(
        requirements(efficiency=None),
        motor(),
        gear(module=2.0, pressure_angle=20.0),
        gear(module=3.0, pressure_angle=25.0, kind="internal_spur"),
    )

    assert result.compatibility_check.status is EngineeringCheckStatus.VIOLATED
    assert result.torque_check.status is EngineeringCheckStatus.UNRESOLVED
    assert result.output_continuous_torque_nm is None


def test_spur_loads_use_driven_design_torque_without_efficiency_duplication():
    result = calculate_spur_loads(requirements(), driven_pitch_diameter_mm=200.0, pressure_angle_deg=20.0)
    expected_ft = 2.0 * 1000.0 * 30.0 / 200.0

    assert result.transmitted_torque_n_mm == 30000.0
    assert result.tangential_force_n == expected_ft
    assert result.radial_force_n == expected_ft * math.tan(math.radians(20.0))


def test_module_mismatch_alone_is_violated():
    result = evaluate_spur_pair(requirements(), motor(), gear(teeth=20), gear(teeth=100, module=3.0))

    assert result.compatibility_check.status is EngineeringCheckStatus.VIOLATED
    assert "module" in (result.compatibility_check.reason or "")


def test_pressure_angle_mismatch_alone_is_violated():
    result = evaluate_spur_pair(requirements(), motor(), gear(teeth=20), gear(teeth=100, pressure_angle=25.0))

    assert result.compatibility_check.status is EngineeringCheckStatus.VIOLATED
    assert "pressure angle" in (result.compatibility_check.reason or "")


def test_spur_speed_check_retains_available_bound_binding_when_other_bound_is_missing():
    payload = motor().model_dump(mode="json")
    payload["properties"] = [
        property_value
        for property_value in payload["properties"]
        if property_value["key"] != "motor.speed_max_rpm"
    ]
    payload["specification_hash"] = "pending"
    incomplete_motor = type(motor()).model_validate(payload)

    result = evaluate_spur_pair(
        requirements(),
        incomplete_motor,
        gear(teeth=20),
        gear(teeth=100),
    )

    assert result.speed_check.status is EngineeringCheckStatus.UNRESOLVED
    assert [binding.property_key for binding in result.speed_check.consumed_property_bindings] == [
        "motor.speed_min_rpm"
    ]


def test_spur_torque_check_retains_binding_for_nonpositive_declared_continuous_torque():
    payload = motor().model_dump(mode="json")
    payload["properties"][0]["normalized_value"] = 0.0
    payload["properties"][0]["property_hash"] = "pending"
    payload["specification_hash"] = "pending"
    invalid_motor = type(motor()).model_validate(payload)

    result = evaluate_spur_pair(
        requirements(),
        invalid_motor,
        gear(teeth=20),
        gear(teeth=100),
    )

    assert result.torque_check.status is EngineeringCheckStatus.VIOLATED
    assert [binding.property_key for binding in result.torque_check.consumed_property_bindings] == [
        "motor.continuous_torque_nm"
    ]


def test_declared_but_unavailable_profile_shift_is_not_silently_assumed_zero():
    driver_payload = gear(teeth=20).model_dump(mode="json")
    driver_payload["properties"].append(
        {
            "key": "gear.profile_shift",
            "availability": "missing",
            "source_identity": "fixture:gear:20@1",
            "authority": "manufacturer_datasheet",
            "property_hash": "pending",
        }
    )
    driver_payload["specification_hash"] = "pending"
    driver = type(gear(teeth=20)).model_validate(driver_payload)

    result = evaluate_spur_pair(requirements(), motor(), driver, gear(teeth=100))

    assert result.compatibility_check.status is EngineeringCheckStatus.UNRESOLVED
    assert "profile-shift" in (result.compatibility_check.reason or "")
    assert any(
        binding.property_key == "gear.profile_shift"
        for binding in result.compatibility_check.consumed_property_bindings
    )


def test_kind_contradiction_alone_is_violated():
    result = evaluate_spur_pair(requirements(), motor(), gear(teeth=20), gear(teeth=100, kind="internal_spur"))

    assert result.compatibility_check.status is EngineeringCheckStatus.VIOLATED


@pytest.mark.parametrize(
    ("diameter", "angle"),
    [
        (0.0, 20.0),
        (-200.0, 20.0),
        (float("nan"), 20.0),
        (float("inf"), 20.0),
        (200.0, 0.0),
        (200.0, 90.0),
        (200.0, -15.0),
        (200.0, float("nan")),
    ],
)
def test_spur_load_rejects_invalid_driven_pitch_diameter_or_pressure_angle(diameter: float, angle: float):
    with pytest.raises(ValueError):
        calculate_spur_loads(requirements(), driven_pitch_diameter_mm=diameter, pressure_angle_deg=angle)
