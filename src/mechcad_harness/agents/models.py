from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Protocol

from pydantic import Field, field_validator

from mechcad_harness.models import ChangeProposal, ConstraintRequest, DesignState, Issue
from mechcad_harness.models.common import Model


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


class AgentAdapter(Protocol):
    identity: AgentAdapterIdentity

    def invoke(self, request: AgentInvocationRequest) -> AgentResponsePayload:
        ...
