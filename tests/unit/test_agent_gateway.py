import json

import pytest


def _controller(tmp_path):
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore
    from mechcad_harness.models import Component, DesignState
    from mechcad_harness.runs import RunController, TaskDefinition
    from mechcad_harness.state import StateManager

    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-1", DesignState(id="DES-1", revision=1, components=[Component(id="P-1", name="Part")]))
    graph = tmp_path / "dependencies.json"
    graph.write_text("rules: []\nedges: []\n", encoding="utf-8")
    controller = RunController(tmp_path, manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/components/*", "owner": "actor"}])), EvidenceStore(tmp_path, manager, DependencyGraph.from_yaml(graph)))
    run = controller.create_run("PRJ-1")
    task = TaskDefinition(task_id="TASK-1", run_id=run.run_id, task_type="agent", objective="inspect", bound_revision=1, bound_state_hash=snapshot.state_hash)
    controller.add_task(run.run_id, task)
    return controller, run, task, snapshot


def _gateway(tmp_path, adapter=None):
    from mechcad_harness.agents import AgentIdentity, AgentRegistry, ContextBuilder, FakeAgentAdapter
    from mechcad_harness.agents.gateway import AgentGateway

    controller, run, task, snapshot = _controller(tmp_path)
    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    registry = AgentRegistry()
    registry.register(identity, adapter or FakeAgentAdapter(identity, findings=("ok",)))
    return AgentGateway(controller, registry, ContextBuilder(controller)), controller, run, task, identity


def test_gateway_persists_invocation_before_adapter_and_result_separately(tmp_path):
    gateway, controller, run, task, identity = _gateway(tmp_path)
    result = gateway.invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version)
    agents = tmp_path / "projects" / "PRJ-1" / "runs" / run.run_id / "agents"
    assert (agents / "invocations").exists()
    assert (agents / "results").exists()
    assert result.response.findings == ("ok",)
    assert result.response_hash.startswith("sha256:")


def test_gateway_uses_invocation_outcome_provenance(tmp_path):
    from mechcad_harness.agents import AgentIdentity, AgentRegistry, ContextBuilder
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.models import AgentAdapterExecutionOutcome, AgentAdapterProvenance, AgentResponsePayload

    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    provenance = AgentAdapterProvenance(adapter_name="outcome", adapter_version="1.0", provider="test-provider", transport="test", session_id="session-1")

    class OutcomeAdapter:
        identity = type("Identity", (), {"adapter_name": "outcome", "adapter_version": "1.0"})()

        def invoke(self, request):
            assert (tmp_path / "projects" / "PRJ-1" / "runs" / run.run_id / "agents" / "invocations").exists()
            return AgentAdapterExecutionOutcome(response=AgentResponsePayload(summary="ok"), provenance=provenance)

    controller, run, task, _ = _controller(tmp_path)
    registry = AgentRegistry()
    registry.register(identity, OutcomeAdapter())
    result = AgentGateway(controller, registry, ContextBuilder(controller)).invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version)
    assert result.adapter_provenance == provenance


def test_gateway_uses_invocation_error_provenance(tmp_path):
    from mechcad_harness.agents import AgentIdentity, AgentRegistry, ContextBuilder
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.models import AgentAdapterExecutionError, AgentAdapterProvenance

    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    provenance = AgentAdapterProvenance(adapter_name="outcome", adapter_version="1.0", provider="test-provider", transport="test", session_id="session-1", message_id="message-1", request_hash="sha256:req", validation_diagnostics={"errors": []})

    class ErrorAdapter:
        identity = type("Identity", (), {"adapter_name": "outcome", "adapter_version": "1.0"})()

        def invoke(self, request):
            raise AgentAdapterExecutionError("structured output invalid", provenance=provenance)

    controller, run, task, _ = _controller(tmp_path)
    registry = AgentRegistry()
    registry.register(identity, ErrorAdapter())
    result = AgentGateway(controller, registry, ContextBuilder(controller)).invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version)
    assert result.status.value == "failed"
    assert result.adapter_provenance == provenance
    assert result.error == "structured output invalid"


def test_fake_invocations_do_not_leak_execution_metadata(tmp_path):
    from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
    from mechcad_harness.agents.models import AgentInvocationRequest
    from mechcad_harness.models import DesignState

    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    adapter = FakeAgentAdapter(identity, findings=("one",))
    context = __import__("mechcad_harness.agents.models", fromlist=["AgentContext"]).AgentContext(project_id="PRJ", run_id="RUN", task_id="TASK", revision=1, state_hash="hash", design_state=DesignState(id="DES", revision=1), task_objective="test", task_instructions="test")
    first = adapter.invoke(AgentInvocationRequest(invocation_id="INV-1", agent=identity, project_id="PRJ", run_id="RUN", task_id="TASK", bound_revision=1, bound_state_hash="hash", context=context, requested_output_schema_version="1.0", context_hash="ctx-1"))
    second = adapter.invoke(AgentInvocationRequest(invocation_id="INV-2", agent=identity, project_id="PRJ", run_id="RUN", task_id="TASK", bound_revision=1, bound_state_hash="hash", context=context, requested_output_schema_version="1.0", context_hash="ctx-2"))
    assert first is not second
    assert first.provenance is not second.provenance
    assert first.provenance.session_id is None
    assert second.provenance.session_id is None


def test_gateway_rejects_unknown_agent(tmp_path):
    gateway, controller, run, task, identity = _gateway(tmp_path)
    with pytest.raises(Exception, match="unknown agent"):
        gateway.invoke(run.run_id, task.task_id, "unknown", "1.0")


def test_gateway_adapter_failure_persists_failed_result(tmp_path):
    from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter

    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    gateway, controller, run, task, identity = _gateway(tmp_path, FakeAgentAdapter(identity, error=RuntimeError("boom")))
    result = gateway.invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version)
    assert result.status.value == "failed"


def test_gateway_preserves_structured_proposal_without_applying_it(tmp_path):
    from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
    from mechcad_harness.agents.models import AgentResponsePayload
    from mechcad_harness.models import ChangeProposal, ProposalStatus

    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    proposal = ChangeProposal(id="PROP-1", title="Proposal", status=ProposalStatus.DRAFT, base_revision=1, base_state_hash="sha256:placeholder", actor="agent")
    controller, run, task, snapshot = _controller(tmp_path)
    proposal = proposal.model_copy(update={"base_state_hash": snapshot.state_hash})
    from mechcad_harness.agents import AgentRegistry, ContextBuilder
    from mechcad_harness.agents.gateway import AgentGateway
    registry = AgentRegistry()
    registry.register(identity, FakeAgentAdapter(identity, response=AgentResponsePayload(change_proposals=(proposal,))))
    gateway = AgentGateway(controller, registry, ContextBuilder(controller))
    snapshot_hash = run.active_state_hash
    result = gateway.invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version)
    assert result.response.change_proposals[0].id == "PROP-1"
    assert controller.state_manager._read_snapshot("PRJ-1", 1).state_hash == snapshot_hash


def test_gateway_fails_wrong_proposal_revision_or_hash(tmp_path):
    from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
    from mechcad_harness.agents.models import AgentResponsePayload
    from mechcad_harness.models import ChangeProposal, ProposalStatus

    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    proposal = ChangeProposal(id="PROP-BAD", title="Bad", status=ProposalStatus.DRAFT, base_revision=99, base_state_hash="sha256:wrong", actor="agent")
    gateway, controller, run, task, identity = _gateway(tmp_path, FakeAgentAdapter(identity, response=AgentResponsePayload(change_proposals=(proposal,))))
    result = gateway.invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version)
    assert result.status.value == "failed"
    assert result.error == "RESPONSE_BINDING_MISMATCH"
    assert controller.state_manager._read_snapshot("PRJ-1", 1).state_hash == run.active_state_hash


def test_duplicate_invocation_and_result_records_are_rejected(tmp_path):
    gateway, controller, run, task, identity = _gateway(tmp_path)
    result = gateway.invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version)
    record = gateway.store.load_result("PRJ-1", run.run_id, result.result_id)
    with pytest.raises(Exception):
        gateway.store.write_result(record)


def test_gateway_marks_response_stale_when_run_binding_advances(tmp_path):
    from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter

    class AdvancingAdapter(FakeAgentAdapter):
        def invoke(self, request):
            response = super().invoke(request)
            self.controller.record_convergence_revision(request.run_id, 2, "sha256:advanced")
            return response

    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    controller, run, task, snapshot = _controller(tmp_path)
    adapter = FakeAgentAdapter(identity, findings=("ok",))
    original = adapter.invoke
    def invoke(request):
        response = original(request)
        controller.record_convergence_revision(run.run_id, 2, "sha256:advanced")
        return response
    adapter.invoke = invoke
    from mechcad_harness.agents import AgentRegistry, ContextBuilder
    from mechcad_harness.agents.gateway import AgentGateway
    registry = AgentRegistry()
    registry.register(identity, adapter)
    result = AgentGateway(controller, registry, ContextBuilder(controller)).invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version)
    assert result.status.value == "stale"
