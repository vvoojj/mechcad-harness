import os
from typing import Any

import pytest

pytestmark = pytest.mark.skipif(os.getenv("MECHCAD_OPENCODE_LIVE") != "1", reason="OpenCode live validation is opt-in")


def _agent_result_diagnostic(result) -> dict[str, Any]:
    provenance = result.adapter_provenance
    response = result.response
    return {
        "status": result.status.value,
        "error": result.error,
        "adapter_name": provenance.adapter_name,
        "adapter_version": provenance.adapter_version,
        "server_version": provenance.server_version,
        "configured_agent_name": provenance.configured_agent_name,
        "provider": provenance.provider,
        "model": provenance.model,
        "session_id": provenance.session_id,
        "message_id": provenance.message_id,
        "request_hash": provenance.request_hash,
        "response_hash": result.response_hash,
        "validation_diagnostics": provenance.validation_diagnostics,
        "response_present": response is not None,
        "response_counts": None if response is None else {
            "findings": len(response.findings),
            "change_proposals": len(response.change_proposals),
            "issues": len(response.issues),
            "constraint_requests": len(response.constraint_requests),
        },
    }


def _preflight(adapter, expected_project_directory: str) -> dict[str, Any]:
    health = adapter.health()
    diagnostic = {
        "healthy": health.healthy,
        "server_version": health.server_version,
        "project_directory": adapter.config.project_directory,
        "configured_agent": adapter.config.agent_name,
        "provider": adapter.config.provider_id,
        "model": adapter.config.model_id,
    }
    assert health.healthy, {"layer": "PREFLIGHT_FAILURE", **diagnostic, "message": health.message}
    assert adapter.config.project_directory == expected_project_directory, {"layer": "PREFLIGHT_FAILURE", **diagnostic}
    agents = adapter.transport.request("GET", "/agent")
    names = [item.get("name") for item in agents if isinstance(item, dict)] if isinstance(agents, list) else []
    diagnostic["agent_names"] = names
    assert adapter.config.agent_name in names, {"layer": "OPENCODE_AGENT_NOT_FOUND", **diagnostic}
    return diagnostic


def test_real_transmission_agent_reasoning_round_trip(tmp_path):
    from mechcad_harness.agents import AgentIdentity, AgentRegistry, ContextBuilder
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig, OpenCodeAgentAdapter, OpenCodeModelSelection, OpenCodeResponseMode, resolve_opencode_config_from_environment
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore
    from mechcad_harness.models import Component, Constraint, DesignState, Requirement
    from mechcad_harness.runs import RunController, TaskDefinition
    from mechcad_harness.state import StateManager

    manager = StateManager(tmp_path)
    snapshot = manager.create_project(
        "PRJ-TRANSMISSION-LIVE",
        DesignState(
            id="DES-TRANSMISSION-LIVE",
            revision=1,
            components=[Component(id="P-LIVE", name="Transmission Part")],
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
    controller = RunController(tmp_path, manager, ChangeEngine(manager, OwnershipPolicy.from_file("config/ownership.yaml")), evidence)
    run = controller.create_run("PRJ-TRANSMISSION-LIVE")
    task = TaskDefinition(
        task_id="TASK-TRANSMISSION-LIVE",
        run_id=run.run_id,
        task_type="agent",
        objective=(
            "Perform preliminary transmission reasoning from the supplied context. "
            "Return one useful plain-string finding, identify the missing allowable backlash "
            "or holding/backdrive input with one ConstraintRequest, and return zero "
            "change proposals. Do not invent deterministic numbers or use tools."
        ),
        bound_revision=1,
        bound_state_hash=snapshot.state_hash,
    )
    controller.add_task(run.run_id, task)
    _, password = resolve_opencode_config_from_environment(provider_id="screenpipe", model_id="gpt-5.6-luna", agent_name="mechcad-transmission")
    config = OpenCodeAdapterConfig(
        project_directory=os.getenv("MECHCAD_OPENCODE_PROJECT_DIRECTORY", "E:/repo/mechcad-harness"),
        provider_id="screenpipe",
        model_id="gpt-5.6-luna",
        agent_name="mechcad-transmission",
        model_selection=OpenCodeModelSelection.EXPLICIT,
        response_mode=OpenCodeResponseMode.VALIDATED_JSON_TEXT,
    )
    assert config.response_mode == OpenCodeResponseMode.VALIDATED_JSON_TEXT
    adapter = OpenCodeAgentAdapter(config, password)
    _preflight(adapter, "E:/repo/mechcad-harness")
    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    registry = AgentRegistry()
    registry.register(identity, adapter)
    before_hash = snapshot.state_hash
    result = AgentGateway(controller, registry, ContextBuilder(controller)).invoke(
        run.run_id,
        task.task_id,
        identity.agent_name,
        identity.agent_version,
        selected_requirement_ids=("REQ-SPEED", "REQ-TORQUE"),
        selected_constraint_ids=("CONSTRAINT-ENVELOPE",),
    )
    assert result.status.value == "succeeded", {"layer": "ADAPTER_TRANSPORT_FAILURE" if result.adapter_provenance.session_id is None else "STRUCTURED_OUTPUT_VALIDATION_FAILURE", **_agent_result_diagnostic(result)}
    assert result.response is not None
    assert result.response.findings
    assert all(isinstance(item, str) for item in result.response.findings)
    assert result.response.change_proposals == ()
    assert result.response.issues or result.response.constraint_requests
    assert result.adapter_provenance.provider == "screenpipe"
    assert result.adapter_provenance.model == "gpt-5.6-luna"
    assert result.adapter_provenance.server_version
    assert result.adapter_provenance.session_id
    assert result.adapter_provenance.message_id
    assert result.adapter_provenance.request_hash
    assert result.response_hash.startswith("sha256:")
    assert manager._read_current("PRJ-TRANSMISSION-LIVE")["state_hash"] == before_hash
    assert not list((tmp_path / "projects" / "PRJ-TRANSMISSION-LIVE" / "evidence").glob("*.json"))
    assert not list((tmp_path / "projects" / "PRJ-TRANSMISSION-LIVE" / "runs" / run.run_id / "tool_calls").glob("*.json"))


def test_m6b1_validated_text_agentgateway_acceptance(tmp_path):
    from mechcad_harness.agents import AgentIdentity, AgentRegistry, ContextBuilder
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig, OpenCodeAgentAdapter, OpenCodeModelSelection, OpenCodeResponseMode, resolve_opencode_config_from_environment
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore
    from mechcad_harness.models import Component, Constraint, DesignState, Requirement
    from mechcad_harness.runs import RunController, TaskDefinition
    from mechcad_harness.state import StateManager

    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-M6B1-GATEWAY", DesignState(id="DES-M6B1-GATEWAY", revision=1, components=[Component(id="P-GATEWAY", name="Transmission Part")], requirements=[Requirement(id="REQ-SPEED", name="Output speed", description="Output speed is 120 rpm.")], constraints=[Constraint(id="CONSTRAINT-ENVELOPE", name="Envelope", expression="Transmission envelope is 80 mm by 80 mm.")]))
    graph_path = tmp_path / "dependencies.json"
    graph_path.write_text('{"rules": [], "edges": []}', encoding="utf-8")
    evidence = EvidenceStore(tmp_path, manager, DependencyGraph.from_yaml(graph_path))
    controller = RunController(tmp_path, manager, ChangeEngine(manager, OwnershipPolicy.from_file("config/ownership.yaml")), evidence)
    run = controller.create_run("PRJ-M6B1-GATEWAY")
    task = TaskDefinition(task_id="TASK-M6B1-GATEWAY", run_id=run.run_id, task_type="agent", objective="Perform preliminary transmission reasoning. Return one plain-string finding, identify the missing allowable backlash or holding/backdrive input with one plain-string constraint request, and return zero change proposals. Do not use tools.", bound_revision=1, bound_state_hash=snapshot.state_hash)
    controller.add_task(run.run_id, task)
    _, password = resolve_opencode_config_from_environment(provider_id="screenpipe", model_id="gpt-5.6-luna", agent_name="mechcad-transmission")
    config = OpenCodeAdapterConfig(project_directory="E:/repo/mechcad-harness", provider_id="screenpipe", model_id="gpt-5.6-luna", agent_name="mechcad-transmission", model_selection=OpenCodeModelSelection.EXPLICIT, response_mode=OpenCodeResponseMode.VALIDATED_JSON_TEXT)
    assert config.response_mode == OpenCodeResponseMode.VALIDATED_JSON_TEXT
    adapter = OpenCodeAgentAdapter(config, password)
    _preflight(adapter, "E:/repo/mechcad-harness")
    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    registry = AgentRegistry()
    registry.register(identity, adapter)
    before_hash = snapshot.state_hash
    result = AgentGateway(controller, registry, ContextBuilder(controller)).invoke(run.run_id, task.task_id, identity.agent_name, identity.agent_version, selected_requirement_ids=("REQ-SPEED",), selected_constraint_ids=("CONSTRAINT-ENVELOPE",))

    assert result.status.value == "succeeded", _agent_result_diagnostic(result)
    assert result.response is not None
    assert result.response.findings and all(isinstance(item, str) for item in result.response.findings)
    assert result.response.change_proposals == ()
    assert result.response.issues or result.response.constraint_requests
    assert result.adapter_provenance.provider == "screenpipe"
    assert result.adapter_provenance.model == "gpt-5.6-luna"
    assert result.adapter_provenance.response_mode == OpenCodeResponseMode.VALIDATED_JSON_TEXT
    assert result.adapter_provenance.schema_hash
    assert result.adapter_provenance.session_id and result.adapter_provenance.message_id and result.adapter_provenance.request_hash
    assert result.response_hash.startswith("sha256:")
    assert result.response_hash != result.adapter_provenance.schema_hash
    assert manager._read_current("PRJ-M6B1-GATEWAY")["state_hash"] == before_hash
    assert not list((tmp_path / "projects" / "PRJ-M6B1-GATEWAY" / "evidence").glob("*.json"))
    assert not list((tmp_path / "projects" / "PRJ-M6B1-GATEWAY" / "runs" / run.run_id / "tool_calls").glob("*.json"))
    assert result.response.issues or result.response.constraint_requests
    if result.response.constraint_requests:
        request = result.response.constraint_requests[0]
        assert request.id.startswith("CR-")
        assert request.revision == task.bound_revision
        assert request.state_hash == task.bound_state_hash
        assert request.description
