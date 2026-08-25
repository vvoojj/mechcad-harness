from __future__ import annotations

import json
import math
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from mechcad_harness.models.structural import StructuralRegionDefinition
from mechcad_harness.structural.models import (
    REGION_RESOLVER_IDENTITY,
    PhysicalGroupBinding,
    ResolvedRegionMap,
    ResolvedStructuralRegion,
    SemanticGeometryKind,
    region_map_hash,
    resolved_region_hash,
)
from mechcad_harness.structural.runtime import DiscoveredRuntime, RuntimeUnavailableError
from mechcad_harness.structural.tolerances import PLANAR_REGION_MATCH_TOLERANCES


class GeometryResolutionError(Exception):
    pass


class RegionResolutionError(Exception):
    pass


@dataclass(frozen=True)
class FaceDescriptor:
    area: float
    centroid: tuple[float, float, float]
    normal: tuple[float, float, float]
    bbox: tuple[float, float, float, float, float, float]
    planarity: float


@dataclass
class GeometryRealization:
    shape_valid: bool
    solid_count: int
    faces: list[FaceDescriptor]
    bounding_box: tuple[float, float, float, float, float, float] | None = None


_GEO_SCRIPT = """import FreeCAD, Part, json
doc = FreeCAD.newDocument("M11Geo")
Part.insert({step!r}, doc.Name)
doc.recompute()
objs = [o for o in doc.Objects if hasattr(o, "Shape") and not o.Shape.isNull()]
if not objs:
    raise RuntimeError("STEP import produced no shape")
# A STEP import may produce several document objects.  Aggregate every shape
# before applying the one-solid admission rule so no imported body is ignored.
shape = Part.makeCompound([o.Shape for o in objs])
faces = []
for f in shape.Faces:
    c = f.CenterOfMass
    n = f.normalAt(0, 0)
    bb = f.BoundBox
    pts, _tris = f.tessellate(0.01)
    nx, ny, nz = n.x, n.y, n.z
    maxd = 0.0
    for p in pts:
        d = (p.x - c.x) * nx + (p.y - c.y) * ny + (p.z - c.z) * nz
        if abs(d) > maxd:
            maxd = abs(d)
    faces.append({{"area": f.Area, "centroid": [c.x, c.y, c.z], "normal": [nx, ny, nz],
                  "bbox": [bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax], "planarity": maxd}})
out = {{"shape_valid": shape.isValid(), "solid_count": len(shape.Solids), "faces": faces,
       "bounding_box": [shape.BoundBox.XMin, shape.BoundBox.YMin, shape.BoundBox.ZMin,
                        shape.BoundBox.XMax, shape.BoundBox.YMax, shape.BoundBox.ZMax]}}
print("M11GEO=" + json.dumps(out, sort_keys=True))
FreeCAD.closeDocument(doc.Name)
"""


class StructuralFreeCADGeometryAdapter:
    """Narrow public-boundary adapter that reuses the trusted FreeCAD command-line
    boundary to realize exact BREP geometry.  It does not call FreeCADBackend
    private methods and does not embed FEA semantics into the CAD backend."""

    identity = REGION_RESOLVER_IDENTITY
    resolver_version = "1"

    def __init__(self, discovery: DiscoveredRuntime):
        self._discovery = discovery

    def realize_geometry(self, step_path: str | Path) -> GeometryRealization:
        try:
            discovery = self._discovery.require_available()
        except RuntimeUnavailableError as exc:
            raise GeometryResolutionError(f"FreeCAD geometry runtime unavailable: {exc}") from exc
        script = _GEO_SCRIPT.format(step=str(step_path))
        with tempfile.TemporaryDirectory(prefix="mechcad-struct-geo-") as directory:
            cwd = Path(directory)
            script_path = cwd / "geo_runner.py"
            script_path.write_text(script, encoding="ascii")
            try:
                result = subprocess.run([discovery.executable, str(script_path)], cwd=cwd,
                                         capture_output=True, text=True, timeout=240, check=False)
            except subprocess.TimeoutExpired as exc:
                raise GeometryResolutionError("FreeCAD geometry realization timed out") from exc
        if result.returncode != 0:
            raise GeometryResolutionError(result.stderr or result.stdout or "FreeCAD geometry realization failed")
        line = next((ln for ln in result.stdout.splitlines() if ln.startswith("M11GEO=")), None)
        if line is None:
            raise GeometryResolutionError(
                "FreeCAD geometry realization produced no structured output\nSTDOUT:\n" + result.stdout[-2000:] + "\nSTDERR:\n" + result.stderr[-2000:])
        try:
            payload = json.loads(line.removeprefix("M11GEO="))
            if not isinstance(payload, dict):
                raise ValueError("structured geometry output must be an object")
            if payload.get("shape_valid") is not True:
                raise GeometryResolutionError("realized FreeCAD shape is invalid")
            solid_count = payload["solid_count"]
            if isinstance(solid_count, bool) or not isinstance(solid_count, int) or solid_count < 0:
                raise ValueError("solid_count is invalid")
            raw_faces = payload["faces"]
            if not isinstance(raw_faces, list) or not raw_faces:
                raise ValueError("faces are invalid")

            def finite(value):
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError("geometry contains a non-finite value")
                return number

            def vector(value, length):
                if not isinstance(value, (list, tuple)) or len(value) != length:
                    raise ValueError("geometry vector has the wrong length")
                return tuple(finite(item) for item in value)

            faces = [
                FaceDescriptor(
                    area=finite(face["area"]),
                    centroid=vector(face["centroid"], 3),
                    normal=vector(face["normal"], 3),
                    bbox=vector(face["bbox"], 6),
                    planarity=finite(face["planarity"]),
                )
                for face in raw_faces
                if isinstance(face, dict)
            ]
            if len(faces) != len(raw_faces):
                raise ValueError("face descriptor is invalid")
            bounding_box = payload.get("bounding_box")
            parsed_bounding_box = None if bounding_box is None else vector(bounding_box, 6)
        except GeometryResolutionError:
            raise
        except Exception as exc:
            raise GeometryResolutionError("FreeCAD geometry realization produced malformed structured output") from exc
        return GeometryRealization(
            shape_valid=True,
            solid_count=solid_count,
            faces=faces,
            bounding_box=parsed_bounding_box,
        )


def _axis_index(axis: str) -> int:
    return {"x": 0, "y": 1, "z": 2}[axis]


def _resolve_one(region: StructuralRegionDefinition, faces: list[FaceDescriptor],
                  tolerances=PLANAR_REGION_MATCH_TOLERANCES) -> ResolvedStructuralRegion:
    if region.geometry_kind != "face":
        raise RegionResolutionError(f"unsupported geometry kind for region {region.region_id}: {region.geometry_kind}")
    kind = region.selector_kind
    if kind != "planar_face_centroid_axis":
        raise RegionResolutionError(f"unsupported selector kind for region {region.region_id}: {kind}")
    axis = str(region.selector_parameters.get("axis", ""))
    side = str(region.selector_parameters.get("side", ""))
    if axis not in {"x", "y", "z"} or side not in {"min", "max"}:
        raise RegionResolutionError(f"invalid planar_face_centroid_axis parameters for region {region.region_id}")
    ai = _axis_index(axis)
    planar = [f for f in faces if f.planarity < tolerances.planarity_mm]
    if not planar:
        raise RegionResolutionError(f"no planar faces available for region {region.region_id}")
    target = min(f.centroid[ai] for f in planar) if side == "min" else max(f.centroid[ai] for f in planar)
    matches = [f for f in planar if abs(f.centroid[ai] - target) <= 1e-9]
    if len(matches) == 0:
        raise RegionResolutionError(f"region {region.region_id} matched zero faces")
    if len(matches) != region.expected_cardinality:
        raise RegionResolutionError(
            f"region {region.region_id} cardinality mismatch: expected {region.expected_cardinality}, found {len(matches)}")
    face = matches[0]
    descriptor = f"planar_face_centroid_axis({axis},{side})"
    resolved = ResolvedStructuralRegion(
        region_id=region.region_id,
        source_geometry_hash="pending",
        resolver_identity=REGION_RESOLVER_IDENTITY,
        resolver_version="1",
        geometry_kind=SemanticGeometryKind.PLANAR_FACE,
        exact_brep_area_mm2=face.area,
        exact_brep_centroid_mm=face.centroid,
        plane_normal=face.normal,
        bounding_box_mm=face.bbox,
        expected_cardinality=region.expected_cardinality,
        actual_cardinality=len(matches),
        semantic_descriptor=descriptor,
        region_realization_hash="pending",
    )
    return resolved.model_copy(update={"region_realization_hash": resolved_region_hash(resolved)})


class StructuralRegionResolver:
    identity = REGION_RESOLVER_IDENTITY
    resolver_version = "1"

    def __init__(self, tolerances=PLANAR_REGION_MATCH_TOLERANCES):
        self._tolerances = tolerances

    def resolve(self, regions: Iterable[StructuralRegionDefinition], realization: GeometryRealization,
                *, source_geometry_hash: str) -> ResolvedRegionMap:
        if realization.solid_count != 1:
            raise RegionResolutionError(f"expected exactly one solid, found {realization.solid_count}")
        if not realization.shape_valid:
            raise RegionResolutionError("realized geometry is not a valid solid")
        resolved = []
        for region in regions:
            r = _resolve_one(region, realization.faces, self._tolerances)
            resolved.append(r.model_copy(update={"source_geometry_hash": source_geometry_hash}))
        rmap = ResolvedRegionMap(
            source_geometry_hash=source_geometry_hash,
            resolver_identity=self.identity,
            resolver_version=self.resolver_version,
            match_policy_id=self._tolerances.policy_id,
            regions=tuple(resolved),
            region_map_hash="pending",
        )
        return rmap.model_copy(update={"region_map_hash": region_map_hash(rmap.regions,
                             source_geometry_hash=source_geometry_hash, match_policy_id=self._tolerances.policy_id)})
