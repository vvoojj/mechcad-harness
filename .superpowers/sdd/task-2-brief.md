# Task 2: Prove trusted identity, exact tool policy, and closed failure behavior

Complete Task 2 of M8B-1 in the current repository. Read the approved design,
plan, and current `src/mechcad_harness/application.py` and
`tests/unit/test_production_application.py` first.

## Scope

Use the existing production composition root. Do not redesign the graph or add
workflow APIs. Preserve all unrelated worktree changes. Do not commit, reset,
stash, clean, or push.

## Required coverage

Add focused tests using a deterministic local adapter injected into
`ProductionApplication.create()`:

1. Adapter identity/provider metadata cannot override the fixed production
   `AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0",
   role="transmission_engineer", protocol_version="1.0")`.
2. Gateway/registry resolves role `transmission_engineer`, never `"test"`.
3. Standard tools resolve by exact `(name, version)` and exposed standard
   permissions contain `name@version`, never a bare name.
4. A bare-name allowed tool permission is rejected by the real `ToolBroker`.
5. Missing project state, corrupt current pointer, missing ownership config,
   and missing dependency config fail closed with specific existing/domain or
   configuration exceptions.
6. Conflicting duplicate standard registration fails closed.
7. `ProductionApplication.create()` and `create_run()` never invoke the
   adapter.
8. Production module has no imports of tests/conftest/fixture helpers.

Use exact exception assertions, not `Exception`.

If implementation changes are needed, keep them limited to validating the
standard production registration/policy. Standard registrations must continue
to come from existing `BuiltinTools.registrations()` and exact versions. Do
not weaken the trusted identity, broker permission, or source-binding
boundaries.

## Tests

Run:

```text
py -3 -m pytest tests/unit/test_production_application.py -q
py -3 -m pytest tests/unit/test_agent_gateway.py tests/unit/test_tools.py -q
```

Write `.superpowers/sdd/task-2-report.md` with status, changed files, tests,
and concerns. Return only status, test summary, and concerns.
