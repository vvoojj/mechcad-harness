# MechCAD Harness M6B-2A Tool Mediation Design

## Status and Scope

M6B-2A adds the first trusted bridge from an agent-authored semantic request to
an existing deterministic MechCAD tool. The first capability is
`transmission.torque`, resolved by trusted policy to
`mechcad-calc-torque@1.0`.

The bounded flow is:

```text
Invocation A
  -> validated AgentAuthoredResponsePayload
  -> AgentToolRequestDraft
  -> trusted AgentToolMediator
  -> immutable ToolMediationRecord
  -> capability authorization and exact tool resolution
  -> TaskDefinition.allowed_tools authorization
  -> binding recheck
  -> ToolBroker.execute(evidence_node=None)
  -> persisted ToolCall / ToolResult
  -> finalized ToolMediationRecord
```

M6B-2A stops at `ToolResult`. It does not create Evidence, perform Invocation
B, apply proposals, mutate `DesignState`, retry, schedule, or run an
autonomous loop. The model has no direct tool, shell, Python, filesystem,
OpenCode, MCP, HTTP, or engineering endpoint access.

M6B-1 behavior remains unchanged except for the backward-compatible authored
response field specified below.

## Existing Infrastructure

M5 already provides the required deterministic execution substrate:

- `ToolRegistry.resolve(name, version)` performs exact name/version lookup.
- `ToolRegistration.input_model` defines the authoritative typed input schema.
- `ToolBroker.execute(...)` validates run/task binding and
  `TaskDefinition.allowed_tools`, persists `ToolCall` before handler execution,
  persists `ToolResult`, and uses the registered handler and provenance path.
- `ToolBroker.execute(..., evidence_node=None)` performs no Evidence write.
- `ToolStore` persists immutable tool records under the run directory.
- `AgentStore` persists immutable agent invocations and results under the same
  run directory.

There is no existing trusted post-`ToolResult` Evidence materialization API
that performs the required binding/freshness recheck. M6B-2B must design and
add that API. M6B-2A must not call `EvidenceStore` directly as a workaround.

## Authored Request Contract

`AgentToolRequestDraft` is a strict Pydantic model with exactly these semantic
fields:

```text
capability: non-empty string
arguments: JSON-safe object
```

The model rejects extra fields and empty capability values. `arguments` is a
JSON object whose recursively contained values are limited to JSON-safe
values: null, booleans, finite numbers, strings, arrays, and objects with
string keys. Runtime Python objects, model instances, bytes, sets, tuples
with non-JSON behavior, dates, decimals, callables, and non-finite numbers are
not accepted. Canonical serialization uses the repository's deterministic JSON
encoding; the canonical arguments hash is computed only after validation.

`AgentAuthoredResponsePayload` gains:

```text
tool_requests: tuple[AgentToolRequestDraft, ...] = ()
```

The default preserves all existing M6B-1 payloads. The field is authored
semantic data only. It cannot contain an exact tool name/version, identity,
project/run/task IDs, revision or state hash, ToolCall/ToolResult/Evidence IDs,
status, hashes, or provenance. `materialize_agent_response(...)` remains
responsible only for canonical reasoning objects and does not execute or
mediate tool requests.

Malformed authored data fails validation before trusted mediation. A validated
response containing more than one request fails closed with
`TOO_MANY_TOOL_REQUESTS`; the first request is not executed. A validated
response containing no request completes the existing M6B-1 path unchanged.

## Trusted Mediation Architecture

Introduce a distinct `AgentToolMediator` in
`src/mechcad_harness/agents/tool_mediation.py`. The mediator receives the
already validated authored response, the persisted source `AgentInvocationRecord`
or equivalent request binding, the trusted `AgentIdentity`, the current run
and task authority, and an existing `ToolBroker`.

The gateway ordering is:

1. Build and persist `AgentInvocationRecord` before adapter invocation, as in
   M6B-1.
2. Invoke the adapter and validate its complete
   `AgentAdapterExecutionOutcome`.
3. Materialize and persist the canonical `AgentResult` for the reasoning
   response. A successfully validated agent response remains
   `AgentResultStatus.SUCCEEDED`, even if later deterministic mediation fails.
4. If `tool_requests` is non-empty, invoke the trusted mediator with the
   persisted invocation ID, canonical binding, and exact trusted agent identity.
5. The mediator persists and finalizes its own records independently of
   `AgentResult` status.

This preserves the distinction between successful reasoning and unsuccessful
tool mediation. Adapter/schema failures remain failed `AgentResult` outcomes;
mediation failures are represented by `ToolMediationRecord` and do not get
rewritten as LLM failures. The source invocation ID and canonical AgentResult
ID are retained as links in the mediation context; the mediation record itself
must at minimum link the source invocation ID.

## Durable Mediation Record

Use `ToolMediationRecord` as the durable trusted audit model. It is immutable
after each exclusive filesystem write; finalization writes a new immutable
record only if the record identity is designed as a state transition record,
or, preferably, uses one record whose lifecycle is persisted through a
repository-approved immutable transition mechanism. The implementation plan
must preserve the repository's exclusive-write rule and must not overwrite an
existing JSON record.

The record contains at minimum:

```text
mediation_id                  deterministic ID
invocation_id                 source Invocation A ID
agent_name                    trusted agent name
agent_version                 trusted agent version
ordinal                       request ordinal within the invocation
capability                    semantic capability
arguments                     canonical JSON-safe arguments
arguments_hash                canonical arguments hash
bound_revision                trusted original revision
bound_state_hash              trusted original state hash
status                        mediation lifecycle/status
resolved_tool_name            exact tool name, when resolution succeeds
resolved_tool_version         exact tool version, when resolution succeeds
tool_call_id                  ToolCall ID, when execution begins
tool_result_id                ToolResult ID, when execution completes
failure_kind                  typed failure kind, when mediation fails
```

The record never stores private reasoning and never accepts IDs, hashes,
provenance, bindings, or status from the authored request. The mediator derives
all such values from trusted invocation/run/task state, canonical arguments,
the capability policy, and ToolBroker results.

The mediation record is persisted before `ToolBroker.execute` is called. At
that point it contains the trusted request, binding, policy-selected capability
and an execution-pending status. If persistence fails, mediation stops with
`MEDIATION_PERSISTENCE_FAILURE` and ToolBroker is not called. A record write
failure is never silently converted into an agent finding.

Because the current `ToolStore` writes immutable records, implementation must
choose a repository-consistent immutable transition representation before code
is added. The preferred narrow design is a mediation record event stream or
separate immutable initial/final records linked by the deterministic
`mediation_id`; the logical `ToolMediationRecord` remains the authoritative
record view. No mutable in-place update is permitted.

## Capability Policy

M6B-2A uses a small typed code-based trusted registry, not YAML and not a new
configuration subsystem. No established typed configuration mechanism exists
that would make `config/agent_tool_permissions.yaml` smaller or safer.

The initial exact policy contains one mapping:

```text
trusted agent: mechcad-transmission@1.0
capability:    transmission.torque
tool:          mechcad-calc-torque@1.0
```

Capability lookup uses exact `(agent_name, agent_version, capability)` matching
and denies by default. The authored capability is only a lookup key. The model
cannot add a mapping, choose a tool version, or request an unregistered exact
tool. Unknown capability produces `UNKNOWN_TOOL_CAPABILITY`. A known
capability requested by an agent identity that is not authorized produces
`TOOL_CAPABILITY_NOT_AUTHORIZED`.

After policy resolution, the mediator calls the existing exact
`ToolRegistry.resolve("mechcad-calc-torque", "1.0")`. If that trusted exact
registration is unavailable, mediation fails with a typed unavailable-tool
failure and ToolBroker is not called.

## Permission Gates

Both gates are mandatory and independent:

1. **Trusted capability gate:** exact trusted identity
   `mechcad-transmission@1.0` must authorize `transmission.torque` and resolve
   it to `mechcad-calc-torque@1.0`.
2. **Task execution gate:** the immutable bound `TaskDefinition.allowed_tools`
   must authorize the exact resolved permission `mechcad-calc-torque@1.0`, using
   the existing ToolBroker semantics.

The mediator must not expand `allowed_tools`, rewrite the task, or treat the
semantic capability as task permission. If the task gate is absent or rejects
the exact tool, ToolBroker must not execute and the mediation record records a
typed authorization failure. The mediator may use a preflight equivalent for
clear diagnostics, but ToolBroker remains the final authority and the actual
execution path.

## Argument Authority

The mediator does not duplicate the torque schema. It passes the validated,
canonical JSON-safe `arguments` object unchanged to:

```text
ToolBroker.execute(
    run_id,
    task_id,
    "mechcad-calc-torque",
    "1.0",
    arguments,
    evidence_node=None,
)
```

The existing `ToolRegistration.input_model` and ToolBroker validation remain
authoritative. Mediation must not drop unknown keys, rename fields, add
aliases, convert units, infer defaults, coerce semantic values, or repair
malformed arguments. Invalid arguments therefore use existing ToolBroker/tool
validation semantics where possible. The invalid-input handler is not called;
ToolBroker persists the normal ToolCall and failed ToolResult according to its
existing behavior.

## Ordering and Statuses

The mediator performs these checks in order:

1. Validate the authored response and request cardinality.
2. Reject duplicate semantic requests within the same invocation.
3. Confirm the source invocation and trusted identity binding.
4. Canonicalize JSON-safe arguments and compute the arguments hash.
5. Resolve the exact trusted capability mapping.
6. Resolve the exact registered tool/version.
7. Verify the immutable task permission gate.
8. Re-read run, task definition, and task state binding immediately before
   persisting the pending mediation record.
9. Persist the pending mediation record.
10. Call `ToolBroker.execute(..., evidence_node=None)`.
11. Record ToolCall and ToolResult IDs and finalize the mediation record using
    immutable persistence.

The logical statuses distinguish at least `pending`, `succeeded`, and `failed`.
Failure kinds include:

- `MALFORMED_TOOL_REQUEST`
- `TOO_MANY_TOOL_REQUESTS`
- `DUPLICATE_TOOL_REQUEST`
- `UNKNOWN_TOOL_CAPABILITY`
- `TOOL_CAPABILITY_NOT_AUTHORIZED`
- `UNAVAILABLE_TRUSTED_TOOL`
- `TASK_TOOL_NOT_AUTHORIZED`
- `INVALID_TOOL_ARGUMENTS`
- `STALE_TOOL_REQUEST_BINDING`
- `TOOL_BROKER_EXECUTION_FAILURE`
- `MEDIATION_PERSISTENCE_FAILURE`

Pre-record validation failures may be represented by a failed mediation record
when enough trusted fields exist to create one; if the authored request cannot
be parsed at all, the existing failed AgentResult/schema path records the
validation failure and no ToolBroker call occurs. The implementation must make
this distinction explicit rather than claiming a durable mediation record for
an unparseable request.

## Duplicate Semantics

M6B-2A permits at most one request, but duplicate detection is still explicit
and occurs before the cardinality decision for a request collection. Canonical
duplicate identity is:

```text
(source invocation ID, capability, canonical arguments)
```

If duplicate semantic requests are present, mediation fails closed with
`DUPLICATE_TOOL_REQUEST`; no request executes. It does not silently deduplicate
and does not execute one request while ignoring another. Cross-invocation
idempotency is out of scope.

## Stale Binding Semantics

The mediator never rebinds a request or result to newer canonical state.

If the run/task binding changes after the agent response but before mediation
record persistence or ToolBroker execution, the mediator records
`STALE_TOOL_REQUEST_BINDING`, does not call ToolBroker, and does not create
Evidence.

If state advances while ToolBroker executes, the ToolBroker call and result
remain bound to the original revision/state hash. The mediation record becomes
failed/stale with `STALE_TOOL_REQUEST_BINDING` after the trusted post-call
binding check. The existing ToolResult is retained as historical execution
data; it is not rebound, discarded, or treated as current Evidence.

This check is deliberately not used to materialize Evidence in M6B-2A. A
future M6B-2B flow must perform the approved post-result freshness check before
Evidence creation.

## ToolBroker and Evidence Boundary

All mediated execution uses the existing ToolBroker, ToolContext, ToolCall,
ToolResult, persistence, exact registry, input model, handler, and backend
provenance behavior. No alternate torque calculator or direct handler call is
allowed.

Every mediated call explicitly supplies `evidence_node=None`. M6B-2A therefore
creates no Evidence, even if the tool registration declares potential Evidence
nodes. M6B-2A also does not call `EvidenceStore`, does not fabricate an
Evidence ID, and does not add ToolResult data to the agent context.

M6B-2B owns the later boundary:

```text
Invocation A
  -> AgentToolRequestDraft
  -> ToolMediationRecord
  -> ToolBroker.execute(evidence_node=None)
  -> ToolResult
  -> trusted binding/freshness recheck
  -> separately approved Evidence materialization
  -> CURRENT Evidence
  -> fresh Invocation B with explicit selected_evidence_ids
```

M6B-2B must add a trusted post-ToolResult Evidence materialization API if no
existing suitable API has been introduced by then. It must not bypass that API
with an ad-hoc mediation-layer `EvidenceStore` call.

## Explicit Non-Goals

M6B-2A does not:

- add `Component.transmission` or activate `/components/*/transmission`;
- apply a ChangeProposal automatically;
- mutate `DesignState`;
- create Evidence or invoke a second reasoning pass;
- expose tools to `.opencode` project agents;
- add YAML capability policy or general configuration infrastructure;
- add autonomous iteration, retries, scheduling, dependency execution, or
  model-driven permission expansion;
- support capabilities other than `transmission.torque`;
- guarantee cross-invocation idempotency;
- run a real Luna mediated workflow.

## Acceptance Criteria

Offline/FakeAgent tests must prove:

1. `AgentToolRequestDraft` has only `capability` and JSON-safe `arguments`.
2. Extra fields, empty capability, runtime objects, and non-JSON-safe values
   are rejected.
3. `tool_requests=()` preserves all existing M6B-1 authored responses.
4. More than one request fails closed with `TOO_MANY_TOOL_REQUESTS`.
5. Duplicate semantic requests fail closed with `DUPLICATE_TOOL_REQUEST` and
   execute zero times.
6. The durable mediation record contains trusted binding, identity, ordinal,
   capability, canonical arguments/hash, status, and linked execution IDs.
7. The pending mediation record is persisted before ToolBroker execution; a
   persistence failure prevents execution.
8. Authored data cannot control trusted IDs, exact tool/version, bindings,
   status, hashes, or provenance.
9. Unknown capability fails with `UNKNOWN_TOOL_CAPABILITY`.
10. Unauthorized trusted identity/capability fails with
    `TOOL_CAPABILITY_NOT_AUTHORIZED`.
11. `TaskDefinition.allowed_tools` remains a required independent execution
    gate.
12. `transmission.torque` resolves only to exact
    `mechcad-calc-torque@1.0`.
13. Missing trusted exact registration fails closed.
14. Arguments reach ToolBroker unchanged and the existing input model decides
    validity.
15. Invalid arguments do not invoke the torque handler and preserve the
    existing ToolCall/failed ToolResult semantics.
16. A stale-before-execution binding fails with
    `STALE_TOOL_REQUEST_BINDING` and creates no ToolCall.
17. A state advance during execution retains the original-bound ToolResult and
    marks mediation stale/failed without rebinding.
18. The actual path uses ToolBroker and persists canonical ToolCall/ToolResult.
19. The mediator passes `evidence_node=None`.
20. No Evidence file is created.
21. No DesignState revision or content changes.
22. No proposal is applied, no OpenCode tool is exposed, and no autonomous loop
    runs.
23. Existing M6B-1 tests remain passing.

## M6B-2B Future Acceptance

M6B-2B, not this milestone, must prove one real
`mechcad-transmission@1.0` Invocation A emits at most one
`transmission.torque` request; receives the exact torque ToolCall/ToolResult;
performs a trusted stale recheck; materializes trusted CURRENT Evidence;
performs a fresh Invocation B with explicit `selected_evidence_ids`; uses real
Luna `VALIDATED_JSON_TEXT`; does not inject ToolResult directly into the model;
allows at most two reasoning invocations; has no autonomous loop; and leaves
DesignState unchanged.

## Proposed Implementation and Test Files

Keep the implementation narrow:

```text
src/mechcad_harness/agents/models.py
  Add AgentToolRequestDraft and backward-compatible tool_requests.

src/mechcad_harness/agents/tool_mediation.py
  Add typed capability policy/registry and AgentToolMediator orchestration.

src/mechcad_harness/agents/persistence.py
  Add immutable mediation record persistence using repository-consistent
  exclusive writes and logical initial/final record loading.

src/mechcad_harness/agents/gateway.py
  Add only the orchestration hook needed to pass validated authored requests
  to the mediator after AgentResult persistence.

tests/unit/test_agent_tool_mediation.py
  Cover authored schema, policy, gates, persistence ordering, duplicate/stale
  handling, ToolBroker delegation, failure semantics, no Evidence, and no state
  mutation.
```

Existing `src/mechcad_harness/tools/broker.py`, registry, models, and
`TaskDefinition` should not change unless implementation reveals a narrowly
necessary compatibility correction. No new calculator, YAML file, or broad
configuration subsystem is proposed.

## Design Conflict Review

No unresolved design conflict remains. The only existing infrastructure nuance
is that `ToolBroker.execute` raises after persisting a failed `ToolResult`, so
the mediator must catch and classify that exception while retaining the
ToolBroker-generated records. The immutable `AgentStore` write pattern also
requires mediation lifecycle persistence to use immutable transitions or a
record-event representation rather than in-place JSON mutation. These are
implementation constraints, not changes to M6B-2A scope or authority.
