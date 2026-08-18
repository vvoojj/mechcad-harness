class RunError(Exception):
    pass


class RunIntegrityError(RunError):
    pass


class RunConflictError(RunError):
    pass


class InvalidRunTransitionError(RunError):
    pass


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
