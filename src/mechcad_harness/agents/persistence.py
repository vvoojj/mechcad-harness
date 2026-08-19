from pathlib import Path

from mechcad_harness.runs.persistence import RunStore

from .models import AgentConstraintRequestObservationRecord, AgentInvocationRecord, AgentResult, AgentToolRequestObservationRecord
from .constraint_requests import ConstraintRequestRecord, ConstraintRequestStore
from .tool_mediation import ToolMediationRecord


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

    def write_tool_request_observation(self, record: AgentToolRequestObservationRecord) -> None:
        self.store._write(self._path(record.project_id, record.run_id, "tool_request_observations", record.observation_id), record.model_dump(mode="json"), exclusive=True)

    def load_tool_request_observation(self, project_id, run_id, invocation_id) -> AgentToolRequestObservationRecord:
        directory = self.store.run_dir(project_id, run_id) / "agents" / "tool_request_observations"
        matches = [path for path in directory.glob("*.json") if AgentToolRequestObservationRecord.model_validate_json(path.read_text(encoding="utf-8")).invocation_id == invocation_id]
        if len(matches) != 1:
            raise ValueError(f"tool request observation not uniquely found: {invocation_id}")
        return self.store._read(matches[0], AgentToolRequestObservationRecord)

    def write_constraint_request_observation(self, record: AgentConstraintRequestObservationRecord) -> None:
        self.store._write(self._path(record.project_id, record.run_id, "constraint_request_observations", record.observation_id), record.model_dump(mode="json"), exclusive=True)

    def load_constraint_request_observation(self, project_id, run_id, invocation_id) -> AgentConstraintRequestObservationRecord:
        directory = self.store.run_dir(project_id, run_id) / "agents" / "constraint_request_observations"
        matches = [path for path in directory.glob("*.json") if AgentConstraintRequestObservationRecord.model_validate_json(path.read_text(encoding="utf-8")).invocation_id == invocation_id]
        if len(matches) != 1:
            raise ValueError(f"constraint request observation not uniquely found: {invocation_id}")
        return self.store._read(matches[0], AgentConstraintRequestObservationRecord)

    def _mediation_path(self, project_id, run_id, mediation_id, filename):
        return self.store.run_dir(project_id, run_id) / "agents" / "tool_mediation" / mediation_id / filename

    def write_mediation_pending(self, project_id, run_id, record: ToolMediationRecord) -> None:
        self.store._write(self._mediation_path(project_id, run_id, record.mediation_id, "pending.json"), record.model_dump(mode="json"), exclusive=True)

    def write_mediation_final(self, project_id, run_id, record: ToolMediationRecord) -> None:
        self.store._write(self._mediation_path(project_id, run_id, record.mediation_id, "final.json"), record.model_dump(mode="json"), exclusive=True)
