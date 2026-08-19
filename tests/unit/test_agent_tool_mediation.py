import json
import math
from pathlib import Path

import pytest
from pydantic import ValidationError


def _controller(tmp_path, *, allowed_tools=("mechcad-calc-torque@1.0",)):
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
    task = TaskDefinition(task_id="TASK-1", run_id=run.run_id, task_type="agent", objective="inspect", bound_revision=1, bound_state_hash=snapshot.state_hash, allowed_tools=allowed_tools)
    controller.add_task(run.run_id, task)
    return controller, run, task, snapshot


def _request(arguments=None, capability="transmission.torque"):
    from mechcad_harness.agents.models import AgentToolRequestDraft

    return AgentToolRequestDraft(capability=capability, arguments=arguments or {"force_n": 10, "lever_arm_m": 0.2, "safety_factor": 2})


def test_authored_tool_request_is_semantic_and_json_safe():
    from mechcad_harness.agents.models import AgentToolRequestDraft

    request = _request()
    assert set(request.model_dump()) == {"capability", "arguments"}
    with pytest.raises(ValidationError):
        AgentToolRequestDraft.model_validate({"capability": "x", "arguments": {}, "tool_name": "bad"})
    with pytest.raises(ValidationError):
        AgentToolRequestDraft.model_validate({"capability": "transmission.torque", "arguments": {"force_n": math.nan, "lever_arm_m": 0.2, "safety_factor": 2}})


def test_authored_response_without_tool_requests_remains_valid():
    from mechcad_harness.agents.models import AgentAuthoredResponsePayload

    response = AgentAuthoredResponsePayload(status="succeeded", summary="ok", findings=(), issues=(), constraint_requests=(), change_proposals=())
    assert response.tool_requests == ()


def test_gateway_mediation_mode_defaults_enabled_and_disabled_observes_without_execution(tmp_path):
    from mechcad_harness.agents import AgentIdentity, AgentRegistry, ContextBuilder, FakeAgentAdapter
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.models import AgentAuthoredResponsePayload
    from mechcad_harness.agents.persistence import AgentStore
    from mechcad_harness.agents.tool_mediation import AgentToolMediationMode

    controller, run, task, snapshot = _controller(tmp_path)
    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    response = AgentAuthoredResponsePayload(status="succeeded", summary="reasoned", findings=("finding",), issues=(), constraint_requests=(), change_proposals=(), tool_requests=(_request(),))
    adapter = FakeAgentAdapter(identity, response=response)
    registry = AgentRegistry()
    registry.register(identity, adapter)
    gateway = AgentGateway(controller, registry, ContextBuilder(controller))

    result = gateway.invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version, mediation_mode=AgentToolMediationMode.DISABLED)
    assert result.status.value == "failed"
    assert not list((tmp_path / "projects" / "PRJ-1" / "runs" / run.run_id / "agents" / "tool_request_observations").glob("*.json"))


def test_gateway_persists_trusted_response_contract_before_adapter_execution(tmp_path):
    from mechcad_harness.agents.models import AgentAuthoredResponseContract
    from mechcad_harness.agents.persistence import AgentStore
    from mechcad_harness.agents.tool_mediation import AgentToolMediationMode

    from mechcad_harness.agents import AgentIdentity, AgentRegistry, ContextBuilder, FakeAgentAdapter
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.models import AgentAuthoredResponsePayload

    controller, run, task, _ = _controller(tmp_path)
    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    adapter = FakeAgentAdapter(identity, response=AgentAuthoredResponsePayload(status="succeeded", summary="ok", findings=(), issues=(), constraint_requests=(), change_proposals=()))
    registry = AgentRegistry()
    registry.register(identity, adapter)
    gateway = AgentGateway(controller, registry, ContextBuilder(controller))
    result = gateway.invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version, mediation_mode=AgentToolMediationMode.DISABLED)
    invocation = AgentStore(tmp_path).load_invocation("PRJ-1", run.run_id, result.invocation_id)
    assert invocation.request.response_contract is AgentAuthoredResponseContract.TOOL_REQUESTS_FORBIDDEN
    assert invocation.request.response_schema_hash.startswith("sha256:")


def test_gateway_persists_empty_request_observation(tmp_path):
    from mechcad_harness.agents import AgentIdentity, AgentRegistry, ContextBuilder, FakeAgentAdapter
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.persistence import AgentStore

    controller, run, task, snapshot = _controller(tmp_path)
    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    adapter = FakeAgentAdapter(identity, findings=("finding",))
    registry = AgentRegistry()
    registry.register(identity, adapter)
    result = AgentGateway(controller, registry, ContextBuilder(controller)).invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version)
    observation = AgentStore(tmp_path).load_tool_request_observation("PRJ-1", run.run_id, adapter.last_request.invocation_id)
    assert result.status.value == "succeeded"
    assert observation.tool_requests == ()


def test_gateway_persists_discovery_observation_before_agent_result(tmp_path):
    from mechcad_harness.agents import AgentConstraintRequestDraft, AgentIdentity, AgentRegistry, ContextBuilder, FakeAgentAdapter
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.models import AgentAuthoredResponseContract, AgentConstraintDiscoveryResponsePayload
    from mechcad_harness.agents.persistence import AgentStore
    from mechcad_harness.agents.tool_mediation import AgentToolMediationMode
    from mechcad_harness.agents.constraint_requests import SupportedConstraintKey

    controller, run, task, _ = _controller(tmp_path)
    identity = AgentIdentity(agent_name="agent", agent_version="1.0", role="test", protocol_version="1.0")
    response = AgentConstraintDiscoveryResponsePayload(status="succeeded", summary="discover", findings=(), issues=(), constraint_requests=(AgentConstraintRequestDraft(key=SupportedConstraintKey.OUTPUT_INTERFACE, description="interface", rationale="needed"),), change_proposals=())
    adapter = FakeAgentAdapter(identity, response=response)
    registry = AgentRegistry()
    registry.register(identity, adapter)
    gateway = AgentGateway(controller, registry, ContextBuilder(controller))
    order = []
    original_constraint = gateway.store.write_constraint_request_observation
    original_tool = gateway.store.write_tool_request_observation
    original_result = gateway.store.write_result
    gateway.store.write_constraint_request_observation = lambda record: (order.append("constraint"), original_constraint(record))[1]
    gateway.store.write_tool_request_observation = lambda record: (order.append("tool"), original_tool(record))[1]
    gateway.store.write_result = lambda record: (order.append("result"), original_result(record))[1]
    result = gateway.invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version, mediation_mode=AgentToolMediationMode.DISABLED, response_contract=AgentAuthoredResponseContract.CONSTRAINT_DISCOVERY_TOOLS_FORBIDDEN)
    assert result.status.value == "succeeded"
    assert order == ["constraint", "tool", "result"]
    observation = AgentStore(tmp_path).load_constraint_request_observation("PRJ-1", run.run_id, adapter.last_request.invocation_id)
    assert observation.constraint_requests[0].key is SupportedConstraintKey.OUTPUT_INTERFACE


def test_gateway_discovery_observation_failure_prevents_successful_result(tmp_path):
    from mechcad_harness.agents import AgentConstraintRequestDraft, AgentIdentity, AgentRegistry, ContextBuilder, FakeAgentAdapter
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.models import AgentAuthoredResponseContract, AgentConstraintDiscoveryResponsePayload
    from mechcad_harness.agents.tool_mediation import AgentToolMediationMode
    from mechcad_harness.agents.constraint_requests import SupportedConstraintKey

    controller, run, task, _ = _controller(tmp_path)
    identity = AgentIdentity(agent_name="agent", agent_version="1.0", role="test", protocol_version="1.0")
    response = AgentConstraintDiscoveryResponsePayload(status="succeeded", summary="discover", findings=(), issues=(), constraint_requests=(AgentConstraintRequestDraft(key=SupportedConstraintKey.OUTPUT_INTERFACE, description="interface", rationale="needed"),), change_proposals=())
    registry = AgentRegistry()
    registry.register(identity, FakeAgentAdapter(identity, response=response))
    gateway = AgentGateway(controller, registry, ContextBuilder(controller))
    gateway.store.write_constraint_request_observation = lambda record: (_ for _ in ()).throw(OSError("disk full"))
    result = gateway.invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version, mediation_mode=AgentToolMediationMode.DISABLED, response_contract=AgentAuthoredResponseContract.CONSTRAINT_DISCOVERY_TOOLS_FORBIDDEN)
    assert result.status.value == "failed"
    assert result.error == "CONSTRAINT_OBSERVATION_PERSISTENCE_FAILED"


def test_observation_persistence_failure_blocks_success_and_mediation(tmp_path):
    from mechcad_harness.agents import AgentIdentity, AgentRegistry, ContextBuilder, FakeAgentAdapter
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.models import AgentAuthoredResponsePayload
    from mechcad_harness.agents.persistence import AgentStore
    from mechcad_harness.tools import BuiltinTools, ToolBroker, ToolRegistry

    controller, run, task, snapshot = _controller(tmp_path)
    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    response = AgentAuthoredResponsePayload(status="succeeded", summary="reasoned", findings=("finding",), issues=(), constraint_requests=(), change_proposals=(), tool_requests=(_request(),))
    registry = AgentRegistry()
    registry.register(identity, FakeAgentAdapter(identity, response=response))
    broker = ToolBroker(controller, ToolRegistry(BuiltinTools.registrations()))
    gateway = AgentGateway(controller, registry, ContextBuilder(controller), tool_broker=broker)
    gateway.store.write_tool_request_observation = lambda record: (_ for _ in ()).throw(OSError("disk full"))

    result = gateway.invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version)
    assert result.status.value == "failed"
    assert result.error == "OBSERVATION_PERSISTENCE_FAILED"
    assert not list((tmp_path / "projects" / "PRJ-1" / "runs" / run.run_id / "tool_calls").glob("*.json"))


def test_capability_policy_resolves_exact_tool_and_denies_untrusted_identity():
    from mechcad_harness.agents import AgentIdentity
    from mechcad_harness.agents.tool_mediation import CapabilityPolicy, ToolMediationError

    policy = CapabilityPolicy()
    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    assert policy.resolve(identity, "transmission.torque") == ("mechcad-calc-torque", "1.0")
    with pytest.raises(ToolMediationError, match="UNKNOWN_TOOL_CAPABILITY"):
        policy.resolve(identity, "unknown")
    other = identity.model_copy(update={"agent_name": "other"})
    with pytest.raises(ToolMediationError, match="TOOL_CAPABILITY_NOT_AUTHORIZED"):
        policy.resolve(other, "transmission.torque")


def test_mediation_id_is_deterministic():
    from mechcad_harness.agents.tool_mediation import mediation_id

    first = mediation_id("INV-1", 0, "transmission.torque", "sha256:args")
    assert first == mediation_id("INV-1", 0, "transmission.torque", "sha256:args")
    assert first != mediation_id("INV-2", 0, "transmission.torque", "sha256:args")


def test_mediator_executes_existing_broker_without_evidence(tmp_path):
    from mechcad_harness.agents import AgentIdentity
    from mechcad_harness.agents.models import AgentInvocationRequest
    from mechcad_harness.agents.tool_mediation import AgentToolMediator
    from mechcad_harness.tools import BuiltinTools, ToolBroker, ToolRegistry

    controller, run, task, snapshot = _controller(tmp_path)
    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    invocation = AgentInvocationRequest(invocation_id="INV-1", agent=identity, project_id="PRJ-1", run_id=run.run_id, task_id=task.task_id, bound_revision=1, bound_state_hash=snapshot.state_hash, context_hash="ctx", context={"project_id": "PRJ-1", "run_id": run.run_id, "task_id": task.task_id, "revision": 1, "state_hash": snapshot.state_hash, "design_state": snapshot.state, "task_objective": "inspect", "task_instructions": "inspect"}, requested_output_schema_version="1.0")
    broker = ToolBroker(controller, ToolRegistry(BuiltinTools.registrations()))
    mediator = AgentToolMediator(controller, broker)
    result = mediator.mediate(invocation, identity, (_request(),), source_result_id="AGENTRES-1")
    assert result.status == "succeeded"
    assert result.tool_result_id
    mediation_dir = Path(tmp_path) / "projects" / "PRJ-1" / "runs" / run.run_id / "agents" / "tool_mediation" / result.mediation_id
    assert (mediation_dir / "pending.json").exists()
    assert (mediation_dir / "final.json").exists()
    assert not list((tmp_path / "projects" / "PRJ-1" / "evidence").glob("*.json"))


def test_mediator_rejects_multiple_requests_before_execution(tmp_path):
    from mechcad_harness.agents import AgentIdentity
    from mechcad_harness.agents.models import AgentInvocationRequest
    from mechcad_harness.agents.tool_mediation import AgentToolMediator, ToolMediationError
    from mechcad_harness.tools import BuiltinTools, ToolBroker, ToolRegistry

    controller, run, task, snapshot = _controller(tmp_path)
    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    invocation = AgentInvocationRequest(invocation_id="INV-1", agent=identity, project_id="PRJ-1", run_id=run.run_id, task_id=task.task_id, bound_revision=1, bound_state_hash=snapshot.state_hash, context_hash="ctx", context={"project_id": "PRJ-1", "run_id": run.run_id, "task_id": task.task_id, "revision": 1, "state_hash": snapshot.state_hash, "design_state": snapshot.state, "task_objective": "inspect", "task_instructions": "inspect"}, requested_output_schema_version="1.0")
    broker = ToolBroker(controller, ToolRegistry(BuiltinTools.registrations()))
    calls = 0
    original = broker.execute
    def execute(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)
    broker.execute = execute
    mediator = AgentToolMediator(controller, broker)
    with pytest.raises(ToolMediationError, match="DUPLICATE_TOOL_REQUEST"):
        mediator.mediate(invocation, identity, (_request(), _request()))
    assert calls == 0


def test_gateway_persists_successful_agent_result_before_mediation(tmp_path):
    from mechcad_harness.agents import AgentIdentity, AgentRegistry, ContextBuilder, FakeAgentAdapter
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.models import AgentAuthoredResponsePayload
    from mechcad_harness.tools import BuiltinTools, ToolBroker, ToolRegistry

    controller, run, task, snapshot = _controller(tmp_path)
    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    response = AgentAuthoredResponsePayload(status="succeeded", summary="reasoned", findings=(), issues=(), constraint_requests=(), change_proposals=(), tool_requests=(_request(),))
    registry = AgentRegistry()
    registry.register(identity, FakeAgentAdapter(identity, response=response))
    broker = ToolBroker(controller, ToolRegistry(BuiltinTools.registrations()))
    gateway = AgentGateway(controller, registry, ContextBuilder(controller), tool_broker=broker)
    result = gateway.invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version)
    assert result.status.value == "succeeded"
    assert result.response is not None
    assert "tool_requests" not in type(result.response).model_fields
    assert list((tmp_path / "projects" / "PRJ-1" / "runs" / run.run_id / "agents" / "results").glob("*.json"))


def _invocation(controller, run, task, snapshot, identity, invocation_id="INV-1"):
    from mechcad_harness.agents.models import AgentInvocationRequest

    return AgentInvocationRequest(invocation_id=invocation_id, agent=identity, project_id="PRJ-1", run_id=run.run_id, task_id=task.task_id, bound_revision=1, bound_state_hash=snapshot.state_hash, context_hash="ctx", context={"project_id": "PRJ-1", "run_id": run.run_id, "task_id": task.task_id, "revision": 1, "state_hash": snapshot.state_hash, "design_state": snapshot.state, "task_objective": "inspect", "task_instructions": "inspect"}, requested_output_schema_version="1.0")


def test_mediator_enforces_task_permission_and_unknown_capability(tmp_path):
    from mechcad_harness.agents import AgentIdentity
    from mechcad_harness.agents.tool_mediation import AgentToolMediator, ToolMediationError
    from mechcad_harness.tools import BuiltinTools, ToolBroker, ToolRegistry

    controller, run, task, snapshot = _controller(tmp_path, allowed_tools=())
    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    invocation = _invocation(controller, run, task, snapshot, identity)
    broker = ToolBroker(controller, ToolRegistry(BuiltinTools.registrations()))
    calls = []
    broker.execute = lambda *args, **kwargs: calls.append((args, kwargs))
    mediator = AgentToolMediator(controller, broker)
    with pytest.raises(ToolMediationError, match="TASK_TOOL_NOT_AUTHORIZED"):
        mediator.mediate(invocation, identity, (_request(),))
    assert calls == []
    unknown_request = type("UnknownRequest", (), {"capability": "other", "arguments": _request().arguments})()
    with pytest.raises(ToolMediationError, match="UNKNOWN_TOOL_CAPABILITY"):
        mediator.mediate(invocation, identity, (unknown_request,))
    mediation_root = tmp_path / "projects" / "PRJ-1" / "runs" / run.run_id / "agents" / "tool_mediation"
    assert len(list(mediation_root.glob("*/pending.json"))) == 2
    assert len(list(mediation_root.glob("*/final.json"))) == 2


def test_mediator_passes_typed_arguments_to_broker(tmp_path):
    from mechcad_harness.agents import AgentIdentity
    from mechcad_harness.agents.tool_mediation import AgentToolMediator
    from mechcad_harness.tools import BuiltinTools, ToolBroker, ToolRegistry

    controller, run, task, snapshot = _controller(tmp_path)
    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    invocation = _invocation(controller, run, task, snapshot, identity)
    broker = ToolBroker(controller, ToolRegistry(BuiltinTools.registrations()))
    captured = {}
    original = broker.execute
    def execute(run_id, task_id, tool_name, tool_version, inputs, **kwargs):
        captured.update(inputs)
        return original(run_id, task_id, tool_name, tool_version, inputs, **kwargs)
    broker.execute = execute
    mediator = AgentToolMediator(controller, broker)
    record = mediator.mediate(invocation, identity, (_request(),))
    assert record.status == "succeeded"
    assert captured == {"force_n": 10.0, "lever_arm_m": 0.2, "safety_factor": 2.0}
    assert record.tool_result_id is not None
    assert len(list((tmp_path / "projects" / "PRJ-1" / "runs" / run.run_id / "tool_calls").glob("*.json"))) == 1
    assert len(list((tmp_path / "projects" / "PRJ-1" / "runs" / run.run_id / "tool_results").glob("*.json"))) == 1


def test_stale_before_execution_does_not_write_tool_call(tmp_path):
    from mechcad_harness.agents import AgentIdentity
    from mechcad_harness.agents.tool_mediation import AgentToolMediator, ToolMediationError
    from mechcad_harness.tools import BuiltinTools, ToolBroker, ToolRegistry

    controller, run, task, snapshot = _controller(tmp_path)
    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    invocation = _invocation(controller, run, task, snapshot, identity)
    controller.record_convergence_revision(run.run_id, 2, "sha256:advanced")
    broker = ToolBroker(controller, ToolRegistry(BuiltinTools.registrations()))
    mediator = AgentToolMediator(controller, broker)
    with pytest.raises(ToolMediationError, match="STALE_TOOL_REQUEST_BINDING"):
        mediator.mediate(invocation, identity, (_request(),))
    tool_dir = tmp_path / "projects" / "PRJ-1" / "runs" / run.run_id
    assert not (tool_dir / "tool_calls").exists()
    assert len(list((tool_dir / "agents" / "tool_mediation").glob("*/final.json"))) == 1


def test_stale_during_execution_retains_original_result_without_rebinding(tmp_path):
    from mechcad_harness.agents import AgentIdentity
    from mechcad_harness.agents.tool_mediation import AgentToolMediator
    from mechcad_harness.tools import BuiltinTools, ToolBroker, ToolRegistry

    controller, run, task, snapshot = _controller(tmp_path)
    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    invocation = _invocation(controller, run, task, snapshot, identity)
    broker = ToolBroker(controller, ToolRegistry(BuiltinTools.registrations()))
    original = broker.execute
    def execute(*args, **kwargs):
        result = original(*args, **kwargs)
        controller.record_convergence_revision(run.run_id, 2, "sha256:advanced")
        return result
    broker.execute = execute
    record = AgentToolMediator(controller, broker).mediate(invocation, identity, (_request(),))
    assert record.failure_kind == "STALE_TOOL_REQUEST_BINDING"
    assert record.bound_revision == 1
    assert record.bound_state_hash == snapshot.state_hash
    assert record.tool_result_id
    assert not list((tmp_path / "projects" / "PRJ-1" / "evidence").glob("*.json"))


def test_pending_and_final_records_are_exclusive(tmp_path):
    from mechcad_harness.agents import AgentIdentity
    from mechcad_harness.agents.models import AgentInvocationRequest
    from mechcad_harness.agents.persistence import AgentStore
    from mechcad_harness.agents.tool_mediation import AgentToolMediator, ToolMediationRecord
    from mechcad_harness.tools import BuiltinTools, ToolBroker, ToolRegistry

    controller, run, task, snapshot = _controller(tmp_path)
    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    invocation = _invocation(controller, run, task, snapshot, identity)
    record = AgentToolMediator(controller, ToolBroker(controller, ToolRegistry(BuiltinTools.registrations()))).mediate(invocation, identity, (_request(),))
    store = AgentStore(tmp_path)
    with pytest.raises(Exception):
        store.write_mediation_pending("PRJ-1", run.run_id, record)
    with pytest.raises(Exception):
        store.write_mediation_final("PRJ-1", run.run_id, record)
