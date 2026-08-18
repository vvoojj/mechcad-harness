from .models import AgentAdapter, AgentIdentity


class AgentRegistry:
    def __init__(self):
        self._agents: dict[tuple[str, str], AgentAdapter] = {}

    def register(self, identity: AgentIdentity, adapter: AgentAdapter) -> None:
        key = (identity.agent_name, identity.agent_version)
        if key in self._agents:
            raise ValueError(f"duplicate agent registration: {identity.agent_name}@{identity.agent_version}")
        self._agents[key] = adapter

    def get(self, agent_name: str, agent_version: str) -> AgentAdapter:
        try:
            return self._agents[(agent_name, agent_version)]
        except KeyError as exc:
            raise LookupError(f"unknown agent: {agent_name}@{agent_version}") from exc

    def list(self) -> tuple[AgentAdapter, ...]:
        return tuple(self._agents[key] for key in sorted(self._agents))
