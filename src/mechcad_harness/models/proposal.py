from enum import StrEnum

from pydantic import Field

from .common import Model, StateBinding


class ProposalStatus(StrEnum):
    DRAFT = "draft"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ChangeOperation(Model):
    target_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    value: str | None = None


class ChangeProposal(StateBinding):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: ProposalStatus
    operations: list[ChangeOperation] = Field(default_factory=list)


class ChangeSet(StateBinding):
    id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    operations: list[ChangeOperation] = Field(default_factory=list)


class ConstraintRequest(StateBinding):
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
