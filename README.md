# MechCAD Harness

MechCAD Harness M0 is the typed Python foundation for a future engineering
workflow system. It provides readable identifiers, minimal Pydantic v2 domain
models, placeholder YAML configuration, and tests.

## M0 Boundary

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
