# M5 Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: IMPLEMENTATION
IMPLEMENTATION_STATUS: PARTIAL
SPEC_CONFORMANCE_STATUS: PARTIAL
HISTORICAL_EXECUTION_EVIDENCE: NOT_RETAINED
ACCEPTANCE_STATUS: NOT_FOUND
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Commit Boundary

`6cbade0ea53f1652d44bb92f92831a0c8daf62c5` (`feat: add M5 tool broker and
backend foundation`) is the direct child of M4 `a958c397` and direct parent of
`b0d77e1` (`feat: add run-scoped gear CAD artifacts`). M5 and M5.5A are
distinct logical milestones sharing `6cbade0`; no fictitious separation commit
is asserted.

## Artifact Inventory

| Historical path | Role |
| --- | --- |
| `docs/superpowers/specs/2026-08-18-mechcad-m5-tool-broker-design.md` | contemporary M5 design |
| `docs/superpowers/plans/2026-08-18-mechcad-m5-tool-broker.md` | contemporary implementation plan |
| `src/mechcad_harness/tools/{models,errors,registry,builtins,persistence,broker,__init__}.py` | M5 implementation |
| `src/mechcad_harness/runs/models.py` | M5 task-permission integration |
| `src/mechcad_harness/models/evidence.py` | shared provenance integration |
| `tests/unit/test_tools.py` | 11 committed M5 tests |
| M5.5A spec/plan, `tests/unit/test_backends.py` | separate shared-commit artifacts |

## Historical Intent

The design requires exact name/version lookup, explicit scalar engineering
inputs, narrow run/task/revision/hash context, explicit task permissions,
immutable call-before-execution and result-after-execution records, and
successful declared Evidence only. It excludes external engineering libraries,
agents, OpenCode, CAD, FEA, plugins, and hidden state access.

## Actual Historical Implementation / Deliverable

`ToolRegistry` registers and resolves exact `(name, version)` pairs.
`ToolBroker.execute()` loads run/task state, validates permission/input, writes
`ToolCall`, invokes the handler, then writes `ToolResult`. `ToolStore` writes
immutable JSON beneath `runs/<run_id>/tool_calls/` and `tool_results/`.
Built-ins implement torque, spur-gear geometry, envelope checking, and
dimension compensation. `allowed_tools` is added to `TaskDefinition`.

## Committed Tests

`tests/unit/test_tools.py` contains 11 `def test_` functions; no parameterized
case count is asserted. It covers context, registry behavior, deterministic
built-ins, permissions, persistence, immutability, failure persistence, stale
tasks, and Evidence provenance. Test code is not evidence of historical pass.

## Historical Execution Evidence

None retained. The plan's task and verification checkboxes are unchecked; no
test transcript, completion report, review, acceptance, tag, note, or CI
artifact was found.

## Design vs Actual

The M5 source imports `mechcad_harness.backends.models.BackendProvenance` in
tool/evidence models, but `src/mechcad_harness/backends/` does not exist at
`6cbade0`. This makes the target tree unimportable. The source also permits
`PENDING` tool invocation, does not revalidate the bound canonical snapshot,
and persists a success result before later Evidence creation, leaving the
durable result without the Evidence ID. These are material deviations.

## Successor Boundary

`b0d77e1` supplies the missing `backends` package as part of broader gear/CAD
work. It is an extension/successor, not evidence that M5 independently worked
or was accepted.

## Review Conclusion

The reconstructed source contains 11 `test_` functions and confirms the shared
boundary, missing import, and absence of retained execution/acceptance
evidence.
