import pytest


def test_opencode_adapter_can_be_registered_exactly():
    from mechcad_harness.agents import AgentIdentity, AgentRegistry
    from mechcad_harness.agents.opencode import OpenCodeAgentAdapter, OpenCodeAdapterConfig

    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    adapter = OpenCodeAgentAdapter(OpenCodeAdapterConfig(project_directory="E:/repo/mechcad-harness", provider_id="screenpipe", model_id="gpt-5.6-luna", agent_name="mechcad-test-agent"), "secret")
    registry = AgentRegistry()
    registry.register(identity, adapter)
    assert registry.get("mechcad-test-agent", "1.0") is adapter
    with pytest.raises(LookupError):
        registry.get("mechcad-test-agent", "latest")


def test_open_code_config_requires_explicit_project_directory():
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig

    with pytest.raises(TypeError):
        OpenCodeAdapterConfig(provider_id="screenpipe", model_id="gpt-5.6-luna")
