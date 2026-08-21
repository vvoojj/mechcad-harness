import json
from pathlib import Path
from typing import Iterable

from pydantic import ConfigDict, Field, field_validator, model_validator

from mechcad_harness.agents import AgentAdapter, AgentIdentity, AgentRegistry, ContextBuilder
from mechcad_harness.agents.gateway import AgentGateway
from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
from mechcad_harness.dependency import DependencyGraph, EvidenceStore
from mechcad_harness.models import DesignState
from mechcad_harness.runs import Run, RunController, SourceBinding, TaskDefinition
from mechcad_harness.runs.errors import RunIntegrityError
from mechcad_harness.state import StateManager, state_hash
from mechcad_harness.state.errors import StateIntegrityError
from mechcad_harness.tools import BuiltinTools, ToolBroker, ToolRegistration, ToolRegistry
from mechcad_harness.models.common import Model
from mechcad_harness.agents.roundtrip import TransmissionToolRoundTripCoordinator, TransmissionToolRoundTripResult


class ProductionStateBinding(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: str = Field(min_length=1)
    state: DesignState
    revision: int = Field(gt=0)
    state_hash: str = Field(min_length=1)

    @field_validator("project_id", "state_hash")
    @classmethod
    def validate_strings(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value

    @model_validator(mode="after")
    def validate_state_revision(self):
        if self.state.revision != self.revision:
            raise ValueError("state revision does not match binding revision")
        return self

    def __getattribute__(self, name):
        value = super().__getattribute__(name)
        if name == "state" and isinstance(value, DesignState):
            return value.model_copy(deep=True)
        return value


class ProductionRunBinding(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run: Run
    source: ProductionStateBinding

    @model_validator(mode="after")
    def validate_run_source(self):
        checks = (
            self.run.project_id == self.source.project_id,
            self.run.initial_revision == self.source.revision,
            self.run.initial_state_hash == self.source.state_hash,
            self.run.active_revision == self.source.revision,
            self.run.active_state_hash == self.source.state_hash,
        )
        if not all(checks):
            raise ValueError("run binding does not match production state source")
        return self

    def __getattribute__(self, name):
        value = super().__getattribute__(name)
        if name in {"run", "source"} and isinstance(value, Model):
            return value.model_copy(deep=True)
        return value


class ProductionApplication:
    _READ_ONLY_DEPENDENCIES = frozenset({
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
        "project_id",
    })
    _IDENTITY = AgentIdentity(
        agent_name="mechcad-transmission",
        agent_version="1.0",
        role="transmission_engineer",
        protocol_version="1.0",
    )

    def __init__(
        self,
        *,
        project_id: str,
        state_manager: StateManager,
        run_controller: RunController,
        agent_registry: AgentRegistry,
        agent_gateway: AgentGateway,
        tool_registry: ToolRegistry,
        tool_broker: ToolBroker,
        evidence_store: EvidenceStore,
        change_engine: ChangeEngine,
        context_builder: ContextBuilder,
    ):
        object.__setattr__(self, "project_id", project_id)
        self.state_manager = state_manager
        self.run_controller = run_controller
        self.agent_registry = agent_registry
        self.agent_gateway = agent_gateway
        self.tool_registry = tool_registry
        self.tool_broker = tool_broker
        self.evidence_store = evidence_store
        self.change_engine = change_engine
        self.context_builder = context_builder
        self.standard_tool_permissions = tuple(
            f"{registration.name}@{registration.version}"
            for registration in BuiltinTools.registrations()
        )
        object.__setattr__(self, "_dependencies_initialized", True)

    def __setattr__(self, name, value):
        if name in self._READ_ONLY_DEPENDENCIES and getattr(self, "_dependencies_initialized", False):
            raise AttributeError(f"{name} is read-only")
        object.__setattr__(self, name, value)

    @classmethod
    def create(
        cls,
        workspace: str | Path,
        project_id: str,
        agent_adapter: AgentAdapter,
        *,
        ownership_path: str | Path,
        dependency_path: str | Path,
        additional_tool_registrations: Iterable[ToolRegistration] = (),
    ) -> "ProductionApplication":
        if not project_id.strip():
            raise ValueError("project_id must not be empty")
        if agent_adapter is None:
            raise ValueError("agent_adapter is required")
        if not callable(getattr(agent_adapter, "invoke", None)) or not hasattr(agent_adapter, "identity"):
            raise ValueError("agent_adapter does not satisfy the agent adapter protocol")
        ownership = Path(ownership_path)
        dependencies = Path(dependency_path)
        if not ownership.exists() or not dependencies.exists():
            raise ValueError("ownership and dependency configuration files are required")

        state_manager = StateManager(workspace)
        graph = DependencyGraph.from_yaml(dependencies)
        evidence_store = EvidenceStore(workspace, state_manager, graph)
        ownership_policy = OwnershipPolicy.from_file(ownership)
        change_engine = ChangeEngine(state_manager, ownership_policy)
        controller = RunController(workspace, state_manager, change_engine, evidence_store)

        standard = BuiltinTools.registrations()
        tool_registry = ToolRegistry([*standard, *tuple(additional_tool_registrations)])
        for registration in standard:
            tool_registry.resolve(registration.name, registration.version)
        tool_broker = ToolBroker(controller, tool_registry)

        agent_registry = AgentRegistry()
        agent_registry.register(cls._IDENTITY, agent_adapter)
        context_builder = ContextBuilder(controller)
        gateway = AgentGateway(controller, agent_registry, context_builder, tool_broker=tool_broker)
        return cls(
            project_id=project_id,
            state_manager=state_manager,
            run_controller=controller,
            agent_registry=agent_registry,
            agent_gateway=gateway,
            tool_registry=tool_registry,
            tool_broker=tool_broker,
            evidence_store=evidence_store,
            change_engine=change_engine,
            context_builder=context_builder,
        )

    def load_state(self) -> ProductionStateBinding:
        try:
            state = self.state_manager.load_current_state(self.project_id)
            current = self.state_manager._read_current(self.project_id)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise StateIntegrityError(f"invalid current state binding: {self.project_id}") from exc
        computed_hash = state_hash(state)
        if state.revision != current["revision"] or computed_hash != current["state_hash"]:
            raise StateIntegrityError(f"current state binding mismatch: {self.project_id}")
        return ProductionStateBinding(
            project_id=self.project_id,
            state=state,
            revision=state.revision,
            state_hash=computed_hash,
        )

    def create_run(self, *, max_iterations: int = 3) -> ProductionRunBinding:
        source = self.load_state()
        run = self.run_controller.create_run(
            self.project_id,
            max_iterations=max_iterations,
            expected_source=SourceBinding(
                project_id=source.project_id,
                revision=source.revision,
                state_hash=source.state_hash,
            ),
        )
        persisted = self.run_controller.get_run(run.run_id, self.project_id)
        if (
            persisted.project_id != source.project_id
            or persisted.initial_revision != source.revision
            or persisted.initial_state_hash != source.state_hash
            or persisted.active_revision != source.revision
            or persisted.active_state_hash != source.state_hash
        ):
            raise RunIntegrityError("persisted run binding does not match loaded source")
        return ProductionRunBinding(run=persisted, source=source)

    def run_transmission_round_trip(
        self,
        *,
        selected_requirement_ids: tuple[str, ...] = (),
        max_iterations: int = 3,
    ) -> TransmissionToolRoundTripResult:
        run_binding = self.create_run(max_iterations=max_iterations)
        source = run_binding.source
        run = run_binding.run
        if (
            run.project_id != source.project_id
            or run.active_revision != source.revision
            or run.active_state_hash != source.state_hash
        ):
            raise RunIntegrityError("production run source binding mismatch")

        task = TaskDefinition(
            task_id="TASK-transmission-roundtrip",
            run_id=run.run_id,
            task_type="agent",
            objective="Perform bounded transmission torque round trip.",
            bound_revision=source.revision,
            bound_state_hash=source.state_hash,
            allowed_tools=("mechcad-calc-torque@1.0",),
        )
        self.run_controller.add_task(run.run_id, task)

        coordinator = TransmissionToolRoundTripCoordinator(
            self.run_controller,
            self.agent_gateway,
            self.agent_registry,
        )
        return coordinator.run(
            run.run_id,
            task.task_id,
            self._IDENTITY.agent_name,
            self._IDENTITY.agent_version,
            selected_requirement_ids=tuple(selected_requirement_ids),
        )
