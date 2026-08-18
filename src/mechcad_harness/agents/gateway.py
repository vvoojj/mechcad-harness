import hashlib
import json
from uuid import uuid4

from mechcad_harness.state.hashing import canonical_json

from .models import AgentAdapterExecutionError, AgentAdapterExecutionOutcome, AgentAdapterProvenance, AgentInvocationRecord, AgentInvocationRequest, AgentResult, AgentResultStatus, AgentResponsePayload
from .persistence import AgentStore


def payload_hash(payload) -> str:
    return f"sha256:{hashlib.sha256(canonical_json(payload)).hexdigest()}"


class AgentGateway:
    def __init__(self, controller, registry, context_builder):
        self.controller = controller
        self.registry = registry
        self.context_builder = context_builder
        self.store = AgentStore(controller.workspace)

    def invoke(self, run_id, task_id, agent_name, agent_version, *, requested_output_schema_version="1.0", selected_evidence_ids=(), selected_requirement_ids=(), selected_constraint_ids=()):
        run = self.controller.get_run(run_id)
        definition = self.controller.store.load_task_definition(run.project_id, run_id, task_id)
        task_state = self.controller.store.load_task_state(run.project_id, run_id, task_id)
        if definition.run_id != run_id or definition.bound_revision != run.active_revision or definition.bound_state_hash != run.active_state_hash:
            raise ValueError("agent task binding is stale")
        if task_state.bound_revision != definition.bound_revision or task_state.bound_state_hash != definition.bound_state_hash:
            raise ValueError("agent task state binding mismatch")
        context = self.context_builder.build(run_id, task_id, selected_evidence_ids=tuple(selected_evidence_ids), selected_requirement_ids=tuple(selected_requirement_ids), selected_constraint_ids=tuple(selected_constraint_ids))
        adapter = self.registry.get(agent_name, agent_version)
        from .models import AgentIdentity

        identity = AgentIdentity(agent_name=agent_name, agent_version=agent_version, role="test", protocol_version="1.0")
        request = AgentInvocationRequest(invocation_id=f"INV-{uuid4()}", agent=identity, project_id=run.project_id, run_id=run_id, task_id=task_id, bound_revision=definition.bound_revision, bound_state_hash=definition.bound_state_hash, context=context, requested_output_schema_version=requested_output_schema_version, context_hash=payload_hash(context.model_dump(mode="json")))
        self.store.write_invocation(AgentInvocationRecord(request=request, request_hash=payload_hash(request.model_dump(mode="json"))))
        static_provenance = AgentAdapterProvenance(adapter_name=adapter.identity.adapter_name, adapter_version=adapter.identity.adapter_version, provider="unknown", transport="in-process")
        try:
            execution = adapter.invoke(request)
            if not isinstance(execution, AgentAdapterExecutionOutcome):
                raise TypeError("agent adapter returned invalid execution outcome")
            response = AgentResponsePayload.model_validate(execution.response)
            provenance = execution.provenance
            for proposal in response.change_proposals:
                if proposal.base_revision != request.bound_revision or proposal.base_state_hash != request.bound_state_hash:
                    raise ValueError("RESPONSE_BINDING_MISMATCH")
            response_hash = payload_hash(response.model_dump(mode="json"))
            current = self.controller.get_run(run_id)
            current_definition = self.controller.store.load_task_definition(current.project_id, run_id, task_id)
            stale = current.project_id != request.project_id or current.active_revision != request.bound_revision or current.active_state_hash != request.bound_state_hash or current_definition.bound_revision != request.bound_revision or current_definition.bound_state_hash != request.bound_state_hash
            status = AgentResultStatus.STALE if stale else AgentResultStatus.SUCCEEDED
            error = "agent response binding is stale" if stale else None
            result = AgentResult(result_id=f"AGENTRES-{uuid4()}", invocation_id=request.invocation_id, agent_name=agent_name, agent_version=agent_version, project_id=request.project_id, run_id=run_id, task_id=task_id, bound_revision=request.bound_revision, bound_state_hash=request.bound_state_hash, status=status, response_hash=response_hash, response=response, adapter_provenance=execution.provenance, error=error)
        except AgentAdapterExecutionError as exc:
            result = AgentResult(result_id=f"AGENTRES-{uuid4()}", invocation_id=request.invocation_id, agent_name=agent_name, agent_version=agent_version, project_id=request.project_id, run_id=run_id, task_id=task_id, bound_revision=request.bound_revision, bound_state_hash=request.bound_state_hash, status=AgentResultStatus.FAILED, response_hash=payload_hash({}), response=None, adapter_provenance=exc.provenance, error=str(exc))
        except Exception as exc:
            result = AgentResult(result_id=f"AGENTRES-{uuid4()}", invocation_id=request.invocation_id, agent_name=agent_name, agent_version=agent_version, project_id=request.project_id, run_id=run_id, task_id=task_id, bound_revision=request.bound_revision, bound_state_hash=request.bound_state_hash, status=AgentResultStatus.FAILED, response_hash=payload_hash({}), response=None, adapter_provenance=static_provenance, error=str(exc))
        self.store.write_result(result)
        return result
