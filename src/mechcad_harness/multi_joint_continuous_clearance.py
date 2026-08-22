from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum

from pydantic import Field, model_validator

from mechcad_harness.cad_assembly import CadAssemblyProgram, assembly_hash
from mechcad_harness.kinematic_sweep import CollisionClassification
from mechcad_harness.models.common import Model
from mechcad_harness.multi_joint_continuous_path import (
    MultiJointContinuousPathRequest,
    ReachBoundTable,
    derive_reach_bounds,
)
from mechcad_harness.multi_joint_kinematics import (
    JointConfiguration,
    MultiJointKinematicsService,
    joint_configuration_hash,
)
from mechcad_harness.transient_assembly_analysis import TransientAssemblyAnalysisRequest


class MultiJointContinuousProofStatus(StrEnum):
    VERIFIED_CLEAR = "verified_clear"
    COLLISION_WITNESS = "collision_witness"
    NOT_PROVEN = "not_proven"


class ProofWitnessLocation(Model):
    waypoint_index: int | None = Field(default=None, ge=0)
    segment_index: int | None = Field(default=None, ge=0)
    t: float | None = None

    @model_validator(mode="after")
    def validate_location(self):
        if self.waypoint_index is not None:
            if self.segment_index is not None or self.t is not None:
                raise ValueError("waypoint witness cannot have segment location")
        elif self.segment_index is None or self.t is None or not 0 < self.t < 1:
            raise ValueError("interior witness requires segment index and t in (0, 1)")
        return self


class MultiJointContinuousCollisionWitness(Model):
    location: ProofWitnessLocation
    configuration: JointConfiguration
    configuration_hash: str = Field(min_length=1)
    transformed_assembly_hash: str = Field(min_length=1)
    moving_instance_id: str = Field(min_length=1)
    stationary_instance_id: str = Field(min_length=1)
    interference_volume_mm3: float = Field(ge=0)
    exact_distance_mm: float = Field(ge=0)
    classification: CollisionClassification


class ContinuousExactPairResult(Model):
    moving_instance_id: str = Field(min_length=1)
    stationary_instance_id: str = Field(min_length=1)
    interference_volume_mm3: float = Field(ge=0)
    exact_distance_mm: float = Field(ge=0)
    classification: CollisionClassification


class ContinuousExactEvaluation(Model):
    evaluation_index: int = Field(ge=0)
    location: ProofWitnessLocation
    configuration: JointConfiguration
    configuration_hash: str = Field(min_length=1)
    transformed_assembly_hash: str = Field(min_length=1)
    pair_results: tuple[ContinuousExactPairResult, ...] = Field(min_length=1)
    produced_requested_clearance_witness: bool


class ContinuousPairCertificate(Model):
    moving_instance_id: str = Field(min_length=1)
    stationary_instance_id: str = Field(min_length=1)
    exact_distance_mm: float = Field(ge=0)
    motion_bound_A_mm: float = Field(ge=0)
    motion_bound_B_mm: float = Field(ge=0)
    pair_motion_bound_mm: float = Field(ge=0)
    certified_lower_clearance_mm: float


class ContinuousIntervalCertificate(Model):
    segment_index: int = Field(ge=0)
    t_start: float
    t_end: float
    t_reference: float
    reference_configuration: JointConfiguration
    reference_configuration_hash: str = Field(min_length=1)
    transformed_assembly_hash: str = Field(min_length=1)
    pair_certificates: tuple[ContinuousPairCertificate, ...] = Field(min_length=1)


class UnresolvedInterval(Model):
    segment_index: int = Field(ge=0)
    t_start: float
    t_end: float
    t_reference: float | None = None
    reason: str = Field(min_length=1)
    resource_limit_reached: bool


class ContinuousSegmentResult(Model):
    segment_index: int = Field(ge=0)
    certified_intervals: tuple[ContinuousIntervalCertificate, ...] = ()
    unresolved_intervals: tuple[UnresolvedInterval, ...] = ()


class MultiJointContinuousClearanceProofResult(Model):
    request_hash: str = Field(min_length=1)
    source_assembly_hash: str = Field(min_length=1)
    model_hash: str = Field(min_length=1)
    proof_algorithm_version: str = Field(min_length=1)
    reach_bound_algorithm_version: str = Field(min_length=1)
    status: MultiJointContinuousProofStatus
    segment_results: tuple[ContinuousSegmentResult, ...]
    certified_leaf_certificates: tuple[ContinuousIntervalCertificate, ...] = ()
    unresolved_intervals: tuple[UnresolvedInterval, ...] = ()
    collision_witness: MultiJointContinuousCollisionWitness | None = None
    reach_bounds: ReachBoundTable
    exact_evaluations: tuple[ContinuousExactEvaluation, ...] = ()
    exact_evaluations_count: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    continuous_path_verified: bool = False
    minimum_certified_lower_clearance_mm: float | None = None
    result_hash: str = "pending"

    @model_validator(mode="after")
    def validate_flag(self):
        if self.continuous_path_verified != (self.status is MultiJointContinuousProofStatus.VERIFIED_CLEAR):
            raise ValueError("continuous_path_verified does not match proof status")
        return self


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def continuous_clearance_result_hash(result: MultiJointContinuousClearanceProofResult) -> str:
    return _digest(result.model_dump(mode="json", exclude={"result_hash"}))


class MultiJointContinuousClearanceProofService:
    def __init__(self, *, exact_measure, extent_provider, kinematics_service=None):
        self.exact_measure = exact_measure
        self.extent_provider = extent_provider
        self.kinematics_service = kinematics_service or MultiJointKinematicsService()

    def execute(self, request: MultiJointContinuousPathRequest, assembly: CadAssemblyProgram):
        if request.source_assembly_id != assembly.assembly_id or request.source_assembly_hash != assembly_hash(assembly):
            raise ValueError("source assembly identity mismatch")
        extents = self.extent_provider(assembly, request.model, tuple(
            item.instance_id for item in assembly.instances
        ))
        bounds = derive_reach_bounds(assembly, request.model, extents)
        pairs = request.pairs
        cache = {}
        exact_calls = 0
        cache_hits = 0
        waypoint_results = []
        exact_evaluations = []
        witness = None

        def evaluate(configuration, location):
            nonlocal exact_calls, cache_hits, witness
            key = (request.source_assembly_hash, request.model_hash,
                   joint_configuration_hash(configuration), pairs,
                   request.volume_tolerance_mm3, request.distance_tolerance_mm)
            if key in cache:
                cache_hits += 1
                result = cache[key]
            else:
                if exact_calls >= request.max_exact_evaluations:
                    return None
                fk = self.kinematics_service.evaluate(assembly, request.model, configuration)
                transient_request = TransientAssemblyAnalysisRequest(
                    source_assembly_hash=request.source_assembly_hash,
                    transformed_assembly_hash=fk.transformed_assembly_hash,
                    sweep_request_hash=request.request_hash,
                    sample_id=joint_configuration_hash(configuration),
                    pairs=pairs,
                )
                measurements = tuple(self.exact_measure(transient_request, fk.transformed_assembly))
                if tuple((a, b) for a, b, _, _ in measurements) != pairs:
                    raise ValueError("exact measurement pairs do not match request")
                result = (fk, measurements)
                cache[key] = result
                pair_results = []
                evaluation_witness = False
                first_witness = None
                for moving, stationary, volume, distance in measurements:
                    classification = CollisionClassification.from_measurement(
                        volume, distance,
                        volume_tolerance_mm3=request.volume_tolerance_mm3,
                        distance_tolerance_mm=request.distance_tolerance_mm,
                    )
                    pair_results.append(ContinuousExactPairResult(
                        moving_instance_id=moving,
                        stationary_instance_id=stationary,
                        interference_volume_mm3=volume,
                        exact_distance_mm=distance,
                        classification=classification,
                    ))
                    if classification in (CollisionClassification.INTERFERENCE, CollisionClassification.TOUCHING) or distance <= request.required_clearance_mm:
                        evaluation_witness = True
                        if first_witness is None:
                            first_witness = (moving, stationary, volume, distance, classification)
                exact_evaluations.append(ContinuousExactEvaluation(
                    evaluation_index=exact_calls,
                    location=location,
                    configuration=configuration,
                    configuration_hash=joint_configuration_hash(configuration),
                    transformed_assembly_hash=fk.transformed_assembly_hash,
                    pair_results=tuple(pair_results),
                    produced_requested_clearance_witness=evaluation_witness,
                ))
                exact_calls += 1
            fk, measurements = result
            if key not in cache:
                raise AssertionError("exact evaluation cache insertion failed")
            for moving, stationary, volume, distance in measurements:
                classification = CollisionClassification.from_measurement(
                    volume, distance,
                    volume_tolerance_mm3=request.volume_tolerance_mm3,
                    distance_tolerance_mm=request.distance_tolerance_mm,
                )
                if witness is None and (classification in (CollisionClassification.INTERFERENCE, CollisionClassification.TOUCHING) or distance <= request.required_clearance_mm):
                    location_value = location
                    witness = MultiJointContinuousCollisionWitness(
                        location=location_value,
                        configuration=configuration,
                        configuration_hash=joint_configuration_hash(configuration),
                        transformed_assembly_hash=fk.transformed_assembly_hash,
                        moving_instance_id=moving,
                        stationary_instance_id=stationary,
                        interference_volume_mm3=volume,
                        exact_distance_mm=distance,
                        classification=classification,
                    )
                    return result
            return result

        for index, configuration in enumerate(request.path.waypoints):
            if evaluate(configuration, ProofWitnessLocation(waypoint_index=index)) is None:
                unresolved_segment = min(index, len(request.path.waypoints) - 2)
                unresolved = (UnresolvedInterval(
                    segment_index=unresolved_segment,
                    t_start=0.0,
                    t_end=1.0,
                    reason="exact evaluation budget exhausted during waypoint validation",
                    resource_limit_reached=True,
                ),)
                return self._result(request, bounds, (), unresolved, None, exact_calls, cache_hits, tuple(), tuple(exact_evaluations))
            if witness is not None:
                return self._result(request, bounds, (), (), witness, exact_calls, cache_hits, tuple(), tuple(exact_evaluations))
            waypoint_results.append(configuration)

        certificates = []
        unresolved = []
        segment_results = []

        def prove(segment_index, start, end, depth):
            midpoint = (start + end) / 2
            configuration = request.path.interpolate(segment_index, midpoint)
            evaluated = evaluate(configuration, ProofWitnessLocation(segment_index=segment_index, t=midpoint))
            if evaluated is None:
                unresolved.append(UnresolvedInterval(segment_index=segment_index, t_start=start, t_end=end, t_reference=midpoint, reason="exact evaluation budget exhausted", resource_limit_reached=True))
                return
            if witness is not None:
                return
            fk, measurements = evaluated
            pair_certificates = []
            interval_clear = True
            segment_a = request.path.waypoints[segment_index]
            segment_b = request.path.waypoints[segment_index + 1]
            half_span = (end - start) / 2
            for moving, stationary, volume, distance in measurements:
                body_bounds = []
                for instance_id in (moving, stationary):
                    total = 0.0
                    for joint in request.model.joints:
                        record = bounds.for_instance_joint(instance_id, joint.joint_id)
                        if record is not None:
                            delta = math.radians(abs(segment_b.positions[joint.joint_id] - segment_a.positions[joint.joint_id]) * half_span)
                            total += 2 * record.reach_bound_mm * math.sin(min(delta, math.pi) / 2) + 1e-9
                    body_bounds.append(total)
                relative = sum(body_bounds)
                lower = distance - relative
                pair_certificates.append(ContinuousPairCertificate(
                    moving_instance_id=moving, stationary_instance_id=stationary,
                    exact_distance_mm=distance, motion_bound_A_mm=body_bounds[0],
                    motion_bound_B_mm=body_bounds[1], pair_motion_bound_mm=relative,
                    certified_lower_clearance_mm=lower,
                ))
                interval_clear &= lower > request.required_clearance_mm + request.proof_guard_mm
            if interval_clear:
                certificates.append(ContinuousIntervalCertificate(
                    segment_index=segment_index, t_start=start, t_end=end,
                    t_reference=midpoint, reference_configuration=configuration,
                    reference_configuration_hash=joint_configuration_hash(configuration),
                    transformed_assembly_hash=fk.transformed_assembly_hash,
                    pair_certificates=tuple(pair_certificates),
                ))
                return
            if depth >= request.max_depth or end - start <= request.minimum_path_interval:
                unresolved.append(UnresolvedInterval(segment_index=segment_index, t_start=start, t_end=end, t_reference=midpoint, reason="conservative bound did not certify", resource_limit_reached=False))
                return
            prove(segment_index, start, midpoint, depth + 1)
            if witness is None:
                prove(segment_index, midpoint, end, depth + 1)

        for segment_index in range(len(request.path.waypoints) - 1):
            prove(segment_index, 0.0, 1.0, 0)
            segment_results.append(ContinuousSegmentResult(
                segment_index=segment_index,
                certified_intervals=tuple(item for item in certificates if item.segment_index == segment_index),
                unresolved_intervals=tuple(item for item in unresolved if item.segment_index == segment_index),
            ))
            if witness is not None:
                break
        if witness is None and not unresolved:
            for segment_index, segment in enumerate(segment_results):
                intervals = sorted(segment.certified_intervals, key=lambda item: item.t_start)
                cursor = 0.0
                for interval in intervals:
                    if not math.isclose(interval.t_start, cursor, rel_tol=0.0, abs_tol=1e-12):
                        raise ValueError("certified path leaves do not have complete coverage")
                    if interval.t_end <= interval.t_start:
                        raise ValueError("certified path leaf is not increasing")
                    cursor = interval.t_end
                if not math.isclose(cursor, 1.0, rel_tol=0.0, abs_tol=1e-12):
                    raise ValueError("certified path leaves do not end at segment boundary")
        return self._result(request, bounds, tuple(segment_results), tuple(unresolved), witness, exact_calls, cache_hits, tuple(certificates), tuple(exact_evaluations))

    def _result(self, request, bounds, segments, unresolved, witness, exact_calls, cache_hits, certificates=(), exact_evaluations=()):
        status = MultiJointContinuousProofStatus.COLLISION_WITNESS if witness else (MultiJointContinuousProofStatus.NOT_PROVEN if unresolved else MultiJointContinuousProofStatus.VERIFIED_CLEAR)
        result = MultiJointContinuousClearanceProofResult(
            request_hash=request.request_hash, source_assembly_hash=request.source_assembly_hash,
            model_hash=request.model_hash,
            proof_algorithm_version="conservative-multi-joint-path-clearance-proof@1.0",
            reach_bound_algorithm_version=bounds.algorithm_version, status=status,
            segment_results=segments, certified_leaf_certificates=certificates,
            unresolved_intervals=unresolved, collision_witness=witness,
            reach_bounds=bounds, exact_evaluations=exact_evaluations,
            exact_evaluations_count=exact_calls,
            cache_hits=cache_hits, continuous_path_verified=status is MultiJointContinuousProofStatus.VERIFIED_CLEAR,
            minimum_certified_lower_clearance_mm=(min((pair.certified_lower_clearance_mm for leaf in certificates for pair in leaf.pair_certificates), default=None)),
        )
        return result.model_copy(update={"result_hash": continuous_clearance_result_hash(result)})


__all__ = [
    "ContinuousExactEvaluation",
    "ContinuousExactPairResult",
    "ContinuousPairCertificate",
    "MultiJointContinuousClearanceProofResult",
    "MultiJointContinuousClearanceProofService",
    "MultiJointContinuousCollisionWitness",
    "MultiJointContinuousProofStatus",
    "ProofWitnessLocation",
    "continuous_clearance_result_hash",
]
