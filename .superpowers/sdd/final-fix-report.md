# Final M8B-1 Fix Report

## Changed files

- `src/mechcad_harness/application.py`
  - Made `ProductionApplication.project_id` read-only after composition.
  - Validated the injected adapter has the required `identity` attribute and callable `invoke` method during composition.
  - Added non-empty validation for `ProductionStateBinding.project_id` and `state_hash`.
- `src/mechcad_harness/runs/controller.py`
  - Normalized malformed expected-source current-pointer data to `RunIntegrityError`.
- `tests/unit/test_production_application.py`
  - Added regressions for project identity immutability, adapter composition validation, binding snapshot stability, and whitespace validation.
- `tests/unit/test_runs.py`
  - Used a guaranteed-different hash and added malformed current-pointer regressions.

## Tests

- `py -3 -m pytest tests/unit/test_production_application.py tests/unit/test_runs.py -q`
  - Passed: 50 tests.
- `py -3 -m pytest tests/unit/test_agent_gateway.py tests/unit/test_tools.py tests/unit/test_state_foundation.py tests/unit/test_changes.py -q`
  - Passed: 45 tests.

## Concerns

- No known concerns from the requested scope.
- Existing unrelated worktree changes were preserved and not included in the fixes.
