from __future__ import annotations

from datetime import datetime

from pydantic import Field

from mechcad_harness.backends.models import BackendProvenance
from mechcad_harness.models.common import Model, utc_now


# Stable identity for the live FreeCAD exact transient measurement provider.
TRANSIENT_MEASUREMENT_PROVIDER_NAME = "freecad-transient-exact"
TRANSIENT_MEASUREMENT_PROVIDER_VERSION = "mechcad-freecad-transient@1.0"
TRANSIENT_MEASUREMENT_EXECUTION_MODE = "freecadcmd-subprocess"

# Identity for the deterministic injected measurement provider used only at the
# trusted composition boundary (never claims a real FreeCAD backend).
DETERMINISTIC_PROVIDER_NAME = "deterministic-test-provider"
DETERMINISTIC_PROVIDER_VERSION = "deterministic-test@1.0"
DETERMINISTIC_EXECUTION_MODE = "deterministic-injected"


class AnalysisExecutionProvenance(Model):
    """Trusted execution provenance binding a kinematic sweep result to the
    exact measurement provider and backend/runtime that produced it.

    This is evidence metadata only. It never alters the deterministic
    engineering result carried by ``CadKinematicSweepResult``.
    """

    request_hash: str = Field(min_length=1)
    result_hash: str = Field(min_length=1)
    source_assembly_hash: str = Field(min_length=1)
    model_hash: str | None = None
    sweep_version: str = Field(min_length=1)
    provider_name: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    execution_mode: str = Field(min_length=1)
    backend_provenance: BackendProvenance | None = None
    recorded_at: datetime = Field(default_factory=utc_now)


class ContinuousProofExecutionProvenance(Model):
    """Trusted execution provenance binding a continuous single-axis clearance
    proof result to the exact measurement provider and backend/runtime.

    Companion to ``AnalysisExecutionProvenance`` for continuous proof, using
    ``proof_algorithm_version`` instead of ``sweep_version``.
    """

    request_hash: str = Field(min_length=1)
    result_hash: str = Field(min_length=1)
    source_assembly_hash: str = Field(min_length=1)
    model_hash: str | None = None
    path_hash: str | None = None
    proof_algorithm_version: str = Field(min_length=1)
    reach_bound_algorithm_version: str | None = None
    provider_name: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    execution_mode: str = Field(min_length=1)
    backend_provenance: BackendProvenance | None = None
    recorded_at: datetime = Field(default_factory=utc_now)
