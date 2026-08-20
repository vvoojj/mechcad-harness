from datetime import datetime

from pydantic import Field, field_validator, model_validator
from typing import Literal
from mechcad_harness.engineering.keys import SupportedConstraintKey
from mechcad_harness.engineering.values import AuthoritativeValue, MotorCharacteristicsValue, OutputAngularSpeedValue, OutputInterfaceValue, PackagingEnvelopeValue

from .common import Model, NamedModel, utc_now


class Requirement(NamedModel):
    description: str = Field(min_length=1)


class Component(NamedModel):
    description: str | None = None


class Assembly(NamedModel):
    component_ids: list[str] = Field(default_factory=list)


class MaterialProfile(NamedModel):
    material: str = Field(min_length=1)


class Interface(NamedModel):
    component_ids: list[str] = Field(default_factory=list)


class Constraint(NamedModel):
    expression: str = Field(min_length=1)


class LoadCase(NamedModel):
    description: str = Field(min_length=1)


class AuthoritativeAnchor(Model):
    kind: Literal["requirement", "constraint"]
    id: str = Field(min_length=1)


class AuthoritativeParameter(Model):
    id: str = Field(min_length=1)
    anchor: AuthoritativeAnchor
    scope_id: str = Field(min_length=1)
    key: SupportedConstraintKey
    value: AuthoritativeValue
    source_resolution_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_binding(self):
        if getattr(self.value, "kind", None) != self.key.value:
            raise ValueError("authoritative parameter key/value mismatch")
        expected = {
            SupportedConstraintKey.OUTPUT_ANGULAR_SPEED: ("requirement", "REQ-TRANSMISSION-OUTPUT-SPEED"),
            SupportedConstraintKey.MOTOR_CHARACTERISTICS: ("requirement", "REQ-TRANSMISSION-MOTOR-CHARACTERISTICS"),
            SupportedConstraintKey.OUTPUT_INTERFACE: ("constraint", "CON-TRANSMISSION-OUTPUT-INTERFACE"),
            SupportedConstraintKey.PACKAGING_ENVELOPE: ("constraint", "CON-TRANSMISSION-PACKAGING-ENVELOPE"),
            SupportedConstraintKey.AZIMUTH_DRIVE_MOUNT_INTERFACE: ("constraint", "CON-AZIMUTH-DRIVE-MOUNT-INTERFACE"),
        }[self.key]
        if (self.anchor.kind, self.anchor.id) != expected:
            raise ValueError("authoritative parameter key/anchor mismatch")
        return self


class DesignState(Model):
    id: str = Field(min_length=1)
    revision: int = Field(gt=0)
    created_at: datetime = Field(default_factory=utc_now)
    requirements: list[Requirement] = Field(default_factory=list)
    components: list[Component] = Field(default_factory=list)
    assemblies: list[Assembly] = Field(default_factory=list)
    materials: list[MaterialProfile] = Field(default_factory=list)
    interfaces: list[Interface] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    load_cases: list[LoadCase] = Field(default_factory=list)
    authoritative_parameters: list[AuthoritativeParameter] = Field(default_factory=list)

    @field_validator("created_at")
    @classmethod
    def require_utc_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value
