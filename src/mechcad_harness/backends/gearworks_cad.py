from pathlib import Path
from uuid import uuid4

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.backends.adapters import PyGearworksAdapter
from mechcad_harness.backends.errors import BackendCompatibilityError
from mechcad_harness.backends.models import BackendProvenance
from mechcad_harness.cad import ArtifactReference, SpurGearCadInput, SpurGearPairCadInput, SpurGearPairCadResult, SpurGearCadResult


def _part_metrics(part, face_width):
    if not part.is_valid or part.volume <= 0:
        raise BackendCompatibilityError("generated gear part is not a valid non-empty solid")
    bounds = part.bounding_box()
    values = (float(bounds.size.X), float(bounds.size.Y), float(bounds.size.Z))
    if any(value != value or abs(value) == float("inf") for value in values):
        raise BackendCompatibilityError("gear bounding box is not finite")
    if abs(values[2] - face_width) > max(0.01, face_width * 0.02):
        raise BackendCompatibilityError("gear axial thickness differs from requested face width")
    center = part.center()
    return values, float(part.volume), (float(center.X), float(center.Y), float(center.Z))


def build_spur_gear_cad(value: SpurGearCadInput, workspace, producer_tool_name="mechcad-build-spur-gear-cad", producer_tool_version="1.0", *, project_id="unbound-project", run_id="unbound-run", task_id=None, bound_revision=1, bound_state_hash="unbound", input_hash=None) -> SpurGearCadResult:
    adapter = PyGearworksAdapter()
    provenance = adapter.provenance()
    gear, metadata = adapter.spur_geometry(value.model_copy(update={"internal": False}))
    try:
        from build123d import Cylinder, Mode
        from importlib.metadata import version as package_version

        build123d_provenance = BackendProvenance(
            backend_name="build123d",
            backend_adapter_version="build123d-runtime",
            library_name="build123d",
            library_version=package_version("build123d"),
        )

        part = gear.build_part()
        if value.bore_diameter_mm is not None:
            pitch_diameter = 2 * float(gear.pitch_radius)
            if value.bore_diameter_mm >= pitch_diameter:
                raise ValueError("bore diameter must be smaller than pitch diameter")
            part = part - Cylinder(value.bore_diameter_mm / 2, value.face_width_mm, mode=Mode.SUBTRACT)
        bounds, volume, center = _part_metrics(part, value.face_width_mm)
        store = ArtifactStore(workspace, project_id=project_id, run_id=run_id, task_id=task_id)
        references = []
        for requested in value.requested_formats:
            artifact_type = ArtifactType(requested)
            temporary = Path(workspace) / f".gear-{uuid4().hex}.{requested}"
            if artifact_type is ArtifactType.STEP:
                from build123d import export_step

                export_step(part, temporary, timestamp="2000-01-01T00:00:00Z")
            else:
                from build123d import export_stl

                export_stl(part, temporary)
            content = temporary.read_bytes()
            temporary.unlink()
            artifact = store.publish(f"ART-{uuid4()}", artifact_type, f"gear.{requested}", content, producer_tool_name, producer_tool_version, bound_revision, bound_state_hash, backend_provenance=provenance, build123d_provenance=build123d_provenance, input_hash=input_hash)
            references.append(ArtifactReference(artifact_id=artifact.artifact_id, artifact_type=requested, relative_path=artifact.relative_path, sha256=artifact.sha256, size_bytes=artifact.size_bytes))
        return SpurGearCadResult(geometry_summary={"module_mm": value.module_mm, "teeth": value.teeth, "pitch_diameter_mm": 2 * float(gear.pitch_radius), "outside_diameter_mm": 2 * metadata["addendum_radius_mm"], "face_width_mm": value.face_width_mm, "bore_diameter_mm": value.bore_diameter_mm or 0.0}, artifact_references=tuple(references), bounding_box_mm=bounds, volume_mm3=volume, center_of_mass_mm=center, backend_provenance=provenance, build123d_provenance=build123d_provenance)
    except Exception as exc:
        if isinstance(exc, (ValueError, BackendCompatibilityError)):
            raise
        raise BackendCompatibilityError(f"gear CAD generation failed: {type(exc).__name__}: {exc}") from exc


def build_spur_gear_pair_cad(value: SpurGearPairCadInput, workspace, *, project_id="unbound-project", run_id="unbound-run", task_id=None, bound_revision=1, bound_state_hash="unbound", input_hash=None):
    from mechcad_harness.backends.gearworks_tools import calc_spur_gear_pair_gearworks
    from mechcad_harness.gear import SpurGearPairInput

    if value.pinion.bore_diameter_mm is not None and value.gear.bore_diameter_mm is not None:
        pass
    pair = calc_spur_gear_pair_gearworks(SpurGearPairInput(module_mm=value.pinion.module_mm, pinion_teeth=value.pinion.teeth, gear_teeth=value.gear.teeth, face_width_mm=value.pinion.face_width_mm, pressure_angle_deg=value.pinion.pressure_angle_deg, pinion_profile_shift=value.pinion.profile_shift, gear_profile_shift=value.gear.profile_shift))
    pinion = build_spur_gear_cad(value.pinion, workspace, producer_tool_name="mechcad-build-spur-gear-pair-cad", project_id=project_id, run_id=run_id, task_id=task_id, bound_revision=bound_revision, bound_state_hash=bound_state_hash, input_hash=input_hash)
    gear = build_spur_gear_cad(value.gear, workspace, producer_tool_name="mechcad-build-spur-gear-pair-cad", project_id=project_id, run_id=run_id, task_id=task_id, bound_revision=bound_revision, bound_state_hash=bound_state_hash, input_hash=input_hash)
    return SpurGearPairCadResult(pinion=pinion, gear=gear, nominal_center_distance_mm=pair.nominal_center_distance_mm, relative_transform=(pair.nominal_center_distance_mm, 0.0, 0.0))
