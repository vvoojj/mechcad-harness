import os

import pytest

pytestmark = pytest.mark.skipif(os.getenv("MECHCAD_OPENCODE_LIVE") != "1", reason="OpenCode live validation is opt-in")


def test_real_agentgateway_opencode_round_trip(tmp_path):
    from mechcad_harness.agents import AgentIdentity, AgentRegistry, ContextBuilder
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig, OpenCodeAgentAdapter, OpenCodeModelSelection, resolve_opencode_config_from_environment
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore
    from mechcad_harness.models import Component, DesignState
    from mechcad_harness.runs import RunController, TaskDefinition
    from mechcad_harness.state import StateManager

    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-LIVE", DesignState(id="DES-LIVE", revision=1, components=[Component(id="P-LIVE", name="Part")]))
    graph_path = tmp_path / "dependencies.json"
    graph_path.write_text("rules: []\nedges: []\n", encoding="utf-8")
    evidence = EvidenceStore(tmp_path, manager, DependencyGraph.from_yaml(graph_path))
    controller = RunController(tmp_path, manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/components/*", "owner": "actor"}])), evidence)
    run = controller.create_run("PRJ-LIVE")
    task = TaskDefinition(task_id="TASK-LIVE", run_id=run.run_id, task_type="agent", objective="Return status succeeded, summary Real OpenCode AgentGateway round trip succeeded., one concise informational finding as a plain string, and empty change_proposals, issues, and constraint_requests. This is protocol validation, not engineering reasoning quality.", bound_revision=1, bound_state_hash=snapshot.state_hash)
    controller.add_task(run.run_id, task)
    _, password = resolve_opencode_config_from_environment(provider_id="screenpipe", model_id="gpt-5.6-luna", agent_name="mechcad-test-agent")
    config = OpenCodeAdapterConfig(project_directory=os.getenv("MECHCAD_OPENCODE_PROJECT_DIRECTORY", "E:/repo/mechcad-harness"), provider_id="screenpipe", model_id="gpt-5.6-luna", agent_name="mechcad-test-agent", model_selection=OpenCodeModelSelection.EXPLICIT)
    adapter = OpenCodeAgentAdapter(config, password)
    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    registry = AgentRegistry()
    registry.register(identity, adapter)
    result = AgentGateway(controller, registry, ContextBuilder(controller)).invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version)
    assert result.status.value == "succeeded"
    assert result.response is not None
    assert result.response.status.value == "succeeded"
    assert len(result.response.findings) >= 1
    assert all(isinstance(finding, str) for finding in result.response.findings)
    assert result.adapter_provenance.provider == "screenpipe"
    assert result.adapter_provenance.model == "gpt-5.6-luna"
    assert not result.response.change_proposals
    assert not result.response.issues
    assert not result.response.constraint_requests
    assert result.adapter_provenance.server_version == "1.18.18"
    assert result.adapter_provenance.session_id.startswith("ses")
    assert result.adapter_provenance.message_id.startswith("msg")
    assert result.adapter_provenance.request_hash.startswith("sha256:")
    assert result.error is None
    assert manager._read_snapshot("PRJ-LIVE", 1).state_hash == snapshot.state_hash
    assert result.response is not None
