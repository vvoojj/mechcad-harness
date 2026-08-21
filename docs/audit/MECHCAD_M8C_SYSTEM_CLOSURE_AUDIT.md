# M8C System-Level Closure Audit

**Date:** 2026-08-22
**Scope:** M8C production chain (M8C-1 → M8C-2 → M8C-3) architectural closure
**Method:** Read current repository bytes; classified every edge from implementation + tests, not milestone summaries.
**Runtime environment:** FreeCAD unavailable (`discover_freecad().available == False`).

---

## 1. Executive Classification

| Edge | Classification |
|---|---|
| State → DesignSpec / CAD compilation | **IMPLEMENTED_AND_CONNECTED** |
| ArtifactStore → ImportedCadComponent | **IMPLEMENTED_AND_CONNECTED** |
| CadPartProgram + ImportedCadComponent → CadAssemblyProgram | **IMPLEMENTED_AND_CONNECTED** |
| CadAssemblyProgram → FreeCAD realization | **RUNTIME_GATED** |
| Assembly → transient analysis | **IMPLEMENTED_AND_CONNECTED** |
| Transient analysis → exact measurement | **IMPLEMENTED_AND_CONNECTED** |
| ProductionApplication → kinematic sweep | **IMPLEMENTED_AND_CONNECTED** |
| Kinematic sweep → deterministic result | **IMPLEMENTED_AND_CONNECTED** |

All intended M8C production edges are implemented and connected. The only sub-classification that is not live-executed is the **live FreeCAD realization** (`CadAssemblyProgram → FreeCAD realization` and the live execution of transient/measurement/sweep geometry). Those are `RUNTIME_GATED`, never claimed as live-verified.

---

## 2. Complete Production Chain (current real bytes)

```
DesignState (canonical, source-bound)
  -> MountingPlateDesignSpec (pre-accepted caller contract)
       [ ProductionApplication.compile_design_spec ]
  -> CadCompilationService.compile_mounting_plate  (validates project/revision/state_hash, fail-closed)
  -> CadPartProgram  (program_hash deterministic)
       +
  ImportedCadComponent  (artifact_id / artifact_hash[sha256] / source_revision / source_state_hash)
       [ trusted ArtifactStore: store.existing + sha256 byte check + format check ]
  -> CadAssemblyProgram  (assembly_id, parts, imported_components, instances)
       [ ProductionApplication.build_assembly_with_imported_components -> CadAssemblyGenerationService -> FreeCADAssemblyBackend ]
  -> assembly_hash (deterministic: program_hash + imported identity/hash + instance transforms)
  -> ProductionApplication.analyze_assembly_kinematics
       [ composes TransientAssemblyAnalysisService(self.kinematic_measure) -> CadKinematicSweepService ]
  -> CadKinematicSweepRequest (axis, partition, ordered angles, source_assembly_hash)
  -> transformed_assembly_program (per angle, deterministic axis-angle transform)
  -> TransientAssemblyAnalysisService.analyze(...)
  -> measurement provider (default: FreeCADTransientAssemblyMeasurementProvider.exact_measure)
  -> CadKinematicSweepResult (request_hash, source_assembly_hash, samples, result_hash,
       continuous_sweep_verified = False)
```

---

## 3. Authority Boundaries

- **Canonical authority** remains `DesignState` + accepted change workflow. No `DesignState` mutation, no hidden revision writes, no `ChangeSet` bypass, no agent mutation across the M8C chain.
- **CAD/assembly/collision/kinematic outputs are derived computation/evidence**, never authority.
- **ArtifactStore authority** is enforced inside the trusted backend (`store.existing` + sha256 recompute + format allow-list). Ordinary workflow callers pass already-resolved `ImportedCadComponent`/`CadPartProgram`; they cannot redirect the workspace or fabricate artifact bytes.
- **Measurement authority** is owned by the `ProductionApplication` composition (see §5).

---

## 4. Deterministic Identity Chain

| Identity | Source | Carried in |
|---|---|---|
| source state hash | `StateManager` (load_revision + state_hash) | `ProductionStateBinding`, `CadCompilationResult`, `ImportedCadComponent` |
| spec_hash | `mounting_plate_spec_hash` | `CadCompilationResult` only |
| compiler_version | `COMPILER_VERSION` | `CadCompilationResult` only |
| program_hash | `cad_program_hash` | `CadCompilationResult`, and inside `assembly_hash` |
| artifact_hash | `ArtifactStore` sha256 | `ImportedCadComponent` |
| imported_component_hash | `imported_component_hash` | inside `assembly_hash` |
| assembly_hash | `assembly_hash(program)` | `CadKinematicSweepRequest.source_assembly_hash`, `CadKinematicSweepResult.source_assembly_hash` |
| request_hash | canonical request payload | `CadKinematicSweepRequest`, `CadKinematicSweepResult` |
| transformed_assembly_hash | `assembly_hash(transformed)` | per `CadKinematicSweepSample` |
| result_hash | canonical result payload | `CadKinematicSweepResult` |

**Provenance separation (explicitly accepted):**
- `spec_hash` / `compiler_version` live **only** on `CadCompilationResult`. They are **not** folded into `CadAssemblyProgram` / `assembly_hash`. → `COMPILATION_PROVENANCE_SEPARATE_NOT_TRANSITIVELY_LINKED`.
- `run_id` is **correlation / storage scope only**; it is not part of any kinematic or assembly semantic identity and is not treated as trusted `RunController` identity.

---

## 5. Trust Boundaries

- **Artifact byte integrity:** `ImportedCadComponent` is resolved only from a persisted `ArtifactStore` record (`store.existing`); the artifact sha256 is recomputed and compared; unsupported formats fail closed. Arbitrary filesystem paths cannot become trusted geometry.
- **Source provenance:** `ImportedCadComponent.source_revision` / `source_state_hash` are taken from trusted artifact metadata, not caller-supplied.
- **Workspace ownership:** the backend constructs `ArtifactStore(workspace, project_id, run_id)` from its own trusted workspace; an ordinary workflow caller cannot redirect it.
- **Measurement provider ownership:** the exact-measurement provider is composed at `ProductionApplication.create(...)` (`kinematic_measure`). `analyze_assembly_kinematics(...)` exposes **no** `exact_measure` / `kinematic_measure` parameter (verified via `inspect.signature`), so an ordinary caller cannot author geometry measurements. The production default is `FreeCADTransientAssemblyMeasurementProvider().exact_measure`.
- **run_id semantics:** correlation/storage scope only.

---

## 6. Runtime Evidence Matrix

| Capability | IMPLEMENTED | CONNECTED | DETERMINISTIC-PROVIDER TEST | LIVE_FREECAD_VERIFIED | RUNTIME_GATED |
|---|---|---|---|---|---|
| Imported STEP load + byte check | yes | yes (backend `store.existing` + sha256) | n/a | no | yes |
| Mixed assembly persistence (FCStd/STEP) | yes | yes (`build_assembly_with_imported_components` → backend) | n/a | no | yes |
| Fresh assembly reload verification | yes | yes (`verify_persisted_assembly` / `_verify_persisted`) | n/a | no | yes |
| Transient FreeCAD transform | yes | yes (transient service + provider) | n/a | no | yes |
| `common().Volume` | yes (in provider script) | yes | n/a (synthetic only) | no | yes |
| `distToShape()` | yes (in provider script) | yes | n/a (synthetic only) | no | yes |
| Full discrete sweep through live FreeCAD provider | yes | yes (production method + composed FreeCAD provider) | yes (injected provider proves internal graph) | no | yes |

Deterministic-provider tests prove the **internal production graph** (request build, sweep service, transient service, partition/hash validation, classification). They are **not** exact FreeCAD proofs and do not create public per-sample `ArtifactStore` artifacts.

---

## 7. Provider / Backend Provenance

The durable `CadKinematicSweepResult` carries `sweep_version = RIGID_BODY_COLLISION_SWEEP_VERSION` (the sweep service identity) but **does not** record the measurement-provider identity or version, nor the FreeCAD backend/runtime identity. The `TransientAssemblyAnalysisResult` likewise carries no provider/backend identity.

**Classification:** `PROVENANCE_LIMITATION`. This does not create a trust ambiguity for current production evidence (the provider is owned by the trusted `ProductionApplication` composition, and the durable result is bound to `source_assembly_hash` + `request_hash`). No result-model redesign is performed in this audit. If future evidence must distinguish a deterministic test provider from a live FreeCAD provider, that is a next-milestone item.

---

## 8. Known Accepted Limitations

- `PREACCEPTED_CALLER_CONTRACT_ONLY` — `MountingPlateDesignSpec` is accepted by the caller; no persisted trusted DesignSpec-acceptance record is claimed.
- `COMPILATION_PROVENANCE_SEPARATE_NOT_TRANSITIVELY_LINKED` — `spec_hash`/`compiler_version` remain on `CadCompilationResult`; not folded into assembly identity.
- `run_id correlation/storage scope only`.
- `continuous_sweep_verified = False` — discrete sampling only; no continuous collision-free motion is claimed.
- Live FreeCAD imported-assembly + exact transient measurement + kinematic sweep is `RUNTIME_GATED` in this verification environment.

---

## 9. Boundary Violations

**NONE.**

No `BOUNDARY_VIOLATION`, incorrect trust claim, stale documentation claim, missing fail-closed validation, or test-proving-the-wrong-thing was found. Architecture docs (`MECHCAD_SYSTEM_CONTRACT`, `MECHCAD_RUNTIME_FLOW`, `MECHCAD_SUBSYSTEM_CONTRACTS`, `MECHCAD_CAPABILITY_MATRIX`) are consistent with the implementation: they explicitly state `continuous_sweep_verified = False`, assert no continuous proof, and describe `accepted DesignSpec` without claiming transitive compiler provenance or trusted `run_id`. No documentation correction was required.

---

## 10. Test Evidence

| Edge / Boundary | Test(s) | Status |
|---|---|---|
| Source binding (revision/hash fail-closed) | `test_m8c1_production_cad_compilation.py::test_production_application_compile_stale_source_fails_closed`, `..._hash_mismatch_fails_closed` | pass |
| Deterministic CAD compilation | `test_cad_compilation.py`, `test_m8c1_*`::`test_production_application_compile_determinism` | pass |
| Artifact byte integrity / provenance | `test_imported_component.py`, `test_imported_component_trust.py`, `test_imported_assembly_bridge.py::TestImportedComponentResolution` | pass |
| Mixed assembly identity | `test_cad_assembly_mixed.py`, `test_imported_assembly_bridge.py::TestCadAssemblyProgramWithImported` | pass |
| Production assembly caller | `ProductionApplication.build_assembly_with_imported_components` (real code path; FreeCAD realization runtime-gated) | connected |
| Provider composition trust boundary | `test_m8c3_...::TestM8C3MeasurementTrustBoundary` (no caller arg; default trusted FreeCAD provider; injected provider composition-only) | pass |
| Transient analysis | `test_transient_assembly_analysis.py`, `test_transient_freecad_measurement.py` | pass |
| Kinematic partition / fail-closed | `test_kinematic_sweep.py::test_execution_service_rejects_source_hash_mismatch...`, M8C-3 `test_production_fails_closed_on_*_partition` / `_invalid_axis` / `_unknown_instance` | pass |
| Deterministic angle order / result | `test_kinematic_sweep.py::test_sweep_result_aggregates...`, M8C-3 `test_production_entry_runs_real_sweep_through_internal_graph` / `test_production_result_is_deterministic` | pass |
| `continuous_sweep_verified = False` | M8C-3 + `test_kinematic_sweep.py` assertions | pass |
| Domain isolation (generic modules) | no Yagi/AZ/EL/gear-tooth/transmission-ratio dependency in `cad_compilation`, `imported_component`, `cad_assembly`, `assembly_service`, `transient_*`, `kinematic_sweep`, M8C `ProductionApplication` methods | verified by source read |

Counts:
- M8C-3 file: **10 passed, 1 skipped** (live test runtime-gated).
- Targeted M8C-1 / M8C-2 / M8C-3 / M7C kinematics / transient / assembly: **105 passed, 4 skipped**.
- Full suite (run during M8C-3 closure verification): **632 passed, 51 skipped**.
- `python -m compileall src/mechcad_harness -q` → exit 0.
- `git diff --check` → exit 0 (only pre-existing CRLF whitespace warnings).

No edge is proven only by a test that manually constructs the production graph: the M8C-3 deterministic tests enter through the real `ProductionApplication.analyze_assembly_kinematics` and real `CadKinematicSweepService` / `TransientAssemblyAnalysisService`; only the external CAD measurement callback is injected at the composition boundary.

---

## 11. Files Changed

**Changed by this audit:** only this document (`docs/audit/MECHCAD_M8C_SYSTEM_CLOSURE_AUDIT.md`). No source code was modified during the audit.

**Pre-existing M8C implementation changes (from prior milestones, present in working tree):**
- Modified: `src/mechcad_harness/application.py`, `src/mechcad_harness/assembly_service.py`, `src/mechcad_harness/backends/freecad_assembly.py`, `src/mechcad_harness/cad_assembly.py`.
- New (untracked): `src/mechcad_harness/cad_compilation.py`, `src/mechcad_harness/imported_component.py`.
- New tests: `tests/integration/test_imported_assembly_bridge.py`, `tests/integration/test_m8c1_production_cad_compilation.py`, `tests/integration/test_m8c3_production_kinematic_vertical_slice.py`, `tests/unit/test_cad_assembly_mixed.py`, `tests/unit/test_cad_compilation.py`, `tests/unit/test_imported_component.py`, `tests/unit/test_imported_component_trust.py`.
- New specs/plans: M8C-1 / M8C-2 / M8C-3 design + plan docs.

No commit / push / stash / reset / clean was performed.

---

## 12. M8C Closure Decision

**M8C_ARCHITECTURALLY_CLOSED_RUNTIME_GATED**

Rationale (per closure rule):
- All intended M8C production edges are implemented and connected.
- No trust/authority boundary violation remains.
- Remaining gaps are explicitly accepted provenance limitations or live-FreeCAD runtime verification only.
- Not `M8C_FULLY_CLOSED_LIVE_VERIFIED`: the live FreeCAD imported-assembly + exact transient measurement + kinematic sweep path has **not** been executed (FreeCAD unavailable). Deterministic-provider tests are explicitly not treated as live proof.

---

## 13. Next Major Milestone Recommendation

**M9 — Live FreeCAD Runtime Verification & Trusted Imported Artifact Production.**

This is the single highest-value remaining gap. The entire M8C production chain is implemented and connected, but every live-FreeCAD edge is `RUNTIME_GATED` in the current environment, and the imported component used in tests is a synthetic/placeholder STEP rather than a genuinely generated trusted artifact wired through the production path. The next milestone should:

1. Execute the connected production chain (`ProductionApplication` → assembly realization → reload → transient transform → `common().Volume` / `distToShape()` → discrete sweep) on a FreeCAD-capable runtime in a temporary/test workspace.
2. Produce a **real trusted imported STEP artifact** (e.g., generated from build123d/gear tooling or an equivalent trusted source) and resolve it through the production `ArtifactStore` path, removing the synthetic-STEP fixture from the live proof.
3. Capture measurement-provider / FreeCAD backend identity in the durable evidence (closing the §7 `PROVENANCE_LIMITATION`).

This is recommended over multi-axis kinematics, FEA, materials, or manufacturing validation, which are explicitly out of scope for M8C closure and represent later-stage concerns (Stage C in the system contract).
