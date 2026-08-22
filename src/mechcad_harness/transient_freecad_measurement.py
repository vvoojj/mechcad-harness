from __future__ import annotations

from collections.abc import Callable
import json
import math
import tempfile
from pathlib import Path

from mechcad_harness.analysis_provenance import (
    TRANSIENT_MEASUREMENT_EXECUTION_MODE,
    TRANSIENT_MEASUREMENT_PROVIDER_NAME,
    TRANSIENT_MEASUREMENT_PROVIDER_VERSION,
)
from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.backends.freecad import FreeCADBackend, FreeCADExecutionError, discover_freecad
from mechcad_harness.backends.models import BackendProvenance
from mechcad_harness.cad_assembly import CadAssemblyProgram, assembly_hash
from mechcad_harness.imported_component import ImportedCadComponent
from mechcad_harness.transient_assembly_analysis import TransientAssemblyAnalysisRequest


class FreeCADTransientAssemblyMeasurementProvider:
    provider_name: str = TRANSIENT_MEASUREMENT_PROVIDER_NAME
    provider_version: str = TRANSIENT_MEASUREMENT_PROVIDER_VERSION
    execution_mode: str = TRANSIENT_MEASUREMENT_EXECUTION_MODE

    def provenance(self) -> BackendProvenance:
        return self.backend.provenance()
    def __init__(
        self,
        *,
        execute: Callable[
            [TransientAssemblyAnalysisRequest, CadAssemblyProgram],
            tuple[tuple[str, str, float, float], ...],
        ] | None = None,
        execute_in_workspace: Callable[
            [TransientAssemblyAnalysisRequest, CadAssemblyProgram, Path],
            tuple[tuple[str, str, float, float], ...],
        ] | None = None,
        backend: FreeCADBackend | None = None,
        workspace: str | Path | None = None,
        project_id: str | None = None,
    ):
        self.execute = execute
        self.execute_in_workspace = execute_in_workspace
        self.backend = backend or FreeCADBackend()
        self.workspace = Path(workspace) if workspace is not None else None
        self.project_id = project_id

    def exact_measure(
        self,
        request: TransientAssemblyAnalysisRequest,
        program: CadAssemblyProgram,
    ) -> tuple[tuple[str, str, float, float], ...]:
        if request.transformed_assembly_hash != assembly_hash(program):
            raise ValueError("transformed assembly hash mismatch")
        if self.execute is not None:
            measurements = tuple(self.execute(request, program))
        else:
            with tempfile.TemporaryDirectory(prefix="mechcad-transient-measure-") as directory:
                workspace = Path(directory)
                measurements = tuple(
                    self.execute_in_workspace(request, program, workspace)
                    if self.execute_in_workspace is not None
                    else self._execute_in_workspace(request, program, workspace)
                )
        if tuple((moving, stationary) for moving, stationary, _, _ in measurements) != request.pairs:
            raise ValueError("exact measurement pairs do not match requested pair inventory")
        return measurements

    def _execute_in_workspace(
        self,
        request: TransientAssemblyAnalysisRequest,
        program: CadAssemblyProgram,
        workspace: Path,
    ) -> tuple[tuple[str, str, float, float], ...]:
        discovery = discover_freecad().require_available()
        part_paths = {}
        for part in program.canonical_parts:
            fcstd_path = workspace / f"{part.part_id}.FCStd"
            step_path = workspace / f"{part.part_id}.step"
            completed = self.backend._run(
                discovery.executable,
                self.backend.compile_program(part, str(fcstd_path), str(step_path)),
                cwd=workspace,
            )
            if completed.returncode != 0 or not fcstd_path.is_file():
                raise FreeCADExecutionError(completed.stderr or completed.stdout or "transient component compilation failed")
            part_paths[part.part_id] = fcstd_path
        imported_paths = {}
        imported_ids = {comp.component_id for comp in program.canonical_imported_components}
        for component in program.canonical_imported_components:
            imported_paths[component.component_id] = self._resolve_imported_artifact_path(component)
        script = self._measurement_script(program, request.pairs, part_paths, imported_paths, imported_ids)
        completed = self.backend._run(discovery.executable, script, cwd=workspace)
        if completed.returncode != 0:
            raise FreeCADExecutionError(completed.stderr or completed.stdout or "transient assembly measurement failed")
        line = next((line for line in completed.stdout.splitlines() if line.startswith("M7C1_JSON=")), None)
        if line is None:
            raise FreeCADExecutionError("transient assembly measurement output is missing")
        payload = json.loads(line.removeprefix("M7C1_JSON="))
        measurements = tuple(
            (item["moving_instance_id"], item["stationary_instance_id"], float(item["interference_volume_mm3"]), float(item["exact_distance_mm"]))
            for item in payload["measurements"]
        )
        return measurements

    def _resolve_imported_artifact_path(self, component: ImportedCadComponent) -> Path:
        if self.workspace is None or not self.project_id:
            raise FreeCADExecutionError("imported transient assembly measurement requires workspace and project_id")
        if not component.artifact_id or not component.artifact_hash:
            raise FreeCADExecutionError("imported component is missing artifact identity")
        store = ArtifactStore(self.workspace, project_id=self.project_id, run_id="_transient_lookup")
        artifact = store.existing_in_project(component.artifact_id)
        if artifact is None:
            raise FreeCADExecutionError(f"imported artifact not found in workspace: {component.artifact_id}")
        if artifact.artifact_type != ArtifactType.STEP:
            raise FreeCADExecutionError(f"imported artifact is not a STEP: {component.artifact_id}")
        if artifact.sha256 != component.artifact_hash:
            raise FreeCADExecutionError(f"imported artifact hash mismatch in transient measurement: {component.artifact_id}")
        path = self.workspace / artifact.relative_path
        if not path.is_file():
            raise FreeCADExecutionError(f"imported artifact file is missing: {component.artifact_id}")
        return path

    @staticmethod
    def _measurement_script(
        program: CadAssemblyProgram,
        pairs: tuple[tuple[str, str], ...],
        part_paths: dict[str, Path],
        imported_paths: dict[str, Path],
        imported_ids: set[str],
    ) -> str:
        records = []
        for instance in program.canonical_instances:
            w, x, y, z = instance.placement.rotation_quaternion
            angle = 2 * math.degrees(math.acos(max(-1.0, min(1.0, w))))
            scale = math.sqrt(max(0.0, 1.0 - w * w))
            axis = (0.0, 0.0, 1.0) if scale <= 1e-12 else (x / scale, y / scale, z / scale)
            if instance.part_id in imported_ids:
                records.append((instance.instance_id, True, str(imported_paths[instance.part_id]), instance.placement.x_mm, instance.placement.y_mm, instance.placement.z_mm, axis, angle))
            else:
                records.append((instance.instance_id, False, str(part_paths[instance.part_id]), instance.placement.x_mm, instance.placement.y_mm, instance.placement.z_mm, axis, angle))
        return "\n".join(
            [
                "import FreeCAD, Part, json",
                "doc = FreeCAD.newDocument('TransientAssemblyMeasurement')",
                "shapes = {}",
                f"records = {records!r}",
                "for instance_id, is_imported, path, x, y, z, axis, angle in records:",
                "    if is_imported:",
                "        source = FreeCAD.newDocument('ImportedStep')",
                "        Part.insert(path, source.Name)",
                "        candidates = [obj for obj in source.Objects if hasattr(obj, 'Shape') and not obj.Shape.isNull()]",
                "        if not candidates: raise RuntimeError('imported step shape missing')",
                "        shape = candidates[0].Shape.copy()",
                "        FreeCAD.closeDocument(source.Name)",
                "    else:",
                "        source = FreeCAD.openDocument(path)",
                "        candidates = [obj for obj in source.Objects if hasattr(obj, 'Shape') and not obj.Shape.isNull()]",
                "        if not candidates: raise RuntimeError('transient part shape missing')",
                "        shape = candidates[0].Shape.copy()",
                "        FreeCAD.closeDocument(source.Name)",
                "    shape.Placement.Base = FreeCAD.Vector(x, y, z)",
                "    shape.Placement.Rotation = FreeCAD.Rotation(FreeCAD.Vector(*axis), angle)",
                "    if shape.isNull() or not shape.isValid(): raise RuntimeError('transient shape invalid')",
                "    shapes[instance_id] = shape",
                f"pairs = {pairs!r}",
                "measurements = []",
                "for moving, stationary in pairs:",
                "    a, b = shapes[moving], shapes[stationary]",
                "    measurements.append({'moving_instance_id': moving, 'stationary_instance_id': stationary, 'interference_volume_mm3': float(a.common(b).Volume), 'exact_distance_mm': float(a.distToShape(b)[0])})",
                "print('M7C1_JSON=' + json.dumps({'measurements': measurements}, sort_keys=True))",
                "FreeCAD.closeDocument(doc.Name)",
                "",
            ]
        )
