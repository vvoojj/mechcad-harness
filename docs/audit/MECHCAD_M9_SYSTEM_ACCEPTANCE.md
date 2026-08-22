# M9 System-Level Live Acceptance

**Date:** 2026-08-22
**Scope:** Final live system acceptance of the complete M9 production chain on a FreeCAD-capable runtime, with the CURRENT M9-4 provenance code in place.
**Method:** Executed the full live production chain end-to-end; ran the M9-1/M9-2/M9-3/M9-4 live integration suites, the focused regression suites, and the complete project test suite against a real freecadcmd.exe (1.1.3) and the real py_gearworks/build123d producer stack. No M10 work was started. No commit/push/stash/reset/clean was performed.
**Runtime environment:** FreeCAD available (discover_freecad().available == True). Previously runtime-gated live edges are now live-verified.

This document supersedes the individual M9-1/M9-2/M9-3/M9-4 milestone reports for overall M9 status, while preserving them as detailed evidence (they recorded the design/code state when those edges were RUNTIME_GATED; this record upgrades the gating to live-verified).

---

## 1. Runtime (M9-1 live backend verified)

| Item | Value |
|---|---|
| FreeCAD executable | C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe (resolved via MECHCAD_FREECADCMD harness override; not hardcoded in production code) |
| Actual FreeCAD version | 1.1.3 (resolved at runtime via discover_freecad() + _freecad_version()) |
| Backend name | freecad |
| Backend adapter version | mechcad-freecad@2.1 (FREECAD_BACKEND_VERSION) |
| Library name | FreeCAD |
| Execution mode | freecadcmd-subprocess |

FreeCADBackend.provenance() resolves library_version = 1.1.3 and library_source to the resolved executable path (diagnostic only; not used as semantic identity). All live M9-1 backend tests pass.

---

## 2. Real Specialized Producer (M9-2 real trusted imported artifact verified)

| Item | Value |
|---|---|
| ToolBroker tool | mechcad-build-spur-gear-cad@1.0 (executed via ToolBroker.execute) |
| Producer tool version | 1.0 |
| Producer libraries | py_gearworks 0.0.18, build123d 0.11.1, numpy 2.3.5, scipy 1.18.0 |
| Real artifact id | ART-<uuid> e.g. ART-da4d706b-7cd3-494b-8955-9f8ef02480cd |
| Real artifact size | 443209 bytes (real STEP) |
| Actual-byte SHA-256 | sha256:ee7dc56408763b727e592ce466fab8a42bbaa50a74045d1fb35c9c940b41d555 (recomputed from bytes and matched against persisted ArtifactStore record) |

The gear STEP was produced by the real py_gearworks/build123d producer, published through ArtifactStore.publish, and resolved via resolve_imported_component into a trusted ImportedCadComponent. No synthetic STEP fixture was used.

---

## 3. Source Binding (exact source/trust binding across the live fixture)

| Item | Value |
|---|---|
| project | PRJ-M9-ACCEPT (acceptance driver) / PRJ-M9-3 (M9-3 canonical fixture) |
| revision | 1 |
| state_hash | sha256:b652f2b07a8625fa444e83935288b4e41f6269604e7d54c63eb4b9f03d98f49b (driver run) |

Generated side validated against canonical StateManager state (compile_design_spec fails-closed on revision/hash mismatch). Imported artifact provenance came from trusted ArtifactStore metadata (source_revision == 1, source_state_hash == state hash), never caller-supplied. Both generated and imported sides are bound to the same source state; the distinction is preserved honestly (generated uses spec_hash/compiler_version; imported carries artifact_hash/source_revision).

---

## 4. Generated CAD (M9-1 / M8C-1 live path)

| Item | Value |
|---|---|
| source_revision | 1 |
| source_state_hash | sha256:b652f2b07a8625fa444e83935288b4e41f6269604e7d54c63eb4b9f03d98f49b |
| spec_hash | sha256:b0d3df6af8e24e774e1a5cdd6892fb3f57972e8a75e22135e09626b9ade1dbaa |
| compiler_version | generic-mounting-plate-compiler@1.0 |
| program_hash | sha256:46c3ffa9a014f8d1b53907b5a2bdcaf48295ecc462a6dc7165faf143d73f0ad0 |

Executed through ProductionApplication.compile_design_spec -> CadCompilationService.compile_mounting_plate -> CadPartProgram. The PREACCEPTED_CALLER_CONTRACT_ONLY boundary was not crossed.

---

## 5. Imported Artifact Trust (M9-2)

| Item | Value |
|---|---|
| artifact id | ART-da4d706b-7cd3-494b-8955-9f8ef02480cd |
| size | 443209 bytes |
| actual-byte SHA-256 | sha256:ee7dc56408763b727e592ce466fab8a42bbaa50a74045d1fb35c9c940b41d555 |
| ImportedCadComponent identity | component_id=gear-1, artifact_id=..., artifact_hash=sha256:ee7dc... |
| artifact-derived source provenance | source_revision=1, source_state_hash=sha256:b652... (from trusted ArtifactStore record, not caller) |

The resolver fail-closes on a forged hash (test_resolver_rejects_forged_hash) and on a missing artifact (store.existing + sha256 recompute + format allow-list).

---

## 6. Mixed Assembly Live Proof (M9-3 / M8C-2)

| Item | Value |
|---|---|
| source assembly hash | sha256:f9076f8521d6a9a9467253e6e10ff6ce228f6083949ed0bc16e0f60bdb4369b9 |
| FCStd artifact id | ASM-m9-accept-fixture-f9076f8521d6a9a9-fcstd |
| FCStd artifact hash | sha256:339a06a00fd1ef3cbf0bda60db33d4ff77958659c587dc4767211e97ba923654 |
| STEP artifact id | ASM-m9-accept-fixture-f9076f8521d6a9a9-step |
| STEP artifact hash | sha256:4eb86ecb11be81fd5d9d8b1051abff28a43d3542d49c198209d184a411e590f1 |
| Fresh reload | verified: separate freecadcmd subprocess reopened the persisted FCStd; placement read back exactly |
| Placement (gear) | [20.0, 0.0, 5.0] (expected) |
| Placement (plate) | [0.0, -60.0, 0.0] (expected) |
| Solid/object verification | FCStd solid_count = 2, STEP solid_count = 2; both plate-inst (generated) and gear-inst (imported) canonical objects present; no duplicate temporary objects |

Real mixed assembly generated through ProductionApplication.build_assembly_with_imported_components -> CadAssemblyGenerationService -> FreeCADAssemblyBackend. Persisted FCStd + STEP via ArtifactStore. Fresh reload proves geometry/placement survive out-of-process.

---

## 7. Exact Live Measurements (M9-3 / M8C-3)

Real transient FreeCAD geometry was created per sampled configuration and measured with common().Volume and distToShape(). Executed in real FreeCAD (provider = FreeCADTransientAssemblyMeasurementProvider.exact_measure, not a deterministic test provider).

| angle (deg) | interference volume (mm3) | distance (mm) | classification |
|---:|---:|---:|---|
| 0.0 | 0.000000 | 6.000000 | positive_clearance |
| 90.0 | 0.000000 | 26.000000 | positive_clearance |
| 180.0 | 0.000000 | 14.922814 | positive_clearance |
| 270.0 | 545.434337 | 0.000000 | interference |

Outcomes reported as-is (no forced clearance/touching/interference pattern). The moving gear orbits the fixture frame; world positions change so measured distances differ across samples, and at 270 deg the gear interferes with the plate (real common().Volume > 0, distToShape() = 0).

---

## 8. Kinematic Result (M9-3)

| Item | Value |
|---|---|
| source assembly hash | sha256:f9076f8521d6a9a9467253e6e10ff6ce228f6083949ed0bc16e0f60bdb4369b9 |
| request hash | sha256:8d0bfaa760d54d736b0addb023e0adc8408038b8a99c9686d95d66b0c7bda4fa |
| sweep version | rigid-body-collision-sweep@1.0 (RIGID_BODY_COLLISION_SWEEP_VERSION) |
| transformed assembly hashes (per sample) | distinct per angle; transformed[0] != transformed[1] (motion changed transforms) |
| result hash | sha256:87b3d5083ef62d2df7346aeef173fc72e1387aa05da754e5ff815df29cc6ae4a |
| continuous_sweep_verified | False |

Re-running the same live sweep twice yields identical measurements within floating-point tolerance. No public per-angle FCStd/STEP artifacts were created during the sweep (transient workspace is disposable).

---

## 9. Trusted Analysis Execution Provenance (M9-4)

Durable AnalysisExecutionProvenance / Evidence retrieved for the exact result:

| Item | Value |
|---|---|
| provider_name | freecad-transient-exact |
| provider_version | mechcad-freecad-transient@1.0 |
| backend_name | freecad |
| backend_adapter_version | mechcad-freecad@2.1 |
| library_name | FreeCAD |
| library_version (actual resolved live) | 1.1.3 (not hardcoded) |
| execution_mode | freecadcmd-subprocess |

Binding to the exact live result (asserted):

- evidence.provenance.request_hash == live_result.request_hash -> True
- evidence.provenance.result_hash == live_result.result_hash -> True
- evidence.provenance.source_assembly_hash == live_result.source_assembly_hash -> True
- evidence.provenance.sweep_version == live_result.sweep_version -> True

The evidence id is derived deterministically from request_hash + result_hash, so the provenance record cannot be detached/reattached to a different result. evidence.input_hash == request_hash, evidence.output_hash == result_hash, evidence.producer_result_id == result_hash.

---

## 10. Live / Test Provider Separation (M9-4)

A deterministic injected provider composition (kinematic_measure = lambda ...) yields separate, non-collapsing identity:

| Item | Deterministic | Live FreeCAD |
|---|---|---|
| provider_name | deterministic-test-provider | freecad-transient-exact |
| provider_version | deterministic-test@1.0 | mechcad-freecad-transient@1.0 |
| execution_mode | deterministic-injected | freecadcmd-subprocess |
| backend_provenance | None | freecad / mechcad-freecad@2.1 / FreeCAD 1.1.3 |

The two execution classes do not collapse into the same provenance; a deterministic result can never be mistaken for a FreeCAD-exact result.

---

## 11. Authority / Mutation Check

- No DesignState mutation during the kinematic sweep (reload hash unchanged after analysis).
- No ChangeProposal / ChangeSet created in the workspace.
- No geometry/assembly/selection/engineering authority escalation: CAD, analysis, and provenance outputs remain derived evidence.
- No canonical component selection, no hidden revision, no ChangeSet bypass.

---

## 12. Artifact / Transient Discipline

- Transient workspace is a disposable tempfile.TemporaryDirectory.
- No per-angle public FCStd/STEP artifacts created during the sweep (verified by comparing projects/*/runs/*/artifacts/*/metadata.json inventory before/after).
- Source assembly hash (assembly_hash(program)) differs from transformed hashes where motion changes geometry.
- Imported artifact is resolved from the persistent ArtifactStore (trusted, byte-checked), not re-fabricated in the transient workspace.

---

## 13. Production Bugs Found

One defect found and fixed (narrow fix, fix-policy 23 - stale test assumption):

- Symptom: The three live M9-4 provenance tests failed at runtime with FreeCADExecutionError: imported artifact not found in workspace (then, after that, ToolPersistenceError: tool record already exists), on a real FreeCAD host.
- Root cause: The live M9-4 tests were authored while M9-4 was RUNTIME_GATED. They built a synthetic ImportedCadComponent (artifact_id='ART-m9-4-body', sha256:aaa...) that was never persisted in the ArtifactStore. The transient measurement provider correctly fail-closes when the imported artifact is not genuinely present (the intended M9-2 trust behavior, transient_freecad_measurement.py:116). Secondarily, the test dependencies.yaml did not declare the artifact.gear dependency node, so gear evidence materialization raised unknown dependency node: artifact.gear.
- Fix: Updated the three live M9-4 tests to produce a real trusted STEP artifact via ToolBroker.execute(mechcad-build-spur-gear-cad@1.0) and resolve it through the production ArtifactStore path (mirroring M9-3), and declared artifact.gear in the dependency config. No production code change was required - the production path was already correct; only the test stale assumption was corrected.
- Regression: All M9-4 tests now pass (10 passed), and the full suite remains green.

No production-code defects were found. Live FreeCAD execution, persistence, reload, transient measurement, and durable provenance all behaved as specified.

---

## 14. Tests

M9 live (integration):

- M9-1 live backend: 7 passed
- M9-2 real imported artifact: 8 passed
- M9-3 live vertical slice: 1 passed
- M9-4 provenance (incl. 3 live + 7 deterministic): 10 passed
- M9 live/integration total: 25 passed (0 skipped, 0 failed)

Provenance (focused):

- test_m9_4_trusted_analysis_backend_provenance.py: 10 passed (3 live FreeCAD + 7 deterministic)

Focused regressions (representative):

- M8C-1 compilation, M8C-2 imported/mixed assembly, M8C-3 production kinematic, transient FreeCAD measurement, ArtifactStore integrity/project-resolution, Evidence/EvidenceStore - all green within the full suite.

Full project suite:

    python -m pytest tests/   ->   689 passed, 25 skipped, 0 failed   (505.35s)
    python -m compileall src/mechcad_harness -q   ->   exit 0
    git diff --check   ->   exit 0 (only pre-existing CRLF whitespace warnings)

The 25 skips are pre-existing skipped unit/integration cases unrelated to the live FreeCAD path (e.g., optional feature gates), not gated-live tests - the live FreeCAD tests executed and passed.

---

## 15. Files Changed

Only test files were changed (narrow fix). No production source was modified for this acceptance run.

- tests/integration/test_m9_4_trusted_analysis_backend_provenance.py - live M9-4 tests now produce and resolve a real trusted imported artifact through the production path (mirrors M9-3); declares artifact.gear dependency node; adds GEAR_AVAILABLE gate.

Pre-existing uncommitted changes in the working tree (from the prior M9-1..M9-4 milestones, already present at session start) remain as-is and were not introduced by this acceptance run:

- src/mechcad_harness/application.py, artifacts/storage.py, backends/freecad_assembly.py, models/evidence.py, transient_freecad_measurement.py, analysis_provenance.py (new)
- tests/integration/test_imported_assembly_bridge.py, test_m8c3_production_kinematic_vertical_slice.py, test_backends.py, test_transient_freecad_measurement.py
- new M9-1/M9-2/M9-3/M9-4 integration test files and spec docs

No commit/push/stash/reset/clean was performed.

---

## 16. Remaining Known Limitations (AFTER M9)

- PREACCEPTED_CALLER_CONTRACT_ONLY - MountingPlateDesignSpec is accepted by the caller; no persisted trusted DesignSpec-acceptance record is claimed.
- COMPILATION_PROVENANCE_SEPARATE_NOT_TRANSITIVELY_LINKED - spec_hash/compiler_version remain on CadCompilationResult; not folded into assembly identity / assembly_hash.
- run_id correlation/storage scope only - not part of any kinematic or assembly semantic identity.
- continuous_sweep_verified = False - discrete sampling only; no continuous collision-free motion is claimed.
- Live FreeCAD execution is no longer a remaining limitation (this acceptance passes). Live runtime identity is resolved at execution time and recorded in provenance.

---

## 17. M9 Closure Decision

M9_FULLY_CLOSED_LIVE_VERIFIED

All acceptance gates from section 26 were met in the current environment:

- real specialized producer executed (mechcad-build-spur-gear-cad@1.0, py_gearworks/build123d);
- real trusted STEP artifact persisted and byte-verified;
- real mixed FreeCAD assembly generated;
- persisted assembly fresh-reloaded in a new subprocess;
- real transient FreeCAD geometry executed;
- real common().Volume executed;
- real distToShape() executed;
- real production discrete kinematic sweep completed;
- trusted durable provenance records the actual FreeCAD provider/backend/runtime (freecad-transient-exact / mechcad-freecad@2.1 / FreeCAD 1.1.3 / freecadcmd-subprocess);
- provenance hashes match the exact live result hashes;
- full project suite is green (689 passed, 25 skipped, 0 failed).

---

## 18. Next Major Milestone Recommendation

Recommended next milestone: M10 - Continuous / Multi-Axis Kinematic Clearance Proof (or formal collision-free motion envelope).

Rationale: The single highest-value remaining capability gap is that continuous_sweep_verified = False. M9 closes the discrete exact-measurement + durable-provenance chain on live FreeCAD, but it only samples discrete angles. The natural next step is proving (or bounding) collision-free motion across continuous angle ranges / multiple revolute/prismatic axes, with the same trusted FreeCAD exact-measurement and durable provenance foundation now live-verified. This is recommended over FEA, materials, manufacturing, or mechanism synthesis, which remain later-stage Stage-C concerns and are not needed to make the current production kinematic chain authoritative.
