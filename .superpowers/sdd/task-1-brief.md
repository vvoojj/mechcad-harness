# Task 1: Define immutable production bindings and composition API

Implement the first task of the M8B-1 production orchestration plan in the current repository.

## Files

- Create `src/mechcad_harness/application.py`.
- Create `tests/unit/test_production_application.py`.
- Do not modify unrelated pre-existing worktree changes.

## Interfaces

- `ProductionStateBinding(project_id: str, state: DesignState, revision: int, state_hash: str)` is immutable and validates `state.revision == revision`.
- `ProductionRunBinding(run: Run, source: ProductionStateBinding)` is immutable and validates project, initial revision/hash, and active revision/hash exactly match source.
- `ProductionApplication.create(workspace: str | Path, project_id: str, agent_adapter: AgentAdapter, *, ownership_path: str | Path, dependency_path: str | Path, additional_tool_registrations: Iterable[ToolRegistration] = ()) -> ProductionApplication` performs composition only.
- `ProductionApplication.load_state() -> ProductionStateBinding` loads/verifies current state and returns a fresh binding without retaining it.
- `ProductionApplication.create_run(*, max_iterations: int = 3) -> ProductionRunBinding` loads once, passes its source binding to the controller boundary, verifies persistence, and never executes an adapter. The controller expected-source signature will be completed in Task 3; make the application call compatible with the intended `expected_source` parameter.

## Composition

Construct existing `StateManager`, `DependencyGraph.from_yaml`, `EvidenceStore`, `OwnershipPolicy.from_file`, `ChangeEngine`, `RunController`, `BuiltinTools.registrations()` plus explicit extensions, `ToolRegistry`, `ToolBroker`, `AgentRegistry`, `ContextBuilder`, and `AgentGateway`.

Own the fixed trusted identity:

```text
agent_name=mechcad-transmission
agent_version=1.0
role=transmission_engineer
protocol_version=1.0
```

Register the injected adapter under this identity. Never use adapter identity/provider metadata for the trusted identity. Do not use `FakeAgentAdapter` as a production default. Standard exact tool permission policy must be represented as `tool@version`, never bare names.

Reject blank project ID, null adapter, and missing config paths with `ValueError`. Use existing domain errors for state not found/integrity failures. Do not add `invoke_agent`, `execute_task`, `run_workflow`, `start_run`, or any workflow API. Do not import tests or fixtures from production.

## Tests

Use a deterministic local adapter only in tests, with forged adapter identity and an invocation counter. Build a real project with `StateManager.create_project`. Cover:

- real graph construction without invoking adapter;
- fresh exact `load_state()` bindings and correct state hash;
- `create_run()` exact loaded source binding and no adapter invocation.

Run `python -m pytest tests/unit/test_production_application.py -q` after implementation.

## Constraints

- Preserve Python 3.11+, Pydantic v2, UTC-aware datetimes, and canonical DesignState boundaries.
- Preserve exact tool version permissions and trusted production role.
- No broad refactoring, CAD/provider/workflow execution, commits, resets, stash, clean, or push.

## Report

Write implementation status, changed files, tests run/results, and concerns to `.superpowers/sdd/task-1-report.md`. Return only status, commit information if any (do not commit here), one-line test summary, and concerns.
