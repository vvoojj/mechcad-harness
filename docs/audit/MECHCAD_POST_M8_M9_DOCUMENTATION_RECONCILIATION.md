# MechCAD Post-M8/M9 Documentation Reconciliation

**Date:** 2026-08-22
**Author:** documentation reconciliation (read-only of code/tests/specs/audits; documentation-only output)
**Scope:** bring current normative architecture documentation into alignment with the accepted M8 (production architecture) and M9 (live-verified) system baseline, after M9 system acceptance.
**Method:** read current repository bytes; classified every claim from accepted system-level records (`docs/audit/MECHCAD_M8C_SYSTEM_CLOSURE_AUDIT.md`, `docs/audit/MECHCAD_M9_SYSTEM_ACCEPTANCE.md`), milestone specs, and current implementation/tests. No production source was modified.

---

## 1. Purpose

M8 established the production orchestration and generic CAD / trusted imported-component / mixed-assembly / production kinematic architecture. M9 upgraded the runtime-gated edges of M8 to live-verified through real FreeCAD (1.1.3) execution, a real trusted imported STEP artifact, a live mixed assembly, exact collision/clearance measurement, a real discrete kinematic sweep, and durable trusted analysis-execution provenance.

The normative architecture documents (`docs/architecture/*`), `README.md`, and `AGENTS.md` were still written against the M7 baseline and described the connected live FreeCAD / trusted-import / exact-kinematic edges as `RUNTIME_GATED` or `TARGET_NEXT` / `FUTURE`. This reconciliation updates those documents so the current system is described accurately: M8 is the current architectural foundation; M9 live-verified the critical edges.

This record is an **audit/bridge document**, not a competing architecture specification. Normative current architecture remains in `docs/architecture/*`.

---

## 2. Baseline Examined

- Current normative architecture: `MECHCAD_PROJECT_OVERVIEW.md`, `MECHCAD_SYSTEM_CONTRACT.md`, `MECHCAD_ENGINEERING_WORKFLOW.md`, `MECHCAD_RUNTIME_FLOW.md`, `MECHCAD_SUBSYSTEM_CONTRACTS.md`, `MECHCAD_CAPABILITY_MATRIX.md`, `MECHCAD_DOMAIN_EXTENSION_GUIDE.md`, `MECHCAD_DOCUMENTATION_GAPS.md`.
- Acceptance / closure audits: `MECHCAD_M8C_SYSTEM_CLOSURE_AUDIT.md`, `MECHCAD_M9_SYSTEM_ACCEPTANCE.md`.
- Milestone specs: M8B-1, M8B-2, M8C-1, M8C-2, M8C-3, M9-1, M9-2, M9-3, M9-4.
- Root guidance: `AGENTS.md`, `README.md`.
- Current implementation/tests: `src/mechcad_harness/application.py`, `cad_compilation.py`, `imported_component.py`, `assembly_service.py`, `backends/freecad_assembly.py`, `transient_freecad_measurement.py`, `analysis_provenance.py`, `models/evidence.py`, `artifacts/storage.py`, and the corresponding test suites.

Accepted milestone closure markers (confirmed against current bytes):

```text
M8B_PRODUCTION_ORCHESTRATION_COMPLETE
M8C_1_COMPLETE_WITH_PREACCEPTED_SPEC_BOUNDARY
M8C_2_FINAL_CLOSURE_COMPLETE
M8C_3_FINAL_CLOSURE_COMPLETE
M8C_ARCHITECTURALLY_CLOSED_RUNTIME_GATED   (historical M8 closure status)
M9_1_LIVE_FREECAD_BACKEND_VERIFIED
M9_2_LIVE_TRUSTED_IMPORTED_ARTIFACT_VERIFIED
M9_2_FINAL_CLOSURE_COMPLETE
M9_3_LIVE_EXACT_VERTICAL_SLICE_VERIFIED
M9_3_FINAL_CLOSURE_COMPLETE
M9_4_TRUSTED_ANALYSIS_PROVENANCE_VERIFIED
M9_FULLY_CLOSED_LIVE_VERIFIED
```

---

## 3. M8 Current Architectural Contribution

### M8B — Production Orchestration

- **Capability introduced:** a real non-test production composition root, `ProductionApplication.create(...)`, owning the trusted service graph (StateManager, EvidenceStore, OwnershipPolicy, ChangeEngine, RunController, ToolRegistry → ToolBroker, AgentRegistry → injected adapter, ContextBuilder → AgentGateway → AgentToolMediator → ToolBroker).
- **Production boundary introduced:** the application owns trusted identities/permissions; the external agent adapter is injected (required, not default); ordinary agents do not own canonical authority; tool access remains controlled; state/source binding fails closed.
- **Trust/authority semantics:** the production identity (`mechcad-transmission@1.0`, role `transmission_engineer`) is harness-owned; the adapter is execution transport only. Canonical mutation remains exclusively through `ChangeEngine`.
- **Status at M8 closure:** production orchestration complete and connected.
- **Current status after M9:** unchanged; it is the composition foundation the M8C and M9 production paths run on.
- **Authoritative evidence:** `2026-08-21-m8b1-production-orchestration-foundation-design.md`, M8B-2 vertical-slice spec, M8C closure audit §2/§5.

### M8C-1 — Source-Bound DesignSpec Compilation

- **Capability introduced:** `DesignState` → (accepted, source-bound) `MountingPlateDesignSpec` → `CadCompilationService.compile_mounting_plate` → deterministic `CadPartProgram` (`program_hash`, `spec_hash`, `compiler_version = generic-mounting-plate-compiler@1.0`).
- **Production boundary introduced:** compilation validates project/revision/state_hash fail-closed; no engineering decision is made (deterministic transform only).
- **Trust/authority semantics:** `PREACCEPTED_CALLER_CONTRACT_ONLY` — the supplied `MountingPlateDesignSpec` is compiled against the source-bound state; the system does not durably represent that this exact spec was formally accepted as the selected engineering design.
- **Status at M8 closure:** `RUNTIME_GATED` for FreeCAD realization, but the compiler itself was connected/deterministic.
- **Current status after M9:** the generated `CadPartProgram` is live-realized through FreeCAD (M9-1 / M8C-1 live path).
- **Authoritative evidence:** `2026-08-21-m8c1-generic-cad-production-ingress-design.md`, M8C closure audit §2/§4/§8.

### M8C-2 — Trusted Imported CAD + Mixed Assembly

- **Capability introduced:** producer output / persisted artifact → `EngineeringArtifact` → trusted `ArtifactStore` resolution → `ImportedCadComponent` → `CadAssemblyProgram` (generics + imported). Includes `resolve_imported_component`, `store.existing_in_project(...)` → `store.existing(...)`.
- **Production boundary introduced:** artifact bytes persisted, size checked, SHA-256 recomputed, imported component source provenance is artifact-derived (`source_revision`/`source_state_hash` from trusted metadata), arbitrary caller provenance not trusted, workspace/project boundary controlled, ambiguous project-scoped lookup fails closed.
- **Trust/authority semantics:** arbitrary STEP filesystem paths are NOT trusted imported components; only a persisted `ArtifactStore` record yields a trusted `ImportedCadComponent`. Generic mixed-assembly semantics do NOT contain gear-specific meaning merely because a gear was the live fixture.
- **Status at M8 closure:** architecture connected; FreeCAD realization + live imported artifact were `RUNTIME_GATED` (the M8C fixture used synthetic/placeholder STEP).
- **Current status after M9:** live-verified with a real trusted imported STEP artifact from `mechcad-build-spur-gear-cad@1.0` (M9-2).
- **Authoritative evidence:** `2026-08-21-m8c2-imported-component-assembly-bridge-design.md`, M8C closure audit §2/§5, M9-2 / M9-3 acceptance.

### M8C-3 — Production Kinematic Entrypoint

- **Capability introduced:** `ProductionApplication.analyze_assembly_kinematics(...)` → `CadKinematicSweepService` → `TransientAssemblyAnalysisService` → composed measurement provider → `CadKinematicSweepResult`. Includes generic `RevoluteAxis`, `CadRigidTransform`, explicit moving/stationary instance partition, ordered discrete angle samples, deterministic request/result identity, source assembly hash, transformed assembly hashes, `continuous_sweep_verified = False`.
- **Production boundary introduced:** an ordinary analysis caller does NOT pass a trusted exact-measurement callback. The production application owns provider composition (`kinematic_measure`); `analyze_assembly_kinematics(...)` exposes no `exact_measure`/`kinematic_measure` parameter (verified via `inspect.signature`). Tests may inject a deterministic provider at the composition boundary, but that is not the normal production path.
- **Trust/authority semantics:** analysis results are derived evidence; no `DesignState` mutation.
- **Status at M8 closure:** production entrypoint connected; transient exact measurement through the real FreeCAD provider was `RUNTIME_GATED`.
- **Current status after M9:** live-verified with real FreeCAD `common().Volume` / `distToShape()` (M9-3).
- **Authoritative evidence:** `2026-08-22-m8c3-production-kinematic-vertical-slice-design.md`, M8C closure audit §2/§5/§8, M9-3 acceptance.

---

## 4. M8 Closure / Runtime Status

At M8 closure (`M8C_ARCHITECTURALLY_CLOSED_RUNTIME_GATED`):

- **Connected (architecturally present, implemented, wired):** state→DesignSpec→CAD compilation; ArtifactStore→ImportedCadComponent; generated+imported→CadAssemblyProgram; assembly→transient analysis; transient analysis→exact measurement (deterministic provider); ProductionApplication→kinematic sweep; kinematic sweep→deterministic result.
- **Runtime-gated (architecture present, not live-executed in the M8 environment):** `CadAssemblyProgram → FreeCAD realization` (live FCStd/STEP persistence + fresh reload), the live execution of transient measurement and discrete sweep geometry through real FreeCAD, and a genuinely generated trusted imported STEP artifact (the M8C fixture used synthetic/placeholder STEP).

The M8 closure audit (§9) found no boundary violation and noted the architecture docs were internally consistent for the M8 `RUNTIME_GATED` state. That assessment is *historical*: after M9, the runtime-gated edges are live-verified and the normative docs must be updated to reflect current reality, not the historical M8 gating.

---

## 5. M9 Live Upgrades

- **M9-1 — Real FreeCAD backend:** FreeCAD (1.1.3, resolved via `discover_freecad()` + `MECHCAD_FREECADCMD` override, not hardcoded) executes real generic `CadPartProgram` realization; persists FCStd/STEP; fresh-process reload verified; backend/runtime provenance captured.
- **M9-2 — Real trusted imported artifact:** real `mechcad-build-spur-gear-cad@1.0` (py_gearworks/build123d) produces real STEP bytes → `ArtifactStore.publish` → `EngineeringArtifact` → actual-byte SHA-256 re-verification → `ImportedCadComponent`. The gear is a real fixture/proof source only.
- **M9-3 — Live mixed assembly + exact kinematics:** the SAME real mixed assembly path (generated `CadPartProgram` + trusted `ImportedCadComponent`) → `CadAssemblyGenerationService` → `FreeCADAssemblyBackend` → persisted FCStd/STEP → fresh reload → real transient transformed mixed assembly → real `common().Volume` / `distToShape()` → real production discrete kinematic sweep. Imported placement survives reload; canonical object names verified; duplicate temporary import geometry removed; transient per-angle geometry disposable; no public per-angle artifact spam; no canonical state revision per angle. Collision semantics: `common().Volume > 0` → interference; zero volume + zero distance → touching; zero volume + positive distance → positive clearance. Positive clearance is NOT manufacturing approval.
- **M9-4 — Trusted analysis execution provenance:** durable `AnalysisExecutionProvenance` / `Evidence` binds `source_assembly_hash`, `request_hash`, `result_hash`, `sweep_version` to provider identity/version (`freecad-transient-exact` / `mechcad-freecad-transient@1.0`), backend identity/version (`freecad` / `mechcad-freecad@2.1`), library/runtime identity (FreeCAD 1.1.3), and execution mode (`freecadcmd-subprocess`). Distinct from the `deterministic-test-provider` class; the two do not collapse. The ordinary workflow caller cannot spoof trusted provider/runtime provenance.

### M9 System Acceptance

`docs/audit/MECHCAD_M9_SYSTEM_ACCEPTANCE.md` is the authoritative M9 system-level closure record. It proves in one live acceptance environment: real specialized producer executed; real trusted STEP artifact persisted; real mixed FreeCAD assembly generated; FCStd/STEP persisted; fresh reload passed; real transient geometry executed; `common().Volume` executed; `distToShape()` executed; real discrete kinematic sweep completed; trusted durable FreeCAD provenance persisted; evidence hashes bind to the exact live result; full suite passed (689 passed, 25 skipped, 0 failed). Current final marker: **M9_FULLY_CLOSED_LIVE_VERIFIED**.

---

## 6. M8 → M9 Upgrade Matrix

| M8 capability / edge | M8 closure status | M9 milestone that upgraded it | Current status | Authoritative evidence |
|---|---|---|---|---|
| Production orchestration (`ProductionApplication` graph) | connected | (none required) | production-connected | M8B closure |
| DesignSpec compilation (`DesignState` → `CadPartProgram`) | connected (deterministic) | M9-1 live realization | live-verified (generated path) | M9-1 / M9 acceptance §4 |
| Generic `CadPartProgram` → FreeCAD | runtime-gated | M9-1 | live-verified | M9-1 |
| Imported artifact trust (ArtifactStore → `ImportedCadComponent`) | connected (synthetic fixture) | M9-2 (real trusted STEP) | live-verified | M9-2 |
| `ImportedCadComponent` | connected | M9-2 | live-verified | M9-2 |
| Mixed `CadAssemblyProgram` → FreeCAD | runtime-gated | M9-3 | live-verified | M9-3 |
| CadPartProgram → FreeCAD realization | runtime-gated | M9-1 | live-verified | M9-1 |
| Mixed generated/imported assembly realization | runtime-gated | M9-3 | live-verified | M9-3 |
| Persisted FCStd/STEP | runtime-gated | M9-1 / M9-3 | live-verified | M9-1 / M9-3 |
| Fresh reload | runtime-gated | M9-1 / M9-3 | live-verified | M9-3 |
| Transient transformed geometry | connected (deterministic provider) | M9-3 (real FreeCAD) | live-verified | M9-3 |
| `common().Volume` | runtime-gated | M9-3 | live-verified | M9-3 |
| `distToShape()` | runtime-gated | M9-3 | live-verified | M9-3 |
| Discrete production kinematic sweep | connected (deterministic provider) | M9-3 (real FreeCAD) | live-verified | M9-3 |
| Analysis execution provenance | known provenance gap (M8C §7) | M9-4 | trusted provenance verified | M9-4 |
| Whole live chain | M8C runtime-gated | M9 system acceptance | M9_FULLY_CLOSED_LIVE_VERIFIED | M9 acceptance |

---

## 7. Current Production Architecture

```text
DesignState (canonical, source-bound)
  -> MountingPlateDesignSpec (pre-accepted caller contract)   [ ProductionApplication.compile_design_spec ]
  -> CadCompilationService.compile_mounting_plate            -> CadPartProgram

Run/Task -> ToolBroker -> real producer (mechcad-build-spur-gear-cad@1.0)
  -> ArtifactStore.publish -> EngineeringArtifact
  -> resolve_imported_component -> ImportedCadComponent

CadPartProgram + ImportedCadComponent
  -> CadAssemblyProgram
  -> ProductionApplication.build_assembly_with_imported_components
  -> CadAssemblyGenerationService -> FreeCADAssemblyBackend
  -> FCStd / STEP -> ArtifactStore -> fresh reload

ProductionApplication.analyze_assembly_kinematics
  -> CadKinematicSweepService -> TransientAssemblyAnalysisService
  -> FreeCADTransientAssemblyMeasurementProvider.exact_measure
  -> common().Volume / distToShape()
  -> CadKinematicSweepResult
  -> AnalysisExecutionProvenance / Evidence
```

The deterministic test provider is a composition-boundary injection only and is not the normal production execution path.

---

## 8. Current Live Verification State

- Real FreeCAD backend: live-verified (FreeCAD 1.1.3).
- Real trusted imported STEP: live-verified.
- Mixed assembly + fresh reload: live-verified.
- Exact `common().Volume` / `distToShape()`: live-verified (discrete samples).
- Real production discrete kinematic sweep: live-verified.
- Trusted durable analysis execution provenance: live-verified.

---

## 9. Trusted Provenance State

`CadKinematicSweepResult` carries `request_hash`, `source_assembly_hash`, `result_hash`, `sweep_version`. Durable `AnalysisExecutionProvenance` / `Evidence` adds provider identity/version, backend identity/version, library/runtime identity, and execution mode. The evidence id is derived deterministically from `request_hash` + `result_hash`, so it cannot be detached/reattached. `spec_hash`/`compiler_version` remain on `CadCompilationResult` (not folded into assembly identity — `COMPILATION_PROVENANCE_SEPARATE_NOT_TRANSITIVELY_LINKED`).

---

## 10. Remaining Limitations

- `PREACCEPTED_CALLER_CONTRACT_ONLY` — supplied `MountingPlateDesignSpec` is compiled against state binding, but exact spec canonical acceptance is not durably represented as state authority.
- `COMPILATION_PROVENANCE_SEPARATE_NOT_TRANSITIVELY_LINKED` — spec/compiler provenance exists but is not necessarily folded through every downstream semantic identity/evidence chain.
- `run_id` correlation/storage scope only — not trusted engineering semantic identity.
- `continuous_sweep_verified = False` — only ordered discrete configurations are verified; no continuous collision-free-motion proof exists between samples.
- No M10 capability is implemented (continuous collision, multi-axis kinematics, FEA, materials selection, manufacturing approval, tolerance verification, optimization, automatic collision avoidance, automatic mechanism synthesis, automatic component selection).

---

## 11. Stale Claims Corrected

The affected files and corrected statements are enumerated in §13–§14 and in the Normative Docs Updated mapping (§35 of the task). Historical records (`MECHCAD_M8C_SYSTEM_CLOSURE_AUDIT.md`, milestone specs) intentionally retain their `RUNTIME_GATED` wording because that was true at their own closure; the normative docs were updated.

---

## 12. Historical Claims Preserved

- `MECHCAD_M8C_SYSTEM_CLOSURE_AUDIT.md` retains `M8C_ARCHITECTURALLY_CLOSED_RUNTIME_GATED` and the §6/§7 provenance-limitation wording — historically accurate for M8 closure.
- Milestone specs M8B-1/M8B-2/M8C-1/2/3 and M9-1/2/3/4 retain their own closure statuses (`RUNTIME_GATED` where applicable) as historical execution records.
- The M7 domain-reference adapters (M7D) and M7E preliminary concept remain historical domain-reference material; M8/M9 are generic and do not depend on Yagi/gear/antenna semantics.

---

## 13. README changes

Added a "Current Architecture Status" section stating M8 (production orchestration and generic CAD/assembly/analysis architecture established) and M9 (real FreeCAD live path, trusted imported STEP, mixed assembly, fresh reload, exact collision/clearance measurement, discrete kinematic sweep, trusted analysis execution provenance), current system status `M9_FULLY_CLOSED_LIVE_VERIFIED`, the hard limitation `continuous_sweep_verified = False`, and repository-relative links to `docs/architecture/MECHCAD_PROJECT_OVERVIEW.md`, `docs/architecture/MECHCAD_CAPABILITY_MATRIX.md`, `docs/architecture/MECHCAD_RUNTIME_FLOW.md`, `docs/audit/MECHCAD_M9_SYSTEM_ACCEPTANCE.md`, and this reconciliation record.

---

## 14. AGENTS.md changes

Rewrote the stale M0-only description into the accepted M8/M9 baseline with progressive-disclosure reading guidance:
- General architecture: `MECHCAD_PROJECT_OVERVIEW.md`, `MECHCAD_SYSTEM_CONTRACT.md`, `MECHCAD_CAPABILITY_MATRIX.md`.
- Runtime/CAD/analysis: `MECHCAD_RUNTIME_FLOW.md`, `MECHCAD_SUBSYSTEM_CONTRACTS.md`, `MECHCAD_M9_SYSTEM_ACCEPTANCE.md`.
- Historical M8→M9 context: this reconciliation record.
- Preserved precedence/discovery rules. Explicitly stated that historical milestone records are secondary to current normative architecture except when investigating history.

---

## 15. Capability Overclaim Audit

After reconciliation, no normative doc claims: continuous collision detection / continuous collision-free proof / arbitrary continuous swept-volume proof / generic multi-axis joint chains / arbitrary multi-joint mechanisms / prismatic joint support / FEA / stress-strain verification / material selection / manufacturing approval / tolerance-stack verification / optimization / automatic collision avoidance / automatic mechanism synthesis / automatic component selection. `continuous_sweep_verified = False` is explicitly retained. Proposed M10 work is not documented as current capability.

---

## 16. Unresolved Contradictions

**NONE.** The M8/M9 system acceptance records are internally consistent and consistent with the updated normative documentation. The historical `RUNTIME_GATED` wording is preserved only in historical records, not in current-facing normative docs.

---

## 17. M10 Baseline Readiness

**M10_BASELINE_DOCUMENTATION_READY.** The current normative architecture now describes M8 as the architectural foundation and M9 as the live-verified upgrade, with explicit limitations and no M10 capability presented as current.

---

## Appendix A — Required Reconciliation Table (Topic / Old statement / Current verified state / Source of truth / Documentation action)

| Topic | Historical / old statement | Current verified state | Source of truth | Documentation action |
|---|---|---|---|---|
| M8B production orchestration | not represented at M7 baseline | production-connected composition root | M8B closure / M8C audit §2 | added to PROJECT_OVERVIEW, SUBSYSTEM_CONTRACTS, CAPABILITY_MATRIX |
| M8C-1 DesignSpec compilation | M7A generic CAD program (runtime unproven) | connected + live-realized | M8C-1 spec, M9-1/acceptance | RUNTIME_FLOW F, CAPABILITY_MATRIX updated to live-verified |
| M8C-2 imported artifact trust | not represented | live-verified trusted ImportedCadComponent | M9-2 acceptance | SUBSYSTEM_CONTRACTS, CAPABILITY_MATRIX updated |
| M8C-2 mixed assembly architecture | M7A rigid assembly (REQUIRED_CURRENT) | live-verified mixed assembly | M9-3 acceptance | RUNTIME_FLOW F, CAPABILITY_MATRIX updated |
| M8C-3 production kinematic entrypoint | M7C generic single-axis sweep (runtime unproven) | connected + live-verified discrete sweep | M9-3 acceptance | RUNTIME_FLOW M, SUBSYSTEM_CONTRACTS updated |
| FreeCAD runtime | "FreeCAD was future/not integrated" / `RUNTIME_GATED` | live-verified (1.1.3) | M9-1 / M9 acceptance | README, PROJECT_OVERVIEW, CAPABILITY_MATRIX updated |
| Generic CAD realization | `RUNTIME_GATED` | live-verified | M9-1 | RUNTIME_FLOW F, CAPABILITY_MATRIX |
| Imported STEP realization | synthetic fixture only | live-verified real trusted STEP | M9-2 | RUNTIME_FLOW, CAPABILITY_MATRIX |
| Mixed assembly live execution | `RUNTIME_GATED` | live-verified | M9-3 | RUNTIME_FLOW F, CAPABILITY_MATRIX |
| Fresh reload | `RUNTIME_GATED` | live-verified | M9-3 | RUNTIME_FLOW F, CAPABILITY_MATRIX |
| Transient mixed geometry | deterministic provider only | live-verified | M9-3 | RUNTIME_FLOW M, CAPABILITY_MATRIX |
| `common().Volume` | `RUNTIME_GATED` | live-verified | M9-3 | CAPABILITY_MATRIX |
| `distToShape()` | `RUNTIME_GATED` | live-verified | M9-3 | CAPABILITY_MATRIX |
| Discrete kinematic sweep | deterministic provider only | live-verified | M9-3 | CAPABILITY_MATRIX |
| Analysis execution provenance | known provenance gap (M8C §7) | trusted provenance verified | M9-4 | SUBSYSTEM_CONTRACTS, CAPABILITY_MATRIX |
| Provider/test separation | not represented | `freecad-transient-exact` vs `deterministic-test-provider` distinct | M9-4 acceptance §10 | SUBSYSTEM_CONTRACTS |
| Continuous motion verification | `continuous_sweep_verified = False` | unchanged (still False) | M8C §8, M9 §16 | preserved in all docs |
| Authority boundary | `DesignState` canonical | unchanged; M9 did not change mutation authority | M8C §3, M9 §11 | SYSTEM_CONTRACT preserved |

## Appendix B — M8 Capability Table (capability / introduced in / M8 closure / M9 upgrade / current / evidence)

| M8 capability | Introduced in | M8 closure status | M9 upgrade | Current status | Evidence |
|---|---|---|---|---|---|
| Production orchestration | M8B | connected | — | production-connected | M8B closure |
| Source-bound DesignSpec compilation | M8C-1 | connected (deterministic) | M9-1 realization | live-verified | M8C-1, M9-1 |
| Trusted imported artifact | M8C-2 | connected (synthetic) | M9-2 real STEP | live-verified | M8C-2, M9-2 |
| Mixed assembly program | M8C-2 | connected | M9-3 | live-verified | M8C-2, M9-3 |
| Production kinematic entrypoint | M8C-3 | connected | M9-3 | live-verified | M8C-3, M9-3 |
| FreeCAD realization | M8C-2/3 | runtime-gated | M9-1/3 | live-verified | M9 acceptance |
| Exact transient measurement | M8C-3 | runtime-gated | M9-3 | live-verified | M9-3 |
| Discrete sweep result | M8C-3 | connected (deterministic) | M9-3 | live-verified | M9-3 |
| Trusted analysis provenance | M9-4 | n/a (post-M8) | M9-4 | trusted provenance verified | M9-4 |
