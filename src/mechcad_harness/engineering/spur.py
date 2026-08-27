from math import isfinite
from numbers import Integral, Real

from mechcad_harness.models.common import Model


class NominalSpurGeometry(Model):
    pitch_diameter_driver_mm: float
    pitch_diameter_driven_mm: float
    center_distance_mm: float
    ratio_magnitude: float


def _positive_finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite positive number")
    numeric = float(value)
    if not isfinite(numeric) or numeric <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return numeric


def _positive_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def calculate_nominal_spur(module_mm: float, driver_teeth: int, driven_teeth: int) -> NominalSpurGeometry:
    module = _positive_finite(module_mm, "module_mm")
    driver = _positive_integer(driver_teeth, "driver_teeth")
    driven = _positive_integer(driven_teeth, "driven_teeth")
    pitch_diameter_driver = module * driver
    pitch_diameter_driven = module * driven
    return NominalSpurGeometry(
        pitch_diameter_driver_mm=pitch_diameter_driver,
        pitch_diameter_driven_mm=pitch_diameter_driven,
        center_distance_mm=(pitch_diameter_driver + pitch_diameter_driven) / 2,
        ratio_magnitude=driven / driver,
    )
