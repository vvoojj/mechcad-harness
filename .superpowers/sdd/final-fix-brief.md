# Final M8B-1 Review Fixes

Read `.superpowers/sdd/final-review-package.md` and the current production and
focused test files. Fix every finding below, preserving scope and existing
worktree changes.

## Important fixes

1. Make `ProductionApplication.project_id` read-only after composition. Keep
   typed access and ensure reassignment fails before it can redirect
   `load_state()` or `create_run()`.
2. Validate the injected adapter at composition time against the existing
   adapter protocol/required callable shape. A plain `object()` must fail with
   `ValueError` during `ProductionApplication.create()`, not later at invoke.
   Do not hard-code OpenCode or FakeAgentAdapter.
3. Normalize malformed expected-source current-pointer data in
   `RunController.create_run(expected_source=...)` to an existing fail-closed
   `RunIntegrityError` or state-domain exception. Do not leak raw
   `JSONDecodeError`, `KeyError`, or unrelated parser exceptions. Preserve
   legacy behavior unless the expected-source path is active.

## Minor fixes/tests

4. Make the hash mismatch test use a guaranteed-different hash such as
   `"sha256:" + "0" * 64` rather than changing one character that can remain
   unchanged.
5. Add the required regression that creates a `ProductionRunBinding`, advances
   canonical state afterward, and proves the existing binding's source/run
   revision/hash remain unchanged.
6. Make `ProductionStateBinding` reject whitespace-only `project_id` and
   `state_hash` with the same non-empty validation convention as `SourceBinding`.

Run:

```text
py -3 -m pytest tests/unit/test_production_application.py tests/unit/test_runs.py -q
py -3 -m pytest tests/unit/test_agent_gateway.py tests/unit/test_tools.py tests/unit/test_state_foundation.py tests/unit/test_changes.py -q
```

Write `.superpowers/sdd/final-fix-report.md` with changed files, tests/results,
and concerns. Do not commit, reset, stash, clean, or push.
