# M6A-1 Agent Gateway Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic agent protocol, context, registry, fake adapter, durable invocation/result records, and AgentGateway without real external execution.

**Architecture:** `agents/models.py` contains strict protocol and persistence models; `agents/registry.py` contains exact trusted lookup; `agents/context.py` builds minimal read-only context from StateManager and RunStore; `agents/gateway.py` validates binding, persists records, invokes the adapter, and handles stale results. Existing M2/M3/M4 records remain authoritative and no proposal is applied automatically.

**Tech Stack:** Python 3.11+, Pydantic v2, existing canonical hashing/state/run persistence, pytest. No new dependencies.

## Global Constraints

- Do not commit unless explicitly requested.
- Do not invoke OpenCode, LLMs, subprocesses, network, shell, Python execution, ToolBroker tools, MCP, FreeCAD, or external services.
- Agents never mutate DesignState or write canonical revision files.
- Public context is minimal, explicit, read-only, and excludes workspace dumps, secrets, environment variables, arbitrary paths, backend objects, and mutable objects.
- Exact agent name/version lookup only; no latest fallback or plugin discovery.
- Invocation persists before adapter execution; invocation/result records are immutable and separate from M4 state authority.
- Stale responses are preserved as `STALE` results and cannot mutate state, create Evidence, or apply proposals.
- Existing ChangeProposal, Issue, and ConstraintRequest models remain the only canonical-impacting response objects.
- No stress, load cases, C-3B, transmission/material/structural agents, automatic proposal application, loops, or chat memory.

---

### Task 1: Add Agent Protocol and Persistence Models

**Files:**
- Create: `src/mechcad_harness/agents/models.py`
- Modify: `src/mechcad_harness/agents/__init__.py`
- Test: `tests/unit/test_agents_models.py`

**Interfaces:**
- `AgentIdentity(agent_name, agent_version, role, protocol_version)`.
- `AgentAdapterIdentity(adapter_name, adapter_version)`.
- `AgentAdapterProvenance(adapter_name, adapter_version, provider, model, model_version, transport)`.
- `AgentEvidenceSummary(evidence_id, dependency_node, bound_revision, bound_state_hash, freshness, summary, source identity)`.
- `AgentContext(project_id, run_id, task_id, revision, state_hash, design_state, task_objective, task_instructions, requirements, constraints, evidence_summaries: tuple[AgentEvidenceSummary, ...])`.
- `AgentInvocationRequest(invocation_id, agent, project_id, run_id, task_id, bound_revision, bound_state_hash, context, requested_output_schema_version, created_at, context_hash)`.
- `AgentResponsePayload(status, summary, findings, change_proposals, issues, constraint_requests)`.
- `AgentInvocationRecord(request, request_hash, created_at)`.
- `AgentResult(result_id, invocation_id, agent identity, bindings, status, response_hash, response, adapter_provenance, error, created_at)`.

- [ ] **Step 1: Write failing model tests**

```python
def test_agent_identity_rejects_empty_fields():
    with pytest.raises(Exception):
        AgentIdentity(agent_name="", agent_version="1.0", role="test", protocol_version="1.0")


def test_agent_response_uses_existing_domain_models():
    proposal = ChangeProposal(...)
    response = AgentResponsePayload(change_proposals=(proposal,))
    assert response.change_proposals[0] == proposal
```

- [ ] **Step 2: Run model tests and verify missing-module failure**

Run: `py -m pytest tests/unit/test_agents_models.py -q`

Expected: FAIL because the agent model module does not exist.

- [ ] **Step 3: Implement strict models and statuses**

Use statuses `SUCCEEDED`, `FAILED`, `STALE` for AgentResult and response status `SUCCEEDED`/`FAILED`. Require UTC-aware datetimes, nonempty identity/binding strings, positive revisions, and extra-forbid models. Keep structured fields typed with existing domain models.

- [ ] **Step 4: Run model tests and verify pass**

Run: `py -m pytest tests/unit/test_agents_models.py -q`

Expected: PASS.

### Task 2: Add Agent Registry, Fake Adapter, and Context Builder

**Files:**
- Create: `src/mechcad_harness/agents/registry.py`
- Create: `src/mechcad_harness/agents/fake.py`
- Create: `src/mechcad_harness/agents/context.py`
- Test: `tests/unit/test_agents_runtime.py`

**Interfaces:**
- `AgentAdapter(Protocol).invoke(request) -> AgentResponsePayload`.
- `AgentRegistry.register(agent_name, agent_version, adapter)`, `get(agent_name, agent_version)`, `list()`.
- `FakeAgentAdapter(identity, response=None, error=None)`.
- `ContextBuilder.build(run_id, task_id, selected_evidence_ids=(), selected_requirement_ids=(), selected_constraint_ids=()) -> AgentContext`.

- [ ] **Step 1: Write failing registry/fake/context tests**

Cover exact lookup, duplicate rejection, unknown lookup, deterministic fake finding, fake proposal/issue/constraint responses, and context loaded from the persisted revision with exact hash.

- [ ] **Step 2: Run focused tests and verify expected missing-module failures**

Run: `py -m pytest tests/unit/test_agents_runtime.py -q`

Expected: FAIL because registry, fake adapter, and ContextBuilder do not exist.

- [ ] **Step 3: Implement exact registry and deterministic fake adapter**

Store adapters by `(agent_name, agent_version)`, sort listings by key, reject duplicates, and make FakeAgentAdapter return only its configured immutable response or raise its configured deterministic exception. Do not add execution capabilities.

- [ ] **Step 4: Implement minimal ContextBuilder**

Load the run, task definition/state, and exact canonical revision through existing managers. Require task/run binding equality and state hash equality. Use the immutable `TaskDefinition.objective` as both the initial `task_objective` and `task_instructions`; do not invent a second mutable instruction authority. Resolve selected Evidence IDs through `EvidenceStore`, require exact revision/hash and `CURRENT` freshness, and construct `AgentEvidenceSummary` from persisted fields. Resolve selected requirement/constraint IDs from the bound DesignState only. Copy/validate the DesignState so the adapter receives no mutable authority reference.

- [ ] **Step 5: Run runtime tests and verify pass**

Run: `py -m pytest tests/unit/test_agents_runtime.py -q`

Expected: PASS.

### Task 3: Add Durable Agent Records and Gateway

**Files:**
- Create: `src/mechcad_harness/agents/persistence.py`
- Create: `src/mechcad_harness/agents/gateway.py`
- Modify: `src/mechcad_harness/agents/__init__.py`
- Test: `tests/unit/test_agent_gateway.py`

**Interfaces:**
- `AgentStore(workspace).write_invocation(record)`, `.load_invocation(project_id, run_id, invocation_id)`, `.write_result(result)`, `.load_result(project_id, run_id, result_id)`.
- `AgentGateway(controller, registry, context_builder).invoke(run_id, task_id, agent_name, agent_version, requested_output_schema_version="1.0", selected_evidence_ids=(), selected_requirement_ids=(), selected_constraint_ids=()) -> AgentResult`.

- [ ] **Step 1: Write failing gateway/persistence tests**

Cover invocation-before-adapter ordering, immutable duplicate rejection, separate result persistence, adapter success/failure, invalid response, exact binding, deterministic request/response hashes, no DesignState mutation, and no automatic proposal application.

- [ ] **Step 2: Run focused tests and verify expected missing-gateway failure**

Run: `py -m pytest tests/unit/test_agent_gateway.py -q`

Expected: FAIL because AgentStore and AgentGateway do not exist.

- [ ] **Step 3: Implement AgentStore using existing atomic exclusive-write conventions**

Persist under `projects/<project_id>/runs/<run_id>/agents/invocations/` and `results/`. Use canonical JSON payload hashes and reject duplicate IDs. Provide typed reads that reject corrupt records.

- [ ] **Step 4: Implement pre-invocation binding and invocation persistence**

Resolve exact agent, build context, create invocation ID/request, calculate context/request hashes, persist the invocation, then call the adapter. Never call the adapter before successful persistence.

- [ ] **Step 5: Validate and normalize adapter response**

Validate `AgentResponsePayload`, verify each ChangeProposal base revision/hash equals the invocation binding, calculate deterministic response hash, and map adapter exceptions, schema failures, or proposal mismatches to failed AgentResult records. Proposal mismatch uses `RESPONSE_BINDING_MISMATCH`. Never fabricate success.

- [ ] **Step 6: Implement stale recheck and result persistence**

Reload authoritative run/task binding after adapter return. If project/run/task/revision/state hash changed, persist `STALE` with the historical response and explicit stale error. Do not write Evidence or apply any proposals. Otherwise persist `SUCCEEDED`.

- [ ] **Step 7: Run gateway tests and verify pass**

Run: `py -m pytest tests/unit/test_agent_gateway.py -q`

Expected: PASS.

### Task 4: Add Documentation and Full Regression Coverage

**Files:**
- Modify: `README.md`
- Test: `tests/unit/test_agent_docs.py`

- [ ] **Step 1: Write failing documentation assertions**

Assert README documents AgentGateway flow, minimal context, immutable records, FakeAgentAdapter-only scope, stale results, no automatic proposal application, and future M6A-2/M6B/C-3B boundaries.

- [ ] **Step 2: Run docs test and verify failure**

Run: `py -m pytest tests/unit/test_agent_docs.py -q`

Expected: FAIL before documentation is added.

- [ ] **Step 3: Document M6A-1 architecture and exclusions**

Explain that agents reason, tools calculate, proposals remain proposals, AgentResult is not Evidence, M4 state remains authoritative, and no OpenCode/LLM execution exists.

- [ ] **Step 4: Run docs test and verify pass**

Run: `py -m pytest tests/unit/test_agent_docs.py -q`

Expected: PASS.

- [ ] **Step 5: Run complete regression suite**

Run: `py -m pytest -q`

Expected: all existing M0-M5.5 tests and new M6A-1 tests pass.

### Task 5: Final Verification

**Files:**
- All M6A-1 implementation and test files

- [ ] **Step 1: Run focused M6A-1 tests**

Run: `py -m pytest tests/unit/test_agents_models.py tests/unit/test_agents_runtime.py tests/unit/test_agent_gateway.py tests/unit/test_agent_docs.py -q`

Expected: all focused tests pass.

- [ ] **Step 2: Run compile and whitespace checks**

Run: `py -m compileall -q src tests`

Run: `git diff --check`

Expected: both pass.

- [ ] **Step 3: Run prohibited-scope scan**

Search new M6A-1 files for `OpenCode`, `subprocess`, `Popen`, `requests`, `http`, `ToolBroker`, `sectionproperties`, `bd_materials`, `shell`, `MCP`, `FreeCAD`, `stress`, `C-3B`, `transmission`, and automatic proposal application. Confirm matches are documentation exclusions, protocol names, or tests proving absence, not implementation.

- [ ] **Step 4: Inspect status without committing**

Run: `git status --short; git diff --stat`

Confirm no unrelated files were reverted and no commit was created.
