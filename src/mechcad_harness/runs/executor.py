from typing import Protocol

from .errors import StaleTaskResultError
from .models import TaskContext, TaskDefinition, TaskExecutionResult, TaskStatus


class TaskExecutor(Protocol):
    def execute(self, task: TaskDefinition, context: TaskContext) -> TaskExecutionResult:
        ...


class FakeTaskExecutor:
    def __init__(self, *, failing_task_ids: set[str] | None = None):
        self.failing_task_ids = failing_task_ids or set()

    def execute(self, task: TaskDefinition, context: TaskContext) -> TaskExecutionResult:
        status = TaskStatus.FAILED if task.task_id in self.failing_task_ids else TaskStatus.SUCCEEDED
        evidence = tuple(
            __import__("mechcad_harness.models", fromlist=["Evidence"]).Evidence(
                id=f"RES-{task.task_id}-{node}", kind=node, summary="fake evidence",
                revision=task.bound_revision, state_hash=task.bound_state_hash,
            ) for node in task.produces_nodes
        ) if status is TaskStatus.SUCCEEDED else ()
        return TaskExecutionResult(
            result_id=f"RES-{task.task_id}", task_id=task.task_id,
            bound_revision=task.bound_revision, bound_state_hash=task.bound_state_hash,
            status=status, evidence=evidence,
        )


def validate_result(task: TaskDefinition, result: TaskExecutionResult) -> None:
    if (result.task_id != task.task_id or result.bound_revision != task.bound_revision or
            result.bound_state_hash != task.bound_state_hash):
        raise StaleTaskResultError("task execution result binding mismatch")
