from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator

from mechcad_harness.models import Evidence
from mechcad_harness.models.common import Model


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def nonempty(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty")
    return value


class RunStatus(StrEnum):
    CREATED = "created"
    PLANNED = "planned"
    RUNNING = "running"
    BLOCKED = "blocked"
    FAILED = "failed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    STALE = "stale"
    SKIPPED = "skipped"


class Run(Model):
    run_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    initial_revision: int = Field(gt=0)
    initial_state_hash: str = Field(min_length=1)
    active_revision: int = Field(gt=0)
    active_state_hash: str = Field(min_length=1)
    status: RunStatus = RunStatus.CREATED
    iteration: int = Field(default=0, ge=0)
    max_iterations: int = Field(default=3, gt=0)
    state_hash_history: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("run_id", "project_id", "initial_state_hash", "active_state_hash")
    @classmethod
    def validate_strings(cls, value: str) -> str:
        return nonempty(value)


class RunManifest(Model):
    schema_version: str = "m4"
    run_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    initial_revision: int = Field(gt=0)
    initial_state_hash: str = Field(min_length=1)
    max_iterations: int = Field(gt=0)
    created_at: datetime


class RunPlan(Model):
    run_id: str = Field(min_length=1)
    required_evidence_nodes: tuple[str, ...] = ()
    task_ids: tuple[str, ...] = ()


class TaskDefinition(Model):
    task_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    bound_revision: int = Field(gt=0)
    bound_state_hash: str = Field(min_length=1)
    depends_on: tuple[str, ...] = ()
    required_nodes: tuple[str, ...] = ()
    produces_nodes: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)


class TaskState(Model):
    task_id: str = Field(min_length=1)
    bound_revision: int = Field(gt=0)
    bound_state_hash: str = Field(min_length=1)
    status: TaskStatus = TaskStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result_id: str | None = None
    error: str | None = None


class TaskContext(Model):
    project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    revision: int = Field(gt=0)
    state_hash: str = Field(min_length=1)
    state: Any


class TaskExecutionResult(Model):
    result_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    bound_revision: int = Field(gt=0)
    bound_state_hash: str = Field(min_length=1)
    status: TaskStatus = TaskStatus.SUCCEEDED
    findings: tuple[str, ...] = ()
    proposals: tuple[Any, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    issues: tuple[Any, ...] = ()


class RunEvent(Model):
    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    payload: dict[str, Any] = {}
    created_at: datetime = Field(default_factory=utc_now)
