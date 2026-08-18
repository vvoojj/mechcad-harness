from importlib import metadata
from math import isfinite, pi

from mechcad_harness.backends.compatibility import inspect_validated_gear_profile
from mechcad_harness.backends.errors import BackendCompatibilityError, BackendUnavailableError
from mechcad_harness.backends.models import BackendHealth, BackendHealthStatus, BackendIdentity
from mechcad_harness.backends.provenance import provenance_from_identity

PY_GEARWORKS_REVISION = "2fc2a13d82a9997a65f30c870498f0bb3be62318"
PY_GEARWORKS_SOURCE = "https://github.com/GarryBGoode/py_gearworks.git"
PY_GEARWORKS_VERSION = "0.0.18"
BUILD123D_VERSION = "0.11.1"
NUMPY_MIN_VERSION = "2"
NUMPY_MAX_VERSION = "2.4"


def _require_finite(value: float, name: str) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")


class PyGearworksAdapter:
    identity = BackendIdentity(
        name="py-gearworks",
        adapter_version="0.1.0",
        library_name="py_gearworks",
        library_source="git",
        library_revision=PY_GEARWORKS_REVISION,
        capabilities=("gear.geometry.spur", "gear.geometry.pair"),
    )

    def healthcheck(self) -> BackendHealth:
        health = inspect_validated_gear_profile()
        return health.model_copy(update={"backend_name": self.identity.name})

    def _ensure_available(self):
        health = self.healthcheck()
        if health.status is BackendHealthStatus.UNAVAILABLE:
            raise BackendUnavailableError(health.message or "py_gearworks is unavailable")
        if health.status is not BackendHealthStatus.AVAILABLE:
            raise BackendCompatibilityError(health.message or "py_gearworks is incompatible")

    def provenance(self):
        self._ensure_available()
        return provenance_from_identity(self.identity, library_version=metadata.version("py_gearworks"))

    def spur_geometry(self, value):
        self._ensure_available()
        try:
            from py_gearworks import SpurGear

            if value.internal:
                raise ValueError("internal spur gears are not supported by this adapter")

            gear = SpurGear(
                number_of_teeth=value.teeth,
                height=value.face_width_mm,
                module=value.module_mm,
                pressure_angle=value.pressure_angle_deg * pi / 180,
                profile_shift=value.profile_shift,
            )
            return gear, {
                "addendum_radius_mm": float(gear.addendum_radius),
                "dedendum_radius_mm": float(gear.dedendum_radius),
                "base_radius_mm": float(gear.r_base),
            }
        except Exception as exc:
            raise BackendCompatibilityError(f"py_gearworks spur geometry failed: {type(exc).__name__}: {exc}") from exc

    def spur_pair(self, value):
        self._ensure_available()
        try:
            from py_gearworks import RIGHT, SpurGear

            pinion = SpurGear(number_of_teeth=value.pinion_teeth, height=value.face_width_mm, module=value.module_mm, pressure_angle=value.pressure_angle_deg * pi / 180, profile_shift=value.pinion_profile_shift)
            gear = SpurGear(number_of_teeth=value.gear_teeth, height=value.face_width_mm, module=value.module_mm, pressure_angle=value.pressure_angle_deg * pi / 180, profile_shift=value.gear_profile_shift)
            gear.mesh_to(pinion, target_dir=RIGHT)
            actual_center = float(((gear.center - pinion.center) ** 2).sum() ** 0.5)
            return pinion, gear, actual_center
        except Exception as exc:
            raise BackendCompatibilityError(f"py_gearworks spur pair failed: {type(exc).__name__}: {exc}") from exc
