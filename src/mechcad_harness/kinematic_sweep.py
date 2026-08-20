from __future__ import annotations

import math
import hashlib
import json
from enum import StrEnum

from pydantic import Field, model_validator

from mechcad_harness.cad_assembly import CadComponentInstance, CadRigidTransform, assembly_hash
from mechcad_harness.cad_assembly import CadAssemblyProgram
from mechcad_harness.models.common import Model
from mechcad_harness.transient_assembly_analysis import TransientAssemblyAnalysisRequest


RIGID_BODY_COLLISION_SWEEP_VERSION = "rigid-body-collision-sweep@1.0"


class CollisionClassification(StrEnum):
    INTERFERENCE = "interference"
    TOUCHING = "touching"
    POSITIVE_CLEARANCE = "positive_clearance"

    @classmethod
    def from_measurement(cls, common_volume_mm3: float, distance_mm: float, *, volume_tolerance_mm3: float = 1e-9, distance_tolerance_mm: float = 1e-7):
        if common_volume_mm3 > volume_tolerance_mm3:
            return cls.INTERFERENCE
        if distance_mm <= distance_tolerance_mm:
            return cls.TOUCHING
        return cls.POSITIVE_CLEARANCE


class SweepAggregateClassification(StrEnum):
    COLLISION_PRESENT = "collision_present"
    TOUCHING_PRESENT = "touching_present"
    COLLISION_FREE = "collision_free"


class CadKinematicCollisionPairResult(Model):
    moving_instance_id: str = Field(min_length=1)
    stationary_instance_id: str = Field(min_length=1)
    interference_volume_mm3: float = Field(ge=0)
    exact_distance_mm: float = Field(ge=0)
    classification: CollisionClassification


class CadKinematicSweepSample(Model):
    angle_deg: float
    transformed_assembly_hash: str = Field(min_length=1)
    pair_results: tuple[CadKinematicCollisionPairResult, ...] = Field(min_length=1)
    maximum_interference_volume_mm3: float = Field(ge=0)
    minimum_exact_distance_mm: float = Field(ge=0)
    classification: CollisionClassification


class CadKinematicSweepResult(Model):
    request_hash: str = Field(min_length=1)
    source_assembly_hash: str = Field(min_length=1)
    sweep_version: str = RIGID_BODY_COLLISION_SWEEP_VERSION
    samples: tuple[CadKinematicSweepSample, ...] = Field(min_length=1)
    aggregate_classification: SweepAggregateClassification
    first_collision_angle_deg: float | None = None
    worst_interference_angle_deg: float | None = None
    worst_interference_volume_mm3: float = Field(ge=0)
    minimum_clearance_angle_deg: float
    minimum_clearance_mm: float = Field(ge=0)
    continuous_sweep_verified: bool = False
    result_hash: str = "pending"

    @classmethod
    def from_samples(cls, request, samples):
        if tuple(sample.angle_deg for sample in samples) != request.sample_angles_deg:
            raise ValueError("sample angles must preserve request order")
        first_collision = next((sample.angle_deg for sample in samples if sample.classification is CollisionClassification.INTERFERENCE), None)
        worst = max(samples, key=lambda sample: sample.maximum_interference_volume_mm3)
        minimum = min(samples, key=lambda sample: sample.minimum_exact_distance_mm)
        aggregate = SweepAggregateClassification.COLLISION_PRESENT if first_collision is not None else (SweepAggregateClassification.TOUCHING_PRESENT if any(sample.classification is CollisionClassification.TOUCHING for sample in samples) else SweepAggregateClassification.COLLISION_FREE)
        result = cls(
            request_hash=request.request_hash,
            source_assembly_hash=request.source_assembly_hash,
            sweep_version=request.sweep_version,
            samples=tuple(samples),
            aggregate_classification=aggregate,
            first_collision_angle_deg=first_collision,
            worst_interference_angle_deg=worst.angle_deg,
            worst_interference_volume_mm3=worst.maximum_interference_volume_mm3,
            minimum_clearance_angle_deg=minimum.angle_deg,
            minimum_clearance_mm=minimum.minimum_exact_distance_mm,
        )
        payload = result.model_dump(mode="json", exclude={"result_hash"})
        return result.model_copy(update={"result_hash": f"sha256:{hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}"})


class RevoluteAxis(Model):
    origin_x_mm: float
    origin_y_mm: float
    origin_z_mm: float
    direction_x: float
    direction_y: float
    direction_z: float
    frame_id: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def normalize_direction(cls, data):
        data = dict(data)
        values = tuple(float(data[name]) for name in ("origin_x_mm", "origin_y_mm", "origin_z_mm", "direction_x", "direction_y", "direction_z"))
        if any(not math.isfinite(value) for value in values):
            raise ValueError("revolute axis values must be finite")
        direction = values[3:]
        norm = math.sqrt(sum(value * value for value in direction))
        if norm <= 1e-12:
            raise ValueError("revolute axis direction must be non-zero")
        data["direction_x"], data["direction_y"], data["direction_z"] = (value / norm for value in direction)
        return data

    @property
    def origin(self):
        return (self.origin_x_mm, self.origin_y_mm, self.origin_z_mm)

    @property
    def direction(self):
        return (self.direction_x, self.direction_y, self.direction_z)


class CadKinematicSweepRequest(Model):
    source_assembly_id: str = Field(min_length=1)
    source_assembly_hash: str = Field(min_length=1)
    axis: RevoluteAxis
    sample_angles_deg: tuple[float, ...] = Field(min_length=1)
    moving_instance_ids: tuple[str, ...] = Field(min_length=1)
    stationary_instance_ids: tuple[str, ...] = Field(min_length=1)
    volume_tolerance_mm3: float = 1e-9
    distance_tolerance_mm: float = 1e-7
    sweep_version: str = RIGID_BODY_COLLISION_SWEEP_VERSION
    request_hash: str = "pending"

    @model_validator(mode="after")
    def validate_request(self):
        if not self.source_assembly_hash.startswith("sha256:"):
            raise ValueError("source assembly hash must be a sha256 identity")
        if any(not math.isfinite(angle) for angle in self.sample_angles_deg):
            raise ValueError("sample angles must be finite")
        if len(set(self.moving_instance_ids)) != len(self.moving_instance_ids) or len(set(self.stationary_instance_ids)) != len(self.stationary_instance_ids):
            raise ValueError("duplicate instance IDs are not allowed")
        if set(self.moving_instance_ids) & set(self.stationary_instance_ids):
            raise ValueError("moving and stationary instance IDs overlap")
        if any(not identity for identity in (*self.moving_instance_ids, *self.stationary_instance_ids)):
            raise ValueError("instance IDs must be non-empty")
        if not all(math.isfinite(value) and value >= 0 for value in (self.volume_tolerance_mm3, self.distance_tolerance_mm)):
            raise ValueError("collision tolerances must be finite and non-negative")
        payload = self.model_dump(mode="json", exclude={"request_hash"})
        digest = f"sha256:{hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}"
        if self.request_hash == "pending":
            self.request_hash = digest
        elif self.request_hash != digest:
            raise ValueError("request hash does not match canonical request")
        return self


def _quaternion_multiply(first, second):
    aw, ax, ay, az = first
    bw, bx, by, bz = second
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def _rotation_quaternion(axis: RevoluteAxis, angle_deg: float):
    angle = math.radians(float(angle_deg) % 360)
    half = angle / 2
    sin_half = math.sin(half)
    return (math.cos(half), axis.direction_x * sin_half, axis.direction_y * sin_half, axis.direction_z * sin_half)


def _rotate_vector(vector, quaternion):
    pure = (0.0, *vector)
    conjugate = (quaternion[0], -quaternion[1], -quaternion[2], -quaternion[3])
    return _quaternion_multiply(_quaternion_multiply(quaternion, pure), conjugate)[1:]


def transform_moving_instances(instances: tuple[CadComponentInstance, ...], axis: RevoluteAxis, angle_deg: float) -> tuple[CadComponentInstance, ...]:
    if not math.isfinite(float(angle_deg)):
        raise ValueError("sweep angle must be finite")
    rotation = _rotation_quaternion(axis, angle_deg)
    transformed = []
    for instance in instances:
        offset = tuple(value - origin for value, origin in zip((instance.placement.x_mm, instance.placement.y_mm, instance.placement.z_mm), axis.origin, strict=True))
        rotated = _rotate_vector(offset, rotation)
        placement = CadRigidTransform(
            x_mm=axis.origin_x_mm + rotated[0],
            y_mm=axis.origin_y_mm + rotated[1],
            z_mm=axis.origin_z_mm + rotated[2],
            rotation_quaternion=_quaternion_multiply(rotation, instance.placement.rotation_quaternion),
        )
        transformed.append(instance.model_copy(update={"placement": placement}))
    return tuple(transformed)


def transformed_assembly_program(assembly: CadAssemblyProgram, axis: RevoluteAxis, angle_deg: float, moving_instance_ids: tuple[str, ...], stationary_instance_ids: tuple[str, ...]) -> CadAssemblyProgram:
    source = {instance.instance_id: instance for instance in assembly.instances}
    requested = set(moving_instance_ids) | set(stationary_instance_ids)
    if requested != set(source):
        missing = requested - set(source)
        omitted = set(source) - requested
        raise ValueError(f"sweep instance classification mismatch: unknown={sorted(missing)}, omitted={sorted(omitted)}")
    moving = tuple(source[identity] for identity in moving_instance_ids)
    transformed = {instance.instance_id: instance for instance in transform_moving_instances(moving, axis, angle_deg)}
    instances = tuple(transformed.get(instance.instance_id, instance) for instance in assembly.instances)
    return assembly.model_copy(update={"assembly_id": f"{assembly.assembly_id}_sweep_{float(angle_deg):g}", "instances": instances})


class CadKinematicSweepService:
    def __init__(self, transient_analysis_service=None):
        self.transient_analysis_service = transient_analysis_service

    def validate_source(self, request: CadKinematicSweepRequest, assembly: CadAssemblyProgram) -> None:
        if request.source_assembly_id != assembly.assembly_id:
            raise ValueError("source assembly ID mismatch")
        if request.source_assembly_hash != assembly_hash(assembly):
            raise ValueError("source assembly hash mismatch")
        source_ids = {instance.instance_id for instance in assembly.instances}
        request_ids = set(request.moving_instance_ids) | set(request.stationary_instance_ids)
        if request_ids != source_ids:
            unknown = sorted(request_ids - source_ids)
            omitted = sorted(source_ids - request_ids)
            raise ValueError(f"sweep instance classification mismatch: unknown={unknown}, omitted={omitted}")

    @staticmethod
    def collision_pairs(request: CadKinematicSweepRequest) -> tuple[tuple[str, str], ...]:
        return tuple((moving, stationary) for moving in request.moving_instance_ids for stationary in request.stationary_instance_ids)

    def execute(self, request: CadKinematicSweepRequest, assembly: CadAssemblyProgram) -> CadKinematicSweepResult:
        if self.transient_analysis_service is None:
            raise ValueError("a transient assembly analysis service is required")
        self.validate_source(request, assembly)
        pairs = self.collision_pairs(request)
        samples = []
        for angle in request.sample_angles_deg:
            transformed = transformed_assembly_program(assembly, request.axis, angle, request.moving_instance_ids, request.stationary_instance_ids)
            transient_request = TransientAssemblyAnalysisRequest(
                source_assembly_hash=request.source_assembly_hash,
                transformed_assembly_hash=assembly_hash(transformed),
                sweep_request_hash=request.request_hash,
                sample_angle_deg=angle,
                pairs=pairs,
            )
            measurements = self.transient_analysis_service.analyze(transient_request, transformed).measurements
            pair_results = tuple(
                CadKinematicCollisionPairResult(
                    moving_instance_id=moving,
                    stationary_instance_id=stationary,
                    interference_volume_mm3=volume,
                    exact_distance_mm=distance,
                    classification=CollisionClassification.from_measurement(volume, distance, volume_tolerance_mm3=request.volume_tolerance_mm3, distance_tolerance_mm=request.distance_tolerance_mm),
                )
                for moving, stationary, volume, distance in measurements
            )
            if tuple((item.moving_instance_id, item.stationary_instance_id) for item in pair_results) != pairs:
                raise ValueError("exact collision measurement pairs do not match the sweep inventory")
            samples.append(CadKinematicSweepSample(
                angle_deg=angle,
                transformed_assembly_hash=assembly_hash(transformed),
                pair_results=pair_results,
                maximum_interference_volume_mm3=max(item.interference_volume_mm3 for item in pair_results),
                minimum_exact_distance_mm=min(item.exact_distance_mm for item in pair_results),
                classification=max((item.classification for item in pair_results), key=lambda value: (CollisionClassification.INTERFERENCE, CollisionClassification.TOUCHING, CollisionClassification.POSITIVE_CLEARANCE).index(value)),
            ))
        return CadKinematicSweepResult.from_samples(request, tuple(samples))
