from __future__ import annotations

from collections.abc import Callable
from copy import copy
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
from mechcad_harness.multi_joint_continuous_path import TrustedLocalGeometryExtent


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

    def composition_snapshot(self) -> "FreeCADTransientAssemblyMeasurementProvider":
        """Capture the provider execution boundary for production-owned v2 use."""
        return FreeCADTransientAssemblyMeasurementProvider(
            execute=self.execute,
            execute_in_workspace=self.execute_in_workspace,
            backend=copy(self.backend),
            workspace=self.workspace,
            project_id=self.project_id,
        )

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
        if tuple((first, second) for first, second, _, _ in measurements) != request.pairs:
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

    def geometry_radial_bounds(
        self,
        program: CadAssemblyProgram,
        axis,
        moving_instance_ids: tuple[str, ...],
    ) -> dict[str, float]:
        """Compute conservative radial bounds for each moving instance.

        Returns a dict mapping instance_id to the conservative upper bound on
        the distance from any point of that instance's geometry to the revolute
        axis line. Uses FreeCAD bounding box corner distances.
        """
        if self.execute is not None:
            raise FreeCADExecutionError("geometry radial bounds require real FreeCAD geometry")
        discovery = discover_freecad().require_available()
        moving_ids = set(moving_instance_ids)
        moving_part_ids = {inst.part_id for inst in program.canonical_instances if inst.instance_id in moving_ids}
        imported_ids = {comp.component_id for comp in program.canonical_imported_components}
        with tempfile.TemporaryDirectory(prefix="mechcad-radial-") as directory:
            workspace = Path(directory)
            part_paths = {}
            for part in program.canonical_parts:
                if not any(inst.part_id == part.part_id and inst.instance_id in moving_ids for inst in program.canonical_instances):
                    continue
                fcstd_path = workspace / f"{part.part_id}.FCStd"
                step_path = workspace / f"{part.part_id}.step"
                completed = self.backend._run(
                    discovery.executable,
                    self.backend.compile_program(part, str(fcstd_path), str(step_path)),
                    cwd=workspace,
                )
                if completed.returncode != 0 or not fcstd_path.is_file():
                    raise FreeCADExecutionError(completed.stderr or completed.stdout or "radial bound part compilation failed")
                part_paths[part.part_id] = fcstd_path
            imported_paths = {}
            for component in program.canonical_imported_components:
                if component.component_id in moving_part_ids:
                    imported_paths[component.component_id] = self._resolve_imported_artifact_path(component)
            records = []
            for instance in program.canonical_instances:
                if instance.instance_id not in moving_ids:
                    continue
                w, x, y, z = instance.placement.rotation_quaternion
                angle = 2 * math.degrees(math.acos(max(-1.0, min(1.0, w))))
                scale = math.sqrt(max(0.0, 1.0 - w * w))
                inst_axis = (0.0, 0.0, 1.0) if scale <= 1e-12 else (x / scale, y / scale, z / scale)
                if instance.part_id in imported_ids:
                    records.append((instance.instance_id, True, str(imported_paths[instance.part_id]), instance.placement.x_mm, instance.placement.y_mm, instance.placement.z_mm, inst_axis, angle))
                else:
                    records.append((instance.instance_id, False, str(part_paths[instance.part_id]), instance.placement.x_mm, instance.placement.y_mm, instance.placement.z_mm, inst_axis, angle))
            script = self._radial_script(records, axis)
            completed = self.backend._run(discovery.executable, script, cwd=workspace)
            if completed.returncode != 0:
                raise FreeCADExecutionError(completed.stderr or completed.stdout or "radial bound computation failed")
            line = next((l for l in completed.stdout.splitlines() if l.startswith("M10_RADIAL=")), None)
            if line is None:
                raise FreeCADExecutionError("radial bound output missing")
            payload = json.loads(line.removeprefix("M10_RADIAL="))
            return {instance_id: float(value) for instance_id, value in payload["radii"].items()}

    def trusted_local_geometry_extents(
        self,
        program: CadAssemblyProgram,
        instance_ids: tuple[str, ...],
    ) -> dict[str, TrustedLocalGeometryExtent]:
        """Return trusted component-local extents for the M10-4 topology layer."""
        radii = self._component_local_geometry_radii(program, instance_ids)
        instances = {instance.instance_id: instance for instance in program.canonical_instances}
        return {
            instance_id: TrustedLocalGeometryExtent(
                instance_id=instance_id,
                component_identity=f"{program.assembly_id}:{instances[instance_id].part_id}",
                local_radius_mm=radius,
            )
            for instance_id, radius in radii.items()
        }

    def _component_local_geometry_radii(
        self,
        program: CadAssemblyProgram,
        instance_ids: tuple[str, ...],
    ) -> dict[str, float]:
        """Use real FreeCAD bounding-box corners in component-local coordinates."""
        if self.execute is not None:
            raise FreeCADExecutionError("trusted geometry extents require real FreeCAD geometry")
        discovery = discover_freecad().require_available()
        selected = set(instance_ids)
        with tempfile.TemporaryDirectory(prefix="mechcad-local-extent-") as directory:
            workspace = Path(directory)
            part_paths = {}
            for part in program.canonical_parts:
                if not any(instance.instance_id in selected and instance.part_id == part.part_id for instance in program.canonical_instances):
                    continue
                fcstd_path = workspace / f"{part.part_id}.FCStd"
                step_path = workspace / f"{part.part_id}.step"
                completed = self.backend._run(discovery.executable, self.backend.compile_program(part, str(fcstd_path), str(step_path)), cwd=workspace)
                if completed.returncode != 0 or not fcstd_path.is_file():
                    raise FreeCADExecutionError(completed.stderr or completed.stdout or "local extent compilation failed")
                part_paths[part.part_id] = fcstd_path
            imported_paths = {
                component.component_id: self._resolve_imported_artifact_path(component)
                for component in program.canonical_imported_components
                if any(instance.instance_id in selected and instance.part_id == component.component_id for instance in program.canonical_instances)
            }
            records = [
                (
                    instance.instance_id,
                    instance.part_id in imported_paths,
                    str(
                        imported_paths[instance.part_id]
                        if instance.part_id in imported_paths
                        else part_paths[instance.part_id]
                    ),
                )
                for instance in program.canonical_instances
                if instance.instance_id in selected and (instance.part_id in part_paths or instance.part_id in imported_paths)
            ]
            completed = self.backend._run(discovery.executable, self._local_extent_script(records), cwd=workspace)
            if completed.returncode != 0:
                raise FreeCADExecutionError(completed.stderr or completed.stdout or "local extent measurement failed")
            line = next((item for item in completed.stdout.splitlines() if item.startswith("M10_LOCAL_EXTENT=")), None)
            if line is None:
                raise FreeCADExecutionError("local extent output missing")
            return {key: float(value) for key, value in json.loads(line.removeprefix("M10_LOCAL_EXTENT="))["radii"].items()}

    @staticmethod
    def _local_extent_script(records) -> str:
        return "\n".join([
            "import FreeCAD, Part, json",
            f"records = {records!r}",
            "radii = {}",
            "for instance_id, is_imported, path in records:",
            "    source = FreeCAD.newDocument('ImportedLocalExtent') if is_imported else FreeCAD.openDocument(path)",
            "    if is_imported: Part.insert(path, source.Name)",
            "    candidates = [obj for obj in source.Objects if hasattr(obj, 'Shape') and not obj.Shape.isNull()]",
            "    if not candidates: raise RuntimeError('local extent shape missing')",
            "    shape = Part.makeCompound([c.Shape.copy() for c in candidates])",
            "    box = shape.BoundBox",
            "    corners = [(box.XMin, box.YMin, box.ZMin), (box.XMin, box.YMin, box.ZMax), (box.XMin, box.YMax, box.ZMin), (box.XMin, box.YMax, box.ZMax), (box.XMax, box.YMin, box.ZMin), (box.XMax, box.YMin, box.ZMax), (box.XMax, box.YMax, box.ZMin), (box.XMax, box.YMax, box.ZMax)]",
            "    radii[instance_id] = max((x*x + y*y + z*z) ** 0.5 for x, y, z in corners) + 1e-9",
            "    FreeCAD.closeDocument(source.Name)",
            "print('M10_LOCAL_EXTENT=' + json.dumps({'radii': radii}, sort_keys=True))",
        ])

    @staticmethod
    def _radial_script(records, axis) -> str:
        return "\n".join([
            "import FreeCAD, Part, json",
            "doc = FreeCAD.newDocument('RadialBound')",
            "shapes = {}",
            f"records = {records!r}",
            "for instance_id, is_imported, path, x, y, z, axis, angle in records:",
            "    if is_imported:",
            "        source = FreeCAD.newDocument('ImportedStep')",
            "        Part.insert(path, source.Name)",
            "        candidates = [obj for obj in source.Objects if hasattr(obj, 'Shape') and not obj.Shape.isNull()]",
            "        if not candidates: raise RuntimeError('imported step shape missing')",
            "        shape = Part.makeCompound([c.Shape.copy() for c in candidates])",
            "        FreeCAD.closeDocument(source.Name)",
            "    else:",
            "        source = FreeCAD.openDocument(path)",
            "        candidates = [obj for obj in source.Objects if hasattr(obj, 'Shape') and not obj.Shape.isNull()]",
            "        if not candidates: raise RuntimeError('part shape missing')",
            "        shape = candidates[0].Shape.copy()",
            "        FreeCAD.closeDocument(source.Name)",
            "    shape.Placement.Base = FreeCAD.Vector(x, y, z)",
            "    shape.Placement.Rotation = FreeCAD.Rotation(FreeCAD.Vector(*axis), angle)",
            "    if shape.isNull() or not shape.isValid(): raise RuntimeError('shape invalid')",
            "    shapes[instance_id] = shape",
            f"Ox, Oy, Oz = {axis.origin_x_mm!r}, {axis.origin_y_mm!r}, {axis.origin_z_mm!r}",
            f"Ux, Uy, Uz = {axis.direction_x!r}, {axis.direction_y!r}, {axis.direction_z!r}",
            "radii = {}",
            "for instance_id, shape in shapes.items():",
            "    box = shape.BoundBox",
            "    corners = [",
            "        FreeCAD.Vector(box.XMin, box.YMin, box.ZMin),",
            "        FreeCAD.Vector(box.XMin, box.YMin, box.ZMax),",
            "        FreeCAD.Vector(box.XMin, box.YMax, box.ZMin),",
            "        FreeCAD.Vector(box.XMin, box.YMax, box.ZMax),",
            "        FreeCAD.Vector(box.XMax, box.YMin, box.ZMin),",
            "        FreeCAD.Vector(box.XMax, box.YMin, box.ZMax),",
            "        FreeCAD.Vector(box.XMax, box.YMax, box.ZMin),",
            "        FreeCAD.Vector(box.XMax, box.YMax, box.ZMax),",
            "    ]",
            "    max_d = 0.0",
            "    for c in corners:",
            "        rx, ry, rz = c.x - Ox, c.y - Oy, c.z - Oz",
            "        cx = ry * Uz - rz * Uy",
            "        cy = rz * Ux - rx * Uz",
            "        cz = rx * Uy - ry * Ux",
            "        dist = (cx*cx + cy*cy + cz*cz) ** 0.5",
            "        if dist > max_d: max_d = dist",
            "    radii[instance_id] = float(max_d)",
            "print('M10_RADIAL=' + json.dumps({'radii': radii}, sort_keys=True))",
            "FreeCAD.closeDocument(doc.Name)",
            "",
        ])

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
                "        shape = Part.makeCompound([c.Shape.copy() for c in candidates])",
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
                "for first, second in pairs:",
                "    a, b = shapes[first], shapes[second]",
                "    measurements.append({'moving_instance_id': first, 'stationary_instance_id': second, 'interference_volume_mm3': float(a.common(b).Volume), 'exact_distance_mm': float(a.distToShape(b)[0])})",
                "print('M7C1_JSON=' + json.dumps({'measurements': measurements}, sort_keys=True))",
                "FreeCAD.closeDocument(doc.Name)",
                "",
            ]
        )
