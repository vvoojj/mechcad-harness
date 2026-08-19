from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable, Type

from pydantic import Field

from mechcad_harness.models.common import Model
from mechcad_harness.backends.models import BackendProvenance


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TorqueInput(Model):
    force_n: float = Field(gt=0)
    lever_arm_m: float = Field(gt=0)
    safety_factor: float = Field(gt=0)


class ToolContext(Model):
    project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    bound_revision: int = Field(gt=0)
    bound_state_hash: str = Field(min_length=1)


class ToolResultStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ToolCall(Model):
    call_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    bound_revision: int = Field(gt=0)
    bound_state_hash: str = Field(min_length=1)
    inputs: dict[str, Any]
    input_hash: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)


class ToolError(Model):
    error_type: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ToolResult(Model):
    result_id: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    bound_revision: int = Field(gt=0)
    bound_state_hash: str = Field(min_length=1)
    status: ToolResultStatus
    input_hash: str = Field(min_length=1)
    output: dict[str, Any] | None = None
    output_hash: str | None = None
    error: ToolError | None = None
    evidence_id: str | None = None
    backend_provenance: BackendProvenance | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ToolRegistration(Model):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    input_model: Type[Model]
    output_model: Type[Model]
    handler: Callable[[Model], Model]
    provenance_handler: Callable[[], BackendProvenance] | None = None
    evidence_summary_handler: Callable[[Model], str] | None = None
    evidence_nodes: tuple[str, ...] = ()

    model_config = {"arbitrary_types_allowed": True, "extra": "forbid"}
