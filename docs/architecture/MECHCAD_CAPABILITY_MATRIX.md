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
| CadPartProgram/CAD compiler | CAD | domain owner | accepted DesignSpec | generic part program | generic operations | deterministic program hash | REQUIRED_CURRENT | M7A |
| CadAssemblyProgram | assembly | domain owner | parts/transforms | rigid assembly program | FreeCAD assembly backend | ordering, identity, transform integrity | REQUIRED_CURRENT | M7A |
| FreeCAD part/assembly realization | CAD backend | CAD service | part/assembly program | verified FCStd/STEP | FreeCAD | fresh reload, shape, solid, placements | REQUIRED_CURRENT | M7A/project description |
| ArtifactStore/durable CAD | artifacts | CAD/provider service | verified bytes/provenance | immutable artifact | filesystem | SHA-256, conflict/no overwrite | FOUNDATION | M5.5/M7A |
| exact collision/interference/clearance | analysis | verification owner | verified assembly pairs | exact classifications | FreeCAD | common volume and exact distance | REQUIRED_CURRENT | M7A |
| transient assembly analysis | transient service | verification owner | source assembly/transform | temporary measurement result | FreeCAD | temporary workspace/no mutation | REQUIRED_CURRENT | M7C |
| generic single-axis sweep | kinematic service | kinematics owner | axis/groups/angles | ordered aggregate | transient provider | hashes/order/discrete classification | REQUIRED_CURRENT | M7C |
| domain extension framework | domain layer | domain owner | authority/spec/ownership | proposals/adapters | generic core | boundary and ownership review | FOUNDATION | universal contract |
| reference domain adapter proof | domain layer | domain owner | domain layout/reference | generic service request/result | generic CAD/kinematics | no generic-layer leakage | FOUNDATION | M7B/M7D reference evidence |
| connected rotary-bracket workflow | integration | orchestrator/domain owners | universal requirements | verified system result | selected current foundations | concrete end-to-end runtime path | TARGET_NEXT | project description Phase E |
| multi-axis kinematic chain | kinematics | kinematics owner | parent/joints/frames | chain result | future backend | frame/joint composition | TARGET_NEXT | project description Phase F |
| structural analysis | structural | structural owner | loads/sections/materials | stress/deflection | future solver | acceptance and calibrated validation | FUTURE | M5.5 exclusions |
| FEA | structural backend | structural owner | mesh/material/load | FEA result | future solver | solver provenance | FUTURE | project description |
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
