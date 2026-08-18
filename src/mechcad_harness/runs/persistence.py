import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .errors import RunConflictError, RunIntegrityError
from .models import Run, RunEvent, RunManifest, RunPlan, TaskDefinition, TaskExecutionResult, TaskState


class RunStore:
    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace)

    def run_dir(self, project_id: str, run_id: str) -> Path:
        return self.workspace / "projects" / project_id / "runs" / run_id

    def _write(self, path: Path, payload: dict[str, Any], *, exclusive: bool) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if exclusive and path.exists():
            raise RunConflictError(f"immutable record already exists: {path}")
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            if exclusive and path.exists():
                raise RunConflictError(f"immutable record already exists: {path}")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _read(self, path: Path, model):
        if not path.exists():
            raise RunIntegrityError(f"missing run record: {path}")
        try:
            return model.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RunIntegrityError(f"invalid run record: {path}") from exc

    def create_manifest(self, run: Run) -> None:
        manifest = RunManifest(
            run_id=run.run_id,
            project_id=run.project_id,
            initial_revision=run.initial_revision,
            initial_state_hash=run.initial_state_hash,
            max_iterations=run.max_iterations,
            created_at=run.created_at,
        )
        self._write(self.run_dir(run.project_id, run.run_id) / "manifest.json", manifest.model_dump(mode="json"), exclusive=True)

    def load_manifest(self, project_id: str, run_id: str) -> RunManifest:
        return self._read(self.run_dir(project_id, run_id) / "manifest.json", RunManifest)

    def write_state(self, run: Run) -> None:
        self._write(self.run_dir(run.project_id, run.run_id) / "state.json", run.model_dump(mode="json"), exclusive=False)

    def load_state(self, project_id: str, run_id: str) -> Run:
        return self._read(self.run_dir(project_id, run_id) / "state.json", Run)

    def write_plan(self, plan: RunPlan) -> None:
        self._write(self.run_dir_from_plan(plan) / "plan.json", plan.model_dump(mode="json"), exclusive=True)

    def run_dir_from_plan(self, plan: RunPlan) -> Path:
        return self.workspace / "projects" / plan.run_id.split("-", 1)[0] / "runs" / plan.run_id

    def write_task_definition(self, definition: TaskDefinition, project_id: str) -> None:
        self._write(self.run_dir(project_id, definition.run_id) / "tasks" / definition.task_id / "definition.json", definition.model_dump(mode="json"), exclusive=True)

    def load_task_definition(self, project_id: str, run_id: str, task_id: str) -> TaskDefinition:
        return self._read(self.run_dir(project_id, run_id) / "tasks" / task_id / "definition.json", TaskDefinition)

    def write_task_state(self, project_id: str, run_id: str, state: TaskState) -> None:
        self._write(self.run_dir(project_id, run_id) / "tasks" / state.task_id / "state.json", state.model_dump(mode="json"), exclusive=False)

    def load_task_state(self, project_id: str, run_id: str, task_id: str) -> TaskState:
        return self._read(self.run_dir(project_id, run_id) / "tasks" / task_id / "state.json", TaskState)

    def write_result(self, project_id: str, run_id: str, result: TaskExecutionResult) -> None:
        self._write(self.run_dir(project_id, run_id) / "results" / f"{result.result_id}.json", result.model_dump(mode="json"), exclusive=True)

    def load_result(self, project_id: str, run_id: str, result_id: str) -> TaskExecutionResult:
        return self._read(self.run_dir(project_id, run_id) / "results" / f"{result_id}.json", TaskExecutionResult)

    def append_event(self, project_id: str, run_id: str, event_type: str, payload: dict[str, Any] | None = None) -> RunEvent:
        directory = self.run_dir(project_id, run_id) / "events"
        directory.mkdir(parents=True, exist_ok=True)
        numbers = [int(path.stem.split("-")[1]) for path in directory.glob("EVT-*.json")]
        event = RunEvent(event_id=f"EVT-{max(numbers, default=0) + 1:06d}", event_type=event_type, payload=payload or {})
        self._write(directory / f"{event.event_id}.json", event.model_dump(mode="json"), exclusive=True)
        return event
