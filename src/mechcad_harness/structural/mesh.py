from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Iterable

from mechcad_harness.models.structural import StructuralRegionDefinition
from mechcad_harness.structural.models import (
    GMSH_PROVIDER_IDENTITY,
    PhysicalGroupBinding,
    ResolvedRegionMap,
    StructuralMeshManifest,
    mesh_manifest_hash,
)
from mechcad_harness.structural.runtime import DiscoveredRuntime, RuntimeUnavailableError
from mechcad_harness.structural.tolerances import (
    C3D10_GEOMETRY_TOLERANCE_MM,
    PLANAR_REGION_MATCH_TOLERANCES,
)

GMSH_PROVIDER_VERSION = "1"


class MeshProviderError(Exception):
    pass


# CalculiX local face table (corner + midside local C3D10 node indices).
C3D10_LOCAL_FACES = {
    "S1": (1, 3, 2, 7, 6, 5),
    "S2": (1, 2, 4, 5, 9, 8),
    "S3": (2, 3, 4, 6, 10, 9),
    "S4": (1, 4, 3, 8, 10, 7),
}

# Midside ordering relative to corner edges: position 5..10.
_C3D10_MIDSIDE_EDGES = (
    (1, 2),  # 5
    (2, 3),  # 6
    (1, 3),  # 7
    (1, 4),  # 8
    (2, 4),  # 9
    (3, 4),  # 10
)


@dataclass
class GmshEntityDescriptor:
    dim: int
    tag: int
    area: float
    centroid: tuple[float, float, float]
    normal: tuple[float, float, float]
    planarity: float


@dataclass
class ParsedMesh:
    nodes: dict[int, tuple[float, float, float]]
    c3d10: dict[int, tuple[int, ...]]          # elid -> 10 node ids
    surface_elements: dict[str, list[tuple[int, tuple[int, ...]]]]  # region -> [(elid, 6 nodes)]
    volume_elset_name: str
    physical_groups: tuple[PhysicalGroupBinding, ...]
    mesh_bytes: bytes


@dataclass(frozen=True)
class FrozenParsedMesh:
    """Immutable mesh snapshot used after a trust boundary has been crossed."""

    nodes: MappingProxyType
    c3d10: MappingProxyType
    surface_elements: MappingProxyType
    volume_elset_name: str
    physical_groups: tuple[PhysicalGroupBinding, ...]
    mesh_bytes: bytes


def freeze_parsed_mesh(mesh: ParsedMesh | FrozenParsedMesh) -> FrozenParsedMesh:
    if isinstance(mesh, FrozenParsedMesh):
        return mesh
    if not isinstance(mesh, ParsedMesh):
        raise TypeError("mesh must be a ParsedMesh")
    return FrozenParsedMesh(
        nodes=MappingProxyType({node_id: tuple(coordinates) for node_id, coordinates in mesh.nodes.items()}),
        c3d10=MappingProxyType({element_id: tuple(nodes) for element_id, nodes in mesh.c3d10.items()}),
        surface_elements=MappingProxyType({
            region: tuple((element_id, tuple(nodes)) for element_id, nodes in elements)
            for region, elements in mesh.surface_elements.items()
        }),
        volume_elset_name=mesh.volume_elset_name,
        physical_groups=tuple(mesh.physical_groups),
        mesh_bytes=bytes(mesh.mesh_bytes),
    )


def _area_weighted_triangles(nodes: dict[int, tuple[float, float, float]], elem_nodes: Iterable[tuple[int, ...]]) -> tuple[float, tuple[float, float, float], tuple[float, float, float], float]:
    total_area = 0.0
    cx = cy = cz = 0.0
    nx = ny = nz = 0.0
    max_dist = 0.0
    for tri in elem_nodes:
        a = nodes[tri[0]]
        b = nodes[tri[1]]
        c = nodes[tri[2]]
        ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        cr = (ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0])
        area = 0.5 * math.sqrt(cr[0] * cr[0] + cr[1] * cr[1] + cr[2] * cr[2])
        if area <= 0:
            continue
        # area-weighted centroid and normal
        cx += (a[0] + b[0] + c[0]) / 3.0 * area
        cy += (a[1] + b[1] + c[1]) / 3.0 * area
        cz += (a[2] + b[2] + c[2]) / 3.0 * area
        nx += cr[0] * 0.5
        ny += cr[1] * 0.5
        nz += cr[2] * 0.5
        total_area += area
    if total_area == 0:
        return 0.0, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 0.0
    centroid = (cx / total_area, cy / total_area, cz / total_area)
    norm = math.sqrt(nx * nx + ny * ny + nz * nz)
    if norm == 0:
        normal = (0.0, 0.0, 0.0)
    else:
        normal = (nx / norm, ny / norm, nz / norm)
        # planarity: max distance of corner points to plane through centroid
        for tri in elem_nodes:
            for idx in range(3):
                p = nodes[tri[idx]]
                d = (p[0] - centroid[0]) * normal[0] + (p[1] - centroid[1]) * normal[1] + (p[2] - centroid[2]) * normal[2]
                if abs(d) > max_dist:
                    max_dist = abs(d)
    return total_area, centroid, normal, max_dist


def _parse_msh_v2(content: bytes) -> tuple[dict[int, tuple[float, float, float]], dict[int, list[tuple[int, tuple[int, ...]]]], dict[int, list[tuple[int, tuple[int, ...]]]], dict[int, list[int]], dict[int, tuple[int, ...]]]:
    """Parse MSH 2.0 format. Returns (nodes, surface_entities, volume_entities, {}, physical_of_entity)."""
    text = content.decode("utf-8", errors="replace")
    lines = text.splitlines()
    nodes: dict[int, tuple[float, float, float]] = {}
    surface_entities: dict[int, list[tuple[int, tuple[int, ...]]]] = {}
    volume_entities: dict[int, list[tuple[int, tuple[int, ...]]]] = {}
    physical_of_entity: dict[int, tuple[int, ...]] = {}
    i = 0
    n = len(lines)
    section = None
    while i < n:
        line = lines[i].strip()
        if line == "$Nodes":
            section = "nodes"
            i += 1
            continue
        if line == "$EndNodes":
            section = None
            i += 1
            continue
        if line == "$Elements":
            section = "elements"
            i += 1
            continue
        if line == "$EndElements":
            section = None
            i += 1
            continue
        if section == "nodes":
            parts = line.split()
            if len(parts) >= 4:
                nid = int(parts[0])
                nodes[nid] = (float(parts[1]), float(parts[2]), float(parts[3]))
        elif section == "elements":
            parts = line.split()
            if len(parts) >= 4:
                elid = int(parts[0])
                eltype = int(parts[1])
                num_tags = int(parts[2])
                tags = [int(parts[3 + j]) for j in range(num_tags)]
                node_start = 3 + num_tags
                elnodes = tuple(int(parts[node_start + j]) for j in range(len(parts) - node_start))
                # MSH 2.0: entity tag is usually tags[1] if num_tags >= 2
                etag = tags[1] if num_tags >= 2 else (tags[0] if num_tags >= 1 else 0)
                # Gmsh element types: 2=3-node tri, 9=6-node tri (CPS6), 11=10-node tet (C3D10)
                if eltype in (2, 9, 3, 6):  # surface elements
                    surface_entities.setdefault(etag, []).append((elid, elnodes))
                elif eltype in (4, 5, 11, 17):  # volume elements (11=C3D10)
                    volume_entities.setdefault(etag, []).append((elid, elnodes))
        i += 1
    return nodes, surface_entities, volume_entities, {}, physical_of_entity


def _parse_inp(content: str) -> ParsedMesh:
    nodes: dict[int, tuple[float, float, float]] = {}
    c3d10: dict[int, tuple[int, ...]] = {}
    surface_elements: dict[str, list[tuple[int, tuple[int, ...]]]] = {}
    physical_groups: list[PhysicalGroupBinding] = []
    volume_elset_name = "volume"
    current_eltype = None
    current_elset = None
    elset_aliases: dict[str, list[str]] = {}  # name -> list of referenced ELSETs
    raw_elements: dict[str, list[tuple[int, tuple[int, ...]]]] = {}  # ELSET -> elements
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("**"):
            continue
        if line.startswith("*"):
            lower = line.lower()
            if lower.startswith("*node"):
                current_eltype = "node"
                current_elset = None
                continue
            if lower.startswith("*element"):
                m = re.search(r"type\s*=\s*([a-zA-Z0-9]+)", lower)
                em = re.search(r"elset\s*=\s*([a-zA-Z0-9_]+)", lower)
                current_eltype = m.group(1).upper() if m else None
                current_elset = em.group(1) if em else None
                continue
            if lower.startswith("*elset"):
                em = re.search(r"elset\s*=\s*([a-zA-Z0-9_]+)", lower)
                if em:
                    current_eltype = "elset"
                    current_elset = em.group(1)
                continue
            # any other keyword terminates node/element reading
            current_eltype = None
            current_elset = None
            continue
        if current_eltype == "node":
            parts = line.split(",")
            nid = int(parts[0])
            nodes[nid] = (float(parts[1]), float(parts[2]), float(parts[3]))
        elif current_eltype == "C3D10":
            parts = [p.strip() for p in line.split(",")]
            elid = int(parts[0])
            c3d10[elid] = tuple(int(p) for p in parts[1:])
        elif current_eltype == "CPS6":
            parts = [p.strip() for p in line.split(",")]
            elid = int(parts[0])
            els = tuple(int(p) for p in parts[1:])
            if current_elset:
                raw_elements.setdefault(current_elset, []).append((elid, els))
        elif current_eltype == "elset" and current_elset:
            # *ELSET entries can contain element IDs directly
            ids = [int(r.strip()) for r in line.split(",") if r.strip().isdigit()]
            elset_aliases.setdefault(current_elset, []).extend(ids)
    # Resolve ELSET aliases to build final surface_elements
    for name, ids in elset_aliases.items():
        for eid in ids:
            for elset_name, elems in raw_elements.items():
                for el in elems:
                    if el[0] == eid:
                        surface_elements.setdefault(name, []).append(el)
                        break
        if name in surface_elements:
            physical_groups.append(PhysicalGroupBinding(
                semantic_region_id=name, physical_group_name=name,
                gmsh_entity_dim=2, gmsh_entity_id=-1))
    # Also include raw ELSETs that weren't aliased
    for name, elems in raw_elements.items():
        if name not in surface_elements:
            surface_elements[name] = elems
            physical_groups.append(PhysicalGroupBinding(
                semantic_region_id=name, physical_group_name=name,
                gmsh_entity_dim=2, gmsh_entity_id=-1))
    return ParsedMesh(nodes=nodes, c3d10=c3d10, surface_elements=surface_elements,
                      volume_elset_name=volume_elset_name,
                      physical_groups=tuple(physical_groups), mesh_bytes=content.encode("utf-8"))


class StructuralGmshMeshingProvider:
    identity = GMSH_PROVIDER_IDENTITY
    provider_version = GMSH_PROVIDER_VERSION

    def __init__(self, discovery: DiscoveredRuntime, tolerances=PLANAR_REGION_MATCH_TOLERANCES):
        self._discovery = discovery
        self._tolerances = tolerances

    def _run_gmsh(self, geo_path: Path, out_path: Path, *, out_format: str) -> None:
        try:
            discovery = self._discovery.require_available()
        except RuntimeUnavailableError as exc:
            raise MeshProviderError(f"Gmsh runtime unavailable: {exc}") from exc
        cmd = [discovery.executable, str(geo_path), "-3", "-format", out_format, "-o", str(out_path), "-nopopup"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
        except subprocess.TimeoutExpired as exc:
            raise MeshProviderError("Gmsh meshing timed out") from exc
        except (OSError, subprocess.SubprocessError) as exc:
            raise MeshProviderError(f"Gmsh launch failed: {exc}") from exc
        if result.returncode != 0 or not out_path.is_file() or out_path.stat().st_size == 0:
            raise MeshProviderError(result.stderr or result.stdout or "Gmsh meshing failed")

    def _preview_entities(self, step_path: Path) -> tuple[dict[int, GmshEntityDescriptor], int]:
        with tempfile.TemporaryDirectory(prefix="mechcad-gmsh-prev-") as directory:
            cwd = Path(directory)
            geo = cwd / "preview.geo"
            geo.write_text(f'Merge "{step_path}";\nMesh.ElementOrder = 2;\nMesh 3;\n', encoding="ascii")
            msh = cwd / "preview.msh"
            self._run_gmsh(geo, msh, out_format="msh2")
            nodes, surface_entities, volume_entities, _phys, _ = _parse_msh_v2(msh.read_bytes())
        entities: dict[int, GmshEntityDescriptor] = {}
        for tag, elems in surface_entities.items():
            tris = [e[1][:3] for e in elems]
            area, centroid, normal, planarity = _area_weighted_triangles(nodes, tris)
            entities[tag] = GmshEntityDescriptor(dim=2, tag=tag, area=area, centroid=centroid, normal=normal, planarity=planarity)
        if len(volume_entities) != 1:
            raise MeshProviderError(f"expected exactly one volume entity, found {len(volume_entities)}")
        vol_id = next(iter(volume_entities))
        return entities, vol_id

    def mesh(
        self,
        step_path: Path,
        region_map: ResolvedRegionMap,
        *,
        mesh_spec_hash: str,
        element_family: str = "c3d10",
    ) -> tuple[ParsedMesh, StructuralMeshManifest, bytes]:
        if element_family != "c3d10":
            raise MeshProviderError(f"unsupported element family: {element_family}")
        entities, vol_id = self._preview_entities(step_path)
        discovery = self._discovery.require_available()
        # Match each semantic region to exactly one Gmsh 2D entity.
        derived: dict[str, int] = {}
        for region in region_map.regions:
            candidates = []
            for tag, desc in entities.items():
                if desc.dim != 2:
                    continue
                if desc.planarity >= self._tolerances.planarity_mm:
                    continue
                if abs(desc.area - region.exact_brep_area_mm2) > self._tolerances.area_mm2:
                    continue
                dcx = desc.centroid[0] - region.exact_brep_centroid_mm[0]
                dcy = desc.centroid[1] - region.exact_brep_centroid_mm[1]
                dcz = desc.centroid[2] - region.exact_brep_centroid_mm[2]
                if math.sqrt(dcx * dcx + dcy * dcy + dcz * dcz) > self._tolerances.centroid_mm:
                    continue
                dot = abs(desc.normal[0] * region.plane_normal[0] + desc.normal[1] * region.plane_normal[1] + desc.normal[2] * region.plane_normal[2])
                if dot < self._tolerances.normal_abs_dot:
                    continue
                candidates.append(tag)
            if len(candidates) != 1:
                raise MeshProviderError(
                    f"region {region.region_id} matched {len(candidates)} Gmsh entities (require exactly one)")
            derived[region.region_id] = candidates[0]
        # Build physical-group geo and mesh to .inp.
        with tempfile.TemporaryDirectory(prefix="mechcad-gmsh-mesh-") as directory:
            cwd = Path(directory)
            geo_lines = [f'Merge "{step_path}";', "Mesh.ElementOrder = 2;"]
            for region_id, tag in derived.items():
                geo_lines.append(f'Physical Surface("{region_id}") = {{{tag}}};')
            geo_lines.append(f'Physical Volume("volume") = {{{vol_id}}};')
            geo_lines.append("Mesh 3;")
            geo = cwd / "mesh.geo"
            geo.write_text("\n".join(geo_lines) + "\n", encoding="ascii")
            msh = cwd / "mesh.msh"
            self._run_gmsh(geo, msh, out_format="msh2")
            inp = cwd / "mesh.inp"
            self._run_gmsh(geo, inp, out_format="inp")
            inp_bytes = inp.read_bytes()
            msh_bytes = msh.read_bytes()
        parsed = _parse_inp(inp_bytes.decode("utf-8", errors="replace"))
        msh_nodes, msh_surfaces, msh_volumes, _msh_phys, _msh_entities = _parse_msh_v2(msh_bytes)
        # Validate mesh contract.
        self._validate_mesh(parsed)
        # Bind derived entity ids into physical groups for audit.
        groups = [
            group for group in parsed.physical_groups
            if group.physical_group_name in derived or group.physical_group_name == "volume"
        ]
        groups.append(PhysicalGroupBinding(semantic_region_id=None, physical_group_name="volume",
                                            gmsh_entity_dim=3, gmsh_entity_id=vol_id))
        region_group_tags = {region_id: tag for region_id, tag in derived.items()}
        bound_groups = []
        for g in groups:
            if g.physical_group_name in region_group_tags:
                bound_groups.append(g.model_copy(update={"gmsh_entity_id": region_group_tags[g.physical_group_name]}))
            else:
                bound_groups.append(g)
        groups = bound_groups
        manifest = StructuralMeshManifest(
            mesh_specification_hash=mesh_spec_hash,
            gmsh_identity=self.identity,
            gmsh_version=discovery.version or "unknown",
            element_family=element_family,
            node_count=len(msh_nodes),
            volume_element_count=sum(len(v) for v in msh_volumes.values()),
            boundary_element_count=sum(len(v) for v in msh_surfaces.values()),
            volume_entity_id=vol_id,
            physical_groups=tuple(groups),
            mesh_hash="pending",
            region_map_hash=region_map.region_map_hash,
        )
        manifest = manifest.model_copy(update={"mesh_hash": "sha256:" + hashlib.sha256(msh_bytes).hexdigest()})
        return parsed, manifest, msh_bytes

    def _validate_mesh(self, parsed: ParsedMesh) -> None:
        if len(parsed.c3d10) == 0:
            raise MeshProviderError("mesh contains no C3D10 volume elements")
        if parsed.nodes is None or len(parsed.nodes) == 0:
            raise MeshProviderError("mesh contains no nodes")
        # Only C3D10 supported; check ordering of midside nodes.
        for elid, nodes in parsed.c3d10.items():
            if len(nodes) != 10:
                raise MeshProviderError(f"unsupported volume element type for element {elid} (nodes={len(nodes)})")
            coord = {i + 1: parsed.nodes[n] for i, n in enumerate(nodes)}
            for pos, (a, b) in enumerate(_C3D10_MIDSIDE_EDGES, start=5):
                mid = coord[pos]
                ca = coord[a]
                cb = coord[b]
                exp = ((ca[0] + cb[0]) / 2.0, (ca[1] + cb[1]) / 2.0, (ca[2] + cb[2]) / 2.0)
                if any(abs(mid[k] - exp[k]) > C3D10_GEOMETRY_TOLERANCE_MM for k in range(3)):
                    raise MeshProviderError(f"C3D10 element {elid} midside {pos} is not edge midpoint")
        if not parsed.surface_elements:
            raise MeshProviderError("mesh contains no semantic boundary surface elements")
        for region, elems in parsed.surface_elements.items():
            if len(elems) == 0:
                raise MeshProviderError(f"physical group {region} is empty")
            for elid, enodes in elems:
                if len(enodes) != 6:
                    raise MeshProviderError(f"unsupported boundary element in group {region} (nodes={len(enodes)})")
