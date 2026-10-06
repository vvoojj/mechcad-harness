from __future__ import annotations

import hashlib
import math
from enum import StrEnum

from pydantic import Field, model_validator

from mechcad_harness.cad_assembly import (
    M10_EXECUTION_SEMANTICS_VERSION,
    CadAssemblyProgram,
    _require_semantic_fields,
    assembly_hash,
    verified_semantic_assembly_hash,
)
from mechcad_harness.core.canonical import canonical_json_bytes
from mechcad_harness.kinematic_sweep import (
    CadKinematicSweepService,
    CollisionClassification,
    RIGID_BODY_COLLISION_SWEEP_VERSION,
    RevoluteAxis,
    transformed_assembly_program,
)
from mechcad_harness.models.common import Model
from mechcad_harness.transient_assembly_analysis import TransientAssemblyAnalysisRequest


# --- Constants ---

CONTINUOUS_PROOF_ALGORITHM_ID = "conservative-single-axis-clearance-proof"
CONTINUOUS_PROOF_ALGORITHM_VERSION = f"{CONTINUOUS_PROOF_ALGORITHM_ID}@1.0"

_MOTION_BOUND_ABS_PAD_MM = 1e-9
_RADIAL_BOUND_PAD_MM = 1e-9


# --- Status ---

class ContinuousSingleAxisProofStatus(StrEnum):
    VERIFIED_CLEAR = "verified_clear"
    COLLISION_WITNESS = "collision_witness"
    NOT_PROVEN = "not_proven"


# --- Models ---

class ContinuousPairCertificate(Model):
    """Per-pair lower bound proof for a certified leaf interval."""
    moving_instance_id: str = Field(min_length=1)
    stationary_instance_id: str = Field(min_length=1)
    exact_distance_mm: float = Field(ge=0)
    radial_bound_mm: float = Field(ge=0)
    angular_motion_bound_mm: float = Field(ge=0)
    certified_lower_clearance_mm: float


class ContinuousIntervalCertificate(Model):
    """Proof certificate for a single certified leaf interval."""
    interval_start_deg: float
    interval_end_deg: float
    reference_angle_deg: float
    pair_certificates: tuple[ContinuousPairCertificate, ...] = Field(min_length=1)
    minimum_certified_lower_clearance_mm: float


class ContinuousCollisionWitness(Model):
    """Exact witness for a collision/touching at a specific configuration."""
    witness_angle_deg: float
    moving_instance_id: str = Field(min_length=1)
    stationary_instance_id: str = Field(min_length=1)
    interference_volume_mm3: float = Field(ge=0)
    exact_distance_mm: float = Field(ge=0)
    classification: CollisionClassification


class ContinuousSingleAxisProofRequest(Model):
    """Request for a continuous single-axis clearance proof."""
    source_assembly_id: str = Field(min_length=1)
    source_assembly_hash: str = Field(min_length=1)
    axis: RevoluteAxis
    start_angle_deg: float
    end_angle_deg: float
    moving_instance_ids: tuple[str, ...] = Field(min_length=1)
    stationary_instance_ids: tuple[str, ...] = Field(min_length=1)
    required_clearance_mm: float = 0.0
    volume_tolerance_mm3: float = 1e-9
    distance_tolerance_mm: float = 1e-7
    proof_guard_mm: float = 1e-6
    max_depth: int = Field(default=16, ge=0)
    minimum_interval_deg: float = 1e-6
    max_exact_evaluations: int = Field(default=4096, ge=1)
    sweep_version: str = "rigid-body-collision-sweep@1.0"
    request_hash: str = "pending"

    @model_validator(mode="after")
    def validate_request(self):
        if not self.source_assembly_hash.startswith("sha256:"):
            raise ValueError("source_assembly_hash must be sha256")
        if not math.isfinite(self.start_angle_deg) or not math.isfinite(self.end_angle_deg):
            raise ValueError("interval endpoints must be finite")
        if abs(self.end_angle_deg - self.start_angle_deg) < 1e-12:
            raise ValueError("interval must have non-zero width")
        if self.required_clearance_mm < 0:
            raise ValueError("required_clearance_mm must be non-negative")
        if self.proof_guard_mm < 0:
            raise ValueError("proof_guard_mm must be non-negative")
        if self.minimum_interval_deg <= 0:
            raise ValueError("minimum_interval_deg must be positive")
        if len(set(self.moving_instance_ids)) != len(self.moving_instance_ids):
            raise ValueError("duplicate moving instance IDs")
        if len(set(self.stationary_instance_ids)) != len(self.stationary_instance_ids):
            raise ValueError("duplicate stationary instance IDs")
        if set(self.moving_instance_ids) & set(self.stationary_instance_ids):
            raise ValueError("moving and stationary instance IDs overlap")
        if any(not math.isfinite(v) for v in (self.volume_tolerance_mm3, self.distance_tolerance_mm)):
            raise ValueError("tolerances must be finite")
        if self.volume_tolerance_mm3 < 0 or self.distance_tolerance_mm < 0:
            raise ValueError("tolerances must be non-negative")
        # Compute deterministic request hash
        payload = self.model_dump(mode="json", exclude={"request_hash"})
        digest = f"sha256:{hashlib.sha256(canonical_json_bytes(payload)).hexdigest()}"
        if self.request_hash == "pending":
            self.request_hash = digest
        elif self.request_hash != digest:
            raise ValueError("request hash mismatch")
        return self


class ContinuousSingleAxisProofResult(Model):
    """Complete result of a continuous single-axis clearance proof."""
    request_hash: str = Field(min_length=1)
    source_assembly_hash: str = Field(min_length=1)
    proof_algorithm_version: str = Field(min_length=1)
    axis: RevoluteAxis
    start_angle_deg: float
    end_angle_deg: float
    moving_instance_ids: tuple[str, ...] = Field(min_length=1)
    stationary_instance_ids: tuple[str, ...] = Field(min_length=1)
    required_clearance_mm: float
    proof_guard_mm: float
    status: ContinuousSingleAxisProofStatus
    certified_leaf_certificates: tuple[ContinuousIntervalCertificate, ...] = Field(default_factory=tuple)
    unresolved_intervals: tuple[tuple[float, float], ...] = Field(default_factory=tuple)
    collision_witness: ContinuousCollisionWitness | None = None
    exact_evaluations_count: int = Field(ge=0)
    maximum_depth_reached: int = Field(ge=0)
    result_hash: str = "pending"


def _semantic_digest(payload: dict[str, object]) -> str:
    return f"sha256:{hashlib.sha256(canonical_json_bytes(payload)).hexdigest()}"


def _semantic_axis(axis: RevoluteAxis) -> dict[str, object]:
    _require_semantic_fields(
        axis,
        RevoluteAxis,
        {
            "origin_x_mm", "origin_y_mm", "origin_z_mm", "direction_x",
            "direction_y", "direction_z", "frame_id",
        },
        "RevoluteAxis",
    )
    return axis.model_dump(mode="json")


def _semantic_proof_request_hash_from_assembly_identity(
    request: ContinuousSingleAxisProofRequest,
    semantic_assembly_hash: str,
) -> str:
    _require_semantic_fields(
        request,
        ContinuousSingleAxisProofRequest,
        {
            "source_assembly_id", "source_assembly_hash", "axis",
            "start_angle_deg", "end_angle_deg", "moving_instance_ids",
            "stationary_instance_ids", "required_clearance_mm",
            "volume_tolerance_mm3", "distance_tolerance_mm", "proof_guard_mm",
            "max_depth", "minimum_interval_deg", "max_exact_evaluations",
            "sweep_version", "request_hash",
        },
        "ContinuousSingleAxisProofRequest",
    )
    if request.sweep_version != RIGID_BODY_COLLISION_SWEEP_VERSION:
        raise ValueError("proof request sweep contract is not trusted")
    payload = {
        "semantic_projection_version": M10_EXECUTION_SEMANTICS_VERSION,
        "axis": _semantic_axis(request.axis),
        "start_angle_deg": request.start_angle_deg,
        "end_angle_deg": request.end_angle_deg,
        "moving_instance_ids": list(request.moving_instance_ids),
        "stationary_instance_ids": list(request.stationary_instance_ids),
        "required_clearance_mm": request.required_clearance_mm,
        "volume_tolerance_mm3": request.volume_tolerance_mm3,
        "distance_tolerance_mm": request.distance_tolerance_mm,
        "proof_guard_mm": request.proof_guard_mm,
        "max_depth": request.max_depth,
        "minimum_interval_deg": request.minimum_interval_deg,
        "max_exact_evaluations": request.max_exact_evaluations,
        "sweep_version": RIGID_BODY_COLLISION_SWEEP_VERSION,
        "semantic_assembly_hash": semantic_assembly_hash,
    }
    return _semantic_digest(payload)


def semantic_proof_request_hash(
    request: ContinuousSingleAxisProofRequest,
    assembly: CadAssemblyProgram,
    mappings,
) -> str:
    """Project P1 onto semantic inputs while retaining raw replay siblings."""
    if request.source_assembly_id != assembly.assembly_id:
        raise ValueError("proof request source assembly ID mismatch")
    semantic_assembly = verified_semantic_assembly_hash(
        assembly, mappings, request.source_assembly_hash
    )
    return _semantic_proof_request_hash_from_assembly_identity(
        request, semantic_assembly
    )


def _semantic_proof_result_hash_from_assembly_identity(
    result: ContinuousSingleAxisProofResult,
    request: ContinuousSingleAxisProofRequest,
    semantic_assembly_hash: str,
) -> str:
    _require_semantic_fields(
        result,
        ContinuousSingleAxisProofResult,
        {
            "request_hash", "source_assembly_hash", "proof_algorithm_version",
            "axis", "start_angle_deg", "end_angle_deg", "moving_instance_ids",
            "stationary_instance_ids", "required_clearance_mm", "proof_guard_mm",
            "status", "certified_leaf_certificates", "unresolved_intervals",
            "collision_witness", "exact_evaluations_count",
            "maximum_depth_reached", "result_hash",
        },
        "ContinuousSingleAxisProofResult",
    )
    semantic_request = _semantic_proof_request_hash_from_assembly_identity(
        request, semantic_assembly_hash
    )
    if result.request_hash != request.request_hash:
        raise ValueError("proof result request hash mismatch")
    if result.source_assembly_hash != request.source_assembly_hash:
        raise ValueError("proof result source assembly hash mismatch")
    for field_name in (
        "axis", "start_angle_deg", "end_angle_deg", "moving_instance_ids",
        "stationary_instance_ids", "required_clearance_mm", "proof_guard_mm",
    ):
        if getattr(result, field_name) != getattr(request, field_name):
            raise ValueError(f"proof result {field_name} does not match request")
    if result.proof_algorithm_version != CONTINUOUS_PROOF_ALGORITHM_VERSION:
        raise ValueError("proof result algorithm contract is not trusted")

    pair_fields = {
        "moving_instance_id", "stationary_instance_id", "exact_distance_mm",
        "radial_bound_mm", "angular_motion_bound_mm",
        "certified_lower_clearance_mm",
    }
    interval_fields = {
        "interval_start_deg", "interval_end_deg", "reference_angle_deg",
        "pair_certificates", "minimum_certified_lower_clearance_mm",
    }
    witness_fields = {
        "witness_angle_deg", "moving_instance_id", "stationary_instance_id",
        "interference_volume_mm3", "exact_distance_mm", "classification",
    }
    intervals = []
    for interval in result.certified_leaf_certificates:
        _require_semantic_fields(
            interval, ContinuousIntervalCertificate, interval_fields,
            "ContinuousIntervalCertificate",
        )
        pair_certificates = []
        for pair in interval.pair_certificates:
            _require_semantic_fields(
                pair, ContinuousPairCertificate, pair_fields,
                "ContinuousPairCertificate",
            )
            pair_certificates.append(pair.model_dump(mode="json"))
        interval_payload = interval.model_dump(mode="json")
        interval_payload["pair_certificates"] = pair_certificates
        intervals.append(interval_payload)
    witness = result.collision_witness
    if witness is not None:
        _require_semantic_fields(
            witness, ContinuousCollisionWitness, witness_fields,
            "ContinuousCollisionWitness",
        )
        witness_payload = witness.model_dump(mode="json")
    else:
        witness_payload = None
    payload = {
        "semantic_projection_version": M10_EXECUTION_SEMANTICS_VERSION,
        "proof_algorithm_version": CONTINUOUS_PROOF_ALGORITHM_VERSION,
        "semantic_proof_request_hash": semantic_request,
        "axis": _semantic_axis(result.axis),
        "start_angle_deg": result.start_angle_deg,
        "end_angle_deg": result.end_angle_deg,
        "moving_instance_ids": list(result.moving_instance_ids),
        "stationary_instance_ids": list(result.stationary_instance_ids),
        "required_clearance_mm": result.required_clearance_mm,
        "proof_guard_mm": result.proof_guard_mm,
        "status": result.status.value,
        "certified_leaf_certificates": intervals,
        "unresolved_intervals": [list(interval) for interval in result.unresolved_intervals],
        "collision_witness": witness_payload,
        "exact_evaluations_count": result.exact_evaluations_count,
        "maximum_depth_reached": result.maximum_depth_reached,
        "semantic_assembly_hash": semantic_assembly_hash,
    }
    return _semantic_digest(payload)


def semantic_proof_result_hash(
    result: ContinuousSingleAxisProofResult,
    request: ContinuousSingleAxisProofRequest,
    assembly: CadAssemblyProgram,
    mappings,
) -> str:
    """Project P2 values and bind them to the semantic P1 request."""
    semantic_proof_request_hash(request, assembly, mappings)
    semantic_assembly = verified_semantic_assembly_hash(
        assembly, mappings, result.source_assembly_hash
    )
    return _semantic_proof_result_hash_from_assembly_identity(
        result, request, semantic_assembly
    )


# --- Mathematical Bound ---

def motion_bound(radial_mm: float, delta_rad: float) -> float:
    """Conservative upper bound on displacement of any point in the moving set.

    For a rigid rotation about a fixed axis by angle delta_rad, every point
    moves by at most 2*R*sin(min(|delta_rad|, pi)/2), where R is the max
    distance of any moving point from the revolute axis.

    A small numerical padding is added for floating-point safety.
    """
    if radial_mm < 0:
        raise ValueError("radial_mm must be non-negative")
    capped = min(abs(delta_rad), math.pi)
    base = 2.0 * radial_mm * math.sin(capped / 2.0)
    return base + _MOTION_BOUND_ABS_PAD_MM * (1.0 + abs(radial_mm))


def point_to_line_distance(px: float, py: float, pz: float,
                           ox: float, oy: float, oz: float,
                           dx: float, dy: float, dz: float) -> float:
    """Distance from point (px,py,pz) to line through (ox,oy,oZ) with unit direction (dx,dy,dz)."""
    rx, ry, rz = px - ox, py - oy, pz - oz
    # cross product of (r) x (d)
    cx = ry * dz - rz * dy
    cy = rz * dx - rx * dz
    cz = rx * dy - ry * dx
    return math.sqrt(cx * cx + cy * cy + cz * cz)


# --- Proof Algorithm ---

class _CollisionWitnessFound(Exception):
    """Internal: raised when an exact evaluation reveals touching/interference."""

    def __init__(self, witness: ContinuousCollisionWitness):
        self.witness = witness


class ContinuousSingleAxisClearanceProof:
    """Deterministic proof engine for continuous single-axis clearance."""

    def __init__(
        self,
        exact_measure,
        radial_bound_provider,
    ):
        """
        Args:
            exact_measure: Callable[[TransientAssemblyAnalysisRequest, CadAssemblyProgram],
                tuple[tuple[str, str, float, float], ...]]
            radial_bound_provider: Callable[[CadAssemblyProgram, RevoluteAxis, tuple[str,...]],
                dict[str, float]]
        """
        self.exact_measure = exact_measure
        self.radial_bound_provider = radial_bound_provider

    def prove(
        self,
        request: ContinuousSingleAxisProofRequest,
        assembly: CadAssemblyProgram,
    ) -> ContinuousSingleAxisProofResult:
        if request.source_assembly_hash != assembly_hash(assembly):
            raise ValueError("source_assembly_hash mismatch")
        if request.source_assembly_id != assembly.assembly_id:
            raise ValueError("source_assembly_id mismatch")
        source_ids = {inst.instance_id for inst in assembly.instances}
        request_ids = set(request.moving_instance_ids) | set(request.stationary_instance_ids)
        if request_ids != source_ids:
            missing = sorted(request_ids - source_ids)
            omitted = sorted(source_ids - request_ids)
            raise ValueError(f"instance mismatch: missing={missing}, omitted={omitted}")

        # Compute invariant radial bounds per moving instance
        radial_raw = self.radial_bound_provider(assembly, request.axis, request.moving_instance_ids)
        radial = {
            iid: r + _RADIAL_BOUND_PAD_MM
            for iid, r in radial_raw.items()
        }
        for iid in request.moving_instance_ids:
            if iid not in radial:
                raise ValueError(f"missing radial bound for {iid}")

        pairs = CadKinematicSweepService.collision_pairs(request)
        counter = [0]
        depth_max = [0]
        certificates: list[ContinuousIntervalCertificate] = []
        unresolved: list[tuple[float, float]] = []
        witness: ContinuousCollisionWitness | None = None

        a = float(request.start_angle_deg)
        b = float(request.end_angle_deg)

        try:
            self._prove_interval(
                request=request,
                assembly=assembly,
                radial=radial,
                pairs=pairs,
                a=a,
                b=b,
                depth=0,
                counter=counter,
                depth_max=depth_max,
                certificates=certificates,
                unresolved=unresolved,
            )
            status = ContinuousSingleAxisProofStatus.NOT_PROVEN if unresolved else ContinuousSingleAxisProofStatus.VERIFIED_CLEAR
        except _CollisionWitnessFound as exc:
            status = ContinuousSingleAxisProofStatus.COLLISION_WITNESS
            witness = exc.witness

        result = ContinuousSingleAxisProofResult(
            request_hash=request.request_hash,
            source_assembly_hash=request.source_assembly_hash,
            proof_algorithm_version=CONTINUOUS_PROOF_ALGORITHM_VERSION,
            axis=request.axis,
            start_angle_deg=a,
            end_angle_deg=b,
            moving_instance_ids=request.moving_instance_ids,
            stationary_instance_ids=request.stationary_instance_ids,
            required_clearance_mm=request.required_clearance_mm,
            proof_guard_mm=request.proof_guard_mm,
            status=status,
            certified_leaf_certificates=tuple(certificates),
            unresolved_intervals=tuple(unresolved),
            collision_witness=witness,
            exact_evaluations_count=counter[0],
            maximum_depth_reached=depth_max[0],
        )
        # Deterministic result hash
        payload = result.model_dump(mode="json", exclude={"result_hash"})
        digest = f"sha256:{hashlib.sha256(canonical_json_bytes(payload)).hexdigest()}"
        return result.model_copy(update={"result_hash": digest})

    def _prove_interval(
        self,
        *,
        request: ContinuousSingleAxisProofRequest,
        assembly: CadAssemblyProgram,
        radial: dict[str, float],
        pairs: tuple[tuple[str, str], ...],
        a: float,
        b: float,
        depth: int,
        counter: list[int],
        depth_max: list[int],
        certificates: list[ContinuousIntervalCertificate],
        unresolved: list[tuple[float, float]],
    ) -> None:
        depth_max[0] = max(depth_max[0], depth)

        # Resource limit check
        if counter[0] >= request.max_exact_evaluations:
            unresolved.append((a, b))
            return

        c = (a + b) / 2.0

        # Evaluate exact geometry at reference
        transformed = transformed_assembly_program(
            assembly, request.axis, c,
            request.moving_instance_ids, request.stationary_instance_ids,
        )
        trequest = TransientAssemblyAnalysisRequest(
            source_assembly_hash=request.source_assembly_hash,
            transformed_assembly_hash=assembly_hash(transformed),
            sweep_request_hash=request.request_hash,
            sample_angle_deg=c,
            pairs=pairs,
        )
        measurements = self.exact_measure(trequest, transformed)
        counter[0] += 1

        # Build per-pair measurements dict
        pair_data = {}
        for moving, stationary, volume, distance in measurements:
            cls = CollisionClassification.from_measurement(
                volume, distance,
                volume_tolerance_mm3=request.volume_tolerance_mm3,
                distance_tolerance_mm=request.distance_tolerance_mm,
            )
            if cls in (CollisionClassification.INTERFERENCE, CollisionClassification.TOUCHING):
                witness = ContinuousCollisionWitness(
                    witness_angle_deg=c,
                    moving_instance_id=moving,
                    stationary_instance_id=stationary,
                    interference_volume_mm3=volume,
                    exact_distance_mm=distance,
                    classification=cls,
                )
                raise _CollisionWitnessFound(witness)
            pair_data[(moving, stationary)] = distance

        # Check certification: d(c) - B > required + guard for every pair
        half_span_rad = math.radians(abs(b - a) / 2.0)
        min_lower = None
        pair_certs = []
        all_certified = True
        for moving, stationary in pairs:
            d = pair_data[(moving, stationary)]
            R = radial[moving]
            B = motion_bound(R, half_span_rad)
            lower = d - B
            if min_lower is None or lower < min_lower:
                min_lower = lower
            pair_certs.append(ContinuousPairCertificate(
                moving_instance_id=moving,
                stationary_instance_id=stationary,
                exact_distance_mm=d,
                radial_bound_mm=R,
                angular_motion_bound_mm=B,
                certified_lower_clearance_mm=lower,
            ))
            if lower <= request.required_clearance_mm + request.proof_guard_mm:
                all_certified = False
                break

        if all_certified:
            certificates.append(ContinuousIntervalCertificate(
                interval_start_deg=a,
                interval_end_deg=b,
                reference_angle_deg=c,
                pair_certificates=tuple(pair_certs),
                minimum_certified_lower_clearance_mm=min_lower,
            ))
            return

        # Cannot certify; try subdivision
        width = abs(b - a)
        if depth >= request.max_depth or width <= request.minimum_interval_deg:
            unresolved.append((a, b))
            return

        # Deterministic order: left first, then right
        self._prove_interval(
            request=request, assembly=assembly, radial=radial, pairs=pairs,
            a=a, b=c, depth=depth + 1,
            counter=counter, depth_max=depth_max,
            certificates=certificates, unresolved=unresolved,
        )
        self._prove_interval(
            request=request, assembly=assembly, radial=radial, pairs=pairs,
            a=c, b=b, depth=depth + 1,
            counter=counter, depth_max=depth_max,
            certificates=certificates, unresolved=unresolved,
        )
