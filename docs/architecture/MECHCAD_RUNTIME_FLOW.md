# MechCAD Runtime Flow

**Maturity:** `FOUNDATION` and `REQUIRED_CURRENT` flows are baseline conformance scope; `TARGET_NEXT` integrations require connected-readiness proof; `FUTURE` capabilities are not implied. See `MECHCAD_SYSTEM_CONTRACT.md`.

All diagrams are generic. Each boundary is labeled: `A` authority, `R` reasoning, `D` deterministic computation, `P` proposal/state mutation, `X` derived artifact, and `V` verification.

## A. Engineering Task Flow

```text
A Requirements -> DesignState -> Dependency/readiness -> RunController task
-> AgentGateway [R] -> AgentResult -> ConstraintRequest or ChangeProposal [P]
-> ChangeEngine -> immutable revision -> CAD/analysis [D,X] -> validation [V]
```

## B. Agent Execution Flow

```text
RunController -> AgentGateway -> bound ContextBuilder -> adapter transport
-> schema validation -> immutable AgentResult -> stale/binding check
```

## C. ToolBroker Flow

```text
Agent -> typed semantic request [R] -> permission/version/binding checks
-> ToolBroker -> registered handler/backend [D] -> ToolResult -> provenance
-> optional Evidence [X,V]
```

## D. Canonical State Mutation

```text
Agent/service -> ChangeProposal -> ChangeSet -> ChangeEngine [P]
-> stale check -> ownership check -> Pydantic state validation
-> StateManager -> immutable revision/hash
```

## E. Dependency Invalidation

```text
new revision -> changed canonical paths -> dependency graph
-> direct/transitive nodes -> immutable invalidation record
-> dependent Evidence STALE/UNKNOWN -> rebuild task
```

## F. Generic Project CAD

```text
accepted DesignState [A] -> typed Domain DesignSpec -> deterministic compiler
-> CadPartProgram / CadAssemblyProgram -> generic operations/transforms
-> FreeCADBackend / FreeCADAssemblyBackend [D,X]
-> durable FCStd / STEP -> fresh reload and geometry verification [V]
-> ArtifactStore
```

This is the general persisted project-CAD path. FreeCAD realizes and verifies generic part and assembly programs. After M9 this path is **live-verified** on real FreeCAD (1.1.3): generated `CadPartProgram` realization, persisted FCStd/STEP, and fresh reload are all executed, not merely architecturally connected.

## G. Specialized Parametric Geometry

```text
accepted specialized geometry input [A] -> specialized engineering provider
-> py_gearworks where applicable [D] -> build123d solid generation [D,X]
-> STEP / STL artifact -> ArtifactStore
-> optional later assembly import or independent verification [V]
```

This is a narrow provider path. build123d is not an interchangeable FreeCAD backend, and the current contract does not assert that every specialized artifact enters the generic assembly pipeline.

## H. Artifact and Evidence

```text
ToolResult/analysis/CAD [D] -> normalized output -> hash and source binding
-> EvidenceStore or ArtifactStore [X] -> freshness/replay verification [V]
```

## I. Torque Round Trip

```text
canonical force/load/lever requirements [A] -> transmission reasoning [R]
-> semantic transmission.torque request -> AgentToolMediator -> ToolBroker
-> deterministic torque handler [D] -> ToolResult -> trusted Evidence [V]
-> Evidence-grounded second invocation [R] -> finding/request/proposal
```

The bounded torque flow does not invoke py_gearworks. Its agent/tool/Evidence foundation is current baseline scope; connection to a general transmission design and CAD workflow is `TARGET_NEXT`.

## J. Gear Calculation

```text
accepted transmission/gear requirements [A] -> gear engineering tool/service
-> ToolBroker where the caller contract requires it -> PyGearworksAdapter
-> real py_gearworks [D] -> normalized gear result -> engineering evaluation [V]
```

The accepted gear-provider foundation is separate from the torque round trip. A production agent-to-gear connection must be proven by the later audit and is not implied here.

## K. Gear CAD

```text
accepted typed gear result/spec [A] -> gear CAD service
-> py_gearworks geometry object where applicable -> build123d [D,X]
-> derived solid / STEP / STL -> ArtifactStore
-> optional later assembly/import/verification
```

## L. Material

**CURRENT FOUNDATION:**

```text
part requirements [A] -> material provider lookup [D]
-> bd_materials adapter -> typed properties/provenance
-> preliminary mass/section evaluation [V]
```

**TARGET_NEXT:**

```text
candidate comparison [R]
-> engineering selection proposal [R]
-> ChangeProposal -> canonical material selection [P]
```

## M. Generic Kinematic Sweep

```text
source CadAssemblyProgram/hash [A,X] -> normalized RevoluteAxis and ordered angles
-> rigid transform -> transient assembly workspace [D,X]
-> exact common/distance measurement -> pair classifications
-> ordered samples and aggregate result [V]
```

The result is discrete. `continuous_sweep_verified` remains false. After M9 the
measurement is **live-verified** through the real FreeCAD
`FreeCADTransientAssemblyMeasurementProvider.exact_measure` (`common().Volume`
and `distToShape()`), not only the deterministic test provider.

## M2. Continuous Single-Axis Clearance Proof (M10-1)

```text
source CadAssemblyProgram/hash [A,X] -> normalized RevoluteAxis and angle interval
-> radial bound (bounding-box corners -> point-to-axis distance -> max)
-> conservative bisection: midpoint exact evaluation + chord-displacement motion bound
-> each leaf: d_ref - B >= required_clearance + guard
-> ContinuousSingleAxisProofStatus (VERIFIED_CLEAR / COLLISION_WITNESS / NOT_PROVEN)
-> ContinuousSingleAxisProofResult + ContinuousIntervalCertificate per leaf
-> ContinuousProofExecutionProvenance / Evidence
```

The proof is conservative: every certified interval has a mathematical guarantee
that the exact distance minus the chord-displacement motion bound exceeds the
required clearance. Touching triggers COLLISION_WITNESS (not positive clearance).
The discrete sweep result (`continuous_sweep_verified`) is not modified by this
proof; it remains a separate entrypoint.

## M3. Generic Multi-Joint Forward Kinematics (M10-2)

```text
KinematicModel (rooted acyclic tree of RevoluteJointModel) [A]
  + JointConfiguration (joint_id -> angle_deg) [A]
  + source CadAssemblyProgram/hash [A,X]
  -> fail-closed topology validation (unique IDs, existence, single parent,
     no cycles, reachability) -> deterministic BFS evaluation order
  -> per joint: T_joint(q) = Translate(p) ∘ Rotate(u,q) ∘ Translate(-p)
  -> T_world_child(q) = T_world_parent(q) ∘ T_joint(q) ∘ T_parent_child_home
  -> instance world transforms + transformed CadAssemblyProgram
  -> KinematicForwardKinematicsResult
     (model_hash / configuration_hash / transformed_assembly_hash / result_hash)
  -> ProductionApplication.evaluate_multi_joint_configuration
     -> Evidence (kind: analysis.multi_joint_kinematics)
```

Core forward kinematics has **no FreeCAD dependency**; it reuses the quaternion
helpers from `kinematic_sweep.py` only. The result is discrete (one explicit
configuration) and performs **no** collision, clearance, or continuous
verification. `transformed_assembly_hash` reuses `assembly_hash()` over the
updated `CadAssemblyProgram`. M10-3 is the intended consumer of the transformed
assembly for real FreeCAD exact measurement.

## M4. Exact Discrete Multi-Joint Collision Sweep (M10-3)

```text
source-bound CadAssemblyProgram/hash + KinematicModel + ordered configurations [A,X]
  -> MultiJointKinematicsService for each configuration
  -> transient transformed assembly [D,X]
  -> FreeCADTransientAssemblyMeasurementProvider
  -> real common().Volume / distToShape() for ordered moving/stationary pairs
  -> exact pair classifications and distance summaries
  -> MultiJointCollisionSweepResult [V]
  -> AnalysisExecutionProvenance + one trusted Evidence record
```

`MultiJointDiscreteCollisionSweepService` evaluates every requested
configuration from the unchanged source assembly. It preserves configuration
and pair order, fails closed on validation/provider/measurement/result or
Evidence failure, and never publishes partial per-configuration artifacts.
The production application owns source binding, provider composition, trusted
runtime provenance, and atomic Evidence persistence. The result is an exact
discrete sweep only; `continuous_path_verified=False` remains explicit.

## O. Production Application Flow (M8B / M8C / M9 / M10-3)

```text
DesignState [A] -> MountingPlateDesignSpec (pre-accepted caller contract)
  -> ProductionApplication.compile_design_spec
  -> CadCompilationService -> CadPartProgram

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

ProductionApplication.analyze_multi_joint_collision_sweep
  -> MultiJointDiscreteCollisionSweepService
  -> MultiJointKinematicsService -> TransientAssemblyAnalysisService
  -> FreeCADTransientAssemblyMeasurementProvider.exact_measure
  -> trusted AnalysisExecutionProvenance / Evidence
  -> common().Volume / distToShape()
  -> CadKinematicSweepResult
  -> AnalysisExecutionProvenance / Evidence
```

The deterministic test provider is a composition-boundary injection only and is
not the normal production execution path. The production application owns
provider composition; an ordinary analysis caller cannot pass a trusted
exact-measurement callback.

## M5. Conservative Continuous Multi-Joint Path Proof (M10-4)

```text
typed ordered MultiJointPath
  -> trusted local geometry extent boundary
  -> pure M10-2 topology reach bounds
  -> direct M10-2 FK from unchanged source assembly
  -> transient FreeCAD exact midpoint/waypoint measurement
  -> adaptive scalar certificates using hierarchical motion bounds
  -> VERIFIED_CLEAR / COLLISION_WITNESS / NOT_PROVEN
  -> one final trusted Evidence record
```

M10-4 proves only the requested piecewise-linear path. It does not mutate
canonical state, create per-midpoint evidence/artifacts, or certify a
configuration-space region. M10-3 results remain discrete-only with
`continuous_path_verified=False`.

## N. Domain Extension

```text
domain authority -> typed domain model/state path/owner
-> deterministic domain service -> proposal
-> generic CAD/analysis -> evidence/artifact -> invalidation-aware iteration
```

## Optional Reference Domain

An antenna payload/rotator may sit above this flow as a domain adapter. It must not appear in the generic diagrams or redefine generic axes, assemblies, or sweep services.
