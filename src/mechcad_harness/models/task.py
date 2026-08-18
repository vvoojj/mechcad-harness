from enum import StrEnum

from pydantic import Field

from .common import Model, StateBinding


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentTask(Model):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: TaskStatus = TaskStatus.PENDING


class AgentResult(StateBinding):
    id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
