from collections.abc import Iterable

from .models import AgentAdapterExecutionError, AgentAdapterExecutionOutcome, AgentAdapterIdentity, AgentAdapterProvenance, AgentAuthoredResponsePayload, AgentIdentity, AgentInvocationRequest, response_model_for_contract


class FakeAgentAdapter:
    def __init__(self, agent_identity: AgentIdentity, *, findings: Iterable[str] = (), response: AgentAuthoredResponsePayload | None = None, scripted_responses: Iterable[AgentAuthoredResponsePayload] | None = None, issues: Iterable[str] = (), constraint_requests: Iterable[str] = (), error: Exception | None = None):
        self.agent_identity = agent_identity
        self.identity = AgentAdapterIdentity(adapter_name="fake-agent-adapter", adapter_version="1.0")
        self._findings = tuple(findings)
        self._issues = tuple(issues)
        self._constraint_requests = tuple(constraint_requests)
        self._response = response
        self._scripted_responses = None if scripted_responses is None else tuple(scripted_responses)
        self._scripted_index = 0
        self._error = error
        self.last_request: AgentInvocationRequest | None = None
        self.requests: list[AgentInvocationRequest] = []
        self.invocation_count = 0

    def invoke(self, request: AgentInvocationRequest) -> AgentAdapterExecutionOutcome:
        self.last_request = request
        self.requests.append(request)
        self.invocation_count += 1
        provenance = self.provenance()
        if self._error is not None:
            raise AgentAdapterExecutionError(str(self._error), provenance=provenance, failure_kind="fake_failure") from self._error
        if self._scripted_responses is not None:
            if self._scripted_index >= len(self._scripted_responses):
                raise AgentAdapterExecutionError("scripted responses exhausted", provenance=provenance, failure_kind="scripted_exhausted")
            response = self._scripted_responses[self._scripted_index]
            self._scripted_index += 1
        elif self._response is not None:
            response = self._response
        else:
            response = AgentAuthoredResponsePayload(status="succeeded", summary="deterministic fake response", findings=self._findings, issues=self._issues, constraint_requests=self._constraint_requests, change_proposals=())
        try:
            response = response_model_for_contract(request.response_contract).model_validate(response.model_dump(mode="json"))
        except Exception as exc:
            raise AgentAdapterExecutionError("fake authored response failed selected response contract", provenance=provenance, failure_kind="structured_validation") from exc
        return AgentAdapterExecutionOutcome(authored_response=response, provenance=provenance, execution_metadata={"authored_response_hash": f"sha256:{__import__('hashlib').sha256(__import__('json').dumps(response.model_dump(mode='json'), sort_keys=True, separators=(',', ':')).encode()).hexdigest()}"})

    def provenance(self) -> AgentAdapterProvenance:
        return AgentAdapterProvenance(adapter_name=self.identity.adapter_name, adapter_version=self.identity.adapter_version, provider="test", transport="in-process")
