# M11-3 Semantic BREP → Gmsh Entity Bridge Proof

This document closes one remaining trust boundary of the M11-3 technical proof
before production implementation:

    StructuralRegionDefinition
        -> resolved FreeCAD semantic BREP face descriptor
        -> imported Gmsh OCC geometry
        -> deterministic geometric matching
        -> Gmsh entity ID
        -> named physical group

It does not implement the production M11-3 service and does not start M11-4.
It builds on `M11_3_RESULTANT_FORCE_LOWERING_PROVEN` and
`M11_3_TECHNICAL_PROOF_READY_FOR_IMPLEMENTATION` (the latter remains the overall
technical disposition after this bridge is proven).

## Existing Gap

The prior technical proof showed FreeCAD semantic region resolution
(`fixed_end = min-X planar face`, `free_end = max-X planar face`) and later used:

```text
Physical Surface("fixed_end") = {1};
Physical Surface("free_end") = {2};
```

This assumed Gmsh surface IDs `1` and `2` are stable and semantically meaningful.
That assumption is false: Gmsh surface entity IDs are runtime OCC topology and
change with import ordering and topology. This proof derives those IDs
deterministically from geometry and proves it on the real Gmsh 4.15.0 install.

## FreeCAD Semantic Descriptor

The BREP resolver (`resolve_regions.py`, real FreeCAD 1.1.3) reads the verified
STEP directly into a `Part.Shape` and resolves, per admitted planar-face region:

- geometry kind = planar face
- centroid (exact BREP)
- area (exact BREP)
- outward plane normal (exact BREP)
- bounding box
- source geometry hash

Resolved descriptors (exact):

- `box.step` hash `sha256:3143f47d4870dc4ea2b923e556d0443bd13a1d0d5428a0c76ed8b17c4a14c6da`
  - fixed: centroid `(0, 10, 5)`, area `200.0`, normal `(-1, 0, 0)`
  - free: centroid `(100, 10, 5)`, area `200.0`, normal `(1, 0, 0)`
- `box_pocket.step` hash `sha256:e9fd803079cb77ee775cdeb5ee15635547e672a5b46bf211781cbe46bdaa1537`
  - fixed: centroid `(0, 10, 5)`, area `200.0`, normal `(-1, 0, 0)`
  - free: centroid `(100, 10, 5)`, area `200.0`, normal `(1, 0, 0)`

The pocket perturbation is a blind pocket cut into the non-target `y=20` face
(one solid preserved). It adds five new faces but leaves the min-X and max-X
semantics intact — a deliberate topology/numbering change.

## Gmsh OCC Entity Inspection

Real Gmsh 4.15.0 (`C:\Program Files\FreeCAD 1.1\bin\gmsh.exe`) imported each
STEP (`Merge "box.step"; Mesh.ElementOrder = 2; Mesh 3;`) and wrote a `.msh`.
The `.msh` element entity tags ARE the Gmsh OCC entity IDs. Per 2D entity, the
real mesh nodes were used to compute geometry invariants:

- centroid = mean of unique mesh nodes
- area = convex-hull projection area of mesh nodes onto the best-fit plane
- normal = smallest eigenvector of the node-covariance matrix (PCA)
- planarity = max distance of mesh nodes to the best-fit plane
- bounding box from mesh nodes

Enumerated entities (real Gmsh):

- original: 6 planar 2D entities (tags 1-6)
- pocket: 11 planar 2D entities (tags 1-11)

All measured planarity = `0` (planar). Measured areas were exact
(`200.0`, `1000.0`, `2000.0`). Measured centroids matched BREP centroids to
`< 1e-3 mm`. The mesh-derived normal axis matched the BREP normal axis exactly;
its PCA sign is arbitrary and therefore matched by absolute direction.

## Matching Algorithm

For each admitted 2D OCC entity, compute the invariants above, then accept the
entity as a candidate for a semantic region if and only if ALL hold:

1. planarity `< 1e-3 mm` (rejects non-planar / curved surfaces);
2. `|area - descriptor.area| <= 2.0 mm^2`;
3. centroid distance `<= 2.0 mm`;
4. `|normal . descriptor.normal| >= 0.999` (plane orientation; sign ignored
   because mesh PCA sign is arbitrary);

The BREP descriptor's outward normal sign is used separately by the load
lowering, not for face identity. Then:

- exactly one candidate for the region -> accept that Gmsh entity ID;
- zero candidates -> fail closed (region not found);
- two or more candidates -> fail closed (ambiguous; do not pick "closest").

Only `dim == 2` entities are considered; 0D/1D/3D entities are excluded by
dimension, satisfying the wrong-dimension rejection.

## Tolerances

| Invariant | Tolerance | Basis |
|---|---:|---|
| planarity | `1e-3 mm` | exact planar faces measure `0` |
| area | `2.0 mm^2` | exact planar triangulation equals BREP area |
| centroid | `2.0 mm` | exact mesh centroid equals BREP centroid |
| normal (abs dot) | `0.999` | cos angle `< ~2.6 deg` |

Tolerances are explicit and conservative; the admitted planar faces measure
well inside them, so the bound is a safety margin, not a fudge.

## Physical Group Construction

Accepted entity IDs are written into a generated `.geo`:

```text
Merge "<step>";
Physical Surface("fixed_end") = {derived_fixed_id};
Physical Surface("free_end") = {derived_free_id};
Physical Volume("volume") = {derived_volume_id};
Mesh.ElementOrder = 2;
Mesh 3;
```

`gmsh.exe` then meshed to a `.inp`. Verified results:

- `bridge_original.inp`: `fixed_end` = 22 elements, `free_end` = 22, `volume` =
  728, `C3D10` present.
- `bridge_pocket.inp`: `fixed_end` = 22, `free_end` = 22, `volume` = 874,
  `C3D10` present.

The named physical groups resolve to the correct element sets, proving the
entity ID derived from geometry drives the physical group, not a hardcoded ID.

## Numbering Independence

| Geometry | free_end Gmsh entity ID | fixed_end Gmsh entity ID |
|---|---:|---:|
| original (6 faces) | `2` | `1` |
| pocket (11 faces) | `6` | `1` |

The `free_end` moved from entity `2` to entity `6` after the pocket perturbation
(which added faces 7-11 on the non-target side). The geometric matcher still
identified `min-X` and `max-X` faces correctly, with zero reliance on the old
numeric IDs. A hardcoded `Physical Surface("free_end") = {2}` would have been
wrong for the pocket geometry; the derived ID `6` is correct. This proves the
bridge operates from geometry and would reject a wrong numeric surface.

## Fail-Closed Cases

All verified on the real Gmsh mesh:

- wrong area (`150` vs `200`): zero candidates -> rejected.
- centroid out of bounds (`x=5` vs `x=0`): zero candidates -> rejected.
- wrong plane normal (`+Z` vs `X` axis): `|dot| = 0` -> rejected.
- ambiguous (under-specified descriptor: area + normal axis only, centroid
  disabled): both `x` faces become candidates `[1, 2]` -> rejected (exactly-one
  rule).
- geometry artifact hash mismatch: pocket descriptor applied to the original
  mesh. Geometry coincidentally matched tag `1`, but the source geometry hash
  (`e9fd8030...`) != the meshed STEP hash (`3143f47d...`) -> rejected before any
  matching. This prevents cross-geometry reuse of a region map.
- wrong dimension: only `dim == 2` entities are matched; volumes/curves/points
  are excluded.

The contract never selects a "closest" entity when ambiguous.

## Identity / Hashing Boundary

- Canonical authority: `StructuralRegionDefinition` (source-bound).
- Realized semantic identity: source geometry hash, resolver version, semantic
  geometric descriptors (kind, centroid, area, normal, bbox), resolved-region-map
  hash.
- Derived Gmsh topology: entity IDs and physical-group names/IDs.

The derived Gmsh entity IDs MAY be recorded in the resolved region map for audit,
but they are bound to the exact source geometry hash, Gmsh identity/version, and
resolved-region-map hash. They MUST NOT survive as reusable region authority
across different geometry bytes. A different STEP (different hash) requires a
fresh resolve and a fresh bridge; reusing old entity IDs is rejected by the hash
binding.

## Production Algorithm

1. Load the immutable source revision/state snapshot and the `StructuralRegionDefinition`.
2. Resolve the source STEP via the public FreeCAD boundary; compute the source
   geometry hash.
3. Run the BREP semantic-region resolver (deterministic planar-face predicates)
   to produce semantic descriptors + resolved-region-map hash, bound to the
   source geometry hash.
4. Invoke Gmsh to import the same STEP and mesh; parse per-2D-entity geometry
   from the real mesh.
5. Match each semantic descriptor to Gmsh 2D entities by geometry invariants with
   explicit tolerances; require exactly one candidate per region.
6. Reject (fail closed) on zero/ambiguous matches, wrong dimension, wrong
   invariants, or source-geometry-hash mismatch.
7. Emit `Physical Surface` / `Physical Volume` groups from the derived IDs;
   mesh and persist the `.inp`/`.msh` as artifacts bound to revision/state hash
   and Gmsh identity.
8. Persist the resolved region map (including derived IDs for audit only) with
   the geometry hash, Gmsh identity, and region-map hash.

## Disposition

`M11_3_SEMANTIC_BREP_GMSH_BRIDGE_PROVEN`

The overall M11-3 technical disposition remains
`M11_3_TECHNICAL_PROOF_READY_FOR_IMPLEMENTATION`.
