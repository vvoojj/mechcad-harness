import json


def _setup(tmp_path):
    from mechcad_harness.agents import AgentIdentity, AgentRegistry, ContextBuilder, FakeAgentAdapter
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.models import AgentAuthoredResponsePayload
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore
    from mechcad_harness.models import Component, DesignState, Requirement
    from mechcad_harness.runs import RunController, TaskDefinition
    from mechcad_harness.state import StateManager
    from mechcad_harness.tools import BuiltinTools, ToolBroker, ToolRegistry

    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-ROUNDTRIP", DesignState(id="DES-ROUNDTRIP", revision=1, components=[Component(id="P-1", name="Transmission")], requirements=[
        Requirement(id="REQ-TORQUE-FORCE", name="Applied tangential force", description="Applied tangential force at the transmission output is 10 N."),
        Requirement(id="REQ-TORQUE-ARM", name="Effective lever arm", description="Effective lever arm for the output force is 0.2 m."),
        Requirement(id="REQ-TORQUE-SAFETY", name="Torque safety factor", description="Required deterministic design safety factor is 2.0."),
    ]))
    graph = tmp_path / "dependencies.json"
    graph.write_text(json.dumps({"rules": [
        {"when": ["/requirements/REQ-TORQUE-FORCE/description"], "invalidates": ["analysis.transmission.torque"]},
        {"when": ["/requirements/REQ-TORQUE-ARM/description"], "invalidates": ["analysis.transmission.torque"]},
        {"when": ["/requirements/REQ-TORQUE-SAFETY/description"], "invalidates": ["analysis.transmission.torque"]},
    ], "edges": []}), encoding="utf-8")
    controller = RunController(tmp_path, manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/components/*", "owner": "actor"}])), EvidenceStore(tmp_path, manager, DependencyGraph.from_yaml(graph)))
    run = controller.create_run("PRJ-ROUNDTRIP")
    task = TaskDefinition(task_id="TASK-ROUNDTRIP", run_id=run.run_id, task_type="agent", objective="Perform bounded transmission torque round trip.", bound_revision=1, bound_state_hash=snapshot.state_hash, allowed_tools=("mechcad-calc-torque@1.0",))
    controller.add_task(run.run_id, task)
    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    requests = (AgentAuthoredResponsePayload(status="succeeded", summary="A", findings=("Torque calculation requested from authoritative inputs.",), issues=(), constraint_requests=(), change_proposals=(), tool_requests=(__import__("mechcad_harness.agents.models", fromlist=["AgentToolRequestDraft"]).AgentToolRequestDraft(capability="transmission.torque", arguments={"force_n": 10, "lever_arm_m": 0.2, "safety_factor": 2}),)),)
    b_response = AgentAuthoredResponsePayload(status="succeeded", summary="B", findings=("The required design torque is supplied by current Evidence.",), issues=(), constraint_requests=(), change_proposals=(), tool_requests=())
    adapter = FakeAgentAdapter(identity, scripted_responses=(requests[0], b_response))
    registry = AgentRegistry()
    registry.register(identity, adapter)
    broker = ToolBroker(controller, ToolRegistry(BuiltinTools.registrations()))
    gateway = AgentGateway(controller, registry, ContextBuilder(controller), tool_broker=broker)
    return controller, run, task, snapshot, identity, gateway, registry, adapter


def test_bounded_transmission_roundtrip_produces_one_tool_and_current_evidence(tmp_path):
    from mechcad_harness.agents.roundtrip import TransmissionToolRoundTripCoordinator

    controller, run, task, snapshot, identity, gateway, registry, adapter = _setup(tmp_path)
    result = TransmissionToolRoundTripCoordinator(controller, gateway, registry).run(run.run_id, task.task_id, identity.agent_name, identity.agent_version, selected_requirement_ids=("REQ-TORQUE-FORCE", "REQ-TORQUE-ARM", "REQ-TORQUE-SAFETY"))
    assert result.status == "complete", result.failure_kind
    run_dir = tmp_path / "projects" / "PRJ-ROUNDTRIP" / "runs" / run.run_id
    assert len(list((run_dir / "tool_calls").glob("*.json"))) == 1
    assert len(list((run_dir / "tool_results").glob("*.json"))) == 1
    assert len(list((tmp_path / "projects" / "PRJ-ROUNDTRIP" / "evidence").glob("*.json"))) == 1
    transitions = sorted((run_dir / "agents" / "roundtrips").glob("*/*.json"))
    assert [path.name for path in transitions] == [
        "00_started.json",
        "10_invocation_a.json",
        "20_tool_result.json",
        "30_evidence.json",
        "40_invocation_b.json",
        "50_complete.json",
    ]
    assert controller.state_manager._read_current("PRJ-ROUNDTRIP")["state_hash"] == snapshot.state_hash


def test_bounded_roundtrip_b_request_never_mediates(tmp_path):
    from mechcad_harness.agents import FakeAgentAdapter
    from mechcad_harness.agents.models import AgentAuthoredResponsePayload, AgentToolRequestDraft
    from mechcad_harness.agents.roundtrip import TransmissionToolRoundTripCoordinator

    controller, run, task, snapshot, identity, gateway, registry, adapter = _setup(tmp_path)
    adapter._scripted_responses = (adapter._scripted_responses[0], AgentAuthoredResponsePayload(status="succeeded", summary="B", findings=("finding",), issues=(), constraint_requests=(), change_proposals=()))
    result = TransmissionToolRoundTripCoordinator(controller, gateway, registry).run(run.run_id, task.task_id, identity.agent_name, identity.agent_version, selected_requirement_ids=("REQ-TORQUE-FORCE", "REQ-TORQUE-ARM", "REQ-TORQUE-SAFETY"))
    assert result.status == "complete"
    run_dir = tmp_path / "projects" / "PRJ-ROUNDTRIP" / "runs" / run.run_id
    assert len(list((run_dir / "tool_calls").glob("*.json"))) == 1
    assert len(list((run_dir / "tool_results").glob("*.json"))) == 1
    transitions = sorted((run_dir / "agents" / "roundtrips").glob("*/*.json"))
    assert [path.name for path in transitions] == [
        "00_started.json",
        "10_invocation_a.json",
        "20_tool_result.json",
        "30_evidence.json",
        "40_invocation_b.json",
        "50_complete.json",
    ]


def test_bounded_roundtrip_recovery_does_not_repeat_a_tool_or_b(tmp_path):
    from mechcad_harness.agents import FakeAgentAdapter
    from mechcad_harness.agents.models import AgentAuthoredResponsePayload, AgentToolRequestDraft
    from mechcad_harness.agents.roundtrip import TransmissionToolRoundTripCoordinator

    controller, run, task, snapshot, identity, gateway, registry, adapter = _setup(tmp_path)
    adapter._scripted_responses = (adapter._scripted_responses[0], AgentAuthoredResponsePayload(status="succeeded", summary="B", findings=("finding",), issues=(), constraint_requests=(), change_proposals=()))
    coordinator = TransmissionToolRoundTripCoordinator(controller, gateway, registry)
    result = coordinator.run(run.run_id, task.task_id, identity.agent_name, identity.agent_version, selected_requirement_ids=("REQ-TORQUE-FORCE", "REQ-TORQUE-ARM", "REQ-TORQUE-SAFETY"))
    assert result.status == "complete"
    invocation_count = adapter.invocation_count
    tool_call_count = len(list((tmp_path / "projects" / "PRJ-ROUNDTRIP" / "runs" / run.run_id / "tool_calls").glob("*.json")))
    resumed = coordinator.resume(run.run_id, task.task_id, identity.agent_name, identity.agent_version)
    assert resumed.status == "complete"
    assert adapter.invocation_count == invocation_count
    assert len(list((tmp_path / "projects" / "PRJ-ROUNDTRIP" / "runs" / run.run_id / "tool_calls").glob("*.json"))) == tool_call_count


def test_bounded_roundtrip_forbidden_contract_fails_before_b_observation(tmp_path):
    from mechcad_harness.agents.models import AgentAuthoredResponsePayload, AgentToolRequestDraft
    from mechcad_harness.agents.roundtrip import TransmissionToolRoundTripCoordinator

    controller, run, task, snapshot, identity, gateway, registry, adapter = _setup(tmp_path)
    adapter._scripted_responses = (adapter._scripted_responses[0], AgentAuthoredResponsePayload(status="succeeded", summary="B", findings=("finding",), issues=(), constraint_requests=(), change_proposals=(), tool_requests=(AgentToolRequestDraft(capability="transmission.torque", arguments={"force_n": 10, "lever_arm_m": 0.2, "safety_factor": 2}),)))
    result = TransmissionToolRoundTripCoordinator(controller, gateway, registry).run(run.run_id, task.task_id, identity.agent_name, identity.agent_version, selected_requirement_ids=("REQ-TORQUE-FORCE", "REQ-TORQUE-ARM", "REQ-TORQUE-SAFETY"))
    assert result.failure_kind == "INVOCATION_B_FAILED"
    run_dir = tmp_path / "projects" / "PRJ-ROUNDTRIP" / "runs" / run.run_id
    transition_dir = next((run_dir / "agents" / "roundtrips").glob("*"))
    failure = json.loads((transition_dir / "40_invocation_b_failure.json").read_text(encoding="utf-8"))
    assert failure["failure_kind"] == "INVOCATION_B_FAILED"
    assert failure["response_contract"] == "tool_requests_forbidden"
    assert failure["response_schema_hash"].startswith("sha256:")
    assert len(list((run_dir / "agents" / "tool_request_observations").glob("*.json"))) == 1
    assert len(list((run_dir / "tool_calls").glob("*.json"))) == 1


def test_bounded_roundtrip_a_failure_writes_terminal_transition_and_recovers(tmp_path):
    from mechcad_harness.agents.models import AgentAdapterExecutionError, AgentAdapterProvenance
    from mechcad_harness.agents.roundtrip import TransmissionToolRoundTripCoordinator

    controller, run, task, snapshot, identity, gateway, registry, adapter = _setup(tmp_path)
    adapter._error = RuntimeError("model unavailable")
    result = TransmissionToolRoundTripCoordinator(controller, gateway, registry).run(run.run_id, task.task_id, identity.agent_name, identity.agent_version, selected_requirement_ids=("REQ-TORQUE-FORCE", "REQ-TORQUE-ARM", "REQ-TORQUE-SAFETY"))
    assert result.failure_kind == "INVOCATION_A_FAILED"
    run_dir = tmp_path / "projects" / "PRJ-ROUNDTRIP" / "runs" / run.run_id
    transition_dir = next((run_dir / "agents" / "roundtrips").glob("*"))
    failure = json.loads((transition_dir / "10_invocation_a_failure.json").read_text(encoding="utf-8"))
    assert failure["failure_kind"] == "INVOCATION_A_FAILED"
    assert failure["bound_revision"] == snapshot.revision
    assert failure["bound_state_hash"] == snapshot.state_hash
    calls = adapter.invocation_count
    resumed = TransmissionToolRoundTripCoordinator(controller, gateway, registry).resume(run.run_id, task.task_id, identity.agent_name, identity.agent_version)
    assert resumed.failure_kind == "INVOCATION_A_FAILED"
    assert adapter.invocation_count == calls


def test_bounded_constraint_discovery_roundtrip_materializes_typed_requests(tmp_path):
    from mechcad_harness.agents.constraint_requests import AgentConstraintRequestDraft, SupportedConstraintKey
    from mechcad_harness.agents.models import AgentAuthoredResponseContract, AgentConstraintDiscoveryResponsePayload
    from mechcad_harness.agents.persistence import AgentStore
    from mechcad_harness.agents.roundtrip import TransmissionToolRoundTripCoordinator

    controller, run, task, snapshot, identity, gateway, registry, adapter = _setup(tmp_path)
    b_response = AgentConstraintDiscoveryResponsePayload(status="succeeded", summary="B", findings=("Required design torque is 4 N*m.",), issues=(), constraint_requests=(
        AgentConstraintRequestDraft(key=SupportedConstraintKey.OUTPUT_ANGULAR_SPEED, description="Target output speed", rationale="derive the transmission ratio"),
        AgentConstraintRequestDraft(key=SupportedConstraintKey.OUTPUT_INTERFACE, description="Output shaft interface", rationale="select a compatible output concept"),
    ), change_proposals=())
    adapter._scripted_responses = (adapter._scripted_responses[0], b_response)
    result = TransmissionToolRoundTripCoordinator(controller, gateway, registry).run(run.run_id, task.task_id, identity.agent_name, identity.agent_version, selected_requirement_ids=("REQ-TORQUE-FORCE", "REQ-TORQUE-ARM", "REQ-TORQUE-SAFETY"), mode="constraint_discovery")
    assert result.status == "complete"
    run_dir = tmp_path / "projects" / "PRJ-ROUNDTRIP" / "runs" / run.run_id
    transition_dir = next((run_dir / "agents" / "roundtrips").glob("*"))
    assert [path.name for path in sorted(transition_dir.glob("*.json"))] == ["00_started.json", "10_invocation_a.json", "20_tool_result.json", "30_evidence.json", "40_invocation_b.json", "45_constraint_requests.json", "50_complete.json"]
    records = list((run_dir / "agents" / "constraint_requests").glob("*.json"))
    assert len(records) == 2
    assert len(list((run_dir / "tool_calls").glob("*.json"))) == 1
    assert len(list((run_dir / "tool_results").glob("*.json"))) == 1
    assert len(list((run_dir / "agents" / "constraint_request_observations").glob("*.json"))) == 1
    complete = json.loads((transition_dir / "50_complete.json").read_text(encoding="utf-8"))
    materialized_ids = sorted(path.stem for path in records)
    assert complete["constraint_request_ids"] == materialized_ids
    assert controller.state_manager._read_current("PRJ-ROUNDTRIP")["state_hash"] == snapshot.state_hash


def test_constraint_discovery_duplicate_drafts_materialize_once(tmp_path):
    from mechcad_harness.agents.constraint_requests import AgentConstraintRequestDraft, SupportedConstraintKey
    from mechcad_harness.agents.models import AgentConstraintDiscoveryResponsePayload
    from mechcad_harness.agents.roundtrip import TransmissionToolRoundTripCoordinator

    controller, run, task, _, identity, gateway, registry, adapter = _setup(tmp_path)
    draft = AgentConstraintRequestDraft(key=SupportedConstraintKey.OUTPUT_INTERFACE, description="first wording", rationale="first rationale")
    duplicate = AgentConstraintRequestDraft(key=SupportedConstraintKey.OUTPUT_INTERFACE, description="different wording", rationale="different rationale")
    adapter._scripted_responses = (adapter._scripted_responses[0], AgentConstraintDiscoveryResponsePayload(status="succeeded", summary="B", findings=(), issues=(), constraint_requests=(draft, duplicate), change_proposals=()))
    result = TransmissionToolRoundTripCoordinator(controller, gateway, registry).run(run.run_id, task.task_id, identity.agent_name, identity.agent_version, mode="constraint_discovery")
    assert result.status == "complete"
    assert len(list((tmp_path / "projects" / "PRJ-ROUNDTRIP" / "runs" / run.run_id / "agents" / "constraint_requests").glob("*.json"))) == 1


def test_constraint_discovery_zero_request_completion_is_valid(tmp_path):
    from mechcad_harness.agents.models import AgentConstraintDiscoveryResponsePayload
    from mechcad_harness.agents.roundtrip import TransmissionToolRoundTripCoordinator

    controller, run, task, _, identity, gateway, registry, adapter = _setup(tmp_path)
    adapter._scripted_responses = (adapter._scripted_responses[0], AgentConstraintDiscoveryResponsePayload(status="succeeded", summary="B", findings=("No additional inputs are required.",), issues=(), constraint_requests=(), change_proposals=()))
    result = TransmissionToolRoundTripCoordinator(controller, gateway, registry).run(run.run_id, task.task_id, identity.agent_name, identity.agent_version, mode="constraint_discovery")
    assert result.status == "complete"
    transition_dir = next((tmp_path / "projects" / "PRJ-ROUNDTRIP" / "runs" / run.run_id / "agents" / "roundtrips").glob("*"))
    assert json.loads((transition_dir / "45_constraint_requests.json").read_text(encoding="utf-8"))["constraint_request_ids"] == []
    assert json.loads((transition_dir / "50_complete.json").read_text(encoding="utf-8"))["constraint_request_ids"] == []
