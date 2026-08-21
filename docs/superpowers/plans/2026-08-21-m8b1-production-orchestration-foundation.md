# M8B-1 Production Orchestration Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real non-test `ProductionApplication.create(...)` composition root that owns the standard MechCAD service graph and provides only verified state loading and run binding.

**Architecture:** `ProductionApplication` constructs the existing state, dependency, evidence, change, run, tool, and agent services. It owns the deterministic `mechcad-transmission@1.0` trusted identity and exact standard tool registrations while receiving only an external agent adapter through dependency injection. `load_state()` returns a fresh immutable binding; `create_run()` uses that authoritative snapshot binding, creates no workflow execution, and fails closed if persistence changes the binding.

**Tech Stack:** Python 3.11+, Pydantic v2, existing filesystem-backed `StateManager`/`RunStore`/`EvidenceStore`, pytest, and deterministic local adapter test doubles.

## Global Constraints

- Preserve Python 3.11+, Pydantic v2, and UTC-aware datetime requirements.
- Treat `DesignState` as canonical state; proposals, results, validation, and evidence remain separate bindable records.
- Preserve exact `tool@version` permissions and the registered trusted agent role.
- Do not add task execution, workflow execution, CAD compiler ingress, provider bridges, scheduling, or OpenCode live execution.
- Do not require callers to construct an `AgentRegistry` or standard `ToolRegistry` for the normal production graph.
- Inject only the external/runtime `AgentAdapter`; do not use `FakeAgentAdapter` as the production default.
- Do not introduce a second state-mutation API; canonical mutation remains exclusively in `ChangeEngine`.
- Preserve all pre-existing worktree changes and do not commit, stash, reset, clean, or push.

---

## File Map

- Create: `src/mechcad_harness/application.py` - typed production composition root and state/run binding records.
- Modify: `src/mechcad_harness/runs/models.py` - typed lower-level expected source binding shared by `RunController` and the application.
- Modify: `src/mechcad_harness/runs/controller.py` - optional expected-source validation while preserving legacy `create_run()` callers.
- Create: `tests/unit/test_production_application.py` - focused tests for production construction, identity/policy, bindings, no execution, and fail-closed behavior.
- Modify: `src/mechcad_harness/__init__.py` only if the repository's public import convention requires exporting the new application API.
- Create: `docs/superpowers/specs/2026-08-21-m8b1-production-orchestration-foundation-design.md` - already approved design record; do not alter unrelated documentation.

### Task 1: Define immutable production bindings and composition API

**Files:**
- Create: `src/mechcad_harness/application.py`
- Test: `tests/unit/test_production_application.py`

**Interfaces:**
- `ProductionStateBinding(project_id: str, state: DesignState, revision: int, state_hash: str)` is immutable and validates that `state.revision == revision`.
- `ProductionRunBinding(run: Run, source: ProductionStateBinding)` is immutable and validates that the run project, initial revision, initial state hash, active revision, and active state hash equal `source`.
- `SourceBinding(project_id: str, revision: int, state_hash: str)` is the lower-level typed binding accepted by `RunController`; `ProductionStateBinding` supplies it without making `runs` depend on `application.py`.
- `ProductionApplication.create(workspace: str | Path, project_id: str, agent_adapter: AgentAdapter, *, ownership_path: str | Path, dependency_path: str | Path, additional_tool_registrations: Iterable[ToolRegistration] = ()) -> ProductionApplication` performs composition only.
- `ProductionApplication.load_state() -> ProductionStateBinding` loads the current state through `StateManager`, verifies the canonical hash, and returns a fresh binding without retaining it on the application.
- `ProductionApplication.create_run(*, max_iterations: int = 3) -> ProductionRunBinding` calls `load_state()` once, passes its `SourceBinding` to `RunController`, verifies the persisted run binding, and returns the binding.

- [ ] **Step 1: Write failing binding and construction tests**

Create a local deterministic adapter in the test module that implements the existing adapter protocol, has a deliberately forged provider identity, and increments a call counter from `invoke()`. Build a real project with `StateManager.create_project(...)`. Assert the new imports and methods are currently unavailable.

Add tests with these names and assertions:

```python
def test_production_application_constructs_real_graph_without_invoking_adapter(tmp_path):
    adapter = CountingAdapter()
    application = build_application(tmp_path, adapter)
    assert isinstance(application.state_manager, StateManager)
    assert isinstance(application.run_controller, RunController)
    assert isinstance(application.agent_registry, AgentRegistry)
    assert isinstance(application.agent_gateway, AgentGateway)
    assert isinstance(application.tool_broker, ToolBroker)
    assert adapter.invocation_count == 0


def test_load_state_returns_exact_fresh_binding(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    first = application.load_state()
    second = application.load_state()
    assert first is not second
    assert (first.revision, first.state_hash) == (1, state_hash(first.state))
    assert second == first


def test_create_run_binds_authoritative_loaded_snapshot(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    source = application.load_state()
    binding = application.create_run()
    assert binding.source == source
    assert binding.run.initial_revision == source.revision
    assert binding.run.initial_state_hash == source.state_hash
    assert binding.run.active_revision == source.revision
    assert binding.run.active_state_hash == source.state_hash


def test_create_and_create_run_never_execute_adapter(tmp_path):
    adapter = CountingAdapter()
    application = build_application(tmp_path, adapter)
    application.create_run()
    assert adapter.invocation_count == 0
```

- [ ] **Step 2: Run focused tests to verify they fail**

Run: `python -m pytest tests/unit/test_production_application.py -q`

Expected: FAIL because `mechcad_harness.application` and its production API do not yet exist.

- [ ] **Step 3: Implement typed bindings and the long-lived application container**

Use existing Pydantic `Model` conventions and frozen models/configuration where available. Store composed dependencies as typed attributes. Do not store `ProductionStateBinding` on the application. The constructor should be private-by-convention through `create()` or otherwise only receive already-validated graph dependencies from `create()`.

The composition method should:

1. Reject blank `project_id`, a null adapter, and missing configuration paths with `ValueError`.
2. Construct `StateManager(workspace)`.
3. Construct `DependencyGraph.from_yaml(dependency_path)` and `EvidenceStore(workspace, state_manager, graph)`.
4. Construct `OwnershipPolicy.from_file(ownership_path)`, `ChangeEngine(state_manager, ownership_policy)`, and `RunController(workspace, state_manager, change_engine, evidence_store)`.
5. Build the standard registrations from `BuiltinTools.registrations()`, append only explicitly supplied extensions, construct `ToolRegistry`, and verify every standard registration resolves by its exact `(name, version)`.
6. Construct `ToolBroker(run_controller, tool_registry)`.
7. Construct the fixed `AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")`, register it with the injected adapter in a new `AgentRegistry`, and never inspect adapter identity to populate that record.
8. Construct `ContextBuilder(run_controller)` and `AgentGateway(run_controller, agent_registry, context_builder, tool_broker=tool_broker)`.

`load_state()` must call `StateManager.load_current_state(project_id)`, read the matching current pointer/revision, compute or verify the hash with the existing `state_hash`, and raise the existing state integrity/not-found errors on mismatch. `create_run()` must call `load_state()` exactly once, call `RunController.create_run(project_id, max_iterations=max_iterations, expected_source=source_binding)`, and reject any run whose persisted fields differ from the loaded binding. `RunController.create_run()` must preserve legacy behavior when `expected_source` is omitted, but when supplied must verify the expected project/revision/hash, referenced snapshot hash, and current pointer before persisting exactly that binding. If the existing implementation has synchronization around state/run persistence, use it for this comparison and write; do not add a new concurrency subsystem. It must not call `load_current_state()` again after the run is created.

- [ ] **Step 4: Run the focused construction and binding tests**

Run: `python -m pytest tests/unit/test_production_application.py -q`

Expected: PASS for graph construction, fresh state bindings, exact run bindings, and no adapter execution.

### Task 2: Prove trusted identity, exact tool policy, and closed failure behavior

**Files:**
- Modify: `src/mechcad_harness/application.py`
- Modify: `tests/unit/test_production_application.py`

**Interfaces:**
- `application.agent_registry.get_identity("mechcad-transmission", "1.0")` returns the fixed production `AgentIdentity`.
- `application.tool_registry.resolve(name, version)` resolves each standard registration exactly.
- Standard task permissions are represented as exact strings such as `"mechcad-calc-torque@1.0"`; no application-created policy may use a bare tool name.

- [ ] **Step 1: Add failing trusted-boundary and failure tests**

Add focused tests:

```python
def test_injected_adapter_cannot_override_production_identity_or_role(tmp_path):
    adapter = CountingAdapter(identity=AgentAdapterIdentity(adapter_name="forged", adapter_version="9.9"))
    application = build_application(tmp_path, adapter)
    identity = application.agent_registry.get_identity("mechcad-transmission", "1.0")
    assert identity == AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")


def test_gateway_uses_registered_transmission_role_not_test_role(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    identity = application.agent_registry.get_identity("mechcad-transmission", "1.0")
    assert identity.role == "transmission_engineer"
    assert identity.role != "test"


def test_standard_tools_are_exactly_versioned_and_bare_permission_is_rejected(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    registration = application.tool_registry.resolve("mechcad-calc-torque", "1.0")
    assert registration.name == "mechcad-calc-torque"
    assert registration.version == "1.0"
    assert "mechcad-calc-torque@1.0" in application.standard_tool_permissions
    assert "mechcad-calc-torque" not in application.standard_tool_permissions


@pytest.mark.parametrize("bad_setup", ["missing_project", "missing_ownership", "missing_dependencies", "corrupt_current"])
def test_invalid_or_missing_state_and_configuration_fail_closed(tmp_path, bad_setup):
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text("ownership:\n  - path: /requirements/*\n    owner: requirements\n", encoding="utf-8")
    dependencies.write_text("rules: []\nedges: []\n", encoding="utf-8")
    if bad_setup == "missing_ownership":
        ownership.unlink()
    elif bad_setup == "missing_dependencies":
        dependencies.unlink()
    elif bad_setup != "missing_project":
        StateManager(workspace).create_project("PRJ-1", make_state())
        if bad_setup == "corrupt_current":
            (workspace / "projects" / "PRJ-1" / "current.json").write_text("not-json\n", encoding="utf-8")
    application = ProductionApplication.create(workspace, "PRJ-1", CountingAdapter(), ownership_path=ownership, dependency_path=dependencies)
    if bad_setup == "missing_project":
        with pytest.raises(RevisionNotFoundError):
            application.load_state()
    elif bad_setup == "corrupt_current":
        with pytest.raises(StateIntegrityError):
            application.load_state()
    else:
        with pytest.raises(ValueError):
            ProductionApplication.create(workspace, "PRJ-1", CountingAdapter(), ownership_path=ownership, dependency_path=dependencies)


def test_conflicting_standard_registration_fails_closed(tmp_path):
    standard = BuiltinTools.registrations()[0]
    with pytest.raises(ToolVersionError):
        ProductionApplication.create(
            tmp_path / "workspace",
            "PRJ-1",
            CountingAdapter(),
            ownership_path=write_ownership(tmp_path),
            dependency_path=write_dependencies(tmp_path),
            additional_tool_registrations=(standard,),
        )
```

The test bodies must create the actual invalid filesystem/configuration condition and assert `RevisionNotFoundError` for a missing project, `StateIntegrityError` for a corrupt current pointer, `ValueError` for missing configuration files, and `ToolVersionError` for a duplicate standard registration; do not use broad exception assertions.

- [ ] **Step 2: Run the new boundary tests to verify they fail**

Run: `python -m pytest tests/unit/test_production_application.py -q`

Expected: FAIL for missing policy assertions and any unimplemented validation.

- [ ] **Step 3: Implement exact registration and fail-closed validation**

Keep the fixed identity in the application module as a constant or a private factory. Validate standard registrations after composition by resolving each exact `(name, version)` pair. Reject extension registrations that duplicate a standard key or conflict with any existing key by relying on `ToolRegistry`; preserve its `ToolVersionError` for duplicate tool identity. Expose `standard_tool_permissions` as an immutable tuple/frozenset of exact `name@version` strings for later task-definition composition; never add bare names.

Do not add `invoke_agent`, `execute_task`, `run_workflow`, `start_run`, or equivalent methods. Do not import `tests`, `conftest`, or fixture modules from production code.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/unit/test_production_application.py -q`

Expected: PASS for trusted identity, exact tool policy, fail-closed configuration/state, and no execution.

### Task 3: Enforce expected source binding at the run boundary

**Files:**
- Modify: `src/mechcad_harness/runs/models.py`
- Modify: `src/mechcad_harness/runs/controller.py`
- Modify: `src/mechcad_harness/application.py`
- Modify: `tests/unit/test_production_application.py`

**Interfaces:**
- Existing `ChangeEngine` remains the only canonical mutation service.
- `ProductionApplication` exposes composed services but has no new mutation method.
- `RunController.create_run(project_id, *, max_iterations=3, expected_source: SourceBinding | None = None) -> Run` preserves current behavior when `expected_source` is `None`; when provided it uses the expected project/revision/hash as the run source and fails closed if the verified snapshot or current pointer differs.

- [ ] **Step 1: Add failing regression tests for legacy and expected source semantics**

Add tests for legacy `RunController.create_run()` with no expected binding, a matching expected binding, a state advance between application `load_state()` and `create_run()` that fails closed, a revision/hash mismatch that fails closed, and existing callers that still use the old signature. If primitive compatibility parameters are introduced instead of `SourceBinding`, add a test that revision-only and hash-only calls are rejected.

Add a test that monkeypatches the application's `load_state()` to return a known binding while making the filesystem current pointer represent a newer revision after that load. Assert `create_run()` fails closed rather than silently binding the newer revision. Add a second test that creates a later revision after `create_run()` and asserts the existing `ProductionRunBinding.source` and `binding.run` fields remain unchanged.

Add an API-surface test:

```python
def test_application_has_no_second_state_mutation_or_execution_api():
    names = set(dir(ProductionApplication))
    assert not names.intersection({"execute_task", "run_workflow", "invoke_agent", "start_run", "apply_change", "mutate_state"})
```

Also inspect `inspect.getsource(mechcad_harness.application)` and assert it does not contain `tests.` or `conftest` imports.

- [ ] **Step 2: Run the focused regression tests to verify expected-source tests fail**

Run: `python -m pytest tests/unit/test_production_application.py -q`

Expected: FAIL until `SourceBinding` and the controller's expected-source validation are implemented.

- [ ] **Step 3: Implement the typed run source binding and controller guard**

Add immutable `SourceBinding` to `src/mechcad_harness/runs/models.py` with non-empty project/hash and positive revision validation. Extend `RunController.create_run()` with `expected_source: SourceBinding | None = None`. If omitted, retain the current pointer-based behavior. If supplied, require the project to match, read and hash-verify the referenced snapshot through `StateManager`, read the current pointer, and raise `RunIntegrityError` or the existing state exception when the pointer revision/hash differs from the expected source. Construct `Run` and persist its manifest/state from the expected source values, not from a second newer pointer read. Check the repository for an existing lock or synchronization primitive before editing; if none exists, keep this change limited to the existing serialized filesystem operations and do not add a broad locking subsystem.

Update `ProductionApplication.create_run()` to pass `SourceBinding(project_id=source.project_id, revision=source.revision, state_hash=source.state_hash)` and then verify the returned/persisted run fields exactly.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/unit/test_production_application.py tests/unit/test_runs.py -q`

Expected: PASS for legacy run creation, expected-source success/failure, authoritative application timing, immutable existing bindings, and the no-new-mutation API surface.

- [ ] **Step 5: Run focused M8A and state/run regression tests**

Run: `python -m pytest tests/unit/test_agent_gateway.py tests/unit/test_tools.py tests/unit/test_state_foundation.py tests/unit/test_runs.py tests/unit/test_changes.py -q`

Expected: all selected existing tests pass, including exact broker permission and registered-role regressions.

- [ ] **Step 4: Review the diff and worktree without altering pre-existing changes**

Run: `git status --short; git diff -- src/mechcad_harness/application.py tests/unit/test_production_application.py docs/superpowers/specs/2026-08-21-m8b1-production-orchestration-foundation-design.md docs/superpowers/plans/2026-08-21-m8b1-production-orchestration-foundation.md`

Expected: only the new production module, focused tests, approved spec, and implementation plan are attributable to M8B-1; no reset, stash, clean, commit, or push is performed.

## Verification Summary

The final implementation must show a non-test importable production entry point, deterministic trusted agent/tool registration, exact current-state and run binding, no adapter execution during composition or run creation, and focused plus relevant regression tests passing. Remaining M8B workflow execution work must remain explicitly unimplemented.
