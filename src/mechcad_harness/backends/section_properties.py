from importlib import metadata
from math import isfinite

from packaging.version import InvalidVersion, Version

from mechcad_harness.sections import CircleSectionInput, HollowCircleSectionInput, RectangleSectionInput, SectionGeometryResult, SectionWarpingResult

from .errors import BackendCompatibilityError, BackendUnavailableError
from .models import BackendHealth, BackendHealthStatus, BackendIdentity
from .provenance import provenance_from_identity


SECTION_PROPERTIES_VERSION = "3.10.2"
NUMPY_MIN_VERSION = "2"
NUMPY_MAX_VERSION = "2.4"
REQUIRED_DISTRIBUTIONS = (
    "sectionproperties",
    "numpy",
    "scipy",
    "matplotlib",
    "shapely",
    "cytriangle",
    "more-itertools",
    "rich",
)


class SectionPropertiesAdapter:
    identity = BackendIdentity(
        name="section-properties",
        adapter_version="0.2.0",
        library_name="sectionproperties",
        library_version=SECTION_PROPERTIES_VERSION,
        library_source="pypi",
        capabilities=("structural.cross_section.geometry", "structural.cross_section.warping"),
    )

    def healthcheck(self) -> BackendHealth:
        versions = {}
        for distribution in REQUIRED_DISTRIBUTIONS:
            try:
                versions[distribution] = metadata.version(distribution)
            except metadata.PackageNotFoundError:
                return BackendHealth(
                    backend_name=self.identity.name,
                    status=BackendHealthStatus.UNAVAILABLE,
                    message=f"distribution is not installed: {distribution}",
                )
        try:
            supported = (
                Version(versions["sectionproperties"]) == Version(SECTION_PROPERTIES_VERSION)
                and Version(NUMPY_MIN_VERSION) <= Version(versions["numpy"]) < Version(NUMPY_MAX_VERSION)
            )
        except InvalidVersion as exc:
            return BackendHealth(
                backend_name=self.identity.name,
                status=BackendHealthStatus.INCOMPATIBLE,
                message=f"invalid dependency version: {exc}",
            )
        if not supported:
            return BackendHealth(
                backend_name=self.identity.name,
                status=BackendHealthStatus.INCOMPATIBLE,
                detected_version=versions["sectionproperties"],
                message=f"validated structural profile mismatch: {versions}",
            )
        return BackendHealth(
            backend_name=self.identity.name,
            status=BackendHealthStatus.AVAILABLE,
            detected_version=versions["sectionproperties"],
            message=f"validated structural profile: {versions}",
        )

    def provenance(self):
        self._ensure_available()
        return provenance_from_identity(self.identity, library_version=metadata.version("sectionproperties"))

    def rectangle(self, value: RectangleSectionInput) -> SectionGeometryResult:
        self._ensure_available()
        try:
            from sectionproperties.analysis import Section
            from sectionproperties.pre.library import rectangular_section

            geometry = rectangular_section(d=value.height_mm, b=value.width_mm)
            geometry.create_mesh(mesh_sizes=value.mesh_size_mm2)
            section = Section(geometry)
            return self._analyze(section, "rectangle", value.mesh_size_mm2)
        except (BackendUnavailableError, BackendCompatibilityError):
            raise
        except Exception as exc:
            raise BackendCompatibilityError(f"sectionproperties rectangle analysis failed: {type(exc).__name__}: {exc}") from exc

    def circle(self, value: CircleSectionInput) -> SectionGeometryResult:
        self._ensure_available()
        try:
            from sectionproperties.analysis import Section
            from sectionproperties.pre.library import circular_section

            geometry = circular_section(d=value.diameter_mm, n=value.discretization_points)
            geometry.create_mesh(mesh_sizes=value.mesh_size_mm2)
            section = Section(geometry)
            return self._analyze(section, "circle", value.mesh_size_mm2, value.discretization_points)
        except (BackendUnavailableError, BackendCompatibilityError):
            raise
        except Exception as exc:
            raise BackendCompatibilityError(f"sectionproperties circle analysis failed: {type(exc).__name__}: {exc}") from exc

    def hollow_circle(self, value: HollowCircleSectionInput) -> SectionGeometryResult:
        self._ensure_available()
        try:
            from sectionproperties.analysis import Section
            from sectionproperties.pre.library import circular_hollow_section

            geometry = circular_hollow_section(
                d=value.outer_diameter_mm,
                t=value.wall_thickness_mm,
                n=value.discretization_points,
            )
            geometry.create_mesh(mesh_sizes=value.mesh_size_mm2)
            section = Section(geometry)
            return self._analyze(section, "hollow_circle", value.mesh_size_mm2, value.discretization_points)
        except (BackendUnavailableError, BackendCompatibilityError):
            raise
        except Exception as exc:
            raise BackendCompatibilityError(f"sectionproperties hollow-circle analysis failed: {type(exc).__name__}: {exc}") from exc

    def rectangle_warping(self, value: RectangleSectionInput) -> SectionWarpingResult:
        return self._warping(value, "rectangle")

    def circle_warping(self, value: CircleSectionInput) -> SectionWarpingResult:
        return self._warping(value, "circle")

    def hollow_circle_warping(self, value: HollowCircleSectionInput) -> SectionWarpingResult:
        return self._warping(value, "hollow_circle")

    @staticmethod
    def _validate_solver_type(solver_type: str) -> str:
        if solver_type != "direct":
            raise ValueError("only the direct solver is supported")
        return solver_type

    @staticmethod
    def _warping_tolerances():
        return {
            "j_relative": 1e-3,
            "gamma_relative": 1e-3,
            "gamma_absolute": 1e-6,
            "shear_area_relative": 1e-3,
            "shear_center_absolute_mm": 1e-4,
        }

    def _warping(self, value, section_type: str) -> SectionWarpingResult:
        self._ensure_available()
        self._validate_solver_type("direct")
        coarse_size = float(value.mesh_size_mm2)
        fine_size = coarse_size / 4
        try:
            coarse = self._calculate_warping_level(value, section_type, coarse_size, "direct")
            fine = self._calculate_warping_level(value, section_type, fine_size, "direct")
            tolerances = self._warping_tolerances()
            j_delta = abs(fine["j"] - coarse["j"])
            j_relative = j_delta / max(abs(fine["j"]), 1e-30)
            gamma_delta = abs(fine["gamma"] - coarse["gamma"])
            gamma_relative = gamma_delta / max(abs(fine["gamma"]), 1e-30)
            as_x_relative = abs(fine["as_x"] - coarse["as_x"]) / max(abs(fine["as_x"]), 1e-30)
            as_y_relative = abs(fine["as_y"] - coarse["as_y"]) / max(abs(fine["as_y"]), 1e-30)
            centroid_x, centroid_y = self._centroid_for_input(value, section_type)
            sc_x_absolute = abs(fine["sc_x"] - centroid_x)
            sc_y_absolute = abs(fine["sc_y"] - centroid_y)
            converged = (
                j_relative <= tolerances["j_relative"]
                and (gamma_relative <= tolerances["gamma_relative"] or gamma_delta <= tolerances["gamma_absolute"])
                and as_x_relative <= tolerances["shear_area_relative"]
                and as_y_relative <= tolerances["shear_area_relative"]
                and sc_x_absolute <= tolerances["shear_center_absolute_mm"]
                and sc_y_absolute <= tolerances["shear_center_absolute_mm"]
            )
            convergence = {
                "solver_type": "direct",
                "coarse_mesh_size_mm2": coarse_size,
                "fine_mesh_size_mm2": fine_size,
                "coarse": coarse,
                "fine": fine,
                "j_absolute_difference": j_delta,
                "j_relative_difference": j_relative,
                "gamma_absolute_difference": gamma_delta,
                "gamma_relative_difference": gamma_relative,
                "shear_area_x_relative_difference": as_x_relative,
                "shear_area_y_relative_difference": as_y_relative,
                "shear_center_x_absolute_difference_mm": sc_x_absolute,
                "shear_center_y_absolute_difference_mm": sc_y_absolute,
                "j_relative_tolerance": tolerances["j_relative"],
                "gamma_relative_tolerance": tolerances["gamma_relative"],
                "gamma_absolute_tolerance": tolerances["gamma_absolute"],
                "shear_area_relative_tolerance": tolerances["shear_area_relative"],
                "shear_center_absolute_tolerance_mm": tolerances["shear_center_absolute_mm"],
                "converged": converged,
            }
            if not converged:
                raise BackendCompatibilityError(
                    f"section warping convergence failed: property=J coarse={coarse['j']} fine={fine['j']} delta={j_delta} tolerance={tolerances['j_relative']}"
                )
            metadata = {"mesh_size_mm2": fine_size}
            if hasattr(value, "discretization_points"):
                metadata["discretization_points"] = value.discretization_points
            return SectionWarpingResult(
                section_type=section_type,
                torsion_constant_j_mm4=float(fine["j"]),
                shear_center_x_mm=float(fine["sc_x"]),
                shear_center_y_mm=float(fine["sc_y"]),
                shear_area_x_mm2=float(fine["as_x"]),
                shear_area_y_mm2=float(fine["as_y"]),
                warping_constant_mm6=float(fine["gamma"]),
                solver_type="direct",
                mesh_metadata=metadata,
                convergence_metadata=convergence,
                backend_provenance=self.provenance(),
            )
        except (BackendUnavailableError, BackendCompatibilityError):
            raise
        except Exception as exc:
            raise BackendCompatibilityError(f"sectionproperties warping analysis failed: {type(exc).__name__}: {exc}") from exc

    def _calculate_warping_level(self, value, section_type: str, mesh_size_mm2: float, solver_type: str):
        from sectionproperties.analysis import Section
        from sectionproperties.pre.library import circular_hollow_section, circular_section, rectangular_section

        if section_type == "rectangle":
            geometry = rectangular_section(d=value.height_mm, b=value.width_mm)
        elif section_type == "circle":
            geometry = circular_section(d=value.diameter_mm, n=value.discretization_points)
        elif section_type == "hollow_circle":
            geometry = circular_hollow_section(d=value.outer_diameter_mm, t=value.wall_thickness_mm, n=value.discretization_points)
        else:
            raise ValueError(f"unsupported section type: {section_type}")
        geometry.create_mesh(mesh_sizes=mesh_size_mm2)
        section = Section(geometry)
        section.calculate_geometric_properties()
        section.calculate_warping_properties(solver_type=solver_type)
        j = float(section.get_j())
        sc_x, sc_y = map(float, section.get_sc())
        as_x, as_y = map(float, section.get_as())
        gamma = float(section.get_gamma())
        values = (j, sc_x, sc_y, as_x, as_y, gamma)
        if any(not isfinite(item) for item in values):
            raise BackendCompatibilityError("sectionproperties returned a non-finite warping property")
        return {"j": j, "sc_x": sc_x, "sc_y": sc_y, "as_x": as_x, "as_y": as_y, "gamma": gamma, "nodes": section.num_nodes, "elements": len(section.elements)}

    @staticmethod
    def _centroid_for_input(value, section_type: str):
        if section_type == "rectangle":
            return value.width_mm / 2, value.height_mm / 2
        return 0.0, 0.0

    def _ensure_available(self):
        health = self.healthcheck()
        if health.status is BackendHealthStatus.UNAVAILABLE:
            raise BackendUnavailableError(health.message or "sectionproperties is unavailable")
        if health.status is not BackendHealthStatus.AVAILABLE:
            raise BackendCompatibilityError(health.message or "sectionproperties is incompatible")

    def _analyze(self, section, section_type: str, mesh_size_mm2: float, discretization_points: int | None = None):
        section.calculate_geometric_properties()
        area = section.get_area()
        cx, cy = section.get_c()
        ixx, iyy, ixy = section.get_ic()
        perimeter = section.get_perimeter()
        rc_x, rc_y = section.get_rc()
        values = (area, cx, cy, ixx, iyy, ixy, perimeter, rc_x, rc_y)
        if any(not isfinite(float(value)) for value in values):
            raise BackendCompatibilityError("sectionproperties returned a non-finite geometric property")
        metadata_payload = {"mesh_size_mm2": float(mesh_size_mm2)}
        if discretization_points is not None:
            metadata_payload["discretization_points"] = discretization_points
        return SectionGeometryResult(
            section_type=section_type,
            area_mm2=float(area),
            centroid_x_mm=float(cx),
            centroid_y_mm=float(cy),
            ixx_centroid_mm4=float(ixx),
            iyy_centroid_mm4=float(iyy),
            ixy_centroid_mm4=float(ixy),
            perimeter_mm=float(perimeter),
            radius_of_gyration_x_mm=float(rc_x),
            radius_of_gyration_y_mm=float(rc_y),
            mesh_metadata=metadata_payload,
            backend_provenance=self.provenance(),
        )
