import json
import os
import tempfile
from pathlib import Path

from .errors import ToolPersistenceError
from .models import ToolCall, ToolResult


class ToolStore:
    def __init__(self, workspace):
        self.workspace = Path(workspace)

    def _path(self, project_id: str, run_id: str, directory: str, identity: str) -> Path:
        return self.workspace / "projects" / project_id / "runs" / run_id / directory / f"{identity}.json"

    def _write(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise ToolPersistenceError(f"tool record already exists: {path}")
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, sort_keys=True, separators=(",", ":"), default=str)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            if path.exists():
                raise ToolPersistenceError(f"tool record already exists: {path}")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def write_call(self, call: ToolCall) -> None:
        self._write(self._path(call.project_id, call.run_id, "tool_calls", call.call_id), call.model_dump(mode="json"))

    def write_result(self, result: ToolResult) -> None:
        self._write(self._path(result.project_id, result.run_id, "tool_results", result.result_id), result.model_dump(mode="json"))
