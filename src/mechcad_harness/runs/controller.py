from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from mechcad_harness.models import ChangeProposal

from .convergence import ConvergenceTracker
from .errors import ConvergenceError, InvalidRunTransitionError, RunIntegrityError, TaskExecutionError
from .executor import TaskExecutor, validate_result
from .models import Run, RunPlan, SourceBinding, TaskContext, TaskDefinition, TaskExecutionResult, TaskState, TaskStatus, RunStatus
from .persistence import RunStore
from .scheduler import TaskScheduler


class RunController:
    def __init__(self, workspace: str | Path, state_manager, change_engine, evidence_store):
        self.workspace = Path(workspace)
        self.state_manager = state_manager
        self.change_engine = change_engine
        self.evidence = evidence_store
        self.store = RunStore(workspace)

    def create_run(
        self,
        project_id: str,
        *,
        max_iterations: int = 3,
        expected_source: SourceBinding | None = None,
    ) -> Run:
        with self.state_manager.project_lock(project_id):
            return self._create_run(
                project_id,
                max_iterations=max_iterations,
                expected_source=expected_source,
            )

    def _create_run(
        self,
        project_id: str,
        *,
        max_iterations: int,
        expected_source: SourceBinding | None,
    ) -> Run:
        if expected_source is None:
            current = self.state_manager._read_current(project_id)
            revision = current["revision"]
            source_hash = current["state_hash"]
        else:
            if expected_source.project_id != project_id:
                raise RunIntegrityError("expected source project mismatch")
            snapshot = self.state_manager._read_snapshot(project_id, expected_source.revision)
            if snapshot.state_hash != expected_source.state_hash:
                raise RunIntegrityError("expected source snapshot hash mismatch")
            try:
                current = self.state_manager._read_current(project_id)
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError, KeyError, AttributeError) as exc:
                raise RunIntegrityError("invalid current canonical pointer") from exc
            if (
                not isinstance(current, dict)
                or current.get("project_id") != expected_source.project_id
                or current.get("revision") != expected_source.revision
                or current.get("state_hash") != expected_source.state_hash
            ):
                raise RunIntegrityError("current canonical pointer does not match expected source")
            revision = expected_source.revision
            source_hash = expected_source.state_hash
        run_id = f"RUN-{uuid4()}"
        run = Run(run_id=run_id, project_id=project_id, initial_revision=revision,
                  initial_state_hash=source_hash, active_revision=revision,
                  active_state_hash=source_hash, max_iterations=max_iterations,
                  state_hash_history=(source_hash,))
        self.store.create_manifest(run)
        self.store.write_state(run)
        self.store.append_event(project_id, run_id, "RUN_CREATED", {"revision": run.active_revision})
        return run

    def get_run(self, run_id: str, project_id: str | None = None) -> Run:
        if project_id is None:
            matches = list(self.workspace.glob(f"projects/*/runs/{run_id}/manifest.json"))
            if len(matches) != 1:
                raise RunIntegrityError(f"run not uniquely found: {run_id}")
            project_id = matches[0].parents[2].name
        return self.store.load_state(project_id, run_id)

    def create_plan(self, run_id: str, *, required_evidence_nodes: tuple[str, ...] = ()) -> RunPlan:
        run = self.get_run(run_id)
        definitions = self._definitions(run)
        scheduler = TaskScheduler(definitions, {item.task_id: self.store.load_task_state(run.project_id, run_id, item.task_id) for item in definitions})
        scheduler.ordered()
        plan = RunPlan(run_id=run_id, required_evidence_nodes=required_evidence_nodes, task_ids=tuple(sorted(item.task_id for item in definitions)))
        self.store._write(self.store.run_dir(run.project_id, run_id) / "plan.json", plan.model_dump(mode="json"), exclusive=False)
        self._save(run.model_copy(update={"status": RunStatus.PLANNED}))
        return plan

    def add_task(self, run_id: str, definition: TaskDefinition) -> TaskDefinition:
        run = self.get_run(run_id)
        if definition.run_id != run_id or definition.bound_revision != run.active_revision or definition.bound_state_hash != run.active_state_hash:
            raise InvalidRunTransitionError("task binding does not match active run")
        self.store.write_task_definition(definition, run.project_id)
        self.store.write_task_state(run.project_id, run_id, TaskState(task_id=definition.task_id, bound_revision=definition.bound_revision, bound_state_hash=definition.bound_state_hash))
        self.store.append_event(run.project_id, run_id, "TASK_CREATED", {"task_id": definition.task_id})
        return definition

    def get_task(self, run_id: str, task_id: str) -> TaskDefinition | TaskState:
        run = self.get_run(run_id)
        definition = self.store.load_task_definition(run.project_id, run_id, task_id)
        state = self.store.load_task_state(run.project_id, run_id, task_id)
        return definition.model_copy(update={"status": state.status}) if False else state

    def _definitions(self, run: Run) -> list[TaskDefinition]:
        directory = self.store.run_dir(run.project_id, run.run_id) / "tasks"
        if not directory.exists():
            return []
        return [self.store.load_task_definition(run.project_id, run.run_id, path.name) for path in sorted(directory.iterdir()) if path.is_dir()]

    def execute_ready_tasks(self, run_id: str, executor: TaskExecutor) -> tuple[str, ...]:
        run = self.get_run(run_id)
        executed = []
        while True:
            definitions = self._definitions(run)
            states = {item.task_id: self.store.load_task_state(run.project_id, run_id, item.task_id) for item in definitions}
            scheduler = TaskScheduler(definitions, states)
            ready_tasks = scheduler.ready_tasks()
            if not ready_tasks:
                break
            for task_id in ready_tasks:
                definition = next(item for item in definitions if item.task_id == task_id)
                started = states[task_id].model_copy(update={"status": TaskStatus.RUNNING, "started_at": datetime.now(timezone.utc)})
                self.store.write_task_state(run.project_id, run_id, started)
                try:
                    result = executor.execute(definition, TaskContext(project_id=run.project_id, run_id=run_id, revision=run.active_revision, state_hash=run.active_state_hash, state=self.state_manager.load_revision(run.project_id, run.active_revision)))
                    validate_result(definition, result)
                    self.accept_result(run_id, task_id, result)
                except Exception as exc:
                    failed = started.model_copy(update={"status": TaskStatus.FAILED, "completed_at": datetime.now(timezone.utc), "error": str(exc)})
                    self.store.write_task_state(run.project_id, run_id, failed)
                    self.store.append_event(run.project_id, run_id, "TASK_FAILED", {"task_id": task_id})
                executed.append(task_id)
        for definition in definitions:
            state = self.store.load_task_state(run.project_id, run_id, definition.task_id)
            current_states = {item.task_id: self.store.load_task_state(run.project_id, run_id, item.task_id) for item in definitions}
            if state.status in (TaskStatus.PENDING, TaskStatus.READY) and any(current_states[d].status in (TaskStatus.FAILED, TaskStatus.BLOCKED) for d in definition.depends_on):
                self.store.write_task_state(run.project_id, run_id, state.model_copy(update={"status": TaskStatus.BLOCKED}))
        return tuple(executed)

    def accept_result(self, run_id: str, task_id: str, result: TaskExecutionResult) -> None:
        run = self.get_run(run_id)
        definition = self.store.load_task_definition(run.project_id, run_id, task_id)
        validate_result(definition, result)
        existing = self.store.load_task_state(run.project_id, run_id, task_id)
        if existing.status is not TaskStatus.RUNNING:
            raise TaskExecutionError("task result can only be accepted for a running task")
        self.store.write_result(run.project_id, run_id, result)
        for evidence in result.evidence:
            self.evidence.write_evidence(run.project_id, evidence)
        self.store.write_task_state(run.project_id, run_id, TaskState(task_id=task_id, bound_revision=definition.bound_revision, bound_state_hash=definition.bound_state_hash, status=result.status, started_at=existing.started_at, completed_at=datetime.now(timezone.utc), result_id=result.result_id))
        self.store.append_event(run.project_id, run_id, "TASK_SUCCEEDED" if result.status is TaskStatus.SUCCEEDED else "TASK_FAILED", {"task_id": task_id, "result_id": result.result_id})

    def apply_approved_proposal(self, run_id: str, proposal: ChangeProposal):
        run = self.get_run(run_id)
        applied = self.change_engine.apply_proposal(run.project_id, proposal)
        try:
            updated = ConvergenceTracker.record_revision(run, applied.snapshot.revision, applied.snapshot.state_hash)
        except Exception as exc:
            updated = run.model_copy(update={"active_revision": applied.snapshot.revision, "active_state_hash": applied.snapshot.state_hash, "iteration": run.iteration + 1, "state_hash_history": (*run.state_hash_history, applied.snapshot.state_hash), "status": RunStatus.BLOCKED})
            self._save(updated)
            raise InvalidRunTransitionError(str(exc)) from exc
        self._save(updated)
        self.store.append_event(run.project_id, run_id, "REVISION_ADVANCED", {"revision": updated.active_revision})
        try:
            record = self.evidence.build_invalidation(run.project_id, applied.snapshot.revision, run.active_revision, applied.changed_paths, applied.changeset_id)
            self.evidence.record_invalidation(record)
            invalidated = set(record.transitively_invalidated_nodes)
            for definition in self._definitions(updated):
                state = self.store.load_task_state(updated.project_id, run_id, definition.task_id)
                if state.status in (TaskStatus.PENDING, TaskStatus.READY) and invalidated.intersection(definition.required_nodes or definition.produces_nodes):
                    self.store.write_task_state(updated.project_id, run_id, state.model_copy(update={"status": TaskStatus.STALE}))
        except Exception as exc:
            blocked = self.get_run(run_id).model_copy(update={"status": RunStatus.BLOCKED})
            self._save(blocked)
            self.store.append_event(run.project_id, run_id, "RUN_BLOCKED", {"error": str(exc)})
            raise InvalidRunTransitionError(str(exc)) from exc
        return self.get_run(run_id)

    def record_convergence_revision(self, run_id: str, revision: int, state_hash: str) -> Run:
        run = self.get_run(run_id)
        try:
            updated = ConvergenceTracker.record_revision(run, revision, state_hash)
        except Exception as exc:
            self._save(run.model_copy(update={"status": RunStatus.BLOCKED}))
            raise ConvergenceError(str(exc)) from exc
        self._save(updated)
        return updated

    def evaluate_completion(self, run_id: str) -> bool:
        run = self.get_run(run_id)
        if run.status in (RunStatus.BLOCKED, RunStatus.FAILED, RunStatus.CANCELLED):
            return False
        plan_path = self.store.run_dir(run.project_id, run_id) / "plan.json"
        if not plan_path.exists():
            return False
        plan = RunPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
        for task_id in plan.task_ids:
            if self.store.load_task_state(run.project_id, run_id, task_id).status is not TaskStatus.SUCCEEDED:
                return False
        if any(self.evidence.fresh_evidence_status(run.project_id, node) != "fresh evidence exists" for node in plan.required_evidence_nodes):
            return False
        self._save(run.model_copy(update={"status": RunStatus.COMPLETED}))
        self.store.append_event(run.project_id, run_id, "RUN_COMPLETED")
        return True

    def resume_run(self, project_id: str, run_id: str) -> Run:
        manifest = self.store.load_manifest(project_id, run_id)
        run = self.store.load_state(project_id, run_id)
        if manifest.project_id != project_id or manifest.run_id != run_id or run.project_id != project_id:
            raise RunIntegrityError("run identity mismatch")
        snapshot = self.state_manager._read_snapshot(project_id, run.active_revision)
        if snapshot.state_hash != run.active_state_hash:
            raise RunIntegrityError("active canonical binding mismatch")
        for definition in self._definitions(run):
            state = self.store.load_task_state(project_id, run_id, definition.task_id)
            if state.bound_revision != definition.bound_revision or state.bound_state_hash != definition.bound_state_hash:
                raise RunIntegrityError("task state binding mismatch")
            if state.result_id:
                result = self.store.load_result(project_id, run_id, state.result_id)
                if result.task_id != definition.task_id or result.bound_revision != definition.bound_revision or result.bound_state_hash != definition.bound_state_hash:
                    raise RunIntegrityError("task result binding mismatch")
        return run

    def _save(self, run: Run) -> None:
        self.store.write_state(run.model_copy(update={"updated_at": datetime.now(timezone.utc)}))
