from __future__ import annotations

import hashlib
import math
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from mechcad_harness.candidates.models import (
    CandidateDesignVariable,
    ComponentPropertyAuthority,
    ComponentSpecificationSnapshot,
    MechanicalDesignCandidate,
)
from mechcad_harness.models.common import Model
from mechcad_harness.state.hashing import canonical_json


_HASH_PREFIX = "sha256:"


def _hash(value: Any, identity_field: str) -> str:
    payload = value.model_dump(mode="json") if isinstance(value, Model) else value
    payload = dict(payload)
    payload.pop(identity_field, None)
    return _HASH_PREFIX + hashlib.sha256(canonical_json(payload)).hexdigest()


def _require_hash(value: str) -> str:
    if len(value) != 71 or not value.startswith(_HASH_PREFIX):
        raise ValueError("must be a sha256 hash")
    if any(character not in "0123456789abcdef" for character in value[7:]):
        raise ValueError("must be a sha256 hash")
    return value


def _scalar_value_hash(value: float, unit: str) -> str:
    return _HASH_PREFIX + hashlib.sha256(
        canonical_json({"value": value, "unit": unit})
    ).hexdigest()


def _require_unit(value: SourceBoundScalar, expected: str, name: str) -> None:
    if value.unit != expected:
        raise ValueError(f"{name} must use {expected}")


def _require_path(value: str) -> str:
    if not value.startswith("/") or value == "/" or "//" in value or "~" in value:
        raise ValueError("must be a literal non-root canonical path")
    return value


def _require_scalar(value: SourceBoundScalar, expected: str, name: str, *, positive: bool = False, nonnegative: bool = False) -> None:
    _require_unit(value, expected, name)
    if positive and value.value <= 0:
        raise ValueError(f"{name} must be positive")
    if nonnegative and value.value < 0:
        raise ValueError(f"{name} must be nonnegative")


class DriveArchitecture(StrEnum):
    DIRECT_DRIVE = "direct_drive"
    EXTERNAL_SPUR_REDUCTION = "external_spur_reduction"


class EngineeringCheckStatus(StrEnum):
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNRESOLVED = "unresolved"


class DriveAdmissibility(StrEnum):
    ADMISSIBLE = "admissible"
    INADMISSIBLE = "inadmissible"
    UNRESOLVED = "unresolved"


class InputProvenanceKind(StrEnum):
    SOURCE_AUTHORITY = "source_authority"
    POLICY_ASSUMPTION = "policy_assumption"


class RevoluteDriveModel(Model):
    model_config = {"frozen": True, "extra": "forbid"}


class SourceBoundScalar(RevoluteDriveModel):
    value: float
    unit: Literal["N*m", "rpm", "V", "mm", "N", "MPa", "N/mm^2", "deg", "1"]
    provenance: InputProvenanceKind
    source_path: str | None = None
    source_value_hash: str | None = None

    @field_validator("value", mode="before")
    @classmethod
    def validate_finite(cls, value: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("scalar value must be numeric")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("scalar value must be finite")
        return value

    @model_validator(mode="after")
    def validate_provenance(self) -> SourceBoundScalar:
        expected_source_value_hash = _scalar_value_hash(self.value, self.unit)
        if self.provenance is InputProvenanceKind.SOURCE_AUTHORITY:
            if self.source_path is None:
                raise ValueError("source-authoritative scalar requires a canonical source path")
            _require_path(self.source_path)
            if self.source_value_hash is None:
                object.__setattr__(self, "source_value_hash", expected_source_value_hash)
            elif self.source_value_hash != expected_source_value_hash:
                raise ValueError("source scalar value hash mismatch")
        elif self.source_path is not None:
            raise ValueError("policy assumptions cannot claim a canonical source path")
        elif self.source_value_hash is not None:
            raise ValueError("policy assumptions cannot claim a source scalar value hash")
        return self


class TrustedCanonicalScalarSourceBinding(RevoluteDriveModel):
    """Explicit scalar evidence supplied by a trusted canonical-source adapter.

    The ordinary candidate source binding hashes the complete state record. It
    cannot prove a number when that record is composite, so M12-3 requires this
    separate, explicitly supplied scalar representation.
    """

    schema_version: Literal["m12-3-trusted-canonical-scalar@1"] = "m12-3-trusted-canonical-scalar@1"
    source_path: str
    source_record_hash: str
    value: float
    unit: Literal["N*m", "rpm", "V", "mm", "N", "MPa", "N/mm^2", "deg", "1"]
    source_identity: str = Field(min_length=1)
    source_value_hash: str = "pending"
    binding_hash: str = "pending"

    _validate_path = field_validator("source_path")(_require_path)
    _validate_record_hash = field_validator("source_record_hash")(_require_hash)
    _validate_source_hash = field_validator("source_value_hash")(
        lambda value: value if value == "pending" else _require_hash(value)
    )

    @field_validator("value", mode="before")
    @classmethod
    def validate_finite(cls, value: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("trusted scalar value must be numeric")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("trusted scalar value must be finite")
        return value

    @model_validator(mode="after")
    def validate_binding(self) -> TrustedCanonicalScalarSourceBinding:
        expected_source_value_hash = _scalar_value_hash(self.value, self.unit)
        if self.source_value_hash == "pending":
            object.__setattr__(self, "source_value_hash", expected_source_value_hash)
        elif self.source_value_hash != expected_source_value_hash:
            raise ValueError("source scalar value hash mismatch")
        expected_binding_hash = _hash(self, "binding_hash")
        if self.binding_hash == "pending":
            object.__setattr__(self, "binding_hash", expected_binding_hash)
        elif self.binding_hash != expected_binding_hash:
            raise ValueError("trusted scalar binding hash mismatch")
        return self


class ConsumedPropertyBinding(RevoluteDriveModel):
    component_instance_id: str = Field(min_length=1)
    specification_hash: str
    property_key: str = Field(min_length=1)
    property_hash: str
    source_identity: str = Field(min_length=1)
    authority: ComponentPropertyAuthority

    _validate_hashes = field_validator("specification_hash", "property_hash")(_require_hash)


class StaticOutputShaftDesignLoadCase(RevoluteDriveModel):
    design_torque: SourceBoundScalar
    transverse_force_y: SourceBoundScalar | None = None
    transverse_force_z: SourceBoundScalar | None = None
    derive_transverse_load_from_spur_mesh: bool = False

    @model_validator(mode="after")
    def validate_load_case(self) -> StaticOutputShaftDesignLoadCase:
        _require_scalar(self.design_torque, "N*m", "design torque", positive=True)
        explicit_y = self.transverse_force_y is not None
        explicit_z = self.transverse_force_z is not None
        if explicit_y != explicit_z:
            raise ValueError("transverse force vector requires both components")
        if explicit_y and self.derive_transverse_load_from_spur_mesh:
            raise ValueError("load case cannot contain both explicit and derived transverse loads")
        if explicit_y:
            _require_scalar(self.transverse_force_y, "N", "transverse force y")
            _require_scalar(self.transverse_force_z, "N", "transverse force z")
        elif not self.derive_transverse_load_from_spur_mesh:
            raise ValueError("load case requires an explicit force vector or spur-load derivation")
        return self


class ShaftSupportGeometry(RevoluteDriveModel):
    support_a_x: SourceBoundScalar
    support_b_x: SourceBoundScalar
    load_plane_x: SourceBoundScalar

    @model_validator(mode="after")
    def validate_order(self) -> ShaftSupportGeometry:
        for coordinate, name in (
            (self.support_a_x, "support A coordinate"),
            (self.support_b_x, "support B coordinate"),
            (self.load_plane_x, "load-plane coordinate"),
        ):
            _require_scalar(coordinate, "mm", name)
        if self.support_a_x.value >= self.support_b_x.value:
            raise ValueError("support A must precede support B")
        if not self.support_a_x.value <= self.load_plane_x.value <= self.support_b_x.value:
            raise ValueError("load plane must lie between the supports")
        return self


class RevoluteDriveEngineeringRequirements(RevoluteDriveModel):
    required_output_speed: SourceBoundScalar
    design_load_case: StaticOutputShaftDesignLoadCase
    required_voltage: SourceBoundScalar | None = None
    required_peak_torque: SourceBoundScalar | None = None
    efficiency: SourceBoundScalar | None = None
    safety_factor: SourceBoundScalar | None = None
    shaft_yield_strength: SourceBoundScalar | None = None
    shaft_support_geometry: ShaftSupportGeometry | None = None
    require_nominal_interface_compatibility: bool = False
    trusted_source_scalar_bindings: tuple[TrustedCanonicalScalarSourceBinding, ...]
    requirements_hash: str = "pending"

    @model_validator(mode="after")
    def validate_requirements(self) -> RevoluteDriveEngineeringRequirements:
        paths = tuple(binding.source_path for binding in self.trusted_source_scalar_bindings)
        if len(set(paths)) != len(paths):
            raise ValueError("trusted scalar source-binding paths must be unique")
        _require_scalar(self.required_output_speed, "rpm", "required output speed", nonnegative=True)
        if self.required_voltage is not None:
            _require_scalar(self.required_voltage, "V", "required voltage", positive=True)
        if self.required_peak_torque is not None:
            _require_scalar(self.required_peak_torque, "N*m", "required peak torque", positive=True)
        if self.efficiency is not None:
            _require_scalar(self.efficiency, "1", "efficiency", positive=True)
            if self.efficiency.value > 1:
                raise ValueError("efficiency must not exceed one")
        if self.safety_factor is not None:
            _require_scalar(self.safety_factor, "1", "safety factor", positive=True)
        if self.shaft_yield_strength is not None:
            _require_scalar(self.shaft_yield_strength, "MPa", "shaft yield strength", positive=True)
        expected = _hash(self, "requirements_hash")
        if self.requirements_hash == "pending":
            object.__setattr__(self, "requirements_hash", expected)
        elif self.requirements_hash != expected:
            raise ValueError("requirements hash mismatch")
        return self


class RevoluteDriveTemplateInput(RevoluteDriveModel):
    architecture: DriveArchitecture
    joint_id: str = Field(min_length=1)
    axis_frame_reference: str | None = None
    motor_instance_id: str | None = None
    motor_specification: ComponentSpecificationSnapshot | None = None
    shaft_instance_id: str | None = None
    shaft_specification: ComponentSpecificationSnapshot | None = None
    bearing_a_instance_id: str | None = None
    bearing_a_specification: ComponentSpecificationSnapshot | None = None
    bearing_b_instance_id: str | None = None
    bearing_b_specification: ComponentSpecificationSnapshot | None = None
    hub_instance_id: str | None = None
    hub_specification: ComponentSpecificationSnapshot | None = None
    mount_instance_id: str | None = None
    mount_specification: ComponentSpecificationSnapshot | None = None
    support_mount_instance_ids: tuple[str, ...] = ()
    support_mount_specifications: tuple[ComponentSpecificationSnapshot, ...] = ()
    driven_body_instance_id: str | None = None
    driven_body_specification: ComponentSpecificationSnapshot | None = None
    driver_gear_instance_id: str | None = None
    driver_gear_specification: ComponentSpecificationSnapshot | None = None
    driven_gear_instance_id: str | None = None
    driven_gear_specification: ComponentSpecificationSnapshot | None = None
    design_variables: tuple[CandidateDesignVariable, ...] = ()

    @field_validator(
        "joint_id",
        "axis_frame_reference",
        "motor_instance_id",
        "shaft_instance_id",
        "bearing_a_instance_id",
        "bearing_b_instance_id",
        "hub_instance_id",
        "mount_instance_id",
        "driven_body_instance_id",
        "driver_gear_instance_id",
        "driven_gear_instance_id",
    )
    @classmethod
    def validate_identifier(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or any(character.isspace() for character in value)):
            raise ValueError("template identifiers must be nonempty and whitespace-free")
        return value

    @field_validator("support_mount_instance_ids")
    @classmethod
    def validate_support_mount_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() or any(character.isspace() for character in item) for item in value):
            raise ValueError("template identifiers must be nonempty and whitespace-free")
        return value

    @model_validator(mode="after")
    def validate_instance_ids(self) -> RevoluteDriveTemplateInput:
        ids = (
            *(item for item in (
                self.motor_instance_id,
                self.shaft_instance_id,
                self.bearing_a_instance_id,
                self.bearing_b_instance_id,
                self.hub_instance_id,
                self.mount_instance_id,
                self.driven_body_instance_id,
            ) if item is not None),
            *self.support_mount_instance_ids,
            *((self.driver_gear_instance_id,) if self.driver_gear_instance_id else ()),
            *((self.driven_gear_instance_id,) if self.driven_gear_instance_id else ()),
        )
        if len(ids) != len(set(ids)):
            raise ValueError("template instance IDs must be unique")
        return self


class RevoluteDriveConstructionOutcome(RevoluteDriveModel):
    candidate: MechanicalDesignCandidate | None = None
    status: DriveAdmissibility
    reason: str | None = None

    @model_validator(mode="after")
    def validate_construction_state(self) -> RevoluteDriveConstructionOutcome:
        if self.candidate is None and self.status is not DriveAdmissibility.UNRESOLVED:
            raise ValueError("construction without a candidate must be unresolved")
        if self.candidate is not None and self.status is DriveAdmissibility.UNRESOLVED:
            raise ValueError("unresolved construction cannot contain a candidate")
        if self.status is DriveAdmissibility.UNRESOLVED and (self.reason is None or not self.reason.strip()):
            raise ValueError("unresolved construction requires a reason")
        return self


class EngineeringCheck(RevoluteDriveModel):
    check_id: str = Field(min_length=1)
    status: EngineeringCheckStatus
    reason: str | None = None
    consumed_property_bindings: tuple[ConsumedPropertyBinding, ...] = ()
    consumed_requirement_paths: tuple[str, ...] = ()
    calculation_id: str = "m12-3.revolute-drive"
    calculation_version: str = "1"

    @model_validator(mode="after")
    def validate_check(self) -> EngineeringCheck:
        if self.status is EngineeringCheckStatus.UNRESOLVED and (self.reason is None or not self.reason.strip()):
            raise ValueError("unresolved check requires a reason")
        for path in self.consumed_requirement_paths:
            _require_path(path)
        return self


class RevoluteDriveAdmissibilityResult(RevoluteDriveModel):
    schema_version: Literal["revolute-drive-admissibility@1"] = "revolute-drive-admissibility@1"
    candidate_hash: str
    source_binding_hash: str
    synthesis_request_hash: str
    synthesis_policy_hash: str
    requirements_hash: str
    design_variables: tuple[CandidateDesignVariable, ...] = ()
    consumed_property_bindings: tuple[ConsumedPropertyBinding, ...] = ()
    calculation_id: str = "m12-3.revolute-drive"
    calculation_version: str = "1"
    checks: tuple[EngineeringCheck, ...] = Field(min_length=1)
    status: DriveAdmissibility | None = None
    result_hash: str = "pending"

    _validate_hashes = field_validator(
        "candidate_hash",
        "source_binding_hash",
        "synthesis_request_hash",
        "synthesis_policy_hash",
        "requirements_hash",
    )(_require_hash)

    @model_validator(mode="after")
    def validate_result(self) -> RevoluteDriveAdmissibilityResult:
        statuses = {check.status for check in self.checks}
        if EngineeringCheckStatus.VIOLATED in statuses:
            expected_status = DriveAdmissibility.INADMISSIBLE
        elif EngineeringCheckStatus.UNRESOLVED in statuses:
            expected_status = DriveAdmissibility.UNRESOLVED
        else:
            expected_status = DriveAdmissibility.ADMISSIBLE
        if self.status is not None and self.status is not expected_status:
            raise ValueError("admissibility status does not match required checks")
        object.__setattr__(self, "status", expected_status)
        expected_hash = _hash(self, "result_hash")
        if self.result_hash == "pending":
            object.__setattr__(self, "result_hash", expected_hash)
        elif self.result_hash != expected_hash:
            raise ValueError("result hash mismatch")
        return self


def admissibility_result_hash(result: RevoluteDriveAdmissibilityResult) -> str:
    return _hash(result, "result_hash")


__all__ = [
    "ConsumedPropertyBinding",
    "DriveAdmissibility",
    "DriveArchitecture",
    "EngineeringCheck",
    "EngineeringCheckStatus",
    "InputProvenanceKind",
    "RevoluteDriveAdmissibilityResult",
    "RevoluteDriveConstructionOutcome",
    "RevoluteDriveEngineeringRequirements",
    "RevoluteDriveTemplateInput",
    "ShaftSupportGeometry",
    "SourceBoundScalar",
    "TrustedCanonicalScalarSourceBinding",
    "StaticOutputShaftDesignLoadCase",
    "admissibility_result_hash",
]
