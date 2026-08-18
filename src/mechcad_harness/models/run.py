from pydantic import Field

from .common import Model


class RunManifest(Model):
    id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    revision: int = Field(gt=0)
