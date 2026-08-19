import pytest


def test_authored_response_requires_all_wire_fields_and_forbids_canonical_fields():
    from mechcad_harness.agents.models import AgentAuthoredResponsePayload

    schema = AgentAuthoredResponsePayload.model_json_schema()
    assert set(schema["required"]) == {"status", "summary", "findings", "issues", "constraint_requests", "change_proposals"}
    assert schema["additionalProperties"] is False
    assert schema["properties"]["status"]["$ref"].endswith("AgentResponseStatus")
    assert schema["properties"]["findings"]["items"] == {"type": "string"}
    assert schema["properties"]["issues"]["items"] == {"type": "string"}
    assert schema["properties"]["constraint_requests"]["items"] == {"type": "string"}
    with pytest.raises(Exception):
        AgentAuthoredResponsePayload.model_validate({
            "status": "succeeded",
            "summary": "ok",
            "findings": [],
            "issues": [],
            "constraint_requests": [],
            "change_proposals": [],
            "revision": 1,
        })


def test_authored_torque_request_schema_is_strict_and_reuses_torque_input():
    from mechcad_harness.agents.models import AgentAuthoredResponsePayload

    schema = AgentAuthoredResponsePayload.model_json_schema()
    draft = schema["$defs"]["TransmissionTorqueToolRequestDraft"]
    capability = draft["properties"]["capability"]
    arguments = schema["$defs"]["TorqueInput"]

    assert capability["const"] == "transmission.torque"
    assert "capability" in draft["required"]
    assert arguments["required"] == ["force_n", "lever_arm_m", "safety_factor"]
    assert arguments["additionalProperties"] is False
    assert all(arguments["properties"][field]["exclusiveMinimum"] == 0 for field in arguments["required"])


def test_authored_torque_request_rejects_noncanonical_capability_and_arguments():
    import pytest
    from pydantic import ValidationError

    from mechcad_harness.agents.models import AgentToolRequestDraft

    valid = {"capability": "transmission.torque", "arguments": {"force_n": 10, "lever_arm_m": 0.2, "safety_factor": 2.0}}
    assert AgentToolRequestDraft.model_validate(valid).arguments.force_n == 10

    invalid = [
        {"capability": "deterministic_torque_calculation", "arguments": valid["arguments"]},
        {"capability": "torque", "arguments": valid["arguments"]},
        {"arguments": valid["arguments"]},
        {"capability": "transmission.torque", "arguments": {"design_safety_factor": 2.0, "effective_lever_arm_m": 0.2, "tangential_force_N": 10}},
        {"capability": "transmission.torque", "arguments": {**valid["arguments"], "extra": 1}},
        {"capability": "transmission.torque", "arguments": {"lever_arm_m": 0.2, "safety_factor": 2.0}},
        {"capability": "transmission.torque", "arguments": {"force_n": 10, "safety_factor": 2.0}},
        {"capability": "transmission.torque", "arguments": {"force_n": 10, "lever_arm_m": 0.2}},
        {"capability": "transmission.torque", "arguments": {"force_n": 0, "lever_arm_m": 0.2, "safety_factor": 2.0}},
        {"capability": "transmission.torque", "arguments": {"force_n": 10, "lever_arm_m": 0, "safety_factor": 2.0}},
        {"capability": "transmission.torque", "arguments": {"force_n": 10, "lever_arm_m": 0.2, "safety_factor": 0}},
    ]
    for payload in invalid:
        with pytest.raises(ValidationError):
            AgentToolRequestDraft.model_validate(payload)


def test_no_tool_contract_rejects_requests_and_generates_zero_item_schema():
    import pytest
    from pydantic import ValidationError

    from mechcad_harness.agents.models import AgentAuthoredNoToolResponsePayload, AgentAuthoredResponseContract, response_model_for_contract

    valid = {"status": "succeeded", "summary": "B", "findings": [], "issues": [], "constraint_requests": [], "change_proposals": []}
    assert response_model_for_contract(AgentAuthoredResponseContract.TOOL_REQUESTS_ALLOWED) is not AgentAuthoredNoToolResponsePayload
    assert AgentAuthoredNoToolResponsePayload.model_validate(valid).tool_requests == ()
    assert AgentAuthoredNoToolResponsePayload.model_validate({**valid, "tool_requests": []}).tool_requests == ()
    schema = AgentAuthoredNoToolResponsePayload.model_json_schema()
    assert schema["properties"]["tool_requests"]["maxItems"] == 0
    with pytest.raises(ValidationError):
            AgentAuthoredNoToolResponsePayload.model_validate({**valid, "tool_requests": [{"capability": "transmission.torque", "arguments": {"force_n": 10, "lever_arm_m": 0.2, "safety_factor": 2.0}}]})


def test_response_contract_materialization_is_canonical_and_distinct():
    from mechcad_harness.agents.models import AgentAuthoredResponseContract, materialize_response_contract

    allowed = materialize_response_contract(AgentAuthoredResponseContract.TOOL_REQUESTS_ALLOWED)
    forbidden = materialize_response_contract(AgentAuthoredResponseContract.TOOL_REQUESTS_FORBIDDEN)
    assert allowed.schema_hash == materialize_response_contract(AgentAuthoredResponseContract.TOOL_REQUESTS_ALLOWED).schema_hash
    assert allowed.schema_hash != forbidden.schema_hash
    assert allowed.schema_hash == f"sha256:{__import__('hashlib').sha256(allowed.schema_json.encode()).hexdigest()}"
    assert forbidden.schema_hash == f"sha256:{__import__('hashlib').sha256(forbidden.schema_json.encode()).hexdigest()}"


def test_materialization_preserves_semantics_and_binds_trusted_fields():
    from mechcad_harness.agents.materialization import materialize_agent_response
    from mechcad_harness.agents.models import AgentAuthoredResponsePayload, AgentIdentity, AgentInvocationRequest, AgentContext
    from mechcad_harness.models import DesignState

    identity = AgentIdentity(agent_name="mechcad-transmission", agent_version="1.0", role="transmission_engineer", protocol_version="1.0")
    request = AgentInvocationRequest(
        invocation_id="INV-MATERIALIZE",
        agent=identity,
        project_id="PRJ-1",
        run_id="RUN-1",
        task_id="TASK-1",
        bound_revision=3,
        bound_state_hash="sha256:bound",
        context=AgentContext(project_id="PRJ-1", run_id="RUN-1", task_id="TASK-1", revision=3, state_hash="sha256:bound", design_state=DesignState(id="DES-1", revision=3), task_objective="test", task_instructions="test"),
        requested_output_schema_version="1.0",
        context_hash="sha256:context",
    )
    authored = AgentAuthoredResponsePayload(status="succeeded", summary="summary", findings=("finding",), issues=("conflict",), constraint_requests=("missing input",), change_proposals=())
    response = materialize_agent_response(request=request, agent=identity, authored=authored)
    assert response.findings == ("finding",)
    assert response.issues[0].title == "conflict"
    assert response.issues[0].revision == 3
    assert response.issues[0].state_hash == "sha256:bound"
    assert response.constraint_requests[0].description == "missing input"
    assert response.constraint_requests[0].revision == 3
    assert response.constraint_requests[0].state_hash == "sha256:bound"
    assert response.issues[0].id.startswith("ISSUE-")
    assert response.constraint_requests[0].id.startswith("CR-")


def test_materialized_ids_are_deterministic_and_invocation_bound():
    from mechcad_harness.agents.materialization import materialize_agent_response
    from mechcad_harness.agents.models import AgentAuthoredResponsePayload, AgentIdentity, AgentInvocationRequest, AgentContext
    from mechcad_harness.models import DesignState

    identity = AgentIdentity(agent_name="agent", agent_version="1.0", role="test", protocol_version="1.0")
    def request(invocation_id):
        return AgentInvocationRequest(invocation_id=invocation_id, agent=identity, project_id="PRJ", run_id="RUN", task_id="TASK", bound_revision=1, bound_state_hash="hash", context=AgentContext(project_id="PRJ", run_id="RUN", task_id="TASK", revision=1, state_hash="hash", design_state=DesignState(id="DES", revision=1), task_objective="test", task_instructions="test"), requested_output_schema_version="1.0", context_hash="context")
    authored = AgentAuthoredResponsePayload(status="succeeded", summary="", findings=(), issues=("one", "two"), constraint_requests=(), change_proposals=())
    first = materialize_agent_response(request=request("INV-1"), agent=identity, authored=authored)
    second = materialize_agent_response(request=request("INV-1"), agent=identity, authored=authored)
    other = materialize_agent_response(request=request("INV-2"), agent=identity, authored=authored)
    assert [item.id for item in first.issues] == [item.id for item in second.issues]
    assert first.issues[0].id != first.issues[1].id
    assert first.issues[0].id != other.issues[0].id
