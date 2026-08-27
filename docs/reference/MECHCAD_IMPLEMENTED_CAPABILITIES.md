# MechCAD Implemented Capability Reference

This document describes the currently implemented capability inventory. It is
descriptive, not normative. For architecture, authority, contracts, and intended
system behavior, the normative documents under [docs/architecture](../architecture/)
take precedence.

Do not read this document for every task. Read it when planning a milestone,
checking whether a capability already exists, avoiding duplicate implementation,
investigating production wiring, integrating providers or tools, extending
CAD/kinematics/FEA/synthesis, or reviewing older M1-M11 functionality.

## Purpose And Usage

Use this as a selective implementation index. Current source and tests establish
what is implemented; accepted audit records establish what was live verified.
The architecture documents remain the authority for intended behavior and
system contracts.

- Architecture and authority: [Project Overview](../architecture/MECHCAD_PROJECT_OVERVIEW.md), [System Contract](../architecture/MECHCAD_SYSTEM_CONTRACT.md), and [Capability Matrix](../architecture/MECHCAD_CAPABILITY_MATRIX.md).
- Runtime composition: [Runtime Flow](../architecture/MECHCAD_RUNTIME_FLOW.md) and [Subsystem Contracts](../architecture/MECHCAD_SUBSYSTEM_CONTRACTS.md).
- Accepted runtime evidence: [M9](../audit/MECHCAD_M9_SYSTEM_ACCEPTANCE.md), [M10](../audit/MECHCAD_M10_SYSTEM_ACCEPTANCE.md), [M10 multi-shape closure](../audit/MECHCAD_M10_MULTI_SHAPE_TRANSIENT_GEOMETRY_CLOSURE.md), and [M11](../audit/MECHCAD_M11_SYSTEM_ACCEPTANCE.md).

## Capability Status Vocabulary

| Status | Meaning |
|---|---|
| `EXISTS_PRODUCTION_VERIFIED` | Implemented, production-composed, reachable through a production entry point, and live verified. |
| `EXISTS_PRODUCTION_UNVERIFIED` | Implemented and production-composed, but no accepted live verification is recorded here. |
| `EXISTS_UNWIRED` | Implemented and tested, but not composed into the default production workflow. |
| `PARTIAL` | Some model, service, or provider boundary exists, but required semantics or end-to-end wiring do not. |
| `SUPERSEDED` | Historical statement or path replaced by current implementation. |
| `TEST_ONLY` | Exists only as a fake, fixture, or test support path. |
| `DOCUMENTATION_ONLY` | Designed or described without runtime implementation. |
| `MISSING` | No current implementation boundary. |

When a status matters, also check whether the model, service, provider,
registration, production composition, caller, end-to-end path, and live proof
exist. An importable library or unit test is not automatically a production
capability.

## Core State / Change Infrastructure

`EXISTS_PRODUCTION_VERIFIED` reusable infrastructure:

- Canonical state, requirements, constraints, components, authoritative parameters, deterministic serialization, immutable revisions, and state hashing: `models/design.py:DesignState`, `state/manager.py:StateManager`.
- Evidence persistence and reload: `dependency/storage.py:EvidenceStore`.
- Derived artifact persistence and byte/provenance checks: `artifacts/storage.py:ArtifactStore`.

`EXISTS_PRODUCTION_UNVERIFIED` reusable infrastructure:

- Dependency invalidation and evidence freshness: `dependency/graph.py:DependencyGraph`, `dependency/storage.py:EvidenceStore`.
- Ownership-checked proposals and change sets: `models/proposal.py:ChangeProposal`, `ChangeSet`; `changes/engine.py:ChangeEngine`. The generic proposal-to-revision path is production-composed and tested, but its accepted evidence does not establish a standalone live-verified workflow.
- Run/task control and proposal application: `runs/controller.py:RunController`. The service is production-composed, while the generic change/run path remains unverified as a complete live workflow.

These are common boundaries, not domain-specific synthesis. `DesignState` is
canonical; proposals, tool results, artifacts, analysis results, and evidence
are separately bound records. See the normative [System Contract](../architecture/MECHCAD_SYSTEM_CONTRACT.md).

## M12 Candidate Foundation

`EXISTS_PRODUCTION_UNVERIFIED`: `candidates/` provides immutable source-bound,
noncanonical mechanical candidate definitions; per-property component authority
snapshots; typed physical mechanism topology and M10-joint realization bindings;
integrity/currentness verification; and explicit `ArtifactStore` publication /
fresh reload. `ProductionApplication` composes only those verification and
publication services. This is not candidate generation, sizing, catalog lookup,
CAD, M10/M11 execution, ranking, selection, promotion, or a second canonical
store.

## Agent / Orchestration Infrastructure

`EXISTS_PRODUCTION_VERIFIED` framework and composition:

- Agent transport/validation: `agents/gateway.py:AgentGateway`, `agents/registry.py:AgentRegistry`, `agents/context.py:ContextBuilder`, and `agents/base.py:AgentAdapter`.
- Tool mediation and exact registrations: `tools/broker.py:ToolBroker`, `tools/registry.py:ToolRegistry`.
- Production composition root: `application.py:ProductionApplication.create` constructs state, change, run, evidence, tool, agent, CAD, kinematic, and structural service boundaries.
- The bounded `mechcad-transmission` workflow is production-wired through `ProductionApplication.run_transmission_round_trip`; it is reasoning-only and does not automatically mutate canonical state.

`EXISTS_UNWIRED` or `TEST_ONLY` workflow boundaries include
`agents/constraint_resolution_workflow.py:ConstraintResolutionWorkflow` and
the deterministic fake agent transport. Their existence does not mean an agent
workflow is selected by the default application path.

## Engineering Provider Inventory

| Provider / capability | Status and implementation | Composition and limitation |
|---|---|---|
| Built-in torque, spur-gear geometry, envelope, and compensation tools | `EXISTS_PRODUCTION_UNVERIFIED`; `tools/builtins.py:BuiltinTools` | Default registered and production-available. The bounded torque vertical slice is live verified through `ProductionApplication.run_transmission_round_trip`; default registration alone does not live-verify the other tools. |
| py_gearworks / build123d external spur geometry and gear CAD | `EXISTS_UNWIRED`; `tools/gearworks.py:GearworksTools`, `backends/adapters/py_gearworks.py:PyGearworksAdapter` | Registrations require `additional_tool_registrations`; live M9/M10 fixtures prove the explicit path. Spur geometry/CAD only, not strength, life, efficiency, or gearbox design. |
| bd-materials typical properties | `EXISTS_UNWIRED`; `tools/materials.py:MaterialTools`, `backends/bd_materials.py:BdMaterialsAdapter` | Explicit optional registration only; values retain typical-reference authority and do not select materials. |
| sectionproperties geometry/warping | `EXISTS_UNWIRED`; `tools/sections.py:SectionTools`, `tools/section_engineering.py:SectionEngineeringTools` | Explicit optional registration only; supports bounded section properties/preliminary integration, not general structural approval. |
| NumPy / SciPy | `PARTIAL` dependency support | Optional provider dependencies; no generic numerical search or optimization production service. |
| FreeCAD generic part CAD | `EXISTS_PRODUCTION_VERIFIED`; `backends/freecad.py:FreeCADBackend`, `cad_compilation.py:CadCompilationService` | Deterministic mounting-plate compilation and verified FCStd/STEP artifacts. |
| FreeCAD mixed assembly | `EXISTS_PRODUCTION_VERIFIED`; `backends/freecad_assembly.py:FreeCADAssemblyBackend` | Generated and trusted imported components; assembly analysis service itself is not the default production caller. |
| Transient FreeCAD geometry measurement | `EXISTS_PRODUCTION_VERIFIED`; `transient_freecad_measurement.py:FreeCADTransientAssemblyMeasurementProvider` | Production-composed for M9/M10 exact collision/clearance and proof geometry. |
| Structural FreeCAD / Gmsh / CalculiX | `EXISTS_PRODUCTION_VERIFIED`; `structural/service.py:StructuralAnalysisService` | Bounded source-bound single-solid linear-static path only. |

## Existing Narrow Synthesis Capabilities

The following are `EXISTS_UNWIRED` narrow/domain-specific synthesis services;
they must not be mistaken for generic mechanism synthesis:

- Azimuth mounting plate synthesis: `azimuth_mount_plate.py:synthesize_azimuth_motor_mount_plate`, `AzimuthMountPlateSynthesisService`.
- Yagi carrier layout synthesis: `yagi_carrier.py:synthesize_yagi_carrier_layout`, `YagiCarrierSynthesisService`.
- Yagi collision/envelope/layout synthesis: `yagi_collision_layout.py:synthesize_yagi_collision_layout`, `YagiCollisionLayoutSynthesisService`.
- Sliding-interface option selection: `yagi_sliding_interface.py:select_yagi_carrier_sliding_interface`.
- Domain result-to-proposal translators: the synthesis modules' `to_change_proposal` functions.

These services are directly tested and can create `ChangeProposal` records, but
`ProductionApplication.create` does not compose or call them as a generic
requirements-to-design workflow. They do not establish automatic general
mechanism synthesis.

## CAD Capability

The following CAD capabilities are implemented; statuses are indicated where
their production wiring differs:

- Backend-independent `CadPartProgram` and deterministic mounting-plate compilation: `cad_program.py`, `cad_compilation.py:CadCompilationService`.
- Trusted imported STEP resolution: `imported_component.py:ImportedCadComponent`, `resolve_imported_component`, and `ArtifactStore`.
- `CadAssemblyProgram` mixed imported/generated rigid assemblies: `cad_assembly.py:CadAssemblyProgram`, `backends/freecad_assembly.py:FreeCADAssemblyBackend`.
- External spur gear STEP production through `GearworksTools` when explicitly registered: `EXISTS_UNWIRED` outside workflows that explicitly add those registrations.
- FreeCAD 1.1.3 production realization, artifact persistence, fresh reload, and disposable transient geometry realization; see [M9 acceptance](../audit/MECHCAD_M9_SYSTEM_ACCEPTANCE.md).

`ImportedCadComponent` means the complete imported STEP artifact. The post-M10
closure verifies that transient collision/clearance, radial-bound, and
local-extent realization compounds all top-level imported shapes, matching
persisted assemblies: [M10 multi-shape closure](../audit/MECHCAD_M10_MULTI_SHAPE_TRANSIENT_GEOMETRY_CLOSURE.md).

## Kinematics / Collision / Clearance

`EXISTS_PRODUCTION_VERIFIED`:

- Discrete single-axis assembly analysis: `ProductionApplication.analyze_assembly_kinematics`.
- M10-1 conservative continuous single-axis proof: `ProductionApplication.prove_continuous_single_axis_clearance`, `continuous_proof.py:ContinuousSingleAxisClearanceProof`.
- M10-2 deterministic multi-joint forward kinematics: `ProductionApplication.evaluate_multi_joint_configuration`, `multi_joint_kinematics.py:MultiJointKinematicsService`.
- M10-3 exact discrete multi-joint collision: `ProductionApplication.analyze_multi_joint_collision_sweep`.
- M10-4 continuous clearance proof over one explicit piecewise-linear multi-joint path: `ProductionApplication.prove_continuous_multi_joint_path_clearance`.

The current model is rigid revolute bodies. It does not provide dynamics,
compliance, backlash, inverse kinematics, trajectory planning, swept-solid
analysis, or whole-configuration-space certification. A discrete sweep is not a
continuous proof. See [M10 acceptance](../audit/MECHCAD_M10_SYSTEM_ACCEPTANCE.md).

## Structural Analysis

`EXISTS_PRODUCTION_VERIFIED` M11 is a source-bound, single homogeneous solid,
linear-static, small-deformation, isotropic linear-elastic workflow:

- Typed structural authority, materials, semantic regions, loads, supports, and criteria.
- Trusted FreeCAD geometry realization and semantic BREP region resolution.
- Real Gmsh C3D10 meshing, deterministic CalculiX deck lowering, and rigid-body constraint preflight.
- CalculiX execution; displacement, extrapolated nodal stress, and reactions; typed `PASS`, `FAIL`, and `NOT_EVALUABLE` evaluation.
- Fixed-cantilever analytical validation, durable structural Evidence, fresh verification, bounded repeatability, and bounded free-end displacement-magnitude mesh convergence.

Production composition is in `application.py:ProductionApplication`; execution
is `structural/service.py:StructuralAnalysisService`; durable verification is
`structural/evidence_service.py:StructuralEvidenceVerifier`. M11 is not
assembly FEA, nonlinear analysis, fatigue, dynamics, thermal stress, global
convergence, global yield, safety, or manufacturing approval. Accepted status:
[`M11_FULLY_CLOSED_LIVE_VERIFIED`](../audit/MECHCAD_M11_SYSTEM_ACCEPTANCE.md).

## Physical Component / Mechanism Capability

| Capability | Status | Current boundary / limitation |
|---|---|---|
| Generic `Component` metadata | `PARTIAL` | `models/design.py:Component`; canonical component metadata remains intentionally separate from noncanonical candidate snapshots. |
| `MotorCharacteristicsValue` | `PARTIAL` | `engineering/values.py`; authority input only, not motor selection/sizing. |
| Generic component catalog/search | `MISSING` | No catalog, supplier API, marketplace search, or component selection workflow. |
| Candidate component property authority | `EXISTS_PRODUCTION_UNVERIFIED` | `candidates/models.py:ComponentPropertySnapshot` and `ComponentSpecificationSnapshot` remain immutable noncanonical snapshots; M12-3 consumes explicit property hashes and authorities in bounded drive checks, with no catalog lookup or canonical promotion. |
| Bounded motor admissibility | `EXISTS_PRODUCTION_UNVERIFIED` | `revolute_drive.calculations:evaluate_motor_checks`, composed by `ProductionApplication.realize_and_evaluate_revolute_drive`; direct-drive and external-spur torque, optional peak torque, scalar speed-range, and optional voltage checks only. No motor catalog or selection. |
| Gearbox sizing | `PARTIAL` | M12-3 evaluates supplied external-spur compatibility, nominal ratio/speed, and efficiency-bound torque transfer; pure `calculate_spur_loads` is available and explicitly tested, but production mesh-derived `Ft`/`Fr` shaft-plane loading remains `UNRESOLVED` because the template lacks explicit plane mapping. Production shaft sizing supports explicit transverse load vectors only; no gearbox selection, gear strength, life, or CAD. |
| Solid-shaft static sizing and support reactions | `EXISTS_PRODUCTION_UNVERIFIED` | `revolute_drive.calculations:calculate_shaft_static_sizing`, composed through the M12-3 production path; static homogeneous solid circular shaft, explicit equilibrium/support reactions, one load plane, and exactly two simple radial supports. No fatigue, buckling, critical-speed, tolerance, or general shaft design. |
| Bearing sizing | `MISSING` | No bearing model, life calculation, or selection. |
| Fastener sizing | `MISSING` | No fastener model or sizing. |
| Typed physical mechanism topology | `EXISTS_PRODUCTION_UNVERIFIED` | `candidates/models.py:PhysicalMechanismRealization`, `PhysicalComponentInstance`, and `MechanicalConnection` are now populated deterministically by the M12-3 service for the two explicit supplied-component templates; topology remains noncanonical and bounded. |
| Typed physical-joint realization binding | `EXISTS_PRODUCTION_UNVERIFIED` | `candidates/models.py:JointPhysicalRealizationBinding` is deterministically created for exactly one scoped joint with shaft, actuator/transmission path, two supports, hub, mounts, and axis/frame reference; it does not bridge to M10 or prove CAD/structural suitability. |
| Bounded physical-joint realization and sizing | `EXISTS_PRODUCTION_UNVERIFIED` | `RevoluteDriveRealizationService.construct_candidate/evaluate` and `ProductionApplication.realize_and_evaluate_revolute_drive` compose direct-drive or external-spur construction plus bounded admissibility and static sizing from supplied snapshots. Incomplete topology is unresolved without a candidate; no generic synthesis, catalog, selection, or promotion. |

## Candidate / Design Generation Capability

- Narrow domain synthesis: `PARTIAL` / `EXISTS_UNWIRED`; see [Existing Narrow Synthesis Capabilities](#existing-narrow-synthesis-capabilities).
- Immutable source-bound `MechanicalDesignCandidate`: `EXISTS_PRODUCTION_UNVERIFIED`; candidate model, integrity/currentness services, and the bounded M12-3 template construction path are composed, but candidates remain noncanonical and are not published automatically.
- Candidate explicit publication/provenance: `EXISTS_PRODUCTION_UNVERIFIED`; publication and fresh resolution use `ArtifactStore` with deterministic identity/source binding. Publication is explicit, not automatic persistence, not a `CandidateStore`, not canonical authority, and not Evidence by itself.
- Generic candidate generation: `MISSING`.
- Candidate ranking, optimization/search, and automated refinement loop: `MISSING`.
- Candidate-to-M10 execution bridge: `MISSING`; M10 remains available independently, but M12-2 does not execute candidate CAD or M10 evaluation.
- Candidate-to-M11 bridge: `MISSING`; M11 accepts source-bound structural definitions/requests, not design candidates.

MechCAD does not currently turn general engineering requirements into general
mechanical design candidates or provide general/unbounded physical-realization
sizing/design, comparison, selection, or promotion. Bounded M12-3 direct-drive
and external-spur realization, engineering evaluation, and sizing from supplied
snapshots are implemented. Generic candidate generation/search remains absent;
the candidate model and explicit publication boundary remain noncanonical, and
canonical promotion does not exist.

## Implemented But Unwired

- `GearworksTools`, `MaterialTools`, `SectionTools`, and `SectionEngineeringTools`: tested optional tool registration families, not `ProductionApplication.create` defaults.
- `ConstraintResolutionWorkflow`: implemented workflow boundary, not default production composition.
- M7 azimuth/Yagi synthesis services: tested narrow direct-service paths, not generic production synthesis.
- `analysis_service.py:CadAssemblyAnalysisService`: implemented/tested assembly analysis service, not a default `ProductionApplication` entry point.

## Superseded / Historical Boundaries

- Pre-M8 claims that no `ProductionApplication` or production CAD/kinematic path exists are superseded by `application.py:ProductionApplication` and M8-M10 acceptance.
- Historical `RUNTIME_GATED` wording is not current status when later live acceptance exists.
- M11-1 is architecture/design history; the implemented M11 path is live closed through M11-6.

## Known Integration Boundaries

- `ImportedCadComponent` is the complete byte-verified STEP artifact, not one selected top-level shape.
- `run_id` is correlation/storage scope, not engineering identity; source revision/state hash and deterministic request/result hashes bind engineering records.
- Compilation provenance is not automatically transitive: `CadCompilationService` accepts a source-bound design specification under `PREACCEPTED_CALLER_CONTRACT_ONLY`; the exact specification is not automatically canonical selected design authority.
- Transient collision/clearance analysis creates disposable derived geometry and does not mutate canonical state.
- M11 is source-bound single-solid structural analysis, not assembly FEA.

## Capability Quick Matrix

| Capability | Status | Production entry point | Live verified? | Main limitation | More detail |
|---|---|---|---|---|---|
| Canonical state, evidence persistence, and artifacts | `EXISTS_PRODUCTION_VERIFIED` | `ProductionApplication.create` | Yes | No automatic authority mutation | [Core State / Change Infrastructure](#core-state--change-infrastructure) |
| Generic proposals, changes, and run control | `EXISTS_PRODUCTION_UNVERIFIED` | `ProductionApplication.create` | No standalone live proof | Generic path has production composition and tests, but no accepted complete live workflow | [Core State / Change Infrastructure](#core-state--change-infrastructure) |
| Built-in tools and transmission reasoning | `EXISTS_PRODUCTION_UNVERIFIED` | `run_transmission_round_trip` | Torque slice only | Default registration is not individual live verification; no automatic synthesis/selection | [Agent / Orchestration Infrastructure](#agent--orchestration-infrastructure) |
| Optional gear/material/section providers | `EXISTS_UNWIRED` | Explicit additional registrations | Selected paths | Not defaults; bounded domains | [Engineering Provider Inventory](#engineering-provider-inventory) |
| Generic/mixed CAD and imported STEP | `EXISTS_PRODUCTION_VERIFIED` | Assembly/CAD application services | Yes | Plate compiler is narrow; external gear CAD requires optional registration | [CAD Capability](#cad-capability) |
| M10 kinematics/collision/clearance | `EXISTS_PRODUCTION_VERIFIED` | M10 `ProductionApplication` methods | Yes | Rigid revolute model; bounded paths | [Kinematics / Collision / Clearance](#kinematics--collision--clearance) |
| M11 structural analysis | `EXISTS_PRODUCTION_VERIFIED` | Structural application methods | Yes | Single-solid linear static | [Structural Analysis](#structural-analysis) |
| M12 candidate authority/topology/publication | `EXISTS_PRODUCTION_UNVERIFIED` | `ProductionApplication` candidate integrity/currentness/publication services plus `realize_and_evaluate_revolute_drive` | Focused M12-3 tests verified; full-suite/live status pending | Immutable noncanonical candidate model, explicit ArtifactStore publication remains separate, and bounded two-template realization/sizing; no generic generation, CAD, M10/M11 execution, ranking, selection, or promotion | [Candidate / Design Generation Capability](#candidate--design-generation-capability) |
| M12 bounded revolute-drive realization and sizing | `EXISTS_PRODUCTION_UNVERIFIED` | `ProductionApplication.realize_and_evaluate_revolute_drive` | Focused production integration verified; no separate live-runtime acceptance | Supplied direct-drive or external-spur inputs only; nominal ratio/load, motor admissibility, two-support solid-shaft sizing, no catalog, arbitrary synthesis, strength, life, CAD, M10/M11 bridge, comparison, selection, promotion, Evidence, or artifact publication | [Physical Component / Mechanism Capability](#physical-component--mechanism-capability) |
| Generic candidate generation | `MISSING` | None | No | Candidate model exists, but no generation/search/ranking workflow | [Candidate / Design Generation Capability](#candidate--design-generation-capability) |

## When To Read Which Document

| Need | Read first |
|---|---|
| Architecture, authority, or intended behavior | [docs/architecture](../architecture/) beginning with [Project Overview](../architecture/MECHCAD_PROJECT_OVERVIEW.md) |
| Whether a capability already exists or is production-wired | This document |
| Exact M9 accepted CAD/import/measurement behavior | [M9 System Acceptance](../audit/MECHCAD_M9_SYSTEM_ACCEPTANCE.md) |
| Exact M10 motion behavior | [M10 System Acceptance](../audit/MECHCAD_M10_SYSTEM_ACCEPTANCE.md) |
| Imported multi-shape STEP consistency closure | [M10 multi-shape closure](../audit/MECHCAD_M10_MULTI_SHAPE_TRANSIENT_GEOMETRY_CLOSURE.md) |
| Structural/FEA accepted behavior | [M11 System Acceptance](../audit/MECHCAD_M11_SYSTEM_ACCEPTANCE.md) |
| Milestone implementation detail | Only the relevant completion report, specification, or plan after identifying the capability |

Do not load the entire historical milestone tree for routine work.
