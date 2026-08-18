from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DependencyRule(Model):
    when: list[str] = Field(min_length=1)
    invalidates: list[str] = Field(min_length=1)


class DependencyEdge(Model):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)


class ChangeImpact(Model):
    changed_paths: tuple[str, ...]
    direct_nodes: tuple[str, ...]
    all_nodes: tuple[str, ...]


class EvidenceFreshness(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    UNKNOWN = "unknown"


class InvalidationRecord(Model):
    project_id: str = Field(min_length=1)
    revision: int = Field(gt=0)
    parent_revision: int | None = Field(default=None, ge=1)
    changeset_id: str | None = None
    changed_paths: tuple[str, ...]
    directly_invalidated_nodes: tuple[str, ...]
    transitively_invalidated_nodes: tuple[str, ...]
    created_at: str = Field(min_length=1)
