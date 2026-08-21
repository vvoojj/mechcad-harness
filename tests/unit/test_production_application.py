from pathlib import Path
import inspect

import pytest

from mechcad_harness.agents.models import (
    AgentAdapterExecutionOutcome,
    AgentAdapterIdentity,
    AgentAdapterProvenance,
    AgentAuthoredResponsePayload,
)
from mechcad_harness.agents import AgentIdentity
from mechcad_harness.models import Component, DesignState
from mechcad_harness.state import StateManager, state_hash
from mechcad_harness.state.errors import RevisionNotFoundError, StateIntegrityError
from mechcad_harness.runs import RunController
from mechcad_harness.runs.models import SourceBinding, TaskDefinition
from mechcad_harness.tools import BuiltinTools, ToolVersionError
from mechcad_harness.tools.errors import ToolPermissionError


class CountingAdapter:
    def __init__(self, identity=None):
        self.identity = identity or AgentAdapterIdentity(adapter_name="forged-provider", adapter_version="9.9")
        self.invocation_count = 0
        self.requests = []

    def invoke(self, request):
        self.invocation_count += 1
        self.requests.append(request)
        return AgentAdapterExecutionOutcome(
            authored_response=AgentAuthoredResponsePayload(
                status="succeeded",
                summary="unused",
                findings=(),
                issues=(),
                constraint_requests=(),
                change_proposals=(),
            ),
            provenance=AgentAdapterProvenance(
                adapter_name="forged-provider",
                adapter_version="9.9",
                provider="test",
                transport="test",
            ),
        )


def make_state() -> DesignState:
    return DesignState(
        id="DES-production",
        revision=1,
        components=[Component(id="PRT-bracket", name="Bracket")],
    )


def build_application(tmp_path: Path, adapter: CountingAdapter):
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /components/*\n    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    dependencies.write_text("rules: []\nedges: []\n", encoding="utf-8")
    StateManager(workspace).create_project("PRJ-production", make_state())

    from mechcad_harness.application import ProductionApplication

    return ProductionApplication.create(
        workspace,
        "PRJ-production",
        adapter,
        ownership_path=ownership,
        dependency_path=dependencies,
    )


def test_production_application_constructs_real_graph_without_invoking_adapter(tmp_path):
    from mechcad_harness.agents import AgentRegistry
    from mechcad_harness.agents.gateway import AgentGateway
    from mechcad_harness.runs import RunController
    from mechcad_harness.tools import ToolBroker

    adapter = CountingAdapter()
    application = build_application(tmp_path, adapter)

    assert isinstance(application.state_manager, StateManager)
    assert isinstance(application.run_controller, RunController)
    assert isinstance(application.agent_registry, AgentRegistry)
    assert isinstance(application.agent_gateway, AgentGateway)
    assert isinstance(application.tool_broker, ToolBroker)
    assert adapter.invocation_count == 0


def test_load_state_returns_exact_fresh_binding(tmp_path):
    application = build_application(tmp_path, CountingAdapter())

    first = application.load_state()
    second = application.load_state()

    assert first is not second
    assert (first.revision, first.state_hash) == (1, state_hash(first.state))
    assert second == first


def test_create_run_binds_authoritative_loaded_snapshot(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    source = application.load_state()

    binding = application.create_run()

    assert binding.source == source
    assert binding.run.initial_revision == source.revision
    assert binding.run.initial_state_hash == source.state_hash
    assert binding.run.active_revision == source.revision
    assert binding.run.active_state_hash == source.state_hash


def test_create_and_create_run_never_execute_adapter(tmp_path):
    adapter = CountingAdapter()
    application = build_application(tmp_path, adapter)

    application.create_run()

    assert adapter.invocation_count == 0


def test_production_bindings_are_immutable_and_validate_source(tmp_path):
    from mechcad_harness.application import ProductionRunBinding, ProductionStateBinding

    application = build_application(tmp_path, CountingAdapter())
    source = application.load_state()

    with pytest.raises((TypeError, ValueError)):
        source.revision = 2

    with pytest.raises(ValueError):
        ProductionStateBinding(
            project_id=source.project_id,
            state=source.state,
            revision=2,
            state_hash=source.state_hash,
        )

    run = application.run_controller.create_run(source.project_id)
    with pytest.raises(ValueError):
        ProductionRunBinding(run=run, source=source.model_copy(update={"revision": 2}))


def test_production_run_binding_returns_a_safe_nested_run_snapshot(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    binding = application.create_run()
    binding.run.active_revision = 2

    assert binding.run.active_revision == 1
    assert application.run_controller.get_run(binding.run.run_id, binding.run.project_id).active_revision == 1


def test_application_composed_dependencies_cannot_be_reassigned(tmp_path):
    application = build_application(tmp_path, CountingAdapter())

    for name in (
        "state_manager",
        "run_controller",
        "agent_registry",
        "agent_gateway",
        "tool_registry",
        "tool_broker",
        "evidence_store",
        "change_engine",
        "context_builder",
        "standard_tool_permissions",
    ):
        with pytest.raises(AttributeError):
            setattr(application, name, getattr(application, name))

    with pytest.raises(AttributeError):
        application.project_id = "PRJ-other"


def test_production_application_rejects_invalid_adapter_at_composition(tmp_path):
    from mechcad_harness.application import ProductionApplication

    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /components/*\n    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    dependencies.write_text("rules: []\nedges: []\n", encoding="utf-8")

    with pytest.raises(ValueError):
        ProductionApplication.create(
            tmp_path / "workspace",
            "PRJ-production",
            object(),
            ownership_path=ownership,
            dependency_path=dependencies,
        )


def test_production_run_binding_keeps_source_and_run_snapshot_after_state_advances(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    binding = application.create_run()
    original_source = binding.source
    original_run = binding.run

    application.state_manager.create_revision(
        "PRJ-production", make_state().model_copy(update={"revision": 2})
    )

    assert binding.source == original_source
    assert binding.run == original_run
    assert binding.source.revision == 1
    assert binding.run.active_revision == 1


def test_production_state_binding_rejects_blank_project_and_hash(tmp_path):
    from mechcad_harness.application import ProductionStateBinding

    source = build_application(tmp_path, CountingAdapter()).load_state()
    for field, value in (("project_id", " "), ("state_hash", "\t")):
        values = {
            "project_id": source.project_id,
            "state": source.state,
            "revision": source.revision,
            "state_hash": source.state_hash,
        }
        values[field] = value
        with pytest.raises(ValueError):
            ProductionStateBinding(**values)


def test_production_state_binding_returns_a_safe_nested_state_snapshot(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    source = application.load_state()
    source.state.components[0].name = "mutated"

    later = application.load_state()

    assert later.state.components[0].name == "Bracket"
    assert later.state_hash == state_hash(later.state)


def test_application_exposes_composed_services_without_execution_api(tmp_path):
    from mechcad_harness.agents import ContextBuilder
    from mechcad_harness.changes import ChangeEngine
    from mechcad_harness.dependency import EvidenceStore

    application = build_application(tmp_path, CountingAdapter())

    assert isinstance(application.evidence_store, EvidenceStore)
    assert isinstance(application.change_engine, ChangeEngine)
    assert isinstance(application.context_builder, ContextBuilder)
    assert not set(dir(type(application))).intersection({
        "execute_task", "run_workflow", "invoke_agent", "start_run", "apply_change", "mutate_state",
    })


def test_application_fails_closed_if_state_advances_after_load(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    original_load = application.load_state

    def load_then_advance():
        source = original_load()
        application.state_manager.create_revision("PRJ-production", make_state().model_copy(update={"revision": 2}))
        return source

    application.load_state = load_then_advance

    from mechcad_harness.runs.errors import RunIntegrityError
    with pytest.raises(RunIntegrityError):
        application.create_run()


def test_application_passes_typed_expected_source_to_controller(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    source = application.load_state()
    calls = []
    original = application.run_controller.create_run

    def create_run(project_id, *, max_iterations=3, expected_source=None):
        calls.append(expected_source)
        return original(project_id, max_iterations=max_iterations, expected_source=expected_source)

    application.run_controller.create_run = create_run
    application.create_run()

    assert isinstance(calls[0], SourceBinding)
    assert calls[0] == SourceBinding(project_id=source.project_id, revision=source.revision, state_hash=source.state_hash)


def test_injected_adapter_cannot_override_production_identity_or_role(tmp_path):
    adapter = CountingAdapter(AgentAdapterIdentity(adapter_name="forged", adapter_version="9.9"))
    application = build_application(tmp_path, adapter)

    assert application.agent_registry.get_identity("mechcad-transmission", "1.0") == AgentIdentity(
        agent_name="mechcad-transmission",
        agent_version="1.0",
        role="transmission_engineer",
        protocol_version="1.0",
    )


def test_gateway_uses_registered_transmission_role_not_test_role(tmp_path):
    adapter = CountingAdapter()
    application = build_application(tmp_path, adapter)
    binding = application.create_run()
    task = TaskDefinition(
        task_id="TASK-role",
        run_id=binding.run.run_id,
        task_type="agent",
        objective="inspect",
        bound_revision=binding.run.active_revision,
        bound_state_hash=binding.run.active_state_hash,
    )
    application.run_controller.add_task(binding.run.run_id, task)

    result = application.agent_gateway.invoke(
        binding.run.run_id,
        task.task_id,
        "mechcad-transmission",
        "1.0",
    )
    identity = application.agent_registry.get_identity("mechcad-transmission", "1.0")

    assert identity.role == "transmission_engineer"
    assert identity.role != "test"
    assert adapter.requests[0].agent == identity
    assert (result.agent_name, result.agent_version) == (identity.agent_name, identity.agent_version)


def test_standard_tools_resolve_exact_versions_and_permissions_are_exact(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    registrations = BuiltinTools.registrations()

    assert application.standard_tool_permissions == tuple(
        f"{registration.name}@{registration.version}" for registration in registrations
    )
    for registration in registrations:
        resolved = application.tool_registry.resolve(registration.name, registration.version)
        assert (resolved.name, resolved.version) == (registration.name, registration.version)
        assert f"{registration.name}@{registration.version}" in application.standard_tool_permissions
        assert registration.name not in application.standard_tool_permissions


def test_real_tool_broker_rejects_bare_name_permission(tmp_path):
    application = build_application(tmp_path, CountingAdapter())
    run = application.run_controller.create_run(application.project_id)
    task = TaskDefinition(
        task_id="TASK-bare-permission",
        run_id=run.run_id,
        task_type="tool",
        objective="calculate",
        bound_revision=run.active_revision,
        bound_state_hash=run.active_state_hash,
        allowed_tools=("mechcad-calc-torque",),
    )
    application.run_controller.add_task(run.run_id, task)

    with pytest.raises(ToolPermissionError):
        application.tool_broker.execute(
            run.run_id,
            task.task_id,
            "mechcad-calc-torque",
            "1.0",
            {"force_n": 1, "lever_arm_m": 1, "safety_factor": 1},
        )


@pytest.mark.parametrize("bad_setup", ["missing_project", "missing_ownership", "missing_dependencies", "corrupt_current"])
def test_invalid_or_missing_state_and_configuration_fail_closed(tmp_path, bad_setup):
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text("ownership:\n  - path: /components/*\n    owner: transmission_engineer\n", encoding="utf-8")
    dependencies.write_text("rules: []\nedges: []\n", encoding="utf-8")

    if bad_setup == "missing_ownership":
        ownership.unlink()
    elif bad_setup == "missing_dependencies":
        dependencies.unlink()
    elif bad_setup != "missing_project":
        StateManager(workspace).create_project("PRJ-production", make_state())
        if bad_setup == "corrupt_current":
            (workspace / "projects" / "PRJ-production" / "current.json").write_text("not-json\n", encoding="utf-8")

    from mechcad_harness.application import ProductionApplication

    if bad_setup in {"missing_ownership", "missing_dependencies"}:
        with pytest.raises(ValueError):
            ProductionApplication.create(workspace, "PRJ-production", CountingAdapter(), ownership_path=ownership, dependency_path=dependencies)
    else:
        application = ProductionApplication.create(workspace, "PRJ-production", CountingAdapter(), ownership_path=ownership, dependency_path=dependencies)
        with pytest.raises(RevisionNotFoundError if bad_setup == "missing_project" else StateIntegrityError):
            application.load_state()


def test_conflicting_standard_registration_fails_closed(tmp_path):
    from mechcad_harness.application import ProductionApplication

    (tmp_path / "ownership.yaml").write_text(
        "ownership:\n  - path: /components/*\n    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    (tmp_path / "dependencies.yaml").write_text("rules: []\nedges: []\n", encoding="utf-8")
    standard = BuiltinTools.registrations()[0]
    with pytest.raises(ToolVersionError):
        ProductionApplication.create(
            tmp_path / "workspace",
            "PRJ-production",
            CountingAdapter(),
            ownership_path=tmp_path / "ownership.yaml",
            dependency_path=tmp_path / "dependencies.yaml",
            additional_tool_registrations=(standard,),
        )


def test_production_module_does_not_import_test_helpers():
    import mechcad_harness.application

    source = inspect.getsource(mechcad_harness.application)
    assert "tests." not in source
    assert "conftest" not in source
