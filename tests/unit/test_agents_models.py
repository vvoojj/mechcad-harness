import pytest


def test_agent_identity_rejects_empty_fields():
    from mechcad_harness.agents.models import AgentIdentity

    with pytest.raises(Exception):
        AgentIdentity(agent_name="", agent_version="1.0", role="test", protocol_version="1.0")


def test_agent_response_uses_existing_domain_models():
    from mechcad_harness.agents.models import AgentResponsePayload
    from mechcad_harness.models import ChangeProposal, ProposalStatus

    proposal = ChangeProposal(id="PROP-1", title="Test", status=ProposalStatus.DRAFT, base_revision=1, base_state_hash="sha256:state", actor="agent")
    response = AgentResponsePayload(change_proposals=(proposal,))
    assert response.change_proposals[0] == proposal


def test_agent_context_requires_exact_binding_fields():
    from mechcad_harness.agents.models import AgentContext

    with pytest.raises(Exception):
        AgentContext(project_id="PRJ-1", run_id="RUN-1", task_id="TASK-1", revision=0, state_hash="hash", design_state={})


def test_agent_result_requires_positive_bound_revision():
    from mechcad_harness.agents.models import AgentResult

    with pytest.raises(Exception):
        AgentResult(result_id="RES-1", invocation_id="INV-1", agent_name="test", agent_version="1.0", project_id="PRJ-1", run_id="RUN-1", task_id="TASK-1", bound_revision=0, bound_state_hash="hash", status="succeeded", response_hash="sha256:x", response={})
