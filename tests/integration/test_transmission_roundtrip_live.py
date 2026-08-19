import json
import os
from pathlib import Path

import pytest

def _load_phase_results(run_dir, agent_store, project_id, run_id):
    roundtrip_dir = next((run_dir / "agents" / "roundtrips").glob("*"))
    invocation_a = json.loads((roundtrip_dir / "10_invocation_a.json").read_text(encoding="utf-8"))
    invocation_b = json.loads((roundtrip_dir / "40_invocation_b.json").read_text(encoding="utf-8"))
    result_a = agent_store.load_result(project_id, run_id, invocation_a["agent_result_a_id"])
    result_b = agent_store.load_result(project_id, run_id, invocation_b["agent_result_b_id"])
    return result_a, result_b


def test_phase_result_lookup_ignores_uuid_filename_order(tmp_path):
    from types import SimpleNamespace

    run_dir = tmp_path / "runs" / "RUN"
    roundtrip_dir = run_dir / "agents" / "roundtrips" / "RTR"
    roundtrip_dir.mkdir(parents=True)
    (roundtrip_dir / "10_invocation_a.json").write_text(json.dumps({"agent_result_a_id": "AGENTRES-z-result-a"}), encoding="utf-8")
    (roundtrip_dir / "40_invocation_b.json").write_text(json.dumps({"agent_result_b_id": "AGENTRES-a-result-b"}), encoding="utf-8")

    class Store:
        def load_result(self, project_id, run_id, result_id):
            return SimpleNamespace(result_id=result_id)

    result_a, result_b = _load_phase_results(run_dir, Store(), "PRJ", "RUN")
    assert result_a.result_id == "AGENTRES-z-result-a"
    assert result_b.result_id == "AGENTRES-a-result-b"


@pytest.mark.skipif(os.getenv("MECHCAD_OPENCODE_LIVE") != "1", reason="OpenCode live validation is opt-in")
def test_real_transmission_tool_roundtrip_live(tmp_path):
    from mechcad_harness.agents import AgentIdentity, AgentRegistry, ContextBuilder
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig, OpenCodeAgentAdapter, OpenCodeModelSelection, OpenCodeResponseMode, resolve_opencode_config_from_environment
    from mechcad_harness.agents.persistence import AgentStore
    from mechcad_harness.agents.roundtrip import TransmissionToolRoundTripCoordinator
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore, EvidenceFreshness
    from mechcad_harness.models import Component, DesignState, Requirement
    from mechcad_harness.runs import RunController, TaskDefinition
    from mechcad_harness.state import StateManager
    from mechcad_harness.tools import BuiltinTools, ToolBroker, ToolRegistry
    from mechcad_harness.tools.persistence import ToolStore

    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-TRANSMISSION-ROUNDTRIP-LIVE", DesignState(id="DES-TRANSMISSION-ROUNDTRIP-LIVE", revision=1, components=[Component(id="P-LIVE", name="Transmission Part")], requirements=[
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
    run = controller.create_run("PRJ-TRANSMISSION-ROUNDTRIP-LIVE")
    task = TaskDefinition(task_id="TASK-TRANSMISSION-ROUNDTRIP-LIVE", run_id=run.run_id, task_type="agent", objective="Use the supplied authoritative torque inputs to request one deterministic transmission torque calculation, then reason from the selected current torque Evidence. Return useful findings, zero change proposals, and no unsupported arithmetic.", bound_revision=1, bound_state_hash=snapshot.state_hash, allowed_tools=("mechcad-calc-torque@1.0",))
    controller.add_task(run.run_id, task)

    _, password = resolve_opencode_config_from_environment(provider_id="screenpipe", model_id="gpt-5.6-luna", agent_name="mechcad-transmission")
    config = OpenCodeAdapterConfig(base_url="http://127.0.0.1:4096", project_directory="E:/repo/mechcad-harness", provider_id="screenpipe", model_id="gpt-5.6-luna", agent_name="mechcad-transmission", model_selection=OpenCodeModelSelection.EXPLICIT, response_mode=OpenCodeResponseMode.VALIDATED_JSON_TEXT)
    adapter = OpenCodeAgentAdapter(config, password)
    health = adapter.health()
    assert health.healthy, health.message
    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    registry = AgentRegistry()
    registry.register(identity, adapter)
    gateway = AgentGateway(controller, registry, ContextBuilder(controller), tool_broker=ToolBroker(controller, ToolRegistry(BuiltinTools.registrations())))

    before = manager._read_current("PRJ-TRANSMISSION-ROUNDTRIP-LIVE")
    result = TransmissionToolRoundTripCoordinator(controller, gateway, registry).run(run.run_id, task.task_id, identity.agent_name, identity.agent_version, selected_requirement_ids=("REQ-TORQUE-FORCE", "REQ-TORQUE-ARM", "REQ-TORQUE-SAFETY"))
    assert result.status == "complete", result.failure_kind

    run_dir = controller.store.run_dir("PRJ-TRANSMISSION-ROUNDTRIP-LIVE", run.run_id)
    agent_store = AgentStore(tmp_path)
    invocation_paths = sorted((run_dir / "agents" / "invocations").glob("*.json"))
    observation_paths = sorted((run_dir / "agents" / "tool_request_observations").glob("*.json"))
    assert len(invocation_paths) == len(observation_paths) == 2
    result_a, result_b = _load_phase_results(run_dir, agent_store, "PRJ-TRANSMISSION-ROUNDTRIP-LIVE", run.run_id)
    assert result_a.status.value == "succeeded"
    assert result_b.status.value == "succeeded"
    assert result_a.invocation_id != result_b.invocation_id
    observation_a = agent_store.load_tool_request_observation("PRJ-TRANSMISSION-ROUNDTRIP-LIVE", run.run_id, result_a.invocation_id)
    observation_b = agent_store.load_tool_request_observation("PRJ-TRANSMISSION-ROUNDTRIP-LIVE", run.run_id, result_b.invocation_id)
    assert observation_a.mediation_mode == "enabled"
    assert len(observation_a.tool_requests) == 1
    assert observation_a.tool_requests[0].capability == "transmission.torque"
    assert observation_a.tool_requests[0].arguments == {"force_n": 10, "lever_arm_m": 0.2, "safety_factor": 2.0}
    assert observation_b.mediation_mode == "disabled"
    assert observation_b.tool_requests == ()
    assert result_a.response.change_proposals == ()
    assert result_b.response.change_proposals == ()
    assert result_a.adapter_provenance.session_id != result_b.adapter_provenance.session_id
    assert result_a.adapter_provenance.provider == result_b.adapter_provenance.provider == "screenpipe"
    assert result_a.adapter_provenance.model == result_b.adapter_provenance.model == "gpt-5.6-luna"

    tool_store = ToolStore(tmp_path)
    call_paths = sorted((run_dir / "tool_calls").glob("*.json"))
    tool_result_paths = sorted((run_dir / "tool_results").glob("*.json"))
    mediation_paths = sorted((run_dir / "agents" / "tool_mediation").glob("*/final.json"))
    assert len(call_paths) == len(tool_result_paths) == len(mediation_paths) == 1
    tool_result = tool_store.load_result("PRJ-TRANSMISSION-ROUNDTRIP-LIVE", run.run_id, tool_result_paths[0].stem)
    assert tool_result.status.value == "succeeded"
    assert (tool_result.tool_name, tool_result.tool_version) == ("mechcad-calc-torque", "1.0")
    assert tool_result.output == {"nominal_torque_nm": 2.0, "design_torque_nm": 4.0}
    assert tool_result.backend_provenance is None
    evidence_paths = sorted(Path(tmp_path / "projects" / "PRJ-TRANSMISSION-ROUNDTRIP-LIVE" / "evidence").glob("*.json"))
    assert len(evidence_paths) == 1
    evidence = evidence_store.load_evidence("PRJ-TRANSMISSION-ROUNDTRIP-LIVE", evidence_paths[0].stem)
    assert evidence.id == result.evidence_id
    assert evidence.kind == "analysis.transmission.torque"
    assert evidence.summary == "Required design torque: 4 N*m"
    assert evidence.backend_provenance is None
    assert evidence_store.get_evidence_freshness("PRJ-TRANSMISSION-ROUNDTRIP-LIVE", evidence.id) is EvidenceFreshness.CURRENT

    transitions = sorted((run_dir / "agents" / "roundtrips").glob("*/*.json"))
    assert len(transitions) == 5
    assert transitions[-1].name == "50_complete.json"
    assert manager._read_current("PRJ-TRANSMISSION-ROUNDTRIP-LIVE") == before
    assert not list((run_dir / "tool_calls").glob("*.json"))[1:]
