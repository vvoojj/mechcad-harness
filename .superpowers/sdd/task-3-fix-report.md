# Task 3 Fix Wave Report

## Status

DONE_WITH_CONCERNS

All findings in the fix brief are addressed at the existing application,
controller, and state-manager boundaries. No workflow or mutation APIs were
added.

## Changed Files

- `src/mechcad_harness/application.py`
  - `ProductionRunBinding` now returns deep-copied `run` and `source` values,
    preventing nested mutation through the typed API.
  - Composed dependencies and standard permissions reject reassignment after
    construction while retaining normal typed attribute access.
- `src/mechcad_harness/runs/controller.py`
  - Expected-source validation and run manifest/state/event persistence now
    execute inside the project synchronization guard.
  - The optional `expected_source` path and legacy omitted-argument path remain
    compatible.
- `src/mechcad_harness/state/manager.py`
  - Added a narrow per-project critical section with an in-process reentrant
    lock and an OS file lock for cross-process serialization.
  - Revision creation and existing-revision promotion use the same guard.
- `tests/unit/test_production_application.py`
  - Added nested run snapshot and composed dependency reassignment regressions.
- `.superpowers/sdd/task-3-fix-report.md`
  - This report.

`tests/unit/test_runs.py` already contained the expected-source, pointer
advance, and legacy-call regressions from the prior dispatch and was retained.

## Tests And Results

- `python -m pytest tests/unit/test_production_application.py tests/unit/test_runs.py -q`
  - The workspace `python` command resolved to a launcher that emitted only
    `Python` and did not run pytest.
- Equivalent `py -3 -m pytest tests/unit/test_production_application.py tests/unit/test_runs.py -q`
  - PASS: `34 passed`
- `py -3 -m pytest tests/unit/test_state_foundation.py tests/unit/test_state_application_provenance.py tests/unit/test_changes.py -q`
  - PASS: `24 passed`

## Concerns

- The requested `python -m pytest` invocation could not be executed by the
  workspace `python` command; the installed `py -3` interpreter produced the
  passing results above.
- The lock uses the repository's serialized filesystem model and creates a
  per-project `.state-run.lock` file. It is intentionally not a general
  concurrency subsystem.
- Unrelated pre-existing worktree changes were not modified.
