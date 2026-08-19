import hashlib
import uuid

from mechcad_harness.models import Evidence

from .broker import payload_hash
from .errors import ToolExecutionError
from .models import ToolResultStatus


def evidence_id(project_id: str, run_id: str, tool_result_id: str, evidence_node: str) -> str:
    value = uuid.uuid5(uuid.NAMESPACE_URL, f"mechcad:evidence:{project_id}:{run_id}:{tool_result_id}:{evidence_node}")
    return f"EVD-{value}"


class ToolEvidenceMaterializer:
    def __init__(self, controller, registry):
        self.controller = controller
        self.registry = registry

    def materialize_from_result(self, project_id, run_id, task_id, tool_result_id, evidence_node, expected_revision, expected_state_hash):
        from .persistence import ToolStore

        store = ToolStore(self.controller.workspace)
        result = store.load_result(project_id, run_id, tool_result_id)
        if result.status is not ToolResultStatus.SUCCEEDED or result.output is None or result.output_hash is None:
            raise ToolExecutionError("tool result is not eligible for evidence")
        call = store.load_call(project_id, run_id, result.call_id)
        if (call.project_id, call.run_id, call.task_id) != (project_id, run_id, task_id) or (result.project_id, result.run_id, result.task_id) != (project_id, run_id, task_id):
            raise ToolExecutionError("tool record scope mismatch")
        if (call.tool_name, call.tool_version) != (result.tool_name, result.tool_version) or (call.bound_revision, call.bound_state_hash) != (expected_revision, expected_state_hash) or (result.bound_revision, result.bound_state_hash) != (expected_revision, expected_state_hash):
            raise ToolExecutionError("tool result binding mismatch")
        if payload_hash(call.inputs) != call.input_hash or payload_hash(result.output) != result.output_hash:
            raise ToolExecutionError("tool record hash mismatch")
        registration = self.registry.resolve(result.tool_name, result.tool_version)
        if evidence_node not in registration.evidence_nodes:
            raise ToolExecutionError("tool evidence node is not authorized")
        output_model = registration.output_model.model_validate(result.output)
        summary = registration.evidence_summary_handler(output_model) if registration.evidence_summary_handler else f"{result.tool_name} result"
        evidence = Evidence(id=evidence_id(project_id, run_id, result.result_id, evidence_node), kind=evidence_node, summary=summary, revision=result.bound_revision, state_hash=result.bound_state_hash, producer_type="tool", producer_name=result.tool_name, producer_version=result.tool_version, producer_result_id=result.result_id, input_hash=call.input_hash, output_hash=result.output_hash, backend_provenance=result.backend_provenance)
        try:
            existing = self.controller.evidence.load_evidence(project_id, evidence.id)
        except Exception:
            existing = None
        if existing is not None:
            if existing != evidence:
                raise ToolExecutionError("conflicting evidence identity")
            return existing
        self.controller.evidence.write_evidence(project_id, evidence)
        return evidence
