from __future__ import annotations

import math
from typing import Literal

from mechcad_harness.candidates.models import (
    ComponentPropertyAvailability,
    ComponentSpecificationSnapshot,
)
from mechcad_harness.engineering.spur import calculate_nominal_spur
from mechcad_harness.revolute_drive.models import (
    ConsumedPropertyBinding,
    DriveArchitecture,
    EngineeringCheck,
    EngineeringCheckStatus,
    RevoluteDriveEngineeringRequirements,
    RevoluteDriveModel,
)


EXTERNAL_SPUR_KIND = "external_spur"

_DESIGN_TORQUE_PATH = "/requirements/design_load_case/design_torque"
_FORCE_Y_PATH = "/requirements/design_load_case/transverse_force_y"
_FORCE_Z_PATH = "/requirements/design_load_case/transverse_force_z"
_SUPPORT_GEOMETRY_PATH = "/requirements/shaft_support_geometry"

_FORCE_RESIDUAL_TOLERANCE_N = 1e-9
_MOMENT_RESIDUAL_TOLERANCE_N_MM = 1e-9
_STRESS_ABSOLUTE_TOLERANCE_MPA = 1e-9
_STRESS_RELATIVE_TOLERANCE = 1e-12


class SpurPairEvaluation(RevoluteDriveModel):
    schema_version: Literal["revolute-drive-spur-pair-evaluation@1"] = "revolute-drive-spur-pair-evaluation@1"
    ratio_magnitude: float | None = None
    pitch_diameter_driver_mm: float | None = None
    pitch_diameter_driven_mm: float | None = None
    center_distance_mm: float | None = None
    output_speed_rpm: float | None = None
    output_continuous_torque_nm: float | None = None
    output_peak_torque_nm: float | None = None
    compatibility_check: EngineeringCheck
    speed_check: EngineeringCheck
    torque_check: EngineeringCheck


class SpurMeshLoadResult(RevoluteDriveModel):
    schema_version: Literal["revolute-drive-spur-mesh-loads@1"] = "revolute-drive-spur-mesh-loads@1"
    transmitted_torque_n_mm: float
    tangential_force_n: float
    radial_force_n: float


class ShaftStaticSizingResult(RevoluteDriveModel):
    schema_version: Literal["revolute-drive-shaft-static-sizing@1"] = "revolute-drive-shaft-static-sizing@1"
    reaction_a_y_n: float | None = None
    reaction_b_y_n: float | None = None
    reaction_a_z_n: float | None = None
    reaction_b_z_n: float | None = None
    force_residual_y_n: float | None = None
    force_residual_z_n: float | None = None
    moment_residual_y_n_mm: float | None = None
    moment_residual_z_n_mm: float | None = None
    maximum_bending_moment_n_mm: float | None = None
    bending_stress_mpa: float | None = None
    torsional_stress_mpa: float | None = None
    von_mises_stress_mpa: float | None = None
    allowable_stress_mpa: float | None = None
    stress_tolerance_mpa: float | None = None
    minimum_diameter_mm: float | None = None
    equilibrium_check: EngineeringCheck
    stress_check: EngineeringCheck


def _positive_finite_argument(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be a finite number")
    if numeric <= 0:
        raise ValueError(f"{name} must be strictly positive")
    return numeric


def _nonnegative_finite_argument(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite nonnegative number")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")
    return numeric


def _validated_spur_drive_ratio(ratio_magnitude: object) -> float:
    if isinstance(ratio_magnitude, bool) or not isinstance(ratio_magnitude, (int, float)):
        raise ValueError("ratio_magnitude must be a finite positive number")
    numeric = float(ratio_magnitude)
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueError("ratio_magnitude must be a finite positive number")
    return numeric


def _validated_drive_efficiency(efficiency: object) -> float:
    if isinstance(efficiency, bool) or not isinstance(efficiency, (int, float)):
        raise ValueError("efficiency must be a finite number in (0, 1]")
    numeric = float(efficiency)
    if not math.isfinite(numeric):
        raise ValueError("efficiency must be a finite number in (0, 1]")
    if not 0 < numeric <= 1:
        raise ValueError("efficiency must lie in (0, 1]")
    return numeric


def _validated_speed_range(speed_min: float | None, speed_max: float | None) -> None:
    if speed_min is not None and speed_max is not None and speed_min > speed_max:
        raise ValueError("motor speed range must satisfy speed_min_rpm <= speed_max_rpm")


class _Verdict:
    def __init__(self) -> None:
        self._violations: list[str] = []
        self._unresolved: list[str] = []

    def violate(self, reason: str) -> None:
        self._violations.append(reason)

    def unresolved(self, reason: str) -> None:
        self._unresolved.append(reason)

    @property
    def status(self) -> EngineeringCheckStatus:
        if self._violations:
            return EngineeringCheckStatus.VIOLATED
        if self._unresolved:
            return EngineeringCheckStatus.UNRESOLVED
        return EngineeringCheckStatus.SATISFIED

    @property
    def reason(self) -> str | None:
        reasons = tuple(self._violations) + tuple(self._unresolved)
        return "; ".join(reasons) if reasons else None


def _check(check_id: str, verdict: _Verdict, bindings=(), paths=()) -> EngineeringCheck:
    return EngineeringCheck(
        check_id=check_id,
        status=verdict.status,
        reason=verdict.reason,
        consumed_property_bindings=tuple(bindings),
        consumed_requirement_paths=tuple(paths),
    )


def _numeric_property(
    specification: ComponentSpecificationSnapshot,
    instance_id: str,
    key: str,
    expected_unit: str,
) -> tuple[ConsumedPropertyBinding | None, float | None, str | None]:
    """Resolve one scalar property, returning (binding, value, defect_reason).

    A missing key yields (None, None, None). A declared but unusable property
    yields its binding with value None plus a defect reason so the caller can
    record UNRESOLVED. A wrong canonical unit is a malformed schema.
    """
    matches = [prop for prop in specification.properties if prop.key == key]
    if not matches:
        return None, None, None
    prop = matches[0]
    binding = ConsumedPropertyBinding(
        component_instance_id=instance_id,
        specification_hash=specification.specification_hash,
        property_key=prop.key,
        property_hash=prop.property_hash,
        source_identity=prop.source_identity,
        authority=prop.authority,
    )
    if prop.availability is not ComponentPropertyAvailability.AVAILABLE:
        return binding, None, f"{key} is declared {prop.availability.value}"
    if prop.normalized_value is None or prop.normalized_range is not None:
        return binding, None, f"{key} must declare a single normalized value"
    if prop.canonical_unit != expected_unit:
        raise ValueError(f"{key} must use {expected_unit}, found {prop.canonical_unit!r}")
    return binding, prop.normalized_value, None


def _gear_kind_declared(specification: ComponentSpecificationSnapshot) -> tuple[bool, bool]:
    kinds = [declaration for declaration in specification.compatibility_declarations if declaration.endswith("_spur")]
    return EXTERNAL_SPUR_KIND in kinds, len(kinds) > 0


def evaluate_motor_checks(
    requirements: RevoluteDriveEngineeringRequirements,
    motor_specification: ComponentSpecificationSnapshot,
    *,
    motor_instance_id: str = "motor",
    architecture: DriveArchitecture = DriveArchitecture.DIRECT_DRIVE,
    ratio_magnitude: float | None = None,
    efficiency: float | None = None,
    include_speed_check: bool = True,
) -> tuple[EngineeringCheck, ...]:
    """Evaluate motor capability against the requirement transferred to the motor side.

    DIRECT_DRIVE requires T_motor >= the output-shaft base value directly.
    EXTERNAL_SPUR_REDUCTION reduces the base value through the nominal mesh:
    required_at_motor = base / (i * eta). An absent efficiency leaves the real
    torque-transfer/motor-capability requirement UNRESOLVED while kinematic
    (speed) and voltage checks stay independently evaluated.
    """
    drive_ratio: float | None = None
    drive_eta: float | None = None
    transfer_unresolved: str | None = None
    if architecture is DriveArchitecture.EXTERNAL_SPUR_REDUCTION:
        if ratio_magnitude is None:
            raise ValueError("external spur reduction evaluation requires an explicit ratio magnitude")
        drive_ratio = _validated_spur_drive_ratio(ratio_magnitude)
        if efficiency is None:
            transfer_unresolved = (
                "mesh efficiency is not supplied; the real torque-transfer/motor-capability "
                "requirement cannot be established"
            )
        else:
            drive_eta = _validated_drive_efficiency(efficiency)

    design_torque = requirements.design_load_case.design_torque.value

    def required_at_motor(base: float) -> float:
        if drive_eta is None:
            return base
        return base / (drive_ratio * drive_eta)

    checks: list[EngineeringCheck] = []

    torque_verdict = _Verdict()
    torque_paths = [_DESIGN_TORQUE_PATH]
    binding, continuous_torque, defect = _numeric_property(
        motor_specification,
        motor_instance_id,
        "motor.continuous_torque_nm",
        "N*m",
    )
    if binding is None:
        torque_verdict.unresolved("motor.continuous_torque_nm property is missing")
    elif defect is not None:
        torque_verdict.unresolved(defect)
    if drive_eta is not None:
        torque_paths.append("/requirements/efficiency")
    if transfer_unresolved is not None:
        torque_verdict.unresolved(transfer_unresolved)
    elif continuous_torque is not None and defect is None:
        required_continuous = required_at_motor(design_torque)
        if continuous_torque <= 0:
            torque_verdict.violate("motor continuous torque must be strictly positive")
        elif continuous_torque >= required_continuous:
            pass
        else:
            torque_verdict.violate(
                f"motor continuous torque {continuous_torque} N*m falls short of the motor-side "
                f"design requirement {required_continuous} N*m"
            )
    checks.append(_check("motor-continuous-torque", torque_verdict, (() if binding is None else (binding,)), tuple(torque_paths)))

    required_peak = requirements.required_peak_torque
    if required_peak is not None:
        peak_paths = ["/requirements/required_peak_torque"]
        peak_verdict = _Verdict()
        peak_binding, peak_torque, peak_defect = _numeric_property(
            motor_specification,
            motor_instance_id,
            "motor.peak_torque_nm",
            "N*m",
        )
        if peak_binding is None:
            peak_verdict.unresolved("motor.peak_torque_nm property is missing")
        elif peak_defect is not None:
            peak_verdict.unresolved(peak_defect)
        if drive_eta is not None:
            peak_paths.append("/requirements/efficiency")
        if transfer_unresolved is not None:
            peak_verdict.unresolved(transfer_unresolved)
        elif peak_torque is not None and peak_defect is None:
            required_peak_at_motor = required_at_motor(required_peak.value)
            if peak_torque <= 0:
                peak_verdict.violate("motor peak torque must be strictly positive")
            elif peak_torque >= required_peak_at_motor:
                pass
            else:
                peak_verdict.violate(
                    f"motor peak torque {peak_torque} N*m falls short of the motor-side peak "
                    f"requirement {required_peak_at_motor} N*m"
                )
        checks.append(_check("motor-peak-torque", peak_verdict, (() if peak_binding is None else (peak_binding,)), tuple(peak_paths)))

    if include_speed_check:
        speed_verdict = _Verdict()
        min_binding, speed_min, min_defect = _numeric_property(motor_specification, motor_instance_id, "motor.speed_min_rpm", "rpm")
        max_binding, speed_max, max_defect = _numeric_property(motor_specification, motor_instance_id, "motor.speed_max_rpm", "rpm")
        consumed_speed_bindings = tuple(
            binding for binding in (min_binding, max_binding) if binding is not None
        )
        if min_binding is None or max_binding is None:
            missing = [
                key
                for key, present in (("motor.speed_min_rpm", min_binding), ("motor.speed_max_rpm", max_binding))
                if present is None
            ]
            speed_verdict.unresolved(f"{', '.join(missing)} properties are missing")
        else:
            defects = [d for d in (min_defect, max_defect) if d is not None]
            if defects:
                speed_verdict.unresolved("; ".join(defects))
            if speed_min is not None and speed_max is not None:
                _validated_speed_range(speed_min, speed_max)
                if speed_min < 0 or speed_max < 0:
                    speed_verdict.violate("motor usable speed bounds must be nonnegative magnitudes")
                required_speed = requirements.required_output_speed.value
                if required_speed < speed_min or required_speed > speed_max:
                    speed_verdict.violate(
                        f"required output speed {required_speed} rpm lies outside the authoritative usable range "
                        f"[{speed_min}, {speed_max}] rpm"
                    )
            consumed_speed_bindings = (min_binding, max_binding)
        checks.append(_check("motor-speed", speed_verdict, consumed_speed_bindings, ("/requirements/required_output_speed",)))

    required_voltage = requirements.required_voltage
    if required_voltage is not None:
        voltage_verdict = _Verdict()
        voltage_binding, rated_voltage, voltage_defect = _numeric_property(
            motor_specification,
            motor_instance_id,
            "motor.rated_voltage_v",
            "V",
        )
        if voltage_binding is None:
            voltage_verdict.unresolved("motor.rated_voltage_v property is missing")
        elif voltage_defect is not None:
            voltage_verdict.unresolved(voltage_defect)
        elif rated_voltage != required_voltage.value:
            voltage_verdict.violate(
                f"motor rated voltage {rated_voltage} V does not equal the required voltage {required_voltage.value} V"
            )
        checks.append(_check("motor-voltage", voltage_verdict, (() if voltage_binding is None else (voltage_binding,)), ("/requirements/required_voltage",)))

    return tuple(checks)


def evaluate_spur_pair(
    requirements: RevoluteDriveEngineeringRequirements,
    motor_specification: ComponentSpecificationSnapshot,
    driver_gear_specification: ComponentSpecificationSnapshot,
    driven_gear_specification: ComponentSpecificationSnapshot,
    motor_speed_rpm: float | None = None,
    *,
    motor_instance_id: str = "motor",
    driver_gear_instance_id: str = "driver_gear",
    driven_gear_instance_id: str = "driven_gear",
) -> SpurPairEvaluation:
    compatibility = _Verdict()
    compat_bindings: list[ConsumedPropertyBinding] = []
    gears = (
        ("driver gear", driver_gear_specification, driver_gear_instance_id),
        ("driven gear", driven_gear_specification, driven_gear_instance_id),
    )

    for label, specification, _ in gears:
        is_external, has_kind = _gear_kind_declared(specification)
        if not is_external:
            if has_kind:
                compatibility.violate(f"{label} declares a non-external spur kind, contradicting the external spur architecture")
            else:
                compatibility.unresolved(f"{label} declares no recognizable spur kind")

    module_results = [(label,) + _numeric_property(specification, instance_id, "gear.module_mm", "mm") for label, specification, instance_id in gears]
    teeth_results = [(label,) + _numeric_property(specification, instance_id, "gear.tooth_count", "1") for label, specification, instance_id in gears]
    angle_results = [(label,) + _numeric_property(specification, instance_id, "gear.pressure_angle_deg", "deg") for label, specification, instance_id in gears]
    face_width_results = [(label,) + _numeric_property(specification, instance_id, "gear.face_width_mm", "mm") for label, specification, instance_id in gears]

    module_values: list[float] = []
    teeth_values: list[int] = []
    angle_values: list[float] = []

    for label, binding, value, defect in module_results:
        if binding is not None:
            compat_bindings.append(binding)
        if binding is None:
            compatibility.unresolved("gear.module_mm is missing on one or both gear snapshots")
        elif defect is not None:
            compatibility.unresolved(defect)
        elif value <= 0:
            compatibility.violate(f"{label} module must be strictly positive")
        else:
            module_values.append(value)

    for label, binding, value, defect in teeth_results:
        if binding is not None:
            compat_bindings.append(binding)
        if binding is None:
            compatibility.unresolved("gear.tooth_count is missing on one or both gear snapshots")
        elif defect is not None:
            compatibility.unresolved(defect)
        elif value <= 0 or not float(value).is_integer():
            compatibility.violate(f"{label} tooth count must be a positive integer")
        else:
            teeth_values.append(int(value))

    for label, binding, value, defect in angle_results:
        if binding is not None:
            compat_bindings.append(binding)
        if binding is None:
            compatibility.unresolved("gear.pressure_angle_deg is missing on one or both gear snapshots")
        elif defect is not None:
            compatibility.unresolved(defect)
        elif value <= 0 or value >= 90:
            compatibility.violate(f"{label} pressure angle must lie strictly between 0 and 90 degrees")
        else:
            angle_values.append(value)

    for label, binding, value, defect in face_width_results:
        if binding is not None:
            compat_bindings.append(binding)
        if binding is None:
            compatibility.unresolved("gear.face_width_mm is missing on one or both gear snapshots")
        elif defect is not None:
            compatibility.unresolved(defect)
        elif value <= 0:
            compatibility.violate(f"{label} face width must be strictly positive")

    if len(module_values) == 2 and module_values[0] != module_values[1]:
        compatibility.violate(f"driver module {module_values[0]} mm differs from driven module {module_values[1]} mm")
    if len(angle_values) == 2 and angle_values[0] != angle_values[1]:
        compatibility.violate(
            f"driver pressure angle {angle_values[0]} deg differs from driven pressure angle {angle_values[1]} deg"
        )

    profile_shift_present = any(
        prop.key == "gear.profile_shift"
        for _, specification, _ in gears
        for prop in specification.properties
    )
    if profile_shift_present:
        for _, specification, instance_id in gears:
            for prop in specification.properties:
                if prop.key == "gear.profile_shift":
                    compat_bindings.append(
                        ConsumedPropertyBinding(
                            component_instance_id=instance_id,
                            specification_hash=specification.specification_hash,
                            property_key=prop.key,
                            property_hash=prop.property_hash,
                            source_identity=prop.source_identity,
                            authority=prop.authority,
                        )
                    )
        compatibility.unresolved("profile-shifted gear pairs are outside the supported compatibility model")

    ratio: float | None = None
    pitch_driver: float | None = None
    pitch_driven: float | None = None
    center_distance: float | None = None
    if (
        compatibility.status is not EngineeringCheckStatus.VIOLATED
        and len(module_values) == 2
        and len(teeth_values) == 2
        and module_values[0] == module_values[1]
    ):
        nominal = calculate_nominal_spur(module_values[0], teeth_values[0], teeth_values[1])
        ratio = nominal.ratio_magnitude
        pitch_driver = nominal.pitch_diameter_driver_mm
        pitch_driven = nominal.pitch_diameter_driven_mm
        center_distance = nominal.center_distance_mm

    speed_bindings: list[ConsumedPropertyBinding] = []
    speed_verdict = _Verdict()
    if ratio is None:
        speed_verdict.unresolved("nominal pair geometry is unavailable for the output-speed check")
    else:
        min_binding, speed_min, min_defect = _numeric_property(motor_specification, motor_instance_id, "motor.speed_min_rpm", "rpm")
        max_binding, speed_max, max_defect = _numeric_property(motor_specification, motor_instance_id, "motor.speed_max_rpm", "rpm")
        if min_binding is None or max_binding is None:
            speed_bindings.extend(
                binding for binding in (min_binding, max_binding) if binding is not None
            )
            speed_verdict.unresolved("motor usable-speed-range properties are missing")
        else:
            speed_bindings.extend((min_binding, max_binding))
            defects = [d for d in (min_defect, max_defect) if d is not None]
            if defects:
                speed_verdict.unresolved("; ".join(defects))
            if speed_min is not None and speed_max is not None:
                _validated_speed_range(speed_min, speed_max)
                if speed_min < 0 or speed_max < 0:
                    speed_verdict.violate("motor usable speed bounds must be nonnegative magnitudes")
                required_motor_speed = requirements.required_output_speed.value * ratio
                if required_motor_speed < speed_min or required_motor_speed > speed_max:
                    speed_verdict.violate(
                        f"required motor speed {required_motor_speed} rpm lies outside the authoritative usable range "
                        f"[{speed_min}, {speed_max}] rpm"
                    )

    output_speed_rpm: float | None = None
    if motor_speed_rpm is not None:
        motor_speed_rpm = _nonnegative_finite_argument(motor_speed_rpm, "motor_speed_rpm")
    if ratio is not None and motor_speed_rpm is not None:
        output_speed_rpm = motor_speed_rpm / ratio

    torque_bindings: list[ConsumedPropertyBinding] = []
    torque_paths: list[str] = []
    torque_verdict = _Verdict()
    output_continuous: float | None = None
    output_peak: float | None = None
    efficiency = requirements.efficiency
    if efficiency is None:
        torque_verdict.unresolved("mesh efficiency is not supplied; real output-torque transfer cannot be established")
    elif ratio is None:
        torque_verdict.unresolved("nominal pair geometry is unavailable for the output-torque transfer check")
    else:
        torque_paths.extend(("/requirements/efficiency", _DESIGN_TORQUE_PATH))
        binding, continuous_torque, defect = _numeric_property(motor_specification, motor_instance_id, "motor.continuous_torque_nm", "N*m")
        if binding is None:
            torque_verdict.unresolved("motor.continuous_torque_nm property is missing")
        else:
            torque_bindings.append(binding)
            if defect is not None:
                torque_verdict.unresolved(defect)
            elif continuous_torque <= 0:
                torque_verdict.violate("motor continuous torque must be strictly positive")
            else:
                output_continuous = continuous_torque * ratio * efficiency.value
                required_torque = requirements.design_load_case.design_torque.value
                if output_continuous < required_torque:
                    torque_verdict.violate(
                        f"efficiency-bound continuous output torque {output_continuous} N*m is below the required "
                        f"output-shaft design torque {required_torque} N*m"
                    )
        required_peak = requirements.required_peak_torque
        if required_peak is not None:
            torque_paths.append("/requirements/required_peak_torque")
            peak_binding, peak_torque, peak_defect = _numeric_property(motor_specification, motor_instance_id, "motor.peak_torque_nm", "N*m")
            if peak_binding is None:
                torque_verdict.unresolved("motor.peak_torque_nm property is missing")
            else:
                torque_bindings.append(peak_binding)
                if peak_defect is not None:
                    torque_verdict.unresolved(peak_defect)
                elif peak_torque <= 0:
                    torque_verdict.violate("motor peak torque must be strictly positive")
                else:
                    output_peak = peak_torque * ratio * efficiency.value
                    if output_peak < required_peak.value:
                        torque_verdict.violate(
                            f"efficiency-bound peak output torque {output_peak} N*m is below the required peak torque "
                            f"{required_peak.value} N*m"
                        )

    return SpurPairEvaluation(
        ratio_magnitude=ratio,
        pitch_diameter_driver_mm=pitch_driver,
        pitch_diameter_driven_mm=pitch_driven,
        center_distance_mm=center_distance,
        output_speed_rpm=output_speed_rpm,
        output_continuous_torque_nm=output_continuous,
        output_peak_torque_nm=output_peak,
        compatibility_check=_check("spur-pair-compatibility", compatibility, compat_bindings),
        speed_check=_check("spur-output-speed", speed_verdict, speed_bindings, ("/requirements/required_output_speed",)),
        torque_check=_check("spur-output-torque-transfer", torque_verdict, torque_bindings, tuple(torque_paths)),
    )


def calculate_spur_loads(
    requirements: RevoluteDriveEngineeringRequirements,
    *,
    driven_pitch_diameter_mm: float,
    pressure_angle_deg: float,
) -> SpurMeshLoadResult:
    diameter = _positive_finite_argument(driven_pitch_diameter_mm, "driven_pitch_diameter_mm")
    angle = _positive_finite_argument(pressure_angle_deg, "pressure_angle_deg")
    if angle >= 90:
        raise ValueError("pressure_angle_deg must lie strictly between 0 and 90 degrees")

    transmitted_torque_n_mm = 1000.0 * requirements.design_load_case.design_torque.value
    tangential_force_n = 2.0 * transmitted_torque_n_mm / diameter
    radial_force_n = tangential_force_n * math.tan(math.radians(angle))
    return SpurMeshLoadResult(
        transmitted_torque_n_mm=transmitted_torque_n_mm,
        tangential_force_n=tangential_force_n,
        radial_force_n=radial_force_n,
    )


def calculate_shaft_static_sizing(
    requirements: RevoluteDriveEngineeringRequirements,
    shaft_specification: ComponentSpecificationSnapshot,
    *,
    shaft_instance_id: str = "shaft",
    selected_diameter_mm: object | None = None,
) -> ShaftStaticSizingResult:
    geometry = requirements.shaft_support_geometry
    force_y_scalar = requirements.design_load_case.transverse_force_y
    force_z_scalar = requirements.design_load_case.transverse_force_z

    equilibrium = _Verdict()
    reactions: dict[str, float] = {}
    residuals: dict[str, float] = {}
    maximum_bending: float | None = None
    if geometry is None:
        equilibrium.unresolved("shaft support geometry is missing")
    elif force_y_scalar is None or force_z_scalar is None:
        equilibrium.unresolved("explicit transverse load vector is missing from the design load case")
    else:
        x_a = geometry.support_a_x.value
        span = geometry.support_b_x.value - x_a
        offset = geometry.load_plane_x.value - x_a
        fy = force_y_scalar.value
        fz = force_z_scalar.value
        ra_y = -fy * (span - offset) / span
        rb_y = -fy * offset / span
        ra_z = -fz * (span - offset) / span
        rb_z = -fz * offset / span
        force_residual_y = ra_y + rb_y + fy
        force_residual_z = ra_z + rb_z + fz
        moment_residual_y = rb_y * span + fy * offset
        moment_residual_z = rb_z * span + fz * offset
        if abs(force_residual_y) > _FORCE_RESIDUAL_TOLERANCE_N or abs(force_residual_z) > _FORCE_RESIDUAL_TOLERANCE_N:
            raise ArithmeticError("shaft static sizing failed the force-equilibrium numerical tolerance")
        if abs(moment_residual_y) > _MOMENT_RESIDUAL_TOLERANCE_N_MM or abs(moment_residual_z) > _MOMENT_RESIDUAL_TOLERANCE_N_MM:
            raise ArithmeticError("shaft static sizing failed the moment-equilibrium numerical tolerance")
        reactions.update({"ra_y": ra_y, "rb_y": rb_y, "ra_z": ra_z, "rb_z": rb_z})
        residuals.update(
            {
                "force_y": force_residual_y,
                "force_z": force_residual_z,
                "moment_y": moment_residual_y,
                "moment_z": moment_residual_z,
            }
        )
        moment_y = abs(ra_y * offset)
        moment_z = abs(ra_z * offset)
        maximum_bending = math.sqrt(moment_y * moment_y + moment_z * moment_z)

    stress = _Verdict()
    stress_bindings: list[ConsumedPropertyBinding] = []
    bending: float | None = None
    torsional: float | None = None
    von_mises: float | None = None
    allowable: float | None = None
    tolerance: float | None = None
    minimum_diameter: float | None = None

    if geometry is None or force_y_scalar is None or force_z_scalar is None:
        stress.unresolved("support/load geometry is incomplete; stresses cannot be evaluated")

    diam_binding, snapshot_diameter, diam_defect = _numeric_property(shaft_specification, shaft_instance_id, "shaft.diameter_mm", "mm")
    diameter = snapshot_diameter
    if diam_binding is None:
        stress.unresolved("shaft.diameter_mm property is missing")
    else:
        stress_bindings.append(diam_binding)
        if diam_defect is not None:
            stress.unresolved(diam_defect)
        elif snapshot_diameter <= 0:
            stress.violate("selected shaft diameter must be strictly positive")

    if selected_diameter_mm is not None:
        try:
            if isinstance(selected_diameter_mm, bool):
                raise ValueError("selected shaft diameter must be a finite positive number")
            if isinstance(selected_diameter_mm, str):
                selected_diameter = float(selected_diameter_mm.strip())
            elif isinstance(selected_diameter_mm, (int, float)):
                selected_diameter = float(selected_diameter_mm)
            else:
                raise ValueError("selected shaft diameter must be a finite positive number")
            if not math.isfinite(selected_diameter) or selected_diameter <= 0:
                raise ValueError("selected shaft diameter must be a finite positive number")
            diameter = selected_diameter
        except (TypeError, ValueError) as exc:
            stress.unresolved(f"selected shaft diameter design variable is invalid: {exc}")
            diameter = None

    if diameter is not None and diameter > 0 and maximum_bending is not None:
        transmitted_torque_n_mm = 1000.0 * requirements.design_load_case.design_torque.value
        section_inverse = math.pi * diameter**3
        bending = 32.0 * maximum_bending / section_inverse
        torsional = 16.0 * transmitted_torque_n_mm / section_inverse
        von_mises = math.sqrt(bending * bending + 3.0 * torsional * torsional)

    yield_strength = requirements.shaft_yield_strength
    safety_factor = requirements.safety_factor
    if yield_strength is None and safety_factor is None:
        stress.unresolved("shaft yield strength and design factor are missing")
    elif yield_strength is None:
        stress.unresolved("shaft yield strength is missing")
    elif safety_factor is None:
        stress.unresolved("design factor is missing")
    else:
        allowable = yield_strength.value / safety_factor.value
        tolerance = max(_STRESS_ABSOLUTE_TOLERANCE_MPA, _STRESS_RELATIVE_TOLERANCE * allowable)
        if von_mises is not None:
            if von_mises <= allowable + tolerance:
                pass
            else:
                stress.violate(
                    f"von Mises stress {von_mises} MPa exceeds the allowable stress {allowable} MPa beyond the comparison tolerance"
                )
            transmitted_torque_n_mm = 1000.0 * requirements.design_load_case.design_torque.value
            coefficient_squared = (32.0 * maximum_bending / math.pi) ** 2 + 3.0 * (16.0 * transmitted_torque_n_mm / math.pi) ** 2
            minimum_diameter = (math.sqrt(coefficient_squared) / allowable) ** (1.0 / 3.0)

    return ShaftStaticSizingResult(
        reaction_a_y_n=reactions.get("ra_y"),
        reaction_b_y_n=reactions.get("rb_y"),
        reaction_a_z_n=reactions.get("ra_z"),
        reaction_b_z_n=reactions.get("rb_z"),
        force_residual_y_n=residuals.get("force_y"),
        force_residual_z_n=residuals.get("force_z"),
        moment_residual_y_n_mm=residuals.get("moment_y"),
        moment_residual_z_n_mm=residuals.get("moment_z"),
        maximum_bending_moment_n_mm=maximum_bending,
        bending_stress_mpa=bending,
        torsional_stress_mpa=torsional,
        von_mises_stress_mpa=von_mises,
        allowable_stress_mpa=allowable,
        stress_tolerance_mpa=tolerance,
        minimum_diameter_mm=minimum_diameter,
        equilibrium_check=_check("shaft-static-equilibrium", equilibrium, (), (_FORCE_Y_PATH, _FORCE_Z_PATH, _SUPPORT_GEOMETRY_PATH)),
        stress_check=_check(
            "shaft-selected-diameter-stress",
            stress,
            stress_bindings,
            (_DESIGN_TORQUE_PATH, "/requirements/shaft_yield_strength", "/requirements/safety_factor", _SUPPORT_GEOMETRY_PATH),
        ),
    )
