from enum import StrEnum
from math import isfinite
from typing import Any

from pydantic import Field, model_validator

from .backends.models import BackendProvenance
from .materials import MaterialDataAuthority, MaterialPropertyName, MaterialPropertyStatus, MaterialPropertyValue, TypicalMaterialPropertiesResult
from .models.common import Model
from .sections import SectionGeometryResult, SectionWarpingResult


class DerivedPropertyStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class DerivedEngineeringValue(Model):
    property: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    status: DerivedPropertyStatus
    min_value: float | None = None
    max_value: float | None = None
    representative_value: float | None = None
    authority: MaterialDataAuthority
    source_dependencies: tuple[str, ...] = ()
    value_semantics: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_value(self):
        values = (self.min_value, self.max_value, self.representative_value)
        if any(value is not None and not isfinite(float(value)) for value in values):
            raise ValueError("derived values must be finite")
        if self.status is DerivedPropertyStatus.UNAVAILABLE and any(value is not None for value in values):
            raise ValueError("unavailable derived values cannot contain numbers")
        if self.status is DerivedPropertyStatus.AVAILABLE and self.min_value is None and self.max_value is None and self.representative_value is None:
            raise ValueError("available derived values require numbers")
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise ValueError("derived minimum exceeds maximum")
        return self


class IntegrationSourceRecord(Model):
    result_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    bound_revision: int = Field(gt=0)
    bound_state_hash: str = Field(min_length=1)
    output_hash: str = Field(min_length=1)
    backend_provenance: BackendProvenance | None = None


class PreliminarySectionEngineeringCalculatorInput(Model):
    material: TypicalMaterialPropertiesResult
    section_geometry: SectionGeometryResult
    section_warping: SectionWarpingResult | None = None
    material_source: IntegrationSourceRecord | None = None
    section_geometry_source: IntegrationSourceRecord | None = None
    section_warping_source: IntegrationSourceRecord | None = None


class PreliminarySectionEngineeringToolInput(Model):
    material_result_id: str = Field(min_length=1)
    section_geometry_result_id: str = Field(min_length=1)
    section_warping_result_id: str | None = None


class PreliminarySectionEngineeringResult(Model):
    material_identity: str = Field(min_length=1)
    material_authority: MaterialDataAuthority
    section_type: str = Field(min_length=1)
    area_mm2: float
    ixx_mm4: float
    iyy_mm4: float
    torsion_constant_j_mm4: float | None = None
    mass_per_length: DerivedEngineeringValue
    axial_rigidity_ea: DerivedEngineeringValue
    bending_rigidity_eix: DerivedEngineeringValue
    bending_rigidity_eiy: DerivedEngineeringValue
    torsional_rigidity_gj: DerivedEngineeringValue
    assumptions: tuple[str, ...]
    contributing_provenance: dict[str, Any]
    source_records: tuple[IntegrationSourceRecord, ...] = ()
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_geometry_values(self):
        for value in (self.area_mm2, self.ixx_mm4, self.iyy_mm4, self.torsion_constant_j_mm4):
            if value is not None and not isfinite(float(value)):
                raise ValueError("section values must be finite")
        return self


def _property(material: TypicalMaterialPropertiesResult, name: MaterialPropertyName) -> MaterialPropertyValue | None:
    return material.properties.get(name.value)


def _unit(value: MaterialPropertyValue, expected: str) -> None:
    if value.unit != expected:
        raise ValueError(f"unsupported unit for {value.property.value}: expected {expected}, got {value.unit}")


def _available(value: MaterialPropertyValue | None, reason: str, authority: MaterialDataAuthority, property_name: str, unit: str, dependencies: tuple[str, ...]):
    if value is None or value.status is not MaterialPropertyStatus.AVAILABLE:
        return DerivedEngineeringValue(property=property_name, unit=unit, status=DerivedPropertyStatus.UNAVAILABLE, authority=authority, source_dependencies=dependencies, reason=reason)
    _unit(value, "GPa" if value.property in (MaterialPropertyName.ELASTIC_MODULUS, MaterialPropertyName.SHEAR_MODULUS) else value.unit)
    return value


def _multiply(value: MaterialPropertyValue, factor: float, property_name: str, unit: str, authority: MaterialDataAuthority, dependencies: tuple[str, ...]):
    minimum = value.min_value * factor if value.min_value is not None else None
    maximum = value.max_value * factor if value.max_value is not None else None
    representative = value.representative_value * factor if value.representative_value is not None else None
    return DerivedEngineeringValue(property=property_name, unit=unit, status=DerivedPropertyStatus.AVAILABLE, min_value=minimum, max_value=maximum, representative_value=representative, authority=authority, source_dependencies=dependencies, value_semantics=value.value_semantics)


def calculate_preliminary_section_engineering(value: PreliminarySectionEngineeringCalculatorInput) -> PreliminarySectionEngineeringResult:
    material = value.material
    authority = material.authority
    dependencies = tuple(record.result_id for record in (value.material_source, value.section_geometry_source, value.section_warping_source) if record is not None)
    density = _available(material.density, "MATERIAL_DENSITY_UNAVAILABLE", authority, "mass_per_length", "kg/m", dependencies)
    if isinstance(density, MaterialPropertyValue):
        _unit(density, "kg/m^3")
        mass = _multiply(density, value.section_geometry.area_mm2 * 1e-6, "mass_per_length", "kg/m", authority, dependencies)
    else:
        mass = density
    modulus = _property(material, MaterialPropertyName.ELASTIC_MODULUS)
    modulus_result = _available(modulus, "ELASTIC_MODULUS_UNAVAILABLE", authority, "axial_rigidity_ea", "N", dependencies)
    if isinstance(modulus_result, MaterialPropertyValue):
        modulus_factor = 1000 * value.section_geometry.area_mm2
        ea = _multiply(modulus_result, modulus_factor, "axial_rigidity_ea", "N", authority, dependencies)
        eix = _multiply(modulus_result, 1000 * value.section_geometry.ixx_centroid_mm4, "bending_rigidity_eix", "N*mm^2", authority, dependencies)
        eiy = _multiply(modulus_result, 1000 * value.section_geometry.iyy_centroid_mm4, "bending_rigidity_eiy", "N*mm^2", authority, dependencies)
    else:
        ea = modulus_result
        eix = modulus_result.model_copy(update={"property": "bending_rigidity_eix", "unit": "N*mm^2"})
        eiy = modulus_result.model_copy(update={"property": "bending_rigidity_eiy", "unit": "N*mm^2"})
    shear = _property(material, MaterialPropertyName.SHEAR_MODULUS)
    if shear is None or shear.status is not MaterialPropertyStatus.AVAILABLE:
        gj = DerivedEngineeringValue(property="torsional_rigidity_gj", unit="N*mm^2", status=DerivedPropertyStatus.UNAVAILABLE, authority=authority, source_dependencies=dependencies, reason="SHEAR_MODULUS_UNAVAILABLE")
    elif value.section_warping is None:
        gj = DerivedEngineeringValue(property="torsional_rigidity_gj", unit="N*mm^2", status=DerivedPropertyStatus.UNAVAILABLE, authority=authority, source_dependencies=dependencies, reason="TORSION_CONSTANT_UNAVAILABLE")
    else:
        _unit(shear, "GPa")
        gj = _multiply(shear, 1000 * value.section_warping.torsion_constant_j_mm4, "torsional_rigidity_gj", "N*mm^2", authority, dependencies)
    warnings = ("TYPICAL_REFERENCE_DATA", "PRINTED_MATERIAL_ANISOTROPY_NOT_REPRESENTED") if authority is MaterialDataAuthority.TYPICAL_REFERENCE else ()
    provenance = {"material": value.material_source.backend_provenance if value.material_source else material.backend_provenance, "section_geometry": value.section_geometry_source.backend_provenance if value.section_geometry_source else value.section_geometry.backend_provenance, "section_warping": value.section_warping_source.backend_provenance if value.section_warping_source else (value.section_warping.backend_provenance if value.section_warping else None), "integration_tool": "mechcad-calc-preliminary-section-engineering-properties@1.0"}
    return PreliminarySectionEngineeringResult(material_identity=material.canonical_name, material_authority=authority, section_type=value.section_geometry.section_type, area_mm2=value.section_geometry.area_mm2, ixx_mm4=value.section_geometry.ixx_centroid_mm4, iyy_mm4=value.section_geometry.iyy_centroid_mm4, torsion_constant_j_mm4=value.section_warping.torsion_constant_j_mm4 if value.section_warping else None, mass_per_length=mass, axial_rigidity_ea=ea, bending_rigidity_eix=eix, bending_rigidity_eiy=eiy, torsional_rigidity_gj=gj, assumptions=("HOMOGENEOUS_SECTION", "ISOTROPIC_LINEAR_ELASTIC_PRELIMINARY"), contributing_provenance=provenance, source_records=tuple(record for record in (value.material_source, value.section_geometry_source, value.section_warping_source) if record is not None), warnings=warnings)
