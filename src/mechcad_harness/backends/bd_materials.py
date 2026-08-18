from importlib import metadata
from math import isfinite

from packaging.version import Version

from .errors import BackendCompatibilityError, BackendUnavailableError
from .models import BackendHealth, BackendHealthStatus, BackendIdentity
from .provenance import provenance_from_identity
from mechcad_harness.materials import MaterialDataAuthority, MaterialMassInput, MaterialMassResult, MaterialPropertyName, MaterialPropertyStatus, MaterialPropertyValue, TypicalMaterialPropertiesInput, TypicalMaterialPropertiesResult

BD_MATERIALS_VERSION = "0.2.4"

PROPERTY_UNITS = {
    "density": "kg/m^3", "modulus_of_elasticity": "GPa", "poisson_ratio": "ratio", "yield_strength": "MPa", "tensile_strength": "MPa", "shear_strength": "MPa", "elongation_at_break": "%", "max_service_temp": "degC", "glass_transition_temperature": "degC", "heat_deflection_temperature": "degC",
}
PROPERTY_NAMES = {item.value: item for item in MaterialPropertyName}


class BdMaterialsAdapter:
    identity = BackendIdentity(name="bd-materials", adapter_version="0.1.0", library_name="bd_materials", library_version=BD_MATERIALS_VERSION, library_source="pypi", capabilities=("material.typical_properties",))

    def healthcheck(self):
        try:
            version = metadata.version("bd-materials")
            if Version(version) != Version(BD_MATERIALS_VERSION):
                return BackendHealth(backend_name=self.identity.name, status=BackendHealthStatus.INCOMPATIBLE, detected_version=version, message="unsupported bd_materials version")
            metadata.version("threejs-materials")
            metadata.version("webcolors")
            return BackendHealth(backend_name=self.identity.name, status=BackendHealthStatus.AVAILABLE, detected_version=version, message="validated bd_materials dependency profile detected")
        except metadata.PackageNotFoundError as exc:
            return BackendHealth(backend_name=self.identity.name, status=BackendHealthStatus.UNAVAILABLE, message=f"missing material dependency: {exc}")
        except Exception as exc:
            return BackendHealth(backend_name=self.identity.name, status=BackendHealthStatus.INCOMPATIBLE, message=f"material dependency check failed: {type(exc).__name__}: {exc}")

    def _ensure_available(self):
        health = self.healthcheck()
        if health.status is BackendHealthStatus.UNAVAILABLE:
            raise BackendUnavailableError(health.message or "bd_materials is unavailable")
        if health.status is not BackendHealthStatus.AVAILABLE:
            raise BackendCompatibilityError(health.message or "bd_materials is incompatible")

    def provenance(self):
        self._ensure_available()
        return provenance_from_identity(self.identity, library_version=metadata.version("bd-materials"))

    def typical_properties(self, value: TypicalMaterialPropertiesInput):
        self._ensure_available()
        try:
            from bd_materials import canonical_name, resolve

            external = resolve(value.material_id)
            material = external.material
            canonical = canonical_name(external)
            warnings = () if canonical == value.material_id else (f"material alias resolved to canonical identity: {canonical}",)
            properties = {}
            for property_name, normalized_name in (("modulus_of_elasticity", "elastic_modulus"), ("poisson_ratio", "poisson_ratio"), ("yield_strength", "yield_strength"), ("tensile_strength", "tensile_strength"), ("shear_strength", "shear_strength"), ("elongation_at_break", "elongation_at_break"), ("max_service_temp", "service_temperature"), ("glass_transition_temperature", "glass_transition_temperature"), ("heat_deflection_temperature", "heat_deflection_temperature")):
                properties[normalized_name] = self._normalize_property(normalized_name, getattr(material, property_name, None))
            density = self._normalize_property("density", material.density, representative=True)
            return TypicalMaterialPropertiesResult(canonical_name=canonical, display_name=material.name, category=str(material.category), family=str(material.family), authority=MaterialDataAuthority.TYPICAL_REFERENCE, density=density, properties=properties, backend_provenance=self.provenance(), warnings=warnings)
        except (BackendUnavailableError, BackendCompatibilityError):
            raise
        except Exception as exc:
            raise BackendCompatibilityError(f"bd_materials lookup failed: {type(exc).__name__}: {exc}") from exc

    def _normalize_property(self, name, value, *, representative=False):
        unit = PROPERTY_UNITS["density" if name == "density" else {"elastic_modulus": "modulus_of_elasticity", "service_temperature": "max_service_temp"}.get(name, name)]
        if value is None:
            return MaterialPropertyValue(property=PROPERTY_NAMES[name], unit=unit, status=MaterialPropertyStatus.MISSING, authority=MaterialDataAuthority.TYPICAL_REFERENCE, source="bd_materials")
        minimum = float(getattr(value, "min", value))
        maximum = float(getattr(value, "max", value))
        if not isfinite(minimum) or not isfinite(maximum):
            return MaterialPropertyValue(property=PROPERTY_NAMES[name], unit=unit, status=MaterialPropertyStatus.NOT_SUITABLE, authority=MaterialDataAuthority.TYPICAL_REFERENCE, source="bd_materials")
        return MaterialPropertyValue(property=PROPERTY_NAMES[name], unit=unit, status=MaterialPropertyStatus.AVAILABLE, min_value=minimum, max_value=maximum, representative_value=minimum if representative else None, authority=MaterialDataAuthority.TYPICAL_REFERENCE, source="bd_materials", value_semantics="representative" if representative else None)

    def mass(self, value: MaterialMassInput):
        result = self.typical_properties(TypicalMaterialPropertiesInput(material_id=value.material_id))
        density = result.density.representative_value
        if density is None:
            raise BackendCompatibilityError("material density is unavailable")
        return MaterialMassResult(mass_g=value.volume_mm3 * density * 1e-6, volume_mm3=value.volume_mm3, density=result.density, authority=MaterialDataAuthority.TYPICAL_REFERENCE, backend_provenance=result.backend_provenance)
