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


def test_gateway_preserves_registered_role_and_ignores_provider_identity(tmp_path):
    from mechcad_harness.agents import AgentIdentity, AgentRegistry, ContextBuilder
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.models import AgentAdapterExecutionOutcome, AgentAdapterProvenance, AgentAuthoredResponsePayload

    controller, run, task, _ = _controller(tmp_path)
    registered = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    provenance = AgentAdapterProvenance(adapter_name="provider", adapter_version="1.0", provider="provider", transport="test")

    class Provider:
        identity = type("Identity", (), {"adapter_name": "provider", "adapter_version": "1.0"})()

        def invoke(self, request):
            assert request.agent == registered
            return AgentAdapterExecutionOutcome(
                authored_response=AgentAuthoredResponsePayload(status="succeeded", summary="ok", findings=(), issues=(), constraint_requests=(), change_proposals=()),
                provenance=provenance,
                execution_metadata={"agent": {"agent_name": "forged", "agent_version": "9.9", "role": "test"}},
            )

    registry = AgentRegistry()
    registry.register(registered, Provider())
    gateway = AgentGateway(controller, registry, ContextBuilder(controller))
    result = gateway.invoke(run.run_id, task.task_id, registered.agent_name, registered.agent_version)
    invocation = gateway.store.load_invocation("PRJ-1", run.run_id, result.invocation_id)
    assert invocation.request.agent == registered
    assert (result.agent_name, result.agent_version) == (registered.agent_name, registered.agent_version)


def test_gateway_uses_invocation_outcome_provenance(tmp_path):
    from mechcad_harness.agents import AgentIdentity, AgentRegistry, ContextBuilder
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.models import AgentAdapterExecutionOutcome, AgentAdapterProvenance, AgentAuthoredResponsePayload

    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    provenance = AgentAdapterProvenance(adapter_name="outcome", adapter_version="1.0", provider="test-provider", transport="test", session_id="session-1")

    class OutcomeAdapter:
        identity = type("Identity", (), {"adapter_name": "outcome", "adapter_version": "1.0"})()

        def invoke(self, request):
            assert (tmp_path / "projects" / "PRJ-1" / "runs" / run.run_id / "agents" / "invocations").exists()
            return AgentAdapterExecutionOutcome(authored_response=AgentAuthoredResponsePayload(status="succeeded", summary="ok", findings=(), issues=(), constraint_requests=(), change_proposals=()), provenance=provenance)

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


def test_fake_adapter_scripted_responses_are_consumed_in_order():
    from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
    from mechcad_harness.agents.models import AgentAuthoredResponsePayload, AgentContext, AgentInvocationRequest
    from mechcad_harness.models import DesignState

    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    first = AgentAuthoredResponsePayload(status="succeeded", summary="A", findings=(), issues=(), constraint_requests=(), change_proposals=())
    second = AgentAuthoredResponsePayload(status="succeeded", summary="B", findings=(), issues=(), constraint_requests=(), change_proposals=())
    adapter = FakeAgentAdapter(identity, scripted_responses=(first, second))
    context = AgentContext(project_id="PRJ", run_id="RUN", task_id="TASK", revision=1, state_hash="hash", design_state=DesignState(id="DES", revision=1), task_objective="test", task_instructions="test")
    request = lambda invocation_id: AgentInvocationRequest(invocation_id=invocation_id, agent=identity, project_id="PRJ", run_id="RUN", task_id="TASK", bound_revision=1, bound_state_hash="hash", context=context, requested_output_schema_version="1.0", context_hash=invocation_id)
    assert adapter.invoke(request("INV-A")).authored_response.summary == "A"
    assert adapter.invoke(request("INV-B")).authored_response.summary == "B"
    assert adapter.invocation_count == 2
    assert [item.invocation_id for item in adapter.requests] == ["INV-A", "INV-B"]


def test_fake_adapter_scripted_exhaustion_fails_closed():
    import pytest
    from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
    from mechcad_harness.agents.models import AgentAuthoredResponsePayload, AgentContext, AgentInvocationRequest
    from mechcad_harness.models import DesignState

    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    response = AgentAuthoredResponsePayload(status="succeeded", summary="A", findings=(), issues=(), constraint_requests=(), change_proposals=())
    adapter = FakeAgentAdapter(identity, scripted_responses=(response,))
    context = AgentContext(project_id="PRJ", run_id="RUN", task_id="TASK", revision=1, state_hash="hash", design_state=DesignState(id="DES", revision=1), task_objective="test", task_instructions="test")
    request = AgentInvocationRequest(invocation_id="INV", agent=identity, project_id="PRJ", run_id="RUN", task_id="TASK", bound_revision=1, bound_state_hash="hash", context=context, requested_output_schema_version="1.0", context_hash="ctx")
    adapter.invoke(request)
    with pytest.raises(Exception, match="scripted responses exhausted"):
        adapter.invoke(request)


def test_fake_adapter_duplicate_identity_registration_remains_rejected():
    import pytest
    from mechcad_harness.agents import AgentIdentity, AgentRegistry, FakeAgentAdapter

    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    registry = AgentRegistry()
    registry.register(identity, FakeAgentAdapter(identity))
    with pytest.raises(ValueError, match="duplicate agent registration"):
        registry.register(identity, FakeAgentAdapter(identity))


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
    from mechcad_harness.agents.models import AgentAuthoredResponsePayload, AgentChangeProposalDraft

    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    controller, run, task, snapshot = _controller(tmp_path)
    from mechcad_harness.agents import AgentRegistry, ContextBuilder
    from mechcad_harness.agents.gateway import AgentGateway
    registry = AgentRegistry()
    registry.register(identity, FakeAgentAdapter(identity, response=AgentAuthoredResponsePayload(status="succeeded", summary="", findings=(), issues=(), constraint_requests=(), change_proposals=(AgentChangeProposalDraft(title="Proposal", operations=()),))))
    gateway = AgentGateway(controller, registry, ContextBuilder(controller))
    snapshot_hash = run.active_state_hash
    result = gateway.invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version)
    assert result.response.change_proposals[0].title == "Proposal"
    assert controller.state_manager._read_snapshot("PRJ-1", 1).state_hash == snapshot_hash


def test_gateway_fails_wrong_proposal_revision_or_hash(tmp_path):
    from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
    from mechcad_harness.agents.models import AgentAuthoredResponsePayload, AgentChangeProposalDraft

    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    gateway, controller, run, task, identity = _gateway(tmp_path, FakeAgentAdapter(identity, response=AgentAuthoredResponsePayload(status="succeeded", summary="", findings=(), issues=(), constraint_requests=(), change_proposals=(AgentChangeProposalDraft(title="Bad", operations=()),))))
    result = gateway.invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version)
    assert result.status.value == "succeeded"
    assert controller.state_manager._read_snapshot("PRJ-1", 1).state_hash == run.active_state_hash


def test_gateway_rejects_enabled_discovery_contract_and_accepts_disabled_discovery(tmp_path):
    from mechcad_harness.agents import AgentIdentity, AgentRegistry, ContextBuilder, FakeAgentAdapter
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.models import AgentAuthoredResponseContract, AgentAuthoredResponsePayload
    from mechcad_harness.agents.tool_mediation import AgentToolMediationMode

    controller, run, task, _ = _controller(tmp_path)
    identity = AgentIdentity(agent_name="agent", agent_version="1.0", role="test", protocol_version="1.0")
    adapter = FakeAgentAdapter(identity, response=AgentAuthoredResponsePayload(status="succeeded", summary="ok", findings=(), issues=(), constraint_requests=(), change_proposals=()))
    registry = AgentRegistry()
    registry.register(identity, adapter)
    gateway = AgentGateway(controller, registry, ContextBuilder(controller))
    with pytest.raises(ValueError, match="enabled mediation"):
        gateway.invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version, mediation_mode=AgentToolMediationMode.ENABLED, response_contract=AgentAuthoredResponseContract.CONSTRAINT_DISCOVERY_TOOLS_FORBIDDEN)
    result = gateway.invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version, mediation_mode=AgentToolMediationMode.DISABLED, response_contract=AgentAuthoredResponseContract.CONSTRAINT_DISCOVERY_TOOLS_FORBIDDEN)
    assert result.status.value == "succeeded"


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
