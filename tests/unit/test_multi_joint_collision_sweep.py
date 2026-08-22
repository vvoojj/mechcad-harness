from __future__ import annotations

import math

import pytest

from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.kinematic_sweep import CollisionClassification
from mechcad_harness.multi_joint_collision_sweep import (
    MULTI_JOINT_EXACT_COLLISION_SWEEP_VERSION,
    MultiJointCollisionSweepRequest,
    MultiJointCollisionSweepResult,
    MultiJointDiscreteCollisionSweepService,
)
from mechcad_harness.multi_joint_kinematics import (
    JointConfiguration,
    KinematicModel,
    MultiJointKinematicsService,
    RevoluteJointModel,
    joint_configuration_hash,
    kinematic_model_hash,
)
from mechcad_harness.transient_assembly_analysis import (
    TransientAssemblyAnalysisRequest,
    TransientAssemblyAnalysisService,
)


_PART = CadPartProgram(
    part_id="link",
    operations=(
        BasePlateOperation(
            operation_id="plate", length_mm=10, width_mm=10, thickness_mm=2
        ),
    ),
)


def _assembly() -> CadAssemblyProgram:
    return CadAssemblyProgram(
        assembly_id="m10-3-fixture",
        parts=(_PART,),
        instances=(
            CadComponentInstance(instance_id="base", part_id="link"),
            CadComponentInstance(
                instance_id="link-1",
                part_id="link",
                placement=CadRigidTransform(x_mm=30),
            ),
            CadComponentInstance(
                instance_id="link-2",
                part_id="link",
                placement=CadRigidTransform(x_mm=80),
            ),
        ),
    )


def _model(*, axis_direction=(0, 0, 1)) -> KinematicModel:
    return KinematicModel(
        model_id="model-3",
        joints=(
            RevoluteJointModel(
                joint_id="joint-1",
                parent_instance_id="base",
                child_instance_id="link-1",
                axis_direction_x=axis_direction[0],
                axis_direction_y=axis_direction[1],
                axis_direction_z=axis_direction[2],
            ),
            RevoluteJointModel(
                joint_id="joint-2",
                parent_instance_id="link-1",
                child_instance_id="link-2",
                axis_origin_x_mm=30,
            ),
        ),
    )


def _configuration(**positions: float) -> JointConfiguration:
    return JointConfiguration(model_id="model-3", positions=dict(positions))


def _request(
    assembly: CadAssemblyProgram | None = None,
    *,
    configurations: tuple[JointConfiguration, ...] | None = None,
    model: KinematicModel | None = None,
    moving=("link-1", "link-2"),
    stationary=("base",),
    **overrides,
) -> MultiJointCollisionSweepRequest:
    assembly = assembly or _assembly()
    model = model or _model()
    values = dict(
        source_assembly_id=assembly.assembly_id,
        source_assembly_hash=assembly_hash(assembly),
        model=model,
        configurations=(
            configurations
            if configurations is not None
            else (
            _configuration(**{"joint-1": 0, "joint-2": 0}),
            _configuration(**{"joint-1": 30, "joint-2": 0}),
            )
        ),
        moving_instance_ids=moving,
        stationary_instance_ids=stationary,
    )
    values.update(overrides)
    return MultiJointCollisionSweepRequest(**values)


def test_request_hash_is_stable_and_configuration_order_is_semantic():
    request = _request()
    assert request.request_hash == _request().request_hash
    reversed_request = _request(
        configurations=tuple(reversed(request.configurations))
    )
    assert reversed_request.request_hash != request.request_hash


def test_configuration_angle_and_model_axis_change_request_identity():
    request = _request()
    angle_changed = _request(
        configurations=(
            request.configurations[0],
            _configuration(**{"joint-1": 31, "joint-2": 0}),
        )
    )
    axis_changed = _request(model=_model(axis_direction=(1, 0, 0)))
    assert joint_configuration_hash(angle_changed.configurations[1]) != joint_configuration_hash(
        request.configurations[1]
    )
    assert angle_changed.request_hash != request.request_hash
    assert kinematic_model_hash(axis_changed.model) != kinematic_model_hash(
        request.model
    )
    assert axis_changed.request_hash != request.request_hash


def test_mapping_insertion_order_does_not_change_request_identity():
    first = _request(
        configurations=(
            JointConfiguration(
                model_id="model-3",
                positions={"joint-1": 10, "joint-2": 20},
            ),
        )
    )
    second = _request(
        configurations=(
            JointConfiguration(
                model_id="model-3",
                positions={"joint-2": 20, "joint-1": 10},
            ),
        )
    )
    assert first.request_hash == second.request_hash


def test_request_validation_is_fail_closed():
    with pytest.raises(ValueError, match="at least one configuration"):
        _request(configurations=())
    with pytest.raises(ValueError, match="evaluator version"):
        _request(evaluator_version="wrong")
    with pytest.raises(ValueError, match="model ID"):
        _request(
            configurations=(
                JointConfiguration(model_id="other", positions={"joint-1": 0, "joint-2": 0}),
            )
        )
    with pytest.raises(ValueError, match="duplicate"):
        _request(moving=("link-1", "link-1"))
    with pytest.raises(ValueError, match="duplicate"):
        _request(stationary=("base", "base"))
    with pytest.raises(ValueError, match="overlap"):
        _request(moving=("link-1",), stationary=("link-1", "base"))


def test_request_rejects_untrusted_nested_kinematics_evaluator_version():
    with pytest.raises(ValueError, match="kinematic model evaluator version"):
        _request(
            model=_model().model_copy(
                update={"evaluator_version": "other-forward-kinematics@1.0"}
            )
        )


def test_service_rejects_untrusted_nested_kinematics_evaluator_version():
    request = _request()
    tampered_model = request.model.model_copy(
        update={"evaluator_version": "other-forward-kinematics@1.0"}
    )
    tampered_request = request.model_copy(update={"model": tampered_model})

    with pytest.raises(ValueError, match="kinematic model evaluator version"):
        _service(lambda received_request, transformed: ()).execute(
            tampered_request, _assembly()
        )


@pytest.mark.parametrize(
    ("mutate", "message"),
    (
        (lambda request: setattr(request, "request_hash", "sha256:stale"), "request hash"),
        (lambda request: setattr(request, "evaluator_version", "wrong"), "evaluator version"),
        (
            lambda request: setattr(
                request,
                "model",
                request.model.model_copy(
                    update={
                        "joints": (
                            request.model.joints[0].model_copy(
                                update={"axis_direction_x": 1.0}
                            ),
                            request.model.joints[1],
                        )
                    }
                ),
            ),
            "model hash",
        ),
        (
            lambda request: setattr(
                request,
                "configurations",
                (request.configurations[0].model_copy(update={"positions": {"joint-1": 1, "joint-2": 0}}),),
            ),
            "request hash",
        ),
        (
            lambda request: setattr(request, "moving_instance_ids", ("link-2", "link-1")),
            "request hash",
        ),
        (lambda request: setattr(request, "distance_tolerance_mm", 1.0), "request hash"),
    ),
)
def test_execute_revalidates_mutated_request_before_fk_or_measurement(mutate, message):
    request = _request()
    kinematics = _RecordingKinematics()
    provider_calls = 0

    def exact_measure(received_request, transformed):
        nonlocal provider_calls
        provider_calls += 1
        return tuple(
            (moving, stationary, 0.0, 1.0)
            for moving, stationary in received_request.pairs
        )

    mutate(request)

    with pytest.raises(ValueError, match=message):
        _service(exact_measure, kinematics).execute(request, _assembly())

    assert kinematics.calls == []
    assert provider_calls == 0


def test_supplied_identity_mismatches_are_rejected():
    with pytest.raises(ValueError, match="model hash"):
        _request(model_hash="sha256:wrong")
    with pytest.raises(ValueError, match="request hash"):
        _request(request_hash="sha256:wrong")


class _RecordingKinematics:
    def __init__(self):
        self.calls = []
        self.delegate = MultiJointKinematicsService()

    def evaluate(self, assembly, model, configuration):
        self.calls.append((assembly, model, configuration))
        return self.delegate.evaluate(assembly, model, configuration)


class _TamperingKinematics:
    def __init__(self, field):
        self.field = field
        self.delegate = MultiJointKinematicsService()

    def evaluate(self, assembly, model, configuration):
        result = self.delegate.evaluate(assembly, model, configuration)
        replacement = {
            "evaluator_version": "other-forward-kinematics@1.0",
            "model_id": "other-model",
            "result_hash": "sha256:tampered",
        }[self.field]
        return result.model_copy(update={self.field: replacement})


class _TamperingTransient:
    def __init__(self, callback, field):
        self.delegate = TransientAssemblyAnalysisService(callback)
        self.field = field

    def analyze(self, request, transformed):
        result = self.delegate.analyze(request, transformed)
        replacement = {
            "source_assembly_hash": "sha256:tampered-source",
            "transformed_assembly_hash": "sha256:tampered-transformed",
            "sweep_request_hash": "sha256:tampered-request",
            "sample_id": "sha256:tampered-sample",
        }[self.field]
        return result.model_copy(update={self.field: replacement})


def _service(measurement_callback, kinematics=None, transient=None):
    transient = transient or TransientAssemblyAnalysisService(measurement_callback)
    return MultiJointDiscreteCollisionSweepService(
        transient, kinematics_service=kinematics
    )


@pytest.mark.parametrize(
    ("field", "message"),
    (
        ("evaluator_version", "evaluator version"),
        ("model_id", "model ID"),
        ("result_hash", "result hash"),
    ),
)
def test_execute_rejects_inconsistent_fk_result_identity(field, message):
    request = _request()

    with pytest.raises(ValueError, match=message):
        _service(
            lambda received_request, transformed: tuple(
                (moving, stationary, 0.0, 1.0)
                for moving, stationary in received_request.pairs
            ),
            _TamperingKinematics(field),
        ).execute(request, _assembly())


@pytest.mark.parametrize(
    ("field", "message"),
    (
        ("source_assembly_hash", "identity"),
        ("transformed_assembly_hash", "identity"),
        ("sweep_request_hash", "identity"),
        ("sample_id", "identity"),
    ),
)
def test_execute_rejects_inconsistent_transient_result_identity(field, message):
    request = _request()

    def exact_measure(received_request, transformed):
        return tuple(
            (moving, stationary, 0.0, 1.0)
            for moving, stationary in received_request.pairs
        )

    transient = _TamperingTransient(exact_measure, field)
    with pytest.raises(ValueError, match=message):
        _service(exact_measure, transient=transient).execute(request, _assembly())


def test_execute_measures_all_configurations_and_pairs_in_order_without_drift():
    assembly = _assembly()
    request = _request(assembly)
    original_hash = assembly_hash(assembly)
    original_placements = tuple(
        (item.instance_id, item.placement.model_dump(mode="json"))
        for item in assembly.instances
    )
    observed = []

    def exact_measure(received_request: TransientAssemblyAnalysisRequest, transformed):
        observed.append(
            (
                received_request.sample_angle_deg,
                received_request.sample_id,
                received_request.pairs,
                transformed,
            )
        )
        return tuple(
            (moving, stationary, 0.0, 10.0)
            for moving, stationary in received_request.pairs
        )

    kinematics = _RecordingKinematics()
    result = _service(exact_measure, kinematics).execute(request, assembly)
    assert [item[1] for item in observed] == [
        joint_configuration_hash(configuration)
        for configuration in request.configurations
    ]
    assert all(item[0] is None for item in observed)
    assert all(
        item[2] == (("link-1", "base"), ("link-2", "base"))
        for item in observed
    )
    assert len(kinematics.calls) == len(request.configurations)
    assert all(call[0] is assembly for call in kinematics.calls)
    assert assembly_hash(assembly) == original_hash
    assert original_placements == tuple(
        (item.instance_id, item.placement.model_dump(mode="json"))
        for item in assembly.instances
    )
    assert result.continuous_path_verified is False
    assert result.all_positive_clearance is True

    q2_alone = _request(configurations=(request.configurations[1],))
    alone = _service(exact_measure).execute(q2_alone, assembly)
    assert (
        result.configuration_results[1].transformed_assembly_hash
        == alone.configuration_results[0].transformed_assembly_hash
    )
    assert result.configuration_results[1].pair_results == alone.configuration_results[0].pair_results


def test_pair_order_is_full_moving_by_stationary_cartesian_product():
    assembly = _assembly().model_copy(
        update={
            "instances": _assembly().instances
            + (
                CadComponentInstance(
                    instance_id="base-2",
                    part_id="link",
                    placement=CadRigidTransform(y_mm=30),
                ),
            )
        }
    )
    request = _request(
        assembly,
        configurations=(_configuration(**{"joint-1": 0, "joint-2": 0}),),
        moving=("link-1", "link-2"),
        stationary=("base", "base-2"),
    )
    observed_pairs = []

    def exact_measure(received_request, transformed):
        observed_pairs.extend(received_request.pairs)
        return tuple(
            (moving, stationary, 0.0, 1.0)
            for moving, stationary in received_request.pairs
        )

    _service(exact_measure).execute(request, assembly)
    assert observed_pairs == [
        ("link-1", "base"),
        ("link-1", "base-2"),
        ("link-2", "base"),
        ("link-2", "base-2"),
    ]


@pytest.mark.parametrize(
    ("volume", "distance", "classification"),
    (
        (1.0, 10.0, CollisionClassification.INTERFERENCE),
        (0.0, 0.0, CollisionClassification.TOUCHING),
        (0.0, 10.0, CollisionClassification.POSITIVE_CLEARANCE),
    ),
)
def test_per_configuration_and_sweep_summaries_are_explicit(
    volume, distance, classification
):
    request = _request(configurations=(_configuration(**{"joint-1": 0, "joint-2": 0}),))

    def exact_measure(received_request, transformed):
        return tuple(
            (moving, stationary, volume, distance)
            for moving, stationary in received_request.pairs
        )

    result = _service(exact_measure).execute(request, _assembly())
    item = result.configuration_results[0]
    assert item.classification is classification
    assert item.any_interference is (classification is CollisionClassification.INTERFERENCE)
    assert item.any_touching is (classification is CollisionClassification.TOUCHING)
    assert item.all_positive_clearance is (classification is CollisionClassification.POSITIVE_CLEARANCE)
    assert result.any_interference is item.any_interference
    assert result.any_touching is item.any_touching
    assert result.all_positive_clearance is item.all_positive_clearance


def test_sweep_summary_uses_first_minimum_distance_and_interference_indices():
    request = _request(
        configurations=(
            _configuration(**{"joint-1": 0, "joint-2": 0}),
            _configuration(**{"joint-1": 30, "joint-2": 0}),
            _configuration(**{"joint-1": 60, "joint-2": 0}),
        )
    )
    distances = iter((2.0, 1.0, 1.0))
    calls = 0

    def exact_measure(received_request, transformed):
        nonlocal calls
        calls += 1
        distance = next(distances)
        return tuple(
            (moving, stationary, 1.0 if calls == 1 else 0.0, distance)
            for moving, stationary in received_request.pairs
        )

    result = _service(exact_measure).execute(request, _assembly())
    assert result.any_interference is True
    assert result.collision_configuration_indices == (0,)
    assert result.minimum_exact_distance_mm == 1.0
    assert result.minimum_distance_configuration_index == 1


def test_per_configuration_classification_uses_interference_then_touching_precedence():
    request = _request(
        configurations=(_configuration(**{"joint-1": 0, "joint-2": 0}),)
    )

    def exact_measure(received_request, transformed):
        return (
            ("link-1", "base", 0.0, 0.0),
            ("link-2", "base", 1.0, 10.0),
        )

    result = _service(exact_measure).execute(request, _assembly())
    assert result.configuration_results[0].classification is CollisionClassification.INTERFERENCE


def test_malformed_measurement_missing_pair_provider_error_and_later_failure_raise():
    request = _request()
    assembly = _assembly()

    def malformed(received_request, transformed):
        return (("link-1", "base", math.nan, 1.0), ("link-2", "base", 0.0, 1.0))

    with pytest.raises(ValueError, match="finite"):
        _service(malformed).execute(request, assembly)

    def missing_pair(received_request, transformed):
        return (("link-1", "base", 0.0, 1.0),)

    with pytest.raises(ValueError, match="pairs"):
        _service(missing_pair).execute(request, assembly)

    def provider_error(received_request, transformed):
        raise RuntimeError("provider failed")

    with pytest.raises(RuntimeError, match="provider failed"):
        _service(provider_error).execute(request, assembly)

    calls = 0

    def later_failure(received_request, transformed):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("later failure")
        return tuple(
            (moving, stationary, 0.0, 1.0)
            for moving, stationary in received_request.pairs
        )

    with pytest.raises(RuntimeError, match="later failure"):
        _service(later_failure).execute(request, assembly)


def test_execute_rechecks_source_and_partition_against_actual_assembly():
    assembly = _assembly()
    with pytest.raises(ValueError, match="source assembly hash"):
        _service(lambda request, transformed: ()).execute(
            _request(source_assembly_hash="sha256:stale"), assembly
        )
    with pytest.raises(ValueError, match="source assembly ID"):
        _service(lambda request, transformed: ()).execute(
            _request(source_assembly_id="wrong-assembly"), assembly
        )
    with pytest.raises(ValueError, match="classification"):
        _service(lambda request, transformed: ()).execute(
            _request(moving=("link-1",), stationary=("base",)), assembly
        )
    with pytest.raises(ValueError, match="unknown"):
        _service(lambda request, transformed: ()).execute(
            _request(moving=("link-1", "unknown"), stationary=("base", "link-2")),
            assembly,
        )


def test_result_hash_is_deterministic_and_contains_complete_result_identity():
    request = _request()

    def exact_measure(received_request, transformed):
        return tuple(
            (moving, stationary, 0.0, 2.5)
            for moving, stationary in received_request.pairs
        )

    first = _service(exact_measure).execute(request, _assembly())
    second = _service(exact_measure).execute(request, _assembly())
    assert first.result_hash == second.result_hash
    assert first.result_hash.startswith("sha256:")
    assert first.evaluator_version == MULTI_JOINT_EXACT_COLLISION_SWEEP_VERSION

    def changed_measure(received_request, transformed):
        return tuple(
            (moving, stationary, 0.0, 3.5)
            for moving, stationary in received_request.pairs
        )

    changed = _service(changed_measure).execute(request, _assembly())
    assert changed.result_hash != first.result_hash


def test_result_rejects_continuous_path_claim():
    request = _request(configurations=(_configuration(**{"joint-1": 0, "joint-2": 0}),))
    result = _service(
        lambda received_request, transformed: tuple(
            (moving, stationary, 0.0, 2.5)
            for moving, stationary in received_request.pairs
        )
    ).execute(request, _assembly())

    payload = result.model_dump(mode="python")
    payload["continuous_path_verified"] = True
    with pytest.raises(ValueError, match="continuous_path_verified"):
        MultiJointCollisionSweepResult(**payload)
