# M9-3 — Live Mixed Assembly + Exact Kinematic Proof

**Date:** 2026-08-22
**Baseline accepted:** M8C_ARCHITECTURALLY_CLOSED_RUNTIME_GATED, M9_1_LIVE_FREECAD_BACKEND_VERIFIED, M9_2_LIVE_TRUSTED_IMPORTED_ARTIFACT_VERIFIED
**Scope:** First full live generic mechanical vertical slice: source-bound generated part + real trusted imported STEP component → mixed `CadAssemblyProgram` → real FreeCAD mixed assembly → persistence + fresh reload → real FreeCAD transient exact measurement → real production kinematic sweep.

## 1. Baseline Preflight

- **FreeCAD executable:** `C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe` (via `MECHCAD_FREECADCMD`, not hardcoded in business logic).
- **FreeCAD version:** `1.1.3` (confirmed at runtime by `discover_filename`/`provenance()`; execution boundary "bundled FreeCAD command line").
- **M9-2 producer runtime:** `py_gearworks==0.0.18` (`library_source=git`, `library_revision=2fc2a13d82a9997a65f30c870498f0bb3be62318`), `build123d==0.11.1`, `numpy==2.3.5`, `scipy==1.18.0` — all present and exercised live.
- **Imported-component routing fix:** present in current `backends/freecad_assembly.py::_compile` (imported instances detected via `canonical_imported_components`, STEP inserted, shape copied to canonical `Name`, temp objects removed).
- **Imported-assembly regression:** green (`tests/integration/test_imported_assembly_bridge.py`).
- **Production `analyze_assembly_kinematics(...)`:** exposes NO caller-controlled `exact_measure` / `kinematic_measure` parameter (verified by signature inspection in `test_m8c3_production_kinematic_vertical_slice.py`); the only knob is the composition-time `kinematic_measure` used only for dependency injection of the real provider or a deterministic test double.
- **ProductionApplication composition:** defaults to the REAL `FreeCADTransientAssemblyMeasurementProvider` (verified `app._kinematic_measurement_provider` is an instance of it and `app.kinematic_measure.__func__ is FreeCADTransientAssemblyMeasurementProvider.exact_measure`).

## 2. Production Bug Found and Fixed

**Defect:** `FreeCADTransientAssemblyMeasurementProvider` only supported generated `CadPartProgram` components. Its transient FreeCAD script built a `part_paths` map keyed by `instance.part_id` from `program.canonical_parts` only, then did `part_paths[instance.part_id]` for every instance. For an imported-component instance (`instance.part_id == component_id`), the key was absent → `KeyError` inside the FreeCAD subprocess (`transient part shape missing` / Python `KeyError`), so any mixed (generated + imported) kinematic sweep failed at the real measurement boundary. The existing kinematic vertical slice (M8C-3) used a *deterministic injected* measure and never exercised the real provider against imported geometry; the live kinematic tests (M7C1/M7D2) used generated-only programs. The gap was therefore never caught until M9-3 drove the real provider through a mixed assembly.

**Root cause:** imported STEP geometry was never loaded into the transient FreeCAD document; the provider had no path to resolve an `ImportedCadComponent`'s artifact bytes.

**Narrow fix (no architecture change, no new primitives/collision/kinematic math):**
- `FreeCADTransientAssemblyMeasurementProvider` gained optional `workspace` and `project_id` constructor params (default `None`, preserving all existing generated-only call sites and the `execute=`/`execute_in_workspace=` test doubles).
- Added `_resolve_imported_artifact_path(component)`: scans `workspace/projects/{project_id}/runs/*/artifacts/{artifact_id}/metadata.json`, loads the `EngineeringArtifact`, re-verifies `sha256 == component.artifact_hash`, confirms file size, and returns the absolute STEP path. This preserves the M9-2 trust chain (artifact-record authoritative, SHA-256 re-checked) and resolves the right physical bytes without adding artifact filesystem paths to the generic `ImportedCadComponent` model.
- The measurement script now branches per instance: imported instances are loaded with `Part.insert` + shape copy + temp-document close (mirroring the assembly backend's imported routing), generated instances are recompiled from their `CadPartProgram` as before. Both paths apply the instance placement and run `common().Volume` / `distToShape()`.
- `ProductionApplication.__init__` now constructs the real provider with `workspace=self.state_manager.workspace` and `project_id=project_id` so it can resolve imported artifacts during a live sweep.

**Regression evidence:** existing transient/kinematic unit + live tests (generated-only) remain green; the new M9-3 live test drives the real provider through a mixed assembly end-to-end.

### 2b. Artifact resolution refactor (final closure)

The first fix (§2) scanned `workspace/projects/{project_id}/runs/*/artifacts/{artifact_id}/metadata.json` and manually loaded `EngineeringArtifact` / checked hash and size inside the FreeCAD provider — duplicating `ArtifactStore` filesystem-layout knowledge. On final closure this was refactored to reuse the **existing trusted `ArtifactStore` boundary**:

- Added `ArtifactStore.existing_in_project(artifact_id)` (run-scoped over the project): it enumerates the project's run directories and delegates to the existing `ArtifactStore.existing(artifact_id)` per run. `existing()` is the canonical trusted resolver and already performs:
  - exact `artifact_id` match (via `_safe_scope`, which rejects absolute paths, multipart paths, and `..`/`/`),
  - `EngineeringArtifact` metadata validation,
  - STEP type/format is carried on the record,
  - **actual-byte SHA-256 recomputation** and comparison to the stored digest,
  - size equality,
  - file existence and that `relative_path` stays under the workspace.
- `FreeCADTransientAssemblyMeasurementProvider._resolve_imported_artifact_path` now calls `store.existing_in_project(component.artifact_id)` and additionally asserts `artifact.artifact_type == STEP` and `artifact.sha256 == component.artifact_hash` (the caller-trusted hash). It no longer parses metadata or recomputes hashes itself.

**Trust proofs (all satisfied, no M9-2 weakening):**
- *cannot escape workspace/project:* `ArtifactStore` constructor + `existing()` use `_safe_scope` on `project_id`/`run_id`/`artifact_id` (rejects `..`/absolute/multipart). Run directories are enumerated from the trusted `projects/{project_id}/runs` root, not from caller input. `relative_path` is always under `self.workspace`.
- *accepts only the exact artifact_id:* `existing()` requires an exact `artifact_id` match.
- *validates EngineeringArtifact metadata:* `model_validate_json` + project/run binding checks in `existing()`.
- *validates STEP format/type:* provider asserts `artifact.artifact_type == ArtifactType.STEP`.
- *validates size:* `existing()` checks `path.stat().st_size == artifact.size_bytes`.
- *recomputes actual-byte SHA-256:* `existing()` does `sha256(path.read_bytes())` vs `artifact.sha256`; provider also enforces `== component.artifact_hash`.
- *fails closed on zero or ambiguous matches:* `existing_in_project` returns `None` when matches count `!= 1` (zero or more than one) → provider raises `FreeCADExecutionError`.
- *cannot silently choose the wrong run/artifact:* `artifact_id` is a unique uuid and `existing_in_project` requires exactly one match; the trusted store's project/run binding is re-checked.

**New regression coverage (unit):** `tests/unit/test_transient_freecad_measurement.py` adds `existing_in_project` single/zero/ambiguous cases and provider resolution tests for missing artifact, hash mismatch, non-STEP type, and missing workspace scope.

## 3. Live Fixture

- **Generated component:** `CadPartProgram(part_id="plate")` — `MountingPlateDesignSpec(40×40×10 mm, one Ø6 mm hole)`, compiled via `ProductionApplication.compile_design_spec` bound to the source `DesignState` (revision 1, `state_hash`).
  - source `revision=1`, `source_state_hash=sha256:dc7cede1569bea4165ccd14ab0feb9e378ece44ad8858b6bc041357809bdaa40`
  - `program_hash=sha256:46c3ffa9a014f8d1b53907b5a2bdcaf48295ecc462a6dc7165faf143d73f0ad0`
- **Imported component:** real trusted STEP spur gear produced by `mechcad-build-spur-gear-cad@1.0` (`module_mm=2, teeth=12, face_width_mm=5, pressure_angle_deg=20`).
  - `artifact_id=ART-8405632e-da82-45bd-babf-6de17bcece6e`
  - `artifact_hash=sha256:ee7dc56408763b727e592ce466fab8a42bbaa50a74045d1fb35c9c940b41d555` (443,209 bytes; identical to the M9-2 recorded digest → byte-deterministic across sessions)
  - producer `BackendProvenance`: `py-gearworks 0.0.18` (`git`, `2fc2a13d82a9997a65f30c870498f0bb3be62318`); `build123d 0.11.1`
  - resolved `ImportedCadComponent(component_id="gear-1")` with `source_revision=1`, `source_state_hash=sha256:dc7cede1569bea4165ccd14ab0feb9e378ece44ad8858b6bc041357809bdaa40` (derived from the artifact record, not caller-authored)
- **Assembly:** `CadAssemblyProgram(assembly_id="m9-3-mixed-fixture")` with two `CadComponentInstance`s:
  - `plate-inst` (generated `plate`) at `(x=0, y=-60, z=0)`
  - `gear-inst` (imported `gear-1`) at `(x=20, y=0, z=5)`

Both components derive from the **same** project `revision=1` / `state_hash` (the plate via `compile_design_spec` source binding, the gear via the task bound to the same active run/state). Provenance is reported separately below; no unified fake binding was constructed.

## 4. Actual Production Chain

```
DesignState(revision=1, state_hash=sha256:dc7c...)
  -> ProductionApplication.compile_design_spec(spec=MountingPlateDesignSpec)
  -> CadCompilationResult.program: CadPartProgram("plate")   [M8C-1 generated]

Run + TaskDefinition(bound to revision=1/state_hash, allowed mechcad-build-spur-gear-cad@1.0)
  -> ToolBroker.execute(..., "mechcad-build-spur-gear-cad", "1.0", {...}, evidence_node="artifact.gear")
  -> build_spur_gear_cad (PyGearworksAdapter.spur_geometry -> build123d build_part -> export_step, ts="2000-01-01T00:00:00Z")
  -> ArtifactStore.publish(STEP, sha256, backend_provenance=py_gearworks, build123d_provenance)
  -> ArtifactStore.existing(artifact_id) -> EngineeringArtifact
  -> resolve_imported_component(...) -> ImportedCadComponent("gear-1")   [M9-2 trusted]

CadAssemblyProgram(mixed: plate part + gear-1 imported component + 2 instances)
  -> ProductionApplication.build_assembly_with_imported_components(run_id=...)
  -> CadAssemblyGenerationService -> FreeCADAssemblyBackend.generate_assembly
  -> real freecadcmd: compile program, Part.insert gear STEP + copy to canonical Name + remove temp,
     recompile plate FCStd; export FCStd + STEP to ArtifactStore
  -> persisted assembly FCStd/STEP + fresh-process reopen + STEP re-import verification
  -> ProductionApplication.analyze_assembly_kinematics(axis, moving=("gear-inst",), stationary=("plate-inst",), angles=(0,90,180,270))
  -> CadKinematicSweepService -> TransientAssemblyAnalysisService(FreeCADTransientAssemblyMeasurementProvider().exact_measure)
  -> per angle: transformed CadAssemblyProgram -> real FreeCAD transient doc -> common().Volume / distToShape()
  -> CadKinematicSweepResult
```

## 5. Mixed Assembly Live Verification

- `generation.fcstd_verification.shape_valid = True`, `solid_count == 2` (no extra/duplicate temporary imported solids remain).
- `generation.step_verification.shape_valid = True`, `solid_count == 2`.
- Canonical object names present in the persisted FCStd: `inst_706c6174652d696e7374` (plate) and `inst_676561722d696e7374` (gear-1) — deterministic `inst_<hex(instance_id)>` names. (The STEP re-import produces FreeCAD-native names `assembly`/`assembly001`; the assembly backend verifies STEP only by solid count, per its existing contract — FCStd is the authoritative persisted document.)
- **Fresh reload:** the persisted FCStd was reopened in a separate freecadcmd process; the canonical placed-gear object's base was read back as `(20.0, 0.0, 5.0)` within 1e-6 — placement preserved. The production `_verify_persisted` also asserts placement equality (raises on mismatch) and ran green.
- **Persisted artifact integrity:** `ArtifactStore.existing(assembly FCStd/STEP ids)` returned the artifacts; recomputed `sha256` matched `artifact.sha256` and `size_bytes` matched the file size.

## 6. Exact Measurement Evidence

`common().Volume` and `distToShape()` were executed by **real FreeCAD** (no bounding box, mesh, radius heuristic, or analytical substitute). Per-angle results:

| angle (deg) | interference_volume_mm3 | distance_mm | classification |
|---|---|---|---|
| 0   | 0.0 | 5.999999999991651 | positive_clearance |
| 90  | 0.0 | 25.99999999999165 | positive_clearance |
| 180 | 0.0 | 14.922813621495427 | positive_clearance |
| 270 | 545.4343369357625 | 0.0 | interference |

The moving gear orbits the Z axis at radius 20 mm; at 270° its world position reaches `(0,-20,5)`, overlapping the stationary plate (which spans `y∈[-60,-20]`), so real FreeCAD reports a genuine 545.43 mm³ common volume. The fixture naturally produced multiple classifications — reported as-is, no values were selected to force a particular collision state.

## 7. Kinematic Identity

- `source_assembly_hash  = sha256:55b01529598de2bfc3c6e20785b87f023007b81c17f8ed9ed6f3778f074077c1`
- `request_hash          = sha256:91e2ffadc27176190e48b3d7ac4776bc889429ddf5319352129379afcb4a4fb2`
- transformed assembly hashes (per sample): `18c0dc1d…`, `8950433b…`, `3e0e4e9e…`, `e20d9ba4…` (distinct → motion really changed transformed geometry)
- `result_hash           = sha256:b95c8101a0f97ccd8aa2682d2f7d2a4a0b8461b046f0ae61cf7993da9ce4ce53`
- `continuous_sweep_verified = False` (discrete samples do not prove continuous collision-free motion)

The live sweep was executed twice; measurements matched within `abs=1e-6` (real FreeCAD floating-point determinism under existing tolerances).

## 8. Transient Behavior

- The transient provider operates only in a **temporary disposable workspace** (`tempfile.TemporaryDirectory`); imported STEP bytes are read from (never written to) the project `ArtifactStore`.
- **No DesignState mutation:** `load_state()` revision/hash before and after the sweep are identical.
- **No ChangeSet / ChangeProposal** created.
- **No public per-angle ArtifactStore artifacts:** the set of `projects/*/runs/*/artifacts/*/metadata.json` files was identical before and after the kinematic sweep (the sweep published nothing; only the earlier producer run and assembly generation published artifacts).
- `source_assembly_hash` (canonical mixed assembly) differs from each `transformed_assembly_hash` (per-angle placement), as required.

## 9. Trust / Provenance Chain (real, retained)

```
build_spur_gear_cad (py_gearworks 0.0.18, git 2fc2a13d…; build123d 0.11.1)
  -> ArtifactStore.publish STEP  (artifact_id=ART-8405632e-…, sha256=ee7dc56408763b727…, 443209 bytes)
  -> ArtifactStore.existing(artifact_id) re-hash verified
  -> resolve_imported_component(...) -> ImportedCadComponent("gear-1")
       source_revision=1, source_state_hash=sha256:dc7cede… (from artifact record, not caller-set)
```
The imported artifact used by the live proof retains the full M9-2 trust chain; no temporary synthetic STEP was substituted.

## 10. Production Bugs Found

1. **Transient measurement provider did not support imported STEP components** (root cause + narrow fix in §2). Regression coverage: new `tests/integration/test_m9_3_live_mixed_assembly_exact_kinematic.py` drives the real provider through a mixed assembly; existing transient/kinematic suites remain green.
2. **Stale unit-test assumption** (`tests/unit/test_backends.py`): `test_package_inspection_uses_trusted_distribution_mapping` hardcoded `py_gearworks` as *unavailable*. Because M9-3 requires the real producer (and `py_gearworks` is now installed), the test's assumption was invalid. Fixed to assert the inspection reflects actual install state (environment-aware), preserving the test's intent (missing packages still raise / report unavailable). This is a test-only correction, not a product-verification weakening.

No other production bugs found.

## 11. Tests

| Group | Result |
|---|---|
| M9-3 live (`test_m9_3_live_mixed_assembly_exact_kinematic.py`) | **1 passed** |
| M9-2 (`test_m9_2_real_trusted_imported_artifact.py`) | **7 passed** |
| M8C-2 imported/mixed assembly (`test_imported_assembly_bridge.py`, `test_cad_assembly_mixed.py`, `test_assembly_integrity.py`) | **17 passed** |
| M8C-3 production kinematic (`test_m8c3_production_kinematic_vertical_slice.py`) | **9 passed** |
| transient FreeCAD measurement (`test_m7c1_transient_freecad_measurement_live.py`, `test_transient_freecad_measurement.py`) | **8 passed** |
| FreeCAD assembly backend (`test_freecad_assembly_verification.py`) | **4 passed** |
| M9-1 (`test_m9_1_freecad_runtime_live.py`) | **7 passed** |
| M7C1 kinematic sweep live (`test_m7c1_kinematic_sweep_live.py`) | **1 passed** |
| Full unit suite (`tests/unit`) | **611 passed, 19 skipped** |

`python -m compileall src/mechcad_harness -q` → exit 0. `git diff --check` → exit 0 (only CRLF working-copy notices, no errors).

## 12. Files Changed

- `src/mechcad_harness/transient_freecad_measurement.py` — imported-component support in the real measurement provider (bug fix) + delegation to `ArtifactStore.existing_in_project` (closure refactor).
- `src/mechcad_harness/artifacts/storage.py` — added `ArtifactStore.existing_in_project(artifact_id)` trusted project-scoped resolver reusing `existing()`.
- `src/mechcad_harness/application.py` — wire `workspace`/`project_id` into the composed real provider.
- `tests/integration/test_m9_3_live_mixed_assembly_exact_kinematic.py` — new M9-3 live vertical-slice test (A–Q coverage).
- `tests/unit/test_backends.py` — environment-aware correction of a stale `py_gearworks` availability assertion.
- `tests/unit/test_transient_freecad_measurement.py` — new resolution trust/regression coverage.

## 13. Edges Upgraded

The following previously `RUNTIME_GATED` edges are now `LIVE_FREECAD_VERIFIED` for the generic (mixed generated + imported) path:

- mixed generated/imported assembly realization by real FreeCAD (`FreeCADAssemblyBackend`)
- fresh mixed-assembly reload (separate freecadcmd process, placement preserved)
- transient FreeCAD transformed geometry for imported STEP components
- `common().Volume` exact measurement on a live mixed assembly
- `distToShape()` exact measurement on a live mixed assembly
- full discrete kinematic sweep through the production `FreeCADTransientAssemblyMeasurementProvider` (real, not deterministic)

NOT upgraded (not executed in this milestone): multi-axis kinematics, continuous collision verification, FEA, materials, manufacturing.

## 14. Remaining M9 Work

- M9-4 trusted analysis/backend provenance (durable provider-identity provenance — known limitation, intentionally not redesigned here).
- M9 system acceptance.

## 15. Scope Confirmation

- No multi-axis kinematics, continuous sweep, FEA, materials, manufacturing, optimization, component/gear selection, or synthesis.
- Generic modules (`cad_assembly.py`, `imported_component.py`, `assembly_service.py`, `transient_freecad_measurement.py`, `application.py`) contain no gear/tooth/pressure-angle/Yagi/AZ/EL semantics; the gear is merely a convenient real imported solid.
- No DesignState mutation, ChangeProposal, ChangeSet, or automatic selection performed.
- No commit / push / stash / reset / clean.
- Runtime environment configured (not architecture changed): `MECHCAD_FREECADCMD` set; `build123d==0.11.1` and `py_gearworks==0.0.18` (from local wheel cache) installed; `numpy==2.3.5` pinned to satisfy the producer's validated-gear-profile compatibility gate.

## 16. Final Disposition

M9_3_LIVE_EXACT_VERTICAL_SLICE_VERIFIED
