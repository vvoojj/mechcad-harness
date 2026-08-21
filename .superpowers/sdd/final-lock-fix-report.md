# Final Lock Side-Effect Fix Report

## Status

DONE

The narrow per-project synchronization guard is preserved. `StateManager.project_lock()` now raises `RevisionNotFoundError` before lock-path creation when the canonical current pointer is absent, so a missing-project `RunController.create_run()` leaves no project directory behind.

## Tests

- `py -3 -m pytest tests/unit/test_production_application.py tests/unit/test_runs.py -q`
  - Passed: 51 tests.
- `py -3 -m pytest tests/unit/test_state_foundation.py tests/unit/test_changes.py -q`
  - Passed: 15 tests.

## Concerns

- Existing valid-project locking, reentrancy, cross-process file locking, and revision/run persistence behavior were not broadened or redesigned.
- Unrelated pre-existing worktree changes were preserved and not modified.
