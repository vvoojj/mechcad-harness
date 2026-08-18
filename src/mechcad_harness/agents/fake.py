from collections.abc import Iterable

from .models import AgentAdapterIdentity, AgentAdapterProvenance, AgentIdentity, AgentInvocationRequest, AgentResponsePayload


class FakeAgentAdapter:
    def __init__(self, agent_identity: AgentIdentity, *, findings: Iterable[str] = (), response: AgentResponsePayload | None = None, error: Exception | None = None):
        self.agent_identity = agent_identity
        self.identity = AgentAdapterIdentity(adapter_name="fake-agent-adapter", adapter_version="1.0")
        self._findings = tuple(findings)
        self._response = response
        self._error = error
        self.last_request: AgentInvocationRequest | None = None

    def invoke(self, request: AgentInvocationRequest) -> AgentResponsePayload:
        self.last_request = request
        if self._error is not None:
            raise self._error
        if self._response is not None:
            return self._response
        return AgentResponsePayload(summary="deterministic fake response", findings=self._findings)

    def provenance(self) -> AgentAdapterProvenance:
        return AgentAdapterProvenance(adapter_name=self.identity.adapter_name, adapter_version=self.identity.adapter_version, provider="test", transport="in-process")
