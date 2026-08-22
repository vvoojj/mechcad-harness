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

Generic M7C models a normalized revolute axis, rigid moving/stationary groups, ordered angles, transient transforms, exact pair measurement, and aggregate discrete sweep classification. Current discrete sweeps explicitly do not prove continuous collision-free motion. M10-1 adds a conservative single-axis continuous clearance proof via bisection with chord-displacement motion bound. M10-2 adds deterministic multi-joint forward kinematics over a rooted acyclic tree of revolute joints, producing world transforms and a transformed `CadAssemblyProgram` for one explicit configuration. M10-3 adds exact discrete collision evaluation over ordered multi-joint configurations with trusted live FreeCAD provenance.

## 16. Artifact/Evidence Architecture

`Evidence` records deterministic engineering computation facts and freshness. `ArtifactStore` stores hashed derived files such as STEP, FCStd, and STL with project/run/revision/backend provenance. Neither is canonical state.

## 17. Domain Extension Architecture

Domains define authority models, state paths, ownership, deterministic services, domain design specs, and thin adapters. They compile into generic CAD and analysis capabilities and use common proposal, dependency, run, evidence, and artifact contracts.

## 18. Currently Established Foundations

**FOUNDATION / REQUIRED_CURRENT:** typed state and separate records; canonical hashing and filesystem revisions; ownership-checked atomic change application; dependency invalidation and freshness; run manifests and task DAG control; ToolRegistry/ToolBroker; AgentGateway, fake and OpenCode transports, strict structured output, bounded transmission reasoning, semantic tool mediation, bounded torque/Evidence follow-up reasoning, constraint discovery/materialization/satisfaction/resolution foundations; backend identity/provenance; narrow gear, material, section, CAD, assembly, exact collision, transient, discrete kinematic, single-axis continuous-proof, and generic multi-joint forward-kinematics foundations. Both maturity classes are included in baseline conformance audit.

The M8 production architecture (orchestration, source-bound CAD compilation,
trusted imported components, mixed assembly, production kinematic entrypoint)
and the M9 live verification (real FreeCAD, trusted imported STEP, live mixed
assembly, exact discrete measurement, trusted execution provenance) are the
current accepted baseline; see §22. M10-1 adds conservative continuous
single-axis clearance proof. M10-2 adds generic multi-joint discrete forward
kinematics. M10-3 adds exact discrete multi-joint collision evaluation over
transformed assemblies with trusted live FreeCAD provenance. Current M10 final
acceptance marker is `M10_FULLY_CLOSED_LIVE_VERIFIED`.

## 19. Target-Next Capabilities

**TARGET_NEXT:** the connected universal mechanical workflow across requirements, agent, deterministic provider, proposal, revision, CAD, assembly, and kinematic verification; broader domain agents; canonical transmission design models; material selection; broader CAD compilation; controlled load-case workflows; and production wiring proof for optional providers.

## 20. Future Capabilities

**FUTURE:** whole configuration-space certification, generalized autonomous constraint solving beyond the accepted bounded resolution loop, FEA, dynamics/MuJoCo integration, wind and environmental loads, manufacturing output, optimization, and broad multi-agent engineering convergence.

## 21. Reference Projects / Domain Examples

The architecture applies to gearboxes, rotary mechanisms, robotic joints, motorized stages, camera mounts, structural frames, shafts and bearing systems, transmission assemblies, and antenna rotators. The current Yagi carrier/rotator work is one domain reference implementation only.

## 22. M8 / M9 / M10 Current Baseline

M8 established the production architecture; M9 live-verified its critical
runtime edges on real FreeCAD (1.1.3). Both are **current** foundations, not
mere history.

### M8B — Production Orchestration

`ProductionApplication.create(...)` is the real non-test composition root. It
owns the trusted service graph: `StateManager`, `EvidenceStore`,
`OwnershipPolicy`, `ChangeEngine`, `RunController`, `ToolRegistry` →
`ToolBroker`, `AgentRegistry` → injected adapter, `ContextBuilder` →
`AgentGateway` → `AgentToolMediator` → `ToolBroker`. The application owns
trusted identities/permissions; the external agent adapter is injected
(required, not default); ordinary agents do not own canonical authority; tool
access remains controlled; state/source binding fails closed.

### M8C-1 — Source-Bound DesignSpec Compilation

A source-bound `MountingPlateDesignSpec` compiles through
`CadCompilationService.compile_mounting_plate` into a deterministic
`CadPartProgram` (`program_hash`, `spec_hash`,
`compiler_version = generic-mounting-plate-compiler@1.0`). Compilation is a
deterministic transform that fails closed on stale/mismatched revision/state
hash. `PREACCEPTED_CALLER_CONTRACT_ONLY`: the supplied spec is compiled against
state binding, but the exact spec is not durably represented as selected
canonical design authority.

### M8C-2 — Trusted Imported CAD + Mixed Assembly

Producer output → `EngineeringArtifact` → trusted `ArtifactStore` resolution →
`ImportedCadComponent` → `CadAssemblyProgram` (generics + imported). Trust rules:
artifact bytes persisted, size checked, SHA-256 recomputed, imported component
source provenance artifact-derived (`source_revision`/`source_state_hash`),
arbitrary caller provenance not trusted, workspace/project boundary controlled,
ambiguous project-scoped lookup fails closed (`store.existing_in_project(...)` →
`store.existing(...)`). Arbitrary STEP filesystem paths are NOT trusted imported
components. Generic mixed-assembly semantics do NOT contain gear-specific
meaning merely because a gear was a live fixture.

### M8C-3 — Production Kinematic Entrypoint

`ProductionApplication.analyze_assembly_kinematics(...)` →
`CadKinematicSweepService` → `TransientAssemblyAnalysisService` → composed
measurement provider → `CadKinematicSweepResult`. Includes generic
`RevoluteAxis`, `CadRigidTransform`, explicit moving/stationary instance
partition, ordered discrete angle samples, deterministic request/result
identity, source/transformed assembly hashes, and `continuous_sweep_verified =
False`. An ordinary analysis caller does NOT pass a trusted exact-measurement
callback; provider composition is owned by `ProductionApplication`.

### M9 — Live Verification

- **M9-1:** real FreeCAD backend executes generic `CadPartProgram` realization;
  persists FCStd/STEP; fresh reload verified; backend/runtime provenance
  captured.
- **M9-2:** real `mechcad-build-spur-gear-cad@1.0` (py_gearworks/build123d)
  produces real STEP bytes → `ArtifactStore` → `ImportedCadComponent` with
  actual-byte SHA-256 re-verification. The gear is a fixture/proof source only.
- **M9-3:** the same real mixed assembly path generates a live FreeCAD assembly,
  persists FCStd/STEP, fresh-reloads, executes real `common().Volume` /
  `distToShape()`, and completes a real discrete kinematic sweep.
- **M9-4:** durable `AnalysisExecutionProvenance` / `Evidence` binds
  `source_assembly_hash`/`request_hash`/`result_hash`/`sweep_version` to provider
  and backend/runtime identity; distinct from the `deterministic-test-provider`
  class.
- **M9 system acceptance:** `M9_FULLY_CLOSED_LIVE_VERIFIED`.

### M10-1 — Continuous Single-Axis Clearance Proof

`ContinuousSingleAxisClearanceProof` implements a conservative bisection
algorithm with chord-displacement motion bound (`2R·sin(min(|Δθ|,π)/2)`).
Radial bound R is derived from FreeCAD bounding box corners projected to the
rotation axis. Three semantic outcomes: `VERIFIED_CLEAR` (every leaf interval
certified), `COLLISION_WITNESS` (touching or interference at reference angle),
`NOT_PROVEN` (resource limits exhausted). Resource limits (`max_depth`,
`max_exact_evaluations`, `minimum_interval_deg`) are computation ceilings, not
correctness shortcuts. Ordinary discrete sweeps remain `continuous_sweep_verified
= False`. Unit-verified 2026-08-22.

### M10-2 — Generic Multi-Joint Kinematic Model

`MultiJointKinematicsService` evaluates a `KinematicModel` containing a rooted
acyclic tree (forest) of revolute joints and a complete `JointConfiguration`.
Axis origins and directions are expressed in the parent instance local frame.
Home parent-to-child transforms are derived from source assembly placements. The
result includes ordered joint states, instance world transforms, a transformed
`CadAssemblyProgram`, and separate model/configuration/transformed-assembly/
result hashes. Topology validation fails closed on duplicate IDs, missing
instances, multiple articulated parents, cycles, and unreachable articulated
nodes. `ProductionApplication.evaluate_multi_joint_configuration` validates
source binding and records deterministic provenance. Core FK has no FreeCAD
dependency and performs no collision, clearance, or continuous proof.
Unit-verified 2026-08-22.

### M10-3 — Exact Discrete Multi-Joint Collision Sweep

`ProductionApplication.analyze_multi_joint_collision_sweep` evaluates ordered
multi-joint configurations from the unchanged source assembly through
`MultiJointKinematicsService`, `TransientAssemblyAnalysisService`, and the
composed `FreeCADTransientAssemblyMeasurementProvider`. Real FreeCAD
`common().Volume` and `distToShape()` measurements produce exact pair
classifications and distance summaries. Request, result, configuration, model,
and transformed-assembly identities are deterministic, and one trusted
provider/backend/runtime provenance record is persisted atomically with the
result. The live fixture and complete test suite were verified on 2026-08-22.
The result remains discrete-only with `continuous_path_verified = False`.

### M10-4 — Continuous Multi-Joint Path Clearance Proof

`ProductionApplication.prove_continuous_multi_joint_path_clearance` evaluates
one typed ordered piecewise-linear path from the unchanged source assembly.
Production composition obtains trusted component-local geometry extents through
the FreeCAD provider; pure topology code derives invariant ancestor-chain reach
bounds. The proof uses direct M10-2 FK, exact FreeCAD waypoint/midpoint
`common().Volume` and `distToShape()` measurements, hierarchical telescoping
motion bounds, and pair-relative `B_A+B_B` certificates. Exact requested
clearance violations are witnesses; bound failure or resource exhaustion is
`NOT_PROVEN`. A verified result requires complete leaf coverage and persists
one trusted M10-4 Evidence record.

### M10-5 - M10 System Acceptance

The complete M10-1 through M10-4 motion stack is live-verified as one coherent
production chain. The system acceptance covers shared M10-2/M10-3/M10-4
configuration and transformed-assembly identity equality, exact pair-measurement
equality, durable M10-4 typed-result reload, trusted runtime provenance, source
immutability, M9 foundation regressions, and full-suite regression safety. It
does not expand the accepted motion semantics or imply configuration-space,
dynamics, FEA, or manufacturing certification.

## 23. Current Remaining Limitations

- `PREACCEPTED_CALLER_CONTRACT_ONLY`
- `COMPILATION_PROVENANCE_SEPARATE_NOT_TRANSITIVELY_LINKED` (spec/compiler
  provenance is not folded through every downstream semantic identity)
- `run_id` is correlation/storage scope only, not trusted engineering identity
- `continuous_sweep_verified = False` (ordinary discrete sweeps remain
  discrete-only; continuous proof is a separate entrypoint)
- M10-3 verifies ordered discrete configurations only; M10-4 verifies only one
  explicit continuous path. Whole configuration-space proof, FEA, materials,
  manufacturing, and optimization remain future

## 24. Next Planning Boundary

M10-1 through M10-4 and the M10-5 system acceptance are implemented and
live-verified. Whole configuration-space continuous clearance, FEA, materials
selection, manufacturing approval, tolerance verification, optimization, and
automatic synthesis/selection remain later-stage and are not current
capability. The next milestone requires a separate design/specification cycle.

## 25. Historical Baseline Reconciliation

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
