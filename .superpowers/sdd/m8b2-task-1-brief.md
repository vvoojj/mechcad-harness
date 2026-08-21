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

