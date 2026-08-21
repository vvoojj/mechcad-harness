# Final Lock Side-Effect Fix

Read the current `src/mechcad_harness/state/manager.py`,
`src/mechcad_harness/runs/controller.py`, and the final review result.

Keep the narrow per-project synchronization guard because expected-source
pointer comparison and run persistence must be serialized with existing state
revision/promotion operations. Do not replace it with a broad scheduler or
concurrency framework.

Fix the concrete side effect: `StateManager.project_lock(project_id)` must not
create `projects/<project_id>` or `.state-run.lock` when the project does not
exist. It should fail with the existing `RevisionNotFoundError` before creating
the lock path. Existing valid-project locking, reentrancy, cross-process file
locking, legacy run creation, and revision creation/promotion behavior must
remain unchanged.

Add/update a focused test proving `RunController.create_run()` for a missing
project raises `RevisionNotFoundError` and leaves no project directory behind.
Run:

```text
py -3 -m pytest tests/unit/test_production_application.py tests/unit/test_runs.py -q
py -3 -m pytest tests/unit/test_state_foundation.py tests/unit/test_changes.py -q
```

Write `.superpowers/sdd/final-lock-fix-report.md`. Do not commit, reset, stash,
clean, or push.
