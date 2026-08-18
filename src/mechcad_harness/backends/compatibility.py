from importlib import metadata

from packaging.version import InvalidVersion, Version

from .errors import BackendCompatibilityError
from .models import BackendHealth, BackendHealthStatus


TRUSTED_DISTRIBUTIONS = {
    "py_gearworks": "py_gearworks",
    "build123d": "build123d",
    "bd_materials": "bd_materials",
    "sectionproperties": "sectionproperties",
    "numpy": "numpy",
    "scipy": "scipy",
    "setuptools": "setuptools",
}


def inspect_distribution(library_name: str) -> BackendHealth:
    distribution = TRUSTED_DISTRIBUTIONS.get(library_name)
    if distribution is None:
        raise BackendCompatibilityError(f"untrusted library name: {library_name}")
    try:
        version = metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return BackendHealth(backend_name=library_name, status=BackendHealthStatus.UNAVAILABLE, message="distribution is not installed")
    return BackendHealth(backend_name=library_name, status=BackendHealthStatus.AVAILABLE, detected_version=version, message="distribution metadata found")


def inspect_validated_gear_profile() -> BackendHealth:
    required = ("py_gearworks", "build123d", "numpy", "scipy")
    versions = {}
    for name in required:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            return BackendHealth(backend_name="py-gearworks", status=BackendHealthStatus.UNAVAILABLE, message=f"distribution is not installed: {name}")
    try:
        supported = (
            versions["py_gearworks"] == "0.0.18"
            and versions["build123d"] == "0.11.1"
            and Version("2") <= Version(versions["numpy"]) < Version("2.4")
            and Version(versions["scipy"]) >= Version("1.10.1")
        )
    except InvalidVersion as exc:
        return BackendHealth(backend_name="py-gearworks", status=BackendHealthStatus.INCOMPATIBLE, message=f"invalid dependency version: {exc}")
    if not supported:
        return BackendHealth(backend_name="py-gearworks", status=BackendHealthStatus.INCOMPATIBLE, detected_version=versions["py_gearworks"], message=f"validated gear profile mismatch: {versions}")
    return BackendHealth(backend_name="py-gearworks", status=BackendHealthStatus.AVAILABLE, detected_version=versions["py_gearworks"], message=f"validated gear profile: {versions}")
