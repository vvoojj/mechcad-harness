# MechCAD Harness

## Documentation

Start with [`docs/README.md`](docs/README.md). It provides task-sized context bundles for architecture, subsystem work, domain extensions, and the later independent integration audit. Do not preload the full documentation tree unless doing architecture reconciliation or audit preparation.

Historically, M0 was the typed Python foundation for a future engineering
workflow system, with readable identifiers, minimal Pydantic v2 domain models,
placeholder YAML configuration, and tests. That description is retained only
as project history; the current capability baseline is documented below.

## Current Architecture Status (M8 / M9 / M10 / M11)

The repository has advanced well beyond M0. The current accepted baseline is
**M8 + M9 + M10-1 + M10-2 + M10-3 + M10-4 + M11-2 + M11-3 + M11-4**.

- **M8** established the production architecture: production orchestration
  (`ProductionApplication` composition root), source-bound `DesignSpec` →
  `CadPartProgram` compilation, trusted imported STEP artifacts
  (`ImportedCadComponent` via `ArtifactStore`), generic mixed assembly
  (`CadAssemblyProgram`), and the production kinematic entrypoint
  (`ProductionApplication.analyze_assembly_kinematics`).
- **M9** live-verified the critical edges on real FreeCAD (1.1.3): real
  `CadPartProgram` realization, a real trusted imported STEP artifact, a live
  mixed FreeCAD assembly, fresh reload, exact `common().Volume` /
  `distToShape()` collision/clearance measurement, a real discrete kinematic
  sweep, and trusted durable analysis-execution provenance.
- **M10-1** adds conservative continuous single-axis clearance proof with
  `VERIFIED_CLEAR`, `COLLISION_WITNESS`, and `NOT_PROVEN` outcomes.
- **M10-2** adds deterministic multi-joint forward kinematics over a rooted
  acyclic revolute-joint tree, producing instance world transforms and a
  transformed `CadAssemblyProgram` without a FreeCAD dependency in core FK.
- **M10-3** adds exact discrete multi-joint collision evaluation through real
  FreeCAD geometry measurement with deterministic identities and trusted
  provider/backend/runtime provenance.
- **M10-4** adds conservative continuous clearance proof along one explicit
  piecewise-linear multi-joint joint-space path, with exact FreeCAD midpoint
  measurements, topology-derived reach bounds, and fail-closed proof outcomes.
- **M10-5** closes the complete M10 motion stack through live system acceptance:
  shared FK/discrete/continuous result equality, durable proof reload, trusted
  provenance, source immutability, and full regression verification.

**Current system status: `M10_FULLY_CLOSED_LIVE_VERIFIED`,
`M11_2_STRUCTURAL_AUTHORITY_MODEL_VERIFIED`,
`M11_3_STRUCTURAL_MESH_SOLVER_FOUNDATION_VERIFIED`, and
`M11_4_REAL_FEA_RESULT_ANALYTICAL_VALIDATION_VERIFIED`.**

MechCAD has a bounded, live-verified structural result interpretation path for
source-bound single-body linear-static analyses. M11-3 executes trusted
FreeCAD 1.1.3 geometry realization, Gmsh 4.15.0 meshing, and CalculiX 2.22
solving. M11-4 interprets trusted FRD/DAT outputs and evaluates typed criteria
with real PASS, FAIL, and NOT_EVALUABLE outcomes. The live analytical
validation is a separate production API using a predeclared fixed rectangular
cantilever policy; stress is extrapolated
nodal stress, not integration-point stress, and no global yield or safety claim
is made. Structural Evidence acceptance and mesh convergence remain outside
this milestone.

**Current hard limitation:** M10-3 remains discrete-only with
`continuous_path_verified = False`. M10-4 verifies only one explicitly
requested piecewise-linear path, not arbitrary configuration-space regions or
general trajectories. FEA beyond the bounded M11-4 result path, materials
selection, manufacturing approval, tolerance verification, optimization, and
automatic synthesis/selection are not implemented.

The milestone sections below (M0 → M6B) are retained as historical
documentation of how the system evolved; they are not the current capability
baseline. For current-state documentation, start with:

- [`docs/architecture/MECHCAD_PROJECT_OVERVIEW.md`](docs/architecture/MECHCAD_PROJECT_OVERVIEW.md)
- [`docs/architecture/MECHCAD_CAPABILITY_MATRIX.md`](docs/architecture/MECHCAD_CAPABILITY_MATRIX.md)
- [`docs/architecture/MECHCAD_RUNTIME_FLOW.md`](docs/architecture/MECHCAD_RUNTIME_FLOW.md)
- [`docs/audit/MECHCAD_M9_SYSTEM_ACCEPTANCE.md`](docs/audit/MECHCAD_M9_SYSTEM_ACCEPTANCE.md)
- [`docs/audit/MECHCAD_M10_2_COMPLETION_REPORT.md`](docs/audit/MECHCAD_M10_2_COMPLETION_REPORT.md)
- [`docs/audit/MECHCAD_M10_3_COMPLETION_REPORT.md`](docs/audit/MECHCAD_M10_3_COMPLETION_REPORT.md)
- [`docs/audit/MECHCAD_M10_4_COMPLETION_REPORT.md`](docs/audit/MECHCAD_M10_4_COMPLETION_REPORT.md)
- [`docs/audit/MECHCAD_POST_M8_M9_DOCUMENTATION_RECONCILIATION.md`](docs/audit/MECHCAD_POST_M8_M9_DOCUMENTATION_RECONCILIATION.md)

## M0 Boundary (historical)

M0 deliberately excludes agents, OpenCode integration, CAD, FreeCAD, FEA,
scheduling, dependency execution, LLM workflows, databases, persistence, and
external services. The package has no execution behavior.

`DesignState` is the canonical engineering state. Proposals, results,
validation records, issues, and evidence are separate records that bind to a
revision and state hash; they do not implicitly mutate canonical state.

## Development

```text
python -m pip install -e ".[test]"
pytest -q
```

The `config/` files are schema/version-marked placeholders and intentionally
contain no runtime integration settings.

## M1 State Foundation

M1 stores canonical state under `workspace/projects/<project_id>/`. A
`DesignState` is serialized as UTF-8 JSON with sorted keys, compact separators,
and JSON-native values. That complete payload, excluding no `DesignState`
fields and excluding all external records, is hashed with SHA-256 as
`sha256:<hex digest>`.

The state flow is:

```text
DesignState
  -> canonical JSON
  -> SHA-256 state hash
  -> immutable revision snapshot
  -> lightweight current.json pointer
```

Revision snapshots are numbered monotonically from 1 and cannot be overwritten.
Loading a snapshot recomputes its hash and rejects tampering. Later agents may
propose changes, but only the harness will create new canonical revisions.

## M2 ChangeSet Foundation

M2 is the deterministic mutation boundary:

```text
ChangeProposal
  -> stale revision/hash check
  -> ownership check
  -> ChangeSet
  -> complete operation validation
  -> Pydantic DesignState validation
  -> new immutable revision
```

Proposals never mutate `DesignState` directly. Supported operations are `add`,
`replace`, and `remove` over literal JSON-Pointer-like paths. Ownership is a
deterministic policy loaded from `config/ownership.yaml`; ungoverned paths fail
closed. Failed ChangeSets do not create revisions or move `current.json`.
Detailed ownership, dependency invalidation, and orchestration are later
milestones.

## M3 Dependency Invalidation

M3 keeps canonical `DesignState` revisions separate from derived evidence. After an accepted M2 `ChangeSet`, the small applied-change result exposes the new revision, changeset ID, and changed canonical paths. A deterministic dependency graph matches those paths using literal segments, one-segment `*` wildcards, and prefix matching. It returns direct and transitive invalidated nodes without executing any analysis.

Invalidation records are immutable JSON files outside canonical revisions. Evidence is also immutable, remains stored after becoming stale, and binds to a dependency node, exact state revision, and exact state hash. State hashes provide provenance; dependency history provides reusable-evidence freshness. A different state hash alone does not make every evidence record stale.

Freshness is fail-closed: `CURRENT` requires valid exact-revision provenance, a known configured node, complete invalidation records for every revision after the evidence revision through the current revision, and no matching later invalidation. Matching later invalidation yields `STALE`; missing/corrupt history, invalid provenance, and unknown nodes yield `UNKNOWN`. Evidence created for revision N does not consider the invalidation record that produced revision N. Unknown and stale evidence never satisfy a fresh-evidence query. Recalculation, scheduling, and orchestration are later scope.

## M4 Run Control

M4 adds deterministic execution control without adding an agent or execution
runtime:

```text
Canonical State
      -> Run
      -> RunPlan
      -> Task DAG
      -> TaskExecutor boundary
      -> immutable structured results and evidence
      -> explicitly approved M2 change
      -> M3 invalidation
      -> iteration and current-evidence completion gate
```

The M4 task DAG is separate from the M3 engineering dependency graph. Task
definitions are immutable and permanently bound to one revision/hash; mutable
task lifecycle state is stored separately. A rerun requires a new task and
result identity. Historical evidence may remain `CURRENT` across unrelated
canonical revisions and can satisfy a run completion gate even though its
original task is not rerun.

Runs persist under `workspace/projects/<project_id>/runs/<run_id>/`:

```text
manifest.json
state.json
tasks/<task_id>/definition.json
tasks/<task_id>/state.json
results/<result_id>.json
events/EVT-000001.json
```

The manifest and records are immutable exclusive-write files; run and task
state use atomic replacement. Only explicitly approved proposals can advance
canonical state. If M2 creates a revision and M3 invalidation persistence then
fails, the run follows the new canonical revision, records the iteration and
hash history, becomes `BLOCKED`, and does not guess invalidated nodes.

Run statuses are `CREATED`, `PLANNED`, `RUNNING`, `BLOCKED`, `FAILED`,
`COMPLETED`, and `CANCELLED`. Task statuses are `PENDING`, `READY`, `RUNNING`,
`SUCCEEDED`, `FAILED`, `BLOCKED`, `STALE`, and `SKIPPED`. Completion requires
successful required task control and `CURRENT` M3 evidence for every required
node; missing, `STALE`, or `UNKNOWN` evidence fails closed.

The M4 convergence skeleton uses exact state hashes only. Iteration counts
accepted design-changing canonical revision advancements. It blocks on no state
progress, repeated state hashes, or an exceeded iteration limit. No OpenCode,
LLM, agent, CAD, FEA, optimization, or parallel execution integration exists
in M4. `FakeTaskExecutor` tests the harness independently of an LLM.

## M5 Tool Broker

M5 adds deterministic pure tools behind an exact-version registry and broker:

```text
M4 task binding
      -> ToolContext provenance
      -> explicit typed ToolCall
      -> exact tool name/version lookup
      -> pure deterministic handler
      -> immutable ToolResult
      -> optional explicitly requested declared Evidence
```

`ToolContext` contains only `project_id`, `run_id`, `task_id`,
`bound_revision`, and `bound_state_hash`. Tools do not receive `DesignState`,
canonical snapshots, hidden project lookups, or arbitrary engineering context.
All engineering values are explicit validated inputs.

Task definitions may explicitly allow tools through `allowed_tools`; empty or
missing permissions fail closed. Tool versions are exact and never silently
resolved to the latest implementation. The broker validates task ownership,
canonical binding, execution state, and permission before invoking a handler.

Each invocation persists a `ToolCall` before execution and a separate immutable
`ToolResult` afterward:

```text
workspace/projects/<project_id>/runs/<run_id>/
  tool_calls/<call_id>.json
  tool_results/<result_id>.json
```

Tool records contain immutable execution provenance and input/output hashes only;
they do not duplicate mutable run-control authority from `state.json`.

The initial tools are `mechcad-calc-torque`,
`mechcad-calc-spur-gear-geometry`, `mechcad-check-envelope`, and
`mechcad-apply-dimension-compensation`. They do not infer safety factors,
material properties, shrinkage, tolerances, stress, friction, efficiency, or
ratings. Evidence is opt-in, requires a successful result, and is restricted to
dependency nodes declared by the exact tool registration. Evidence carries
optional tool/result and input/output hash provenance while remaining compatible
with existing M0-M4 records.

## M5.5A Backend Foundation

M5.5A prepares a trusted backend boundary without adding external engineering
libraries or performing external calculations:

```text
ToolBroker
    -> MechCAD Tool
    -> trusted Backend Adapter
    -> external engineering library
    -> normalized MechCAD result
```

`BackendIdentity` describes what trusted adapter/library is registered. It is
not runtime detection. `BackendHealth` separately reports whether a mapped
distribution is available in the current environment, with statuses
`AVAILABLE`, `UNAVAILABLE`, `INCOMPATIBLE`, and `UNKNOWN`. Detected package
versions never mutate registered identity.

Backend provenance is a single optional structured model:

```text
BackendProvenance
  backend_name
  backend_adapter_version
  library_name
  library_version
  library_source
  library_revision
```

Only normalized scalar provenance crosses ToolResult/Evidence persistence
boundaries. External backend objects cannot enter canonical state or persisted
records.

`BackendRegistry` exposes deterministic `register`, `get`, `list`, and
`find_by_capability` operations. Registrations are explicit trusted Python
objects. There is no dynamic plugin loading, configuration-driven import,
network download, shell execution, or generic backend `execute()` API.

Package inspection uses a fixed logical-library-to-distribution mapping and
`importlib.metadata`; target engineering packages are not imported merely to
check availability. Missing packages produce deterministic `UNAVAILABLE`
health.

No engineering libraries were added to runtime dependencies in M5.5A. The
planned roadmap remains:

```text
M5.5A Backend Foundation
M5.5B Gear Geometry
M5.5C Materials + Structural
M5.5D Search + Optimization
M6A OpenCode Adapter
```

## M5.5C-2A Section Geometry

M5.5C-2A adds an optional `structural` dependency profile for deterministic
geometric cross-section properties. The validated legacy-host profile is
Python 3.12.10 with `sectionproperties==3.10.2`, NumPy `2.3.5`, SciPy `1.18.0`,
matplotlib `3.11.1`, Shapely `2.1.2`, cytriangle `3.0.2`,
more-itertools `11.1.0`, and rich `15.0.0`; `pip check` passed. The project
runtime contract remains Python `>=3.11`, and NumPy remains outside core
dependencies with the structural profile constrained to `<2.4` for the tested
legacy Windows host. This host-specific profile does not claim that newer
Python versions or modern CPU hosts are incompatible.

The C-2A flow is:

```text
Normalized MechCAD section input
        -> SectionPropertiesAdapter
        -> transient sectionproperties Geometry/mesh/Section
        -> normalized geometric result
        -> ToolResult
        -> optional Evidence
```

Supported inputs are rectangles, solid circles, and circular hollow sections.
All dimensions are explicit millimetres. `mesh_size_mm2` is the FEM
triangulation parameter. `discretization_points` is the circular boundary
approximation parameter. Both are persisted only as scalar reproducibility
metadata; Geometry, Shapely, mesh, Section, and FEM objects never cross the
adapter boundary or enter ToolResult, Evidence, Run, DesignState, or artifact
metadata.

MechCAD axes are `x = horizontal` and `y = vertical`. For a rectangle, width is `b`,
height/depth is `d`, and sectionproperties is called as
`rectangular_section(d=height_mm, b=width_mm)`. The adapter retrieves
production centroids from `section.get_c()` after
`calculate_geometric_properties()`, and retrieves `(Ixx, Iyy, Ixy)` directly
from `section.get_ic()` without swapping axes. The independent rectangle
oracles are `A=b*h`, `Ixx=b*h^3/12`, `Iyy=h*b^3/12`, and `Ixy=0`. Circle and
hollow-circle oracles use the corresponding pi formulas. Circle residuals are
boundary-discretization error from finite `n`; increasing `n` improves or
preserves agreement with the analytic oracle. Rectangle coarse/fine mesh
comparisons check expected mesh independence for these geometric quantities;
they are not FEM convergence proofs for future analyses.

C-2A is geometric only. It deliberately does not implement material
integration, bd_materials consumption, EA/EI, mass-per-length, warping,
torsion, shear centre, shear areas, stress, plastic properties, yield checks,
safety factors, or FEA structures. Those require separate controlled phases.

## M5.5C-2B Section Warping and Torsion

M5.5C-2B extends the same `SectionPropertiesAdapter` to a narrow,
material-independent warping analysis for rectangles, solid circles, and
concentric hollow circles. C-2A geometric properties use
`calculate_geometric_properties()` only. C-2B requires that operation first,
then calls the validated upstream
`calculate_warping_properties(solver_type="direct")` sequence.

The adapter exposes only these verified public getters:

```text
get_j()      -> St. Venant torsion constant J, mm^4
get_sc()     -> global shear-centre coordinates (x_se, y_se), mm
get_as()     -> centroidal shear areas (a_sx, a_sy), mm^2
get_gamma()  -> warping constant Gamma, mm^6
```

No `bd_materials` values or custom `sectionproperties.pre.Material` objects are
supplied. This preserves the default homogeneous, non-composite geometric
behavior and avoids elastic-modulus-weighted torsion or warping quantities.

The adapter version is `0.2.0`, with capabilities
`structural.cross_section.geometry` and `structural.cross_section.warping`.
Historical 0.1.0 provenance remains valid and is not rewritten.

Every calculation uses `solver_type = `direct`` and two deterministic mesh levels:
`coarse_mesh_size_mm2 = input.mesh_size_mm2` and
`fine_mesh_size_mm2 = input.mesh_size_mm2 / 4`. The normalized result uses the
fine result only after fail-closed checks. The initial validated thresholds are
`1e-3` relative for J, nonzero Gamma, and both shear areas, `1e-6` absolute for
near-zero Gamma, and `1e-4 mm` absolute for the symmetry shear-centre check.
Convergence metadata records both mesh sizes, scalar coarse/fine values,
deltas, tolerances, solver type, and status. A failed convergence check creates
a failed ToolResult and no Evidence; it never silently publishes the fine
result or loops adaptively.

For independent validation, circles use `J = pi*d^4/32` and hollow circles
use `J = pi*(Do^4-Di^4)/32`. Symmetric sections cross-check shear centre
against the C-2A centroid convention. Rectangle J uses convergence,
positivity, repeatability, and symmetry checks rather than an unverified
approximate analytic formula. The checked public API reports disconnected
geometry as invalid for warping analysis; C-2B supports only the connected
library shapes listed above.

C-2B remains geometric/material-independent. It does not implement stress,
plastic analysis, material integration, EA, EI, mass per length, buckling,
beam solving, 3D FEA, or optimization. C-3 is the future controlled material x
section integration phase.

## M5.5C-3A Preliminary Section Integration

C-3A combines persisted normalized C-1 material facts with persisted C-2A
geometry facts and optional C-2B warping facts:

```text
material ToolResult ID
section geometry ToolResult ID
optional warping ToolResult ID
        -> immutable source resolution and verification
        -> pure native MechCAD calculator
        -> PreliminarySectionEngineeringResult
        -> ToolResult / optional Evidence
```

The public operation accepts only result IDs. It does not accept caller-supplied
copies of historical normalized outputs. Each source is reloaded from immutable
run persistence and verified for existence, `SUCCEEDED` status, expected tool
name/version, project, run, task binding, revision, state hash, and exact
`output_hash` before its persisted output is parsed. Contributing records retain
result ID, source task ID, tool identity, project/run, revision/hash, output hash,
and the original BackendProvenance. Source task IDs are provenance only and do
not need to equal the current integration task.

The pure calculator has no ToolBroker, RunStore, filesystem, `bd_materials`, or
`sectionproperties` access. It consumes only normalized MechCAD models and
performs native deterministic arithmetic. The integration itself has no single
backend provenance; its ToolResult backend provenance is `None`, while
contributing source provenance remains structured in the normalized output.

All five outputs always exist as explicit status-bearing values:

```text
mass_per_length       -> kg/m
axial_rigidity_ea     -> N
bending_rigidity_eix  -> N*mm^2
bending_rigidity_eiy  -> N*mm^2
torsional_rigidity_gj -> N*mm^2
```

Ranges remain ranges and no midpoint is fabricated. Density must be exactly
`kg/m^3`; elastic and explicit shear modulus must be exactly `GPa`; section area
is `mm^2`, second moments and J are `mm^4`. GPa is explicitly converted to
N/mm^2 by multiplying by 1000. Unsupported units fail closed.

Missing density produces an explicit unavailable mass value while valid E still
produces EA/EIx/EIy. Missing E produces a successful partial result with mass
available and all stiffness values unavailable. GJ is available only when both
an explicit normalized shear modulus and a valid persisted C-2B J are supplied;
otherwise it is `UNAVAILABLE` with `SHEAR_MODULUS_UNAVAILABLE` or
`TORSION_CONSTANT_UNAVAILABLE`. E and Poisson ratio are never used to derive G.

Derived authority inherits the material authority. Typical `bd_materials` data
therefore remains `TYPICAL_REFERENCE`; deterministic arithmetic never upgrades
it. Assumptions include `HOMOGENEOUS_SECTION` and
`ISOTROPIC_LINEAR_ELASTIC_PRELIMINARY`. Printed-material direction, layers,
infill, moisture, calibration, and shrink compensation are not represented.

Partial success is distinct from structural Evidence completeness. A successful
partial ToolResult does not create `analysis.structural` Evidence unless EA,
EIx, and EIy are all `AVAILABLE`. Unavailable mass or GJ does not block Evidence
when those three stiffness outputs are available. Source-integrity failures,
binding mismatches, malformed values, and unsupported units fail the ToolResult
and create no Evidence.

C-3A computes mass and preliminary stiffness envelopes only. It does not
implement stress, strength, yield, load cases, safety factors, buckling, fatigue,
material selection, manufacturing profiles, or optimization. C-3B is the future
controlled load/stress/allowable semantics phase and is not implemented.

## M6A-1 Agent Gateway Foundation

M6A-1 introduces the deterministic boundary for future reasoning agents without
invoking OpenCode or an LLM:

```text
M4 RunTask
    -> AgentGateway
    -> ContextBuilder
    -> AgentAdapter protocol
    -> FakeAgentAdapter
    -> structured AgentResponsePayload
    -> immutable AgentResult
```

The context is minimal and read-only. It contains the exact persisted canonical
DesignState revision, project/run/task identity, revision, state hash, immutable
task objective/instructions, selected canonical requirement/constraint records,
and selected persisted Evidence resolved by explicit Evidence IDs. The builder
verifies each Evidence record's binding and M3 `CURRENT` freshness, then creates
an `AgentEvidenceSummary`; callers cannot supply arbitrary summary text. Unknown,
stale, mismatched, or unknown-freshness Evidence is rejected. It does not dump
the workspace or automatically include all Evidence or ToolResults. Context
hashes use canonical JSON.

The only agent registered in M6A-1 is `mechcad-test-agent@1.0`. Agent registry
lookup is exact by name and version; there is no latest fallback, plugin
discovery, dynamic import, or external runtime. `FakeAgentAdapter` returns
deterministic findings or configured structured `ChangeProposal`, `Issue`, and
`ConstraintRequest` objects. It cannot execute tools, Python, shell, network
requests, or filesystem operations.

Agent records are persisted separately from M4 authority:

```text
projects/<project_id>/runs/<run_id>/agents/
    invocations/<invocation_id>.json
    results/<result_id>.json
```

Invocation records are written before adapter execution. Invocations and results
are immutable exclusive-write records with deterministic request/response
hashes. An AgentResult is not canonical DesignState and is not Evidence.

The gateway rechecks run/task/revision/state-hash binding after adapter return.
If canonical binding advanced during execution, the historical result is stored
as `STALE`; it cannot apply a proposal, mutate DesignState, or create current
Evidence. Returned `ChangeProposal` objects are checked immediately against the
exact invocation revision/state hash. A mismatch produces FAILED with
`RESPONSE_BINDING_MISMATCH`. Matching proposals remain proposals and must later pass
the existing M2 stale, ownership, operation, and resulting-state validation.

M6A-1 deliberately excludes real OpenCode/LLM execution. M6A-2 may add a real
adapter round trip. M6B may add the first engineering agent,
`mechcad-transmission`. C-3B remains the future load/stress/safety phase.

## M6B-1 Transmission Reasoning Agent

M6B-1 adds the first real engineering reasoning boundary:

```text
authoritative DesignState / selected CURRENT Evidence
    -> mechcad-transmission reasoning
    -> findings / Issues / ConstraintRequests / proposals
    -> immutable AgentResult
```

`mechcad-transmission@1.0` is trusted by exact MechCAD registry identity and is
explicitly bound to the project-scoped `mechcad-transmission` OpenCode agent.
The project agent is reasoning-only with deny-all permissions; it receives no
repository access and cannot invoke tools, shell, filesystem, MCP, or other
agents. M6B-1 uses the existing `ContextBuilder` and only caller-selected
requirements, constraints, and CURRENT Evidence.

Transmission reasoning is not deterministic Evidence. Missing engineering data
produces a `ConstraintRequest`; a conflict revealed by supplied authoritative
context produces an `Issue`. Findings are plain strings. Proposals remain
proposals and are never applied automatically. The first fixture intentionally
returns zero ChangeProposals and does not create Evidence or mutate
`DesignState`.

The ownership rule `/components/*/transmission` is reserved-but-inactive
ownership. Because `Component.transmission` does not exist in the canonical
Pydantic model, the path is not currently representable or writable. M6B-1 does
not use `Component.description` or another generic field as a substitute. A
future canonical transmission model requires separate design and approval.

M6B-1 does not add agent tool calling, automatic iteration, stress/load-case
C-3B, or direct ToolBroker orchestration. Those remain later milestones.

## M5.5B-1 Pinned Gear Geometry

M5.5B-1 adds an optional, geometry-only py_gearworks backend. Core MechCAD
installation remains independent of NumPy, SciPy, build123d, and py_gearworks.
The `gear` extra uses the exact upstream commit
`2fc2a13d82a9997a65f30c870498f0bb3be62318` from
`GarryBGoode/py_gearworks`, `build123d==0.11.1`, and NumPy constrained to
`>=2,<2.4` for the validated legacy-CPU profile. The tested runtime resolved
Python 3.13.15, NumPy 2.3.5, SciPy 1.18.0, build123d 0.11.1, and
cadquery-ocp-novtk 7.9.3.1.1.

The validated flow is:

```text
ToolBroker
    -> mechcad-calc-spur-gear-geometry-gearworks
    -> PyGearworksAdapter 0.1.0
    -> py_gearworks 0.0.18 at exact Git revision
    -> build123d internally
    -> normalized Pydantic gear geometry
    -> ToolResult / optional Evidence
```

The adapter exposes standard external spur geometry and spur-pair geometry only.
It is not a strength, efficiency, fatigue, pitting, or lifetime solver. Native
`mechcad-calc-spur-gear-geometry` remains available as the simple reference
calculator and is cross-validated against normalized backend pitch diameters,
ratio, and nominal center distance.

The adapter healthcheck verifies the runtime dependency profile without importing
third-party packages: py_gearworks 0.0.18, build123d 0.11.1, NumPy `>=2,<2.4`,
and SciPy `>=1.10.1`. Backend provenance records the detected runtime library
version and exact Git revision. Backend objects never enter ToolCall, ToolResult,
Evidence, Run, or DesignState persistence. CAD artifact persistence and general
CAD generation remain deferred to M5.5B-2.

The NumPy 2.4+ x86-64-v2 baseline was not executable on the tested AMD Phenom II
X6 1045T Windows host (`STATUS_ILLEGAL_INSTRUCTION`, `0xc000001d`). NumPy 2.3.5
passed the numeric and full gear-stack smoke tests on that host. This is a
host/profile validation constraint, not a change to the core Python `>=3.11`
requirement and not a claim that newer CPUs or operating systems are incompatible.

## M5.5B-2 Gear CAD Artifacts

M5.5B-2 converts accepted external spur geometry into derived STEP and STL
artifacts through the existing ToolBroker boundary:

```text
normalized gear input
    -> mechcad-build-spur-gear-cad
    -> PyGearworksAdapter
    -> transient py_gearworks/build123d Part
    -> explicit central bore subtraction
    -> STEP/STL exporter
    -> immutable hashed artifact metadata
```

Artifacts are stored below the workspace in
`projects/<project_id>/runs/<run_id>/artifacts/<artifact_id>/` with the artifact
file and `metadata.json`.

The previous global `projects/_artifacts/<artifact_id>/` layout is not retained
as a compatibility alias. Publication requires trusted project/run/task binding
from ToolContext; user-supplied absolute paths and traversal/separator tricks are
rejected. Artifact bytes and metadata are immutable exclusive-write records, and
the uniqueness boundary is `(project_id, run_id, artifact_id)`, allowing the same
artifact ID to exist independently in separate runs.
Metadata records the safe workspace-relative path, exact SHA-256 and byte size,
tool/version, bound revision/state hash, normalized input hash, and structured
backend provenance. Artifact bytes and metadata are exclusive-write and are not
canonical DesignState or Evidence content. Optional Evidence may reference a
successful artifact-producing result without embedding file bytes.

The supported CAD operations are external spur gear generation and a narrow spur
pair operation that records two independent artifact results plus a nominal
relative transform. STEP is the authoritative interchange output; STL is a
derived mesh output. No arbitrary output paths, internal gears, assemblies,
general CAD scripts, strength calculations, or optimization are implemented.

## M5.5C-1 Typical Material Data

The optional `materials` extra uses `bd-materials==0.2.4` from
`bernhard-42/bd_materials`, with `threejs-materials==1.2.3` and
`webcolors==24.8.0` resolved by that package. It remains separate from the
optional `gear` extra and is not a core dependency.

`BdMaterialsAdapter` exposes only the capability
`material.typical_properties`. Its results always carry
`MaterialDataAuthority.TYPICAL_REFERENCE`. The authority ladder is represented
as:

```text
TYPICAL_REFERENCE
        -> lower-authority early-design reference data
SUPPLIER_DATASHEET
MEASURED
USER_OVERRIDE
```

The latter three are domain semantics only in M5.5C-1; no ingestion or override
execution paths exist. Catalog ranges preserve min/max without inventing a
midpoint. Scalar density is explicitly represented as a representative typical
value. Missing properties remain `MISSING`; upstream `NOT_SUITABLE` values remain
`NOT_SUITABLE`; neither becomes zero, NaN, or a fabricated engineering value.

The tool `mechcad-material-typical-properties` requires an explicit material
identity and returns normalized mechanical/thermal properties, canonical identity,
authority, and backend provenance. Family aliases such as `aluminum` expose the
resolved canonical grade and emit a warning rather than silently becoming an
exact material selection. `mechcad-calc-mass-from-typical-material` uses only an
available representative density and marks the result as a typical reference
estimate.

`bd_materials` appearance/PBR/finish/process wrappers never cross the MechCAD
boundary. The backend is not authoritative for supplier data, measured values,
FDM shrink compensation, print calibration, tolerances, anisotropic strength,
or manufacturing process corrections. Section properties, structural analysis,
materials selection, optimization, and M5.5C-2/C-3 remain out of scope.
## OpenCode Response Modes

The OpenCode adapter has two explicitly selected response modes:

- `NATIVE_JSON_SCHEMA` is the default. It sends OpenCode's native JSON Schema
  format and accepts only `info.structured_output`. Structured-output errors,
  missing structured output, and invalid authoritative output fail closed.
- `VALIDATED_JSON_TEXT` is a separate transport contract for profiles whose
  OpenCode backend cannot return native structured output. It omits the native
  format envelope, injects the generated `AgentAuthoredResponsePayload` schema
  into the deterministic output contract, and validates the complete ordered
  text parts as one JSON document.

`VALIDATED_JSON_TEXT` is not an automatic fallback. It must be selected in
trusted adapter configuration before invocation. Text is not trusted because it
is JSON: it becomes acceptable only after whole-document JSON parsing and
strict `AgentAuthoredResponsePayload` validation. Markdown fences, prose,
multiple documents, extra fields, repair, extraction, and response merging are
rejected.

Canonical IDs, revision/state binding, statuses, proposal actor/base binding,
materialization, and state mutation remain harness-owned. The model cannot
authorize those fields. The generated Pydantic schema is the single schema
source of truth, and response mode plus schema hash are retained in normal
execution provenance.

The mode exists because OpenCode `1.18.18` with
`screenpipe/gpt-5.6-luna` repeatedly returned `StructuredOutputError` without
`info.structured_output`, including with `retryCount=2`, while ordinary text
could contain semantically valid authored JSON. This compatibility mode does
not weaken or rename the native fail-closed mode.
