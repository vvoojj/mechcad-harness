# M7E-2 Preliminary AZ/EL Rotator FreeCAD Concept Implementation Plan

> **For agentic workers:** Execute this plan inline through the FreeCAD integration. Do not commit, push, stash, reset, clean, or modify unrelated worktree files.

**Goal:** Create and verify a deterministic FreeCAD FCStd/STEP packaging concept for a two-axis Yagi rotator without making final mechanical claims.

**Architecture:** Build a root `Assembly` App::Part with deterministic child groups and simple Part primitives. Represent AZ and EL axes as visible placeholder cylinders and demonstrate discrete placements without adding production kinematic logic or canonical design-state records.

**Tech Stack:** FreeCAD Part primitives, App::Part/App::FeaturePython metadata, FreeCAD document save/reload, STEP export.

## Global Constraints

- This is `PRELIMINARY_CONCEPT_ONLY` geometry and packaging, not a manufacturing design.
- Structural status is `NOT_VERIFIED`; manufacturing status is `NOT_READY`.
- Do not select real motors, gearboxes, bearings, materials, dimensions, loads, wind assumptions, FEA results, or final clamps.
- Preserve the existing repository code and unrelated dirty files.
- Do not mutate `DesignState` or create `ChangeSet` records.
- Use deterministic object names, group order, and placements.

---

### Task 1: Create the Parametric Concept Assembly

**Files/artifacts:**
- Create: `workspace/m7e2_preliminary_az_el_rotator/M7E2_Preliminary_AZ_EL_Rotator.FCStd`
- Create when supported: `workspace/m7e2_preliminary_az_el_rotator/M7E2_Preliminary_AZ_EL_Rotator.step`

**Structure:**
- Root `Assembly`.
- Groups `Base`, `AZ_Rotator`, `EL_Frame`, `Yagi_Carrier`, `Motor_Placeholders` in that order.
- Base: circular ground plate, circular AZ platform, central axis, bearing interface ring, motor envelope and hole markers.
- AZ stage: vertical axis, payload support frame, side uprights.
- EL frame: left/right supports, horizontal axis, carrier frame, EL motor envelope and hole markers.
- Yagi carrier: `40 x 40 x 500 mm` envelope, T-slot concept rails, adjustable mount tabs.

**Metadata:** Add `DesignStatus`, `StructuralStatus`, `ManufacturingStatus`, and `ConceptRole` string properties to the root and concept groups/objects.

### Task 2: Verify Discrete Kinematic Concept Placements

- Create temporary or retained placement copies for AZ `0` and `360` degrees.
- Create temporary or retained placement copies for EL `-90`, `0`, and `+90` degrees.
- Verify rigid placement changes preserve the conceptual axis and do not introduce obvious self-intersection.
- Record checks as document properties or a compact verification feature without claiming continuous proof.

### Task 3: Save, Export, Reload, and Inspect

- Save FCStd.
- Export STEP using the FreeCAD document export API.
- Close/reload the FCStd.
- Verify the deterministic tree order, object names, metadata, and object count.
- Fit an isometric view and inspect the resulting assembly.
- Confirm no `DesignState`, `ChangeSet`, artifact-store, or final-design objects were introduced.
