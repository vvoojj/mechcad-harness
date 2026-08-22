from __future__ import annotations

import hashlib
import json
import math

from pydantic import Field, model_validator

from mechcad_harness.cad_assembly import CadAssemblyProgram, assembly_hash
from mechcad_harness.kinematic_sweep import (
    CadKinematicCollisionPairResult,
    CollisionClassification,
)
from mechcad_harness.models.common import Model
from mechcad_harness.multi_joint_kinematics import (
    EvaluatedJointState,
    InstanceWorldTransform,
    JointConfiguration,
    KinematicModel,
    KinematicForwardKinematicsResult,
    MULTI_JOINT_FORWARD_KINEMATICS_VERSION,
    MultiJointKinematicsService,
    joint_configuration_hash,
    kinematic_model_hash,
    kinematic_forward_kinematics_result_hash,
)
from mechcad_harness.transient_assembly_analysis import (
    TransientAssemblyAnalysisRequest,
    TransientAssemblyAnalysisService,
)


MULTI_JOINT_EXACT_COLLISION_SWEEP_VERSION = (
    "multi-joint-exact-collision-sweep@1.0"
)


def _digest(payload: object) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


class MultiJointCollisionSweepRequest(Model):
    source_assembly_id: str = Field(min_length=1)
    source_assembly_hash: str = Field(min_length=1)
    model: KinematicModel
    configurations: tuple[JointConfiguration, ...] = Field(default_factory=tuple)
    moving_instance_ids: tuple[str, ...] = Field(min_length=1)
    stationary_instance_ids: tuple[str, ...] = Field(min_length=1)
    volume_tolerance_mm3: float = Field(default=1e-9, ge=0)
    distance_tolerance_mm: float = Field(default=1e-7, ge=0)
    evaluator_version: str = MULTI_JOINT_EXACT_COLLISION_SWEEP_VERSION
    model_hash: str = "pending"
    request_hash: str = "pending"

    @model_validator(mode="after")
    def validate_request(self):
        if not self.source_assembly_hash.startswith("sha256:"):
            raise ValueError("source assembly hash must be a sha256 identity")
        if self.evaluator_version != MULTI_JOINT_EXACT_COLLISION_SWEEP_VERSION:
            raise ValueError("evaluator version does not match trusted constant")
        if self.model.evaluator_version != MULTI_JOINT_FORWARD_KINEMATICS_VERSION:
            raise ValueError("kinematic model evaluator version is not trusted")
        if not all(
            math.isfinite(value) and value >= 0
            for value in (self.volume_tolerance_mm3, self.distance_tolerance_mm)
        ):
            raise ValueError("collision tolerances must be finite and non-negative")
        if len(self.configurations) == 0:
            raise ValueError("at least one configuration is required")
        if any(
            configuration.model_id != self.model.model_id
            for configuration in self.configurations
        ):
            raise ValueError("configuration model ID does not match request model")

        all_partition_ids = (
            *self.moving_instance_ids,
            *self.stationary_instance_ids,
        )
        if any(not instance_id for instance_id in all_partition_ids):
            raise ValueError("instance IDs must be non-empty")
        if len(set(self.moving_instance_ids)) != len(self.moving_instance_ids):
            raise ValueError("duplicate moving instance IDs are not allowed")
        if len(set(self.stationary_instance_ids)) != len(
            self.stationary_instance_ids
        ):
            raise ValueError("duplicate stationary instance IDs are not allowed")
        if set(self.moving_instance_ids) & set(self.stationary_instance_ids):
            raise ValueError("moving and stationary instance IDs overlap")

        expected_model_hash = kinematic_model_hash(self.model)
        if self.model_hash == "pending":
            self.model_hash = expected_model_hash
        elif self.model_hash != expected_model_hash:
            raise ValueError("model hash does not match canonical model")

        payload = {
            "source_assembly_id": self.source_assembly_id,
            "source_assembly_hash": self.source_assembly_hash,
            "model_hash": expected_model_hash,
            "configuration_hashes": [
                joint_configuration_hash(configuration)
                for configuration in self.configurations
            ],
            "moving_instance_ids": list(self.moving_instance_ids),
            "stationary_instance_ids": list(self.stationary_instance_ids),
            "volume_tolerance_mm3": self.volume_tolerance_mm3,
            "distance_tolerance_mm": self.distance_tolerance_mm,
            "evaluator_version": MULTI_JOINT_EXACT_COLLISION_SWEEP_VERSION,
        }
        expected_request_hash = _digest(payload)
        if self.request_hash == "pending":
            self.request_hash = expected_request_hash
        elif self.request_hash != expected_request_hash:
            raise ValueError("request hash does not match canonical request")
        return self


class MultiJointCollisionConfigurationResult(Model):
    configuration_index: int = Field(ge=0)
    configuration_hash: str = Field(min_length=1)
    transformed_assembly_hash: str = Field(min_length=1)
    ordered_joint_states: tuple[EvaluatedJointState, ...] = Field(
        default_factory=tuple
    )
    instance_world_transforms: tuple[InstanceWorldTransform, ...] = Field(
        min_length=1
    )
    pair_results: tuple[CadKinematicCollisionPairResult, ...] = Field(
        min_length=1
    )
    classification: CollisionClassification
    any_interference: bool
    any_touching: bool
    all_positive_clearance: bool
    minimum_exact_distance_mm: float = Field(ge=0)


class MultiJointCollisionSweepResult(Model):
    evaluator_version: str = Field(min_length=1)
    source_assembly_hash: str = Field(min_length=1)
    model_hash: str = Field(min_length=1)
    request_hash: str = Field(min_length=1)
    configuration_results: tuple[
        MultiJointCollisionConfigurationResult, ...
    ] = Field(min_length=1)
    any_interference: bool
    any_touching: bool
    all_positive_clearance: bool
    collision_configuration_indices: tuple[int, ...]
    minimum_exact_distance_mm: float = Field(ge=0)
    minimum_distance_configuration_index: int = Field(ge=0)
    continuous_path_verified: bool = False
    result_hash: str = "pending"

    @model_validator(mode="after")
    def validate_discrete_result(self):
        if self.continuous_path_verified:
            raise ValueError("continuous_path_verified must remain False for a discrete sweep")
        return self

_CLASSIFICATION_ORDER = (
    CollisionClassification.INTERFERENCE,
    CollisionClassification.TOUCHING,
    CollisionClassification.POSITIVE_CLEARANCE,
)


def _configuration_classification(
    pair_results: tuple[CadKinematicCollisionPairResult, ...],
) -> CollisionClassification:
    for classification in _CLASSIFICATION_ORDER:
        if any(item.classification is classification for item in pair_results):
            return classification
    raise ValueError("collision pair results must not be empty")


class MultiJointDiscreteCollisionSweepService:
    def __init__(
        self,
        transient_analysis_service: TransientAssemblyAnalysisService,
        kinematics_service: MultiJointKinematicsService | None = None,
    ) -> None:
        self.transient_analysis_service = transient_analysis_service
        self.kinematics_service = kinematics_service or MultiJointKinematicsService()

    @staticmethod
    def collision_pairs(
        request: MultiJointCollisionSweepRequest,
    ) -> tuple[tuple[str, str], ...]:
        return tuple(
            (moving, stationary)
            for moving in request.moving_instance_ids
            for stationary in request.stationary_instance_ids
        )

    @staticmethod
    def _validate_source(
        request: MultiJointCollisionSweepRequest,
        assembly: CadAssemblyProgram,
    ) -> str:
        actual_source_hash = assembly_hash(assembly)
        if request.source_assembly_id != assembly.assembly_id:
            raise ValueError("source assembly ID mismatch")
        if request.source_assembly_hash != actual_source_hash:
            raise ValueError("source assembly hash mismatch")
        if request.model.evaluator_version != MULTI_JOINT_FORWARD_KINEMATICS_VERSION:
            raise ValueError("kinematic model evaluator version is not trusted")
        if request.model_hash != kinematic_model_hash(request.model):
            raise ValueError("model hash mismatch")

        actual_instance_ids = {instance.instance_id for instance in assembly.instances}
        requested_instance_ids = set(
            request.moving_instance_ids
        ) | set(request.stationary_instance_ids)
        if requested_instance_ids != actual_instance_ids:
            unknown = sorted(requested_instance_ids - actual_instance_ids)
            omitted = sorted(actual_instance_ids - requested_instance_ids)
            raise ValueError(
                "collision sweep instance classification mismatch: "
                f"unknown={unknown}, omitted={omitted}"
            )
        return actual_source_hash

    @staticmethod
    def _validate_fk_result(
        fk_result: KinematicForwardKinematicsResult,
        request: MultiJointCollisionSweepRequest,
        configuration: JointConfiguration,
        source_assembly_hash: str,
    ) -> None:
        expected_configuration_hash = joint_configuration_hash(configuration)
        if fk_result.evaluator_version != MULTI_JOINT_FORWARD_KINEMATICS_VERSION:
            raise ValueError("forward-kinematics evaluator version mismatch")
        if fk_result.model_id != request.model.model_id:
            raise ValueError("forward-kinematics model ID mismatch")
        if fk_result.source_assembly_hash != source_assembly_hash:
            raise ValueError("forward-kinematics source assembly hash mismatch")
        if fk_result.model_hash != request.model_hash:
            raise ValueError("forward-kinematics model hash mismatch")
        if fk_result.configuration_hash != expected_configuration_hash:
            raise ValueError("forward-kinematics configuration hash mismatch")
        if fk_result.transformed_assembly_hash != assembly_hash(
            fk_result.transformed_assembly
        ):
            raise ValueError("forward-kinematics transformed assembly hash mismatch")
        if fk_result.result_hash != kinematic_forward_kinematics_result_hash(
            fk_result
        ):
            raise ValueError("forward-kinematics result hash mismatch")

    @staticmethod
    def _pair_results(
        measurements: object,
        pairs: tuple[tuple[str, str], ...],
        request: MultiJointCollisionSweepRequest,
    ) -> tuple[CadKinematicCollisionPairResult, ...]:
        try:
            measurements = tuple(measurements)
            measurement_pairs = tuple(
                (measurement[0], measurement[1]) for measurement in measurements
            )
        except (TypeError, IndexError):
            raise ValueError("exact collision measurements are malformed") from None
        if measurement_pairs != pairs:
            raise ValueError("exact collision measurement pairs do not match sweep inventory")

        pair_results = []
        for measurement in measurements:
            try:
                moving, stationary, volume, distance = measurement
                volume = float(volume)
                distance = float(distance)
            except (TypeError, ValueError):
                raise ValueError("exact collision measurement is malformed") from None
            if not all(
                math.isfinite(value) and value >= 0 for value in (volume, distance)
            ):
                raise ValueError(
                    "exact collision measurements must be finite and non-negative"
                )
            pair_results.append(
                CadKinematicCollisionPairResult(
                    moving_instance_id=moving,
                    stationary_instance_id=stationary,
                    interference_volume_mm3=volume,
                    exact_distance_mm=distance,
                    classification=CollisionClassification.from_measurement(
                        volume,
                        distance,
                        volume_tolerance_mm3=request.volume_tolerance_mm3,
                        distance_tolerance_mm=request.distance_tolerance_mm,
                    ),
                )
            )
        return tuple(pair_results)

    def execute(
        self,
        request: MultiJointCollisionSweepRequest,
        assembly: CadAssemblyProgram,
    ) -> MultiJointCollisionSweepResult:
        request.validate_request()
        source_hash = self._validate_source(request, assembly)
        pairs = self.collision_pairs(request)

        # Complete FK validation precedes any exact measurement, and every call
        # starts from the unchanged source assembly.
        fk_results = tuple(
            self.kinematics_service.evaluate(
                assembly, request.model, configuration
            )
            for configuration in request.configurations
        )
        for configuration, fk_result in zip(
            request.configurations, fk_results, strict=True
        ):
            self._validate_fk_result(
                fk_result, request, configuration, source_hash
            )

        configuration_results = []
        for index, (configuration, fk_result) in enumerate(
            zip(request.configurations, fk_results, strict=True)
        ):
            configuration_hash = joint_configuration_hash(configuration)
            transient_request = TransientAssemblyAnalysisRequest(
                source_assembly_hash=source_hash,
                transformed_assembly_hash=fk_result.transformed_assembly_hash,
                sweep_request_hash=request.request_hash,
                sample_angle_deg=None,
                sample_id=configuration_hash,
                pairs=pairs,
            )
            transient_result = self.transient_analysis_service.analyze(
                transient_request, fk_result.transformed_assembly
            )
            if (
                transient_result.source_assembly_hash != source_hash
                or transient_result.transformed_assembly_hash
                != fk_result.transformed_assembly_hash
                or transient_result.sweep_request_hash != request.request_hash
                or transient_result.sample_angle_deg is not None
                or transient_result.sample_id != configuration_hash
            ):
                raise ValueError("transient exact result identity mismatch")
            pair_results = self._pair_results(
                transient_result.measurements, pairs, request
            )
            classification = _configuration_classification(pair_results)
            configuration_results.append(
                MultiJointCollisionConfigurationResult(
                    configuration_index=index,
                    configuration_hash=configuration_hash,
                    transformed_assembly_hash=fk_result.transformed_assembly_hash,
                    ordered_joint_states=fk_result.ordered_joint_states,
                    instance_world_transforms=fk_result.instance_world_transforms,
                    pair_results=pair_results,
                    classification=classification,
                    any_interference=any(
                        item.classification is CollisionClassification.INTERFERENCE
                        for item in pair_results
                    ),
                    any_touching=any(
                        item.classification is CollisionClassification.TOUCHING
                        for item in pair_results
                    ),
                    all_positive_clearance=all(
                        item.classification
                        is CollisionClassification.POSITIVE_CLEARANCE
                        for item in pair_results
                    ),
                    minimum_exact_distance_mm=min(
                        item.exact_distance_mm for item in pair_results
                    ),
                )
            )

        configuration_results = tuple(configuration_results)
        minimum = min(
            configuration_results,
            key=lambda item: item.minimum_exact_distance_mm,
        )
        result = MultiJointCollisionSweepResult(
            evaluator_version=MULTI_JOINT_EXACT_COLLISION_SWEEP_VERSION,
            source_assembly_hash=source_hash,
            model_hash=request.model_hash,
            request_hash=request.request_hash,
            configuration_results=configuration_results,
            any_interference=any(
                item.any_interference for item in configuration_results
            ),
            any_touching=any(item.any_touching for item in configuration_results),
            all_positive_clearance=all(
                item.all_positive_clearance for item in configuration_results
            ),
            collision_configuration_indices=tuple(
                item.configuration_index
                for item in configuration_results
                if item.any_interference
            ),
            minimum_exact_distance_mm=minimum.minimum_exact_distance_mm,
            minimum_distance_configuration_index=minimum.configuration_index,
            continuous_path_verified=False,
        )
        return result.model_copy(
            update={
                "result_hash": _digest(
                    result.model_dump(mode="json", exclude={"result_hash"})
                )
            }
        )
