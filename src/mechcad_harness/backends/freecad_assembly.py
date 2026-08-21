from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

from pydantic import Field

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.backends.freecad import FreeCADBackend, FreeCADArtifactVerificationError, FreeCADExecutionError, FreeCADGeometryVerification, discover_freecad
from mechcad_harness.cad_assembly import CadAssemblyProgram, assembly_hash, instance_object_name
from mechcad_harness.cad_assembly_manifest import CadAssemblyManifest, build_assembly_manifest
from mechcad_harness.cad_program import cad_program_hash
from mechcad_harness.models.common import Model
from mechcad_harness.backends.models import BackendProvenance


ASSEMBLY_BACKEND_VERSION = "mechcad-freecad-assembly@1.0"


class FreeCADAssemblyInstanceVerification(Model):
    instance_id: str = Field(min_length=1)
    object_name: str = Field(min_length=1)
    x_length_mm: float
    y_length_mm: float
    z_length_mm: float
    x_min_mm: float
    x_max_mm: float
    y_min_mm: float
    y_max_mm: float
    z_min_mm: float
    z_max_mm: float
    volume_mm3: float = Field(gt=0)
    shape_valid: bool


class FreeCADAssemblyVerification(Model):
    assembly_id: str = Field(min_length=1)
    assembly_hash: str = Field(min_length=1)
    instances: tuple[FreeCADAssemblyInstanceVerification, ...] = Field(min_length=1)
    overall_bounds_mm: tuple[float, float, float]
    total_volume_mm3: float = Field(gt=0)
    solid_count: int = Field(gt=0)
    shape_valid: bool


class FreeCADAssemblyGenerationResult(Model):
    fcstd: object
    step: object
    manifest: CadAssemblyManifest
    fcstd_verification: FreeCADAssemblyVerification
    step_verification: FreeCADAssemblyVerification
    project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    bound_revision: int = Field(gt=0)
    bound_state_hash: str = Field(min_length=1)
    backend_version: str = Field(min_length=1)
    freecad_version: str | None = None
    backend_provenance: BackendProvenance | None = None


def assembly_artifact_id(project_id, run_id, revision, state_hash, program, kind):
    return f"ASM-{program.assembly_id}-{assembly_hash(program).split(':', 1)[1][:16]}-{kind.lower()}"


def store_artifacts(store):
    root = store.workspace / "projects" / store.project_id / "runs" / store.run_id / "artifacts"
    for metadata in root.glob("*/metadata.json"):
        try:
            from mechcad_harness.artifacts.models import EngineeringArtifact
            yield EngineeringArtifact.model_validate_json(metadata.read_text(encoding="utf-8"))
        except Exception:
            continue


def _quaternion_to_axis_angle(quaternion):
    w, x, y, z = quaternion
    angle = 2 * math.acos(max(-1.0, min(1.0, w)))
    scale = math.sqrt(max(0.0, 1 - w * w))
    if scale <= 1e-12:
        return (0, 0, 1), 0
    return (x / scale, y / scale, z / scale), angle


class FreeCADAssemblyBackend:
    def __init__(self, part_backend: FreeCADBackend | None = None):
        self.part_backend = part_backend or FreeCADBackend()

    @staticmethod
    def placement_matches(actual, expected, translation_tolerance=1e-6, rotation_tolerance=1e-6):
        base = actual["base"]
        if any(abs(float(actual_value) - expected_value) > translation_tolerance for actual_value, expected_value in zip(base, (expected.x_mm, expected.y_mm, expected.z_mm))):
            return False
        quaternion = tuple(float(value) for value in actual["quaternion"])
        norm = math.sqrt(sum(value * value for value in quaternion))
        if norm <= 1e-12:
            return False
        quaternion = tuple(value / norm for value in quaternion)
        if next(value for value in quaternion if abs(value) > 1e-12) < 0:
            quaternion = tuple(-value for value in quaternion)
        return all(abs(actual_value - expected_value) <= rotation_tolerance for actual_value, expected_value in zip(quaternion, expected.rotation_quaternion))

    @staticmethod
    def verify_component_artifact(artifact, workspace, *, expected_part_hash: str, expected_artifact_id: str):
        if artifact is None or artifact.artifact_id != expected_artifact_id or artifact.input_hash != expected_part_hash:
            raise FreeCADArtifactVerificationError("component artifact identity mismatch")
        path = Path(workspace) / artifact.relative_path
        if not path.is_file():
            raise FreeCADArtifactVerificationError("component artifact is missing")
        import hashlib
        if f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}" != artifact.sha256:
            raise FreeCADArtifactVerificationError("component artifact byte hash mismatch")
        return artifact

    def verify_persisted_assembly(self, program, workspace, *, project_id: str, run_id: str, revision: int, state_hash: str):
        discovery = discover_freecad().require_available()
        runtime_provenance = self.part_backend.provenance()
        store = ArtifactStore(workspace, project_id=project_id, run_id=run_id)
        fcstd_id = assembly_artifact_id(project_id, run_id, revision, state_hash, program, "FCStd")
        step_id = assembly_artifact_id(project_id, run_id, revision, state_hash, program, "STEP")
        fcstd = store.existing(fcstd_id)
        step = store.existing(step_id)
        if fcstd is None or step is None:
            raise FreeCADArtifactVerificationError("verified assembly artifacts are missing or invalid")
        manifest = build_assembly_manifest(program, {part.part_id: self._component_artifact(store, part, workspace, project_id, run_id, revision, state_hash) for part in program.canonical_parts}, revision, state_hash)
        return self._verify_persisted(program, workspace, project_id, run_id, revision, state_hash, discovery, fcstd, step, manifest, backend_provenance=fcstd.backend_provenance or runtime_provenance)

    @staticmethod
    def _component_artifact(store, part, workspace, project_id, run_id, revision, state_hash):
        from mechcad_harness.backends.freecad import freecad_program_artifact_id
        artifact_id = freecad_program_artifact_id(project_id, run_id, revision, state_hash, part, "FCStd")
        artifact = store.existing(artifact_id)
        return FreeCADAssemblyBackend.verify_component_artifact(artifact, workspace, expected_part_hash=cad_program_hash(part), expected_artifact_id=artifact_id)

    def generate_assembly(self, program: CadAssemblyProgram, workspace, *, project_id: str, run_id: str, revision: int, state_hash: str) -> FreeCADAssemblyGenerationResult:
        discovery = discover_freecad().require_available()
        backend_provenance = self.part_backend.provenance()
        store = ArtifactStore(workspace, project_id=project_id, run_id=run_id)
        part_artifacts = {}
        for part in program.canonical_parts:
            part_result = self.part_backend.generate_program(part, workspace, project_id=project_id, run_id=run_id, revision=revision, state_hash=state_hash)
            self.verify_component_artifact(part_result.fcstd, workspace, expected_part_hash=cad_program_hash(part), expected_artifact_id=part_result.fcstd.artifact_id)
            part_artifacts[part.part_id] = part_result.fcstd
        manifest = build_assembly_manifest(program, part_artifacts, revision, state_hash)
        assembly_id_fcstd = assembly_artifact_id(project_id, run_id, revision, state_hash, program, "FCStd")
        assembly_id_step = assembly_artifact_id(project_id, run_id, revision, state_hash, program, "STEP")
        existing_fcstd = store.existing(assembly_id_fcstd)
        existing_step = store.existing(assembly_id_step)
        if existing_fcstd and existing_step:
            return self._verify_persisted(program, workspace, project_id, run_id, revision, state_hash, discovery, existing_fcstd, existing_step, manifest, backend_provenance=existing_fcstd.backend_provenance or backend_provenance)
        with tempfile.TemporaryDirectory(prefix="mechcad-assembly-") as directory:
            fcstd_path = Path(directory) / "assembly.FCStd"
            step_path = Path(directory) / "assembly.step"
            script = self._compile(program, part_artifacts, manifest, fcstd_path, step_path, workspace)
            result = self.part_backend._run(discovery.executable, script, cwd=Path(directory))
            if result.returncode != 0 or not fcstd_path.is_file() or not step_path.is_file():
                raise FreeCADExecutionError(result.stderr or result.stdout or "assembly generation failed")
            fcstd_content = fcstd_path.read_bytes()
            step_content = step_path.read_bytes()
        fcstd_artifact = existing_fcstd or store.publish(assembly_id_fcstd, ArtifactType.FCSTD, "assembly.FCStd", fcstd_content, "mechcad-freecad-assembly", ASSEMBLY_BACKEND_VERSION, revision, state_hash, backend_provenance=backend_provenance, input_hash=manifest.assembly_hash)
        step_artifact = existing_step or store.publish(assembly_id_step, ArtifactType.STEP, "assembly.step", step_content, "mechcad-freecad-assembly", ASSEMBLY_BACKEND_VERSION, revision, state_hash, backend_provenance=backend_provenance, input_hash=manifest.assembly_hash)
        return self._verify_persisted(program, workspace, project_id, run_id, revision, state_hash, discovery, fcstd_artifact, step_artifact, manifest, backend_provenance=backend_provenance)

    def _compile(self, program, part_artifacts, manifest, fcstd_path, step_path, workspace):
        records = []
        for instance in program.canonical_instances:
            artifact = part_artifacts[instance.part_id]
            axis, angle = _quaternion_to_axis_angle(instance.placement.rotation_quaternion)
            records.append((instance, str((Path(workspace) / artifact.relative_path).resolve()), axis, angle))
        lines = ["import FreeCAD, Part, json", f"doc = FreeCAD.newDocument({program.assembly_id!r})"]
        for instance, source_path, axis, angle in records:
            name = instance_object_name(instance.instance_id)
            lines += [f"source = FreeCAD.openDocument({source_path!r})", "source_objects = [item for item in source.Objects if hasattr(item, 'Shape') and not item.Shape.isNull()]", "if not source_objects: raise RuntimeError('source part shape missing')", f"obj = doc.addObject('Part::Feature', {name!r})", "obj.Shape = source_objects[0].Shape.copy()", f"obj.Placement.Base = FreeCAD.Vector({instance.placement.x_mm!r}, {instance.placement.y_mm!r}, {instance.placement.z_mm!r})", f"obj.Placement.Rotation = FreeCAD.Rotation(FreeCAD.Vector({axis[0]!r}, {axis[1]!r}, {axis[2]!r}), {math.degrees(angle)!r})", "FreeCAD.closeDocument(source.Name)"]
        manifest_json = json.dumps(manifest.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        lines += ["meta = doc.addObject('App::FeaturePython', 'assembly_manifest')", "meta.addProperty('App::PropertyString', 'ManifestJson', 'Assembly')", f"meta.ManifestJson = {manifest_json!r}", "doc.recompute()", f"doc.saveAs({str(fcstd_path)!r})", f"Part.export([item for item in doc.Objects if hasattr(item, 'Shape') and not item.Shape.isNull()], {str(step_path)!r})", "FreeCAD.closeDocument(doc.Name)"]
        return "\n".join(lines) + "\n"

    def _verify_persisted(self, program, workspace, project_id, run_id, revision, state_hash, discovery, fcstd_artifact, step_artifact, manifest, *, backend_provenance=None):
        fcstd_path = (Path(workspace) / fcstd_artifact.relative_path).resolve()
        step_path = (Path(workspace) / step_artifact.relative_path).resolve()
        expected_json = json.dumps(manifest.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        expected_names = [instance_object_name(instance.instance_id) for instance in program.canonical_instances]
        expected_placements = {instance_object_name(instance.instance_id): instance.placement.model_dump(mode="json") for instance in program.canonical_instances}
        fcstd_script = f'''import FreeCAD, json
doc = FreeCAD.openDocument({str(fcstd_path)!r})
meta = doc.getObject("assembly_manifest")
if meta is None or meta.ManifestJson != {expected_json!r}: raise RuntimeError("assembly manifest mismatch")
objects = [doc.getObject(name) for name in {expected_names!r}]
if any(obj is None or obj.Shape.isNull() or not obj.Shape.isValid() for obj in objects): raise RuntimeError("assembly object mismatch")
items = []
for obj in objects:
    placement = {{"base": (obj.Placement.Base.x, obj.Placement.Base.y, obj.Placement.Base.z), "quaternion": (obj.Placement.Rotation.Q[3], obj.Placement.Rotation.Q[0], obj.Placement.Rotation.Q[1], obj.Placement.Rotation.Q[2])}}
    expected = {expected_placements!r}[obj.Name]
    print("M7A2B_PLACEMENT=" + json.dumps({{"name": obj.Name, "base": placement["base"], "quaternion": placement["quaternion"]}}, sort_keys=True))
    if any(abs(a - b) > 1e-6 for a, b in zip(placement["base"], (expected["x_mm"], expected["y_mm"], expected["z_mm"]))): raise RuntimeError("assembly Placement translation mismatch")
    q = placement["quaternion"]
    norm = (sum(value * value for value in q)) ** 0.5
    q = tuple(value / norm for value in q)
    if next(value for value in q if abs(value) > 1e-12) < 0: q = tuple(-value for value in q)
    if any(abs(a - b) > 1e-6 for a, b in zip(q, expected["rotation_quaternion"])): raise RuntimeError("assembly Placement rotation mismatch")
    box = obj.Shape.BoundBox
    items.append({{"instance_id": obj.Name, "object_name": obj.Name, "x_length_mm": box.XLength, "y_length_mm": box.YLength, "z_length_mm": box.ZLength, "x_min_mm": box.XMin, "x_max_mm": box.XMax, "y_min_mm": box.YMin, "y_max_mm": box.YMax, "z_min_mm": box.ZMin, "z_max_mm": box.ZMax, "volume_mm3": obj.Shape.Volume, "shape_valid": obj.Shape.isValid()}})
print("M7A2B_JSON=" + json.dumps({{"assembly_id": {program.assembly_id!r}, "assembly_hash": {manifest.assembly_hash!r}, "instances": items, "overall_bounds_mm": [max(item["x_max_mm"] for item in items)-min(item["x_min_mm"] for item in items), max(item["y_max_mm"] for item in items)-min(item["y_min_mm"] for item in items), max(item["z_max_mm"] for item in items)-min(item["z_min_mm"] for item in items)], "total_volume_mm3": sum(item["volume_mm3"] for item in items), "solid_count": len(items), "shape_valid": all(item["shape_valid"] for item in items)}}, sort_keys=True))
FreeCAD.closeDocument(doc.Name)
'''
        step_script = f'''import FreeCAD, Part, json
doc = FreeCAD.newDocument("M7A2BStepVerify")
Part.insert({str(step_path)!r}, doc.Name)
doc.recompute()
objects = [obj for obj in doc.Objects if hasattr(obj, "Shape") and not obj.Shape.isNull()]
items = []
for obj in objects:
    shape = obj.Shape
    box = shape.BoundBox
    items.append({{"instance_id": obj.Name, "object_name": obj.Name, "x_length_mm": box.XLength, "y_length_mm": box.YLength, "z_length_mm": box.ZLength, "x_min_mm": box.XMin, "x_max_mm": box.XMax, "y_min_mm": box.YMin, "y_max_mm": box.YMax, "z_min_mm": box.ZMin, "z_max_mm": box.ZMax, "volume_mm3": shape.Volume, "shape_valid": shape.isValid()}})
if len(items) != {len(program.instances)!r}: raise RuntimeError("assembly STEP solid count mismatch")
print("M7A2B_JSON=" + json.dumps({{"assembly_id": {program.assembly_id!r}, "assembly_hash": {manifest.assembly_hash!r}, "instances": items, "overall_bounds_mm": [max(item["x_max_mm"] for item in items)-min(item["x_min_mm"] for item in items), max(item["y_max_mm"] for item in items)-min(item["y_min_mm"] for item in items), max(item["z_max_mm"] for item in items)-min(item["z_min_mm"] for item in items)], "total_volume_mm3": sum(item["volume_mm3"] for item in items), "solid_count": len(items), "shape_valid": all(item["shape_valid"] for item in items)}}, sort_keys=True))
FreeCAD.closeDocument(doc.Name)
'''
        with tempfile.TemporaryDirectory(prefix="mechcad-assembly-verify-") as directory:
            fcstd = self._parse(self.part_backend._run(discovery.executable, fcstd_script, cwd=Path(directory)), expected_hash=manifest.assembly_hash, expected_solid_count=len(program.instances))
            step = self._parse(self.part_backend._run(discovery.executable, step_script, cwd=Path(directory)), expected_hash=manifest.assembly_hash, expected_solid_count=len(program.instances), require_names=False)
        backend_provenance = backend_provenance or fcstd_artifact.backend_provenance
        return FreeCADAssemblyGenerationResult(fcstd=fcstd_artifact, step=step_artifact, manifest=manifest, fcstd_verification=fcstd, step_verification=step, project_id=project_id, run_id=run_id, bound_revision=revision, bound_state_hash=state_hash, backend_version=ASSEMBLY_BACKEND_VERSION, freecad_version=backend_provenance.library_version if backend_provenance else None, backend_provenance=backend_provenance)

    @staticmethod
    def _parse(result, *, expected_hash, expected_solid_count=None, require_names=True):
        if result.returncode != 0:
            raise FreeCADArtifactVerificationError(result.stderr or result.stdout or "assembly verification failed")
        line = next((line for line in result.stdout.splitlines() if line.startswith("M7A2B_JSON=")), None)
        if line is None:
            raise FreeCADArtifactVerificationError("assembly structured verification missing")
        payload = json.loads(line.removeprefix("M7A2B_JSON="))
        if payload["assembly_hash"] != expected_hash or payload["solid_count"] != (expected_solid_count or payload["solid_count"]) or payload["solid_count"] <= 0 or not payload["shape_valid"]:
            raise FreeCADArtifactVerificationError("assembly verification mismatch")
        return FreeCADAssemblyVerification.model_validate(payload)
