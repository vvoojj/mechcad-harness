from datetime import datetime, timezone
from enum import StrEnum
import math
from typing import Any, Literal, NamedTuple, Protocol
import hashlib
import json

from pydantic import Field, field_validator

from mechcad_harness.models import ChangeProposal, ConstraintRequest, DesignState, Issue
from mechcad_harness.models.common import Model
from mechcad_harness.tools.models import TorqueInput
from .constraint_requests import AgentConstraintRequestDraft, SupportedConstraintKey


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def nonempty(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty")
    return value


class AgentIdentity(Model):
    agent_name: str = Field(min_length=1)
    agent_version: str = Field(min_length=1)
    role: str = Field(min_length=1)
    protocol_version: str = Field(min_length=1)

    @field_validator("agent_name", "agent_version", "role", "protocol_version")
    @classmethod
    def validate_strings(cls, value: str) -> str:
        return nonempty(value)


class AgentAdapterIdentity(Model):
    adapter_name: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)


class AgentAdapterProvenance(Model):
    adapter_name: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str | None = None
    model_version: str | None = None
    transport: str = Field(min_length=1)
    server_version: str | None = None
    configured_agent_name: str | None = None
    session_id: str | None = None
    message_id: str | None = None
    project_directory: str | None = None
    request_hash: str | None = None
    response_mode: str | None = None
    schema_hash: str | None = None
    validation_diagnostics: dict[str, Any] | None = None


class AgentEvidenceSummary(Model):
    evidence_id: str = Field(min_length=1)
    dependency_node: str = Field(min_length=1)
    bound_revision: int = Field(gt=0)
    bound_state_hash: str = Field(min_length=1)
    freshness: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    source_tool_name: str | None = None
    source_tool_version: str | None = None
    source_result_id: str | None = None


class AgentContext(Model):
    project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    revision: int = Field(gt=0)
    state_hash: str = Field(min_length=1)
    design_state: DesignState
    task_objective: str = Field(min_length=1)
    task_instructions: str = Field(min_length=1)
    requirements: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    evidence_summaries: tuple[AgentEvidenceSummary, ...] = ()


class AgentInvocationRequest(Model):
    invocation_id: str = Field(min_length=1)
    agent: AgentIdentity
    project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    bound_revision: int = Field(gt=0)
    bound_state_hash: str = Field(min_length=1)
    context: AgentContext
    requested_output_schema_version: str = Field(min_length=1)
    response_contract: "AgentAuthoredResponseContract" = "tool_requests_allowed"
    response_schema_hash: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    context_hash: str = Field(min_length=1)


class AgentResponseStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AgentResponsePayload(Model):
    status: AgentResponseStatus = AgentResponseStatus.SUCCEEDED
    summary: str = ""
    findings: tuple[str, ...] = ()
    change_proposals: tuple[ChangeProposal, ...] = ()
    issues: tuple[Issue, ...] = ()
    constraint_requests: tuple[ConstraintRequest, ...] = ()


class AgentChangeProposalDraft(Model):
    title: str = Field(min_length=1)
    operations: tuple["ChangeOperation", ...] = ()


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("arguments must contain finite numbers")
        return value
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("argument object keys must be strings")
        return {key: _json_safe(item) for key, item in value.items()}
    raise ValueError("arguments must contain only JSON-safe values")


class TransmissionTorqueToolRequestDraft(Model):
    capability: Literal["transmission.torque"]
    arguments: TorqueInput


AgentToolRequestDraft = TransmissionTorqueToolRequestDraft


class AgentToolRequestObservationRecord(Model):
    observation_id: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    agent_name: str = Field(min_length=1)
    agent_version: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    bound_revision: int = Field(gt=0)
    bound_state_hash: str = Field(min_length=1)
    mediation_mode: str = Field(min_length=1)
    tool_requests: tuple[AgentToolRequestDraft, ...] = ()
    tool_requests_hash: str = Field(min_length=1)


class AgentConstraintRequestObservationRecord(Model):
    observation_id: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    agent_name: str = Field(min_length=1)
    agent_version: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    bound_revision: int = Field(gt=0)
    bound_state_hash: str = Field(min_length=1)
    response_contract: str = Field(min_length=1)
    constraint_requests: tuple[AgentConstraintRequestDraft, ...] = ()
    constraint_requests_hash: str = Field(min_length=1)


class AgentAuthoredResponsePayload(Model):
    status: AgentResponseStatus
    summary: str
    findings: tuple[str, ...]
    issues: tuple[str, ...]
    constraint_requests: tuple[str, ...]
    change_proposals: tuple[AgentChangeProposalDraft, ...]
    tool_requests: tuple[AgentToolRequestDraft, ...] = ()


class AgentAuthoredResponseContract(StrEnum):
    TOOL_REQUESTS_ALLOWED = "tool_requests_allowed"
    TOOL_REQUESTS_FORBIDDEN = "tool_requests_forbidden"
    CONSTRAINT_DISCOVERY_TOOLS_FORBIDDEN = "constraint_discovery_tools_forbidden"


class AgentAuthoredNoToolResponsePayload(AgentAuthoredResponsePayload):
    tool_requests: tuple[()] = ()


class AgentConstraintDiscoveryResponsePayload(AgentAuthoredResponsePayload):
    tool_requests: tuple[()] = ()
    constraint_requests: tuple[AgentConstraintRequestDraft, ...] = ()


class ResponseContractMaterialization(NamedTuple):
    contract: AgentAuthoredResponseContract
    response_model: type[AgentAuthoredResponsePayload]
    schema: dict[str, Any]
    schema_json: str
    schema_hash: str


def response_model_for_contract(contract: AgentAuthoredResponseContract):
    contract = AgentAuthoredResponseContract(contract)
    if contract is AgentAuthoredResponseContract.TOOL_REQUESTS_ALLOWED:
        return AgentAuthoredResponsePayload
    if contract is AgentAuthoredResponseContract.TOOL_REQUESTS_FORBIDDEN:
        return AgentAuthoredNoToolResponsePayload
    if contract is AgentAuthoredResponseContract.CONSTRAINT_DISCOVERY_TOOLS_FORBIDDEN:
        return AgentConstraintDiscoveryResponsePayload
    raise ValueError(f"unsupported authored response contract: {contract}")


def materialize_response_contract(contract: AgentAuthoredResponseContract) -> ResponseContractMaterialization:
    contract = AgentAuthoredResponseContract(contract)
    response_model = response_model_for_contract(contract)
    schema = response_model.model_json_schema()
    schema_json = json.dumps(schema, sort_keys=True, separators=(",", ":"))
    schema_hash = f"sha256:{hashlib.sha256(schema_json.encode()).hexdigest()}"
    return ResponseContractMaterialization(contract, response_model, schema, schema_json, schema_hash)


from mechcad_harness.changes.operations import ChangeOperation

AgentChangeProposalDraft.model_rebuild(_types_namespace={"ChangeOperation": ChangeOperation})
AgentInvocationRequest.model_rebuild(_types_namespace={"AgentAuthoredResponseContract": AgentAuthoredResponseContract})


class AgentResultStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STALE = "stale"


class AgentInvocationRecord(Model):
    request: AgentInvocationRequest
    request_hash: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)


class AgentResult(Model):
    result_id: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    agent_name: str = Field(min_length=1)
    agent_version: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    bound_revision: int = Field(gt=0)
    bound_state_hash: str = Field(min_length=1)
    status: AgentResultStatus
    response_hash: str = Field(min_length=1)
    response: AgentResponsePayload | None = None
    adapter_provenance: AgentAdapterProvenance
    error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class AgentAdapterExecutionOutcome(Model):
    authored_response: AgentAuthoredResponsePayload
    provenance: AgentAdapterProvenance
    execution_metadata: dict[str, Any] | None = None


class AgentAdapterExecutionError(Exception):
    def __init__(self, message: str, *, provenance: AgentAdapterProvenance, execution_metadata: dict[str, Any] | None = None, failure_kind: str = "adapter_failure"):
        super().__init__(message)
        self.failure_kind = failure_kind
        self.provenance = provenance
        self.execution_metadata = execution_metadata


class AgentAdapter(Protocol):
    identity: AgentAdapterIdentity

    def invoke(self, request: AgentInvocationRequest) -> AgentAdapterExecutionOutcome:
        ...
