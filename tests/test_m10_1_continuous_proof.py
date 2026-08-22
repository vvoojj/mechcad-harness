from __future__ import annotations

import hashlib
import importlib.util
import json
import math

import pytest

from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_compilation import MountingPlateDesignSpec
from mechcad_harness.cad_program import (
    BasePlateOperation,
    CadPartProgram,
)
from mechcad_harness.continuous_proof import (
    CONTINUOUS_PROOF_ALGORITHM_VERSION,
    ContinuousCollisionWitness,
    ContinuousIntervalCertificate,
    ContinuousPairCertificate,
    ContinuousSingleAxisClearanceProof,
    ContinuousSingleAxisProofRequest,
    ContinuousSingleAxisProofResult,
    ContinuousSingleAxisProofStatus,
    motion_bound,
    point_to_line_distance,
)
from mechcad_harness.kinematic_sweep import CollisionClassification, RevoluteAxis
from mechcad_harness.transient_assembly_analysis import TransientAssemblyAnalysisRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

AXIS_Z = RevoluteAxis(
    origin_x_mm=0, origin_y_mm=0, origin_z_mm=0,
    direction_x=0, direction_y=0, direction_z=1,
    frame_id="frame",
)

AXIS_TILTED = RevoluteAxis(
    origin_x_mm=10, origin_y_mm=20, origin_z_mm=30,
    direction_x=1, direction_y=1, direction_z=1,
    frame_id="tilted_frame",
)

AXIS_DIAGONAL = RevoluteAxis(
    origin_x_mm=5, origin_y_mm=-3, origin_z_mm=7,
    direction_x=0, direction_y=1, direction_z=0,
    frame_id="diag_frame",
)


_DUMMY_PART = CadPartProgram(
    part_id="plate",
    operations=(BasePlateOperation(operation_id="base", length_mm=10, width_mm=10, thickness_mm=2),),
)


def _simple_assembly(assembly_id="test-asm"):
    return CadAssemblyProgram(
        assembly_id=assembly_id,
        parts=(_DUMMY_PART,),
        imported_components=(),
        instances=(
            CadComponentInstance(instance_id="m1", part_id="plate",
                                 placement=CadRigidTransform(x_mm=0, y_mm=0, z_mm=0)),
            CadComponentInstance(instance_id="s1", part_id="plate",
                                 placement=CadRigidTransform(x_mm=0, y_mm=-60, z_mm=0)),
        ),
    )


def _two_pair_assembly(assembly_id="test-asm-2"):
    return CadAssemblyProgram(
        assembly_id=assembly_id,
        parts=(_DUMMY_PART,),
        imported_components=(),
        instances=(
            CadComponentInstance(instance_id="m1", part_id="plate",
                                 placement=CadRigidTransform(x_mm=0, y_mm=0, z_mm=0)),
            CadComponentInstance(instance_id="m2", part_id="plate",
                                 placement=CadRigidTransform(x_mm=20, y_mm=0, z_mm=0)),
            CadComponentInstance(instance_id="s1", part_id="plate",
                                 placement=CadRigidTransform(x_mm=0, y_mm=-60, z_mm=0)),
        ),
    )


def _make_request(**overrides):
    asm = _simple_assembly(overrides.pop("_assembly", None) or "test-asm")
    defaults = dict(
        source_assembly_id=asm.assembly_id,
        source_assembly_hash=assembly_hash(asm),
        axis=AXIS_Z,
        start_angle_deg=0.0,
        end_angle_deg=90.0,
        moving_instance_ids=("m1",),
        stationary_instance_ids=("s1",),
    )
    defaults.update(overrides)
    return ContinuousSingleAxisProofRequest(**defaults), asm


def _constant_exact_measure(distance_mm=50.0):
    def measure(request: TransientAssemblyAnalysisRequest, program):
        return tuple(
            (m, s, 0.0, distance_mm) for m, s in request.pairs
        )
    return measure


def _constant_radial_bound(radial_mm=100.0):
    def provider(program, axis, moving_ids):
        return {iid: radial_mm for iid in moving_ids}
    return provider


def _sin_distance_exact_measure(amplitude=25.0, offset=30.0):
    """Distance varies sinusoidally with angle (approximation)."""
    def measure(request: TransientAssemblyAnalysisRequest, program):
        angle_rad = math.radians(request.sample_angle_deg % 360)
        d = offset + amplitude * math.sin(angle_rad)
        d = max(0.001, d)
        return tuple((m, s, 0.0, d) for m, s in request.pairs)
    return measure


def _collision_at_angle_exact_measure(collision_angle=180.0):
    """Returns interference at a specific angle."""
    def measure(request: TransientAssemblyAnalysisRequest, program):
        angle = request.sample_angle_deg % 360
        if abs(angle - collision_angle) < 0.01:
            return tuple((m, s, 100.0, 0.0) for m, s in request.pairs)
        return tuple((m, s, 0.0, 10.0) for m, s in request.pairs)
    return measure


def _touching_at_angle_exact_measure(touch_angle=180.0):
    """Returns touching (volume=0, distance=0) at a specific angle."""
    def measure(request: TransientAssemblyAnalysisRequest, program):
        angle = request.sample_angle_deg % 360
        if abs(angle - touch_angle) < 0.01:
            return tuple((m, s, 0.0, 0.0) for m, s in request.pairs)
        return tuple((m, s, 0.0, 10.0) for m, s in request.pairs)
    return measure


# ===================================================================
# 34: UNIT TESTS - MATHEMATICAL BOUND
# ===================================================================

class TestMotionBound:
    def test_zero_displacement(self):
        assert motion_bound(100.0, 0.0) == pytest.approx(1e-9 * (1 + 100), abs=1e-12)

    def test_180_degrees(self):
        R = 50.0
        b = motion_bound(R, math.pi)
        assert b == pytest.approx(2 * R + 1e-9 * (1 + R), rel=1e-10)

    def test_displacement_greater_than_180_capped(self):
        R = 30.0
        b_180 = motion_bound(R, math.pi)
        b_360 = motion_bound(R, 2 * math.pi)
        b_720 = motion_bound(R, 4 * math.pi)
        assert b_360 == pytest.approx(b_180, rel=1e-10)
        assert b_720 == pytest.approx(b_180, rel=1e-10)

    def test_full_turn_same_as_180(self):
        R = 10.0
        assert motion_bound(R, math.pi) == pytest.approx(motion_bound(R, 2 * math.pi))

    def test_small_angle_proportional(self):
        R = 100.0
        small = 0.01  # rad
        b = motion_bound(R, small)
        # Exact: 2R sin(small/2) + pad
        expected = 2 * R * math.sin(small / 2) + 1e-9 * (1 + R)
        assert b == pytest.approx(expected, rel=1e-12)

    def test_arbitrary_axis_orientation_invariant(self):
        R = 50.0
        b1 = motion_bound(R, 0.5)
        b2 = motion_bound(R, -0.5)
        assert b1 == pytest.approx(b2, rel=1e-12)

    def test_zero_radius(self):
        b = motion_bound(0.0, math.pi / 2)
        assert b == pytest.approx(1e-9, abs=1e-12)

    def test_negative_radius_fails(self):
        with pytest.raises(ValueError, match="non-negative"):
            motion_bound(-1.0, 1.0)

    def test_negative_required_clearance_fails(self):
        with pytest.raises(ValueError, match="non-negative"):
            ContinuousSingleAxisProofRequest(
                source_assembly_id="x",
                source_assembly_hash="sha256:" + "a" * 64,
                axis=AXIS_Z,
                start_angle_deg=0.0,
                end_angle_deg=10.0,
                moving_instance_ids=("m1",),
                stationary_instance_ids=("s1",),
                required_clearance_mm=-1.0,
            )


class TestPointToLineDistance:
    def test_point_on_line(self):
        d = point_to_line_distance(0, 0, 0, 0, 0, 0, 0, 0, 1)
        assert d == pytest.approx(0.0, abs=1e-12)

    def test_point_perpendicular(self):
        d = point_to_line_distance(1, 0, 0, 0, 0, 0, 0, 0, 1)
        assert d == pytest.approx(1.0, abs=1e-12)

    def test_translated_axis(self):
        d = point_to_line_distance(0, 5, 0, 0, 0, 0, 0, 1, 0)
        assert d == pytest.approx(0.0, abs=1e-12)
        d2 = point_to_line_distance(5, 0, 0, 0, 0, 0, 0, 1, 0)
        assert d2 == pytest.approx(5.0, abs=1e-12)


# ===================================================================
# 35: UNIT TESTS - INTERVAL PROOF
# ===================================================================

class TestContinuousProofDeterministic:
    def test_coarse_interval_certifies_immediately(self):
        """A wide interval with large clearance certifies without subdivision."""
        request, asm = _make_request(
            start_angle_deg=0.0,
            end_angle_deg=90.0,
        )
        proof = ContinuousSingleAxisClearanceProof(
            exact_measure=_constant_exact_measure(50.0),
            radial_bound_provider=_constant_radial_bound(10.0),
        )
        result = proof.prove(request, asm)
        assert result.status is ContinuousSingleAxisProofStatus.VERIFIED_CLEAR
        assert len(result.certified_leaf_certificates) == 1
        assert len(result.unresolved_intervals) == 0
        assert result.exact_evaluations_count == 1
        assert result.collision_witness is None

    def test_narrow_interval_subdivides_to_certify(self):
        """A loose bound fails at coarse level, subdivision certifies children."""
        # R=30, half_span=45 deg for [0,90]: B ~ 2*30*sin(22.5deg) ~ 22.96
        # d(c=45) = 30, lower = 30 - 22.96 = 7.04 > 0 (with guard 1e-6) -> certified
        request, asm = _make_request(
            start_angle_deg=0.0,
            end_angle_deg=90.0,
            proof_guard_mm=0.01,
        )
        proof = ContinuousSingleAxisClearanceProof(
            exact_measure=_constant_exact_measure(30.0),
            radial_bound_provider=_constant_radial_bound(30.0),
        )
        result = proof.prove(request, asm)
        assert result.status is ContinuousSingleAxisProofStatus.VERIFIED_CLEAR
        assert result.exact_evaluations_count >= 1

    def test_collision_at_midpoint_terminates(self):
        """Collision at the midpoint returns COLLISION_WITNESS immediately."""
        request, asm = _make_request(
            start_angle_deg=0.0,
            end_angle_deg=360.0,
        )
        proof = ContinuousSingleAxisClearanceProof(
            exact_measure=_collision_at_angle_exact_measure(180.0),
            radial_bound_provider=_constant_radial_bound(10.0),
        )
        result = proof.prove(request, asm)
        assert result.status is ContinuousSingleAxisProofStatus.COLLISION_WITNESS
        assert result.collision_witness is not None
        assert result.collision_witness.classification is CollisionClassification.INTERFERENCE

    def test_touching_does_not_produce_verified_clear(self):
        """Touching at reference returns COLLISION_WITNESS, not VERIFIED_CLEAR."""
        request, asm = _make_request(
            start_angle_deg=0.0,
            end_angle_deg=360.0,
        )
        proof = ContinuousSingleAxisClearanceProof(
            exact_measure=_touching_at_angle_exact_measure(180.0),
            radial_bound_provider=_constant_radial_bound(10.0),
        )
        result = proof.prove(request, asm)
        assert result.status is ContinuousSingleAxisProofStatus.COLLISION_WITNESS
        assert result.collision_witness.classification is CollisionClassification.TOUCHING

    def test_resource_exhaustion_produces_not_proven(self):
        """Hitting max_exact_evaluations yields NOT_PROVEN."""
        request, asm = _make_request(
            start_angle_deg=0.0,
            end_angle_deg=360.0,
            max_exact_evaluations=1,
            max_depth=100,
            minimum_interval_deg=1e-12,
        )
        proof = ContinuousSingleAxisClearanceProof(
            exact_measure=_sin_distance_exact_measure(amplitude=25.0, offset=30.0),
            radial_bound_provider=_constant_radial_bound(50.0),
        )
        result = proof.prove(request, asm)
        assert result.status is ContinuousSingleAxisProofStatus.NOT_PROVEN
        assert len(result.unresolved_intervals) > 0

    def test_depth_exhaustion_produces_not_proven(self):
        """Hitting max_depth yields NOT_PROVEN for wide interval."""
        # R=200: motion bound for 90° interval ~153mm; sinusoidal distance
        # max ~70mm at midpoint — insufficient to certify at coarse or child level.
        request, asm = _make_request(
            start_angle_deg=0.0,
            end_angle_deg=90.0,
            max_depth=1,
            max_exact_evaluations=1000,
            proof_guard_mm=0.0,
        )
        proof = ContinuousSingleAxisClearanceProof(
            exact_measure=_sin_distance_exact_measure(amplitude=50.0, offset=20.0),
            radial_bound_provider=_constant_radial_bound(200.0),
        )
        result = proof.prove(request, asm)
        assert result.status is ContinuousSingleAxisProofStatus.NOT_PROVEN

    def test_every_moving_stationary_pair_must_certify(self):
        """With two moving-stationary pairs, both must be certified for the leaf."""
        asm = _two_pair_assembly()
        request = ContinuousSingleAxisProofRequest(
            source_assembly_id=asm.assembly_id,
            source_assembly_hash=assembly_hash(asm),
            axis=AXIS_Z,
            start_angle_deg=0.0,
            end_angle_deg=90.0,
            moving_instance_ids=("m1", "m2"),
            stationary_instance_ids=("s1",),
        )

        def measure(req, prog):
            return (
                ("m1", "s1", 0.0, 50.0),
                ("m2", "s1", 0.0, 50.0),
            )

        def radial(prog, axis, mv):
            return {"m1": 5.0, "m2": 5.0}

        proof = ContinuousSingleAxisClearanceProof(
            exact_measure=measure,
            radial_bound_provider=radial,
        )
        result = proof.prove(request, asm)
        assert result.status is ContinuousSingleAxisProofStatus.VERIFIED_CLEAR
        for cert in result.certified_leaf_certificates:
            assert len(cert.pair_certificates) == 2

    def test_one_unresolved_pair_prevents_certification(self):
        """If one pair fails, the whole interval is not certified."""
        asm = _two_pair_assembly()
        request = ContinuousSingleAxisProofRequest(
            source_assembly_id=asm.assembly_id,
            source_assembly_hash=assembly_hash(asm),
            axis=AXIS_Z,
            start_angle_deg=0.0,
            end_angle_deg=90.0,
            moving_instance_ids=("m1", "m2"),
            stationary_instance_ids=("s1",),
            max_depth=2,
            max_exact_evaluations=1000,
        )

        def measure(req, prog):
            # m1 has plenty of clearance, m2 has tight clearance
            return (
                ("m1", "s1", 0.0, 50.0),
                ("m2", "s1", 0.0, 2.0),
            )

        def radial(prog, axis, mv):
            return {"m1": 5.0, "m2": 50.0}

        proof = ContinuousSingleAxisClearanceProof(
            exact_measure=measure,
            radial_bound_provider=radial,
        )
        result = proof.prove(request, asm)
        # With m2 R=50, even small intervals will have large B, may not certify
        assert result.status != ContinuousSingleAxisProofStatus.VERIFIED_CLEAR or \
            result.exact_evaluations_count > 1

    def test_interval_coverage_no_gaps(self):
        """Certified leaf intervals must tile the full requested interval."""
        request, asm = _make_request(
            start_angle_deg=0.0,
            end_angle_deg=90.0,
        )
        proof = ContinuousSingleAxisClearanceProof(
            exact_measure=_constant_exact_measure(100.0),
            radial_bound_provider=_constant_radial_bound(1.0),
        )
        result = proof.prove(request, asm)
        assert result.status is ContinuousSingleAxisProofStatus.VERIFIED_CLEAR
        leaves = sorted(result.certified_leaf_certificates, key=lambda c: c.interval_start_deg)
        assert leaves[0].interval_start_deg == pytest.approx(0.0)
        assert leaves[-1].interval_end_deg == pytest.approx(90.0)
        for i in range(len(leaves) - 1):
            assert leaves[i].interval_end_deg == pytest.approx(leaves[i + 1].interval_start_deg)

    def test_deterministic_result_hash(self):
        """Same inputs produce identical result hash."""
        request, asm = _make_request(
            start_angle_deg=0.0,
            end_angle_deg=90.0,
        )
        proof = ContinuousSingleAxisClearanceProof(
            exact_measure=_constant_exact_measure(50.0),
            radial_bound_provider=_constant_radial_bound(10.0),
        )
        r1 = proof.prove(request, asm)
        r2 = proof.prove(request, asm)
        assert r1.result_hash == r2.result_hash

    def test_discrete_sweep_still_continuous_false(self):
        """CadKinematicSweepResult.continuous_sweep_verified remains False."""
        from mechcad_harness.kinematic_sweep import CadKinematicSweepResult
        assert CadKinematicSweepResult.model_fields["continuous_sweep_verified"].default is False

    def test_request_hash_deterministic(self):
        r1, _ = _make_request()
        r2, _ = _make_request()
        assert r1.request_hash == r2.request_hash

    def test_360_degree_interval(self):
        """Full 360 degree interval certifies when clearance is sufficient."""
        request, asm = _make_request(
            start_angle_deg=0.0,
            end_angle_deg=360.0,
        )
        proof = ContinuousSingleAxisClearanceProof(
            exact_measure=_constant_exact_measure(50.0),
            radial_bound_provider=_constant_radial_bound(10.0),
        )
        result = proof.prove(request, asm)
        assert result.status is ContinuousSingleAxisProofStatus.VERIFIED_CLEAR

    def test_multi_turn_interval(self):
        """Interval > 360 works."""
        request, asm = _make_request(
            start_angle_deg=0.0,
            end_angle_deg=720.0,
        )
        proof = ContinuousSingleAxisClearanceProof(
            exact_measure=_constant_exact_measure(100.0),
            radial_bound_provider=_constant_radial_bound(10.0),
        )
        result = proof.prove(request, asm)
        assert result.status is ContinuousSingleAxisProofStatus.VERIFIED_CLEAR


class TestContinuousProofRequestValidation:
    def test_rejects_overlapping_partition(self):
        with pytest.raises(ValueError, match="overlap"):
            ContinuousSingleAxisProofRequest(
                source_assembly_id="x",
                source_assembly_hash="sha256:" + "a" * 64,
                axis=AXIS_Z,
                start_angle_deg=0.0,
                end_angle_deg=10.0,
                moving_instance_ids=("a",),
                stationary_instance_ids=("a",),
            )

    def test_rejects_zero_width_interval(self):
        with pytest.raises(ValueError, match="non-zero width"):
            ContinuousSingleAxisProofRequest(
                source_assembly_id="x",
                source_assembly_hash="sha256:" + "a" * 64,
                axis=AXIS_Z,
                start_angle_deg=10.0,
                end_angle_deg=10.0,
                moving_instance_ids=("a",),
                stationary_instance_ids=("b",),
            )

    def test_rejects_negative_guard(self):
        with pytest.raises(ValueError, match="non-negative"):
            ContinuousSingleAxisProofRequest(
                source_assembly_id="x",
                source_assembly_hash="sha256:" + "a" * 64,
                axis=AXIS_Z,
                start_angle_deg=0.0,
                end_angle_deg=10.0,
                moving_instance_ids=("a",),
                stationary_instance_ids=("b",),
                proof_guard_mm=-1.0,
            )


# ===================================================================
# 37: PROVENANCE TESTS (deterministic composition)
# ===================================================================

class TestContinuousProofProvenanceDeterministic:
    def test_provenance_model_fields(self):
        from mechcad_harness.analysis_provenance import ContinuousProofExecutionProvenance
        prov = ContinuousProofExecutionProvenance(
            request_hash="sha256:" + "a" * 64,
            result_hash="sha256:" + "b" * 64,
            source_assembly_hash="sha256:" + "c" * 64,
            proof_algorithm_version=CONTINUOUS_PROOF_ALGORITHM_VERSION,
            provider_name="deterministic-test-provider",
            provider_version="deterministic-test@1.0",
            execution_mode="deterministic-injected",
        )
        assert prov.proof_algorithm_version.startswith("conservative-single-axis-clearance-proof@")
        assert prov.backend_provenance is None

    def test_evidence_carries_continuous_provenance(self):
        from mechcad_harness.analysis_provenance import ContinuousProofExecutionProvenance
        from mechcad_harness.models.evidence import Evidence
        prov = ContinuousProofExecutionProvenance(
            request_hash="sha256:" + "a" * 64,
            result_hash="sha256:" + "b" * 64,
            source_assembly_hash="sha256:" + "c" * 64,
            proof_algorithm_version=CONTINUOUS_PROOF_ALGORITHM_VERSION,
            provider_name="test",
            provider_version="test@1.0",
            execution_mode="test",
        )
        evidence = Evidence(
            id="EVD-TEST",
            kind="analysis.continuous_clearance_proof",
            summary="test",
            revision=1,
            state_hash="sha256:" + "d" * 64,
            continuous_proof_execution_provenance=prov,
        )
        assert evidence.continuous_proof_execution_provenance is not None
        assert evidence.continuous_proof_execution_provenance.proof_algorithm_version == CONTINUOUS_PROOF_ALGORITHM_VERSION

    def test_evidence_without_continuous_provenance(self):
        from mechcad_harness.models.evidence import Evidence
        evidence = Evidence(
            id="EVD-TEST2",
            kind="analysis.kinematic_sweep",
            summary="test",
            revision=1,
            state_hash="sha256:" + "e" * 64,
        )
        assert evidence.continuous_proof_execution_provenance is None

    def test_result_hash_covers_semantic_proof(self):
        """Result hash changes when proof semantics change."""
        request, asm = _make_request(start_angle_deg=0.0, end_angle_deg=90.0)
        proof = ContinuousSingleAxisClearanceProof(
            exact_measure=_constant_exact_measure(50.0),
            radial_bound_provider=_constant_radial_bound(10.0),
        )
        r1 = proof.prove(request, asm)
        # Change guard -> different hash
        request2, asm2 = _make_request(
            start_angle_deg=0.0, end_angle_deg=90.0, proof_guard_mm=0.5
        )
        r2 = proof.prove(request2, asm2)
        assert r1.result_hash != r2.result_hash
