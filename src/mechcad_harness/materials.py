from enum import StrEnum
from math import isfinite

from pydantic import Field, model_validator

from .backends.models import BackendProvenance
from .models.common import Model


class MaterialDataAuthority(StrEnum):
    TYPICAL_REFERENCE = "typical_reference"
    SUPPLIER_DATASHEET = "supplier_datasheet"
    MEASURED = "measured"
    USER_OVERRIDE = "user_override"


class MaterialPropertyStatus(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    NOT_SUITABLE = "not_suitable"


class MaterialPropertyName(StrEnum):
    DENSITY = "density"
    ELASTIC_MODULUS = "elastic_modulus"
    SHEAR_MODULUS = "shear_modulus"
    POISSON_RATIO = "poisson_ratio"
    YIELD_STRENGTH = "yield_strength"
    TENSILE_STRENGTH = "tensile_strength"
    SHEAR_STRENGTH = "shear_strength"
    ELONGATION_AT_BREAK = "elongation_at_break"
    SERVICE_TEMPERATURE = "service_temperature"
    GLASS_TRANSITION_TEMPERATURE = "glass_transition_temperature"
    HEAT_DEFLECTION_TEMPERATURE = "heat_deflection_temperature"


class MaterialPropertyValue(Model):
    property: MaterialPropertyName
    unit: str = Field(min_length=1)
    status: MaterialPropertyStatus
    min_value: float | None = None
    max_value: float | None = None
    representative_value: float | None = None
    authority: MaterialDataAuthority
    source: str = Field(min_length=1)
    value_semantics: str | None = None

    @model_validator(mode="after")
    def validate_values(self):
        numbers = (self.min_value, self.max_value, self.representative_value)
        if any(value is not None and not isfinite(value) for value in numbers):
            raise ValueError("material property values must be finite")
        if self.status is not MaterialPropertyStatus.AVAILABLE and any(value is not None for value in numbers):
            raise ValueError("unavailable material properties cannot contain numeric values")
        if self.status is MaterialPropertyStatus.AVAILABLE and self.min_value is None and self.max_value is None and self.representative_value is None:
            raise ValueError("available material property requires a numeric value")
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise ValueError("material property minimum exceeds maximum")
        return self


class TypicalMaterialPropertiesInput(Model):
    material_id: str = Field(min_length=1)


class TypicalMaterialPropertiesResult(Model):
    canonical_name: str = Field(min_length=1)
    display_name: str | None = None
    category: str = Field(min_length=1)
    family: str = Field(min_length=1)
    grade: str | None = None
    condition_process: str | None = None
    authority: MaterialDataAuthority
    density: MaterialPropertyValue
    properties: dict[str, MaterialPropertyValue]
    backend_provenance: BackendProvenance
    warnings: tuple[str, ...] = ()


class MaterialMassInput(Model):
    volume_mm3: float = Field(gt=0)
    material_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def finite_volume(self):
        if not isfinite(self.volume_mm3):
            raise ValueError("volume_mm3 must be finite")
        return self


class MaterialMassResult(Model):
    mass_g: float = Field(gt=0)
    volume_mm3: float
    density: MaterialPropertyValue
    authority: MaterialDataAuthority
    estimate: bool = True
    backend_provenance: BackendProvenance
