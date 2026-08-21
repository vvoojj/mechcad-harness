# M6B-1 Transmission Reasoning Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add and validate the first real reasoning-only `mechcad-transmission@1.0` agent without extending `DesignState`.

**Architecture:** Use a strict `AgentAuthoredResponsePayload` wire contract, then trusted deterministic materialization into unchanged `AgentResponsePayload` records before persisting `AgentResult`. `AgentGateway` may receive the smallest narrowly authorized materialization extension; `ContextBuilder` and canonical domain models remain unchanged. The reserved `/components/*/transmission` ownership path remains inactive and no proposal is emitted by the first fixture.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, existing MechCAD state/run/evidence/tool/change infrastructure, OpenCode Desktop HTTP adapter.

## Global Constraints

- Do not modify `DesignState`, `ContextBuilder`, `AgentResponsePayload`, or canonical domain models. Extend `AgentGateway` only for validated authored-response materialization.
- Do not add tool calling, automatic iteration, retries, stress/load-case C-3B, direct ToolBroker execution, or automatic proposal application.
- Treat `/components/*/transmission` as reserved-but-inactive ownership; proposals targeting it must fail canonical Pydantic validation.
- Use exact trusted identity `mechcad-transmission@1.0` and explicit OpenCode agent binding `mechcad-transmission`.
- Use only explicitly selected requirements, constraints, and CURRENT Evidence.
- Missing inputs produce authored constraint-request strings; supplied conflicts produce authored issue strings.
- Findings, issues, and constraint requests are plain strings on the wire; no response repair, coercion, alternate models, or handwritten complete schema.
- Do not commit unless explicitly requested.

The authority split is explicit: the agent owns semantic status, summary,
finding text, issue text, constraint-request text, proposal titles, and
operations. The harness owns record IDs, revision/state-hash binding, proposal
base binding, proposal actor, and canonical lifecycle status.

---

### Task 1: Add Project Transmission Agent Definition

**Files:**
- Create: `.opencode/agents/mechcad-transmission.md`
- Test: `tests/unit/test_transmission_agent.py`

**Interfaces:**
- Produces the project-scoped OpenCode agent name consumed by `OpenCodeAdapterConfig(agent_name="mechcad-transmission")`.

- [ ] **Step 1: Write the failing security and prompt test**

```python
def test_transmission_project_agent_is_reasoning_only():
    text = Path(".opencode/agents/mechcad-transmission.md").read_text(encoding="utf-8")
    assert "mechcad-transmission" in text
    assert "permission: deny" in text
    assert "INPUT CONTEXT" in text
    assert "OUTPUT CONTRACT" in text
    assert "plain JSON strings" in text
    assert "Do not use tools" in text
    assert "Do not invent missing engineering facts" in text
    assert "mechcad-calc-torque" not in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `py -m pytest tests/unit/test_transmission_agent.py::test_transmission_project_agent_is_reasoning_only -q`

Expected: FAIL because the project agent file does not exist.

- [ ] **Step 3: Create the concise deny-all agent definition**

Use the accepted project-agent format with no read/edit/bash/task/web/MCP/
skill/question/tool actions. State that the agent receives all context through
AgentGateway, reasons only from authoritative context, distinguishes Evidence
from findings, Issues, ConstraintRequests, and proposals, and must return only
the native response schema.

- [ ] **Step 4: Run the focused test**

Run: `py -m pytest tests/unit/test_transmission_agent.py::test_transmission_project_agent_is_reasoning_only -q`

Expected: PASS.

### Task 2: Add Trusted Transmission Identity and Fixture Helpers

**Files:**
- Modify: `tests/unit/test_transmission_agent.py`
- Test: `tests/unit/test_transmission_agent.py`

**Interfaces:**
- Uses `AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")`.
- Uses existing `AgentRegistry`, `FakeAgentAdapter`, `ContextBuilder`, and `AgentGateway`.

- [ ] **Step 1: Add failing exact-registration tests**

```python
def test_transmission_identity_is_exact_and_unknown_version_rejected():
    identity = transmission_identity()
    assert identity.agent_name == "mechcad-transmission"
    assert identity.agent_version == "1.0"
    assert identity.role == "transmission_engineer"
    registry = AgentRegistry()
    registry.register(identity, FakeAgentAdapter(identity))
    assert registry.get("mechcad-transmission", "1.0")
    with pytest.raises(LookupError, match="unknown agent"):
        registry.get("mechcad-transmission", "2.0")
```

- [ ] **Step 2: Run the focused test to verify the fixture helper is missing**

Run: `py -m pytest tests/unit/test_transmission_agent.py::test_transmission_identity_is_exact_and_unknown_version_rejected -q`

Expected: FAIL because `transmission_identity` and the fixture are not yet defined.

- [ ] **Step 3: Add only test fixture construction**

Create a deterministic helper that builds a project with requirements for
output speed, output torque, and envelope; an intentionally absent backlash
bound; selected current torque/geometry Evidence where useful; and a
`FakeAgentAdapter` response containing one plain finding plus a
`ConstraintRequest` for missing backlash. Do not add production agent-specific
models or dynamic OpenCode discovery.

- [ ] **Step 4: Run focused identity and fixture tests**

Run: `py -m pytest tests/unit/test_transmission_agent.py -q`

Expected: PASS for the tests written so far.

### Task 3: Cover Context, Evidence, and Engineering Semantics

**Files:**
- Modify: `tests/unit/test_transmission_agent.py`

**Interfaces:**
- Uses the unchanged `ContextBuilder.build(..., selected_evidence_ids=..., selected_requirement_ids=..., selected_constraint_ids=...)`.
- Uses existing `EvidenceStore` freshness and binding behavior.

- [ ] **Step 1: Add tests for explicit context selection and stale rejection**

```python
def test_transmission_context_contains_only_selected_records(...):
    context = ContextBuilder(controller).build(
        run.run_id,
        task.task_id,
        selected_requirement_ids=("REQ-SPEED",),
        selected_constraint_ids=("CONSTRAINT-ENVELOPE",),
        selected_evidence_ids=("EVIDENCE-TORQUE",),
    )
    assert context.requirements == ("...",)
    assert context.constraints == ("...",)
    assert tuple(item.evidence_id for item in context.evidence_summaries) == ("EVIDENCE-TORQUE",)

def test_transmission_context_rejects_stale_evidence(...):
    with pytest.raises(ValueError, match="evidence is not current|evidence binding mismatch"):
        ContextBuilder(controller).build(run.run_id, task.task_id, selected_evidence_ids=("EVIDENCE-STALE",))
```

- [ ] **Step 2: Run the tests to verify the existing ContextBuilder behavior**

Run: `py -m pytest tests/unit/test_transmission_agent.py -k "context or evidence" -q`

Expected: PASS without modifying `ContextBuilder`.

- [ ] **Step 3: Add semantic response tests**

Validate that the deterministic fixture response has at least one plain-string
finding and a `ConstraintRequest` for missing data. Add a separate response
with an `Issue` for an explicit conflict. Assert the fixture does not emit a
proposal and does not contain numeric claims unsupported by selected Evidence.

- [ ] **Step 4: Add no-tool/no-authority tests**

Use a fake adapter that records no ToolBroker access and assert the gateway
persists the response without creating Evidence or changing the canonical
snapshot. Do not invoke shell, filesystem, MCP, or deterministic tools from
the fixture.

### Task 4: Cover Reserved Ownership and Proposal Boundary

**Files:**
- Modify: `tests/unit/test_transmission_agent.py`
- Test: existing `tests/unit/test_changes.py` patterns

**Interfaces:**
- Uses `ChangeProposal`, `ChangeOperation`, `OperationType`, `ChangeEngine`, and `OwnershipPolicy`.

- [ ] **Step 1: Add failing regression tests for the inactive path**

```python
def test_component_rejects_inline_transmission_field():
    with pytest.raises(ValidationError):
        Component.model_validate({"id": "P", "name": "Part", "transmission": {"ratio": 5}})

def test_reserved_transmission_proposal_cannot_create_revision(...):
    proposal = ChangeProposal(
        id="PROP-TRANSMISSION",
        title="Transmission proposal",
        status=ProposalStatus.DRAFT,
        base_revision=snapshot.revision,
        base_state_hash=snapshot.state_hash,
        actor="mechcad-transmission",
        operations=[ChangeOperation(operation=OperationType.ADD, path="/components/P/transmission", value={"ratio": 5})],
    )
    with pytest.raises(ChangeSetValidationError):
        controller.change_engine.apply_proposal("PRJ-TRANSMISSION", proposal)
```

- [ ] **Step 2: Run the tests and verify the absence boundary**

Run: `py -m pytest tests/unit/test_transmission_agent.py -k "inline or reserved or proposal" -q`

Expected: PASS using existing Pydantic validation; no production model change.

- [ ] **Step 3: Assert reasoning does not use generic fields**

Assert the fixture response has zero proposals and that the persisted
`DesignState` has no `transmission` field and unchanged state hash.

### Task 5: Add Gateway and Stale Result Coverage

**Files:**
- Modify: `tests/unit/test_transmission_agent.py`

**Interfaces:**
- Uses unchanged `AgentGateway.invoke` and immutable `AgentResult`.

- [ ] **Step 1: Add success, stale, and persistence assertions**

Assert the transmission response persists as `SUCCEEDED`, remains separate
from Evidence, preserves plain findings and structured requests/issues, and
does not mutate canonical state. Reuse the existing in-flight advancement
pattern to assert a successful transmission response becomes `STALE` while
retaining its response and execution provenance.

- [ ] **Step 2: Run focused gateway tests**

Run: `py -m pytest tests/unit/test_transmission_agent.py tests/unit/test_agent_gateway.py -q`

Expected: PASS.

### Task 6: Add Opt-In Live Transmission Test

**Files:**
- Create: `tests/integration/test_transmission_agent_live.py`

**Interfaces:**
- Uses `OpenCodeAdapterConfig(project_directory=..., provider_id="screenpipe", model_id="gpt-5.6-luna", agent_name="mechcad-transmission", model_selection=OpenCodeModelSelection.EXPLICIT)`.
- Uses the existing `resolve_opencode_config_from_environment` and `AgentGateway`.

- [ ] **Step 1: Add the skipped-by-default live test**

Set `pytestmark` to skip unless `MECHCAD_OPENCODE_LIVE == "1"`. Build the
generic fixture with intentionally missing backlash or holding/backdrive data,
select only relevant current Evidence, and invoke the exact trusted identity.

Assert:

```python
assert result.status.value == "succeeded"
assert result.response.change_proposals == ()
assert result.response.findings
assert all(isinstance(item, str) for item in result.response.findings)
assert result.response.issues or result.response.constraint_requests
assert result.adapter_provenance.provider == "screenpipe"
assert result.adapter_provenance.model == "gpt-5.6-luna"
assert manager._read_snapshot(project_id, 1).state_hash == snapshot.state_hash
```

Also verify no Evidence record is created and no tool calls/results exist.

- [ ] **Step 2: Run the default test**

Run: `py -m pytest tests/integration/test_transmission_agent_live.py -q`

Expected: SKIPPED unless live mode is enabled.

- [ ] **Step 3: Run the opt-in live test when credentials/runtime are available**

Run: `$env:MECHCAD_OPENCODE_LIVE='1'; py -m pytest tests/integration/test_transmission_agent_live.py -q`

Expected: PASS with `AgentResult.SUCCEEDED`, no proposal, and at least one
Issue or ConstraintRequest.

### Task 7: Document M6B-1 Boundary

**Files:**
- Modify: `README.md`
- Modify: `.opencode/README.md` only if the existing boundary documentation needs a direct M6B reference

- [ ] **Step 1: Document the accepted flow**

Add a concise M6B-1 section covering:

```text
authoritative state/evidence
    -> mechcad-transmission reasoning
    -> findings/issues/constraint requests/proposals
    -> immutable AgentResult
```

State that reasoning is not deterministic Evidence, no direct tools exist,
proposals remain proposals, missing data produces requests/issues, and
`/components/*/transmission` is reserved-but-inactive ownership until a future
canonical model is separately designed and approved.

- [ ] **Step 2: Run documentation-focused tests if present**

Run: `py -m pytest tests/unit/test_agent_docs.py tests/unit/test_transmission_agent.py -q`

Expected: PASS.

### Task 8: Full Verification

**Files:**
- No additional files.

- [ ] **Step 1: Run focused transmission suite**

Run: `py -m pytest tests/unit/test_transmission_agent.py tests/unit/test_agent_gateway.py tests/unit/test_agents_runtime.py tests/unit/test_opencode_adapter.py tests/integration/test_transmission_agent_live.py -q`

- [ ] **Step 2: Run the full repository suite**

Run: `py -m pytest -q`

- [ ] **Step 3: Run compile and whitespace checks**

Run: `py -m compileall -q src tests`

Run: `git diff --check`

- [ ] **Step 4: Inspect status and confirm no commit**

Run: `git status --short`

Confirm no commit is created and no canonical model files were modified.
