import pytest


def test_agent_registry_requires_exact_name_and_version():
    from mechcad_harness.agents.models import AgentAdapterIdentity, AgentIdentity, AgentResponsePayload
    from mechcad_harness.agents.registry import AgentRegistry

    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    adapter = type("Adapter", (), {"identity": AgentAdapterIdentity(adapter_name="fake", adapter_version="1.0"), "invoke": lambda self, request: AgentResponsePayload(summary="ok")})()
    registry = AgentRegistry()
    registry.register(identity, adapter)
    assert registry.get("mechcad-test-agent", "1.0") is adapter
    with pytest.raises(Exception):
        registry.get("mechcad-test-agent", "latest")
    with pytest.raises(Exception):
        registry.register(identity, adapter)


def test_fake_agent_returns_configured_finding():
    from mechcad_harness.agents.fake import FakeAgentAdapter
    from mechcad_harness.agents.models import AgentAdapterIdentity, AgentIdentity, AgentInvocationRequest, AgentContext
    from mechcad_harness.models import DesignState

    adapter = FakeAgentAdapter(AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0"), findings=("deterministic",))
    request = AgentInvocationRequest(invocation_id="INV-1", agent=adapter.agent_identity, project_id="PRJ-1", run_id="RUN-1", task_id="TASK-1", bound_revision=1, bound_state_hash="sha256:state", context=AgentContext(project_id="PRJ-1", run_id="RUN-1", task_id="TASK-1", revision=1, state_hash="sha256:state", design_state=DesignState(id="DES-1", revision=1), task_objective="test", task_instructions="test"), requested_output_schema_version="1.0", context_hash="sha256:context")
    assert adapter.invoke(request).authored_response.findings == ("deterministic",)


def test_context_builder_reads_persisted_revision(tmp_path):
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore
    from mechcad_harness.models import Component, DesignState
    from mechcad_harness.runs import RunController, TaskDefinition
    from mechcad_harness.state import StateManager
    from mechcad_harness.agents.context import ContextBuilder

    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-1", DesignState(id="DES-1", revision=1, components=[Component(id="P-1", name="Part")]))
    graph = tmp_path / "dependencies.json"
    graph.write_text("rules: []\nedges: []\n", encoding="utf-8")
    controller = RunController(tmp_path, manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/components/*", "owner": "actor"}])), EvidenceStore(tmp_path, manager, DependencyGraph.from_yaml(graph)))
    run = controller.create_run("PRJ-1")
    task = TaskDefinition(task_id="TASK-1", run_id=run.run_id, task_type="agent", objective="inspect", bound_revision=1, bound_state_hash=snapshot.state_hash)
    controller.add_task(run.run_id, task)
    context = ContextBuilder(controller).build(run.run_id, task.task_id)
    assert context.revision == 1
    assert context.state_hash == snapshot.state_hash
    assert context.design_state.components[0].name == "Part"
