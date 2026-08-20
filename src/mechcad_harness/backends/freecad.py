from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import shutil
import subprocess
import tempfile
import binascii
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from mechcad_harness.backends.models import BackendHealth, BackendHealthStatus, BackendIdentity, BackendProvenance
from mechcad_harness.models.common import Model


FREECAD_BACKEND_VERSION = "mechcad-freecad@2.1"


class FreeCADBackendError(Exception):
    pass


class FreeCADUnavailableError(FreeCADBackendError):
    pass


class FreeCADExecutionError(FreeCADBackendError):
    pass


class FreeCADArtifactVerificationError(FreeCADBackendError):
    pass


class FreeCADFixtureRequest(Model):
    document_id: str = Field(min_length=1)
    object_id: str = Field(min_length=1)
    length_mm: float = Field(gt=0)
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)

    @model_validator(mode="after")
    def finite_dimensions(self) -> "FreeCADFixtureRequest":
        if any(not math.isfinite(value) for value in self.dimensions_mm):
            raise ValueError("fixture dimensions must be finite")
        return self

    @property
    def dimensions_mm(self) -> tuple[float, float, float]:
        return (float(self.length_mm), float(self.width_mm), float(self.height_mm))


class FreeCADArtifactProvenance(Model):
    project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    bound_revision: int = Field(gt=0)
    bound_state_hash: str = Field(min_length=1)
    backend_name: str = Field(min_length=1)
    backend_adapter_version: str = Field(min_length=1)
    freecad_version: str = Field(min_length=1)
    fixture_input_hash: str = Field(min_length=1)
    artifact_kind: str = Field(min_length=1)
    artifact_path: str = Field(min_length=1)
    artifact_sha256: str = Field(min_length=1)
    creation_status: str = Field(min_length=1)


class FreeCADGeometryVerification(Model):
    status: str = Field(min_length=1)
    object_name: str = Field(min_length=1)
    shape_valid: bool
    x_length_mm: float
    y_length_mm: float
    z_length_mm: float
    volume_mm3: float = Field(default=1, gt=0)
    solid_count: int = Field(default=1, gt=0)
    feature_probes: dict[str, bool] = Field(default_factory=dict)


class FreeCADGenerationResult(Model):
    fcstd: Any
    step: Any
    fcstd_verification: FreeCADGeometryVerification
    step_verification: FreeCADGeometryVerification
    project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    bound_revision: int = Field(gt=0)
    bound_state_hash: str = Field(min_length=1)
    backend_version: str = Field(min_length=1)
    freecad_version: str = Field(min_length=1)


@dataclass(frozen=True)
class FreeCADDiscovery:
    available: bool
    executable: str | None = None
    version: str | None = None
    importable: bool = False
    execution_boundary: str | None = None

    def require_available(self) -> "FreeCADDiscovery":
        if not self.available:
            raise FreeCADUnavailableError("FreeCAD is not available through a deterministic local boundary")
        return self


def discover_freecad() -> FreeCADDiscovery:
    configured = os.environ.get("MECHCAD_FREECADCMD")
    if configured and Path(configured).is_file():
        return FreeCADDiscovery(True, str(Path(configured)), None, False, "bundled FreeCAD command line")
    executable = shutil.which("FreeCADCmd") or shutil.which("FreeCAD")
    importable = importlib.util.find_spec("FreeCAD") is not None
    if executable:
        return FreeCADDiscovery(True, executable, None, importable, "bundled FreeCAD command line")
    if importable:
        return FreeCADDiscovery(True, None, None, True, "isolated FreeCAD Python adapter")
    return FreeCADDiscovery(False, None, None, False, None)


def _freecad_version(discovery: FreeCADDiscovery) -> str:
    if discovery.version:
        return discovery.version
    with tempfile.TemporaryDirectory(prefix="mechcad-freecad-version-") as directory:
        script = 'import FreeCAD\nprint("M7A1_VERSION=" + ".".join(FreeCAD.Version()[:3]))\n'
        script_path = Path(directory) / "version.py"
        script_path.write_text(script, encoding="ascii")
        result = subprocess.run([discovery.executable, str(script_path)], cwd=directory, capture_output=True, text=True, timeout=30, check=False)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith("M7A1_VERSION="):
                    return line.removeprefix("M7A1_VERSION=")
    return "unknown"


def _fixture_hash(request: FreeCADFixtureRequest) -> str:
    payload = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def freecad_artifact_id(project_id: str, run_id: str, revision: int, state_hash: str, request: FreeCADFixtureRequest, kind: str) -> str:
    payload = f"{project_id}|{run_id}|{revision}|{state_hash}|{FREECAD_BACKEND_VERSION}|{_fixture_hash(request)}|{kind}".encode()
    return f"FC-{request.document_id}-{hashlib.sha256(payload).hexdigest()[:16]}"


def freecad_program_artifact_id(project_id: str, run_id: str, revision: int, state_hash: str, program, kind: str) -> str:
    from mechcad_harness.cad_program import cad_program_hash
    payload = f"{project_id}|{run_id}|{revision}|{state_hash}|{FREECAD_BACKEND_VERSION}|{cad_program_hash(program)}|{kind}".encode()
    return f"FC-{program.part_id}-{hashlib.sha256(payload).hexdigest()[:16]}"


def freecad_object_name(operation_id: str) -> str:
    encoded = binascii.hexlify(operation_id.encode("utf-8")).decode("ascii")
    if len(encoded) > 240:
        raise ValueError("operation_id is too long for deterministic FreeCAD identity")
    return f"op_{encoded}"


def freecad_provenance(project_id: str, run_id: str, revision: int, state_hash: str, request: FreeCADFixtureRequest, artifact_sha256: str, kind: str, freecad_version: str, artifact_path: str = "pending") -> FreeCADArtifactProvenance:
    return FreeCADArtifactProvenance(project_id=project_id, run_id=run_id, bound_revision=revision, bound_state_hash=state_hash, backend_name="freecad", backend_adapter_version=FREECAD_BACKEND_VERSION, freecad_version=freecad_version, fixture_input_hash=_fixture_hash(request), artifact_kind=kind, artifact_path=artifact_path, artifact_sha256=artifact_sha256, creation_status="verified")


class FreeCADBackend:
    identity = BackendIdentity(name="freecad", adapter_version=FREECAD_BACKEND_VERSION, library_name="FreeCAD", capabilities=("cad.document", "cad.fcstd", "cad.step"))

    def healthcheck(self) -> BackendHealth:
        discovery = discover_freecad()
        return BackendHealth(backend_name=self.identity.name, status=BackendHealthStatus.AVAILABLE if discovery.available else BackendHealthStatus.UNAVAILABLE, detected_version=discovery.version, message=discovery.execution_boundary or "FreeCAD unavailable")

    def provenance(self) -> BackendProvenance:
        discovery = discover_freecad().require_available()
        return BackendProvenance(backend_name="freecad", backend_adapter_version=FREECAD_BACKEND_VERSION, library_name="FreeCAD", library_version=_freecad_version(discovery), library_source=discovery.executable)

    @staticmethod
    def compile_program(program: CadPartProgram, fcstd_path: str, step_path: str) -> str:
        from mechcad_harness.cad_program import BasePlateOperation, RectangularPocketOperation, ThroughHoleOperation, ThroughSlotOperation
        from mechcad_harness.cad_manifest import build_program_manifest
        manifest = build_program_manifest(program)
        manifest_json = json.dumps(manifest.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        lines = ["import FreeCAD, Part", f"doc = FreeCAD.newDocument({program.part_id!r})", "shape = None"]
        for operation in program.operations:
            if isinstance(operation, BasePlateOperation):
                lines.append(f"base = Part.makeBox({operation.length_mm!r}, {operation.width_mm!r}, {operation.thickness_mm!r})")
                lines.append("shape = base")
            elif isinstance(operation, ThroughHoleOperation):
                lines.append(f"shape = shape.cut(Part.makeCylinder({operation.diameter_mm / 2!r}, {program.operations[0].thickness_mm!r}, FreeCAD.Vector({operation.x_mm!r}, {operation.y_mm!r}, 0)))")
            elif isinstance(operation, RectangularPocketOperation):
                lines.append(f"shape = shape.cut(Part.makeBox({operation.length_mm!r}, {operation.width_mm!r}, {operation.depth_mm!r}, FreeCAD.Vector({operation.x_mm!r}, {operation.y_mm!r}, {program.operations[0].thickness_mm - operation.depth_mm!r})))")
            elif isinstance(operation, ThroughSlotOperation):
                if operation.orientation == "x":
                    left_x = operation.center_x_mm - operation.length_mm / 2 + operation.width_mm / 2
                    right_x = operation.center_x_mm + operation.length_mm / 2 - operation.width_mm / 2
                    rect_x = left_x
                    rect_y = operation.center_y_mm - operation.width_mm / 2
                    rect_length = operation.length_mm - operation.width_mm
                    rect_width = operation.width_mm
                    first = (left_x, operation.center_y_mm)
                    second = (right_x, operation.center_y_mm)
                else:
                    bottom_y = operation.center_y_mm - operation.length_mm / 2 + operation.width_mm / 2
                    top_y = operation.center_y_mm + operation.length_mm / 2 - operation.width_mm / 2
                    rect_x = operation.center_x_mm - operation.width_mm / 2
                    rect_y = bottom_y
                    rect_length = operation.width_mm
                    rect_width = operation.length_mm - operation.width_mm
                    first = (operation.center_x_mm, bottom_y)
                    second = (operation.center_x_mm, top_y)
                thickness = program.operations[0].thickness_mm
                lines.append(f"slot_rect = Part.makeBox({rect_length!r}, {rect_width!r}, {thickness!r}, FreeCAD.Vector({rect_x!r}, {rect_y!r}, 0))")
                lines.append(f"slot_cap_a = Part.makeCylinder({operation.width_mm / 2!r}, {thickness!r}, FreeCAD.Vector({first[0]!r}, {first[1]!r}, 0))")
                lines.append(f"slot_cap_b = Part.makeCylinder({operation.width_mm / 2!r}, {thickness!r}, FreeCAD.Vector({second[0]!r}, {second[1]!r}, 0))")
                lines.append("shape = shape.cut(slot_rect.fuse(slot_cap_a).fuse(slot_cap_b))")
        final_name = freecad_object_name(program.operations[-1].operation_id)
        lines.extend([f"obj = doc.addObject('PartDesign::Feature', {final_name!r})", "obj.Label = 'final_geometry'", "obj.Shape = shape", f"manifest = doc.addObject('App::FeaturePython', 'program_manifest')", "manifest.Label = 'program_manifest'", "manifest.addProperty('App::PropertyString', 'ManifestJson', 'CAD')", f"manifest.ManifestJson = {manifest_json!r}", "doc.recompute()", f"doc.saveAs({fcstd_path!r})", f"Part.export([obj], {step_path!r})", "FreeCAD.closeDocument(doc.Name)"])
        return "\n".join(lines) + "\n"

    @staticmethod
    def _parse_verification(result: subprocess.CompletedProcess[str], *, expected: tuple[float, float, float], object_name: str | None) -> FreeCADGeometryVerification:
        if result.returncode != 0:
            raise FreeCADArtifactVerificationError(result.stderr or result.stdout or "FreeCAD verification failed")
        line = next((line for line in result.stdout.splitlines() if line.startswith("M7A1_JSON=")), None)
        if line is None:
            raise FreeCADArtifactVerificationError("FreeCAD verification output is missing structured result")
        try:
            payload = json.loads(line.removeprefix("M7A1_JSON="))
            values = (float(payload["x_length_mm"]), float(payload["y_length_mm"]), float(payload["z_length_mm"]))
            verification = FreeCADGeometryVerification(status=payload["status"], object_name=payload["object_name"], shape_valid=bool(payload["shape_valid"]), x_length_mm=values[0], y_length_mm=values[1], z_length_mm=values[2], volume_mm3=float(payload["volume_mm3"]), solid_count=int(payload["solid_count"]), feature_probes=dict(payload.get("feature_probes", {})))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise FreeCADArtifactVerificationError("malformed FreeCAD structured verification output") from exc
        tolerance = 1e-6
        if (object_name is not None and verification.object_name != object_name) or not verification.shape_valid or verification.solid_count != 1 or any(abs(actual - wanted) > tolerance for actual, wanted in zip(values, expected)):
            raise FreeCADArtifactVerificationError("FreeCAD geometry verification mismatch")
        return verification

    @staticmethod
    def _run(executable: str, script: str, *, cwd: Path, timeout_seconds: float = 120.0) -> subprocess.CompletedProcess[str]:
        script_path = cwd / "freecad_runner.py"
        script_path.write_text(script, encoding="ascii")
        try:
            return subprocess.run([executable, str(script_path)], cwd=cwd, capture_output=True, text=True, timeout=timeout_seconds, check=False)
        except subprocess.TimeoutExpired as exc:
            raise FreeCADExecutionError("FreeCADCmd timed out") from exc
        finally:
            script_path.unlink(missing_ok=True)

    def generate_plate(self, request: FreeCADFixtureRequest, workspace: str | os.PathLike[str], *, project_id: str, run_id: str, revision: int, state_hash: str) -> FreeCADGenerationResult:
        from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
        program = CadPartProgram(part_id=request.document_id, operations=(BasePlateOperation(operation_id=request.object_id, length_mm=request.length_mm, width_mm=request.width_mm, thickness_mm=request.height_mm),))
        return self.generate_program(program, workspace, project_id=project_id, run_id=run_id, revision=revision, state_hash=state_hash)

    def generate_program(self, program: CadPartProgram, workspace: str | os.PathLike[str], *, project_id: str, run_id: str, revision: int, state_hash: str) -> FreeCADGenerationResult:
        from mechcad_harness.cad_program import BasePlateOperation, cad_program_hash, CadPartProgram
        from mechcad_harness.artifacts import ArtifactStore, ArtifactType
        discovery = discover_freecad().require_available()
        store = ArtifactStore(workspace, project_id=project_id, run_id=run_id)
        fcstd_id = freecad_program_artifact_id(project_id, run_id, revision, state_hash, program, "FCStd")
        step_id = freecad_program_artifact_id(project_id, run_id, revision, state_hash, program, "STEP")
        existing_fcstd = store.existing(fcstd_id)
        existing_step = store.existing(step_id)
        if existing_fcstd and existing_step:
            return self._verify_persisted(program, workspace, project_id, run_id, revision, state_hash, discovery, existing_fcstd, existing_step)
        with tempfile.TemporaryDirectory(prefix="mechcad-freecad-") as directory:
            output_dir = Path(directory)
            fcstd = output_dir / "plate.FCStd"
            step = output_dir / "plate.step"
            script = self.compile_program(program, str(fcstd), str(step))
            result = self._run(discovery.executable, script, cwd=Path(directory))
            if result.returncode != 0 or not fcstd.is_file() or not step.is_file() or fcstd.stat().st_size == 0 or step.stat().st_size == 0:
                raise FreeCADExecutionError(result.stderr or result.stdout or "FreeCAD artifact generation failed")
            fcstd_content = fcstd.read_bytes()
            step_content = step.read_bytes()
        backend_provenance = self.provenance()
        input_hash = cad_program_hash(program)
        fcstd_artifact = existing_fcstd or store.publish(fcstd_id, ArtifactType.FCSTD, "plate.FCStd", fcstd_content, "mechcad-freecad", FREECAD_BACKEND_VERSION, revision, state_hash, backend_provenance=backend_provenance, input_hash=input_hash)
        step_artifact = existing_step or store.publish(step_id, ArtifactType.STEP, "plate.step", step_content, "mechcad-freecad", FREECAD_BACKEND_VERSION, revision, state_hash, backend_provenance=backend_provenance, input_hash=input_hash)
        return self._verify_persisted(program, workspace, project_id, run_id, revision, state_hash, discovery, fcstd_artifact, step_artifact)

    def _verify_persisted(self, program, workspace, project_id, run_id, revision, state_hash, discovery, fcstd_artifact, step_artifact):
        from mechcad_harness.cad_program import BasePlateOperation, RectangularPocketOperation, ThroughHoleOperation, ThroughSlotOperation
        base = program.operations[0]
        assert isinstance(base, BasePlateOperation)
        fcstd_path = (Path(workspace) / fcstd_artifact.relative_path).resolve()
        step_path = (Path(workspace) / step_artifact.relative_path).resolve()
        expected = (base.length_mm, base.width_mm, base.thickness_mm)
        probe_lines = []
        for operation in program.operations:
            if isinstance(operation, ThroughHoleOperation):
                probe_lines.append(f"hole_{operation.operation_id} = not shape.isInside(FreeCAD.Vector({operation.x_mm!r}, {operation.y_mm!r}, 4), 1e-7, True)")
            elif isinstance(operation, RectangularPocketOperation):
                probe_lines.append(f"pocket_{operation.operation_id} = not shape.isInside(FreeCAD.Vector({operation.x_mm + operation.length_mm / 2!r}, {operation.y_mm + operation.width_mm / 2!r}, {base.thickness_mm - operation.depth_mm / 2!r}), 1e-7, True)")
            elif isinstance(operation, ThroughSlotOperation):
                major_offset = operation.length_mm / 2 - operation.width_mm / 4
                points = ((operation.center_x_mm, operation.center_y_mm), (operation.center_x_mm + (major_offset if operation.orientation == "x" else 0), operation.center_y_mm + (major_offset if operation.orientation == "y" else 0)), (operation.center_x_mm - (major_offset if operation.orientation == "x" else 0), operation.center_y_mm - (major_offset if operation.orientation == "y" else 0)))
                for index, point in enumerate(points, start=1):
                    probe_lines.append(f"slot_{operation.operation_id}_{index} = not shape.isInside(FreeCAD.Vector({point[0]!r}, {point[1]!r}, {base.thickness_mm / 2!r}), 1e-7, True)")
        probe_names = [f"hole_{operation.operation_id}" for operation in program.operations if isinstance(operation, ThroughHoleOperation)] + [f"pocket_{operation.operation_id}" for operation in program.operations if isinstance(operation, RectangularPocketOperation)] + [f"slot_{operation.operation_id}_{index}" for operation in program.operations if isinstance(operation, ThroughSlotOperation) for index in range(1, 4)]
        probe_payload = "{" + ",".join(f"{name!r}: {name}" for name in probe_names) + "}"
        from mechcad_harness.cad_manifest import build_program_manifest
        expected_manifest = build_program_manifest(program)
        final_name = expected_manifest.operations[-1].internal_name
        expected_manifest_json = json.dumps(expected_manifest.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        fcstd_script = f'''import FreeCAD, json
doc = FreeCAD.openDocument({str(fcstd_path)!r})
obj = doc.getObject({final_name!r})
if obj is None or obj.Shape.isNull(): raise RuntimeError("expected FCStd object is invalid")
manifest = doc.getObject("program_manifest")
if manifest is None: raise RuntimeError("expected CAD manifest is missing")
if manifest.ManifestJson != {expected_manifest_json!r}: raise RuntimeError("CAD manifest mismatch")
parsed = json.loads(manifest.ManifestJson)
if parsed.get("part_id") != {program.part_id!r} or parsed.get("program_hash") != {expected_manifest.program_hash!r}: raise RuntimeError("CAD manifest binding mismatch")
if [entry["operation_id"] for entry in parsed["operations"]] != {[entry.operation_id for entry in expected_manifest.operations]!r}: raise RuntimeError("CAD manifest order mismatch")
if [entry["operation_kind"] for entry in parsed["operations"]] != {[entry.operation_kind for entry in expected_manifest.operations]!r}: raise RuntimeError("CAD manifest kind mismatch")
if [entry["internal_name"] for entry in parsed["operations"]] != {[entry.internal_name for entry in expected_manifest.operations]!r}: raise RuntimeError("CAD manifest identity mismatch")
box = obj.Shape.BoundBox
shape = obj.Shape
{chr(10).join(probe_lines)}
print("M7A1_JSON=" + json.dumps({{"status":"verified","object_name":obj.Name,"shape_valid":shape.isValid(),"x_length_mm":box.XLength,"y_length_mm":box.YLength,"z_length_mm":box.ZLength,"volume_mm3":shape.Volume,"solid_count":len(shape.Solids),"feature_probes":{probe_payload}}}, sort_keys=True))
FreeCAD.closeDocument(doc.Name)
'''
        step_probe_lines = []
        for operation in program.operations:
            if isinstance(operation, ThroughSlotOperation):
                major_offset = operation.length_mm / 2 - operation.width_mm / 4
                points = ((operation.center_x_mm, operation.center_y_mm), (operation.center_x_mm + (major_offset if operation.orientation == "x" else 0), operation.center_y_mm + (major_offset if operation.orientation == "y" else 0)), (operation.center_x_mm - (major_offset if operation.orientation == "x" else 0), operation.center_y_mm - (major_offset if operation.orientation == "y" else 0)))
                for index, point in enumerate(points, start=1):
                    step_probe_lines.append(f"slot_{operation.operation_id}_{index} = not shape.isInside(FreeCAD.Vector({point[0]!r}, {point[1]!r}, {base.thickness_mm / 2!r}), 1e-7, True)")
        step_probe_payload = "{" + ",".join(f"{name!r}: {name}" for name in [f"slot_{operation.operation_id}_{index}" for operation in program.operations if isinstance(operation, ThroughSlotOperation) for index in range(1, 4)]) + "}"
        step_script = f'''import FreeCAD, Part, json
doc = FreeCAD.newDocument("M7A1StepVerify")
Part.insert({str(step_path)!r}, doc.Name)
doc.recompute()
objects = [obj for obj in doc.Objects if hasattr(obj, "Shape") and not obj.Shape.isNull()]
if not objects: raise RuntimeError("STEP import produced no shape")
shape = objects[0].Shape
box = shape.BoundBox
{chr(10).join(step_probe_lines)}
print("M7A1_JSON=" + json.dumps({{"status":"verified","object_name":objects[0].Name,"shape_valid":shape.isValid(),"x_length_mm":box.XLength,"y_length_mm":box.YLength,"z_length_mm":box.ZLength,"volume_mm3":shape.Volume,"solid_count":len(shape.Solids),"feature_probes":{step_probe_payload}}}, sort_keys=True))
FreeCAD.closeDocument(doc.Name)
'''
        with tempfile.TemporaryDirectory(prefix="mechcad-freecad-verify-") as directory:
            fcstd_verification = self._parse_verification(self._run(discovery.executable, fcstd_script, cwd=Path(directory)), expected=expected, object_name=final_name)
            step_verification = self._parse_verification(self._run(discovery.executable, step_script, cwd=Path(directory)), expected=expected, object_name=None)
        return FreeCADGenerationResult(fcstd=fcstd_artifact, step=step_artifact, fcstd_verification=fcstd_verification, step_verification=step_verification, project_id=project_id, run_id=run_id, bound_revision=revision, bound_state_hash=state_hash, backend_version=FREECAD_BACKEND_VERSION, freecad_version=_freecad_version(discovery))
