from .errors import TaskDependencyCycleError, TaskDependencyError
from .models import TaskDefinition, TaskState, TaskStatus


class TaskScheduler:
    def __init__(self, definitions: list[TaskDefinition], states: dict[str, TaskState]):
        self.definitions = {item.task_id: item for item in definitions}
        self.states = states

    def ordered(self) -> tuple[str, ...]:
        for definition in self.definitions.values():
            if any(dependency not in self.definitions for dependency in definition.depends_on):
                raise TaskDependencyError(f"unknown task dependency: {definition.task_id}")
        indegree = {task_id: len(definition.depends_on) for task_id, definition in self.definitions.items()}
        ready = sorted(task_id for task_id, degree in indegree.items() if degree == 0)
        result = []
        while ready:
            task_id = ready.pop(0)
            result.append(task_id)
            for candidate in sorted(self.definitions):
                if task_id in self.definitions[candidate].depends_on:
                    indegree[candidate] -= 1
                    if indegree[candidate] == 0:
                        ready.append(candidate)
                        ready.sort()
        if len(result) != len(self.definitions):
            raise TaskDependencyCycleError("task dependency cycle")
        return tuple(result)

    def ready_tasks(self) -> tuple[str, ...]:
        self.ordered()
        ready = []
        for task_id in sorted(self.definitions):
            state = self.states[task_id]
            definition = self.definitions[task_id]
            if state.status not in (TaskStatus.PENDING, TaskStatus.READY):
                continue
            dependency_states = [self.states[dependency].status for dependency in definition.depends_on]
            if any(status in (TaskStatus.FAILED, TaskStatus.BLOCKED, TaskStatus.STALE) for status in dependency_states):
                continue
            if all(status is TaskStatus.SUCCEEDED for status in dependency_states):
                ready.append(task_id)
        return tuple(ready)
