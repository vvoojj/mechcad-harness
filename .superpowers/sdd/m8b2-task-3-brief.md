### Task 3: Run narrow regressions and inspect scope

**Files:**
- Verify: `src/mechcad_harness/application.py`
- Verify: `tests/integration/test_m8b2_production_vertical_slice.py`
- Verify: existing M8B-1 and M6B tests listed below

- [ ] **Step 1: Run M8B-1 regression tests**

Run:

```text
python -m pytest tests/unit/test_production_application.py -q
```

Expected: all existing M8B-1 composition, binding, identity, and fail-closed tests pass.

- [ ] **Step 2: Run affected M6B and persistence tests**

Run:

```text
python -m pytest tests/unit/test_agent_roundtrip.py tests/unit/test_agent_gateway.py tests/unit/test_tools.py tests/unit/test_runs.py tests/unit/test_dependency.py -q
```

Expected: existing coordinator, gateway, exact mediation, ToolBroker, run binding, and Evidence freshness tests pass.

- [ ] **Step 3: Verify production coordinator safety and source scope**

Inspect `src/mechcad_harness/agents/roundtrip.py` and assert it contains no imports from `tests`, `conftest`, or fixture modules. Inspect the application diff and confirm the only production behavior added is the thin method described in Task 2. Confirm no new `ChangeProposal`, revision, CAD, provider, scheduler, or M8C code was added.

- [ ] **Step 4: Run whitespace verification**

Run:

```text
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 5: Inspect the final intended diff without changing unrelated files**

Run:

```text
git diff -- src/mechcad_harness/application.py tests/integration/test_m8b2_production_vertical_slice.py docs/superpowers/specs/2026-08-21-m8b2-production-vertical-slice-design.md docs/superpowers/plans/2026-08-21-m8b2-production-vertical-slice.md
git status --short
```

Expected: only the M8B-2 application method, focused integration test, and M8B-2 design/plan documentation are attributable to this work; pre-existing dirty files remain untouched.

## Verification Summary

The implementation is complete only when a non-test caller enters through `ProductionApplication.run_transmission_round_trip()`, uses the exact `ProductionRunBinding.source`, creates the task through the real `RunController`, delegates through the existing Gateway/Mediator/Broker graph, produces one bound ToolCall/ToolResult and trusted Evidence, performs Invocation B without a second successful torque call, and demonstrates coordinator-level recovery without repeated execution. The selected workflow stops at AgentResult; `ChangeProposal -> ChangeEngine -> revision` is explicitly not exercised.
