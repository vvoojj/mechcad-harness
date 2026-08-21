# MechCAD Harness M6B-2B First Real Transmission Tool Round Trip

## Status and Scope

This is a design-only document for M6B-2B. It does not authorize production
implementation and does not authorize a commit. M6B-2A is accepted and remains
the implementation baseline. M6B-2B must be implemented as one bounded,
explicit workflow:

```text
Invocation A
  -> mechcad-transmission@1.0
  -> one semantic transmission.torque request
  -> AgentToolMediator
  -> mechcad-calc-torque@1.0
  -> persisted ToolCall / ToolResult
  -> trusted post-result binding and freshness check
  -> trusted Evidence materialization
  -> CURRENT Evidence
  -> fresh Invocation B/session
  -> selected Evidence only
  -> final immutable AgentResult
```

Hard bounds are two reasoning invocations and one mediated tool execution. There
is no autonomous loop, retry loop, recursive invocation, scheduling extension,
proposal application, DesignState mutation, direct OpenCode tool, or generic
planner.

The trusted coordinator selects a per-invocation mediation mode:

```text
AgentToolMediationMode.ENABLED
AgentToolMediationMode.DISABLED
```

Invocation A uses `ENABLED`; Invocation B uses `DISABLED`. The mode is a trusted
harness argument to the Gateway/coordinator API, not an authored field, not
model-inferred, and not a capability permission. It never exposes tools to
OpenCode. The default remains `ENABLED` for the existing M6B-2A Gateway path,
preserving accepted behavior for callers that do not specify a mode.

With `DISABLED`, Gateway still validates the complete authored response and
persists the authored-request observation described below before persisting the
normal AgentResult. It does not invoke AgentToolMediator. Any observed B request
is classified by the coordinator as `SECOND_TOOL_REQUEST`, and no ToolCall can
result from B.

## Verified M6B-2A Baseline

### Agent request and gateway

`AgentToolRequestDraft` in `src/mechcad_harness/agents/models.py` contains only
`capability` and JSON-safe `arguments`. `AgentAuthoredResponsePayload` has a
backward-compatible defaulted `tool_requests` tuple. Canonical
`AgentResponsePayload` deliberately does not contain tool requests.

`AgentGateway.invoke` builds and persists the invocation, invokes the adapter,
validates the complete authored response, persists the request observation,
materializes and persists `AgentResult`, then calls `AgentToolMediator` only
when the trusted mode is `ENABLED` and the authored response contains requests.
Thus a successful reasoning `AgentResult` stays successful even if later
mediation fails.

M6B-2B adds the trusted `mediation_mode` argument at the Gateway boundary. It
must be an enum/equivalent trusted parameter with no authored or OpenCode
representation. The exact ordering is:

1. Persist `AgentInvocationRecord`.
2. Execute the adapter.
3. Validate the complete `AgentAuthoredResponsePayload`.
4. Persist the immutable `AgentToolRequestObservationRecord`.
5. Materialize canonical `AgentResponsePayload`.
6. Persist `AgentResult`.
7. If mode is `ENABLED` and requests are non-empty, invoke
   `AgentToolMediator`.
8. If mode is `DISABLED`, never invoke the mediator.

If observation persistence fails, Gateway fails closed: it does not persist a
successful AgentResult, does not mediate, and returns the repository-consistent
gateway/persistence failure outcome. This guarantees that every successful
AgentResult has a durable validated-request observation paired by
`invocation_id`.

### Mediation

`CapabilityPolicy` maps exactly:

```text
mechcad-transmission@1.0 + transmission.torque
  -> mechcad-calc-torque@1.0
```

`AgentToolMediator` creates a deterministic mediation ID from Invocation A,
ordinal, capability, and arguments hash. It persists `pending.json`, checks the
trusted binding, checks the task permission, and invokes:

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

It writes an immutable `final.json` transition. A successful final mediation
record contains `tool_result_id` and `tool_call_id`. A failed ToolBroker call
currently raises after persisting its failed ToolResult; the M6B-2B coordinator
must preserve those records and classify mediation failure without treating it
as a successful engineering finding.

The exact current permission check still accepts a bare tool name as an
alternative to `name@version`. M6B-2B must not rely on that compatibility path:
the coordinator and mediator acceptance tests must require the exact
`mechcad-calc-torque@1.0` entry. If production correction is needed, remove the
bare-name alternative as a narrow security fix rather than adding a new
permission mechanism.

### Deterministic ToolResult lookup

The successful torque result is located deterministically from the final
`ToolMediationRecord` as follows:

1. Load the unique final record at
   `projects/<project>/runs/<run>/agents/tool_mediation/<mediation_id>/final.json`.
2. Require `status == succeeded`, `capability == transmission.torque`, and a
   non-empty `tool_result_id` and `tool_call_id`.
3. Load the ToolResult at
   `projects/<project>/runs/<run>/tool_results/<tool_result_id>.json`.
4. Load the ToolCall at
   `projects/<project>/runs/<run>/tool_calls/<tool_call_id>.json`.
5. Verify all project, run, task, tool, version, binding, and hash linkages.

The mediation record is the deterministic index; directory scans are not the
lookup algorithm. The result is eligible only after this integrity validation.

## Durable Authored-Request Observation

Canonical `AgentResult` intentionally excludes `tool_requests`, so it cannot be
the recovery source for a crash after AgentResult A persistence and before the
mediator dispatch. Add a narrow immutable observation record:

```text
AgentToolRequestObservationRecord
  observation_id                 deterministic ID
  invocation_id                  source invocation
  agent_name, agent_version      trusted identity
  project_id, run_id, task_id    trusted scope
  bound_revision, bound_state_hash
  mediation_mode                 ENABLED or DISABLED
  tool_requests                  validated semantic requests only
  tool_requests_hash             canonical hash of the tuple
```

The record contains no private reasoning, raw model transcript, adapter secret,
ToolCall ID, ToolResult ID, Evidence ID, or hidden execution state. The
observation ID is deterministic from Invocation ID, mediation mode, and the
canonical tool-request hash. It is written with exclusive persistence at:

```text
projects/<project>/runs/<run>/agents/tool_request_observations/<observation_id>.json
```

The observation is written for both non-empty and empty request tuples. An empty
tuple is therefore durable proof of a validated zero-request response, while a
missing observation means the response did not reach the durable validation
boundary. Recovery loads this record rather than re-invoking the model.

The same observation is authoritative for Invocation A recovery, Invocation B
second-request detection, and audit proof that B emitted zero requests. It is
not added to canonical AgentResult.

## Existing Evidence Creation Authority

### Current inline path

`ToolBroker.execute` currently performs inline Evidence creation after a
successful handler result when `evidence_node` is non-null:

1. Resolve the exact `ToolRegistration`.
2. Reject an Evidence node not present in `registration.evidence_nodes`.
3. Validate inputs through `registration.input_model` and serialize normalized
   inputs.
4. Persist `ToolCall` with `input_hash = payload_hash(normalized_inputs)`.
5. Invoke the registered handler.
6. Serialize the output model and compute `output_hash`.
7. Obtain `backend_provenance` from `registration.provenance_handler()` when
   present.
8. Persist successful `ToolResult` with the ToolCall input hash and output hash.
9. Construct `Evidence` using the shared deterministic `EVD-` identity derived
   from project, run, ToolResult ID, and node, the requested node as
   `kind`, summary `"<tool_name> result"`, the ToolContext revision/state hash,
   producer type `tool`, trusted registration name/version, ToolResult ID,
   input/output hashes, and ToolResult backend provenance.
10. Write the Evidence through `EvidenceStore`, whose graph registry rejects an
    unknown node and whose exclusive write rejects a conflicting ID.
11. Return the result with `evidence_id` in the in-memory return value.

Important current facts:

- Before the M6B-2B shared-authority refactor, the inline Evidence ID was random
  UUID-based; M6B-2B replaces that construction with the shared deterministic ID.
- Evidence kind is caller-selected but constrained by registration.
- `Evidence` stores no raw ToolResult output, only summary and provenance/hash
  links.
- Builtin torque currently has no `evidence_nodes` and no provenance handler.
- `analysis.transmission.torque` is not currently present in the repository's
  default dependency graph. The graph supplied by each run is the actual
  authority, so both the default config and test fixture must declare it.
- The current inline implementation persists ToolResult before Evidence. If
  Evidence write fails, it raises after the successful ToolResult is durable.

### Recommended shared authority

Use one canonical trusted Evidence construction/materialization authority for
both paths. The recommended narrow refactor is:

```text
ToolEvidenceMaterializer
  - materialize_from_result(...)
  - validates trusted ToolCall/ToolResult/registration links
  - validates registration Evidence node
  - constructs canonical Evidence
  - writes through EvidenceStore

ToolBroker inline path
  -> persists ToolResult
  -> ToolEvidenceMaterializer.materialize_from_result(...)

M6B-2B post-result path
  -> loads persisted ToolCall/ToolResult
  -> performs current binding/freshness gate
  -> ToolEvidenceMaterializer.materialize_from_result(...)
```

This is Option 1 and is recommended. It preserves one Evidence format and one
producer/hash/provenance authority while allowing the post-result path to add a
freshness gate before calling it.

Option 2, a separate materializer that calls shared construction primitives, is
acceptable only if repository layering makes a public class impractical. It
must still have exactly one shared constructor/validation implementation.

Option 3, re-running ToolBroker merely to request Evidence, is rejected. It
would create a second ToolCall/ToolResult, repeat deterministic engineering
execution, complicate audit identity, and violate the one mediated execution
bound.

## Trusted Post-ToolResult Evidence API

Proposed repository-consistent API:

```text
ToolEvidenceMaterializer.materialize_from_result(
    project_id,
    run_id,
    task_id,
    tool_result_id,
    evidence_node,
    expected_revision,
    expected_state_hash,
)
```

The caller may select the approved workflow node, but may not provide Evidence
ID, producer identity, tool version, hashes, output, or backend provenance.
Those values come from the persisted ToolResult, linked ToolCall, and exact
ToolRegistration.

The materializer must:

1. Load ToolResult and require immutable persisted data.
2. Require `status == SUCCEEDED`, a dict output, and a non-empty output hash.
3. Load ToolCall by `call_id` and require matching project/run/task.
4. Require ToolCall and ToolResult exact tool name/version equality.
5. Require the expected exact tool/version from trusted policy/registration.
6. Require ToolCall and ToolResult binding equal the original Invocation A
   binding and the API expected revision/state hash.
7. Recompute the ToolCall input hash from persisted normalized inputs.
8. Recompute the ToolResult output hash from persisted output.
9. Resolve the exact registration and require `evidence_node` in its declared
   `evidence_nodes`.
10. Obtain provenance only from the trusted registration/result path.
11. Obtain the deterministic summary from the trusted registration-owned
    `evidence_summary_handler(output_payload)` hook.
12. Derive the Evidence identity according to the idempotency rule below.
13. Construct the existing `Evidence` model and write it exclusively through
    `EvidenceStore`.

No authored request or coordinator record can supply producer, version, hashes,
revision, state hash, backend provenance, or Evidence ID.

## Torque Evidence Node, Summary, and Registration

The exact node `analysis.transmission.torque` fits the existing architecture:
Evidence kinds are opaque dependency node strings, `EvidenceStore.write_evidence`
requires `DependencyGraph.knows(kind)`, and freshness uses graph invalidation
records. No separate Evidence registry exists.

The current architecture does require two narrow declarations before this node
can be materialized:

1. Add `analysis.transmission.torque` to the dependency graph's known nodes via
   the exact rule specified in the authoritative fixture section below.
2. Add `evidence_nodes=("analysis.transmission.torque",)` to the torque
   `ToolRegistration`.

The existing `TorqueOutput` model has exactly these normalized JSON fields:

```json
{
  "nominal_torque_nm": <finite number>,
  "design_torque_nm": <finite number>
}
```

`calc_torque` computes `nominal_torque_nm = force_n * lever_arm_m` and
`design_torque_nm = nominal_torque_nm * safety_factor`. Invocation B needs the
design result, so the trusted torque registration must declare an
`evidence_summary_handler` equivalent with the contract:

```text
evidence_summary_handler(output_payload) ->
  "Required design torque: <output_payload.design_torque_nm> N*m"
```

The handler reads only the validated normalized output model/payload, uses a
fixed harness formatting rule, and returns no model-authored text. The
materializer obtains the summary through this registration hook for both inline
and post-result Evidence. The round-trip coordinator never formats or computes
torque. `AgentEvidenceSummary.summary` then exposes the trusted result through
the normal ContextBuilder path; raw ToolResult output is never injected.

The builtin torque registration is a native deterministic harness calculation,
not an external backend call. Its `provenance_handler` remains absent and its
successful ToolResult and Evidence use `backend_provenance = None`. This matches
the existing optional native-tool convention and avoids fabricating a backend
identity solely to populate an optional field.

The torque node should not be connected to unrelated structural or packaging
nodes. Existing graph edges do not require a torque-specific edge for this
round trip. Invalidation must make a torque Evidence record STALE when an
authoritative input changes, and unknown/missing invalidation history must remain
UNKNOWN, never CURRENT.

## Eligibility and Race-Safe Ordering

The coordinator receives the successful final mediation record and uses its
trusted ToolResult ID. The exact ordering is:

```text
ToolResult persisted
  -> load mediation, ToolCall, ToolResult
  -> validate immutable identity/link/hash integrity
  -> re-read current active revision/state hash
  -> compare current binding with Invocation A / ToolResult binding
  -> stale? finalize coordinator as STALE_BEFORE_EVIDENCE; no Evidence
  -> current? call ToolEvidenceMaterializer
  -> Evidence persisted
  -> call EvidenceStore.get_evidence_freshness
  -> require CURRENT
  -> fresh Invocation B with selected_evidence_ids=(evidence_id,)
```

Eligibility fails closed unless all of the following hold:

- ToolResult is persisted and immutable.
- ToolResult status is `SUCCEEDED`.
- ToolCall exists and is immutable.
- ToolCall and ToolResult belong to the expected project/run/task.
- Exact trusted tool name/version is `mechcad-calc-torque@1.0`.
- ToolCall and ToolResult hashes recompute consistently.
- ToolCall and ToolResult binding equals Invocation A's original binding.
- Current active state equals that original binding.
- The requested node is declared by the exact ToolRegistration.
- No conflicting Evidence already exists for the logical materialization.

The pre-Evidence state check is necessary but not sufficient. If state changes
after the check and during or after Evidence persistence, the Evidence remains
immutable historical data with its original binding. It may become STALE
immediately. Before Invocation B, the coordinator must call
`EvidenceStore.get_evidence_freshness` and require `CURRENT`; otherwise it must
not invoke B. There is no rebinding and no mutable Evidence update.

`ContextBuilder` independently repeats binding and freshness checks when it
receives `selected_evidence_ids`. Both checks are required. A race after the
coordinator check therefore fails closed at either the explicit coordinator
check or ContextBuilder check.

## Authoritative Torque Fixture and Invalidation

Use the existing `DesignState.requirements: list[Requirement]` model. Each
Requirement is a `NamedModel` with `id`, `name`, `created_at`, and `description`.
The three authoritative fixture records are:

```text
Requirement(
  id="REQ-TORQUE-FORCE",
  name="Applied tangential force",
  description="Applied tangential force at the transmission output is 10 N.",
)
Requirement(
  id="REQ-TORQUE-ARM",
  name="Effective lever arm",
  description="Effective lever arm for the output force is 0.2 m.",
)
Requirement(
  id="REQ-TORQUE-SAFETY",
  name="Torque safety factor",
  description="Required deterministic design safety factor is 2.0.",
)
```

Their exact canonical JSON paths in the revision snapshot are:

```text
/requirements/REQ-TORQUE-FORCE/description
/requirements/REQ-TORQUE-ARM/description
/requirements/REQ-TORQUE-SAFETY/description
```

The dependency engine supports exact canonical paths: `path_matches` compares
all path segments and only treats a literal `*` segment as a wildcard. Therefore
use three exact rules:

```yaml
- when:
    - /requirements/REQ-TORQUE-FORCE/description
  invalidates:
    - analysis.transmission.torque
- when:
    - /requirements/REQ-TORQUE-ARM/description
  invalidates:
    - analysis.transmission.torque
- when:
    - /requirements/REQ-TORQUE-SAFETY/description
  invalidates:
    - analysis.transmission.torque
```

These rules invalidate torque Evidence when FORCE, ARM, or SAFETY changes. An
unrelated Requirement path, such as `/requirements/REQ-OTHER/description`, does
not match any rule. Unrelated component, material, placement, interface, and
constraint paths also do not match, so those changes do not invalidate torque
Evidence. The fixture must select the three exact Requirement IDs into
Invocation A context; the LLM may copy their authoritative values into request
arguments but may not invent them.

## Evidence Idempotency

The pre-M6B-2B random Evidence ID is not sufficient for recovery-safe
post-ToolResult materialization. M6B-2B uses a deterministic logical
materialization ID derived from trusted:

```text
project_id\nrun_id\ntool_result_id\nevidence_node
```

Use the repository's existing `EVD-` style with a deterministic UUID/hash. The
same ToolResult and node therefore identify the same logical Evidence. The
materializer must load an existing record at that deterministic ID before
writing:

- If it exists and every trusted field matches, return it as an idempotent
  success without writing a duplicate.
- If it exists but any field conflicts, fail with a typed Evidence identity or
  integrity failure. Never overwrite it.
- If it does not exist, write exclusively.
- A different node produces a different logical ID and is allowed only when the
  trusted ToolRegistration declares that node. The M6B-2B workflow itself
  requests exactly one approved torque node.

The materializer must not use `ToolResult.evidence_id` as the primary identity:
  ToolResult remains immutable and post-result materialization needs a stable
  identity independent of an in-memory return value. The shared inline path
  returns the deterministic `evidence_id` without rewriting ToolResult.

## Bounded Workflow and Durable Record

Existing immutable Invocation, AgentResult, ToolMediationRecord, ToolCall,
ToolResult, and Evidence records already provide the domain audit trail, but no
single durable record currently links Invocation A through Invocation B. A
small dedicated M6B-2 workflow record is warranted for crash recovery because
the coordinator must distinguish completed durable boundaries without scanning
or re-running execution.

Recommended record:

```text
TransmissionToolRoundTripRecord
  workflow_id
  project_id, run_id, task_id
  bound_revision, bound_state_hash
  invocation_a_id, agent_result_a_id
  mediation_id, tool_call_id, tool_result_id
  evidence_id, evidence_node
  invocation_b_id, agent_result_b_id
  status
  failure_kind
```

Persist immutable lifecycle transitions as separate files or an append-only
event sequence. Do not mutate one JSON file in place. The logical record view
must be reconstructable by deterministic `workflow_id` and exclusive
transitions.

The coordinator is an explicit finite state machine:

```text
START
  -> INVOCATION_A_SUCCEEDED
  -> TOOL_MEDIATION_SUCCEEDED
  -> EVIDENCE_CURRENT
  -> INVOCATION_B_SUCCEEDED
  -> COMPLETE
```

Terminal failures include `INVOCATION_A_FAILED`, `NO_TOOL_REQUEST`,
`TOO_MANY_TOOL_REQUESTS`, `MEDIATED_TOOL_FAILED`, `STALE_BEFORE_EVIDENCE`,
`EVIDENCE_MATERIALIZATION_FAILED`, `EVIDENCE_NOT_CURRENT`,
`INVOCATION_B_FAILED`, `INVOCATION_B_STALE`, and `SECOND_TOOL_REQUEST`.

There is no `while` loop. The coordinator calls Gateway A once, mediator once
through Gateway A's existing hook, materializer once, and Gateway B once.

## Invocation A Fixture

The fixture must make all torque inputs authoritative before Invocation A. The
existing torque input model requires `force_n`, `lever_arm_m`, and
`safety_factor`. Store those values as the three Requirement records and exact
paths already defined above. The fixture values are:

```text
REQ-TORQUE-FORCE:
  Applied tangential force at the transmission output is 10 N.
REQ-TORQUE-ARM:
  Effective lever arm for the output force is 0.2 m.
REQ-TORQUE-SAFETY:
  Required deterministic design safety factor for this preliminary calculation is 2.0.
```

The harness fixture, not the prompt and not the LLM, owns the numeric values.
The test may verify the expected deterministic output as an assertion, but must
not pre-compute or insert torque as prompt text. Invocation A receives selected
authoritative requirement IDs and is allowed to copy the three values into
semantic `tool_requests.arguments`.

No ConstraintRequest is needed for these three values. A genuinely missing
backlash or holding/backdrive requirement may still be requested, but the
M6B-2B round-trip acceptance fixture should keep the result focused and require
zero ChangeProposals.

## Invocation A Authored Contract

The minimal `.opencode/agents/mechcad-transmission.md` change should add:

- deterministic calculations must be requested through semantic
  `tool_requests` capabilities allowed by the supplied protocol/context;
- when authoritative inputs for an allowed deterministic capability are present,
  request that capability rather than performing authoritative arithmetic in
  reasoning;
- copy only supplied authoritative values into arguments; never invent numbers;
- do not name implementation tool names or versions;
- do not calculate authoritative torque directly;
- when CURRENT Evidence already supplies the deterministic result, reason from
  that Evidence and do not request the same calculation again;
- for this bounded workflow, return exactly one `transmission.torque` request in
  Invocation A, zero ChangeProposals, and no implementation metadata.

The prompt must not expose ToolBroker, registration, version, persistence,
Evidence IDs, or OpenCode mechanics. It should not say that the model can invoke
tools. It authors a semantic request only.

Expected Invocation A response:

```text
status = succeeded
findings = at least one useful reasoning observation
tool_requests = exactly one transmission.torque request
change_proposals = []
issues = [] unless a real supplied conflict exists
constraint_requests = [] unless a real missing input exists
```

## Tool Execution and ToolResult-to-Evidence Flow

The trusted mapping and both M6B-2A authorization gates remain unchanged:

```text
transmission.torque
  -> trusted policy
  -> mechcad-calc-torque@1.0
```

The mediator must pass `evidence_node=None`. It must not ask the model to select
the node. After ToolResult success, the coordinator selects the approved
`analysis.transmission.torque` node and calls the trusted materializer.

The materializer creates exactly one Evidence record with:

- deterministic Evidence ID from ToolResult ID plus node;
- kind `analysis.transmission.torque`;
- trusted summary `Required design torque: <design_torque_nm> N*m`, generated by
  the torque registration's `evidence_summary_handler` from normalized output;
- revision/state hash from the persisted ToolResult/ToolCall binding;
- producer type `tool`;
- producer name/version from trusted registration/result;
- producer result ID from ToolResult;
- input/output hashes from validated persisted records;
- backend provenance from ToolResult/registration authority.

No raw output is copied into agent context by the coordinator. The normal
`AgentEvidenceSummary` path exposes only the persisted summary and trusted
source links.

## Invocation B

Invocation B is a new call to:

```text
AgentGateway.invoke(..., selected_evidence_ids=(torque_evidence_id, ...))
```

It uses a fresh OpenCode session because `OpenCodeAgentAdapter.invoke` creates a
new session for each invocation. The coordinator must not reuse Invocation A's
session, raw response, request, ToolResult, ToolCall, mediation record, or
hidden execution state.

The only execution-specific context supplied to B is the normal
`ContextBuilder`-generated `AgentEvidenceSummary` for the explicitly selected
CURRENT Evidence. ContextBuilder also supplies the normal authoritative design
state and any explicitly selected requirements/constraints. Raw ToolResult and
ToolCall payloads are never injected.

Invocation B must:

- recognize the selected current torque Evidence;
- produce at least one useful finding grounded in that Evidence;
- produce zero ChangeProposals;
- emit zero tool requests;
- not repeat torque arithmetic as an unsupported claim;
- terminate the workflow if any tool request is authored.

The gateway's existing canonical `AgentResult` does not preserve authored tool
requests. The coordinator must inspect the validated authored response returned
by the B gateway boundary or add a narrow workflow-facing return value without
changing canonical AgentResult semantics. B requests are a bounded failure, not
an invitation to invoke the mediator.

With the trusted B mode set to `DISABLED`, Gateway never invokes the mediator.
The persisted B observation is the sole request-cardinality authority. If its
tuple is non-empty, the coordinator records `SECOND_TOOL_REQUEST` and ends the
workflow with zero second ToolCalls. If its tuple is empty, the observation is
durable proof that B emitted no tool request and the workflow may complete.

B follows the same ordering as A: adapter response validation, observation
persistence, AgentResult B persistence, then coordinator inspection. The
coordinator never dispatches B's observation to the mediator.

## Failure and Status Semantics

Historical records are never rewritten retroactively.

| Failure | Durable records | Workflow result |
| --- | --- | --- |
| Invocation A adapter/schema failure | Invocation A; failed AgentResult A | `INVOCATION_A_FAILED` |
| Invocation A emits zero requests | Invocation A; succeeded AgentResult A | `NO_TOOL_REQUEST` |
| Invocation A emits more than one request | Invocation A; succeeded AgentResult A; failed mediation when recordable | `TOO_MANY_TOOL_REQUESTS` |
| Tool mediation authorization/persistence failure | Invocation A; AgentResult A; mediation transitions; no ToolCall if preflight failed | `MEDIATED_TOOL_FAILED` |
| Tool execution failure | Invocation A; AgentResult A; mediation; ToolCall; failed ToolResult | `MEDIATED_TOOL_FAILED` |
| Stale before Evidence | Invocation A; AgentResult A; successful ToolResult; failed/stale mediation; no Evidence | `STALE_BEFORE_EVIDENCE` |
| Evidence materialization failure | Prior records; no valid new Evidence or conflicting immutable record | `EVIDENCE_MATERIALIZATION_FAILED` |
| Evidence not CURRENT before B | Prior records; Evidence retained as historical, possibly stale/unknown | `EVIDENCE_NOT_CURRENT` |
| Invocation B adapter/schema failure | Invocation B; failed AgentResult B | `INVOCATION_B_FAILED` |
| Invocation B stale | Invocation B; stale AgentResult B with response retained where existing gateway semantics allow | `INVOCATION_B_STALE` |
| Invocation B emits another request | Invocation B; succeeded AgentResult B; no second ToolCall | `SECOND_TOOL_REQUEST` |
| Request observation persistence failure | Invocation record and adapter outcome only; no successful AgentResult; no mediation | `OBSERVATION_PERSISTENCE_FAILED` |

Invocation A may be `SUCCEEDED` even when mediation or post-tool workflow fails.
`ToolMediationRecord` owns mediation failure. The Evidence materializer and
round-trip record own post-tool failures. Invocation B has its own independent
AgentResult status.

## Final Bounded Flow

The implementation must realize this exact finite sequence:

```text
RoundTrip start
  -> Invocation A, mediation_mode=ENABLED
  -> durable AgentToolRequestObservationRecord
  -> AgentResult A
  -> exactly one transmission.torque request
  -> AgentToolMediator
  -> exactly one ToolCall / ToolResult
  -> current binding recheck
  -> ToolEvidenceMaterializer
  -> one deterministic torque Evidence with trusted numeric summary
  -> active binding equality check
  -> EvidenceStore freshness == CURRENT
  -> fresh Invocation B, mediation_mode=DISABLED,
       selected_evidence_ids=(torque_evidence_id,)
  -> durable AgentToolRequestObservationRecord
  -> AgentResult B
  -> observation.tool_requests == ()
  -> COMPLETE
```

The hard counts are exactly: two reasoning invocation attempts maximum, one
mediated tool execution maximum, one Evidence materialization maximum, and zero
second tool executions. Any B request terminates with `SECOND_TOOL_REQUEST`
before mediator dispatch.

## Crash and Resume Semantics

Recovery inspects immutable records and advances only across already durable
boundaries:

- After Invocation A: load Invocation A, AgentResult A, and the durable authored
  request observation. If A is successful and the observation says
  `ENABLED` plus exactly one request, continue to the single mediation step.
  If the observation says zero requests or more than one, terminate with the
  recorded bounded failure. Never invoke A again merely to recover requests.
- If the process crashes after observation persistence but before AgentResult A,
  the observation remains historical but no false successful AgentResult exists.
  Recovery does not mediate from the observation alone; it requires the
  AgentResult boundary. If the process crashes immediately after AgentResult A,
  the observation is already durable and recovery uses it to continue without
  re-invoking A.
- After ToolResult: load the final mediation record and linked ToolCall/ToolResult.
  If the ToolResult is successful, perform the current binding check and
  materialization step. Never call ToolBroker again.
- After Evidence persistence: load deterministic Evidence ID, verify all fields,
  then run the freshness check. If CURRENT, proceed to B; if stale/unknown,
  terminate without B.
- Before Invocation B: if no B invocation record exists and Evidence is CURRENT,
  call Gateway exactly once with trusted `mediation_mode=DISABLED`. If an
  Invocation B and AgentResult B already exist, do not call the adapter again.
- After Invocation B: load and validate the immutable AgentResult B and its
  durable observation. A zero-request observation completes the workflow. A
  non-empty observation terminates as `SECOND_TOOL_REQUEST` without mediation.
- If the process crashes immediately after AgentResult B, the durable B
  observation determines the zero/nonzero request decision and recovery does
  not re-invoke B. If observation persistence itself fails for either
  invocation, no successful AgentResult is persisted and no mediator execution
  occurs.

The observation/AgentResult boundary is therefore ordered as:

```text
validated authored response
  -> observation persisted
  -> canonical AgentResult persisted
```

An observation without an AgentResult is historical evidence of a partially
completed invocation, not permission to execute mediation or complete the
workflow.
- If the process crashes immediately after AgentResult B, the durable B
  observation determines the zero/nonzero request decision and recovery does
  not re-invoke B. If observation persistence itself fails for either
  invocation, no successful AgentResult is persisted and no mediator execution
  occurs.

If an immutable transition write has ambiguous outcome, recovery must inspect the
target record and either accept a matching record or fail with a persistence
failure. It must not repeat ToolBroker execution to resolve ambiguity.

`RunController.resume_run` remains the canonical run integrity check. M6B-2B
should add only a thin round-trip recovery method or coordinator record reader;
it should not turn `RunController` into a general workflow engine.

## Real OpenCode Profile

The live acceptance profile remains the accepted M6B-1 profile:

```text
agent:               mechcad-transmission
identity:            mechcad-transmission@1.0
provider:            screenpipe
model:               gpt-5.6-luna
model selection:     explicit
response mode:       VALIDATED_JSON_TEXT
project directory:   E:/repo/mechcad-harness
OpenCode tools:      none
```

The adapter must continue to send `tools: {}` and reject tool parts. Each
gateway invocation creates a distinct session and records its own provenance.
No native structured-output mode or model matrix is part of M6B-2B.

## Offline Test Plan

Use `FakeAgentAdapter` first. Add focused tests for:

1. Torque registration declares the approved Evidence node and graph knows it.
2. Shared materializer constructs the same Evidence fields as the inline path.
3. Post-result materialization loads ToolCall/ToolResult through the mediation
   record and rejects missing, mismatched, failed, or tampered records.
4. Input/output hashes, tool/version, project/run/task, and binding checks fail
   closed.
5. Stale before Evidence writes no Evidence and retains ToolResult.
6. State change during or after Evidence persistence leaves immutable historical
   Evidence and prevents B unless freshness reports CURRENT.
7. Same ToolResult plus node is idempotent; conflicting second write fails;
   different undeclared node fails.
8. `ContextBuilder` receives exactly the new Evidence ID and rejects stale or
   unknown Evidence.
9. A full FakeAgent two-invocation round trip produces one ToolCall, one
   ToolResult, one Evidence, two Invocation records, two AgentResults, and no
   DesignState mutation.
10. Invocation A zero requests, multiple requests, adapter failure, tool failure,
    stale, materialization failure, B failure, B stale, and B second-request
    cases end in the typed workflow failure without hidden retries.
11. Recovery from each durable boundary does not repeat a successful tool call
    or reasoning invocation.
12. B receives no raw ToolResult, ToolCall, mediation record, or prior raw model
    response and emits no tool request.
13. No proposal is applied, no OpenCode tools are exposed, and no autonomous
    loop exists.
14. A trusted A mode is `ENABLED`, a trusted B mode is `DISABLED`, and the mode
    cannot be supplied through authored JSON or OpenCode.
15. B authored requests are observed, produce `SECOND_TOOL_REQUEST`, and create
    zero second ToolCalls.
16. The authored observation survives a simulated crash after AgentResult A;
     recovery uses it and never invokes A again to recover tool requests.
17. A zero-request B observation is durable and proves B emitted no requests.
18. A crash after observation persistence but before AgentResult leaves the
    observation historical, persists no successful AgentResult, and does not
    mediate from the observation alone.
19. A crash immediately after AgentResult B leaves the B observation durable;
    recovery decides zero/nonzero requests without invoking B again.
20. Observation persistence failure prevents a successful AgentResult and any
    mediator execution.
21. Normalized torque output fields `nominal_torque_nm` and
     `design_torque_nm` produce a trusted summary containing the exact
     `design_torque_nm` value and `N*m` unit; no model-generated arithmetic is
     involved.
22. ContextBuilder exposes that trusted summary to B through
     `AgentEvidenceSummary`, with no raw ToolResult injection.
23. Mediated preflight requires exact `mechcad-calc-torque@1.0`; bare
     `mechcad-calc-torque` alone fails and does not invoke the broker.
24. Shared deterministic Evidence identity preserves the existing inline
     ToolBroker Evidence regression: one ToolResult plus one node yields one ID,
     a different ToolResult yields a different ID, and repeating the same pair
     is idempotent while ToolResult stays immutable and Broker returns the ID.
25. Each exact authoritative torque requirement path invalidates torque Evidence;
     unrelated state changes do not.

The tests must assert exact execution counts, not only final files.

## Gated Live Acceptance Sequence

Run the acceptance in this order:

1. Offline post-ToolResult Evidence materialization tests.
2. Offline bounded two-invocation workflow with FakeAgentAdapter.
3. One live Invocation A control using the accepted profile and authoritative
   fixture.
4. One real mediated `transmission.torque` execution.
5. Verify exactly one persisted ToolCall and successful ToolResult, including
   trusted binding and hashes.
6. Materialize exactly one deterministic torque Evidence and verify
   `EvidenceStore` reports CURRENT.
7. Run exactly one live Invocation B in a fresh session with explicit selected
   Evidence.
8. Verify B used the Evidence, emitted no second tool request, and produced a
   useful finding with zero proposals.
9. Run the full offline regression suite.

Do not run five-model matrices. This milestone validates the bounded workflow,
not stochastic reliability benchmarking.

## Immutable Round-Trip Transition Layout

The workflow uses one deterministic `workflow_id`, derived from the trusted
project, run, task, and Invocation A identity. Its transitions are immutable
exclusive files:

```text
projects/<project>/runs/<run>/agents/roundtrips/<workflow_id>/
  00_started.json
  10_invocation_a.json
  20_tool_result.json
  30_evidence.json
  40_invocation_b.json
  50_complete.json
```

Failure transitions use the next applicable numbered terminal file with a
typed `failure_kind`; they do not overwrite a prior transition. Each transition
contains the cumulative trusted link fields needed for recovery, including the
observation ID and the relevant invocation, mediation, ToolCall, ToolResult,
Evidence, and AgentResult IDs. Recovery reads the highest valid transition,
checks that its predecessor exists, and permits only the single next state in
the finite sequence. It never scans for an arbitrary next action, retries a
successful call, or creates a general workflow engine.

## Expected Production and Test Files

Expected narrow production changes:

```text
src/mechcad_harness/tools/broker.py
  Delegate inline post-ToolResult Evidence creation to the shared authority.

src/mechcad_harness/tools/builtins.py
  Declare analysis.transmission.torque, native None provenance, and the trusted
  torque evidence summary handler.

src/mechcad_harness/tools/evidence.py (new, or repository-equivalent)
  Trusted ToolResult/ToolCall validation, deterministic identity, shared Evidence
  materialization, and registration-owned summary hook dispatch.

src/mechcad_harness/agents/tool_mediation.py
  Expose deterministic final-record lookup only if the existing record API is
  insufficient; preserve M6B-2A authorization and one-call semantics.

src/mechcad_harness/agents/gateway.py
  Add trusted mediation mode selection, durable request observation before
  dispatch, and no mediator call when mode is DISABLED.

src/mechcad_harness/agents/roundtrip.py (new, or repository-equivalent)
  Explicit two-invocation/one-tool coordinator, mode selection, and durable
  transitions.

src/mechcad_harness/agents/persistence.py (or roundtrip persistence module)
  Exclusive request-observation persistence and round-trip transition/recovery
  reads.

src/mechcad_harness/agents/context.py
  No semantic change expected; existing explicit Evidence selection/freshness
  checks are the authority.

config/dependencies.yaml
  Three exact Requirement-description invalidation rules for
  analysis.transmission.torque.

.opencode/agents/mechcad-transmission.md
  Minimal semantic tool_requests and CURRENT Evidence instructions.
```

Expected tests:

```text
tests/unit/test_tool_evidence_materializer.py (new or equivalent)
tests/unit/test_agent_roundtrip.py (new)
tests/unit/test_agent_tool_mediation.py
tests/unit/test_agent_authoritative_context.py
tests/unit/test_transmission_agent.py
tests/integration/test_transmission_agent_live.py
tests/unit/test_agent_gateway.py
tests/unit/test_tools.py
```

Exact file placement may follow existing package conventions, but no generic
workflow package or unrelated production refactor should be introduced.

## Option Comparison

### Option 1: shared trusted ToolResult-to-Evidence materializer

Recommended. It gives inline execution and post-result recovery one authority
for registration checks, Evidence construction, hashes, producer identity, and
provenance. It avoids duplicate formats and does not repeat engineering
execution. Cost is a small ToolBroker extraction and deterministic Evidence ID
decision.

### Option 2: separate post-result materializer using shared primitives

Acceptable fallback if import boundaries prevent a direct shared service. It
still centralizes the constructor and validation primitives, but has more
surface area for the two call paths to diverge. It should not duplicate the
Evidence model or trust caller-provided fields.

### Option 3: re-run ToolBroker with an Evidence node

Rejected. It repeats the deterministic calculation, creates duplicate ToolCall
and ToolResult records, violates the one mediated execution bound, obscures
which result was selected, and creates a race window with no architectural
benefit.

## Final Architecture Closure

All requested architecture gaps are closed. The remaining implementation
constraints are explicit decisions:

1. A trusted per-invocation mode defaults to M6B-2A `ENABLED`; B is explicitly
   `DISABLED` and cannot create a second ToolCall.
2. Every validated authored response, including zero-request responses, gets an
   immutable observation before mediation dispatch.
3. Torque Evidence uses normalized `design_torque_nm` with fixed `N*m` units via
   a trusted registration-owned summary handler.
 4. Torque inputs are Requirements at the three exact paths above, with three
    exact dependency invalidation rules and no over-invalidation of unrelated
    requirements or state.
5. Native torque backend provenance is explicitly `None`.
6. Mediated agent execution requires exact `mechcad-calc-torque@1.0`; a bare
   name fails mediator preflight without changing global M5 compatibility.
7. Deterministic Evidence identity is shared by inline and post-result paths,
   while ToolResult remains immutable and Broker returns `evidence_id`.
8. Round-trip transitions are immutable files under one deterministic workflow
   ID; recovery advances only across existing transitions.

No production code or commit is authorized by this document.

M6B2B_FIRST_TOOL_ROUNDTRIP_DESIGN_CLOSED
