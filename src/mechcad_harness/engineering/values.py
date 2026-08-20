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


class AzimuthDriveMountInterfaceValue(Model):
    kind: Literal["azimuth.drive_mount_interface"]
    component_id: str = Field(min_length=1)
    coordinate_convention: Literal["interface-center; mounting plane XY; +Z housing-to-mating-plate; +X source-defined reference; +Y right-handed"] = "interface-center; mounting plane XY; +Z housing-to-mating-plate; +X source-defined reference; +Y right-handed"
    in_plane_alignment: Literal["aligned-with-plate-axes"] = "aligned-with-plate-axes"
    frame_reference_id: str = Field(min_length=1)
    mount_points: tuple[dict, ...] = Field(min_length=1)
    central_keepout_diameter_mm: float | None = Field(default=None, gt=0)
    central_required_mating_opening_diameter_mm: float | None = Field(default=None, gt=0)
    manufacturer_required_central_radial_clearance_mm: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_mount_points(self):
        ids = [point.get("hole_id") for point in self.mount_points]
        if any(not isinstance(item, str) or not item.strip() for item in ids) or len(ids) != len(set(ids)):
            raise ValueError("mount point IDs must be unique")
        return self

    def to_domain(self):
        from mechcad_harness.azimuth_mount_plate import AzimuthDriveMountInterface
        return AzimuthDriveMountInterface.model_validate(self.model_dump(exclude={"kind"}))


class PlateThicknessPolicyValue(Model):
    allowed_thicknesses_mm: tuple[float, ...]
    minimum_thickness_mm: float


class AzimuthMotorMountPlateDesignRequirementsValue(Model):
    kind: Literal["azimuth.mount_plate_design_requirements"]
    minimum_edge_margin_mm: float
    minimum_hole_ligament_mm: float
    plate_thickness_policy: PlateThicknessPolicyValue
    mounting_hole_radial_clearance_mm: float | None = None
    central_radial_clearance_mm: float | None = None
    provenance: str = "M7B1B_TEST_FIXTURE_ONLY"

    @classmethod
    def from_domain(cls, requirements):
        return cls(kind="azimuth.mount_plate_design_requirements", **requirements.model_dump(mode="json"))

    def to_domain(self):
        from mechcad_harness.azimuth_mount_plate import AzimuthMotorMountPlateDesignRequirements, PlateThicknessPolicy
        payload = self.model_dump(exclude={"kind"})
        payload["plate_thickness_policy"] = PlateThicknessPolicy.model_validate(payload["plate_thickness_policy"])
        return AzimuthMotorMountPlateDesignRequirements(**payload)


AuthoritativeValue = Annotated[Union[OutputAngularSpeedValue, MotorCharacteristicsValue, OutputInterfaceValue, PackagingEnvelopeValue, AzimuthDriveMountInterfaceValue, AzimuthMotorMountPlateDesignRequirementsValue], Field(discriminator="kind")]
