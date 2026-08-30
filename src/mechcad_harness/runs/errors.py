from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mechcad_harness.changes.engine import AppliedChangeResult

    from .models import Run


class RunError(Exception):
    pass


class RunIntegrityError(RunError):
    pass


class RunConflictError(RunError):
    pass


class InvalidRunTransitionError(RunError):
    pass


class PostApplyRunTransitionError(InvalidRunTransitionError):
    """A run transition failed after the canonical change was committed."""

    def __init__(self, message: str, *, applied: "AppliedChangeResult", current: "Run"):
        super().__init__(message)
        self.applied = applied
        self.current = current


class PostApplyInvalidationError(PostApplyRunTransitionError):
    def __init__(self, message: str, *, applied: "AppliedChangeResult", blocked: "Run"):
        super().__init__(message, applied=applied, current=blocked)
        self.blocked = blocked


class TaskError(RunError):
    pass


class TaskDependencyError(TaskError):
    pass


class TaskDependencyCycleError(TaskDependencyError):
    pass


class TaskExecutionError(TaskError):
    pass


class StaleTaskResultError(TaskExecutionError):
    pass


class ConvergenceError(RunError):
    pass
