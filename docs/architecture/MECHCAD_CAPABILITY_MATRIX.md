# MechCAD Capability Matrix

Maturity values are normative expectations, not audit verdicts. Definitions are authoritative in `MECHCAD_SYSTEM_CONTRACT.md`: `FOUNDATION` and `REQUIRED_CURRENT` are both mandatory baseline conformance scope; selected `TARGET_NEXT` capabilities enter connected-readiness audit; `FUTURE` is documentary only.

| Capability | Subsystem | Expected owner | Canonical input | Output | Expected tool/library | Verification requirement | Maturity | Normative source |
|---|---|---|---|---|---|---|---|---|
| canonical DesignState | state | state authority | requirements/domain authority | typed state | Pydantic | schema and authority separation | FOUNDATION | M0/M1 |
| immutable revision/hash | StateManager | state authority | DesignState | snapshot/hash/current pointer | SHA-256/filesystem | canonical serialization, reload, tamper, no overwrite | REQUIRED_CURRENT | M1/project description |
| ChangeProposal | changes | domain owner | bounded result/decision | proposal | none | source binding and typed operations | FOUNDATION | M2 |
| ChangeSet/ChangeEngine | changes | harness authority | proposal plus source binding | new revision/receipt | StateManager | source/currentness where applicable, ownership, operation, and resulting-state validation; proposal status is not an approval gate | REQUIRED_CURRENT | M2 |
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
| candidate authority/currentness/publication | candidates | candidate service | source-bound candidate, request, policy, trusted artifacts | noncanonical candidate/publication/currentness decision | candidate services / ArtifactStore | full hash/binding verification; relevant source drift, tampered, missing, or foreign artifacts fail closed; publication creates no canonical authority | REQUIRED_CURRENT (bounded M12) | M12-2/M12-6 |
| bounded revolute-drive realization | candidates | candidate service | supplied direct-drive or external-spur authority | noncanonical realization/candidate | revolute-drive services | declared admissibility only; no generic generation, catalog search, or optimization | REQUIRED_CURRENT (bounded M12-3) | M12-3/M12-6 |
| candidate CAD/M10/evaluation | candidates/CAD/kinematics | candidate services | current candidate, trusted source STEP, mapping, declared M10 scope | candidate CAD/M10/evaluation | FreeCAD/M10 services | complete bindings; collision is infeasible and `NOT_PROVEN` unresolved; candidate result is noncanonical | REQUIRED_CURRENT (bounded M12-4) | M12-4/M12-6 |
| comparison and explicit selection | candidates | production caller | current feasible evaluations and optional comparison | comparison or noncanonical selection | candidate services | sole declared metric only; comparison does not select; selection is explicit and does not promote | REQUIRED_CURRENT (bounded M12-4) | M12-4/M12-6 |
| promotion and canonical rebinding | candidates/changes | ProductionApplication | selected current feasible candidate and validated compilation | N+1 physical mechanism plus durable manifests | RunController / ChangeEngine | one target operation; candidate facts do not become canonical by selection; replay/conflict fail closed | REQUIRED_CURRENT (bounded M12-5/6) | M12-5/M12-6 |
| fresh canonical promotion verification | candidates/CAD/kinematics | promotion verifier | N+1 revision, manifests, trusted artifacts | fresh reconstruction/CAD/M10 and bound result | canonical CAD/M10 services | distinct from candidate identities; durable restart/reload; required scope comparison | REQUIRED_CURRENT (bounded M12-6) | M12-6 |
| M11 promotion handoff | candidates/structural | handoff service | promoted canonical mechanism and mappings | eligibility assessment | M11 handoff service | no structural definition, mesh, solve, or structural Evidence | REQUIRED_CURRENT (bounded M12-6) | M12-6 |
| supplied-component interface authority | physical mechanisms | physical-mechanism services | typed supplied interface facts, frames, trusted component | source-bound interface authority | typed models | geometry/labels/filenames do not infer authority; unit-verified at this boundary | REQUIRED_CURRENT (bounded M13-1) | M13-1/M13-4 |
| generated-part authority and CAD | physical mechanisms/CAD | physical-mechanism and CAD services | bound semantic generated-part specification | derived generated CAD/placement | canonical CAD services | current cylindrical stock plus axial-bore scope; exactness is semantic, not manufacturing truth | REQUIRED_CURRENT (bounded M13-2) | M13-2/M13-4 |
| M10 v2 rigid-body groups/multi-joint bridge | physical mechanisms/kinematics | bridge services | physical bodies, joints, placements, CAD universe | source-bound grouped-body M10 request/result | M10 services | complete non-overlapping groups and placement agreement; no general trajectory/configuration-space proof | REQUIRED_CURRENT (bounded M13-3) | M13-3P/M13-3/M13-4 |
| multi-joint promotion/production composition | candidates/production | ProductionApplication | selected multi-joint candidate and compilation | N+1 promotion receipts plus fresh canonical verification | RunController / ChangeEngine / canonical services | explicit, one obligation, durable decision/result verification; no authority bypass | REQUIRED_CURRENT (bounded M13-4) | M13-4 |
| dynamics/simulation | dynamics | kinematics owner | mechanism/trajectory | dynamic result | MuJoCo if accepted | solver/version/binding | FUTURE | project description |
| manufacturing output | manufacturing | manufacturing owner | verified design | manufacturing package | future tools | tolerances/BOM/review | FUTURE | project description |

## Traceability Pointers

The capability rows above own current normative scope, maturity, and limits.
Historical chronology, missing-record qualifications, and retained execution
boundaries belong to `docs/reconstruction/` and accepted audits.

### M6B

Current bounded agent, strict structured-output, mediated-tool, Evidence
round-trip, and constraint capabilities are defined by the matrix and System
Contract. The round-trip provenance caveat and constraint traceability gaps
remain audit concerns, not different current contracts. See
`../reconstruction/milestones/M6B.md`, `M6B-3.md`, and `M6B-4A.md`.

### M7

Current generic CAD, assembly, exact-geometry, and discrete-sweep semantics are
defined by the matrix and System Contract. Reference-domain evidence remains
non-generic, and preliminary concepts remain documentary only. See
`../reconstruction/milestones/` and
`../audit/MECHCAD_POST_M8_M9_DOCUMENTATION_RECONCILIATION.md`.

### M8 / M9 / M10

Current production composition, source-bound CAD, trusted imported artifacts,
live FreeCAD realization, exact measurement, and motion semantics are defined
by the matrix and System Contract. Ordinary discrete sweeps retain
`continuous_sweep_verified = False`; M10-4 proves only one explicitly requested
path and does not certify a configuration-space region. See
`../audit/MECHCAD_M9_SYSTEM_ACCEPTANCE.md`,
`../audit/MECHCAD_M10_SYSTEM_ACCEPTANCE.md`, and reconstruction milestones
`M8C.md`, `M9.md`, and `M10.md`.

### M11

The current path is source-bound, single-solid, homogeneous, linear-static
structural analysis with durable Evidence, declared repeatability, and bounded
free-end displacement-magnitude mesh-convergence studies. It does not imply
assembly FEA, nonlinear/fatigue/dynamics/thermal analysis, global convergence,
or general safety or manufacturing approval. See
`../audit/MECHCAD_M11_SYSTEM_ACCEPTANCE.md` and reconstruction milestones
`M11-2.md` through `M11-6.md`.

## M12 Traceability

| Milestone | Accepted evidence | Current bounded capability | Normative treatment |
|---|---|---|---|
| M12-2 through M12-4 | M12-6 system acceptance | source-bound noncanonical candidates; bounded direct-drive/external-spur realization; candidate CAD, M10, evaluation, comparison, and explicit selection | REQUIRED_CURRENT within declared candidate and M10 scopes; not general synthesis or optimization |
| M12-5 | M12-6 system acceptance | validated promotion compilation/application, N→N+1 canonical rebinding, durable manifests, and fresh canonical reconstruction | REQUIRED_CURRENT within one selected feasible candidate and one obligation |
| M12-6 | `M12_6_LIVE_END_TO_END_PHYSICAL_MECHANISM_ACCEPTANCE_VERIFIED` | production-composed direct-drive and external-spur flows through fresh canonical CAD/M10 and restart verification | REQUIRED_CURRENT (bounded live-verified flow); M11 handoff remains eligibility-only |

## M13 Traceability

| Milestone | Accepted evidence | Current bounded capability | Normative treatment |
|---|---|---|---|
| M13-1 | M13-4 accepted baseline | typed supplied-component interface facts, bindings, and frames | REQUIRED_CURRENT; unit-verified interface boundary, not fit/clearance/manufacturing authority |
| M13-2 | M13-4 accepted baseline | semantic generated-part authority and derived CAD placement | REQUIRED_CURRENT; generated CAD remains within declared part scope |
| M13-3P / M13-3 | M13-4 accepted baseline | M10 v2 rigid-body groups and candidate/canonical multi-joint lowering | REQUIRED_CURRENT; bounded verification only, not general trajectory proof |
| M13-4 | `M13_4_INDEPENDENT_FINAL_ACCEPTED` | durable multi-joint promotion verification and ProductionApplication composition | REQUIRED_CURRENT (bounded current accepted terminal baseline) |
