from __future__ import annotations

import math

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
    ShaftSupportGeometry,
    SourceBoundScalar,
    StaticOutputShaftDesignLoadCase,
    calculate_shaft_static_sizing,
)


def scalar(value: float, unit: str, path: str) -> SourceBoundScalar:
    return SourceBoundScalar(value=value, unit=unit, provenance=InputProvenanceKind.SOURCE_AUTHORITY, source_path=path)


def shaft(diameter: float) -> ComponentSpecificationSnapshot:
    return ComponentSpecificationSnapshot(
        component_type="shaft",
        source_identity="fixture:shaft@1",
        properties=(
            ComponentPropertySnapshot(
                key="shaft.diameter_mm",
                availability=ComponentPropertyAvailability.AVAILABLE,
                normalized_value=diameter,
                canonical_unit="mm",
                source_identity="fixture:shaft@1",
                authority=ComponentPropertyAuthority.USER_DECLARED,
            ),
        ),
    )


def requirements(*, yield_strength: float | None = 250.0, safety_factor: float | None = 2.0) -> RevoluteDriveEngineeringRequirements:
    return RevoluteDriveEngineeringRequirements(
        required_output_speed=scalar(10.0, "rpm", "/requirements/required_output_speed"),
        design_load_case=StaticOutputShaftDesignLoadCase(
            design_torque=scalar(20.0, "N*m", "/requirements/design_load_case/design_torque"),
            transverse_force_y=scalar(100.0, "N", "/requirements/design_load_case/transverse_force_y"),
            transverse_force_z=scalar(-50.0, "N", "/requirements/design_load_case/transverse_force_z"),
        ),
        safety_factor=None if safety_factor is None else SourceBoundScalar(value=safety_factor, unit="1", provenance=InputProvenanceKind.POLICY_ASSUMPTION),
        shaft_yield_strength=None if yield_strength is None else scalar(yield_strength, "MPa", "/requirements/shaft_yield_strength"),
        shaft_support_geometry=ShaftSupportGeometry(
            support_a_x=scalar(0.0, "mm", "/geometry/support_a_x"),
            support_b_x=scalar(100.0, "mm", "/geometry/support_b_x"),
            load_plane_x=scalar(40.0, "mm", "/geometry/load_plane_x"),
        ),
        trusted_source_scalar_bindings=(),
    )


def oracle():
    L = 100.0
    a = 40.0
    fy, fz = 100.0, -50.0
    ray = -fy * (L - a) / L
    rby = -fy * a / L
    raz = -fz * (L - a) / L
    rbz = -fz * a / L
    my = abs(ray * a)
    mz = abs(raz * a)
    m = math.sqrt(my * my + mz * mz)
    t = 1000.0 * 20.0
    C = math.sqrt((32.0 * m / math.pi) ** 2 + 3.0 * (16.0 * t / math.pi) ** 2)
    d_min = (C / (250.0 / 2.0)) ** (1.0 / 3.0)
    return ray, rby, raz, rbz, m, d_min


def test_shaft_sizing_reports_reactions_equilibrium_stress_and_minimum_diameter():
    result = calculate_shaft_static_sizing(requirements(), shaft(20.0))
    ray, rby, raz, rbz, m, d_min = oracle()
    d = 20.0
    sigma_b = 32.0 * m / (math.pi * d**3)
    tau = 16.0 * 20000.0 / (math.pi * d**3)

    assert result.reaction_a_y_n == ray
    assert result.reaction_b_y_n == rby
    assert result.reaction_a_z_n == raz
    assert result.reaction_b_z_n == rbz
    assert result.maximum_bending_moment_n_mm == m
    assert result.bending_stress_mpa == sigma_b
    assert result.torsional_stress_mpa == tau
    assert result.von_mises_stress_mpa == math.sqrt(sigma_b**2 + 3.0 * tau**2)
    assert result.minimum_diameter_mm == d_min
    assert result.allowable_stress_mpa == 125.0
    assert result.equilibrium_check.status is EngineeringCheckStatus.SATISFIED
    assert abs(result.force_residual_y_n) < 1e-9
    assert abs(result.force_residual_z_n) < 1e-9
    assert abs(result.moment_residual_y_n_mm) < 1e-9
    assert abs(result.moment_residual_z_n_mm) < 1e-9


def test_shaft_diameter_boundary_uses_only_the_declared_stress_tolerance():
    _, _, _, _, _, d_min = oracle()
    at_min = calculate_shaft_static_sizing(requirements(), shaft(d_min))
    below = calculate_shaft_static_sizing(requirements(), shaft(0.99 * d_min))
    above = calculate_shaft_static_sizing(requirements(), shaft(1.01 * d_min))

    assert at_min.stress_check.status is EngineeringCheckStatus.SATISFIED
    assert below.stress_check.status is EngineeringCheckStatus.VIOLATED
    assert above.stress_check.status is EngineeringCheckStatus.SATISFIED


def test_missing_yield_strength_or_design_factor_leaves_stress_check_unresolved():
    without_yield = calculate_shaft_static_sizing(requirements(yield_strength=None), shaft(20.0))
    without_factor = calculate_shaft_static_sizing(requirements(safety_factor=None), shaft(20.0))

    for result in (without_yield, without_factor):
        assert result.reaction_a_y_n == oracle()[0]
        assert result.maximum_bending_moment_n_mm == oracle()[4]
        assert result.minimum_diameter_mm is None
        assert result.allowable_stress_mpa is None
        assert result.equilibrium_check.status is EngineeringCheckStatus.SATISFIED
        assert result.stress_check.status is EngineeringCheckStatus.UNRESOLVED


def test_stress_check_retains_binding_for_nonpositive_declared_shaft_diameter():
    result = calculate_shaft_static_sizing(requirements(), shaft(0.0))

    assert result.stress_check.status is EngineeringCheckStatus.VIOLATED
    assert [binding.property_key for binding in result.stress_check.consumed_property_bindings] == [
        "shaft.diameter_mm"
    ]


def test_selected_diameter_drives_stress_while_theoretical_minimum_stays_separate():
    baseline = calculate_shaft_static_sizing(requirements(), shaft(12.0), selected_diameter_mm=12.0)
    selected = calculate_shaft_static_sizing(requirements(), shaft(12.0), selected_diameter_mm=14.0)

    assert selected.von_mises_stress_mpa < baseline.von_mises_stress_mpa
    assert selected.minimum_diameter_mm == baseline.minimum_diameter_mm
    assert selected.stress_check.status is EngineeringCheckStatus.SATISFIED


def test_invalid_selected_diameter_is_a_typed_unresolved_stress_result():
    result = calculate_shaft_static_sizing(requirements(), shaft(12.0), selected_diameter_mm="not-a-number")

    assert result.stress_check.status is EngineeringCheckStatus.UNRESOLVED
    assert "design variable" in (result.stress_check.reason or "")
