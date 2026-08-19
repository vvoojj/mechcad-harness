import json

import pytest


def _request_model():
    from mechcad_harness.agents.models import AgentContext, AgentIdentity, AgentInvocationRequest
    from mechcad_harness.models import DesignState

    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    return AgentInvocationRequest(invocation_id="INV", agent=identity, project_id="PRJ", run_id="RUN", task_id="TASK", bound_revision=1, bound_state_hash="hash", context=AgentContext(project_id="PRJ", run_id="RUN", task_id="TASK", revision=1, state_hash="hash", design_state=DesignState(id="DES", revision=1), task_objective="test", task_instructions="test"), requested_output_schema_version="1.0", context_hash="hash")


def _valid_structured_output(summary="structured"):
    return {"status": "succeeded", "summary": summary, "findings": [], "change_proposals": [], "issues": [], "constraint_requests": []}


def test_response_mode_defaults_to_native():
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig, OpenCodeResponseMode

    config = OpenCodeAdapterConfig(project_directory="E:/repo/mechcad-harness", provider_id="screenpipe", model_id="gpt-5.6-luna")

    assert config.response_mode == OpenCodeResponseMode.NATIVE_JSON_SCHEMA


def test_validated_text_response_mode_is_explicitly_selectable():
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig, OpenCodeResponseMode

    config = OpenCodeAdapterConfig(project_directory="E:/repo/mechcad-harness", provider_id="screenpipe", model_id="gpt-5.6-luna", response_mode=OpenCodeResponseMode.VALIDATED_JSON_TEXT)

    assert config.response_mode == OpenCodeResponseMode.VALIDATED_JSON_TEXT


def test_unknown_response_mode_is_rejected():
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig

    with pytest.raises(ValueError, match="unsupported OpenCode response mode"):
        OpenCodeAdapterConfig(project_directory="E:/repo/mechcad-harness", provider_id="screenpipe", model_id="gpt-5.6-luna", response_mode="fallback")


def test_adapter_provenance_carries_response_mode_and_schema_hash():
    from mechcad_harness.agents.models import AgentAdapterProvenance

    provenance = AgentAdapterProvenance(adapter_name="test", adapter_version="1.0", provider="screenpipe", transport="test", response_mode="validated_json_text", schema_hash="sha256:schema")

    assert provenance.response_mode == "validated_json_text"
    assert provenance.schema_hash == "sha256:schema"


def test_contract_schema_and_runtime_validation_use_the_same_selected_model(monkeypatch):
    from mechcad_harness.agents.models import AgentAuthoredResponseContract
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig, OpenCodeAgentAdapter, OpenCodeResponseMode

    response = {"info": {"id": "msg-text", "providerID": "screenpipe", "modelID": "gpt-5.6-luna"}, "parts": [{"type": "text", "text": _valid_authored_text(tool_requests=[])}]}
    adapter, calls = _text_adapter_with_response(monkeypatch, response)
    adapter.config = OpenCodeAdapterConfig(project_directory="E:/repo/mechcad-harness", provider_id="screenpipe", model_id="gpt-5.6-luna", response_mode=OpenCodeResponseMode.VALIDATED_JSON_TEXT)
    outcome = adapter.invoke(_request_model().model_copy(update={"response_contract": AgentAuthoredResponseContract.TOOL_REQUESTS_FORBIDDEN}))
    prompt = calls[1][2]["parts"][0]["text"]
    assert '"maxItems":0' in prompt
    assert outcome.authored_response.tool_requests == ()
    assert outcome.provenance.schema_hash


def test_native_json_schema_uses_forbidden_contract_schema(monkeypatch):
    from mechcad_harness.agents.models import AgentAuthoredResponseContract
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig, OpenCodeAgentAdapter

    adapter = OpenCodeAgentAdapter(OpenCodeAdapterConfig(project_directory="E:/repo/mechcad-harness", provider_id="screenpipe", model_id="gpt-5.6-luna"), "secret")
    monkeypatch.setattr(adapter, "health", lambda: type("Health", (), {"healthy": True, "server_version": "1.18.18", "message": None})())
    calls = []

    def request(method, path, payload=None):
        calls.append((method, path, payload))
        if path == "/session":
            return {"id": "ses-native"}
        return {"info": {"id": "msg-native", "providerID": "screenpipe", "modelID": "gpt-5.6-luna", "structured_output": {"status": "succeeded", "summary": "B", "findings": [], "issues": [], "constraint_requests": [], "change_proposals": [], "tool_requests": []}}, "parts": []}

    monkeypatch.setattr(adapter.transport, "request", request)
    request_model = _request_model().model_copy(update={"response_contract": AgentAuthoredResponseContract.TOOL_REQUESTS_FORBIDDEN})
    outcome = adapter.invoke(request_model)
    assert calls[1][2]["format"]["schema"]["properties"]["tool_requests"]["maxItems"] == 0
    assert outcome.authored_response.tool_requests == ()


def _valid_authored_text(summary="text", **overrides):
    value = {"status": "succeeded", "summary": summary, "findings": [], "issues": [], "constraint_requests": [], "change_proposals": []}
    value.update(overrides)
    return json.dumps(value, separators=(",", ":"))


def _text_adapter_with_response(monkeypatch, response):
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig, OpenCodeAgentAdapter, OpenCodeResponseMode

    adapter = OpenCodeAgentAdapter(OpenCodeAdapterConfig(project_directory="E:/repo/mechcad-harness", provider_id="screenpipe", model_id="gpt-5.6-luna", response_mode=OpenCodeResponseMode.VALIDATED_JSON_TEXT), "secret")
    monkeypatch.setattr(adapter, "health", lambda: type("Health", (), {"healthy": True, "server_version": "1.18.18", "message": None})())
    calls = []

    def request(method, path, payload=None):
        calls.append((method, path, payload))
        if path == "/session":
            return {"id": "ses-text"}
        return response

    monkeypatch.setattr(adapter.transport, "request", request)
    return adapter, calls


def test_validated_text_accepts_one_exact_json_document(monkeypatch):
    adapter, _ = _text_adapter_with_response(monkeypatch, {"info": {"id": "msg-text", "providerID": "screenpipe", "modelID": "gpt-5.6-luna"}, "parts": [{"type": "text", "text": _valid_authored_text()}]})

    outcome = adapter.invoke(_request_model())

    assert outcome.authored_response.summary == "text"


def test_validated_text_accepts_surrounding_json_whitespace(monkeypatch):
    adapter, _ = _text_adapter_with_response(monkeypatch, {"info": {"id": "msg-text", "providerID": "screenpipe", "modelID": "gpt-5.6-luna"}, "parts": [{"type": "text", "text": "  \n" + _valid_authored_text() + "\t\n"}]})

    assert adapter.invoke(_request_model()).authored_response.status.value == "succeeded"


def test_validated_text_omits_native_format_and_does_not_require_structured_output(monkeypatch):
    adapter, calls = _text_adapter_with_response(monkeypatch, {"info": {"id": "msg-text", "providerID": "screenpipe", "modelID": "gpt-5.6-luna"}, "parts": [{"type": "text", "text": _valid_authored_text()}]})

    adapter.invoke(_request_model())

    payload = calls[1][2]
    assert "format" not in payload
    assert "OUTPUT CONTRACT" in payload["parts"][0]["text"]


@pytest.mark.parametrize("text", [
    "",
    "not json",
    "```json\n" + _valid_authored_text() + "\n```",
    "prefix " + _valid_authored_text(),
    _valid_authored_text() + " suffix",
    _valid_authored_text() + _valid_authored_text(),
])
def test_validated_text_rejects_non_whole_document_text(monkeypatch, text):
    from mechcad_harness.agents.models import AgentAdapterExecutionError

    adapter, _ = _text_adapter_with_response(monkeypatch, {"info": {"id": "msg-text", "providerID": "screenpipe", "modelID": "gpt-5.6-luna"}, "parts": [{"type": "text", "text": text}]})

    with pytest.raises(AgentAdapterExecutionError):
        adapter.invoke(_request_model())


def test_validated_text_rejects_extra_root_field(monkeypatch):
    from mechcad_harness.agents.models import AgentAdapterExecutionError

    adapter, _ = _text_adapter_with_response(monkeypatch, {"info": {"id": "msg-text", "providerID": "screenpipe", "modelID": "gpt-5.6-luna"}, "parts": [{"type": "text", "text": _valid_authored_text(extra="forbidden")}]})

    with pytest.raises(AgentAdapterExecutionError):
        adapter.invoke(_request_model())


def test_validated_text_rejects_nested_canonical_constraint_request(monkeypatch):
    from mechcad_harness.agents.models import AgentAdapterExecutionError

    adapter, _ = _text_adapter_with_response(monkeypatch, {"info": {"id": "msg-text", "providerID": "screenpipe", "modelID": "gpt-5.6-luna"}, "parts": [{"type": "text", "text": _valid_authored_text(constraint_requests=[{"id": "CR-1", "description": "legacy"}])}]})

    with pytest.raises(AgentAdapterExecutionError):
        adapter.invoke(_request_model())


def test_validated_text_accepts_plain_string_constraint_request(monkeypatch):
    adapter, _ = _text_adapter_with_response(monkeypatch, {"info": {"id": "msg-text", "providerID": "screenpipe", "modelID": "gpt-5.6-luna"}, "parts": [{"type": "text", "text": _valid_authored_text(constraint_requests=["missing backlash input"])}]})

    assert adapter.invoke(_request_model()).authored_response.constraint_requests == ("missing backlash input",)


def test_validated_text_rejects_tool_parts(monkeypatch):
    from mechcad_harness.agents.models import AgentAdapterExecutionError

    adapter, _ = _text_adapter_with_response(monkeypatch, {"info": {"id": "msg-text", "providerID": "screenpipe", "modelID": "gpt-5.6-luna"}, "parts": [{"type": "tool", "tool": "bash"}, {"type": "text", "text": _valid_authored_text()}]})

    with pytest.raises(AgentAdapterExecutionError):
        adapter.invoke(_request_model())


def test_validated_text_error_precedes_valid_text(monkeypatch):
    from mechcad_harness.agents.models import AgentAdapterExecutionError

    adapter, _ = _text_adapter_with_response(monkeypatch, {"info": {"id": "msg-text", "providerID": "screenpipe", "modelID": "gpt-5.6-luna", "error": {"name": "ProviderError", "data": {"message": "provider failed"}}}, "parts": [{"type": "text", "text": _valid_authored_text()}]})

    with pytest.raises(AgentAdapterExecutionError) as error:
        adapter.invoke(_request_model())

    assert error.value.failure_kind == "text_protocol"
    assert error.value.provenance.validation_diagnostics["failure_layer"] == "OPENCODE_TEXT_RESPONSE_ERROR"
    assert error.value.provenance.validation_diagnostics["error_name"] == "ProviderError"


def _adapter_with_response(monkeypatch, response):
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig, OpenCodeAgentAdapter

    adapter = OpenCodeAgentAdapter(OpenCodeAdapterConfig(project_directory="E:/repo/mechcad-harness", provider_id="screenpipe", model_id="gpt-5.6-luna"), "secret")
    monkeypatch.setattr(adapter, "health", lambda: type("Health", (), {"healthy": True, "server_version": "1.18.18", "message": None})())

    def request(method, path, payload=None):
        if path == "/session":
            return {"id": "ses-test"}
        return response

    monkeypatch.setattr(adapter.transport, "request", request)
    return adapter


def test_json_schema_uses_valid_structured_output_and_ignores_text(monkeypatch):
    adapter = _adapter_with_response(monkeypatch, {"info": {"id": "msg-test", "providerID": "screenpipe", "modelID": "gpt-5.6-luna", "structured_output": _valid_structured_output()}, "parts": [{"type": "text", "text": '{"status":"succeeded","summary":"text is not authoritative","findings":[],"change_proposals":[],"issues":[],"constraint_requests":[]}'}]})

    outcome = adapter.invoke(_request_model())

    assert outcome.authored_response.summary == "structured"
    assert outcome.execution_metadata["authored_response_hash"].startswith("sha256:")


@pytest.mark.parametrize("text", [
    '{"status":"succeeded","summary":"valid-looking","findings":[],"change_proposals":[],"issues":[],"constraint_requests":[]}',
    "not json",
])
def test_structured_output_error_fails_closed_even_when_text_is_valid_or_invalid(monkeypatch, text):
    from mechcad_harness.agents.models import AgentAdapterExecutionError

    adapter = _adapter_with_response(monkeypatch, {"info": {"id": "msg-test", "providerID": "screenpipe", "modelID": "gpt-5.6-luna", "error": {"name": "StructuredOutputError", "data": {"message": "Model did not produce structured output", "retries": 0}}}, "parts": [{"type": "text", "text": text}]})

    with pytest.raises(AgentAdapterExecutionError) as error:
        adapter.invoke(_request_model())

    assert error.value.failure_kind == "structured_output_rejected"
    diagnostics = error.value.provenance.validation_diagnostics
    assert diagnostics["failure_layer"] == "OPENCODE_STRUCTURED_OUTPUT_REJECTED"
    assert diagnostics["error_name"] == "StructuredOutputError"
    assert diagnostics["error_message"] == "Model did not produce structured output"
    assert diagnostics["retry_count"] == 0
    assert text not in error.value.provenance.model_dump_json()


def test_missing_structured_output_without_error_fails_closed(monkeypatch):
    from mechcad_harness.agents.models import AgentAdapterExecutionError

    adapter = _adapter_with_response(monkeypatch, {"info": {"id": "msg-test", "providerID": "screenpipe", "modelID": "gpt-5.6-luna"}, "parts": [{"type": "text", "text": '{"status":"succeeded","summary":"fallback","findings":[],"change_proposals":[],"issues":[],"constraint_requests":[]}'}]})

    with pytest.raises(AgentAdapterExecutionError) as error:
        adapter.invoke(_request_model())

    assert error.value.failure_kind == "structured_output_missing"
    assert error.value.provenance.validation_diagnostics["failure_layer"] == "STRUCTURED_OUTPUT_MISSING"


def test_invalid_structured_output_is_validation_failure_without_text_fallback(monkeypatch):
    from mechcad_harness.agents.models import AgentAdapterExecutionError

    adapter = _adapter_with_response(monkeypatch, {"info": {"id": "msg-test", "providerID": "screenpipe", "modelID": "gpt-5.6-luna", "structured_output": {"status": "succeeded", "summary": 42}}, "parts": [{"type": "text", "text": '{"status":"succeeded","summary":"valid fallback","findings":[],"change_proposals":[],"issues":[],"constraint_requests":[]}'}]})

    with pytest.raises(AgentAdapterExecutionError) as error:
        adapter.invoke(_request_model())

    assert error.value.failure_kind == "structured_validation"
    assert error.value.provenance.validation_diagnostics["failure_layer"] == "PYDANTIC_AUTHORED_RESPONSE_VALIDATION_FAILURE"


def test_valid_structured_output_wins_over_different_valid_text(monkeypatch):
    adapter = _adapter_with_response(monkeypatch, {"info": {"id": "msg-test", "providerID": "screenpipe", "modelID": "gpt-5.6-luna", "structured_output": _valid_structured_output("authoritative")}, "parts": [{"type": "text", "text": '{"status":"succeeded","summary":"different","findings":[],"change_proposals":[],"issues":[],"constraint_requests":[]}'}]})

    assert adapter.invoke(_request_model()).authored_response.summary == "authoritative"


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
        return {"info": {"id": "msg-test", "providerID": "screenpipe", "modelID": "gpt-5.6-terra", "structured_output": _valid_structured_output("ok")}, "parts": [{"type": "text", "text": '{"status":"succeeded","summary":"text","findings":[],"change_proposals":[],"issues":[],"constraint_requests":[]}' }]}
    monkeypatch.setattr(adapter.transport, "request", request)
    from mechcad_harness.agents.models import AgentContext, AgentIdentity, AgentInvocationRequest
    from mechcad_harness.models import DesignState
    identity = AgentIdentity(agent_name="mechcad-test-agent", agent_version="1.0", role="test", protocol_version="1.0")
    req = AgentInvocationRequest(invocation_id="INV", agent=identity, project_id="PRJ", run_id="RUN", task_id="TASK", bound_revision=1, bound_state_hash="hash", context=AgentContext(project_id="PRJ", run_id="RUN", task_id="TASK", revision=1, state_hash="hash", design_state=DesignState(id="DES", revision=1), task_objective="test", task_instructions="test"), requested_output_schema_version="1.0", context_hash="hash")
    outcome = adapter.invoke(req)
    assert outcome.authored_response.status.value == "succeeded"
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
        return {"info": {"id": "msg-test", "providerID": "screenpipe", "modelID": "gpt-5.6-luna", "structured_output": {"status": "SUCCEEDED", "private": "do not persist"}}, "parts": [{"type": "text", "text": "ignored"}]}
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
