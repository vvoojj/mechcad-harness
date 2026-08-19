import json
import os

import pytest

pytestmark = pytest.mark.skipif(os.getenv("MECHCAD_OPENCODE_LIVE") != "1", reason="OpenCode live validation is opt-in")


def test_real_transmission_constraint_discovery_live(tmp_path):
    from mechcad_harness.agents import AgentIdentity, AgentRegistry, ContextBuilder
    from mechcad_harness.agents.constraint_requests import SupportedConstraintKey
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.models import AgentAuthoredResponseContract
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig, OpenCodeAgentAdapter, OpenCodeModelSelection, OpenCodeResponseMode, resolve_opencode_config_from_environment
    from mechcad_harness.agents.persistence import AgentStore
    from mechcad_harness.agents.roundtrip import TransmissionToolRoundTripCoordinator
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.dependency import DependencyGraph, EvidenceFreshness, EvidenceStore
    from mechcad_harness.models import Component, DesignState, Requirement
    from mechcad_harness.runs import RunController, TaskDefinition
    from mechcad_harness.state import StateManager
    from mechcad_harness.tools import BuiltinTools, ToolBroker, ToolRegistry

    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-TRANSMISSION-CONSTRAINT-DISCOVERY-LIVE", DesignState(id="DES-TRANSMISSION-CONSTRAINT-DISCOVERY-LIVE", revision=1, components=[Component(id="P-LIVE", name="Transmission Part")], requirements=[
        Requirement(id="REQ-TORQUE-FORCE", name="Applied tangential force", description="Applied tangential force at the transmission output is 10 N."),
        Requirement(id="REQ-TORQUE-ARM", name="Effective lever arm", description="Effective lever arm for the output force is 0.2 m."),
        Requirement(id="REQ-TORQUE-SAFETY", name="Torque safety factor", description="Required deterministic design safety factor is 2.0."),
    ]))
    graph_path = tmp_path / "dependencies.json"
    graph_path.write_text(json.dumps({"rules": [
        {"when": ["/requirements/REQ-TORQUE-FORCE/description"], "invalidates": ["analysis.transmission.torque"]},
        {"when": ["/requirements/REQ-TORQUE-ARM/description"], "invalidates": ["analysis.transmission.torque"]},
        {"when": ["/requirements/REQ-TORQUE-SAFETY/description"], "invalidates": ["analysis.transmission.torque"]},
    ], "edges": []}), encoding="utf-8")
    evidence_store = EvidenceStore(tmp_path, manager, DependencyGraph.from_yaml(graph_path))
    controller = RunController(tmp_path, manager, ChangeEngine(manager, OwnershipPolicy.from_file("config/ownership.yaml")), evidence_store)
    run = controller.create_run("PRJ-TRANSMISSION-CONSTRAINT-DISCOVERY-LIVE")
    task = TaskDefinition(task_id="TASK-TRANSMISSION-CONSTRAINT-DISCOVERY-LIVE", run_id=run.run_id, task_type="agent", objective="Use authoritative torque inputs to request one deterministic torque calculation, then use current torque Evidence to identify only missing authoritative inputs required before the next deterministic transmission-design step. Return zero tools and zero change proposals.", bound_revision=1, bound_state_hash=snapshot.state_hash, allowed_tools=("mechcad-calc-torque@1.0",))
    controller.add_task(run.run_id, task)
    _, password = resolve_opencode_config_from_environment(provider_id="screenpipe", model_id="gpt-5.6-luna", agent_name="mechcad-transmission")
    adapter = OpenCodeAgentAdapter(OpenCodeAdapterConfig(project_directory="E:/repo/mechcad-harness", provider_id="screenpipe", model_id="gpt-5.6-luna", agent_name="mechcad-transmission", model_selection=OpenCodeModelSelection.EXPLICIT, response_mode=OpenCodeResponseMode.VALIDATED_JSON_TEXT), password)
    assert adapter.health().healthy
    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    registry = AgentRegistry()
    registry.register(identity, adapter)
    gateway = AgentGateway(controller, registry, ContextBuilder(controller), tool_broker=ToolBroker(controller, ToolRegistry(BuiltinTools.registrations())))
    before = manager._read_current("PRJ-TRANSMISSION-CONSTRAINT-DISCOVERY-LIVE")
    result = TransmissionToolRoundTripCoordinator(controller, gateway, registry).run(run.run_id, task.task_id, identity.agent_name, identity.agent_version, selected_requirement_ids=("REQ-TORQUE-FORCE", "REQ-TORQUE-ARM", "REQ-TORQUE-SAFETY"), mode="constraint_discovery")
    assert result.status == "complete", result.failure_kind
    run_dir = controller.store.run_dir("PRJ-TRANSMISSION-CONSTRAINT-DISCOVERY-LIVE", run.run_id)
    agent_store = AgentStore(tmp_path)
    transition_dir = next((run_dir / "agents" / "roundtrips").glob("*"))
    transitions = {path.name for path in transition_dir.glob("*.json")}
    assert transitions == {"00_started.json", "10_invocation_a.json", "20_tool_result.json", "30_evidence.json", "40_invocation_b.json", "45_constraint_requests.json", "50_complete.json"}
    invocation_a = json.loads((transition_dir / "10_invocation_a.json").read_text(encoding="utf-8"))
    invocation_b = json.loads((transition_dir / "40_invocation_b.json").read_text(encoding="utf-8"))
    result_a = agent_store.load_result("PRJ-TRANSMISSION-CONSTRAINT-DISCOVERY-LIVE", run.run_id, invocation_a["agent_result_a_id"])
    result_b = agent_store.load_result("PRJ-TRANSMISSION-CONSTRAINT-DISCOVERY-LIVE", run.run_id, invocation_b["agent_result_b_id"])
    observation_b = agent_store.load_tool_request_observation("PRJ-TRANSMISSION-CONSTRAINT-DISCOVERY-LIVE", run.run_id, result_b.invocation_id)
    constraint_observation = agent_store.load_constraint_request_observation("PRJ-TRANSMISSION-CONSTRAINT-DISCOVERY-LIVE", run.run_id, result_b.invocation_id)
    assert result_a.status.value == result_b.status.value == "succeeded"
    assert result_b.adapter_provenance.session_id != result_a.adapter_provenance.session_id
    assert observation_b.tool_requests == ()
    assert result_b.response.change_proposals == ()
    assert constraint_observation.response_contract == AgentAuthoredResponseContract.CONSTRAINT_DISCOVERY_TOOLS_FORBIDDEN.value
    assert all(draft.key in set(SupportedConstraintKey) and draft.description and draft.rationale for draft in constraint_observation.constraint_requests)
    request_records = list((run_dir / "agents" / "constraint_requests").glob("*.json"))
    request_ids = sorted(path.stem for path in request_records)
    transition_45 = json.loads((transition_dir / "45_constraint_requests.json").read_text(encoding="utf-8"))
    transition_50 = json.loads((transition_dir / "50_complete.json").read_text(encoding="utf-8"))
    assert transition_45["constraint_request_ids"] == transition_50["constraint_request_ids"] == request_ids
    assert len(list((run_dir / "tool_calls").glob("*.json"))) == 1
    assert len(list((run_dir / "tool_results").glob("*.json"))) == 1
    assert len(list((tmp_path / "projects" / "PRJ-TRANSMISSION-CONSTRAINT-DISCOVERY-LIVE" / "evidence").glob("*.json"))) == 1
    assert manager._read_current("PRJ-TRANSMISSION-CONSTRAINT-DISCOVERY-LIVE") == before
