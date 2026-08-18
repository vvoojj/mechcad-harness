from .adapters import PyGearworksAdapter
from mechcad_harness.gear import SpurGearGeometryInput, SpurGearGeometryResult, SpurGearPairInput, SpurGearPairResult


def calc_spur_gear_geometry_gearworks(value: SpurGearGeometryInput) -> SpurGearGeometryResult:
    adapter = PyGearworksAdapter()
    gear, metadata = adapter.spur_geometry(value)
    return SpurGearGeometryResult(
        module_mm=value.module_mm,
        teeth=value.teeth,
        pitch_diameter_mm=2 * float(gear.pitch_radius),
        pitch_radius_mm=float(gear.pitch_radius),
        addendum_diameter_mm=2 * metadata["addendum_radius_mm"],
        root_diameter_mm=2 * metadata["dedendum_radius_mm"],
        base_diameter_mm=2 * metadata["base_radius_mm"],
        face_width_mm=value.face_width_mm,
        pressure_angle_deg=value.pressure_angle_deg,
        profile_shift=value.profile_shift,
        internal=value.internal,
        geometry_metadata=metadata,
    )


def calc_spur_gear_pair_gearworks(value: SpurGearPairInput) -> SpurGearPairResult:
    adapter = PyGearworksAdapter()
    pinion, gear, actual_center = adapter.spur_pair(value)
    return SpurGearPairResult(
        module_mm=value.module_mm,
        pinion_teeth=value.pinion_teeth,
        gear_teeth=value.gear_teeth,
        gear_ratio=value.gear_teeth / value.pinion_teeth,
        pinion_pitch_diameter_mm=2 * float(pinion.pitch_radius),
        gear_pitch_diameter_mm=2 * float(gear.pitch_radius),
        nominal_center_distance_mm=(float(pinion.pitch_radius) + float(gear.pitch_radius)),
        actual_center_distance_mm=actual_center,
        pinion_profile_shift=value.pinion_profile_shift,
        gear_profile_shift=value.gear_profile_shift,
    )


def gearworks_provenance():
    return PyGearworksAdapter().provenance()
