from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

from mechcad_harness.models.structural import (
    StructuralAnalysisDefinition,
    StructuralBodyAcceleration,
    StructuralFixedSupport,
    StructuralLoadCase,
    StructuralRegionDefinition,
    StructuralResultantForce,
    StructuralResultField,
    StructuralSurfacePressure,
    StructuralMaterialPropertyName,
)
from mechcad_harness.structural.models import (
    DECK_BUILDER_IDENTITY,
    LoweredLoadProvenance,
    ResolvedRegionMap,
    deck_semantic_hash,
    lowered_load_semantic_hash,
    canonical_load_semantic_hash,
)
from mechcad_harness.structural.mesh import C3D10_LOCAL_FACES, ParsedMesh
from mechcad_harness.structural.tolerances import RESULTANT_FORCE_CONSERVATION_TOLERANCE_N

DECK_BUILDER_VERSION = "1"
UNIT_POLICY_ID = "structural-units@1"
C3D10_SURFACE_INTEGRATION_RULE_VERSION = "consistent-nodal-planar@1"
RESULTANT_FORCE_LOWERING_ALGORITHM = "consistent-nodal-surface-integration@1"
DEFAULT_RESULT_FIELDS = (
    StructuralResultField.DISPLACEMENT,
    StructuralResultField.VON_MISES_STRESS,
    StructuralResultField.REACTIONS,
)
RESULT_OUTPUT_CARD_VALUES = {
    StructuralResultField.VON_MISES_STRESS: ("*EL FILE", "S"),
    StructuralResultField.DISPLACEMENT: ("*NODE FILE", "U"),
    StructuralResultField.REACTIONS: ("*NODE PRINT", "RF"),
}


class DeckBuildError(Exception):
    pass


@dataclass
class DeckRepresentation:
    heading: str
    nodes: dict[int, tuple[float, float, float]]
    c3d10: dict[int, tuple[int, ...]]
    material_name: str
    elastic_modulus_mpa: float
    poisson_ratio: float
    density_t_per_mm3: float | None
    boundary_node_sets: dict[str, tuple[int, ...]]
    surfaces: dict[str, list[tuple[int, str]]]  # region -> [(vol_el, face_key)]
    pressure_loads: list[tuple[str, float]]     # (region, pressure_value)
    cload: dict[int, tuple[float, float, float]]
    grav_loads: list[tuple[float, float, float, float]]  # (magnitude, dx, dy, dz)
    fixed_dofs: tuple[int, int, int] = (1, 2, 3)


@dataclass
class BuiltDeck:
    text: str
    representation: DeckRepresentation
    lowered_loads: list[LoweredLoadProvenance]
    mesh_hash: str


def parse_cload_semantics(deck_text: str) -> dict[int, tuple[float, float, float]]:
    """Parse the deterministic nodal CLOAD values emitted in a deck."""
    nodal_loads: dict[int, list[float]] = {}
    in_cload = False
    for line in deck_text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("*CLOAD"):
            in_cload = True
            continue
        if stripped.startswith("*"):
            in_cload = False
        if not in_cload or not stripped:
            continue
        fields = [field.strip() for field in stripped.split(",")]
        if len(fields) != 3 or not fields[0].isdigit() or fields[1] not in {"1", "2", "3"}:
            raise DeckBuildError("malformed CLOAD record")
        try:
            node_id = int(fields[0])
            value = float(fields[2])
        except ValueError as exc:
            raise DeckBuildError("malformed CLOAD value") from exc
        if node_id <= 0 or not math.isfinite(value):
            raise DeckBuildError("invalid CLOAD identity or value")
        vector = nodal_loads.setdefault(node_id, [0.0, 0.0, 0.0])
        vector[int(fields[1]) - 1] += value
    return {node_id: tuple(vector) for node_id, vector in nodal_loads.items()}


def cload_semantic_hash(deck_text: str) -> str:
    """Hash the deterministic nodal CLOAD values emitted in a deck."""
    return lowered_load_semantic_hash(parse_cload_semantics(deck_text))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def map_surface_to_volume_faces(parsed: ParsedMesh, region: str) -> list[tuple[int, int, str, tuple[int, int, int]]]:
    """Map each semantic boundary triangle to exactly one adjacent C3D10 volume
    element face.  Returns (boundary_el_id, vol_el_id, face_key, midside_global_nodes)."""
    face_index: dict[frozenset, list[tuple[int, str]]] = {}
    for elid, nodes in parsed.c3d10.items():
        local = {i + 1: nodes[i] for i in range(10)}
        for face_key, indices in C3D10_LOCAL_FACES.items():
            corners = (local[indices[0]], local[indices[1]], local[indices[2]])
            key = frozenset(corners)
            face_index.setdefault(key, []).append((elid, face_key))
    result = []
    for elid, enodes in parsed.surface_elements.get(region, []):
        corners = (enodes[0], enodes[1], enodes[2])
        key = frozenset(corners)
        matches = face_index.get(key)
        if not matches or len(matches) != 1:
            raise DeckBuildError(
                f"region {region} boundary triangle on element {elid} matched {len(matches) if matches else 0} volume faces")
        vol_el, face_key = matches[0]
        local = {i + 1: parsed.c3d10[vol_el][i] for i in range(10)}
        mid_local = C3D10_LOCAL_FACES[face_key][3:]
        mids = (local[mid_local[0]], local[mid_local[1]], local[mid_local[2]])
        result.append((elid, vol_el, face_key, mids))
    return result


def _triangle_area(nodes: dict[int, tuple[float, float, float]], tri: tuple[int, int, int]) -> float:
    a = nodes[tri[0]]; b = nodes[tri[1]]; c = nodes[tri[2]]
    cr = _cross((b[0] - a[0], b[1] - a[1], b[2] - a[2]), (c[0] - a[0], c[1] - a[1], c[2] - a[2]))
    return 0.5 * math.sqrt(cr[0] * cr[0] + cr[1] * cr[1] + cr[2] * cr[2])


class StructuralDeckBuilder:
    identity = DECK_BUILDER_IDENTITY
    builder_version = DECK_BUILDER_VERSION

    def __init__(self, *, unit_policy_id: str = UNIT_POLICY_ID):
        self._unit_policy_id = unit_policy_id

    def build(
        self,
        *,
        definition: StructuralAnalysisDefinition,
        selected_cases: tuple[StructuralLoadCase, ...],
        fixed_supports: tuple[StructuralFixedSupport, ...],
        region_definitions: tuple[StructuralRegionDefinition, ...],
        region_map: ResolvedRegionMap,
        parsed_mesh: ParsedMesh,
        mesh_hash: str,
        requested_result_fields: tuple[StructuralResultField, ...] = DEFAULT_RESULT_FIELDS,
    ) -> BuiltDeck:
        region_by_id = {r.region_id: r for r in region_definitions}
        # Material lowering (property-specific).
        snapshots = {s.property_name: s for s in definition.material_assignment.property_snapshot}
        e = snapshots.get(StructuralMaterialPropertyName.ELASTIC_MODULUS)
        nu = snapshots.get(StructuralMaterialPropertyName.POISSON_RATIO)
        if e is None or nu is None:
            raise DeckBuildError("missing required elastic modulus or poisson ratio")
        density_t = None
        if any(isinstance(load, StructuralBodyAcceleration) for case in selected_cases for load in case.loads):
            d = snapshots.get(StructuralMaterialPropertyName.DENSITY)
            if d is None:
                raise DeckBuildError("body acceleration requested but density property is missing")
            density_t = d.value * 1e-12

        # Fixed support node set.
        boundary_node_sets: dict[str, list[int]] = {}
        for support in fixed_supports:
            rid = support.target_region_id
            nset: list[int] = []
            elems = parsed_mesh.surface_elements.get(rid, [])
            for _elid, enodes in elems:
                nset.extend(enodes)
            boundary_node_sets[rid] = sorted(set(nset))
            if not boundary_node_sets[rid]:
                raise DeckBuildError(f"fixed support region {rid} resolved no nodes")

        surfaces: dict[str, list[tuple[int, str]]] = {}
        midside_by_region: dict[str, dict[int, tuple[int, int, int]]] = {}
        pressure_loads: list[tuple[str, float]] = []
        cload: dict[int, tuple[float, float, float]] = {}
        grav_loads: list[tuple[float, float, float, float]] = []
        lowered: list[LoweredLoadProvenance] = []

        for case in selected_cases:
            for load in case.loads:
                if isinstance(load, StructuralSurfacePressure):
                    rid = load.target_region_id
                    if rid not in surfaces:
                        mapped = map_surface_to_volume_faces(parsed_mesh, rid)
                        surfaces[rid] = [(ve, fk) for _bel, ve, fk, _m in mapped]
                        midside_by_region[rid] = {bel: mids for bel, _ve, _fk, mids in mapped}
                    # Positive pressure acts opposite outward face normal (proven convention).
                    p = load.pressure_mpa if load.signed_normal_convention == "outward_positive" else -load.pressure_mpa
                    pressure_loads.append((rid, p))
                elif isinstance(load, StructuralResultantForce):
                    rid = load.target_region_id
                    if rid not in surfaces:
                        mapped = map_surface_to_volume_faces(parsed_mesh, rid)
                        surfaces[rid] = [(ve, fk) for _bel, ve, fk, _m in mapped]
                        midside_by_region[rid] = {bel: mids for bel, _ve, _fk, mids in mapped}
                    lowered.append(self._lower_resultant_force(
                        load=load, region=region_by_id[rid], region_map=region_map,
                        parsed_mesh=parsed_mesh, cload=cload, mesh_hash=mesh_hash,
                        midside_by_boundary_el=midside_by_region[rid]))
                elif isinstance(load, StructuralBodyAcceleration):
                    acc = load.acceleration_xyz
                    mag = math.sqrt(acc[0] * acc[0] + acc[1] * acc[1] + acc[2] * acc[2])
                    if mag == 0:
                        raise DeckBuildError("body acceleration magnitude is zero")
                    grav_loads.append((mag, acc[0] / mag, acc[1] / mag, acc[2] / mag))

        rep = DeckRepresentation(
            heading="MechCAD structural linear-static deck",
            nodes=parsed_mesh.nodes,
            c3d10=parsed_mesh.c3d10,
            material_name="mat1",
            elastic_modulus_mpa=e.value,
            poisson_ratio=nu.value,
            density_t_per_mm3=density_t,
            boundary_node_sets={k: tuple(v) for k, v in boundary_node_sets.items()},
            surfaces={k: v for k, v in surfaces.items()},
            pressure_loads=pressure_loads,
            cload=cload,
            grav_loads=grav_loads,
        )
        self.validate(rep, requested_result_fields=requested_result_fields)
        text = self._render(rep, requested_result_fields=requested_result_fields)
        if lowered:
            lowered[-1] = lowered[-1].model_copy(update={
                "produced_nodal_load_semantic_hash": cload_semantic_hash(text),
            })
        return BuiltDeck(text=text, representation=rep, lowered_loads=lowered, mesh_hash=mesh_hash)

    def _lower_resultant_force(
        self,
        *,
        load: StructuralResultantForce,
        region: StructuralRegionDefinition,
        region_map: ResolvedRegionMap,
        parsed_mesh: ParsedMesh,
        cload: dict[int, tuple[float, float, float]],
        mesh_hash: str,
        midside_by_boundary_el: dict[int, tuple[int, int, int]],
    ) -> LoweredLoadProvenance:
        # Normalize direction.
        d = load.direction_xyz
        mag_dir = math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2])
        if mag_dir == 0:
            raise DeckBuildError(f"resultant force {load.load_id} direction is zero")
        unit = (d[0] / mag_dir, d[1] / mag_dir, d[2] / mag_dir)
        f_vec = (load.magnitude_n * unit[0], load.magnitude_n * unit[1], load.magnitude_n * unit[2])
        # Total area from resolved region map.
        rmap = next(r for r in region_map.regions if r.region_id == region.region_id)
        a_total = rmap.exact_brep_area_mm2
        t_vec = (f_vec[0] / a_total, f_vec[1] / a_total, f_vec[2] / a_total)
        # Per-triangle consistent nodal lowering.
        total_area = 0.0
        sum_f = [0.0, 0.0, 0.0]
        sum_m = [0.0, 0.0, 0.0]
        centroid_acc = [0.0, 0.0, 0.0]
        local_cload: dict[int, tuple[float, float, float]] = {}
        for elid, enodes in parsed_mesh.surface_elements.get(region.region_id, []):
            a_e = _triangle_area(parsed_mesh.nodes, (enodes[0], enodes[1], enodes[2]))
            total_area += a_e
            cen = (
                (parsed_mesh.nodes[enodes[0]][0] + parsed_mesh.nodes[enodes[1]][0] + parsed_mesh.nodes[enodes[2]][0]) / 3.0,
                (parsed_mesh.nodes[enodes[0]][1] + parsed_mesh.nodes[enodes[1]][1] + parsed_mesh.nodes[enodes[2]][1]) / 3.0,
                (parsed_mesh.nodes[enodes[0]][2] + parsed_mesh.nodes[enodes[1]][2] + parsed_mesh.nodes[enodes[2]][2]) / 3.0,
            )
            centroid_acc[0] += cen[0] * a_e
            centroid_acc[1] += cen[1] * a_e
            centroid_acc[2] += cen[2] * a_e
            per = (a_e / 3.0) * t_vec[0], (a_e / 3.0) * t_vec[1], (a_e / 3.0) * t_vec[2]
            mids = midside_by_boundary_el[elid]
            for mnode in mids:
                local_existing = local_cload.get(mnode, (0.0, 0.0, 0.0))
                local_cload[mnode] = (
                    local_existing[0] + per[0],
                    local_existing[1] + per[1],
                    local_existing[2] + per[2],
                )
                existing = cload.get(mnode, (0.0, 0.0, 0.0))
                cload[mnode] = (existing[0] + per[0], existing[1] + per[1], existing[2] + per[2])
        if total_area <= 0:
            raise DeckBuildError(f"resultant force region {region.region_id} has zero area")
        g_centroid = (centroid_acc[0] / total_area, centroid_acc[1] / total_area, centroid_acc[2] / total_area)
        for vec in local_cload.values():
            sum_f[0] += vec[0]; sum_f[1] += vec[1]; sum_f[2] += vec[2]
        for node, vec in local_cload.items():
            r = parsed_mesh.nodes[node]
            sum_m[0] += r[1] * vec[2] - r[2] * vec[1]
            sum_m[1] += r[2] * vec[0] - r[0] * vec[2]
            sum_m[2] += r[0] * vec[1] - r[1] * vec[0]
        expected_m = _cross(g_centroid, f_vec)
        force_err = math.sqrt((sum_f[0] - f_vec[0]) ** 2 + (sum_f[1] - f_vec[1]) ** 2 + (sum_f[2] - f_vec[2]) ** 2)
        mom_err = math.sqrt((sum_m[0] - expected_m[0]) ** 2 + (sum_m[1] - expected_m[1]) ** 2 + (sum_m[2] - expected_m[2]) ** 2)
        if force_err > RESULTANT_FORCE_CONSERVATION_TOLERANCE_N or mom_err > RESULTANT_FORCE_CONSERVATION_TOLERANCE_N:
            raise DeckBuildError(
                f"resultant force {load.load_id} not conserved: force_err={force_err}, moment_err={mom_err}")
        return LoweredLoadProvenance(
            canonical_load_id=load.load_id,
            canonical_load_semantic_hash=canonical_load_semantic_hash(load),
            semantic_region_id=region.region_id,
            resolved_region_map_hash=region_map.region_map_hash,
            exact_semantic_face_area_mm2=a_total,
            source_force_vector_n=f_vec,
            source_application_point_mm=g_centroid,
            normalized_solver_traction_vector_n_per_mm2=t_vec,
            lowering_algorithm_id=RESULTANT_FORCE_LOWERING_ALGORITHM,
            c3d10_surface_integration_rule_version=C3D10_SURFACE_INTEGRATION_RULE_VERSION,
            produced_nodal_load_semantic_hash=lowered_load_semantic_hash(cload),
            mesh_hash=mesh_hash,
            force_conservation_error_n=force_err,
            moment_conservation_error_n_mm=mom_err,
        )

    def validate(
        self,
        rep: DeckRepresentation,
        *,
        requested_result_fields: tuple[StructuralResultField, ...] = DEFAULT_RESULT_FIELDS,
    ) -> None:
        supported_cards = {
            "*HEADING", "*NODE", "*ELEMENT", "*SOLID SECTION", "*MATERIAL", "*ELASTIC",
            "*DENSITY", "*STEP", "*STATIC", "*BOUNDARY", "*NSET", "*SURFACE", "*DLOAD",
            "*CLOAD", "*EL FILE", "*NODE FILE", "*NODE PRINT", "*END STEP",
        }
        for field in requested_result_fields:
            card, _value = RESULT_OUTPUT_CARD_VALUES.get(field, (None, None))
            if card not in supported_cards:
                raise DeckBuildError(f"unsupported requested result field: {field}")
        if not rep.nodes:
            raise DeckBuildError("deck has no nodes")
        if not rep.c3d10:
            raise DeckBuildError("deck has no C3D10 elements")
        if not all(isfinite(v) for v in (rep.elastic_modulus_mpa, rep.poisson_ratio)):
            raise DeckBuildError("non-finite material values")
        if rep.poisson_ratio <= -1 or rep.poisson_ratio >= 0.5:
            raise DeckBuildError("invalid poisson ratio")
        if rep.elastic_modulus_mpa <= 0:
            raise DeckBuildError("invalid elastic modulus")
        if rep.density_t_per_mm3 is not None and rep.density_t_per_mm3 <= 0:
            raise DeckBuildError("invalid density")
        if not rep.boundary_node_sets:
            raise DeckBuildError("deck has no fixed support node sets")
        for nset in rep.boundary_node_sets.values():
            if not nset:
                raise DeckBuildError("empty fixed node set")
            for nid in nset:
                if nid not in rep.nodes:
                    raise DeckBuildError(f"fixed node {nid} not in mesh")
        for region, faces in rep.surfaces.items():
            if not faces:
                raise DeckBuildError(f"surface {region} has no mapped faces")
            for ve, _fk in faces:
                if ve not in rep.c3d10:
                    raise DeckBuildError(f"surface face references unknown element {ve}")
        for region, _p in rep.pressure_loads:
            if region not in rep.surfaces:
                raise DeckBuildError(f"pressure load references unmapped surface {region}")
        for nid, vec in rep.cload.items():
            if nid not in rep.nodes:
                raise DeckBuildError(f"cload node {nid} not in mesh")
            if not all(isfinite(v) for v in vec):
                raise DeckBuildError("non-finite cload value")
        for g in rep.grav_loads:
            if not all(isfinite(v) for v in g):
                raise DeckBuildError("non-finite gravity load")
        # supported_cards reserved for rendered-text validation gate.

    def _render(
        self,
        rep: DeckRepresentation,
        *,
        requested_result_fields: tuple[StructuralResultField, ...] = DEFAULT_RESULT_FIELDS,
    ) -> str:
        lines: list[str] = []
        lines.append("*HEADING")
        lines.append(rep.heading)
        lines.append("*NODE")
        for nid in sorted(rep.nodes):
            x, y, z = rep.nodes[nid]
            lines.append(f"{nid},{x!r},{y!r},{z!r}")
        lines.append(f"*ELEMENT,TYPE=C3D10,ELSET={rep.material_name}_vol")
        for elid in sorted(rep.c3d10):
            nodes = rep.c3d10[elid]
            lines.append(",".join([str(elid)] + [str(n) for n in nodes]))
        lines.append(f"*SOLID SECTION,ELSET={rep.material_name}_vol,MATERIAL={rep.material_name}")
        lines.append(f"*MATERIAL,NAME={rep.material_name}")
        lines.append("*ELASTIC")
        lines.append(f"{rep.elastic_modulus_mpa!r},{rep.poisson_ratio!r}")
        if rep.density_t_per_mm3 is not None:
            lines.append("*DENSITY")
            lines.append(f"{rep.density_t_per_mm3!r}")
        lines.append("*STEP")
        lines.append("*STATIC")
        for rid, nset in rep.boundary_node_sets.items():
            lines.append(f"*NSET,NSET={rid}_nodes")
            for i in range(0, len(nset), 16):
                chunk = nset[i:i+16]
                lines.append(",".join(str(n) for n in chunk))
            lines.append("*BOUNDARY")
            lines.append(f"{rid}_nodes,1,3")
        for region, faces in rep.surfaces.items():
            lines.append(f"*SURFACE,NAME={region},TYPE=ELEMENT")
            for ve, fk in faces:
                lines.append(f"{ve},{fk}")
        for region, p in rep.pressure_loads:
            lines.append("*DLOAD")
            lines.append(f"{region},P,{p!r}")
        if rep.cload:
            lines.append("*CLOAD")
            for nid in sorted(rep.cload):
                fx, fy, fz = rep.cload[nid]
                lines.append(f"{nid},1,{fx!r}")
                lines.append(f"{nid},2,{fy!r}")
                lines.append(f"{nid},3,{fz!r}")
        for mag, dx, dy, dz in rep.grav_loads:
            lines.append("*DLOAD")
            lines.append(f"{rep.material_name}_vol,GRAV,{mag!r},{dx!r},{dy!r},{dz!r}")
        if StructuralResultField.VON_MISES_STRESS in requested_result_fields:
            lines.extend(RESULT_OUTPUT_CARD_VALUES[StructuralResultField.VON_MISES_STRESS])
        if StructuralResultField.DISPLACEMENT in requested_result_fields:
            lines.extend(RESULT_OUTPUT_CARD_VALUES[StructuralResultField.DISPLACEMENT])
            for support_region in rep.boundary_node_sets:
                lines.extend((f"*NODE PRINT,NSET={support_region}_nodes", "U"))
        if StructuralResultField.REACTIONS in requested_result_fields:
            for support_region in rep.boundary_node_sets:
                lines.extend((
                    f"{RESULT_OUTPUT_CARD_VALUES[StructuralResultField.REACTIONS][0]},NSET={support_region}_nodes",
                    RESULT_OUTPUT_CARD_VALUES[StructuralResultField.REACTIONS][1],
                ))
        lines.append("*END STEP")
        return "\n".join(lines) + "\n"


def isfinite(value: float) -> bool:
    return math.isfinite(value)
