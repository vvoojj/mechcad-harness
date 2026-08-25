from __future__ import annotations

from dataclasses import dataclass

# Deterministic versioned tolerance policy for initial single-solid planar-face
# semantic region matching.  Thresholds are justified by the M11-3 technical
# proof and recorded in resolver/bridge provenance and region-map identity/hash.
PLANAR_REGION_MATCH_POLICY_ID = "structural-planar-region-match@1"

# C3D10 midside/face-mapping geometric tolerance (mm).
C3D10_GEOMETRY_TOLERANCE_MM = 1e-6

# Constraint-preflight numerical tolerance.  Deterministic, versioned.
RIGID_BODY_RANK_TOLERANCE = 1e-9
RIGID_BODY_RANK_POLICY_ID = "structural-rigid-body-preflight@1"

# Resultant-force nodal conservation tolerance (N).
RESULTANT_FORCE_CONSERVATION_TOLERANCE_N = 1e-6


@dataclass(frozen=True)
class PlanarRegionMatchTolerances:
    policy_id: str
    planarity_mm: float
    area_mm2: float
    centroid_mm: float
    normal_abs_dot: float


PLANAR_REGION_MATCH_TOLERANCES = PlanarRegionMatchTolerances(
    policy_id=PLANAR_REGION_MATCH_POLICY_ID,
    planarity_mm=1e-3,
    area_mm2=2.0,
    centroid_mm=2.0,
    normal_abs_dot=0.999,
)
