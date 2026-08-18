from enum import StrEnum

from pydantic import Field, model_validator

from .common import Model, StateBinding
from mechcad_harness.changes.operations import ChangeOperation


class ProposalStatus(StrEnum):
    DRAFT = "draft"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ChangeProposal(StateBinding):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: ProposalStatus
    base_revision: int = Field(gt=0)
    base_state_hash: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operations: list[ChangeOperation] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_binding(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            if "revision" in value and "base_revision" not in value:
                value["base_revision"] = value["revision"]
            if "state_hash" in value and "base_state_hash" not in value:
                value["base_state_hash"] = value["state_hash"]
            value.setdefault("actor", "legacy")
            value.setdefault("operations", [])
        return value

    @model_validator(mode="before")
    @classmethod
    def fill_binding(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            value.setdefault("revision", value.get("base_revision"))
            value.setdefault("state_hash", value.get("base_state_hash"))
        return value


class ChangeSet(Model):
    id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    base_revision: int = Field(gt=0)
    base_state_hash: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    status: ProposalStatus
    operations: list[ChangeOperation] = Field(default_factory=list)


class ConstraintRequest(StateBinding):
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
