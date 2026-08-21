import json

from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
from mechcad_harness.agents.gateway import AgentGateway
from mechcad_harness.agents.models import AgentAuthoredResponsePayload, AgentToolRequestDraft
from mechcad_harness.agents.roundtrip import TransmissionToolRoundTripCoordinator
from mechcad_harness.agents.tool_mediation import AgentToolMediator
from mechcad_harness.application import ProductionApplication, ProductionRunBinding
from mechcad_harness.changes import ChangeEngine
from mechcad_harness.dependency import EvidenceStore
from mechcad_harness.models import Component, DesignState, Requirement
from mechcad_harness.runs import RunController
from mechcad_harness.state import StateManager, state_hash
from mechcad_harness.tools import ToolBroker, ToolRegistry
from mechcad_harness.tools.broker import payload_hash


def test_production_application_runs_and_recovers_transmission_roundtrip(tmp_path):
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /components/*\n    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    dependencies.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "when": [
                            "/requirements/REQ-TORQUE-FORCE/description",
                        ],
                        "invalidates": ["analysis.transmission.torque"],
                    },
                    {
                        "when": [
                            "/requirements/REQ-TORQUE-ARM/description",
                        ],
                        "invalidates": ["analysis.transmission.torque"],
                    },
                    {
                        "when": [
                            "/requirements/REQ-TORQUE-SAFETY/description",
                        ],
                        "invalidates": ["analysis.transmission.torque"],
                    },
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    state = DesignState(
        id="DES-production-roundtrip",
        revision=1,
        components=[Component(id="P-transmission", name="Transmission")],
        requirements=[
            Requirement(
                id="REQ-TORQUE-FORCE",
                name="Applied tangential force",
                description="Applied tangential force at the transmission output is 10 N.",
            ),
            Requirement(
                id="REQ-TORQUE-ARM",
                name="Effective lever arm",
                description="Effective lever arm for the output force is 0.2 m.",
            ),
            Requirement(
                id="REQ-TORQUE-SAFETY",
                name="Torque safety factor",
                description="Required deterministic design safety factor is 2.0.",
            ),
        ],
    )
    StateManager(workspace).create_project("PRJ-production-roundtrip", state)
    original_hash = state_hash(state)

    identity = AgentIdentity(
        agent_name="mechcad-transmission",
        agent_version="1.0",
        role="transmission_engineer",
        protocol_version="1.0",
    )
    response_a = AgentAuthoredResponsePayload(
        status="succeeded",
        summary="A",
        findings=("Torque calculation requested from authoritative inputs.",),
        issues=(),
        constraint_requests=(),
        change_proposals=(),
        tool_requests=(
            AgentToolRequestDraft(
                capability="transmission.torque",
                arguments={"force_n": 10, "lever_arm_m": 0.2, "safety_factor": 2},
            ),
        ),
    )
    response_b = AgentAuthoredResponsePayload(
        status="succeeded",
        summary="B",
        findings=("The required design torque is supplied by current Evidence.",),
        issues=(),
        constraint_requests=(),
        change_proposals=(),
        tool_requests=(),
    )
    adapter = FakeAgentAdapter(identity, scripted_responses=(response_a, response_b))
    application = ProductionApplication.create(
        workspace,
        "PRJ-production-roundtrip",
        adapter,
        ownership_path=ownership,
        dependency_path=dependencies,
    )

    captured: list[ProductionRunBinding] = []
    original_create_run = application.create_run

    def capture_create_run(*, max_iterations=3):
        binding = original_create_run(max_iterations=max_iterations)
        captured.append(binding)
        return binding

    application.create_run = capture_create_run
    result = application.run_transmission_round_trip(
        selected_requirement_ids=(
            "REQ-TORQUE-FORCE",
            "REQ-TORQUE-ARM",
            "REQ-TORQUE-SAFETY",
        ),
    )

    assert result.status == "complete", result.failure_kind
    assert adapter.invocation_count == 2
    run_id = adapter.requests[0].run_id
    run_dir = workspace / "projects" / application.project_id / "runs" / run_id
    call_paths = list((run_dir / "tool_calls").glob("*.json"))
    result_paths = list((run_dir / "tool_results").glob("*.json"))
    assert len(call_paths) == 1
    assert len(result_paths) == 1
    tool_call = application.tool_broker.store.load_call(
        application.project_id, run_id, call_paths[0].stem
    )
    tool_result = application.tool_broker.store.load_result(
        application.project_id, run_id, result_paths[0].stem
    )
    assert (tool_call.project_id, tool_call.run_id, tool_call.task_id) == (
        application.project_id,
        run_id,
        "TASK-transmission-roundtrip",
    )
    assert (tool_result.project_id, tool_result.run_id, tool_result.task_id) == (
        application.project_id,
        run_id,
        "TASK-transmission-roundtrip",
    )
    assert (tool_call.tool_name, tool_call.tool_version) == (
        "mechcad-calc-torque",
        "1.0",
    )
    assert (tool_result.tool_name, tool_result.tool_version) == (
        "mechcad-calc-torque",
        "1.0",
    )
    assert tool_result.call_id == tool_call.call_id
    assert tool_result.input_hash == tool_call.input_hash == payload_hash(tool_call.inputs)
    assert tool_result.output is not None
    assert tool_result.output_hash == payload_hash(tool_result.output)
    assert tool_result.backend_provenance is None
    assert tool_call.bound_revision == tool_result.bound_revision
    assert tool_call.bound_state_hash == tool_result.bound_state_hash
    evidence_paths = list((workspace / "projects" / application.project_id / "evidence").glob("*.json"))
    assert len(evidence_paths) == 1
    evidence = application.evidence_store.load_evidence(
        application.project_id, evidence_paths[0].stem
    )
    assert evidence_paths[0].parents[1].name == application.project_id
    assert evidence.revision == tool_result.bound_revision
    assert evidence.state_hash == tool_result.bound_state_hash
    assert evidence.producer_type == "tool"
    assert evidence.producer_name == tool_result.tool_name
    assert evidence.producer_version == tool_result.tool_version
    assert evidence.producer_result_id == tool_result.result_id
    assert evidence.input_hash == tool_result.input_hash
    assert evidence.output_hash == tool_result.output_hash
    assert evidence.backend_provenance == tool_result.backend_provenance
    assert application.state_manager._read_current(application.project_id)["state_hash"] == original_hash

    assert len(captured) == 1
    binding = captured[0]
    assert binding.source.revision == binding.run.active_revision
    assert binding.source.state_hash == binding.run.active_state_hash
    task = application.run_controller.store.load_task_definition(
        application.project_id,
        run_id,
        "TASK-transmission-roundtrip",
    )
    assert task.bound_revision == binding.source.revision
    assert task.bound_state_hash == binding.source.state_hash
    assert task.allowed_tools == ("mechcad-calc-torque@1.0",)
    assert task.objective == "Perform bounded transmission torque round trip."
    assert application.agent_registry.get_identity("mechcad-transmission", "1.0").role == "transmission_engineer"
    assert adapter.requests[0].agent.role == "transmission_engineer"

    invocation_paths = list((run_dir / "agents" / "invocations").glob("*.json"))
    assert len(invocation_paths) == 2
    invocations = [
        application.agent_gateway.store.load_invocation(
            application.project_id, run_id, path.stem
        )
        for path in invocation_paths
    ]
    assert all(invocation.request.agent == identity for invocation in invocations)
    for invocation in invocations:
        assert (
            invocation.request.project_id,
            invocation.request.run_id,
            invocation.request.task_id,
        ) == (application.project_id, run_id, "TASK-transmission-roundtrip")
        assert invocation.request.bound_revision == binding.source.revision
        assert invocation.request.bound_state_hash == binding.source.state_hash

    assert isinstance(application.run_controller, RunController)
    assert isinstance(application.agent_gateway, AgentGateway)
    assert isinstance(application.agent_gateway.tool_mediator, AgentToolMediator)
    assert isinstance(application.tool_broker, ToolBroker)
    assert isinstance(application.tool_registry, ToolRegistry)
    assert isinstance(application.evidence_store, EvidenceStore)
    assert isinstance(application.change_engine, ChangeEngine)

    evidence_summary = adapter.requests[1].context.evidence_summaries
    assert len(evidence_summary) == 1
    assert evidence_summary[0].summary == "Required design torque: 4 N*m"
    assert "ToolResult" not in evidence_summary[0].summary

    coordinator = TransmissionToolRoundTripCoordinator(
        application.run_controller,
        application.agent_gateway,
        application.agent_registry,
    )
    resumed = coordinator.resume(
        run_id,
        "TASK-transmission-roundtrip",
        "mechcad-transmission",
        "1.0",
    )
    assert resumed.status == "complete"
    assert adapter.invocation_count == 2
    assert len(list((run_dir / "tool_calls").glob("*.json"))) == 1
