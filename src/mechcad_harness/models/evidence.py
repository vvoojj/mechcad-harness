from pydantic import Field

from .common import StateBinding


class Evidence(StateBinding):
    id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    summary: str = Field(min_length=1)
