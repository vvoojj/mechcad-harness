# Task 3 Report: Expected Source Binding

## Status

DONE

Task 3 is implemented. `RunController.create_run()` now accepts the typed,
immutable `SourceBinding` while preserving the legacy call with no expected
source. Supplied bindings are checked against the referenced verified snapshot
and the current canonical pointer, and runs persist exactly the expected
revision and hash. `ProductionApplication.create_run()` now passes the typed
binding directly, verifies the reloaded run fields, and fails closed instead of
falling back through signature inspection or binding a newer pointer.

## Changed Files

- `src/mechcad_harness/runs/models.py`
  - Added frozen `SourceBinding` with blank-string and positive-revision validation.
- `src/mechcad_harness/runs/__init__.py`
  - Exported `SourceBinding` through the runs package.
- `src/mechcad_harness/runs/controller.py`
  - Added optional expected-source validation at the run boundary.
  - Preserved pointer-based behavior when `expected_source` is omitted.
- `src/mechcad_harness/application.py`
  - Removed `inspect.signature` and `_ExpectedSource`.
  - Passes `SourceBinding` directly and verifies persisted run identity/binding.
  - Exposes `evidence_store`, `change_engine`, and `context_builder`.
  - Returns deep copies from the `ProductionStateBinding.state` accessor so nested mutation cannot alter its internal snapshot.
- `tests/unit/test_runs.py`
  - Added legacy, matching-source, mismatch, pointer-advance, and `SourceBinding` validation tests.
- `tests/unit/test_production_application.py`
  - Added state-binding immutability, dependency exposure, typed-source, and application fail-closed tests.

## Tests And Results

- `py -3 -m pytest tests/unit/test_production_application.py tests/unit/test_runs.py -q`
  - PASS: `32 passed`
- `py -3 -m pytest tests/unit/test_agent_gateway.py tests/unit/test_tools.py tests/unit/test_state_foundation.py tests/unit/test_runs.py tests/unit/test_changes.py -q`
  - PASS: `67 passed`
- `py -3 -m compileall -q src/mechcad_harness/runs src/mechcad_harness/application.py`
  - PASS

## Concerns

- No existing lock or transaction primitive was present. The implementation
  intentionally remains within the current serialized filesystem operations and
  does not introduce a broad concurrency subsystem.
- The worktree contains unrelated pre-existing changes; they were not modified.
