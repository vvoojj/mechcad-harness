from enum import StrEnum

from pydantic import Field

from .common import StateBinding


class IssueStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Issue(StateBinding):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: IssueStatus = IssueStatus.OPEN
