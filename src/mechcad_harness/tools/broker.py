import json
import hashlib
from uuid import uuid4

from mechcad_harness.models import Evidence

from .errors import ToolExecutionError, ToolPermissionError
from .models import ToolCall, ToolContext, ToolError, ToolResult, ToolResultStatus
from .persistence import ToolStore


def payload_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _structural_evidence_complete(output: dict) -> bool:
    return all(output.get(name, {}).get("status") == "available" for name in ("axial_rigidity_ea", "bending_rigidity_eix", "bending_rigidity_eiy"))


class ToolBroker:
    def __init__(self, controller, registry):
        self.controller = controller
        self.registry = registry
        self.store = ToolStore(controller.workspace)

    def execute(self, run_id: str, task_id: str, tool_name: str, tool_version: str, inputs: dict, *, evidence_node: str | None = None) -> ToolResult:
        run = self.controller.get_run(run_id)
        definition = self.controller.store.load_task_definition(run.project_id, run_id, task_id)
        state = self.controller.store.load_task_state(run.project_id, run_id, task_id)
        if definition.run_id != run_id or state.status not in (state.status.RUNNING, state.status.PENDING, state.status.READY):
            raise ToolExecutionError("task is not valid for tool execution")
        if definition.bound_revision != run.active_revision or definition.bound_state_hash != run.active_state_hash:
            raise ToolExecutionError("task binding is stale for the active run")
        permission = f"{tool_name}@{tool_version}"
        if permission not in definition.allowed_tools and tool_name not in definition.allowed_tools:
            raise ToolPermissionError(f"tool is not permitted by task: {permission}")
        registration = self.registry.resolve(tool_name, tool_version)
        if evidence_node is not None and evidence_node not in registration.evidence_nodes:
            raise ToolExecutionError("tool is not declared to produce evidence node")
        context = ToolContext(project_id=run.project_id, run_id=run_id, task_id=task_id, bound_revision=definition.bound_revision, bound_state_hash=definition.bound_state_hash)
        if context.bound_revision != definition.bound_revision or context.bound_state_hash != definition.bound_state_hash:
            raise ToolExecutionError("tool context binding mismatch")
        try:
            validated = registration.input_model.model_validate(inputs)
            normalized = validated.model_dump(mode="json")
        except Exception:
            normalized = dict(inputs)
            validated = None
        call = ToolCall(call_id=f"CALL-{uuid4()}", tool_name=tool_name, tool_version=tool_version, project_id=context.project_id, run_id=context.run_id, task_id=context.task_id, bound_revision=context.bound_revision, bound_state_hash=context.bound_state_hash, inputs=normalized, input_hash=payload_hash(normalized))
        self.store.write_call(call)
        result_id = f"TOOLRES-{uuid4()}"
        try:
            if validated is None:
                raise ToolExecutionError("invalid tool input")
            if tool_name in {"mechcad-build-spur-gear-cad", "mechcad-build-spur-gear-pair-cad"}:
                output = registration.handler(validated, self.controller.workspace, project_id=context.project_id, run_id=context.run_id, task_id=context.task_id, bound_revision=context.bound_revision, bound_state_hash=context.bound_state_hash, input_hash=call.input_hash)
            elif tool_name == "mechcad-calc-preliminary-section-engineering-properties":
                output = registration.handler(validated, self.controller, project_id=context.project_id, run_id=context.run_id, revision=context.bound_revision, state_hash=context.bound_state_hash)
            else:
                output = registration.handler(validated)
            output_payload = output.model_dump(mode="json")
            provenance = registration.provenance_handler() if registration.provenance_handler else None
            result = ToolResult(result_id=result_id, call_id=call.call_id, tool_name=tool_name, tool_version=tool_version, project_id=context.project_id, run_id=context.run_id, task_id=context.task_id, bound_revision=context.bound_revision, bound_state_hash=context.bound_state_hash, status=ToolResultStatus.SUCCEEDED, input_hash=call.input_hash, output=output_payload, output_hash=payload_hash(output_payload), backend_provenance=provenance)
            self.store.write_result(result)
            if evidence_node is not None and not (tool_name == "mechcad-calc-preliminary-section-engineering-properties" and not _structural_evidence_complete(output_payload)):
                try:
                    from .evidence import ToolEvidenceMaterializer
                    evidence = ToolEvidenceMaterializer(self.controller, self.registry).materialize_from_result(context.project_id, context.run_id, context.task_id, result.result_id, evidence_node, context.bound_revision, context.bound_state_hash)
                except Exception as exc:
                    raise ToolExecutionError(f"evidence persistence failed: {type(exc).__name__}: {exc}") from exc
                result = result.model_copy(update={"evidence_id": evidence.id})
            return result
        except ToolExecutionError as exc:
            failed = ToolResult(result_id=result_id, call_id=call.call_id, tool_name=tool_name, tool_version=tool_version, project_id=context.project_id, run_id=context.run_id, task_id=context.task_id, bound_revision=context.bound_revision, bound_state_hash=context.bound_state_hash, status=ToolResultStatus.FAILED, input_hash=call.input_hash, error=ToolError(error_type=type(exc).__name__, message=str(exc)))
            self.store.write_result(failed)
            raise
        except Exception as exc:
            failed = ToolResult(result_id=result_id, call_id=call.call_id, tool_name=tool_name, tool_version=tool_version, project_id=context.project_id, run_id=context.run_id, task_id=context.task_id, bound_revision=context.bound_revision, bound_state_hash=context.bound_state_hash, status=ToolResultStatus.FAILED, input_hash=call.input_hash, error=ToolError(error_type=type(exc).__name__, message=str(exc)))
            self.store.write_result(failed)
            raise ToolExecutionError("tool execution failed") from exc
