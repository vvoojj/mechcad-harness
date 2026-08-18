import pytest


def test_loopback_url_policy():
    from mechcad_harness.agents.opencode import validate_loopback_url

    assert validate_loopback_url("http://127.0.0.1:4096") == "http://127.0.0.1:4096"
    assert validate_loopback_url("http://localhost:4096") == "http://localhost:4096"
    with pytest.raises(ValueError):
        validate_loopback_url("https://example.com:4096")
    with pytest.raises(ValueError):
        validate_loopback_url("http://8.8.8.8:4096")


def test_config_does_not_persist_password():
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig

    config = OpenCodeAdapterConfig(project_directory="E:\\repo\\mechcad-harness", provider_id="screenpipe", model_id="gpt-5.6-luna")
    assert not hasattr(config, "password")
    assert config.project_directory == "E:/repo/mechcad-harness"


def test_session_selected_mode_omits_message_model(monkeypatch):
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig, OpenCodeAgentAdapter, OpenCodeModelSelection

    config = OpenCodeAdapterConfig(project_directory="E:/repo/mechcad-harness", provider_id=None, model_id=None, model_selection=OpenCodeModelSelection.SESSION_SELECTED)
    adapter = OpenCodeAgentAdapter(config, "secret")
    calls = []
    monkeypatch.setattr(adapter, "health", lambda: type("Health", (), {"healthy": True, "server_version": "1.18.18", "message": None})())
    def request(method, path, payload=None):
        calls.append((method, path, payload))
        if path == "/session":
            return {"id": "ses-test"}
        return {"info": {"id": "msg-test", "providerID": "screenpipe", "modelID": "gpt-5.6-terra"}, "parts": [{"type": "text", "text": '{"status":"succeeded","summary":"ok","findings":[],"change_proposals":[],"issues":[],"constraint_requests":[]}' }]}
    monkeypatch.setattr(adapter.transport, "request", request)
    from mechcad_harness.agents.models import AgentContext, AgentIdentity, AgentInvocationRequest
    from mechcad_harness.models import DesignState
    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    req = AgentInvocationRequest(invocation_id="INV", agent=identity, project_id="PRJ", run_id="RUN", task_id="TASK", bound_revision=1, bound_state_hash="hash", context=AgentContext(project_id="PRJ", run_id="RUN", task_id="TASK", revision=1, state_hash="hash", design_state=DesignState(id="DES", revision=1), task_objective="test", task_instructions="test"), requested_output_schema_version="1.0", context_hash="hash")
    outcome = adapter.invoke(req)
    assert outcome.response.status.value == "succeeded"
    assert "model" not in calls[1][2]
    assert outcome.provenance.provider == "screenpipe"
    assert outcome.provenance.model == "gpt-5.6-terra"


def test_structured_validation_failure_retains_execution_diagnostics(monkeypatch):
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig, OpenCodeAgentAdapter
    from mechcad_harness.agents.models import AgentContext, AgentIdentity, AgentInvocationRequest, AgentAdapterExecutionError
    from mechcad_harness.models import DesignState

    adapter = OpenCodeAgentAdapter(OpenCodeAdapterConfig(project_directory="E:/repo/mechcad-harness", provider_id="screenpipe", model_id="gpt-5.6-luna"), "secret")
    monkeypatch.setattr(adapter, "health", lambda: type("Health", (), {"healthy": True, "server_version": "1.18.18", "message": None})())
    def request(method, path, payload=None):
        if path == "/session":
            return {"id": "ses-test"}
        return {"info": {"id": "msg-test", "providerID": "screenpipe", "modelID": "gpt-5.6-luna"}, "parts": [{"type": "text", "text": '{"status":"SUCCEEDED","private":"do not persist"}'}]}
    monkeypatch.setattr(adapter.transport, "request", request)
    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    request_model = AgentInvocationRequest(invocation_id="INV", agent=identity, project_id="PRJ", run_id="RUN", task_id="TASK", bound_revision=1, bound_state_hash="hash", context=AgentContext(project_id="PRJ", run_id="RUN", task_id="TASK", revision=1, state_hash="hash", design_state=DesignState(id="DES", revision=1), task_objective="test", task_instructions="test"), requested_output_schema_version="1.0", context_hash="hash")
    with pytest.raises(AgentAdapterExecutionError) as error:
        adapter.invoke(request_model)
    provenance = error.value.provenance
    assert provenance.server_version == "1.18.18"
    assert provenance.session_id == "ses-test"
    assert provenance.message_id == "msg-test"
    assert provenance.provider == "screenpipe"
    assert provenance.model == "gpt-5.6-luna"
    assert provenance.request_hash.startswith("sha256:")
    assert provenance.validation_diagnostics["top_level_keys"] == ["private", "status"]
    assert provenance.validation_diagnostics["status"] == "SUCCEEDED"
    assert provenance.validation_diagnostics["status_type"] == "str"
    assert "private" in provenance.validation_diagnostics["unexpected_fields"]
    assert "status" not in provenance.validation_diagnostics["missing_fields"]
    serialized = provenance.model_dump_json()
    assert "do not persist" not in serialized
    assert "Authorization" not in serialized
    assert "secret" not in serialized


def test_windows_project_directory_is_normalized_for_transport():
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig

    config = OpenCodeAdapterConfig(project_directory="E:\\repo\\mechcad-harness", provider_id="screenpipe", model_id="gpt-5.6-luna")
    assert config.project_directory == "E:/repo/mechcad-harness"


def test_transport_request_includes_project_directory_header(monkeypatch):
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig, OpenCodeHttpTransport

    captured = {}
    class Response:
        status = 200
        def read(self, size):
            return b'{}'
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
    def fake_urlopen(request, timeout):
        captured["headers"] = dict(request.headers)
        captured["timeout"] = timeout
        return Response()
    monkeypatch.setattr("mechcad_harness.agents.opencode.urlopen", fake_urlopen)
    config = OpenCodeAdapterConfig(project_directory="E:/repo/mechcad-harness", provider_id="screenpipe", model_id="gpt-5.6-luna", request_timeout_seconds=7)
    OpenCodeHttpTransport(config, "secret").request("GET", "/project/current")
    assert captured["headers"]["X-opencode-directory"] == "E:/repo/mechcad-harness"
    assert captured["timeout"] == 7


def test_structured_response_extraction_rejects_tool_parts():
    from mechcad_harness.agents.opencode import OpenCodeAgentAdapter, OpenCodeStructuredOutputError

    with pytest.raises(OpenCodeStructuredOutputError):
        OpenCodeAgentAdapter._extract_response({"parts": [{"type": "tool", "tool": "bash"}]})


def test_prompt_contains_context_but_not_credentials():
    from mechcad_harness.agents.models import AgentContext, AgentIdentity, AgentInvocationRequest
    from mechcad_harness.agents.opencode import OpenCodeAgentAdapter
    from mechcad_harness.models import DesignState

    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    request = AgentInvocationRequest(invocation_id="INV-1", agent=identity, project_id="PRJ-1", run_id="RUN-1", task_id="TASK-1", bound_revision=1, bound_state_hash="sha256:state", context=AgentContext(project_id="PRJ-1", run_id="RUN-1", task_id="TASK-1", revision=1, state_hash="sha256:state", design_state=DesignState(id="DES-1", revision=1), task_objective="test", task_instructions="test"), requested_output_schema_version="1.0", context_hash="sha256:context")
    prompt = OpenCodeAgentAdapter._prompt(request)
    assert "sha256:state" in prompt
    assert "password" not in prompt.lower()


def test_prompt_explicitly_separates_input_and_plain_string_findings_contract():
    from mechcad_harness.agents.models import AgentContext, AgentIdentity, AgentInvocationRequest
    from mechcad_harness.agents.opencode import OpenCodeAgentAdapter
    from mechcad_harness.models import DesignState

    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    request = AgentInvocationRequest(invocation_id="INV-1", agent=identity, project_id="PRJ-1", run_id="RUN-1", task_id="TASK-1", bound_revision=1, bound_state_hash="sha256:state", context=AgentContext(project_id="PRJ-1", run_id="RUN-1", task_id="TASK-1", revision=1, state_hash="sha256:state", design_state=DesignState(id="DES-1", revision=1), task_objective="test", task_instructions="test"), requested_output_schema_version="1.0", context_hash="sha256:context")
    prompt = OpenCodeAgentAdapter._prompt(request)
    assert "INPUT CONTEXT" in prompt
    assert "OUTPUT CONTRACT" in prompt
    assert "findings field is an array of plain JSON strings" in prompt
    assert "Do not return objects inside findings" in prompt
    assert "structured finding" not in prompt.lower()
    assert "severity" not in prompt.lower()
    assert "category" not in prompt.lower()
