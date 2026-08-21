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

This is the general persisted project-CAD path. FreeCAD realizes and verifies generic part and assembly programs.

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

The result is discrete. `continuous_sweep_verified` remains false.

## N. Domain Extension

```text
domain authority -> typed domain model/state path/owner
-> deterministic domain service -> proposal
-> generic CAD/analysis -> evidence/artifact -> invalidation-aware iteration
```

## Optional Reference Domain

An antenna payload/rotator may sit above this flow as a domain adapter. It must not appear in the generic diagrams or redefine generic axes, assemblies, or sweep services.
