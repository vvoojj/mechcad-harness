# Task 3 Fix Wave

Fix all findings from the Task 3 review in the existing worktree. Read the
review result in the previous dispatch and these files first:

- `src/mechcad_harness/application.py`
- `src/mechcad_harness/runs/controller.py`
- `src/mechcad_harness/state/manager.py`
- `tests/unit/test_production_application.py`
- `tests/unit/test_runs.py`

## Findings to fix

1. `ProductionRunBinding` must be effectively immutable. A caller must not be
   able to mutate `binding.run.active_revision` or other nested run fields and
   alter the binding. Preserve the typed `run` API, using the same defensive
   deep-copy approach as the state binding if that is the smallest safe fix.
2. Composed dependencies must be read-only after `ProductionApplication` is
   constructed. Prevent reassignment of `state_manager`, `run_controller`,
   `agent_registry`, `agent_gateway`, `tool_registry`, `tool_broker`,
   `evidence_store`, `change_engine`, `context_builder`, and
   `standard_tool_permissions`, while preserving typed access.
3. Expected-source pointer validation and run manifest/state persistence must
   use an existing synchronization mechanism if one exists. Initial inspection
   found no lock/transaction. Add only the smallest narrow project-level
   critical section needed for this state/run operation, not a broad concurrency
   subsystem. It must cover the expected pointer check through run persistence,
   and state revision creation must use the same guard if that is required for
   the guard to be meaningful. Cross-process behavior must fail closed or be
   explicitly constrained by the implementation’s existing filesystem model.

## Required tests

Add or update focused tests proving:

- `binding.run.active_revision = 2` cannot mutate the binding;
- assigning a composed dependency on `ProductionApplication` fails;
- expected-source run creation still rejects pointer advance/mismatch;
- the existing legacy create_run path remains compatible;
- the focused production/run tests pass.

Do not add workflow execution or mutation APIs. Do not commit, reset, stash,
clean, or push. Write `.superpowers/sdd/task-3-fix-report.md` with changed
files, tests and results, and concerns.
