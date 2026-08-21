# M8B-1 Production Orchestration Foundation

## Goal

Add one real non-test production composition root that constructs the existing
MechCAD service graph. The only new lifecycle/application operations introduced
by M8B-1 are state loading and run binding. This is composition infrastructure
for later M8B stages, not a universal workflow executor.

## Composition Root

`ProductionApplication.create(...)` constructs a long-lived
`ProductionApplication` from a workspace, project identity, and one injected
agent adapter. It owns the standard service graph:

```text
StateManager
EvidenceStore
OwnershipPolicy
ChangeEngine
RunController
ToolRegistry -> standard exact-version tools -> ToolBroker
AgentRegistry -> mechcad-transmission@1.0 -> injected adapter
ContextBuilder -> AgentGateway -> AgentToolMediator -> ToolBroker
```

The application owns the trusted identity:

```text
agent_name     = mechcad-transmission
agent_version  = 1.0
role           = transmission_engineer
protocol       = 1.0
```

The adapter is an execution boundary only. Its identity or provider metadata
cannot replace the registered production identity. The injected adapter is
required; no `FakeAgentAdapter` or OpenCode-specific adapter is the default.

Standard tool registrations are created by the composition root using the
existing registration implementations. Required permissions use exact
`tool@version` entries. Missing, duplicate, or conflicting standard
registrations fail closed during composition.

## State And Run API

The application does not retain a canonical state binding. Each
`load_state()` call loads and verifies the current authoritative snapshot via
`StateManager` and returns a fresh immutable `ProductionStateBinding` carrying
the project ID, `DesignState`, revision, and state hash.

`create_run()` first loads that binding, creates the run through
`RunController` using one typed expected source binding as the authoritative
source, verifies that the controller persisted the same revision/hash, and
returns an immutable
`ProductionRunBinding` containing the run and exact source binding. It must not
silently re-resolve a newer canonical state after loading. The sequence is:
load the exact snapshot, create the run bound to that revision/hash, verify the
persisted binding, and return the run binding. The method does not execute an
adapter, agent, task, or workflow. Existing run bindings remain unchanged if a
later canonical state revision is created.

`RunController.create_run()` accepts the typed expected source as an optional
argument. With no expected source, existing callers retain current behavior.
With one provided, the controller verifies the project, revision, snapshot
hash, and current canonical pointer, then persists exactly that binding. A
partial primitive binding is not accepted. Any existing synchronization or
critical-section mechanism must cover the pointer comparison and run
persistence; M8B-1 does not introduce a new concurrency subsystem.

`ProductionApplication` may own and expose its composed services as typed,
read-only dependencies for later bounded workflows, including the existing
`ChangeEngine`. No application method added by M8B-1 mutates `DesignState` or
introduces a second state-mutation API. Canonical changes continue exclusively
through the existing `ChangeEngine` boundary.

## Failure Behavior

Composition rejects invalid workspace/project/adapter configuration, missing
required tool registrations, duplicate or conflicting registrations, and an
invalid production identity. State loading propagates existing revision,
integrity, and not-found exceptions. Any persisted run binding that differs
from the loaded state binding fails closed.

## Tests

Focused tests exercise the real production composition code with a deterministic
local adapter injected at the external boundary. They verify graph ownership,
adapter identity, trusted gateway role, exact tool permissions, state and run
bindings, immutability/no additional or direct state-mutation API, fail-closed construction and
state loading, and that composition/run creation never invokes the adapter.
They also check that the production module does not import or depend on test
composition helpers.

## Scope Exclusions

This change does not add task execution, agent invocation APIs, workflow
execution, universal CAD synthesis, provider workflow bridges, scheduling,
OpenCode live execution, or broad refactoring.
