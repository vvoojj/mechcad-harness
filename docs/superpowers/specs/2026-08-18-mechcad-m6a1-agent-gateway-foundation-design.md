# M6A-1 Agent Gateway Foundation Design

## Goal

Introduce a strict, deterministic boundary for future reasoning agents using a
FakeAgentAdapter only, with read-only context, structured responses, immutable
invocation/result records, and stale-response protection.

## Flow

```text
M4 RunTask
    -> AgentGateway
    -> ContextBuilder
    -> AgentAdapter protocol
    -> FakeAgentAdapter
    -> validated AgentResponsePayload
    -> immutable AgentResult
```

The gateway validates binding, resolves exact agent identity/version, builds
minimal context, persists invocation before adapter execution, validates the
response, rechecks authoritative binding, persists an immutable result, and
returns it. It never applies proposals, invokes M2, mutates DesignState,
executes tools, or invokes external processes.

## Context

`AgentContext` contains only the authoritative canonical DesignState at the
bound revision, project/run/task identity, revision/state hash, task objective
and instructions, selected canonical requirements/constraints resolved by ID,
and selected persisted Evidence resolved by ID. The builder creates
`AgentEvidenceSummary` after verifying binding and M3 freshness; callers never
supply summary text. Unknown, mismatched, stale, or unknown-freshness Evidence
is rejected. It never dumps the workspace or automatically includes all
Evidence/ToolResults. Context is read-only by model boundary and serialized
using canonical JSON for deterministic hashing.

## Models

Strict models include:

- `AgentIdentity`;
- `AgentAdapterIdentity`;
- `AgentAdapterProvenance`;
- `AgentContext`;
- `AgentInvocationRequest`;
- `AgentResponsePayload`;
- `AgentInvocationRecord`;
- `AgentResult`.

Response payloads use existing `ChangeProposal`, `Issue`, and
`ConstraintRequest` models. Informational findings and summary text are not
canonical mutations. Every returned ChangeProposal must match the invocation
revision and state hash; otherwise the result is FAILED with
`RESPONSE_BINDING_MISMATCH`. An AgentResult is neither Evidence nor canonical
state.

## Registry and Adapter

`AgentRegistry` uses exact `(agent_name, agent_version)` lookup with
deterministic listing, duplicate rejection, and no plugin discovery. The
adapter protocol is external-runtime neutral and exposes only `invoke(request)`.
The only implementation is deterministic `FakeAgentAdapter`, configurable for
finding, proposal, issue, constraint request, invalid response, or failure.

## Persistence and Hashing

Records are stored under:

```text
projects/<project_id>/runs/<run_id>/agents/
    invocations/<invocation_id>.json
    results/<result_id>.json
```

Invocation is written before adapter execution. Invocation and result records
are exclusive immutable writes. Canonical JSON hashes cover normalized request
context and normalized response payload; object repr is never hashed.

## Stale Results

The gateway validates exact project/run/task/revision/state binding before
execution and reloads authoritative run/task state after adapter execution. If
the binding advanced, it persists the historical result as `STALE`. A stale
result cannot mutate DesignState, create Evidence, or be applied as a proposal.

## Exclusions

M6A-1 does not invoke OpenCode, LLMs, subprocesses, network, shell, Python
execution, ToolBroker tools, MCP, FreeCAD, transmission/material/structural
agents, automatic proposal application, autonomous loops, conversational
memory, stress/load cases, or C-3B.
