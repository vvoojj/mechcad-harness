import math

import pytest

from mechcad_harness.engineering import NominalSpurGeometry, calculate_nominal_spur
from mechcad_harness.tools.builtins import SpurGearInput, calc_spur_gear


def test_nominal_spur_geometry_uses_independent_nominal_equations():
    module_mm = 2.5
    driver_teeth = 20
    driven_teeth = 50
    driver_diameter = module_mm * driver_teeth
    driven_diameter = module_mm * driven_teeth

    result = calculate_nominal_spur(module_mm, driver_teeth, driven_teeth)

    assert isinstance(result, NominalSpurGeometry)
    assert result.pitch_diameter_driver_mm == driver_diameter
    assert result.pitch_diameter_driven_mm == driven_diameter
    assert result.center_distance_mm == (driver_diameter + driven_diameter) / 2
    assert result.ratio_magnitude == driven_teeth / driver_teeth


def test_builtin_spur_calculation_maps_shared_nominal_geometry():
    value = SpurGearInput(module_mm=2.5, teeth_pinion=20, teeth_gear=50)
    driver_diameter = value.module_mm * value.teeth_pinion
    driven_diameter = value.module_mm * value.teeth_gear

    result = calc_spur_gear(value)

    assert result.pitch_diameter_pinion_mm == driver_diameter
    assert result.pitch_diameter_gear_mm == driven_diameter
    assert result.center_distance_mm == (driver_diameter + driven_diameter) / 2
    assert result.ratio == value.teeth_gear / value.teeth_pinion


@pytest.mark.parametrize("module_mm", [0, -1, math.nan, math.inf, -math.inf])
def test_nominal_spur_rejects_non_finite_or_non_positive_module(module_mm):
    with pytest.raises(ValueError):
        calculate_nominal_spur(module_mm, 20, 50)


@pytest.mark.parametrize("driver_teeth,driven_teeth", [(0, 50), (-1, 50), (20, 0), (20, -1), (20.0, 50), (20, 50.0), (True, 50)])
def test_nominal_spur_rejects_non_positive_or_non_exact_integer_teeth(driver_teeth, driven_teeth):
    with pytest.raises(ValueError):
        calculate_nominal_spur(2.5, driver_teeth, driven_teeth)
