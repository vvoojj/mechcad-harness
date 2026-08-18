from collections.abc import Iterable

from .models import AgentAdapterExecutionError, AgentAdapterExecutionOutcome, AgentAdapterIdentity, AgentAdapterProvenance, AgentIdentity, AgentInvocationRequest, AgentResponsePayload


class FakeAgentAdapter:
    def __init__(self, agent_identity: AgentIdentity, *, findings: Iterable[str] = (), response: AgentResponsePayload | None = None, error: Exception | None = None):
        self.agent_identity = agent_identity
        self.identity = AgentAdapterIdentity(adapter_name="fake-agent-adapter", adapter_version="1.0")
        self._findings = tuple(findings)
        self._response = response
        self._error = error
        self.last_request: AgentInvocationRequest | None = None

    def invoke(self, request: AgentInvocationRequest) -> AgentAdapterExecutionOutcome:
        self.last_request = request
        provenance = self.provenance()
        if self._error is not None:
            raise AgentAdapterExecutionError(str(self._error), provenance=provenance, failure_kind="fake_failure") from self._error
        if self._response is not None:
            response = self._response
        else:
            response = AgentResponsePayload(summary="deterministic fake response", findings=self._findings)
        return AgentAdapterExecutionOutcome(response=response, provenance=provenance)

    def provenance(self) -> AgentAdapterProvenance:
        return AgentAdapterProvenance(adapter_name=self.identity.adapter_name, adapter_version=self.identity.adapter_version, provider="test", transport="in-process")
