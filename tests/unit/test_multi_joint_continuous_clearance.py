from __future__ import annotations

from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, CadRigidTransform, assembly_hash
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.multi_joint_continuous_clearance import (
    ContinuousExactEvaluation,
    MultiJointContinuousClearanceProofService,
    MultiJointContinuousProofStatus,
)
from mechcad_harness.multi_joint_continuous_path import (
    MultiJointContinuousPathRequest,
    MultiJointPath,
    TrustedLocalGeometryExtent,
)
from mechcad_harness.multi_joint_kinematics import JointConfiguration, KinematicModel, RevoluteJointModel


PART = CadPartProgram(
    part_id="p",
    operations=(BasePlateOperation(operation_id="op", length_mm=5, width_mm=5, thickness_mm=2),),
)
ASSEMBLY = CadAssemblyProgram(
    assembly_id="proof-assembly",
    parts=(PART,),
    instances=(
        CadComponentInstance(instance_id="base", part_id="p"),
        CadComponentInstance(instance_id="a", part_id="p", placement=CadRigidTransform(x_mm=20)),
        CadComponentInstance(instance_id="b", part_id="p", placement=CadRigidTransform(x_mm=40)),
    ),
)
MODEL = KinematicModel(
    model_id="proof-model",
    joints=(
        RevoluteJointModel(joint_id="j1", parent_instance_id="base", child_instance_id="a"),
        RevoluteJointModel(joint_id="j2", parent_instance_id="a", child_instance_id="b", axis_origin_x_mm=20),
    ),
)
EXTENTS = {
    instance_id: TrustedLocalGeometryExtent(
        instance_id=instance_id, component_identity="p@extent", local_radius_mm=1
    )
    for instance_id in ("base", "a", "b")
}


def request(*, waypoints=((0, 0), (10, 10)), max_exact_evaluations=20, required_clearance=0.0, max_depth=0):
    path = MultiJointPath(
        model_id=MODEL.model_id,
        waypoints=tuple(
            JointConfiguration(model_id=MODEL.model_id, positions={"j1": q1, "j2": q2})
            for q1, q2 in waypoints
        ),
    )
    return MultiJointContinuousPathRequest(
        source_assembly_id=ASSEMBLY.assembly_id,
        source_assembly_hash=assembly_hash(ASSEMBLY),
        model=MODEL,
        path=path,
        moving_instance_ids=("a", "b"),
        stationary_instance_ids=("base",),
        required_clearance_mm=required_clearance,
        max_exact_evaluations=max_exact_evaluations,
        max_depth=max_depth,
    )


def service(measure):
    return MultiJointContinuousClearanceProofService(
        exact_measure=measure,
        extent_provider=lambda assembly, model, instance_ids: {
            instance_id: EXTENTS[instance_id] for instance_id in instance_ids
        },
    )


def all_pairs(requested, distance=10.0, volume=0.0):
    return tuple((a, b, volume, distance) for a, b in requested.pairs)


def test_clear_path_certifies_and_cache_budget_counts_unique_provider_calls():
    calls = []

    def measure(transient_request, transformed):
        calls.append(transient_request.sample_id)
        return all_pairs(transient_request, distance=100.0)

    result = service(measure).execute(
        request(waypoints=((0, 0), (10, 10), (10, 10))), ASSEMBLY
    )
    assert result.status is MultiJointContinuousProofStatus.VERIFIED_CLEAR
    assert result.continuous_path_verified is True
    assert result.exact_evaluations_count == len(set(calls))
    assert result.cache_hits >= 1
    assert result.certified_leaf_certificates
    assert result.segment_results[0].certified_intervals[0].t_start == 0.0
    assert result.segment_results[0].certified_intervals[-1].t_end == 1.0
    assert [item.evaluation_index for item in result.exact_evaluations] == [0, 1, 2]
    assert result.exact_evaluations[0].location.waypoint_index == 0
    assert result.exact_evaluations[1].location.waypoint_index == 1
    assert result.exact_evaluations[2].location.segment_index == 0
    assert result.exact_evaluations[2].location.t == 0.5
    assert all(item.pair_results for item in result.exact_evaluations)


def test_exact_evaluation_trace_retains_subdivision_midpoints_without_cache_duplicates():
    def measure(transient_request, transformed):
        return all_pairs(transient_request, distance=1.0)

    result = service(measure).execute(
        request(max_exact_evaluations=20, max_depth=1), ASSEMBLY
    )
    assert result.status is MultiJointContinuousProofStatus.NOT_PROVEN
    assert len(result.exact_evaluations) == result.exact_evaluations_count
    assert [item.evaluation_index for item in result.exact_evaluations] == list(range(len(result.exact_evaluations)))
    assert any(item.location.segment_index == 0 and item.location.t == 0.25 for item in result.exact_evaluations)
    assert any(item.location.segment_index == 0 and item.location.t == 0.75 for item in result.exact_evaluations)
    assert all(isinstance(item, ContinuousExactEvaluation) for item in result.exact_evaluations)


def test_exact_requested_clearance_violation_is_witness_without_proof_guard():
    def measure(transient_request, transformed):
        return all_pairs(transient_request, distance=5.0)

    result = service(measure).execute(
        request(required_clearance=5.0), ASSEMBLY
    )
    assert result.status is MultiJointContinuousProofStatus.COLLISION_WITNESS
    assert result.collision_witness is not None
    assert result.collision_witness.location.waypoint_index == 0
    assert result.continuous_path_verified is False


def test_shared_interior_waypoint_witness_uses_canonical_waypoint_index():
    seen = []

    def measure(transient_request, transformed):
        seen.append(transient_request.sample_id)
        if len(seen) == 2:
            return all_pairs(transient_request, distance=0.0, volume=1.0)
        return all_pairs(transient_request, distance=100.0)

    result = service(measure).execute(
        request(waypoints=((0, 0), (10, 10), (20, 20))), ASSEMBLY
    )
    assert result.collision_witness is not None
    assert result.collision_witness.location.waypoint_index == 1
    assert result.collision_witness.location.segment_index is None


def test_budget_exhaustion_after_real_waypoint_measurement_is_not_proven():
    calls = []

    def measure(transient_request, transformed):
        calls.append(transient_request.sample_id)
        return all_pairs(transient_request, distance=100.0)

    result = service(measure).execute(
        request(max_exact_evaluations=2), ASSEMBLY
    )
    assert calls
    assert result.status is MultiJointContinuousProofStatus.NOT_PROVEN
    assert result.exact_evaluations_count == 2
    assert result.unresolved_intervals
    assert result.continuous_path_verified is False


def test_budget_exhaustion_during_waypoint_validation_is_not_proven():
    calls = []

    def measure(transient_request, transformed):
        calls.append(transient_request.sample_id)
        return all_pairs(transient_request, distance=100.0)

    result = service(measure).execute(
        request(max_exact_evaluations=1), ASSEMBLY
    )
    assert calls
    assert result.status is MultiJointContinuousProofStatus.NOT_PROVEN
    assert result.unresolved_intervals
    assert result.continuous_path_verified is False


def test_both_pair_sides_motion_is_recorded_in_relative_bound():
    def measure(transient_request, transformed):
        return all_pairs(transient_request, distance=100.0)

    both_sides = request()
    both_sides = both_sides.model_copy(
        update={
            "moving_instance_ids": ("a",),
            "stationary_instance_ids": ("b",),
            "request_hash": "pending",
        }
    )
    result = service(measure).execute(both_sides, ASSEMBLY)
    certificate = result.certified_leaf_certificates[0]
    pair = certificate.pair_certificates[0]
    assert pair.motion_bound_A_mm > 0
    assert pair.motion_bound_B_mm > 0
    assert pair.pair_motion_bound_mm == pair.motion_bound_A_mm + pair.motion_bound_B_mm
