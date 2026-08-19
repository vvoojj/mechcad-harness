import hashlib
import uuid

from mechcad_harness.models import ChangeProposal, ConstraintRequest, Issue, IssueStatus, ProposalStatus

from .models import AgentAuthoredResponsePayload, AgentIdentity, AgentInvocationRequest, AgentResponsePayload


def _materialized_id(prefix: str, invocation_id: str, kind: str, ordinal: int) -> str:
    value = uuid.uuid5(uuid.NAMESPACE_URL, f"mechcad:{invocation_id}:{kind}:{ordinal}")
    return f"{prefix}-{value}"


def materialize_agent_response(*, request: AgentInvocationRequest, agent: AgentIdentity, authored: AgentAuthoredResponsePayload) -> AgentResponsePayload:
    issues = tuple(
        Issue(
            id=_materialized_id("ISSUE", request.invocation_id, "issue", index),
            revision=request.bound_revision,
            state_hash=request.bound_state_hash,
            status=IssueStatus.OPEN,
            title=value,
        )
        for index, value in enumerate(authored.issues)
    )
    constraint_requests = tuple(
        ConstraintRequest(
            id=_materialized_id("CR", request.invocation_id, "constraint_request", index),
            revision=request.bound_revision,
            state_hash=request.bound_state_hash,
            description=value,
        )
        for index, value in enumerate(authored.constraint_requests)
    )
    proposals = tuple(
        ChangeProposal(
            id=_materialized_id("CP", request.invocation_id, "change_proposal", index),
            title=draft.title,
            status=ProposalStatus.DRAFT,
            base_revision=request.bound_revision,
            base_state_hash=request.bound_state_hash,
            actor=agent.agent_name,
            operations=draft.operations,
            revision=request.bound_revision,
            state_hash=request.bound_state_hash,
        )
        for index, draft in enumerate(authored.change_proposals)
    )
    return AgentResponsePayload(status=authored.status, summary=authored.summary, findings=authored.findings, issues=issues, constraint_requests=constraint_requests, change_proposals=proposals)
