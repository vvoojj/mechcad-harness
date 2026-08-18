from .errors import ConvergenceError
from .models import Run


class ConvergenceTracker:
    @staticmethod
    def record_revision(run: Run, revision: int, state_hash: str) -> Run:
        history = run.state_hash_history
        if state_hash == run.active_state_hash:
            raise ConvergenceError("NO_STATE_PROGRESS")
        if state_hash in history:
            raise ConvergenceError("STATE_CYCLE")
        iteration = run.iteration + 1
        if iteration > run.max_iterations:
            raise ConvergenceError("ITERATION_LIMIT")
        return run.model_copy(update={
            "active_revision": revision,
            "active_state_hash": state_hash,
            "iteration": iteration,
            "state_hash_history": (*history, state_hash),
        })
