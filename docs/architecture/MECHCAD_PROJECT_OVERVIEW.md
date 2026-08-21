# MechCAD Project Overview

**Document status:** normative architecture baseline. This document describes intended behavior and current capability maturity; it is not an implementation audit. Maturity terms are defined authoritatively in `MECHCAD_SYSTEM_CONTRACT.md`.

## 1. What MechCAD Is

MechCAD is a general-purpose, deterministic, provenance-aware, multi-agent mechanical-engineering harness. It converts authoritative requirements into verified engineering state, derived geometry and analysis, and reproducible evidence while preserving ownership, revision history, and fail-closed validation.

## 2. What MechCAD Is Not

MechCAD is not a Yagi antenna application, FreeCAD automation script, gear generator wrapper, or LLM that edits CAD directly. FreeCAD, build123d, py_gearworks, material databases, numerical libraries, solvers, and agents are bounded providers or participants. None is canonical engineering authority.

## 3. Universal Engineering Workflow

External requirements become typed canonical state. Readiness and dependencies select bounded tasks. Agents reason and return structured results. Deterministic tools calculate values. Accepted proposals pass through `ChangeSet` and `ChangeEngine` into an immutable revision. CAD and analysis are derived from accepted state, then verified and stored with evidence.

## 4. Trust and Authority Model

`DesignState` is the canonical engineering source of truth. Agents, prose, CAD files, solver state, library objects, results, and evidence do not mutate it. Trusted change machinery is the only state mutation boundary.

## 5. Canonical DesignState

`DesignState` contains project identity, revision, requirements, components, assemblies, materials, interfaces, constraints, load cases, and other authoritative domain paths. Evidence, proposals, results, issues, validation, and artifacts remain separate bindable records.

## 6. Immutable Revision Model

Canonical serialization is deterministic. A complete state payload receives a SHA-256 hash and is persisted as an immutable revision snapshot. State-bound records carry the source revision and hash. A changed authority creates a new revision; external records are not silently folded into state.

## 7. ChangeProposal / ChangeSet Flow

The normative path is:

```text
Agent or engineering service -> ChangeProposal -> ChangeSet -> ChangeEngine
-> ownership and stale checks -> validated immutable DesignState revision
```

Proposals can be rejected for stale binding, invalid paths, ownership failure, invalid operations, or resulting-state validation failure.

## 8. Dependency and Invalidation

The dependency graph maps authoritative paths to derived nodes and propagates impact transitively. When inputs change, dependent evidence becomes stale or unknown until rebuilt. Freshness is bound to exact revision/hash and complete invalidation history.

## 9. RunController / Provenance

`RunController` binds a run, manifest, plan, task, invocation, result, tool call, evidence, artifact, and state transition to exact source state. Immutable records and resume/replay rules make it possible to identify the inputs that produced a result.

## 10. Agent Architecture

`AgentGateway` constructs constrained context and validates structured output. `FakeAgentAdapter` is deterministic test transport. `OpenCodeAgentAdapter` is execution transport, not authority. `mechcad-transmission` is a bounded transmission reasoning identity. The test agent is testing-only. Domain owner labels are not automatically engineering agents.

## 11. ToolBroker Architecture

Agents request semantic capabilities. `ToolBroker` verifies task binding, exact tool identity, permissions, typed input, execution state, and provenance before invoking a registered deterministic handler. Tool calls and results are immutable records.

## 12. Engineering Library Architecture

Libraries are behind typed adapters and normalized result boundaries. Current repository families include transmission/gear computation, material lookup, section properties, numerical support, parametric geometry, and CAD backends. Library output is derived input to engineering decisions, never approval.

## 13. CAD Architecture

Accepted typed design specifications compile into backend-independent `CadPartProgram` or `CadAssemblyProgram` objects. Generic operations such as plates, holes, pockets, and slots are realized by a CAD backend. Artifacts are derived and verified; they do not replace state.

## 14. Analysis Architecture

Current foundations cover exact interference/clearance, transient assembly measurement, transmission calculations, material/mass estimates, and preliminary section properties. Structural load/stress, FEA, dynamics, and manufacturing validation remain `TARGET_NEXT` or `FUTURE` unless a later specification establishes them.

## 15. Kinematic Architecture

Generic M7C models a normalized revolute axis, rigid moving/stationary groups, ordered angles, transient transforms, exact pair measurement, and aggregate discrete sweep classification. Current discrete sweeps explicitly do not prove continuous collision-free motion.

## 16. Artifact/Evidence Architecture

`Evidence` records deterministic engineering computation facts and freshness. `ArtifactStore` stores hashed derived files such as STEP, FCStd, and STL with project/run/revision/backend provenance. Neither is canonical state.

## 17. Domain Extension Architecture

Domains define authority models, state paths, ownership, deterministic services, domain design specs, and thin adapters. They compile into generic CAD and analysis capabilities and use common proposal, dependency, run, evidence, and artifact contracts.

## 18. Currently Established Foundations

**FOUNDATION / REQUIRED_CURRENT:** typed state and separate records; canonical hashing and filesystem revisions; ownership-checked atomic change application; dependency invalidation and freshness; run manifests and task DAG control; ToolRegistry/ToolBroker; AgentGateway, fake and OpenCode transports, strict structured output, bounded transmission reasoning, semantic tool mediation, bounded torque/Evidence follow-up reasoning, constraint discovery/materialization/satisfaction/resolution foundations; backend identity/provenance; narrow gear, material, section, CAD, assembly, exact collision, transient, and discrete kinematic foundations. Both maturity classes are included in baseline conformance audit.

## 19. Target-Next Capabilities

**TARGET_NEXT:** the connected universal mechanical workflow across requirements, agent, deterministic provider, proposal, revision, CAD, assembly, and kinematic verification; broader domain agents; canonical transmission design models; material selection; broader CAD compilation; multi-joint kinematic chains; controlled load-case workflows; and production wiring proof for optional providers.

## 20. Future Capabilities

**FUTURE:** continuous motion proof, generalized autonomous constraint solving beyond the accepted bounded resolution loop, FEA, dynamics/MuJoCo integration, wind and environmental loads, manufacturing output, optimization, and broad multi-agent engineering convergence.

## 21. Reference Projects / Domain Examples

The architecture applies to gearboxes, rotary mechanisms, robotic joints, motorized stages, camera mounts, structural frames, shafts and bearing systems, transmission assemblies, and antenna rotators. The current Yagi carrier/rotator work is one domain reference implementation only.

## 22. Historical Baseline Reconciliation

| Historical Statement | Current Classification | Current Source | Reconciliation Decision (not maturity) | Notes |
|---|---|---|---|---|
| Universal reusable mechanical-engineering harness | Architecture principle | `docs/MechCAD_Harness_Project_Description.md` sections 1, 26, 28 | PRESERVE | The antenna rotator is the first practical reference project, not the system definition. |
| DesignState authority | Canonical contract | M0/M1/M2 specs; `models/design.py` | PRESERVE | External records remain separate. |
| Immutable revisions and hashes | Current foundation | `state/manager.py`, `state/hashing.py` | PRESERVE | Filesystem persistence is established. |
| Dependency and invalidation | Current foundation | M3 spec; `dependency/` | PRESERVE | Freshness is fail-closed. |
| RunController | Current foundation | M4 spec; `runs/` | UPDATE | It is beyond the old roadmap description. |
| ToolBroker | Current foundation | M5 spec; `tools/` | UPDATE | Exact registration and provenance are normative. |
| Evidence | Current foundation | M0/M3/M5/M6B specs | UPDATE | Tool and backend provenance extend the record. |
| Agent Gateway / OpenCode | Accepted foundation | M6A/M6B specs and project description sections 10-12, 18 | UPDATE | Gateway, strict transport, and live path are baseline foundations; connected runtime behavior remains audit-required. |
| Transmission agent | Accepted bounded foundation | M6B-1 specs and project description sections 13, 18 | UPDATE | Reasoning/tool/Evidence boundary is current; general transmission synthesis remains target-next. |
| ConstraintRequest discovery/materialization | Accepted foundation | Project description sections 14-17, 18 | UPDATE | Typed keys, deterministic identity, persistence, and satisfaction suppression are current baseline contracts. |
| Constraint resolution loop | Accepted foundation | Project description sections 17-18 | UPDATE | Trusted external resolution flows through proposal, ChangeSet, ChangeEngine, revision, and invalidation; runtime wiring remains audit-required. |
| Engineering backend libraries | Narrow adapters | M5.5 specs; `backends/` | UPDATE | Package existence is not integration proof. |
| FreeCAD was future/not integrated | Stale roadmap status | Project description sections 18-21; M7 records | SUPERSEDED | M7A establishes a generic derived CAD foundation; connected call paths remain audit-required. |
| M6B-3 live acceptance was pending | Stale intermediate status | Project description section 17 | SUPERSEDED | Constraint discovery is recorded as established. |
| M6B-4 was future | Stale intermediate status | Project description section 17 | SUPERSEDED | Constraint resolution is recorded as implemented and accepted as a foundation. |
| M7A / first FreeCAD model was upcoming | Stale roadmap status | Project description sections 18, 20-21 | SUPERSEDED | Typed part, assembly, exact geometry, and persisted CAD foundations now precede the next connected-workflow goal. |
| M7A CAD foundation | Accepted narrow foundation | Project description sections 18, 20; M7 trace | UPDATE | Not a general CAD solver. |
| M7B domain modeling | Domain reference exercise | Project description sections 18, 26 | DOMAIN_EXAMPLE_ONLY | Done for current reference scope, with physical and structural questions unresolved. |
| M7C generic kinematics | Accepted discrete foundation | Project description section 18; M7C plan/closure evidence | UPDATE | Continuous verification remains future. |
| M7D domain kinematic integration | Completed reference adapter | M7D specs/plans; project description section 18 | DOMAIN_EXAMPLE_ONLY | Thin Yagi adapter over generic M7C, not core architecture. |
| MuJoCo | Future simulation backend | No accepted current contract identified | FUTURE | Do not claim current integration. |
| FEA | Future structural backend | README/M5.5C exclusions | FUTURE | Section properties are not FEA. |
| Multi-agent engineering goals | Future orchestration | M6/M7 boundaries | FUTURE | Existing agent identities do not prove multi-agent execution. |

The historical/current project brief reviewed for this reconciliation is `docs/MechCAD_Harness_Project_Description.md`. It preserves the original universal intent while explicitly updating stale roadmap statements. Its implementation-status assertions establish baseline maturity for documentation purposes but do not replace the independent runtime audit.
