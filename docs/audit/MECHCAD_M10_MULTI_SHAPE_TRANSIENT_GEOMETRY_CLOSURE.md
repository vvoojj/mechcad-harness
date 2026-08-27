# M10 Multi-Shape Transient Imported STEP Geometry Consistency — Closure

**Disposition:** `M10_MULTI_SHAPE_TRANSIENT_GEOMETRY_CONSISTENCY_VERIFIED`

**Closure type:** narrow latent-input trust-boundary closure (no new capability,
no milestone re-baseline).

---

## 1. Original defect

A read-only audit (`M10_MULTI_SHAPE_TRANSIENT_GEOMETRY_DEFECT_CONFIRMED`) found
that `FreeCADTransientAssemblyMeasurementProvider` realized an imported STEP
artifact in transient analysis (exact measurement, radial bounds, and local
extent) from **only the first top-level shape**:

- `_measurement_script` — `shape = candidates[0].Shape.copy()`
- `_radial_script` — `shape = candidates[0].Shape.copy()`
- `_local_extent_script` — `box = candidates[0].Shape.BoundBox`

For an imported STEP containing multiple top-level solids, this made M10
transient collision/clearance and reach/extent analysis incomplete: later
imported shapes were silently dropped.

## 2. Accepted whole-artifact contract

`ImportedCadComponent == the complete imported STEP artifact`. Persisted
assembly realization (`FreeCADAssemblyBackend`) and M11 structural geometry
(`StructuralFreeCADGeometryAdapter`) already aggregate every top-level imported
shape into one compound. The transient provider must do the same.

## 3. Exact affected helpers

`src/mechcad_harness/transient_freecad_measurement.py`:

- `_measurement_script` (imported branch)
- `_radial_script` (imported branch)
- `_local_extent_script` (imported branch)

## 4. Fix

In all three scripts, for imported instances the provider now:

```python
candidates = [obj for obj in source.Objects if hasattr(obj, 'Shape') and not obj.Shape.isNull()]
if not candidates:
    raise RuntimeError('... imported step shape missing')
shape = Part.makeCompound([c.Shape.copy() for c in candidates])
```

- `_local_extent_script`: the authoritative transient component is the
  **complete compound** (`box = shape.BoundBox`), not `candidates[0]`.
- `_radial_script` / `_measurement_script`: the authoritative transient
  component shape is the **complete compound**, and placement is applied to it
  before `common()` / `distToShape()`.

Fail-closed semantics are preserved: if no valid imported shape candidate
exists, the script raises explicitly. Generated (`CadPartProgram`) instances
still use a single authoritative generated object (`candidates[0]`), which is
correct for single-object generated parts and was left behaviorally unchanged.

## 5. Real multi-shape fixture

A real trusted STEP with **two separate top-level solids** is produced with
FreeCAD:

- solid A near `x = 0` (box `0..20`)
- solid B near `x = 100` (box `100..120`)

A stationary obstacle (box `20^3`) is placed at `x = 110`, so it intersects
only solid B and not solid A. The same fixture was verified to yield:

- legacy first-candidate realization (`candidates[0]`): `common volume == 0`
- corrected complete-artifact realization (`makeCompound(all candidates)`):
  `common volume > 0`

## 6. Persisted vs transient comparison

For the exact same imported STEP bytes, the persisted realization
(`FreeCADAssemblyBackend.generate_assembly` → FCStd) and the transient
realization (`Part.insert` + `makeCompound` of all top-level shapes) were
compared on physical geometry invariants:

- total volume ≈ `16000 mm³`
- bounding box `XMax ≈ 120 mm`, `XMin ≈ 0 mm`

Both realizations agree within `1e-6` relative tolerance. Object identity or
byte equality was not required; physical geometry equivalence was demonstrated.

## 7. M10-3 result

`ProductionApplication.analyze_multi_joint_collision_sweep` was run through a
two-joint kinematic chain whose imported leaf instance (`IMP`) collides with a
stationary obstacle only via its **second** solid (near `x = 100`). The
exact-transient sweep detects the collision:

- pair `(imp_inst, obs_inst)` `interference_volume_mm3 > 0`
- pair classification `CollisionClassification.INTERFERENCE`

This confirms the fix is not limited to a unit helper.

## 8. M10-4 extent/reach result

`ProductionApplication.prove_continuous_multi_joint_path_clearance` was run on
the same chain. The proof consumes `trusted_local_geometry_extents` (which now
includes all imported shapes) and exact transient measurement (which now uses
the complete compound). Because the collision occurs only against the second
imported solid, the proof returns:

- `status is MultiJointContinuousProofStatus.COLLISION_WITNESS`

A first-shape-only realization would have reported verified clearance, so the
result demonstrates the complete geometry participates in the M10-4 path.

Direct real-geometry tests also prove radial bounds and local extents include
the far second solid (`radius > 100 mm`, versus ~28–34 mm under
first-shape-only logic).

## 9. Regression results

New focused tests:

- `tests/unit/test_transient_freecad_measurement.py` — static assertions that
  imported scripts compound all candidates and retain `candidates[0]` only for
  the generated-part branch.
- `tests/integration/test_transient_imported_multishape_collision.py`:
  - real multi-shape STEP detects collision against the second shape (exact
    transient measurement);
  - legacy first-candidate realization misses the second shape (real geometry
    proof);
  - persisted vs transient geometry consistency;
  - radial bounds include all imported shapes;
  - local extents include all imported shapes;
  - M10-3 collision-through-exact-sweep detects the second shape;
  - M10-4 proof uses the complete imported extent.

All new focused tests pass. Relevant prior regressions remain green:

- transient FreeCAD measurement (live) — pass
- imported assembly bridge — pass
- M9-1 / M9-3 / M9-4 (FreeCAD runtime, mixed assembly, backend provenance) —
  pass
- M10-1 live continuous proof — pass
- M10-4 live continuous path — pass
- M10-5 system acceptance — pass
- M11-3 / M11-4 / M11-5 structural geometry — pass (shared FreeCAD code
  untouched; verified for consistency)

Full repository suite: **1390 passed, 25 skipped, 0 failed, 0 errors**.

## 10. Search for the same bug

Remaining `[0]` imported-shape realizations in the repository were classified:

- `src/mechcad_harness/transient_freecad_measurement.py:290` (radial,
  generated-part branch) — `GENERATED_SINGLE_OBJECT_OK`
- `src/mechcad_harness/transient_freecad_measurement.py:361` (measurement,
  generated-part branch) — `GENERATED_SINGLE_OBJECT_OK`
- `src/mechcad_harness/structural/mesh.py:422` — `NOT_APPLICABLE` (Gmsh 2D
  region matching; intentionally requires exactly one matched entity)
- `src/mechcad_harness/backends/freecad_assembly.py:237` (generated-part
  `source_objects[0]`) — `GENERATED_SINGLE_OBJECT_OK`
- `src/mechcad_harness/backends/freecad.py:354` (generated-part
  `objects[0]`) — `GENERATED_SINGLE_OBJECT_OK`

The accepted imported whole-artifact contract is already satisfied by
`FreeCADAssemblyBackend` (`makeCompound([item.Shape.copy() for item in
imported_objects])`) and `StructuralFreeCADGeometryAdapter`
(`makeCompound([o.Shape for o in objs])`). No imported multi-shape defect
remains.

## 11. Remaining limitations

- This is a narrow trust-boundary closure; no new component, candidate,
  synthesis, M12, CAD, or kinematic semantics were added.
- `ImportedCadComponent` schema is unchanged; artifact identity, source
  revision/state binding, instance identity, backend/provider provenance, and
  transformed-assembly identity are preserved.
- Ordinary M10-3 discrete sweeps retain `continuous_path_verified = False`;
  M10-4 proves only the explicitly requested path. These pre-existing M10
  limitations are unchanged.
- FEA, materials selection, manufacturing approval, tolerance verification,
  optimization, automatic synthesis/selection, and configuration-space
  certification remain outside scope.
