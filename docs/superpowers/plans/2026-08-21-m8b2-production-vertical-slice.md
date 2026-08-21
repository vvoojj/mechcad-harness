# M8B-2 Production Agent-to-Revision Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one thin `ProductionApplication` caller that creates a trusted bound transmission task and delegates to the existing M6B-2B round-trip using the M8B-1 production graph.

**Architecture:** `ProductionApplication.run_transmission_round_trip()` calls `create_run()` exactly once, treats `ProductionRunBinding.source` as the normative task source, creates one fixed task through the real `RunController`, and delegates to `TransmissionToolRoundTripCoordinator` with the application's existing `RunController`, `AgentGateway`, and `AgentRegistry`. The coordinator remains the authority for Gateway, mediation, ToolBroker, ToolResult, Evidence, Invocation B, durable transitions, and recovery.

**Tech Stack:** Python 3.11+, Pydantic v2, existing filesystem-backed production services, pytest, and `FakeAgentAdapter` only as the injected external runtime boundary.

## Global Constraints

- Preserve Python 3.11+, Pydantic v2, and UTC-aware datetime requirements.
- Do not call `load_state()` separately from the M8B-2 application method; `create_run()` owns the authoritative snapshot-binding sequence.
- `ProductionRunBinding.source` is the normative task source authority; do not independently re-resolve revision or state hash.
- Keep `DesignState` canonical and immutable; do not fabricate a `ChangeProposal` or revision.
- Reuse the existing `TransmissionToolRoundTripCoordinator` unchanged for workflow and recovery behavior.
- Internal production services must come from `ProductionApplication.create()`; only the external agent/runtime adapter may be replaced in tests.
- Preserve trusted `mechcad-transmission@1.0` identity and exact `mechcad-calc-torque@1.0` permission.
- Do not add a separate `ProductionApplication` recovery API unless required by an existing interface; coordinator-level recovery may be exercised with application-owned services.
- Do not add CAD, FEA, scheduling, provider capability, generic workflow, or M8C functionality.
- Preserve unrelated dirty files and do not reset, stash, clean, commit, or push.

---

## File Map

- Modify: `src/mechcad_harness/application.py` - add the thin production round-trip entry point and fixed task construction.
- Create: `tests/integration/test_m8b2_production_vertical_slice.py` - exercise the application entry point against the real M8B-1 graph and deterministic external adapter.
- Do not modify: `src/mechcad_harness/agents/roundtrip.py` - verify its production-safe imports and reuse it unchanged.
- Do not modify: `src/mechcad_harness/agents/gateway.py`, `src/mechcad_harness/agents/tool_mediation.py`, `src/mechcad_harness/tools/broker.py`, or Evidence code - the selected workflow already provides these boundaries.

### Task 1: Add the failing production-entry integration tests

**Files:**
- Create: `tests/integration/test_m8b2_production_vertical_slice.py`
- Reference: `src/mechcad_harness/application.py`
- Reference: `src/mechcad_harness/agents/roundtrip.py`

**Interfaces:**
- Consumes: `ProductionApplication.create(...)` and the existing `TransmissionToolRoundTripCoordinator` result/recovery APIs.
- Produces: tests that require `ProductionApplication.run_transmission_round_trip(*, selected_requirement_ids=(), max_iterations=3) -> TransmissionToolRoundTripResult`.

- [ ] **Step 1: Write the production fixture using only the application composition root**

Create a test-local workspace, ownership file, and dependency file. Seed the project with `StateManager.create_project(...)` and three authoritative torque requirements. Construct the application only with:

```python
application = ProductionApplication.create(
    workspace,
    "PRJ-production-roundtrip",
    adapter,
    ownership_path=ownership,
    dependency_path=dependencies,
)
```

The test may create the `FakeAgentAdapter` as the external boundary, but must not instantiate `RunController`, `AgentGateway`, `AgentToolMediator`, `ToolBroker`, `ToolRegistry`, `EvidenceStore`, `ChangeEngine`, or a coordinator dependency graph independently.

- [ ] **Step 2: Write the failing end-to-end application caller test**

Use scripted A/B authored responses matching the existing M6B-2B contract:

```python
response_a = AgentAuthoredResponsePayload(
    status="succeeded",
    summary="A",
    findings=("Torque calculation requested from authoritative inputs.",),
    issues=(),
    constraint_requests=(),
    change_proposals=(),
    tool_requests=(AgentToolRequestDraft(
        capability="transmission.torque",
        arguments={"force_n": 10, "lever_arm_m": 0.2, "safety_factor": 2},
    ),),
)
response_b = AgentAuthoredResponsePayload(
    status="succeeded",
    summary="B",
    findings=("The required design torque is supplied by current Evidence.",),
    issues=(),
    constraint_requests=(),
    change_proposals=(),
    tool_requests=(),
)
```

Call only:

```python
result = application.run_transmission_round_trip(
    selected_requirement_ids=(
        "REQ-TORQUE-FORCE",
        "REQ-TORQUE-ARM",
        "REQ-TORQUE-SAFETY",
    ),
)
```

Assert the result is complete, the adapter was invoked twice, exactly one ToolCall and ToolResult exist, exactly one Evidence exists, and the current canonical state hash remains the original hash. Assert the second adapter request contains exactly one selected Evidence summary with the trusted torque summary, not raw ToolResult output.

- [ ] **Step 3: Add binding, identity, permission, and graph assertions**

Wrap the instance `create_run` method only to capture its returned `ProductionRunBinding`, then call the application method. Assert:

```python
assert captured.source.revision == captured.run.active_revision
assert captured.source.state_hash == captured.run.active_state_hash
assert task.bound_revision == captured.source.revision
assert task.bound_state_hash == captured.source.state_hash
assert task.allowed_tools == ("mechcad-calc-torque@1.0",)
assert task.objective == "Perform bounded transmission torque round trip."
assert application.agent_registry.get_identity("mechcad-transmission", "1.0").role == "transmission_engineer"
assert adapter.requests[0].agent.role == "transmission_engineer"
```

Load the persisted task through `application.run_controller.store.load_task_definition(...)`; do not inspect a test-created substitute. Assert the application exposes the real `RunController`, `AgentGateway`, `AgentToolMediator`, `ToolBroker`, `EvidenceStore`, and `ChangeEngine` instances already covered by M8B-1 composition tests.

- [ ] **Step 4: Add the coordinator-recovery assertion**

After the application workflow completes, locate the single persisted run ID from `adapter.requests[0].run_id`, construct only the coordinator from application-owned services:

```python
coordinator = TransmissionToolRoundTripCoordinator(
    application.run_controller,
    application.agent_gateway,
    application.agent_registry,
)
resumed = coordinator.resume(
    adapter.requests[0].run_id,
    "TASK-transmission-roundtrip",
    "mechcad-transmission",
    "1.0",
)
```

Assert the resumed result is complete, adapter invocation count is unchanged, and the persisted ToolCall count remains one. This proves coordinator-level recovery through application-owned services without claiming a separate application resume API.

- [ ] **Step 5: Run the new tests to verify they fail before implementation**

Run:

```text
python -m pytest tests/integration/test_m8b2_production_vertical_slice.py -q
```

Expected: FAIL because `ProductionApplication.run_transmission_round_trip` does not yet exist.

### Task 2: Implement the minimal application boundary

**Files:**
- Modify: `src/mechcad_harness/application.py`

**Interfaces:**
- Consumes: `ProductionApplication.create_run(max_iterations=...) -> ProductionRunBinding`, existing `RunController.add_task`, and `TransmissionToolRoundTripCoordinator.run`.
- Produces:

```python
def run_transmission_round_trip(
    self,
    *,
    selected_requirement_ids: tuple[str, ...] = (),
    max_iterations: int = 3,
) -> TransmissionToolRoundTripResult
```

- [ ] **Step 1: Add the method with no independent state resolution**

Import `TaskDefinition` alongside the existing run imports. Inside the method, call `self.create_run(max_iterations=max_iterations)` exactly once. Use `run_binding.source` as the normative source and fail closed with `RunIntegrityError` if the already-returned run does not have matching active revision/hash:

```python
run_binding = self.create_run(max_iterations=max_iterations)
source = run_binding.source
run = run_binding.run
if run.project_id != source.project_id or run.active_revision != source.revision or run.active_state_hash != source.state_hash:
    raise RunIntegrityError("production run source binding mismatch")
```

Do not call `load_state()`, `_read_current()`, or `_read_snapshot()` in this method.

- [ ] **Step 2: Construct the fixed trusted task through RunController**

Create exactly one task with harness-owned values:

```python
task = TaskDefinition(
    task_id="TASK-transmission-roundtrip",
    run_id=run.run_id,
    task_type="agent",
    objective="Perform bounded transmission torque round trip.",
    bound_revision=source.revision,
    bound_state_hash=source.state_hash,
    allowed_tools=("mechcad-calc-torque@1.0",),
)
self.run_controller.add_task(run.run_id, task)
```

The caller supplies no agent identity, role, revision, state hash, permission, task ID, or Evidence ID. `source` is already validated by `create_run()` and is not re-resolved.

- [ ] **Step 3: Delegate using existing application-owned services**

Import `TransmissionToolRoundTripCoordinator` from `mechcad_harness.agents.roundtrip` inside the method or at module scope without changing the coordinator. Construct it only with services owned by this application and run it with the fixed registered identity:

```python
coordinator = TransmissionToolRoundTripCoordinator(
    self.run_controller,
    self.agent_gateway,
    self.agent_registry,
)
return coordinator.run(
    run.run_id,
    task.task_id,
    self._IDENTITY.agent_name,
    self._IDENTITY.agent_version,
    selected_requirement_ids=tuple(selected_requirement_ids),
)
```

Do not add a parallel result model, direct torque call, direct Evidence call, proposal application, or application-level recovery method.

- [ ] **Step 4: Run the focused integration test**

Run:

```text
python -m pytest tests/integration/test_m8b2_production_vertical_slice.py -q
```

Expected: PASS for the full application-entered round trip and coordinator recovery assertions.

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
