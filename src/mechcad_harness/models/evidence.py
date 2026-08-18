from pydantic import Field

from .common import StateBinding
from mechcad_harness.backends.models import BackendProvenance


class Evidence(StateBinding):
    id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    producer_type: str | None = None
    producer_name: str | None = None
    producer_version: str | None = None
    producer_result_id: str | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    backend_provenance: BackendProvenance | None = None
