# MechCAD Capability Matrix

Maturity values are normative expectations, not audit verdicts. Definitions are authoritative in `MECHCAD_SYSTEM_CONTRACT.md`: `FOUNDATION` and `REQUIRED_CURRENT` are both mandatory baseline conformance scope; selected `TARGET_NEXT` capabilities enter connected-readiness audit; `FUTURE` is documentary only.

| Capability | Subsystem | Expected owner | Canonical input | Output | Expected tool/library | Verification requirement | Maturity | Normative source |
|---|---|---|---|---|---|---|---|---|
| canonical DesignState | state | state authority | requirements/domain authority | typed state | Pydantic | schema and authority separation | FOUNDATION | M0/M1 |
| immutable revision/hash | StateManager | state authority | DesignState | snapshot/hash/current pointer | SHA-256/filesystem | canonical serialization, reload, tamper, no overwrite | REQUIRED_CURRENT | M1/project description |
| ChangeProposal | changes | domain owner | bounded result/decision | proposal | none | source binding and typed operations | FOUNDATION | M2 |
| ChangeSet/ChangeEngine | changes | harness authority | accepted proposal | new revision/receipt | StateManager | stale, ownership, atomic validation | REQUIRED_CURRENT | M2 |
| ownership enforcement | changes | policy owner | path/identity | allow/reject | ownership policy | unowned/unrelated fail closed | REQUIRED_CURRENT | M2 |
| dependency graph/invalidation | dependency | harness | changed paths | invalidated nodes/record | graph | deterministic transitive impact | REQUIRED_CURRENT | M3 |
| Evidence freshness | dependency/evidence | harness | evidence plus revision history | CURRENT/STALE/UNKNOWN | EvidenceStore | exact binding and complete history | REQUIRED_CURRENT | M3 |
| RunController | runs | harness | state-bound plan/tasks | transitions/results | RunStore | resume, convergence, exact binding | REQUIRED_CURRENT | M4 |
| manifest/replay | runs | harness | project/revision/hash | immutable manifest/events | filesystem | immutable identity and recovery | FOUNDATION | M4 |
| ToolRegistry | tools | harness | registration | exact lookup | registered handlers | duplicate/version checks | FOUNDATION | M5 |
| ToolBroker | tools | harness | typed call/context | ToolCall/ToolResult | registered handler | permission, binding, version, persistence | REQUIRED_CURRENT | M5 |
| ToolCall/ToolResult | tools | harness | broker invocation | immutable records | ToolStore | hashes and source provenance | FOUNDATION | M5 |
| Evidence materialization | tools/evidence | harness | eligible ToolResult | Evidence | ToolEvidenceMaterializer | deterministic ID, binding, freshness | FOUNDATION | M5/M6B |
| AgentGateway | agents | harness | AgentTask/state/evidence IDs | AgentResult | adapter/schema | context hash, stale and response checks | FOUNDATION | M6A |
| FakeAgentAdapter | agents | test harness | invocation | deterministic response | none | no external side effects | FOUNDATION | M6A |
| OpenCodeAgentAdapter transport | agents | harness | bound invocation | validated response | OpenCode/Luna | strict transport/schema and live path | REQUIRED_CURRENT | M6A/M6B/project description |
| structured response validation | agents | harness | native schema or one JSON document | typed authored payload | Pydantic | no regex, repair, or text fallback | REQUIRED_CURRENT | M6B-1 validated text |
| mechcad-transmission contract | agents/transmission | transmission owner | selected authority/current Evidence | findings/issues/requests/proposals | OpenCode adapter | bounded permissions and output | REQUIRED_CURRENT | M6B-1 |
| semantic transmission tool mediation | agents/tools | harness | `transmission.torque` request | mediated ToolResult | torque tool | capability policy plus exact permission | REQUIRED_CURRENT | M6B-2A |
| torque Evidence round trip | agents/tools/evidence | harness | invocation A/tool result | current Evidence/invocation B | torque handler | one tool, two invocations, freshness | FOUNDATION | M6B/project description; M6B-2B design caveat |
| ConstraintRequest discovery | agents | transmission owner/harness | authored typed drafts | observations/requests | structured response | four supported keys and explicit schema | FOUNDATION | M6B-3/project description |
| ConstraintRequest materialization | agents | harness | typed draft and binding | deterministic record | request store | identity, idempotency, persistence/recovery | FOUNDATION | M6B-3/project description |
| constraint satisfaction | agents/state | harness | supported key and state | suppression/proof | exact anchor rules | no fuzzy/LLM matching | FOUNDATION | M6B-3/project description |
| constraint resolution loop | agents/changes | external authority + harness | trusted answer/request | proposal, ChangeSet, revision, invalidation | ChangeEngine | ownership, replay, no direct mutation | REQUIRED_CURRENT | M6B-4/project description |
| general transmission synthesis | transmission | transmission owner | speed/torque/duty/envelope | canonical design proposal | tools/providers | deterministic candidate evaluation | TARGET_NEXT | universal roadmap |
| py_gearworks calculation | gear adapter/tools | transmission owner | spur gear/pair inputs | normalized gear result | py_gearworks | runtime version, oracle/cross-check | FOUNDATION | M5.5B |
| specialized gear CAD | gear CAD | transmission owner | typed gear CAD input | solid/STEP/STL | py_gearworks/build123d | shape/export/artifact checks | FOUNDATION | M5.5B-2 |
| material lookup/mass | materials | material owner | material query/volume | properties/mass | bd_materials | provenance, authority status, units | FOUNDATION | M5.5C |
| material selection | proposal | material owner | evaluated candidates | canonical selection | provider/evaluator | explicit authority comparison | TARGET_NEXT | project description roadmap |
| section geometry/warping | section tools | structural owner | typed section geometry | normalized properties | sectionproperties/NumPy/SciPy | analytic oracle/convergence | FOUNDATION | M5.5C |
| preliminary section integration | section engineering | structural owner | persisted material/section results | mass/stiffness ranges | native arithmetic | source hashes/units/authority preservation | FOUNDATION | M5.5C-3A |
| CadPartProgram/CAD compiler | CAD | domain owner | accepted DesignSpec | generic part program | generic operations | deterministic program hash; live-verified FreeCAD realization (M9-1) | REQUIRED_CURRENT | M8C-1/M9-1 |
| CadAssemblyProgram | assembly | domain owner | parts/transforms + imported components | rigid assembly program | FreeCAD assembly backend | ordering, identity, transform integrity; live-verified mixed assembly (M9-3) | REQUIRED_CURRENT | M8C-2/M9-3 |
| FreeCAD part/assembly realization | CAD backend | CAD service | part/assembly program | verified FCStd/STEP | FreeCAD | fresh reload, shape, solid, placements; live-verified (M9-1/3) | REQUIRED_CURRENT | M8C-2/M9-1/M9-3 |
| ArtifactStore/durable CAD | artifacts | CAD/provider service | verified bytes/provenance | immutable artifact | filesystem | SHA-256, conflict/no overwrite; trusted imported STEP live-verified (M9-2) | FOUNDATION | M5.5/M8C-2/M9-2 |
| exact collision/interference/clearance | analysis | verification owner | verified assembly pairs | exact classifications | FreeCAD | common volume and exact distance; live-verified (M9-3) | REQUIRED_CURRENT | M8C-3/M9-3 |
| transient assembly analysis | transient service | verification owner | source assembly/transform | temporary measurement result | FreeCAD | temporary workspace/no mutation; live-verified (M9-3) | REQUIRED_CURRENT | M8C-3/M9-3 |
| generic single-axis sweep | kinematic service | kinematics owner | axis/groups/angles | ordered aggregate | transient provider | hashes/order/discrete classification; live-verified (M9-3) | REQUIRED_CURRENT | M8C-3/M9-3 |
| generic multi-joint forward kinematics | kinematic service | kinematics owner | kinematic model (rooted tree) + joint configuration | instance world transforms + transformed CadAssemblyProgram + identity hashes | deterministic core (no FreeCAD) | unique joint IDs; parent/child existence; single articulated parent; no cycles; reachability; deterministic BFS; config/model/transformed-assembly hashes | REQUIRED_CURRENT | M10-2 |
| ProductionApplication orchestration | production | harness | workspace/project/injected adapter | composed trusted service graph | internal services | graph ownership, identity, fail-closed composition | REQUIRED_CURRENT | M8B |
| source-bound DesignSpec compilation | CAD | domain owner | source-bound MountingPlateDesignSpec | CadPartProgram + result hashes | CadCompilationService | fail-closed revision/state-hash; deterministic program/spec hash | REQUIRED_CURRENT | M8C-1 |
| trusted imported CadComponent | artifacts/assembly | CAD/provider service | persisted EngineeringArtifact | ImportedCadComponent | ArtifactStore/resolve_imported_component | store.existing + sha256 recompute + format allow-list; live-verified real STEP (M9-2) | REQUIRED_CURRENT | M8C-2/M9-2 |
| trusted analysis execution provenance | analysis/evidence | verification owner | sweep result + provider/backend identity | AnalysisExecutionProvenance / Evidence | EvidenceStore | evidence id derived from request+result hash; provider/backend/runtime bound; live-verified (M9-4) | REQUIRED_CURRENT | M9-4 |
| durable structural Evidence | structural/evidence | structural owner | trusted M11-4 execution/result/verification/analytical validation | immutable structural Evidence | EvidenceStore / ArtifactStore | exact artifact/result/criterion/material/analytical/provenance binding; fresh reload/currentness; PASS/FAIL/NOT_EVALUABLE | REQUIRED_CURRENT (bounded M11-5 scope) | M11-5 |
| structural repeatability | structural/evidence | structural owner | predeclared policy + two verified structural Evidence records | repeatability result | StructuralRepeatabilityService | policy hashed before runs; declared semantic summaries only; raw bytes and mesh numbering ignored | REQUIRED_CURRENT (bounded M11-5 scope) | M11-5 |
| structural mesh convergence | structural/evidence | structural owner | predeclared ordered study + at least three verified level Evidence records | convergence-study Evidence | StructuralMeshConvergenceService | supported free-end displacement-magnitude metric; ordered IDs/hashes; no global convergence claim | REQUIRED_CURRENT (bounded M11-5 scope) | M11-5 |
| domain extension framework | domain layer | domain owner | authority/spec/ownership | proposals/adapters | generic core | boundary and ownership review | FOUNDATION | universal contract |
| reference domain adapter proof | domain layer | domain owner | domain layout/reference | generic service request/result | generic CAD/kinematics | no generic-layer leakage | FOUNDATION | M7B/M7D reference evidence |
| connected rotary-bracket workflow | integration | orchestrator/domain owners | universal requirements | verified system result | selected current foundations | concrete end-to-end runtime path | TARGET_NEXT | project description Phase E |
| multi-axis kinematic chain | kinematics | kinematics owner | parent/joints/frames | chain result | deterministic core (M10-2) or future backend | frame/joint composition; M10-2 delivers discrete forward kinematics only | REQUIRED_CURRENT | M10-2 (discrete FK); project description Phase F (continuous/trajectory future) |
| structural analysis | structural | structural owner | source-bound single-body linear-static definition/request | typed displacement/stress/reaction result and bounded criterion outcomes | FreeCAD + Gmsh + CalculiX | exact source/artifact/runtime provenance; trusted FRD/DAT interpretation; fixed cantilever analytical checks | REQUIRED_CURRENT (bounded M11-3/M11-4 scope) | M11-2/M11-3/M11-4 |
| FEA | structural backend | structural owner | source-bound single-body mesh/material/load execution | trusted raw execution manifest plus interpreted FRD/DAT result | Gmsh C3D10 + CalculiX 2.22 | byte-verified artifacts, solver/case provenance, parser integrity, analytical validation; bounded declared displacement-metric convergence only; no global safety claim | REQUIRED_CURRENT (bounded M11-3/M11-4/M11-5 scope) | M11-3/M11-4/M11-5 |
| dynamics/simulation | dynamics | kinematics owner | mechanism/trajectory | dynamic result | MuJoCo if accepted | solver/version/binding | FUTURE | project description |
| manufacturing output | manufacturing | manufacturing owner | verified design | manufacturing package | future tools | tolerances/BOM/review | FUTURE | project description |

## M6B Traceability

The project description supplies later completion/maturity evidence where no dedicated Superpowers specification or plan exists. That evidence defines the normative baseline but does not replace implementation audit.

| M6B milestone | Spec | Plan | Accepted completion evidence | Primary capability | Current normative maturity | Reason |
|---|---|---|---|---|---|---|
| M6B-1 transmission reasoning | `2026-08-19-mechcad-m6b1-transmission-reasoning-agent-design.md` | matching transmission plan | project description sections 13 and 18 | bounded real transmission agent | REQUIRED_CURRENT | Accepted first engineering-agent contract; no direct mutation. |
| M6B-1 validated structured output | `2026-08-19-m6b1-validated-json-text-design.md` | matching validated-text plan and Task 1 report | project description sections 12 and 18 | strict native/validated JSON transport | REQUIRED_CURRENT | Current accepted transport behavior is fail-closed. |
| M6B-2A semantic tool mediation | `2026-08-19-mechcad-m6b2a-tool-mediation-design.md` | no dedicated plan found | M6B-2B explicitly calls M6B-2A accepted baseline; project description section 18 | semantic torque request -> exact tool | REQUIRED_CURRENT | Later accepted document supersedes ambiguity in plan status. |
| M6B-2B first tool/Evidence round trip | `2026-08-19-mechcad-m6b2b-first-tool-roundtrip-design.md` | no dedicated plan found | design marked closed but design-only; project description sections 13 and 18 record the foundation established | ToolResult -> Evidence -> Invocation B | FOUNDATION | Contract is part of baseline; audit must resolve implementation/connection versus the design-only source caveat. |
| M6B-3 constraint discovery | no dedicated Superpowers spec found | no dedicated plan found | project description section 17 records established/implemented capabilities | typed discovery, persistence, satisfaction suppression | FOUNDATION | Accepted current project baseline, with independent audit required. |
| M6B-4 constraint resolution | no dedicated Superpowers spec found | no dedicated plan found | project description section 17 says implemented and accepted | trusted answer -> proposal/ChangeSet/revision/invalidation | REQUIRED_CURRENT | Supersedes the earlier “future/unfinished” status. |

## M7 Traceability

| Milestone | Spec / plan evidence | Accepted completion evidence | Architectural capability | Generic vs domain | Normative treatment |
|---|---|---|---|---|---|
| M7A | no single dedicated spec/plan found | project description sections 18 and 20 record complete foundation | generic part programs, rigid assemblies, FreeCAD realization, exact geometry | Generic | REQUIRED_CURRENT |
| M7B | No umbrella or sub-milestone M7B spec/plan found. Exact filename searches for `docs/superpowers/{specs,plans}/**/*m7b*.md` returned none; content search found only an M7B regression reference in `2026-08-20-m7c1-transient-freecad-measurement.md`. | project description sections 18 and 26: done for current reference scope, unresolved physical/structural details | first substantial domain authority/synthesis/CAD exercise | Domain reference | FOUNDATION |
| M7C | `2026-08-20-m7c1-transient-freecad-measurement.md`; plan checklist remains open | project description section 18 records complete; explicit closure evidence exists in history | generic transient exact measurement and discrete single-axis sweep | Generic | REQUIRED_CURRENT |
| M7D-1 | M7D-1 spec and plan | project description section 18 records complete domain reference | EL reference over generic `RevoluteAxis` | Domain reference | FOUNDATION |
| M7D-2 | M7D-2 spec and plan | project description section 18 records complete domain integration proof | thin domain adapter over generic M7C/FreeCAD transient path | Domain reference | FOUNDATION |
| M7E-2 | preliminary concept spec and plan | `PRELIMINARY_CONCEPT_ONLY`, `NOT_VERIFIED`, `NOT_READY` | exploratory domain concept | Domain reference | Documentary reference only; no capability maturity or audit gate |

Source-file or artifact existence does not by itself establish any audit verdict.

## M8 / M9 / M10 Traceability

| Milestone | Spec / plan evidence | Accepted completion evidence | Architectural capability | Generic vs domain | Normative treatment |
|---|---|---|---|---|---|
| M8B (production orchestration) | `2026-08-21-m8b1-production-orchestration-foundation-design.md`, M8B-2 vertical-slice spec | M8B closure (`M8B_PRODUCTION_ORCHESTRATION_COMPLETE`); M8C closure audit §2/§5 | `ProductionApplication` composition root; trusted service graph | Generic | REQUIRED_CURRENT (production-connected) |
| M8C-1 (DesignSpec → CadPartProgram) | `2026-08-21-m8c1-generic-cad-production-ingress-design.md` | `M8C_1_COMPLETE_WITH_PREACCEPTED_SPEC_BOUNDARY`; M8C closure audit §2/§4 | source-bound `MountingPlateDesignSpec` → `CadCompilationService` → `CadPartProgram` | Generic | REQUIRED_CURRENT |
| M8C-2 (trusted imported + mixed assembly) | `2026-08-21-m8c2-imported-component-assembly-bridge-design.md` | `M8C_2_FINAL_CLOSURE_COMPLETE`; M8C closure audit §2/§5 | `ArtifactStore` → `ImportedCadComponent` → `CadAssemblyProgram` | Generic | REQUIRED_CURRENT |
| M8C-3 (production kinematic entrypoint) | `2026-08-22-m8c3-production-kinematic-vertical-slice-design.md` | `M8C_3_FINAL_CLOSURE_COMPLETE`; M8C closure audit §2/§5/§8 | `ProductionApplication.analyze_assembly_kinematics` → `CadKinematicSweepService` → `TransientAssemblyAnalysisService` → `CadKinematicSweepResult` | Generic | REQUIRED_CURRENT |
| M8C closure | `MECHCAD_M8C_SYSTEM_CLOSURE_AUDIT.md` | `M8C_ARCHITECTURALLY_CLOSED_RUNTIME_GATED` (historical) | all M8C edges implemented/connected; live FreeCAD gated | Generic | Historical closure status |
| M9-1 (live FreeCAD backend) | `2026-08-22-m9-1-freecad-runtime-live-verification.md` | `M9_1_LIVE_FREECAD_BACKEND_VERIFIED` | real FreeCAD 1.1.3 realizes generic `CadPartProgram`; FCStd/STEP; fresh reload | Generic | REQUIRED_CURRENT (live-verified) |
| M9-2 (real trusted imported artifact) | `2026-08-22-m9-2-real-trusted-imported-artifact-production.md` | `M9_2_LIVE_TRUSTED_IMPORTED_ARTIFACT_VERIFIED`, `M9_2_FINAL_CLOSURE_COMPLETE` | real `mechcad-build-spur-gear-cad@1.0` STEP → `ArtifactStore` → `ImportedCadComponent` | Generic (gear is fixture only) | REQUIRED_CURRENT (live-verified) |
| M9-3 (live mixed assembly + exact kinematics) | `2026-08-22-m9-3-live-mixed-assembly-exact-kinematic-proof.md` | `M9_3_LIVE_EXACT_VERTICAL_SLICE_VERIFIED`, `M9_3_FINAL_CLOSURE_COMPLETE` | live mixed FreeCAD assembly; real `common().Volume` / `distToShape()`; real discrete sweep | Generic | REQUIRED_CURRENT (live-verified) |
| M9-4 (trusted analysis provenance) | `2026-08-22-m9-4-trusted-analysis-backend-provenance.md` | `M9_4_TRUSTED_ANALYSIS_PROVENANCE_VERIFIED` | durable `AnalysisExecutionProvenance` / `Evidence` bound to live result | Generic | REQUIRED_CURRENT (live-verified) |
| M9 system acceptance | `MECHCAD_M9_SYSTEM_ACCEPTANCE.md` | `M9_FULLY_CLOSED_LIVE_VERIFIED` | whole live chain verified; full suite green | Generic | Current final acceptance marker |
| M10-1 (continuous single-axis clearance proof) | `2026-08-22-m10-1-continuous-single-axis-collision-proof.md` | `M10_1_CONTINUOUS_SINGLE_AXIS_CLEARANCE_PROOF_VERIFIED` | conservative bisection proof with chord-displacement bound; `ContinuousSingleAxisProofStatus` (VERIFIED_CLEAR / COLLISION_WITNESS / NOT_PROVEN) | Generic (single-axis only) | REQUIRED_CURRENT (unit-verified) |
| M10-2 (generic multi-joint kinematic model) | `2026-08-22-m10-2-generic-multi-joint-kinematic-model.md` | `M10_2_GENERIC_MULTI_JOINT_KINEMATICS_VERIFIED` | deterministic forward kinematics over a rooted acyclic tree of revolute joints; config/model/transformed-assembly identity hashes; fail-closed topology; `ProductionApplication.evaluate_multi_joint_configuration`; core FK has no FreeCAD dependency | Generic (discrete FK only) | REQUIRED_CURRENT (unit-verified) |
| M10-3 (exact discrete multi-joint collision sweep) | `2026-08-22-m10-3-multi-joint-exact-discrete-collision-sweep.md` | `M10_3_MULTI_JOINT_EXACT_DISCRETE_COLLISION_VERIFIED` | ordered multi-joint configurations evaluated through transformed assemblies; real FreeCAD `common().Volume` / `distToShape()` pair measurement; deterministic request/result identities; trusted provider/backend/runtime provenance; atomic Evidence persistence | Generic (discrete collision evaluation only) | REQUIRED_CURRENT (live-verified) |
| M10-4 (continuous multi-joint path clearance proof) | `2026-08-22-m10-4-continuous-multi-joint-path-clearance-proof.md` | `M10_4_CONTINUOUS_MULTI_JOINT_PATH_CLEARANCE_PROOF_VERIFIED` | explicit typed ordered path; trusted local geometry extent boundary; pure topology-derived invariant reach bounds; hierarchical telescoping and pair-relative motion certificates; real FreeCAD exact waypoint/midpoint measurement; `VERIFIED_CLEAR` / `COLLISION_WITNESS` / `NOT_PROVEN` | Generic (explicit path only; no configuration-space region claim) | REQUIRED_CURRENT (live-verified) |
| M10-5 system acceptance | `MECHCAD_M10_SYSTEM_ACCEPTANCE.md` | `M10_FULLY_CLOSED_LIVE_VERIFIED` | coherent M10-1 through M10-4 production chain; shared FK/discrete/continuous configuration equality; durable M10-4 typed-result reload; trusted provenance; source immutability; M9 and full-suite regression safety | Generic motion-system acceptance | REQUIRED_CURRENT (live-verified) |

`continuous_sweep_verified = False` remains explicit for ordinary discrete sweeps
(M8C-3 / M9). M10-1 adds a separate continuous proof entrypoint
(`prove_continuous_single_axis_clearance`) that does not modify the discrete
sweep result. M10-2 adds discrete multi-joint forward kinematics and M10-3 adds
exact discrete multi-joint collision evaluation. M10-4 adds explicit-path
continuous proof; whole configuration-space proof, FEA, and manufacturing proof
remain future capability.

## M11 Traceability

| Milestone | Accepted completion evidence | Current bounded capability | Normative treatment |
|---|---|---|---|
| M11-2 | `M11_2_STRUCTURAL_AUTHORITY_MODEL_VERIFIED` | Typed source-bound single-body linear-static definitions and requests with semantic regions, material authority, loads, supports, criteria, mesh/output settings, and deterministic identities; no solving or result acceptance. | REQUIRED_CURRENT |
| M11-3 | `M11_3_STRUCTURAL_MESH_SOLVER_FOUNDATION_VERIFIED` | Trusted FreeCAD source geometry and semantic-region realization, Gmsh C3D10 mesh, deterministic CalculiX deck lowering, per-case solver execution, shared-mesh multi-case manifests, and raw artifact provenance. | REQUIRED_CURRENT (bounded) |
| M11-4 | `M11_4_REAL_FEA_RESULT_ANALYTICAL_VALIDATION_VERIFIED` | Trusted FRD/DAT/LOG interpretation, typed PASS/FAIL/NOT_EVALUABLE criteria, and a separate production analytical-validation API for a predeclared fixed rectangular cantilever policy. | REQUIRED_CURRENT (bounded) |
| M11-5 | `M11_5_DURABLE_STRUCTURAL_EVIDENCE_VERIFIED` | Durable source-bound structural Evidence through the existing EvidenceStore; fresh historical verification/currentness; trusted PASS/FAIL/NOT_EVALUABLE outcomes; bounded repeatability; and explicitly declared ordered displacement-magnitude mesh-convergence studies. | REQUIRED_CURRENT (bounded) |

The M11 rows do not claim general structural approval. Assemblies, nonlinear
analysis, fatigue, dynamics, thermal stress, tolerances, optimization,
manufacturing approval, global convergence, adaptive refinement, generic mesh
correspondence, global yield/safety certification, and automatic
synthesis/selection remain future or out of scope. M11-5 structural Evidence
and bounded convergence are current only within the stated source-bound
single-solid linear-static scope.
