from typing import Annotated, Literal, Union

from pydantic import Field, model_validator

from pydantic import BaseModel, ConfigDict


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AngularSpeedQuantity(Model):
    source_value: float
    source_unit: Literal["deg/s", "rad/s"]
    canonical_value_rad_s: float = Field(gt=0)


class OutputAngularSpeedValue(Model):
    kind: Literal["transmission.output_angular_speed"]
    value_rad_s: float = Field(gt=0)


class MotorCharacteristicsValue(Model):
    kind: Literal["transmission.motor_characteristics"]
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


class OutputInterfaceValue(Model):
    kind: Literal["transmission.output_interface"]
    interface_type: str = Field(min_length=1)
    shaft_diameter_mm: float | None = Field(default=None, gt=0)
    torque_transfer_description: str = Field(min_length=1)


class PackagingEnvelopeValue(Model):
    kind: Literal["transmission.packaging_envelope"]
    max_length_mm: float = Field(gt=0)
    max_width_mm: float = Field(gt=0)
    max_height_mm: float = Field(gt=0)
    mounting_description: str = Field(min_length=1)


AuthoritativeValue = Annotated[Union[OutputAngularSpeedValue, MotorCharacteristicsValue, OutputInterfaceValue, PackagingEnvelopeValue], Field(discriminator="kind")]
