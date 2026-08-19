import hashlib
from uuid import uuid4

from mechcad_harness.state.hashing import canonical_json

from .materialization import materialize_agent_response
from .models import AgentAdapterExecutionError, AgentAdapterExecutionOutcome, AgentAdapterProvenance, AgentAuthoredResponseContract, AgentConstraintRequestObservationRecord, AgentInvocationRecord, AgentInvocationRequest, AgentResult, AgentResultStatus, AgentResponsePayload, AgentToolRequestObservationRecord, materialize_response_contract
from .persistence import AgentStore
from .tool_mediation import AgentToolMediator, AgentToolMediationMode


def payload_hash(payload) -> str:
    return f"sha256:{hashlib.sha256(canonical_json(payload)).hexdigest()}"


class AgentGateway:
    def __init__(self, controller, registry, context_builder, *, tool_broker=None):
        self.controller = controller
        self.registry = registry
        self.context_builder = context_builder
        self.store = AgentStore(controller.workspace)
        self.tool_mediator = AgentToolMediator(controller, tool_broker) if tool_broker is not None else None

    def invoke(self, run_id, task_id, agent_name, agent_version, *, requested_output_schema_version="1.0", selected_evidence_ids=(), selected_requirement_ids=(), selected_constraint_ids=(), mediation_mode=AgentToolMediationMode.ENABLED, response_contract=None):
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
        contract = response_contract or (AgentAuthoredResponseContract.TOOL_REQUESTS_ALLOWED if mediation_mode is AgentToolMediationMode.ENABLED else AgentAuthoredResponseContract.TOOL_REQUESTS_FORBIDDEN)
        if mediation_mode is AgentToolMediationMode.ENABLED and contract is not AgentAuthoredResponseContract.TOOL_REQUESTS_ALLOWED:
            raise ValueError("enabled mediation requires TOOL_REQUESTS_ALLOWED")
        if mediation_mode is AgentToolMediationMode.DISABLED and contract is AgentAuthoredResponseContract.TOOL_REQUESTS_ALLOWED:
            raise ValueError("disabled mediation requires a no-tool response contract")
        response_schema_hash = materialize_response_contract(contract).schema_hash
        request = AgentInvocationRequest(invocation_id=f"INV-{uuid4()}", agent=identity, project_id=run.project_id, run_id=run_id, task_id=task_id, bound_revision=definition.bound_revision, bound_state_hash=definition.bound_state_hash, context=context, requested_output_schema_version=requested_output_schema_version, context_hash=payload_hash(context.model_dump(mode="json")), response_contract=contract, response_schema_hash=response_schema_hash)
        self.store.write_invocation(AgentInvocationRecord(request=request, request_hash=payload_hash(request.model_dump(mode="json"))))
        static_provenance = AgentAdapterProvenance(adapter_name=adapter.identity.adapter_name, adapter_version=adapter.identity.adapter_version, provider="unknown", transport="in-process")
        try:
            execution = adapter.invoke(request)
            if not isinstance(execution, AgentAdapterExecutionOutcome):
                raise TypeError("agent adapter returned invalid execution outcome")
            authored = execution.authored_response
            response = materialize_agent_response(request=request, agent=identity, authored=authored)
            response = AgentResponsePayload.model_validate(response)
            authored_requests = [item.model_dump(mode="json") for item in authored.tool_requests]
            if contract is AgentAuthoredResponseContract.CONSTRAINT_DISCOVERY_TOOLS_FORBIDDEN:
                constraint_requests = [item.model_dump(mode="json") for item in authored.constraint_requests]
                constraint_observation_id = payload_hash({"invocation_id": request.invocation_id, "constraint_requests": constraint_requests})[7:]
                constraint_observation = AgentConstraintRequestObservationRecord(
                    observation_id=f"OBS-{constraint_observation_id}",
                    invocation_id=request.invocation_id,
                    agent_name=identity.agent_name,
                    agent_version=identity.agent_version,
                    project_id=request.project_id,
                    run_id=request.run_id,
                    task_id=task_id,
                    bound_revision=request.bound_revision,
                    bound_state_hash=request.bound_state_hash,
                    response_contract=contract.value,
                    constraint_requests=authored.constraint_requests,
                    constraint_requests_hash=payload_hash(constraint_requests),
                )
                try:
                    self.store.write_constraint_request_observation(constraint_observation)
                except Exception:
                    result = AgentResult(result_id=f"AGENTRES-{uuid4()}", invocation_id=request.invocation_id, agent_name=agent_name, agent_version=agent_version, project_id=request.project_id, run_id=run_id, task_id=task_id, bound_revision=request.bound_revision, bound_state_hash=request.bound_state_hash, status=AgentResultStatus.FAILED, response_hash=payload_hash({}), response=None, adapter_provenance=execution.provenance, error="CONSTRAINT_OBSERVATION_PERSISTENCE_FAILED")
                    self.store.write_result(result)
                    return result
            observation_digest = payload_hash({"invocation_id": request.invocation_id, "mode": mediation_mode.value, "tool_requests": authored_requests})
            observation = AgentToolRequestObservationRecord(
                observation_id=f"OBS-{observation_digest[7:]}",
                invocation_id=request.invocation_id,
                agent_name=identity.agent_name,
                agent_version=identity.agent_version,
                project_id=request.project_id,
                run_id=request.run_id,
                task_id=request.task_id,
                bound_revision=request.bound_revision,
                bound_state_hash=request.bound_state_hash,
                mediation_mode=mediation_mode.value,
                tool_requests=authored.tool_requests,
                tool_requests_hash=payload_hash(authored_requests),
            )
            try:
                self.store.write_tool_request_observation(observation)
            except Exception:
                result = AgentResult(result_id=f"AGENTRES-{uuid4()}", invocation_id=request.invocation_id, agent_name=agent_name, agent_version=agent_version, project_id=request.project_id, run_id=run_id, task_id=task_id, bound_revision=request.bound_revision, bound_state_hash=request.bound_state_hash, status=AgentResultStatus.FAILED, response_hash=payload_hash({}), response=None, adapter_provenance=execution.provenance, error="OBSERVATION_PERSISTENCE_FAILED")
                self.store.write_result(result)
                return result
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
        if result.status is AgentResultStatus.SUCCEEDED and mediation_mode is AgentToolMediationMode.ENABLED and authored.tool_requests:
            if self.tool_mediator is None:
                raise ValueError("tool mediator is not configured")
            self.tool_mediator.mediate(request, identity, authored.tool_requests, source_result_id=result.result_id)
        return result
