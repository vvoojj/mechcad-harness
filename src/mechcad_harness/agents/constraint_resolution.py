import hashlib
import json
import math
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Union
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, model_validator

from mechcad_harness.engineering.keys import SupportedConstraintKey
from mechcad_harness.engineering.values import AuthoritativeValue, AzimuthDriveMountInterfaceValue, AzimuthMotorMountPlateDesignRequirementsValue, MotorCharacteristicsValue, OutputAngularSpeedValue, OutputInterfaceValue, PackagingEnvelopeValue, YagiPayloadCarrierRequirementsValue
from mechcad_harness.models.common import Model
from .constraint_requests import ConstraintRequestLifecycle


class OutputAngularSpeedAnswer(Model):
    kind: Literal["transmission.output_angular_speed"] = "transmission.output_angular_speed"
    value: float = Field(gt=0)
    unit: Literal["deg/s", "rad/s"]


class MotorCharacteristicsAnswer(Model):
    kind: Literal["transmission.motor_characteristics"] = "transmission.motor_characteristics"
    motor_id: str = Field(min_length=1)
    speed_min_rpm: float = Field(ge=0)
    speed_max_rpm: float = Field(gt=0)
    continuous_torque_nm: float = Field(gt=0)
    peak_torque_nm: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self):
        if self.speed_min_rpm > self.speed_max_rpm or self.peak_torque_nm < self.continuous_torque_nm:
            raise ValueError("motor characteristics ranges are invalid")
        return self


class OutputInterfaceAnswer(Model):
    kind: Literal["transmission.output_interface"] = "transmission.output_interface"
    interface_type: str = Field(min_length=1)
    shaft_diameter_mm: float | None = Field(default=None, gt=0)
    torque_transfer_description: str = Field(min_length=1)


class PackagingEnvelopeAnswer(Model):
    kind: Literal["transmission.packaging_envelope"] = "transmission.packaging_envelope"
    max_length_mm: float = Field(gt=0)
    max_width_mm: float = Field(gt=0)
    max_height_mm: float = Field(gt=0)
    mounting_description: str = Field(min_length=1)


class AzimuthDriveMountInterfaceAnswer(AzimuthDriveMountInterfaceValue):
    kind: Literal["azimuth.drive_mount_interface"] = "azimuth.drive_mount_interface"


class AzimuthMotorMountPlateDesignRequirementsAnswer(AzimuthMotorMountPlateDesignRequirementsValue):
    kind: Literal["azimuth.mount_plate_design_requirements"] = "azimuth.mount_plate_design_requirements"


class YagiPayloadCarrierRequirementsAnswer(YagiPayloadCarrierRequirementsValue):
    kind: Literal["yagi.payload_carrier_requirements"] = "yagi.payload_carrier_requirements"


TypedResolutionAnswer = Annotated[Union[OutputAngularSpeedAnswer, MotorCharacteristicsAnswer, OutputInterfaceAnswer, PackagingEnvelopeAnswer, AzimuthDriveMountInterfaceAnswer, AzimuthMotorMountPlateDesignRequirementsAnswer, YagiPayloadCarrierRequirementsAnswer], Field(discriminator="kind")]  # type: ignore


class ConstraintResolutionAnswer(Model):
    request_id: str = Field(min_length=1)
    answer: TypedResolutionAnswer


class ConstraintResolutionBatchCommand(Model):
    command_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    engineering_scope_id: str = Field(min_length=1)
    source_revision: int = Field(gt=0)
    source_state_hash: str = Field(min_length=1)
    answers: tuple[ConstraintResolutionAnswer, ...] = Field(min_length=1)
    resolver_type: str = Field(min_length=1)
    resolver_id: str = Field(min_length=1)
    received_at: datetime

    @model_validator(mode="after")
    def reject_duplicate_requests(self):
        ids = [item.request_id for item in self.answers]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate request IDs")
        return self


class ResolutionStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    STALE = "stale"
    CONFLICT = "conflict"


class ConstraintResolutionRecord(Model):
    resolution_id: str = Field(min_length=1)
    source_command_id: str = Field(min_length=1)
    source_constraint_request_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    engineering_scope_id: str = Field(min_length=1)
    source_revision: int = Field(gt=0)
    source_state_hash: str = Field(min_length=1)
    resolver_type: str = Field(min_length=1)
    resolver_id: str = Field(min_length=1)
    key: SupportedConstraintKey
    source_answer: TypedResolutionAnswer
    canonical_value: AuthoritativeValue
    status: ResolutionStatus
    validated_at: datetime

    @model_validator(mode="after")
    def validate_key_value(self):
        if self.canonical_value.kind != self.key.value:
            raise ValueError("resolution key/canonical value mismatch")
        if self.source_answer.kind != self.key.value:
            raise ValueError("resolution key/source answer mismatch")
        return self


class ConstraintResolutionMaterializationResult(Model):
    command_id: str = Field(min_length=1)
    resolution_ids: tuple[str, ...] = ()
    resolution_records: tuple[ConstraintResolutionRecord, ...] = ()


class ConstraintResolutionStore:
    def __init__(self, workspace):
        from mechcad_harness.runs.persistence import RunStore
        self.store = RunStore(workspace)

    def _path(self, project_id, run_id, directory, record_id):
        return self.store.run_dir(project_id, run_id) / "agents" / directory / f"{record_id}.json"

    def write_command(self, run_id: str, command: ConstraintResolutionBatchCommand) -> None:
        self.store._write(self._path(command.project_id, run_id, "constraint_resolution_commands", command.command_id), command.model_dump(mode="json"), exclusive=True)

    def write_resolution(self, run_id: str, resolution: ConstraintResolutionRecord) -> None:
        self.store._write(self._path(resolution.project_id, run_id, "constraint_resolutions", resolution.resolution_id), resolution.model_dump(mode="json"), exclusive=True)

    def load_command(self, project_id, run_id, command_id):
        return self.store._read(self._path(project_id, run_id, "constraint_resolution_commands", command_id), ConstraintResolutionBatchCommand)

    def load_resolution(self, project_id, run_id, resolution_id):
        return self.store._read(self._path(project_id, run_id, "constraint_resolutions", resolution_id), ConstraintResolutionRecord)

    def load_accepted_by_source_request(self, project_id, run_id, source_constraint_request_id):
        directory = self.store.run_dir(project_id, run_id) / "agents" / "constraint_resolutions"
        if not directory.exists():
            return ()
        records = []
        for path in sorted(directory.glob("*.json"), key=lambda item: item.name):
            record = self.store._read(path, ConstraintResolutionRecord)
            if record.source_constraint_request_id == source_constraint_request_id and record.status is ResolutionStatus.ACCEPTED:
                records.append(record)
        if len(records) > 1:
            raise ValueError("multiple accepted resolutions for source request")
        return tuple(records)


class ConstraintResolutionMaterializer:
    def __init__(self, request_store, resolution_store=None):
        self.request_store = request_store
        self.resolution_store = resolution_store or ConstraintResolutionStore(request_store.store.workspace)

    def materialize(self, command: ConstraintResolutionBatchCommand, *, run_id: str):
        requests = []
        for answer in command.answers:
            request = self.request_store.load(command.project_id, run_id, answer.request_id)
            if request.project_id != command.project_id or request.run_id != run_id or request.engineering_scope_id != command.engineering_scope_id or request.request.revision != command.source_revision or request.request.state_hash != command.source_state_hash or request.key.value != answer.answer.kind or request.lifecycle is not ConstraintRequestLifecycle.DISCOVERED:
                raise ValueError("resolution request binding or answer type mismatch")
            requests.append((request, answer))
        prepared = []
        for request, answer in sorted(requests, key=lambda item: item[0].request.id):
            key = SupportedConstraintKey(request.key.value)
            canonical = canonical_value_for_answer(key, answer.answer)
            identity = resolution_id(project_id=command.project_id, source_request_id=request.request.id, source_revision=command.source_revision, source_state_hash=command.source_state_hash, answer=answer.answer)
            record = ConstraintResolutionRecord(resolution_id=identity, source_command_id=command.command_id, source_constraint_request_id=request.request.id, project_id=command.project_id, engineering_scope_id=command.engineering_scope_id, source_revision=command.source_revision, source_state_hash=command.source_state_hash, resolver_type=command.resolver_type, resolver_id=command.resolver_id, key=key, source_answer=answer.answer, canonical_value=canonical, status=ResolutionStatus.ACCEPTED, validated_at=command.received_at)
            accepted = self.resolution_store.load_accepted_by_source_request(command.project_id, run_id, request.request.id)
            if accepted and not canonical_record_equivalent(accepted[0], record.model_copy(update={"source_command_id": accepted[0].source_command_id})):
                raise ValueError("conflicting accepted resolution for source request")
            prepared.append((identity, record, accepted[0] if accepted else None))
        records = []
        for identity, record, accepted in prepared:
            try:
                existing = self.resolution_store.load_resolution(command.project_id, run_id, identity)
            except Exception:
                existing = None
            if existing is None:
                if accepted is not None:
                    existing = accepted
                else:
                    self.resolution_store.write_resolution(run_id, record)
                    existing = self.resolution_store.load_resolution(command.project_id, run_id, identity)
            elif not canonical_record_equivalent(existing, record.model_copy(update={"source_command_id": existing.source_command_id})):
                raise ValueError("conflicting immutable resolution record")
            loaded = self.resolution_store.load_resolution(command.project_id, run_id, existing.resolution_id)
            if not canonical_record_equivalent(loaded, existing):
                raise ValueError("persisted resolution changed during materialization")
            records.append(loaded)
        return tuple(records)

    def materialize_batch(self, command: ConstraintResolutionBatchCommand, *, run_id: str) -> ConstraintResolutionMaterializationResult:
        try:
            existing_command = self.resolution_store.load_command(command.project_id, run_id, command.command_id)
        except Exception:
            existing_command = None
        if existing_command is None:
            self.resolution_store.write_command(run_id, command)
        elif _canonical_json(existing_command.model_dump(mode="json")) != _canonical_json(command.model_dump(mode="json")):
            raise ValueError("conflicting immutable resolution command")
        records = self.materialize(command, run_id=run_id)
        result = ConstraintResolutionMaterializationResult(command_id=command.command_id, resolution_ids=tuple(record.resolution_id for record in records), resolution_records=records)
        if tuple(record.resolution_id for record in result.resolution_records) != result.resolution_ids:
            raise ValueError("resolution result identity mismatch")
        return result


def _canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def canonical_record_equivalent(left: ConstraintResolutionRecord, right: ConstraintResolutionRecord) -> bool:
    return _canonical_json(left.model_dump(mode="json")) == _canonical_json(right.model_dump(mode="json"))


def command_id(*, project_id, engineering_scope_id, source_revision, source_state_hash, answers, resolver_type, resolver_id, received_at=None) -> str:
    ordered = sorted((item.request_id, item.answer.kind, item.answer) for item in answers)
    identity = _canonical_json({"project_id": project_id, "engineering_scope_id": engineering_scope_id, "source_revision": source_revision, "source_state_hash": source_state_hash, "answers": ordered, "resolver_type": resolver_type, "resolver_id": resolver_id})
    return f"CMD-{uuid5(NAMESPACE_URL, identity)}"


def resolution_id(*, project_id, source_request_id, source_revision, source_state_hash, answer) -> str:
    identity = _canonical_json({"project_id": project_id, "source_request_id": source_request_id, "source_revision": source_revision, "source_state_hash": source_state_hash, "answer": answer.model_dump(mode="json")})
    return f"CRRES-{uuid5(NAMESPACE_URL, identity)}"


def canonical_value_for_answer(key: SupportedConstraintKey, answer):
    if key is SupportedConstraintKey.OUTPUT_ANGULAR_SPEED:
        if not isinstance(answer, OutputAngularSpeedAnswer):
            raise ValueError("answer type does not match key")
        value = answer.value * math.pi / 180 if answer.unit == "deg/s" else answer.value
        return OutputAngularSpeedValue(kind=key.value, value_rad_s=value)
    if key is SupportedConstraintKey.MOTOR_CHARACTERISTICS:
        if not isinstance(answer, MotorCharacteristicsAnswer):
            raise ValueError("answer type does not match key")
        return MotorCharacteristicsValue(**answer.model_dump())
    if key is SupportedConstraintKey.OUTPUT_INTERFACE:
        if not isinstance(answer, OutputInterfaceAnswer):
            raise ValueError("answer type does not match key")
        return OutputInterfaceValue(**answer.model_dump())
    if key is SupportedConstraintKey.AZIMUTH_DRIVE_MOUNT_INTERFACE:
        if not isinstance(answer, AzimuthDriveMountInterfaceAnswer):
            raise ValueError("answer type does not match key")
        return AzimuthDriveMountInterfaceValue(**answer.model_dump())
    if key is SupportedConstraintKey.AZIMUTH_MOUNT_PLATE_DESIGN_REQUIREMENTS:
        if not isinstance(answer, AzimuthMotorMountPlateDesignRequirementsAnswer):
            raise ValueError("answer type does not match key")
        return AzimuthMotorMountPlateDesignRequirementsValue(**answer.model_dump())
    if key is SupportedConstraintKey.YAGI_PAYLOAD_CARRIER_REQUIREMENTS:
        if not isinstance(answer, YagiPayloadCarrierRequirementsAnswer):
            raise ValueError("answer type does not match key")
        return YagiPayloadCarrierRequirementsValue(**answer.model_dump())
    if not isinstance(answer, PackagingEnvelopeAnswer):
        raise ValueError("answer type does not match key")
    return PackagingEnvelopeValue(**answer.model_dump())


def parameter_id(*, project_id, scope_id, anchor_kind, anchor_id, key: SupportedConstraintKey) -> str:
    identity = "\n".join((project_id, scope_id, anchor_kind, anchor_id, key.value))
    return f"PARAM-{uuid5(NAMESPACE_URL, identity)}"
