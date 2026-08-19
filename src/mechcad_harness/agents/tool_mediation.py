import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import Field

from mechcad_harness.models.common import Model
from mechcad_harness.state.hashing import canonical_json
from mechcad_harness.tools.errors import ToolExecutionError, ToolPermissionError, ToolVersionError

from .models import AgentIdentity, AgentInvocationRequest, AgentToolRequestDraft


class ToolMediationError(Exception):
    def __init__(self, failure_kind: str, message: str | None = None):
        self.failure_kind = failure_kind
        super().__init__(message or failure_kind)


class AgentToolMediationMode(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class MediationStatus(str):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ToolMediationRecord(Model):
    mediation_id: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    agent_name: str = Field(min_length=1)
    agent_version: str = Field(min_length=1)
    ordinal: int = Field(ge=0)
    capability: str = Field(min_length=1)
    arguments: dict[str, Any]
    arguments_hash: str = Field(min_length=1)
    bound_revision: int = Field(gt=0)
    bound_state_hash: str = Field(min_length=1)
    status: str = Field(min_length=1)
    resolved_tool_name: str | None = None
    resolved_tool_version: str | None = None
    tool_call_id: str | None = None
    tool_result_id: str | None = None
    failure_kind: str | None = None


def arguments_hash(arguments: dict[str, Any]) -> str:
    return f"sha256:{hashlib.sha256(canonical_json(arguments)).hexdigest()}"


def mediation_id(invocation_id: str, ordinal: int, capability: str, argument_digest: str) -> str:
    payload = f"{invocation_id}\n{ordinal}\n{capability}\n{argument_digest}".encode()
    return f"MED-{hashlib.sha256(payload).hexdigest()}"


class CapabilityPolicy:
    _mapping = {
        ("mechcad-transmission", "1.0", "transmission.torque"): ("mechcad-calc-torque", "1.0"),
    }

    def resolve(self, identity: AgentIdentity, capability: str) -> tuple[str, str]:
        if not any(item[2] == capability for item in self._mapping):
            raise ToolMediationError("UNKNOWN_TOOL_CAPABILITY")
        try:
            return self._mapping[(identity.agent_name, identity.agent_version, capability)]
        except KeyError as exc:
            raise ToolMediationError("TOOL_CAPABILITY_NOT_AUTHORIZED") from exc


class AgentToolMediator:
    def __init__(self, controller, broker, *, policy: CapabilityPolicy | None = None):
        self.controller = controller
        self.broker = broker
        self.policy = policy or CapabilityPolicy()

    def mediate(self, invocation: AgentInvocationRequest, identity: AgentIdentity, requests: tuple[AgentToolRequestDraft, ...], *, source_result_id: str | None = None) -> ToolMediationRecord:
        seen = set()
        for request in requests:
            arguments = request.arguments.model_dump(mode="json")
            digest = arguments_hash(arguments)
            key = (invocation.invocation_id, request.capability, digest)
            if key in seen:
                raise ToolMediationError("DUPLICATE_TOOL_REQUEST")
            seen.add(key)
        if len(requests) > 1:
            raise ToolMediationError("TOO_MANY_TOOL_REQUESTS")
        if not requests:
            raise ValueError("no tool request to mediate")
        request = requests[0]
        arguments = request.arguments.model_dump(mode="json")
        digest = arguments_hash(arguments)
        mediation = ToolMediationRecord(mediation_id=mediation_id(invocation.invocation_id, 0, request.capability, digest), invocation_id=invocation.invocation_id, agent_name=identity.agent_name, agent_version=identity.agent_version, ordinal=0, capability=request.capability, arguments=arguments, arguments_hash=digest, bound_revision=invocation.bound_revision, bound_state_hash=invocation.bound_state_hash, status=MediationStatus.PENDING)
        self._write_pending(invocation, mediation)
        try:
            tool_name, tool_version = self.policy.resolve(identity, request.capability)
            mediation = mediation.model_copy(update={"resolved_tool_name": tool_name, "resolved_tool_version": tool_version})
            self._check_binding(invocation)
            permission = f"{tool_name}@{tool_version}"
            definition = self.controller.store.load_task_definition(invocation.project_id, invocation.run_id, invocation.task_id)
            if permission not in definition.allowed_tools:
                raise ToolMediationError("TASK_TOOL_NOT_AUTHORIZED")
        except ToolMediationError as exc:
            final = mediation.model_copy(update={"status": MediationStatus.FAILED, "failure_kind": exc.failure_kind})
            self._write_final(invocation, final)
            raise
        except ToolVersionError as exc:
            final = mediation.model_copy(update={"status": MediationStatus.FAILED, "failure_kind": "UNAVAILABLE_TRUSTED_TOOL"})
            self._write_final(invocation, final)
            raise ToolMediationError("UNAVAILABLE_TRUSTED_TOOL") from exc
        try:
            result = self.broker.execute(invocation.run_id, invocation.task_id, tool_name, tool_version, arguments, evidence_node=None)
            final = mediation.model_copy(update={"status": MediationStatus.SUCCEEDED, "tool_call_id": result.call_id, "tool_result_id": result.result_id})
            if not self._binding_current(invocation):
                final = final.model_copy(update={"status": MediationStatus.FAILED, "failure_kind": "STALE_TOOL_REQUEST_BINDING"})
        except (ToolExecutionError, ToolPermissionError, ToolVersionError) as exc:
            final = mediation.model_copy(update={"status": MediationStatus.FAILED, "failure_kind": type(exc).__name__})
        self._write_final(invocation, final)
        return final

    def _binding_current(self, invocation: AgentInvocationRequest) -> bool:
        run = self.controller.get_run(invocation.run_id)
        definition = self.controller.store.load_task_definition(invocation.project_id, invocation.run_id, invocation.task_id)
        return run.active_revision == invocation.bound_revision and run.active_state_hash == invocation.bound_state_hash and definition.bound_revision == invocation.bound_revision and definition.bound_state_hash == invocation.bound_state_hash

    def _check_binding(self, invocation: AgentInvocationRequest) -> None:
        if not self._binding_current(invocation):
            raise ToolMediationError("STALE_TOOL_REQUEST_BINDING")

    def _write_pending(self, invocation, record):
        from .persistence import AgentStore
        AgentStore(self.controller.workspace).write_mediation_pending(invocation.project_id, invocation.run_id, record)

    def _write_final(self, invocation, record):
        from .persistence import AgentStore
        AgentStore(self.controller.workspace).write_mediation_final(invocation.project_id, invocation.run_id, record)
