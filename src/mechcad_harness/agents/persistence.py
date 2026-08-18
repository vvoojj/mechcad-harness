from pathlib import Path

from mechcad_harness.runs.persistence import RunStore

from .models import AgentInvocationRecord, AgentResult


class AgentStore:
    def __init__(self, workspace):
        self.store = RunStore(workspace)

    def _path(self, project_id, run_id, category, record_id):
        return self.store.run_dir(project_id, run_id) / "agents" / category / f"{record_id}.json"

    def write_invocation(self, record: AgentInvocationRecord) -> None:
        request = record.request
        self.store._write(self._path(request.project_id, request.run_id, "invocations", request.invocation_id), record.model_dump(mode="json"), exclusive=True)

    def load_invocation(self, project_id, run_id, invocation_id) -> AgentInvocationRecord:
        return self.store._read(self._path(project_id, run_id, "invocations", invocation_id), AgentInvocationRecord)

    def write_result(self, result: AgentResult) -> None:
        self.store._write(self._path(result.project_id, result.run_id, "results", result.result_id), result.model_dump(mode="json"), exclusive=True)

    def load_result(self, project_id, run_id, result_id) -> AgentResult:
        return self.store._read(self._path(project_id, run_id, "results", result_id), AgentResult)
