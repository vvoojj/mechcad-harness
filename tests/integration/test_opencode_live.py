import json
import os

import pytest


pytestmark = pytest.mark.skipif(os.getenv("MECHCAD_OPENCODE_LIVE") != "1", reason="OpenCode live validation is opt-in")


def test_desktop_opencode_transport_and_structured_response():
    from mechcad_harness.agents.models import AgentContext, AgentIdentity, AgentInvocationRequest
    from mechcad_harness.agents.opencode import OpenCodeAgentAdapter, OpenCodeAdapterConfig, resolve_opencode_config_from_environment
    from mechcad_harness.models import DesignState

    config, password = resolve_opencode_config_from_environment(provider_id=os.getenv("MECHCAD_OPENCODE_PROVIDER", "screenpipe"), model_id=os.getenv("MECHCAD_OPENCODE_MODEL", "gpt-5.6-luna"), agent_name="mechcad-test-agent")
    adapter = OpenCodeAgentAdapter(config, password)
    health = adapter.health()
    assert health.healthy is True
    assert health.server_version == "1.18.18"
    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    request = AgentInvocationRequest(invocation_id="INV-LIVE", agent=identity, project_id="PRJ-LIVE", run_id="RUN-LIVE", task_id="TASK-LIVE", bound_revision=1, bound_state_hash="sha256:live", context=AgentContext(project_id="PRJ-LIVE", run_id="RUN-LIVE", task_id="TASK-LIVE", revision=1, state_hash="sha256:live", design_state=DesignState(id="DES-LIVE", revision=1), task_objective="Return exactly one JSON object with status succeeded, summary M6A-2A structured round trip successful, and empty findings, change_proposals, issues, and constraint_requests arrays. Do not add any other fields.", task_instructions="Return exactly one JSON object matching AgentResponsePayload. Do not add project, run, task, revision, state_hash, compatible, or reason fields."), requested_output_schema_version="1.0", context_hash="sha256:context")
    result = adapter.invoke(request)
    assert result.authored_response.status.value == "succeeded"
    assert result.provenance.session_id.startswith("ses")
    assert result.provenance.message_id.startswith("msg")
