# M8B-2 Production Agent-to-Revision Vertical Slice

## Goal

Connect the existing bounded M6B-2B transmission round trip to the M8B-1
production composition root. This milestone adds one thin application caller;
it does not duplicate or redesign the round-trip coordinator.

## Production Entry Point

Add:

```text
ProductionApplication.run_transmission_round_trip(...)
```

The method performs only application-bound task setup and delegation:

1. Call `ProductionApplication.create_run()` exactly once.
2. Use the returned `ProductionRunBinding` as the sole authoritative source.
3. Create one `TaskDefinition` through the existing `RunController`, bound to
   `run_binding.run.active_revision` and `run_binding.run.active_state_hash`.
4. Use the harness-owned `mechcad-transmission@1.0` identity, fixed workflow
   objective, and exact `mechcad-calc-torque@1.0` permission.
5. Delegate to `TransmissionToolRoundTripCoordinator` using the application’s
   already-composed `RunController`, `AgentGateway`, and `AgentRegistry`.
6. Return the existing `TransmissionToolRoundTripResult`.

The method does not call `load_state()` separately, re-resolve a revision/hash,
accept caller-supplied identity or permissions, or construct another service
graph.

`ProductionRunBinding.source` is the normative task source authority. The run's
active revision/hash must equal `source.revision` and `source.state_hash` before
task creation. Task construction uses those already-validated binding values;
it does not independently re-resolve source identity.

## Data Flow

```text
DesignState
  -> ProductionApplication.create_run()
  -> ProductionRunBinding
  -> RunController.add_task()
  -> TransmissionToolRoundTripCoordinator
  -> AgentGateway
  -> AgentToolMediator
  -> ToolBroker
  -> mechcad-calc-torque@1.0
  -> ToolResult
  -> trusted Evidence
  -> Invocation B
  -> AgentResult
```

The coordinator remains responsible for the existing finite sequence,
durable transitions, Evidence freshness, second-invocation behavior, and
no-second-tool-execution invariant. The external adapter is the only test
substitute; all internal services come from `ProductionApplication.create()`.

## Task Authority

The application owns task construction. Callers may select only bounded
workflow inputs such as selected authoritative requirement IDs. Adapter
behavior belongs to the injected external runtime boundary and is not a
`run_transmission_round_trip(...)` input. Callers cannot provide the agent identity,
role, revision, state hash, tool permission, or Evidence IDs. Evidence IDs are
selected by the existing coordinator after trusted materialization.

The task is created against the exact run binding returned by `create_run()`.
No second state load or independent current-pointer lookup is introduced by
M8B-2.

## Recovery

The existing `TransmissionToolRoundTripCoordinator.resume(...)` implementation
is reused unchanged. M8B-2 does not add a parallel recovery abstraction or
require callers to manually reconstruct the production graph. The new
application method starts a new run/round trip; coordinator-level recovery
may be exercised using services owned by the `ProductionApplication` and is
covered by the existing coordinator tests. This is coordinator-level recovery,
not a separate `ProductionApplication` resume API; callers must not bypass
trusted application composition to claim application-level recovery.

## Proposal / Revision Boundary

The selected M6B-2B workflow legitimately terminates at Evidence, Invocation B,
and AgentResult. It produces no authoritative canonical change. Therefore:

```text
ChangeProposal -> ChangeEngine -> immutable revision
NOT EXERCISED BY THIS SELECTED WORKFLOW
```

M8B-2 must not fabricate a proposal or mutate `DesignState` merely to extend
the path.

## Failure Behavior

Existing RunController, Gateway, mediator, ToolBroker, Evidence, and
coordinator fail-closed behavior remains authoritative. A stale or mismatched
run/task binding must fail closed before any external agent invocation or
engineering tool execution. ProductionApplication does not duplicate
coordinator or Gateway validation merely to reject before coordinator
delegation. Tool and Evidence records retain their existing exact identity,
binding, hash, and persistence checks.

## Tests

Add focused production integration tests that:

- enter through `ProductionApplication.create()` and
  `run_transmission_round_trip()`;
- verify the task uses the exact returned run binding and exact tool permission;
- verify the adapter is the only fake boundary;
- verify one invocation-A ToolCall/ToolResult and one trusted Evidence;
- verify Invocation B receives Evidence through ContextBuilder;
- verify no second successful torque ToolCall;
- verify trusted production agent identity is preserved;
- verify canonical state remains unchanged;
- verify existing coordinator recovery remains non-repeating;
- verify no proposal or revision is fabricated.

## Scope Exclusions

Do not add new engineering capability, provider integrations, CAD/FEA,
scheduling, generic workflow execution, ChangeProposal fabrication, or a new
recovery architecture.
