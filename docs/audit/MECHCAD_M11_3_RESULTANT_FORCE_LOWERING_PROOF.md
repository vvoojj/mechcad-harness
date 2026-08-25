# M11-3 ResultantForce → Consistent Nodal Load Lowering Proof

- **Accepted baseline preserved:** `M11_1_STRUCTURAL_FEA_ARCHITECTURE_READY`, `M11_2_STRUCTURAL_AUTHORITY_MODEL_VERIFIED`, `CALCULIX_SURFACE_SYNTAX_PROVEN_BUT_VECTOR_TRACTION_UNRESOLVED`.
- **No production M11-3 code changed. No M11-4 started.**
- **Runtime under proof:** FreeCAD 1.1.3 / Gmsh 4.15.0 / CalculiX 2.22 (`C:\Program Files\FreeCAD 1.1\bin\{freecadcmd,gmsh,ccx}.exe`).
- **Disposable evidence:** `C:\Users\vvooj\AppData\Local\Temp\opencode\m11-3-spike\consistent_load_proof.py` and `box_cl_{normal,tang_y,oblique}.inp/.frd/.dat`.

## Canonical Load Semantics

`StructuralResultantForce` (M11-2 authority model, unchanged) carries:
- `resultant` vector `F` [N], `direction` (unit), `coordinate_frame`, `semantic_region` (one connected planar CAD face), `distribution = UNIFORM_SURFACE_TRACTION_EQUIVALENT`.
- Physical traction field `t = F / A_total`, where `A_total` is the exact resolved semantic-face area.

The question is only the finite-element weak-form lowering of `t` onto the mesh. The M11-2 model is not modified; this is an encoding of the same physical traction.

## C3D10 Shape-Function Integration

For a six-node quadratic triangular face (C3D10 boundary face), area coordinates `L1,L2,L3`, `L1+L2+L3=1`:
- `N1 = L1(2L1−1)`, `N2 = L2(2L2−1)`, `N3 = L3(2L3−1)` (corners)
- `N4 = 4 L1 L2`, `N5 = 4 L2 L3`, `N6 = 4 L3 L1` (midside 1−2, 2−3, 3−1)

Consistent nodal force: `f_i = ∫_A N_i t dA`. For constant `t`, `∫_A L1^a L2^b L3^c dA = 2A·a!b!c!/(a+b+c+2)!`.

- Corner: `∫ N_corner dA = ∫(2 L^2 − L) dA = 2·(2A·2!/4!) − (2A/3!) = A/3 − A/3 = 0`.
- Midside: `∫ N_mid dA = 4·(2A·1!1!/4!) = 8A/24 = A/3`.

**Exact result (straight-sided planar triangle):** `f_corner = 0`, `f_midside = (A/3)·t`. Per-element total `= 3·(A/3)·t = A·t = F_element`. Matches the hint `corners = 0`, `midsides = F_element/3`.

This is corroborated independently by the CalculiX 2.22 manual (Facial distributed loading, Figure 146): for C3D10 "the force is zero … for quadratic elements" at corners under pressure — i.e. CalculiX's native pressure consistent load uses exactly this corner-zero / midside rule.

## Gmsh Planar-Face Geometry Finding

Empirical check on the real Gmsh 4.15.0 C3D10 mesh (`box_volume_surface.inp`, free_end = the 20×10 mm face at `x=100`):
- Boundary faces on the semantic face: **14**.
- Total resolved area: **200.000000 mm²** (exactly 20×10).
- Max midside off-plane deviation: **0.0 mm** (all six face nodes coplanar).
- Max midside off-edge-midpoint deviation: **4.99e−13 mm** (midside nodes lie at edge midpoints → straight sides).

Conclusion: Gmsh produced **straight-sided, planar, quadratic triangles** appropriate for the closed-form `A/3` rule. The derivation's geometry assumption holds on this mesh. **Fallback (fail-closed):** if a future mesh yields a curved boundary triangle (midside off-plane or off edge-midpoint beyond tolerance, or non-planar corner set), the same framework applies exact numerical surface integration (Gauss quadrature over the parametric triangle with the true Jacobian) instead of the closed form; such a deck is not accepted until the integration is verified.

## Per-Element Consistent Load

For each boundary triangle `e` with corner/midside nodes from the proven C3D10 face table (`surfaces.f`, `ifacet`):
- area `A_e` from the three corner coordinates (cross product);
- for each of the three midside nodes: `f_mid = (A_e/3)·t` (vector, world frame);
- corner nodes receive exactly `0`.

## Multi-Element Accumulation

For total area `A_total`, uniform traction `t = F/A_total`:
- accumulation is a node-keyed `dict` (global node id → vector), so it is **independent of incidental element numbering**;
- per element, three midside contributions each `(A_e/3)·t`; total lowered load `= Σ_e A_e·t = A_total·t = F`.
- Verified empirically: lowered `Ftot = (−200,0,0)`, `(0,200,0)`, `(200,200,200)` equals `A_total·t` exactly for the three test directions.

## Global Vector Encoding

Arbitrary vector direction is encoded through CalculiX `*CLOAD` using global translational DOFs `1=X, 2=Y, 3=Z` after the accepted component/world-frame conversion. No pressure is used for tangential/oblique tests.
- **purely normal** (`t = (−1,0,0)` N/mm²): ran, solver reaction `(+200, ~0, ~0)`.
- **purely tangential** (`t = (0,+1,0)`): ran, solver reaction `(~0, −200, ~0)`.
- **oblique** (`t = (+1,+1,+1)`): ran, solver reaction `(−200,−200,−200)`.

## Force Conservation

Numerically (solver reaction = `−applied`, equilibrium):
- normal: applied `(−200,0,0)`, reaction `(2.00000E+02, −1.78e−12, +9.79e−13)`.
- tang_y: applied `(0,200,0)`, reaction `(+1.79e−10, −2.00000E+02, +1.99e−10)`.
- oblique: applied `(200,200,200)`, reaction `(−2.00000E+02, −2.00000E+02, −2.00000E+02)`.

`Σ(all nodal force vectors) == requested F` within `≤ 2e−12 N` (≤ 1e−14 relative). Not merely solver completion — exact reaction balance.

## Moment Conservation

`Σ(r_i × f_i)` computed from the lowered nodal loads equals `r_G × F` (area-weighted centroid `G=(100,10,5)`), exact:
- normal: `Σ(r×f) = (0, −1000, +2000)`; `r_G×F = (0, −1000, +2000)`.
- tang_y: `Σ(r×f) = (−1000, 0, +20000)`; `r_G×F = (−1000, 0, +20000)`.
- oblique: `Σ(r×f) = (+1000, −19000, +18000)`; `r_G×F = (+1000, −19000, +18000)`.

The lowering preserves both resultant **force** and resultant **moment**; it is not merely force-balanced.

## Native Pressure Cross-Check

Two otherwise identical models on the same finite-element mesh:
- **A (native):** `*DLOAD free_end, P, 1.0` (positive pressure, normal to face).
- **B (lowering):** `*CLOAD` with the consistent nodal vector for `t = (−1,0,0)` total `F = −200 N`.

Results:
- total fixed-end reaction vector: A `(+200, ~0, ~0)` vs B `(+200, ~0, ~0)` — agreement `≤ 1.8e−12 N`.
- selected nodal displacements (full `.frd` parse, 854 shared nodes): **max `|U_A − U_B| = 0.0`** (e.g. node 8: `U=(−1.43977e−3, 4.75507e−5, 2.36002e−5)` identical in both).
- solver equilibrium: both completed (`*STEP` increment 1).

The identical displacement field confirms the consistent lowering is the exact weak-form equivalent of native pressure. (Stress singularities were not used for this equivalence proof.)

## Tangential Traction Test

Load parallel to the surface (`t = (0,+1,0)`) cannot be represented by ordinary pressure. Applied only through the consistent nodal lowering (`*CLOAD`):
- requested global resultant `(0,200,0)`; solver reaction `(~0, −200, ~0)`;
- moment conserved (section 7); fixed-end reaction balanced; solver ran to completion.

This proves the lowering is capable of arbitrary constant vector traction, not merely reproducing pressure.

## Oblique Traction Test

Oblique direction `t = (+1,+1,+1)` (all of X,Y,Z nonzero), applied only through `*CLOAD`:
- requested resultant `(200,200,200)`; reaction `(−200,−200,−200)`;
- moment conserved (section 7); stable solver execution.

## Required Provenance

Minimum lowering provenance (node ids are derived mesh-bound identities, NOT canonical engineering authority):
- `canonical_load_id` (the `StructuralResultantForce` id)
- `semantic_region_id` (connected planar CAD face)
- `resolved_region_map_hash` (semantic face → boundary-triangle map)
- `exact_semantic_face_area` (e.g. `200.000000 mm²`)
- `source_force_vector` (requested `F`, world frame)
- `normalized_solver_frame_traction_vector` (`t = F/A_total`)
- `lowering_algorithm_id/version` (consistent-nodal, `∫ N_i t dA`)
- `c3d10_surface_integration_rule_version` (corner=0, midside=`A_e/3`; or exact Gauss fallback)
- `produced_nodal_load_semantic_hash` (the accumulated `dict`)
- `mesh_hash` (Gmsh C3D10 mesh)

## Limitations

- Valid only for straight-sided **planar** C3D10 boundary triangles (verified on this Gmsh mesh). Curved/high-order boundary faces require the exact-Gauss fallback and re-verification (fail-closed until proven).
- One connected planar semantic region per `ResultantForce` (canonical already).
- Requires proven C3D10 face ordering (`ifacet`); confirmed for CalculiX 2.22.
- Solver units must be self-consistent (N, mm, MPa) — unchanged from M11-2 contract.

## Architecture Consequence

The proof **succeeds**. Recommended narrow clarification to M11-1 (encoding only, not a change to the canonical `ResultantForce` authority model, and M11-2 remains unchanged):

> `UNIFORM_SURFACE_TRACTION_EQUIVALENT` may be lowered by a trusted backend to the mathematically consistent nodal force vector obtained by exact finite-element surface integration `∫_A N_i t dA` (corner=0, midside=`A_e/3` for straight-sided planar C3D10 faces; exact Gauss otherwise). This is the identical weak-form equivalent of the same physical uniform traction — confirmed by exact agreement with native CalculiX pressure (reaction `≤1e−12 N`, displacement field identical to `0.0`).

Initial M11 live acceptance may therefore admit `ResultantForce` via this consistent `*CLOAD` lowering alongside `SurfacePressure` / `BodyAcceleration`; the direct CalculiX provider need not reject `ResultantForce` as `UNSUPPORTED_LOAD`.

---

## Disposition

**M11_3_RESULTANT_FORCE_LOWERING_PROVEN**
