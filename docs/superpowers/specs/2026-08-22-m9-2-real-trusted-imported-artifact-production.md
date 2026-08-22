# M9-2 — Real Trusted Imported Artifact Production

**Date:** 2026-08-22
**Baseline accepted:** M8C_ARCHITECTURALLY_CLOSED_RUNTIME_GATED, M9_1_LIVE_FREECAD_BACKEND_VERIFIED
**Scope:** Trusted specialized/generated CAD artifact production chain only.
No mixed assembly realization, no kinematics, no FEA, no materials, no manufacturing.

## 1. Initial Producer Status

**PRODUCTION_PRODUCER_ALREADY_CONNECTED.**

The specialized producer `build_spur_gear_cad` is a registered production tool
(`mechcad-build-spur-gear-cad`, version `1.0`) in `tools/gearworks.py`
(`GearworksTools.registrations()`). `ToolBroker.execute` contains a dedicated
branch that invokes it with a real `Run`/`TaskDefinition` binding
(`project_id`, `run_id`, `task_id`, `bound_revision`, `bound_state_hash`),
so it is reachable through the production tool/backend boundary, not merely
unit-instantiated.

## 2. Selected Real Producer

- **Service/tool:** `mechcad-build-spur-gear-cad` (registered `ToolRegistration`)
- **Backend module:** `backends/gearworks_cad.py::build_spur_gear_cad`
- **Adapter:** `backends/adapters/py_gearworks.py::PyGearworksAdapter`
  (`adapter_version=0.1.0`, `library_name=py_gearworks`, `library_source=git`,
  `library_revision=2fc2a13d82a9997a65f30c870498f0bb3be62318`)
- **Libraries (validated profile):** `py_gearworks==0.0.18`, `build123d==0.11.1`,
  `numpy==2.3.5`, `scipy==1.18.0`
- **Runtime versions:** Python 3.14.6; FreeCAD 1.1.3 (live STEP verification only)

The producer is the existing production gear CAD path. Gear geometry is only the
proof fixture; the generic imported-component bridge is domain-neutral.

## 3. Actual Production Path

```
accepted fixed gear input (module_mm=2, teeth=12, face_width_mm=5, pressure_angle_deg=20)
  -> ToolBroker.execute(run, task, "mechcad-build-spur-gear-cad", "1.0", {...}, evidence_node="artifact.gear")
       -> build_spur_gear_cad(...)  [PyGearworksAdapter.spur_geometry -> build123d build_part -> export_step]
       -> real STEP bytes (443,209 bytes; byte-deterministic)
       -> ArtifactStore.publish(..., backend_provenance=py_gearworks, build123d_provenance=build123d,
                                 bound_revision, bound_state_hash, input_hash)
       -> EngineeringArtifact (sha256 + size + metadata persisted)
  -> ArtifactStore.existing(artifact_id)  [byte re-hash verified]
  -> resolve_imported_component(artifact_id, artifact_hash, store, component_id)
       -> ImportedCadComponent (artifact_id, artifact_hash, source_revision, source_state_hash from artifact record)
```

## 4. Source Binding

The producer is invoked with the **real** `bound_revision`/`bound_state_hash`
from the `TaskDefinition`, which is bound to the `Run`'s active revision/state
hash, which is bound to the actual `DesignState` (`StateManager.create_project`
revision 1, computed `state_hash`). The artifact records:
- `project_id="PRJ-M9-2"`, `run_id`, `task_id`
- `bound_revision=1`
- `bound_state_hash=<snapshot.state_hash>`

No state provenance is fabricated; the binding is genuine (verified equal to the
reloaded `DesignState` after generation).

## 5. Artifact Integrity

Verified in `tests/integration/test_m9_2_real_trusted_imported_artifact.py`:
- `artifact_id`: `ART-...` (uuid)
- `size`: 443,209 bytes (real STEP)
- `stored SHA-256`: `sha256:ee7dc56408763b727e592ce466fab8a42bbaa50a74045d1fb35c9c940b41d555`
  (for the fixed fixture; recomputed each run)
- `recomputed SHA-256` from actual persisted bytes == stored digest
- `ArtifactStore.existing(artifact_id)` returns the artifact; persisted byte
  re-hash matches `artifact.sha256` and `size_bytes` matches file size.

## 6. Producer Provenance

Captured from runtime (not invented):
- `backend_provenance`: `name=py-gearworks`, `adapter_version=0.1.0`,
  `library_name=py_gearworks`, `library_version=0.0.18`,
  `library_revision=2fc2a13d82a9997a65f30c870498f0bb3be62318`
- `build123d_provenance`: `name=build123d`, `adapter_version=build123d-runtime`,
  `library_name=build123d`, `library_version=0.11.1`

These are stored on `EngineeringArtifact`. The generic `ImportedCadComponent`
carries **no** producer/gear-specific fields — only `component_id`,
`artifact_id`, `artifact_hash`, `format`, `source_revision`, `source_state_hash`.

## 7. Imported Component Resolution

`resolve_imported_component` (generic M8C-2 bridge) reads the artifact and
returns `ImportedCadComponent` with:
- `component_id` (caller-supplied label only)
- `artifact_id`, `artifact_hash` (echoed from the trusted lookup)
- `format="step"`
- `source_revision = artifact.bound_revision` (trusted, from record)
- `source_state_hash = artifact.bound_state_hash` (trusted, from record)

**Why trusted, not caller-authored:** `resolve_imported_component` exposes no
parameters for `source_revision`/`source_state_hash`; they are derived solely
from the persisted artifact record. A caller supplying a wrong `artifact_hash`
raises `ImportedArtifactIntegrityError`. The generic bridge does not gain
build123d/gear-specific fields.

## 8. Live STEP Validation

FreeCAD **used** (1.1.3, `MECHCAD_FREECADCMD` set to the real executable).
Narrow existing backend boundary: the produced gear STEP was imported via a
freecadcmd subprocess (`FreeCADBackend._run`), recomputed, and verified:
- `shape_valid = True`
- `solid_count >= 1` (one valid gear solid)
- volume matches the build123d-computed volume (cross-checked in `test_gear_cad`)

No mixed assembly, collision, or kinematics were performed.

## 9. Determinism

Proven: same semantic input (`SpurGearCadInput(module_mm=2, teeth=12,
face_width_mm=5, pressure_angle_deg=20)`) executed twice through the real
producer yields **byte-identical STEP** (`export_step` uses a fixed
`timestamp="2000-01-01T00:00:00Z"`), hence identical `artifact.sha256`. This is
stronger than semantic identity: binary byte determinism was actually observed.

## 10. Domain Isolation

`imported_component.py`, `cad_assembly.py`, and `assembly_service.py` contain
**no** references to `py_gearworks`, `build123d`, `SpurGear`, `pressure_angle`,
`gear_ratio`, `tooth`, or `module_mm` (asserted by `test_generic_bridge_has_no_gear_semantics`).
A gear STEP is simply trusted STEP geometry to the generic layer.

## 11. Authority Boundary

- **No DesignState mutation:** reloaded `DesignState` revision and `state_hash`
  are unchanged after generation.
- **No ChangeProposal:** no `proposal` artifact/file created in the workspace.
- **No ChangeSet:** no `changeset` artifact/file created in the workspace.
- **No canonical component selection:** M9-2 ends at `ImportedCadComponent`.

## 12. Remaining M9 Work

- M9-3 live mixed assembly + exact kinematic proof
- M9-4 trusted analysis/backend provenance
- M9 system acceptance

## 13. Scope Confirmation

- No mixed assembly milestone implemented.
- No kinematic sweep, collision, measurement-provenance redesign, FEA, materials,
  or manufacturing.
- No commit / push / stash / reset / clean.
- No architecture change was required; only the `gear`/`test`/packaging
  environment dependencies were installed to make the already-connected producer
  reachable (analogous to M9-1 configuring `MECHCAD_FREECADCMD`).

## 14. Final Disposition

M9_2_LIVE_TRUSTED_IMPORTED_ARTIFACT_VERIFIED

## 15. M8C-2 Imported-Assembly Regression Closure (follow-up)

`tests/integration/test_imported_assembly_bridge.py::test_backend_with_imported_components`
previously failed under live FreeCAD. Two defects were corrected (narrow, no
production-validation weakening):

1. **Fixture:** the test fed a synthetic header-only STEP that real FreeCAD
   correctly rejected. Replaced with a **valid generic plate STEP** produced by
   the existing supported `FreeCADBackend.generate_program` (option b) — fully
   generic, non-gear, preserving imported-component semantics.
2. **Production routing bug in `backends/freecad_assembly.py::_compile`:** imported
   instances were mis-routed through the generated-part branch
   (`FreeCAD.openDocument` on a `.step`), so the `Part.insert` imported branch was
   never reached, and the imported object was given a `Label` instead of the
   canonical deterministic `Name` expected by `_verify_persisted`. Fixed to:
   detect imported components via `canonical_imported_components`, import the STEP,
   copy its shape into a canonical-named `Part::Feature` with the instance
   placement, and remove all temporary inserted objects. The Name-based
   verifier semantics are unchanged.

After the fix the M8C-2 regression passes; M9-2 acceptance (7 tests) and the
FreeCAD live regressions remain green.
