# Task 3: Enforce expected source binding at the run boundary

Read the approved design and plan, then implement the run-boundary correction and Task 1 review fixes in the current repository.

## Files

- Modify `src/mechcad_harness/runs/models.py`.
- Modify `src/mechcad_harness/runs/controller.py`.
- Modify `src/mechcad_harness/application.py`.
- Modify `tests/unit/test_production_application.py` and/or `tests/unit/test_runs.py` with focused tests.
- Preserve unrelated pre-existing changes. Do not commit, reset, stash, clean, or push.

## Required API

Add one typed lower-level binding in `runs/models.py`:

```python
SourceBinding(project_id: str, revision: int, state_hash: str)
```

It must reject blank strings and non-positive revisions and be immutable.

Extend:

```python
RunController.create_run(
    project_id: str,
    *,
    max_iterations: int = 3,
    expected_source: SourceBinding | None = None,
) -> Run
```

When `expected_source is None`, preserve existing caller behavior and signature compatibility. When provided:

- require expected project to equal `project_id`;
- verify the referenced revision snapshot exists and its hash matches `expected_source.state_hash`;
- verify the current canonical pointer still equals the expected project/revision/hash;
- fail closed using existing `RunIntegrityError` or state-domain exceptions if any check fails;
- persist manifest/run state with exactly the expected revision/hash;
- do not silently use a newer pointer.

Search for an existing lock/transaction/critical section first. None was found in the initial inspection; do not invent a broad concurrency subsystem. Keep the implementation within current serialized filesystem operations.

Update `ProductionApplication.create_run()` to pass `SourceBinding` directly. Remove the `inspect.signature` fallback and private `_ExpectedSource` shim. Verify returned and reloaded run fields exactly. Expose the composed `EvidenceStore`, `ChangeEngine`, and `ContextBuilder` on `ProductionApplication` as typed read-only dependencies in the same style as existing exposed services.

## Immutability

The reviewer found that frozen Pydantic wrappers do not freeze nested `DesignState`. Ensure a caller cannot mutate the canonical state through a binding and change the binding’s internal hash. Use the smallest clear approach consistent with repository conventions, such as storing a deep internal snapshot and returning a deep copy from a read-only state accessor. Preserve the typed `state` API and equality semantics used by focused tests.

## Tests

Add focused tests for:

1. legacy `RunController.create_run()` with no expected source;
2. matching expected source creates exact revision/hash;
3. state advances between application `load_state()` and `create_run()` and application fails closed rather than binding newer state;
4. project/revision/hash mismatch fails closed;
5. if primitive parameters are used, partial binding is rejected; prefer no primitive parameters;
6. existing callers remain compatible;
7. mutating an object returned from `ProductionStateBinding.state` does not alter a later binding/hash;
8. application exposes `evidence_store`, `change_engine`, and `context_builder` without adding mutation/execution methods.

Run at minimum:

```text
python -m pytest tests/unit/test_production_application.py tests/unit/test_runs.py -q
```

Write `.superpowers/sdd/task-3-report.md` with status, changed files, tests/results, and concerns. Return only status, test summary, and concerns.
