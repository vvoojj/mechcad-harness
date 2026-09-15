from __future__ import annotations

import math

from mechcad_harness.engineering import SupportedConstraintKey
from mechcad_harness.engineering.scalar_projection import CanonicalScalarProjection

from .models import ProjectedSourceBoundScalar


def lower_projected_output_speed(
    projection: CanonicalScalarProjection,
) -> ProjectedSourceBoundScalar:
    projection = CanonicalScalarProjection.model_validate(
        projection.model_dump(mode="json")
        if isinstance(projection, CanonicalScalarProjection)
        else projection
    )
    if (
        projection.authoritative_key is not SupportedConstraintKey.OUTPUT_ANGULAR_SPEED
        or projection.unit != "rad/s"
        or projection.projection_rule_id != "authoritative-output-angular-speed-rad-s@1"
    ):
        raise ValueError("projection is not an output angular speed claim")
    rpm = projection.value * 60.0 / (2.0 * math.pi)
    return ProjectedSourceBoundScalar(
        value=rpm,
        unit="rpm",
        canonical_projection=projection,
        normalization_rule_id="m12-output-angular-speed-rad-s-to-rpm@1",
    )


__all__ = ["lower_projected_output_speed"]
