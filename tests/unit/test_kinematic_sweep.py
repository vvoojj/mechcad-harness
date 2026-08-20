import math

import pytest

from mechcad_harness.cad_assembly import CadComponentInstance, CadRigidTransform
from mechcad_harness.kinematic_sweep import (
    CadKinematicCollisionPairResult,
    CadKinematicSweepResult,
    CadKinematicSweepSample,
    CadKinematicSweepRequest,
    CadKinematicSweepService,
    CollisionClassification,
    SweepAggregateClassification,
    RevoluteAxis,
    transformed_assembly_program,
    transform_moving_instances,
)


def _axis(**overrides):
    payload = {"origin_x_mm": 0, "origin_y_mm": 0, "origin_z_mm": 0, "direction_x": 0, "direction_y": 1, "direction_z": 0, "frame_id": "fixture"}
    payload.update(overrides)
    return RevoluteAxis(**payload)


def test_revolute_axis_normalizes_direction_and_rejects_invalid_values():
    assert _axis(direction_y=2).direction == (0.0, 1.0, 0.0)
    with pytest.raises(ValueError, match="non-zero"):
        _axis(direction_y=0)
    with pytest.raises(ValueError, match="finite"):
        _axis(direction_y=math.inf)


def test_rigid_rotation_moves_point_and_orientation_at_zero_ninety_one_eighty_and_full_turn():
    instance = CadComponentInstance(instance_id="moving", part_id="part", placement=CadRigidTransform(x_mm=10))
    assert transform_moving_instances((instance,), _axis(), 0)[0].placement.x_mm == pytest.approx(10)
    ninety = transform_moving_instances((instance,), _axis(), 90)[0].placement
    assert (ninety.x_mm, ninety.y_mm, ninety.z_mm) == pytest.approx((0, 0, -10))
    assert ninety.rotation_quaternion == pytest.approx((math.sqrt(0.5), 0, math.sqrt(0.5), 0))
    one_eighty = transform_moving_instances((instance,), _axis(), 180)[0].placement
    assert (one_eighty.x_mm, one_eighty.y_mm, one_eighty.z_mm) == pytest.approx((-10, 0, 0))
    full_turn = transform_moving_instances((instance,), _axis(), 360)[0].placement
    assert (full_turn.x_mm, full_turn.y_mm, full_turn.z_mm) == pytest.approx((10, 0, 0), abs=1e-9)
    assert full_turn.rotation_quaternion == pytest.approx((1, 0, 0, 0), abs=1e-9)


def test_rotation_honors_non_origin_axis_and_preserves_group_distances_and_stationary_instances():
    moving = (
        CadComponentInstance(instance_id="one", part_id="one", placement=CadRigidTransform(x_mm=11, y_mm=2, z_mm=3)),
        CadComponentInstance(instance_id="two", part_id="two", placement=CadRigidTransform(x_mm=14, y_mm=2, z_mm=3)),
    )
    rotated = transform_moving_instances(moving, _axis(origin_x_mm=1, origin_y_mm=2, origin_z_mm=3), 90)
    assert (rotated[0].placement.x_mm, rotated[0].placement.y_mm, rotated[0].placement.z_mm) == pytest.approx((1, 2, -7))
    before = math.dist((11, 2, 3), (14, 2, 3))
    after = math.dist(*(tuple((item.placement.x_mm, item.placement.y_mm, item.placement.z_mm) for item in rotated)))
    assert after == pytest.approx(before)


def test_collision_classifications_distinguish_interference_touching_and_clearance():
    assert CollisionClassification.from_measurement(1e-3, 0) is CollisionClassification.INTERFERENCE
    assert CollisionClassification.from_measurement(0, 0) is CollisionClassification.TOUCHING
    assert CollisionClassification.from_measurement(0, 1) is CollisionClassification.POSITIVE_CLEARANCE


def test_sweep_request_preserves_angle_order_and_rejects_invalid_instance_sets():
    request = CadKinematicSweepRequest(
        source_assembly_id="assembly",
        source_assembly_hash="sha256:assembly",
        axis=_axis(),
        sample_angles_deg=(0, 90, 15),
        moving_instance_ids=("moving",),
        stationary_instance_ids=("obstacle",),
    )
    assert request.sample_angles_deg == (0.0, 90.0, 15.0)
    assert request.request_hash == CadKinematicSweepRequest(**request.model_dump(exclude={"request_hash"})).request_hash
    with pytest.raises(ValueError, match="duplicate"):
        CadKinematicSweepRequest(**(request.model_dump(exclude={"request_hash"}) | {"moving_instance_ids": ("moving", "moving")}))
    with pytest.raises(ValueError, match="overlap"):
        CadKinematicSweepRequest(**(request.model_dump(exclude={"request_hash"}) | {"stationary_instance_ids": ("moving",)}))


def test_transformed_assembly_changes_only_moving_instances():
    from mechcad_harness.cad_assembly import CadAssemblyProgram
    from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram

    moving = CadComponentInstance(instance_id="moving", part_id="moving", placement=CadRigidTransform(x_mm=10))
    stationary = CadComponentInstance(instance_id="obstacle", part_id="obstacle", placement=CadRigidTransform(x_mm=20))
    assembly = CadAssemblyProgram(
        assembly_id="assembly",
        parts=(
            CadPartProgram(part_id="moving", operations=(BasePlateOperation(operation_id="base", length_mm=1, width_mm=1, thickness_mm=1),)),
            CadPartProgram(part_id="obstacle", operations=(BasePlateOperation(operation_id="base", length_mm=1, width_mm=1, thickness_mm=1),)),
        ),
        instances=(moving, stationary),
    )
    transformed = transformed_assembly_program(assembly, _axis(), 90, ("moving",), ("obstacle",))
    by_id = {item.instance_id: item for item in transformed.instances}
    assert (by_id["moving"].placement.x_mm, by_id["moving"].placement.z_mm) == pytest.approx((0, -10))
    assert by_id["obstacle"].placement == stationary.placement


def _sample(angle, classification, volume=0, distance=1):
    return CadKinematicSweepSample(
        angle_deg=angle,
        transformed_assembly_hash=f"sha256:{angle}",
        pair_results=(CadKinematicCollisionPairResult(moving_instance_id="moving", stationary_instance_id="obstacle", interference_volume_mm3=volume, exact_distance_mm=distance, classification=classification),),
        maximum_interference_volume_mm3=volume,
        minimum_exact_distance_mm=distance,
        classification=classification,
    )


def test_sweep_result_aggregates_request_order_and_hashes_deterministically():
    request = CadKinematicSweepRequest(source_assembly_id="assembly", source_assembly_hash="sha256:assembly", axis=_axis(), sample_angles_deg=(90, 0, 180), moving_instance_ids=("moving",), stationary_instance_ids=("obstacle",))
    result = CadKinematicSweepResult.from_samples(request, (
        _sample(90, CollisionClassification.POSITIVE_CLEARANCE, distance=5),
        _sample(0, CollisionClassification.INTERFERENCE, volume=2, distance=0),
        _sample(180, CollisionClassification.INTERFERENCE, volume=2, distance=0),
    ))
    assert result.aggregate_classification is SweepAggregateClassification.COLLISION_PRESENT
    assert result.first_collision_angle_deg == 0
    assert result.worst_interference_angle_deg == 0
    assert result.minimum_clearance_angle_deg == 0
    assert result.continuous_sweep_verified is False
    assert result.result_hash == CadKinematicSweepResult.from_samples(request, result.samples).result_hash


def test_touching_and_clear_only_sweeps_aggregate_without_claiming_continuous_proof():
    request = CadKinematicSweepRequest(source_assembly_id="assembly", source_assembly_hash="sha256:assembly", axis=_axis(), sample_angles_deg=(0, 90), moving_instance_ids=("moving",), stationary_instance_ids=("obstacle",))
    touching = CadKinematicSweepResult.from_samples(request, (_sample(0, CollisionClassification.TOUCHING, distance=0), _sample(90, CollisionClassification.POSITIVE_CLEARANCE, distance=5)))
    clear = CadKinematicSweepResult.from_samples(request, (_sample(0, CollisionClassification.POSITIVE_CLEARANCE, distance=1), _sample(90, CollisionClassification.POSITIVE_CLEARANCE, distance=5)))
    assert touching.aggregate_classification is SweepAggregateClassification.TOUCHING_PRESENT
    assert clear.aggregate_classification is SweepAggregateClassification.COLLISION_FREE
    assert clear.continuous_sweep_verified is False


def test_execution_service_rejects_source_hash_mismatch_and_derives_only_moving_stationary_pairs():
    from mechcad_harness.cad_assembly import CadAssemblyProgram, assembly_hash
    from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram

    assembly = CadAssemblyProgram(
        assembly_id="assembly",
        parts=(
            CadPartProgram(part_id="moving", operations=(BasePlateOperation(operation_id="moving", length_mm=1, width_mm=1, thickness_mm=1),)),
            CadPartProgram(part_id="obstacle", operations=(BasePlateOperation(operation_id="obstacle", length_mm=1, width_mm=1, thickness_mm=1),)),
        ),
        instances=(CadComponentInstance(instance_id="moving", part_id="moving"), CadComponentInstance(instance_id="obstacle", part_id="obstacle")),
    )
    request = CadKinematicSweepRequest(source_assembly_id="assembly", source_assembly_hash=assembly_hash(assembly), axis=_axis(), sample_angles_deg=(0,), moving_instance_ids=("moving",), stationary_instance_ids=("obstacle",))
    service = CadKinematicSweepService()
    assert service.collision_pairs(request) == (("moving", "obstacle"),)
    with pytest.raises(ValueError, match="hash mismatch"):
        service.validate_source(request.model_copy(update={"source_assembly_hash": "sha256:other", "request_hash": "pending"}), assembly)


def test_execution_service_preserves_request_order_and_propagates_pair_measurements():
    from mechcad_harness.cad_assembly import CadAssemblyProgram, assembly_hash
    from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram

    assembly = CadAssemblyProgram(
        assembly_id="assembly",
        parts=(
            CadPartProgram(part_id="moving", operations=(BasePlateOperation(operation_id="moving", length_mm=1, width_mm=1, thickness_mm=1),)),
            CadPartProgram(part_id="obstacle", operations=(BasePlateOperation(operation_id="obstacle", length_mm=1, width_mm=1, thickness_mm=1),)),
        ),
        instances=(CadComponentInstance(instance_id="moving", part_id="moving", placement=CadRigidTransform(x_mm=10)), CadComponentInstance(instance_id="obstacle", part_id="obstacle")),
    )
    request = CadKinematicSweepRequest(source_assembly_id="assembly", source_assembly_hash=assembly_hash(assembly), axis=_axis(), sample_angles_deg=(180, 0, 90), moving_instance_ids=("moving",), stationary_instance_ids=("obstacle",))
    calls = []

    class RecordingTransientAnalysisService:
        def analyze(self, transient_request, program):
            calls.append((transient_request, program))
            volume, distance = {180: (0, 2), 0: (1, 0), 90: (0, 0)}[int(transient_request.sample_angle_deg)]
            return type("TransientResult", (), {"measurements": (("moving", "obstacle", volume, distance),)})()

    result = CadKinematicSweepService(transient_analysis_service=RecordingTransientAnalysisService()).execute(request, assembly)
    assert [sample.angle_deg for sample in result.samples] == [180, 0, 90]
    assert [call_request.sample_angle_deg for call_request, _ in calls] == [180, 0, 90]
    assert [call_request.source_assembly_hash for call_request, _ in calls] == [request.source_assembly_hash] * 3
    assert [call_request.sweep_request_hash for call_request, _ in calls] == [request.request_hash] * 3
    assert [call_request.pairs for call_request, _ in calls] == [(('moving', 'obstacle'),)] * 3
    assert [call_request.transformed_assembly_hash for call_request, program in calls] == [assembly_hash(program) for _, program in calls]
    assert result.samples[1].pair_results[0].interference_volume_mm3 == 1
    assert result.samples[2].classification is CollisionClassification.TOUCHING
    assert result.aggregate_classification is SweepAggregateClassification.COLLISION_PRESENT
