from __future__ import annotations

import math

import pytest

from mechcad_harness.continuous_proof import (
    ContinuousSingleAxisProofResult,
    ContinuousSingleAxisProofStatus,
    motion_bound,
)
from mechcad_harness.kinematic_sweep import RevoluteAxis
from mechcad_harness.multi_joint_continuous_clearance import (
    MultiJointContinuousProofStatus,
)
from tests.unit.test_multi_joint_continuous_clearance import (
    ASSEMBLY,
    all_pairs,
    request,
    service,
)


def _multi_joint_motion_contribution(delta_rad: float) -> tuple[float, float]:
    endpoint_delta_deg = math.degrees(2.0 * delta_rad)
    proof_request = request(
        waypoints=((0.0, 0.0), (endpoint_delta_deg, 1.0)),
        max_depth=0,
    )
    result = service(
        lambda transient_request, transformed: all_pairs(
            transient_request, distance=1000.0
        )
    ).execute(proof_request, ASSEMBLY)
    reach = result.reach_bounds.for_instance_joint("a", "j1")
    assert reach is not None
    return reach.reach_bound_mm, result.certified_leaf_certificates[0].pair_certificates[0].motion_bound_A_mm


@pytest.mark.parametrize("delta_rad", (0.0, 0.01, math.pi / 2.0, math.pi, 2.0 * math.pi))
def test_m10_1_and_m10_4_motion_bounds_retain_distinct_padding(delta_rad: float):
    reach_mm, multi_joint_bound_mm = _multi_joint_motion_contribution(delta_rad)
    capped_delta = min(abs(delta_rad), math.pi)
    expected_multi_joint = 2.0 * reach_mm * math.sin(capped_delta / 2.0) + 1e-9

    assert multi_joint_bound_mm == expected_multi_joint
    assert motion_bound(reach_mm, delta_rad) == (
        2.0 * reach_mm * math.sin(capped_delta / 2.0)
        + 1e-9 * (1.0 + abs(reach_mm))
    )
    assert multi_joint_bound_mm != motion_bound(reach_mm, delta_rad)


def test_m10_4_accumulates_one_fixed_pad_per_influencing_joint():
    delta_rad = math.pi / 2.0
    endpoint_delta_deg = math.degrees(2.0 * delta_rad)
    proof_request = request(
        waypoints=((0.0, 0.0), (endpoint_delta_deg, 2.0)),
        max_depth=0,
    )
    result = service(
        lambda transient_request, transformed: all_pairs(
            transient_request, distance=1000.0
        )
    ).execute(proof_request, ASSEMBLY)

    b_pair = result.certified_leaf_certificates[0].pair_certificates[1]
    reach_j1 = result.reach_bounds.for_instance_joint("b", "j1")
    reach_j2 = result.reach_bounds.for_instance_joint("b", "j2")
    assert reach_j1 is not None
    assert reach_j2 is not None
    delta_j1 = delta_rad
    delta_j2 = math.radians(1.0)
    expected = sum(
        2.0 * reach * math.sin(min(delta, math.pi) / 2.0) + 1e-9
        for reach, delta in ((reach_j1.reach_bound_mm, delta_j1), (reach_j2.reach_bound_mm, delta_j2))
    )
    assert b_pair.motion_bound_A_mm == expected


def test_status_enums_are_distinct_types_with_equal_wire_strings():
    for single_status, multi_status in zip(
        ContinuousSingleAxisProofStatus,
        MultiJointContinuousProofStatus,
        strict=True,
    ):
        assert single_status.value == multi_status.value
        assert single_status is not multi_status

    assert ContinuousSingleAxisProofStatus is not MultiJointContinuousProofStatus


def test_status_serialization_preserves_each_public_enum_type():
    axis = RevoluteAxis(
        origin_x_mm=0.0,
        origin_y_mm=0.0,
        origin_z_mm=0.0,
        direction_x=0.0,
        direction_y=0.0,
        direction_z=1.0,
        frame_id="axis",
    )
    single = ContinuousSingleAxisProofResult(
        request_hash="sha256:request",
        source_assembly_hash="sha256:assembly",
        proof_algorithm_version="proof@1.0",
        axis=axis,
        start_angle_deg=0.0,
        end_angle_deg=1.0,
        moving_instance_ids=("moving",),
        stationary_instance_ids=("stationary",),
        required_clearance_mm=0.0,
        proof_guard_mm=1e-6,
        status=ContinuousSingleAxisProofStatus.NOT_PROVEN,
        exact_evaluations_count=0,
        maximum_depth_reached=0,
    )
    multi = service(
        lambda transient_request, transformed: all_pairs(
            transient_request, distance=1000.0
        )
    ).execute(request(max_depth=0), ASSEMBLY)

    single_payload = single.model_dump(mode="json")
    multi_payload = multi.model_dump(mode="json")
    assert single_payload["status"] == "not_proven"
    assert multi_payload["status"] == "verified_clear"
    assert type(
        ContinuousSingleAxisProofResult.model_validate(single_payload).status
    ) is ContinuousSingleAxisProofStatus
    assert type(type(multi).model_validate(multi_payload).status) is MultiJointContinuousProofStatus
