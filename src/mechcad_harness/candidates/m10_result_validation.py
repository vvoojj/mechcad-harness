from __future__ import annotations

import hashlib
from dataclasses import dataclass

from mechcad_harness.cad_assembly import CadAssemblyProgram, assembly_hash
from mechcad_harness.continuous_proof import (
    CONTINUOUS_PROOF_ALGORITHM_VERSION,
    ContinuousSingleAxisProofRequest,
    ContinuousSingleAxisProofResult,
    ContinuousSingleAxisProofStatus,
)
from mechcad_harness.core.canonical import canonical_json_bytes
from mechcad_harness.kinematic_sweep import (
    CadKinematicSweepRequest,
    CadKinematicSweepResult,
    CollisionClassification,
    SweepAggregateClassification,
    transformed_assembly_program,
)
from mechcad_harness.models.common import Model


def m10_result_hash(result: Model) -> str:
    payload = result.model_dump(mode="json", exclude={"result_hash"})
    return "sha256:" + hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


@dataclass(frozen=True)
class ContinuousM10ResultValidationContract:
    require_source_assembly_id: bool
    allowed_collision_witness_classifications: frozenset[CollisionClassification] | None

    def validate(
        self,
        request: ContinuousSingleAxisProofRequest,
        result: ContinuousSingleAxisProofResult,
        assembly: CadAssemblyProgram | None = None,
    ) -> None:
        if assembly is not None:
            if request.source_assembly_hash != assembly_hash(assembly):
                raise ValueError("M10 continuous source assembly does not match induced assembly")
            if self.require_source_assembly_id and request.source_assembly_id != assembly.assembly_id:
                raise ValueError("M10 continuous source assembly ID does not match induced assembly")
        comparisons = (
            (result.request_hash, request.request_hash, "request"),
            (result.source_assembly_hash, request.source_assembly_hash, "source assembly"),
            (result.axis, request.axis, "axis"),
            (result.start_angle_deg, request.start_angle_deg, "path"),
            (result.end_angle_deg, request.end_angle_deg, "path"),
            (result.moving_instance_ids, request.moving_instance_ids, "moving partition"),
            (result.stationary_instance_ids, request.stationary_instance_ids, "stationary partition"),
            (result.required_clearance_mm, request.required_clearance_mm, "clearance"),
            (result.proof_guard_mm, request.proof_guard_mm, "proof guard"),
            (result.proof_algorithm_version, CONTINUOUS_PROOF_ALGORITHM_VERSION, "algorithm version"),
        )
        for actual, expected, label in comparisons:
            if actual != expected:
                raise ValueError(f"M10 continuous result {label} mismatch")
        expected_pairs = tuple(
            (moving, stationary)
            for moving in request.moving_instance_ids
            for stationary in request.stationary_instance_ids
        )
        for certificate in result.certified_leaf_certificates:
            certificate_pairs = tuple(
                (pair.moving_instance_id, pair.stationary_instance_id)
                for pair in certificate.pair_certificates
            )
            if certificate_pairs != expected_pairs:
                raise ValueError("M10 continuous certificate pair mismatch")
        if result.status is ContinuousSingleAxisProofStatus.COLLISION_WITNESS:
            if result.collision_witness is None:
                raise ValueError("M10 collision-witness result requires a witness")
        elif result.collision_witness is not None:
            raise ValueError("M10 non-collision result cannot carry a collision witness")
        if result.status is ContinuousSingleAxisProofStatus.VERIFIED_CLEAR and not result.certified_leaf_certificates:
            raise ValueError("M10 verified-clear result requires certificates")
        if result.collision_witness is not None:
            witness_pair = (
                result.collision_witness.moving_instance_id,
                result.collision_witness.stationary_instance_id,
            )
            if witness_pair not in expected_pairs:
                raise ValueError("M10 collision witness pair mismatch")
            if (
                self.allowed_collision_witness_classifications is not None
                and result.collision_witness.classification
                not in self.allowed_collision_witness_classifications
            ):
                raise ValueError("M10 collision witness classification mismatch")
        if result.result_hash != m10_result_hash(result):
            raise ValueError("M10 continuous result hash mismatch")


@dataclass(frozen=True)
class HomeM10ResultValidationContract:
    accepted_sweep_version: str | None

    def validate(
        self,
        request: CadKinematicSweepRequest,
        result: CadKinematicSweepResult,
        assembly: CadAssemblyProgram | None = None,
    ) -> None:
        if request.sample_angles_deg != (0.0,):
            raise ValueError("M10 home request must use exactly the zero-angle sample")
        if self.accepted_sweep_version is not None:
            if request.sweep_version != self.accepted_sweep_version:
                raise ValueError("M10 home request uses an unsupported discrete sweep service")
            if result.sweep_version != self.accepted_sweep_version:
                raise ValueError("M10 home result uses an unsupported discrete sweep service")
        if result.request_hash != request.request_hash:
            raise ValueError("M10 home result request identity mismatch")
        if result.source_assembly_hash != request.source_assembly_hash:
            raise ValueError("M10 home result source assembly mismatch")
        if assembly is not None:
            expected_transformed = assembly_hash(
                transformed_assembly_program(
                    assembly,
                    request.axis,
                    0.0,
                    request.moving_instance_ids,
                    request.stationary_instance_ids,
                )
            )
            if result.samples[0].transformed_assembly_hash != expected_transformed:
                raise ValueError("M10 home transformed assembly hash mismatch")
        if tuple(sample.angle_deg for sample in result.samples) != (0.0,):
            raise ValueError("M10 home result must contain exactly the zero-angle sample")
        expected_pairs = tuple(
            (moving, stationary)
            for moving in request.moving_instance_ids
            for stationary in request.stationary_instance_ids
        )
        sample = result.samples[0]
        actual_pairs = tuple(
            (pair.moving_instance_id, pair.stationary_instance_id)
            for pair in sample.pair_results
        )
        if actual_pairs != expected_pairs:
            raise ValueError("M10 home result pair mismatch")
        precedence = {
            CollisionClassification.POSITIVE_CLEARANCE: 0,
            CollisionClassification.TOUCHING: 1,
            CollisionClassification.INTERFERENCE: 2,
        }
        expected_pair_classifications = tuple(
            CollisionClassification.from_measurement(
                pair.interference_volume_mm3,
                pair.exact_distance_mm,
                volume_tolerance_mm3=request.volume_tolerance_mm3,
                distance_tolerance_mm=request.distance_tolerance_mm,
            )
            for pair in sample.pair_results
        )
        if tuple(pair.classification for pair in sample.pair_results) != expected_pair_classifications:
            raise ValueError("M10 home result pair classification mismatch")
        expected_sample_classification = max(expected_pair_classifications, key=precedence.__getitem__)
        if sample.classification is not expected_sample_classification:
            raise ValueError("M10 home result sample classification mismatch")
        expected_aggregate = (
            SweepAggregateClassification.COLLISION_PRESENT
            if CollisionClassification.INTERFERENCE in expected_pair_classifications
            else SweepAggregateClassification.TOUCHING_PRESENT
            if CollisionClassification.TOUCHING in expected_pair_classifications
            else SweepAggregateClassification.COLLISION_FREE
        )
        if result.aggregate_classification is not expected_aggregate:
            raise ValueError("M10 home result aggregate classification mismatch")
        if result.result_hash != m10_result_hash(result):
            raise ValueError("M10 home result hash mismatch")
