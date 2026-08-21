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

