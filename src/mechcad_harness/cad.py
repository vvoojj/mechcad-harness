from math import isfinite

from pydantic import Field, field_validator, model_validator

from mechcad_harness.backends.models import BackendProvenance
from mechcad_harness.models.common import Model


class SpurGearCadInput(Model):
    module_mm: float = Field(gt=0)
    teeth: int = Field(gt=0)
    face_width_mm: float = Field(gt=0)
    pressure_angle_deg: float = Field(gt=0)
    profile_shift: float = 0.0
    bore_diameter_mm: float | None = Field(default=None, gt=0)
    requested_formats: tuple[str, ...] = ("step", "stl")

    @field_validator("requested_formats")
    @classmethod
    def validate_formats(cls, values):
        if not values or any(value not in {"step", "stl"} for value in values) or len(set(values)) != len(values):
            raise ValueError("requested_formats must contain unique values from step/stl")
        return values

    @model_validator(mode="after")
    def validate_finite(self):
        for name in ("module_mm", "face_width_mm", "pressure_angle_deg", "profile_shift"):
            if not isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be finite")
        return self


class ArtifactReference(Model):
    artifact_id: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=1)
    size_bytes: int = Field(gt=0)


class SpurGearCadResult(Model):
    geometry_summary: dict[str, float | int | bool]
    artifact_references: tuple[ArtifactReference, ...]
    bounding_box_mm: tuple[float, float, float]
    volume_mm3: float = Field(gt=0)
    center_of_mass_mm: tuple[float, float, float]
    backend_provenance: BackendProvenance
    build123d_provenance: BackendProvenance


class SpurGearPairCadInput(Model):
    pinion: SpurGearCadInput
    gear: SpurGearCadInput


class SpurGearPairCadResult(Model):
    pinion: SpurGearCadResult
    gear: SpurGearCadResult
    nominal_center_distance_mm: float
    relative_transform: tuple[float, float, float]
