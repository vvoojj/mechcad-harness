from math import isfinite
from typing import Any

from pydantic import Field, field_validator, model_validator

from mechcad_harness.backends.models import BackendProvenance
from mechcad_harness.models.common import Model


def _finite_positive(value: float, name: str) -> float:
    numeric = float(value)
    if not isfinite(numeric) or numeric <= 0:
        raise ValueError(f"{name} must be finite and greater than zero")
    return numeric


class RectangleSectionInput(Model):
    width_mm: float
    height_mm: float
    mesh_size_mm2: float

    @field_validator("width_mm", "height_mm", "mesh_size_mm2")
    @classmethod
    def validate_positive_finite(cls, value: float, info):
        return _finite_positive(value, info.field_name)


class CircleSectionInput(Model):
    diameter_mm: float
    discretization_points: int = Field(ge=8, le=4096)
    mesh_size_mm2: float

    @field_validator("diameter_mm", "mesh_size_mm2")
    @classmethod
    def validate_positive_finite(cls, value: float, info):
        return _finite_positive(value, info.field_name)


class HollowCircleSectionInput(Model):
    outer_diameter_mm: float
    wall_thickness_mm: float
    discretization_points: int = Field(ge=8, le=4096)
    mesh_size_mm2: float

    @field_validator("outer_diameter_mm", "mesh_size_mm2")
    @classmethod
    def validate_positive_finite(cls, value: float, info):
        return _finite_positive(value, info.field_name)

    @field_validator("discretization_points")
    @classmethod
    def validate_discretization_points(cls, value: int):
        return value

    @field_validator("wall_thickness_mm")
    @classmethod
    def validate_wall_positive_finite(cls, value: float):
        return _finite_positive(value, "wall_thickness_mm")

    @model_validator(mode="after")
    def validate_wall_feasibility(self):
        if self.wall_thickness_mm * 2 >= self.outer_diameter_mm:
            raise ValueError("wall_thickness_mm must leave a positive inner diameter")
        return self


class SectionGeometryResult(Model):
    section_type: str = Field(min_length=1)
    area_mm2: float
    centroid_x_mm: float
    centroid_y_mm: float
    ixx_centroid_mm4: float
    iyy_centroid_mm4: float
    ixy_centroid_mm4: float
    perimeter_mm: float | None = None
    radius_of_gyration_x_mm: float | None = None
    radius_of_gyration_y_mm: float | None = None
    mesh_metadata: dict[str, Any]
    backend_provenance: BackendProvenance | None = None

    @field_validator(
        "area_mm2",
        "centroid_x_mm",
        "centroid_y_mm",
        "ixx_centroid_mm4",
        "iyy_centroid_mm4",
        "ixy_centroid_mm4",
        "perimeter_mm",
        "radius_of_gyration_x_mm",
        "radius_of_gyration_y_mm",
    )
    @classmethod
    def validate_finite(cls, value: float | None, info):
        if value is not None and not isfinite(float(value)):
            raise ValueError(f"{info.field_name} must be finite")
        return value


class SectionWarpingResult(Model):
    section_type: str = Field(min_length=1)
    torsion_constant_j_mm4: float
    shear_center_x_mm: float
    shear_center_y_mm: float
    shear_area_x_mm2: float
    shear_area_y_mm2: float
    warping_constant_mm6: float
    solver_type: str = Field(min_length=1)
    mesh_metadata: dict[str, Any]
    convergence_metadata: dict[str, Any]
    backend_provenance: BackendProvenance | None = None

    @field_validator(
        "torsion_constant_j_mm4",
        "shear_center_x_mm",
        "shear_center_y_mm",
        "shear_area_x_mm2",
        "shear_area_y_mm2",
        "warping_constant_mm6",
    )
    @classmethod
    def validate_warping_finite(cls, value: float, info):
        if not isfinite(float(value)):
            raise ValueError(f"{info.field_name} must be finite")
        return value
