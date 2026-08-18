# MechCAD Harness M4 Run Control Design

## Goal

M4 adds a deterministic execution-control layer around the accepted M0-M3
boundaries. It creates runs bound to canonical state, validates explicit task
DAGs, executes tasks through an abstract executor, persists immutable history,
and gates completion on M3 current evidence.

## Boundaries

M4 does not add OpenCode integration, agents, LLMs, CAD, FEA, calculators,
parallel execution, databases, optimization, or autonomous planning or proposal
approval.

`DesignState` remains canonical. M4 composes `StateManager`, `ChangeEngine`,
and `EvidenceStore`; it does not reimplement them. The M3 engineering
`DependencyGraph` and the M4 task DAG are separate graphs.

## Run And Task Records

A run stores immutable initial provenance and mutable active control state.
The initial project, revision, and state hash never change. Active revision and
hash follow canonical state only after an explicitly approved proposal creates a
new revision.

Task definitions and task lifecycle state are deliberately separate:

```text
projects/<project_id>/runs/<run_id>/
  manifest.json
  state.json
  tasks/<task_id>/definition.json
  tasks/<task_id>/state.json
  results/<result_id>.json
  events/EVT-000001.json
```

Definitions and results are immutable exclusive-write records. Task state and
run state are atomically replaced mutable records. Existing task definitions
are never rebound or reset. A rerun requires a new task ID and result ID.

## Scheduler And Executor

The scheduler validates all explicit task dependencies, rejects unknown IDs and
cycles, and exposes a stable topological order. A task is `READY` only when all
prerequisites are `SUCCEEDED`; permanently failed prerequisites block
downstream tasks. Execution is single-threaded and deterministic.

`TaskExecutor` is a protocol. M4 production code does not know the execution
runtime. Tests use deterministic fake executors. An execution result is accepted
only when its task ID, revision, and state hash exactly match the immutable task
definition.

## Revision Advancement

`apply_approved_proposal` delegates mutation to M2. As soon as M2 returns, the
canonical project is at the new revision. M4 updates the run active revision and
hash, records the hash in convergence history, and increments the iteration,
even if subsequent M3 invalidation persistence fails.

If invalidation persistence fails, M4 does not roll back the valid canonical
revision and does not guess affected nodes. It records the failure, blocks the
run, and leaves M3 freshness fail-closed as `UNKNOWN`.

When invalidation succeeds, only pending or ready tasks affected by the
invalidation are marked `STALE`. Completed task and result history is never
rewritten. Evidence from an old completed task may remain `CURRENT` across an
unrelated revision and can satisfy completion.

## Completion And Convergence

Iteration equals the number of accepted design-changing canonical revision
advancements in the run. Read-only execution and failed proposals do not
increment it.

Completion requires the run not to be blocked or failed, all required task
control conditions to be satisfied, and at least one `CURRENT` M3 evidence
record for every required evidence node. `STALE`, `UNKNOWN`, or missing evidence
never satisfies the gate.

After each accepted revision, exact hashes are checked in this order:

1. `NO_STATE_PROGRESS` when the new hash equals the previous active hash.
2. `STATE_CYCLE` when the new hash appeared earlier in this run's history.
3. `ITERATION_LIMIT` when the new iteration exceeds `max_iterations`.

Any convergence block preserves the canonical revision.

## Resume And Integrity

Resume loads and verifies the immutable manifest, mutable state, project
identity, active canonical revision/hash, task definitions and states, and
loaded result/task bindings. Corruption or inconsistency fails closed. Resume
never repairs files.

## Events

Events are small immutable JSON records with sequential names
`EVT-000001.json`, allocated by scanning existing events in the single-threaded
controller. Existing event files are never overwritten.
