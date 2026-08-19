import json
from pathlib import Path

import pytest
from pydantic import ValidationError


def _controller(tmp_path):
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore
    from mechcad_harness.models import Component, Constraint, DesignState, Requirement
    from mechcad_harness.runs import RunController, TaskDefinition
    from mechcad_harness.state import StateManager

    manager = StateManager(tmp_path)
    snapshot = manager.create_project(
        "PRJ-TRANSMISSION",
        DesignState(
            id="DES-TRANSMISSION",
            revision=1,
            components=[Component(id="P-1", name="Transmission Part")],
            requirements=[
                Requirement(id="REQ-SPEED", name="Output speed", description="Output speed is 120 rpm."),
                Requirement(id="REQ-TORQUE", name="Output torque", description="Output torque is 4 N m."),
            ],
            constraints=[Constraint(id="CONSTRAINT-ENVELOPE", name="Envelope", expression="Transmission envelope is 80 mm by 80 mm.")],
        ),
    )
    graph_path = tmp_path / "dependencies.json"
    graph_path.write_text('{"rules": [{"when": ["/components/*"], "invalidates": ["analysis.transmission"]}], "edges": []}', encoding="utf-8")
    evidence = EvidenceStore(tmp_path, manager, DependencyGraph.from_yaml(graph_path))
    controller = RunController(
        tmp_path,
        manager,
        ChangeEngine(manager, OwnershipPolicy.from_file("config/ownership.yaml")),
        evidence,
    )
    run = controller.create_run("PRJ-TRANSMISSION")
    task = TaskDefinition(
        task_id="TASK-TRANSMISSION",
        run_id=run.run_id,
        task_type="agent",
        objective="Reason about preliminary transmission architecture and identify missing backlash data.",
        bound_revision=1,
        bound_state_hash=snapshot.state_hash,
    )
    controller.add_task(run.run_id, task)
    return controller, run, task, snapshot


def transmission_identity():
    from mechcad_harness.agents import AgentIdentity

    return AgentIdentity(
        agent_name="mechcad-transmission",
        agent_version="1.0",
        role="transmission_engineer",
        protocol_version="1.0",
    )


def test_transmission_project_agent_is_reasoning_only():
    text = Path(".opencode/agents/mechcad-transmission.md").read_text(encoding="utf-8")
    assert "mechcad-transmission" in text
    assert "read: deny" in text
    assert "edit: deny" in text
    assert "bash: deny" in text
    assert "INPUT CONTEXT" in text
    assert "OUTPUT CONTRACT" in text
    assert "plain strings" in text
    assert "tools, shell, filesystem" in text
    assert "Do not invent missing engineering facts" in text
    assert "transmission.torque" in text
    assert "force_n" in text
    assert "lever_arm_m" in text
    assert "safety_factor" in text
    assert "CURRENT torque Evidence takes precedence" in text
    assert "even when force_n, lever_arm_m, and safety_factor Requirements are also present" in text
    for key in (
        "transmission.output_angular_speed",
        "transmission.motor_characteristics",
        "transmission.output_interface",
        "transmission.packaging_envelope",
    ):
        assert key in text
    assert "key" in text
    assert "description" in text
    assert "rationale" in text
    assert "CURRENT torque Evidence is not a missing authoritative input" in text
    assert "already supplied authoritative inputs" in text
    assert "gear ratio" in text
    assert "constraint_requests = []" in text
    assert "Do not create a request merely because information could be useful later" in text
    assert "mechcad-calc-torque" not in text
    assert "mechcad-calc-torque@1.0" not in text


def test_transmission_identity_is_exact_and_unknown_version_rejected():
    from mechcad_harness.agents import AgentRegistry, FakeAgentAdapter

    identity = transmission_identity()
    assert identity.agent_name == "mechcad-transmission"
    assert identity.agent_version == "1.0"
    assert identity.role == "transmission_engineer"
    registry = AgentRegistry()
    registry.register(identity, FakeAgentAdapter(identity, findings=("The selected requirements imply a reduction stage should be evaluated.",)))
    assert registry.get("mechcad-transmission", "1.0")
    with pytest.raises(LookupError, match="unknown agent"):
        registry.get("mechcad-transmission", "2.0")


def test_transmission_context_contains_only_selected_records(tmp_path):
    from mechcad_harness.agents import ContextBuilder

    controller, run, task, _ = _controller(tmp_path)
    context = ContextBuilder(controller).build(
        run.run_id,
        task.task_id,
        selected_requirement_ids=("REQ-SPEED",),
        selected_constraint_ids=("CONSTRAINT-ENVELOPE",),
    )
    assert context.requirements == ("Output speed is 120 rpm.",)
    assert context.constraints == ("Transmission envelope is 80 mm by 80 mm.",)
    assert context.evidence_summaries == ()
    assert context.design_state.requirements[0].id == "REQ-SPEED"


def test_transmission_context_rejects_stale_evidence(tmp_path):
    from mechcad_harness.agents import ContextBuilder
    from mechcad_harness.models import Evidence

    controller, run, task, snapshot = _controller(tmp_path)
    controller.evidence.write_evidence(
        "PRJ-TRANSMISSION",
        Evidence(
            id="EVIDENCE-STALE",
            kind="analysis.transmission",
            summary="old torque evidence",
            revision=snapshot.revision,
            state_hash=snapshot.state_hash,
        ),
    )
    controller.record_convergence_revision(run.run_id, 2, "sha256:advanced")
    with pytest.raises(ValueError, match="agent task binding is stale|evidence is not current"):
        ContextBuilder(controller).build(run.run_id, task.task_id, selected_evidence_ids=("EVIDENCE-STALE",))


def test_component_rejects_inline_transmission_field():
    from mechcad_harness.models import Component

    with pytest.raises(ValidationError):
        Component.model_validate({"id": "P-1", "name": "Part", "transmission": {"ratio": 5}})


def test_transmission_proposal_cannot_create_revision(tmp_path):
    from mechcad_harness.changes import ChangeOperation, OperationType
    from mechcad_harness.changes.errors import ChangeSetValidationError
    from mechcad_harness.models import ChangeProposal, ProposalStatus

    controller, _, _, snapshot = _controller(tmp_path)
    proposal = ChangeProposal(
        id="PROP-TRANSMISSION",
        title="Transmission proposal",
        status=ProposalStatus.DRAFT,
        base_revision=snapshot.revision,
        base_state_hash=snapshot.state_hash,
        actor="mechcad-transmission",
        operations=[
            ChangeOperation(
                operation=OperationType.ADD,
                path="/components/P-1/transmission",
                value={"ratio": 5},
            )
        ],
    )
    with pytest.raises(ChangeSetValidationError):
        controller.change_engine.apply_proposal("PRJ-TRANSMISSION", proposal)
    assert controller.state_manager._read_current("PRJ-TRANSMISSION")["revision"] == snapshot.revision


def test_transmission_reasoning_persists_finding_and_constraint_request_without_mutation(tmp_path):
    from mechcad_harness.agents import AgentRegistry, ContextBuilder, FakeAgentAdapter
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.models import AgentAuthoredResponsePayload

    controller, run, task, snapshot = _controller(tmp_path)
    identity = transmission_identity()
    response = AgentAuthoredResponsePayload(
        status="succeeded",
        summary="Preliminary transmission reasoning",
        findings=("The supplied speed and torque requirements indicate that a reduction architecture should be evaluated.",),
        issues=(),
        constraint_requests=("Specify the allowable output backlash before transmission selection can be finalized.",),
        change_proposals=(),
    )
    adapter = FakeAgentAdapter(identity, response=response)
    registry = AgentRegistry()
    registry.register(identity, adapter)
    result = AgentGateway(controller, registry, ContextBuilder(controller)).invoke(
        run.run_id,
        task.task_id,
        identity.agent_name,
        identity.agent_version,
        selected_requirement_ids=("REQ-SPEED", "REQ-TORQUE"),
        selected_constraint_ids=("CONSTRAINT-ENVELOPE",),
    )
    assert result.status.value == "succeeded"
    assert result.response is not None
    assert result.response.change_proposals == ()
    assert result.response.findings and all(isinstance(item, str) for item in result.response.findings)
    assert result.response.constraint_requests[0].description.startswith("Specify")
    assert controller.state_manager._read_current("PRJ-TRANSMISSION")["state_hash"] == snapshot.state_hash
    assert not list((tmp_path / "projects" / "PRJ-TRANSMISSION" / "evidence").glob("*.json"))


def test_transmission_conflict_uses_issue_not_constraint_request(tmp_path):
    from mechcad_harness.agents import AgentRegistry, ContextBuilder, FakeAgentAdapter
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.models import AgentAuthoredResponsePayload

    controller, run, task, snapshot = _controller(tmp_path)
    identity = transmission_identity()
    response = AgentAuthoredResponsePayload(
        status="succeeded",
        summary="",
        findings=("The supplied envelope constraint conflicts with the selected gear geometry evidence.",),
        issues=("Transmission envelope conflict",),
        constraint_requests=(),
        change_proposals=(),
    )
    registry = AgentRegistry()
    registry.register(identity, FakeAgentAdapter(identity, response=response))
    result = AgentGateway(controller, registry, ContextBuilder(controller)).invoke(
        run.run_id,
        task.task_id,
        identity.agent_name,
        identity.agent_version,
    )
    assert result.response.issues[0].title == "Transmission envelope conflict"
    assert result.response.constraint_requests == ()


def test_transmission_stale_result_retains_response(tmp_path):
    from mechcad_harness.agents import AgentRegistry, ContextBuilder, FakeAgentAdapter
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.models import AgentAdapterExecutionOutcome, AgentAdapterProvenance

    controller, run, task, _ = _controller(tmp_path)
    identity = transmission_identity()
    adapter = FakeAgentAdapter(identity, findings=("Transmission reasoning completed.",))
    original = adapter.invoke

    def invoke(request):
        outcome = original(request)
        controller.record_convergence_revision(run.run_id, 2, "sha256:advanced")
        return AgentAdapterExecutionOutcome(
            authored_response=outcome.authored_response,
            provenance=AgentAdapterProvenance(
                adapter_name="fake-agent-adapter",
                adapter_version="1.0",
                provider="test",
                transport="in-process",
                session_id="transmission-session",
            ),
        )

    adapter.invoke = invoke
    registry = AgentRegistry()
    registry.register(identity, adapter)
    result = AgentGateway(controller, registry, ContextBuilder(controller)).invoke(
        run.run_id,
        task.task_id,
        identity.agent_name,
        identity.agent_version,
    )
    assert result.status.value == "stale"
    assert result.response is not None
    assert result.adapter_provenance.session_id == "transmission-session"


def test_transmission_identity_is_not_discovered_from_opencode_agent_endpoint():
    from mechcad_harness.agents import AgentRegistry, FakeAgentAdapter

    identity = transmission_identity()
    registry = AgentRegistry()
    registry.register(identity, FakeAgentAdapter(identity))
    with pytest.raises(LookupError):
        registry.get("mechcad-transmission", "latest")
