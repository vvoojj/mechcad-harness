from datetime import datetime, timezone
from enum import StrEnum

from pydantic import Field

from mechcad_harness.backends.models import BackendProvenance
from mechcad_harness.models.common import Model


class ArtifactType(StrEnum):
    STEP = "step"
    STL = "stl"


class EngineeringArtifact(Model):
    artifact_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    task_id: str | None = None
    artifact_type: ArtifactType
    media_type: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=1)
    size_bytes: int = Field(gt=0)
    producer_tool_name: str = Field(min_length=1)
    producer_tool_version: str = Field(min_length=1)
    backend_provenance: BackendProvenance | None = None
    bound_revision: int = Field(gt=0)
    bound_state_hash: str = Field(min_length=1)
    input_hash: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
