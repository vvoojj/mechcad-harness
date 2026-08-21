# M6B-1 Transmission Reasoning Agent Design

## Goal

Introduce `mechcad-transmission@1.0` as the first real engineering reasoning
agent while preserving MechCAD's canonical-state, evidence, proposal, and
deterministic-tool boundaries.

## Scope

The transmission agent reasons about preliminary drive architecture, reduction
requirements, speed/torque relationships, interfaces, backlash, packaging,
constraints, and missing engineering data. It receives only authoritative
context selected by the caller through the existing `ContextBuilder`.

The external response flow is:

```text
OpenCode
    -> AgentAuthoredResponsePayload
    -> trusted MechCAD materialization
    -> canonical AgentResponsePayload
    -> AgentResult
```

The milestone stops at immutable `AgentResult` persistence. It does not add
tool calling, automatic iteration, retries, proposal application, Evidence
creation, DesignState mutation, or stress/load-case workflows.

## Canonical Boundary

`DesignState` is unchanged. It currently has no transmission field.

The existing `/components/*/transmission` ownership rule is **reserved-but-
inactive ownership**. It is not presently writable or representable. M6B-1
must not emit a proposal targeting that path, use `Component.description`, or
use another unrelated field as a transmission storage surface. Pydantic
validation remains authoritative; a proposal attempting the reserved path must
not produce a canonical revision.

The first fixture requires zero ChangeProposals. It demonstrates engineering
reasoning with plain-string findings, Issues, and ConstraintRequests.

## Identity and Runtime Binding

Register the exact trusted identity:

```text
mechcad-transmission@1.0
role: transmission_engineer
```

Bind it explicitly to the project-scoped OpenCode agent
`mechcad-transmission`. OpenCode `/agent` discovery is not a trust mechanism.
The project agent uses the accepted deny-all, reasoning-only security model and
cannot read files, edit files, execute shell, call tools, use MCP, or invoke
other agents.

## Context and Authority

`ContextBuilder` remains unchanged. The caller explicitly selects relevant
requirements, constraints, and current Evidence. No automatic Evidence
discovery is added, and stale or unknown Evidence is rejected.

The agent may interpret current deterministic Evidence but must not turn its
own arithmetic into authoritative facts. If a deterministic input is missing,
it emits a `ConstraintRequest`; if supplied authoritative context reveals a
conflict, it emits an `Issue`.

The agent must not claim stress, tooth-root strength, contact stress, fatigue,
shaft stress, bearing life, buckling, safety factor, thermal design, FEA,
printed-part strength, or material allowables. Such needs become Issues or
ConstraintRequests.

## Authority Split

The agent owns semantic content only:

- status and summary;
- finding text;
- issue text;
- constraint-request text;
- proposal titles and operations.

The harness owns canonical authority and provenance:

- record IDs;
- revision and state-hash binding;
- proposal base revision and state hash;
- proposal actor;
- canonical lifecycle status.

Canonical `Issue`, `ConstraintRequest`, `ChangeProposal`, and
`AgentResponsePayload` models remain unchanged.

## Response Contract

`AgentAuthoredResponsePayload` is the strict external wire model. All six root
fields are required, findings/issues/constraint requests are plain strings,
and proposal drafts contain only semantic titles and operations. The native
schema is authoritative and input binding metadata must not be echoed.

`AgentGateway` may receive the smallest narrowly authorized extension needed to
materialize already-validated semantic authored data into the existing
canonical domain records. It does not change `DesignState` or canonical model
shapes.

The live fixture requests:

- `status = succeeded`;
- at least one useful plain-string finding;
- at least one intentional Issue or ConstraintRequest;
- `change_proposals = []`;
- no unexpected root fields or tool parts.

## Testing

Offline tests use `FakeAgentAdapter` and verify exact identity lookup,
explicit context selection, stale Evidence rejection, proposal binding and
non-application, reserved-path rejection, plain-string findings, Issue versus
ConstraintRequest semantics, no ToolBroker access, no direct filesystem/shell
access, no deterministic calculation, unchanged DesignState, immutable
AgentResult, stale in-flight handling, and continued M6A test-agent behavior.

An opt-in live test uses explicit `screenpipe/gpt-5.6-luna`, native
`AgentAuthoredResponsePayload` JSON Schema, retry count zero, no tools, and the
`mechcad-transmission` project agent. The trusted materializer then creates
canonical records and preserves separate authored/materialized hashes.

## Future Work

M6B-1 deliberately does not design `Component.transmission`. Real agent
outputs and missing-data requests will inform a separate future canonical model
design and approval.
