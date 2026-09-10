# MechCAD M4 Git Reconstruction Report

## 1. Verdict

```text
M4_CAPABILITY_EXISTENCE: YES
M4_IMPLEMENTATION_STATUS: IMPLEMENTED_WITH_DEVIATIONS
M4_SPEC_CONFORMANCE: CONFORMANT_WITH_DEVIATIONS
M4_HISTORICAL_EXECUTION_EVIDENCE: NOT_RETAINED
RECONSTRUCTION_CONFIDENCE: HIGH
```

Committed implementation and committed tests establish M4 capability. The
absence of retained execution transcripts affects only historical execution
verification, not implementation status.

## 2. Commit Boundary

```text
M3_PREDECESSOR_COMMIT: df584f00b240ef8086b99d408f76f42a90c4b517
M4_START_COMMIT: a958c397d974153d5712ff5bb2e35df7e4966c4f
M4_IMPLEMENTATION_COMMITS:
- a958c397d974153d5712ff5bb2e35df7e4966c4f
M4_COMPLETION_TREE: a958c397d974153d5712ff5bb2e35df7e4966c4f
M5_START_COMMIT: 6cbade0ea53f1652d44bb92f92831a0c8daf62c5
GIT_HISTORY_STATUS: SINGLE_COMMIT_PURE_M4
```

`a958c397` is `feat: add M4 run control`. Its direct parent is M3. The next
commit is M5 and is classified `PURE_M5`.

## 3. Artifact Inventory

| Artifact | First commit | Role | Temporal status |
| --- | --- | --- | --- |
| `docs/superpowers/specs/2026-08-18-mechcad-m4-run-control-design.md` | `a958c397` | Design/spec | Contemporary |
| `docs/superpowers/plans/2026-08-18-mechcad-m4-run-control.md` | `a958c397` | Implementation plan | Contemporary |
| M4 section in `README.md` | `a958c397` | Milestone narrative | Contemporary |
| `src/mechcad_harness/runs/` | `a958c397` | Committed implementation | Contemporary |
| `tests/unit/test_runs.py` | `a958c397` | Committed M4 tests | Contemporary |
| architecture, audit, and reference documents | Later commits | Retrospective/current evidence | Retrospective |

No M4-specific completion report, acceptance record, pytest/compileall/diff
transcript, or CI artifact was retained.

## 4. M3 -> M4 Boundary

The M3-to-M4 boundary is `PURE_M4`: M4 adds its own package, documentation,
README narrative, and tests without modifying M3 dependency implementation or
configuration.

## 5. Intended M4 Architecture

```text
Canonical State -> Run -> RunPlan -> Task DAG -> TaskExecutor
-> immutable result / Evidence -> M2 proposal -> new revision
-> M3 invalidation -> iteration / convergence -> completion gate
```

M1 owns canonical revision persistence, M2 canonical mutation, M3 derived
invalidation and Evidence freshness, and M4 deterministic orchestration. M4
was explicitly scoped to exclude execution runtimes and later integrations.

## 6. Actual M4 Architecture

```text
RunController -> StateManager, ChangeEngine, EvidenceStore, RunStore
TaskScheduler -> task execution-prerequisite DAG
TaskExecutor -> Protocol boundary
ConvergenceTracker -> exact state-hash checks
FakeTaskExecutor -> deterministic in-package test support
```

The M4 package consists of `models.py`, `errors.py`, `persistence.py`,
`scheduler.py`, `executor.py`, `convergence.py`, `controller.py`, and
`__init__.py`.

## 7. M4-Owned Historical Files

M4-owned production files are the complete `runs/` package above. M4-owned
tests are `tests/unit/test_runs.py`. The M4 design, plan, and README section
are documentation changes. M1-M3 packages were not modified; M4 integrates
them through their existing interfaces.

## 8. Run / RunPlan / RunManifest Models

`Run` carries initial and active revision/hash, status, iteration, maximum
iterations, exact hash history, and timestamps. `RunManifest` contains only
immutable initial provenance. `RunPlan` contains run ID, required evidence
nodes, and plan task IDs. `TaskDefinition`, `TaskState`, `TaskContext`,
`TaskExecutionResult`, and `RunEvent` are separate typed records.

## 9. Immutable Provenance vs Mutable Control State

Immutable exclusive-write records are manifest, task definition, result, and
event files. Mutable atomic-replacement records are run and task state files.
Manifest, definitions, results, and events reject overwrite.

Deviation: `create_plan()` writes `plan.json` with `exclusive=False`; it is
mutable in practice. `RunStore.write_plan()` is unused and derives the project
directory incorrectly from the generated `RUN-<uuid>` ID.

```text
PLAN_PERSISTENCE_STATUS: IMPLEMENTED_WITH_DEVIATIONS
```

## 10. Filesystem Persistence Layout

```text
projects/<project_id>/runs/<run_id>/
  manifest.json
  state.json
  plan.json
  tasks/<task_id>/definition.json
  tasks/<task_id>/state.json
  results/<result_id>.json
  events/EVT-000001.json
```

Directories are lazy. `RunStore` writes deterministic JSON through a temporary
file, flushes and fsyncs it, and calls `os.replace()`. The guarantee is atomic
replacement per mutable file, not a multi-file transaction.

## 11. Run Status Behavior

Enum values are `CREATED`, `PLANNED`, `RUNNING`, `BLOCKED`, `FAILED`,
`COMPLETED`, and `CANCELLED`.

Actual controller flow sets creation to `CREATED`, planning to `PLANNED`,
completion to `COMPLETED`, and convergence/invalidation failure to `BLOCKED`.
There is no centralized transition table, no controller path sets `RUNNING`,
and terminal status does not generally prevent later controller mutation.

```text
RUN_STATE_MACHINE: IMPLEMENTED_WITH_DEVIATIONS
```

## 12. TaskDefinition

Historical fields are `task_id`, `run_id`, `task_type`, `objective`,
`bound_revision`, `bound_state_hash`, `depends_on`, `required_nodes`,
`produces_nodes`, and `created_at`. Definitions are exclusive-write and an
existing definition cannot be rebound through ordinary API use. A rerun needs
a new task identity.

## 13. TaskState Behavior

Task statuses are `PENDING`, `READY`, `RUNNING`, `SUCCEEDED`, `FAILED`,
`BLOCKED`, `STALE`, and `SKIPPED`.

The scheduler treats `READY` as eligibility rather than a persisted lifecycle
transition. Execution persists `RUNNING` and then normally result status.
Failed/blocked dependencies can persistently block pending/ready dependents;
successful invalidation can stale only pending/ready tasks. Completed states
are not reset.

## 14. Task DAG vs M3 DependencyGraph

M4 task DAG nodes are task identities and edges are execution prerequisites.
M3 dependency graph nodes are engineering/Evidence nodes and edges propagate
invalidation. The committed code keeps these graph systems separate.

## 15. Scheduler Validation

`TaskScheduler.ordered()` uses deterministic Kahn ordering. It rejects unknown
dependency IDs, rejects cycles, and treats a self dependency as a cycle. It
does not explicitly reject duplicate dependency entries; duplicate task IDs can
collapse when definitions are mapped by task ID.

## 16. Deterministic Ordering

```text
TASK_ORDER_DETERMINISTIC: YES
```

Zero-indegree and newly eligible tasks, plus candidate traversal, are sorted
lexically by task ID. Independent and diamond-DAG tie resolution is stable.

## 17. Readiness / Blocking Semantics

Readiness requires every prerequisite to be `SUCCEEDED`. `PENDING`, `READY`,
or `RUNNING` prerequisites do not satisfy it. `FAILED`, `BLOCKED`, and `STALE`
suppress readiness. The controller marks downstream tasks `BLOCKED` only for
failed/blocked prerequisites. `STALE` suppresses readiness but is not itself a
downstream-blocking transition. `SKIPPED` does not satisfy success.

## 18. TaskExecutor

```python
TaskExecutor.execute(
    task: TaskDefinition,
    context: TaskContext,
) -> TaskExecutionResult
```

`TaskContext` includes project/run identity, active revision/hash, and the
canonical `DesignState` at that revision. The boundary is a `Protocol`, not a
concrete runtime.

## 19. FakeTaskExecutor

`FakeTaskExecutor` is deterministic in-package test support. Configured task
IDs fail; other tasks succeed and produce M3 Evidence for their produced nodes.
It is not a real agent, LLM, or external execution backend.

## 20. Execution Result Binding

`validate_result()` compares result task ID, bound revision, and bound state
hash with the immutable definition. Any mismatch raises
`StaleTaskResultError`; invalid results cannot normally be accepted as
successful results.

## 21. Result / Evidence Persistence

Results are immutable exclusive-write records containing identity, binding,
status, findings, proposals, Evidence, and issues. Evidence is optional and is
written by `RunController` through `EvidenceStore` after result persistence.

Material deviation: the result record binding is checked, but each contained
Evidence record is not independently validated against task/result provenance.

```text
RESULT_EVIDENCE_BINDING: PARTIAL
```

## 22. RunStore Atomicity / Immutability

`os.replace()` gives per-file mutable replacement under ordinary filesystem
semantics. Exclusive writes reject pre-existing immutable targets. No
multi-record transaction exists: Evidence persistence failure can leave a
durable result while task state remains `RUNNING` until exception handling
attempts to mark it failed.

## 23. Events

`RunEvent` has `event_id`, `event_type`, `payload`, and `created_at`. Names are
allocated by scanning `EVT-*.json` files and writing the next immutable ID.
This is deterministic under the single-threaded controller assumption, not
concurrency-safe across independent writers.

## 24. Run Creation / Planning / Task Addition

`create_run()` reads M1 current state, generates `RUN-<uuid>`, writes immutable
manifest and mutable state, and emits `RUN_CREATED`. Initial and active
revision/hash start equal; callers cannot provide arbitrary creation binding.

`create_plan()` validates the existing DAG and stores sorted task IDs plus
required evidence nodes. `add_task()` requires task binding equal to active run
binding, writes immutable definition and pending state, and emits
`TASK_CREATED`. Dependencies need not exist until planning/scheduling.

## 25. Ready Task Execution

Historical order is:

1. Load definitions and states.
2. Compute ready tasks.
3. Persist `RUNNING` task state.
4. Build `TaskContext`.
5. Invoke executor.
6. Validate result binding.
7. Persist immutable result.
8. Persist Evidence.
9. Persist final task state.
10. Emit success/failure event.

Executor, validation, result, or Evidence errors are caught by the execution
path, which attempts to persist `FAILED` and `TASK_FAILED`.

## 26. Proposal Advancement

```text
DOES_M4_ENFORCE_APPROVED_ONLY_PROPOSAL_ADVANCEMENT: NO
APPROVED_PROPOSAL_GATE: MISSING
```

Despite its public name, `apply_approved_proposal()` never checks
`proposal.status`; M2 also does not. Historical M4 tests apply
`ProposalStatus.DRAFT` proposals successfully. This is a semantic deviation,
not a test-coverage gap.

## 27. Canonical Revision Advancement

Actual order:

1. `ChangeEngine.apply_proposal()` creates the canonical revision.
2. M4 records active revision/hash, iteration, and history through convergence.
3. Run state is persisted and `REVISION_ADVANCED` is emitted.
4. M3 invalidation is built and persisted.
5. Relevant pending/ready tasks may become stale.

## 28. M3 Integration

M4 is the first retained production orchestration layer that explicitly maps:

```text
AppliedChangeResult
    -> EvidenceStore.build_invalidation()
    -> EvidenceStore.record_invalidation()
```

It composes M3 without changing its semantics.

## 29. M3 Failure After Canonical Success

```text
M4_FOLLOWS_CANONICAL_REALITY_ON_M3_FAILURE: YES
```

When M2 creates a revision but M3 invalidation persistence fails, canonical
state is preserved. Active run binding, iteration, and history remain advanced;
the run becomes `BLOCKED`, emits `RUN_BLOCKED`, and does not guess impact or
speculatively stale tasks.

## 30. Task Staleness

After successful invalidation, only `PENDING` or `READY` tasks are marked
`STALE` when invalidated nodes intersect `required_nodes` or `produces_nodes`.
`RUNNING`, `SUCCEEDED`, `FAILED`, `BLOCKED`, and `SKIPPED` are preserved.
Unaffected pending tasks remain pending.

## 31. Historical Evidence Reuse

```text
CAN_CURRENT_HISTORICAL_EVIDENCE_SATISFY_M4_COMPLETION: YES
```

Evidence from an older revision can satisfy M4 completion if complete M3
history establishes it is still `CURRENT` across later unrelated revisions.

## 32. Completion Gate

Completion requires an existing `plan.json`, a run not `BLOCKED`, `FAILED`, or
`CANCELLED`, every captured plan task `SUCCEEDED`, and M3 current Evidence for
every plan-required node. Missing, stale, and unknown Evidence fail closed.
Tasks added after the plan are not automatically part of its required task set.

## 33. Iteration Semantics

Iteration advances for accepted canonical revision advancement, including an
advancement followed by M3 invalidation persistence failure. Ordinary task
execution and failed proposals do not increment it.

## 34. Convergence

Checks are exact-hash and ordered:

1. `NO_STATE_PROGRESS`: new hash equals active hash.
2. `STATE_CYCLE`: new hash appears in any prior run hash history.
3. `ITERATION_LIMIT`: proposed iteration is greater than maximum.

```text
CONVERGENCE_CHECK_ORDER_CONFIRMED: YES
```

The threshold is `iteration > max_iterations`, not `>=`. Controller recovery
preserves the already-created canonical revision and blocks the run. Tests cover
behavior but do not independently assert check-order/error-label precedence.

## 35. Resume / Integrity

```text
RESUME_REPAIRS_FILES: NO
RESUME_INTEGRITY: IMPLEMENTED_WITH_DEVIATIONS
```

Resume verifies manifest/run/project identity, active canonical snapshot
revision/hash, task-state binding to definition, and referenced result binding.
Missing, malformed, or schema-invalid required records fail closed as
`RunIntegrityError`; no repair occurs.

It does not fully validate plan content, manifest/state initial provenance,
events, orphan results, Evidence, dependency-history completeness, or
iteration/hash-history consistency.

## 36. Event / Resume Relationship

`state.json` is authoritative mutable state. Events are immutable audit
history, not an event-sourced state machine. Resume neither reconstructs state
from events nor validates event history.

## 37. Scope Exclusions

Committed M4 adds no OpenCode execution, real agents, LLM runtime, CAD,
FreeCAD, FEA, MuJoCo, MCP, SQL/database persistence, tools/calculators,
optimization, parallel/distributed workers, autonomous planning, or external
services. Automatic proposal approval is also absent; the missing approval
check is not an automatic approval implementation.

## 38. Historical M4 Tests

```text
M4_TEST_FILE: tests/unit/test_runs.py
M4_TEST_FUNCTION_COUNT: 17
TEST_CODE_IMPLEMENTED: YES
HISTORICAL_EXECUTION_EVIDENCE: NOT_RETAINED
```

Binding and immutability:

- `test_run_binds_exact_canonical_revision_and_manifest_is_immutable`
- `test_manifest_contains_only_immutable_provenance`
- `test_manifest_stays_unchanged_while_mutable_state_advances`
- `test_resume_uses_state_not_mutable_manifest_fields`
- `test_task_definition_is_immutable_and_state_is_separate`

Scheduling and binding:

- `test_scheduler_orders_tasks_and_blocks_failed_dependents`
- `test_scheduler_rejects_unknown_dependencies_and_cycles`
- `test_result_binding_mismatch_fails_closed`

Completion and evidence:

- `test_completion_requires_current_evidence_and_old_unrelated_evidence_reuses`

Revision and invalidation:

- `test_revision_advancement_stales_pending_task_without_rebinding`
- `test_m3_failure_follows_canonical_revision_and_blocks_without_guessing_impact`
- `test_unaffected_pending_task_remains_pending_after_invalidation`

Convergence:

- `test_convergence_rejects_same_hash_progression`
- `test_convergence_detects_cycle_and_iteration_limit`

Resume and rerun:

- `test_resume_verifies_active_revision_and_state_hash`
- `test_rerun_requires_new_task_and_result_identity`

End-to-end:

- `test_end_to_end_fake_executor_revision_replacement`

No pytest parameterization was found. Predecessor tests are not included in
this M4 function count.

## 39. Design / Plan / Implementation Comparison

| Requirement | Design / plan | Committed Git | Test evidence | Classification |
| --- | --- | --- | --- | --- |
| State-bound run provenance | Required | Implemented | Yes | IMPLEMENTED_AS_DESIGNED |
| Immutable manifest | Required | Implemented | Yes | IMPLEMENTED_AS_DESIGNED |
| Mutable state split | Required | Implemented | Yes | IMPLEMENTED_AS_DESIGNED |
| Immutable definitions/results | Required | Implemented | Yes | IMPLEMENTED_AS_DESIGNED |
| Persisted immutable plan | Implied | Overwriteable | No | IMPLEMENTED_WITH_DEVIATIONS |
| Event persistence | Required | Implemented | Indirect | IMPLEMENTED_AS_DESIGNED |
| DAG validation/order | Kahn required | Sorted Kahn | Partial | IMPLEMENTED_AS_DESIGNED |
| Executor protocol | Required | Implemented | Fake E2E | IMPLEMENTED_AS_DESIGNED |
| Result binding | Required | Implemented | Task-ID branch only | TEST_COVERAGE_GAP |
| Approved-only advancement | Required | Absent | DRAFT proposals succeed | MISSING |
| M2/M3 integration | Required | Implemented | Yes | IMPLEMENTED_AS_DESIGNED |
| M3 failure canonical reality | Required | Implemented | Yes | IMPLEMENTED_AS_DESIGNED |
| Task staleness | Required | Implemented | Yes | IMPLEMENTED_AS_DESIGNED |
| Historical Evidence reuse | Required | Implemented | Yes | IMPLEMENTED_AS_DESIGNED |
| CURRENT-only completion | Required | Implemented | Partial | IMPLEMENTED_AS_DESIGNED |
| Exact convergence/order | Required | Implemented | No order assertion | TEST_COVERAGE_GAP |
| Resume/no repair | Required | Partial integrity checks | Partial | IMPLEMENTED_WITH_DEVIATIONS |
| Scope exclusions | Required | Preserved | Source inspection | IMPLEMENTED_AS_DESIGNED |

## 40. Historical Execution Evidence

```text
HISTORICAL_PYTEST_EVIDENCE: NOT_RETAINED
HISTORICAL_COMPILEALL_EVIDENCE: NOT_RETAINED
HISTORICAL_DIFF_CHECK_EVIDENCE: NOT_RETAINED
HISTORICAL_COMPLETION_RECORD: NOT_RETAINED
HISTORICAL_ACCEPTANCE_RECORD: NOT_RETAINED
```

Unchecked Superpowers-plan verification boxes are not negative implementation
evidence.

## 41. M4 -> M5 Boundary

```text
M5_START_COMMIT: 6cbade0ea53f1652d44bb92f92831a0c8daf62c5
BOUNDARY_CLASSIFICATION: PURE_M5
```

M5 introduces Tool Broker capability and adds `allowed_tools` to
`TaskDefinition`. It does not repair M4 Run Control or modify
`tests/unit/test_runs.py` at the boundary.

## 42. Later Evolution

| M4 foundation | Later state | Evidence |
| --- | --- | --- |
| RunController/run binding | EXTENDED | M8B source-binding support |
| RunStore/persistence | PRESERVED | Later run-directory use |
| Task models | EXTENDED | M5 allowed-tools and later bindings |
| Task DAG/executor boundary | PRESERVED | Later orchestration retains boundary |
| Completion/convergence/resume | MIXED | Later failure handling strengthened |
| Event history | PRESERVED | Remains audit-oriented |

## 43. Unresolved Questions

- Retained Git history does not prove whether M4-era pytest, compileall, or
  diff-check commands were run.
- No separate explicit M4 completion or acceptance record was retained.
- Concurrent event allocation is neither proven nor supported by the M4 code.

These are evidence gaps, not implementation failures.

## 44. Final Reconstructed Classification

```text
M4_CAPABILITY_STATUS: IMPLEMENTED_WITH_DEVIATIONS
M4_GIT_HISTORY_STATUS: SINGLE_COMMIT_PURE_M4
AT_TIME_IMPLEMENTATION_STATUS: IMPLEMENTED_WITH_DEVIATIONS
SPEC_CONFORMANCE_STATUS: CONFORMANT_WITH_DEVIATIONS
HISTORICAL_EXECUTION_EVIDENCE: NOT_RETAINED
CURRENT_HISTORICAL_STATUS: PRESERVED_AND_EXTENDED
```

## 45. Repository Safety Observations

The forensic investigation began with an already dirty worktree containing
unrelated modified and untracked artifacts. It made no changes, staged no
files, and created no commit. This documentation-persistence pass is limited to
the M4 reconstruction ledger and records.

The M0-M4 reconstruction records were subsequently published in
`8fda5aa580993b5256bfbf1267216ce0f066d0cd`. That reconstruction checkpoint
does not change the M4 historical boundary or supply historical execution
evidence.
