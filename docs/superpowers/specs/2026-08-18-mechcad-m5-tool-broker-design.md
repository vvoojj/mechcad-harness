# MechCAD Harness M5 Tool Broker Design

## Goal

M5 adds deterministic tool registration, exact-version dispatch, immutable
request/result audit records, explicit task permissions, and four pure initial
mechanical tools. M4 remains the run-control authority.

## Boundaries

Tools receive no `DesignState`, canonical snapshot, project lookup, chat
history, or hidden engineering context. `ToolContext` contains only:

```text
project_id
run_id
task_id
bound_revision
bound_state_hash
```

All engineering values are supplied through validated typed input models. There
are no agents, OpenCode integration, LLMs, CAD, FEA, MCP, SQL, dynamic plugins,
parallelism, optimization, or autonomous tool selection.

## Registry And Permissions

`ToolRegistry` resolves an exact `(tool_name, tool_version)` pair. It never
falls back to a latest version. Each registration contains immutable metadata,
typed input/output models, a pure handler, and declared evidence nodes it may
produce. Duplicate registrations are rejected.

`TaskDefinition` gains `allowed_tools: tuple[str, ...] = ()`. The list contains
exact tool names with optional exact versions represented by the request; an
empty list means no tool access. The broker rejects every request not explicitly
permitted by the immutable task definition. No agent-level permission model is
added.

## Calls And Results

Every invocation persists two immutable records. The `ToolCall` is written
before the handler runs:

```text
tool_calls/<call_id>.json
tool_results/<result_id>.json
```

`ToolCall` records the validated normalized input, input hash, exact tool
version, task/run identity, and immutable revision/hash binding. `ToolResult`
references the call and records status, exact binding, input hash, successful
typed output/output hash, or a structured error. Failed execution preserves the
call and writes a failed result whenever persistence remains possible.

These records duplicate only immutable execution provenance. They never become
authoritative copies of active revision, run status, iteration, or state history.

## Canonical Binding

Before a call is persisted or executed, the broker verifies the task belongs to
the requested run, the context exactly matches the immutable task binding, the
bound revision/hash resolves to an intact canonical snapshot, the task is
currently executable, and the exact tool is allowed. A task bound to an old
revision cannot invoke a tool after canonical advancement.

## Built-In Tools

All four handlers are pure deterministic functions:

- `mechcad-calc-torque`:
  - `nominal_torque_nm = force_n * lever_arm_m`
  - `design_torque_nm = nominal_torque_nm * safety_factor`
- `mechcad-calc-spur-gear-geometry`:
  - explicit module and tooth counts produce pitch diameters, ratio, and center distance.
- `mechcad-check-envelope`:
  - axis-aligned fit check from explicit part and maximum dimensions;
  - no collision detection.
- `mechcad-apply-dimension-compensation`:
  - `compensated_mm = nominal_mm + compensation_mm`;
  - no material or tolerance inference.

All positive physical inputs are explicitly validated. No tool invents safety
factors, material properties, shrinkage, tolerances, stress, friction,
efficiency, ratings, or other engineering values.

## Evidence Integration

Tool registration declares allowed evidence nodes. Evidence is created only
when the caller explicitly requests a node after a successful result. The node
must be declared by the tool. Failed results produce no evidence.

Evidence keeps existing fields compatible and adds optional fields:

```text
producer_type
producer_name
producer_version
producer_result_id
input_hash
output_hash
```

Evidence preserves the exact result revision/hash and references the result ID.
The existing M3 `EvidenceStore` remains responsible for persistence and node
validation.

## Persistence Safety

Tool calls/results use exclusive immutable writes and are stored below the
existing M4 run directory. `RunManifest` and mutable `state.json` boundaries
are unchanged. Tool execution never mutates canonical revision snapshots.
