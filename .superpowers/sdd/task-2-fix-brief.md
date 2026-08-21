# Task 2 Review Fixes

Read `.superpowers/sdd/task-2-brief.md`, `.superpowers/sdd/task-2-report.md`,
the Task 2 review, and the current focused test file.

Address these review improvements without broad production changes:

1. Expand the exact standard-tool test to iterate over every
   `BuiltinTools.registrations()` entry, resolve each exact `(name, version)`,
   assert every exposed permission is `name@version`, and assert no bare name
   appears.
2. Make the trusted-role test exercise the real `AgentGateway` request path,
   not only a direct `AgentRegistry` lookup. A deterministic adapter may record
   the request and return the existing structured response. Create the minimal
   real run/task records needed by existing contracts. Keep the separate
   composition/create_run no-execution test intact.
3. Keep missing configuration rejection at the composition boundary with the
   existing `ValueError` policy unless a concrete existing domain exception is
   already the established convention; do not broaden scope just to change
   exception taxonomy.

Run:

```text
py -3 -m pytest tests/unit/test_production_application.py -q
py -3 -m pytest tests/unit/test_agent_gateway.py tests/unit/test_tools.py -q
```

Write `.superpowers/sdd/task-2-fix-report.md`. Do not commit, reset, stash,
clean, or push.
