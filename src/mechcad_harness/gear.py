from math import isfinite

from pydantic import Field, model_validator

from .models.common import Model


class SpurGearGeometryInput(Model):
    module_mm: float = Field(gt=0)
    teeth: int = Field(gt=0)
    face_width_mm: float = Field(gt=0)
    pressure_angle_deg: float = Field(gt=0)
    profile_shift: float = 0.0
    internal: bool = False

    @model_validator(mode="after")
    def finite_values(self):
        for name in ("module_mm", "face_width_mm", "pressure_angle_deg", "profile_shift"):
            if not isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be finite")
        return self


class SpurGearGeometryResult(Model):
    module_mm: float
    teeth: int
    pitch_diameter_mm: float
    pitch_radius_mm: float
    addendum_diameter_mm: float
    root_diameter_mm: float
    base_diameter_mm: float
    face_width_mm: float
    pressure_angle_deg: float
    profile_shift: float
    internal: bool
    geometry_metadata: dict[str, float]


class SpurGearPairInput(Model):
    module_mm: float = Field(gt=0)
    pinion_teeth: int = Field(gt=0)
    gear_teeth: int = Field(gt=0)
    face_width_mm: float = Field(gt=0)
    pressure_angle_deg: float = Field(gt=0)
    pinion_profile_shift: float = 0.0
    gear_profile_shift: float = 0.0

    @model_validator(mode="after")
    def finite_values(self):
        for name in ("module_mm", "face_width_mm", "pressure_angle_deg", "pinion_profile_shift", "gear_profile_shift"):
            if not isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be finite")
        return self


class SpurGearPairResult(Model):
    module_mm: float
    pinion_teeth: int
    gear_teeth: int
    gear_ratio: float
    pinion_pitch_diameter_mm: float
    gear_pitch_diameter_mm: float
    nominal_center_distance_mm: float
    actual_center_distance_mm: float
    pinion_profile_shift: float
    gear_profile_shift: float
